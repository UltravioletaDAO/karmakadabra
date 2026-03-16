"""
Karma Kadabra V2 — IRC Service

IRC integration service for KK agent swarm communication on MeshRelay.
Provides heartbeat announcements, message polling, task negotiation
forwarding, and channel management.

Can be used as:
  1. CLI tool for individual agent actions
  2. Library imported by swarm_runner.py for heartbeat integration

Usage (CLI):
  python irc_service.py connect --config workspace/irc-config.json
  python irc_service.py send --config workspace/irc-config.json --message "Hello"
  python irc_service.py send --config workspace/irc-config.json --target kk-agent --message "DM"
  python irc_service.py read --config workspace/irc-config.json --new
  python irc_service.py read --config workspace/irc-config.json --tail 10
  python irc_service.py heartbeat --config workspace/irc-config.json --status idle
  python irc_service.py disconnect --config workspace/irc-config.json

Usage (Library):
  from services.irc_service import IRCService
  svc = IRCService.from_config("workspace/irc-config.json")
  svc.connect()
  svc.announce_heartbeat("idle", budget_remaining=1.50, skills=["DeFi", "AI"])
  messages = svc.poll_messages()
  svc.disconnect()
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.irc_client import IRCClient, IRCMessage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.irc_service")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class IRCConfig:
    """IRC configuration for one KK agent."""

    server: str = "irc.meshrelay.xyz"
    port: int = 6667
    tls: bool = False
    tls_port: int = 6697
    nick: str = "kk-agent"
    channels: list[str] = field(default_factory=lambda: ["#Agents"])
    realname: str = "Karma Kadabra Agent - Ultravioleta DAO"
    auto_join: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> IRCConfig:
        """Load config from JSON file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"IRC config not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(
            server=data.get("server", "irc.meshrelay.xyz"),
            port=data.get("port", 6667),
            tls=data.get("tls", False),
            tls_port=data.get("tls_port", data.get("port_ssl", 6697)),
            nick=data.get("nick", "kk-agent"),
            channels=data.get("channels", ["#Agents"]),
            realname=data.get("realname", "Karma Kadabra Agent - Ultravioleta DAO"),
            auto_join=data.get("auto_join", True),
        )


# ---------------------------------------------------------------------------
# IRC Service
# ---------------------------------------------------------------------------


class IRCService:
    """High-level IRC service for KK agents."""

    def __init__(self, config: IRCConfig):
        self.config = config
        self.client = IRCClient(
            server=config.server,
            port=config.port,
            nick=config.nick,
            realname=config.realname,
            use_tls=config.tls,
            tls_port=config.tls_port,
        )
        self._message_log: list[IRCMessage] = []
        self._read_cursor = 0

    @classmethod
    def from_config(cls, config_path: str | Path) -> IRCService:
        """Create service from config file path."""
        config = IRCConfig.from_file(config_path)
        return cls(config)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 15.0) -> bool:
        """Connect to IRC and join configured channels."""
        ok = self.client.connect(timeout=timeout)
        if not ok:
            return False

        if self.config.auto_join:
            for channel in self.config.channels:
                self.client.join(channel)
                time.sleep(0.3)

        return True

    def disconnect(self) -> None:
        """Send goodbye and disconnect."""
        main_channel = self.config.channels[0] if self.config.channels else "#Agents"
        try:
            self.client.send_message(main_channel, f"[BYE] {self.config.nick} signing off.")
        except Exception:
            pass
        self.client.disconnect()

    @property
    def connected(self) -> bool:
        return self.client.connected

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def send(self, message: str, target: str | None = None) -> None:
        """Send a message to a channel or specific user.

        Args:
            message: Message text.
            target: Channel or nick. Defaults to first configured channel.
        """
        if target is None:
            target = self.config.channels[0] if self.config.channels else "#Agents"
        self.client.send_message(target, message)

    def send_dm(self, nick: str, message: str) -> None:
        """Send a direct message to a specific nick."""
        self.client.send_message(nick, message)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def announce_heartbeat(
        self,
        status: str = "idle",
        budget_remaining: float = 0.0,
        budget_total: float = 2.0,
        skills: list[str] | None = None,
        task_id: str | None = None,
    ) -> None:
        """Announce agent status to the main channel.

        Sends a formatted [STATUS] message.
        """
        skill_str = ", ".join(skills[:3]) if skills else "general"
        budget_str = f"${budget_remaining:.2f}/${budget_total:.2f}"

        parts = [
            f"[STATUS] {self.config.nick}",
            status,
            f"budget: {budget_str}",
            f"skills: {skill_str}",
        ]
        if task_id:
            parts.append(f"task: {task_id[:8]}")

        msg = " | ".join(parts)
        self.send(msg)

    # ------------------------------------------------------------------
    # Message polling
    # ------------------------------------------------------------------

    def poll_messages(self) -> list[IRCMessage]:
        """Get all new messages since last poll."""
        new_msgs = self.client.poll_all()
        self._message_log.extend(new_msgs)
        return new_msgs

    def get_new_messages(self) -> list[IRCMessage]:
        """Get messages received since last read cursor."""
        # First drain from client
        new_msgs = self.client.poll_all()
        self._message_log.extend(new_msgs)

        # Return unread
        unread = self._message_log[self._read_cursor :]
        self._read_cursor = len(self._message_log)
        return unread

    def get_tail(self, count: int = 10) -> list[IRCMessage]:
        """Get last N messages from the log."""
        # Drain first
        new_msgs = self.client.poll_all()
        self._message_log.extend(new_msgs)
        return self._message_log[-count:]

    def get_mentions(self, nick: str | None = None) -> list[IRCMessage]:
        """Get messages that mention the agent's nick."""
        target_nick = nick or self.config.nick
        pattern = target_nick.lower()
        return [
            m
            for m in self._message_log
            if pattern in m.text.lower() or pattern in m.trailing.lower()
        ]

    # ------------------------------------------------------------------
    # Task negotiation helpers
    # ------------------------------------------------------------------

    def announce_task(
        self,
        title: str,
        bounty_usd: float,
        category: str = "",
    ) -> None:
        """Announce a task to the channel."""
        cat_str = f" [{category}]" if category else ""
        self.send(f"[TASK]{cat_str} {title} - ${bounty_usd:.2f} USDC")

    def announce_offer(self, description: str, price_usd: float) -> None:
        """Announce a service/data offer."""
        self.send(f"[OFFER] {description} - ${price_usd:.2f} USDC")

    def announce_request(self, description: str, max_budget: float) -> None:
        """Post a request for services/data."""
        self.send(f"[REQUEST] {description} - budget: ${max_budget:.2f} USDC")

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    def create_channel(self, channel_name: str) -> None:
        """Create and join a new channel."""
        if not channel_name.startswith("#"):
            channel_name = f"#{channel_name}"
        self.client.join(channel_name)

    def leave_channel(self, channel_name: str) -> None:
        """Leave a channel."""
        self.client.part(channel_name)


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------


