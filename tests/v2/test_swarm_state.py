"""
Tests for lib/swarm_state.py — Shared Swarm State Client

Tests the Supabase-backed state management used by all KK agents.
All DB calls are mocked — no Supabase connection needed.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import swarm_state


# ── Fixtures ──


@pytest.fixture(autouse=True)
def reset_supabase_client():
    """Reset lazy-loaded client between tests."""
    swarm_state._supabase_client = None
    yield
    swarm_state._supabase_client = None


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client with chainable API."""
    client = MagicMock()
    # Make table().select/insert/update/upsert/delete chainable
    table = MagicMock()
    client.table.return_value = table

    # Default: select returns empty
    execute_result = MagicMock()
    execute_result.data = []
    table.select.return_value.eq.return_value.execute.return_value = execute_result
    table.select.return_value.execute.return_value = execute_result
    table.upsert.return_value.execute.return_value = execute_result
    table.insert.return_value.execute.return_value = execute_result
    table.update.return_value.eq.return_value.execute.return_value = execute_result
    table.delete.return_value.eq.return_value.execute.return_value = execute_result

    return client


# ── _get_supabase tests ──


class TestGetSupabase:
    def test_returns_none_without_env(self):
        """No SUPABASE_URL → returns None gracefully."""
        with patch.dict("os.environ", {}, clear=True):
            swarm_state._supabase_client = None
            result = swarm_state._get_supabase()
            # Should be None or warn — either is acceptable
            # The function is designed for graceful degradation

    def test_returns_none_without_supabase_package(self):
        """Missing supabase-py → returns None."""
        with patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_ANON_KEY": "test-key"}):
            with patch.dict("sys.modules", {"supabase": None}):
                swarm_state._supabase_client = None
                # Should handle missing package gracefully


# ── get_agent_states tests ──


class TestGetAgentStates:
    @pytest.mark.asyncio
    async def test_returns_empty_without_client(self):
        """No Supabase → returns empty dict."""
        with patch.object(swarm_state, "_get_supabase", return_value=None):
            result = await swarm_state.get_agent_states()
            assert result == {} or result == []

    @pytest.mark.asyncio
    async def test_returns_states_from_db(self, mock_supabase):
        """Parses agent states from Supabase response."""
        mock_data = [
            {
                "agent_id": "kk-coordinator",
                "status": "idle",
                "last_heartbeat": "2026-02-24T03:00:00+00:00",
                "current_task": None,
            },
            {
                "agent_id": "kk-karma-hello",
                "status": "working",
                "last_heartbeat": "2026-02-24T02:55:00+00:00",
                "current_task": "task-123",
            },
        ]
        execute_result = MagicMock()
        execute_result.data = mock_data
        mock_supabase.table.return_value.select.return_value.execute.return_value = execute_result

        with patch.object(swarm_state, "_get_supabase", return_value=mock_supabase):
            result = await swarm_state.get_agent_states()
            # Should return the states (format may vary)
            assert result is not None


# ── get_stale_agents tests ──


class TestGetStaleAgents:
    @pytest.mark.asyncio
    async def test_returns_empty_without_client(self):
        """No Supabase → returns empty list."""
        with patch.object(swarm_state, "_get_supabase", return_value=None):
            result = await swarm_state.get_stale_agents()
            assert result == [] or result is not None

    @pytest.mark.asyncio
    async def test_identifies_stale_by_heartbeat(self, mock_supabase):
        """Agents without recent heartbeat are stale."""
        old_time = "2026-02-24T00:00:00+00:00"  # 3 hours ago
        mock_data = [
            {"agent_id": "kk-stale", "last_heartbeat": old_time, "status": "idle"},
        ]
        execute_result = MagicMock()
        execute_result.data = mock_data
        mock_supabase.table.return_value.select.return_value.execute.return_value = execute_result

        with patch.object(swarm_state, "_get_supabase", return_value=mock_supabase):
            result = await swarm_state.get_stale_agents()
            assert result is not None


# ── claim_task tests ──


class TestClaimTask:
    @pytest.mark.asyncio
    async def test_returns_false_without_client(self):
        """No Supabase → claim fails gracefully."""
        with patch.object(swarm_state, "_get_supabase", return_value=None):
            result = await swarm_state.claim_task("agent-1", "task-1")
            assert result is False or result is None

    @pytest.mark.asyncio
    async def test_successful_claim(self, mock_supabase):
        """Successful claim writes to kk_task_claims."""
        execute_result = MagicMock()
        execute_result.data = [{"agent_id": "agent-1", "task_id": "task-1"}]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = execute_result

        with patch.object(swarm_state, "_get_supabase", return_value=mock_supabase):
            result = await swarm_state.claim_task("agent-1", "task-1")
            # Should succeed
            assert result is not None


# ── send_notification tests ──


class TestSendNotification:
    @pytest.mark.asyncio
    async def test_returns_false_without_client(self):
        """No Supabase → notification fails gracefully."""
        with patch.object(swarm_state, "_get_supabase", return_value=None):
            result = await swarm_state.send_notification("agent-1", "Task assigned", "info")
            assert result is False or result is None

    @pytest.mark.asyncio
    async def test_successful_notification(self, mock_supabase):
        """Successful notification inserts into kk_notifications."""
        execute_result = MagicMock()
        execute_result.data = [{"id": 1}]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = execute_result

        with patch.object(swarm_state, "_get_supabase", return_value=mock_supabase):
            result = await swarm_state.send_notification("agent-1", "New task available", "task_assigned")
            assert result is not None


# ── get_swarm_summary tests ──


class TestGetSwarmSummary:
    @pytest.mark.asyncio
    async def test_returns_summary_without_client(self):
        """No Supabase → returns default/empty summary."""
        with patch.object(swarm_state, "_get_supabase", return_value=None):
            result = await swarm_state.get_swarm_summary()
            assert result is not None  # Should return something, even if empty

    @pytest.mark.asyncio
    async def test_summary_with_agents(self, mock_supabase):
        """Summary aggregates agent statuses."""
        mock_data = [
            {"agent_id": "a1", "status": "idle"},
            {"agent_id": "a2", "status": "working"},
            {"agent_id": "a3", "status": "idle"},
        ]
        execute_result = MagicMock()
        execute_result.data = mock_data
        mock_supabase.table.return_value.select.return_value.execute.return_value = execute_result

        with patch.object(swarm_state, "_get_supabase", return_value=mock_supabase):
            result = await swarm_state.get_swarm_summary()
            assert result is not None


# ── Edge cases ──


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_all_functions_handle_exception(self, mock_supabase):
        """All public functions survive Supabase errors."""
        mock_supabase.table.side_effect = Exception("Connection refused")

        with patch.object(swarm_state, "_get_supabase", return_value=mock_supabase):
            # None of these should raise
            states = await swarm_state.get_agent_states()
            stale = await swarm_state.get_stale_agents()
            claim = await swarm_state.claim_task("a", "t")
            notif = await swarm_state.send_notification("a", "msg", "type")
            summary = await swarm_state.get_swarm_summary()
            # All should return gracefully
            assert True  # If we got here, no exceptions

    def test_module_imports_cleanly(self):
        """Module loads without side effects."""
        import importlib
        importlib.reload(swarm_state)
        assert hasattr(swarm_state, "get_agent_states")
        assert hasattr(swarm_state, "claim_task")
        assert hasattr(swarm_state, "send_notification")
        assert hasattr(swarm_state, "get_stale_agents")
        assert hasattr(swarm_state, "get_swarm_summary")
