#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 — Full-Chain Swarm Integration Test

Validates that ALL swarm components work together end-to-end:

  Lifecycle → Reputation → Coordinator Matching → Dispatch → Evidence → Health

This is the "glue test" — it doesn't test individual components (those have
their own test files), it tests that the INTERFACES between components are
compatible and the data flows correctly through the entire pipeline.

Component chain tested:
  1. agent_lifecycle: roster creation → startup → state transitions
  2. reputation_bridge: tri-layer scoring → unified reputation → leaderboard
  3. coordinator matching: skill + performance + reputation → ranked agents
  4. swarm_dispatch: task dispatch → tracking → stall detection → reassignment
  5. agent_lifecycle: task assignment → completion/failure → circuit breaker
  6. health assessment: swarm metrics → recommendations → status display
  7. persistence: save/load lifecycle state + reputation snapshots

Usage:
    pytest tests/v2/test_swarm_full_chain.py -v
    python tests/v2/test_swarm_full_chain.py
"""

import json
import math
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    SwarmHealth,
    TransitionReason,
    assess_swarm_health,
    check_balance,
    check_heartbeat,
    check_task_timeout,
    compute_cooldown,
    create_agent_roster,
    get_available_agents,
    is_cooldown_expired,
    load_lifecycle_state,
    plan_startup_order,
    recommend_actions,
    record_heartbeat,
    save_lifecycle_state,
    should_trip_circuit_breaker,
    transition,
    update_balance,
)
from lib.reputation_bridge import (
    DataSource,
    OffChainReputation,
    OnChainReputation,
    ReputationTier,
    SealScore,
    TransactionalReputation,
    UnifiedReputation,
    classify_tier,
    compute_on_chain_score,
    compute_swarm_reputation,
    compute_unified_reputation,
    extract_off_chain_reputation,
    extract_transactional_reputation,
    format_leaderboard_text,
    generate_leaderboard,
    load_latest_snapshot,
    load_reputation_snapshot,
    rank_by_reputation,
    reputation_boost_for_matching,
    save_reputation_snapshot,
)
from services.swarm_dispatch import (
    DispatchQueue,
    DispatchRecord,
    dispatch_task,
    check_stalled_tasks,
    reassign_failed_task,
    mark_completed,
    mark_acknowledged,
    dispatch_cycle,
    load_dispatch_queue,
    save_dispatch_queue,
    format_irc_assignment,
    format_irc_stall_warning,
    format_irc_reassignment,
)


# ---------------------------------------------------------------------------
# Test Fixtures — Shared Swarm State
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 2, 5, 0, 0, tzinfo=timezone.utc)

AGENT_REGISTRY = [
    {"name": "kk-coordinator", "type": "system"},
    {"name": "kk-validator", "type": "system"},
    {"name": "kk-karma-hello", "type": "core"},
    {"name": "kk-skill-extractor", "type": "core"},
    {"name": "kk-agent-alpha", "type": "user"},
    {"name": "kk-agent-beta", "type": "user"},
    {"name": "kk-agent-gamma", "type": "user"},
    {"name": "kk-agent-delta", "type": "user"},
    {"name": "kk-agent-epsilon", "type": "user"},
    {"name": "kk-agent-zeta", "type": "user"},
]

SAMPLE_TASKS = [
    {
        "id": "task-001",
        "title": "Photograph the sunset at a local park",
        "instructions": "Take a high-quality photo of the sunset. Include GPS metadata.",
        "category": "photography",
        "bounty_usd": 2.50,
        "payment_network": "base",
        "evidence_types": ["photo_geo"],
    },
    {
        "id": "task-002",
        "title": "Verify restaurant operating hours",
        "instructions": "Visit the restaurant and confirm the posted operating hours match their online listing.",
        "category": "verification",
        "bounty_usd": 1.00,
        "payment_network": "polygon",
        "evidence_types": ["photo", "text_response"],
    },
    {
        "id": "task-003",
        "title": "Transcribe handwritten recipe from grandmother's cookbook",
        "instructions": "Digitize a handwritten recipe. Type out all ingredients and steps accurately.",
        "category": "transcription",
        "bounty_usd": 3.00,
        "payment_network": "base",
        "evidence_types": ["text_response", "photo"],
    },
    {
        "id": "task-004",
        "title": "Code review for Solidity smart contract",
        "instructions": "Review a 200-line Solidity contract for security vulnerabilities.",
        "category": "code_review",
        "bounty_usd": 10.00,
        "payment_network": "ethereum",
        "evidence_types": ["text_response", "document"],
    },
]


@pytest.fixture
def config():
    """Lifecycle configuration with fast timeouts for testing."""
    return LifecycleConfig(
        circuit_breaker_threshold=3,
        cooldown_base_seconds=10.0,
        cooldown_max_seconds=60.0,
        cooldown_multiplier=2.0,
        cooldown_jitter=0.0,  # Deterministic for testing
        heartbeat_interval_seconds=60.0,
        stale_threshold_seconds=120.0,
        dead_threshold_seconds=300.0,
        min_usdc_balance=0.01,
        min_eth_balance=0.0001,
        startup_batch_size=3,
        task_timeout_seconds=600.0,
    )


@pytest.fixture
def agents():
    """Create a fresh agent roster."""
    roster = create_agent_roster(AGENT_REGISTRY)
    return roster


@pytest.fixture
def tmp_dir():
    """Temporary directory for state persistence."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ---------------------------------------------------------------------------
# Phase 1: Lifecycle — Startup Sequence
# ---------------------------------------------------------------------------


