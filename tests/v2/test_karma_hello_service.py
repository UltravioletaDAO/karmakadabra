"""
Karma Kadabra V2 — Phase 9.4: Karma Hello Service Tests

Unit tests for the three Karma Hello service cycles:
  - Collect: IRC log aggregation
  - Publish: EM task creation from PRODUCTS catalog
  - Fulfill: Auto-approval of data delivery submissions

All EM API calls are mocked via a FakeEMClient to avoid network access.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the services package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.karma_hello_service import (
    MAX_DAILY_SPEND_USD,
    collect_all_logs,
    fulfill_purchases,
    publish_offerings,
    run_service,
)
from services.karma_hello_seller import PRODUCTS
from services.em_client import AgentContext, EMClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with sample IRC logs."""
    irc_dir = tmp_path / "irc-logs"
    irc_dir.mkdir()

    # Write two daily log files
    entries_day1 = [
        {"ts": "2026-02-18T10:00:00+00:00", "sender": "alice", "channel": "#Agents", "content": "hello world"},
        {"ts": "2026-02-18T10:05:00+00:00", "sender": "bob", "channel": "#Agents", "content": "hey alice"},
    ]
    entries_day2 = [
        {"ts": "2026-02-19T08:00:00+00:00", "sender": "carol", "channel": "#Agents", "content": "good morning"},
    ]

    day1_file = irc_dir / "2026-02-18.json"
    day1_file.write_text(
        "\n".join(json.dumps(e) for e in entries_day1),
        encoding="utf-8",
    )

    day2_file = irc_dir / "2026-02-19.json"
    day2_file.write_text(
        json.dumps(entries_day2[0]),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def agent() -> AgentContext:
    """Create a test agent context."""
    return AgentContext(
        name="kk-karma-hello",
        wallet_address="0xTEST_WALLET",
        workspace_dir=Path("/tmp/kk-test"),
        daily_budget_usd=2.0,
        daily_spent_usd=0.0,
    )


@pytest.fixture
def mock_client(agent: AgentContext) -> EMClient:
    """Create an EMClient with mocked HTTP methods."""
    client = EMClient.__new__(EMClient)
    client.agent = agent
    client._client = MagicMock()
    # Mock all async methods
    client.health = AsyncMock(return_value={"status": "ok"})
    client.publish_task = AsyncMock(return_value={"task": {"id": "task-001"}})
    client.list_tasks = AsyncMock(return_value=[])
    client.get_submissions = AsyncMock(return_value=[])
    client.approve_submission = AsyncMock(return_value={"status": "approved"})
    client.close = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Collect cycle tests
# ---------------------------------------------------------------------------


def test_collect_finds_and_aggregates_logs(data_dir: Path) -> None:
    """Collect cycle discovers IRC log files and aggregates messages."""
    result = collect_all_logs(data_dir)

    assert result["files_found"] == 2
    assert result["new_messages"] == 3
    assert result["total_messages"] == 3
    assert "2026-02-18" in result["dates"]
    assert "2026-02-19" in result["dates"]

    # Verify aggregated file was written
    agg_file = data_dir / "aggregated.json"
    assert agg_file.exists()

    agg = json.loads(agg_file.read_text(encoding="utf-8"))
    assert len(agg["messages"]) == 3
    assert agg["stats"]["total_messages"] == 3
    assert agg["stats"]["date_count"] == 2


def test_collect_skips_duplicate_messages(data_dir: Path) -> None:
    """Running collect twice does not duplicate messages."""
    # First run
    collect_all_logs(data_dir)

    # Second run — same logs, no new messages
    result = collect_all_logs(data_dir)
    assert result["new_messages"] == 0
    assert result["total_messages"] == 3

    agg = json.loads((data_dir / "aggregated.json").read_text(encoding="utf-8"))
    assert len(agg["messages"]) == 3


def test_collect_handles_empty_directory(tmp_path: Path) -> None:
    """Collect gracefully handles missing irc-logs/ directory."""
    result = collect_all_logs(tmp_path)
    assert result["files_found"] == 0
    assert result["new_messages"] == 0


def test_collect_dry_run_does_not_write(data_dir: Path) -> None:
    """Dry run collects stats but does not write aggregated.json."""
    result = collect_all_logs(data_dir, dry_run=True)
    assert result["new_messages"] == 3
    assert not (data_dir / "aggregated.json").exists()


# ---------------------------------------------------------------------------
# Publish cycle tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_creates_correct_payloads(
    mock_client: EMClient,
    data_dir: Path,
) -> None:
    """Publish cycle creates EM tasks from PRODUCTS catalog with correct data."""
    # First aggregate some data
    collect_all_logs(data_dir)

    result = await publish_offerings(mock_client, data_dir)

    assert result["published"] == len(PRODUCTS)
    assert result["skipped"] == 0
    assert mock_client.publish_task.call_count == len(PRODUCTS)

    # Verify first call has correct structure
    first_call = mock_client.publish_task.call_args_list[0]
    assert "[KK Data]" in first_call.kwargs.get("title", first_call[1].get("title", ""))


