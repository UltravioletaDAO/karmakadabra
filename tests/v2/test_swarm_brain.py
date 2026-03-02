"""
Tests for Karma Kadabra V2 — Swarm Brain (Unified Orchestrator)

Tests the capstone integration layer that ties all subsystems together:
  - Agent Lifecycle ↔ Decision Engine ↔ Task Pipeline ↔ Monitor ↔ Analytics

Each test class covers a specific aspect of brain coordination.
All tests are self-contained (no external dependencies, no I/O).
"""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.swarm_brain import (
    BrainConfig,
    CyclePhase,
    CycleResult,
    PhaseResult,
    SwarmBrain,
    build_agent_health_snapshot,
    build_agent_profile,
    build_pipeline_snapshot,
    build_task_profile,
)
from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    TransitionReason,
    create_agent_roster,
    transition,
)
from lib.decision_engine import (
    AgentProfile,
    DecisionConfig,
    DecisionEngine,
    OptimizationMode,
    TaskProfile,
)
from services.task_pipeline import (
    PipelineStage,
    PipelineState,
    PipelineTask,
    TaskEvidence,
    execute_transition,
)
from services.swarm_monitor import (
    AgentHealthSnapshot,
    MonitorConfig,
    PipelineSnapshot,
    SystemSnapshot,
)
from lib.reputation_bridge import UnifiedReputation


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

SAMPLE_REGISTRY = [
    {"name": "kk-coordinator", "type": "system"},
    {"name": "kk-validator", "type": "system"},
    {"name": "kk-worker-1", "type": "core"},
    {"name": "kk-worker-2", "type": "core"},
    {"name": "kk-agent-1", "type": "user"},
    {"name": "kk-agent-2", "type": "user"},
    {"name": "kk-agent-3", "type": "user"},
]


def make_brain(
    agent_count: int = 7,
    auto_restart: bool = True,
    auto_reassign: bool = True,
) -> SwarmBrain:
    """Create a brain with initialized agents for testing."""
    config = BrainConfig(
        auto_restart_agents=auto_restart,
        auto_reassign_stuck=auto_reassign,
        analytics_every_n_cycles=1,
        leaderboard_every_n_cycles=5,
        state_dir=tempfile.mkdtemp(),
    )
    registry = SAMPLE_REGISTRY[:agent_count]
    brain = SwarmBrain(config=config)
    brain.initialize(agent_registry=registry)
    return brain


def make_task_data(
    task_id: str = "task-001",
    title: str = "Test photo in downtown Miami",
    category: str = "physical_verification",
    bounty: float = 1.50,
) -> dict:
    """Create sample task data as it comes from EM API."""
    return {
        "id": task_id,
        "title": title,
        "category": category,
        "bounty_usd": bounty,
        "payment_network": "base",
        "creator_wallet": "0xABC123",
    }


