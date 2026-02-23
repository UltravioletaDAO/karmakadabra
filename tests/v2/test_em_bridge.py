"""
Tests for EM Bridge Bot — IRC-to-Execution Market Bridge

Tests command parsing, response formatting, rate limiting,
nick resolution, and notification generation.
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys

# Add parent paths so imports work
_kk_root = Path(__file__).parent.parent
sys.path.insert(0, str(_kk_root / "irc"))
sys.path.insert(0, str(_kk_root / "services"))
sys.path.insert(0, str(_kk_root / "lib"))

from em_bridge_bot import (
    COMMANDS,
    MAX_MSG_LEN,
    RATE_LIMIT_COMMANDS,
    RATE_LIMIT_WINDOW,
    TaskNotifier,
    _extract_error,
    _nick_to_agent,
    _rate_buckets,
    _split_message,
    check_rate_limit,
    handle_apply,
    handle_approve,
    handle_cancel,
    handle_help,
    handle_publish,
    handle_reject,
    handle_submit,
    handle_task,
    handle_tasks,
    load_identities,
    match_short_id,
    parse_command,
    rate_limit_wait,
    resolve_nick,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_state():
    """Reset global state between tests."""
    _nick_to_agent.clear()
    _rate_buckets.clear()
    yield
    _nick_to_agent.clear()
    _rate_buckets.clear()


@pytest.fixture
def sample_identities(tmp_path):
    """Create a sample identities.json file."""
    data = {
        "version": "1.0",
        "agents": [
            {
                "address": "0xE66C0A519F4B4Bef94FC45447FDba5bF381cDD48",
                "name": "kk-coordinator",
                "index": 0,
                "type": "system",
                "executor_id": "b210bb0b-da62-4613-a0f5-2dee04a4f2f8",
                "registrations": {
                    "base": {"agent_id": 18775, "status": "success"}
                },
            },
            {
                "address": "0x3aebb73a33377F0d6FC2195F83559635aDeE8408",
                "name": "kk-juanjumagalp",
                "index": 6,
                "type": "user",
                "executor_id": "44ccf13e-61b1-40d5-9a0c-456f8a5dd9e8",
                "registrations": {
                    "base": {"agent_id": 18896, "status": "success"}
                },
            },
        ],
    }
    path = tmp_path / "identities.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def loaded_identities(sample_identities):
    """Load sample identities into global state."""
    load_identities(sample_identities)
    return sample_identities


@pytest.fixture
def mock_em_client():
    """Create a mock EMClient."""
    client = AsyncMock()
    client.publish_task = AsyncMock(
        return_value={"id": "abc12345-6789-0123-4567-890abcdef012", "status": "published"}
    )
    client.browse_tasks = AsyncMock(
        return_value=[
            {
                "id": "task-0001-0000-0000-000000000001",
                "title": "Verify store hours",
                "status": "published",
                "bounty_usd": 0.10,
                "category": "physical_presence",
                "payment_network": "base",
            },
            {
                "id": "task-0002-0000-0000-000000000002",
                "title": "Audit smart contract",
                "status": "published",
                "bounty_usd": 0.15,
                "category": "knowledge_access",
                "payment_network": "polygon",
            },
        ]
    )
    client.get_task = AsyncMock(
        return_value={
            "id": "abc12345-6789-0123-4567-890abcdef012",
            "title": "Verify store hours",
            "status": "published",
            "bounty_usd": 0.10,
            "category": "physical_presence",
            "payment_network": "base",
            "instructions": "Go to the store and check the opening hours.",
        }
    )
    client.apply_to_task = AsyncMock(return_value={"success": True})
    client.submit_evidence = AsyncMock(return_value={"success": True})
    client.approve_submission = AsyncMock(return_value={"success": True})
    client.reject_submission = AsyncMock(return_value={"success": True})
    client.cancel_task = AsyncMock(return_value={"success": True})
    return client


# ---------------------------------------------------------------------------
# Command parsing tests
# ---------------------------------------------------------------------------


class TestParseCommand:
    def test_em_prefix(self):
        assert parse_command("!em help") == ("help", "")

    def test_em_with_args(self):
        assert parse_command("!em tasks published") == ("tasks", "published")

    def test_em_publish_full(self):
        cmd, args = parse_command("!em publish Title | Instructions | 0.10 base USDC")
        assert cmd == "publish"
        assert "Title | Instructions | 0.10 base USDC" in args

    def test_bare_em(self):
        assert parse_command("!em") == ("help", "")

    def test_not_em_command(self):
        assert parse_command("hello world") == ("", "")

    def test_other_command(self):
        assert parse_command("!ab help") == ("", "")

    def test_case_insensitive(self):
        assert parse_command("!EM HELP") == ("help", "")

    def test_extra_whitespace(self):
        assert parse_command("  !em   tasks   published  ") == ("tasks", "published")

    def test_apply_with_message(self):
        cmd, args = parse_command("!em apply abc12345 I can do this task")
        assert cmd == "apply"
        assert args == "abc12345 I can do this task"


# ---------------------------------------------------------------------------
# Identity resolution tests
# ---------------------------------------------------------------------------


class TestIdentities:
    def test_load_identities(self, sample_identities):
        load_identities(sample_identities)
        assert len(_nick_to_agent) == 2
        assert "kk-coordinator" in _nick_to_agent
        assert "kk-juanjumagalp" in _nick_to_agent

    def test_resolve_known_nick(self, loaded_identities):
        agent = resolve_nick("kk-coordinator")
        assert agent is not None
        assert agent["wallet"] == "0xE66C0A519F4B4Bef94FC45447FDba5bF381cDD48"
        assert agent["executor_id"] == "b210bb0b-da62-4613-a0f5-2dee04a4f2f8"
        assert agent["agent_id"] == 18775

    def test_resolve_unknown_nick(self, loaded_identities):
        assert resolve_nick("unknown-nick") is None

    def test_load_missing_file(self, tmp_path):
        load_identities(tmp_path / "nonexistent.json")
        assert len(_nick_to_agent) == 0


# ---------------------------------------------------------------------------
# Rate limiting tests
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_under_limit(self):
        for _ in range(RATE_LIMIT_COMMANDS):
            assert check_rate_limit("user1") is True

    def test_over_limit(self):
        for _ in range(RATE_LIMIT_COMMANDS):
            check_rate_limit("user1")
        assert check_rate_limit("user1") is False

    def test_separate_nicks(self):
        for _ in range(RATE_LIMIT_COMMANDS):
            check_rate_limit("user1")
        # Different nick should not be affected
        assert check_rate_limit("user2") is True

    def test_window_expiry(self):
        # Fill up the bucket
        for _ in range(RATE_LIMIT_COMMANDS):
            check_rate_limit("user1")
        assert check_rate_limit("user1") is False

        # Expire all entries
        _rate_buckets["user1"] = [time.time() - RATE_LIMIT_WINDOW - 1] * RATE_LIMIT_COMMANDS
        assert check_rate_limit("user1") is True

    def test_rate_limit_wait(self):
        for _ in range(RATE_LIMIT_COMMANDS):
            check_rate_limit("user1")
        wait = rate_limit_wait("user1")
        assert 0 < wait <= RATE_LIMIT_WINDOW + 1

    def test_rate_limit_wait_empty(self):
        assert rate_limit_wait("nobody") == 0


# ---------------------------------------------------------------------------
# Short ID matching tests
# ---------------------------------------------------------------------------


class TestShortId:
    def test_unique_match(self):
        candidates = ["abc12345-full-uuid", "def67890-full-uuid"]
        assert match_short_id("abc1", candidates) == "abc12345-full-uuid"

    def test_ambiguous_match(self):
        candidates = ["abc12345-uuid1", "abc12346-uuid2"]
        assert match_short_id("abc1234", candidates) is None

    def test_no_match(self):
        candidates = ["abc12345-full-uuid"]
        assert match_short_id("xyz", candidates) is None

    def test_case_insensitive(self):
        candidates = ["ABC12345-full-uuid"]
        assert match_short_id("abc1", candidates) == "ABC12345-full-uuid"


# ---------------------------------------------------------------------------
# Command handler tests
# ---------------------------------------------------------------------------


class TestHandlePublish:
    @pytest.mark.asyncio
    async def test_publish_success(self, loaded_identities, mock_em_client):
        result = await handle_publish(
            mock_em_client,
            "kk-coordinator",
            "Test Task | Do something useful | 0.10",
        )
        assert "[OK]" in result
        assert "Test Task" in result
        assert "$0.10" in result
        mock_em_client.publish_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_unknown_nick(self, loaded_identities, mock_em_client):
        result = await handle_publish(mock_em_client, "unknown", "T | I | 0.10")
        assert "[ERR]" in result
        assert "Unknown nick" in result

    @pytest.mark.asyncio
    async def test_publish_bad_syntax(self, loaded_identities, mock_em_client):
        result = await handle_publish(mock_em_client, "kk-coordinator", "no pipes here")
        assert "[ERR]" in result
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_publish_bounty_too_high(self, loaded_identities, mock_em_client):
        result = await handle_publish(
            mock_em_client, "kk-coordinator", "T | I | 1.00"
        )
        assert "[ERR]" in result
        assert "too high" in result

    @pytest.mark.asyncio
    async def test_publish_with_network(self, loaded_identities, mock_em_client):
        result = await handle_publish(
            mock_em_client,
            "kk-coordinator",
            "Task | Instructions | 0.10 polygon",
        )
        assert "[OK]" in result
        call_kwargs = mock_em_client.publish_task.call_args
        assert call_kwargs.kwargs.get("payment_network") == "polygon" or (
            call_kwargs[1].get("payment_network") == "polygon"
            if call_kwargs[1]
            else True
        )

    @pytest.mark.asyncio
    async def test_publish_invalid_bounty(self, loaded_identities, mock_em_client):
        result = await handle_publish(
            mock_em_client, "kk-coordinator", "T | I | abc"
        )
        assert "[ERR]" in result
        assert "Invalid bounty" in result


class TestHandleTasks:
    @pytest.mark.asyncio
    async def test_tasks_list(self, mock_em_client):
        result = await handle_tasks(mock_em_client, "anyone", "")
        assert "[TASKS]" in result
        assert "Verify store" in result

    @pytest.mark.asyncio
    async def test_tasks_empty(self, mock_em_client):
        mock_em_client.browse_tasks.return_value = []
        result = await handle_tasks(mock_em_client, "anyone", "")
        assert "No published tasks" in result

    @pytest.mark.asyncio
    async def test_tasks_with_status(self, mock_em_client):
        await handle_tasks(mock_em_client, "anyone", "completed")
        mock_em_client.browse_tasks.assert_awaited_with(
            status="completed", category=None, limit=5
        )


class TestHandleTask:
    @pytest.mark.asyncio
    async def test_task_detail(self, mock_em_client):
        result = await handle_task(mock_em_client, "anyone", "abc12345")
        assert "[TASK]" in result
        assert "Verify store" in result
        assert "$0.10" in result

    @pytest.mark.asyncio
    async def test_task_no_id(self, mock_em_client):
        result = await handle_task(mock_em_client, "anyone", "")
        assert "[ERR]" in result
        assert "Usage" in result


class TestHandleApply:
    @pytest.mark.asyncio
    async def test_apply_success(self, loaded_identities, mock_em_client):
        result = await handle_apply(
            mock_em_client, "kk-juanjumagalp", "abc12345 I'm available"
        )
        assert "[OK]" in result
        assert "applied" in result

    @pytest.mark.asyncio
    async def test_apply_unknown_nick(self, loaded_identities, mock_em_client):
        result = await handle_apply(mock_em_client, "unknown", "abc12345")
        assert "[ERR]" in result

    @pytest.mark.asyncio
    async def test_apply_no_task_id(self, loaded_identities, mock_em_client):
        result = await handle_apply(mock_em_client, "kk-juanjumagalp", "")
        assert "[ERR]" in result
        assert "Usage" in result


class TestHandleSubmit:
    @pytest.mark.asyncio
    async def test_submit_success(self, loaded_identities, mock_em_client):
        result = await handle_submit(
            mock_em_client, "kk-juanjumagalp", "abc12345 https://example.com/photo.jpg"
        )
        assert "[OK]" in result
        assert "Evidence submitted" in result

    @pytest.mark.asyncio
    async def test_submit_missing_url(self, loaded_identities, mock_em_client):
        result = await handle_submit(mock_em_client, "kk-juanjumagalp", "abc12345")
        assert "[ERR]" in result
        assert "Usage" in result


class TestHandleApproveReject:
    @pytest.mark.asyncio
    async def test_approve(self, mock_em_client):
        result = await handle_approve(mock_em_client, "kk-coordinator", "sub123")
        assert "[OK]" in result
        assert "approved" in result

    @pytest.mark.asyncio
    async def test_approve_with_rating(self, mock_em_client):
        result = await handle_approve(mock_em_client, "kk-coordinator", "sub123 95")
        assert "[OK]" in result
        mock_em_client.approve_submission.assert_awaited_with("sub123", rating_score=95)

    @pytest.mark.asyncio
    async def test_reject(self, mock_em_client):
        result = await handle_reject(
            mock_em_client, "kk-coordinator", "sub123 Quality too low"
        )
        assert "[OK]" in result
        assert "rejected" in result

    @pytest.mark.asyncio
    async def test_reject_default_reason(self, mock_em_client):
        result = await handle_reject(mock_em_client, "kk-coordinator", "sub123")
        assert "[OK]" in result
        mock_em_client.reject_submission.assert_awaited_with(
            "sub123", notes="Does not meet requirements."
        )


class TestHandleCancel:
    @pytest.mark.asyncio
    async def test_cancel(self, mock_em_client):
        result = await handle_cancel(mock_em_client, "kk-coordinator", "abc12345")
        assert "[OK]" in result
        assert "cancelled" in result

    @pytest.mark.asyncio
    async def test_cancel_no_id(self, mock_em_client):
        result = await handle_cancel(mock_em_client, "kk-coordinator", "")
        assert "[ERR]" in result


class TestHandleHelp:
    @pytest.mark.asyncio
    async def test_help(self, mock_em_client):
        result = await handle_help(mock_em_client, "anyone", "")
        assert "!em publish" in result
        assert "!em tasks" in result
        assert "!em apply" in result
        assert "!em help" in result


# ---------------------------------------------------------------------------
# Notification poller tests
# ---------------------------------------------------------------------------


class TestTaskNotifier:
    @pytest.mark.asyncio
    async def test_first_poll_no_notifications(self, mock_em_client):
        """First poll should populate seen set but NOT generate notifications."""
        notifier = TaskNotifier(mock_em_client)
        notifications = await notifier.poll()
        assert notifications == []

    @pytest.mark.asyncio
    async def test_second_poll_new_task(self, mock_em_client):
        """Second poll should notify about new tasks."""
        notifier = TaskNotifier(mock_em_client)

        # First poll — populate
        await notifier.poll()

        # Add a new task
        mock_em_client.browse_tasks.return_value = [
            {
                "id": "new-task-0000-0000-000000000001",
                "title": "Brand new task",
                "status": "published",
                "bounty_usd": 0.25,
                "category": "simple_action",
                "payment_network": "base",
            },
        ]

        notifications = await notifier.poll()
        assert len(notifications) == 1
        assert "[TASK-NEW]" in notifications[0]
        assert "Brand new task" in notifications[0]
        assert "$0.25" in notifications[0]

    @pytest.mark.asyncio
    async def test_no_duplicate_notifications(self, mock_em_client):
        """Same task should not generate duplicate notifications."""
        notifier = TaskNotifier(mock_em_client)

        # First poll
        await notifier.poll()

        # Second poll — same tasks
        notifications = await notifier.poll()
        assert notifications == []

    @pytest.mark.asyncio
    async def test_poll_handles_api_error(self, mock_em_client):
        """Poll should gracefully handle API errors."""
        mock_em_client.browse_tasks.side_effect = Exception("Connection failed")
        notifier = TaskNotifier(mock_em_client)
        notifications = await notifier.poll()
        assert notifications == []


# ---------------------------------------------------------------------------
# Message splitting tests
# ---------------------------------------------------------------------------


class TestSplitMessage:
    def test_short_message(self):
        assert _split_message("hello", 400) == ["hello"]

    def test_exact_limit(self):
        msg = "a" * 400
        assert _split_message(msg, 400) == [msg]

    def test_split_long_message(self):
        msg = "a" * 800
        chunks = _split_message(msg, 400)
        assert len(chunks) == 2
        assert all(len(c) <= 400 for c in chunks)
        assert "".join(chunks) == msg


# ---------------------------------------------------------------------------
# Error extraction tests
# ---------------------------------------------------------------------------


class TestExtractError:
    def test_simple_exception(self):
        assert _extract_error(Exception("Something failed")) == "Something failed"

    def test_httpx_exception_with_json(self):
        """Extract detail from httpx response."""
        exc = Exception("HTTP error")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"detail": "Task not found"}
        exc.response = mock_resp
        assert _extract_error(exc) == "Task not found"

    def test_truncation(self):
        long_msg = "x" * 500
        result = _extract_error(Exception(long_msg))
        assert len(result) <= 200


# ---------------------------------------------------------------------------
# Command registration tests
# ---------------------------------------------------------------------------


class TestCommandRegistration:
    def test_all_commands_registered(self):
        expected = {
            "publish", "tasks", "task", "apply", "submit",
            "approve", "reject", "cancel", "help",
        }
        assert set(COMMANDS.keys()) == expected

    def test_all_handlers_are_callable(self):
        for name, handler in COMMANDS.items():
            assert callable(handler), f"Handler for '{name}' is not callable"
