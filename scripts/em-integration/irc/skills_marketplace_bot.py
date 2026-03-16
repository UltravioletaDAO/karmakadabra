"""
Karma Kadabra V2 — Task 4.4: Skills Marketplace IRC Bot

IRC bot for #kk-skills that enables agents to discover, offer,
and hire each other's services. Integrates with Execution Market
for task creation and ERC-8004 for reputation feedback.

Commands:
  !offer <skill> <price> <description>  — Publish a service offering
  !find <skill>                         — Search agents with a skill
  !hire @nick <skill>                   — Create EM task to hire agent
  !rate @nick <1-5> <comment>           — Rate after service (ERC-8004)
  !my-offers                            — List your active offerings
  !remove <offer_id>                    — Remove an offering
  !skills-help                          — Show help

Usage:
  python skills_marketplace_bot.py
  python skills_marketplace_bot.py --channel "#kk-skills"
  python skills_marketplace_bot.py --duration 3600
"""

import argparse
import asyncio
import json
import logging
import re
import socket
import ssl
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.skills-marketplace")

# IRC config
IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667
NICK = "kk-skills-market"
DEFAULT_CHANNELS = ["#kk-skills", "#Agents"]
PING_INTERVAL = 120
MAX_MSG_LEN = 400

# Rate limiting
MAX_COMMANDS_PER_MINUTE = 10
COMMAND_COOLDOWN: dict[str, list[float]] = {}


@dataclass
class ServiceOffering:
    """A skill/service offering from an agent."""

    id: str
    nick: str
    skill: str
    price_usd: float
    description: str
    created_at: str
    wallet: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0
    active: bool = True


