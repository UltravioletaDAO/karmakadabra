"""
Tests for swarm_dashboard.py — Dashboard rendering and data collection.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    assess_swarm_health,
)

from services.swarm_dashboard import (
    render_markdown,
    render_json,
    render_terminal,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_agent(name: str, state: AgentState = AgentState.IDLE,
                agent_type: AgentType = AgentType.USER,
                successes: int = 0, failures: int = 0,
                consec_failures: int = 0, task_id: str = None,
                usdc: float = 10.0, eth: float = 0.001) -> AgentLifecycle:
    agent = AgentLifecycle(
        agent_name=name,
        agent_type=agent_type,
        state=state,
    )
    agent.total_successes = successes
    agent.total_failures = failures
    agent.consecutive_failures = consec_failures
    agent.current_task_id = task_id
    agent.usdc_balance = usdc
    agent.eth_balance = eth
    agent.last_heartbeat = datetime.now(timezone.utc).isoformat()
    return agent


@pytest.fixture
def sample_agents():
    return [
        _make_agent("kk-coordinator", AgentState.IDLE, AgentType.SYSTEM, 50, 2),
        _make_agent("kk-validator", AgentState.IDLE, AgentType.SYSTEM, 30, 1),
        _make_agent("kk-karma-hello", AgentState.WORKING, AgentType.CORE, 100, 5, task_id="task_123"),
        _make_agent("kk-abracadabra", AgentState.IDLE, AgentType.USER, 75, 3),
        _make_agent("kk-agent-3", AgentState.ERROR, AgentType.USER, 10, 8, 3),
        _make_agent("kk-agent-4", AgentState.COOLDOWN, AgentType.USER, 40, 2),
        _make_agent("kk-agent-5", AgentState.IDLE, AgentType.USER, 60, 1, usdc=0.01),  # Low balance
    ]


@pytest.fixture
def sample_data(sample_agents):
    config = LifecycleConfig()
    now = datetime.now(timezone.utc)
    health = assess_swarm_health(sample_agents, config, now)

    # Minimal reputation data
    from lib.reputation_bridge import UnifiedReputation, ReputationTier, classify_tier

    reps = {}
    for agent in sample_agents:
        score = 50.0 + agent.total_successes * 0.5 - agent.total_failures * 2
        rep = UnifiedReputation(
            agent_name=agent.agent_name,
            composite_score=score,
            effective_confidence=0.5,
            on_chain_score=score,
            off_chain_score=score,
            transactional_score=score,
            sources_available=["lifecycle"],
        )
        rep.tier = classify_tier(score)
        reps[agent.agent_name] = rep

    actions = [
        {"priority": "critical", "agent": "kk-agent-3", "reason": "3 consecutive failures — circuit breaker imminent"},
        {"priority": "high", "agent": "kk-agent-5", "reason": "Low USDC balance ($0.01)"},
    ]

    return {
        "timestamp": now.isoformat(),
        "agents": sample_agents,
        "health": health,
        "agent_snapshots": [],
        "metrics": None,
        "reputations": reps,
        "actions": actions,
        "config": config,
    }


# ---------------------------------------------------------------------------
# Tests: Markdown Rendering
# ---------------------------------------------------------------------------

class TestMarkdownDashboard:
    def test_returns_string(self, sample_data):
        output = render_markdown(sample_data)
        assert isinstance(output, str)
        assert len(output) > 100

    def test_contains_header(self, sample_data):
        output = render_markdown(sample_data)
        assert "KK V2 Swarm Dashboard" in output

    def test_contains_fleet_status(self, sample_data):
        output = render_markdown(sample_data)
        assert "Fleet Status" in output
        assert "Total Agents" in output

    def test_contains_agent_count(self, sample_data):
        output = render_markdown(sample_data)
        assert "7" in output  # 7 sample agents

    def test_contains_error_agents(self, sample_data):
        output = render_markdown(sample_data)
        assert "Error" in output or "error" in output

    def test_contains_reputation(self, sample_data):
        output = render_markdown(sample_data)
        assert "Reputation" in output

    def test_contains_actions(self, sample_data):
        output = render_markdown(sample_data)
        assert "Actions" in output
        assert "kk-agent-3" in output

    def test_handles_empty_agents(self):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agents": [],
            "health": None,
            "agent_snapshots": [],
            "metrics": None,
            "reputations": {},
            "actions": [],
            "config": LifecycleConfig(),
        }
        output = render_markdown(data)
        assert isinstance(output, str)
        assert "KK V2 Swarm Dashboard" in output


# ---------------------------------------------------------------------------
# Tests: JSON Rendering
# ---------------------------------------------------------------------------

class TestJSONDashboard:
    def test_returns_valid_json(self, sample_data):
        output = render_json(sample_data)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_swarm_section(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        assert "swarm" in parsed
        assert "total_agents" in parsed["swarm"]
        assert parsed["swarm"]["total_agents"] == 7

    def test_contains_agents_list(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        assert "agents" in parsed
        assert len(parsed["agents"]) == 7

    def test_agent_has_required_fields(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        agent = parsed["agents"][0]
        assert "name" in agent
        assert "state" in agent
        assert "type" in agent
        assert "consecutive_failures" in agent

    def test_contains_reputation(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        assert "reputation" in parsed
        assert len(parsed["reputation"]) > 0

    def test_contains_actions(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        assert "actions" in parsed
        assert len(parsed["actions"]) == 2


# ---------------------------------------------------------------------------
# Tests: Terminal Rendering
# ---------------------------------------------------------------------------

class TestTerminalDashboard:
    def test_returns_string(self, sample_data):
        output = render_terminal(sample_data)
        assert isinstance(output, str)
        assert len(output) > 200

    def test_contains_header(self, sample_data):
        output = render_terminal(sample_data)
        assert "KARMA KADABRA V2" in output
        assert "SWARM DASHBOARD" in output

    def test_contains_fleet_box(self, sample_data):
        output = render_terminal(sample_data)
        assert "FLEET STATUS" in output

    def test_contains_agents_box(self, sample_data):
        output = render_terminal(sample_data)
        assert "AGENTS" in output

    def test_contains_leaderboard(self, sample_data):
        output = render_terminal(sample_data)
        assert "REPUTATION LEADERBOARD" in output

    def test_contains_actions_box(self, sample_data):
        output = render_terminal(sample_data)
        assert "RECOMMENDED ACTIONS" in output

    def test_agent_states_displayed(self, sample_data):
        output = render_terminal(sample_data)
        assert "kk-coordinator" in output
        assert "kk-agent-3" in output

    def test_handles_no_reputation(self):
        agents = [_make_agent("test-agent")]
        config = LifecycleConfig()
        health = assess_swarm_health(agents, config, datetime.now(timezone.utc))
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agents": agents,
            "health": health,
            "agent_snapshots": [],
            "metrics": None,
            "reputations": {},
            "actions": [],
            "config": config,
        }
        output = render_terminal(data)
        assert "AGENTS" in output
        # No leaderboard section when no reputations
        assert "REPUTATION LEADERBOARD" not in output


# ---------------------------------------------------------------------------
# Tests: Data Integrity
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_all_agents_in_json(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        names_in_json = {a["name"] for a in parsed["agents"]}
        names_in_data = {a.agent_name for a in sample_data["agents"]}
        assert names_in_json == names_in_data

    def test_health_counts_match(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        swarm = parsed["swarm"]
        total = swarm["online"] + swarm["error"] + swarm["offline"] + swarm["cooldown"]
        assert total == swarm["total_agents"]

    def test_success_rate_consistent(self, sample_data):
        parsed = json.loads(render_json(sample_data))
        rate = parsed["swarm"]["success_rate"]
        assert 0 <= rate <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