NOW = datetime(2026, 3, 2, 4, 0, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════
# Test: Initialization
# ═══════════════════════════════════════════════════════════════════

class TestBrainInitialization:
    """Tests for brain startup and agent bootstrapping."""

    def test_init_creates_agents(self):
        brain = make_brain()
        assert len(brain.agents) == 7

    def test_init_boots_all_agents_to_idle(self):
        brain = make_brain()
        for agent in brain.agents:
            assert agent.state == AgentState.IDLE, (
                f"Agent {agent.agent_name} should be IDLE, got {agent.state}"
            )

    def test_init_creates_reputations(self):
        brain = make_brain()
        assert len(brain.reputations) == 7
        for rep in brain.reputations.values():
            assert rep.composite_score == 50.0  # Default for new agents

    def test_init_returns_report(self):
        config = BrainConfig(state_dir=tempfile.mkdtemp())
        brain = SwarmBrain(config=config)
        report = brain.initialize(agent_registry=SAMPLE_REGISTRY)
        assert report["agents_total"] == 7
        assert report["agents_booted"] == 7
        assert "initialized_at" in report

    def test_init_with_empty_registry(self):
        config = BrainConfig(state_dir=tempfile.mkdtemp())
        brain = SwarmBrain(config=config)
        report = brain.initialize(agent_registry=[])
        assert report["agents_total"] == 0
        assert report["agents_booted"] == 0

    def test_init_with_existing_agents(self):
        """Brain preserves pre-loaded agents."""
        agents = create_agent_roster(SAMPLE_REGISTRY[:3])
        config = BrainConfig(state_dir=tempfile.mkdtemp())
        brain = SwarmBrain(config=config, agents=agents)
        report = brain.initialize()
        assert report["agents_total"] == 3

    def test_init_pipeline_starts_empty(self):
        brain = make_brain()
        assert len(brain.pipeline.tasks) == 0
        assert brain.pipeline.total_completed == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Full Coordination Cycle
# ═══════════════════════════════════════════════════════════════════

class TestCoordinationCycle:
    """Tests for the main coordination cycle."""

    def test_empty_cycle_succeeds(self):
        """A cycle with no tasks should still complete cleanly."""
        brain = make_brain()
        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.cycle_number == 1
        assert result.total_duration_ms >= 0
        assert len(result.phases) >= 7  # At least 7 phases (analytics + persistence too)

    def test_cycle_increments_counter(self):
        brain = make_brain()
        brain.run_cycle(new_tasks=[], now=NOW)
        brain.run_cycle(new_tasks=[], now=NOW + timedelta(minutes=2))
        assert brain.cycle_count == 2

    def test_cycle_sets_timestamps(self):
        brain = make_brain()
        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.started_at == NOW.isoformat()
        assert result.completed_at != ""

    def test_cycle_with_tasks_discovers_them(self):
        brain = make_brain()
        tasks = [make_task_data("t1"), make_task_data("t2")]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        assert result.tasks_discovered == 2
        assert len(brain.pipeline.tasks) == 2

    def test_cycle_matches_discovered_tasks(self):
        brain = make_brain()
        tasks = [make_task_data("t1")]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        # Task should be discovered AND matched in the same cycle
        assert result.tasks_discovered == 1
        assert result.tasks_matched >= 1

    def test_full_task_lifecycle_in_single_cycle(self):
        """Discovery → Matching → Assignment happens in one cycle."""
        brain = make_brain()
        tasks = [make_task_data("t1")]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        assert result.tasks_discovered == 1
        assert result.tasks_assigned >= 1

        # Task should be IN_PROGRESS
        task = brain.pipeline.tasks["t1"]
        assert task.stage == PipelineStage.IN_PROGRESS
        assert task.assigned_agent is not None

    def test_duplicate_tasks_ignored(self):
        brain = make_brain()
        tasks = [make_task_data("t1"), make_task_data("t1")]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        assert result.tasks_discovered == 1  # Second one ignored

    def test_cycle_respects_max_tasks_per_cycle(self):
        config = BrainConfig(
            max_tasks_per_cycle=2,
            state_dir=tempfile.mkdtemp(),
        )
        brain = SwarmBrain(config=config)
        brain.initialize(agent_registry=SAMPLE_REGISTRY)

        tasks = [make_task_data(f"t{i}") for i in range(5)]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        assert result.tasks_discovered == 2

    def test_cycle_summary_text(self):
        brain = make_brain()
        tasks = [make_task_data("t1")]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        summary = result.summary()
        assert "Ciclo #1" in summary
        assert "descubiertas" in summary

    def test_cycle_summary_oneline(self):
        brain = make_brain()
        result = brain.run_cycle(new_tasks=[], now=NOW)
        oneline = result.summary_oneline()
        assert "Cycle #1" in oneline


# ═══════════════════════════════════════════════════════════════════
# Test: Health Check Phase
# ═══════════════════════════════════════════════════════════════════

class TestHealthCheckPhase:
    """Tests for the health monitoring phase."""

    def test_healthy_swarm_reports_healthy(self):
        brain = make_brain()
        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.swarm_status == "healthy"

    def test_error_agents_generate_alerts(self):
        brain = make_brain()
        # Force an agent into error state
        agent = brain.agents[0]
        transition(agent, TransitionReason.TASK_ASSIGNED, now=NOW)
        agent.consecutive_failures = 5
        transition(agent, TransitionReason.FATAL_ERROR, now=NOW)

        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.alerts_generated > 0

    def test_all_offline_agents_report_down(self):
        brain = make_brain()
        # Force all agents offline
        for agent in brain.agents:
            transition(agent, TransitionReason.MANUAL_STOP, now=NOW)
            transition(agent, TransitionReason.MANUAL_STOP, now=NOW)

        result = brain.run_cycle(new_tasks=[], now=NOW)
        # Should report impaired or down
        assert result.swarm_status in ("impaired", "down")


# ═══════════════════════════════════════════════════════════════════
# Test: Self-Healing Phase
# ═══════════════════════════════════════════════════════════════════

class TestSelfHealingPhase:
    """Tests for automatic agent recovery and task reassignment."""

    def test_auto_restart_error_agent(self):
        brain = make_brain()
        agent = brain.agents[0]
        transition(agent, TransitionReason.TASK_ASSIGNED, now=NOW)
        agent.consecutive_failures = 5
        transition(agent, TransitionReason.FATAL_ERROR, now=NOW)

        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.agents_restarted >= 1
        assert agent.state == AgentState.IDLE  # Recovered
        assert agent.consecutive_failures == 0  # Reset

    def test_no_restart_when_disabled(self):
        brain = make_brain(auto_restart=False)
        agent = brain.agents[0]
        transition(agent, TransitionReason.TASK_ASSIGNED, now=NOW)
        agent.consecutive_failures = 5
        transition(agent, TransitionReason.FATAL_ERROR, now=NOW)

        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.agents_restarted == 0
        assert agent.state == AgentState.ERROR

    def test_max_restarts_per_cycle(self):
        config = BrainConfig(
            max_auto_restarts_per_cycle=1,
            state_dir=tempfile.mkdtemp(),
        )
        brain = SwarmBrain(config=config)
        brain.initialize(agent_registry=SAMPLE_REGISTRY)

        # Put 3 agents in error
        for agent in brain.agents[:3]:
            transition(agent, TransitionReason.TASK_ASSIGNED, now=NOW)
            agent.consecutive_failures = 5
            transition(agent, TransitionReason.FATAL_ERROR, now=NOW)

        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.agents_restarted == 1  # Only 1 per cycle

    def test_reassign_stuck_task(self):
        brain = make_brain()

        # Create a stuck task
        task = PipelineTask(
            task_id="stuck-1",
            stage=PipelineStage.IN_PROGRESS,
            title="Stuck task",
            assigned_agent="kk-worker-1",
            started_at=(NOW - timedelta(hours=10)).isoformat(),
            stage_entered_at=(NOW - timedelta(hours=10)).isoformat(),
            created_at=(NOW - timedelta(hours=10)).isoformat(),
            updated_at=(NOW - timedelta(hours=10)).isoformat(),
        )
        brain.pipeline.tasks["stuck-1"] = task

        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.tasks_reassigned >= 1
        # Task was re-discovered and immediately re-matched + re-assigned in same cycle
        # So it ends up back IN_PROGRESS with a different (or same) agent
        assert task.retry_count == 1
        # The key proof: events show FAILED → DISCOVERED → EVALUATED → OFFERED → ...
        event_stages = [e.to_stage for e in task.events]
        assert "failed" in event_stages
        assert "discovered" in event_stages


# ═══════════════════════════════════════════════════════════════════
# Test: Discovery Phase
# ═══════════════════════════════════════════════════════════════════

class TestDiscoveryPhase:
    """Tests for task discovery and ingestion."""

    def test_discover_tasks(self):
        brain = make_brain()
        tasks = [make_task_data("t1"), make_task_data("t2"), make_task_data("t3")]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        assert result.tasks_discovered == 3
        assert brain.pipeline.total_discovered == 3

    def test_task_enters_pipeline_correctly(self):
        brain = make_brain()
        result = brain.run_cycle(
            new_tasks=[make_task_data("t1", title="Test task", bounty=2.50)],
            now=NOW,
        )
        task = brain.pipeline.tasks["t1"]
        assert task.title == "Test task"
        assert task.bounty_usd == 2.50
        assert task.payment_network == "base"
        assert task.creator_wallet == "0xABC123"

    def test_fetcher_is_called_when_no_tasks_provided(self):
        fetched = [make_task_data("fetched-1")]
        brain = make_brain()
        brain._fetch_tasks = lambda: fetched
        result = brain.run_cycle(now=NOW)
        assert result.tasks_discovered == 1
        assert "fetched-1" in brain.pipeline.tasks

    def test_fetcher_error_handled_gracefully(self):
        brain = make_brain()
        brain._fetch_tasks = lambda: (_ for _ in ()).throw(ConnectionError("timeout"))
        result = brain.run_cycle(now=NOW)
        # Should not crash, just log error
        assert result.tasks_discovered == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Matching Phase
# ═══════════════════════════════════════════════════════════════════

class TestMatchingPhase:
    """Tests for decision engine integration."""

    def test_tasks_get_matched_to_agents(self):
        brain = make_brain()
        tasks = [make_task_data("t1")]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        assert result.tasks_matched >= 1

    def test_matched_task_has_rankings(self):
        brain = make_brain()
        result = brain.run_cycle(
            new_tasks=[make_task_data("t1")],
            now=NOW,
        )
        task = brain.pipeline.tasks["t1"]
        assert len(task.rankings) > 0
        assert task.rankings[0].agent_name  # Has agent assigned

    def test_decision_is_logged(self):
        brain = make_brain()
        result = brain.run_cycle(
            new_tasks=[make_task_data("t1")],
            now=NOW,
        )
        assert len(brain._decisions_log) >= 1
        assert brain._decisions_log[0]["task_id"] == "t1"

    def test_multiple_tasks_matched_independently(self):
        brain = make_brain()
        tasks = [make_task_data(f"t{i}") for i in range(3)]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)
        assert result.tasks_matched >= 3