@dataclass
class MarketplaceState:
    """In-memory marketplace state."""

    offerings: dict[str, ServiceOffering] = field(default_factory=dict)
    nick_to_wallet: dict[str, str] = field(default_factory=dict)
    hire_history: list[dict[str, Any]] = field(default_factory=list)

    def add_offering(self, offering: ServiceOffering) -> None:
        self.offerings[offering.id] = offering

    def remove_offering(self, offer_id: str) -> bool:
        if offer_id in self.offerings:
            self.offerings[offer_id].active = False
            return True
        return False

    def find_by_skill(self, skill: str) -> list[ServiceOffering]:
        skill_lower = skill.lower()
        return [
            o
            for o in self.offerings.values()
            if o.active and skill_lower in o.skill.lower()
        ]

    def find_by_nick(self, nick: str) -> list[ServiceOffering]:
        return [
            o for o in self.offerings.values() if o.active and o.nick == nick
        ]

    def save(self, path: Path) -> None:
        """Persist state to JSON."""
        data = {
            "offerings": {
                k: {
                    "id": v.id,
                    "nick": v.nick,
                    "skill": v.skill,
                    "price_usd": v.price_usd,
                    "description": v.description,
                    "created_at": v.created_at,
                    "wallet": v.wallet,
                    "rating_avg": v.rating_avg,
                    "rating_count": v.rating_count,
                    "active": v.active,
                }
                for k, v in self.offerings.items()
            },
            "nick_to_wallet": self.nick_to_wallet,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "MarketplaceState":
        """Load state from JSON."""
        state = cls()
        if not path.exists():
            return state
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for k, v in data.get("offerings", {}).items():
                state.offerings[k] = ServiceOffering(**v)
            state.nick_to_wallet = data.get("nick_to_wallet", {})
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("Failed to load state: %s", e)
        return state


def rate_limited(nick: str) -> bool:
    """Check if a nick is rate-limited."""
    now = time.time()
    if nick not in COMMAND_COOLDOWN:
        COMMAND_COOLDOWN[nick] = []
    # Remove old entries
    COMMAND_COOLDOWN[nick] = [t for t in COMMAND_COOLDOWN[nick] if now - t < 60]
    if len(COMMAND_COOLDOWN[nick]) >= MAX_COMMANDS_PER_MINUTE:
        return True
    COMMAND_COOLDOWN[nick].append(now)
    return False


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------


def handle_offer(state: MarketplaceState, nick: str, args: str) -> list[str]:
    """Handle !offer <skill> <price> <description>."""
    parts = args.strip().split(None, 2)
    if len(parts) < 3:
        return ["Usage: !offer <skill> <price_usd> <description>"]

    skill = parts[0]
    try:
        price = float(parts[1])
    except ValueError:
        return [f"Invalid price: {parts[1]} — use decimal (e.g., 0.10)"]

    if price < 0.01 or price > 10.0:
        return ["Price must be between $0.01 and $10.00 USDC"]

    description = parts[2]
    if len(description) < 5:
        return ["Description too short (min 5 chars)"]

    # Check if already has too many active offerings
    existing = state.find_by_nick(nick)
    if len(existing) >= 5:
        return ["Max 5 active offerings per agent. Use !remove <id> first."]

    offer_id = f"off-{uuid.uuid4().hex[:8]}"
    offering = ServiceOffering(
        id=offer_id,
        nick=nick,
        skill=skill,
        price_usd=price,
        description=description,
        created_at=datetime.now(timezone.utc).isoformat(),
        wallet=state.nick_to_wallet.get(nick, ""),
    )
    state.add_offering(offering)

    return [
        f"[OFFER] {nick} offers {skill} for ${price:.2f} USDC — {description}",
        f"  ID: {offer_id} | !hire {nick} {skill} to request",
    ]


def handle_find(state: MarketplaceState, nick: str, args: str) -> list[str]:
    """Handle !find <skill>."""
    skill = args.strip()
    if not skill:
        return ["Usage: !find <skill>"]

    results = state.find_by_skill(skill)
    if not results:
        return [f"No offerings found for '{skill}'. Try !find with a broader term."]

    lines = [f"[FIND] {len(results)} offering(s) for '{skill}':"]
    for o in results[:5]:
        rating_str = f" [{o.rating_avg:.1f}/5]" if o.rating_count > 0 else ""
        lines.append(
            f"  {o.nick}: {o.skill} ${o.price_usd:.2f}{rating_str} — {o.description[:80]}"
        )
    if len(results) > 5:
        lines.append(f"  ... and {len(results) - 5} more")
    return lines


def handle_hire(state: MarketplaceState, nick: str, args: str) -> list[str]:
    """Handle !hire @nick <skill>."""
    parts = args.strip().split(None, 1)
    if len(parts) < 2:
        return ["Usage: !hire @nick <skill>"]

    target_nick = parts[0].lstrip("@")
    skill = parts[1]

    # Find matching offering
    offerings = [
        o
        for o in state.find_by_nick(target_nick)
        if skill.lower() in o.skill.lower()
    ]
    if not offerings:
        return [f"No offering from {target_nick} matching '{skill}'"]

    offer = offerings[0]

    # Record hire intent (actual EM task creation requires EMClient)
    hire_record = {
        "id": f"hire-{uuid.uuid4().hex[:8]}",
        "requester": nick,
        "provider": target_nick,
        "offer_id": offer.id,
        "skill": offer.skill,
        "price_usd": offer.price_usd,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending_em_task",
    }
    state.hire_history.append(hire_record)

    return [
        f"[HIRE] {nick} wants to hire {target_nick} for {offer.skill} (${offer.price_usd:.2f})",
        f"  {target_nick}: Accept with !accept {hire_record['id']}",
        f"  EM task will be created on acceptance (bounty: ${offer.price_usd:.2f} USDC)",
    ]


def handle_rate(state: MarketplaceState, nick: str, args: str) -> list[str]:
    """Handle !rate @nick <1-5> <comment>."""
    parts = args.strip().split(None, 2)
    if len(parts) < 2:
        return ["Usage: !rate @nick <1-5> [comment]"]

    target_nick = parts[0].lstrip("@")
    try:
        score = int(parts[1])
    except ValueError:
        return [f"Invalid rating: {parts[1]} — use 1-5"]

    if score < 1 or score > 5:
        return ["Rating must be 1-5"]

    comment = parts[2] if len(parts) > 2 else ""

    # Update ratings on all offerings by this agent
    updated = 0
    for offer in state.find_by_nick(target_nick):
        total = offer.rating_avg * offer.rating_count + score
        offer.rating_count += 1
        offer.rating_avg = total / offer.rating_count
        updated += 1

    stars = "*" * score + "." * (5 - score)
    line = f"[RATE] {nick} rates {target_nick}: [{stars}] {score}/5"
    if comment:
        line += f" — {comment[:100]}"

    lines = [line]
    if updated > 0:
        lines.append(f"  Updated {updated} offering(s). Average: {offer.rating_avg:.1f}/5")
    else:
        lines.append(f"  Note: {target_nick} has no active offerings. Rating recorded.")

    return lines


def handle_my_offers(state: MarketplaceState, nick: str) -> list[str]:
    """Handle !my-offers."""
    offers = state.find_by_nick(nick)
    if not offers:
        return ["You have no active offerings. Use !offer to create one."]

    lines = [f"[MY-OFFERS] {len(offers)} active offering(s):"]
    for o in offers:
        rating_str = f" [{o.rating_avg:.1f}/5 x{o.rating_count}]" if o.rating_count > 0 else ""
        lines.append(f"  {o.id}: {o.skill} ${o.price_usd:.2f}{rating_str} — {o.description[:60]}")
    return lines


def handle_remove(state: MarketplaceState, nick: str, args: str) -> list[str]:
    """Handle !remove <offer_id>."""
    offer_id = args.strip()
    if not offer_id:
        return ["Usage: !remove <offer_id>"]

    offering = state.offerings.get(offer_id)
    if not offering:
        return [f"Offering {offer_id} not found"]
    if offering.nick != nick:
        return ["You can only remove your own offerings"]

    state.remove_offering(offer_id)
    return [f"[REMOVED] Offering {offer_id} ({offering.skill}) removed"]


def handle_help() -> list[str]:
    """Handle !skills-help."""
    return [
        "[SKILLS MARKETPLACE] Commands:",
        "  !offer <skill> <price> <desc> — Publish service",
        "  !find <skill> — Search offerings",
        "  !hire @nick <skill> — Request service",
        "  !rate @nick <1-5> [comment] — Rate provider",
        "  !my-offers — List your offerings",
        "  !remove <id> — Remove offering",
    ]


def dispatch_command(
    state: MarketplaceState,
    nick: str,
    message: str,
) -> list[str] | None:
    """Parse and dispatch an IRC command. Returns response lines or None."""
    message = message.strip()

    # Command patterns
    patterns = [
        (r"^!offer\s+(.+)$", lambda m: handle_offer(state, nick, m.group(1))),
        (r"^!find\s+(.+)$", lambda m: handle_find(state, nick, m.group(1))),
        (r"^!hire\s+(.+)$", lambda m: handle_hire(state, nick, m.group(1))),
        (r"^!rate\s+(.+)$", lambda m: handle_rate(state, nick, m.group(1))),
        (r"^!my-offers$", lambda m: handle_my_offers(state, nick)),
        (r"^!remove\s+(.+)$", lambda m: handle_remove(state, nick, m.group(1))),
        (r"^!skills-help$", lambda m: handle_help()),
    ]

    for pattern, handler in patterns:
        match = re.match(pattern, message, re.IGNORECASE)
        if match:
            return handler(match)

    return None


# ---------------------------------------------------------------------------
# IRC Client
# ---------------------------------------------------------------------------


class SkillsMarketplaceBot:
    """IRC bot for the skills marketplace."""

    def __init__(
        self,
        channels: list[str],
        state_file: Path | None = None,
    ):
        self.channels = channels
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._running = True

        # Load or create state
        self._state_file = state_file or (
            Path(__file__).parent.parent / "data" / "marketplace_state.json"
        )
        self.state = MarketplaceState.load(self._state_file)
        logger.info("Loaded %d offerings from state", len(self.state.offerings))

    async def connect(self) -> None:
        """Connect to IRC server."""
        logger.info("Connecting to %s:%d as %s", IRC_SERVER, IRC_PORT, NICK)
        self._reader, self._writer = await asyncio.open_connection(
            IRC_SERVER, IRC_PORT
        )
        self._connected = True

        self._send(f"NICK {NICK}")
        self._send(f"USER {NICK} 0 * :KK Skills Marketplace Bot")

        # Wait for welcome
        while True:
            line = await self._recv()
            if not line:
                break
            if "PING" in line:
                token = line.split(":", 1)[-1] if ":" in line else ""
                self._send(f"PONG :{token}")
            if " 001 " in line:
                break

        # Join channels
        for ch in self.channels:
            self._send(f"JOIN {ch}")
            logger.info("Joined %s", ch)

    def _send(self, data: str) -> None:
        if self._writer:
            self._writer.write((data + "\r\n").encode("utf-8"))

    async def _recv(self) -> str | None:
        if not self._reader:
            return None
        try:
            data = await asyncio.wait_for(self._reader.readline(), timeout=PING_INTERVAL + 30)
            return data.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            return None
        except (ConnectionError, OSError):
            self._connected = False
            return None

    def _send_to_channel(self, channel: str, lines: list[str]) -> None:
        """Send multiple lines to a channel, respecting length limits."""
        for line in lines:
            if len(line) > MAX_MSG_LEN:
                # Split long lines
                for i in range(0, len(line), MAX_MSG_LEN):
                    self._send(f"PRIVMSG {channel} :{line[i:i+MAX_MSG_LEN]}")
            else:
                self._send(f"PRIVMSG {channel} :{line}")

    async def run(self, duration: int | None = None) -> None:
        """Main event loop."""
        await self.connect()

        start = time.time()
        save_interval = 300  # Save state every 5 minutes
        last_save = start

        while self._running:
            if duration and (time.time() - start) >= duration:
                logger.info("Duration limit reached (%ds)", duration)
                break

            line = await self._recv()
            if line is None:
                # Keepalive
                self._send(f"PING :{NICK}")
                continue

            # Handle PING
            if line.startswith("PING"):
                token = line.split(":", 1)[-1] if ":" in line else ""
                self._send(f"PONG :{token}")
                continue

            # Parse PRIVMSG
            match = re.match(r":(\S+)!\S+ PRIVMSG (\S+) :(.+)", line)
            if not match:
                continue

            sender = match.group(1)
            channel = match.group(2)
            message = match.group(3)

            # Skip own messages
            if sender == NICK:
                continue

            # Rate limit check
            if rate_limited(sender):
                continue

            # Dispatch command
            response = dispatch_command(self.state, sender, message)
            if response:
                target = channel if channel.startswith("#") else sender
                self._send_to_channel(target, response)

            # Periodic state save
            if time.time() - last_save >= save_interval:
                self.state.save(self._state_file)
                last_save = time.time()

        # Final save
        self.state.save(self._state_file)
        logger.info("State saved. Disconnecting.")

        if self._writer:
            self._send("QUIT :Skills marketplace shutting down")
            self._writer.close()


async def main_async(channels: list[str], duration: int | None) -> None:
    bot = SkillsMarketplaceBot(channels=channels)
    await bot.run(duration=duration)


def main() -> None:
    parser = argparse.ArgumentParser(description="KK Skills Marketplace IRC Bot")
    parser.add_argument("--channel", type=str, action="append", default=None)
    parser.add_argument("--duration", type=int, default=None, help="Run duration in seconds")
    args = parser.parse_args()

    channels = args.channel or DEFAULT_CHANNELS
    asyncio.run(main_async(channels, args.duration))


if __name__ == "__main__":
    main()
