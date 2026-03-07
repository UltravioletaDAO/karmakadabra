"""
Tests for services/karma_hello_scheduler.py — Background Scheduler

Covers:
  - KarmaHelloScheduler construction
  - Schedule constants (intervals)
  - _load_client (creates agent + EMClient)
  - run_once (calls collect, publish, fulfill)
  - run_daemon (launches concurrent tasks)
  - stop (cancels all tasks, sets _running=False)
  - Error handling in each cycle
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))

from services.karma_hello_scheduler import (
    COLLECT_INTERVAL,
    FULFILL_INTERVAL,
    KarmaHelloScheduler,
    PUBLISH_INTERVAL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scheduler(tmp_path):
    return KarmaHelloScheduler(
        data_dir=tmp_path / "data",
        workspace_dir=tmp_path / "workspace",
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_collect_interval(self):
        assert COLLECT_INTERVAL == 30 * 60  # 30 minutes

    def test_publish_interval(self):
        assert PUBLISH_INTERVAL == 2 * 3600  # 2 hours

    def test_fulfill_interval(self):
        assert FULFILL_INTERVAL == 15 * 60  # 15 minutes


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_stores_config(self, tmp_path):
        sched = KarmaHelloScheduler(
            data_dir=tmp_path / "data",
            workspace_dir=tmp_path / "ws",
            dry_run=True,
        )
        assert sched.dry_run is True
        assert sched._running is True
        assert sched._tasks == []

    def test_default_not_dry_run(self, tmp_path):
        sched = KarmaHelloScheduler(
            data_dir=tmp_path / "data",
            workspace_dir=tmp_path / "ws",
        )
        assert sched.dry_run is False


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


class TestStop:
    def test_stop_sets_running_false(self, scheduler):
        assert scheduler._running is True
        scheduler.stop()
        assert scheduler._running is False

    def test_stop_cancels_tasks(self, scheduler):
        mock_task = MagicMock()
        scheduler._tasks = [mock_task]
        scheduler.stop()
        mock_task.cancel.assert_called_once()


# ---------------------------------------------------------------------------
# run_once
# ---------------------------------------------------------------------------


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_calls_all_cycles(self, scheduler):
        mock_client = MagicMock()
        mock_client.close = AsyncMock()

        with patch("services.karma_hello_scheduler.collect_irc_logs") as mock_collect, \
             patch("services.karma_hello_scheduler.publish_offerings", new_callable=AsyncMock) as mock_publish, \
             patch("services.karma_hello_scheduler.fulfill_purchases", new_callable=AsyncMock) as mock_fulfill, \
             patch.object(scheduler, "_load_client") as mock_load:
            mock_collect.return_value = {"new_messages": 10}
            mock_publish.return_value = {"published": 2, "skipped": 1}
            mock_fulfill.return_value = {"approved": 0, "reviewed": 0}
            mock_load.return_value = (MagicMock(), mock_client)

            await scheduler.run_once()

            mock_collect.assert_called_once()
            mock_publish.assert_called_once()
            mock_fulfill.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_once_handles_collect_error(self, scheduler):
        mock_client = MagicMock()
        mock_client.close = AsyncMock()

        with patch("services.karma_hello_scheduler.collect_irc_logs", side_effect=Exception("collect failed")), \
             patch("services.karma_hello_scheduler.publish_offerings", new_callable=AsyncMock) as mock_publish, \
             patch("services.karma_hello_scheduler.fulfill_purchases", new_callable=AsyncMock) as mock_fulfill, \
             patch.object(scheduler, "_load_client") as mock_load:
            mock_publish.return_value = {"published": 0, "skipped": 0}
            mock_fulfill.return_value = {"approved": 0, "reviewed": 0}
            mock_load.return_value = (MagicMock(), mock_client)

            await scheduler.run_once()  # Should not raise
            mock_publish.assert_called_once()  # Still runs publish

    @pytest.mark.asyncio
    async def test_run_once_handles_publish_error(self, scheduler):
        mock_client = MagicMock()
        mock_client.close = AsyncMock()

        with patch("services.karma_hello_scheduler.collect_irc_logs") as mock_collect, \
             patch("services.karma_hello_scheduler.publish_offerings", new_callable=AsyncMock, side_effect=Exception("publish failed")), \
             patch("services.karma_hello_scheduler.fulfill_purchases", new_callable=AsyncMock) as mock_fulfill, \
             patch.object(scheduler, "_load_client") as mock_load:
            mock_collect.return_value = {"new_messages": 0}
            mock_load.return_value = (MagicMock(), mock_client)

            await scheduler.run_once()  # Should not raise
            mock_client.close.assert_called_once()  # Client still cleaned up