class TestPhase1Startup:
    """Test the startup sequence: OFFLINE → STARTING → IDLE."""

    def test_roster_creation(self, agents):
        """All agents start OFFLINE with correct types."""
        assert len(agents) == 10
        system = [a for a in agents if a.agent_type == AgentType.SYSTEM]
        core = [a for a in agents if a.agent_type == AgentType.CORE]
        user = [a for a in agents if a.agent_type == AgentType.USER]
        assert len(system) == 2
        assert len(core) == 2
        assert len(user) == 6
        for a in agents:
            assert a.state == AgentState.OFFLINE

    def test_startup_batch_planning(self, agents, config):
        """Startup is batched: system → core → user in groups."""
        batches = plan_startup_order(agents, config)
        # System agents first
        assert set(batches[0]) == {"kk-coordinator", "kk-validator"}
        # Core agents second
        assert set(batches[1]) == {"kk-karma-hello", "kk-skill-extractor"}
        # User agents in batches of 3
        assert len(batches[2]) == 3
        assert len(batches[3]) == 3

    def test_full_startup_sequence(self, agents, config):
        """All agents transition through OFFLINE → STARTING → IDLE."""
        for agent in agents:
            # Start
            ev1 = transition(agent, TransitionReason.STARTUP, config, NOW)
            assert ev1 is not None
            assert agent.state == AgentState.STARTING

            # Complete startup
            ev2 = transition(agent, TransitionReason.STARTUP, config, NOW)
            assert ev2 is not None
            assert agent.state == AgentState.IDLE

        # All should now be idle
        available = get_available_agents(agents)
        assert len(available) == 10

    def test_startup_with_funding(self, agents, config):
        """Agents with balances remain available; unfunded trigger alerts."""
        # Start all agents
        for agent in agents:
            transition(agent, TransitionReason.STARTUP, config, NOW)
            transition(agent, TransitionReason.STARTUP, config, NOW)

        # Fund some agents
        for i, agent in enumerate(agents):
            if i < 6:
                update_balance(agent, usdc=5.0, eth=0.01)
            else:
                update_balance(agent, usdc=0.0, eth=0.0)

        # Check health recommends balance alerts
        actions = recommend_actions(agents, config, NOW)
        balance_alerts = [a for a in actions if a["action"] == "balance_alert"]
        assert len(balance_alerts) == 4  # 4 unfunded agents


# ---------------------------------------------------------------------------
# Phase 2: Reputation — Tri-Layer Scoring
# ---------------------------------------------------------------------------


class TestPhase2Reputation:
    """Test reputation scoring flows into the coordinator matching."""

    def test_on_chain_scoring(self):
        """On-chain seals produce time-weighted scores."""
        seals = [
            SealScore("SKILLFUL", "A2H", 85, "0xeval1",
                       (NOW - timedelta(days=5)).isoformat(), "", 1),
            SealScore("RELIABLE", "A2H", 90, "0xeval2",
                       (NOW - timedelta(days=30)).isoformat(), "", 2),
            SealScore("SKILLFUL", "A2H", 60, "0xeval3",
                       (NOW - timedelta(days=180)).isoformat(), "", 3),
        ]
        rep = compute_on_chain_score(seals, time_decay_days=90.0, now=NOW)
        # Recent seals should weigh more
        assert rep.type_averages["SKILLFUL"] > 70  # Recent 85 should dominate old 60
        assert rep.type_averages["RELIABLE"] > 85  # Only one seal, close to 90
        assert rep.confidence > 0.3
        assert 0 <= rep.normalized_score <= 100

    def test_off_chain_scoring(self):
        """Performance data converts to normalized scores."""
        perf_data = {
            "tasks_completed": 25,
            "tasks_attempted": 30,
            "reliability_score": 0.83,
            "avg_rating_received": 78.0,
            "category_completions": {
                "photography": 10,
                "verification": 8,
                "transcription": 5,
            },
            "category_attempts": {
                "photography": 12,
                "verification": 9,
                "transcription": 6,
            },
            "chain_tasks": {"base": 15, "polygon": 8, "ethereum": 2},
            "total_earned_usd": 45.0,
        }
        rep = extract_off_chain_reputation("kk-agent-alpha", perf_data)
        assert rep.completion_rate == 25 / 30
        assert rep.reliability_score == 0.83
        assert rep.avg_rating == 78.0
        assert len(rep.category_strengths) == 3
        assert rep.category_strengths["photography"] == 10 / 12
        assert len(rep.chain_experience) == 3
        assert rep.normalized_score > 60  # Should be decent
        assert rep.confidence > 0.4

    def test_transactional_scoring(self):
        """EM API ratings normalize properly."""
        api_data = {
            "agent_id": 101,
            "avg_rating_received": 82.0,
            "total_ratings_received": 15,
            "avg_rating_given": 75.0,
            "total_ratings_given": 12,
        }
        rep = extract_transactional_reputation("kk-agent-beta", api_data)
        assert rep.normalized_score == 82.0
        assert rep.confidence > 0.5
        assert rep.agent_id == 101

    def test_unified_reputation_all_layers(self):
        """Unified score combines all three layers with confidence weighting."""
        on_chain = compute_on_chain_score([
            SealScore("SKILLFUL", "A2H", 88, "0xeval", NOW.isoformat(), "", 1),
            SealScore("RELIABLE", "A2H", 92, "0xeval", NOW.isoformat(), "", 2),
        ], now=NOW)

        off_chain = extract_off_chain_reputation("alpha", {
            "tasks_completed": 20, "tasks_attempted": 25,
            "reliability_score": 0.80, "avg_rating_received": 75.0,
            "category_completions": {"photo": 10, "verify": 8},
            "category_attempts": {"photo": 12, "verify": 9},
        })

        transactional = extract_transactional_reputation("alpha", {
            "avg_rating_received": 80.0, "total_ratings_received": 10,
        })

        unified = compute_unified_reputation(
            "alpha", on_chain, off_chain, transactional,
        )
        assert unified.composite_score > 70  # All layers are positive
        assert unified.tier in (ReputationTier.ORO, ReputationTier.DIAMANTE)
        assert len(unified.sources_available) == 3
        assert unified.effective_confidence > 0.3

    def test_unified_reputation_partial_data(self):
        """Scoring works gracefully with only some data sources."""
        # Only off-chain available
        off_chain = extract_off_chain_reputation("beta", {
            "tasks_completed": 5, "tasks_attempted": 6,
            "reliability_score": 0.9, "avg_rating_received": 85.0,
        })

        unified = compute_unified_reputation("beta", off_chain=off_chain)
        assert unified.composite_score > 60
        assert len(unified.sources_available) == 1
        assert "off_chain" in unified.sources_available

    def test_swarm_reputation_batch(self):
        """Compute reputation for entire swarm at once."""
        agents_data = {
            "alpha": {
                "on_chain": [
                    {"seal_type": "SKILLFUL", "quadrant": "A2H", "score": 85,
                     "evaluator": "0x1", "timestamp": NOW.isoformat()},
                ],
                "off_chain": {
                    "tasks_completed": 20, "tasks_attempted": 25,
                    "reliability_score": 0.8, "avg_rating_received": 78.0,
                },
                "transactional": {
                    "avg_rating_received": 80.0, "total_ratings_received": 8,
                },
            },
            "beta": {
                "off_chain": {
                    "tasks_completed": 3, "tasks_attempted": 5,
                    "reliability_score": 0.6, "avg_rating_received": 60.0,
                },
            },
            "gamma": {},  # No data
        }

        reps = compute_swarm_reputation(agents_data)
        assert len(reps) == 3
        assert reps["alpha"].composite_score > reps["beta"].composite_score
        assert reps["gamma"].composite_score == 50.0  # Neutral

    def test_reputation_boost_for_matching(self):
        """Reputation data boosts coordinator match scores."""
        high_rep = UnifiedReputation(
            agent_name="alpha",
            composite_score=90.0,
            effective_confidence=0.8,
        )
        low_rep = UnifiedReputation(
            agent_name="beta",
            composite_score=30.0,
            effective_confidence=0.8,
        )

        base_score = 0.7
        boosted_high = reputation_boost_for_matching(high_rep, base_score, 0.15)
        boosted_low = reputation_boost_for_matching(low_rep, base_score, 0.15)

        assert boosted_high > boosted_low
        assert boosted_high > base_score * 0.85  # Higher than 85% of base
        assert boosted_low < base_score  # Lower than base


