"""
Tests for cron/shutdown_handler.py — KK V2 Graceful Shutdown

Tests cover:
  - ShutdownHandler initialization
  - Signal registration
  - Final state persistence (WORKING.md)
  - Offline status reporting to swarm
  - Daily note logging on shutdown
  - Standalone mode lifecycle
  - Wrapper mode (child process management)
  - Graceful degradation on failures
"""

from __future__ import annotations

import asyncio
import json
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cron.shutdown_handler import ShutdownHandler


# ═══════════════════════════════════════════════════════════════════
# Initialization
# ═══════════════════════════════════════════════════════════════════


class TestShutdownHandlerInit:
    """Tests for ShutdownHandler initialization."""

    def test_basic_init(self, tmp_path):
        ws = tmp_path / "kk-test-agent"
        ws.mkdir()
        handler = ShutdownHandler(ws)
        assert handler.agent_name == "kk-test-agent"
        assert handler.workspace_dir == ws
        assert handler.memory_dir == ws / "memory"
        assert handler.working_path == ws / "memory" / "WORKING.md"
        assert not handler.shutdown_event.is_set()
        assert handler.shutdown_reason == "unknown"
        assert handler._child_process is None

    def test_paths_derived_from_workspace(self, tmp_path):
        ws = tmp_path / "kk-coordinator"
        ws.mkdir()
        handler = ShutdownHandler(ws)
        assert handler.agent_name == "kk-coordinator"
        assert handler.working_path.parent.name == "memory"


# ═══════════════════════════════════════════════════════════════════
# Final State Persistence
# ═══════════════════════════════════════════════════════════════════


class TestWriteFinalState:
    """Tests for writing shutdown state to WORKING.md."""

    @pytest.fixture
    def handler_with_memory(self, tmp_path):
        ws = tmp_path / "kk-agent"
        ws.mkdir()
        memory_dir = ws / "memory"
        memory_dir.mkdir()
        working = memory_dir / "WORKING.md"
        working.write_text(
            "# WORKING.md\n\n## Status\nidle\n\n## Budget\n"
            "daily_budget: 1.00\ndaily_spent: 0.00\n",
            encoding="utf-8",
        )
        handler = ShutdownHandler(ws)
        handler.shutdown_reason = "received SIGTERM"
        return handler

    @pytest.mark.asyncio
    async def test_writes_shutdown_to_working(self, handler_with_memory):
        """Should update WORKING.md with shutdown state."""
        with patch("cron.shutdown_handler.parse_working_md") as mock_parse, \
             patch("cron.shutdown_handler.update_heartbeat") as mock_update, \
             patch("cron.shutdown_handler.write_working_md") as mock_write:

            mock_state = MagicMock()
            mock_parse.return_value = mock_state

            await handler_with_memory.write_final_state()

            mock_parse.assert_called_once()
            mock_update.assert_called_once_with(
                mock_state,
                action="shutdown",
                result="received SIGTERM",
            )
            mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_missing_working_md(self, tmp_path):
        """Should handle missing WORKING.md gracefully."""
        ws = tmp_path / "kk-no-working"
        ws.mkdir()
        handler = ShutdownHandler(ws)

        with patch("cron.shutdown_handler.parse_working_md") as mock_parse:
            mock_parse.side_effect = FileNotFoundError("No such file")
            # Should not raise
            await handler.write_final_state()


# ═══════════════════════════════════════════════════════════════════
# Offline Reporting
# ═══════════════════════════════════════════════════════════════════


class TestReportOffline:
    """Tests for reporting offline status to swarm state."""

    @pytest.fixture
    def handler(self, tmp_path):
        ws = tmp_path / "kk-agent"
        ws.mkdir()
        h = ShutdownHandler(ws)
        h.shutdown_reason = "received SIGINT"
        return h

    @pytest.mark.asyncio
    async def test_reports_offline_success(self, handler):
        """Should report offline status to swarm state."""
        with patch("cron.shutdown_handler.report_heartbeat", new_callable=AsyncMock) as mock_rh:
            mock_rh.return_value = True
            await handler.report_offline()
            mock_rh.assert_called_once_with(
                agent_name="kk-agent",
                status="offline",
                notes="shutdown: received SIGINT",
            )

    @pytest.mark.asyncio
    async def test_handles_report_failure(self, handler):
        """Should handle report failure gracefully (non-fatal)."""
        with patch("cron.shutdown_handler.report_heartbeat", new_callable=AsyncMock) as mock_rh:
            mock_rh.side_effect = ConnectionError("IRC down")
            # Should not raise
            await handler.report_offline()

    @pytest.mark.asyncio
    async def test_handles_report_false_return(self, handler):
        """Should handle False return from report_heartbeat."""
        with patch("cron.shutdown_handler.report_heartbeat", new_callable=AsyncMock) as mock_rh:
            mock_rh.return_value = False
            await handler.report_offline()


# ═══════════════════════════════════════════════════════════════════
# Shutdown Note
# ═══════════════════════════════════════════════════════════════════


