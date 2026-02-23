"""
Tests for coordinator_service.py enhanced matching integration.

Validates that the coordinator correctly uses the 5-factor performance
tracker for agent-task matching, and that legacy mode still works.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.performance_tracker import AgentPerformance
from services.coordinator_service import (
    compute_skill_match,
    load_agent_skills,
    load_performance_profiles,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspaces_dir(tmp_path):
    """Create a mock workspaces directory with agent profiles."""
    ws_dir = tmp_path / "workspaces"

    agents = {
        "kk-alice": {
            "soul_skills": ["research", "defi", "data analysis"],
            "profile": {"top_skills": [{"skill": "research"}, {"skill": "DeFi"}]},
            "performance": {
                "agent_name": "kk-alice",
                "tasks_completed": 15,
                "tasks_attempted": 18,
                "tasks_failed": 3,
                "avg_rating_received": 85.0,
                "rating_count": 12,
                "total_earned_usd": 2.50,
                "category_completions": {"knowledge_access": 10, "simple_action": 5},
                "category_attempts": {"knowledge_access": 12, "simple_action": 6},
                "chain_tasks": {"base": 10, "polygon": 5},
            },
        },
        "kk-bob": {
            "soul_skills": ["photography", "verification", "gps"],
            "profile": {"top_skills": [{"skill": "photography"}, {"skill": "verification"}]},
            "performance": {
                "agent_name": "kk-bob",
                "tasks_completed": 5,
                "tasks_attempted": 10,
                "tasks_failed": 5,
                "avg_rating_received": 60.0,
                "rating_count": 4,
                "total_earned_usd": 0.50,
                "category_completions": {"digital_physical": 4, "verification": 1},
                "category_attempts": {"digital_physical": 8, "verification": 2},
                "chain_tasks": {"polygon": 5},
            },
        },
        "kk-charlie": {
            "soul_skills": [],
            "profile": {},
            "performance": None,  # No performance data (new agent)
        },
    }

    for name, config in agents.items():
        agent_dir = ws_dir / name
        data_dir = agent_dir / "data"
        data_dir.mkdir(parents=True)

        # Write profile.json
        if config["profile"]:
            (data_dir / "profile.json").write_text(json.dumps(config["profile"]))

        # Write performance.json
        if config["performance"]:
            (data_dir / "performance.json").write_text(json.dumps(config["performance"]))

        # Write SOUL.md
        soul_content = "# Agent\n\n## Skills\n"
        for skill in config["soul_skills"]:
            soul_content += f"- **{skill}** (General)\n"
        soul_content += "\n## Personality\nFriendly\n"
        (agent_dir / "SOUL.md").write_text(soul_content)

    return ws_dir


@pytest.fixture
def workspaces_dir_with_notes(tmp_path):
    """Create workspaces with daily notes for extraction."""
    ws_dir = tmp_path / "workspaces"

    agent_dir = ws_dir / "kk-dana" / "memory" / "notes"
    agent_dir.mkdir(parents=True)

    notes = """# 2026-02-20

## Activity
- [COMPLETED] task-001 category:simple_action chain:base bounty:$0.05
- [COMPLETED] task-002 category:knowledge_access chain:polygon bounty:$0.10
- [FAILED] task-003 reason:expired category:verification
- [RATED] 4/5 by kk-coordinator
- [EARNED] $0.15 from tasks
- [APPLIED] task-004 category:simple_action
"""
    (agent_dir / "2026-02-20.md").write_text(notes)

    return ws_dir


# ---------------------------------------------------------------------------
# Tests: load_agent_skills
# ---------------------------------------------------------------------------


class TestLoadAgentSkills:
    def test_loads_from_profile_json(self, workspaces_dir):
        skills = load_agent_skills(workspaces_dir, "kk-alice")
        assert "research" in skills
        assert "defi" in skills

    def test_loads_from_soul_md_fallback(self, tmp_path):
        """When no profile.json, falls back to SOUL.md."""
        ws_dir = tmp_path / "workspaces"
        agent_dir = ws_dir / "kk-test"
        agent_dir.mkdir(parents=True)

        soul = "# Agent\n\n## Skills\n- **coding** (Tech)\n- **writing** (Creative)\n\n## Other\n"
        (agent_dir / "SOUL.md").write_text(soul)

        skills = load_agent_skills(ws_dir, "kk-test")
        assert "coding" in skills
        assert "writing" in skills

    def test_returns_empty_for_missing(self, workspaces_dir):
        skills = load_agent_skills(workspaces_dir, "kk-nonexistent")
        assert skills == set()

    def test_agent_without_skills(self, workspaces_dir):
        # kk-charlie has no profile data
        skills = load_agent_skills(workspaces_dir, "kk-charlie")
        assert isinstance(skills, set)

    def test_tries_prefixed_name(self, tmp_path):
        """If agent_name doesn't match, tries kk- prefix."""
        ws_dir = tmp_path / "workspaces"
        agent_dir = ws_dir / "kk-test"
        (agent_dir / "data").mkdir(parents=True)
        (agent_dir / "data" / "profile.json").write_text(
            json.dumps({"top_skills": [{"skill": "testing"}]})
        )

        skills = load_agent_skills(ws_dir, "test")
        assert "testing" in skills