def cli_connect(args: argparse.Namespace) -> None:
    """Connect and stay connected (blocking)."""
    svc = IRCService.from_config(args.config)
    ok = svc.connect()
    if not ok:
        print("ERROR: Failed to connect")
        sys.exit(1)
    print(f"Connected as {svc.client.nick}")
    print("Press Ctrl+C to disconnect")
    try:
        while svc.connected:
            msgs = svc.poll_messages()
            for m in msgs:
                print(f"[{m.channel}] <{m.nick}> {m.text}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        svc.disconnect()


def cli_send(args: argparse.Namespace) -> None:
    """Connect, send one message, disconnect."""
    svc = IRCService.from_config(args.config)
    ok = svc.connect()
    if not ok:
        print("ERROR: Failed to connect")
        sys.exit(1)
    time.sleep(1)  # Wait for JOIN to complete
    target = args.target if args.target else None
    svc.send(args.message, target=target)
    time.sleep(0.5)
    svc.disconnect()
    print(f"Sent: {args.message}")


def cli_read(args: argparse.Namespace) -> None:
    """Connect, read messages, disconnect."""
    svc = IRCService.from_config(args.config)
    ok = svc.connect()
    if not ok:
        print("ERROR: Failed to connect")
        sys.exit(1)

    # Wait for messages
    wait = args.wait if hasattr(args, "wait") else 5
    time.sleep(wait)

    if args.new:
        msgs = svc.get_new_messages()
    elif args.tail:
        msgs = svc.get_tail(args.tail)
    else:
        msgs = svc.poll_messages()

    for m in msgs:
        print(f"[{m.channel}] <{m.nick}> {m.text}")

    if not msgs:
        print("(no messages)")

    svc.disconnect()


def cli_heartbeat(args: argparse.Namespace) -> None:
    """Connect, send heartbeat, disconnect."""
    svc = IRCService.from_config(args.config)
    ok = svc.connect()
    if not ok:
        print("ERROR: Failed to connect")
        sys.exit(1)
    time.sleep(1)

    skills = args.skills.split(",") if args.skills else []
    svc.announce_heartbeat(
        status=args.status,
        budget_remaining=args.budget or 2.0,
        skills=skills,
    )
    time.sleep(0.5)
    svc.disconnect()
    print(f"Heartbeat sent: status={args.status}")


def cli_disconnect(args: argparse.Namespace) -> None:
    """Send disconnect message."""
    svc = IRCService.from_config(args.config)
    ok = svc.connect()
    if ok:
        svc.disconnect()
    print("Disconnected")


def main() -> None:
    parser = argparse.ArgumentParser(description="KK IRC Service")
    sub = parser.add_subparsers(dest="command")

    # connect
    p_conn = sub.add_parser("connect", help="Connect and listen")
    p_conn.add_argument("--config", required=True, help="Path to irc-config.json")

    # send
    p_send = sub.add_parser("send", help="Send a message")
    p_send.add_argument("--config", required=True)
    p_send.add_argument("--message", "-m", required=True)
    p_send.add_argument("--target", "-t", default=None, help="Channel or nick (default: main channel)")

    # read
    p_read = sub.add_parser("read", help="Read messages")
    p_read.add_argument("--config", required=True)
    p_read.add_argument("--new", action="store_true", help="Only unread")
    p_read.add_argument("--tail", type=int, default=None, help="Last N messages")
    p_read.add_argument("--wait", type=int, default=5, help="Seconds to wait for messages")

    # heartbeat
    p_hb = sub.add_parser("heartbeat", help="Send heartbeat status")
    p_hb.add_argument("--config", required=True)
    p_hb.add_argument("--status", default="idle", choices=["idle", "busy", "offline"])
    p_hb.add_argument("--budget", type=float, default=None)
    p_hb.add_argument("--skills", default="", help="Comma-separated skills")

    # disconnect
    p_disc = sub.add_parser("disconnect", help="Disconnect")
    p_disc.add_argument("--config", required=True)

    args = parser.parse_args()

    if args.command == "connect":
        cli_connect(args)
    elif args.command == "send":
        cli_send(args)
    elif args.command == "read":
        cli_read(args)
    elif args.command == "heartbeat":
        cli_heartbeat(args)
    elif args.command == "disconnect":
        cli_disconnect(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
