"""
Karma Kadabra V2 — Task 5.5: MeshRelay IRC Integration

Connects KK agents to MeshRelay IRC for real-time communication,
marketplace negotiations, and deal execution.

Channels:
  #Agents         — General agent communication
  #kk-ops         — Swarm coordination (system agents only)
  #kk-data-market — Data marketplace (buy/sell offerings)

Agent behaviors:
  - Post "HAVE:" messages when publishing new EM offerings
  - Post "NEED:" messages when looking for specific data
  - Respond to queries about their skills/capabilities
  - Negotiate deals that execute on EM

Usage:
  python agent_irc_client.py --agent kk-juanjumagalp
  python agent_irc_client.py --agent kk-coordinator --channel "#kk-ops"
  python agent_irc_client.py --list-agents
"""

import argparse
import asyncio
import json
import logging
import random
import socket
import ssl
import time
from pathlib import Path

# Turnstile integration (premium channel access)
try:
    from lib.turnstile_client import TurnstileClient, ChannelInfo, AccessResult
    HAS_TURNSTILE = True
except ImportError:
    HAS_TURNSTILE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.irc")

# IRC server config
IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667
IRC_SSL_PORT = 6697
DEFAULT_CHANNELS = ["#Agents", "#kk-data-market"]
RECONNECT_DELAY = 30
PING_INTERVAL = 120


