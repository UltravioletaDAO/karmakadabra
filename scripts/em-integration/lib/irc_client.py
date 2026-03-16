"""
Karma Kadabra V2 — IRC Client Library

Lightweight IRC client for KK agents to communicate on MeshRelay
(irc.meshrelay.xyz). Supports channels, DMs, and basic IRC protocol.

Uses raw sockets (no external dependencies) for maximum portability.

Usage:
    from lib.irc_client import IRCClient

    client = IRCClient("irc.meshrelay.xyz", 6667, "kk-agent-name")
    client.connect()
    client.join("#Agents")
    client.send_message("#Agents", "[HELLO] Online!")
    messages = client.poll_messages()
    client.disconnect()
"""

from __future__ import annotations

import logging
import queue
import re
import select
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger("kk.irc_client")


@dataclass
class IRCMessage:
    """Parsed IRC message."""

    raw: str
    prefix: str = ""
    nick: str = ""
    command: str = ""
    params: list[str] = field(default_factory=list)
    trailing: str = ""
    timestamp: float = 0.0

    @property
    def channel(self) -> str:
        """Target channel or nick for PRIVMSG/NOTICE."""
        if self.params:
            return self.params[0]
        return ""

    @property
    def text(self) -> str:
        """Message text (trailing param)."""
        return self.trailing

    @property
    def is_private(self) -> bool:
        """True if this is a DM (not a channel message)."""
        return bool(self.channel) and not self.channel.startswith("#")


def parse_irc_message(raw: str) -> IRCMessage:
    """Parse a raw IRC protocol line into an IRCMessage."""
    msg = IRCMessage(raw=raw, timestamp=time.time())

    line = raw.strip()
    if not line:
        return msg

    # Extract trailing (after " :")
    trailing = ""
    if " :" in line:
        idx = line.index(" :")
        trailing = line[idx + 2 :]
        line = line[:idx]
    msg.trailing = trailing

    parts = line.split()
    if not parts:
        return msg

    idx = 0

    # Prefix starts with ':'
    if parts[0].startswith(":"):
        msg.prefix = parts[0][1:]
        # Extract nick from prefix (nick!user@host)
        if "!" in msg.prefix:
            msg.nick = msg.prefix.split("!")[0]
        else:
            msg.nick = msg.prefix
        idx = 1

    if idx < len(parts):
        msg.command = parts[idx].upper()
        idx += 1

    msg.params = parts[idx:]

    return msg


