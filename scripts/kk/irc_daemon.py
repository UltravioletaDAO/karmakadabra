#!/usr/bin/env python3
"""Lightweight IRC daemon for KK agents on EC2.

Runs as a background process alongside the heartbeat loop.
Communicates with the heartbeat via file-based inbox/outbox:

  data/irc-inbox.jsonl   — messages received from IRC (daemon writes)
  data/irc-outbox.jsonl  — messages to send to IRC (heartbeat writes, daemon reads+sends)

Features:
  - Connects to MeshRelay SSL with CERT_NONE
  - Auto-reconnect with exponential backoff
  - Keepalive PINGs every 120s
  - Writes received messages to inbox for heartbeat consumption
  - Reads outbox and sends queued messages
  - Auto-introduction on channel join

Usage:
    python irc_daemon.py --agent kk-karma-hello --channel "#karmakadabra"
    python irc_daemon.py --agent kk-validator --channel "#karmakadabra" --extra-channels "#Execution-Market"
"""

import argparse
import asyncio
import json
import logging
import os
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [irc-daemon] %(message)s",
)
logger = logging.getLogger("kk.irc-daemon")

IRC_SERVER = "irc.meshrelay.xyz"
IRC_SSL_PORT = 6697
PING_INTERVAL = 120
OUTBOX_POLL_INTERVAL = 5  # seconds between outbox checks
MAX_RECONNECT_DELAY = 300  # 5 minutes max backoff
INBOX_MAX_LINES = 10000  # truncate inbox if it gets too large