class TestSaveShutdownNote:
    """Tests for saving shutdown notes to daily log."""

    @pytest.fixture
    def handler(self, tmp_path):
        ws = tmp_path / "kk-agent"
        ws.mkdir()
        (ws / "memory").mkdir()
        h = ShutdownHandler(ws)
        h.shutdown_reason = "maintenance"
        return h

    @pytest.mark.asyncio
    async def test_saves_daily_note(self, handler):
        """Should save shutdown event to daily notes."""
        with patch("cron.shutdown_handler.append_daily_note") as mock_adn:
            await handler.save_shutdown_note()
            mock_adn.assert_called_once_with(
                handler.memory_dir,
                action="shutdown",
                result="maintenance",
            )

    @pytest.mark.asyncio
    async def test_handles_note_save_failure(self, handler):
        """Should handle daily note save failure gracefully."""
        with patch("cron.shutdown_handler.append_daily_note") as mock_adn:
            mock_adn.side_effect = PermissionError("read-only filesystem")
            await handler.save_shutdown_note()


# ═══════════════════════════════════════════════════════════════════
# Full Shutdown Sequence
# ═══════════════════════════════════════════════════════════════════


class TestFullShutdown:
    """Tests for the complete shutdown sequence."""

    @pytest.fixture
    def handler(self, tmp_path):
        ws = tmp_path / "kk-agent"
        ws.mkdir()
        (ws / "memory").mkdir()
        h = ShutdownHandler(ws)
        h.shutdown_reason = "test shutdown"
        return h

    @pytest.mark.asyncio
    async def test_executes_full_sequence(self, handler):
        """Shutdown should call all steps in order."""
        with patch.object(handler, "write_final_state", new_callable=AsyncMock) as mock_write, \
             patch.object(handler, "report_offline", new_callable=AsyncMock) as mock_report, \
             patch.object(handler, "save_shutdown_note", new_callable=AsyncMock) as mock_note:

            await handler.shutdown()
            mock_write.assert_called_once()
            mock_report.assert_called_once()
            mock_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminates_child_process(self, handler):
        """Should terminate child process if running."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Still running
        mock_proc.pid = 12345
        handler._child_process = mock_proc

        with patch.object(handler, "write_final_state", new_callable=AsyncMock), \
             patch.object(handler, "report_offline", new_callable=AsyncMock), \
             patch.object(handler, "save_shutdown_note", new_callable=AsyncMock):

            await handler.shutdown()
            mock_proc.terminate.assert_called_once()
            mock_proc.wait.assert_called_once_with(timeout=10)

    @pytest.mark.asyncio
    async def test_kills_child_on_timeout(self, handler):
        """Should kill child if it doesn't terminate within timeout."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 12345
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=10)
        handler._child_process = mock_proc

        with patch.object(handler, "write_final_state", new_callable=AsyncMock), \
             patch.object(handler, "report_offline", new_callable=AsyncMock), \
             patch.object(handler, "save_shutdown_note", new_callable=AsyncMock):

            await handler.shutdown()
            mock_proc.terminate.assert_called_once()
            mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_already_exited_child(self, handler):
        """Should skip termination if child already exited."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # Already exited
        handler._child_process = mock_proc

        with patch.object(handler, "write_final_state", new_callable=AsyncMock), \
             patch.object(handler, "report_offline", new_callable=AsyncMock), \
             patch.object(handler, "save_shutdown_note", new_callable=AsyncMock):

            await handler.shutdown()
            mock_proc.terminate.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# Signal Registration
# ═══════════════════════════════════════════════════════════════════


class TestSignalRegistration:
    """Tests for signal handler registration."""

    @pytest.mark.asyncio
    async def test_register_signals(self, tmp_path):
        """Should register SIGINT (and SIGTERM on Unix)."""
        ws = tmp_path / "kk-agent"
        ws.mkdir()
        handler = ShutdownHandler(ws)

        with patch("signal.signal") as mock_signal:
            handler.register_signals()
            # Should register at least SIGINT
            calls = [c[0][0] for c in mock_signal.call_args_list]
            assert signal.SIGINT in calls


# ═══════════════════════════════════════════════════════════════════
# Wrapper Mode
# ═══════════════════════════════════════════════════════════════════


class TestWrapperMode:
    """Tests for wrapper mode (managing a child process)."""

    @pytest.fixture
    def handler(self, tmp_path):
        ws = tmp_path / "kk-agent"
        ws.mkdir()
        (ws / "memory").mkdir()
        return ShutdownHandler(ws)

    @pytest.mark.asyncio
    async def test_child_exit_triggers_shutdown(self, handler):
        """When child process exits, handler should run shutdown."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # Immediately exited

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(handler, "register_signals"), \
             patch.object(handler, "shutdown", new_callable=AsyncMock) as mock_shutdown:

            exit_code = await handler.run_wrapper(["echo", "hello"])
            assert exit_code == 0
            mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_child_nonzero_exit_code(self, handler):
        """Non-zero exit from child should be propagated."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # Exit with error

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(handler, "register_signals"), \
             patch.object(handler, "shutdown", new_callable=AsyncMock):

            exit_code = await handler.run_wrapper(["false"])
            assert exit_code == 1
            assert "child exited with code 1" in handler.shutdown_reason

    @pytest.mark.asyncio
    async def test_shutdown_signal_during_child(self, handler):
        """Shutdown signal should trigger shutdown while child runs."""
        # Simulate child that never exits on its own
        call_count = 0

        def poll_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                # After 2 polls, trigger shutdown
                handler.shutdown_event.set()
            return None

        mock_proc = MagicMock()
        mock_proc.poll.side_effect = poll_side_effect

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(handler, "register_signals"), \
             patch.object(handler, "shutdown", new_callable=AsyncMock) as mock_shutdown:

            exit_code = await handler.run_wrapper(["sleep", "999"])
            assert exit_code == 0
            mock_shutdown.assert_called_once()
