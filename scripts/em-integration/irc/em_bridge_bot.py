"""
Karma Kadabra V2 — Phase 2: IRC-to-Execution Market Bridge Bot

Bidirectional bridge between MeshRelay IRC and the Execution Market REST API.
Agents interact with EM directly from IRC using !em commands. The bot also
polls for task status changes and posts notifications to IRC channels.

Commands:
  !em publish <title> | <instructions> | <bounty> [<network>] [<token>]
  !em tasks [status] [category]
  !em task <task_id>
  !em apply <task_id> [message]
  !em submit <task_id> <evidence_url>
  !em approve <submission_id> [rating]
  !em reject <submission_id> [reason]
  !em cancel <task_id>
  !em balance [network]
  !em help

Usage:
  python em_bridge_bot.py
  python em_bridge_bot.py --channel "#tasks"
  python em_bridge_bot.py --notify-channel "#tasks" --cmd-channel "#Agents"
  python em_bridge_bot.py --poll-interval 30
  python em_bridge_bot.py --duration 3600  # Run for 1 hour
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure sibling packages are importable
_kk_root = Path(__file__).parent.parent
sys.path.insert(0, str(_kk_root / "services"))
sys.path.insert(0, str(_kk_root / "lib"))
sys.path.insert(0, str(_kk_root / "irc"))

from agent_irc_client import IRC_PORT, IRC_SERVER, PING_INTERVAL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.em-bridge")

NICK = "kk-em-bridge"
DEFAULT_CMD_CHANNELS = ["#Agents"]
DEFAULT_NOTIFY_CHANNELS = ["#tasks"]
MAX_MSG_LEN = 400
POLL_INTERVAL_SECONDS = 30
RATE_LIMIT_COMMANDS = 10
RATE_LIMIT_WINDOW = 60  # seconds


# ---------------------------------------------------------------------------
# Agent identity mapping
# ---------------------------------------------------------------------------

_nick_to_agent: dict[str, dict] = {}


def load_identities(config_path: Path | None = None) -> None:
    """Load nick-to-agent mapping from identities.json."""
    global _nick_to_agent

    if config_path is None:
        config_path = _kk_root / "config" / "identities.json"

    if not config_path.exists():
        logger.warning(f"  Identities file not found: {config_path}")
        return

    data = json.loads(config_path.read_text(encoding="utf-8"))
    agents = data.get("agents", [])
    for agent in agents:
        nick = agent.get("name", "")
        if nick:
            _nick_to_agent[nick] = {
                "wallet": agent.get("address", ""),
                "executor_id": agent.get("executor_id", ""),
                "agent_id": agent.get("registrations", {})
                .get("base", {})
                .get("agent_id"),
                "type": agent.get("type", "user"),
                "index": agent.get("index", -1),
            }
    logger.info(f"  Loaded {len(_nick_to_agent)} agent identities")


def resolve_nick(nick: str) -> dict | None:
    """Resolve an IRC nick to an agent identity."""
    return _nick_to_agent.get(nick)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_rate_buckets: dict[str, list[float]] = {}


def check_rate_limit(nick: str) -> bool:
    """Return True if the nick is within rate limits."""
    now = time.time()
    if nick not in _rate_buckets:
        _rate_buckets[nick] = []

    # Prune old entries
    _rate_buckets[nick] = [t for t in _rate_buckets[nick] if now - t < RATE_LIMIT_WINDOW]

    if len(_rate_buckets[nick]) >= RATE_LIMIT_COMMANDS:
        return False

    _rate_buckets[nick].append(now)
    return True


def rate_limit_wait(nick: str) -> int:
    """Return seconds until the nick can send again."""
    if nick not in _rate_buckets or not _rate_buckets[nick]:
        return 0
    oldest = min(_rate_buckets[nick])
    return max(0, int(RATE_LIMIT_WINDOW - (time.time() - oldest)) + 1)


# ---------------------------------------------------------------------------
# Short ID resolution
# ---------------------------------------------------------------------------


def match_short_id(short_id: str, candidates: list[str]) -> str | None:
    """Match a short ID prefix to a full UUID.

    Returns the full UUID if exactly one match, None otherwise.
    """
    short_lower = short_id.lower()
    matches = [c for c in candidates if c.lower().startswith(short_lower)]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------


def parse_command(message: str) -> tuple[str, str]:
    """Parse an IRC message into (command, arguments).

    Returns ("", "") if the message is not an EM command.
    """
    msg = message.strip()

    if not (msg.lower().startswith("!em ") or msg.lower() == "!em"):
        return ("", "")

    rest = msg[3:].strip()
    if not rest:
        return ("help", "")

    parts = rest.split(None, 1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""

    return (command, argument)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def handle_publish(em_client, nick: str, args: str) -> str:
    """Handle !em publish <title> | <instructions> | <bounty> [network] [token]"""
    agent = resolve_nick(nick)
    if not agent:
        return f"[ERR] Unknown nick '{nick}' -- not in identities.json"

    parts = [p.strip() for p in args.split("|")]
    if len(parts) < 3:
        return "[ERR] Usage: !em publish <title> | <instructions> | <bounty> [network] [token]"

    title = parts[0]
    instructions = parts[1]
    bounty_str = parts[2]

    # Parse bounty and optional network/token
    bounty_parts = bounty_str.split()
    try:
        bounty = float(bounty_parts[0])
    except (ValueError, IndexError):
        return f"[ERR] Invalid bounty: '{bounty_str}'. Use a number like 0.10"

    if bounty > 0.50:
        return f"[ERR] Bounty too high: ${bounty:.2f}. Max $0.50 for safety."

    network = bounty_parts[1] if len(bounty_parts) > 1 else "base"
    # token = bounty_parts[2] if len(bounty_parts) > 2 else "USDC"  # future

    try:
        result = await em_client.publish_task(
            title=title,
            instructions=instructions,
            category="simple_action",
            bounty_usd=bounty,
            deadline_hours=2,
            payment_network=network,
        )
        task_id = result.get("id", result.get("task_id", "?"))
        short_id = task_id[:8] if task_id else "?"
        return f"[OK] Task published: \"{title}\" -- ${bounty:.2f} USDC on {network} -- !em apply {short_id}"
    except Exception as e:
        return f"[ERR] Publish failed: {_extract_error(e)}"


async def handle_tasks(em_client, nick: str, args: str) -> str:
    """Handle !em tasks [status] [category]"""
    parts = args.split() if args else []
    status = parts[0] if parts else "published"
    category = parts[1] if len(parts) > 1 else None

    try:
        tasks = await em_client.browse_tasks(status=status, category=category, limit=5)
        if not tasks:
            return f"[TASKS] No {status} tasks found"

        lines = [f"[TASKS] {len(tasks)} {status} task(s):"]
        for i, t in enumerate(tasks[:5], 1):
            tid = t.get("id", "?")[:8]
            title = t.get("title", "?")[:40]
            bounty = t.get("bounty_usd", 0)
            cat = t.get("category", "?")
            lines.append(f"  {i}. {tid} -- \"{title}\" -- ${bounty:.2f} -- {cat}")

        return " | ".join(lines) if len(" | ".join(lines)) <= MAX_MSG_LEN else "\n".join(lines)
    except Exception as e:
        return f"[ERR] List tasks failed: {_extract_error(e)}"


async def handle_task(em_client, nick: str, args: str) -> str:
    """Handle !em task <task_id>"""
    if not args:
        return "[ERR] Usage: !em task <task_id>"

    task_id = args.strip().split()[0]

    try:
        task = await em_client.get_task(task_id)
        tid = task.get("id", "?")[:8]
        title = task.get("title", "?")
        status = task.get("status", "?")
        bounty = task.get("bounty_usd", 0)
        network = task.get("payment_network", "base")
        cat = task.get("category", "?")
        instr = (task.get("instructions", "") or "")[:100]
        return (
            f"[TASK] {tid} | \"{title}\" | {status} | ${bounty:.2f} {network} | {cat} | {instr}"
        )
    except Exception as e:
        return f"[ERR] Get task failed: {_extract_error(e)}"


async def handle_apply(em_client, nick: str, args: str) -> str:
    """Handle !em apply <task_id> [message]"""
    agent = resolve_nick(nick)
    if not agent:
        return f"[ERR] Unknown nick '{nick}' -- not in identities.json"

    parts = args.split(None, 1)
    if not parts:
        return "[ERR] Usage: !em apply <task_id> [message]"

    task_id = parts[0]
    message = parts[1] if len(parts) > 1 else f"Applied via IRC by {nick}"

    executor_id = agent.get("executor_id")
    if not executor_id:
        return f"[ERR] No executor_id for {nick} -- register on EM first"

    try:
        result = await em_client.apply_to_task(task_id, executor_id, message)
        return f"[OK] {nick} applied to {task_id[:8]} -- waiting for assignment"
    except Exception as e:
        return f"[ERR] Apply failed: {_extract_error(e)}"


async def handle_submit(em_client, nick: str, args: str) -> str:
    """Handle !em submit <task_id> <evidence_url>"""
    agent = resolve_nick(nick)
    if not agent:
        return f"[ERR] Unknown nick '{nick}' -- not in identities.json"

    parts = args.split(None, 1)
    if len(parts) < 2:
        return "[ERR] Usage: !em submit <task_id> <evidence_url>"

    task_id = parts[0]
    evidence_url = parts[1]

    executor_id = agent.get("executor_id")
    if not executor_id:
        return f"[ERR] No executor_id for {nick}"

    try:
        result = await em_client.submit_evidence(
            task_id,
            executor_id,
            evidence={"url": evidence_url, "type": "url", "notes": f"Submitted via IRC by {nick}"},
        )
        return f"[OK] Evidence submitted for {task_id[:8]} by {nick}"
    except Exception as e:
        return f"[ERR] Submit failed: {_extract_error(e)}"


async def handle_approve(em_client, nick: str, args: str) -> str:
    """Handle !em approve <submission_id> [rating]"""
    parts = args.split() if args else []
    if not parts:
        return "[ERR] Usage: !em approve <submission_id> [rating]"

    submission_id = parts[0]
    rating = int(parts[1]) if len(parts) > 1 else 80

    try:
        result = await em_client.approve_submission(submission_id, rating_score=rating)
        return f"[OK] Submission {submission_id[:8]} approved (rating: {rating})"
    except Exception as e:
        return f"[ERR] Approve failed: {_extract_error(e)}"


async def handle_reject(em_client, nick: str, args: str) -> str:
    """Handle !em reject <submission_id> [reason]"""
    parts = args.split(None, 1)
    if not parts:
        return "[ERR] Usage: !em reject <submission_id> [reason]"

    submission_id = parts[0]
    reason = parts[1] if len(parts) > 1 else "Does not meet requirements."

    try:
        result = await em_client.reject_submission(submission_id, notes=reason)
        return f"[OK] Submission {submission_id[:8]} rejected"
    except Exception as e:
        return f"[ERR] Reject failed: {_extract_error(e)}"


async def handle_cancel(em_client, nick: str, args: str) -> str:
    """Handle !em cancel <task_id>"""
    if not args:
        return "[ERR] Usage: !em cancel <task_id>"

    task_id = args.strip().split()[0]

    try:
        result = await em_client.cancel_task(task_id)
        return f"[OK] Task {task_id[:8]} cancelled"
    except Exception as e:
        return f"[ERR] Cancel failed: {_extract_error(e)}"


async def handle_help(em_client, nick: str, args: str) -> str:
    """Handle !em help"""
    return (
        "EM Bridge commands: "
        "!em publish <title>|<desc>|<bounty> -- create task | "
        "!em tasks [status] -- list tasks | "
        "!em task <id> -- task details | "
        "!em apply <id> [msg] -- apply to task | "
        "!em submit <id> <url> -- submit evidence | "
        "!em approve <id> [rating] -- approve submission | "
        "!em reject <id> [reason] -- reject | "
        "!em cancel <id> -- cancel task | "
        "!em help"
    )


COMMANDS: dict[str, callable] = {
    "publish": handle_publish,
    "tasks": handle_tasks,
    "task": handle_task,
    "apply": handle_apply,
    "submit": handle_submit,
    "approve": handle_approve,
    "reject": handle_reject,
    "cancel": handle_cancel,
    "help": handle_help,
}


def _extract_error(exc: Exception) -> str:
    """Extract a human-readable error from an exception."""
    msg = str(exc)
    # Try to extract detail from httpx response
    if hasattr(exc, "response") and exc.response is not None:
        try:
            detail = exc.response.json().get("detail", msg)
            return str(detail)[:200]
        except Exception:
            pass
    return msg[:200]


# ---------------------------------------------------------------------------
# Notification poller
# ---------------------------------------------------------------------------


class TaskNotifier:
    """Polls EM API for task changes and generates IRC notifications."""

    def __init__(self, em_client):
        self.em_client = em_client
        self._seen_tasks: set[str] = set()
        self._last_poll: float = 0.0

    async def poll(self) -> list[str]:
        """Poll for new/changed tasks. Returns list of IRC notification strings."""
        notifications = []

        try:
            tasks = await self.em_client.browse_tasks(status="published", limit=20)
        except Exception as e:
            logger.debug(f"  Poll failed: {e}")
            return notifications

        for task in tasks:
            task_id = task.get("id", "")
            if not task_id or task_id in self._seen_tasks:
                continue

            self._seen_tasks.add(task_id)

            # Skip notification on first poll (historical tasks)
            if self._last_poll == 0.0:
                continue

            title = task.get("title", "?")[:50]
            bounty = task.get("bounty_usd", 0)
            network = task.get("payment_network", "base")
            short_id = task_id[:8]
            notifications.append(
                f"[TASK-NEW] \"{title}\" -- ${bounty:.2f} USDC on {network} -- !em apply {short_id}"
            )

        self._last_poll = time.time()
        return notifications


# ---------------------------------------------------------------------------
# IRC Bridge Bot
# ---------------------------------------------------------------------------


class EMBridgeBot:
    """IRC bot that bridges commands to Execution Market API."""

    def __init__(
        self,
        nick: str,
        cmd_channels: list[str],
        notify_channels: list[str],
        em_client,
        poll_interval: int = POLL_INTERVAL_SECONDS,
    ):
        self.nick = nick
        self.cmd_channels = cmd_channels
        self.notify_channels = notify_channels
        self.em_client = em_client
        self.poll_interval = poll_interval
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._running = True
        self._notifier = TaskNotifier(em_client)
        self._all_channels = list(set(cmd_channels + notify_channels))

    async def connect(self) -> None:
        """Connect to IRC server."""
        logger.info(f"  [{self.nick}] Connecting to {IRC_SERVER}:{IRC_PORT}...")
        self._reader, self._writer = await asyncio.open_connection(IRC_SERVER, IRC_PORT)

        await self._send(f"NICK {self.nick}")
        await self._send(f"USER {self.nick} 0 * :KK EM Bridge Bot - Ultravioleta DAO")

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

        for channel in self._all_channels:
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
        """Send a message to a channel, splitting if too long."""
        for chunk in _split_message(message, MAX_MSG_LEN):
            await self._send(f"PRIVMSG {target} :{chunk}")

    async def run(self) -> None:
        """Main loop — handle messages and poll for notifications concurrently."""
        listener = asyncio.create_task(self._listen())
        poller = asyncio.create_task(self._poll_loop())

        try:
            await asyncio.gather(listener, poller)
        except asyncio.CancelledError:
            pass

    async def _listen(self) -> None:
        """Listen for IRC messages and dispatch commands."""
        logger.info(f"  [{self.nick}] Listening for !em commands...")

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
        """Handle an incoming IRC message — dispatch !em commands."""
        # Ignore own messages
        if sender == self.nick:
            return

        command, argument = parse_command(message)
        if not command:
            return

        # Only respond to commands in command channels
        if channel not in self.cmd_channels and not channel.startswith(self.nick):
            return

        logger.info(f"  [{self.nick}] Command from {sender}: !em {command} {argument}")

        # Rate limit
        if not check_rate_limit(sender):
            wait = rate_limit_wait(sender)
            await self.send_message(
                channel, f"{sender}: [ERR] Rate limit exceeded -- try again in {wait}s"
            )
            return

        handler = COMMANDS.get(command)
        if not handler:
            await self.send_message(
                channel, f"{sender}: [ERR] Unknown command: {command}. Try: !em help"
            )
            return

        response = await handler(self.em_client, sender, argument)
        # Truncate response for IRC
        if len(response) > MAX_MSG_LEN:
            response = response[: MAX_MSG_LEN - 3] + "..."
        await self.send_message(channel, f"{sender}: {response}")

    async def _poll_loop(self) -> None:
        """Periodically poll EM for new tasks and post notifications."""
        # Initial poll (populate seen set without notifications)
        await self._notifier.poll()

        while self._running:
            await asyncio.sleep(self.poll_interval)

            if not self._connected:
                continue

            notifications = await self._notifier.poll()
            for notif in notifications:
                for ch in self.notify_channels:
                    await self.send_message(ch, notif)
                    await asyncio.sleep(0.5)  # Avoid flood

    async def disconnect(self) -> None:
        """Disconnect from IRC."""
        self._running = False
        if self._writer:
            await self._send("QUIT :EM Bridge signing off")
            self._writer.close()
        logger.info(f"  [{self.nick}] Disconnected")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_message(text: str, max_len: int = 400) -> list[str]:
    """Split a long message into IRC-safe chunks."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="EM Bridge Bot -- IRC-to-Execution Market")
    parser.add_argument(
        "--cmd-channel",
        type=str,
        action="append",
        help="Channel(s) to listen for commands (default: #Agents)",
    )
    parser.add_argument(
        "--notify-channel",
        type=str,
        action="append",
        help="Channel(s) for notifications (default: #tasks)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=POLL_INTERVAL_SECONDS,
        help=f"Seconds between task polls (default: {POLL_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--nick",
        type=str,
        default=NICK,
        help=f"IRC nickname (default: {NICK})",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Run duration in seconds (0=forever)",
    )
    parser.add_argument(
        "--identities",
        type=str,
        default=None,
        help="Path to identities.json",
    )
    args = parser.parse_args()

    cmd_channels = args.cmd_channel or DEFAULT_CMD_CHANNELS
    notify_channels = args.notify_channel or DEFAULT_NOTIFY_CHANNELS

    print(f"\n{'=' * 60}")
    print(f"  EM Bridge Bot -- IRC-to-Execution Market")
    print(f"  Nick: {args.nick}")
    print(f"  Server: {IRC_SERVER}")
    print(f"  Command channels: {', '.join(cmd_channels)}")
    print(f"  Notify channels: {', '.join(notify_channels)}")
    print(f"  Poll interval: {args.poll_interval}s")
    print(f"{'=' * 60}\n")

    # Load agent identities
    identities_path = Path(args.identities) if args.identities else None
    load_identities(identities_path)

    # Create EM client using coordinator agent context
    from em_client import AgentContext, EMClient

    coordinator = resolve_nick("kk-coordinator")
    if coordinator:
        ctx = AgentContext(
            name="kk-em-bridge",
            wallet_address=coordinator["wallet"],
            workspace_dir=_kk_root / "data" / "workspaces" / "kk-coordinator",
            api_key=os.environ.get("EM_API_KEY", ""),
        )
    else:
        logger.warning("  kk-coordinator not found in identities -- using empty context")
        ctx = AgentContext(
            name="kk-em-bridge",
            wallet_address="",
            workspace_dir=_kk_root,
            api_key=os.environ.get("EM_API_KEY", ""),
        )

    em = EMClient(ctx)

    bot = EMBridgeBot(
        nick=args.nick,
        cmd_channels=cmd_channels,
        notify_channels=notify_channels,
        em_client=em,
        poll_interval=args.poll_interval,
    )

    try:
        await bot.connect()

        # Announce presence
        await asyncio.sleep(2)
        for ch in cmd_channels:
            await bot.send_message(
                ch,
                f"[BRIDGE] EM Bridge online. {len(_nick_to_agent)} agents loaded. Try: !em help",
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
        await em.close()


if __name__ == "__main__":
    asyncio.run(main())