# ---------------------------------------------------------------------------
# Phase 3: Coordinator Matching → Dispatch
# ---------------------------------------------------------------------------


class TestPhase3MatchingToDispatch:
    """Test that coordinator matching results flow into the dispatch system."""

    def test_ranked_agents_to_dispatch(self):
        """Reputation rankings map into dispatch records."""
        # Build reputation data
        reps = {
            "alpha": UnifiedReputation(agent_name="alpha", composite_score=85.0,
                                        effective_confidence=0.8),
            "beta": UnifiedReputation(agent_name="beta", composite_score=65.0,
                                       effective_confidence=0.6),
            "gamma": UnifiedReputation(agent_name="gamma", composite_score=45.0,
                                        effective_confidence=0.3),
        }

        # Rank
        rankings = rank_by_reputation(reps)
        assert rankings[0][0] == "alpha"
        assert rankings[1][0] == "beta"
        assert rankings[2][0] == "gamma"

        # Create dispatch record for top-ranked agent
        task = SAMPLE_TASKS[0]
        now_iso = NOW.isoformat()
        record = DispatchRecord(
            task_id=task["id"],
            agent_name=rankings[0][0],  # alpha
            dispatched_at=now_iso,
            bounty_usd=task["bounty_usd"],
            title=task["title"],
            match_score=rankings[0][1] / 100.0,
        )
        assert record.agent_name == "alpha"
        assert record.status == "dispatched"

    def test_dispatch_queue_operations(self, tmp_dir):
        """Dispatch queue handles full lifecycle: add → complete."""
        queue = DispatchQueue()
        now_iso = NOW.isoformat()

        # Add a dispatch record to active
        record = DispatchRecord(
            task_id="task-001",
            agent_name="kk-agent-alpha",
            dispatched_at=now_iso,
            bounty_usd=2.50,
            title="Test Task",
        )
        queue.active.append(record)
        queue.total_dispatched += 1
        assert len(queue.active) == 1

        # Mark as completed via the module function
        completed = mark_completed(queue, "task-001", "kk-agent-alpha")
        assert completed is not None
        assert completed.status == "completed"
        assert len(queue.completed) == 1
        assert len(queue.active) == 0
        assert queue.total_completed == 1

    def test_dispatch_queue_acknowledged(self, tmp_dir):
        """Task acknowledgment updates status."""
        queue = DispatchQueue()
        now_iso = NOW.isoformat()
        record = DispatchRecord(
            task_id="task-002",
            agent_name="kk-agent-beta",
            dispatched_at=now_iso,
            title="Verify hours",
        )
        queue.active.append(record)

        ack = mark_acknowledged(queue, "task-002", "kk-agent-beta")
        assert ack is not None
        assert ack.status == "acknowledged"
        assert ack.acknowledged_at is not None

    def test_dispatch_queue_persistence(self, tmp_dir):
        """Queue state persists via save/load."""
        queue = DispatchQueue()
        now_iso = NOW.isoformat()
        record = DispatchRecord(
            task_id="task-003",
            agent_name="kk-agent-gamma",
            dispatched_at=now_iso,
            bounty_usd=3.0,
            title="Transcribe recipe",
            match_score=0.75,
        )
        queue.active.append(record)
        queue.total_dispatched = 1

        # Save
        queue_path = tmp_dir / "dispatch.json"
        save_dispatch_queue(queue, queue_path)

        # Load in new queue
        loaded = load_dispatch_queue(queue_path)
        assert len(loaded.active) == 1
        assert loaded.active[0].task_id == "task-003"
        assert loaded.active[0].agent_name == "kk-agent-gamma"
        assert loaded.total_dispatched == 1

    def test_irc_notification_formatting(self):
        """IRC notification messages format correctly."""
        record = DispatchRecord(
            task_id="task-001",
            agent_name="kk-agent-alpha",
            dispatched_at=NOW.isoformat(),
            bounty_usd=2.50,
            title="Photo of sunset",
            match_score=0.85,
        )
        msg = format_irc_assignment(record)
        assert "kk-agent-alpha" in msg
        assert "$2.50" in msg

        # Stall warning
        stall_msg = format_irc_stall_warning(record, 45)
        assert "kk-agent-alpha" in stall_msg
        assert "45 min" in stall_msg

        # Reassignment
        reassign_msg = format_irc_reassignment("alpha", "beta", "Photo of sunset")
        assert "alpha" in reassign_msg
        assert "beta" in reassign_msg

    def test_leaderboard_generation(self):
        """Leaderboard generates from reputation data."""
        reps = {
            "alpha": UnifiedReputation(
                agent_name="alpha", composite_score=85.0,
                effective_confidence=0.8, sources_available=["on_chain", "off_chain"],
                on_chain_score=90.0, off_chain_score=80.0, transactional_score=50.0,
            ),
            "beta": UnifiedReputation(
                agent_name="beta", composite_score=65.0,
                effective_confidence=0.6, sources_available=["off_chain"],
                on_chain_score=50.0, off_chain_score=65.0, transactional_score=50.0,
            ),
        }
        reps["alpha"].tier = classify_tier(85.0)
        reps["beta"].tier = classify_tier(65.0)

        lb = generate_leaderboard(reps)
        assert len(lb) == 2
        assert lb[0]["rank"] == 1
        assert lb[0]["agent"] == "alpha"
        assert lb[0]["tier"] == "Diamante"
        assert lb[1]["rank"] == 2
        assert lb[1]["agent"] == "beta"

        # Text formatting
        text = format_leaderboard_text(lb)
        assert "Leaderboard" in text
        assert "alpha" in text
        assert "Diamante" in text


