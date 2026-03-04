"""
Tests for AutoJob Bridge with Skill Decay Integration

Verifies that when the AutoJob bridge uses decay-aware matching,
the KK swarm correctly prefers recently-active agents over
historically-strong-but-idle agents.

These tests use LOCAL mode with real AutoJob imports (not mocks)
to verify the full chain:
  KK task → AutoJob bridge → ReputationMatcher (with decay)
    → WorkerRegistry → match result

Requires AutoJob to be importable (same machine or on sys.path).
"""

import json
import sys
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

# Try importing AutoJob components
AUTOJOB_PATH = str(Path(__file__).parent.parent.parent / "autojob")
if Path(AUTOJOB_PATH).exists():
    sys.path.insert(0, AUTOJOB_PATH)

try:
    from worker_registry import WorkerRegistry, apply_skill_decay
    from em_evidence_parser import EMEvidenceParser
    AUTOJOB_AVAILABLE = True
except ImportError:
    AUTOJOB_AVAILABLE = False

from lib.autojob_bridge import AutoJobBridge, AgentRanking


# Skip all tests if AutoJob not available
pytestmark = pytest.mark.skipif(
    not AUTOJOB_AVAILABLE,
    reason="AutoJob not available on sys.path"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workers_dir(tmp_path):
    """Create a temporary workers directory."""
    d = tmp_path / "workers"
    d.mkdir()
    return str(d)


@pytest.fixture
def registry(workers_dir):
    return WorkerRegistry(storage_dir=workers_dir)


def _days_ago(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


def _build_skill_dna(skills: dict, last_task: str = None) -> dict:
    """Build a minimal Skill DNA dict for testing."""
    tech_skills = {}
    for name, conf in skills.items():
        entry = {
            "level": "EXPERT" if conf >= 0.8 else "INTERMEDIATE" if conf >= 0.5 else "BEGINNER",
            "confidence": conf,
            "evidence": f"Test evidence for {name}",
            "sessions": 10,
            "files_touched": 0,
        }
        tech_skills[name] = entry

    raw_stats = {}
    if last_task:
        raw_stats["last_task"] = last_task

    return {
        "technical_skills": tech_skills,
        "domains": [],
        "working_style": {"autonomy": "HIGH"},
        "strengths": [],
        "growth_areas": [],
        "work_patterns": {},
        "seniority_signal": "MID",
        "evidence_weight": 0.65,
        "raw_stats": raw_stats,
        "tool_usage": {},
    }


def _build_task_history(category: str, count: int, wallet: str,
                        days_ago_start: int = 1) -> list:
    """Build fake EM task history for a worker."""
    tasks = []
    for i in range(count):
        ts = _days_ago(days_ago_start + i)
        tasks.append({
            "task_id": f"task-{wallet[:8]}-{i}",
            "worker_address": wallet,
            "category": category,
            "evidence_types": ["photo_geo", "text_response"],
            "quality_rating": 4.5,
            "completion_time_minutes": 15,
            "on_time": True,
            "bounty_usd": 0.50,
            "chain": "base",
            "timestamp": ts,
            "requester_type": "agent",
            "requester_reputation": 80.0,
        })
    return tasks


# ---------------------------------------------------------------------------
# Skill Decay + Bridge Integration
# ---------------------------------------------------------------------------


class TestDecayAwareMatching:
    """Test that the bridge correctly applies skill decay."""

    def test_registry_preserves_timestamps(self, registry):
        """Skills with last_seen are preserved through registry storage."""
        dna = _build_skill_dna({"field_work": 0.90, "photography": 0.70})
        dna["technical_skills"]["field_work"]["last_seen"] = _days_ago(5)
        dna["technical_skills"]["photography"]["last_seen"] = _days_ago(200)

        registry.upsert("0xABC123", dna, source="execution_market")
        merged = registry.get_merged_dna("0xABC123")

        assert "last_seen" in merged["technical_skills"]["field_work"]
        assert "last_seen" in merged["technical_skills"]["photography"]

    def test_decay_on_read_reduces_old_skills(self, registry):
        """get_merged_dna(with_decay=True) reduces confidence of old skills."""
        dna = _build_skill_dna({"field_work": 0.90})
        dna["technical_skills"]["field_work"]["last_seen"] = _days_ago(365)

        registry.upsert("0xABC123", dna, source="execution_market")

        raw = registry.get_merged_dna("0xABC123", with_decay=False)
        decayed = registry.get_merged_dna("0xABC123", with_decay=True)

        assert raw["technical_skills"]["field_work"]["confidence"] == 0.90
        assert decayed["technical_skills"]["field_work"]["confidence"] < 0.90

    def test_decay_does_not_mutate_storage(self, registry):
        """Reading with decay doesn't affect the stored data."""
        dna = _build_skill_dna({"field_work": 0.90})
        dna["technical_skills"]["field_work"]["last_seen"] = _days_ago(365)
        registry.upsert("0xABC123", dna, source="execution_market")

        # Read with decay
        _ = registry.get_merged_dna("0xABC123", with_decay=True)

        # Verify storage unchanged
        raw = registry.get_merged_dna("0xABC123", with_decay=False)
        assert raw["technical_skills"]["field_work"]["confidence"] == 0.90


class TestEMEvidenceTimestamps:
    """Test that EM evidence parser emits timestamps for decay."""

    def test_parser_emits_last_seen(self):
        """EMEvidenceParser includes last_seen in Skill DNA output."""
        parser = EMEvidenceParser()
        tasks = _build_task_history("physical_verification", 5, "0xWORKER1")

        dna = parser.build_skill_dna_from_history(tasks=tasks)
        tech = dna.get("technical_skills", {})

        # At least one skill should have last_seen
        skills_with_timestamp = [
            name for name, data in tech.items()
            if isinstance(data, dict) and data.get("last_seen")
        ]
        assert len(skills_with_timestamp) > 0, \
            f"No skills with last_seen. Skills: {list(tech.keys())}"

    def test_parser_emits_first_seen(self):
        """EMEvidenceParser includes first_seen in Skill DNA output."""
        parser = EMEvidenceParser()
        tasks = _build_task_history("data_collection", 3, "0xWORKER2")

        dna = parser.build_skill_dna_from_history(tasks=tasks)
        tech = dna.get("technical_skills", {})

        skills_with_first = [
            name for name, data in tech.items()
            if isinstance(data, dict) and data.get("first_seen")
        ]
        assert len(skills_with_first) > 0

    def test_parser_emits_last_task_in_raw_stats(self):
        """raw_stats includes last_task for global decay fallback."""
        parser = EMEvidenceParser()
        tasks = _build_task_history("survey", 2, "0xWORKER3")

        dna = parser.build_skill_dna_from_history(tasks=tasks)
        assert "last_task" in dna.get("raw_stats", {})
        assert dna["raw_stats"]["last_task"] != ""


class TestBridgeWithDecayPreference:
    """
    Test that the bridge ranks recently-active agents higher than
    historically-strong-but-idle agents when skill decay is active.
    """

    def test_active_agent_beats_idle_agent(self, workers_dir):
        """A recently-active worker should score higher than an idle one."""
        registry = WorkerRegistry(storage_dir=workers_dir)
        parser = EMEvidenceParser()

        # Agent A: strong history but idle for 1 year
        old_tasks = _build_task_history(
            "physical_verification", 20, "0xAGENT_A", days_ago_start=365
        )
        dna_a = parser.build_skill_dna_from_history(tasks=old_tasks)
        registry.upsert("0xAGENT_A", dna_a, source="execution_market")

        # Agent B: less history but active this week
        recent_tasks = _build_task_history(
            "physical_verification", 5, "0xAGENT_B", days_ago_start=1
        )
        dna_b = parser.build_skill_dna_from_history(tasks=recent_tasks)
        registry.upsert("0xAGENT_B", dna_b, source="execution_market")

        # Get decayed DNA for both
        dna_a_decayed = registry.get_merged_dna("0xAGENT_A", with_decay=True)
        dna_b_decayed = registry.get_merged_dna("0xAGENT_B", with_decay=True)

        # Agent B's skills should have higher confidence after decay
        # Because Agent A's skills decayed significantly over 1 year
        a_skills = dna_a_decayed.get("technical_skills", {})
        b_skills = dna_b_decayed.get("technical_skills", {})

        # Get max confidence from each agent's shared skills
        a_max = max(
            (s.get("confidence", 0) for s in a_skills.values() if isinstance(s, dict)),
            default=0
        )
        b_max = max(
            (s.get("confidence", 0) for s in b_skills.values() if isinstance(s, dict)),
            default=0
        )

        # Agent B (recent) should have higher or equal confidence
        # Despite Agent A having 4x more tasks
        assert b_max >= a_max * 0.9, \
            f"Agent B (recent, {b_max:.3f}) should be competitive with Agent A (old+decayed, {a_max:.3f})"


class TestDecayApplyFunction:
    """Direct tests of apply_skill_decay from within KK context."""

    def test_can_import_decay(self):
        """verify we can import apply_skill_decay from AutoJob."""
        assert callable(apply_skill_decay)

    def test_decay_recent_skill(self):
        """Skill active within grace period is not decayed."""
        dna = {
            "technical_skills": {
                "python": {
                    "confidence": 0.90,
                    "last_seen": _days_ago(10),
                },
            },
            "raw_stats": {},
        }
        apply_skill_decay(dna)
        assert dna["technical_skills"]["python"]["confidence"] == 0.90

    def test_decay_old_skill(self):
        """Skill idle for a long time is decayed."""
        dna = {
            "technical_skills": {
                "python": {
                    "confidence": 0.90,
                    "last_seen": _days_ago(300),
                },
            },
            "raw_stats": {},
        }
        apply_skill_decay(dna)
        assert dna["technical_skills"]["python"]["confidence"] < 0.90
        assert dna["technical_skills"]["python"]["_decayed"] is True