# ---------------------------------------------------------------------------
# Tests: compute_skill_match (legacy)
# ---------------------------------------------------------------------------


class TestComputeSkillMatch:
    def test_no_skills_low_score(self):
        score = compute_skill_match(set(), "Research task", "Do research on DeFi")
        assert score == 0.1

    def test_matching_skills(self):
        skills = {"research", "defi"}
        score = compute_skill_match(skills, "DeFi Research Needed", "Research DeFi trends")
        assert score > 0.5

    def test_no_match(self):
        skills = {"photography", "gps"}
        score = compute_skill_match(skills, "DeFi Research", "Analyze yield strategies")
        assert score == 0.0

    def test_kk_tagged_task(self):
        skills = {"photography"}
        score = compute_skill_match(skills, "[KK Data] Generic Task", "Any agent can do this")
        assert score == 0.3

    def test_single_skill_match(self):
        skills = {"research", "defi", "analysis"}
        score = compute_skill_match(skills, "Need research", "Research needed")
        assert 0.0 < score <= 1.0

    def test_all_skills_match(self):
        skills = {"a", "b"}
        score = compute_skill_match(skills, "a b task", "a b description")
        assert score == 1.0


# ---------------------------------------------------------------------------
# Tests: load_performance_profiles
# ---------------------------------------------------------------------------


class TestLoadPerformanceProfiles:
    def test_loads_json_profiles(self, workspaces_dir):
        profiles = load_performance_profiles(workspaces_dir)
        assert "kk-alice" in profiles
        assert profiles["kk-alice"].tasks_completed == 15
        assert profiles["kk-alice"].tasks_attempted == 18

    def test_alice_reliability(self, workspaces_dir):
        profiles = load_performance_profiles(workspaces_dir)
        alice = profiles["kk-alice"]
        # completion_rate = 15/18 ≈ 0.833
        assert 0.8 < alice.completion_rate < 0.9

    def test_bob_lower_reliability(self, workspaces_dir):
        profiles = load_performance_profiles(workspaces_dir)
        bob = profiles["kk-bob"]
        # completion_rate = 5/10 = 0.5
        assert bob.completion_rate == 0.5

    def test_new_agent_neutral(self, workspaces_dir):
        profiles = load_performance_profiles(workspaces_dir)
        charlie = profiles["kk-charlie"]
        # No data → neutral 0.5
        assert charlie.completion_rate == 0.5
        assert charlie.reliability_score == 0.5

    def test_category_completions(self, workspaces_dir):
        profiles = load_performance_profiles(workspaces_dir)
        alice = profiles["kk-alice"]
        assert alice.category_completions.get("knowledge_access") == 10
        assert alice.category_strength("knowledge_access") > 0.8

    def test_chain_experience(self, workspaces_dir):
        profiles = load_performance_profiles(workspaces_dir)
        alice = profiles["kk-alice"]
        assert alice.chain_experience("base") > alice.chain_experience("arbitrum")

    def test_loads_from_notes(self, workspaces_dir_with_notes):
        profiles = load_performance_profiles(workspaces_dir_with_notes)
        assert "kk-dana" in profiles
        dana = profiles["kk-dana"]
        assert dana.tasks_completed == 2
        assert dana.tasks_failed == 1

    def test_empty_dir(self, tmp_path):
        ws = tmp_path / "empty"
        ws.mkdir()
        profiles = load_performance_profiles(ws)
        assert profiles == {}


# ---------------------------------------------------------------------------
# Tests: Enhanced matching selection
# ---------------------------------------------------------------------------