# ---------------------------------------------------------------------------
# Phase 4: Task Lifecycle Through Agent State Machine
# ---------------------------------------------------------------------------


class TestPhase4TaskLifecycle:
    """Test complete task lifecycle through the agent state machine."""

    def test_happy_path_task_completion(self, config):
        """Agent: IDLE → WORKING → IDLE (task completed successfully)."""
        agent = AgentLifecycle(
            agent_name="kk-agent-alpha",
            agent_type=AgentType.USER,
            state=AgentState.IDLE,
        )
        update_balance(agent, usdc=5.0, eth=0.01)
        record_heartbeat(agent, NOW)

        # Assign task
        ev1 = transition(agent, TransitionReason.TASK_ASSIGNED, config, NOW,
                          {"task_id": "task-001"})
        assert ev1 is not None
        assert agent.state == AgentState.WORKING
        assert agent.current_task_id == "task-001"

        # Complete task
        ev2 = transition(agent, TransitionReason.TASK_COMPLETED, config,
                          NOW + timedelta(minutes=15))
        assert ev2 is not None
        assert agent.state == AgentState.IDLE
        assert agent.current_task_id == ""
        assert agent.total_successes == 1
        assert agent.consecutive_failures == 0

    def test_task_failure_and_circuit_breaker(self, config):
        """3 consecutive failures trip the circuit breaker."""
        agent = AgentLifecycle(
            agent_name="kk-agent-beta",
            agent_type=AgentType.USER,
            state=AgentState.IDLE,
        )

        # Fail 3 tasks consecutively
        for i in range(3):
            transition(agent, TransitionReason.TASK_ASSIGNED, config, NOW,
                        {"task_id": f"task-fail-{i}"})
            transition(agent, TransitionReason.TASK_FAILED, config, NOW)

        assert agent.consecutive_failures == 3
        assert agent.total_failures == 3
        assert should_trip_circuit_breaker(agent, config)

        # Trip the breaker
        ev = transition(agent, TransitionReason.CIRCUIT_BREAKER, config, NOW)
        assert ev is not None
        assert agent.state == AgentState.COOLDOWN
        assert agent.circuit_breaker_trips == 1
        assert agent.cooldown_until != ""

    def test_cooldown_recovery_cycle(self, config):
        """Agent recovers from cooldown after timeout."""
        agent = AgentLifecycle(
            agent_name="kk-agent-gamma",
            agent_type=AgentType.USER,
            state=AgentState.COOLDOWN,
            circuit_breaker_trips=1,
        )
        # Set cooldown that's already expired
        past = (NOW - timedelta(seconds=30)).isoformat()
        agent.cooldown_until = past

        assert is_cooldown_expired(agent, NOW)

        ev = transition(agent, TransitionReason.COOLDOWN_EXPIRED, config, NOW)
        assert ev is not None
        assert agent.state == AgentState.IDLE
        assert agent.cooldown_until == ""

    def test_exponential_backoff_cooldown(self, config):
        """Each circuit breaker trip increases cooldown duration."""
        cd1 = compute_cooldown(1, base=10.0, max_cooldown=60.0,
                                multiplier=2.0, jitter=0.0)
        cd2 = compute_cooldown(2, base=10.0, max_cooldown=60.0,
                                multiplier=2.0, jitter=0.0)
        cd3 = compute_cooldown(3, base=10.0, max_cooldown=60.0,
                                multiplier=2.0, jitter=0.0)

        assert cd1 == 10.0  # 10 * 2^0
        assert cd2 == 20.0  # 10 * 2^1
        assert cd3 == 40.0  # 10 * 2^2

        # Hits max
        cd5 = compute_cooldown(5, base=10.0, max_cooldown=60.0,
                                multiplier=2.0, jitter=0.0)
        assert cd5 == 60.0  # Capped

    def test_graceful_shutdown_draining(self, config):
        """Working agent drains before stopping."""
        agent = AgentLifecycle(
            agent_name="kk-agent-delta",
            agent_type=AgentType.USER,
            state=AgentState.WORKING,
            current_task_id="task-important",
        )

        # Request shutdown while working
        ev1 = transition(agent, TransitionReason.MANUAL_STOP, config, NOW)
        assert ev1 is not None
        assert agent.state == AgentState.DRAINING

        # Task completes during drain
        ev2 = transition(agent, TransitionReason.TASK_COMPLETED, config, NOW)
        assert ev2 is not None
        assert agent.state == AgentState.STOPPING

        # Final stop
        ev3 = transition(agent, TransitionReason.MANUAL_STOP, config, NOW)
        assert ev3 is not None
        assert agent.state == AgentState.OFFLINE

    def test_task_timeout_detection(self, config):
        """Tasks that exceed timeout are detected."""
        agent = AgentLifecycle(
            agent_name="kk-agent-epsilon",
            agent_type=AgentType.USER,
            state=AgentState.WORKING,
            current_task_id="task-slow",
            current_task_started=(NOW - timedelta(seconds=700)).isoformat(),
        )

        # Should timeout (config is 600s)
        assert check_task_timeout(agent, config, NOW)

        # Not yet timed out
        agent.current_task_started = (NOW - timedelta(seconds=500)).isoformat()
        assert not check_task_timeout(agent, config, NOW)