# ═══════════════════════════════════════════════════════════════════
# Test: Assignment Phase
# ═══════════════════════════════════════════════════════════════════

class TestAssignmentPhase:
    """Tests for task assignment through the pipeline."""

    def test_task_assigned_to_chosen_agent(self):
        brain = make_brain()
        result = brain.run_cycle(
            new_tasks=[make_task_data("t1")],
            now=NOW,
        )
        task = brain.pipeline.tasks["t1"]
        assert task.assigned_agent is not None
        assert task.stage == PipelineStage.IN_PROGRESS

    def test_agent_transitions_to_working(self):
        brain = make_brain()
        result = brain.run_cycle(
            new_tasks=[make_task_data("t1")],
            now=NOW,
        )
        task = brain.pipeline.tasks["t1"]
        agent_name = task.assigned_agent
        agent = brain._get_agent(agent_name)
        assert agent.state == AgentState.WORKING
        assert agent.current_task_id == "t1"

    def test_assignment_fallback_to_alternative(self):
        """If top agent is unavailable, uses next alternative."""
        brain = make_brain()
        # Make first few agents unavailable
        for agent in brain.agents[:3]:
            transition(agent, TransitionReason.MANUAL_STOP, now=NOW)
            transition(agent, TransitionReason.MANUAL_STOP, now=NOW)

        result = brain.run_cycle(
            new_tasks=[make_task_data("t1")],
            now=NOW,
        )
        task = brain.pipeline.tasks["t1"]
        if task.assigned_agent:
            agent = brain._get_agent(task.assigned_agent)
            assert agent.state == AgentState.WORKING

    def test_multiple_tasks_get_assigned(self):
        """Multiple tasks should all get assigned when agents available."""
        brain = make_brain()
        tasks = [make_task_data(f"t{i}") for i in range(3)]
        result = brain.run_cycle(new_tasks=tasks, now=NOW)

        assigned_count = sum(
            1 for task in brain.pipeline.tasks.values()
            if task.assigned_agent is not None
        )
        # All 3 should be assigned (we have 7 agents)
        assert assigned_count >= 3


