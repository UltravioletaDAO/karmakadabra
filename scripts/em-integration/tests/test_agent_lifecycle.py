"""
Tests for agent_lifecycle.py — Agent Lifecycle Manager

Covers:
  - State machine transitions (valid and invalid)
  - Circuit breaker logic (tripping, cooldown, recovery)
  - Heartbeat monitoring
  - Balance checking
  - Task timeout detection
  - Startup planning
  - Swarm health assessment
  - Action recommendations
  - Persistence (save/load)
  - Edge cases
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    SwarmHealth,
    TransitionEvent,
    TransitionReason,
    assess_swarm_health,
    check_balance,
    check_heartbeat,
    check_task_timeout,
    compute_cooldown,
    create_agent_roster,
    get_agents_by_state,
    get_available_agents,
    get_next_state,
    is_cooldown_expired,
    is_valid_transition,
    load_lifecycle_state,
    plan_startup_order,
    recommend_actions,
    record_heartbeat,
    save_lifecycle_state,
    should_trip_circuit_breaker,
    transition,
    update_balance,
)

NOW = datetime(2026, 2, 23, 0, 0, 0, tzinfo=timezone.utc)


def make_agent(
    name: str = "kk-agent-1",
    state: AgentState = AgentState.OFFLINE,
    agent_type: AgentType = AgentType.USER,
    failures: int = 0,
    successes: int = 0,
    usdc: float = 0.1,
    eth: float = 0.001,
) -> AgentLifecycle:
    """Helper to create an agent."""
    return AgentLifecycle(
        agent_name=name,
        agent_type=agent_type,
        state=state,
        consecutive_failures=failures,
        total_failures=failures,
        total_successes=successes,
        usdc_balance=usdc,
        eth_balance=eth,
    )


# ---------------------------------------------------------------------------
# State Machine Tests
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_valid_startup_transition(self):
        assert is_valid_transition(AgentState.OFFLINE, TransitionReason.STARTUP)
        assert get_next_state(AgentState.OFFLINE, TransitionReason.STARTUP) == AgentState.STARTING

    def test_valid_task_assignment(self):
        assert is_valid_transition(AgentState.IDLE, TransitionReason.TASK_ASSIGNED)
        assert get_next_state(AgentState.IDLE, TransitionReason.TASK_ASSIGNED) == AgentState.WORKING

    def test_valid_task_completion(self):
        assert is_valid_transition(AgentState.WORKING, TransitionReason.TASK_COMPLETED)
        assert get_next_state(AgentState.WORKING, TransitionReason.TASK_COMPLETED) == AgentState.IDLE

    def test_valid_task_failure(self):
        assert is_valid_transition(AgentState.WORKING, TransitionReason.TASK_FAILED)
        assert get_next_state(AgentState.WORKING, TransitionReason.TASK_FAILED) == AgentState.IDLE

    def test_invalid_transition(self):
        assert not is_valid_transition(AgentState.OFFLINE, TransitionReason.TASK_ASSIGNED)
        assert get_next_state(AgentState.OFFLINE, TransitionReason.TASK_ASSIGNED) is None

    def test_circuit_breaker_from_idle(self):
        assert get_next_state(AgentState.IDLE, TransitionReason.CIRCUIT_BREAKER) == AgentState.COOLDOWN

    def test_cooldown_expiry(self):
        assert get_next_state(AgentState.COOLDOWN, TransitionReason.COOLDOWN_EXPIRED) == AgentState.IDLE

    def test_graceful_shutdown_idle(self):
        assert get_next_state(AgentState.IDLE, TransitionReason.MANUAL_STOP) == AgentState.STOPPING

    def test_graceful_shutdown_working(self):
        assert get_next_state(AgentState.WORKING, TransitionReason.MANUAL_STOP) == AgentState.DRAINING

    def test_drain_complete(self):
        assert get_next_state(AgentState.DRAINING, TransitionReason.DRAIN_COMPLETE) == AgentState.STOPPING

    def test_error_recovery(self):
        assert get_next_state(AgentState.ERROR, TransitionReason.RECOVERY) == AgentState.STARTING

    def test_heartbeat_timeout(self):
        assert get_next_state(AgentState.IDLE, TransitionReason.HEARTBEAT_TIMEOUT) == AgentState.ERROR
        assert get_next_state(AgentState.WORKING, TransitionReason.HEARTBEAT_TIMEOUT) == AgentState.ERROR

    def test_balance_low_idle(self):
        assert get_next_state(AgentState.IDLE, TransitionReason.BALANCE_LOW) == AgentState.COOLDOWN

    def test_balance_low_working(self):
        assert get_next_state(AgentState.WORKING, TransitionReason.BALANCE_LOW) == AgentState.DRAINING


# ---------------------------------------------------------------------------
# Transition Engine Tests
# ---------------------------------------------------------------------------

class TestTransitionEngine:
    def test_successful_transition(self):
        agent = make_agent(state=AgentState.OFFLINE)
        event = transition(agent, TransitionReason.STARTUP, now=NOW)
        assert event is not None
        assert event.from_state == AgentState.OFFLINE
        assert event.to_state == AgentState.STARTING
        assert agent.state == AgentState.STARTING

    def test_invalid_transition_returns_none(self):
        agent = make_agent(state=AgentState.OFFLINE)
        event = transition(agent, TransitionReason.TASK_COMPLETED, now=NOW)
        assert event is None
        assert agent.state == AgentState.OFFLINE  # Unchanged

    def test_task_assignment_sets_task_id(self):
        agent = make_agent(state=AgentState.IDLE)
        event = transition(
            agent, TransitionReason.TASK_ASSIGNED, now=NOW,
            details={"task_id": "task-123"},
        )
        assert agent.state == AgentState.WORKING
        assert agent.current_task_id == "task-123"
        assert agent.current_task_started == NOW.isoformat()

    def test_task_completion_clears_task(self):
        agent = make_agent(state=AgentState.WORKING)
        agent.current_task_id = "task-123"
        agent.current_task_started = NOW.isoformat()
        agent.consecutive_failures = 2

        event = transition(agent, TransitionReason.TASK_COMPLETED, now=NOW)
        assert agent.state == AgentState.IDLE
        assert agent.current_task_id == ""
        assert agent.total_successes == 1
        assert agent.consecutive_failures == 0  # Reset on success

    def test_task_failure_increments_failures(self):
        agent = make_agent(state=AgentState.WORKING, failures=1)
        event = transition(agent, TransitionReason.TASK_FAILED, now=NOW)
        assert agent.state == AgentState.IDLE
        assert agent.consecutive_failures == 2
        assert agent.total_failures == 2

    def test_circuit_breaker_sets_cooldown(self):
        agent = make_agent(state=AgentState.IDLE, failures=3)
        config = LifecycleConfig(cooldown_base_seconds=120, cooldown_jitter=0)
        event = transition(agent, TransitionReason.CIRCUIT_BREAKER, config=config, now=NOW)
        assert agent.state == AgentState.COOLDOWN
        assert agent.circuit_breaker_trips == 1
        assert agent.cooldown_until != ""

    def test_transition_recorded_in_history(self):
        agent = make_agent(state=AgentState.OFFLINE)
        transition(agent, TransitionReason.STARTUP, now=NOW)
        assert len(agent.recent_transitions) == 1
        assert agent.recent_transitions[0]["reason"] == "startup"

    def test_history_capped_at_20(self):
        agent = make_agent(state=AgentState.OFFLINE)
        # Cycle through startup → idle → working → complete → idle...
        transition(agent, TransitionReason.STARTUP, now=NOW)
        transition(agent, TransitionReason.STARTUP, now=NOW)  # starting → idle
        for i in range(25):
            agent.state = AgentState.IDLE
            transition(agent, TransitionReason.TASK_ASSIGNED, now=NOW, details={"task_id": f"t{i}"})
            transition(agent, TransitionReason.TASK_COMPLETED, now=NOW)
        assert len(agent.recent_transitions) <= 20

    def test_full_lifecycle(self):
        """Test complete lifecycle: offline → starting → idle → working → idle → stopping → offline."""
        agent = make_agent(state=AgentState.OFFLINE)
        config = LifecycleConfig()

        # Start
        e1 = transition(agent, TransitionReason.STARTUP, config=config, now=NOW)
        assert agent.state == AgentState.STARTING

        # Complete startup
        e2 = transition(agent, TransitionReason.STARTUP, config=config, now=NOW)
        assert agent.state == AgentState.IDLE

        # Assign task
        e3 = transition(agent, TransitionReason.TASK_ASSIGNED, config=config, now=NOW,
                        details={"task_id": "task-1"})
        assert agent.state == AgentState.WORKING

        # Complete task
        e4 = transition(agent, TransitionReason.TASK_COMPLETED, config=config, now=NOW)
        assert agent.state == AgentState.IDLE

        # Stop
        e5 = transition(agent, TransitionReason.MANUAL_STOP, config=config, now=NOW)
        assert agent.state == AgentState.STOPPING

        # Go offline
        e6 = transition(agent, TransitionReason.MANUAL_STOP, config=config, now=NOW)
        assert agent.state == AgentState.OFFLINE

        assert all(e is not None for e in [e1, e2, e3, e4, e5, e6])


# ---------------------------------------------------------------------------
# Circuit Breaker Tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_should_not_trip_below_threshold(self):
        agent = make_agent(failures=2)
        config = LifecycleConfig(circuit_breaker_threshold=3)
        assert not should_trip_circuit_breaker(agent, config)

    def test_should_trip_at_threshold(self):
        agent = make_agent(failures=3)
        config = LifecycleConfig(circuit_breaker_threshold=3)
        assert should_trip_circuit_breaker(agent, config)

    def test_should_trip_above_threshold(self):
        agent = make_agent(failures=5)
        config = LifecycleConfig(circuit_breaker_threshold=3)
        assert should_trip_circuit_breaker(agent, config)

    def test_cooldown_exponential_backoff(self):
        c1 = compute_cooldown(1, base=60, max_cooldown=3600, multiplier=2, jitter=0)
        c2 = compute_cooldown(2, base=60, max_cooldown=3600, multiplier=2, jitter=0)
        c3 = compute_cooldown(3, base=60, max_cooldown=3600, multiplier=2, jitter=0)
        assert c1 == pytest.approx(60, abs=1)
        assert c2 == pytest.approx(120, abs=1)
        assert c3 == pytest.approx(240, abs=1)

    def test_cooldown_max_cap(self):
        c = compute_cooldown(10, base=60, max_cooldown=300, multiplier=2, jitter=0)
        assert c <= 300

    def test_cooldown_jitter(self):
        """Jitter should produce varied results."""
        values = set()
        for _ in range(50):
            c = compute_cooldown(1, base=60, jitter=0.2)
            values.add(round(c))
        # With 20% jitter, we should see some variation
        assert len(values) > 1

    def test_cooldown_expired_true(self):
        agent = make_agent()
        agent.cooldown_until = (NOW - timedelta(minutes=5)).isoformat()
        assert is_cooldown_expired(agent, now=NOW)

    def test_cooldown_expired_false(self):
        agent = make_agent()
        agent.cooldown_until = (NOW + timedelta(minutes=5)).isoformat()
        assert not is_cooldown_expired(agent, now=NOW)

    def test_cooldown_expired_empty(self):
        agent = make_agent()
        assert is_cooldown_expired(agent, now=NOW)

    def test_cooldown_expired_invalid_timestamp(self):
        agent = make_agent()
        agent.cooldown_until = "not-a-date"
        assert is_cooldown_expired(agent, now=NOW)


# ---------------------------------------------------------------------------
# Heartbeat Tests
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_alive(self):
        agent = make_agent()
        agent.last_heartbeat = (NOW - timedelta(seconds=60)).isoformat()
        assert check_heartbeat(agent, now=NOW) == "alive"

    def test_stale(self):
        agent = make_agent()
        config = LifecycleConfig(stale_threshold_seconds=300)
        agent.last_heartbeat = (NOW - timedelta(seconds=400)).isoformat()
        assert check_heartbeat(agent, config=config, now=NOW) == "stale"

    def test_dead(self):
        agent = make_agent()
        config = LifecycleConfig(dead_threshold_seconds=1800)
        agent.last_heartbeat = (NOW - timedelta(seconds=2000)).isoformat()
        assert check_heartbeat(agent, config=config, now=NOW) == "dead"

    def test_unknown_no_heartbeat(self):
        agent = make_agent()
        assert check_heartbeat(agent, now=NOW) == "unknown"

    def test_unknown_bad_timestamp(self):
        agent = make_agent()
        agent.last_heartbeat = "garbage"
        assert check_heartbeat(agent, now=NOW) == "unknown"

    def test_record_heartbeat(self):
        agent = make_agent()
        record_heartbeat(agent, now=NOW)
        assert agent.last_heartbeat == NOW.isoformat()


# ---------------------------------------------------------------------------
# Balance Tests
# ---------------------------------------------------------------------------

class TestBalance:
    def test_balance_ok(self):
        agent = make_agent(usdc=0.5, eth=0.01)
        result = check_balance(agent)
        assert result["overall_ok"]
        assert result["usdc_ok"]
        assert result["eth_ok"]

    def test_balance_low_usdc(self):
        agent = make_agent(usdc=0.001, eth=0.01)
        result = check_balance(agent)
        assert not result["usdc_ok"]
        assert not result["overall_ok"]

    def test_balance_low_eth(self):
        agent = make_agent(usdc=0.5, eth=0.00001)
        result = check_balance(agent)
        assert not result["eth_ok"]
        assert not result["overall_ok"]

    def test_update_balance(self):
        agent = make_agent(usdc=0, eth=0)
        update_balance(agent, usdc=1.5, eth=0.05)
        assert agent.usdc_balance == 1.5
        assert agent.eth_balance == 0.05

    def test_update_partial(self):
        agent = make_agent(usdc=1.0, eth=0.01)
        update_balance(agent, usdc=2.0)
        assert agent.usdc_balance == 2.0
        assert agent.eth_balance == 0.01  # Unchanged


# ---------------------------------------------------------------------------
# Task Timeout Tests
# ---------------------------------------------------------------------------

class TestTaskTimeout:
    def test_no_timeout_not_working(self):
        agent = make_agent(state=AgentState.IDLE)
        assert not check_task_timeout(agent, now=NOW)

    def test_no_timeout_within_limit(self):
        agent = make_agent(state=AgentState.WORKING)
        agent.current_task_started = (NOW - timedelta(minutes=30)).isoformat()
        config = LifecycleConfig(task_timeout_seconds=3600)
        assert not check_task_timeout(agent, config=config, now=NOW)

    def test_timeout_exceeded(self):
        agent = make_agent(state=AgentState.WORKING)
        agent.current_task_started = (NOW - timedelta(hours=2)).isoformat()
        config = LifecycleConfig(task_timeout_seconds=3600)
        assert check_task_timeout(agent, config=config, now=NOW)

    def test_no_timeout_no_start_time(self):
        agent = make_agent(state=AgentState.WORKING)
        assert not check_task_timeout(agent, now=NOW)


# ---------------------------------------------------------------------------
# Startup Planning Tests
# ---------------------------------------------------------------------------

class TestStartupPlanning:
    def test_empty_roster(self):
        batches = plan_startup_order([])
        assert batches == []

    def test_system_first(self):
        agents = [
            make_agent("user-1", agent_type=AgentType.USER),
            make_agent("coord", agent_type=AgentType.SYSTEM),
            make_agent("user-2", agent_type=AgentType.USER),
        ]
        batches = plan_startup_order(agents)
        assert batches[0] == ["coord"]  # System first
        assert "user-1" in batches[1] or "user-2" in batches[1]

    def test_system_then_core_then_user(self):
        agents = [
            make_agent("worker-1", agent_type=AgentType.USER),
            make_agent("extractor", agent_type=AgentType.CORE),
            make_agent("coordinator", agent_type=AgentType.SYSTEM),
        ]
        batches = plan_startup_order(agents)
        assert batches[0] == ["coordinator"]
        assert batches[1] == ["extractor"]
        assert batches[2] == ["worker-1"]

    def test_user_batching(self):
        agents = [make_agent(f"user-{i}", agent_type=AgentType.USER) for i in range(12)]
        config = LifecycleConfig(startup_batch_size=5)
        batches = plan_startup_order(agents, config)
        assert len(batches) == 3  # 5 + 5 + 2
        assert len(batches[0]) == 5
        assert len(batches[1]) == 5
        assert len(batches[2]) == 2

    def test_only_system_agents(self):
        agents = [
            make_agent("coord", agent_type=AgentType.SYSTEM),
            make_agent("validator", agent_type=AgentType.SYSTEM),
        ]
        batches = plan_startup_order(agents)
        assert len(batches) == 1
        assert len(batches[0]) == 2


# ---------------------------------------------------------------------------
# Swarm Health Tests
# ---------------------------------------------------------------------------

class TestSwarmHealth:
    def test_empty_swarm(self):
        health = assess_swarm_health([])
        assert health.total_agents == 0
        assert health.availability_ratio == 0.0

    def test_all_idle(self):
        agents = [make_agent(f"a-{i}", state=AgentState.IDLE) for i in range(5)]
        health = assess_swarm_health(agents, now=NOW)
        assert health.total_agents == 5
        assert health.idle_agents == 5
        assert health.online_agents == 5
        assert health.availability_ratio == 1.0

    def test_mixed_states(self):
        agents = [
            make_agent("idle-1", state=AgentState.IDLE),
            make_agent("idle-2", state=AgentState.IDLE),
            make_agent("work-1", state=AgentState.WORKING),
            make_agent("cool-1", state=AgentState.COOLDOWN),
            make_agent("err-1", state=AgentState.ERROR),
        ]
        health = assess_swarm_health(agents, now=NOW)
        assert health.idle_agents == 2
        assert health.working_agents == 1
        assert health.online_agents == 3  # idle + working
        assert health.cooldown_agents == 1
        assert health.error_agents == 1
        assert health.availability_ratio == pytest.approx(0.6, abs=0.01)

    def test_success_ratio(self):
        agents = [
            make_agent("a", successes=8, failures=2),
            make_agent("b", successes=5, failures=5),
        ]
        health = assess_swarm_health(agents)
        assert health.total_successes == 13
        assert health.total_failures == 7
        assert health.success_ratio == pytest.approx(13 / 20, abs=0.01)

    def test_low_balance_detection(self):
        agents = [
            make_agent("rich", usdc=1.0, eth=0.01),
            make_agent("poor", usdc=0.001, eth=0.00001),
        ]
        health = assess_swarm_health(agents)
        assert health.agents_with_low_balance == 1

    def test_stale_heartbeat_detection(self):
        agents = [
            make_agent("fresh", state=AgentState.IDLE),
            make_agent("stale", state=AgentState.IDLE),
        ]
        agents[0].last_heartbeat = (NOW - timedelta(seconds=60)).isoformat()
        agents[1].last_heartbeat = (NOW - timedelta(seconds=2000)).isoformat()
        health = assess_swarm_health(agents, now=NOW)
        assert health.agents_with_stale_heartbeat == 1

    def test_to_dict(self):
        health = SwarmHealth(total_agents=5, online_agents=3, availability_ratio=0.6)
        d = health.to_dict()
        assert d["total_agents"] == 5
        assert d["online"] == 3
        assert d["availability_ratio"] == 0.6


# ---------------------------------------------------------------------------
# Action Recommendation Tests
# ---------------------------------------------------------------------------

class TestRecommendations:
    def test_expired_cooldown_recommendation(self):
        agent = make_agent("cool", state=AgentState.COOLDOWN)
        agent.cooldown_until = (NOW - timedelta(minutes=5)).isoformat()
        actions = recommend_actions([agent], now=NOW)
        assert any(a["action"] == "cooldown_release" for a in actions)

    def test_task_timeout_recommendation(self):
        agent = make_agent("slow", state=AgentState.WORKING)
        agent.current_task_started = (NOW - timedelta(hours=2)).isoformat()
        agent.current_task_id = "task-stuck"
        config = LifecycleConfig(task_timeout_seconds=3600)
        actions = recommend_actions([agent], config=config, now=NOW)
        assert any(a["action"] == "task_timeout" for a in actions)

    def test_circuit_breaker_recommendation(self):
        agent = make_agent("failing", state=AgentState.IDLE, failures=5)
        config = LifecycleConfig(circuit_breaker_threshold=3)
        actions = recommend_actions([agent], config=config, now=NOW)
        assert any(a["action"] == "trip_breaker" for a in actions)

    def test_dead_heartbeat_recommendation(self):
        agent = make_agent("dead", state=AgentState.IDLE)
        agent.last_heartbeat = (NOW - timedelta(hours=2)).isoformat()
        config = LifecycleConfig(dead_threshold_seconds=1800)
        actions = recommend_actions([agent], config=config, now=NOW)
        assert any(a["action"] == "recover" and a["priority"] == "critical" for a in actions)

    def test_low_balance_recommendation(self):
        agent = make_agent("broke", state=AgentState.IDLE, usdc=0.001, eth=0.00001)
        actions = recommend_actions([agent], now=NOW)
        assert any(a["action"] == "balance_alert" for a in actions)

    def test_error_recovery_recommendation(self):
        agent = make_agent("err", state=AgentState.ERROR)
        actions = recommend_actions([agent], now=NOW)
        assert any(a["action"] == "recover" for a in actions)

    def test_no_actions_for_healthy_swarm(self):
        agents = [make_agent("healthy", state=AgentState.IDLE, usdc=1.0, eth=0.01)]
        agents[0].last_heartbeat = NOW.isoformat()
        actions = recommend_actions(agents, now=NOW)
        # No critical actions for a healthy agent
        assert not any(a["priority"] == "critical" for a in actions)

    def test_actions_sorted_by_priority(self):
        agents = [
            make_agent("dead", state=AgentState.IDLE),
            make_agent("cool", state=AgentState.COOLDOWN),
        ]
        agents[0].last_heartbeat = (NOW - timedelta(hours=5)).isoformat()
        agents[1].cooldown_until = (NOW - timedelta(minutes=1)).isoformat()
        actions = recommend_actions(agents, now=NOW)
        if len(actions) >= 2:
            priorities = [a["priority"] for a in actions]
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            ranks = [priority_order.get(p, 4) for p in priorities]
            assert ranks == sorted(ranks)  # Should be in order


# ---------------------------------------------------------------------------
# Persistence Tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        agents = [
            make_agent("coord", state=AgentState.IDLE, agent_type=AgentType.SYSTEM),
            make_agent("worker", state=AgentState.WORKING),
        ]
        agents[0].last_heartbeat = NOW.isoformat()
        agents[1].current_task_id = "task-42"

        path = tmp_path / "lifecycle.json"
        save_lifecycle_state(agents, path)
        assert path.exists()

        loaded = load_lifecycle_state(path)
        assert len(loaded) == 2
        names = {a.agent_name for a in loaded}
        assert "coord" in names
        assert "worker" in names

        coord = next(a for a in loaded if a.agent_name == "coord")
        assert coord.state == AgentState.IDLE
        assert coord.agent_type == AgentType.SYSTEM
        assert coord.last_heartbeat == NOW.isoformat()

        worker = next(a for a in loaded if a.agent_name == "worker")
        assert worker.state == AgentState.WORKING
        assert worker.current_task_id == "task-42"

    def test_load_nonexistent(self, tmp_path):
        result = load_lifecycle_state(tmp_path / "nope.json")
        assert result == []

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        result = load_lifecycle_state(path)
        assert result == []


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_create_agent_roster(self):
        configs = [
            {"name": "coord", "type": "system", "usdc_balance": 1.0, "eth_balance": 0.01},
            {"name": "worker-1", "type": "user"},
            {"name": "extractor", "type": "core"},
        ]
        agents = create_agent_roster(configs)
        assert len(agents) == 3
        assert agents[0].agent_type == AgentType.SYSTEM
        assert agents[0].usdc_balance == 1.0
        assert agents[1].agent_type == AgentType.USER
        assert agents[2].agent_type == AgentType.CORE

    def test_get_available_agents(self):
        agents = [
            make_agent("idle-1", state=AgentState.IDLE),
            make_agent("work-1", state=AgentState.WORKING),
            make_agent("idle-2", state=AgentState.IDLE),
            make_agent("off-1", state=AgentState.OFFLINE),
        ]
        available = get_available_agents(agents)
        assert len(available) == 2
        assert all(a.state == AgentState.IDLE for a in available)

    def test_get_agents_by_state(self):
        agents = [
            make_agent("a", state=AgentState.IDLE),
            make_agent("b", state=AgentState.WORKING),
            make_agent("c", state=AgentState.WORKING),
        ]
        working = get_agents_by_state(agents, AgentState.WORKING)
        assert len(working) == 2

    def test_agent_to_dict(self):
        agent = make_agent("test", state=AgentState.IDLE)
        agent.last_heartbeat = NOW.isoformat()
        d = agent.to_dict()
        assert d["agent_name"] == "test"
        assert d["state"] == "idle"
        assert d["last_heartbeat"] == NOW.isoformat()

    def test_transition_event_to_dict(self):
        event = TransitionEvent(
            agent_name="test",
            from_state=AgentState.IDLE,
            to_state=AgentState.WORKING,
            reason=TransitionReason.TASK_ASSIGNED,
            timestamp=NOW.isoformat(),
            details={"task_id": "t1"},
        )
        d = event.to_dict()
        assert d["from"] == "idle"
        assert d["to"] == "working"
        assert d["reason"] == "task_assigned"


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_double_startup(self):
        """Starting an already starting agent should fail."""
        agent = make_agent(state=AgentState.STARTING)
        event = transition(agent, TransitionReason.STARTUP, now=NOW)
        # STARTING → STARTUP → IDLE (valid transition)
        assert event is not None
        assert agent.state == AgentState.IDLE

    def test_stop_offline_agent(self):
        """Stopping an offline agent is invalid."""
        agent = make_agent(state=AgentState.OFFLINE)
        event = transition(agent, TransitionReason.MANUAL_STOP, now=NOW)
        assert event is None

    def test_multiple_circuit_breaker_trips(self):
        """Each trip should increase cooldown exponentially."""
        config = LifecycleConfig(
            cooldown_base_seconds=60, cooldown_max_seconds=3600,
            cooldown_multiplier=2, cooldown_jitter=0,
        )
        c1 = compute_cooldown(1, **{
            "base": config.cooldown_base_seconds,
            "max_cooldown": config.cooldown_max_seconds,
            "multiplier": config.cooldown_multiplier,
            "jitter": 0,
        })
        c3 = compute_cooldown(3, **{
            "base": config.cooldown_base_seconds,
            "max_cooldown": config.cooldown_max_seconds,
            "multiplier": config.cooldown_multiplier,
            "jitter": 0,
        })
        assert c3 > c1

    def test_drain_then_complete(self):
        """Agent draining should transition to stopping on task completion."""
        agent = make_agent(state=AgentState.WORKING)
        agent.current_task_id = "task-1"
        # Initiate graceful shutdown
        transition(agent, TransitionReason.MANUAL_STOP, now=NOW)
        assert agent.state == AgentState.DRAINING
        # Task completes during drain
        event = transition(agent, TransitionReason.TASK_COMPLETED, now=NOW)
        assert agent.state == AgentState.STOPPING

    def test_cooldown_zero_trips(self):
        c = compute_cooldown(0, base=60, jitter=0)
        assert c == pytest.approx(60, abs=1)  # 60 * 2^max(0,0-1) = 60 * 2^0 = 60

    def test_all_agent_states_enum_values(self):
        """Verify all states have string values."""
        for state in AgentState:
            assert isinstance(state.value, str)

    def test_all_transition_reasons_enum_values(self):
        for reason in TransitionReason:
            assert isinstance(reason.value, str)

    def test_zero_balance(self):
        agent = make_agent(usdc=0, eth=0)
        result = check_balance(agent)
        assert not result["overall_ok"]
