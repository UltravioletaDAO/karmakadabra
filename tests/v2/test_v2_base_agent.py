"""
Tests for lib/agent_lifecycle.py — Agent lifecycle state machine.
"""

import sys
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Mock crewai before shared/ loads
for mod_name in ("crewai", "crewai.tools"):
    if mod_name not in sys.modules:
        m = ModuleType(mod_name)
        for attr in ("Agent", "Task", "Crew", "Process", "BaseTool"):
            setattr(m, attr, MagicMock)
        sys.modules[mod_name] = m

from lib.agent_lifecycle import (
    AgentState, AgentType, AgentLifecycle, LifecycleConfig, TransitionReason,
    TransitionEvent, VALID_TRANSITIONS, is_valid_transition, transition,
    should_trip_circuit_breaker, compute_cooldown, record_heartbeat,
    plan_startup_order, create_agent_roster, get_available_agents,
    get_agents_by_state, assess_swarm_health, recommend_actions,
    save_lifecycle_state, load_lifecycle_state,
)


# ── Fixtures ──

SAMPLE_ROSTER_CONFIG = [
    {"name": "coordinator", "type": "system"},
    {"name": "karma-hello", "type": "core"},
    {"name": "worker-1", "type": "user"},
    {"name": "worker-2", "type": "user"},
]


# ── Enums ──

class TestEnums:
    def test_agent_states(self):
        for n in ("OFFLINE", "STARTING", "IDLE", "WORKING", "STOPPING", "COOLDOWN", "ERROR", "DRAINING"):
            assert hasattr(AgentState, n)
        assert len(set(s.value for s in AgentState)) == len(list(AgentState))

    def test_transition_reasons(self):
        for n in ("STARTUP", "TASK_ASSIGNED", "TASK_COMPLETED", "TASK_FAILED",
                   "CIRCUIT_BREAKER", "COOLDOWN_EXPIRED", "MANUAL_STOP", "FATAL_ERROR", "RECOVERY"):
            assert hasattr(TransitionReason, n)

    def test_agent_types(self):
        assert AgentType.SYSTEM.value == "system"
        assert AgentType.CORE.value == "core"


# ── LifecycleConfig ──

class TestLifecycleConfig:
    def test_defaults(self):
        c = LifecycleConfig()
        assert c.circuit_breaker_threshold == 3
        assert c.heartbeat_interval_seconds == 300.0

    def test_custom(self):
        c = LifecycleConfig(circuit_breaker_threshold=10)
        assert c.circuit_breaker_threshold == 10


# ── AgentLifecycle ──

class TestAgentLifecycle:
    def test_create(self):
        lc = AgentLifecycle(agent_name="a")
        assert lc.state == AgentState.OFFLINE
        assert lc.consecutive_failures == 0

    def test_to_dict(self):
        d = AgentLifecycle(agent_name="a").to_dict()
        assert d["agent_name"] == "a"
        assert "state" in d


# ── Transition validation ──

class TestValidTransitions:
    def test_table_populated(self):
        assert len(VALID_TRANSITIONS) > 10

    def test_valid_combos(self):
        assert is_valid_transition(AgentState.OFFLINE, TransitionReason.STARTUP)
        assert is_valid_transition(AgentState.IDLE, TransitionReason.TASK_ASSIGNED)
        assert is_valid_transition(AgentState.WORKING, TransitionReason.TASK_COMPLETED)
        assert is_valid_transition(AgentState.WORKING, TransitionReason.TASK_FAILED)
        assert is_valid_transition(AgentState.COOLDOWN, TransitionReason.COOLDOWN_EXPIRED)
        assert is_valid_transition(AgentState.ERROR, TransitionReason.RECOVERY)

    def test_invalid_combos(self):
        assert not is_valid_transition(AgentState.IDLE, TransitionReason.COOLDOWN_EXPIRED)
        assert not is_valid_transition(AgentState.OFFLINE, TransitionReason.TASK_COMPLETED)


# ── transition() ──

