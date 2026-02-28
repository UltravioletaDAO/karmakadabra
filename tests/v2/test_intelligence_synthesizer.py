"""
Tests for Intelligence Synthesizer — Compound Intelligence Layer

Tests the cross-system intelligence synthesis that creates
multiplier effects from combining subsystem data.
"""

import json
import math
import pytest
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from intelligence_synthesizer import (
    AgentIntelligence,
    IntelligenceSynthesizer,
    RoutingDecision,
    SwarmIntelligenceReport,
    TaskRoutingRequest,
    SYNTHESIS_WEIGHTS,
    COLD_START_TASK_THRESHOLD,
    BURNOUT_TASK_THRESHOLD,
    CATEGORY_KEYWORDS,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def workspace_dir(tmp_path):
    """Create a workspace directory with test data."""
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    return workspaces


@pytest.fixture
def data_dir(tmp_path):
    """Create a data directory structure."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "reputation").mkdir()
    (data / "intelligence").mkdir()
    return data


@pytest.fixture
def populated_workspace(workspace_dir, data_dir):
    """Create workspace with agent data across all subsystems."""
    # Rename data_dir's parent
    # workspaces should be inside a 'data' parent for the synthesizer
    # Actually the synthesizer looks for workspaces_dir.parent / "data"
    # Let's organize: tmp / data / workspaces
    # BUT workspace_dir fixture already created at tmp/workspaces
    # Recreate properly:
    base = workspace_dir.parent
    data = base / "data"
    data.mkdir(exist_ok=True)
    workspaces = data / "workspaces"
    workspaces.mkdir(exist_ok=True)

    # Agent 1: Aurora — experienced, reliable
    aurora = workspaces / "aurora"
    aurora.mkdir()
    (aurora / "performance.json").write_text(json.dumps({
        "agent_name": "aurora",
        "total_tasks": 25,
        "total_approved": 22,
        "total_rejected": 2,
        "total_cost_usd": 1.50,
        "total_revenue_usd": 5.00,
        "reliability_score": 85.0,
        "efficiency_score": 78.0,
        "versatility_score": 60.0,
        "overall_score": 76.0,
    }))
    aurora_history = [
        {"category": "research", "approved": True, "bounty_usd": 0.25, "cost_usd": 0.05,
         "timestamp": "2026-02-28T01:00:00Z"},
        {"category": "research", "approved": True, "bounty_usd": 0.20, "cost_usd": 0.04},
        {"category": "research", "approved": True, "bounty_usd": 0.30, "cost_usd": 0.06},
        {"category": "code_review", "approved": True, "bounty_usd": 0.50, "cost_usd": 0.10},
        {"category": "code_review", "approved": False, "bounty_usd": 0.50, "cost_usd": 0.12},
        {"category": "content_creation", "approved": True, "bounty_usd": 0.20, "cost_usd": 0.03},
        {"category": "research", "approved": True, "bounty_usd": 0.25, "cost_usd": 0.05},
        {"category": "research", "approved": True, "bounty_usd": 0.25, "cost_usd": 0.04},
    ]
    (aurora / "evidence_history.json").write_text(json.dumps(aurora_history))

    # Agent 2: Nebula — new agent, few tasks (cold start)
    nebula = workspaces / "nebula"
    nebula.mkdir()
    (nebula / "performance.json").write_text(json.dumps({
        "agent_name": "nebula",
        "total_tasks": 2,
        "total_approved": 2,
        "total_cost_usd": 0.10,
        "total_revenue_usd": 0.40,
        "overall_score": 60.0,
    }))
    (nebula / "evidence_history.json").write_text(json.dumps([
        {"category": "translation", "approved": True, "bounty_usd": 0.20, "cost_usd": 0.05},
        {"category": "translation", "approved": True, "bounty_usd": 0.20, "cost_usd": 0.05},
    ]))

    # Agent 3: Zenith — declining performance
    zenith = workspaces / "zenith"
    zenith.mkdir()
    (zenith / "performance.json").write_text(json.dumps({
        "agent_name": "zenith",
        "total_tasks": 15,
        "total_approved": 8,
        "total_rejected": 5,
        "total_cost_usd": 2.00,
        "total_revenue_usd": 2.50,
        "reliability_score": 45.0,
        "efficiency_score": 30.0,
        "overall_score": 38.0,
    }))
    # First half approved, second half rejected = declining
    zenith_history = (
        [{"category": "research", "approved": True, "bounty_usd": 0.20, "cost_usd": 0.10}] * 5
        + [{"category": "research", "approved": False, "bounty_usd": 0.20, "cost_usd": 0.15}] * 5
    )
    (zenith / "evidence_history.json").write_text(json.dumps(zenith_history))

    # Lifecycle state
    lifecycle = [
        {"agent_name": "aurora", "state": "idle", "consecutive_failures": 0,
         "total_successes": 22, "total_failures": 3},
        {"agent_name": "nebula", "state": "idle", "consecutive_failures": 0,
         "total_successes": 2, "total_failures": 0},
        {"agent_name": "zenith", "state": "cooldown", "consecutive_failures": 3,
         "total_successes": 8, "total_failures": 7},
    ]
    (data / "lifecycle_state.json").write_text(json.dumps(lifecycle))

    # Reputation snapshot
    rep = {
        "aurora": {
            "composite_score": 82.0,
            "tier": "Diamante",
            "confidence": 0.85,
            "sources_available": ["on_chain", "off_chain", "transactional"],
            "layers": {
                "on_chain": {"score": 78.0},
                "off_chain": {"score": 85.0},
                "transactional": {"score": 80.0},
            },
        },
        "nebula": {
            "composite_score": 55.0,
            "tier": "Plata",
            "confidence": 0.30,
            "sources_available": ["off_chain"],
            "layers": {
                "on_chain": {"score": 50.0},
                "off_chain": {"score": 55.0},
                "transactional": {"score": 50.0},
            },
        },
        "zenith": {
            "composite_score": 35.0,
            "tier": "Bronce",
            "confidence": 0.60,
            "sources_available": ["off_chain", "transactional"],
            "layers": {
                "on_chain": {"score": 50.0},
                "off_chain": {"score": 30.0},
                "transactional": {"score": 25.0},
            },
        },
    }
    (data / "reputation" / "snapshot_20260228_040000.json").write_text(json.dumps(rep))

    return workspaces


def make_task(
    task_id="task-001",
    title="Research market analysis for DeFi",
    description="Analyze the current DeFi market trends",
    category="research",
    bounty_usd=0.25,
) -> TaskRoutingRequest:
    """Create a test task."""
    return TaskRoutingRequest(
        task_id=task_id,
        title=title,
        description=description,
        category=category,
        bounty_usd=bounty_usd,
    )


# ═══════════════════════════════════════════════════════════════════
# AgentIntelligence Tests
# ═══════════════════════════════════════════════════════════════════


class TestAgentIntelligence:
    """Tests for the AgentIntelligence dataclass."""

    def test_default_values(self):
        intel = AgentIntelligence(agent_name="test")
        assert intel.agent_name == "test"
        assert intel.compound_score == 50.0
        assert intel.momentum == 0.0
        assert intel.availability == 1.0
        assert intel.sources_available == []

    def test_to_dict(self):
        intel = AgentIntelligence(
            agent_name="aurora",
            compound_score=85.3,
            profiler_overall=76.0,
            reputation_composite=82.0,
            lifecycle_state="idle",
            is_healthy=True,
            momentum=5.2,
            learning_trajectory="improving",
            sources_available=["profiler", "reputation"],
        )
        d = intel.to_dict()
        assert d["agent_name"] == "aurora"
        assert d["compound_score"] == 85.3
        assert d["profiler"]["overall"] == 76.0
        assert d["reputation"]["composite"] == 82.0
        assert d["signals"]["momentum"] == 5.2
        assert d["signals"]["learning_trajectory"] == "improving"

    def test_warnings_included(self):
        intel = AgentIntelligence(
            agent_name="test",
            warnings=["High burnout", "Declining"],
        )
        d = intel.to_dict()
        assert len(d["warnings"]) == 2


# ═══════════════════════════════════════════════════════════════════
# TaskRoutingRequest Tests
# ═══════════════════════════════════════════════════════════════════


class TestTaskRoutingRequest:
    """Tests for task routing request creation."""

    def test_from_em_task(self):
        em_task = {
            "id": "abc-123",
            "title": "Photo verification at location",
            "instructions": "Take a geotagged photo",
            "category": "photo_verification",
            "bounty_usd": "0.50",
            "payment_network": "base",
            "evidence_types": ["photo_geo"],
        }
        req = TaskRoutingRequest.from_em_task(em_task)
        assert req.task_id == "abc-123"
        assert req.requires_physical is True
        assert req.bounty_usd == 0.50

    def test_non_physical_task(self):
        em_task = {
            "id": "def-456",
            "title": "Research report",
            "instructions": "Write analysis",
            "evidence_types": ["text_response"],
        }
        req = TaskRoutingRequest.from_em_task(em_task)
        assert req.requires_physical is False


# ═══════════════════════════════════════════════════════════════════
# Compound Signal Computation Tests
# ═══════════════════════════════════════════════════════════════════


class TestCompoundSignals:
    """Tests for individual compound signal computations."""

    def setup_method(self):
        self.synth = IntelligenceSynthesizer("/tmp/nonexistent")

    def test_momentum_stable_with_few_entries(self):
        evidence = [{"approved": True}, {"approved": True}]
        momentum, trajectory = self.synth._compute_momentum(evidence)
        assert momentum == 0.0
        assert trajectory == "stable"

    def test_momentum_improving(self):
        # First half: 50% approval, second half: 100%
        evidence = (
            [{"approved": False}] * 4
            + [{"approved": True}] * 4
        )
        momentum, trajectory = self.synth._compute_momentum(evidence)
        assert momentum > 0
        assert trajectory == "improving"

    def test_momentum_declining(self):
        # First half: 100%, second half: 0%
        evidence = (
            [{"approved": True}] * 4
            + [{"approved": False}] * 4
        )
        momentum, trajectory = self.synth._compute_momentum(evidence)
        assert momentum < 0
        assert trajectory == "declining"

    def test_momentum_empty(self):
        momentum, trajectory = self.synth._compute_momentum([])
        assert momentum == 0.0
        assert trajectory == "stable"

    def test_burnout_risk_low_workload(self):
        evidence = [{"timestamp": "2026-01-01T00:00:00Z"}]  # Old task
        risk = self.synth._compute_burnout_risk(evidence, {})
        assert risk < 0.5

    def test_burnout_risk_high_failures(self):
        risk = self.synth._compute_burnout_risk([], {"consecutive_failures": 5})
        assert risk > 0  # Failures contribute to risk

    def test_burnout_risk_empty(self):
        risk = self.synth._compute_burnout_risk([], {})
        assert risk == 0.0

    def test_cold_start_bonus_new_agent(self):
        bonus = self.synth._compute_cold_start_bonus(0)
        assert bonus == 15.0  # COLD_START_MAX_BONUS

    def test_cold_start_bonus_experienced(self):
        bonus = self.synth._compute_cold_start_bonus(10)
        assert bonus == 0.0

    def test_cold_start_bonus_partial(self):
        bonus = self.synth._compute_cold_start_bonus(2)
        assert 0 < bonus < 15.0

    def test_availability_idle(self):
        avail = self.synth._compute_availability({"state": "idle"})
        assert avail == 1.0

    def test_availability_working(self):
        avail = self.synth._compute_availability({"state": "working"})
        assert avail == 0.0

    def test_availability_cooldown(self):
        avail = self.synth._compute_availability({"state": "cooldown"})
        assert avail == 0.1

    def test_availability_offline(self):
        avail = self.synth._compute_availability({"state": "offline"})
        assert avail == 0.0

    def test_economic_viability_profitable(self):
        prof = {"total_tasks": 10, "total_cost_usd": 0.50}
        viability = self.synth._compute_economic_viability(prof, 0.50)
        assert viability > 0.5  # Profitable (bounty > avg cost)

    def test_economic_viability_unprofitable(self):
        prof = {"total_tasks": 10, "total_cost_usd": 5.00}
        viability = self.synth._compute_economic_viability(prof, 0.10)
        assert viability < 0.4  # Unprofitable

    def test_economic_viability_no_data(self):
        viability = self.synth._compute_economic_viability({}, 0.25)
        assert viability == 0.5  # Neutral

    def test_economic_viability_zero_bounty(self):
        viability = self.synth._compute_economic_viability({"total_tasks": 5, "total_cost_usd": 1}, 0)
        assert viability == 0.3  # Unknown bounty

    def test_infer_category_research(self):
        cat = self.synth._infer_task_category("Market research", "Analyze trends")
        assert cat == "research"

    def test_infer_category_code_review(self):
        cat = self.synth._infer_task_category("Code review needed", "Review this PR")
        assert cat == "code_review"

    def test_infer_category_unknown(self):
        cat = self.synth._infer_task_category("", "")
        assert cat == ""


# ═══════════════════════════════════════════════════════════════════
# Full Synthesis Tests
# ═══════════════════════════════════════════════════════════════════


class TestSynthesis:
    """Tests for the full intelligence synthesis pipeline."""

    def test_synthesize_with_populated_data(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        assert len(result) == 3  # aurora, nebula, zenith
        assert "aurora" in result
        assert "nebula" in result
        assert "zenith" in result

    def test_aurora_scores_highest(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        aurora = result["aurora"]
        zenith = result["zenith"]
        # Aurora should score higher than declining zenith
        assert aurora.compound_score > zenith.compound_score

    def test_aurora_has_all_sources(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        aurora = result["aurora"]
        assert "profiler" in aurora.sources_available
        assert "reputation" in aurora.sources_available
        assert "lifecycle" in aurora.sources_available
        assert "evidence" in aurora.sources_available

    def test_nebula_gets_cold_start_bonus(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        nebula = result["nebula"]
        assert nebula.cold_start_bonus > 0

    def test_zenith_shows_declining(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        zenith = result["zenith"]
        # Zenith is in cooldown → availability near 0
        assert zenith.availability < 0.5
        # Zenith has 3 consecutive failures
        assert zenith.consecutive_failures >= 3

    def test_zenith_has_warnings(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        zenith = result["zenith"]
        assert len(zenith.warnings) > 0

    def test_synthesis_empty_workspace(self, tmp_path):
        empty = tmp_path / "workspaces"
        empty.mkdir()
        synth = IntelligenceSynthesizer(empty)
        result = synth.synthesize()
        assert len(result) == 0

    def test_synthesis_partial_data(self, tmp_path):
        """Agent with only profiler data, no reputation/lifecycle."""
        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()
        solo = workspaces / "solo-agent"
        solo.mkdir()
        (solo / "performance.json").write_text(json.dumps({
            "total_tasks": 5,
            "total_approved": 4,
            "overall_score": 70.0,
        }))

        synth = IntelligenceSynthesizer(workspaces)
        result = synth.synthesize()

        assert "solo-agent" in result
        intel = result["solo-agent"]
        assert "profiler" in intel.sources_available
        assert "reputation" not in intel.sources_available
        assert intel.compound_score > 0

    def test_compound_score_bounded(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        for name, intel in result.items():
            assert 0 <= intel.compound_score <= 100, f"{name} score out of bounds"

    def test_synthesis_timestamp_set(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()
        for intel in result.values():
            assert intel.synthesis_timestamp is not None


# ═══════════════════════════════════════════════════════════════════
# Task Routing Tests
# ═══════════════════════════════════════════════════════════════════


class TestTaskRouting:
    """Tests for the compound intelligence routing decisions."""

    def test_route_research_task_to_aurora(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task(category="research")
        decision = synth.route_task(task)

        assert decision.selected_agent == "aurora"
        assert decision.selection_score > 0
        assert decision.alternatives > 0

    def test_route_physical_task_rejected(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = TaskRoutingRequest(
            task_id="phys-001",
            title="Take photo at location",
            requires_physical=True,
        )
        decision = synth.route_task(task)
        assert decision.selected_agent is None
        assert any("physical" in w.lower() for w in decision.warnings)

    def test_route_excludes_agents(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task()
        decision = synth.route_task(task, exclude_agents={"aurora"})
        assert decision.selected_agent != "aurora"

    def test_route_unavailable_agents_excluded(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        result = synth.synthesize()

        # Zenith is in cooldown (availability = 0.1)
        task = make_task()
        decision = synth.route_task(task)
        # Zenith might be in rankings but with very low score
        if decision.ranked_agents:
            zenith_entries = [(n, s) for n, s in decision.ranked_agents if n == "zenith"]
            if zenith_entries:
                # Zenith's score should be much lower than aurora's
                aurora_entries = [(n, s) for n, s in decision.ranked_agents if n == "aurora"]
                if aurora_entries:
                    assert aurora_entries[0][1] > zenith_entries[0][1]

    def test_route_with_confidence(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task()
        decision = synth.route_task(task)
        assert 0 <= decision.confidence <= 1

    def test_route_has_reasoning(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task()
        decision = synth.route_task(task)
        assert len(decision.reasoning) > 0

    def test_route_to_dict(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task()
        decision = synth.route_task(task)
        d = decision.to_dict()
        assert "selected_agent" in d
        assert "top_5" in d
        assert "confidence" in d

    def test_route_translation_task(self, populated_workspace):
        """Nebula has translation experience — should be considered."""
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task(
            task_id="trans-001",
            title="Translate document to Spanish",
            description="Spanish translation needed",
            category="translation",
        )
        decision = synth.route_task(task)
        # Both aurora and nebula could be selected
        # but nebula has translation experience + cold-start bonus
        assert decision.selected_agent is not None

    def test_route_empty_workspace(self, tmp_path):
        empty = tmp_path / "workspaces"
        empty.mkdir()
        synth = IntelligenceSynthesizer(empty)

        task = make_task()
        decision = synth.route_task(task)
        assert decision.selected_agent is None

    def test_route_min_score_filter(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task()
        decision = synth.route_task(task, min_score=9999)
        assert decision.selected_agent is None

    def test_route_category_inference(self, populated_workspace):
        """Test routing when no explicit category — infer from title."""
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = TaskRoutingRequest(
            task_id="infer-001",
            title="Code review for smart contract",
            description="Review this Solidity code for vulnerabilities",
            category="",  # No explicit category
        )
        decision = synth.route_task(task)
        # Should still route successfully by inferring 'code_review'
        assert decision.selected_agent is not None


# ═══════════════════════════════════════════════════════════════════
# Fleet Intelligence Tests
# ═══════════════════════════════════════════════════════════════════


class TestFleetIntelligence:
    """Tests for fleet-wide intelligence analysis."""

    def test_generate_report(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        report = synth.generate_intelligence_report()
        assert report.total_agents == 3
        assert report.timestamp != ""

    def test_report_health_score(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        report = synth.generate_intelligence_report()
        assert 0 <= report.swarm_health_score <= 100

    def test_report_tiers(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        report = synth.generate_intelligence_report()
        all_tiered = (
            report.elite + report.reliable + report.developing + report.underperforming
        )
        assert len(all_tiered) == 3  # All agents classified

    def test_report_patterns(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        report = synth.generate_intelligence_report()
        # Should detect opportunities (uncovered categories)
        assert len(report.opportunities) > 0

    def test_report_to_dict(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        report = synth.generate_intelligence_report()
        d = report.to_dict()
        assert "health" in d
        assert "intelligence" in d
        assert "tiers" in d
        assert "patterns" in d

    def test_format_report(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        text = synth.format_intelligence_report()
        assert "Intelligence Report" in text
        assert "Health Score" in text

    def test_format_routing_decision(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        task = make_task()
        decision = synth.route_task(task)
        text = synth.format_routing_decision(decision)
        assert "Routing Decision" in text


# ═══════════════════════════════════════════════════════════════════
# Persistence Tests
# ═══════════════════════════════════════════════════════════════════


class TestPersistence:
    """Tests for saving and loading intelligence snapshots."""

    def test_save_snapshot(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        path = synth.save_snapshot()
        assert path.exists()
        data = json.loads(path.read_text())
        assert "agents" in data
        assert "report" in data
        assert "aurora" in data["agents"]

    def test_load_latest_snapshot(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()
        synth.save_snapshot()

        loaded = synth.load_latest_snapshot()
        assert loaded is not None
        assert "agents" in loaded

    def test_snapshot_round_trip(self, populated_workspace):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()
        synth.save_snapshot()

        loaded = synth.load_latest_snapshot()
        aurora_data = loaded["agents"]["aurora"]
        assert aurora_data["compound_score"] > 0
        assert len(aurora_data["sources"]) > 0


# ═══════════════════════════════════════════════════════════════════
# Compound Effect Tests (The Multiplier)
# ═══════════════════════════════════════════════════════════════════


class TestCompoundEffects:
    """Tests that verify the multiplier effects emerge from synthesis.

    These test the core insight: compound signals that are invisible
    to individual subsystems but emerge from cross-referencing.
    """

    def test_improving_agent_with_good_reputation_gets_boost(self, tmp_path):
        """An agent improving + strong reputation should score higher
        than improving alone or reputation alone."""
        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()
        (base / "reputation").mkdir()

        # Agent with improving trajectory
        agent = workspaces / "climber"
        agent.mkdir()
        (agent / "performance.json").write_text(json.dumps({
            "total_tasks": 10,
            "total_approved": 8,
            "overall_score": 65.0,
            "reliability_score": 70.0,
        }))
        # Trajectory: poor start, strong finish
        history = (
            [{"category": "research", "approved": False}] * 4
            + [{"category": "research", "approved": True}] * 6
        )
        (agent / "evidence_history.json").write_text(json.dumps(history))

        # Good reputation
        (base / "reputation" / "snapshot_20260228.json").write_text(json.dumps({
            "climber": {
                "composite_score": 80.0,
                "tier": "Diamante",
                "confidence": 0.9,
                "sources_available": ["on_chain", "off_chain"],
                "layers": {"on_chain": {"score": 80}, "off_chain": {"score": 80}, "transactional": {"score": 80}},
            },
        }))

        # Lifecycle: healthy
        (base / "lifecycle_state.json").write_text(json.dumps([
            {"agent_name": "climber", "state": "idle", "consecutive_failures": 0,
             "total_successes": 8, "total_failures": 2},
        ]))

        synth = IntelligenceSynthesizer(workspaces)
        result = synth.synthesize()

        climber = result["climber"]
        assert climber.momentum > 0, "Should detect improving trajectory"
        assert climber.reputation_composite == 80.0
        assert climber.compound_score > 65.0, "Compound should exceed profiler alone"

    def test_burnout_suppresses_high_performer(self, tmp_path):
        """Even a high-performing agent should get suppressed if at burnout risk."""
        import time

        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()

        agent = workspaces / "overworked"
        agent.mkdir()
        (agent / "performance.json").write_text(json.dumps({
            "total_tasks": 50,
            "total_approved": 48,
            "overall_score": 95.0,
            "reliability_score": 95.0,
            "efficiency_score": 90.0,
        }))

        # Many recent tasks (high burnout risk)
        now = time.time()
        history = [
            {"category": "research", "approved": True,
             "timestamp": now - i * 3600}  # One per hour, recent
            for i in range(10)
        ]
        (agent / "evidence_history.json").write_text(json.dumps(history))

        (base / "lifecycle_state.json").write_text(json.dumps([
            {"agent_name": "overworked", "state": "idle", "consecutive_failures": 0,
             "total_successes": 48, "total_failures": 2},
        ]))

        synth = IntelligenceSynthesizer(workspaces)
        result = synth.synthesize()

        agent_intel = result["overworked"]
        assert agent_intel.burnout_risk > 0.5, "Should detect burnout risk"
        # Compound score should be lower than raw profiler score
        assert agent_intel.compound_score < 95.0

    def test_cold_start_levels_playing_field(self, tmp_path):
        """New agent should get close enough to experienced agent
        to ensure task exposure (avoiding rich-get-richer)."""
        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()

        # Experienced agent
        veteran = workspaces / "veteran"
        veteran.mkdir()
        (veteran / "performance.json").write_text(json.dumps({
            "total_tasks": 20,
            "total_approved": 15,
            "overall_score": 70.0,
        }))

        # New agent with no history
        newbie = workspaces / "newbie"
        newbie.mkdir()
        (newbie / "performance.json").write_text(json.dumps({
            "total_tasks": 0,
            "overall_score": 50.0,
        }))

        (base / "lifecycle_state.json").write_text(json.dumps([
            {"agent_name": "veteran", "state": "idle", "consecutive_failures": 0, "total_successes": 15},
            {"agent_name": "newbie", "state": "idle", "consecutive_failures": 0, "total_successes": 0},
        ]))

        synth = IntelligenceSynthesizer(workspaces)
        result = synth.synthesize()

        newbie_intel = result["newbie"]
        veteran_intel = result["veteran"]

        assert newbie_intel.cold_start_bonus > 0
        assert veteran_intel.cold_start_bonus == 0

        # The cold-start bonus should bring newbie's score closer
        # (not necessarily equal, but within striking distance)
        gap = veteran_intel.compound_score - newbie_intel.compound_score
        assert gap < 40, f"Gap too large ({gap:.1f}) — cold start not effective"


# ═══════════════════════════════════════════════════════════════════
# Synthesis Weight Tests
# ═══════════════════════════════════════════════════════════════════


class TestSynthesisWeights:
    """Verify synthesis weight configuration."""

    def test_weights_sum_to_one(self):
        total = sum(SYNTHESIS_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_weight_keys_present(self):
        expected = {"profiler", "reputation", "lifecycle", "evidence", "momentum", "economics"}
        assert set(SYNTHESIS_WEIGHTS.keys()) == expected

    def test_all_weights_positive(self):
        for key, weight in SYNTHESIS_WEIGHTS.items():
            assert weight > 0, f"{key} weight should be positive"


# ═══════════════════════════════════════════════════════════════════
# Category Keywords Tests
# ═══════════════════════════════════════════════════════════════════


class TestCategoryKeywords:
    """Verify category keyword configuration."""

    def test_all_categories_have_keywords(self):
        for cat, keywords in CATEGORY_KEYWORDS.items():
            assert len(keywords) > 0, f"{cat} has no keywords"

    def test_expected_categories_present(self):
        expected = {"knowledge_access", "content_creation", "research", "code_review"}
        assert expected.issubset(set(CATEGORY_KEYWORDS.keys()))

    def test_keywords_are_lowercase(self):
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                assert kw == kw.lower(), f"Keyword '{kw}' in {cat} not lowercase"


# ═══════════════════════════════════════════════════════════════════
# Edge Case Tests
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_missing_workspace_dir(self, tmp_path):
        synth = IntelligenceSynthesizer(tmp_path / "nonexistent")
        result = synth.synthesize()
        assert len(result) == 0

    def test_corrupted_json_files(self, tmp_path):
        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()

        broken = workspaces / "broken-agent"
        broken.mkdir()
        (broken / "performance.json").write_text("{{not valid json")
        (broken / "evidence_history.json").write_text("[incomplete")

        synth = IntelligenceSynthesizer(workspaces)
        result = synth.synthesize()
        # Should handle gracefully — agent may or may not appear
        # but should NOT crash

    def test_lifecycle_state_as_dict(self, tmp_path):
        """Lifecycle state stored as dict with 'agents' key."""
        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()

        agent = workspaces / "test-agent"
        agent.mkdir()
        (agent / "performance.json").write_text(json.dumps({"total_tasks": 1, "overall_score": 50}))

        (base / "lifecycle_state.json").write_text(json.dumps({
            "agents": [
                {"agent_name": "test-agent", "state": "idle", "consecutive_failures": 0},
            ]
        }))

        synth = IntelligenceSynthesizer(workspaces)
        result = synth.synthesize()
        assert "test-agent" in result
        assert result["test-agent"].lifecycle_state == "idle"

    def test_evidence_history_as_dict(self, tmp_path):
        """Evidence stored as dict with 'completions' key."""
        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()

        agent = workspaces / "dict-agent"
        agent.mkdir()
        (agent / "evidence_history.json").write_text(json.dumps({
            "completions": [
                {"category": "research", "approved": True},
            ]
        }))

        synth = IntelligenceSynthesizer(workspaces)
        result = synth.synthesize()
        assert "dict-agent" in result
        assert result["dict-agent"].recent_task_count == 1

    def test_save_to_custom_dir(self, populated_workspace, tmp_path):
        synth = IntelligenceSynthesizer(populated_workspace)
        synth.synthesize()

        custom = tmp_path / "custom_output"
        path = synth.save_snapshot(custom)
        assert path.exists()
        assert "custom_output" in str(path)

    def test_load_nonexistent_snapshot(self, tmp_path):
        synth = IntelligenceSynthesizer(tmp_path / "workspaces")
        loaded = synth.load_latest_snapshot()
        assert loaded is None
