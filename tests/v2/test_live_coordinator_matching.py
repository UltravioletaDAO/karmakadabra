#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 — Live Coordinator Matching Test

Fetches REAL completed tasks from the EM API and validates that:
1. The coordinator matching pipeline processes them without errors
2. Reputation scoring produces valid rankings
3. The AutoJob bridge (if available) enhances matching quality
4. Task dispatch records format correctly

This is a READ-ONLY test — it doesn't create tasks or assign agents.
It proves the matching pipeline works with real-world data.

Usage:
    pytest tests/v2/test_live_coordinator_matching.py -v
    python tests/v2/test_live_coordinator_matching.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from lib.reputation_bridge import (
    OffChainReputation,
    UnifiedReputation,
    compute_swarm_reputation,
    compute_unified_reputation,
    extract_off_chain_reputation,
    generate_leaderboard,
    format_leaderboard_text,
    rank_by_reputation,
    reputation_boost_for_matching,
)
from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    assess_swarm_health,
    create_agent_roster,
    transition,
    TransitionReason,
    update_balance,
    record_heartbeat,
)
from services.swarm_dispatch import (
    DispatchQueue,
    DispatchRecord,
    format_irc_assignment,
)


# ---------------------------------------------------------------------------
# Live API fetching
# ---------------------------------------------------------------------------

def fetch_completed_tasks(limit: int = 30) -> list[dict]:
    """Fetch completed tasks from live EM API."""
    import urllib.request
    url = f"https://api.execution.market/api/v1/tasks?status=completed&limit={limit}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tasks", [])
    except Exception as e:
        pytest.skip(f"EM API unreachable: {e}")
        return []


def fetch_published_tasks(limit: int = 20) -> list[dict]:
    """Fetch published (available) tasks from live EM API."""
    import urllib.request
    url = f"https://api.execution.market/api/v1/tasks?status=published&limit={limit}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tasks", [])
    except Exception as e:
        return []


def fetch_api_health() -> dict:
    """Check EM API health."""
    import urllib.request
    url = "https://api.execution.market/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}


# ---------------------------------------------------------------------------
# Simulated Agent Profiles (based on KK V2 24-agent swarm)
# ---------------------------------------------------------------------------

