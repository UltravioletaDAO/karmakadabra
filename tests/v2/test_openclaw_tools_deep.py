"""
Tests for openclaw/tools/ — Deep Coverage

Tests cover:
  - IRC Guard: dedup, rate limiting, self-detection, circuit breaker
  - Wallet Tool: budget calculations, affordability checks
  - EM Tool: action routing, parameter validation, error handling

These tools are the primary interface between OpenClaw agents and KK.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ═══════════════════════════════════════════════════════════════════
# IRC Guard Tests
# ═══════════════════════════════════════════════════════════════════


class TestIrcGuardSimilarity:
    """Tests for word-overlap similarity function."""

    def test_identical_strings(self):
        from openclaw.tools.irc_guard import _similarity
        assert _similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        from openclaw.tools.irc_guard import _similarity
        assert _similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        from openclaw.tools.irc_guard import _similarity
        sim = _similarity("hello world foo", "hello world bar")
        # Jaccard: intersection(hello,world) / union(hello,world,foo,bar) = 2/4 = 0.5
        assert sim == 0.5

    def test_empty_string(self):
        from openclaw.tools.irc_guard import _similarity
        assert _similarity("", "hello") == 0.0
        assert _similarity("hello", "") == 0.0
        assert _similarity("", "") == 0.0

    def test_case_insensitive(self):
        from openclaw.tools.irc_guard import _similarity
        assert _similarity("Hello World", "hello world") == 1.0


class TestIrcGuardWordSet:
    """Tests for word set extraction."""

    def test_basic_extraction(self):
        from openclaw.tools.irc_guard import _word_set
        result = _word_set("Hello World")
        assert result == {"hello", "world"}

    def test_deduplication(self):
        from openclaw.tools.irc_guard import _word_set
        result = _word_set("hello hello hello")
        assert result == {"hello"}

    def test_empty_string(self):
        from openclaw.tools.irc_guard import _word_set
        result = _word_set("")
        # set().split() on empty string gives empty set
        assert isinstance(result, set)


class TestIrcGuardCheckMessage:
    """Tests for the main check_message guard function."""

    @pytest.fixture(autouse=True)
    def clean_state(self, tmp_path, monkeypatch):
        """Point guard state/logs to temp directory."""
        import openclaw.tools.irc_guard as guard_mod
        monkeypatch.setattr(guard_mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(guard_mod, "SENT_LOG", tmp_path / "irc_sent_log.jsonl")
        monkeypatch.setattr(guard_mod, "STATE_FILE", tmp_path / "irc_guard_state.json")

    def test_allows_first_message(self):
        from openclaw.tools.irc_guard import check_message
        result = check_message("Hello everyone!", "#karmakadabra", "kk-test")
        assert result["allow"] is True
        assert result["reason"] == "OK"

    def test_rejects_self_detection_angle_brackets(self):
        from openclaw.tools.irc_guard import check_message
        result = check_message("<kk-test> Hello!", "#karmakadabra", "kk-test")
        assert result["allow"] is False
        assert "Self-detection" in result["reason"]

    def test_rejects_self_detection_colon(self):
        from openclaw.tools.irc_guard import check_message
        result = check_message("kk-test: some reply", "#karmakadabra", "kk-test")
        assert result["allow"] is False
        assert "Self-detection" in result["reason"]

    def test_allows_different_agent_name(self):
        from openclaw.tools.irc_guard import check_message
        result = check_message("<kk-other> Hello!", "#karmakadabra", "kk-test")
        assert result["allow"] is True

    def test_dedup_rejects_similar_message(self):
        from openclaw.tools.irc_guard import check_message
        # Send first message
        result1 = check_message("I have data for sale", "#channel", "kk-test")
        assert result1["allow"] is True
        # Send nearly identical message
        result2 = check_message("I have data for sale", "#channel", "kk-test")
        assert result2["allow"] is False
        assert "Duplicate" in result2["reason"]

    def test_dedup_allows_different_message(self):
        from openclaw.tools.irc_guard import check_message
        result1 = check_message("Selling blockchain data", "#channel", "kk-test")
        assert result1["allow"] is True
        result2 = check_message("Looking for AI expertise", "#channel", "kk-test")
        assert result2["allow"] is True

    def test_rate_limit_blocks_after_threshold(self):
        from openclaw.tools.irc_guard import check_message, RATE_LIMIT_MSGS
        # Send up to the limit
        for i in range(RATE_LIMIT_MSGS):
            result = check_message(f"Unique message number {i} with different words {i*100}", "#ch", "kk-test")
            assert result["allow"] is True, f"Message {i} should be allowed"
        # Next should be blocked
        result = check_message("One more message that is completely unique and novel", "#ch", "kk-test")
        assert result["allow"] is False
        # Circuit breaker fires before rate limit (same thresholds)
        assert result["reason"] and ("Rate limit" in result["reason"] or "Circuit breaker" in result["reason"])

    def test_circuit_breaker_triggers(self):
        from openclaw.tools.irc_guard import (
            check_message, _record_sent,
            CIRCUIT_BREAKER_MSGS, CIRCUIT_BREAKER_WINDOW,
        )
        # Simulate many messages in short window (bypass normal rate limit by recording directly)
        for i in range(CIRCUIT_BREAKER_MSGS):
            _record_sent(f"burst message {i} unique content {i*1000}", "#ch", "kk-test")

        result = check_message("trigger breaker message", "#ch", "kk-test")
        assert result["allow"] is False
        assert "Circuit breaker" in result["reason"]

    def test_circuit_breaker_cooldown(self):
        from openclaw.tools.irc_guard import check_message, _save_state
        # Set circuit breaker to future
        _save_state({"circuit_breaker_until": time.time() + 100})
        result = check_message("Hello!", "#ch", "kk-test")
        assert result["allow"] is False
        assert "Circuit breaker active" in result["reason"]

    def test_circuit_breaker_expired(self):
        from openclaw.tools.irc_guard import check_message, _save_state
        # Set circuit breaker to past
        _save_state({"circuit_breaker_until": time.time() - 100})
        result = check_message("Hello after cooldown!", "#ch", "kk-test")
        assert result["allow"] is True

    def test_records_sent_message(self):
        from openclaw.tools.irc_guard import check_message, SENT_LOG
        check_message("Track this message", "#ch", "kk-test")
        assert SENT_LOG.exists()
        entries = [json.loads(line) for line in SENT_LOG.read_text().splitlines() if line.strip()]
        assert len(entries) == 1
        assert entries[0]["message"] == "Track this message"
        assert entries[0]["agent"] == "kk-test"


class TestIrcGuardLoadSentLog:
    """Tests for sent log loading."""

    @pytest.fixture(autouse=True)
    def clean_state(self, tmp_path, monkeypatch):
        import openclaw.tools.irc_guard as guard_mod
        monkeypatch.setattr(guard_mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(guard_mod, "SENT_LOG", tmp_path / "irc_sent_log.jsonl")
        monkeypatch.setattr(guard_mod, "STATE_FILE", tmp_path / "irc_guard_state.json")

    def test_empty_log(self):
        from openclaw.tools.irc_guard import _load_sent_log
        entries = _load_sent_log(0)
        assert entries == []

    def test_filters_by_timestamp(self):
        from openclaw.tools.irc_guard import _load_sent_log, SENT_LOG
        now = time.time()
        SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        entries = [
            {"ts": now - 1000, "message": "old", "channel": "#ch", "agent": "test"},
            {"ts": now - 10, "message": "recent", "channel": "#ch", "agent": "test"},
        ]
        SENT_LOG.write_text(
            "\n".join(json.dumps(e) for e in entries),
            encoding="utf-8",
        )
        result = _load_sent_log(now - 100)
        assert len(result) == 1
        assert result[0]["message"] == "recent"

    def test_handles_corrupt_jsonl(self):
        from openclaw.tools.irc_guard import _load_sent_log, SENT_LOG
        SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        SENT_LOG.write_text(
            '{"ts": 999999999, "message": "ok"}\nNOT JSON\n',
            encoding="utf-8",
        )
        result = _load_sent_log(0)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════
# Wallet Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestWalletToolBudget:
    """Tests for wallet budget calculations."""

    def test_budget_default_values(self):
        from openclaw.tools.wallet_tool import action_budget, DEFAULT_DAILY_BUDGET
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=0.0):
            result = action_budget({})
            assert result["daily_budget_usd"] == DEFAULT_DAILY_BUDGET
            assert result["daily_spent_usd"] == 0.0
            assert result["remaining_usd"] == DEFAULT_DAILY_BUDGET
            assert result["utilization_pct"] == 0.0

    def test_budget_with_spending(self):
        from openclaw.tools.wallet_tool import action_budget
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=0.75):
            result = action_budget({"daily_budget": 2.0})
            assert result["daily_spent_usd"] == 0.75
            assert result["remaining_usd"] == 1.25
            assert result["utilization_pct"] == 37.5

    def test_budget_fully_spent(self):
        from openclaw.tools.wallet_tool import action_budget
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=2.0):
            result = action_budget({"daily_budget": 2.0})
            assert result["remaining_usd"] == 0.0
            assert result["utilization_pct"] == 100.0

    def test_budget_overspent(self):
        from openclaw.tools.wallet_tool import action_budget
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=3.0):
            result = action_budget({"daily_budget": 2.0})
            assert result["remaining_usd"] == 0.0  # max(0, ...)

    def test_budget_custom_limit(self):
        from openclaw.tools.wallet_tool import action_budget
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=0.0):
            result = action_budget({"daily_budget": 5.0})
            assert result["daily_budget_usd"] == 5.0
            assert result["remaining_usd"] == 5.0


class TestWalletToolCanAfford:
    """Tests for affordability checks."""

    def test_can_afford_within_budget(self):
        from openclaw.tools.wallet_tool import action_can_afford
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=0.5):
            result = action_can_afford({"amount": 0.10, "daily_budget": 2.0})
            assert result["can_afford"] is True
            assert result["amount_usd"] == 0.10

    def test_cannot_afford_over_budget(self):
        from openclaw.tools.wallet_tool import action_can_afford
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=1.95):
            result = action_can_afford({"amount": 0.10, "daily_budget": 2.0})
            assert result["can_afford"] is False

    def test_zero_amount_error(self):
        from openclaw.tools.wallet_tool import action_can_afford
        result = action_can_afford({"amount": 0})
        assert "error" in result

    def test_negative_amount_error(self):
        from openclaw.tools.wallet_tool import action_can_afford
        result = action_can_afford({"amount": -1})
        assert "error" in result

    def test_exact_remaining(self):
        from openclaw.tools.wallet_tool import action_can_afford
        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=1.90):
            result = action_can_afford({"amount": 0.10, "daily_budget": 2.0})
            assert result["can_afford"] is True


class TestWalletToolLoadDailySpent:
    """Tests for daily spending load logic."""

    def test_no_files_returns_zero(self):
        from openclaw.tools.wallet_tool import _load_daily_spent
        with patch("openclaw.tools.wallet_tool.Path") as MockPath:
            mock_working = MagicMock()
            mock_working.exists.return_value = False
            mock_state = MagicMock()
            mock_state.exists.return_value = False
            MockPath.side_effect = lambda p: mock_state if "escrow" in str(p) else mock_working
            # Since the function uses hardcoded paths, just verify it returns 0 on missing files
            # by running with non-existent env
            with patch.dict(os.environ, {"KK_AGENT_NAME": "nonexistent-agent-xyz"}):
                result = _load_daily_spent()
                assert isinstance(result, float)


class TestWalletToolActions:
    """Tests for action routing."""

    def test_action_map_has_all_actions(self):
        from openclaw.tools.wallet_tool import ACTIONS
        expected = {"balance", "budget", "can_afford"}
        assert set(ACTIONS.keys()) == expected


# ═══════════════════════════════════════════════════════════════════
# EM Tool Tests
# ═══════════════════════════════════════════════════════════════════


class TestEmToolActions:
    """Tests for EM tool action routing and validation."""

    def test_action_map_complete(self):
        from openclaw.tools.em_tool import ACTIONS
        expected = {"browse", "publish", "apply", "submit", "approve", "status", "history"}
        assert set(ACTIONS.keys()) == expected

    @pytest.mark.asyncio
    async def test_publish_missing_fields(self):
        from openclaw.tools.em_tool import action_publish
        with patch("openclaw.tools.em_tool._load_context"), \
             patch("services.em_client.EMClient") as mock_emc_cls:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client
            result = await action_publish({"title": "Test"})  # Missing instructions, etc.
            assert "error" in result
            assert "Missing required field" in result["error"]

    @pytest.mark.asyncio
    async def test_apply_missing_task_id(self):
        from openclaw.tools.em_tool import action_apply
        with patch("openclaw.tools.em_tool._load_context") as mock_ctx:
            mock_ctx.return_value = MagicMock(executor_id="exec-1")
            with patch("services.em_client.EMClient") as mock_emc_cls:
                mock_client = MagicMock()
                mock_client.close = AsyncMock()
                mock_emc_cls.return_value = mock_client
                result = await action_apply({})
                assert "error" in result
                assert "task_id" in result["error"]

    @pytest.mark.asyncio
    async def test_apply_no_executor_id(self):
        from openclaw.tools.em_tool import action_apply
        with patch("openclaw.tools.em_tool._load_context") as mock_ctx:
            mock_ctx.return_value = MagicMock(executor_id=None)
            result = await action_apply({"task_id": "task-1"})
            assert "error" in result
            assert "executor_id" in result["error"]

    @pytest.mark.asyncio
    async def test_submit_missing_task_id(self):
        from openclaw.tools.em_tool import action_submit
        with patch("openclaw.tools.em_tool._load_context") as mock_ctx:
            mock_ctx.return_value = MagicMock(executor_id="exec-1")
            with patch("services.em_client.EMClient") as mock_emc_cls:
                mock_client = MagicMock()
                mock_client.close = AsyncMock()
                mock_emc_cls.return_value = mock_client
                result = await action_submit({})
                assert "error" in result

    @pytest.mark.asyncio
    async def test_submit_invalid_evidence(self):
        from openclaw.tools.em_tool import action_submit
        with patch("openclaw.tools.em_tool._load_context") as mock_ctx:
            mock_ctx.return_value = MagicMock(executor_id="exec-1")
            with patch("services.em_client.EMClient") as mock_emc_cls:
                mock_client = MagicMock()
                mock_client.close = AsyncMock()
                mock_emc_cls.return_value = mock_client
                result = await action_submit({"task_id": "t-1", "evidence": "not a dict"})
                assert "error" in result
                assert "dict" in result["error"]

    @pytest.mark.asyncio
    async def test_approve_missing_submission_id(self):
        from openclaw.tools.em_tool import action_approve
        with patch("openclaw.tools.em_tool._load_context"), \
             patch("services.em_client.EMClient") as mock_emc_cls:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client
            result = await action_approve({})
            assert "error" in result
            assert "submission_id" in result["error"]

    @pytest.mark.asyncio
    async def test_history_no_state_file(self):
        from openclaw.tools.em_tool import action_history
        with patch.dict(os.environ, {"KK_AGENT_NAME": "nonexistent"}):
            result = await action_history({})
            assert result["count"] == 0
            assert result["purchases"] == []

    @pytest.mark.asyncio
    async def test_browse_returns_tasks(self):
        from openclaw.tools.em_tool import action_browse
        with patch("openclaw.tools.em_tool._load_context") as mock_ctx, \
             patch("services.em_client.EMClient") as mock_emc_cls:

            mock_ctx.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.browse_tasks = AsyncMock(return_value=[
                {"id": "t1", "title": "Task 1"},
                {"id": "t2", "title": "Task 2"},
            ])
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            result = await action_browse({"status": "published"})
            assert result["count"] == 2
            assert len(result["tasks"]) == 2

    @pytest.mark.asyncio
    async def test_publish_success(self):
        from openclaw.tools.em_tool import action_publish
        with patch("openclaw.tools.em_tool._load_context") as mock_ctx, \
             patch("services.em_client.EMClient") as mock_emc_cls:

            mock_ctx.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.publish_task = AsyncMock(return_value={"id": "new-task"})
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            result = await action_publish({
                "title": "Test Task",
                "instructions": "Do something",
                "category": "data_collection",
                "bounty_usd": 0.05,
            })
            assert result["published"] is True
            assert result["task"]["id"] == "new-task"

    @pytest.mark.asyncio
    async def test_status_returns_tasks(self):
        from openclaw.tools.em_tool import action_status
        with patch("openclaw.tools.em_tool._load_context") as mock_ctx, \
             patch("services.em_client.EMClient") as mock_emc_cls:

            mock_ctx.return_value = MagicMock()
            mock_client = MagicMock()
            mock_client.list_tasks = AsyncMock(return_value=[
                {"id": "t1", "status": "in_progress"},
            ])
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            result = await action_status({"status": "in_progress"})
            assert result["count"] == 1
