"""
Tests for agent_lifecycle.py — Agent state machine, circuit breaker,
heartbeat monitoring, and swarm health assessment.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    TransitionReason,
    LifecycleConfig,
    SwarmHealth,
    # State machine
    is_valid_transition,
    get_next_state,
    transition,
    # Circuit breaker
    should_trip_circuit_breaker,
    compute_cooldown,
    is_cooldown_expired,
    # Heartbeat
    check_heartbeat,
    record_heartbeat,
    # Balance
    check_balance,
    update_balance,
    # Task timeout
    check_task_timeout,
    # Startup planning
    plan_startup_order,
    # Swarm health
    assess_swarm_health,
    recommend_actions,
    # Persistence
    save_lifecycle_state,
    load_lifecycle_state,
    # Helpers
    create_agent_roster,
    get_available_agents,
    get_agents_by_state,
)


NOW = datetime(2026, 2, 24, 4, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return LifecycleConfig()


@pytest.fixture
def agent():
    return AgentLifecycle(agent_name="test-agent", agent_type=AgentType.USER)


@pytest.fixture
def idle_agent():
    a = AgentLifecycle(agent_name="idle-agent", agent_type=AgentType.USER)
    a.state = AgentState.IDLE
    a.state_entered_at = NOW.isoformat()
    a.last_heartbeat = NOW.isoformat()
    return a


@pytest.fixture
def working_agent():
    a = AgentLifecycle(agent_name="working-agent", agent_type=AgentType.USER)
    a.state = AgentState.WORKING
    a.state_entered_at = NOW.isoformat()
    a.current_task_id = "task-123"
    a.current_task_started = NOW.isoformat()
    a.last_heartbeat = NOW.isoformat()
    return a


# ---------------------------------------------------------------------------
# State Machine Transitions
# ---------------------------------------------------------------------------

class TestValidTransitions:
    def test_offline_to_starting(self):
        assert is_valid_transition(AgentState.OFFLINE, TransitionReason.STARTUP)
        assert get_next_state(AgentState.OFFLINE, TransitionReason.STARTUP) == AgentState.STARTING

    def test_starting_to_idle(self):
        assert is_valid_transition(AgentState.STARTING, TransitionReason.STARTUP)
        assert get_next_state(AgentState.STARTING, TransitionReason.STARTUP) == AgentState.IDLE

    def test_idle_to_working(self):
        assert is_valid_transition(AgentState.IDLE, TransitionReason.TASK_ASSIGNED)
        assert get_next_state(AgentState.IDLE, TransitionReason.TASK_ASSIGNED) == AgentState.WORKING

    def test_working_to_idle_on_complete(self):
        assert is_valid_transition(AgentState.WORKING, TransitionReason.TASK_COMPLETED)
        assert get_next_state(AgentState.WORKING, TransitionReason.TASK_COMPLETED) == AgentState.IDLE

    def test_working_to_idle_on_fail(self):
        assert is_valid_transition(AgentState.WORKING, TransitionReason.TASK_FAILED)
        assert get_next_state(AgentState.WORKING, TransitionReason.TASK_FAILED) == AgentState.IDLE

    def test_idle_to_cooldown(self):
        assert is_valid_transition(AgentState.IDLE, TransitionReason.CIRCUIT_BREAKER)
        assert get_next_state(AgentState.IDLE, TransitionReason.CIRCUIT_BREAKER) == AgentState.COOLDOWN

    def test_cooldown_to_idle(self):
        assert is_valid_transition(AgentState.COOLDOWN, TransitionReason.COOLDOWN_EXPIRED)
        assert get_next_state(AgentState.COOLDOWN, TransitionReason.COOLDOWN_EXPIRED) == AgentState.IDLE

    def test_idle_to_stopping(self):
        assert is_valid_transition(AgentState.IDLE, TransitionReason.MANUAL_STOP)

    def test_working_to_draining(self):
        assert is_valid_transition(AgentState.WORKING, TransitionReason.MANUAL_STOP)
        assert get_next_state(AgentState.WORKING, TransitionReason.MANUAL_STOP) == AgentState.DRAINING

    def test_draining_to_stopping(self):
        assert is_valid_transition(AgentState.DRAINING, TransitionReason.DRAIN_COMPLETE)
        assert is_valid_transition(AgentState.DRAINING, TransitionReason.TASK_COMPLETED)

    def test_error_to_starting(self):
        assert is_valid_transition(AgentState.ERROR, TransitionReason.RECOVERY)
        assert is_valid_transition(AgentState.ERROR, TransitionReason.MANUAL_START)


class TestInvalidTransitions:
    def test_idle_cannot_startup(self):
        assert not is_valid_transition(AgentState.IDLE, TransitionReason.STARTUP)

    def test_working_cannot_startup(self):
        assert not is_valid_transition(AgentState.WORKING, TransitionReason.STARTUP)

    def test_offline_cannot_complete_task(self):
        assert not is_valid_transition(AgentState.OFFLINE, TransitionReason.TASK_COMPLETED)

    def test_cooldown_cannot_be_assigned(self):
        assert not is_valid_transition(AgentState.COOLDOWN, TransitionReason.TASK_ASSIGNED)

    def test_error_cannot_be_assigned(self):
        assert not is_valid_transition(AgentState.ERROR, TransitionReason.TASK_ASSIGNED)

    def test_invalid_returns_none(self):
        assert get_next_state(AgentState.OFFLINE, TransitionReason.TASK_COMPLETED) is None


# ---------------------------------------------------------------------------
# Transition Engine
# ---------------------------------------------------------------------------

class TestTransitionEngine:
    def test_successful_transition(self, agent, config):
        """OFFLINE → STARTING should work."""
        event = transition(agent, TransitionReason.STARTUP, config, now=NOW)
        assert event is not None
        assert agent.state == AgentState.STARTING
        assert event.from_state == AgentState.OFFLINE
        assert event.to_state == AgentState.STARTING

    def test_invalid_transition_returns_none(self, agent, config):
        """OFFLINE → TASK_COMPLETED is invalid."""
        event = transition(agent, TransitionReason.TASK_COMPLETED, config, now=NOW)
        assert event is None
        assert agent.state == AgentState.OFFLINE  # Unchanged

    def test_full_lifecycle(self, agent, config):
        """Test complete lifecycle: OFFLINE → STARTING → IDLE → WORKING → IDLE."""
        transition(agent, TransitionReason.STARTUP, config, now=NOW)
        assert agent.state == AgentState.STARTING

        transition(agent, TransitionReason.STARTUP, config, now=NOW)
        assert agent.state == AgentState.IDLE

        transition(agent, TransitionReason.TASK_ASSIGNED, config, now=NOW,
                   details={"task_id": "task-001"})
        assert agent.state == AgentState.WORKING
        assert agent.current_task_id == "task-001"

        transition(agent, TransitionReason.TASK_COMPLETED, config, now=NOW)
        assert agent.state == AgentState.IDLE
        assert agent.current_task_id == ""
        assert agent.total_successes == 1

    def test_task_failure_increments_counter(self, idle_agent, config):
        transition(idle_agent, TransitionReason.TASK_ASSIGNED, config, now=NOW,
                   details={"task_id": "t1"})
        transition(idle_agent, TransitionReason.TASK_FAILED, config, now=NOW)

        assert idle_agent.total_failures == 1
        assert idle_agent.consecutive_failures == 1
        assert idle_agent.state == AgentState.IDLE

    def test_success_resets_consecutive_failures(self, idle_agent, config):
        idle_agent.consecutive_failures = 2

        transition(idle_agent, TransitionReason.TASK_ASSIGNED, config, now=NOW,
                   details={"task_id": "t1"})
        transition(idle_agent, TransitionReason.TASK_COMPLETED, config, now=NOW)

        assert idle_agent.consecutive_failures == 0
        assert idle_agent.total_successes == 1

    def test_circuit_breaker_sets_cooldown(self, idle_agent, config):
        transition(idle_agent, TransitionReason.CIRCUIT_BREAKER, config, now=NOW)

        assert idle_agent.state == AgentState.COOLDOWN
        assert idle_agent.cooldown_until != ""
        assert idle_agent.circuit_breaker_trips == 1

    def test_transition_records_history(self, agent, config):
        transition(agent, TransitionReason.STARTUP, config, now=NOW)
        transition(agent, TransitionReason.STARTUP, config, now=NOW)

        assert len(agent.recent_transitions) == 2
        assert agent.recent_transitions[0]["to"] == "starting"
        assert agent.recent_transitions[1]["to"] == "idle"

    def test_draining_flow(self, working_agent, config):
        """WORKING → DRAINING → STOPPING."""
        transition(working_agent, TransitionReason.MANUAL_STOP, config, now=NOW)
        assert working_agent.state == AgentState.DRAINING

        transition(working_agent, TransitionReason.TASK_COMPLETED, config, now=NOW)
        assert working_agent.state == AgentState.STOPPING

    def test_error_recovery(self, config):
        agent = AgentLifecycle(agent_name="err-agent")
        agent.state = AgentState.ERROR

        transition(agent, TransitionReason.RECOVERY, config, now=NOW)
        assert agent.state == AgentState.STARTING


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_should_not_trip_below_threshold(self, idle_agent, config):
        idle_agent.consecutive_failures = 2
        assert not should_trip_circuit_breaker(idle_agent, config)

    def test_should_trip_at_threshold(self, idle_agent, config):
        idle_agent.consecutive_failures = 3
        assert should_trip_circuit_breaker(idle_agent, config)

    def test_should_trip_above_threshold(self, idle_agent, config):
        idle_agent.consecutive_failures = 5
        assert should_trip_circuit_breaker(idle_agent, config)

    def test_cooldown_increases_with_trips(self):
        c1 = compute_cooldown(1, base=60, max_cooldown=3600, multiplier=2, jitter=0)
        c2 = compute_cooldown(2, base=60, max_cooldown=3600, multiplier=2, jitter=0)
        c3 = compute_cooldown(3, base=60, max_cooldown=3600, multiplier=2, jitter=0)

        assert c1 == 60.0
        assert c2 == 120.0
        assert c3 == 240.0

    def test_cooldown_caps_at_max(self):
        c = compute_cooldown(20, base=60, max_cooldown=3600, multiplier=2, jitter=0)
        assert c == 3600.0

    def test_cooldown_jitter_varies(self):
        """With jitter, consecutive calls should produce different values."""
        results = set()
        for _ in range(20):
            c = compute_cooldown(2, base=60, max_cooldown=3600, multiplier=2, jitter=0.2)
            results.add(round(c))
        # With 20% jitter on 120s, range is 96-144. Should get some variation.
        assert len(results) > 1

    def test_cooldown_expired_true(self, idle_agent):
        idle_agent.state = AgentState.COOLDOWN
        idle_agent.cooldown_until = (NOW - timedelta(minutes=5)).isoformat()
        assert is_cooldown_expired(idle_agent, now=NOW)

    def test_cooldown_not_expired(self, idle_agent):
        idle_agent.state = AgentState.COOLDOWN
        idle_agent.cooldown_until = (NOW + timedelta(minutes=5)).isoformat()
        assert not is_cooldown_expired(idle_agent, now=NOW)

    def test_empty_cooldown_is_expired(self, idle_agent):
        idle_agent.cooldown_until = ""
        assert is_cooldown_expired(idle_agent, now=NOW)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_alive(self, idle_agent, config):
        idle_agent.last_heartbeat = NOW.isoformat()
        assert check_heartbeat(idle_agent, config, now=NOW) == "alive"

    def test_stale(self, idle_agent, config):
        idle_agent.last_heartbeat = (NOW - timedelta(seconds=700)).isoformat()
        assert check_heartbeat(idle_agent, config, now=NOW) == "stale"

    def test_dead(self, idle_agent, config):
        idle_agent.last_heartbeat = (NOW - timedelta(seconds=2000)).isoformat()
        assert check_heartbeat(idle_agent, config, now=NOW) == "dead"

    def test_unknown(self, idle_agent, config):
        idle_agent.last_heartbeat = ""
        assert check_heartbeat(idle_agent, config, now=NOW) == "unknown"

    def test_record_heartbeat(self, idle_agent):
        record_heartbeat(idle_agent, now=NOW)
        assert idle_agent.last_heartbeat == NOW.isoformat()


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

class TestBalance:
    def test_both_ok(self, idle_agent, config):
        idle_agent.usdc_balance = 1.0
        idle_agent.eth_balance = 0.01
        result = check_balance(idle_agent, config)
        assert result["overall_ok"] is True

    def test_usdc_low(self, idle_agent, config):
        idle_agent.usdc_balance = 0.001
        idle_agent.eth_balance = 0.01
        result = check_balance(idle_agent, config)
        assert result["usdc_ok"] is False
        assert result["overall_ok"] is False

    def test_eth_low(self, idle_agent, config):
        idle_agent.usdc_balance = 1.0
        idle_agent.eth_balance = 0.00001
        result = check_balance(idle_agent, config)
        assert result["eth_ok"] is False
        assert result["overall_ok"] is False

    def test_update_balance(self, idle_agent):
        update_balance(idle_agent, usdc=5.5, eth=0.1)
        assert idle_agent.usdc_balance == 5.5
        assert idle_agent.eth_balance == 0.1

    def test_update_partial(self, idle_agent):
        idle_agent.usdc_balance = 1.0
        idle_agent.eth_balance = 0.01
        update_balance(idle_agent, usdc=2.0)
        assert idle_agent.usdc_balance == 2.0
        assert idle_agent.eth_balance == 0.01  # Unchanged


# ---------------------------------------------------------------------------
# Task Timeout
# ---------------------------------------------------------------------------

class TestTaskTimeout:
    def test_no_timeout(self, working_agent, config):
        assert not check_task_timeout(working_agent, config, now=NOW)

    def test_timed_out(self, working_agent, config):
        # Task started 2 hours ago (timeout is 1 hour)
        working_agent.current_task_started = (NOW - timedelta(hours=2)).isoformat()
        assert check_task_timeout(working_agent, config, now=NOW)

    def test_idle_never_timeout(self, idle_agent, config):
        assert not check_task_timeout(idle_agent, config, now=NOW)


# ---------------------------------------------------------------------------
# Startup Planning
# ---------------------------------------------------------------------------

class TestStartupPlanning:
    def test_empty_roster(self, config):
        assert plan_startup_order([], config) == []

    def test_system_first(self, config):
        agents = [
            AgentLifecycle(agent_name="user-1", agent_type=AgentType.USER),
            AgentLifecycle(agent_name="sys-1", agent_type=AgentType.SYSTEM),
            AgentLifecycle(agent_name="core-1", agent_type=AgentType.CORE),
        ]
        batches = plan_startup_order(agents, config)
        assert batches[0] == ["sys-1"]
        assert batches[1] == ["core-1"]
        assert batches[2] == ["user-1"]

    def test_user_agents_batched(self, config):
        config.startup_batch_size = 3
        agents = [
            AgentLifecycle(agent_name=f"user-{i}", agent_type=AgentType.USER)
            for i in range(7)
        ]
        batches = plan_startup_order(agents, config)
        assert len(batches) == 3  # 3 + 3 + 1
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 1


# ---------------------------------------------------------------------------
# Swarm Health
# ---------------------------------------------------------------------------

class TestSwarmHealth:
    def test_empty_swarm(self, config):
        health = assess_swarm_health([], config, now=NOW)
        assert health.total_agents == 0
        assert health.availability_ratio == 0

    def test_all_idle(self, config):
        agents = []
        for i in range(5):
            a = AgentLifecycle(agent_name=f"a-{i}")
            a.state = AgentState.IDLE
            a.last_heartbeat = NOW.isoformat()
            a.usdc_balance = 1.0
            a.eth_balance = 0.01
            agents.append(a)

        health = assess_swarm_health(agents, config, now=NOW)
        assert health.total_agents == 5
        assert health.online_agents == 5
        assert health.idle_agents == 5
        assert health.availability_ratio == 1.0

    def test_mixed_states(self, config):
        agents = [
            _make_agent("a1", AgentState.IDLE),
            _make_agent("a2", AgentState.WORKING),
            _make_agent("a3", AgentState.COOLDOWN),
            _make_agent("a4", AgentState.ERROR),
            _make_agent("a5", AgentState.OFFLINE),
        ]
        for a in agents:
            a.usdc_balance = 1.0
            a.eth_balance = 0.01
            a.last_heartbeat = NOW.isoformat()

        health = assess_swarm_health(agents, config, now=NOW)
        assert health.total_agents == 5
        assert health.online_agents == 2  # IDLE + WORKING
        assert health.idle_agents == 1
        assert health.working_agents == 1
        assert health.cooldown_agents == 1
        assert health.error_agents == 1
        assert health.offline_agents == 1

    def test_success_ratio(self, config):
        agents = [_make_agent("a1", AgentState.IDLE)]
        agents[0].total_successes = 8
        agents[0].total_failures = 2
        agents[0].usdc_balance = 1.0
        agents[0].eth_balance = 0.01
        agents[0].last_heartbeat = NOW.isoformat()

        health = assess_swarm_health(agents, config, now=NOW)
        assert health.success_ratio == 0.8

    def test_detects_low_balance(self, config):
        agents = [_make_agent("a1", AgentState.IDLE)]
        agents[0].usdc_balance = 0.001
        agents[0].eth_balance = 0.0
        agents[0].last_heartbeat = NOW.isoformat()

        health = assess_swarm_health(agents, config, now=NOW)
        assert health.agents_with_low_balance == 1


# ---------------------------------------------------------------------------
# Action Recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:
    def test_no_actions_for_healthy_swarm(self, config):
        agents = [
            _make_agent("a1", AgentState.IDLE, heartbeat=NOW, usdc=1.0, eth=0.01),
        ]
        actions = recommend_actions(agents, config, now=NOW)
        assert len(actions) == 0

    def test_recommends_cooldown_release(self, config):
        a = _make_agent("a1", AgentState.COOLDOWN)
        a.cooldown_until = (NOW - timedelta(minutes=1)).isoformat()
        actions = recommend_actions([a], config, now=NOW)
        assert any(act["action"] == "cooldown_release" for act in actions)

    def test_recommends_task_timeout(self, config):
        a = _make_agent("a1", AgentState.WORKING)
        a.current_task_id = "stuck-task"
        a.current_task_started = (NOW - timedelta(hours=2)).isoformat()
        a.last_heartbeat = NOW.isoformat()
        a.usdc_balance = 1.0
        a.eth_balance = 0.01
        actions = recommend_actions([a], config, now=NOW)
        assert any(act["action"] == "task_timeout" for act in actions)

    def test_recommends_circuit_breaker(self, config):
        a = _make_agent("a1", AgentState.IDLE, heartbeat=NOW, usdc=1.0, eth=0.01)
        a.consecutive_failures = 5
        actions = recommend_actions([a], config, now=NOW)
        assert any(act["action"] == "trip_breaker" for act in actions)

    def test_recommends_recovery_for_dead(self, config):
        a = _make_agent("a1", AgentState.IDLE, usdc=1.0, eth=0.01)
        a.last_heartbeat = (NOW - timedelta(hours=1)).isoformat()
        actions = recommend_actions([a], config, now=NOW)
        assert any(act["action"] == "recover" for act in actions)

    def test_recommends_balance_alert(self, config):
        a = _make_agent("a1", AgentState.IDLE, heartbeat=NOW)
        a.usdc_balance = 0.001
        a.eth_balance = 0.0
        actions = recommend_actions([a], config, now=NOW)
        assert any(act["action"] == "balance_alert" for act in actions)

    def test_actions_sorted_by_priority(self, config):
        agents = [
            _make_agent("err", AgentState.ERROR),  # medium
            _make_agent("dead", AgentState.IDLE, usdc=1.0, eth=0.01),  # critical
        ]
        agents[1].last_heartbeat = (NOW - timedelta(hours=1)).isoformat()
        actions = recommend_actions(agents, config, now=NOW)
        if len(actions) >= 2:
            priorities = [a["priority"] for a in actions]
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            assert all(
                priority_order.get(priorities[i], 4) <= priority_order.get(priorities[i+1], 4)
                for i in range(len(priorities) - 1)
            )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load(self, tmp_path, config):
        agents = [
            _make_agent("a1", AgentState.IDLE, usdc=5.0, eth=0.1),
            _make_agent("a2", AgentState.WORKING),
        ]
        agents[0].total_successes = 10
        agents[0].consecutive_failures = 0
        agents[1].current_task_id = "task-xyz"

        path = tmp_path / "lifecycle.json"
        save_lifecycle_state(agents, path)

        loaded = load_lifecycle_state(path)
        assert len(loaded) == 2

        a1 = next(a for a in loaded if a.agent_name == "a1")
        assert a1.state == AgentState.IDLE
        assert a1.total_successes == 10
        assert a1.usdc_balance == 5.0

        a2 = next(a for a in loaded if a.agent_name == "a2")
        assert a2.state == AgentState.WORKING
        assert a2.current_task_id == "task-xyz"

    def test_load_nonexistent(self, tmp_path):
        loaded = load_lifecycle_state(tmp_path / "nope.json")
        assert loaded == []


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_create_roster(self):
        configs = [
            {"name": "sys-coord", "type": "system"},
            {"name": "worker-1", "type": "user", "usdc_balance": 10.0},
            {"name": "worker-2"},  # Default type
        ]
        roster = create_agent_roster(configs)
        assert len(roster) == 3
        assert roster[0].agent_type == AgentType.SYSTEM
        assert roster[1].usdc_balance == 10.0
        assert roster[2].agent_type == AgentType.USER

    def test_get_available_agents(self):
        agents = [
            _make_agent("a1", AgentState.IDLE),
            _make_agent("a2", AgentState.WORKING),
            _make_agent("a3", AgentState.IDLE),
            _make_agent("a4", AgentState.COOLDOWN),
        ]
        available = get_available_agents(agents)
        assert len(available) == 2
        assert all(a.state == AgentState.IDLE for a in available)

    def test_get_agents_by_state(self):
        agents = [
            _make_agent("a1", AgentState.IDLE),
            _make_agent("a2", AgentState.WORKING),
            _make_agent("a3", AgentState.IDLE),
        ]
        working = get_agents_by_state(agents, AgentState.WORKING)
        assert len(working) == 1
        assert working[0].agent_name == "a2"

    def test_to_dict(self, idle_agent):
        d = idle_agent.to_dict()
        assert d["agent_name"] == "idle-agent"
        assert d["state"] == "idle"
        assert isinstance(d["recent_transitions"], list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(name, state, heartbeat=None, usdc=0.0, eth=0.0):
    a = AgentLifecycle(agent_name=name)
    a.state = state
    if heartbeat:
        a.last_heartbeat = heartbeat.isoformat() if isinstance(heartbeat, datetime) else heartbeat
    a.usdc_balance = usdc
    a.eth_balance = eth
    return a
