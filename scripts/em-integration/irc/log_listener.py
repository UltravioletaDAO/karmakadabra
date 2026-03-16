"""
Karma Kadabra V2 — Phase 9.1: IRC Log Listener

Connects to MeshRelay IRC and captures all channel messages to JSON log files.
Used by Karma Hello to collect raw chat data for analysis and marketplace sales.

Channels:
  #Agents         — General agent communication
  #kk-ops         — Swarm coordination (system agents only)
  #kk-data-market — Data marketplace (buy/sell offerings)

Log format (per message):
  {"ts": "ISO8601", "sender": "nick", "channel": "#Agents", "content": "message text"}

Output: data/irc-logs/{YYYY-MM-DD}.json (append mode, one JSON object per line)

Usage:
  python log_listener.py                                # Default: #Agents, 1 hour
  python log_listener.py --channel "#kk-data-market"    # Specific channel
  python log_listener.py --duration 3600                # Run for 1 hour
  python log_listener.py --output-dir /tmp/irc-logs     # Custom output dir
  python log_listener.py --dry-run                      # Print to stdout only
"""

import argparse
import asyncio
import json
import logging
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.log_listener")

# IRC server config (same as agent_irc_client.py)
IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667
IRC_SSL_PORT = 6697
PING_INTERVAL = 120

# Defaults
DEFAULT_CHANNELS = ["#Agents"]
DEFAULT_DURATION = 3600  # 1 hour
LISTENER_NICK = "kk-log-listener"


class IRCLogListener:
    """Passive IRC listener that captures messages to JSON log files."""

    def __init__(
        self,
        nick: str,
        channels: list[str],
        output_dir: Path,
        dry_run: bool = False,
        use_ssl: bool = False,
    ):
        self.nick = nick
        self.channels = channels
        self.output_dir = output_dir
        self.dry_run = dry_run
        self.use_ssl = use_ssl
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._running = True
        self._message_count = 0

    async def connect(self) -> None:
        """Connect to IRC server and join channels."""
        port = IRC_SSL_PORT if self.use_ssl else IRC_PORT
        logger.info(f"Connecting to {IRC_SERVER}:{port}...")

        if self.use_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._reader, self._writer = await asyncio.open_connection(
                IRC_SERVER, port, ssl=ctx,
            )
        else:
            self._reader, self._writer = await asyncio.open_connection(
                IRC_SERVER, port,
            )

        # Register
        await self._send(f"NICK {self.nick}")
        await self._send(f"USER {self.nick} 0 * :KK Log Listener")

        # Wait for welcome or handle nick collision
        while True:
            line = await self._recv()
            if not line:
                break
            if " 001 " in line:
                self._connected = True
                logger.info("Connected to IRC server")
                break
            if " 433 " in line:
                self.nick = self.nick + "_"
                logger.warning(f"Nick in use, retrying as {self.nick}")
                await self._send(f"NICK {self.nick}")
            if "PING" in line:
                await self._handle_ping(line)

        # Join channels
        for channel in self.channels:
            await self._send(f"JOIN {channel}")
            logger.info(f"Joined {channel}")

    async def _send(self, msg: str) -> None:
        if self._writer:
            self._writer.write(f"{msg}\r\n".encode("utf-8"))
            await self._writer.drain()

    async def _recv(self) -> str:
        if self._reader:
            try:
                data = await asyncio.wait_for(
                    self._reader.readline(), timeout=PING_INTERVAL + 30,
                )
                return data.decode("utf-8", errors="replace").strip()
            except asyncio.TimeoutError:
                return ""
        return ""

    async def _handle_ping(self, line: str) -> None:
        token = line.split("PING ")[-1] if "PING " in line else ":server"
        await self._send(f"PONG {token}")

    def _should_skip(self, sender: str, content: str) -> bool:
        """Filter out bot messages and commands."""
        # Skip messages starting with ! (IRC bot commands)
        if content.startswith("!"):
            return True
        # Skip common bot nicks
        bot_patterns = ["chanserv", "nickserv", "memoserv", "operserv"]
        if sender.lower() in bot_patterns:
            return True
        # Skip own messages
        if sender.lower() == self.nick.lower():
            return True
        return False

    def _log_message(self, sender: str, channel: str, content: str) -> None:
        """Append a message to the daily log file."""
        now = datetime.now(timezone.utc)
        entry = {
            "ts": now.isoformat(),
            "sender": sender,
            "channel": channel,
            "content": content,
        }

        if self.dry_run:
            print(f"  [{channel}] <{sender}> {content}")
            self._message_count += 1
            return

        # Ensure output dir exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Append to daily log file
        date_str = now.strftime("%Y-%m-%d")
        log_file = self.output_dir / f"{date_str}.json"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._message_count += 1
        if self._message_count % 50 == 0:
            logger.info(f"Captured {self._message_count} messages so far")

    async def listen(self, duration: int = 0) -> int:
        """Listen for messages and log them.

        Args:
            duration: Max listen time in seconds (0 = indefinite).

        Returns:
            Number of messages captured.
        """
        logger.info(
            f"Listening on {', '.join(self.channels)} "
            f"({'indefinite' if duration == 0 else f'{duration}s'})"
        )
        start = time.monotonic()

        while self._running and self._connected:
            # Check duration
            if duration > 0 and (time.monotonic() - start) >= duration:
                logger.info(f"Duration reached ({duration}s)")
                break

            line = await self._recv()
            if not line:
                await self._send(f"PING :keepalive-{int(time.time())}")
                continue

            if line.startswith("PING"):
                await self._handle_ping(line)
                continue

            # Parse PRIVMSG: :nick!user@host PRIVMSG #channel :message
            if "PRIVMSG" in line:
                try:
                    prefix, _, rest = line.partition(" PRIVMSG ")
                    sender = prefix.split("!")[0].lstrip(":")
                    channel, _, content = rest.partition(" :")

                    if not self._should_skip(sender, content):
                        self._log_message(sender, channel, content)
                except Exception:
                    pass

        return self._message_count

    async def disconnect(self) -> None:
        """Disconnect from IRC."""
        self._running = False
        if self._writer:
            try:
                await self._send("QUIT :KK log listener signing off")
                self._writer.close()
            except Exception:
                pass
        logger.info(f"Disconnected. Total messages captured: {self._message_count}")

    def stop(self) -> None:
        """Signal the listener to stop."""
        self._running = False


