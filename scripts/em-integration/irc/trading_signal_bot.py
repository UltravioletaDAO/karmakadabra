"""
Karma Kadabra V2 — Phase 3: Trading Signal Tracker Bot

IRC bot that tracks trading signals, monitors P&L, maintains a
leaderboard, and auto-closes signals when TP/SL is hit.

Signals are published as [SIGNAL] messages or via !ts commands.
The bot polls CoinGecko for price updates every 60 seconds.

Commands:
  !ts signal BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 4H
  !ts open [@nick]           — List open signals
  !ts history [limit]        — Recent closed signals
  !ts detail <signal_id>     — Signal details
  !ts close <signal_id> [price]  — Manually close a signal
  !ts cancel <signal_id>     — Cancel a signal (no P&L)
  !ts leaderboard [period]   — Top traders (7d, 30d, all)
  !ts stats [@nick]          — Trader performance stats
  !ts help                   — Show commands

Usage:
  python trading_signal_bot.py
  python trading_signal_bot.py --channel "#kk-alpha"
  python trading_signal_bot.py --price-interval 60 --duration 3600
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Ensure sibling packages are importable
_kk_root = Path(__file__).parent.parent
sys.path.insert(0, str(_kk_root / "irc"))
sys.path.insert(0, str(_kk_root / "lib"))

from agent_irc_client import IRC_PORT, IRC_SERVER, PING_INTERVAL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.trading-signals")

NICK = "kk-trading"
DEFAULT_CHANNELS = ["#Agents"]
MAX_MSG_LEN = 400
PRICE_POLL_INTERVAL = 60  # seconds
RATE_LIMIT_SIGNALS = 5
RATE_LIMIT_SIGNAL_WINDOW = 3600  # 1 hour
RATE_LIMIT_COMMANDS = 10
RATE_LIMIT_CMD_WINDOW = 60  # seconds

# Copy trading subscription plans: plan -> (price_usdc, label)
SUBSCRIPTION_PLANS: dict[str, tuple[float, str]] = {
    "daily": (0.50, "1 day"),
    "weekly": (2.00, "7 days"),
    "monthly": (5.00, "30 days"),
}

# Revenue split percentages
REVENUE_SPLIT = {
    "trader": 70,
    "meshrelay": 20,
    "em_treasury": 10,
}

# Plan duration in seconds
PLAN_DURATION_SECONDS: dict[str, int] = {
    "daily": 86400,
    "weekly": 604800,
    "monthly": 2592000,
}

# CoinGecko ID mapping for common pairs
COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "POL": "matic-network",
    "ARB": "arbitrum",
    "OP": "optimism",
    "CELO": "celo",
    "MONAD": "monad",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "AAVE": "aave",
    "CRV": "curve-dao-token",
    "MKR": "maker",
    "SNX": "havven",
    "DOGE": "dogecoin",
    "PEPE": "pepe",
}

# Timeframe to seconds mapping
TIMEFRAME_SECONDS: dict[str, int] = {
    "1H": 3600,
    "4H": 14400,
    "1D": 86400,
    "1W": 604800,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TradingSignal:
    id: str
    author: str
    direction: str  # BUY or SELL
    pair: str  # e.g. ETH/USDC
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: int  # 0-100
    timeframe: str  # 1H, 4H, 1D, 1W
    status: str  # open, tp_hit, sl_hit, closed, cancelled, expired
    created_at: str
    closed_at: str | None = None
    close_price: float | None = None
    pnl_percent: float | None = None
    close_reason: str | None = None

    def base_asset(self) -> str:
        """Return the base asset of the pair (e.g. ETH from ETH/USDC)."""
        return self.pair.split("/")[0].upper()

    def calc_pnl(self, current_price: float) -> float:
        """Calculate P&L percentage at given price."""
        if self.direction == "BUY":
            return ((current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100

    def check_tp_sl(self, current_price: float) -> str | None:
        """Check if TP or SL was hit. Returns 'tp_hit', 'sl_hit', or None."""
        if self.direction == "BUY":
            if current_price >= self.take_profit:
                return "tp_hit"
            if current_price <= self.stop_loss:
                return "sl_hit"
        else:
            if current_price <= self.take_profit:
                return "tp_hit"
            if current_price >= self.stop_loss:
                return "sl_hit"
        return None

    def is_expired(self) -> bool:
        """Check if signal has expired based on timeframe."""
        created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        duration = TIMEFRAME_SECONDS.get(self.timeframe, 14400)
        return (datetime.now(timezone.utc) - created).total_seconds() > duration


@dataclass
class TraderStats:
    nick: str
    total_signals: int = 0
    wins: int = 0
    losses: int = 0
    open_count: int = 0
    expired: int = 0
    cancelled: int = 0
    avg_pnl: float = 0.0
    total_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    current_streak: int = 0
    longest_streak: int = 0


# ---------------------------------------------------------------------------
# Signal store (JSON file persistence)
# ---------------------------------------------------------------------------


class SignalStore:
    """Persist signals to JSON files."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "trading_signals"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._signals: dict[str, TradingSignal] = {}
        self._load()

    def _signals_file(self) -> Path:
        return self.data_dir / "signals.json"

    def _load(self) -> None:
        path = self._signals_file()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for s in data:
                sig = TradingSignal(**s)
                self._signals[sig.id] = sig
            logger.info(f"  Loaded {len(self._signals)} signals from disk")
        except Exception as e:
            logger.warning(f"  Failed to load signals: {e}")

    def _save(self) -> None:
        data = [asdict(s) for s in self._signals.values()]
        self._signals_file().write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    def add(self, signal: TradingSignal) -> None:
        self._signals[signal.id] = signal
        self._save()

    def get(self, signal_id: str) -> TradingSignal | None:
        # Support short IDs
        if signal_id in self._signals:
            return self._signals[signal_id]
        matches = [s for sid, s in self._signals.items() if sid.startswith(signal_id)]
        return matches[0] if len(matches) == 1 else None

    def update(self, signal: TradingSignal) -> None:
        self._signals[signal.id] = signal
        self._save()

    def open_signals(self, author: str | None = None) -> list[TradingSignal]:
        sigs = [s for s in self._signals.values() if s.status == "open"]
        if author:
            sigs = [s for s in sigs if s.author == author]
        return sorted(sigs, key=lambda s: s.created_at, reverse=True)

    def closed_signals(self, limit: int = 10) -> list[TradingSignal]:
        closed = [
            s
            for s in self._signals.values()
            if s.status in ("tp_hit", "sl_hit", "closed", "expired")
        ]
        return sorted(closed, key=lambda s: s.closed_at or "", reverse=True)[:limit]

    def signals_by_author(
        self, author: str, since: float | None = None
    ) -> list[TradingSignal]:
        sigs = [s for s in self._signals.values() if s.author == author]
        if since:
            cutoff = datetime.fromtimestamp(since, tz=timezone.utc).isoformat()
            sigs = [s for s in sigs if s.created_at >= cutoff]
        return sigs

    def all_authors(self) -> set[str]:
        return {s.author for s in self._signals.values()}