# ═══════════════════════════════════════════════════════════════════
# Test: Completion Phase
# ═══════════════════════════════════════════════════════════════════

class TestCompletionPhase:
    """Tests for evidence processing and task completion."""

    def test_submitted_task_completes_full_pipeline(self):
        """Submitted task with evidence flows all the way to COMPLETED in one cycle."""
        brain = make_brain()

        # Create a submitted task
        task = PipelineTask(
            task_id="sub-1",
            stage=PipelineStage.SUBMITTED,
            assigned_agent="kk-worker-1",
            evidence=[TaskEvidence(evidence_type="photo", content_url="https://example.com/proof.jpg")],
            created_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
            stage_entered_at=NOW.isoformat(),
        )
        brain.pipeline.tasks["sub-1"] = task

        brain.run_cycle(new_tasks=[], now=NOW)
        # In one cycle: SUBMITTED → UNDER_REVIEW → APPROVED → PAID → RATED → COMPLETED
        assert task.stage == PipelineStage.COMPLETED
        event_stages = [e.to_stage for e in task.events]
        assert "under_review" in event_stages
        assert "approved" in event_stages
        assert "paid" in event_stages
        assert "completed" in event_stages

    def test_reviewed_task_with_evidence_completes(self):
        """Under-review task with evidence flows to COMPLETED."""
        brain = make_brain()

        task = PipelineTask(
            task_id="rev-1",
            stage=PipelineStage.UNDER_REVIEW,
            assigned_agent="kk-worker-1",
            evidence=[TaskEvidence(evidence_type="photo", content_url="https://example.com/proof.jpg")],
            created_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
            stage_entered_at=NOW.isoformat(),
        )
        brain.pipeline.tasks["rev-1"] = task

        brain.run_cycle(new_tasks=[], now=NOW)
        # UNDER_REVIEW → APPROVED → PAID → RATED → COMPLETED
        assert task.stage == PipelineStage.COMPLETED
        assert task.approved_at is not None

    def test_approved_task_gets_paid_and_completed(self):
        brain = make_brain()

        # Create an approved task with agent assigned
        agent = brain.agents[2]
        transition(agent, TransitionReason.TASK_ASSIGNED, now=NOW)
        agent.current_task_id = "app-1"

        task = PipelineTask(
            task_id="app-1",
            stage=PipelineStage.APPROVED,
            assigned_agent=agent.agent_name,
            bounty_usd=1.50,
            approved_at=NOW.isoformat(),
            created_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
            stage_entered_at=NOW.isoformat(),
        )
        brain.pipeline.tasks["app-1"] = task

        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert task.stage == PipelineStage.COMPLETED
        assert task.paid_at is not None
        assert result.tasks_completed >= 1

    def test_completion_updates_agent_stats(self):
        brain = make_brain()

        agent = brain.agents[2]
        transition(agent, TransitionReason.TASK_ASSIGNED, now=NOW)
        agent.current_task_id = "stat-1"
        initial_successes = agent.total_successes

        task = PipelineTask(
            task_id="stat-1",
            stage=PipelineStage.APPROVED,
            assigned_agent=agent.agent_name,
            bounty_usd=2.00,
            created_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
            stage_entered_at=NOW.isoformat(),
        )
        brain.pipeline.tasks["stat-1"] = task

        brain.run_cycle(new_tasks=[], now=NOW)
        assert agent.total_successes > initial_successes  # At least 1 more
        assert agent.state == AgentState.IDLE  # Returned to idle

    def test_completion_tracks_payment(self):
        brain = make_brain()

        task = PipelineTask(
            task_id="pay-1",
            stage=PipelineStage.APPROVED,
            assigned_agent="kk-worker-1",
            bounty_usd=3.50,
            created_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
            stage_entered_at=NOW.isoformat(),
        )
        brain.pipeline.tasks["pay-1"] = task

        brain.run_cycle(new_tasks=[], now=NOW)
        assert brain.pipeline.total_paid_usd >= 3.50

    def test_no_evidence_fails_review(self):
        brain = make_brain()

        task = PipelineTask(
            task_id="noev-1",
            stage=PipelineStage.UNDER_REVIEW,
            assigned_agent="kk-worker-1",
            evidence=[],  # No evidence!
            created_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
            stage_entered_at=NOW.isoformat(),
        )
        brain.pipeline.tasks["noev-1"] = task

        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert task.stage == PipelineStage.FAILED
        assert task.failure_reason == "no_evidence"