async def run_listener(
    channels: list[str],
    output_dir: Path,
    duration: int = DEFAULT_DURATION,
    dry_run: bool = False,
) -> int:
    """Run the IRC log listener.

    Returns:
        Number of messages captured.
    """
    listener = IRCLogListener(
        nick=LISTENER_NICK,
        channels=channels,
        output_dir=output_dir,
        dry_run=dry_run,
    )

    try:
        await listener.connect()
        return await listener.listen(duration=duration)
    except Exception as e:
        logger.error(f"Listener error: {e}")
        return listener._message_count
    finally:
        await listener.disconnect()


async def main() -> None:
    parser = argparse.ArgumentParser(description="KK IRC Log Listener")
    parser.add_argument(
        "--channel", type=str, action="append",
        help="IRC channel to listen on (can specify multiple)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Directory for log files (default: data/irc-logs/)",
    )
    parser.add_argument(
        "--duration", type=int, default=DEFAULT_DURATION,
        help=f"Listen duration in seconds (default: {DEFAULT_DURATION}, 0=indefinite)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print messages to stdout instead of saving",
    )
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    channels = args.channel or DEFAULT_CHANNELS
    output_dir = Path(args.output_dir) if args.output_dir else base / "data" / "irc-logs"

    print(f"\n{'=' * 60}")
    print(f"  KK IRC Log Listener")
    print(f"  Server: {IRC_SERVER}")
    print(f"  Channels: {', '.join(channels)}")
    print(f"  Output: {output_dir}")
    print(f"  Duration: {'indefinite' if args.duration == 0 else f'{args.duration}s'}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    count = await run_listener(
        channels=channels,
        output_dir=output_dir,
        duration=args.duration,
        dry_run=args.dry_run,
    )
    print(f"\n  Total messages captured: {count}")


if __name__ == "__main__":
    asyncio.run(main())