# ---------------------------------------------------------------------------
# Subscription store (JSON file persistence for copy trading)
# ---------------------------------------------------------------------------


class SubscriptionStore:
    """Persist copy trading subscriptions to JSON files."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "trading_signals"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._subs: list[dict] = []
        self._load()

    def _subs_file(self) -> Path:
        return self.data_dir / "subscriptions.json"

    def _load(self) -> None:
        path = self._subs_file()
        if not path.exists():
            return
        try:
            self._subs = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"  Loaded {len(self._subs)} subscriptions from disk")
        except Exception as e:
            logger.warning(f"  Failed to load subscriptions: {e}")

    def _save(self) -> None:
        self._subs_file().write_text(
            json.dumps(self._subs, indent=2, default=str), encoding="utf-8"
        )

    def add_subscription(
        self, subscriber: str, trader: str, plan: str
    ) -> dict:
        """Add or renew a subscription."""
        now = datetime.now(timezone.utc).isoformat()
        duration = PLAN_DURATION_SECONDS.get(plan, 86400)
        price, _ = SUBSCRIPTION_PLANS.get(plan, (0.50, "1 day"))

        # Cancel any existing active sub
        for s in self._subs:
            if (
                s["subscriber"] == subscriber
                and s["trader"] == trader
                and s["status"] == "active"
            ):
                s["status"] = "replaced"

        sub = {
            "subscriber": subscriber,
            "trader": trader,
            "plan": plan,
            "price_usdc": price,
            "status": "active",
            "created_at": now,
            "expires_at": datetime.fromtimestamp(
                time.time() + duration, tz=timezone.utc
            ).isoformat(),
        }
        self._subs.append(sub)
        self._save()
        return sub

    def cancel_subscription(self, subscriber: str, trader: str) -> bool:
        """Cancel an active subscription."""
        for s in self._subs:
            if (
                s["subscriber"] == subscriber
                and s["trader"] == trader
                and s["status"] == "active"
            ):
                s["status"] = "cancelled"
                s["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                self._save()
                return True
        return False

    def get_subscription(
        self, subscriber: str, trader: str
    ) -> dict | None:
        """Get active subscription between subscriber and trader."""
        for s in self._subs:
            if (
                s["subscriber"] == subscriber
                and s["trader"] == trader
                and s["status"] == "active"
            ):
                return s
        return None

    def get_trader_subscribers(self, trader: str) -> list[dict]:
        """Get all subscriptions for a trader."""
        return [s for s in self._subs if s["trader"] == trader]

    def active_subscribers_for(self, trader: str) -> list[str]:
        """Get list of active subscriber nicks for a trader."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            s["subscriber"]
            for s in self._subs
            if s["trader"] == trader
            and s["status"] == "active"
            and s.get("expires_at", "") > now
        ]

    def expire_subscriptions(self) -> list[dict]:
        """Mark expired subscriptions. Returns list of newly expired."""
        now = datetime.now(timezone.utc).isoformat()
        expired = []
        for s in self._subs:
            if s["status"] == "active" and s.get("expires_at", "") <= now:
                s["status"] = "expired"
                expired.append(s)
        if expired:
            self._save()
        return expired

    def all_subscriptions(self) -> list[dict]:
        return list(self._subs)