class IRCAgent:
    """Single KK agent connected to MeshRelay IRC."""

    def __init__(
        self,
        nick: str,
        channels: list[str],
        workspace_dir: Path | None = None,
        use_ssl: bool = False,
    ):
        self.nick = nick
        self.channels = channels
        self.workspace_dir = workspace_dir
        self.use_ssl = use_ssl
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._running = True
        self._wallet_key: str | None = None

        # Load agent profile for personality
        self._profile: dict = {}
        self._skills: list[str] = []
        self._load_profile()

    def _load_profile(self) -> None:
        if not self.workspace_dir:
            return
        soul_file = self.workspace_dir / "SOUL.md"
        profile_file = self.workspace_dir / "data" / "profile.json"

        if profile_file.exists():
            data = json.loads(profile_file.read_text(encoding="utf-8"))
            self._profile = data
            self._skills = [s.get("skill", "") for s in data.get("top_skills", [])]

    async def connect(self) -> None:
        """Connect to IRC server."""
        port = IRC_SSL_PORT if self.use_ssl else IRC_PORT

        logger.info(f"  [{self.nick}] Connecting to {IRC_SERVER}:{port}...")

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

        # Register with server
        await self._send(f"NICK {self.nick}")
        await self._send(f"USER {self.nick} 0 * :KK Agent {self.nick}")

        # Wait for welcome (001), handle NICK-in-use (433)
        while True:
            line = await self._recv()
            if not line:
                break
            if " 001 " in line:
                self._connected = True
                logger.info(f"  [{self.nick}] Connected!")
                break
            if " 433 " in line:
                # Nick already in use — append underscore and retry
                self.nick = self.nick + "_"
                logger.warning(f"  Nick in use, retrying as {self.nick}")
                await self._send(f"NICK {self.nick}")
            if "PING" in line:
                await self._handle_ping(line)

        # Join channels
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

    async def announce_offering(self, channel: str, title: str, bounty: float) -> None:
        """Announce a new EM offering on IRC."""
        msg = f"HAVE: {title} | ${bounty:.2f} USDC | Browse at execution.market"
        await self.send_message(channel, msg)

    async def post_need(self, channel: str, description: str, budget: float) -> None:
        """Post a need/request on IRC."""
        msg = f"NEED: {description} | Budget: ${budget:.2f} USDC | DM me or check EM"
        await self.send_message(channel, msg)

    async def introduce(self, channel: str) -> None:
        """Introduce agent to the channel."""
        skills_str = ", ".join(self._skills[:3]) if self._skills else "general"
        msg = f"Hey! I'm {self.nick} from KK swarm. Skills: {skills_str}. Browsing tasks on EM."
        await self.send_message(channel, msg)

    # ------------------------------------------------------------------
    # Turnstile — Premium channel access
    # ------------------------------------------------------------------

    async def join_premium_channel(self, channel_name: str, wallet_key: str | None = None) -> bool:
        """Pay x402 and join a premium channel via Turnstile.

        Uses the full 402 → sign EIP-3009 → pay flow matching the official
        MeshRelay SDK (TurnstileClient.js).

        Args:
            channel_name: Channel name (e.g., "kk-alpha" or "#kk-alpha").
            wallet_key: Hex private key for signing x402 payment.
                If None, uses self._wallet_key (set via --wallet-key arg).

        Returns:
            True if access was granted.
        """
        if not HAS_TURNSTILE:
            logger.error(f"  [{self.nick}] Turnstile client not available (install aiohttp)")
            return False

        key = wallet_key or getattr(self, "_wallet_key", None)
        if not key:
            logger.error(f"  [{self.nick}] No wallet key for Turnstile payment")
            return False

        client = TurnstileClient()

        # Check channel exists and has slots
        channel_info = await client.get_channel(channel_name)
        if not channel_info:
            logger.error(f"  [{self.nick}] Channel {channel_name} not found on Turnstile")
            return False

        if not channel_info.is_available:
            logger.error(f"  [{self.nick}] Channel {channel_name} is full ({channel_info.active_slots}/{channel_info.max_slots})")
            return False

        logger.info(
            f"  [{self.nick}] Requesting access to {channel_info.name} "
            f"(${channel_info.price} {channel_info.currency} / {channel_info.duration_seconds // 60}min)"
        )

        # Full flow: 402 → sign EIP-3009 → pay (matches official SDK)
        result = await client.request_access_with_wallet(
            channel=channel_name,
            nick=self.nick,
            private_key=key,
        )

        if result.success:
            logger.info(
                f"  [{self.nick}] Access granted to {result.channel} "
                f"until {result.expires_at} (session: {result.session_id})"
            )
            if result.channel not in self.channels:
                self.channels.append(result.channel)
            return True
        else:
            logger.error(f"  [{self.nick}] Access denied: {result.error}")
            return False

    async def list_premium_channels(self) -> list:
        """List available premium channels from Turnstile."""
        if not HAS_TURNSTILE:
            return []
        client = TurnstileClient()
        try:
            return await client.list_channels()
        except Exception as e:
            logger.error(f"  [{self.nick}] Failed to list channels: {e}")
            return []

    async def handle_message(self, sender: str, channel: str, message: str) -> None:
        """Handle an incoming IRC message."""
        msg_lower = message.lower()

        # Handle premium channel commands
        if msg_lower.startswith("!join-premium "):
            target_channel = message.split(" ", 1)[1].strip()
            if hasattr(self, "_wallet_key") and self._wallet_key:
                success = await self.join_premium_channel(target_channel)
                status = "Joined!" if success else "Failed to join"
                await self.send_message(channel, f"{sender}: {status} {target_channel}")
            else:
                await self.send_message(channel, f"{sender}: No wallet key configured for payments")
            return

        if msg_lower.strip() == "!channels":
            channels_list = await self.list_premium_channels()
            if channels_list:
                for ch in channels_list:
                    await self.send_message(
                        channel,
                        f"  {ch.name}: ${ch.price} {ch.currency} / "
                        f"{ch.duration_seconds // 60}min "
                        f"[{ch.available_slots} slots] — {ch.description}",
                    )
            else:
                await self.send_message(channel, "No premium channels available")
            return

        # Respond to direct mentions
        if self.nick.lower() in msg_lower:
            if "skills" in msg_lower or "what can you do" in msg_lower:
                skills_str = ", ".join(self._skills[:5]) if self._skills else "general knowledge"
                await self.send_message(channel, f"{sender}: My skills: {skills_str}")
            elif "help" in msg_lower:
                await self.send_message(
                    channel,
                    f"{sender}: I buy/sell data on execution.market. Ask me about my offerings!",
                )

        # Respond to marketplace queries
        if channel == "#kk-data-market":
            if msg_lower.startswith("need:") and any(s.lower() in msg_lower for s in self._skills):
                await self.send_message(
                    channel,
                    f"{sender}: I might be able to help with that! Check my offerings on EM.",
                )

    async def listen(self) -> None:
        """Main listen loop — process incoming messages."""
        logger.info(f"  [{self.nick}] Listening...")

        while self._running and self._connected:
            line = await self._recv()
            if not line:
                # Possible timeout — send ping
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
                    channel, _, message = rest.partition(" :")
                    await self.handle_message(sender, channel, message)
                except Exception:
                    pass

    async def disconnect(self) -> None:
        """Disconnect from IRC."""
        self._running = False
        if self._writer:
            await self._send("QUIT :KK agent signing off")
            self._writer.close()
        logger.info(f"  [{self.nick}] Disconnected")


