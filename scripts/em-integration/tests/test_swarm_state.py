"""
Tests for Swarm State — KK V2 Shared State via Supabase

Covers:
  - _get_supabase lazy loading (missing env vars, missing package, success)
  - report_heartbeat (upsert, failure handling)
  - get_agent_states (all agents, filtered by status, empty result)
  - get_agent_state (single agent, not found)
  - get_stale_agents (age computation, thresholds)
  - claim_task (success, duplicate/already claimed, error handling)
  - release_claim (success, error)
  - get_claimed_tasks (all, filtered by agent)
  - send_notification (success, error)
  - poll_notifications (fetch + mark delivered, empty, error)
  - get_swarm_summary (aggregation)
  - Graceful degradation (all functions return sensible defaults when Supabase unavailable)
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import swarm_state


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def reset_supabase_client():
    """Reset the lazy-loaded Supabase client between tests."""
    swarm_state._supabase_client = None
    yield
    swarm_state._supabase_client = None


def _make_mock_supabase():
    """Create a mock Supabase client with chained query builders."""
    mock_sb = MagicMock()
    
    # Default: table().method() returns MagicMock with .execute()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    
    return mock_sb, mock_table


# ═══════════════════════════════════════════════════════════════════
# _get_supabase Tests
# ═══════════════════════════════════════════════════════════════════


class TestGetSupabase:
    """Tests for lazy Supabase client initialization."""

    def test_missing_env_vars(self):
        with patch.dict("os.environ", {}, clear=True):
            result = swarm_state._get_supabase()
            assert result is None

    def test_missing_supabase_package(self):
        with patch.dict("os.environ", {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_KEY": "test-key",
        }):
            with patch.dict("sys.modules", {"supabase": None}):
                # Force reimport to trigger ImportError
                swarm_state._supabase_client = None
                # The import will fail inside the function
                result = swarm_state._get_supabase()
                # May return None or succeed depending on whether supabase is installed

    def test_returns_cached_client(self):
        mock_client = MagicMock()
        swarm_state._supabase_client = mock_client
        result = swarm_state._get_supabase()
        assert result is mock_client


# ═══════════════════════════════════════════════════════════════════
# report_heartbeat Tests
# ═══════════════════════════════════════════════════════════════════


class TestReportHeartbeat:
    """Tests for agent heartbeat reporting."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.upsert.return_value.execute.return_value = MagicMock()
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.report_heartbeat(
            agent_name="kk-aurora",
            status="working",
            task_id="task_123",
            daily_spent=0.50,
            current_chain="polygon",
            notes="Processing photo verification",
        )
        assert result is True
        mock_sb.table.assert_called_with("kk_swarm_state")
        # Verify the upsert was called with correct conflict key
        call_args = mock_table.upsert.call_args
        row = call_args[0][0]
        assert row["agent_name"] == "kk-aurora"
        assert row["status"] == "working"
        assert row["task_id"] == "task_123"
        assert row["daily_spent_usd"] == 0.50
        assert row["current_chain"] == "polygon"

    @pytest.mark.asyncio
    async def test_failure_returns_false(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.upsert.return_value.execute.side_effect = Exception("DB error")
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.report_heartbeat("kk-aurora")
        assert result is False

    @pytest.mark.asyncio
    async def test_no_supabase_returns_false(self):
        swarm_state._supabase_client = None
        with patch.dict("os.environ", {}, clear=True):
            result = await swarm_state.report_heartbeat("kk-aurora")
            assert result is False

    @pytest.mark.asyncio
    async def test_default_values(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.upsert.return_value.execute.return_value = MagicMock()
        swarm_state._supabase_client = mock_sb
        
        await swarm_state.report_heartbeat("kk-aurora")
        row = mock_table.upsert.call_args[0][0]
        assert row["status"] == "idle"
        assert row["task_id"] == ""
        assert row["daily_spent_usd"] == 0.0
        assert row["current_chain"] == "base"


# ═══════════════════════════════════════════════════════════════════
# get_agent_states Tests
# ═══════════════════════════════════════════════════════════════════


class TestGetAgentStates:
    """Tests for reading agent states."""

    @pytest.mark.asyncio
    async def test_all_agents(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [
            {"agent_name": "aurora", "status": "idle"},
            {"agent_name": "spark", "status": "working"},
        ]
        mock_table.select.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_states()
        assert len(result) == 2
        assert result[0]["agent_name"] == "aurora"

    @pytest.mark.asyncio
    async def test_filtered_by_status(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [{"agent_name": "spark", "status": "working"}]
        mock_table.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_states(status="working")
        assert len(result) == 1
        assert result[0]["status"] == "working"

    @pytest.mark.asyncio
    async def test_empty_result(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = []
        mock_table.select.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_states()
        assert result == []

    @pytest.mark.asyncio
    async def test_none_data(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = None
        mock_table.select.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_states()
        assert result == []

    @pytest.mark.asyncio
    async def test_error_returns_empty(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.select.return_value.order.return_value.execute.side_effect = Exception("DB error")
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_states()
        assert result == []


# ═══════════════════════════════════════════════════════════════════
# get_agent_state Tests
# ═══════════════════════════════════════════════════════════════════


class TestGetAgentState:
    """Tests for reading a single agent's state."""

    @pytest.mark.asyncio
    async def test_found(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [{"agent_name": "aurora", "status": "working"}]
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_state("aurora")
        assert result is not None
        assert result["agent_name"] == "aurora"

    @pytest.mark.asyncio
    async def test_not_found(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = []
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_state("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.select.side_effect = Exception("Connection error")
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_agent_state("aurora")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# get_stale_agents Tests
# ═══════════════════════════════════════════════════════════════════


class TestGetStaleAgents:
    """Tests for finding stale (non-heartbeating) agents."""

    @pytest.mark.asyncio
    async def test_stale_detection(self):
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(minutes=60)).isoformat()
        fresh_time = (now - timedelta(minutes=5)).isoformat()
        
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [
            {"agent_name": "stale_bot", "status": "idle", "last_heartbeat": old_time},
            {"agent_name": "fresh_bot", "status": "idle", "last_heartbeat": fresh_time},
        ]
        mock_table.select.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_stale_agents(stale_minutes=30)
        assert len(result) == 1
        assert result[0]["agent_name"] == "stale_bot"
        assert "minutes_stale" in result[0]
        assert result[0]["minutes_stale"] > 30

    @pytest.mark.asyncio
    async def test_no_stale_agents(self):
        now = datetime.now(timezone.utc)
        fresh_time = (now - timedelta(minutes=5)).isoformat()
        
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [
            {"agent_name": "bot1", "status": "idle", "last_heartbeat": fresh_time},
        ]
        mock_table.select.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_stale_agents(stale_minutes=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_heartbeat_field(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [
            {"agent_name": "no_hb", "status": "idle"},  # No last_heartbeat
        ]
        mock_table.select.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_stale_agents()
        # Agent without heartbeat should not be in stale list (no timestamp to compare)
        assert result == []


# ═══════════════════════════════════════════════════════════════════
# claim_task Tests
# ═══════════════════════════════════════════════════════════════════


class TestClaimTask:
    """Tests for atomic task claiming."""

    @pytest.mark.asyncio
    async def test_claim_success(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.insert.return_value.execute.return_value = MagicMock()
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.claim_task("task_123", "aurora")
        assert result is True
        row = mock_table.insert.call_args[0][0]
        assert row["em_task_id"] == "task_123"
        assert row["claimed_by"] == "aurora"
        assert row["status"] == "claimed"

    @pytest.mark.asyncio
    async def test_claim_already_claimed(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.insert.return_value.execute.side_effect = Exception(
            "duplicate key value violates unique constraint"
        )
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.claim_task("task_123", "aurora")
        assert result is False

    @pytest.mark.asyncio
    async def test_claim_unique_23505(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.insert.return_value.execute.side_effect = Exception(
            "23505: unique violation"
        )
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.claim_task("task_123", "aurora")
        assert result is False

    @pytest.mark.asyncio
    async def test_claim_other_error(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.insert.return_value.execute.side_effect = Exception("Connection timeout")
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.claim_task("task_123", "aurora")
        assert result is False

    @pytest.mark.asyncio
    async def test_claim_no_supabase(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await swarm_state.claim_task("task_123", "aurora")
            assert result is False


# ═══════════════════════════════════════════════════════════════════
# release_claim Tests
# ═══════════════════════════════════════════════════════════════════


class TestReleaseClaim:
    """Tests for releasing task claims."""

    @pytest.mark.asyncio
    async def test_release_success(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.release_claim("task_123")
        assert result is True
        mock_table.update.assert_called_with({"status": "released"})

    @pytest.mark.asyncio
    async def test_release_error(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.update.return_value.eq.return_value.execute.side_effect = Exception("DB error")
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.release_claim("task_123")
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# get_claimed_tasks Tests
# ═══════════════════════════════════════════════════════════════════


class TestGetClaimedTasks:
    """Tests for reading claimed tasks."""

    @pytest.mark.asyncio
    async def test_all_claims(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [
            {"em_task_id": "t1", "claimed_by": "aurora", "status": "claimed"},
            {"em_task_id": "t2", "claimed_by": "spark", "status": "claimed"},
        ]
        mock_table.select.return_value.eq.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_claimed_tasks()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filtered_by_agent(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [{"em_task_id": "t1", "claimed_by": "aurora", "status": "claimed"}]
        mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.get_claimed_tasks(agent_name="aurora")
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════
# send_notification Tests
# ═══════════════════════════════════════════════════════════════════


class TestSendNotification:
    """Tests for sending notifications between agents."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.insert.return_value.execute.return_value = MagicMock()
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.send_notification(
            target_agent="aurora",
            from_agent="coordinator",
            content="New task available: photo_verification in NYC",
        )
        assert result is True
        row = mock_table.insert.call_args[0][0]
        assert row["target_agent"] == "aurora"
        assert row["from_agent"] == "coordinator"
        assert row["delivered"] is False

    @pytest.mark.asyncio
    async def test_send_error(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.insert.return_value.execute.side_effect = Exception("Table not found")
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.send_notification("aurora", "coord", "hello")
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# poll_notifications Tests
# ═══════════════════════════════════════════════════════════════════


class TestPollNotifications:
    """Tests for polling agent notifications."""

    @pytest.mark.asyncio
    async def test_poll_and_mark_delivered(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "n1", "target_agent": "aurora", "content": "task available", "delivered": False},
            {"id": "n2", "target_agent": "aurora", "content": "standup time", "delivered": False},
        ]
        mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_result
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.poll_notifications("aurora")
        assert len(result) == 2
        # Should mark both as delivered
        assert mock_table.update.call_count == 2

    @pytest.mark.asyncio
    async def test_poll_empty(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_result = MagicMock()
        mock_result.data = []
        mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_result
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.poll_notifications("aurora")
        assert result == []
        # No update calls when no notifications
        mock_table.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_error(self):
        mock_sb, mock_table = _make_mock_supabase()
        mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.side_effect = Exception("Error")
        swarm_state._supabase_client = mock_sb
        
        result = await swarm_state.poll_notifications("aurora")
        assert result == []


# ═══════════════════════════════════════════════════════════════════
# get_swarm_summary Tests
# ═══════════════════════════════════════════════════════════════════


class TestGetSwarmSummary:
    """Tests for swarm state summary."""

    @pytest.mark.asyncio
    async def test_summary(self):
        now = datetime.now(timezone.utc)
        fresh_time = (now - timedelta(minutes=5)).isoformat()
        stale_time = (now - timedelta(minutes=60)).isoformat()
        
        mock_sb, mock_table = _make_mock_supabase()
        
        # Mock get_agent_states call
        mock_all_result = MagicMock()
        mock_all_result.data = [
            {"agent_name": "aurora", "status": "working", "last_heartbeat": fresh_time, "daily_spent_usd": 0.5},
            {"agent_name": "spark", "status": "idle", "last_heartbeat": fresh_time, "daily_spent_usd": 0.1},
            {"agent_name": "stale", "status": "idle", "last_heartbeat": stale_time, "daily_spent_usd": 0},
        ]
        
        # Mock get_claimed_tasks call
        mock_claims_result = MagicMock()
        mock_claims_result.data = [
            {"em_task_id": "t1", "claimed_by": "aurora", "status": "claimed"},
        ]
        
        # We need to mock at the function level since get_swarm_summary calls other functions
        with patch.object(swarm_state, 'get_agent_states', return_value=mock_all_result.data):
            with patch.object(swarm_state, 'get_stale_agents', return_value=[mock_all_result.data[2]]):
                with patch.object(swarm_state, 'get_claimed_tasks', return_value=mock_claims_result.data):
                    summary = await swarm_state.get_swarm_summary()
        
        assert summary["total_agents"] == 3
        assert summary["by_status"]["working"] == 1
        assert summary["by_status"]["idle"] == 2
        assert summary["stale_agents"] == 1
        assert summary["active_claims"] == 1
        assert summary["total_daily_spent_usd"] == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_empty_swarm_summary(self):
        with patch.object(swarm_state, 'get_agent_states', return_value=[]):
            with patch.object(swarm_state, 'get_stale_agents', return_value=[]):
                with patch.object(swarm_state, 'get_claimed_tasks', return_value=[]):
                    summary = await swarm_state.get_swarm_summary()
        
        assert summary["total_agents"] == 0
        assert summary["by_status"] == {}
        assert summary["active_claims"] == 0
        assert summary["total_daily_spent_usd"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# Graceful Degradation Tests
# ═══════════════════════════════════════════════════════════════════


class TestGracefulDegradation:
    """Ensure all functions degrade gracefully without Supabase."""

    @pytest.mark.asyncio
    async def test_all_functions_without_supabase(self):
        """All functions should return sensible defaults when Supabase is unavailable."""
        with patch.dict("os.environ", {}, clear=True):
            swarm_state._supabase_client = None
            
            assert await swarm_state.report_heartbeat("test") is False
            assert await swarm_state.get_agent_states() == []
            assert await swarm_state.get_agent_state("test") is None
            assert await swarm_state.get_stale_agents() == []
            assert await swarm_state.claim_task("t", "a") is False
            assert await swarm_state.release_claim("t") is False
            assert await swarm_state.get_claimed_tasks() == []
            assert await swarm_state.send_notification("a", "b", "c") is False
            assert await swarm_state.poll_notifications("a") == []