# ---------------------------------------------------------------------------
# Signal parsing
# ---------------------------------------------------------------------------

# [SIGNAL] BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 4H
_SIGNAL_RE = re.compile(
    r"\[SIGNAL\]\s+(BUY|SELL)\s+(\S+)\s+@\s*([\d.]+)"
    r"\s*\|\s*SL:\s*([\d.]+)"
    r"\s*\|\s*TP:\s*([\d.]+)"
    r"(?:\s*\|\s*(\d+)%)?"
    r"(?:\s*\|\s*(\w+))?",
    re.IGNORECASE,
)


def parse_signal(text: str) -> TradingSignal | None:
    """Parse a [SIGNAL] message or !ts signal command into a TradingSignal.

    Returns None if the message doesn't match the signal format.
    """
    # Strip !ts signal prefix if present
    stripped = text.strip()
    if stripped.lower().startswith("!ts signal "):
        stripped = "[SIGNAL] " + stripped[11:]

    m = _SIGNAL_RE.search(stripped)
    if not m:
        return None

    direction = m.group(1).upper()
    pair = m.group(2).upper()
    entry = float(m.group(3))
    sl = float(m.group(4))
    tp = float(m.group(5))
    confidence = int(m.group(6)) if m.group(6) else 50
    timeframe = (m.group(7) or "4H").upper()

    # Validate
    if confidence < 1 or confidence > 100:
        return None
    if timeframe not in TIMEFRAME_SECONDS:
        return None
    if entry <= 0 or sl <= 0 or tp <= 0:
        return None

    # Validate SL/TP relative to direction
    if direction == "BUY" and (sl >= entry or tp <= entry):
        return None
    if direction == "SELL" and (sl <= entry or tp >= entry):
        return None

    short_id = "s-" + uuid.uuid4().hex[:8]
    return TradingSignal(
        id=short_id,
        author="",  # Set by caller
        direction=direction,
        pair=pair,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
        confidence=confidence,
        timeframe=timeframe,
        status="open",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------


def parse_command(message: str) -> tuple[str, str]:
    """Parse an IRC message into (command, arguments).

    Returns ("", "") if not a trading signal command.
    Also detects raw [SIGNAL] messages as ("_raw_signal", full_message).
    """
    msg = message.strip()

    # Detect raw [SIGNAL] messages from traders
    if msg.upper().startswith("[SIGNAL]"):
        return ("_raw_signal", msg)

    # !ts prefix
    if not (msg.lower().startswith("!ts ") or msg.lower() == "!ts"):
        return ("", "")

    rest = msg[3:].strip()
    if not rest:
        return ("help", "")

    parts = rest.split(None, 1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""

    return (command, argument)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_signal_buckets: dict[str, list[float]] = {}
_cmd_buckets: dict[str, list[float]] = {}


def check_signal_rate(nick: str) -> bool:
    """Check if nick can publish a new signal."""
    now = time.time()
    if nick not in _signal_buckets:
        _signal_buckets[nick] = []
    _signal_buckets[nick] = [
        t for t in _signal_buckets[nick] if now - t < RATE_LIMIT_SIGNAL_WINDOW
    ]
    if len(_signal_buckets[nick]) >= RATE_LIMIT_SIGNALS:
        return False
    _signal_buckets[nick].append(now)
    return True


def check_cmd_rate(nick: str) -> bool:
    """Check if nick can send a command."""
    now = time.time()
    if nick not in _cmd_buckets:
        _cmd_buckets[nick] = []
    _cmd_buckets[nick] = [
        t for t in _cmd_buckets[nick] if now - t < RATE_LIMIT_CMD_WINDOW
    ]
    if len(_cmd_buckets[nick]) >= RATE_LIMIT_COMMANDS:
        return False
    _cmd_buckets[nick].append(now)
    return True


# ---------------------------------------------------------------------------
# Price fetching
# ---------------------------------------------------------------------------


async def fetch_price(asset: str, http_client=None) -> float | None:
    """Fetch current USD price for an asset via CoinGecko.

    Returns None if the asset is not found or the API fails.
    """
    cg_id = COINGECKO_IDS.get(asset.upper())
    if not cg_id:
        return None

    try:
        import httpx

        client = http_client or httpx.AsyncClient(timeout=10)
        close_after = http_client is None

        resp = await client.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": cg_id, "vs_currencies": "usd"},
        )

        if close_after:
            await client.aclose()

        if resp.status_code == 200:
            data = resp.json()
            return data.get(cg_id, {}).get("usd")
    except Exception as e:
        logger.debug(f"  Price fetch failed for {asset}: {e}")

    return None


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------


def compute_stats(
    signals: list[TradingSignal], nick: str | None = None
) -> TraderStats:
    """Compute performance statistics from a list of signals."""
    stats = TraderStats(nick=nick or "all")

    pnls = []
    streak = 0
    longest = 0

    for s in sorted(signals, key=lambda x: x.created_at):
        stats.total_signals += 1

        if s.status == "open":
            stats.open_count += 1
            continue
        if s.status == "cancelled":
            stats.cancelled += 1
            continue
        if s.status == "expired":
            stats.expired += 1

        pnl = s.pnl_percent or 0.0
        pnls.append(pnl)

        if s.status == "tp_hit" or (s.pnl_percent is not None and s.pnl_percent > 0):
            stats.wins += 1
            streak += 1
            longest = max(longest, streak)
        elif s.status == "sl_hit" or (
            s.pnl_percent is not None and s.pnl_percent <= 0
        ):
            stats.losses += 1
            streak = 0

        if pnl > stats.best_trade:
            stats.best_trade = pnl
        if pnl < stats.worst_trade:
            stats.worst_trade = pnl

    stats.current_streak = streak
    stats.longest_streak = longest
    stats.total_pnl = sum(pnls)
    stats.avg_pnl = stats.total_pnl / len(pnls) if pnls else 0.0

    return stats


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def handle_signal(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts signal or raw [SIGNAL] message."""
    if not check_signal_rate(nick):
        return "[ERR] Signal rate limit: max 5 signals per hour"

    sig = parse_signal(args)
    if not sig:
        return "[ERR] Invalid signal. Format: !ts signal BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 4H"

    sig.author = nick
    store.add(sig)

    return (
        f"[OK] Signal {sig.id}: {sig.direction} {sig.pair} @ {sig.entry_price} | "
        f"SL: {sig.stop_loss} | TP: {sig.take_profit} | {sig.confidence}% {sig.timeframe}"
    )


async def handle_open(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts open [@nick]"""
    author = args.lstrip("@").strip() if args else None
    signals = store.open_signals(author=author)

    if not signals:
        label = f"by @{author}" if author else ""
        return f"[SIGNALS] No open signals {label}"

    lines = [f"[SIGNALS] {len(signals)} open:"]
    for s in signals[:5]:
        lines.append(
            f"  {s.id} {s.direction} {s.pair} @ {s.entry_price} | "
            f"TP: {s.take_profit} SL: {s.stop_loss} | {s.confidence}% {s.timeframe} | @{s.author}"
        )

    return " | ".join(lines) if len(" | ".join(lines)) <= MAX_MSG_LEN else "\n".join(lines)


async def handle_history(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts history [limit]"""
    limit = 5
    if args:
        try:
            limit = min(int(args), 10)
        except ValueError:
            pass

    signals = store.closed_signals(limit=limit)
    if not signals:
        return "[HISTORY] No closed signals yet"

    lines = [f"[HISTORY] Last {len(signals)} closed:"]
    for s in signals:
        pnl = f"{s.pnl_percent:+.1f}%" if s.pnl_percent is not None else "?"
        emoji = "W" if (s.pnl_percent or 0) > 0 else "L"
        lines.append(f"  {s.id} {s.pair} {emoji} {pnl} | {s.close_reason or s.status} | @{s.author}")

    return " | ".join(lines) if len(" | ".join(lines)) <= MAX_MSG_LEN else "\n".join(lines)


async def handle_detail(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts detail <signal_id>"""
    if not args:
        return "[ERR] Usage: !ts detail <signal_id>"

    sig = store.get(args.split()[0])
    if not sig:
        return f"[ERR] Signal not found: {args.split()[0]}"

    pnl = f"{sig.pnl_percent:+.1f}%" if sig.pnl_percent is not None else "live"
    return (
        f"[SIGNAL] {sig.id} | {sig.direction} {sig.pair} @ {sig.entry_price} | "
        f"TP: {sig.take_profit} SL: {sig.stop_loss} | {sig.confidence}% {sig.timeframe} | "
        f"Status: {sig.status} | P&L: {pnl} | @{sig.author}"
    )


async def handle_close(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts close <signal_id> [price]"""
    parts = args.split() if args else []
    if not parts:
        return "[ERR] Usage: !ts close <signal_id> [price]"

    sig = store.get(parts[0])
    if not sig:
        return f"[ERR] Signal not found: {parts[0]}"
    if sig.author != nick:
        return f"[ERR] Only @{sig.author} can close this signal"
    if sig.status != "open":
        return f"[ERR] Signal already {sig.status}"

    # Use provided price or try to fetch
    close_price = None
    if len(parts) > 1:
        try:
            close_price = float(parts[1])
        except ValueError:
            return f"[ERR] Invalid price: {parts[1]}"

    if close_price is None:
        close_price = await fetch_price(sig.base_asset())

    if close_price is None:
        return "[ERR] Could not determine close price. Provide it: !ts close <id> <price>"

    sig.status = "closed"
    sig.close_price = close_price
    sig.pnl_percent = sig.calc_pnl(close_price)
    sig.closed_at = datetime.now(timezone.utc).isoformat()
    sig.close_reason = "manual"
    store.update(sig)

    return (
        f"[SIGNAL-CLOSE] {sig.pair} closed @ {close_price} | "
        f"P&L: {sig.pnl_percent:+.1f}% | by @{sig.author}"
    )


async def handle_cancel(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts cancel <signal_id>"""
    if not args:
        return "[ERR] Usage: !ts cancel <signal_id>"

    sig = store.get(args.split()[0])
    if not sig:
        return f"[ERR] Signal not found: {args.split()[0]}"
    if sig.author != nick:
        return f"[ERR] Only @{sig.author} can cancel this signal"
    if sig.status != "open":
        return f"[ERR] Signal already {sig.status}"

    sig.status = "cancelled"
    sig.closed_at = datetime.now(timezone.utc).isoformat()
    sig.close_reason = "cancelled"
    store.update(sig)

    return f"[OK] Signal {sig.id} cancelled (no P&L recorded)"


async def handle_leaderboard(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts leaderboard [period]"""
    period = args.strip().lower() if args else "30d"
    period_map = {"7d": 7, "30d": 30, "all": 9999}
    days = period_map.get(period, 30)
    since = time.time() - (days * 86400) if days < 9999 else None

    authors = store.all_authors()
    if not authors:
        return "[LEADERBOARD] No signals recorded yet"

    stats_list = []
    for author in authors:
        sigs = store.signals_by_author(author, since=since)
        if not sigs:
            continue
        st = compute_stats(sigs, nick=author)
        if st.total_signals - st.open_count - st.cancelled > 0:
            st_wr = (
                st.wins / (st.wins + st.losses) * 100
                if (st.wins + st.losses) > 0
                else 0
            )
            stats_list.append((st, st_wr))

    if not stats_list:
        return f"[LEADERBOARD] No closed signals in {period}"

    stats_list.sort(key=lambda x: x[0].total_pnl, reverse=True)

    lines = [f"[LEADERBOARD] Top 5 ({period}):"]
    for i, (st, wr) in enumerate(stats_list[:5], 1):
        lines.append(
            f"  {i}. @{st.nick} | Win: {wr:.0f}% | "
            f"Avg: {st.avg_pnl:+.1f}% | {st.total_signals} sigs | "
            f"Total: {st.total_pnl:+.1f}%"
        )

    return " | ".join(lines) if len(" | ".join(lines)) <= MAX_MSG_LEN else "\n".join(lines)


async def handle_stats(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts stats [@nick]"""
    target = args.lstrip("@").strip() if args else nick

    sigs = store.signals_by_author(target)
    if not sigs:
        return f"[STATS] No signals from @{target}"

    st = compute_stats(sigs, nick=target)
    closed = st.wins + st.losses + st.expired
    wr = st.wins / (st.wins + st.losses) * 100 if (st.wins + st.losses) > 0 else 0

    return (
        f"[STATS] @{target}: "
        f"{st.total_signals} signals ({closed} closed, {st.open_count} open) | "
        f"Win: {wr:.0f}% | Avg: {st.avg_pnl:+.1f}% | "
        f"Best: {st.best_trade:+.1f}% | Worst: {st.worst_trade:+.1f}% | "
        f"Total: {st.total_pnl:+.1f}% | Streak: {st.current_streak}W"
    )


async def handle_help(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts help"""
    return (
        "Trading Signal commands: "
        "!ts signal BUY ETH/USDC @ 3500 | SL: 3400 | TP: 3700 | 85% | 4H -- publish | "
        "!ts open -- open signals | "
        "!ts history -- closed signals | "
        "!ts detail <id> -- signal info | "
        "!ts close <id> [price] -- close signal | "
        "!ts leaderboard [7d|30d|all] -- top traders | "
        "!ts stats [@nick] -- performance | "
        "!ts subscribe @nick [daily|weekly|monthly] -- copy trading | "
        "!ts unsubscribe @nick | "
        "!ts subscribers -- your sub count | "
        "!ts help"
    )


async def handle_subscribe(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts subscribe @trader [daily|weekly|monthly]"""
    parts = args.split() if args else []
    if not parts:
        return (
            "[ERR] Usage: !ts subscribe @trader [daily|weekly|monthly] — "
            "daily $0.50 | weekly $2.00 | monthly $5.00"
        )

    trader = parts[0].lstrip("@").strip()
    if not trader:
        return "[ERR] Must specify a trader nick"
    if trader == nick:
        return "[ERR] Cannot subscribe to yourself"

    plan = parts[1].lower() if len(parts) > 1 else "daily"
    if plan not in SUBSCRIPTION_PLANS:
        return f"[ERR] Invalid plan: {plan}. Options: daily, weekly, monthly"

    price, duration_label = SUBSCRIPTION_PLANS[plan]

    # Check if trader has signals
    sigs = store.signals_by_author(trader)
    if not sigs:
        return f"[ERR] @{trader} has no signals — nothing to subscribe to"

    # Check existing subscription
    sub_store = getattr(store, "_sub_store", None)
    if sub_store:
        existing = sub_store.get_subscription(nick, trader)
        if existing and existing.get("status") == "active":
            return f"[ERR] Already subscribed to @{trader} ({existing.get('plan', '?')})"

    return (
        f"[SUBSCRIBE] To subscribe to @{trader}'s signals ({plan} = ${price:.2f} USDC):\n"
        f"  Pay via Turnstile in #abra-alpha or send ${price:.2f} USDC to MeshRelay treasury.\n"
        f"  After payment, signals from @{trader} will be DM'd to you.\n"
        f"  Revenue split: 70% trader / 20% MeshRelay / 10% EM treasury"
    )


async def handle_unsubscribe(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts unsubscribe @trader"""
    if not args:
        return "[ERR] Usage: !ts unsubscribe @trader"

    trader = args.split()[0].lstrip("@").strip()
    if not trader:
        return "[ERR] Must specify a trader nick"

    sub_store = getattr(store, "_sub_store", None)
    if sub_store:
        existing = sub_store.get_subscription(nick, trader)
        if existing and existing.get("status") == "active":
            sub_store.cancel_subscription(nick, trader)
            return f"[OK] Unsubscribed from @{trader}. No further signals will be DM'd."

    return f"[ERR] No active subscription to @{trader}"


async def handle_subscribers(store: SignalStore, nick: str, args: str) -> str:
    """Handle !ts subscribers — show your subscriber count (for traders)"""
    sub_store = getattr(store, "_sub_store", None)
    if not sub_store:
        return f"[SUBS] @{nick}: 0 subscribers (copy trading not yet active)"

    subs = sub_store.get_trader_subscribers(nick)
    active = [s for s in subs if s.get("status") == "active"]
    if not active:
        return f"[SUBS] @{nick}: 0 active subscribers"

    plans = {}
    for s in active:
        p = s.get("plan", "daily")
        plans[p] = plans.get(p, 0) + 1

    plan_str = " | ".join(f"{v}x {k}" for k, v in sorted(plans.items()))
    return f"[SUBS] @{nick}: {len(active)} subscribers ({plan_str})"


COMMANDS: dict[str, callable] = {
    "signal": handle_signal,
    "open": handle_open,
    "history": handle_history,
    "detail": handle_detail,
    "close": handle_close,
    "cancel": handle_cancel,
    "leaderboard": handle_leaderboard,
    "stats": handle_stats,
    "subscribe": handle_subscribe,
    "unsubscribe": handle_unsubscribe,
    "subscribers": handle_subscribers,
    "help": handle_help,
}


# ---------------------------------------------------------------------------
# Price monitor
# ---------------------------------------------------------------------------


class PriceMonitor:
    """Polls prices and closes signals when TP/SL is hit."""

    def __init__(self, store: SignalStore, send_fn):
        self.store = store
        self.send_fn = send_fn  # async fn(channel, message)
        self._http = None

    async def check_signals(self, notify_channel: str) -> list[str]:
        """Check all open signals against current prices.

        Returns list of notification strings for any signals that closed.
        """
        import httpx

        if self._http is None:
            self._http = httpx.AsyncClient(timeout=10)

        notifications = []
        open_sigs = self.store.open_signals()

        # Batch price lookups by asset
        assets = {s.base_asset() for s in open_sigs}
        prices: dict[str, float] = {}

        for asset in assets:
            price = await fetch_price(asset, http_client=self._http)
            if price is not None:
                prices[asset] = price

        now_iso = datetime.now(timezone.utc).isoformat()

        for sig in open_sigs:
            asset = sig.base_asset()

            # Check expiry
            if sig.is_expired():
                price = prices.get(asset)
                sig.status = "expired"
                sig.closed_at = now_iso
                sig.close_price = price
                sig.pnl_percent = sig.calc_pnl(price) if price else 0.0
                sig.close_reason = "expired"
                self.store.update(sig)
                pnl_str = f"{sig.pnl_percent:+.1f}%" if price else "?"
                notifications.append(
                    f"[SIGNAL-EXPIRED] {sig.pair} expired @ {price or '?'} | "
                    f"P&L: {pnl_str} | {sig.timeframe} | by @{sig.author}"
                )
                continue

            # Check TP/SL
            price = prices.get(asset)
            if price is None:
                continue

            result = sig.check_tp_sl(price)
            if result:
                sig.status = result
                sig.close_price = price
                sig.pnl_percent = sig.calc_pnl(price)
                sig.closed_at = now_iso
                sig.close_reason = result
                self.store.update(sig)

                label = "TP HIT" if result == "tp_hit" else "SL HIT"
                created = datetime.fromisoformat(
                    sig.created_at.replace("Z", "+00:00")
                )
                duration_s = (datetime.now(timezone.utc) - created).total_seconds()
                duration = _format_duration(duration_s)

                notifications.append(
                    f"[SIGNAL-UPDATE] {sig.pair} {label} @ {price} | "
                    f"P&L: {sig.pnl_percent:+.1f}% | Duration: {duration} | by @{sig.author}"
                )

        return notifications

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()


def _format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}H"
    return f"{seconds / 86400:.1f}D"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    """Split a long message into IRC-safe chunks."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks


# ---------------------------------------------------------------------------
# IRC Bot
# ---------------------------------------------------------------------------


class TradingSignalBot:
    """IRC bot that tracks trading signals and maintains a leaderboard."""

    def __init__(
        self,
        nick: str,
        channels: list[str],
        store: SignalStore,
        sub_store: SubscriptionStore | None = None,
        price_interval: int = PRICE_POLL_INTERVAL,
    ):
        self.nick = nick
        self.channels = channels
        self.store = store
        self.sub_store = sub_store
        self.price_interval = price_interval
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._running = True
        self._monitor = PriceMonitor(store, self.send_message)
        # Attach sub_store to signal store so handlers can access it
        if sub_store:
            self.store._sub_store = sub_store  # type: ignore[attr-defined]

    async def connect(self) -> None:
        logger.info(f"  [{self.nick}] Connecting to {IRC_SERVER}:{IRC_PORT}...")
        self._reader, self._writer = await asyncio.open_connection(IRC_SERVER, IRC_PORT)

        await self._send(f"NICK {self.nick}")
        await self._send(
            f"USER {self.nick} 0 * :KK Trading Signal Bot - Ultravioleta DAO"
        )

        while True:
            line = await self._recv()
            if not line:
                break
            if " 001 " in line:
                self._connected = True
                logger.info(f"  [{self.nick}] Connected!")
                break
            if " 433 " in line:
                self.nick = self.nick + "_"
                logger.warning(f"  Nick in use, retrying as {self.nick}")
                await self._send(f"NICK {self.nick}")
            if "PING" in line:
                await self._handle_ping(line)

        for channel in self.channels:
            await self._send(f"JOIN {channel}")
            logger.info(f"  [{self.nick}] Joined {channel}")

    async def _send(self, msg: str) -> None:
        if self._writer:
            self._writer.write(f"{msg}\r\n".encode("utf-8"))
            await self._writer.drain()

    async def _recv(self) -> str:
        if self._reader:
            try:
                data = await asyncio.wait_for(
                    self._reader.readline(), timeout=PING_INTERVAL + 30
                )
                return data.decode("utf-8", errors="replace").strip()
            except asyncio.TimeoutError:
                return ""
        return ""

    async def _handle_ping(self, line: str) -> None:
        token = line.split("PING ")[-1] if "PING " in line else ":server"
        await self._send(f"PONG {token}")

    async def send_message(self, target: str, message: str) -> None:
        for chunk in _split_message(message, MAX_MSG_LEN):
            await self._send(f"PRIVMSG {target} :{chunk}")

    async def run(self) -> None:
        listener = asyncio.create_task(self._listen())
        poller = asyncio.create_task(self._price_loop())

        try:
            await asyncio.gather(listener, poller)
        except asyncio.CancelledError:
            pass

    async def _listen(self) -> None:
        logger.info(f"  [{self.nick}] Listening for !ts commands and [SIGNAL] messages...")

        while self._running and self._connected:
            line = await self._recv()
            if not line:
                await self._send(f"PING :keepalive-{int(time.time())}")
                continue

            if line.startswith("PING"):
                await self._handle_ping(line)
                continue

            if "PRIVMSG" in line:
                try:
                    prefix, _, rest = line.partition(" PRIVMSG ")
                    sender = prefix.split("!")[0].lstrip(":")
                    channel, _, message = rest.partition(" :")
                    await self._handle_message(sender, channel, message)
                except Exception as e:
                    logger.error(f"  Message handling error: {e}")

    async def _handle_message(self, sender: str, channel: str, message: str) -> None:
        if sender == self.nick:
            return

        command, argument = parse_command(message)
        if not command:
            return

        logger.info(f"  [{self.nick}] From {sender}: {command} {argument[:80]}")

        # Handle raw [SIGNAL] messages
        if command == "_raw_signal":
            if not check_signal_rate(sender):
                return  # Silent rate limit for raw signals
            sig = parse_signal(argument)
            if sig:
                sig.author = sender
                self.store.add(sig)
                await self.send_message(
                    channel,
                    f"[OK] Signal tracked: {sig.id} {sig.direction} {sig.pair} @ {sig.entry_price}",
                )
                # Forward to copy trading subscribers
                await self._notify_subscribers(sig)
            return

        # Rate limit commands
        if not check_cmd_rate(sender):
            await self.send_message(
                channel, f"{sender}: [ERR] Rate limit -- max 10 commands/minute"
            )
            return

        handler = COMMANDS.get(command)
        if not handler:
            await self.send_message(
                channel, f"{sender}: [ERR] Unknown: {command}. Try: !ts help"
            )
            return

        response = await handler(self.store, sender, argument)
        if len(response) > MAX_MSG_LEN:
            response = response[: MAX_MSG_LEN - 3] + "..."
        await self.send_message(channel, f"{sender}: {response}")

        # Forward to subscribers if this was a signal command
        if command == "signal" and response.startswith("[OK] Signal"):
            open_sigs = self.store.open_signals(author=sender)
            if open_sigs:
                await self._notify_subscribers(open_sigs[0])

    async def _notify_subscribers(self, sig: TradingSignal) -> None:
        """DM all active subscribers when a trader publishes a signal."""
        if not self.sub_store:
            return
        subscribers = self.sub_store.active_subscribers_for(sig.author)
        if not subscribers:
            return

        dm_msg = (
            f"[COPY-SIGNAL] @{sig.author}: {sig.direction} {sig.pair} @ {sig.entry_price} | "
            f"SL: {sig.stop_loss} | TP: {sig.take_profit} | {sig.confidence}% {sig.timeframe}"
        )
        for sub_nick in subscribers:
            try:
                await self.send_message(sub_nick, dm_msg)
                logger.info(f"  DM signal to subscriber {sub_nick}")
            except Exception as e:
                logger.debug(f"  Failed to DM {sub_nick}: {e}")
            await asyncio.sleep(0.3)

    async def _price_loop(self) -> None:
        """Periodically check prices and close signals."""
        # Wait for first price check
        await asyncio.sleep(10)

        while self._running:
            if self._connected:
                try:
                    notifications = await self._monitor.check_signals(
                        self.channels[0]
                    )
                    for notif in notifications:
                        for ch in self.channels:
                            await self.send_message(ch, notif)
                            await asyncio.sleep(0.5)
                except Exception as e:
                    logger.debug(f"  Price check error: {e}")

            await asyncio.sleep(self.price_interval)

    async def disconnect(self) -> None:
        self._running = False
        await self._monitor.close()
        if self._writer:
            await self._send("QUIT :Trading Signal Bot signing off")
            self._writer.close()
        logger.info(f"  [{self.nick}] Disconnected")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="Trading Signal Bot")
    parser.add_argument(
        "--channel", type=str, action="append", help="IRC channels (default: #Agents)"
    )
    parser.add_argument(
        "--nick", type=str, default=NICK, help=f"IRC nickname (default: {NICK})"
    )
    parser.add_argument(
        "--price-interval",
        type=int,
        default=PRICE_POLL_INTERVAL,
        help=f"Price poll interval seconds (default: {PRICE_POLL_INTERVAL})",
    )
    parser.add_argument(
        "--data-dir", type=str, default=None, help="Data directory for signal storage"
    )
    parser.add_argument(
        "--duration", type=int, default=0, help="Run duration seconds (0=forever)"
    )
    args = parser.parse_args()

    channels = args.channel or DEFAULT_CHANNELS
    data_dir = Path(args.data_dir) if args.data_dir else _kk_root / "data"

    print(f"\n{'=' * 60}")
    print(f"  Trading Signal Bot")
    print(f"  Nick: {args.nick}")
    print(f"  Server: {IRC_SERVER}")
    print(f"  Channels: {', '.join(channels)}")
    print(f"  Price poll: every {args.price_interval}s")
    print(f"  Data: {data_dir}")
    print(f"{'=' * 60}\n")

    store = SignalStore(data_dir)
    sub_store = SubscriptionStore(data_dir)
    open_count = len(store.open_signals())
    active_subs = len([s for s in sub_store.all_subscriptions() if s.get("status") == "active"])
    logger.info(f"  {open_count} open signals, {active_subs} active subscriptions loaded")

    bot = TradingSignalBot(
        nick=args.nick,
        channels=channels,
        store=store,
        sub_store=sub_store,
        price_interval=args.price_interval,
    )

    try:
        await bot.connect()
        await asyncio.sleep(2)

        for ch in channels:
            await bot.send_message(
                ch,
                f"[TRADING] Signal Bot online. {open_count} open signals. Try: !ts help",
            )

        if args.duration > 0:
            try:
                await asyncio.wait_for(bot.run(), timeout=args.duration)
            except asyncio.TimeoutError:
                pass
        else:
            await bot.run()

    except KeyboardInterrupt:
        logger.info("  Interrupted")
    except Exception as e:
        logger.error(f"  Error: {e}")
    finally:
        await bot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