class TestEnhancedMatchingSelection:
    """Test that the coordinator correctly selects agents via enhanced matching."""

    def test_alice_preferred_for_research(self, workspaces_dir):
        """Alice (high reliability + research skills) beats Bob for research tasks."""
        from lib.performance_tracker import rank_agents_for_task

        profiles = load_performance_profiles(workspaces_dir)
        skills_map = {
            name: load_agent_skills(workspaces_dir, name)
            for name in profiles
        }

        ranked = rank_agents_for_task(
            profiles=profiles,
            agent_skills_map=skills_map,
            task_title="DeFi Research Report",
            task_description="Research latest DeFi yield strategies on Base",
            task_category="knowledge_access",
            task_chain="base",
            task_bounty=0.10,
        )

        # Alice should rank first (research skills + knowledge_access experience + Base chain)
        assert len(ranked) > 0
        assert ranked[0][0] == "kk-alice"

    def test_bob_preferred_for_photography(self, workspaces_dir):
        """Bob (photography skills) beats Alice for photo tasks."""
        from lib.performance_tracker import rank_agents_for_task

        profiles = load_performance_profiles(workspaces_dir)
        skills_map = {
            name: load_agent_skills(workspaces_dir, name)
            for name in profiles
        }

        ranked = rank_agents_for_task(
            profiles=profiles,
            agent_skills_map=skills_map,
            task_title="Photo Verification",
            task_description="Take a gps-tagged photography of the location",
            task_category="digital_physical",
            task_chain="polygon",
            task_bounty=0.05,
        )

        # Bob should rank first (photography skills + digital_physical + Polygon)
        assert len(ranked) > 0
        assert ranked[0][0] == "kk-bob"

    def test_new_agent_gets_fair_chance(self, workspaces_dir):
        """New agent (Charlie) gets neutral scores, not zero."""
        from lib.performance_tracker import rank_agents_for_task

        profiles = load_performance_profiles(workspaces_dir)
        skills_map = {
            name: load_agent_skills(workspaces_dir, name)
            for name in profiles
        }

        # Generic task that no one has specific skills for
        ranked = rank_agents_for_task(
            profiles=profiles,
            agent_skills_map=skills_map,
            task_title="[KK] General Survey Task",
            task_description="Complete a simple survey about crypto usage",
            task_category="simple_action",
            task_chain="base",
            task_bounty=0.02,
        )

        # Charlie should appear in rankings (not excluded)
        charlie_scores = [s for name, s in ranked if name == "kk-charlie"]
        assert len(charlie_scores) > 0
        assert charlie_scores[0] > 0  # Not zero

    def test_system_agents_excluded(self, workspaces_dir):
        """System agents should be excluded when specified."""
        from lib.performance_tracker import rank_agents_for_task

        profiles = load_performance_profiles(workspaces_dir)
        skills_map = {name: set() for name in profiles}

        ranked = rank_agents_for_task(
            profiles=profiles,
            agent_skills_map=skills_map,
            task_title="Test",
            task_description="Test task",
            exclude_agents={"kk-alice"},
        )

        names = [name for name, _ in ranked]
        assert "kk-alice" not in names

    def test_reliability_matters(self, workspaces_dir):
        """With equal skills, higher reliability wins."""
        from lib.performance_tracker import compute_enhanced_match_score

        profiles = load_performance_profiles(workspaces_dir)

        # Give both agents the same skills
        same_skills = {"generic"}

        alice_score = compute_enhanced_match_score(
            agent_perf=profiles["kk-alice"],
            agent_skills=same_skills,
            task_title="Generic task",
            task_description="A generic task",
        )

        bob_score = compute_enhanced_match_score(
            agent_perf=profiles["kk-bob"],
            agent_skills=same_skills,
            task_title="Generic task",
            task_description="A generic task",
        )

        # Alice (83% completion, 85 rating) should beat Bob (50% completion, 60 rating)
        assert alice_score > bob_score

    def test_min_score_threshold(self, workspaces_dir):
        """Tasks below min_score threshold are excluded."""
        from lib.performance_tracker import rank_agents_for_task

        profiles = load_performance_profiles(workspaces_dir)
        skills_map = {
            name: load_agent_skills(workspaces_dir, name)
            for name in profiles
        }

        ranked = rank_agents_for_task(
            profiles=profiles,
            agent_skills_map=skills_map,
            task_title="Quantum Physics Analysis",
            task_description="Advanced quantum computing research",
            min_score=0.99,  # Unreasonably high threshold
        )

        # No one should qualify
        assert len(ranked) == 0

    def test_chain_experience_tiebreaker(self, workspaces_dir):
        """Chain experience helps break ties between similar agents."""
        from lib.performance_tracker import compute_enhanced_match_score

        profiles = load_performance_profiles(workspaces_dir)

        alice_base = compute_enhanced_match_score(
            agent_perf=profiles["kk-alice"],
            agent_skills=set(),
            task_title="Task on Base",
            task_description="Do something on base",
            task_chain="base",
        )

        alice_arbitrum = compute_enhanced_match_score(
            agent_perf=profiles["kk-alice"],
            agent_skills=set(),
            task_title="Task on Arbitrum",
            task_description="Do something on arbitrum",
            task_chain="arbitrum",
        )

        # Alice has Base experience but not Arbitrum
        assert alice_base > alice_arbitrum
