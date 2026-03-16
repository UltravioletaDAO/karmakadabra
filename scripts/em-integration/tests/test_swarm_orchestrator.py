"""
Tests for KK V2 Swarm Orchestrator

Covers:
  - Agent registry loading and roster creation
  - Status display (output formatting)
  - Startup planning (batch ordering)
  - Health report generation
  - Leaderboard display
  - State persistence (save/load lifecycle state)
  - Action recommendations and self-healing decisions
  - Swarm health aggregation with edge cases
  - Integration: lifecycle + reputation + observability together
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    TransitionReason,
    assess_swarm_health,
    create_agent_roster,
    get_available_agents,
    load_lifecycle_state,
    plan_startup_order,
    recommend_actions,
    save_lifecycle_state,
    transition,
)
from lib.reputation_bridge import (
    UnifiedReputation,
    ReputationTier,
    classify_tier,
    compute_unified_reputation,
    compute_swarm_reputation,
    format_leaderboard_text,
    generate_leaderboard,
    save_reputation_snapshot,
    load_latest_snapshot,
    rank_by_reputation,
    OnChainReputation,
    OffChainReputation,
    TransactionalReputation,
    SealScore,
    compute_on_chain_score,
    extract_off_chain_reputation,
    extract_transactional_reputation,
    reputation_boost_for_matching,
)
from lib.observability import (
    assess_agent_health,
    compute_swarm_metrics,
    generate_health_report,
    save_health_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_config():
    return LifecycleConfig()


@pytest.fixture
def sample_registry():
    """Minimal agent registry like AGENT_REGISTRY in swarm_orchestrator."""
    return [
        {"name": "kk-coordinator", "type": "system"},
        {"name": "kk-validator", "type": "system"},
        {"name": "kk-karma-hello", "type": "core"},
        {"name": "kk-skill-extractor", "type": "core"},
        {"name": "kk-agent-1", "type": "user"},
        {"name": "kk-agent-2", "type": "user"},
        {"name": "kk-agent-3", "type": "user"},
        {"name": "kk-agent-4", "type": "user"},
        {"name": "kk-agent-5", "type": "user"},
        {"name": "kk-agent-6", "type": "user"},
    ]


@pytest.fixture
def full_swarm(sample_registry, base_config):
    """Create a full swarm of agents in various states."""
    agents = create_agent_roster(sample_registry)
    now = datetime.now(timezone.utc)

    # Transition some agents to different states
    transition(agents[0], TransitionReason.STARTUP, base_config, now)  # STARTING
    transition(agents[0], TransitionReason.STARTUP, base_config, now)  # IDLE
    transition(agents[1], TransitionReason.STARTUP, base_config, now)  # STARTING
    transition(agents[1], TransitionReason.STARTUP, base_config, now)  # IDLE

    transition(agents[2], TransitionReason.STARTUP, base_config, now)  # STARTING
    transition(agents[2], TransitionReason.STARTUP, base_config, now)  # IDLE
    transition(agents[2], TransitionReason.TASK_ASSIGNED, base_config, now,
               {"task_id": "task-001"})  # WORKING

    transition(agents[3], TransitionReason.STARTUP, base_config, now)  # STARTING
    transition(agents[3], TransitionReason.STARTUP, base_config, now)  # IDLE

    # Some user agents start too
    transition(agents[4], TransitionReason.STARTUP, base_config, now)
    transition(agents[4], TransitionReason.STARTUP, base_config, now)  # IDLE

    # kk-agent-2 has failures and enters cooldown
    transition(agents[5], TransitionReason.STARTUP, base_config, now)
    transition(agents[5], TransitionReason.STARTUP, base_config, now)
    agents[5].consecutive_failures = 3
    transition(agents[5], TransitionReason.CIRCUIT_BREAKER, base_config, now)  # COOLDOWN

    # kk-agent-3 in ERROR state
    transition(agents[6], TransitionReason.STARTUP, base_config, now)
    transition(agents[6], TransitionReason.STARTUP, base_config, now)
    transition(agents[6], TransitionReason.FATAL_ERROR, base_config, now)  # ERROR

    # Remaining agents stay OFFLINE
    return agents


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ===========================================================================
# Test: Agent Registry & Roster Creation
# ===========================================================================

class TestRosterCreation:
    def test_create_roster_basic(self, sample_registry):
        agents = create_agent_roster(sample_registry)
        assert len(agents) == 10
        assert all(a.state == AgentState.OFFLINE for a in agents)

    def test_create_roster_agent_types(self, sample_registry):
        agents = create_agent_roster(sample_registry)
        system = [a for a in agents if a.agent_type == AgentType.SYSTEM]
        core = [a for a in agents if a.agent_type == AgentType.CORE]
        user = [a for a in agents if a.agent_type == AgentType.USER]
        assert len(system) == 2
        assert len(core) == 2
        assert len(user) == 6

    def test_create_roster_with_balances(self):
        configs = [
            {"name": "a1", "type": "user", "usdc_balance": 5.0, "eth_balance": 0.01},
            {"name": "a2", "type": "user"},
        ]
        agents = create_agent_roster(configs)
        assert agents[0].usdc_balance == 5.0
        assert agents[0].eth_balance == 0.01
        assert agents[1].usdc_balance == 0.0
        assert agents[1].eth_balance == 0.0

    def test_create_roster_names(self, sample_registry):
        agents = create_agent_roster(sample_registry)
        names = {a.agent_name for a in agents}
        assert "kk-coordinator" in names
        assert "kk-validator" in names
        assert "kk-agent-6" in names

    def test_empty_registry(self):
        agents = create_agent_roster([])
        assert len(agents) == 0


# ===========================================================================
# Test: Startup Planning
# ===========================================================================

class TestStartupPlanning:
    def test_three_tier_ordering(self, sample_registry, base_config):
        agents = create_agent_roster(sample_registry)
        batches = plan_startup_order(agents, base_config)

        # First batch: system agents
        assert set(batches[0]) == {"kk-coordinator", "kk-validator"}
        # Second batch: core agents
        assert set(batches[1]) == {"kk-karma-hello", "kk-skill-extractor"}
        # Remaining batches: user agents
        user_agents = set()
        for batch in batches[2:]:
            user_agents.update(batch)
        assert len(user_agents) == 6

    def test_batch_sizing(self, base_config):
        # 12 user agents, batch size 5 → 3 batches
        configs = [{"name": f"agent-{i}", "type": "user"} for i in range(12)]
        agents = create_agent_roster(configs)
        batches = plan_startup_order(agents, base_config)
        # batch_size=5: 12 users → batches of 5, 5, 2
        assert len(batches[0]) == 5
        assert len(batches[1]) == 5
        assert len(batches[2]) == 2

    def test_custom_batch_size(self, sample_registry):
        agents = create_agent_roster(sample_registry)
        config = LifecycleConfig(startup_batch_size=2)
        batches = plan_startup_order(agents, config)
        # system(2) + core(2) + user batches of 2 (3 batches)
        assert len(batches) == 5
        # Each user batch has ≤2 agents
        for batch in batches[2:]:
            assert len(batch) <= 2

    def test_only_system_agents(self, base_config):
        configs = [{"name": "sys-1", "type": "system"}]
        agents = create_agent_roster(configs)
        batches = plan_startup_order(agents, base_config)
        assert len(batches) == 1
        assert batches[0] == ["sys-1"]

    def test_empty_roster_startup(self, base_config):
        batches = plan_startup_order([], base_config)
        assert batches == []


# ===========================================================================
# Test: Swarm Health Assessment (Integration)
# ===========================================================================

class TestSwarmHealthIntegration:
    def test_full_swarm_health(self, full_swarm, base_config):
        health = assess_swarm_health(full_swarm, base_config)
        assert health.total_agents == 10
        # coordinator (idle), validator (idle), skill-extractor (idle), agent-1 (idle) = 4 idle
        # karma-hello (working) = 1 working
        assert health.online_agents == 5  # idle + working
        assert health.working_agents == 1
        assert health.idle_agents == 4
        assert health.cooldown_agents == 1
        assert health.error_agents == 1
        assert health.offline_agents == 3

    def test_availability_ratio(self, full_swarm, base_config):
        health = assess_swarm_health(full_swarm, base_config)
        assert health.availability_ratio == 0.5  # 5 online out of 10

    def test_success_ratio_with_mixed(self, full_swarm, base_config):
        # Add some success/failure records
        full_swarm[0].total_successes = 10
        full_swarm[0].total_failures = 2
        full_swarm[1].total_successes = 5
        full_swarm[5].total_failures = 3  # agent-2 has failures from circuit breaker

        health = assess_swarm_health(full_swarm, base_config)
        total = health.total_successes + health.total_failures
        assert total > 0
        assert 0 <= health.success_ratio <= 1

    def test_all_agents_idle(self, base_config):
        configs = [{"name": f"a-{i}", "type": "user"} for i in range(5)]
        agents = create_agent_roster(configs)
        now = datetime.now(timezone.utc)
        for a in agents:
            transition(a, TransitionReason.STARTUP, base_config, now)
            transition(a, TransitionReason.STARTUP, base_config, now)

        health = assess_swarm_health(agents, base_config)
        assert health.availability_ratio == 1.0
        assert health.idle_agents == 5
        assert health.working_agents == 0

    def test_all_agents_offline(self, base_config):
        configs = [{"name": f"a-{i}", "type": "user"} for i in range(5)]
        agents = create_agent_roster(configs)
        health = assess_swarm_health(agents, base_config)
        assert health.availability_ratio == 0.0
        assert health.offline_agents == 5

    def test_low_balance_detection(self, full_swarm, base_config):
        # All agents start with 0 balance → all online agents flagged
        health = assess_swarm_health(full_swarm, base_config)
        assert health.agents_with_low_balance > 0


# ===========================================================================
# Test: Action Recommendations
# ===========================================================================

class TestActionRecommendations:
    def test_cooldown_release_recommendation(self, base_config):
        agent = AgentLifecycle(agent_name="test-agent", state=AgentState.COOLDOWN)
        # Set cooldown to past
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        agent.cooldown_until = past.isoformat()

        now = datetime.now(timezone.utc)
        actions = recommend_actions([agent], base_config, now)
        cooldown_actions = [a for a in actions if a["action"] == "cooldown_release"]
        assert len(cooldown_actions) == 1

    def test_task_timeout_recommendation(self, base_config):
        agent = AgentLifecycle(agent_name="test-agent", state=AgentState.WORKING)
        agent.current_task_id = "task-slow"
        agent.current_task_started = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).isoformat()

        actions = recommend_actions([agent], base_config)
        timeout_actions = [a for a in actions if a["action"] == "task_timeout"]
        assert len(timeout_actions) == 1

    def test_circuit_breaker_trip_recommendation(self, base_config):
        agent = AgentLifecycle(agent_name="test-agent", state=AgentState.IDLE)
        agent.consecutive_failures = base_config.circuit_breaker_threshold

        actions = recommend_actions([agent], base_config)
        breaker_actions = [a for a in actions if a["action"] == "trip_breaker"]
        assert len(breaker_actions) == 1

    def test_dead_heartbeat_recommendation(self, base_config):
        agent = AgentLifecycle(agent_name="test-agent", state=AgentState.IDLE)
        agent.last_heartbeat = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()

        actions = recommend_actions([agent], base_config)
        recover_actions = [a for a in actions if a["action"] == "recover"]
        assert len(recover_actions) == 1
        assert recover_actions[0]["priority"] == "critical"

    def test_error_state_recovery(self, base_config):
        agent = AgentLifecycle(agent_name="test-agent", state=AgentState.ERROR)
        actions = recommend_actions([agent], base_config)
        recover_actions = [a for a in actions if a["action"] == "recover"]
        assert len(recover_actions) == 1

    def test_balance_alert(self, base_config):
        agent = AgentLifecycle(
            agent_name="test-agent",
            state=AgentState.IDLE,
            usdc_balance=0.0,
            eth_balance=0.0,
        )
        actions = recommend_actions([agent], base_config)
        balance_actions = [a for a in actions if a["action"] == "balance_alert"]
        assert len(balance_actions) == 1

    def test_actions_sorted_by_priority(self, base_config):
        agents = [
            AgentLifecycle(agent_name="low-priority", state=AgentState.ERROR),
            AgentLifecycle(
                agent_name="critical",
                state=AgentState.IDLE,
                last_heartbeat=(
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).isoformat(),
            ),
        ]
        actions = recommend_actions(agents, base_config)
        # Critical should come before medium
        priorities = [a["priority"] for a in actions]
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        numeric = [priority_order.get(p, 4) for p in priorities]
        assert numeric == sorted(numeric)

    def test_no_recommendations_for_healthy_swarm(self, base_config):
        # Idle agent with good balance and fresh heartbeat
        now = datetime.now(timezone.utc)
        agent = AgentLifecycle(
            agent_name="healthy-agent",
            state=AgentState.IDLE,
            usdc_balance=10.0,
            eth_balance=0.1,
            last_heartbeat=now.isoformat(),
        )
        actions = recommend_actions([agent], base_config, now)
        assert len(actions) == 0


# ===========================================================================
# Test: Lifecycle State Persistence
# ===========================================================================

class TestStatePersistence:
    def test_save_and_load_roundtrip(self, full_swarm, tmp_dir):
        path = tmp_dir / "lifecycle_state.json"
        save_lifecycle_state(full_swarm, path)

        loaded = load_lifecycle_state(path)
        assert len(loaded) == len(full_swarm)

        # Verify states preserved
        original_states = {a.agent_name: a.state for a in full_swarm}
        loaded_states = {a.agent_name: a.state for a in loaded}
        assert original_states == loaded_states

    def test_save_creates_directory(self, tmp_dir):
        path = tmp_dir / "nested" / "deep" / "state.json"
        agent = AgentLifecycle(agent_name="test")
        save_lifecycle_state([agent], path)
        assert path.exists()

    def test_load_preserves_agent_types(self, tmp_dir):
        agents = create_agent_roster([
            {"name": "sys", "type": "system"},
            {"name": "core", "type": "core"},
            {"name": "user", "type": "user"},
        ])
        path = tmp_dir / "state.json"
        save_lifecycle_state(agents, path)

        loaded = load_lifecycle_state(path)
        types = {a.agent_name: a.agent_type for a in loaded}
        assert types["sys"] == AgentType.SYSTEM
        assert types["core"] == AgentType.CORE
        assert types["user"] == AgentType.USER

    def test_load_preserves_counters(self, tmp_dir):
        agent = AgentLifecycle(
            agent_name="test",
            total_successes=42,
            total_failures=3,
            circuit_breaker_trips=2,
            consecutive_failures=1,
        )
        path = tmp_dir / "state.json"
        save_lifecycle_state([agent], path)

        loaded = load_lifecycle_state(path)
        assert loaded[0].total_successes == 42
        assert loaded[0].total_failures == 3
        assert loaded[0].circuit_breaker_trips == 2
        assert loaded[0].consecutive_failures == 1

    def test_load_preserves_balances(self, tmp_dir):
        agent = AgentLifecycle(
            agent_name="test", usdc_balance=5.5, eth_balance=0.01
        )
        path = tmp_dir / "state.json"
        save_lifecycle_state([agent], path)

        loaded = load_lifecycle_state(path)
        assert loaded[0].usdc_balance == 5.5
        assert loaded[0].eth_balance == 0.01

    def test_load_nonexistent_file(self, tmp_dir):
        loaded = load_lifecycle_state(tmp_dir / "nonexistent.json")
        assert loaded == []

    def test_load_corrupted_file(self, tmp_dir):
        path = tmp_dir / "bad.json"
        path.write_text("not valid json {{{")
        loaded = load_lifecycle_state(path)
        assert loaded == []

    def test_save_preserves_transitions(self, tmp_dir, base_config):
        agent = AgentLifecycle(agent_name="test")
        now = datetime.now(timezone.utc)
        transition(agent, TransitionReason.STARTUP, base_config, now)
        transition(agent, TransitionReason.STARTUP, base_config, now)

        path = tmp_dir / "state.json"
        save_lifecycle_state([agent], path)

        loaded = load_lifecycle_state(path)
        assert len(loaded[0].recent_transitions) == 2


# ===========================================================================
# Test: Reputation + Lifecycle Integration
# ===========================================================================

class TestReputationLifecycleIntegration:
    """Test that reputation bridge works with lifecycle data for matching."""

    def test_reputation_boost_for_idle_agent(self):
        rep = UnifiedReputation(
            agent_name="test",
            composite_score=80.0,
            effective_confidence=0.8,
        )
        base_score = 0.7
        boosted = reputation_boost_for_matching(rep, base_score, reputation_weight=0.15)
        # With high reputation, score should be boosted slightly
        assert boosted > base_score * 0.85  # At minimum
        assert boosted <= 1.0

    def test_low_reputation_reduces_score(self):
        rep = UnifiedReputation(
            agent_name="test",
            composite_score=20.0,
            effective_confidence=0.8,
        )
        base_score = 0.7
        boosted = reputation_boost_for_matching(rep, base_score, reputation_weight=0.15)
        # Low reputation should pull score down
        assert boosted < base_score

    def test_low_confidence_minimal_effect(self):
        rep = UnifiedReputation(
            agent_name="test",
            composite_score=95.0,
            effective_confidence=0.1,
        )
        base_score = 0.5
        boosted = reputation_boost_for_matching(rep, base_score, reputation_weight=0.15)
        # Low confidence → reputation effect is dampened toward 0.5
        assert abs(boosted - base_score) < 0.1  # Minimal impact

    def test_swarm_reputation_with_multiple_sources(self):
        now = datetime.now(timezone.utc)
        agents_data = {
            "agent-1": {
                "on_chain": [
                    {"seal_type": "SKILLFUL", "quadrant": "A2H", "score": 85,
                     "evaluator": "0x123", "timestamp": now.isoformat()},
                    {"seal_type": "RELIABLE", "quadrant": "A2H", "score": 90,
                     "evaluator": "0x456", "timestamp": now.isoformat()},
                ],
                "off_chain": {
                    "tasks_completed": 15,
                    "tasks_attempted": 18,
                    "reliability_score": 0.85,
                    "avg_rating_received": 82.0,
                    "category_completions": {"physical_verification": 10},
                    "category_attempts": {"physical_verification": 12},
                },
                "transactional": {
                    "avg_rating_received": 88.0,
                    "total_ratings_received": 12,
                },
            },
            "agent-2": {
                "off_chain": {
                    "tasks_completed": 3,
                    "tasks_attempted": 5,
                    "reliability_score": 0.6,
                    "avg_rating_received": 60.0,
                },
            },
        }

        results = compute_swarm_reputation(agents_data)
        assert "agent-1" in results
        assert "agent-2" in results
        # Agent 1 should score higher (more data, better ratings)
        assert results["agent-1"].composite_score > results["agent-2"].composite_score

    def test_leaderboard_generation(self):
        reps = {
            "alpha": UnifiedReputation(
                agent_name="alpha",
                composite_score=90.0,
                effective_confidence=0.9,
                on_chain_score=85.0,
                off_chain_score=92.0,
                transactional_score=88.0,
                sources_available=["on_chain", "off_chain", "transactional"],
            ),
            "beta": UnifiedReputation(
                agent_name="beta",
                composite_score=60.0,
                effective_confidence=0.5,
                on_chain_score=50.0,
                off_chain_score=65.0,
                transactional_score=55.0,
                sources_available=["off_chain"],
            ),
        }
        reps["alpha"].tier = classify_tier(90.0)
        reps["beta"].tier = classify_tier(60.0)

        lb = generate_leaderboard(reps)
        assert len(lb) == 2
        assert lb[0]["agent"] == "alpha"
        assert lb[0]["rank"] == 1
        assert lb[1]["agent"] == "beta"

    def test_leaderboard_text_formatting(self):
        reps = {
            "alpha": UnifiedReputation(
                agent_name="alpha",
                composite_score=90.0,
                effective_confidence=0.9,
                sources_available=["on_chain", "off_chain"],
            ),
        }
        reps["alpha"].tier = ReputationTier.DIAMANTE
        lb = generate_leaderboard(reps)
        text = format_leaderboard_text(lb)
        assert "alpha" in text
        assert "Leaderboard" in text


# ===========================================================================
# Test: Observability Integration
# ===========================================================================

class TestObservabilityIntegration:
    """Test health monitoring + report generation from swarm state."""

    def test_health_report_from_swarm(self, full_swarm, tmp_dir):
        now = datetime.now(timezone.utc)
        snapshots = []
        for agent in full_swarm:
            snap = assess_agent_health(
                agent_name=agent.agent_name,
                last_heartbeat=agent.last_heartbeat or None,
                active_task_id=agent.current_task_id or None,
                tasks_completed_24h=agent.total_successes,
                tasks_failed_24h=agent.total_failures,
                balance_usdc=agent.usdc_balance,
                balance_eth=agent.eth_balance,
                now=now,
            )
            snapshots.append(snap)

        metrics = compute_swarm_metrics(snapshots, now=now)
        report = generate_health_report(snapshots, metrics)

        assert "summary" in report
        assert report["summary"]["total_agents"] == 10

    def test_health_report_save(self, full_swarm, tmp_dir):
        now = datetime.now(timezone.utc)
        snapshots = []
        for agent in full_swarm:
            snap = assess_agent_health(
                agent_name=agent.agent_name,
                now=now,
            )
            snapshots.append(snap)

        metrics = compute_swarm_metrics(snapshots, now=now)
        report = generate_health_report(snapshots, metrics)
        path = save_health_report(report, tmp_dir / "reports")
        assert path.exists()

        # Verify JSON is valid
        data = json.loads(path.read_text())
        assert "summary" in data


# ===========================================================================
# Test: Reputation Snapshot Persistence
# ===========================================================================

class TestReputationSnapshots:
    def test_save_and_load_snapshot(self, tmp_dir):
        reps = {
            "agent-1": UnifiedReputation(
                agent_name="agent-1",
                composite_score=85.0,
                effective_confidence=0.8,
                sources_available=["off_chain"],
            ),
        }
        reps["agent-1"].tier = classify_tier(85.0)

        path = save_reputation_snapshot(reps, tmp_dir / "rep")
        assert path.exists()

        loaded = load_latest_snapshot(tmp_dir / "rep")
        assert "agent-1" in loaded
        assert loaded["agent-1"]["composite_score"] == 85.0

    def test_load_empty_directory(self, tmp_dir):
        (tmp_dir / "empty").mkdir()
        loaded = load_latest_snapshot(tmp_dir / "empty")
        assert loaded == {}

    def test_multiple_snapshots_loads_latest(self, tmp_dir):
        rep_dir = tmp_dir / "rep"

        reps1 = {
            "agent-1": UnifiedReputation(
                agent_name="agent-1", composite_score=60.0
            ),
        }
        reps1["agent-1"].tier = classify_tier(60.0)
        save_reputation_snapshot(reps1, rep_dir)

        # Wait to ensure different filename
        import time
        time.sleep(0.01)

        reps2 = {
            "agent-1": UnifiedReputation(
                agent_name="agent-1", composite_score=90.0
            ),
        }
        reps2["agent-1"].tier = classify_tier(90.0)
        save_reputation_snapshot(reps2, rep_dir)

        loaded = load_latest_snapshot(rep_dir)
        # Should load the latest (90.0), not the first (60.0)
        assert loaded["agent-1"]["composite_score"] == 90.0


# ===========================================================================
# Test: Full Orchestration Scenarios
# ===========================================================================

class TestOrchestrationScenarios:
    """End-to-end orchestration scenarios."""

    def test_full_lifecycle_with_reputation(self, base_config, tmp_dir):
        """Simulate: startup → work → reputation → shutdown."""
        now = datetime.now(timezone.utc)

        # Create roster
        agents = create_agent_roster([
            {"name": "worker-1", "type": "user", "usdc_balance": 5.0, "eth_balance": 0.01},
            {"name": "worker-2", "type": "user", "usdc_balance": 3.0, "eth_balance": 0.005},
        ])

        # Startup
        for a in agents:
            transition(a, TransitionReason.STARTUP, base_config, now)
            transition(a, TransitionReason.STARTUP, base_config, now)

        assert all(a.state == AgentState.IDLE for a in agents)

        # Assign tasks
        transition(agents[0], TransitionReason.TASK_ASSIGNED, base_config, now,
                   {"task_id": "task-A"})
        transition(agents[1], TransitionReason.TASK_ASSIGNED, base_config, now,
                   {"task_id": "task-B"})

        assert all(a.state == AgentState.WORKING for a in agents)

        # Complete tasks
        transition(agents[0], TransitionReason.TASK_COMPLETED, base_config, now)
        transition(agents[1], TransitionReason.TASK_COMPLETED, base_config, now)

        assert all(a.state == AgentState.IDLE for a in agents)
        assert all(a.total_successes == 1 for a in agents)

        # Build reputation
        agents_data = {
            "worker-1": {
                "off_chain": {
                    "tasks_completed": 1,
                    "tasks_attempted": 1,
                    "reliability_score": 1.0,
                    "avg_rating_received": 90.0,
                },
            },
            "worker-2": {
                "off_chain": {
                    "tasks_completed": 1,
                    "tasks_attempted": 1,
                    "reliability_score": 1.0,
                    "avg_rating_received": 85.0,
                },
            },
        }
        reps = compute_swarm_reputation(agents_data)
        assert "worker-1" in reps
        assert reps["worker-1"].composite_score > 0

        # Save everything
        save_lifecycle_state(agents, tmp_dir / "state.json")
        save_reputation_snapshot(reps, tmp_dir / "rep")

        # Verify persistence
        loaded_agents = load_lifecycle_state(tmp_dir / "state.json")
        loaded_reps = load_latest_snapshot(tmp_dir / "rep")
        assert len(loaded_agents) == 2
        assert "worker-1" in loaded_reps

    def test_failure_cascade_and_recovery(self, base_config):
        """Simulate: failures → circuit breaker → cooldown → recovery."""
        now = datetime.now(timezone.utc)

        agent = AgentLifecycle(
            agent_name="fragile-agent",
            agent_type=AgentType.USER,
        )

        # Startup
        transition(agent, TransitionReason.STARTUP, base_config, now)
        transition(agent, TransitionReason.STARTUP, base_config, now)
        assert agent.state == AgentState.IDLE

        # 3 consecutive failures
        for i in range(3):
            transition(agent, TransitionReason.TASK_ASSIGNED, base_config, now,
                       {"task_id": f"task-{i}"})
            transition(agent, TransitionReason.TASK_FAILED, base_config, now)

        assert agent.consecutive_failures == 3
        assert agent.total_failures == 3

        # Circuit breaker trips
        transition(agent, TransitionReason.CIRCUIT_BREAKER, base_config, now)
        assert agent.state == AgentState.COOLDOWN
        assert agent.cooldown_until != ""

        # Fast forward past cooldown
        future = now + timedelta(hours=2)
        transition(agent, TransitionReason.COOLDOWN_EXPIRED, base_config, future)
        assert agent.state == AgentState.IDLE

        # Successful task resets consecutive failures
        transition(agent, TransitionReason.TASK_ASSIGNED, base_config, future,
                   {"task_id": "task-recovery"})
        transition(agent, TransitionReason.TASK_COMPLETED, base_config, future)
        assert agent.consecutive_failures == 0
        assert agent.total_successes == 1

    def test_graceful_shutdown_during_work(self, base_config):
        """Simulate: working → drain → complete → stop → offline."""
        now = datetime.now(timezone.utc)

        agent = AgentLifecycle(agent_name="busy-agent")
        transition(agent, TransitionReason.STARTUP, base_config, now)
        transition(agent, TransitionReason.STARTUP, base_config, now)
        transition(agent, TransitionReason.TASK_ASSIGNED, base_config, now,
                   {"task_id": "important-task"})

        assert agent.state == AgentState.WORKING

        # Shutdown requested → drain
        transition(agent, TransitionReason.MANUAL_STOP, base_config, now)
        assert agent.state == AgentState.DRAINING

        # Task completes during drain
        transition(agent, TransitionReason.TASK_COMPLETED, base_config, now)
        assert agent.state == AgentState.STOPPING

        # Final stop
        transition(agent, TransitionReason.MANUAL_STOP, base_config, now)
        assert agent.state == AgentState.OFFLINE

    def test_multi_agent_matching_with_reputation(self, base_config):
        """Test that reputation affects agent selection for tasks."""
        now = datetime.now(timezone.utc)

        # Two agents, different reputations
        agents = create_agent_roster([
            {"name": "expert", "type": "user"},
            {"name": "novice", "type": "user"},
        ])
        for a in agents:
            transition(a, TransitionReason.STARTUP, base_config, now)
            transition(a, TransitionReason.STARTUP, base_config, now)

        # Expert has better reputation
        expert_rep = UnifiedReputation(
            agent_name="expert",
            composite_score=90.0,
            effective_confidence=0.9,
        )
        novice_rep = UnifiedReputation(
            agent_name="novice",
            composite_score=40.0,
            effective_confidence=0.7,
        )

        base_match = 0.6  # Same base match score for both
        expert_boosted = reputation_boost_for_matching(expert_rep, base_match, 0.15)
        novice_boosted = reputation_boost_for_matching(novice_rep, base_match, 0.15)

        # Expert should have higher boosted score
        assert expert_boosted > novice_boosted

    def test_swarm_ranking_consistency(self):
        """Test that ranking is deterministic and consistent."""
        reps = {}
        for i, (name, score) in enumerate([
            ("diamond-1", 95), ("diamond-2", 85), ("gold-1", 75),
            ("silver-1", 50), ("bronze-1", 15),
        ]):
            r = UnifiedReputation(agent_name=name, composite_score=score)
            r.tier = classify_tier(score)
            r.effective_confidence = 0.8
            reps[name] = r

        ranked = rank_by_reputation(reps)
        assert ranked[0][0] == "diamond-1"
        assert ranked[-1][0] == "bronze-1"
        # Scores descending
        scores = [s for _, s, _ in ranked]
        assert scores == sorted(scores, reverse=True)


# ===========================================================================
# Test: Edge Cases
# ===========================================================================

class TestEdgeCases:
    def test_single_agent_swarm(self, base_config):
        agents = create_agent_roster([{"name": "lonely", "type": "user"}])
        health = assess_swarm_health(agents, base_config)
        assert health.total_agents == 1
        assert health.offline_agents == 1
        assert health.availability_ratio == 0.0

    def test_all_agents_in_error(self, base_config):
        now = datetime.now(timezone.utc)
        configs = [{"name": f"broken-{i}", "type": "user"} for i in range(5)]
        agents = create_agent_roster(configs)
        for a in agents:
            transition(a, TransitionReason.STARTUP, base_config, now)
            transition(a, TransitionReason.STARTUP, base_config, now)
            transition(a, TransitionReason.FATAL_ERROR, base_config, now)

        health = assess_swarm_health(agents, base_config)
        assert health.error_agents == 5
        assert health.online_agents == 0

        actions = recommend_actions(agents, base_config, now)
        assert len(actions) == 5  # All need recovery

    def test_reputation_with_no_data(self):
        rep = compute_unified_reputation("unknown-agent")
        assert rep.composite_score == 50.0
        assert rep.tier == ReputationTier.PLATA
        assert rep.effective_confidence == 0.0

    def test_rapid_transitions(self, base_config):
        """Test rapid state changes don't corrupt state."""
        now = datetime.now(timezone.utc)
        agent = AgentLifecycle(agent_name="rapid-agent")

        transition(agent, TransitionReason.STARTUP, base_config, now)
        transition(agent, TransitionReason.STARTUP, base_config, now)

        # 10 rapid task cycles
        for i in range(10):
            transition(agent, TransitionReason.TASK_ASSIGNED, base_config, now,
                       {"task_id": f"task-{i}"})
            transition(agent, TransitionReason.TASK_COMPLETED, base_config, now)

        assert agent.state == AgentState.IDLE
        assert agent.total_successes == 10
        assert agent.consecutive_failures == 0

    def test_large_swarm_health(self, base_config):
        """Test with 100 agents."""
        configs = [{"name": f"agent-{i}", "type": "user"} for i in range(100)]
        agents = create_agent_roster(configs)
        now = datetime.now(timezone.utc)

        # Start half
        for a in agents[:50]:
            transition(a, TransitionReason.STARTUP, base_config, now)
            transition(a, TransitionReason.STARTUP, base_config, now)

        health = assess_swarm_health(agents, base_config)
        assert health.total_agents == 100
        assert health.online_agents == 50
        assert health.offline_agents == 50
        assert health.availability_ratio == 0.5

    def test_reputation_snapshot_roundtrip_with_all_fields(self, tmp_dir):
        """Full fidelity roundtrip for reputation data."""
        rep = UnifiedReputation(
            agent_name="full-agent",
            agent_address="0x1234567890abcdef1234567890abcdef12345678",
            agent_id=42,
            on_chain_score=85.0,
            off_chain_score=72.0,
            transactional_score=90.0,
            on_chain_confidence=0.8,
            off_chain_confidence=0.6,
            transactional_confidence=0.9,
            composite_score=82.5,
            effective_confidence=0.77,
            tier=ReputationTier.DIAMANTE,
            sources_available=["on_chain", "off_chain", "transactional"],
            weights_used={"on_chain": 0.3, "off_chain": 0.4, "transactional": 0.3},
            seal_type_scores={"SKILLFUL": 88.0, "RELIABLE": 82.0},
            category_strengths={"physical_verification": 0.9, "data_collection": 0.7},
        )

        path = save_reputation_snapshot({"full-agent": rep}, tmp_dir / "rep")
        loaded = load_latest_snapshot(tmp_dir / "rep")

        assert loaded["full-agent"]["composite_score"] == 82.5
        assert loaded["full-agent"]["agent_address"] == "0x1234567890abcdef1234567890abcdef12345678"
        assert loaded["full-agent"]["agent_id"] == 42
        assert "SKILLFUL" in loaded["full-agent"]["seal_type_scores"]
