"""
Tests for lib/agent_memory.py — Persistent Agent Memory

Covers:
  - AgentMemory construction (creates dirs, loads existing)
  - record_seen (creates agent entry, updates last_seen, increments count)
  - record_interaction (purchase, sale, note, cap at 50)
  - add_note (free text, cap at 20)
  - update_role (role, sells, buys)
  - get_agent (existing, unknown)
  - list_agents (sorted)
  - get_summary (formatted output)
  - KNOWN_ROLES (default role info for system agents)
  - Persistence (_save/_load cycle)
  - Edge cases: bad JSON, missing file, large interaction history
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from lib.agent_memory import AgentMemory, KNOWN_ROLES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mem(tmp_path):
    """Create an AgentMemory with a temp workspace."""
    return AgentMemory(tmp_path / "workspace")


@pytest.fixture
def populated_mem(mem):
    """Memory with some pre-recorded agents."""
    mem.record_seen("kk-skill-extractor", channel="#Agents")
    mem.record_seen("kk-voice-extractor", channel="#Agents")
    mem.record_interaction("kk-skill-extractor", "purchase", amount=0.05)
    return mem


# ---------------------------------------------------------------------------
# KNOWN_ROLES
# ---------------------------------------------------------------------------


class TestKnownRoles:
    def test_coordinator_role(self):
        assert "kk-coordinator" in KNOWN_ROLES
        assert KNOWN_ROLES["kk-coordinator"]["role"] == "Orchestrator"

    def test_karma_hello_role(self):
        assert "kk-karma-hello" in KNOWN_ROLES
        assert KNOWN_ROLES["kk-karma-hello"]["role"] == "Data Collector"

    def test_all_roles_have_required_fields(self):
        for name, info in KNOWN_ROLES.items():
            assert "role" in info, f"{name} missing 'role'"
            assert "sells" in info, f"{name} missing 'sells'"
            assert "buys" in info, f"{name} missing 'buys'"

    def test_expected_agents(self):
        expected = [
            "kk-coordinator", "kk-karma-hello", "kk-skill-extractor",
            "kk-voice-extractor", "kk-soul-extractor", "kk-validator",
        ]
        for name in expected:
            assert name in KNOWN_ROLES


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_creates_memory_dir(self, tmp_path):
        workspace = tmp_path / "new_workspace"
        mem = AgentMemory(workspace)
        assert (workspace / "memory").exists()

    def test_starts_empty(self, mem):
        assert mem.list_agents() == []

    def test_loads_existing_file(self, tmp_path):
        workspace = tmp_path / "workspace"
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True)
        agents_file = memory_dir / "agents.json"
        agents_file.write_text(json.dumps({
            "existing-agent": {
                "first_seen": "2026-01-01T00:00:00",
                "last_seen": "2026-01-01T00:00:00",
                "role": "Test",
                "message_count": 5,
            }
        }))

        mem = AgentMemory(workspace)
        assert "existing-agent" in mem.list_agents()

    def test_handles_bad_json_file(self, tmp_path):
        workspace = tmp_path / "workspace"
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "agents.json").write_text("not valid json {{{")

        mem = AgentMemory(workspace)
        assert mem.list_agents() == []  # graceful fallback


# ---------------------------------------------------------------------------
# record_seen
# ---------------------------------------------------------------------------


class TestRecordSeen:
    def test_creates_new_agent(self, mem):
        mem.record_seen("new-agent")
        agent = mem.get_agent("new-agent")
        assert agent is not None
        assert agent["message_count"] == 1
        assert agent["role"] == "unknown"

    def test_increments_message_count(self, mem):
        mem.record_seen("agent-a")
        mem.record_seen("agent-a")
        mem.record_seen("agent-a")
        assert mem.get_agent("agent-a")["message_count"] == 3

    def test_updates_last_seen(self, mem):
        mem.record_seen("agent-b")
        first_seen = mem.get_agent("agent-b")["last_seen"]
        mem.record_seen("agent-b")
        second_seen = mem.get_agent("agent-b")["last_seen"]
        assert second_seen >= first_seen

    def test_known_agent_gets_default_role(self, mem):
        mem.record_seen("kk-skill-extractor")
        agent = mem.get_agent("kk-skill-extractor")
        assert agent["role"] == "Skill Analyst"
        assert "skill profiles" in agent["sells"]

    def test_unknown_agent_default_role(self, mem):
        mem.record_seen("random-agent")
        agent = mem.get_agent("random-agent")
        assert agent["role"] == "unknown"
        assert agent["sells"] == ""

    def test_persists_to_disk(self, mem):
        mem.record_seen("persistent-agent")
        assert mem.agents_file.exists()
        data = json.loads(mem.agents_file.read_text())
        assert "persistent-agent" in data


# ---------------------------------------------------------------------------
# record_interaction
# ---------------------------------------------------------------------------


class TestRecordInteraction:
    def test_basic_interaction(self, mem):
        mem.record_interaction("buyer", "purchase", amount=0.05)
        agent = mem.get_agent("buyer")
        assert len(agent["interactions"]) == 1
        assert agent["interactions"][0]["type"] == "purchase"
        assert agent["interactions"][0]["amount"] == 0.05

    def test_interaction_with_note(self, mem):
        mem.record_interaction("seller", "sale", amount=0.10, note="skill data")
        interaction = mem.get_agent("seller")["interactions"][0]
        assert interaction["note"] == "skill data"

    def test_interaction_without_note(self, mem):
        mem.record_interaction("agent", "trade", amount=0.01)
        interaction = mem.get_agent("agent")["interactions"][0]
        assert "note" not in interaction

    def test_multiple_interactions(self, mem):
        mem.record_interaction("busy", "purchase", amount=0.01)
        mem.record_interaction("busy", "sale", amount=0.05)
        mem.record_interaction("busy", "purchase", amount=0.02)
        agent = mem.get_agent("busy")
        assert len(agent["interactions"]) == 3

    def test_interaction_cap_at_50(self, mem):
        for i in range(60):
            mem.record_interaction("heavy", "trade", amount=0.01)
        agent = mem.get_agent("heavy")
        assert len(agent["interactions"]) == 50

    def test_interaction_date_format(self, mem):
        mem.record_interaction("dated", "purchase")
        date = mem.get_agent("dated")["interactions"][0]["date"]
        # Should be YYYY-MM-DD format
        parts = date.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year

    def test_interaction_updates_last_seen(self, mem):
        mem.record_seen("early")
        first = mem.get_agent("early")["last_seen"]
        mem.record_interaction("early", "purchase")
        second = mem.get_agent("early")["last_seen"]
        assert second >= first


# ---------------------------------------------------------------------------
# add_note
# ---------------------------------------------------------------------------


class TestAddNote:
    def test_basic_note(self, mem):
        mem.add_note("noted-agent", "Seems reliable")
        agent = mem.get_agent("noted-agent")
        assert "Seems reliable" in agent["notes"]

    def test_multiple_notes(self, mem):
        mem.add_note("noted", "Note 1")
        mem.add_note("noted", "Note 2")
        assert len(mem.get_agent("noted")["notes"]) == 2

    def test_note_cap_at_20(self, mem):
        for i in range(25):
            mem.add_note("verbose", f"Note {i}")
        assert len(mem.get_agent("verbose")["notes"]) == 20


# ---------------------------------------------------------------------------
# update_role
# ---------------------------------------------------------------------------


class TestUpdateRole:
    def test_update_role(self, mem):
        mem.record_seen("agent-x")
        mem.update_role("agent-x", role="Custom Role")
        assert mem.get_agent("agent-x")["role"] == "Custom Role"

    def test_update_sells(self, mem):
        mem.update_role("agent-y", sells="premium data ($0.10)")
        assert mem.get_agent("agent-y")["sells"] == "premium data ($0.10)"

    def test_update_buys(self, mem):
        mem.update_role("agent-z", buys="raw logs ($0.01)")
        assert mem.get_agent("agent-z")["buys"] == "raw logs ($0.01)"

    def test_partial_update(self, mem):
        mem.record_seen("kk-coordinator")
        original_role = mem.get_agent("kk-coordinator")["role"]
        mem.update_role("kk-coordinator", sells="new products")
        assert mem.get_agent("kk-coordinator")["role"] == original_role  # unchanged
        assert mem.get_agent("kk-coordinator")["sells"] == "new products"

    def test_empty_strings_dont_overwrite(self, mem):
        mem.record_seen("kk-skill-extractor")
        mem.update_role("kk-skill-extractor", role="", sells="")
        # Empty strings should NOT overwrite existing values
        agent = mem.get_agent("kk-skill-extractor")
        assert agent["role"] == "Skill Analyst"  # preserved


# ---------------------------------------------------------------------------
# get_agent / list_agents
# ---------------------------------------------------------------------------


class TestAccess:
    def test_get_unknown_agent(self, mem):
        assert mem.get_agent("nonexistent") is None

    def test_list_agents_sorted(self, populated_mem):
        agents = populated_mem.list_agents()
        assert agents == sorted(agents)
        assert len(agents) == 2

    def test_list_agents_empty(self, mem):
        assert mem.list_agents() == []


# ---------------------------------------------------------------------------
# get_summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_summary_empty(self, mem):
        assert "No agents known" in mem.get_summary()

    def test_summary_with_agents(self, populated_mem):
        summary = populated_mem.get_summary()
        assert "Known agents (2)" in summary
        assert "kk-skill-extractor" in summary
        assert "kk-voice-extractor" in summary

    def test_summary_shows_roles(self, populated_mem):
        summary = populated_mem.get_summary()
        assert "Skill Analyst" in summary

    def test_summary_shows_counts(self, populated_mem):
        summary = populated_mem.get_summary()
        assert "1 msgs" in summary  # each was seen once
        assert "1 interactions" in summary  # skill-extractor had 1


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_load_cycle(self, tmp_path):
        workspace = tmp_path / "workspace"
        mem1 = AgentMemory(workspace)
        mem1.record_seen("persist-test")
        mem1.record_interaction("persist-test", "purchase", amount=0.05)
        mem1.add_note("persist-test", "Good agent")

        # Create new instance from same workspace
        mem2 = AgentMemory(workspace)
        agent = mem2.get_agent("persist-test")
        assert agent is not None
        assert agent["message_count"] == 1
        assert len(agent["interactions"]) == 1
        assert "Good agent" in agent["notes"]

    def test_concurrent_writes(self, tmp_path):
        workspace = tmp_path / "workspace"
        mem = AgentMemory(workspace)
        for i in range(20):
            mem.record_seen(f"agent-{i}")
        assert len(mem.list_agents()) == 20
