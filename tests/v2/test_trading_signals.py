"""
Tests for Trading Signal Bot — signal parsing, P&L calculation,
leaderboard, store persistence, rate limiting, and command handlers.
"""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import sys

_kk_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_kk_root / "irc"))
sys.path.insert(0, str(_kk_root / "lib"))

from trading_signal_bot import (
    COMMANDS,
    COINGECKO_IDS,
    PLAN_DURATION_SECONDS,
    REVENUE_SPLIT,
    SUBSCRIPTION_PLANS,
    TIMEFRAME_SECONDS,
    PriceMonitor,
    SignalStore,
    SubscriptionStore,
    TraderStats,
    TradingSignal,
    _format_duration,
    _split_message,
    check_cmd_rate,
    check_signal_rate,
    compute_stats,
    handle_cancel,
    handle_close,
    handle_detail,
    handle_help,
    handle_history,
    handle_leaderboard,
    handle_open,
    handle_signal,
    handle_stats,
    handle_subscribe,
    handle_subscribers,
    handle_unsubscribe,
    parse_command,
    parse_signal,
    _signal_buckets,
    _cmd_buckets,
)


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear rate limit state between tests."""
    _signal_buckets.clear()
    _cmd_buckets.clear()
    yield
    _signal_buckets.clear()
    _cmd_buckets.clear()


@pytest.fixture
def tmp_store(tmp_path):
    """Create a SignalStore backed by tmp_path."""
    return SignalStore(tmp_path)


@pytest.fixture
def sample_signal():
    """A valid open BUY signal."""
    return TradingSignal(
        id="s-abc12345",
        author="trader1",
        direction="BUY",
        pair="ETH/USDC",
        entry_price=3500.0,
        stop_loss=3400.0,
        take_profit=3700.0,
        confidence=85,
        timeframe="4H",
        status="open",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def sample_sell_signal():
    """A valid open SELL signal."""
    return TradingSignal(
        id="s-def67890",
        author="trader2",
        direction="SELL",
        pair="AVAX/USDC",
        entry_price=38.50,
        stop_loss=40.00,
        take_profit=35.00,
        confidence=72,
        timeframe="1D",
        status="open",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# =========================================================================
# Signal parsing
# =========================================================================


class TestParseSignal:
    def test_basic_buy(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 4H")
        assert sig is not None
        assert sig.direction == "BUY"
        assert sig.pair == "ETH/USDC"
        assert sig.entry_price == 3500.0
        assert sig.stop_loss == 3400.0
        assert sig.take_profit == 3700.0
        assert sig.confidence == 85
        assert sig.timeframe == "4H"
        assert sig.status == "open"

    def test_basic_sell(self):
        sig = parse_signal("[SIGNAL] SELL AVAX/USDC @ 38.50 | SL: 40.00 | TP: 35.00 | 72% | 1D")
        assert sig is not None
        assert sig.direction == "SELL"
        assert sig.pair == "AVAX/USDC"
        assert sig.entry_price == 38.50
        assert sig.stop_loss == 40.0
        assert sig.take_profit == 35.0

    def test_ts_command_prefix(self):
        sig = parse_signal("!ts signal BUY SOL/USDC @ 180 | SL: 170 | TP: 200 | 90% | 1W")
        assert sig is not None
        assert sig.pair == "SOL/USDC"
        assert sig.timeframe == "1W"

    def test_defaults(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700")
        assert sig is not None
        assert sig.confidence == 50  # default
        assert sig.timeframe == "4H"  # default

    def test_case_insensitive(self):
        sig = parse_signal("[signal] buy eth/usdc @ 3500 | sl: 3400 | tp: 3700")
        assert sig is not None
        assert sig.direction == "BUY"

    def test_invalid_no_sl(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | TP: 3700")
        assert sig is None

    def test_invalid_buy_sl_above_entry(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3600 | TP: 3700 | 85% | 4H")
        assert sig is None  # SL must be below entry for BUY

    def test_invalid_sell_sl_below_entry(self):
        sig = parse_signal("[SIGNAL] SELL ETH/USDC @ 3500 | SL: 3400 | TP: 3300 | 85% | 4H")
        assert sig is None  # SL must be above entry for SELL

    def test_invalid_buy_tp_below_entry(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3400 | 85% | 4H")
        assert sig is None  # TP must be above entry for BUY

    def test_invalid_confidence_out_of_range(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 150% | 4H")
        assert sig is None

    def test_invalid_timeframe(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 3M")
        assert sig is None

    def test_not_a_signal(self):
        sig = parse_signal("hello world")
        assert sig is None

    def test_has_id(self):
        sig = parse_signal("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700")
        assert sig is not None
        assert sig.id.startswith("s-")
        assert len(sig.id) == 10  # s- + 8 hex chars


# =========================================================================
# TradingSignal methods
# =========================================================================


class TestTradingSignal:
    def test_base_asset(self, sample_signal):
        assert sample_signal.base_asset() == "ETH"

    def test_calc_pnl_buy_profit(self, sample_signal):
        pnl = sample_signal.calc_pnl(3700)
        assert abs(pnl - 5.714) < 0.01

    def test_calc_pnl_buy_loss(self, sample_signal):
        pnl = sample_signal.calc_pnl(3400)
        assert pnl < 0

    def test_calc_pnl_sell_profit(self, sample_sell_signal):
        pnl = sample_sell_signal.calc_pnl(35.0)
        assert pnl > 0

    def test_calc_pnl_sell_loss(self, sample_sell_signal):
        pnl = sample_sell_signal.calc_pnl(40.0)
        assert pnl < 0

    def test_check_tp_buy(self, sample_signal):
        assert sample_signal.check_tp_sl(3700) == "tp_hit"
        assert sample_signal.check_tp_sl(3800) == "tp_hit"

    def test_check_sl_buy(self, sample_signal):
        assert sample_signal.check_tp_sl(3400) == "sl_hit"
        assert sample_signal.check_tp_sl(3300) == "sl_hit"

    def test_check_none_buy(self, sample_signal):
        assert sample_signal.check_tp_sl(3500) is None
        assert sample_signal.check_tp_sl(3600) is None

    def test_check_tp_sell(self, sample_sell_signal):
        assert sample_sell_signal.check_tp_sl(35.0) == "tp_hit"
        assert sample_sell_signal.check_tp_sl(34.0) == "tp_hit"

    def test_check_sl_sell(self, sample_sell_signal):
        assert sample_sell_signal.check_tp_sl(40.0) == "sl_hit"

    def test_is_expired_not_yet(self, sample_signal):
        assert not sample_signal.is_expired()

    def test_is_expired_yes(self, sample_signal):
        sample_signal.created_at = (
            datetime.now(timezone.utc) - timedelta(hours=5)
        ).isoformat()
        assert sample_signal.is_expired()


# =========================================================================
# Command parsing
# =========================================================================


class TestParseCommand:
    def test_ts_prefix(self):
        assert parse_command("!ts help") == ("help", "")

    def test_ts_with_args(self):
        cmd, args = parse_command("!ts stats @trader1")
        assert cmd == "stats"
        assert args == "@trader1"

    def test_bare_ts(self):
        assert parse_command("!ts") == ("help", "")

    def test_not_ts(self):
        assert parse_command("hello") == ("", "")

    def test_raw_signal(self):
        cmd, args = parse_command("[SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700")
        assert cmd == "_raw_signal"
        assert "[SIGNAL]" in args

    def test_case_insensitive(self):
        assert parse_command("!TS HELP") == ("help", "")

    def test_whitespace(self):
        assert parse_command("  !ts   leaderboard   30d  ") == ("leaderboard", "30d")


# =========================================================================
# Signal store
# =========================================================================


class TestSignalStore:
    def test_add_and_get(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        retrieved = tmp_store.get("s-abc12345")
        assert retrieved is not None
        assert retrieved.pair == "ETH/USDC"

    def test_short_id_lookup(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        retrieved = tmp_store.get("s-abc1")
        assert retrieved is not None

    def test_open_signals(self, tmp_store, sample_signal, sample_sell_signal):
        tmp_store.add(sample_signal)
        tmp_store.add(sample_sell_signal)
        opens = tmp_store.open_signals()
        assert len(opens) == 2

    def test_open_by_author(self, tmp_store, sample_signal, sample_sell_signal):
        tmp_store.add(sample_signal)
        tmp_store.add(sample_sell_signal)
        opens = tmp_store.open_signals(author="trader1")
        assert len(opens) == 1

    def test_persistence(self, tmp_path, sample_signal):
        store1 = SignalStore(tmp_path)
        store1.add(sample_signal)

        store2 = SignalStore(tmp_path)
        assert store2.get("s-abc12345") is not None

    def test_update(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        sample_signal.status = "tp_hit"
        sample_signal.pnl_percent = 5.7
        tmp_store.update(sample_signal)

        retrieved = tmp_store.get("s-abc12345")
        assert retrieved.status == "tp_hit"
        assert retrieved.pnl_percent == 5.7

    def test_closed_signals(self, tmp_store, sample_signal):
        sample_signal.status = "tp_hit"
        sample_signal.closed_at = datetime.now(timezone.utc).isoformat()
        sample_signal.pnl_percent = 5.7
        tmp_store.add(sample_signal)

        closed = tmp_store.closed_signals()
        assert len(closed) == 1


# =========================================================================
# Rate limiting
# =========================================================================


class TestRateLimiting:
    def test_signal_under_limit(self):
        for _ in range(5):
            assert check_signal_rate("trader1")

    def test_signal_over_limit(self):
        for _ in range(5):
            check_signal_rate("trader1")
        assert not check_signal_rate("trader1")

    def test_cmd_under_limit(self):
        for _ in range(10):
            assert check_cmd_rate("trader1")

    def test_cmd_over_limit(self):
        for _ in range(10):
            check_cmd_rate("trader1")
        assert not check_cmd_rate("trader1")

    def test_separate_nicks(self):
        for _ in range(5):
            check_signal_rate("trader1")
        assert check_signal_rate("trader2")


# =========================================================================
# Stats computation
# =========================================================================


class TestComputeStats:
    def test_empty(self):
        stats = compute_stats([], nick="empty")
        assert stats.total_signals == 0
        assert stats.avg_pnl == 0.0

    def test_wins_and_losses(self):
        sigs = [
            TradingSignal(
                id=f"s-{i}",
                author="t1",
                direction="BUY",
                pair="ETH/USDC",
                entry_price=3500,
                stop_loss=3400,
                take_profit=3700,
                confidence=80,
                timeframe="4H",
                status="tp_hit" if i % 2 == 0 else "sl_hit",
                created_at=(datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                closed_at=datetime.now(timezone.utc).isoformat(),
                pnl_percent=5.0 if i % 2 == 0 else -3.0,
            )
            for i in range(6)
        ]
        stats = compute_stats(sigs, nick="t1")
        assert stats.total_signals == 6
        assert stats.wins == 3
        assert stats.losses == 3
        assert stats.best_trade == 5.0
        assert stats.worst_trade == -3.0
        assert abs(stats.total_pnl - 6.0) < 0.01

    def test_open_signals_counted(self, sample_signal):
        stats = compute_stats([sample_signal], nick="t1")
        assert stats.open_count == 1
        assert stats.wins == 0

    def test_streak(self):
        sigs = [
            TradingSignal(
                id=f"s-{i}",
                author="t1",
                direction="BUY",
                pair="ETH/USDC",
                entry_price=3500,
                stop_loss=3400,
                take_profit=3700,
                confidence=80,
                timeframe="4H",
                status="tp_hit",
                created_at=(datetime.now(timezone.utc) - timedelta(hours=5 - i)).isoformat(),
                closed_at=datetime.now(timezone.utc).isoformat(),
                pnl_percent=2.0,
            )
            for i in range(3)
        ]
        stats = compute_stats(sigs, nick="t1")
        assert stats.current_streak == 3
        assert stats.longest_streak == 3


# =========================================================================
# Command handlers (async)
# =========================================================================


class TestHandleSignal:
    @pytest.mark.asyncio
    async def test_publish_success(self, tmp_store):
        result = await handle_signal(
            tmp_store,
            "trader1",
            "!ts signal BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 4H",
        )
        assert "[OK]" in result
        assert "ETH/USDC" in result
        assert len(tmp_store.open_signals()) == 1

    @pytest.mark.asyncio
    async def test_publish_invalid(self, tmp_store):
        result = await handle_signal(tmp_store, "trader1", "not a signal")
        assert "[ERR]" in result

    @pytest.mark.asyncio
    async def test_publish_rate_limited(self, tmp_store):
        for _ in range(5):
            check_signal_rate("spammer")
        result = await handle_signal(
            tmp_store,
            "spammer",
            "!ts signal BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 4H",
        )
        assert "rate limit" in result.lower()


class TestHandleOpen:
    @pytest.mark.asyncio
    async def test_empty(self, tmp_store):
        result = await handle_open(tmp_store, "trader1", "")
        assert "No open" in result

    @pytest.mark.asyncio
    async def test_with_signals(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        result = await handle_open(tmp_store, "anyone", "")
        assert "1 open" in result
        assert "ETH/USDC" in result

    @pytest.mark.asyncio
    async def test_by_author(self, tmp_store, sample_signal, sample_sell_signal):
        tmp_store.add(sample_signal)
        tmp_store.add(sample_sell_signal)
        result = await handle_open(tmp_store, "anyone", "@trader1")
        assert "1 open" in result


class TestHandleHistory:
    @pytest.mark.asyncio
    async def test_empty(self, tmp_store):
        result = await handle_history(tmp_store, "anyone", "")
        assert "No closed" in result

    @pytest.mark.asyncio
    async def test_with_closed(self, tmp_store, sample_signal):
        sample_signal.status = "tp_hit"
        sample_signal.closed_at = datetime.now(timezone.utc).isoformat()
        sample_signal.pnl_percent = 5.7
        tmp_store.add(sample_signal)
        result = await handle_history(tmp_store, "anyone", "")
        assert "5.7%" in result


class TestHandleDetail:
    @pytest.mark.asyncio
    async def test_found(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        result = await handle_detail(tmp_store, "anyone", "s-abc12345")
        assert "ETH/USDC" in result
        assert "3500" in result

    @pytest.mark.asyncio
    async def test_not_found(self, tmp_store):
        result = await handle_detail(tmp_store, "anyone", "s-nope")
        assert "[ERR]" in result

    @pytest.mark.asyncio
    async def test_no_id(self, tmp_store):
        result = await handle_detail(tmp_store, "anyone", "")
        assert "[ERR]" in result


class TestHandleClose:
    @pytest.mark.asyncio
    async def test_close_with_price(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        result = await handle_close(tmp_store, "trader1", "s-abc12345 3600")
        assert "[SIGNAL-CLOSE]" in result
        assert "2.9%" in result

    @pytest.mark.asyncio
    async def test_close_wrong_author(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        result = await handle_close(tmp_store, "other", "s-abc12345 3600")
        assert "[ERR]" in result
        assert "trader1" in result

    @pytest.mark.asyncio
    async def test_close_already_closed(self, tmp_store, sample_signal):
        sample_signal.status = "tp_hit"
        tmp_store.add(sample_signal)
        result = await handle_close(tmp_store, "trader1", "s-abc12345 3600")
        assert "[ERR]" in result


class TestHandleCancel:
    @pytest.mark.asyncio
    async def test_cancel_success(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        result = await handle_cancel(tmp_store, "trader1", "s-abc12345")
        assert "[OK]" in result
        assert "cancelled" in result.lower()

    @pytest.mark.asyncio
    async def test_cancel_wrong_author(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        result = await handle_cancel(tmp_store, "other", "s-abc12345")
        assert "[ERR]" in result


class TestHandleLeaderboard:
    @pytest.mark.asyncio
    async def test_empty(self, tmp_store):
        result = await handle_leaderboard(tmp_store, "anyone", "")
        assert "No signals" in result or "LEADERBOARD" in result

    @pytest.mark.asyncio
    async def test_with_data(self, tmp_store):
        for i in range(3):
            sig = TradingSignal(
                id=f"s-lb{i}",
                author="trader1",
                direction="BUY",
                pair="ETH/USDC",
                entry_price=3500,
                stop_loss=3400,
                take_profit=3700,
                confidence=80,
                timeframe="4H",
                status="tp_hit",
                created_at=datetime.now(timezone.utc).isoformat(),
                closed_at=datetime.now(timezone.utc).isoformat(),
                pnl_percent=3.0 + i,
            )
            tmp_store.add(sig)
        result = await handle_leaderboard(tmp_store, "anyone", "30d")
        assert "trader1" in result
        assert "LEADERBOARD" in result


class TestHandleStats:
    @pytest.mark.asyncio
    async def test_no_signals(self, tmp_store):
        result = await handle_stats(tmp_store, "trader1", "")
        assert "No signals" in result

    @pytest.mark.asyncio
    async def test_with_signals(self, tmp_store, sample_signal):
        sample_signal.status = "tp_hit"
        sample_signal.closed_at = datetime.now(timezone.utc).isoformat()
        sample_signal.pnl_percent = 5.7
        tmp_store.add(sample_signal)
        result = await handle_stats(tmp_store, "anyone", "@trader1")
        assert "trader1" in result
        assert "5.7%" in result


class TestHandleHelp:
    @pytest.mark.asyncio
    async def test_help(self, tmp_store):
        result = await handle_help(tmp_store, "anyone", "")
        assert "!ts signal" in result
        assert "!ts leaderboard" in result


# =========================================================================
# Price monitor
# =========================================================================


class TestPriceMonitor:
    @pytest.mark.asyncio
    async def test_tp_hit_notification(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        monitor = PriceMonitor(tmp_store, AsyncMock())

        with patch("trading_signal_bot.fetch_price", return_value=3700.0):
            notifications = await monitor.check_signals("#test")

        assert len(notifications) == 1
        assert "TP HIT" in notifications[0]
        assert sample_signal.status == "tp_hit"

    @pytest.mark.asyncio
    async def test_sl_hit_notification(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        monitor = PriceMonitor(tmp_store, AsyncMock())

        with patch("trading_signal_bot.fetch_price", return_value=3400.0):
            notifications = await monitor.check_signals("#test")

        assert len(notifications) == 1
        assert "SL HIT" in notifications[0]

    @pytest.mark.asyncio
    async def test_no_notification_within_range(self, tmp_store, sample_signal):
        tmp_store.add(sample_signal)
        monitor = PriceMonitor(tmp_store, AsyncMock())

        with patch("trading_signal_bot.fetch_price", return_value=3550.0):
            notifications = await monitor.check_signals("#test")

        assert len(notifications) == 0
        assert sample_signal.status == "open"

    @pytest.mark.asyncio
    async def test_expired_signal(self, tmp_store, sample_signal):
        sample_signal.created_at = (
            datetime.now(timezone.utc) - timedelta(hours=5)
        ).isoformat()
        tmp_store.add(sample_signal)
        monitor = PriceMonitor(tmp_store, AsyncMock())

        with patch("trading_signal_bot.fetch_price", return_value=3550.0):
            notifications = await monitor.check_signals("#test")

        assert len(notifications) == 1
        assert "EXPIRED" in notifications[0]


# =========================================================================
# Helpers
# =========================================================================


class TestHelpers:
    def test_split_message_short(self):
        assert _split_message("hello", 400) == ["hello"]

    def test_split_message_long(self):
        msg = "a" * 500
        chunks = _split_message(msg, 400)
        assert len(chunks) == 2
        assert len(chunks[0]) == 400
        assert len(chunks[1]) == 100

    def test_format_duration_minutes(self):
        assert _format_duration(1800) == "30m"

    def test_format_duration_hours(self):
        assert _format_duration(7200) == "2.0H"

    def test_format_duration_days(self):
        assert _format_duration(172800) == "2.0D"


class TestCommandRegistration:
    def test_all_commands_registered(self):
        expected = {
            "signal", "open", "history", "detail", "close", "cancel",
            "leaderboard", "stats", "subscribe", "unsubscribe", "subscribers", "help",
        }
        assert set(COMMANDS.keys()) == expected

    def test_all_handlers_callable(self):
        for name, handler in COMMANDS.items():
            assert callable(handler), f"{name} is not callable"


class TestConstants:
    def test_coingecko_ids_has_major_assets(self):
        for asset in ["BTC", "ETH", "SOL", "AVAX"]:
            assert asset in COINGECKO_IDS

    def test_timeframes(self):
        assert "1H" in TIMEFRAME_SECONDS
        assert "4H" in TIMEFRAME_SECONDS
        assert "1D" in TIMEFRAME_SECONDS
        assert "1W" in TIMEFRAME_SECONDS

    def test_subscription_plans_have_required_fields(self):
        for plan_name, (price, label) in SUBSCRIPTION_PLANS.items():
            assert isinstance(price, float)
            assert isinstance(label, str)
            assert price > 0
            assert plan_name in PLAN_DURATION_SECONDS

    def test_revenue_split_totals_100(self):
        assert sum(REVENUE_SPLIT.values()) == 100

    def test_plan_duration_seconds(self):
        assert PLAN_DURATION_SECONDS["daily"] == 86400
        assert PLAN_DURATION_SECONDS["weekly"] == 604800
        assert PLAN_DURATION_SECONDS["monthly"] == 2592000


# ---------------------------------------------------------------------------
# Subscription Store Tests
# ---------------------------------------------------------------------------


class TestSubscriptionStore:
    def test_empty_store(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        assert store.all_subscriptions() == []

    def test_add_subscription(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        sub = store.add_subscription("buyer", "trader1", "daily")
        assert sub["subscriber"] == "buyer"
        assert sub["trader"] == "trader1"
        assert sub["plan"] == "daily"
        assert sub["status"] == "active"
        assert sub["price_usdc"] == 0.50

    def test_cancel_subscription(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        store.add_subscription("buyer", "trader1", "daily")
        assert store.cancel_subscription("buyer", "trader1")
        sub = store.get_subscription("buyer", "trader1")
        assert sub is None  # No longer active

    def test_cancel_nonexistent_returns_false(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        assert store.cancel_subscription("nobody", "trader1") is False

    def test_get_trader_subscribers(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        store.add_subscription("buyer1", "trader1", "daily")
        store.add_subscription("buyer2", "trader1", "weekly")
        store.add_subscription("buyer1", "trader2", "monthly")
        subs = store.get_trader_subscribers("trader1")
        assert len(subs) == 2

    def test_active_subscribers_for(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        store.add_subscription("buyer1", "trader1", "daily")
        store.add_subscription("buyer2", "trader1", "weekly")
        active = store.active_subscribers_for("trader1")
        assert "buyer1" in active
        assert "buyer2" in active

    def test_expire_subscriptions(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        sub = store.add_subscription("buyer1", "trader1", "daily")
        # Manually set expiry to the past
        store._subs[0]["expires_at"] = "2020-01-01T00:00:00+00:00"
        expired = store.expire_subscriptions()
        assert len(expired) == 1
        assert expired[0]["subscriber"] == "buyer1"

    def test_persistence(self, tmp_path):
        store1 = SubscriptionStore(tmp_path)
        store1.add_subscription("buyer", "trader", "weekly")

        store2 = SubscriptionStore(tmp_path)
        assert len(store2.all_subscriptions()) == 1
        assert store2.all_subscriptions()[0]["subscriber"] == "buyer"

    def test_replace_on_duplicate(self, tmp_path):
        store = SubscriptionStore(tmp_path)
        store.add_subscription("buyer", "trader", "daily")
        store.add_subscription("buyer", "trader", "weekly")
        active = [s for s in store.all_subscriptions() if s["status"] == "active"]
        assert len(active) == 1
        assert active[0]["plan"] == "weekly"


# ---------------------------------------------------------------------------
# Copy Trading Command Handler Tests
# ---------------------------------------------------------------------------


class TestHandleSubscribe:
    @pytest.fixture
    def store_with_signals(self, tmp_path):
        store = SignalStore(tmp_path)
        sig = TradingSignal(
            id="s-test01", author="trader1", direction="BUY",
            pair="ETH/USDC", entry_price=3500, stop_loss=3400,
            take_profit=3700, confidence=85, timeframe="4H",
            status="open", created_at=datetime.now(timezone.utc).isoformat(),
        )
        store.add(sig)
        return store

    @pytest.mark.asyncio
    async def test_subscribe_no_args(self, tmp_path):
        store = SignalStore(tmp_path)
        result = await handle_subscribe(store, "buyer", "")
        assert "[ERR]" in result
        assert "Usage" in result

    @pytest.mark.asyncio
    async def test_subscribe_to_self(self, tmp_path):
        store = SignalStore(tmp_path)
        result = await handle_subscribe(store, "trader1", "@trader1")
        assert "[ERR]" in result
        assert "yourself" in result

    @pytest.mark.asyncio
    async def test_subscribe_invalid_plan(self, store_with_signals):
        result = await handle_subscribe(store_with_signals, "buyer", "@trader1 hourly")
        assert "[ERR]" in result
        assert "Invalid plan" in result

    @pytest.mark.asyncio
    async def test_subscribe_no_signals(self, tmp_path):
        store = SignalStore(tmp_path)
        result = await handle_subscribe(store, "buyer", "@trader1")
        assert "[ERR]" in result
        assert "no signals" in result

    @pytest.mark.asyncio
    async def test_subscribe_success(self, store_with_signals):
        result = await handle_subscribe(store_with_signals, "buyer", "@trader1 daily")
        assert "[SUBSCRIBE]" in result
        assert "$0.50" in result
        assert "70% trader" in result

    @pytest.mark.asyncio
    async def test_subscribe_default_plan(self, store_with_signals):
        result = await handle_subscribe(store_with_signals, "buyer", "@trader1")
        assert "[SUBSCRIBE]" in result
        assert "daily" in result


class TestHandleUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribe_no_args(self, tmp_path):
        store = SignalStore(tmp_path)
        result = await handle_unsubscribe(store, "buyer", "")
        assert "[ERR]" in result

    @pytest.mark.asyncio
    async def test_unsubscribe_no_active(self, tmp_path):
        store = SignalStore(tmp_path)
        result = await handle_unsubscribe(store, "buyer", "@trader1")
        assert "[ERR]" in result
        assert "No active" in result

    @pytest.mark.asyncio
    async def test_unsubscribe_with_active(self, tmp_path):
        store = SignalStore(tmp_path)
        sub_store = SubscriptionStore(tmp_path)
        sub_store.add_subscription("buyer", "trader1", "daily")
        store._sub_store = sub_store
        result = await handle_unsubscribe(store, "buyer", "@trader1")
        assert "[OK]" in result
        assert "Unsubscribed" in result


class TestHandleSubscribers:
    @pytest.mark.asyncio
    async def test_no_sub_store(self, tmp_path):
        store = SignalStore(tmp_path)
        result = await handle_subscribers(store, "trader1", "")
        assert "0 subscribers" in result

    @pytest.mark.asyncio
    async def test_with_subscribers(self, tmp_path):
        store = SignalStore(tmp_path)
        sub_store = SubscriptionStore(tmp_path)
        sub_store.add_subscription("buyer1", "trader1", "daily")
        sub_store.add_subscription("buyer2", "trader1", "weekly")
        store._sub_store = sub_store
        result = await handle_subscribers(store, "trader1", "")
        assert "2 subscribers" in result or "2 active" in result