# ---------------------------------------------------------------------------
# Phase 5: Health Assessment & Recommendations
# ---------------------------------------------------------------------------


class TestPhase5Health:
    """Test swarm health assessment from aggregated agent states."""

    def test_healthy_swarm(self, agents, config):
        """All agents online → healthy swarm metrics."""
        # Start all agents and fund them
        for agent in agents:
            transition(agent, TransitionReason.STARTUP, config, NOW)
            transition(agent, TransitionReason.STARTUP, config, NOW)
            update_balance(agent, usdc=5.0, eth=0.01)
            record_heartbeat(agent, NOW)

        health = assess_swarm_health(agents, config, NOW)
        assert health.total_agents == 10
        assert health.online_agents == 10
        assert health.availability_ratio == 1.0
        assert health.agents_with_low_balance == 0

    def test_degraded_swarm(self, agents, config):
        """Mixed agent states → degraded metrics + recommendations."""
        for agent in agents:
            transition(agent, TransitionReason.STARTUP, config, NOW)
            transition(agent, TransitionReason.STARTUP, config, NOW)
            update_balance(agent, usdc=5.0, eth=0.01)
            record_heartbeat(agent, NOW)

        # Put some agents in bad states
        # Agent 4: working on a task
        transition(agents[4], TransitionReason.TASK_ASSIGNED, config, NOW,
                    {"task_id": "task-001"})

        # Agent 5: failed 3 times → circuit breaker
        for _ in range(3):
            transition(agents[5], TransitionReason.TASK_ASSIGNED, config, NOW,
                        {"task_id": "task-x"})
            transition(agents[5], TransitionReason.TASK_FAILED, config, NOW)
        transition(agents[5], TransitionReason.CIRCUIT_BREAKER, config, NOW)

        # Agent 6: stale heartbeat
        agents[6].last_heartbeat = (NOW - timedelta(seconds=200)).isoformat()

        # Agent 7: dead heartbeat
        agents[7].last_heartbeat = (NOW - timedelta(seconds=400)).isoformat()

        # Agent 8: low balance
        update_balance(agents[8], usdc=0.0, eth=0.0)

        health = assess_swarm_health(agents, config, NOW)
        assert health.online_agents == 9  # 10 - 1 cooldown; stale/dead heartbeat agents still in IDLE
        assert health.working_agents == 1
        assert health.cooldown_agents == 1
        assert health.agents_with_stale_heartbeat >= 2
        assert health.agents_with_low_balance >= 1

        # Should generate recommendations
        actions = recommend_actions(agents, config, NOW)
        action_types = {a["action"] for a in actions}
        assert "trip_breaker" in action_types or "balance_alert" in action_types

    def test_recommendation_priorities(self, config):
        """Recommendations are sorted by priority."""
        agents_list = [
            AgentLifecycle(agent_name="dead", state=AgentState.IDLE,
                           last_heartbeat=(NOW - timedelta(seconds=400)).isoformat()),
            AgentLifecycle(agent_name="stale", state=AgentState.IDLE,
                           last_heartbeat=(NOW - timedelta(seconds=200)).isoformat()),
            AgentLifecycle(agent_name="error", state=AgentState.ERROR),
            AgentLifecycle(agent_name="low-bal", state=AgentState.IDLE,
                           usdc_balance=0.0, eth_balance=0.0,
                           last_heartbeat=NOW.isoformat()),
        ]

        actions = recommend_actions(agents_list, config, NOW)
        assert len(actions) > 0
        # Critical actions should come first
        priorities = [a["priority"] for a in actions]
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        numeric = [priority_order.get(p, 4) for p in priorities]
        assert numeric == sorted(numeric)  # Monotonically non-decreasing


# ---------------------------------------------------------------------------
# Phase 6: Persistence — Round-Trip Save/Load
# ---------------------------------------------------------------------------


