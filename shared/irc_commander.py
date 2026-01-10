#!/usr/bin/env python3
"""
IRC Commander for Karmacadabra Agent Fleet

This is the bridge between IRC and the agent fleet. It:
1. Connects to IRC server and joins control channels
2. Listens for signed commands from authorized users
3. Translates commands to Tasks and publishes to Redis Streams
4. Subscribes to Redis results and publishes back to IRC
5. Maintains agent presence list via heartbeats

Security:
- All commands must be HMAC-signed
- Rate limiting per user
- Action whitelist
- Audit logging

Usage:
    # Set environment variables
    export IRC_SERVER=irc.libera.chat
    export IRC_PORT=6667
    export IRC_NICK=uvd_commander
    export IRC_CHANNEL=#karma-cabra
    export IRC_HMAC_SECRET=your-secret-here
    export REDIS_URL=redis://localhost:6379/0

    # Run
    python -m shared.irc_commander
"""

import os
import sys
import json
import time
import asyncio
import logging
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Redis not installed. Run: pip install redis")

try:
    from irc.bot import SingleServerIRCBot
    from irc.connection import Factory as IRCFactory
    import irc.strings
    IRC_AVAILABLE = True
except ImportError:
    IRC_AVAILABLE = False
    print("IRC library not installed. Run: pip install irc")

from .irc_protocol import (
    Task,
    TaskResult,
    TaskStatus,
    CommandType,
    RateLimiter,
    STREAM_TASKS,
    STREAM_RESULTS,
    STREAM_EVENTS,
    HEARTBEAT_PREFIX,
    IRC_CHANNEL_COMMANDS,
    IRC_CHANNEL_ALERTS,
    IRC_CHANNEL_LOGS,
    now_ts,
    make_task_id,
    sign_command,
    verify_command,
    parse_irc_command,
    PRIVILEGED_COMMANDS,
    PUBLIC_COMMANDS,
)


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("irc_commander")


@dataclass
class CommanderConfig:
    """Configuration for IRC Commander"""
    # IRC settings
    irc_server: str = "irc.libera.chat"
    irc_port: int = 6667
    irc_nick: str = "uvd_commander"
    irc_channels: List[str] = None
    irc_use_ssl: bool = False

    # Security
    hmac_secret: str = ""
    allowed_users: Set[str] = None  # If None, any signed command is accepted
    privileged_users: Set[str] = None  # Users allowed to run privileged commands

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate limiting
    rate_limit_requests: int = 20
    rate_limit_window_sec: int = 60

    def __post_init__(self):
        if self.irc_channels is None:
            self.irc_channels = [IRC_CHANNEL_COMMANDS]
        if self.allowed_users is None:
            self.allowed_users = set()
        if self.privileged_users is None:
            self.privileged_users = set()

    @classmethod
    def from_env(cls) -> "CommanderConfig":
        """Load configuration from environment variables"""
        allowed = os.getenv("IRC_ALLOWED_USERS", "")
        privileged = os.getenv("IRC_PRIVILEGED_USERS", "")

        return cls(
            irc_server=os.getenv("IRC_SERVER", "irc.libera.chat"),
            irc_port=int(os.getenv("IRC_PORT", "6667")),
            irc_nick=os.getenv("IRC_NICK", "uvd_commander"),
            irc_channels=os.getenv("IRC_CHANNELS", IRC_CHANNEL_COMMANDS).split(","),
            irc_use_ssl=os.getenv("IRC_USE_SSL", "false").lower() == "true",
            hmac_secret=os.getenv("IRC_HMAC_SECRET", ""),
            allowed_users=set(allowed.split(",")) if allowed else set(),
            privileged_users=set(privileged.split(",")) if privileged else set(),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            rate_limit_requests=int(os.getenv("IRC_RATE_LIMIT", "20")),
            rate_limit_window_sec=int(os.getenv("IRC_RATE_WINDOW", "60")),
        )