class IRCClient:
    """Simple IRC client for KK agent communication."""

    def __init__(
        self,
        server: str = "irc.meshrelay.xyz",
        port: int = 6667,
        nick: str = "kk-agent",
        realname: str = "Karma Kadabra Agent - Ultravioleta DAO",
        use_tls: bool = False,
        tls_port: int = 6697,
    ):
        self.server = server
        self.port = tls_port if use_tls else port
        self.nick = nick
        self.realname = realname
        self.use_tls = use_tls

        self._sock: socket.socket | None = None
        self._connected = False
        self._registered = False
        self._channels: set[str] = set()
        self._recv_buffer = ""

        # Thread-safe message queue
        self._inbox: queue.Queue[IRCMessage] = queue.Queue(maxsize=1000)
        self._recv_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Callbacks
        self._on_message: Callable[[IRCMessage], None] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def channels(self) -> set[str]:
        return self._channels.copy()

    def on_message(self, callback: Callable[[IRCMessage], None]) -> None:
        """Register a callback for incoming messages."""
        self._on_message = callback

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 15.0) -> bool:
        """Connect to IRC server and register."""
        try:
            raw_sock = socket.create_connection(
                (self.server, self.port), timeout=timeout
            )

            if self.use_tls:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                self._sock = ctx.wrap_socket(raw_sock, server_hostname=self.server)
            else:
                self._sock = raw_sock

            self._sock.settimeout(1.0)
            self._connected = True

            # Send NICK and USER
            self._send(f"NICK {self.nick}")
            self._send(f"USER {self.nick} 0 * :{self.realname}")

            # Wait for registration (001 RPL_WELCOME)
            deadline = time.time() + timeout
            while time.time() < deadline:
                lines = self._recv_lines()
                for line in lines:
                    msg = parse_irc_message(line)
                    if msg.command == "001":
                        self._registered = True
                        logger.info(
                            f"Connected to {self.server}:{self.port} as {self.nick}"
                        )
                        # Start background receiver
                        self._stop_event.clear()
                        self._recv_thread = threading.Thread(
                            target=self._recv_loop, daemon=True
                        )
                        self._recv_thread.start()
                        return True
                    elif msg.command == "PING":
                        self._send(f"PONG :{msg.trailing}")
                    elif msg.command in ("433", "436"):
                        # Nick already in use — append timestamp
                        self.nick = f"{self.nick}-{int(time.time()) % 10000}"
                        self._send(f"NICK {self.nick}")
                        logger.warning(f"Nick collision, retrying as {self.nick}")

            logger.error(f"Timeout waiting for registration on {self.server}")
            self.disconnect()
            return False

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Gracefully disconnect from IRC."""
        self._stop_event.set()
        if self._sock and self._connected:
            try:
                self._send("QUIT :Karma Kadabra agent signing off")
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self._connected = False
        self._registered = False
        self._channels.clear()
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=3.0)
        logger.info("Disconnected")

    # ------------------------------------------------------------------
    # Channel operations
    # ------------------------------------------------------------------

    def join(self, channel: str) -> None:
        """Join an IRC channel."""
        if not channel.startswith("#"):
            channel = f"#{channel}"
        self._send(f"JOIN {channel}")
        self._channels.add(channel)
        logger.info(f"Joined {channel}")

    def part(self, channel: str, message: str = "Leaving") -> None:
        """Leave an IRC channel."""
        if not channel.startswith("#"):
            channel = f"#{channel}"
        self._send(f"PART {channel} :{message}")
        self._channels.discard(channel)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def send_message(self, target: str, message: str) -> None:
        """Send a PRIVMSG to a channel or nick.

        Args:
            target: Channel name (#Agents) or nick for DM.
            message: Message text (max 400 chars to be safe).
        """
        # IRC line limit is 512 bytes including CRLF; be conservative
        for chunk in self._split_message(message, max_len=400):
            self._send(f"PRIVMSG {target} :{chunk}")

    def send_notice(self, target: str, message: str) -> None:
        """Send a NOTICE (no auto-reply expected)."""
        self._send(f"NOTICE {target} :{message}")

    # ------------------------------------------------------------------
    # Message polling
    # ------------------------------------------------------------------

    def poll_messages(self, max_count: int = 100) -> list[IRCMessage]:
        """Drain up to max_count messages from the inbox queue.

        Returns list of IRCMessage with command=PRIVMSG (chat messages).
        Non-blocking.
        """
        messages: list[IRCMessage] = []
        while len(messages) < max_count:
            try:
                msg = self._inbox.get_nowait()
                messages.append(msg)
            except queue.Empty:
                break
        return messages

    def poll_all(self) -> list[IRCMessage]:
        """Drain all pending messages."""
        return self.poll_messages(max_count=10000)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(self, line: str) -> None:
        """Send a raw IRC line."""
        if not self._sock:
            return
        try:
            self._sock.sendall((line + "\r\n").encode("utf-8", errors="replace"))
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self._connected = False

    def _recv_lines(self) -> list[str]:
        """Read available data and return complete lines."""
        if not self._sock:
            return []
        try:
            data = self._sock.recv(4096)
            if not data:
                self._connected = False
                return []
            self._recv_buffer += data.decode("utf-8", errors="replace")
        except socket.timeout:
            return []
        except Exception as e:
            logger.error(f"Recv failed: {e}")
            self._connected = False
            return []

        lines = []
        while "\r\n" in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split("\r\n", 1)
            if line.strip():
                lines.append(line)
        return lines

    def _recv_loop(self) -> None:
        """Background thread: read messages and enqueue PRIVMSG/NOTICE."""
        while not self._stop_event.is_set() and self._connected:
            lines = self._recv_lines()
            for line in lines:
                msg = parse_irc_message(line)

                # Handle PING
                if msg.command == "PING":
                    self._send(f"PONG :{msg.trailing}")
                    continue

                # Enqueue chat messages
                if msg.command in ("PRIVMSG", "NOTICE"):
                    try:
                        self._inbox.put_nowait(msg)
                    except queue.Full:
                        # Drop oldest
                        try:
                            self._inbox.get_nowait()
                            self._inbox.put_nowait(msg)
                        except queue.Empty:
                            pass

                    # Fire callback if registered
                    if self._on_message:
                        try:
                            self._on_message(msg)
                        except Exception as e:
                            logger.error(f"on_message callback error: {e}")

            if not lines:
                time.sleep(0.1)

    @staticmethod
    def _split_message(text: str, max_len: int = 400) -> list[str]:
        """Split a long message into IRC-safe chunks."""
        if len(text) <= max_len:
            return [text]
        chunks = []
        while text:
            chunks.append(text[:max_len])
            text = text[max_len:]
        return chunks