class TestPhase6Persistence:
    """Test that state survives save → load cycles."""

    def test_lifecycle_state_persistence(self, agents, config, tmp_dir):
        """Agent lifecycle state persists across save/load."""
        # Set up some state
        for agent in agents:
            transition(agent, TransitionReason.STARTUP, config, NOW)
            transition(agent, TransitionReason.STARTUP, config, NOW)
            update_balance(agent, usdc=5.0, eth=0.01)
            record_heartbeat(agent, NOW)

        # Give alpha a task and complete it
        alpha = agents[4]
        transition(alpha, TransitionReason.TASK_ASSIGNED, config, NOW,
                    {"task_id": "task-001"})
        transition(alpha, TransitionReason.TASK_COMPLETED, config, NOW)

        # Give beta 3 failures
        beta = agents[5]
        for _ in range(3):
            transition(beta, TransitionReason.TASK_ASSIGNED, config, NOW,
                        {"task_id": "task-x"})
            transition(beta, TransitionReason.TASK_FAILED, config, NOW)

        # Save
        state_path = tmp_dir / "lifecycle.json"
        save_lifecycle_state(agents, state_path)

        # Load
        loaded = load_lifecycle_state(state_path)
        assert len(loaded) == len(agents)

        # Verify alpha's state
        loaded_alpha = [a for a in loaded if a.agent_name == "kk-agent-alpha"][0]
        assert loaded_alpha.total_successes == 1
        assert loaded_alpha.state == AgentState.IDLE

        # Verify beta's state
        loaded_beta = [a for a in loaded if a.agent_name == "kk-agent-beta"][0]
        assert loaded_beta.consecutive_failures == 3
        assert loaded_beta.total_failures == 3

    def test_reputation_snapshot_persistence(self, tmp_dir):
        """Reputation snapshots persist and load correctly."""
        reps = {
            "alpha": UnifiedReputation(
                agent_name="alpha", composite_score=85.0,
                effective_confidence=0.8, sources_available=["on_chain", "off_chain"],
                on_chain_score=90.0, off_chain_score=80.0,
            ),
            "beta": UnifiedReputation(
                agent_name="beta", composite_score=60.0,
                effective_confidence=0.5, sources_available=["off_chain"],
                off_chain_score=60.0,
            ),
        }
        reps["alpha"].tier = classify_tier(85.0)
        reps["beta"].tier = classify_tier(60.0)

        # Save
        rep_dir = tmp_dir / "reputation"
        path = save_reputation_snapshot(reps, rep_dir)
        assert path.exists()

        # Load
        loaded = load_reputation_snapshot(path)
        assert "alpha" in loaded
        assert loaded["alpha"]["composite_score"] == 85.0
        assert loaded["alpha"]["tier"] == "Diamante"

        # Load latest
        latest = load_latest_snapshot(rep_dir)
        assert "alpha" in latest

    def test_dispatch_queue_persistence(self, tmp_dir):
        """Dispatch queue survives save/load."""
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="task-001", agent_name="alpha",
            dispatched_at=NOW.isoformat(), bounty_usd=2.50,
            title="Test",
        ))
        queue.total_dispatched = 1

        queue_path = tmp_dir / "dispatch_queue.json"
        save_dispatch_queue(queue, queue_path)

        # Load in new queue instance
        queue2 = load_dispatch_queue(queue_path)
        assert len(queue2.active) == 1
        assert queue2.active[0].task_id == "task-001"
        assert queue2.active[0].status == "dispatched"


# ---------------------------------------------------------------------------
# Phase 7: Full Pipeline — End-to-End Simulation
# ---------------------------------------------------------------------------