class TestTransition:
    def test_startup(self):
        lc = AgentLifecycle(agent_name="t")
        ev = transition(lc, TransitionReason.STARTUP)
        assert ev is not None
        assert lc.state == AgentState.STARTING

    def test_full_startup(self):
        lc = AgentLifecycle(agent_name="t")
        transition(lc, TransitionReason.STARTUP)
        transition(lc, TransitionReason.STARTUP)
        assert lc.state == AgentState.IDLE

    def test_task_lifecycle(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.IDLE)
        transition(lc, TransitionReason.TASK_ASSIGNED)
        assert lc.state == AgentState.WORKING
        transition(lc, TransitionReason.TASK_COMPLETED)
        assert lc.state == AgentState.IDLE

    def test_task_failure(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.WORKING)
        transition(lc, TransitionReason.TASK_FAILED)
        assert lc.total_failures >= 1

    def test_records_history(self):
        lc = AgentLifecycle(agent_name="t")
        transition(lc, TransitionReason.STARTUP)
        assert len(lc.recent_transitions) >= 1

    def test_invalid_returns_none(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.IDLE)
        ev = transition(lc, TransitionReason.COOLDOWN_EXPIRED)
        assert ev is None
        assert lc.state == AgentState.IDLE  # unchanged

    def test_manual_stop_from_idle(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.IDLE)
        transition(lc, TransitionReason.MANUAL_STOP)
        assert lc.state == AgentState.STOPPING

    def test_drain_from_working(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.WORKING)
        transition(lc, TransitionReason.MANUAL_STOP)
        assert lc.state == AgentState.DRAINING

    def test_fatal_error(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.WORKING)
        transition(lc, TransitionReason.FATAL_ERROR)
        assert lc.state == AgentState.ERROR

    def test_recovery(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.ERROR)
        transition(lc, TransitionReason.RECOVERY)
        assert lc.state == AgentState.STARTING


# ── Circuit breaker ──

class TestCircuitBreaker:
    def test_below(self):
        lc = AgentLifecycle(agent_name="t", consecutive_failures=1)
        assert not should_trip_circuit_breaker(lc, LifecycleConfig(circuit_breaker_threshold=3))

    def test_at(self):
        lc = AgentLifecycle(agent_name="t", consecutive_failures=3)
        assert should_trip_circuit_breaker(lc, LifecycleConfig(circuit_breaker_threshold=3))

    def test_above(self):
        lc = AgentLifecycle(agent_name="t", consecutive_failures=10)
        assert should_trip_circuit_breaker(lc, LifecycleConfig(circuit_breaker_threshold=3))


# ── Cooldown ──

class TestCooldown:
    def test_base(self):
        assert compute_cooldown(0, base=60, jitter=0) >= 60

    def test_exponential(self):
        assert compute_cooldown(2, base=60, jitter=0) > compute_cooldown(0, base=60, jitter=0)

    def test_capped(self):
        assert compute_cooldown(100, base=60, max_cooldown=300, jitter=0) <= 300

    def test_jitter(self):
        # With jitter, result is within ±20% of base
        val = compute_cooldown(0, base=100, jitter=0.2)
        assert 80 <= val <= 120


# ── Heartbeat ──

class TestHeartbeat:
    def test_record(self):
        lc = AgentLifecycle(agent_name="t", state=AgentState.IDLE)
        record_heartbeat(lc)
        assert lc.last_heartbeat != ""


# ── Roster ──

class TestRoster:
    def test_create(self):
        r = create_agent_roster(SAMPLE_ROSTER_CONFIG)
        assert len(r) == 4

    def test_system_type(self):
        r = create_agent_roster(SAMPLE_ROSTER_CONFIG)
        coords = [a for a in r if a.agent_name == "coordinator"]
        assert coords[0].agent_type == AgentType.SYSTEM

    def test_available(self):
        r = create_agent_roster(SAMPLE_ROSTER_CONFIG)
        for a in r:
            a.state = AgentState.IDLE
        avail = get_available_agents(r)
        assert len(avail) == 4

    def test_filter_by_state(self):
        r = create_agent_roster(SAMPLE_ROSTER_CONFIG)
        r[0].state = AgentState.IDLE
        r[1].state = AgentState.WORKING
        assert len(get_agents_by_state(r, AgentState.IDLE)) >= 1
        assert len(get_agents_by_state(r, AgentState.WORKING)) >= 1

    def test_startup_order(self):
        r = create_agent_roster(SAMPLE_ROSTER_CONFIG)
        order = plan_startup_order(r)
        assert len(order) >= 3  # 3 tiers: system, core, user
        # First tier should contain system agents
        assert "coordinator" in order[0]


# ── Swarm health ──

class TestSwarmHealth:
    def test_empty(self):
        assert assess_swarm_health([]) is not None

    def test_healthy(self):
        r = create_agent_roster(SAMPLE_ROSTER_CONFIG)
        for a in r:
            a.state = AgentState.IDLE
            a.last_heartbeat = datetime.now(timezone.utc).isoformat()
        h = assess_swarm_health(r)
        assert h is not None

    def test_actions_empty(self):
        assert isinstance(recommend_actions([]), list)


# ── Serialization ──

class TestSerialization:
    def test_roundtrip(self, tmp_path):
        r = create_agent_roster(SAMPLE_ROSTER_CONFIG)
        r[0].state = AgentState.IDLE
        p = tmp_path / "state.json"
        save_lifecycle_state(r, p)
        loaded = load_lifecycle_state(p)
        assert len(loaded) == 4
        assert loaded[0].agent_name == "coordinator"

    def test_missing_file(self, tmp_path):
        loaded = load_lifecycle_state(tmp_path / "nope.json")
        assert loaded == [] or loaded is not None