@pytest.mark.asyncio
async def test_publish_respects_budget_limit(
    mock_client: EMClient,
    data_dir: Path,
) -> None:
    """Publish cycle skips products when daily budget is exhausted."""
    collect_all_logs(data_dir)

    # Exhaust the budget
    mock_client.agent.daily_spent_usd = MAX_DAILY_SPEND_USD

    result = await publish_offerings(mock_client, data_dir)

    assert result["published"] == 0
    assert result["skipped"] == len(PRODUCTS)
    assert mock_client.publish_task.call_count == 0


@pytest.mark.asyncio
async def test_publish_skips_when_no_data(
    mock_client: EMClient,
    tmp_path: Path,
) -> None:
    """Publish cycle skips all products when no aggregated data exists."""
    result = await publish_offerings(mock_client, tmp_path)

    assert result["skipped"] == len(PRODUCTS)
    assert result["published"] == 0


# ---------------------------------------------------------------------------
# Fulfill cycle tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fulfill_auto_approves_data_deliveries(
    mock_client: EMClient,
) -> None:
    """Fulfill cycle auto-approves submissions on [KK Data] tasks."""
    mock_client.list_tasks.return_value = [
        {"id": "task-100", "title": "[KK Data] Raw Twitch Chat Logs"},
    ]
    mock_client.get_submissions.return_value = [
        {"id": "sub-200"},
    ]

    result = await fulfill_purchases(mock_client)

    assert result["reviewed"] == 1
    assert result["approved"] == 1
    mock_client.approve_submission.assert_called_once_with(
        "sub-200", rating_score=90, notes="KK data delivery auto-approved",
    )


@pytest.mark.asyncio
async def test_fulfill_ignores_non_kk_tasks(
    mock_client: EMClient,
) -> None:
    """Fulfill cycle ignores tasks not prefixed with [KK Data]."""
    mock_client.list_tasks.return_value = [
        {"id": "task-999", "title": "Take a photo of the store"},
    ]

    result = await fulfill_purchases(mock_client)

    assert result["reviewed"] == 0
    assert result["approved"] == 0
    mock_client.get_submissions.assert_not_called()


@pytest.mark.asyncio
async def test_fulfill_dry_run_does_not_approve(
    mock_client: EMClient,
) -> None:
    """Dry run counts but does not call approve_submission."""
    mock_client.list_tasks.return_value = [
        {"id": "task-100", "title": "[KK Data] Topic Analysis"},
    ]
    mock_client.get_submissions.return_value = [
        {"id": "sub-300"},
    ]

    result = await fulfill_purchases(mock_client, dry_run=True)

    assert result["approved"] == 1
    mock_client.approve_submission.assert_not_called()


# ---------------------------------------------------------------------------
# Budget safety test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_respects_safety_cap(
    mock_client: EMClient,
    data_dir: Path,
) -> None:
    """Publish cycle enforces MAX_DAILY_SPEND_USD safety cap."""
    collect_all_logs(data_dir)

    # Set spent just under the cap — only cheapest product should fit
    mock_client.agent.daily_spent_usd = MAX_DAILY_SPEND_USD - 0.02

    result = await publish_offerings(mock_client, data_dir)

    # Only the $0.01 product fits under the $0.50 cap
    assert result["published"] == 1
    assert result["skipped"] == len(PRODUCTS) - 1
