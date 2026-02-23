"""
Tests for lib/acontext_client.py — Acontext Integration for KK Agents

Covers:
  - Client initialization and availability checks
  - Graceful degradation when SDK/API unavailable
  - Session management (create, store, retrieve)
  - Compressed context retrieval
  - Session summaries
  - Disk (workspace) management
  - Artifact storage and search
  - Convenience methods (coordinator events, agent lookups)
  - Health check
  - Singleton pattern
"""

from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════
# Helpers — Reset module state between tests
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset the module-level singleton and lazy client before each test."""
    import lib.acontext_client as mod

    mod._client = None
    mod._kk_client = None
    yield
    mod._client = None
    mod._kk_client = None


def _make_client_available():
    """Create a KKAcontextClient with a mocked SDK client."""
    import lib.acontext_client as mod

    mock_sdk = MagicMock()
    mod._client = mock_sdk  # Set the lazy-loaded global

    from lib.acontext_client import KKAcontextClient

    client = KKAcontextClient()
    return client, mock_sdk


def _make_client_unavailable():
    """Create a KKAcontextClient with no SDK available."""
    import lib.acontext_client as mod

    mod._client = None

    from lib.acontext_client import KKAcontextClient

    client = KKAcontextClient()
    client._client = None  # Ensure unavailable
    return client


# ═══════════════════════════════════════════════════════════════════
# TestClientAvailability — SDK presence and initialization
# ═══════════════════════════════════════════════════════════════════


class TestClientAvailability:
    """Client availability based on SDK and API key."""

    def test_available_when_sdk_present(self):
        client, _ = _make_client_available()
        assert client.available is True

    def test_unavailable_when_no_sdk(self):
        client = _make_client_unavailable()
        assert client.available is False

    def test_get_client_no_api_key(self):
        """Without ACONTEXT_API_KEY, client should be None."""
        import lib.acontext_client as mod

        mod._client = None

        with patch.dict(os.environ, {}, clear=True):
            with patch("lib.acontext_client._get_client", return_value=None):
                from lib.acontext_client import KKAcontextClient

                c = KKAcontextClient()
                c._client = None
                assert c.available is False

    def test_lazy_initialization(self):
        """_get_client should be called lazily on first use."""
        import lib.acontext_client as mod

        # Module-level _client starts as None
        assert mod._client is None


# ═══════════════════════════════════════════════════════════════════
# TestSessionManagement — Create and manage agent sessions
# ═══════════════════════════════════════════════════════════════════


class TestSessionManagement:
    """Agent session lifecycle."""

    def test_create_session_success(self):
        client, mock_sdk = _make_client_available()
        mock_session = MagicMock()
        mock_session.id = "session-abc-123"
        mock_sdk.sessions.create.return_value = mock_session

        result = client.create_agent_session(
            "kk-coordinator", agent_id=18775, archetype="coordinator"
        )
        assert result is not None
        assert result.id == "session-abc-123"
        assert client.get_agent_session_id("kk-coordinator") == "session-abc-123"

    def test_create_session_stores_id(self):
        client, mock_sdk = _make_client_available()
        mock_session = MagicMock()
        mock_session.id = "sess-001"
        mock_sdk.sessions.create.return_value = mock_session

        client.create_agent_session("agent-01")
        assert client._agent_sessions["agent-01"] == "sess-001"

    def test_create_session_metadata(self):
        client, mock_sdk = _make_client_available()
        mock_session = MagicMock()
        mock_session.id = "sess-002"
        mock_sdk.sessions.create.return_value = mock_session

        client.create_agent_session(
            "kk-explorer",
            agent_id=18780,
            archetype="explorer",
            cycle_id="cycle-2026-02-22",
        )

        call_kwargs = mock_sdk.sessions.create.call_args[1]
        metadata = call_kwargs["metadata"]
        assert metadata["agent_name"] == "kk-explorer"
        assert metadata["archetype"] == "explorer"
        assert metadata["erc8004_agent_id"] == 18780
        assert metadata["cycle"] == "cycle-2026-02-22"
        assert metadata["platform"] == "execution-market"

    def test_create_session_default_cycle(self):
        client, mock_sdk = _make_client_available()
        mock_session = MagicMock()
        mock_session.id = "sess-003"
        mock_sdk.sessions.create.return_value = mock_session

        client.create_agent_session("agent-02")
        call_kwargs = mock_sdk.sessions.create.call_args[1]
        metadata = call_kwargs["metadata"]
        # cycle should be an ISO datetime string
        assert "T" in metadata["cycle"]

    def test_create_session_no_agent_id(self):
        client, mock_sdk = _make_client_available()
        mock_session = MagicMock()
        mock_session.id = "sess-004"
        mock_sdk.sessions.create.return_value = mock_session

        client.create_agent_session("agent-03")
        call_kwargs = mock_sdk.sessions.create.call_args[1]
        metadata = call_kwargs["metadata"]
        assert "erc8004_agent_id" not in metadata

    def test_create_session_sdk_error_returns_none(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.create.side_effect = Exception("API error")

        result = client.create_agent_session("agent-fail")
        assert result is None

    def test_create_session_unavailable_returns_none(self):
        client = _make_client_unavailable()
        result = client.create_agent_session("agent-x")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# TestStoreInteraction — Message storage in sessions
# ═══════════════════════════════════════════════════════════════════


class TestStoreInteraction:
    """Store messages in agent sessions."""

    def test_store_success(self):
        client, mock_sdk = _make_client_available()
        result = client.store_interaction(
            "sess-001", role="user", content="Browse EM for tasks"
        )
        assert result is True
        mock_sdk.sessions.store_message.assert_called_once()

    def test_store_with_metadata(self):
        client, mock_sdk = _make_client_available()
        meta = {"task_id": "task-42", "action": "browse"}
        result = client.store_interaction(
            "sess-001",
            role="assistant",
            content="Found 3 available tasks",
            metadata=meta,
        )
        assert result is True
        call_kwargs = mock_sdk.sessions.store_message.call_args[1]
        blob = call_kwargs["blob"]
        assert blob["metadata"] == meta

    def test_store_format_passed(self):
        client, mock_sdk = _make_client_available()
        client.store_interaction(
            "sess-001", role="user", content="test", format="openai"
        )
        call_kwargs = mock_sdk.sessions.store_message.call_args[1]
        assert call_kwargs["format"] == "openai"

    def test_store_error_returns_false(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.store_message.side_effect = Exception("Storage error")
        result = client.store_interaction("sess-001", role="user", content="fail")
        assert result is False

    def test_store_unavailable_returns_false(self):
        client = _make_client_unavailable()
        result = client.store_interaction("sess-001", role="user", content="test")
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# TestCompressedContext — Context retrieval with edit strategies
# ═══════════════════════════════════════════════════════════════════


class TestCompressedContext:
    """Compressed context retrieval for agents."""

    def test_get_context_success(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.get_messages.return_value = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]

        result = client.get_compressed_context("sess-001")
        assert result is not None
        assert len(result) == 2

    def test_get_context_edit_strategies(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.get_messages.return_value = []

        client.get_compressed_context("sess-001", max_tokens=30000, keep_recent_tools=3)
        call_kwargs = mock_sdk.sessions.get_messages.call_args[1]
        strategies = call_kwargs["edit_strategies"]
        assert len(strategies) == 2
        assert strategies[0]["type"] == "remove_tool_result"
        assert strategies[0]["params"]["keep_recent_n_tool_results"] == 3
        assert strategies[1]["type"] == "token_limit"
        assert strategies[1]["params"]["limit_tokens"] == 30000

    def test_get_context_format(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.get_messages.return_value = []

        client.get_compressed_context("sess-001", format="openai")
        call_kwargs = mock_sdk.sessions.get_messages.call_args[1]
        assert call_kwargs["format"] == "openai"

    def test_get_context_error_returns_none(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.get_messages.side_effect = Exception("Timeout")

        result = client.get_compressed_context("sess-001")
        assert result is None

    def test_get_context_unavailable_returns_none(self):
        client = _make_client_unavailable()
        result = client.get_compressed_context("sess-001")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# TestSessionSummary — AI-generated session summaries
# ═══════════════════════════════════════════════════════════════════


class TestSessionSummary:
    """Session summary generation."""

    def test_get_summary_success(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.get_session_summary.return_value = (
            "Agent explored 5 tasks and applied for 2."
        )

        result = client.get_session_summary("sess-001")
        assert result == "Agent explored 5 tasks and applied for 2."

    def test_get_summary_error_returns_none(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.sessions.get_session_summary.side_effect = Exception("Error")

        result = client.get_session_summary("sess-001")
        assert result is None

    def test_get_summary_unavailable_returns_none(self):
        client = _make_client_unavailable()
        result = client.get_session_summary("sess-001")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# TestDiskManagement — Agent workspace persistence
# ═══════════════════════════════════════════════════════════════════


class TestDiskManagement:
    """Agent disk (workspace) creation and management."""

    def test_create_disk_success(self):
        client, mock_sdk = _make_client_available()
        mock_disk = MagicMock()
        mock_disk.id = "disk-001"
        mock_sdk.disks.create.return_value = mock_disk

        result = client.create_agent_disk("kk-coordinator")
        assert result is not None
        assert result.id == "disk-001"
        assert client.get_agent_disk_id("kk-coordinator") == "disk-001"

    def test_create_disk_name_format(self):
        client, mock_sdk = _make_client_available()
        mock_disk = MagicMock()
        mock_disk.id = "disk-002"
        mock_sdk.disks.create.return_value = mock_disk

        client.create_agent_disk("kk-explorer", metadata={"region": "us-east-1"})
        call_kwargs = mock_sdk.disks.create.call_args[1]
        assert call_kwargs["name"] == "kk-kk-explorer-workspace"

    def test_create_disk_error_returns_none(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.disks.create.side_effect = Exception("Disk error")

        result = client.create_agent_disk("agent-fail")
        assert result is None

    def test_create_disk_unavailable_returns_none(self):
        client = _make_client_unavailable()
        result = client.create_agent_disk("agent-x")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# TestArtifacts — File storage and search on disks
# ═══════════════════════════════════════════════════════════════════


class TestArtifacts:
    """Artifact storage and search operations."""

    def test_store_artifact_success(self):
        client, mock_sdk = _make_client_available()
        result = client.store_artifact(
            "disk-001", path="/logs", filename="cycle.log", content="Log data"
        )
        assert result is True
        mock_sdk.artifacts.upsert.assert_called_once_with(
            disk_id="disk-001",
            path="/logs",
            filename="cycle.log",
            content="Log data",
        )

    def test_store_artifact_bytes(self):
        client, mock_sdk = _make_client_available()
        result = client.store_artifact(
            "disk-001", path="/data", filename="blob.bin", content=b"\x00\x01\x02"
        )
        assert result is True

    def test_store_artifact_error_returns_false(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.artifacts.upsert.side_effect = Exception("Write error")
        result = client.store_artifact(
            "disk-001", path="/", filename="test", content="x"
        )
        assert result is False

    def test_store_artifact_unavailable_returns_false(self):
        client = _make_client_unavailable()
        result = client.store_artifact(
            "disk-001", path="/", filename="test", content="x"
        )
        assert result is False

    def test_search_artifacts_success(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.artifacts.search_content.return_value = [
            {"path": "/logs/day1.log", "match": "task completed"}
        ]
        result = client.search_artifacts("disk-001", "task completed")
        assert result is not None
        assert len(result) == 1

    def test_search_artifacts_error_returns_none(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.artifacts.search_content.side_effect = Exception("Search error")
        result = client.search_artifacts("disk-001", "pattern")
        assert result is None

    def test_search_artifacts_unavailable_returns_none(self):
        client = _make_client_unavailable()
        result = client.search_artifacts("disk-001", "pattern")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# TestConvenienceMethods — Coordinator events and lookups
# ═══════════════════════════════════════════════════════════════════


class TestConvenienceMethods:
    """Convenience methods for common operations."""

    def test_get_agent_session_id_exists(self):
        client, _ = _make_client_available()
        client._agent_sessions["kk-coordinator"] = "sess-abc"
        assert client.get_agent_session_id("kk-coordinator") == "sess-abc"

    def test_get_agent_session_id_missing(self):
        client, _ = _make_client_available()
        assert client.get_agent_session_id("nonexistent") is None

    def test_get_agent_disk_id_exists(self):
        client, _ = _make_client_available()
        client._agent_disks["kk-coordinator"] = "disk-abc"
        assert client.get_agent_disk_id("kk-coordinator") == "disk-abc"

    def test_get_agent_disk_id_missing(self):
        client, _ = _make_client_available()
        assert client.get_agent_disk_id("nonexistent") is None

    def test_store_coordinator_event(self):
        client, mock_sdk = _make_client_available()
        result = client.store_coordinator_event(
            "sess-001",
            event_type="task_assignment",
            details={"task_id": "42", "agent": "kk-explorer"},
        )
        assert result is True
        call_kwargs = mock_sdk.sessions.store_message.call_args[1]
        blob = call_kwargs["blob"]
        assert "[TASK_ASSIGNMENT]" in blob["content"]
        assert blob["metadata"]["event_type"] == "task_assignment"

    def test_store_coordinator_event_unavailable(self):
        client = _make_client_unavailable()
        result = client.store_coordinator_event(
            "sess-001", event_type="test", details={}
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# TestHealthCheck — Server health monitoring
# ═══════════════════════════════════════════════════════════════════


class TestHealthCheck:
    """Acontext server health check."""

    def test_health_check_healthy(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.ping.return_value = "pong"
        result = client.health_check()
        assert result["status"] == "healthy"
        assert "pong" in result["response"]

    def test_health_check_unhealthy(self):
        client, mock_sdk = _make_client_available()
        mock_sdk.ping.side_effect = Exception("Connection refused")
        result = client.health_check()
        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["error"]

    def test_health_check_unavailable(self):
        client = _make_client_unavailable()
        result = client.health_check()
        assert result["status"] == "unavailable"
        assert "not initialized" in result["reason"]


# ═══════════════════════════════════════════════════════════════════
# TestSingleton — Module-level singleton pattern
# ═══════════════════════════════════════════════════════════════════


class TestSingleton:
    """get_acontext singleton behavior."""

    def test_singleton_returns_same_instance(self):
        from lib.acontext_client import get_acontext

        c1 = get_acontext()
        c2 = get_acontext()
        assert c1 is c2

    def test_singleton_creates_instance(self):
        from lib.acontext_client import get_acontext

        c = get_acontext()
        assert c is not None

    def test_singleton_reset(self):
        """After reset, new instance is created."""
        import lib.acontext_client as mod
        from lib.acontext_client import get_acontext

        c1 = get_acontext()
        mod._kk_client = None
        c2 = get_acontext()
        assert c1 is not c2


# ═══════════════════════════════════════════════════════════════════
# TestGracefulDegradation — Everything works when SDK unavailable
# ═══════════════════════════════════════════════════════════════════


class TestGracefulDegradation:
    """All methods return safe defaults when Acontext is unavailable."""

    def test_all_methods_return_safely(self):
        """No method should raise when client is unavailable."""
        client = _make_client_unavailable()

        # All should return None or False without raising
        assert client.create_agent_session("test") is None
        assert client.store_interaction("s", "user", "content") is False
        assert client.get_compressed_context("s") is None
        assert client.get_session_summary("s") is None
        assert client.create_agent_disk("test") is None
        assert client.store_artifact("d", "/", "f", "c") is False
        assert client.search_artifacts("d", "p") is None
        assert client.store_coordinator_event("s", "evt", {}) is False
        result = client.health_check()
        assert result["status"] == "unavailable"

    def test_agent_lookups_work_without_sdk(self):
        """Session/disk ID lookups work even without SDK."""
        client = _make_client_unavailable()
        # These use internal dicts, no SDK needed
        assert client.get_agent_session_id("test") is None
        assert client.get_agent_disk_id("test") is None

        # Manually set values should still be retrievable
        client._agent_sessions["test"] = "manual-session"
        assert client.get_agent_session_id("test") == "manual-session"