# ═══════════════════════════════════════════════════════════════════
# Test: Analytics Phase
# ═══════════════════════════════════════════════════════════════════

class TestAnalyticsPhase:
    """Tests for the analytics subsystem integration."""

    def test_analytics_runs_at_configured_interval(self):
        brain = make_brain()
        brain.config.analytics_every_n_cycles = 1  # Every cycle
        result = brain.run_cycle(new_tasks=[], now=NOW)
        phase_names = [p.phase for p in result.phases]
        assert CyclePhase.ANALYTICS in phase_names

    def test_efficiencies_computed(self):
        brain = make_brain()
        brain.run_cycle(new_tasks=[], now=NOW)
        assert len(brain.efficiencies) == 7

    def test_capacity_forecast_in_analytics(self):
        brain = make_brain()
        result = brain.run_cycle(new_tasks=[], now=NOW)
        analytics_phase = next(
            (p for p in result.phases if p.phase == CyclePhase.ANALYTICS),
            None,
        )
        assert analytics_phase is not None
        assert "capacity" in analytics_phase.details


# ═══════════════════════════════════════════════════════════════════
# Test: Persistence Phase
# ═══════════════════════════════════════════════════════════════════

class TestPersistencePhase:
    """Tests for state save/load."""

    def test_cycle_saves_state(self):
        brain = make_brain()
        result = brain.run_cycle(new_tasks=[], now=NOW)
        state_dir = Path(brain.config.state_dir)
        assert (state_dir / "lifecycle_state.json").exists()

    def test_save_and_load_roundtrip(self):
        brain = make_brain()
        brain.run_cycle(new_tasks=[make_task_data("t1")], now=NOW)

        # Save
        save_path = brain.save()

        # Load
        loaded = SwarmBrain.load(save_path)
        assert loaded.cycle_count == 1
        assert len(loaded.agents) == 7

    def test_save_creates_all_files(self):
        brain = make_brain()
        brain.run_cycle(new_tasks=[], now=NOW)
        save_path = brain.save()

        assert (save_path / "lifecycle_state.json").exists()
        assert (save_path / "pipeline_state.json").exists()
        assert (save_path / "monitor_state.json").exists()
        assert (save_path / "brain_meta.json").exists()

    def test_load_nonexistent_dir_creates_empty_brain(self):
        path = Path(tempfile.mkdtemp()) / "nonexistent"
        path.mkdir()
        brain = SwarmBrain.load(path)
        assert len(brain.agents) == 0
        assert brain.cycle_count == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Multi-Cycle Scenarios
# ═══════════════════════════════════════════════════════════════════