async def run_agent(
    agent_name: str,
    workspace_dir: Path | None,
    channels: list[str],
    introduce: bool = True,
    duration: int = 0,
    wallet_key: str | None = None,
    premium_channels: list[str] | None = None,
) -> None:
    """Run a single IRC agent."""
    agent = IRCAgent(
        nick=agent_name,
        channels=channels,
        workspace_dir=workspace_dir,
    )
    if wallet_key:
        agent._wallet_key = wallet_key

    try:
        await agent.connect()

        if introduce:
            await asyncio.sleep(2)
            for ch in channels:
                await agent.introduce(ch)

        # Auto-join premium channels if configured
        if premium_channels and wallet_key:
            for pch in premium_channels:
                logger.info(f"  [{agent_name}] Auto-joining premium channel: {pch}")
                await agent.join_premium_channel(pch, wallet_key)
                await asyncio.sleep(2)  # Rate limit between payments

        if duration > 0:
            # Run for specified duration
            try:
                await asyncio.wait_for(agent.listen(), timeout=duration)
            except asyncio.TimeoutError:
                pass
        else:
            await agent.listen()

    except Exception as e:
        logger.error(f"  [{agent_name}] Error: {e}")
    finally:
        await agent.disconnect()


def list_available_agents(workspaces_dir: Path) -> list[str]:
    """List all available agent workspaces."""
    manifest = workspaces_dir / "_manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return [ws["name"] for ws in data.get("workspaces", [])]
    return [d.name for d in workspaces_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]


async def main():
    parser = argparse.ArgumentParser(description="KK Agent IRC Client")
    parser.add_argument("--agent", type=str, help="Agent name (e.g., kk-juanjumagalp)")
    parser.add_argument("--channel", type=str, action="append", help="IRC channel to join")
    parser.add_argument("--workspaces", type=str, default=None)
    parser.add_argument("--duration", type=int, default=0, help="Run duration in seconds (0=forever)")
    parser.add_argument("--no-intro", action="store_true", help="Skip channel introduction")
    parser.add_argument("--list-agents", action="store_true")
    parser.add_argument("--wallet-key-env", type=str, default=None, help="Env var name containing wallet private key (never pass key directly)")
    parser.add_argument("--premium-channel", type=str, action="append", help="Premium channel to auto-join on connect (requires --wallet-key-env)")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspaces_dir = Path(args.workspaces) if args.workspaces else base / "data" / "workspaces"

    if args.list_agents:
        agents = list_available_agents(workspaces_dir)
        print(f"\nAvailable agents ({len(agents)}):")
        for a in agents:
            print(f"  - {a}")
        return

    if not args.agent:
        print("ERROR: --agent required. Use --list-agents to see available agents.")
        return

    channels = args.channel or DEFAULT_CHANNELS
    workspace_dir = workspaces_dir / args.agent
    if not workspace_dir.exists():
        workspace_dir = workspaces_dir / f"kk-{args.agent}"

    print(f"\n{'=' * 60}")
    print(f"  KK IRC Agent: {args.agent}")
    print(f"  Server: {IRC_SERVER}")
    print(f"  Channels: {', '.join(channels)}")
    print(f"{'=' * 60}\n")

    # Load wallet key from env var (NEVER from CLI arg — streaming safe)
    wallet_key = None
    if args.wallet_key_env:
        import os
        wallet_key = os.environ.get(args.wallet_key_env)
        if not wallet_key:
            print(f"WARNING: Env var {args.wallet_key_env} not set. Premium channels disabled.")

    await run_agent(
        agent_name=args.agent,
        workspace_dir=workspace_dir if workspace_dir.exists() else None,
        channels=channels,
        introduce=not args.no_intro,
        duration=args.duration,
        wallet_key=wallet_key,
        premium_channels=args.premium_channel,
    )


if __name__ == "__main__":
    asyncio.run(main())