class IRCCommander(SingleServerIRCBot):
    """
    IRC bot that bridges commands to the agent fleet via Redis

    Commands (all require |sig=<hmac>):
        !agents              - List online agents
        !ping <target>       - Ping agents
        !status <target>     - Get agent status
        !dispatch <target> <action> <json>  - Send custom command
        !halt <target>       - Halt agent(s)
        !resume <target>     - Resume agent(s)
        !help                - Show help
    """

    def __init__(self, config: CommanderConfig):
        if not IRC_AVAILABLE:
            raise RuntimeError("IRC library not installed")
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis library not installed")

        self.config = config

        # Validate secret
        if not config.hmac_secret:
            raise ValueError("IRC_HMAC_SECRET is required")

        # IRC connection
        server_list = [(config.irc_server, config.irc_port)]
        super().__init__(
            server_list,
            config.irc_nick,
            config.irc_nick,
        )

        # Redis (sync for IRC callbacks)
        self.rds = redis.Redis.from_url(config.redis_url, decode_responses=False)

        # Security
        self.rate_limiter = RateLimiter(
            max_requests=config.rate_limit_requests,
            window_sec=config.rate_limit_window_sec,
        )

        # Command prefix
        self.cmd_prefix = "!"

        # Allowed actions
        self.allowed_actions = {cmd.value for cmd in CommandType}

        # Result subscriber thread
        self._result_thread: Optional[threading.Thread] = None
        self._running = True

        logger.info(
            f"Commander initialized. Server: {config.irc_server}:{config.irc_port}, "
            f"Channels: {config.irc_channels}"
        )

    def on_welcome(self, connection, event):
        """Called when connected to IRC server"""
        logger.info(f"Connected to {self.config.irc_server}")

        # Join channels
        for channel in self.config.irc_channels:
            connection.join(channel)
            logger.info(f"Joined {channel}")

        # Announce presence
        main_channel = self.config.irc_channels[0]
        connection.privmsg(main_channel, "uvd_commander online. Type !help for commands.")

        # Start result subscriber
        self._start_result_subscriber()

    def on_pubmsg(self, connection, event):
        """Handle public messages in channels"""
        msg = event.arguments[0].strip()
        nick = event.source.nick
        channel = event.target

        if not msg.startswith(self.cmd_prefix):
            return

        # Rate limit check
        if not self.rate_limiter.check(nick):
            connection.privmsg(channel, f"{nick}: Rate limit exceeded. Try again later.")
            return

        try:
            self._handle_command(connection, channel, nick, msg)
        except Exception as e:
            logger.error(f"Command error from {nick}: {e}")
            connection.privmsg(channel, f"{nick}: Error: {str(e)[:100]}")

    def _handle_command(self, connection, channel: str, nick: str, msg: str):
        """Parse and execute a command"""
        # Help doesn't require signature
        if msg.startswith("!help"):
            self._send_help(connection, channel, nick)
            return

        # Agents list doesn't require signature (read-only)
        if msg.startswith("!agents"):
            self._handle_agents(connection, channel)
            return

        # All other commands require signature
        try:
            raw, sig = parse_irc_command(msg)
        except ValueError as e:
            connection.privmsg(channel, f"{nick}: {e}")
            return

        # Verify signature
        if not verify_command(self.config.hmac_secret, raw, sig):
            connection.privmsg(channel, f"{nick}: Invalid signature")
            logger.warning(f"Invalid signature from {nick}: {raw}")
            return

        # Check user permissions
        if self.config.allowed_users and nick not in self.config.allowed_users:
            connection.privmsg(channel, f"{nick}: Not authorized")
            return

        # Parse command
        parts = raw.split(maxsplit=3)
        cmd = parts[0].lower()

        if cmd == "!ping":
            self._handle_ping(connection, channel, nick, parts)
        elif cmd == "!status":
            self._handle_status(connection, channel, nick, parts)
        elif cmd == "!dispatch":
            self._handle_dispatch(connection, channel, nick, parts)
        elif cmd == "!halt":
            self._handle_halt(connection, channel, nick, parts)
        elif cmd == "!resume":
            self._handle_resume(connection, channel, nick, parts)
        elif cmd == "!balance":
            self._handle_balance(connection, channel, nick, parts)
        else:
            connection.privmsg(channel, f"{nick}: Unknown command. Try !help")

    def _send_help(self, connection, channel: str, nick: str):
        """Send help message"""
        help_lines = [
            f"{nick}: Karmacadabra IRC Control",
            "Commands (append |sig=<hmac> for signed commands):",
            "  !agents - List online agents (no sig required)",
            "  !ping <target> |sig=... - Ping agent(s)",
            "  !status <target> |sig=... - Get status",
            "  !dispatch <target> <action> <json> |sig=... - Send command",
            "  !halt <target> |sig=... - Halt agent(s)",
            "  !resume <target> |sig=... - Resume agent(s)",
            "  !balance <target> |sig=... - Check balance",
            "Targets: agent:<id>, agent:all, karma-cabra:all, role:<role>",
        ]
        for line in help_lines:
            connection.privmsg(channel, line)

    def _handle_agents(self, connection, channel: str):
        """List online agents from heartbeat keys"""
        keys = self.rds.keys(f"{HEARTBEAT_PREFIX}*")
        if not keys:
            connection.privmsg(channel, "No agents online")
            return

        agents = []
        now = now_ts()
        for key in keys:
            agent_id = key.decode().split(":")[-1]
            ts = int(self.rds.get(key) or b"0")
            age = now - ts
            status = "OK" if age < 60 else f"STALE({age}s)"
            agents.append(f"{agent_id}:{status}")

        # Split into multiple messages if too long
        msg = "Agents: " + " | ".join(agents)
        if len(msg) > 400:
            connection.privmsg(channel, f"Agents online: {len(agents)}")
            for i in range(0, len(agents), 5):
                chunk = agents[i:i+5]
                connection.privmsg(channel, "  " + " | ".join(chunk))
        else:
            connection.privmsg(channel, msg)

    def _handle_ping(self, connection, channel: str, nick: str, parts: List[str]):
        """Handle !ping <target>"""
        if len(parts) < 2:
            connection.privmsg(channel, f"{nick}: Usage: !ping <target> |sig=...")
            return

        target = parts[1]
        task = Task(
            task_id=make_task_id("ping"),
            target=target,
            action=CommandType.PING.value,
            payload={},
            sender=nick,
            ttl_sec=30,
        )
        self._enqueue_task(task)
        connection.privmsg(channel, f"{nick}: Ping sent to {target} id={task.task_id}")

    def _handle_status(self, connection, channel: str, nick: str, parts: List[str]):
        """Handle !status <target>"""
        if len(parts) < 2:
            connection.privmsg(channel, f"{nick}: Usage: !status <target> |sig=...")
            return

        target = parts[1]
        task = Task(
            task_id=make_task_id("status"),
            target=target,
            action=CommandType.STATUS.value,
            payload={},
            sender=nick,
            ttl_sec=30,
        )
        self._enqueue_task(task)
        connection.privmsg(channel, f"{nick}: Status request sent to {target} id={task.task_id}")

    def _handle_dispatch(self, connection, channel: str, nick: str, parts: List[str]):
        """Handle !dispatch <target> <action> <json>"""
        if len(parts) < 4:
            connection.privmsg(
                channel,
                f"{nick}: Usage: !dispatch <target> <action> <json> |sig=..."
            )
            return

        target = parts[1]
        action = parts[2]
        payload_json = parts[3]

        # Validate action
        if action not in self.allowed_actions:
            connection.privmsg(channel, f"{nick}: Action not allowed: {action}")
            return

        # Check privileged actions
        if action in {cmd.value for cmd in PRIVILEGED_COMMANDS}:
            if self.config.privileged_users and nick not in self.config.privileged_users:
                connection.privmsg(channel, f"{nick}: Privileged action requires elevated access")
                return

        # Parse payload
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as e:
            connection.privmsg(channel, f"{nick}: Invalid JSON: {e}")
            return

        task = Task(
            task_id=make_task_id("dispatch"),
            target=target,
            action=action,
            payload=payload,
            sender=nick,
            ttl_sec=int(payload.get("ttl_sec", 60)),
            priority=int(payload.get("priority", 1)),
        )
        self._enqueue_task(task)
        connection.privmsg(
            channel,
            f"{nick}: Dispatched {action} to {target} id={task.task_id}"
        )

    def _handle_halt(self, connection, channel: str, nick: str, parts: List[str]):
        """Handle !halt <target>"""
        # Check privileged
        if self.config.privileged_users and nick not in self.config.privileged_users:
            connection.privmsg(channel, f"{nick}: HALT requires elevated access")
            return

        if len(parts) < 2:
            connection.privmsg(channel, f"{nick}: Usage: !halt <target> |sig=...")
            return

        target = parts[1]
        reason = " ".join(parts[2:]) if len(parts) > 2 else f"Halted by {nick}"

        task = Task(
            task_id=make_task_id("halt"),
            target=target,
            action=CommandType.HALT.value,
            payload={"reason": reason},
            sender=nick,
            ttl_sec=60,
            priority=2,
        )
        self._enqueue_task(task)
        connection.privmsg(channel, f"{nick}: HALT sent to {target} id={task.task_id}")
        logger.warning(f"HALT command from {nick} to {target}: {reason}")

    def _handle_resume(self, connection, channel: str, nick: str, parts: List[str]):
        """Handle !resume <target>"""
        if self.config.privileged_users and nick not in self.config.privileged_users:
            connection.privmsg(channel, f"{nick}: RESUME requires elevated access")
            return

        if len(parts) < 2:
            connection.privmsg(channel, f"{nick}: Usage: !resume <target> |sig=...")
            return

        target = parts[1]
        task = Task(
            task_id=make_task_id("resume"),
            target=target,
            action=CommandType.RESUME.value,
            payload={},
            sender=nick,
            ttl_sec=60,
            priority=2,
        )
        self._enqueue_task(task)
        connection.privmsg(channel, f"{nick}: RESUME sent to {target} id={task.task_id}")
        logger.info(f"RESUME command from {nick} to {target}")

    def _handle_balance(self, connection, channel: str, nick: str, parts: List[str]):
        """Handle !balance <target>"""
        if len(parts) < 2:
            connection.privmsg(channel, f"{nick}: Usage: !balance <target> |sig=...")
            return

        target = parts[1]
        task = Task(
            task_id=make_task_id("balance"),
            target=target,
            action=CommandType.BALANCE.value,
            payload={},
            sender=nick,
            ttl_sec=30,
        )
        self._enqueue_task(task)
        connection.privmsg(channel, f"{nick}: Balance request sent to {target} id={task.task_id}")

    def _enqueue_task(self, task: Task):
        """Add task to Redis Stream"""
        self.rds.xadd(STREAM_TASKS, task.to_redis())
        logger.info(f"Enqueued task: {task.task_id} action={task.action} target={task.target}")

    def _start_result_subscriber(self):
        """Start background thread to listen for results"""
        self._result_thread = threading.Thread(target=self._result_loop, daemon=True)
        self._result_thread.start()
        logger.info("Result subscriber started")

    def _result_loop(self):
        """Background loop to read results and publish to IRC"""
        # Create separate Redis connection for blocking reads
        rds = redis.Redis.from_url(self.config.redis_url, decode_responses=False)

        # Start from current time
        last_id = "$"

        while self._running:
            try:
                # Read new results
                messages = rds.xread(
                    {STREAM_RESULTS: last_id},
                    count=10,
                    block=2000,
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        last_id = msg_id.decode()
                        self._handle_result(fields)

            except Exception as e:
                logger.error(f"Result loop error: {e}")
                time.sleep(1)

    def _handle_result(self, fields: Dict[bytes, bytes]):
        """Process a result and send to IRC"""
        try:
            result = TaskResult.from_redis(fields)
            msg = result.to_irc()

            # Send to main channel
            main_channel = self.config.irc_channels[0]
            self.connection.privmsg(main_channel, msg)

        except Exception as e:
            logger.error(f"Error handling result: {e}")

    def disconnect(self, msg="Shutting down"):
        """Clean shutdown"""
        self._running = False
        if self._result_thread:
            self._result_thread.join(timeout=2)
        super().disconnect(msg)


def main():
    """Main entry point"""
    if not IRC_AVAILABLE or not REDIS_AVAILABLE:
        print("Required dependencies not installed:")
        if not IRC_AVAILABLE:
            print("  pip install irc")
        if not REDIS_AVAILABLE:
            print("  pip install redis")
        sys.exit(1)

    config = CommanderConfig.from_env()

    if not config.hmac_secret:
        print("ERROR: IRC_HMAC_SECRET environment variable is required")
        print("Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
        sys.exit(1)

    commander = IRCCommander(config)

    try:
        logger.info("Starting IRC Commander...")
        commander.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        commander.disconnect()


if __name__ == "__main__":
    main()