class TestPhase7FullPipeline:
    """Simulate the complete swarm pipeline from startup to completion."""

    def test_full_swarm_cycle(self, config, tmp_dir):
        """
        Complete swarm cycle:
        1. Create roster → startup all agents
        2. Compute reputation for all agents
        3. Rank agents for task matching
        4. Dispatch top-ranked agent
        5. Agent completes task → update lifecycle
        6. Assess swarm health → verify improvement
        """
        # 1. Create and start agents
        roster = create_agent_roster(AGENT_REGISTRY)
        for agent in roster:
            transition(agent, TransitionReason.STARTUP, config, NOW)
            transition(agent, TransitionReason.STARTUP, config, NOW)
            update_balance(agent, usdc=5.0, eth=0.01)
            record_heartbeat(agent, NOW)

        # 2. Build reputation data (simulated)
        agents_rep_data = {}
        for i, agent in enumerate(roster):
            if agent.agent_type == AgentType.USER:
                agents_rep_data[agent.agent_name] = {
                    "off_chain": {
                        "tasks_completed": 10 + i * 3,
                        "tasks_attempted": 12 + i * 3,
                        "reliability_score": 0.7 + i * 0.03,
                        "avg_rating_received": 60.0 + i * 5,
                        "category_completions": {"photography": 5 + i},
                        "category_attempts": {"photography": 6 + i},
                    },
                }

        reps = compute_swarm_reputation(agents_rep_data)
        assert len(reps) > 0

        # 3. Rank agents for a photography task
        rankings = rank_by_reputation(reps)
        assert len(rankings) > 0

        # Top-ranked agent should have the best score
        top_agent_name = rankings[0][0]
        top_score = rankings[0][1]
        bottom_score = rankings[-1][1]
        assert top_score >= bottom_score

        # 4. Dispatch to top-ranked agent
        queue = DispatchQueue()
        task = SAMPLE_TASKS[0]  # Photography task
        record = DispatchRecord(
            task_id=task["id"],
            agent_name=top_agent_name,
            dispatched_at=NOW.isoformat(),
            bounty_usd=task["bounty_usd"],
            title=task["title"],
            category=task.get("category", ""),
        )
        queue.active.append(record)
        queue.total_dispatched += 1

        # 5. Update lifecycle — assign task to the agent
        top_agent = [a for a in roster if a.agent_name == top_agent_name][0]
        ev = transition(top_agent, TransitionReason.TASK_ASSIGNED, config, NOW,
                         {"task_id": task["id"]})
        assert ev is not None
        assert top_agent.state == AgentState.WORKING

        # Agent completes the task
        ev2 = transition(top_agent, TransitionReason.TASK_COMPLETED, config,
                           NOW + timedelta(minutes=20))
        assert ev2 is not None
        assert top_agent.state == AgentState.IDLE
        assert top_agent.total_successes == 1

        # Mark dispatch as completed
        completed = mark_completed(queue, task["id"], top_agent_name)
        assert completed is not None
        assert len(queue.completed) == 1

        # 6. Health assessment
        health = assess_swarm_health(roster, config,
                                      NOW + timedelta(minutes=25))
        assert health.total_successes == 1
        assert health.availability_ratio > 0.9
        assert health.online_agents >= 9  # At least 9 still idle/working

        # Save all state
        save_lifecycle_state(roster, tmp_dir / "lifecycle.json")
        save_reputation_snapshot(reps, tmp_dir / "reputation")
        save_dispatch_queue(queue, tmp_dir / "dispatch.json")

        # Verify persistence
        loaded = load_lifecycle_state(tmp_dir / "lifecycle.json")
        loaded_top = [a for a in loaded if a.agent_name == top_agent_name][0]
        assert loaded_top.total_successes == 1

    def test_failure_cascade_and_recovery(self, config, tmp_dir):
        """
        Simulate a failure cascade:
        1. Agent fails repeatedly → circuit breaker trips
        2. Task gets reassigned to next-ranked agent
        3. Second agent succeeds
        4. First agent recovers from cooldown
        5. Swarm health returns to normal
        """
        # Setup: 3 user agents
        mini_registry = [
            {"name": "fast-but-flaky", "type": "user"},
            {"name": "slow-but-reliable", "type": "user"},
            {"name": "backup-agent", "type": "user"},
        ]
        agents_list = create_agent_roster(mini_registry)
        for a in agents_list:
            transition(a, TransitionReason.STARTUP, config, NOW)
            transition(a, TransitionReason.STARTUP, config, NOW)
            update_balance(a, usdc=5.0, eth=0.01)
            record_heartbeat(a, NOW)

        flaky = agents_list[0]
        reliable = agents_list[1]

        # Dispatch queue
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="task-critical",
            agent_name="fast-but-flaky",
            dispatched_at=NOW.isoformat(),
            title="Critical verification",
            bounty_usd=5.0,
        ))
        queue.total_dispatched += 1

        # Flaky agent gets the task
        transition(flaky, TransitionReason.TASK_ASSIGNED, config, NOW,
                    {"task_id": "task-critical"})

        # Flaky fails
        transition(flaky, TransitionReason.TASK_FAILED, config,
                    NOW + timedelta(minutes=5))

        # Flaky retries and fails again (simulate 3 total failures)
        for i in range(2):
            transition(flaky, TransitionReason.TASK_ASSIGNED, config, NOW,
                        {"task_id": f"task-retry-{i}"})
            transition(flaky, TransitionReason.TASK_FAILED, config, NOW)

        # Circuit breaker trips
        assert should_trip_circuit_breaker(flaky, config)
        transition(flaky, TransitionReason.CIRCUIT_BREAKER, config,
                    NOW + timedelta(minutes=10))
        assert flaky.state == AgentState.COOLDOWN

        # Reassign to reliable agent — update old record manually
        for r in queue.active[:]:
            if r.task_id == "task-critical":
                r.status = "reassigned"
                r.reassigned_to = "slow-but-reliable"
                queue.active.remove(r)
                queue.failed.append(r)
                break
        # Create new dispatch record for reliable agent
        queue.active.append(DispatchRecord(
            task_id="task-critical",
            agent_name="slow-but-reliable",
            dispatched_at=(NOW + timedelta(minutes=11)).isoformat(),
            title="Critical verification",
            bounty_usd=5.0,
        ))
        queue.total_reassigned += 1

        transition(reliable, TransitionReason.TASK_ASSIGNED, config,
                    NOW + timedelta(minutes=11),
                    {"task_id": "task-critical"})

        # Reliable agent succeeds
        transition(reliable, TransitionReason.TASK_COMPLETED, config,
                    NOW + timedelta(minutes=25))
        mark_completed(queue, "task-critical", "slow-but-reliable")

        assert reliable.total_successes == 1
        assert flaky.total_failures == 3
        assert flaky.state == AgentState.COOLDOWN

        # Time passes — flaky's cooldown expires
        flaky.cooldown_until = (NOW + timedelta(seconds=10)).isoformat()
        assert is_cooldown_expired(flaky, NOW + timedelta(minutes=1))

        transition(flaky, TransitionReason.COOLDOWN_EXPIRED, config,
                    NOW + timedelta(minutes=30))
        assert flaky.state == AgentState.IDLE

        # Health check — all agents recovered
        health = assess_swarm_health(agents_list, config,
                                      NOW + timedelta(minutes=35))
        assert health.online_agents == 3
        assert health.cooldown_agents == 0
        assert health.total_successes == 1
        assert health.total_failures == 3

    def test_multi_task_parallel_dispatch(self, config, tmp_dir):
        """
        Dispatch multiple tasks simultaneously:
        1. 4 tasks available, 6 agents available
        2. Each task assigned to a different agent
        3. All complete successfully
        4. Reputation scores improve
        """
        agents_list = create_agent_roster([
            {"name": f"worker-{i}", "type": "user"} for i in range(6)
        ])
        for a in agents_list:
            transition(a, TransitionReason.STARTUP, config, NOW)
            transition(a, TransitionReason.STARTUP, config, NOW)
            update_balance(a, usdc=5.0, eth=0.01)
            record_heartbeat(a, NOW)

        queue = DispatchQueue()

        # Dispatch 4 tasks to first 4 agents
        assigned = set()
        for i, task in enumerate(SAMPLE_TASKS):
            agent = agents_list[i]
            queue.active.append(DispatchRecord(
                task_id=task["id"],
                agent_name=agent.agent_name,
                dispatched_at=NOW.isoformat(),
                bounty_usd=task["bounty_usd"],
                title=task["title"],
                category=task.get("category", ""),
            ))
            queue.total_dispatched += 1
            transition(agent, TransitionReason.TASK_ASSIGNED, config, NOW,
                        {"task_id": task["id"]})
            assigned.add(agent.agent_name)

        # 4 agents working, 2 idle
        health_during = assess_swarm_health(agents_list, config, NOW)
        assert health_during.working_agents == 4
        assert health_during.idle_agents == 2

        # All complete
        for i, task in enumerate(SAMPLE_TASKS):
            agent = agents_list[i]
            transition(agent, TransitionReason.TASK_COMPLETED, config,
                        NOW + timedelta(minutes=15 + i * 5))
            mark_completed(queue, task["id"], agent.agent_name)

        # All back to idle
        health_after = assess_swarm_health(agents_list, config,
                                            NOW + timedelta(minutes=40))
        assert health_after.working_agents == 0
        assert health_after.idle_agents == 6
        assert health_after.total_successes == 4

        # Queue fully completed
        assert len(queue.completed) == 4
        assert len(queue.active) == 0