class TestMultiCycleScenarios:
    """Tests for behavior across multiple coordination cycles."""

    def test_task_completes_across_cycles(self):
        """Full lifecycle: discover → assign → submit → complete."""
        brain = make_brain()

        # Cycle 1: Discover and assign
        brain.run_cycle(new_tasks=[make_task_data("t1")], now=NOW)
        task = brain.pipeline.tasks["t1"]
        assert task.stage == PipelineStage.IN_PROGRESS

        # Simulate submission
        execute_transition(task, PipelineStage.SUBMITTED,
                           actor="test", now=NOW + timedelta(hours=1))
        task.evidence.append(TaskEvidence(
            evidence_type="photo",
            content_url="https://example.com/evidence.jpg",
        ))

        # Cycle 2: Review and complete
        result = brain.run_cycle(
            new_tasks=[],
            now=NOW + timedelta(hours=2),
        )
        assert task.stage == PipelineStage.COMPLETED
        assert result.tasks_completed >= 1

    def test_cycle_history_maintained(self):
        brain = make_brain()
        for i in range(5):
            brain.run_cycle(new_tasks=[], now=NOW + timedelta(minutes=i * 2))
        assert len(brain.cycle_history) == 5
        assert brain.cycle_history[0].cycle_number == 1
        assert brain.cycle_history[4].cycle_number == 5

    def test_cycle_history_trimmed(self):
        brain = make_brain()
        for i in range(120):
            brain.run_cycle(new_tasks=[], now=NOW + timedelta(minutes=i * 2))
        assert len(brain.cycle_history) <= 100

    def test_multiple_tasks_flow_through(self):
        """Batch of tasks discovered and assigned across cycles."""
        brain = make_brain()

        # Cycle 1: 3 tasks
        brain.run_cycle(
            new_tasks=[make_task_data(f"batch-{i}") for i in range(3)],
            now=NOW,
        )

        # Cycle 2: 2 more tasks
        brain.run_cycle(
            new_tasks=[make_task_data(f"batch-{i}") for i in range(3, 5)],
            now=NOW + timedelta(minutes=2),
        )

        assert len(brain.pipeline.tasks) == 5
        assigned = sum(
            1 for t in brain.pipeline.tasks.values()
            if t.assigned_agent is not None
        )
        assert assigned >= 3  # At least some should be assigned


# ═══════════════════════════════════════════════════════════════════
# Test: Bridge Functions (build_agent_profile, build_task_profile, etc.)
# ═══════════════════════════════════════════════════════════════════

class TestBridgeFunctions:
    """Tests for the bridge functions between subsystems."""

    def test_build_agent_profile_basic(self):
        agent = AgentLifecycle(
            agent_name="test-agent",
            agent_type=AgentType.USER,
            state=AgentState.IDLE,
        )
        profile = build_agent_profile(agent)
        assert profile.agent_name == "test-agent"
        assert profile.is_available is True
        assert profile.is_idle is True

    def test_build_agent_profile_with_reputation(self):
        agent = AgentLifecycle(
            agent_name="test",
            agent_type=AgentType.USER,
            state=AgentState.IDLE,
        )
        rep = UnifiedReputation(
            agent_name="test",
            composite_score=85.0,
            effective_confidence=0.8,
            on_chain_score=80.0,
            off_chain_score=90.0,
            transactional_score=85.0,
            sources_available=["chain", "off_chain"],
        )
        profile = build_agent_profile(agent, reputation=rep)
        assert profile.reputation_score == 85.0
        assert profile.reputation_confidence == 0.8

    def test_build_agent_profile_error_state(self):
        agent = AgentLifecycle(
            agent_name="broken",
            agent_type=AgentType.USER,
            state=AgentState.ERROR,
        )
        profile = build_agent_profile(agent)
        assert profile.is_available is False
        assert profile.in_error is True

    def test_build_task_profile_complexity_inference(self):
        task = PipelineTask(task_id="low", bounty_usd=0.25)
        profile = build_task_profile(task)
        assert profile.complexity == "low"

        task2 = PipelineTask(task_id="high", bounty_usd=10.0)
        profile2 = build_task_profile(task2)
        assert profile2.complexity == "high"

    def test_build_agent_health_snapshot(self):
        agent = AgentLifecycle(
            agent_name="healthy",
            agent_type=AgentType.USER,
            state=AgentState.IDLE,
            total_successes=10,
            total_failures=2,
            usdc_balance=5.0,
        )
        agent.last_heartbeat = NOW - timedelta(minutes=1)

        snap = build_agent_health_snapshot(agent, now=NOW)
        assert snap.is_online is True
        assert snap.total_successes == 10
        assert snap.usdc_balance == 5.0
        assert 50 < snap.last_heartbeat_age_seconds < 70

    def test_build_pipeline_snapshot(self):
        pipeline = PipelineState()
        pipeline.tasks["t1"] = PipelineTask(
            task_id="t1",
            stage=PipelineStage.IN_PROGRESS,
            stage_entered_at=NOW.isoformat(),
        )
        pipeline.tasks["t2"] = PipelineTask(
            task_id="t2",
            stage=PipelineStage.COMPLETED,
            stage_entered_at=NOW.isoformat(),
        )
        pipeline.total_completed = 5
        pipeline.total_failed = 1

        snap = build_pipeline_snapshot(pipeline)
        assert snap.total_tasks == 1  # Only active tasks
        assert "IN_PROGRESS" in snap.by_stage


