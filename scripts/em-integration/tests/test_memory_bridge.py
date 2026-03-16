"""
Tests for Karma Kadabra V2 — Memory Bridge

Covers:
  - LocalBackend file operations (working state, memory, notes, events)
  - MemoryBridge routing (local-first, Acontext write-through)
  - AgentContext assembly and prompt generation
  - Cross-agent queries (coordinator use case)
  - Event logging and querying
  - Graceful degradation when backends unavailable
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.memory_bridge import (
    AgentContext,
    AcontextBackend,
    LocalBackend,
    MemoryBridge,
    MemoryEntry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_workspaces():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        # Create agent workspaces
        for name in ["alice", "bob", "carol"]:
            agent_dir = ws / name / "memory"
            agent_dir.mkdir(parents=True)
            (agent_dir / "notes").mkdir()
        yield ws


@pytest.fixture
def local_backend(tmp_workspaces):
    return LocalBackend(tmp_workspaces)


@pytest.fixture
def bridge(tmp_workspaces):
    return MemoryBridge(tmp_workspaces)


# ---------------------------------------------------------------------------
# MemoryEntry Tests
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    def test_default_values(self):
        entry = MemoryEntry()
        assert entry.source == "local"
        assert entry.metadata == {}

    def test_to_dict(self):
        entry = MemoryEntry(
            timestamp="2026-02-22T03:00:00",
            agent_name="alice",
            category="learned_patterns",
            content="Base chain is faster for small bounties",
        )
        d = entry.to_dict()
        assert d["agent_name"] == "alice"
        assert d["category"] == "learned_patterns"
        assert d["source"] == "local"


# ---------------------------------------------------------------------------
# AgentContext Tests
# ---------------------------------------------------------------------------


class TestAgentContext:
    def test_to_prompt_basic(self):
        ctx = AgentContext(
            agent_name="alice",
            working_state="## Active Task\n- Status: idle",
            memory="## Trusted Agents\n- Bob (reliable)",
            recent_notes=["10:00 Browsed tasks", "10:05 Applied to task-1"],
        )
        prompt = ctx.to_prompt()
        assert "Current State" in prompt
        assert "Agent Memory" in prompt
        assert "Recent Activity" in prompt
        assert ctx.token_estimate > 0

    def test_to_prompt_empty(self):
        ctx = AgentContext(agent_name="empty")
        prompt = ctx.to_prompt()
        assert prompt == ""

    def test_to_prompt_working_state_only(self):
        ctx = AgentContext(
            agent_name="minimal",
            working_state="- Status: idle",
        )
        prompt = ctx.to_prompt()
        assert "Current State" in prompt
        assert "Agent Memory" not in prompt

    def test_to_prompt_respects_token_budget(self):
        ctx = AgentContext(
            agent_name="big",
            working_state="x" * 1000,
            memory="y" * 10000,
            recent_notes=["z" * 100 for _ in range(50)],
        )
        prompt = ctx.to_prompt(max_tokens=500)
        assert ctx.token_estimate <= 500

    def test_token_estimate(self):
        ctx = AgentContext(
            agent_name="test",
            working_state="hello world",  # ~11 chars ≈ 3 tokens
        )
        ctx.to_prompt()
        assert ctx.token_estimate > 0


# ---------------------------------------------------------------------------
# LocalBackend Working State Tests
# ---------------------------------------------------------------------------


class TestLocalBackendWorkingState:
    def test_read_nonexistent(self, local_backend):
        result = local_backend.read_working_state("alice")
        assert result == ""

    def test_write_and_read(self, local_backend):
        content = "## Active Task\n- Status: working\n- Task ID: t1"
        assert local_backend.write_working_state("alice", content) is True
        result = local_backend.read_working_state("alice")
        assert "t1" in result

    def test_write_creates_dirs(self, local_backend, tmp_workspaces):
        """Write to a new agent creates directories."""
        content = "## Status: idle"
        assert local_backend.write_working_state("new_agent", content) is True
        path = tmp_workspaces / "new_agent" / "memory" / "WORKING.md"
        assert path.exists()

    def test_overwrite(self, local_backend):
        local_backend.write_working_state("alice", "version 1")
        local_backend.write_working_state("alice", "version 2")
        result = local_backend.read_working_state("alice")
        assert "version 2" in result


# ---------------------------------------------------------------------------
# LocalBackend Memory Tests
# ---------------------------------------------------------------------------


class TestLocalBackendMemory:
    def test_read_nonexistent(self, local_backend):
        result = local_backend.read_memory("alice")
        assert result == ""

    def test_append_creates_memory(self, local_backend):
        result = local_backend.append_memory("alice", "Trusted Agents", "Bob (reliable)")
        assert result is True
        memory = local_backend.read_memory("alice")
        assert "Bob (reliable)" in memory

    def test_append_to_existing_section(self, local_backend):
        local_backend.append_memory("alice", "Trusted Agents", "Bob")
        local_backend.append_memory("alice", "Trusted Agents", "Carol")
        memory = local_backend.read_memory("alice")
        assert "Bob" in memory
        assert "Carol" in memory

    def test_append_new_section(self, local_backend):
        local_backend.append_memory("alice", "Trusted Agents", "Bob")
        local_backend.append_memory("alice", "New Section", "Something new")
        memory = local_backend.read_memory("alice")
        assert "New Section" in memory
        assert "Something new" in memory

    def test_timestamp_updated(self, local_backend):
        local_backend.append_memory("alice", "Trusted Agents", "Bob")
        memory = local_backend.read_memory("alice")
        assert "Last updated:" in memory


# ---------------------------------------------------------------------------
# LocalBackend Daily Notes Tests
# ---------------------------------------------------------------------------


class TestLocalBackendNotes:
    def test_append_note(self, local_backend):
        result = local_backend.append_note("alice", "Browsed 5 tasks", "found 2 matches")
        assert result is True

    def test_get_recent_notes(self, local_backend):
        local_backend.append_note("alice", "Action 1", "result 1")
        local_backend.append_note("alice", "Action 2", "result 2")
        local_backend.append_note("alice", "Action 3")

        notes = local_backend.get_recent_notes("alice")
        assert len(notes) >= 3

    def test_get_notes_limit(self, local_backend):
        for i in range(10):
            local_backend.append_note("alice", f"Action {i}")

        notes = local_backend.get_recent_notes("alice", limit=3)
        assert len(notes) <= 3

    def test_get_notes_empty_agent(self, local_backend):
        notes = local_backend.get_recent_notes("bob")
        assert notes == []

    def test_get_notes_nonexistent_agent(self, local_backend):
        notes = local_backend.get_recent_notes("nonexistent")
        assert notes == []

    def test_note_creates_file(self, local_backend, tmp_workspaces):
        local_backend.append_note("alice", "First note")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        notes_path = tmp_workspaces / "alice" / "memory" / "notes" / f"{today}.md"
        assert notes_path.exists()
        content = notes_path.read_text()
        assert "First note" in content


# ---------------------------------------------------------------------------
# LocalBackend Event Logging Tests
# ---------------------------------------------------------------------------


class TestLocalBackendEvents:
    def test_log_event(self, local_backend):
        result = local_backend.log_event("alice", "task_complete", {"task_id": "t1"})
        assert result is True

    def test_query_events(self, local_backend):
        local_backend.log_event("alice", "task_complete", {"task_id": "t1"})
        local_backend.log_event("alice", "heartbeat", {"status": "ok"})
        local_backend.log_event("bob", "task_complete", {"task_id": "t2"})

        # All events
        events = local_backend.query_events()
        assert len(events) == 3

    def test_query_by_agent(self, local_backend):
        local_backend.log_event("alice", "task_complete")
        local_backend.log_event("bob", "task_complete")

        events = local_backend.query_events(agent_name="alice")
        assert len(events) == 1
        assert events[0]["agent"] == "alice"

    def test_query_by_type(self, local_backend):
        local_backend.log_event("alice", "task_complete")
        local_backend.log_event("alice", "heartbeat")

        events = local_backend.query_events(event_type="heartbeat")
        assert len(events) == 1
        assert events[0]["event"] == "heartbeat"

    def test_query_by_agent_and_type(self, local_backend):
        local_backend.log_event("alice", "task_complete")
        local_backend.log_event("alice", "heartbeat")
        local_backend.log_event("bob", "task_complete")

        events = local_backend.query_events(agent_name="alice", event_type="task_complete")
        assert len(events) == 1

    def test_query_limit(self, local_backend):
        for i in range(10):
            local_backend.log_event("alice", "heartbeat", {"n": i})

        events = local_backend.query_events(limit=3)
        assert len(events) == 3

    def test_query_empty(self, local_backend):
        events = local_backend.query_events()
        assert events == []

    def test_event_format(self, local_backend):
        local_backend.log_event("alice", "task_complete", {"task_id": "t1", "bounty": 0.10})
        events = local_backend.query_events()
        assert len(events) == 1
        event = events[0]
        assert "timestamp" in event
        assert event["agent"] == "alice"
        assert event["event"] == "task_complete"
        assert event["details"]["task_id"] == "t1"


# ---------------------------------------------------------------------------
# LocalBackend Agent Discovery Tests
# ---------------------------------------------------------------------------


class TestLocalBackendAgentDiscovery:
    def test_get_all_agents(self, local_backend):
        agents = local_backend.get_all_agent_names()
        assert "alice" in agents
        assert "bob" in agents
        assert "carol" in agents

    def test_excludes_underscore_dirs(self, local_backend, tmp_workspaces):
        (tmp_workspaces / "_events").mkdir(exist_ok=True)
        (tmp_workspaces / "_cache").mkdir(exist_ok=True)
        agents = local_backend.get_all_agent_names()
        assert "_events" not in agents
        assert "_cache" not in agents

    def test_sorted(self, local_backend):
        agents = local_backend.get_all_agent_names()
        assert agents == sorted(agents)

    def test_empty_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            backend = LocalBackend(Path(d))
            assert backend.get_all_agent_names() == []

    def test_nonexistent_workspace(self):
        backend = LocalBackend(Path("/nonexistent"))
        assert backend.get_all_agent_names() == []


# ---------------------------------------------------------------------------
# MemoryBridge Tests
# ---------------------------------------------------------------------------


class TestMemoryBridge:
    def test_no_acontext_by_default(self, bridge):
        assert not bridge.has_acontext

    def test_with_acontext(self, tmp_workspaces):
        b = MemoryBridge(tmp_workspaces, acontext_url="http://localhost:8029", acontext_key="sk-test")
        assert b.has_acontext

    def test_read_working_state_delegates_to_local(self, bridge):
        bridge.local.write_working_state("alice", "test state")
        assert "test state" in bridge.read_working_state("alice")

    def test_write_working_state_local_only(self, bridge):
        assert bridge.write_working_state("alice", "new state") is True
        assert "new state" in bridge.local.read_working_state("alice")

    def test_write_working_state_with_acontext(self, tmp_workspaces):
        mock_acontext = MagicMock(spec=AcontextBackend)
        b = MemoryBridge(tmp_workspaces)
        b.acontext = mock_acontext

        b.write_working_state("alice", "state")
        mock_acontext.write_working_state.assert_called_once_with("alice", "state")

    def test_acontext_failure_doesnt_break_local(self, tmp_workspaces):
        mock_acontext = MagicMock(spec=AcontextBackend)
        mock_acontext.write_working_state.side_effect = Exception("Acontext down")
        b = MemoryBridge(tmp_workspaces)
        b.acontext = mock_acontext

        # Should succeed (local write works even if Acontext fails)
        assert b.write_working_state("alice", "state") is True
        assert "state" in b.local.read_working_state("alice")

    def test_append_memory(self, bridge):
        assert bridge.append_memory("alice", "Trusted Agents", "Bob") is True
        memory = bridge.read_memory("alice")
        assert "Bob" in memory

    def test_append_note(self, bridge):
        assert bridge.append_note("alice", "Test action", "ok") is True
        notes = bridge.get_recent_notes("alice")
        assert len(notes) >= 1

    def test_log_event(self, bridge):
        assert bridge.log_event("alice", "heartbeat", {"status": "ok"}) is True
        events = bridge.query_events(agent_name="alice")
        assert len(events) == 1

    def test_get_all_agent_names(self, bridge):
        names = bridge.get_all_agent_names()
        assert "alice" in names
        assert "bob" in names


# ---------------------------------------------------------------------------
# AgentContext Assembly Tests
# ---------------------------------------------------------------------------


class TestGetAgentContext:
    def test_basic_context(self, bridge):
        bridge.write_working_state("alice", "## Status: idle")
        bridge.append_memory("alice", "Notes", "Something important")
        bridge.append_note("alice", "Did a thing")

        ctx = bridge.get_agent_context("alice")
        assert ctx.agent_name == "alice"
        assert "idle" in ctx.working_state
        assert len(ctx.recent_notes) >= 1

    def test_empty_context(self, bridge):
        ctx = bridge.get_agent_context("bob")
        assert ctx.agent_name == "bob"
        assert ctx.working_state == ""
        assert ctx.memory == ""
        assert ctx.recent_notes == []

    def test_context_to_prompt(self, bridge):
        bridge.write_working_state("alice", "Active task: t1")
        ctx = bridge.get_agent_context("alice")
        prompt = ctx.to_prompt()
        assert "Active task: t1" in prompt

    def test_max_notes_respected(self, bridge):
        for i in range(20):
            bridge.append_note("alice", f"Action {i}")

        ctx = bridge.get_agent_context("alice", max_notes=5)
        assert len(ctx.recent_notes) <= 5


# ---------------------------------------------------------------------------
# Swarm Overview Tests
# ---------------------------------------------------------------------------


class TestGetSwarmOverview:
    def test_overview_all_agents(self, bridge):
        bridge.write_working_state("alice", "Alice working")
        bridge.write_working_state("bob", "Bob idle")

        overview = bridge.get_swarm_overview()
        assert "alice" in overview
        assert "bob" in overview
        assert "carol" in overview

    def test_overview_context_quality(self, bridge):
        bridge.write_working_state("alice", "Alice working on task-1")
        bridge.append_note("alice", "Applied to task-1")

        overview = bridge.get_swarm_overview()
        ctx = overview["alice"]
        assert "task-1" in ctx.working_state
        assert len(ctx.recent_notes) >= 1


# ---------------------------------------------------------------------------
# AcontextBackend Graceful Degradation Tests
# ---------------------------------------------------------------------------


class TestAcontextBackendGraceful:
    def test_no_sdk_returns_empty(self):
        with patch.dict("sys.modules", {"acontext": None}):
            backend = AcontextBackend("http://localhost", "sk-test")
            assert backend.read_working_state("alice") == ""
            assert backend.read_memory("alice") == ""
            assert backend.get_recent_notes("alice") == []
            assert backend.query_events() == []

    def test_get_all_agents_returns_sessions(self):
        backend = AcontextBackend("http://localhost", "sk-test")
        backend._sessions = {"alice": "s1", "bob": "s2"}
        assert set(backend.get_all_agent_names()) == {"alice", "bob"}


# ---------------------------------------------------------------------------
# Integration: Memory Bridge + Observability
# ---------------------------------------------------------------------------


class TestMemoryBridgeWithObservability:
    """Test that memory_bridge events integrate with observability queries."""

    def test_events_feed_observability(self, bridge):
        """Events logged through bridge should be queryable for observability."""
        bridge.log_event("alice", "task_complete", {"task_id": "t1", "bounty": 0.10})
        bridge.log_event("alice", "task_complete", {"task_id": "t2", "bounty": 0.05})
        bridge.log_event("alice", "task_fail", {"task_id": "t3", "reason": "expired"})
        bridge.log_event("bob", "task_complete", {"task_id": "t4", "bounty": 0.08})

        # Query all completions
        completions = bridge.query_events(event_type="task_complete")
        assert len(completions) == 3

        # Query per-agent
        alice_events = bridge.query_events(agent_name="alice")
        assert len(alice_events) == 3

        bob_events = bridge.query_events(agent_name="bob")
        assert len(bob_events) == 1

    def test_notes_provide_observability_context(self, bridge):
        """Daily notes provide context for observability health checks."""
        bridge.append_note("alice", "Browsed 10 tasks, found 3 matches")
        bridge.append_note("alice", "[COMPLETED] task-123 category:simple_action chain:base bounty:$0.10")
        bridge.append_note("alice", "[FAILED] task-456 reason:expired")

        notes = bridge.get_recent_notes("alice")
        assert len(notes) == 3
        # Observability can parse these structured notes
        completed = [n for n in notes if "COMPLETED" in n]
        assert len(completed) == 1