class IRCDaemon:
    """File-based IRC daemon for EC2 agents."""

    def __init__(
        self,
        agent_name: str,
        channels: list[str],
        data_dir: Path,
        soul_path: Path | None = None,
    ):
        self.agent_name = agent_name
        self.channels = channels
        self.data_dir = data_dir
        self.inbox_path = data_dir / "irc-inbox.jsonl"
        self.outbox_path = data_dir / "irc-outbox.jsonl"
        self.soul_path = soul_path

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._running = True
        self._reconnect_delay = 5
        self._nick = agent_name

        # Ensure data dir exists
        data_dir.mkdir(parents=True, exist_ok=True)

    async def connect(self) -> bool:
        """Connect to MeshRelay IRC via SSL."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            logger.info(f"Connecting to {IRC_SERVER}:{IRC_SSL_PORT} as {self._nick}...")
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(IRC_SERVER, IRC_SSL_PORT, ssl=ctx),
                timeout=15.0,
            )

            # Register
            await self._send(f"NICK {self._nick}")
            await self._send(f"USER {self._nick} 0 * :KK Agent {self._nick} - Ultravioleta DAO")

            # Wait for welcome
            deadline = asyncio.get_event_loop().time() + 15.0
            while asyncio.get_event_loop().time() < deadline:
                line = await self._recv(timeout=10.0)
                if not line:
                    continue
                if " 001 " in line:
                    self._connected = True
                    self._reconnect_delay = 5  # reset backoff
                    logger.info(f"Connected as {self._nick}")
                    break
                if " 433 " in line:
                    self._nick = f"{self._nick}_"
                    logger.warning(f"Nick in use, retrying as {self._nick}")
                    await self._send(f"NICK {self._nick}")
                if line.startswith("PING"):
                    await self._handle_ping(line)

            if not self._connected:
                logger.error("Failed to register within timeout")
                return False

            # Join channels
            for channel in self.channels:
                await self._send(f"JOIN {channel}")
                logger.info(f"Joined {channel}")
                await asyncio.sleep(0.3)

            return True

        except Exception as e:
            logger.error(f"Connect failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Gracefully disconnect."""
        self._running = False
        if self._writer:
            try:
                await self._send(f"QUIT :KK agent {self._nick} signing off")
            except Exception:
                pass
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        logger.info("Disconnected")

    async def _send(self, msg: str) -> None:
        if self._writer:
            self._writer.write(f"{msg}\r\n".encode("utf-8"))
            await self._writer.drain()

    async def _recv(self, timeout: float = 150.0) -> str:
        if not self._reader:
            return ""
        try:
            data = await asyncio.wait_for(self._reader.readline(), timeout=timeout)
            if not data:
                # Empty bytes = EOF, server closed connection
                logger.warning("Server closed connection (EOF)")
                self._connected = False
                return ""
            return data.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            return ""
        except Exception as e:
            logger.warning(f"Recv error: {e}")
            self._connected = False
            return ""

    async def _handle_ping(self, line: str) -> None:
        token = line.split("PING ")[-1] if "PING " in line else ":meshrelay"
        await self._send(f"PONG {token}")

    async def send_message(self, target: str, message: str) -> None:
        """Send a PRIVMSG, split if too long."""
        for i in range(0, len(message), 400):
            chunk = message[i : i + 400]
            await self._send(f"PRIVMSG {target} :{chunk}")
            await asyncio.sleep(0.3)

    def _write_inbox(self, entry: dict) -> None:
        """Append a message to the inbox file."""
        try:
            with open(self.inbox_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error(f"Inbox write failed: {e}")

    def _read_and_clear_outbox(self) -> list[dict]:
        """Read all messages from outbox and truncate the file."""
        if not self.outbox_path.exists():
            return []

        messages = []
        try:
            with open(self.outbox_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            messages.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

            # Clear outbox after reading
            if messages:
                self.outbox_path.write_text("", encoding="utf-8")
        except OSError:
            pass

        return messages

    async def _introduce(self) -> None:
        """Introduce agent in the main channel with a short, natural greeting."""
        name = self.agent_name.replace("kk-", "")
        role = self._detect_role()

        greetings = {
            "producer": f"Hola! Soy {name}. Tengo datos frescos para compartir. Pregunten lo que necesiten.",
            "refiner": f"Hey, {name} conectado. Listo para procesar datos y generar perfiles.",
            "aggregator": f"Buenas! {name} aqui. Sintetizando perfiles de la comunidad.",
            "orchestrator": f"Hola equipo! {name} monitoreando el swarm. Todos los sistemas activos.",
            "validator": f"Soy {name}. Validando calidad de datos. Confianza primero.",
            "buyer": f"Que mas! Soy {name}, recien conectado. Buscando datos para autodescubrirme.",
        }
        intro = greetings.get(role, f"Hola! Soy {name} del swarm KK.")

        main_channel = self.channels[0] if self.channels else "#karmakadabra"
        await self.send_message(main_channel, intro)

    def _detect_role(self) -> str:
        """Detect agent role from name or SOUL.md."""
        n = self.agent_name
        if "karma-hello" in n:
            return "producer"
        if "skill-extractor" in n or "voice-extractor" in n:
            return "refiner"
        if "soul-extractor" in n:
            return "aggregator"
        if "coordinator" in n:
            return "orchestrator"
        if "validator" in n:
            return "validator"
        # Community agents (juanjumagalp, 0xjokker, etc.) are buyers
        return "buyer"

    async def _process_outbox(self) -> None:
        """Send queued messages from outbox file."""
        messages = self._read_and_clear_outbox()
        for msg in messages:
            target = msg.get("target", msg.get("channel", ""))
            text = msg.get("message", msg.get("text", ""))
            if target and text:
                await self.send_message(target, text)
                logger.info(f"[OUT] -> {target}: {text[:80]}")

    async def _listen_loop(self) -> None:
        """Main loop: receive IRC messages and process outbox."""
        last_outbox_check = 0
        last_ping = time.time()

        while self._running and self._connected:
            # Check outbox periodically
            now = time.time()
            if now - last_outbox_check > OUTBOX_POLL_INTERVAL:
                await self._process_outbox()
                last_outbox_check = now

            # Send keepalive ping
            if now - last_ping > PING_INTERVAL:
                await self._send(f"PING :keepalive-{int(now)}")
                last_ping = now

            # Receive
            line = await self._recv(timeout=OUTBOX_POLL_INTERVAL)
            if not line:
                continue

            if line.startswith("PING"):
                await self._handle_ping(line)
                continue

            # Parse PRIVMSG
            if "PRIVMSG" in line:
                try:
                    prefix, _, rest = line.partition(" PRIVMSG ")
                    sender = prefix.split("!")[0].lstrip(":")
                    channel, _, message = rest.partition(" :")

                    entry = {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "sender": sender,
                        "channel": channel,
                        "message": message,
                    }
                    self._write_inbox(entry)
                except Exception:
                    pass

    async def run(self) -> None:
        """Main run loop with auto-reconnect."""
        logger.info(f"Starting IRC daemon for {self.agent_name}")
        logger.info(f"Channels: {', '.join(self.channels)}")
        logger.info(f"Inbox: {self.inbox_path}")
        logger.info(f"Outbox: {self.outbox_path}")

        while self._running:
            ok = await self.connect()
            if ok:
                # Introduce after connecting
                await asyncio.sleep(2)
                await self._introduce()

                # Listen until disconnected
                await self._listen_loop()

            if not self._running:
                break

            # Reconnect with backoff
            logger.warning(
                f"Disconnected. Reconnecting in {self._reconnect_delay}s..."
            )
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2, MAX_RECONNECT_DELAY
            )


def main():
    parser = argparse.ArgumentParser(description="KK IRC Daemon for EC2 agents")
    parser.add_argument("--agent", required=True, help="Agent name (e.g., kk-karma-hello)")
    parser.add_argument(
        "--channel",
        default="#karmakadabra",
        help="Primary channel (default: #karmakadabra)",
    )
    parser.add_argument(
        "--extra-channels",
        nargs="*",
        default=["#Execution-Market"],
        help="Additional channels to join",
    )
    parser.add_argument("--data-dir", default="/app/data", help="Data directory")
    parser.add_argument("--soul-dir", default=None, help="Directory with SOUL.md")
    args = parser.parse_args()

    channels = [args.channel]
    if args.extra_channels:
        channels.extend(args.extra_channels)

    data_dir = Path(args.data_dir)

    # Resolve SOUL.md path
    soul_path = None
    if args.soul_dir:
        soul_path = Path(args.soul_dir) / "SOUL.md"
    else:
        # Default locations in Docker
        for candidate in [
            Path(f"/app/openclaw/agents/{args.agent}/SOUL.md"),
            Path(f"/app/workspaces/{args.agent}/SOUL.md"),
        ]:
            if candidate.exists():
                soul_path = candidate
                break

    daemon = IRCDaemon(
        agent_name=args.agent,
        channels=channels,
        data_dir=data_dir,
        soul_path=soul_path,
    )

    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")


if __name__ == "__main__":
    main()