# ═══════════════════════════════════════════════════════════════════
# Test: Status & Reporting API
# ═══════════════════════════════════════════════════════════════════

class TestStatusAPI:
    """Tests for the brain's query/reporting interface."""

    def test_status_snapshot(self):
        brain = make_brain()
        brain.run_cycle(new_tasks=[], now=NOW)
        status = brain.status()
        assert "swarm" in status
        assert "pipeline" in status
        assert status["brain_cycle_count"] == 1

    def test_status_text(self):
        brain = make_brain()
        brain.run_cycle(new_tasks=[], now=NOW)
        text = brain.status_text()
        assert "KK Swarm Brain" in text
        assert "en línea" in text

    def test_agent_report(self):
        brain = make_brain()
        brain.run_cycle(new_tasks=[], now=NOW)
        report = brain.get_agent_report("kk-worker-1")
        assert report["agent_name"] == "kk-worker-1"
        assert "state" in report
        assert "reputation" in report

    def test_agent_report_not_found(self):
        brain = make_brain()
        report = brain.get_agent_report("nonexistent")
        assert "error" in report

    def test_pipeline_report(self):
        brain = make_brain()
        brain.run_cycle(
            new_tasks=[make_task_data("t1")],
            now=NOW,
        )
        report = brain.get_pipeline_report()
        assert report["total_tasks"] == 1

    def test_cycle_result_to_dict(self):
        brain = make_brain()
        result = brain.run_cycle(new_tasks=[], now=NOW)
        d = result.to_dict()
        assert "cycle_number" in d
        assert "phases" in d
        assert "summary" in d
        assert d["cycle_number"] == 1


# ═══════════════════════════════════════════════════════════════════
# Test: Notification Integration
# ═══════════════════════════════════════════════════════════════════

class TestNotifications:
    """Tests for notification dispatch."""

    def test_notifier_called_on_critical_alert(self):
        notifications = []
        brain = make_brain()
        brain._notify = lambda msg: notifications.append(msg)

        # Force critical state
        for agent in brain.agents:
            transition(agent, TransitionReason.MANUAL_STOP, now=NOW)
            transition(agent, TransitionReason.MANUAL_STOP, now=NOW)

        brain.run_cycle(new_tasks=[], now=NOW)
        assert len(notifications) > 0

    def test_no_notification_when_healthy(self):
        notifications = []
        brain = make_brain()
        brain._notify = lambda msg: notifications.append(msg)

        brain.run_cycle(new_tasks=[], now=NOW)
        # Healthy swarm shouldn't trigger critical notifications
        critical_notifs = [n for n in notifications if "🚨" in n or "🔥" in n]
        assert len(critical_notifs) == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and robustness tests."""

    def test_brain_with_no_agents(self):
        config = BrainConfig(state_dir=tempfile.mkdtemp())
        brain = SwarmBrain(config=config)
        brain.initialize(agent_registry=[])
        result = brain.run_cycle(new_tasks=[make_task_data("t1")], now=NOW)
        # Should discover but not assign (no agents)
        assert result.tasks_discovered == 1
        assert result.tasks_assigned == 0

    def test_brain_with_single_agent(self):
        config = BrainConfig(state_dir=tempfile.mkdtemp())
        brain = SwarmBrain(config=config)
        brain.initialize(agent_registry=[{"name": "solo", "type": "user"}])
        result = brain.run_cycle(
            new_tasks=[make_task_data("t1")],
            now=NOW,
        )
        assert result.tasks_assigned <= 1

    def test_task_with_zero_bounty(self):
        brain = make_brain()
        result = brain.run_cycle(
            new_tasks=[make_task_data("zero", bounty=0.0)],
            now=NOW,
        )
        assert result.tasks_discovered == 1

    def test_rapid_cycles(self):
        """Multiple cycles in quick succession don't corrupt state."""
        brain = make_brain()
        for i in range(10):
            tasks = [make_task_data(f"rapid-{i}")]
            brain.run_cycle(new_tasks=tasks, now=NOW + timedelta(seconds=i))
        assert brain.cycle_count == 10
        assert len(brain.pipeline.tasks) == 10

    def test_task_data_missing_fields(self):
        """Gracefully handle incomplete task data."""
        brain = make_brain()
        result = brain.run_cycle(
            new_tasks=[{"id": "minimal"}],
            now=NOW,
        )
        assert result.tasks_discovered == 1
        task = brain.pipeline.tasks["minimal"]
        assert task.bounty_usd == 0.0
        assert task.category == ""

    def test_concurrent_task_tracking(self):
        """Agents can have multiple tasks in pipeline simultaneously."""
        brain = make_brain()

        # First batch
        brain.run_cycle(
            new_tasks=[make_task_data(f"batch1-{i}") for i in range(3)],
            now=NOW,
        )

        # Second batch
        brain.run_cycle(
            new_tasks=[make_task_data(f"batch2-{i}") for i in range(3)],
            now=NOW + timedelta(minutes=2),
        )

        total_in_pipeline = len(brain.pipeline.tasks)
        assert total_in_pipeline == 6