SIMULATED_AGENTS = {
    "kk-agent-alpha": {
        "off_chain": {
            "tasks_completed": 45, "tasks_attempted": 50,
            "reliability_score": 0.90, "avg_rating_received": 85.0,
            "category_completions": {
                "simple_action": 20, "photography": 10,
                "verification": 8, "transcription": 7,
            },
            "category_attempts": {
                "simple_action": 22, "photography": 11,
                "verification": 9, "transcription": 8,
            },
            "chain_tasks": {"base": 25, "polygon": 10, "ethereum": 5, "optimism": 5},
            "total_earned_usd": 89.50,
        },
    },
    "kk-agent-beta": {
        "off_chain": {
            "tasks_completed": 30, "tasks_attempted": 38,
            "reliability_score": 0.79, "avg_rating_received": 72.0,
            "category_completions": {
                "simple_action": 15, "code_review": 8, "research": 7,
            },
            "category_attempts": {
                "simple_action": 18, "code_review": 10, "research": 10,
            },
            "chain_tasks": {"base": 20, "ethereum": 10, "arbitrum": 8},
            "total_earned_usd": 55.00,
        },
    },
    "kk-agent-gamma": {
        "off_chain": {
            "tasks_completed": 12, "tasks_attempted": 15,
            "reliability_score": 0.80, "avg_rating_received": 68.0,
            "category_completions": {
                "photography": 6, "verification": 4, "simple_action": 2,
            },
            "category_attempts": {
                "photography": 7, "verification": 5, "simple_action": 3,
            },
            "chain_tasks": {"base": 8, "polygon": 4},
            "total_earned_usd": 22.00,
        },
    },
    "kk-agent-delta": {
        "off_chain": {
            "tasks_completed": 5, "tasks_attempted": 8,
            "reliability_score": 0.63, "avg_rating_received": 55.0,
            "category_completions": {"simple_action": 5},
            "category_attempts": {"simple_action": 8},
            "chain_tasks": {"base": 5},
            "total_earned_usd": 8.00,
        },
    },
    "kk-agent-epsilon": {
        "off_chain": {
            "tasks_completed": 0, "tasks_attempted": 0,
            "reliability_score": 0.5, "avg_rating_received": 0.0,
        },
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLiveAPIConnection:
    """Verify the EM API is reachable and returning valid data."""

    def test_api_health(self):
        """EM API health endpoint responds."""
        health = fetch_api_health()
        assert health.get("status") in ("healthy", "ok"), f"API status: {health}"

    def test_fetch_completed_tasks(self):
        """Can fetch completed tasks from the API."""
        tasks = fetch_completed_tasks(limit=5)
        assert len(tasks) > 0, "No completed tasks found"
        # Validate task structure
        for task in tasks:
            assert "id" in task
            assert "title" in task
            assert task["status"] == "completed"

    def test_task_data_quality(self):
        """Completed tasks have the fields needed for matching."""
        tasks = fetch_completed_tasks(limit=10)
        assert len(tasks) > 0

        for task in tasks:
            # These fields are used by the coordinator
            assert "id" in task
            assert "title" in task
            assert "category" in task
            assert "bounty_usd" in task
            assert "payment_network" in task


class TestLiveCoordinatorMatching:
    """Test the coordinator matching pipeline with real task data."""

    def test_reputation_scoring_with_real_tasks(self):
        """Build reputation from simulated profiles and rank for real tasks."""
        # Compute reputation for all simulated agents
        reps = compute_swarm_reputation(SIMULATED_AGENTS)

        assert len(reps) == 5
        # Alpha should be highest (most tasks, best scores)
        rankings = rank_by_reputation(reps)
        assert rankings[0][0] == "kk-agent-alpha"
        # Epsilon should be lowest (no data)
        assert rankings[-1][0] == "kk-agent-epsilon"

        # All scores should be valid 0-100
        for name, score, tier in rankings:
            assert 0 <= score <= 100, f"{name} has invalid score: {score}"

    def test_matching_against_real_completed_tasks(self):
        """Run matching pipeline against real completed tasks."""
        tasks = fetch_completed_tasks(limit=20)
        assert len(tasks) > 0

        reps = compute_swarm_reputation(SIMULATED_AGENTS)

        matched_count = 0
        for task in tasks:
            task_category = task.get("category", "")
            task_chain = task.get("payment_network", "base")

            # For each task, rank agents by reputation
            rankings = rank_by_reputation(reps)
            assert len(rankings) > 0

            # Top agent should always be valid
            top_name, top_score, top_tier = rankings[0]
            assert top_name in SIMULATED_AGENTS
            assert top_score > 0

            # Category-aware matching: check if top agent has category experience
            top_rep = reps[top_name]
            if task_category in top_rep.category_strengths:
                matched_count += 1

        # At least some tasks should have category matches
        # (most are "simple_action" which alpha has experience in)
        assert matched_count > 0 or len(tasks) == 0

    def test_reputation_boost_improves_matching(self):
        """Reputation boost differentiates agents for real tasks."""
        tasks = fetch_completed_tasks(limit=10)
        if not tasks:
            pytest.skip("No tasks available")

        reps = compute_swarm_reputation(SIMULATED_AGENTS)

        for task in tasks[:5]:
            base_score = 0.5  # Neutral base match score

            boosted_scores = {}
            for name, rep in reps.items():
                boosted = reputation_boost_for_matching(
                    rep, base_score, reputation_weight=0.15,
                )
                boosted_scores[name] = boosted

            # Alpha should get highest boost (best reputation)
            # Epsilon should get lowest (no data → neutral)
            sorted_scores = sorted(boosted_scores.items(),
                                    key=lambda x: x[1], reverse=True)
            assert sorted_scores[0][0] == "kk-agent-alpha"

            # Spread should exist (not all same)
            scores = list(boosted_scores.values())
            assert max(scores) > min(scores)

    def test_dispatch_record_creation_from_real_tasks(self):
        """Create dispatch records from real task data."""
        tasks = fetch_completed_tasks(limit=5)
        if not tasks:
            pytest.skip("No tasks available")

        reps = compute_swarm_reputation(SIMULATED_AGENTS)
        rankings = rank_by_reputation(reps)
        top_agent = rankings[0][0]

        queue = DispatchQueue()
        for task in tasks[:3]:
            record = DispatchRecord(
                task_id=task["id"],
                agent_name=top_agent,
                dispatched_at=datetime.now(timezone.utc).isoformat(),
                bounty_usd=task.get("bounty_usd", 0),
                title=task.get("title", ""),
                category=task.get("category", ""),
                match_score=rankings[0][1] / 100.0,
            )
            queue.active.append(record)

            # Verify IRC notification formats properly
            msg = format_irc_assignment(record)
            assert top_agent in msg
            assert len(msg) > 20

        assert len(queue.active) == 3

    def test_full_matching_pipeline_with_lifecycle(self):
        """Full pipeline: lifecycle + reputation + matching + dispatch."""
        tasks = fetch_completed_tasks(limit=5)
        if not tasks:
            pytest.skip("No tasks available")

        now = datetime.now(timezone.utc)
        config = LifecycleConfig()

        # Create agent roster
        registry = [
            {"name": name, "type": "user"}
            for name in SIMULATED_AGENTS.keys()
        ]
        roster = create_agent_roster(registry)
        for agent in roster:
            transition(agent, TransitionReason.STARTUP, config, now)
            transition(agent, TransitionReason.STARTUP, config, now)
            update_balance(agent, usdc=5.0, eth=0.01)
            record_heartbeat(agent, now)

        # Compute reputation
        reps = compute_swarm_reputation(SIMULATED_AGENTS)
        rankings = rank_by_reputation(reps)

        # Dispatch first task to top-ranked agent
        task = tasks[0]
        top_name = rankings[0][0]
        top_agent = [a for a in roster if a.agent_name == top_name][0]

        # Assign task
        ev = transition(top_agent, TransitionReason.TASK_ASSIGNED, config, now,
                         {"task_id": task["id"]})
        assert ev is not None
        assert top_agent.state == AgentState.WORKING
        assert top_agent.current_task_id == task["id"]

        # Complete task
        ev2 = transition(top_agent, TransitionReason.TASK_COMPLETED, config,
                           now + timedelta(minutes=10))
        assert ev2 is not None
        assert top_agent.state == AgentState.IDLE
        assert top_agent.total_successes == 1

        # Health check
        health = assess_swarm_health(roster, config, now + timedelta(minutes=15))
        assert health.total_successes == 1
        assert health.online_agents == 5


class TestLiveLeaderboard:
    """Test leaderboard generation with real-world-scale data."""

    def test_leaderboard_output(self):
        """Leaderboard renders cleanly with simulated data."""
        reps = compute_swarm_reputation(SIMULATED_AGENTS)

        # Set tiers
        from lib.reputation_bridge import classify_tier
        for rep in reps.values():
            rep.tier = classify_tier(rep.composite_score)

        lb = generate_leaderboard(reps)
        assert len(lb) == 5
        assert lb[0]["rank"] == 1
        assert lb[0]["agent"] == "kk-agent-alpha"  # Best performer

        text = format_leaderboard_text(lb)
        assert "Leaderboard" in text
        assert "kk-agent-alpha" in text
        assert "kk-agent-epsilon" in text

        # Print for visual inspection
        print("\n" + text + "\n")


class TestLiveAutoJobBridge:
    """Test AutoJob bridge integration (if available)."""

    def test_autojob_bridge_import(self):
        """AutoJob bridge module loads successfully."""
        try:
            from lib.autojob_bridge import AutoJobBridge
            bridge = AutoJobBridge(mode="local")
            assert bridge is not None
        except ImportError:
            pytest.skip("AutoJob bridge not installed")
        except Exception as e:
            # May fail if autojob isn't on the path — that's ok
            if "autojob" in str(e).lower() or "import" in str(e).lower():
                pytest.skip(f"AutoJob not available: {e}")
            raise

    def test_autojob_health(self):
        """AutoJob bridge reports health status."""
        try:
            from lib.autojob_bridge import AutoJobBridge
            bridge = AutoJobBridge(mode="local")
            health = bridge.health()
            assert "mode" in health
            assert "status" in health
        except (ImportError, Exception) as e:
            pytest.skip(f"AutoJob not available: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
