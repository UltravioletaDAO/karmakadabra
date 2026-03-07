"""
Tests for KK V2 Lifecycle Manager Service.

Covers:
  - Agent lifecycle: start → assign → complete/fail → stop
  - Circuit breaker: consecutive failures → cooldown
  - Heartbeat monitoring: detect stale/dead agents
  - Batch operations: start/stop multiple agents
  - State persistence: save/load
  - Health reporting: aggregate statistics
  - Recovery: agent recovery from cooldown/error states
  - Legacy compatibility: old API still works
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.lifecycle_manager import (
    AgentLifecycleManager,
    AgentStats,
    LifecycleManagerService,
)
from lib.agent_lifecycle import (
    AgentState,
    AgentType,
    LifecycleConfig,
    TransitionReason,
)


# ---------------------------------------------------------------------------
# AgentStats
# ---------------------------------------------------------------------------

class TestAgentStats:
    def test_success_rate_with_data(self):
        stats = AgentStats(
            agent_name="test",
            total_tasks_completed=8,
            total_tasks_failed=2,
        )
        assert stats.success_rate == 0.8

    def test_success_rate_no_tasks(self):
        stats = AgentStats(agent_name="test")
        assert stats.success_rate == 0.0

    def test_mtbf_no_failures(self):
        stats = AgentStats(
            agent_name="test",
            uptime_seconds=3600,
            total_circuit_breaks=0,
        )
        assert stats.mtbf_hours == float("inf")

    def test_mtbf_with_failures(self):
        stats = AgentStats(
            agent_name="test",
            uptime_seconds=7200,
            total_circuit_breaks=2,
        )
        assert stats.mtbf_hours == pytest.approx(1.0)

    def test_to_dict(self):
        stats = AgentStats(
            agent_name="test",
            total_tasks_completed=5,
            total_tasks_failed=1,
        )
        d = stats.to_dict()
        assert d["agent_name"] == "test"
        assert d["tasks_completed"] == 5
        assert d["success_rate"] == pytest.approx(0.833, abs=0.001)


# ---------------------------------------------------------------------------
# Agent Lifecycle Operations
# ---------------------------------------------------------------------------

class TestAgentLifecycle:
    def test_start_agent(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        agent = manager.start_agent("kk-researcher")

        assert agent.state == AgentState.IDLE
        assert agent.agent_name == "kk-researcher"
        assert agent.last_heartbeat is not None
        # State file should exist
        assert (tmp_path / "state" / "kk-researcher.json").exists()

    def test_start_agent_with_type(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        agent = manager.start_agent("kk-coordinator", agent_type=AgentType.SYSTEM)
        assert agent.agent_type == AgentType.SYSTEM

    def test_start_already_running(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        agent = manager.start_agent("a1")
        # Should be idempotent — still IDLE
        assert agent.state == AgentState.IDLE

    def test_stop_agent(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        agent = manager.stop_agent("a1")
        assert agent.state == AgentState.OFFLINE

    def test_stop_already_stopped(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        agent = manager.stop_agent("nonexistent")
        assert agent.state == AgentState.OFFLINE

    def test_assign_task(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        agent = manager.assign_task("a1", "task-001")
        assert agent.state == AgentState.WORKING
        assert agent.current_task_id == "task-001"

    def test_assign_task_not_idle(self, tmp_path):
        """Cannot assign task to non-idle agent."""
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        manager.assign_task("a1", "task-001")  # Now WORKING
        agent = manager.assign_task("a1", "task-002")
        # Should stay with original task
        assert agent.current_task_id == "task-001"

    def test_report_success(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        manager.assign_task("a1", "task-001")
        agent = manager.report_success("a1", task_id="task-001")

        assert agent.state == AgentState.IDLE
        assert agent.current_task_id == ""
        # Stats updated
        stats = manager._get_stats("a1")
        assert stats.total_tasks_completed == 1

    def test_report_failure(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        manager.assign_task("a1", "task-001")
        agent = manager.report_failure("a1", task_id="task-001", error="timeout")

        assert agent.state == AgentState.IDLE
        stats = manager._get_stats("a1")
        assert stats.total_tasks_failed == 1

    def test_drain_working_agent(self, tmp_path):
        """Stop with drain=True should go WORKING → DRAINING."""
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        manager.assign_task("a1", "task-001")
        agent = manager.stop_agent("a1", drain=True)
        assert agent.state == AgentState.DRAINING

    def test_stop_working_no_drain(self, tmp_path):
        """Stop WORKING agent goes through DRAINING (state machine safety).

        The state machine always routes WORKING + MANUAL_STOP → DRAINING
        to protect running tasks, regardless of drain flag.
        """
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        manager.assign_task("a1", "task-001")
        agent = manager.stop_agent("a1", drain=False)
        # State machine protects running tasks
        assert agent.state == AgentState.DRAINING


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_circuit_breaker_trips_on_failures(self, tmp_path):
        config = LifecycleConfig(circuit_breaker_threshold=3)
        manager = LifecycleManagerService(state_dir=tmp_path / "state", config=config)
        manager.start_agent("a1")

        # Fail 3 times
        for i in range(3):
            manager.assign_task("a1", f"fail-{i}")
            agent = manager.report_failure("a1", task_id=f"fail-{i}")

        # Should be in COOLDOWN
        assert agent.state == AgentState.COOLDOWN
        stats = manager._get_stats("a1")
        assert stats.total_circuit_breaks == 1

    def test_circuit_breaker_does_not_trip_on_success(self, tmp_path):
        config = LifecycleConfig(circuit_breaker_threshold=3)
        manager = LifecycleManagerService(state_dir=tmp_path / "state", config=config)
        manager.start_agent("a1")

        # Fail 2 times, then succeed
        for i in range(2):
            manager.assign_task("a1", f"fail-{i}")
            manager.report_failure("a1")

        manager.assign_task("a1", "success-1")
        agent = manager.report_success("a1")

        # Should still be IDLE (success resets consecutive failures)
        assert agent.state == AgentState.IDLE


# ---------------------------------------------------------------------------
# Heartbeat Monitoring
# ---------------------------------------------------------------------------

class TestHeartbeatMonitoring:
    def test_heartbeat_registers(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        result = manager.heartbeat("a1")
        assert result is True

        stats = manager._get_stats("a1")
        assert stats.total_heartbeats == 1

    def test_heartbeat_nonexistent_agent(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        result = manager.heartbeat("nonexistent")
        assert result is False

    def test_check_heartbeats_fresh(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        stale = manager.check_heartbeats(timeout_seconds=300)
        assert "a1" not in stale

    def test_check_heartbeats_stale(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")

        # Manually set old heartbeat
        agent = manager._load_agent("a1")
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        agent.last_heartbeat = old_time
        manager._save_agent(agent)

        stale = manager.check_heartbeats(timeout_seconds=300)
        assert "a1" in stale

    def test_check_heartbeats_skips_offline(self, tmp_path):
        """Offline agents should not be considered stale."""
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        manager.stop_agent("a1")
        stale = manager.check_heartbeats(timeout_seconds=1)
        assert "a1" not in stale


# ---------------------------------------------------------------------------
# Batch Operations
# ---------------------------------------------------------------------------

class TestBatchOperations:
    def test_start_batch(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        agents = manager.start_batch(
            ["kk-researcher", "kk-coder", "kk-coordinator"],
            agent_types={
                "kk-coordinator": AgentType.SYSTEM,
                "kk-researcher": AgentType.USER,
                "kk-coder": AgentType.USER,
            },
        )
        assert len(agents) == 3
        # System agents should be started first
        assert agents[0].agent_name == "kk-coordinator"
        assert agents[0].agent_type == AgentType.SYSTEM

    def test_stop_all(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_batch(["a1", "a2", "a3"])
        results = manager.stop_all(drain=False)
        assert len(results) == 3
        assert all(a.state == AgentState.OFFLINE for a in results)


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

class TestRecovery:
    def test_recover_from_cooldown(self, tmp_path):
        config = LifecycleConfig(circuit_breaker_threshold=2)
        manager = LifecycleManagerService(state_dir=tmp_path / "state", config=config)
        manager.start_agent("a1")

        # Trigger circuit breaker
        for i in range(2):
            manager.assign_task("a1", f"fail-{i}")
            manager.report_failure("a1")

        agent = manager._load_agent("a1")
        assert agent.state == AgentState.COOLDOWN

        # Set cooldown to past
        agent.cooldown_until = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        manager._save_agent(agent)

        # Recover
        recovered = manager.recover_agent("a1")
        assert recovered.state == AgentState.IDLE

        stats = manager._get_stats("a1")
        assert stats.total_recoveries == 1

    def test_recover_while_still_in_cooldown(self, tmp_path):
        config = LifecycleConfig(circuit_breaker_threshold=2)
        manager = LifecycleManagerService(state_dir=tmp_path / "state", config=config)
        manager.start_agent("a1")

        for i in range(2):
            manager.assign_task("a1", f"fail-{i}")
            manager.report_failure("a1")

        # Cooldown is in the future — recovery should fail
        agent = manager.recover_agent("a1")
        assert agent.state == AgentState.COOLDOWN

    def test_recover_non_recoverable_state(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        # Agent is IDLE — not recoverable
        agent = manager.recover_agent("a1")
        assert agent.state == AgentState.IDLE


# ---------------------------------------------------------------------------
# State Queries
# ---------------------------------------------------------------------------

class TestStateQueries:
    def test_get_agent_state(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        state = manager.get_agent_state("a1")
        assert state["agent_name"] == "a1"
        assert state["state"] == "idle"
        assert "stats" in state

    def test_get_all_states(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_batch(["a1", "a2", "a3"])
        states = manager.get_all_states()
        assert len(states) == 3


# ---------------------------------------------------------------------------
# Health Report
# ---------------------------------------------------------------------------

class TestHealthReport:
    def test_health_report_structure(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_batch(["a1", "a2", "a3"])
        manager.assign_task("a1", "t1")
        manager.report_success("a1")

        report = manager.health_report()
        assert report["agents_online"] == 3
        assert report["agents_total"] == 3
        assert report["total_tasks_completed"] == 1
        assert report["total_tasks_failed"] == 0
        assert "by_state" in report
        assert "timestamp" in report

    def test_health_report_with_failures(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_batch(["a1", "a2"])
        manager.assign_task("a1", "t1")
        manager.report_failure("a1")
        manager.stop_agent("a2")

        report = manager.health_report()
        assert report["agents_online"] == 1  # Only a1 (idle after failure)
        assert report["total_tasks_failed"] == 1

    def test_summary_text(self, tmp_path):
        manager = LifecycleManagerService(state_dir=tmp_path / "state")
        manager.start_batch(["a1", "a2"])
        text = manager.summary_text()
        assert "KK Lifecycle Report" in text
        assert "Online: 2/2" in text


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_state_survives_reload(self, tmp_path):
        state_dir = tmp_path / "state"

        # Create and modify agent
        m1 = LifecycleManagerService(state_dir=state_dir)
        m1.start_agent("a1")
        m1.assign_task("a1", "t1")
        m1.report_success("a1")

        # Load fresh manager from same directory
        m2 = LifecycleManagerService(state_dir=state_dir)
        agent = m2._load_agent("a1")
        assert agent.state == AgentState.IDLE
        assert agent.total_successes > 0

    def test_stats_survive_reload(self, tmp_path):
        state_dir = tmp_path / "state"

        m1 = LifecycleManagerService(state_dir=state_dir)
        m1.start_agent("a1")
        m1.assign_task("a1", "t1")
        m1.report_success("a1")

        m2 = LifecycleManagerService(state_dir=state_dir)
        stats = m2._get_stats("a1")
        assert stats.total_tasks_completed == 1

    def test_corrupt_state_handled(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "bad-agent.json").write_text("NOT JSON")

        manager = LifecycleManagerService(state_dir=state_dir)
        agent = manager._load_agent("bad-agent")
        # Should create fresh agent
        assert agent.state == AgentState.OFFLINE


# ---------------------------------------------------------------------------
# Legacy Compatibility
# ---------------------------------------------------------------------------

class TestLegacyCompat:
    def test_legacy_transition(self, tmp_path):
        manager = AgentLifecycleManager(state_dir=tmp_path / "state")
        result = manager.transition("a1", "IDLE")
        assert result["state"] == "idle"

    def test_legacy_get_stale_agents(self, tmp_path):
        manager = AgentLifecycleManager(state_dir=tmp_path / "state")
        manager.start_agent("a1")
        stale = manager.get_stale_agents(timeout_seconds=300)
        assert isinstance(stale, list)