# ═══════════════════════════════════════════════════════════════════
# Test: Integration — Full Pipeline Stress Test
# ═══════════════════════════════════════════════════════════════════

class TestFullPipelineIntegration:
    """End-to-end stress tests for the full swarm brain."""

    def test_20_tasks_through_pipeline(self):
        """Process 20 tasks through discovery → assignment."""
        brain = make_brain()
        tasks = [make_task_data(f"stress-{i}", bounty=0.50 + i * 0.10) for i in range(20)]

        # Feed tasks across 4 cycles
        for i in range(4):
            batch = tasks[i * 5 : (i + 1) * 5]
            brain.run_cycle(
                new_tasks=batch,
                now=NOW + timedelta(minutes=i * 2),
            )

        assert brain.pipeline.total_discovered == 20
        assigned = sum(
            1 for t in brain.pipeline.tasks.values()
            if t.assigned_agent is not None
        )
        assert assigned >= 10  # At least half should be assigned

    def test_complete_happy_path_lifecycle(self):
        """One task goes from discovery to completion with all checks."""
        brain = make_brain()

        # Cycle 1: Discover and assign
        brain.run_cycle(
            new_tasks=[make_task_data("happy", bounty=2.00)],
            now=NOW,
        )
        task = brain.pipeline.tasks["happy"]
        assert task.stage == PipelineStage.IN_PROGRESS
        agent_name = task.assigned_agent
        assert agent_name is not None

        # Simulate: agent submits evidence
        execute_transition(task, PipelineStage.SUBMITTED, actor=agent_name, now=NOW + timedelta(hours=1))
        task.evidence.append(TaskEvidence(
            evidence_type="photo",
            content_url="https://evidence.example.com/photo.jpg",
            submitted_at=(NOW + timedelta(hours=1)).isoformat(),
        ))

        # Cycle 2: Review → Approve → Pay → Rate → Complete
        result = brain.run_cycle(new_tasks=[], now=NOW + timedelta(hours=2))

        assert task.stage == PipelineStage.COMPLETED
        assert task.paid_at is not None
        assert task.agent_rating is not None
        assert brain.pipeline.total_completed >= 1
        assert brain.pipeline.total_paid_usd >= 2.00

        # Agent should be back to idle
        agent = brain._get_agent(agent_name)
        assert agent.state == AgentState.IDLE
        assert agent.total_successes >= 1

    def test_failure_and_recovery_path(self):
        """Task fails, gets retried through self-healing, re-assigned in same cycle."""
        brain = make_brain()

        # Create a task that's been stuck for a while
        task = PipelineTask(
            task_id="stuck-recovery",
            stage=PipelineStage.IN_PROGRESS,
            title="Long-running task",
            assigned_agent="kk-worker-1",
            bounty_usd=1.00,
            started_at=(NOW - timedelta(hours=12)).isoformat(),
            stage_entered_at=(NOW - timedelta(hours=12)).isoformat(),
            created_at=(NOW - timedelta(hours=12)).isoformat(),
            updated_at=(NOW - timedelta(hours=12)).isoformat(),
        )
        brain.pipeline.tasks["stuck-recovery"] = task

        # Cycle 1: Self-heal detects → fails → re-discovers → re-matches → re-assigns
        result = brain.run_cycle(new_tasks=[], now=NOW)
        assert result.tasks_reassigned >= 1
        assert task.retry_count == 1

        # Task went through full recovery in one cycle:
        # IN_PROGRESS → FAILED → DISCOVERED → EVALUATED → OFFERED → ACCEPTED → IN_PROGRESS
        event_stages = [e.to_stage for e in task.events]
        assert "failed" in event_stages
        assert "discovered" in event_stages
        # Task should be back in pipeline, either in_progress or further
        assert task.stage == PipelineStage.IN_PROGRESS
