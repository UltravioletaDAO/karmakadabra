"""
Tests for irc/em_bridge_bot.py — IRC-to-Execution Market Bridge

Tests cover:
  - Command parsing (!em <command> <args>)
  - Rate limiting (per-nick throttling)
  - Short ID resolution (UUID prefix matching)
  - Identity resolution (nick → agent mapping)
  - Command handlers (publish, tasks, apply, submit, approve, reject, cancel)
  - Message splitting (IRC 400-char limit)
  - Error extraction from exceptions
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from irc.em_bridge_bot import (
    MAX_MSG_LEN,
    RATE_LIMIT_COMMANDS,
    RATE_LIMIT_WINDOW,
    _extract_error,
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


# ═══════════════════════════════════════════════════════════════════
# Command Parsing
# ═══════════════════════════════════════════════════════════════════


class TestParseCommand:
    """Tests for IRC command parsing."""

    def test_basic_command(self):
        cmd, args = parse_command("!em tasks")
        assert cmd == "tasks"
        assert args == ""

    def test_command_with_args(self):
        cmd, args = parse_command("!em publish My Task | Do this | 0.05")
        assert cmd == "publish"
        assert args == "My Task | Do this | 0.05"

    def test_bare_em(self):
        cmd, args = parse_command("!em")
        assert cmd == "help"
        assert args == ""

    def test_not_em_command(self):
        cmd, args = parse_command("hello everyone")
        assert cmd == ""
        assert args == ""

    def test_case_insensitive(self):
        cmd, args = parse_command("!EM TASKS published")
        assert cmd == "tasks"
        assert args == "published"

    def test_with_leading_whitespace(self):
        cmd, args = parse_command("  !em tasks  ")
        assert cmd == "tasks"
        assert args == ""

    def test_complex_args(self):
        cmd, args = parse_command("!em submit abc-123 https://evidence.example.com/proof.json")
        assert cmd == "submit"
        assert "abc-123" in args
        assert "https://" in args

    def test_unknown_command_passes_through(self):
        cmd, args = parse_command("!em foobar something")
        assert cmd == "foobar"
        assert args == "something"


# ═══════════════════════════════════════════════════════════════════
# Rate Limiting
# ═══════════════════════════════════════════════════════════════════


class TestRateLimit:
    """Tests for per-nick rate limiting."""

    @pytest.fixture(autouse=True)
    def clean_buckets(self):
        """Clear rate limit state between tests."""
        import irc.em_bridge_bot as mod
        mod._rate_buckets.clear()

    def test_allows_first_command(self):
        assert check_rate_limit("test-nick") is True

    def test_allows_up_to_limit(self):
        for i in range(RATE_LIMIT_COMMANDS):
            assert check_rate_limit("nick-limit") is True

    def test_blocks_after_limit(self):
        for _ in range(RATE_LIMIT_COMMANDS):
            check_rate_limit("nick-flood")
        assert check_rate_limit("nick-flood") is False

    def test_different_nicks_independent(self):
        for _ in range(RATE_LIMIT_COMMANDS):
            check_rate_limit("nick-a")
        # nick-b should still be allowed
        assert check_rate_limit("nick-b") is True

    def test_rate_limit_wait_zero_for_new_nick(self):
        assert rate_limit_wait("new-nick") == 0

    def test_rate_limit_wait_positive_after_flood(self):
        for _ in range(RATE_LIMIT_COMMANDS):
            check_rate_limit("flood-nick")
        wait = rate_limit_wait("flood-nick")
        assert wait > 0
        assert wait <= RATE_LIMIT_WINDOW + 1


# ═══════════════════════════════════════════════════════════════════
# Short ID Resolution
# ═══════════════════════════════════════════════════════════════════


class TestMatchShortId:
    """Tests for UUID prefix matching."""

    def test_exact_match(self):
        candidates = ["abc-123-def", "xyz-789-ghi"]
        result = match_short_id("abc-123-def", candidates)
        assert result == "abc-123-def"

    def test_prefix_match(self):
        candidates = ["abc-123-def-456", "xyz-789-ghi-012"]
        result = match_short_id("abc", candidates)
        assert result == "abc-123-def-456"

    def test_ambiguous_match(self):
        candidates = ["abc-123", "abc-456"]
        result = match_short_id("abc", candidates)
        assert result is None

    def test_no_match(self):
        candidates = ["abc-123", "xyz-789"]
        result = match_short_id("qqq", candidates)
        assert result is None

    def test_case_insensitive(self):
        candidates = ["ABC-123-DEF"]
        result = match_short_id("abc", candidates)
        assert result == "ABC-123-DEF"

    def test_empty_candidates(self):
        result = match_short_id("abc", [])
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Identity Resolution
# ═══════════════════════════════════════════════════════════════════


class TestIdentityResolution:
    """Tests for nick-to-agent identity mapping."""

    @pytest.fixture(autouse=True)
    def clean_identities(self):
        """Clear identity mapping."""
        import irc.em_bridge_bot as mod
        mod._nick_to_agent.clear()

    def test_load_from_file(self, tmp_path):
        config = tmp_path / "identities.json"
        config.write_text(json.dumps({
            "agents": [
                {"name": "kk-agent-1", "address": "0xABC", "executor_id": "exec-1"},
                {"name": "kk-agent-2", "address": "0xDEF", "executor_id": "exec-2"},
            ]
        }), encoding="utf-8")
        load_identities(config)
        agent = resolve_nick("kk-agent-1")
        assert agent is not None
        assert agent["wallet"] == "0xABC"
        assert agent["executor_id"] == "exec-1"

    def test_resolve_unknown_nick(self):
        assert resolve_nick("unknown-nick") is None

    def test_missing_config_file(self, tmp_path):
        load_identities(tmp_path / "nonexistent.json")
        # Should not crash
        assert resolve_nick("anyone") is None


# ═══════════════════════════════════════════════════════════════════
# Message Splitting
# ═══════════════════════════════════════════════════════════════════


class TestSplitMessage:
    """Tests for IRC message length splitting."""

    def test_short_message_not_split(self):
        parts = _split_message("Hello world")
        assert parts == ["Hello world"]

    def test_long_message_split(self):
        msg = "a" * 1000
        parts = _split_message(msg, max_len=MAX_MSG_LEN)
        assert all(len(p) <= MAX_MSG_LEN for p in parts)
        assert "".join(parts) == msg

    def test_empty_message(self):
        parts = _split_message("")
        assert parts == [""]

    def test_exact_length(self):
        msg = "x" * MAX_MSG_LEN
        parts = _split_message(msg, max_len=MAX_MSG_LEN)
        assert len(parts) == 1

    def test_one_over(self):
        msg = "x" * (MAX_MSG_LEN + 1)
        parts = _split_message(msg, max_len=MAX_MSG_LEN)
        assert len(parts) == 2


# ═══════════════════════════════════════════════════════════════════
# Error Extraction
# ═══════════════════════════════════════════════════════════════════


class TestExtractError:
    """Tests for error message extraction from exceptions."""

    def test_basic_error(self):
        err = _extract_error(ValueError("bad input"))
        assert "bad input" in err

    def test_json_error_body(self):
        """Some API errors contain JSON in the message."""
        exc = Exception('{"error": "task not found", "code": 404}')
        err = _extract_error(exc)
        assert "task not found" in err or "404" in err


# ═══════════════════════════════════════════════════════════════════
# Command Handlers
# ═══════════════════════════════════════════════════════════════════


class TestHandlePublish:
    """Tests for !em publish command."""

    @pytest.fixture(autouse=True)
    def setup_identity(self):
        import irc.em_bridge_bot as mod
        mod._nick_to_agent = {
            "kk-test": {
                "name": "kk-test",
                "wallet": "0xTestWallet",
                "executor_id": "exec-test",
            }
        }

    @pytest.mark.asyncio
    async def test_unknown_nick(self):
        result = await handle_publish(MagicMock(), "unknown-nick", "Test | Instructions | 0.05")
        assert "[ERR]" in result
        assert "Unknown nick" in result

    @pytest.mark.asyncio
    async def test_too_few_parts(self):
        result = await handle_publish(MagicMock(), "kk-test", "just a title")
        assert "[ERR]" in result
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_invalid_bounty(self):
        result = await handle_publish(MagicMock(), "kk-test", "Title | Instructions | notanumber")
        assert "[ERR]" in result
        assert "Invalid bounty" in result

    @pytest.mark.asyncio
    async def test_bounty_too_high(self):
        result = await handle_publish(MagicMock(), "kk-test", "Title | Instructions | 100.00")
        assert "[ERR]" in result
        assert "too high" in result

    @pytest.mark.asyncio
    async def test_successful_publish(self):
        mock_client = MagicMock()
        mock_client.publish_task = AsyncMock(return_value={"id": "new-task-123", "bounty_usd": 0.05})
        result = await handle_publish(mock_client, "kk-test", "Test Task | Do something | 0.05")
        assert "new-task-123" in result or "published" in result.lower()


class TestHandleTasks:
    """Tests for !em tasks command."""

    @pytest.mark.asyncio
    async def test_lists_tasks(self):
        mock_client = MagicMock()
        mock_client.browse_tasks = AsyncMock(return_value=[
            {"id": "t-1", "title": "Task One", "bounty_usd": 0.05, "status": "published"},
            {"id": "t-2", "title": "Task Two", "bounty_usd": 0.10, "status": "published"},
        ])
        result = await handle_tasks(mock_client, "kk-test", "")
        assert "Task One" in result or "2" in result

    @pytest.mark.asyncio
    async def test_no_tasks(self):
        mock_client = MagicMock()
        mock_client.browse_tasks = AsyncMock(return_value=[])
        result = await handle_tasks(mock_client, "kk-test", "")
        assert "no" in result.lower() and "task" in result.lower()


class TestHandleTask:
    """Tests for !em task <id> command."""

    @pytest.mark.asyncio
    async def test_missing_task_id(self):
        result = await handle_task(MagicMock(), "kk-test", "")
        assert "[ERR]" in result or "Usage" in result

    @pytest.mark.asyncio
    async def test_task_details(self):
        mock_client = MagicMock()
        mock_client.get_task = AsyncMock(return_value={
            "id": "t-abc",
            "title": "My Task",
            "status": "published",
            "bounty_usd": 0.05,
        })
        result = await handle_task(mock_client, "kk-test", "t-abc")
        assert "My Task" in result or "t-abc" in result


class TestHandleApply:
    """Tests for !em apply command."""

    @pytest.fixture(autouse=True)
    def setup_identity(self):
        import irc.em_bridge_bot as mod
        mod._nick_to_agent = {
            "kk-test": {
                "name": "kk-test",
                "wallet": "0xTestWallet",
                "executor_id": "exec-test",
            }
        }

    @pytest.mark.asyncio
    async def test_unknown_nick(self):
        import irc.em_bridge_bot as mod
        mod._nick_to_agent.clear()
        result = await handle_apply(MagicMock(), "unknown", "task-123")
        assert "[ERR]" in result

    @pytest.mark.asyncio
    async def test_missing_task_id(self):
        result = await handle_apply(MagicMock(), "kk-test", "")
        assert "[ERR]" in result or "Usage" in result


class TestHandleApproveReject:
    """Tests for !em approve and !em reject commands."""

    @pytest.fixture(autouse=True)
    def setup_identity(self):
        import irc.em_bridge_bot as mod
        mod._nick_to_agent = {
            "kk-test": {
                "name": "kk-test",
                "wallet": "0xTestWallet",
                "executor_id": "exec-test",
            }
        }

    @pytest.mark.asyncio
    async def test_approve_missing_id(self):
        result = await handle_approve(MagicMock(), "kk-test", "")
        assert "[ERR]" in result or "Usage" in result

    @pytest.mark.asyncio
    async def test_reject_missing_id(self):
        result = await handle_reject(MagicMock(), "kk-test", "")
        assert "[ERR]" in result or "Usage" in result


class TestHandleCancel:
    """Tests for !em cancel command."""

    @pytest.fixture(autouse=True)
    def setup_identity(self):
        import irc.em_bridge_bot as mod
        mod._nick_to_agent = {
            "kk-test": {
                "name": "kk-test",
                "wallet": "0xTestWallet",
                "executor_id": "exec-test",
            }
        }

    @pytest.mark.asyncio
    async def test_cancel_missing_id(self):
        result = await handle_cancel(MagicMock(), "kk-test", "")
        assert "[ERR]" in result or "Usage" in result


class TestHandleHelp:
    """Tests for !em help command."""

    @pytest.mark.asyncio
    async def test_returns_help_text(self):
        result = await handle_help(MagicMock(), "anyone", "")
        assert "publish" in result.lower()
        assert "tasks" in result.lower()
        assert "help" in result.lower()


class TestHandleSubmit:
    """Tests for !em submit command."""

    @pytest.fixture(autouse=True)
    def setup_identity(self):
        import irc.em_bridge_bot as mod
        mod._nick_to_agent = {
            "kk-test": {
                "name": "kk-test",
                "wallet": "0xTestWallet",
                "executor_id": "exec-test",
            }
        }

    @pytest.mark.asyncio
    async def test_submit_missing_args(self):
        result = await handle_submit(MagicMock(), "kk-test", "")
        assert "[ERR]" in result or "Usage" in result

    @pytest.mark.asyncio
    async def test_submit_missing_evidence(self):
        result = await handle_submit(MagicMock(), "kk-test", "task-123")
        assert "[ERR]" in result or "Usage" in result