# ---------------------------------------------------------------------------
# Phase 8: Edge Cases & Error Recovery
# ---------------------------------------------------------------------------


class TestPhase8EdgeCases:
    """Test edge cases and error recovery paths."""

    def test_invalid_state_transitions_rejected(self, config):
        """Invalid transitions return None without changing state."""
        agent = AgentLifecycle(
            agent_name="agent-x", state=AgentState.OFFLINE,
        )
        # Can't assign task to offline agent
        ev = transition(agent, TransitionReason.TASK_ASSIGNED, config, NOW)
        assert ev is None
        assert agent.state == AgentState.OFFLINE

        # Can't complete task if not working
        agent.state = AgentState.IDLE
        ev = transition(agent, TransitionReason.TASK_COMPLETED, config, NOW)
        assert ev is None
        assert agent.state == AgentState.IDLE

    def test_heartbeat_states(self, config):
        """Heartbeat monitoring detects alive/stale/dead/unknown."""
        agent = AgentLifecycle(agent_name="hb-test")

        # No heartbeat
        assert check_heartbeat(agent, config, NOW) == "unknown"

        # Fresh heartbeat
        agent.last_heartbeat = NOW.isoformat()
        assert check_heartbeat(agent, config, NOW) == "alive"

        # Stale (>120s)
        agent.last_heartbeat = (NOW - timedelta(seconds=150)).isoformat()
        assert check_heartbeat(agent, config, NOW) == "stale"

        # Dead (>300s)
        agent.last_heartbeat = (NOW - timedelta(seconds=400)).isoformat()
        assert check_heartbeat(agent, config, NOW) == "dead"

    def test_balance_monitoring(self, config):
        """Balance checks detect low funds correctly."""
        agent = AgentLifecycle(agent_name="bal-test")

        # Zero balance
        bal = check_balance(agent, config)
        assert not bal["overall_ok"]

        # Funded
        update_balance(agent, usdc=1.0, eth=0.001)
        bal = check_balance(agent, config)
        assert bal["overall_ok"]

        # USDC ok but ETH low
        update_balance(agent, usdc=1.0, eth=0.00001)
        bal = check_balance(agent, config)
        assert bal["usdc_ok"]
        assert not bal["eth_ok"]
        assert not bal["overall_ok"]

    def test_reputation_with_no_data(self):
        """Unified reputation handles empty data gracefully."""
        rep = compute_unified_reputation("empty-agent")
        assert rep.composite_score == 50.0
        assert rep.tier == ReputationTier.PLATA
        assert rep.effective_confidence == 0.0
        assert len(rep.sources_available) == 0

    def test_empty_dispatch_queue_operations(self, tmp_dir):
        """Queue operations on empty/missing records are safe."""
        queue = DispatchQueue()
        # Operations on non-existent records return None
        result = mark_completed(queue, "nonexistent", "no-agent")
        assert result is None
        result = mark_acknowledged(queue, "nonexistent", "no-agent")
        assert result is None
        assert len(queue.active) == 0

    def test_load_nonexistent_dispatch_queue(self, tmp_dir):
        """Loading from nonexistent path returns empty queue."""
        queue = load_dispatch_queue(tmp_dir / "nope.json")
        assert len(queue.active) == 0
        assert queue.total_dispatched == 0

    def test_large_swarm_health_assessment(self, config):
        """Health assessment scales to 100+ agents."""
        agents_list = create_agent_roster([
            {"name": f"agent-{i:03d}", "type": "user"} for i in range(100)
        ])
        for a in agents_list:
            transition(a, TransitionReason.STARTUP, config, NOW)
            transition(a, TransitionReason.STARTUP, config, NOW)
            update_balance(a, usdc=1.0, eth=0.001)
            record_heartbeat(a, NOW)

        health = assess_swarm_health(agents_list, config, NOW)
        assert health.total_agents == 100
        assert health.online_agents == 100
        assert health.availability_ratio == 1.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
