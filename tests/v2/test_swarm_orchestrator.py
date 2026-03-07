"""
Tests for KK V2 Swarm Orchestrator

Comprehensive test suite covering:
  - State management (load/save/persistence)
  - Startup sequence (batched, ordered by agent type)
  - Health monitoring
  - Self-healing (error recovery, stale heartbeat, circuit breaker)
  - Recovery rate limiting
  - Reputation sync
  - Coordination cycles (full integration)
  - Graceful shutdown (drain + stop)
  - Orchestrator configuration
  - Main loop lifecycle
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))

from services.swarm_orchestrator import (
    AGENT_REGISTRY,
    CycleResult,
    OrchestratorConfig,
    OrchestratorPhase,
    OrchestratorState,
    SwarmOrchestrator,
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

# Helper: start an agent through the valid transition path
def _start_agent(agent, now):
    """Start an agent via valid transition path: OFFLINE → STARTING → IDLE."""
    transition(agent, TransitionReason.STARTUP, now=now)  # OFFLINE → STARTING
    transition(agent, TransitionReason.STARTUP, now=now)  # STARTING → IDLE


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory for orchestrator state."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def small_registry():
    """A smaller agent registry for faster tests."""
    return [
        {"name": "test-coordinator", "type": "system"},
        {"name": "test-validator", "type": "system"},
        {"name": "test-core-1", "type": "core"},
        {"name": "test-user-1", "type": "user"},
        {"name": "test-user-2", "type": "user"},
        {"name": "test-user-3", "type": "user"},
    ]


@pytest.fixture
def config():
    """Default test configuration with shorter intervals."""
    return OrchestratorConfig(
        cycle_interval_seconds=5,
        health_check_interval_seconds=10,
        reputation_sync_interval_seconds=30,
        max_recovery_attempts=3,
        recovery_cooldown_seconds=5,
        drain_timeout_seconds=5,
        startup_batch_delay_seconds=0,
        stale_heartbeat_minutes=5,
    )


@pytest.fixture
def orchestrator(tmp_data_dir, small_registry, config):
    """Create a test orchestrator instance."""
    return SwarmOrchestrator(
        data_dir=tmp_data_dir,
        config=config,
        agent_registry=small_registry,
    )


# ═══════════════════════════════════════════════════════════════════
# OrchestratorState Tests
# ═══════════════════════════════════════════════════════════════════


class TestOrchestratorState:
    """Test state serialization and deserialization."""

    def test_default_state(self):
        state = OrchestratorState()
        assert state.phase == OrchestratorPhase.INIT
        assert state.total_cycles == 0
        assert state.total_tasks_assigned == 0
        assert state.total_agents_recovered == 0
        assert state.total_errors == 0
        assert state.cycle_history == []

    def test_to_dict(self):
        state = OrchestratorState(
            phase=OrchestratorPhase.RUNNING,
            total_cycles=42,
            total_tasks_assigned=10,
        )
        d = state.to_dict()
        assert d["phase"] == "running"
        assert d["total_cycles"] == 42
        assert d["total_tasks_assigned"] == 10
        assert "recent_cycles" in d

    def test_from_dict_roundtrip(self):
        original = OrchestratorState(
            phase=OrchestratorPhase.RUNNING,
            total_cycles=100,
            total_tasks_assigned=50,
            total_agents_recovered=12,
            total_errors=3,
            started_at="2026-03-06T03:00:00+00:00",
            last_cycle_at="2026-03-06T04:00:00+00:00",
        )
        d = original.to_dict()
        restored = OrchestratorState.from_dict(d)

        assert restored.phase == OrchestratorPhase.RUNNING
        assert restored.total_cycles == 100
        assert restored.total_tasks_assigned == 50
        assert restored.total_agents_recovered == 12
        assert restored.total_errors == 3

    def test_from_dict_unknown_phase(self):
        d = {"phase": "nonexistent_phase"}
        state = OrchestratorState.from_dict(d)
        assert state.phase == OrchestratorPhase.INIT

    def test_from_dict_empty(self):
        state = OrchestratorState.from_dict({})
        assert state.phase == OrchestratorPhase.INIT
        assert state.total_cycles == 0


class TestCycleResult:
    """Test cycle result serialization."""

    def test_to_dict(self):
        result = CycleResult(
            cycle_number=1,
            phase="running",
            started_at="2026-03-06T03:00:00Z",
            finished_at="2026-03-06T03:00:01Z",
            duration_ms=1000,
            tasks_found=5,
            tasks_assigned=2,
        )
        d = result.to_dict()
        assert d["cycle"] == 1
        assert d["tasks_found"] == 5
        assert d["tasks_assigned"] == 2
        assert d["duration_ms"] == 1000

    def test_default_values(self):
        result = CycleResult(
            cycle_number=1,
            phase="running",
            started_at="",
            finished_at="",
            duration_ms=0,
        )
        assert result.errors == []
        assert result.warnings == []
        assert result.actions_taken == []
        assert result.matching_mode == "enhanced"


# ═══════════════════════════════════════════════════════════════════
# OrchestratorConfig Tests
# ═══════════════════════════════════════════════════════════════════


class TestOrchestratorConfig:
    """Test orchestrator configuration."""

    def test_defaults(self):
        config = OrchestratorConfig()
        assert config.cycle_interval_seconds == 60
        assert config.health_check_interval_seconds == 300
        assert config.max_recovery_attempts == 3
        assert config.autojob_enabled is False
        assert config.dry_run is False

    def test_custom_config(self):
        config = OrchestratorConfig(
            cycle_interval_seconds=30,
            autojob_enabled=True,
            autojob_path="/path/to/autojob",
        )
        assert config.cycle_interval_seconds == 30
        assert config.autojob_enabled is True
        assert config.autojob_path == "/path/to/autojob"

    def test_to_dict(self):
        config = OrchestratorConfig(dry_run=True)
        d = config.to_dict()
        assert d["dry_run"] is True
        assert "cycle_interval" in d
        assert "autojob_enabled" in d


# ═══════════════════════════════════════════════════════════════════
# State Persistence Tests
# ═══════════════════════════════════════════════════════════════════


class TestStatePersistence:
    """Test loading and saving orchestrator state."""

    def test_load_creates_roster_when_no_state(self, orchestrator, tmp_data_dir):
        orchestrator.load_state()
        assert len(orchestrator.agents) == 6  # small_registry has 6

    def test_save_creates_files(self, orchestrator, tmp_data_dir):
        orchestrator.load_state()
        orchestrator.save_state()

        assert (tmp_data_dir / "lifecycle_state.json").exists()
        assert (tmp_data_dir / "orchestrator_state.json").exists()

    def test_state_roundtrip(self, orchestrator, tmp_data_dir):
        orchestrator.load_state()
        orchestrator.state.total_cycles = 42
        orchestrator.state.total_tasks_assigned = 10
        orchestrator.state.phase = OrchestratorPhase.RUNNING
        orchestrator.save_state()

        # Create new orchestrator, load saved state
        orch2 = SwarmOrchestrator(
            data_dir=tmp_data_dir,
            agent_registry=orchestrator.agent_registry,
        )
        orch2.load_state()

        assert orch2.state.total_cycles == 42
        assert orch2.state.total_tasks_assigned == 10
        assert orch2.state.phase == OrchestratorPhase.RUNNING
        assert len(orch2.agents) == 6

    def test_load_with_corrupted_state(self, orchestrator, tmp_data_dir):
        # Write corrupted JSON
        (tmp_data_dir / "orchestrator_state.json").write_text("not json", encoding="utf-8")
        orchestrator.load_state()
        # Should fall back to default state
        assert orchestrator.state.phase == OrchestratorPhase.INIT
        assert orchestrator.state.total_cycles == 0


# ═══════════════════════════════════════════════════════════════════
# Startup Sequence Tests
# ═══════════════════════════════════════════════════════════════════


class TestStartup:
    """Test the agent startup sequence."""

    @pytest.mark.asyncio
    async def test_startup_starts_all_agents(self, orchestrator):
        orchestrator.load_state()
        started = await orchestrator.startup()

        assert started == 6
        assert orchestrator.state.phase == OrchestratorPhase.RUNNING

        # All agents should be IDLE
        for agent in orchestrator.agents:
            assert agent.state == AgentState.IDLE

    @pytest.mark.asyncio
    async def test_startup_sets_started_at(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        assert orchestrator.state.started_at is not None
        assert orchestrator._start_time is not None

    @pytest.mark.asyncio
    async def test_startup_saves_state(self, orchestrator, tmp_data_dir):
        orchestrator.load_state()
        await orchestrator.startup()

        assert (tmp_data_dir / "lifecycle_state.json").exists()
        assert (tmp_data_dir / "orchestrator_state.json").exists()

    @pytest.mark.asyncio
    async def test_startup_skips_already_running(self, orchestrator):
        orchestrator.load_state()
        # Pre-set some agents to IDLE (already running)
        now = datetime.now(timezone.utc)
        for agent in orchestrator.agents[:2]:
            _start_agent(agent, now)

        started = await orchestrator.startup()
        assert started == 6  # All should be "started" (some were already idle)

    @pytest.mark.asyncio
    async def test_startup_with_batch_delay(self, orchestrator):
        orchestrator.config.startup_batch_delay_seconds = 0.01
        orchestrator.load_state()

        start = time.time()
        await orchestrator.startup()
        elapsed = time.time() - start

        # Should have at least 2 delays (3 batch types: system, core, user)
        assert elapsed >= 0.02


# ═══════════════════════════════════════════════════════════════════
# Health Monitoring Tests
# ═══════════════════════════════════════════════════════════════════


class TestHealthMonitoring:
    """Test health check functionality."""

    def test_run_health_check(self, orchestrator):
        orchestrator.load_state()
        # Start all agents so they're IDLE
        now = datetime.now(timezone.utc)
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        health = orchestrator.run_health_check()

        assert health["total_agents"] == 6
        assert health["online"] == 6
        assert health["error"] == 0
        assert health["availability"] > 0
        assert orchestrator.state.last_health_check_at is not None

    def test_health_check_with_errors(self, orchestrator):
        orchestrator.load_state()
        now = datetime.now(timezone.utc)

        # Start all, then put 2 in error
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        transition(orchestrator.agents[3], TransitionReason.FATAL_ERROR, now=now)
        transition(orchestrator.agents[4], TransitionReason.FATAL_ERROR, now=now)

        health = orchestrator.run_health_check()
        assert health["error"] == 2
        assert health["online"] == 4

    def test_health_report_saved(self, orchestrator, tmp_data_dir):
        orchestrator.load_state()
        now = datetime.now(timezone.utc)
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        health = orchestrator.run_health_check()
        report_path = health.get("report_path")
        assert report_path is not None
        assert Path(report_path).exists()


# ═══════════════════════════════════════════════════════════════════
# Self-Healing Tests
# ═══════════════════════════════════════════════════════════════════


class TestSelfHealing:
    """Test auto-recovery of failed/stale agents."""

    def test_recover_error_agents(self, orchestrator):
        orchestrator.load_state()
        now = datetime.now(timezone.utc)

        # Start all agents
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        # Put a user agent in error
        user_agent = next(a for a in orchestrator.agents if a.agent_type == AgentType.USER)
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)

        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name in recovered
        assert user_agent.state == AgentState.IDLE
        assert user_agent.consecutive_failures == 0

    def test_recover_stale_heartbeat(self, orchestrator):
        orchestrator.load_state()
        orchestrator.config.stale_heartbeat_minutes = 5
        now = datetime.now(timezone.utc)

        # Start all agents
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        # Set stale heartbeat on a user agent (6 minutes ago)
        user_agent = next(a for a in orchestrator.agents if a.agent_type == AgentType.USER)
        stale_time = now - timedelta(minutes=6)
        user_agent.last_heartbeat = stale_time.isoformat()

        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name in recovered
        assert user_agent.state == AgentState.IDLE

    def test_circuit_breaker(self, orchestrator):
        orchestrator.load_state()
        now = datetime.now(timezone.utc)

        # Start all agents
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        # Set high consecutive failures on a user agent
        user_agent = next(a for a in orchestrator.agents if a.agent_type == AgentType.USER)
        user_agent.consecutive_failures = 5

        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name in recovered
        # Circuit breaker puts agent in COOLDOWN, not IDLE
        assert user_agent.state == AgentState.COOLDOWN

    def test_skip_system_agents(self, orchestrator):
        orchestrator.load_state()
        now = datetime.now(timezone.utc)

        # Start all agents
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        # Put system agent in error
        sys_agent = next(a for a in orchestrator.agents if a.agent_type == AgentType.SYSTEM)
        transition(sys_agent, TransitionReason.FATAL_ERROR, now=now)

        recovered = orchestrator.attempt_recovery()
        # System agents should NOT be auto-recovered
        assert sys_agent.agent_name not in recovered

    def test_recovery_rate_limit(self, orchestrator):
        orchestrator.load_state()
        orchestrator.config.max_recovery_attempts = 2
        orchestrator.config.recovery_cooldown_seconds = 1
        now = datetime.now(timezone.utc)

        # Start all agents
        for agent in orchestrator.agents:
            _start_agent(agent, now)

        user_agent = next(a for a in orchestrator.agents if a.agent_type == AgentType.USER)

        # First recovery
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)
        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name in recovered

        # Second recovery (should work after cooldown)
        time.sleep(1.1)
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)
        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name in recovered

        # Third recovery (should be rate-limited — max 2)
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)
        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name not in recovered

    def test_recovery_cooldown_enforced(self, orchestrator):
        orchestrator.load_state()
        orchestrator.config.recovery_cooldown_seconds = 60  # 60s cooldown
        now = datetime.now(timezone.utc)

        for agent in orchestrator.agents:
            _start_agent(agent, now)

        user_agent = next(a for a in orchestrator.agents if a.agent_type == AgentType.USER)

        # First recovery
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)
        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name in recovered

        # Immediate second attempt (within cooldown)
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)
        recovered = orchestrator.attempt_recovery()
        assert user_agent.agent_name not in recovered

    def test_no_recovery_when_all_healthy(self, orchestrator):
        orchestrator.load_state()
        now = datetime.now(timezone.utc)

        # Start all agents with fresh heartbeats
        for agent in orchestrator.agents:
            _start_agent(agent, now)
            agent.last_heartbeat = now.isoformat()

        recovered = orchestrator.attempt_recovery()
        assert recovered == []

    def test_recovery_increments_total(self, orchestrator):
        orchestrator.load_state()
        now = datetime.now(timezone.utc)

        for agent in orchestrator.agents:
            _start_agent(agent, now)

        # Recover two agents
        user_agents = [a for a in orchestrator.agents if a.agent_type == AgentType.USER]
        for ua in user_agents[:2]:
            transition(ua, TransitionReason.FATAL_ERROR, now=now)

        orchestrator.attempt_recovery()
        assert orchestrator.state.total_agents_recovered == 2


# ═══════════════════════════════════════════════════════════════════
# Coordination Cycle Tests
# ═══════════════════════════════════════════════════════════════════


class TestCoordinationCycle:
    """Test the main coordination cycle."""

    @pytest.mark.asyncio
    async def test_basic_cycle(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        result = await orchestrator.run_cycle()

        assert result.cycle_number == 1
        assert result.phase == "running"
        assert result.duration_ms >= 0
        assert result.started_at
        assert result.finished_at

    @pytest.mark.asyncio
    async def test_cycle_increments_counter(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        await orchestrator.run_cycle()
        assert orchestrator.state.total_cycles == 1

        await orchestrator.run_cycle()
        assert orchestrator.state.total_cycles == 2

    @pytest.mark.asyncio
    async def test_cycle_saves_state(self, orchestrator, tmp_data_dir):
        orchestrator.load_state()
        await orchestrator.startup()
        await orchestrator.run_cycle()

        # State should be saved
        state_file = tmp_data_dir / "orchestrator_state.json"
        assert state_file.exists()
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["total_cycles"] == 1

    @pytest.mark.asyncio
    async def test_cycle_health_check_triggered(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        # First cycle should trigger health check (never run before)
        result = await orchestrator.run_cycle()
        assert result.health_checks_run == 1

    @pytest.mark.asyncio
    async def test_cycle_health_check_not_repeated(self, orchestrator):
        orchestrator.load_state()
        orchestrator.config.health_check_interval_seconds = 600
        await orchestrator.startup()

        # First cycle triggers
        result1 = await orchestrator.run_cycle()
        assert result1.health_checks_run == 1

        # Second cycle should NOT trigger (interval not elapsed)
        result2 = await orchestrator.run_cycle()
        assert result2.health_checks_run == 0

    @pytest.mark.asyncio
    async def test_cycle_matching_mode_enhanced(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        result = await orchestrator.run_cycle()
        assert result.matching_mode == "enhanced"

    @pytest.mark.asyncio
    async def test_cycle_matching_mode_legacy(self, orchestrator):
        orchestrator.config.use_legacy_matching = True
        orchestrator.load_state()
        await orchestrator.startup()

        result = await orchestrator.run_cycle()
        assert result.matching_mode == "legacy"

    @pytest.mark.asyncio
    async def test_cycle_matching_mode_autojob(self, orchestrator):
        orchestrator.config.autojob_enabled = True
        orchestrator.load_state()
        await orchestrator.startup()

        result = await orchestrator.run_cycle()
        assert result.matching_mode == "autojob"

    @pytest.mark.asyncio
    async def test_cycle_history_bounded(self, orchestrator):
        orchestrator.load_state()
        orchestrator.config.max_cycle_history = 5
        await orchestrator.startup()

        for _ in range(10):
            await orchestrator.run_cycle()

        assert len(orchestrator.state.cycle_history) == 5

    @pytest.mark.asyncio
    async def test_cycle_recovers_failed_agents(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        # Put a user agent in error
        user_agent = next(
            a for a in orchestrator.agents if a.agent_type == AgentType.USER
        )
        now = datetime.now(timezone.utc)
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)

        result = await orchestrator.run_cycle()
        assert result.agents_recovered >= 1
        assert user_agent.state == AgentState.IDLE

    @pytest.mark.asyncio
    async def test_cycle_error_handling(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        # Patch health check to raise
        with patch.object(orchestrator, 'run_health_check', side_effect=Exception("test error")):
            result = await orchestrator.run_cycle()

        assert len(result.errors) >= 1
        assert orchestrator.state.total_errors >= 1


# ═══════════════════════════════════════════════════════════════════
# Shutdown Tests
# ═══════════════════════════════════════════════════════════════════


class TestShutdown:
    """Test graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_stops_all_agents(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        stopped = await orchestrator.shutdown()

        assert stopped == 6
        assert orchestrator.state.phase == OrchestratorPhase.STOPPED
        for agent in orchestrator.agents:
            assert agent.state == AgentState.OFFLINE

    @pytest.mark.asyncio
    async def test_shutdown_saves_state(self, orchestrator, tmp_data_dir):
        orchestrator.load_state()
        await orchestrator.startup()
        await orchestrator.shutdown()

        state_file = tmp_data_dir / "orchestrator_state.json"
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["phase"] == "stopped"

    @pytest.mark.asyncio
    async def test_shutdown_drains_working_agents(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        # Put a user agent in WORKING state
        user_agent = next(
            a for a in orchestrator.agents if a.agent_type == AgentType.USER
        )
        now = datetime.now(timezone.utc)
        transition(user_agent, TransitionReason.TASK_ASSIGNED, now=now)

        stopped = await orchestrator.shutdown()

        # All should be offline (drain completed or timed out)
        assert stopped >= 5  # At least the non-working ones
        for agent in orchestrator.agents:
            assert agent.state == AgentState.OFFLINE


# ═══════════════════════════════════════════════════════════════════
# Main Loop Tests
# ═══════════════════════════════════════════════════════════════════


class TestMainLoop:
    """Test the main orchestrator loop."""

    @pytest.mark.asyncio
    async def test_run_once(self, orchestrator):
        orchestrator.load_state()

        await orchestrator.run(once=True)

        assert orchestrator.state.total_cycles >= 1
        assert orchestrator.state.phase == OrchestratorPhase.RUNNING

    @pytest.mark.asyncio
    async def test_run_once_saves_state(self, orchestrator, tmp_data_dir):
        await orchestrator.run(once=True)

        state_file = tmp_data_dir / "orchestrator_state.json"
        assert state_file.exists()
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["total_cycles"] >= 1

    @pytest.mark.asyncio
    async def test_shutdown_request_stops_loop(self, orchestrator):
        orchestrator.config.cycle_interval_seconds = 0.1

        async def stop_after_delay():
            await asyncio.sleep(0.3)
            orchestrator._request_shutdown()

        # Run loop and stop it
        task = asyncio.create_task(orchestrator.run(once=False))
        stop_task = asyncio.create_task(stop_after_delay())

        await asyncio.gather(task, stop_task)

        assert orchestrator.state.total_cycles >= 1
        assert orchestrator.state.phase == OrchestratorPhase.STOPPED


# ═══════════════════════════════════════════════════════════════════
# _is_due Tests
# ═══════════════════════════════════════════════════════════════════


class TestIsDue:
    """Test periodic action scheduling."""

    def test_due_when_never_run(self, orchestrator):
        assert orchestrator._is_due("health_check", 300) is True
        assert orchestrator._is_due("reputation_sync", 900) is True

    def test_not_due_recently_run(self, orchestrator):
        orchestrator.state.last_health_check_at = datetime.now(timezone.utc).isoformat()
        assert orchestrator._is_due("health_check", 300) is False

    def test_due_after_interval(self, orchestrator):
        past = datetime.now(timezone.utc) - timedelta(seconds=301)
        orchestrator.state.last_health_check_at = past.isoformat()
        assert orchestrator._is_due("health_check", 300) is True

    def test_unknown_check_type(self, orchestrator):
        assert orchestrator._is_due("unknown", 100) is True

    def test_due_with_invalid_timestamp(self, orchestrator):
        orchestrator.state.last_health_check_at = "not-a-timestamp"
        assert orchestrator._is_due("health_check", 300) is True


# ═══════════════════════════════════════════════════════════════════
# get_status Tests
# ═══════════════════════════════════════════════════════════════════


class TestGetStatus:
    """Test status reporting."""

    @pytest.mark.asyncio
    async def test_status_after_startup(self, orchestrator):
        orchestrator.load_state()
        await orchestrator.startup()

        status = orchestrator.get_status()

        assert "orchestrator" in status
        assert "config" in status
        assert "swarm_health" in status
        assert "agents" in status
        assert status["swarm_health"]["total_agents"] == 6
        assert status["swarm_health"]["online"] == 6

    def test_status_before_startup(self, orchestrator):
        orchestrator.load_state()
        status = orchestrator.get_status()

        assert status["orchestrator"]["phase"] == "init"
        assert len(status["agents"]) == 6


# ═══════════════════════════════════════════════════════════════════
# Agent Registry Tests
# ═══════════════════════════════════════════════════════════════════


class TestAgentRegistry:
    """Test default agent registry."""

    def test_registry_has_system_agents(self):
        system = [a for a in AGENT_REGISTRY if a["type"] == "system"]
        assert len(system) == 2
        names = {a["name"] for a in system}
        assert "kk-coordinator" in names
        assert "kk-validator" in names

    def test_registry_has_core_agents(self):
        core = [a for a in AGENT_REGISTRY if a["type"] == "core"]
        assert len(core) == 4

    def test_registry_has_user_agents(self):
        user = [a for a in AGENT_REGISTRY if a["type"] == "user"]
        assert len(user) >= 14

    def test_total_agents(self):
        assert len(AGENT_REGISTRY) == 24


# ═══════════════════════════════════════════════════════════════════
# Integration: Full Lifecycle
# ═══════════════════════════════════════════════════════════════════


class TestFullLifecycle:
    """Integration tests for the complete orchestrator lifecycle."""

    @pytest.mark.asyncio
    async def test_start_cycle_shutdown(self, orchestrator, tmp_data_dir):
        """Full lifecycle: start → cycle → shutdown."""
        orchestrator.load_state()

        # Startup
        started = await orchestrator.startup()
        assert started == 6
        assert orchestrator.state.phase == OrchestratorPhase.RUNNING

        # Run 3 cycles
        for i in range(3):
            result = await orchestrator.run_cycle()
            assert result.cycle_number == i + 1

        assert orchestrator.state.total_cycles == 3

        # Shutdown
        stopped = await orchestrator.shutdown()
        assert stopped == 6
        assert orchestrator.state.phase == OrchestratorPhase.STOPPED

        # Verify persistence
        state_file = tmp_data_dir / "orchestrator_state.json"
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["total_cycles"] == 3
        assert saved["phase"] == "stopped"

    @pytest.mark.asyncio
    async def test_restart_preserves_history(self, orchestrator, tmp_data_dir, small_registry, config):
        """Restart preserves total counts and history."""
        orchestrator.load_state()
        await orchestrator.startup()
        await orchestrator.run_cycle()
        await orchestrator.run_cycle()
        await orchestrator.shutdown()

        # Create new orchestrator, load from disk
        orch2 = SwarmOrchestrator(
            data_dir=tmp_data_dir,
            config=config,
            agent_registry=small_registry,
        )
        orch2.load_state()

        assert orch2.state.total_cycles == 2
        assert orch2.state.phase == OrchestratorPhase.STOPPED

    @pytest.mark.asyncio
    async def test_cycle_with_failure_and_recovery(self, orchestrator):
        """Agent fails during cycle, gets recovered next cycle."""
        orchestrator.load_state()
        await orchestrator.startup()

        # Run initial cycle
        await orchestrator.run_cycle()

        # Simulate agent failure
        user_agent = next(
            a for a in orchestrator.agents if a.agent_type == AgentType.USER
        )
        now = datetime.now(timezone.utc)
        transition(user_agent, TransitionReason.FATAL_ERROR, now=now)

        # Next cycle should recover
        result = await orchestrator.run_cycle()
        assert result.agents_recovered >= 1
        assert user_agent.state == AgentState.IDLE
        assert orchestrator.state.total_agents_recovered >= 1

    @pytest.mark.asyncio
    async def test_multiple_agents_fail_and_recover(self, orchestrator):
        """Multiple agents fail, all get recovered."""
        orchestrator.load_state()
        await orchestrator.startup()

        now = datetime.now(timezone.utc)
        user_agents = [a for a in orchestrator.agents if a.agent_type == AgentType.USER]

        # Fail all user agents
        for ua in user_agents:
            transition(ua, TransitionReason.FATAL_ERROR, now=now)

        result = await orchestrator.run_cycle()
        assert result.agents_recovered == len(user_agents)
        for ua in user_agents:
            assert ua.state == AgentState.IDLE


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_registry(self, tmp_data_dir, config):
        orch = SwarmOrchestrator(
            data_dir=tmp_data_dir,
            config=config,
            agent_registry=[],
        )
        # Don't call load_state (which may load default registry from disk).
        # Directly set empty agents list.
        orch.agents = []
        orch.state = OrchestratorState()
        started = await orch.startup()
        assert started == 0

    def test_find_nonexistent_agent(self, orchestrator):
        orchestrator.load_state()
        assert orchestrator._find_agent("nonexistent") is None

    def test_find_existing_agent(self, orchestrator):
        orchestrator.load_state()
        agent = orchestrator._find_agent("test-coordinator")
        assert agent is not None
        assert agent.agent_name == "test-coordinator"

    @pytest.mark.asyncio
    async def test_cycle_without_startup(self, orchestrator):
        """Running a cycle without startup should still work (degrade gracefully)."""
        orchestrator.load_state()
        # Don't call startup — agents are in OFFLINE state
        result = await orchestrator.run_cycle()
        assert result.cycle_number == 1
        # Cycle completes even without started agents

    def test_reputation_sync_no_data(self, orchestrator):
        """Reputation sync when no data exists."""
        orchestrator.load_state()
        result = orchestrator.sync_reputation()
        assert result["agents_scored"] >= 0
