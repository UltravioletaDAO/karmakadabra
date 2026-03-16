"""
Karma Kadabra V2 — Phase 10: Abracadabra IRC Command Responder

Connects to MeshRelay IRC (#Agents) and responds to content
intelligence commands. Acts as the public interface for Abracadabra's
content generation capabilities.

Commands:
  !abracadabra trending   / !ab trending    — Current trending topics
  !abracadabra predict X  / !ab predict X   — Prediction for topic X
  !abracadabra blog X     / !ab blog X      — Request blog generation
  !abracadabra clips ID   / !ab clips ID    — Clip suggestions for stream
  !abracadabra help       / !ab help        — List available commands

Usage:
  python abracadabra_irc.py
  python abracadabra_irc.py --channel "#Agents"
  python abracadabra_irc.py --duration 3600    # Run for 1 hour
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure sibling packages are importable
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent))

from agent_irc_client import IRC_PORT, IRC_SERVER, PING_INTERVAL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.abracadabra-irc")

NICK = "kk-abracadabra"
DEFAULT_CHANNELS = ["#Agents"]

# Max IRC message length (conservative to avoid truncation)
MAX_MSG_LEN = 400


# ---------------------------------------------------------------------------
# Cached content data (loaded from disk if available)
# ---------------------------------------------------------------------------

_cached_trending: list[dict] = []
_cached_predictions: dict[str, dict] = {}
_cached_clips: dict[str, list[dict]] = {}


def load_content_cache(data_dir: Path) -> None:
    """Load cached content products from disk."""
    global _cached_trending, _cached_predictions, _cached_clips

    cache_dir = data_dir / "content_cache"
    if not cache_dir.exists():
        logger.info("  No content cache found -- responses will be limited")
        return

    # Load trending predictions
    for f in sorted(cache_dir.glob("predict_trending_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            _cached_trending = data.get("predictions", [])
            logger.info(f"  Loaded {len(_cached_trending)} trending predictions from {f.name}")
            break
        except Exception:
            pass

    # Load knowledge graphs as prediction source
    for f in cache_dir.glob("knowledge_graph_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            topic = data.get("topic", "unknown")
            _cached_predictions[topic] = data
        except Exception:
            pass

    # Load clip suggestions
    for f in cache_dir.glob("suggest_clips_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            stream_id = data.get("stream_id", "unknown")
            _cached_clips[stream_id] = data.get("suggestions", [])
        except Exception:
            pass

    logger.info(f"  Cache loaded: {len(_cached_predictions)} predictions, {len(_cached_clips)} clip sets")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def handle_trending() -> str:
    """Return current trending topics."""
    if not _cached_trending:
        return "No trending data yet. Run abracadabra_service.py --generate first."

    lines = []
    for pred in _cached_trending[:5]:
        topic = pred.get("topic", "?")
        conf = pred.get("confidence", 0)
        trend = pred.get("trend", "?")
        lines.append(f"{topic} ({conf:.0%} {trend})")

    return "Trending: " + " | ".join(lines)


def handle_predict(topic: str) -> str:
    """Return prediction for a specific topic."""
    if not topic:
        return "Usage: !ab predict <topic>"

    topic_lower = topic.lower()

    # Check cached predictions
    if topic_lower in _cached_predictions:
        data = _cached_predictions[topic_lower]
        nodes = len(data.get("nodes", []))
        edges = len(data.get("edges", []))
        return f"[{topic}] Knowledge graph: {nodes} entities, {edges} connections. Trend: active."

    # Check trending data
    for pred in _cached_trending:
        if topic_lower in pred.get("topic", "").lower():
            conf = pred.get("confidence", 0)
            trend = pred.get("trend", "?")
            return f"[{topic}] Confidence: {conf:.0%}, trend: {trend}"

    return f"No prediction data for '{topic}'. Available: {', '.join(p.get('topic', '?') for p in _cached_trending[:5])}"


def handle_blog(topic: str) -> str:
    """Acknowledge blog generation request."""
    if not topic:
        return "Usage: !ab blog <topic>"

    return (
        f"Blog request queued for '{topic}'. "
        f"Will publish on execution.market when ready. "
        f"Bounty: $0.10 USDC."
    )


def handle_clips(stream_id: str) -> str:
    """Return clip suggestions for a stream."""
    if not stream_id:
        return "Usage: !ab clips <stream_id>"

    clips = _cached_clips.get(stream_id, [])
    if not clips:
        available = list(_cached_clips.keys())[:3]
        if available:
            return f"No clips for '{stream_id}'. Available: {', '.join(available)}"
        return f"No clip data available. Run abracadabra_service.py --generate first."

    lines = []
    for clip in clips[:3]:
        title = clip.get("suggested_title", "?")
        virality = clip.get("estimated_virality", 0)
        lines.append(f"{title} (virality: {virality:.0%})")

    return f"Clips for {stream_id}: " + " | ".join(lines)


def handle_help() -> str:
    """List available commands."""
    return (
        "Abracadabra commands: "
        "!ab trending -- top topics | "
        "!ab predict <topic> -- prediction | "
        "!ab blog <topic> -- request blog | "
        "!ab clips <stream_id> -- clip ideas | "
        "!ab help -- this message"
    )


COMMANDS = {
    "trending": handle_trending,
    "predict": handle_predict,
    "blog": handle_blog,
    "clips": handle_clips,
    "help": handle_help,
}


def parse_command(message: str) -> tuple[str, str]:
    """Parse an IRC message into (command, argument).

    Returns ("", "") if the message is not an Abracadabra command.
    """
    msg = message.strip()

    # Accept !abracadabra or !ab prefix
    prefix = ""
    if msg.lower().startswith("!abracadabra ") or msg.lower() == "!abracadabra":
        prefix = "!abracadabra"
    elif msg.lower().startswith("!ab ") or msg.lower() == "!ab":
        prefix = "!ab"
    else:
        return ("", "")

    rest = msg[len(prefix):].strip()
    if not rest:
        return ("help", "")

    parts = rest.split(None, 1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""

    return (command, argument)


def dispatch_command(command: str, argument: str) -> str:
    """Dispatch a parsed command to its handler.

    Returns the response string, truncated to MAX_MSG_LEN.
    """
    handler = COMMANDS.get(command)
    if not handler:
        return f"Unknown command: {command}. Try: !ab help"

    # Commands that take an argument
    if command in ("predict", "blog", "clips"):
        response = handler(argument)
    else:
        response = handler()

    # Truncate for IRC
    if len(response) > MAX_MSG_LEN:
        response = response[: MAX_MSG_LEN - 3] + "..."

    return response


# ---------------------------------------------------------------------------
# IRC connection (lightweight, follows agent_irc_client pattern)
# ---------------------------------------------------------------------------


class AbracadabraIRC:
    """IRC client for Abracadabra command responder."""

    def __init__(self, nick: str, channels: list[str]):
        self.nick = nick
        self.channels = channels
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._running = True

    async def connect(self) -> None:
        """Connect to IRC server."""
        logger.info(f"  [{self.nick}] Connecting to {IRC_SERVER}:{IRC_PORT}...")
        self._reader, self._writer = await asyncio.open_connection(IRC_SERVER, IRC_PORT)

        await self._send(f"NICK {self.nick}")
        await self._send(f"USER {self.nick} 0 * :KK Abracadabra Content Agent")

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
                data = await asyncio.wait_for(self._reader.readline(), timeout=PING_INTERVAL + 30)
                return data.decode("utf-8", errors="replace").strip()
            except asyncio.TimeoutError:
                return ""
        return ""

    async def _handle_ping(self, line: str) -> None:
        token = line.split("PING ")[-1] if "PING " in line else ":server"
        await self._send(f"PONG {token}")

    async def send_message(self, channel: str, message: str) -> None:
        """Send a message to a channel."""
        await self._send(f"PRIVMSG {channel} :{message}")

    async def listen(self) -> None:
        """Main listen loop — process incoming messages and commands."""
        logger.info(f"  [{self.nick}] Listening for commands...")

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
                except Exception:
                    pass

    async def _handle_message(self, sender: str, channel: str, message: str) -> None:
        """Handle an incoming IRC message."""
        command, argument = parse_command(message)
        if not command:
            return

        logger.info(f"  [{self.nick}] Command from {sender}: {command} {argument}")
        response = dispatch_command(command, argument)
        await self.send_message(channel, f"{sender}: {response}")

    async def disconnect(self) -> None:
        """Disconnect from IRC."""
        self._running = False
        if self._writer:
            await self._send("QUIT :Abracadabra signing off")
            self._writer.close()
        logger.info(f"  [{self.nick}] Disconnected")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="Abracadabra -- IRC Command Responder")
    parser.add_argument("--channel", type=str, action="append", help="IRC channel to join")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory for content cache")
    parser.add_argument("--duration", type=int, default=0, help="Run duration in seconds (0=forever)")
    parser.add_argument("--nick", type=str, default=NICK, help="IRC nickname")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"
    channels = args.channel or DEFAULT_CHANNELS

    print(f"\n{'=' * 60}")
    print(f"  Abracadabra -- IRC Command Responder")
    print(f"  Nick: {args.nick}")
    print(f"  Server: {IRC_SERVER}")
    print(f"  Channels: {', '.join(channels)}")
    print(f"{'=' * 60}\n")

    # Load cached content for responses
    load_content_cache(data_dir)

    bot = AbracadabraIRC(nick=args.nick, channels=channels)

    try:
        await bot.connect()

        # Announce presence
        await asyncio.sleep(2)
        for ch in channels:
            await bot.send_message(ch, "Abracadabra online. Content intelligence ready. Try: !ab help")

        if args.duration > 0:
            try:
                await asyncio.wait_for(bot.listen(), timeout=args.duration)
            except asyncio.TimeoutError:
                pass
        else:
            await bot.listen()
    except Exception as e:
        logger.error(f"  Error: {e}")
    finally:
        await bot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
