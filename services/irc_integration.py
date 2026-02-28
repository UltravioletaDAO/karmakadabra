"""
Karma Kadabra V2 — IRC Integration for Heartbeat

Bridges the heartbeat cycle with the IRC daemon via file-based inbox/outbox.
The IRC daemon (scripts/kk/irc_daemon.py) runs as a separate background
process. This module:

  1. Reads data/irc-inbox.jsonl for new messages
  2. Detects mentions of the agent
  3. Queues responses to data/irc-outbox.jsonl
  4. Announces heartbeat status and offerings to IRC channels

Called from cron/heartbeat.py at the end of each heartbeat cycle.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("kk.irc-integration")

# Rate limiting: max messages per heartbeat, cooldown per topic
MAX_MESSAGES_PER_HEARTBEAT = 8
COOLDOWN_HOURS = 0.5  # 30 minutes -- with 5-min heartbeats, allows active conversation


def _read_inbox(data_dir: Path, since_ts: float = 0) -> list[dict]:
    """Read new messages from IRC inbox since a given timestamp."""
    inbox_path = data_dir / "irc-inbox.jsonl"
    if not inbox_path.exists():
        return []

    messages = []
    try:
        for line in inbox_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Filter by timestamp if provided
                ts_str = entry.get("ts", "")
                if since_ts > 0 and ts_str:
                    try:
                        msg_ts = datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00")
                        ).timestamp()
                        if msg_ts < since_ts:
                            continue
                    except (ValueError, OSError):
                        pass
                messages.append(entry)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass

    return messages


def _write_outbox(data_dir: Path, target: str, message: str) -> None:
    """Queue a message for the IRC daemon to send."""
    outbox_path = data_dir / "irc-outbox.jsonl"
    entry = {
        "target": target,
        "message": message,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(outbox_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.error(f"Outbox write failed: {e}")


def _load_irc_state(data_dir: Path) -> dict:
    """Load persistent IRC state (last check time, sent messages)."""
    state_path = data_dir / ".irc-state.json"
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_check_ts": 0, "recent_messages": []}


def _save_irc_state(data_dir: Path, state: dict) -> None:
    """Persist IRC state."""
    state_path = data_dir / ".irc-state.json"
    try:
        state_path.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def _is_mention(message: str, agent_name: str) -> bool:
    """Check if a message mentions the agent."""
    name_lower = agent_name.lower()
    msg_lower = message.lower()
    return (
        name_lower in msg_lower
        or f"@{name_lower}" in msg_lower
        or f"{name_lower}:" in msg_lower
    )


def _was_recently_sent(state: dict, message_hash: str) -> bool:
    """Check if a similar message was sent recently (cooldown)."""
    now = time.time()
    cutoff = now - (COOLDOWN_HOURS * 3600)
    for sent in state.get("recent_messages", []):
        if sent.get("hash") == message_hash and sent.get("ts", 0) > cutoff:
            return True
    return False


def _record_sent(state: dict, message_hash: str) -> None:
    """Record a sent message for cooldown tracking."""
    state.setdefault("recent_messages", []).append({
        "hash": message_hash,
        "ts": time.time(),
    })
    # Prune old entries
    cutoff = time.time() - (COOLDOWN_HOURS * 3600 * 2)
    state["recent_messages"] = [
        m for m in state["recent_messages"] if m.get("ts", 0) > cutoff
    ]


def _proactive_messages(agent_name: str, action: str, action_result: str, data_dir: Path) -> list[tuple[str, str]]:
    """Generate proactive IRC messages based on agent state.

    Returns list of (channel, message) tuples.
    """
    messages = []
    result_lower = action_result.lower()

    # Seller announcing available products
    if agent_name == "kk-karma-hello":
        if "published" in result_lower and "0 published" not in result_lower:
            messages.append(("#Execution-Market", "HAVE: Fresh chat log bundles available on EM. Raw data from 834 unique users."))
        if "approved" in result_lower and "0 approved" not in result_lower:
            messages.append(("#karmakadabra", "Just delivered data to a buyer. The supply chain is flowing."))

    # Extractors announcing needs and products
    elif agent_name == "kk-skill-extractor":
        if "0 raw data" in result_lower or "no matching" in result_lower:
            messages.append(("#Execution-Market", "NEED: Raw chat logs for skill extraction. @kk-karma-hello publishing?"))
        if "bought" in result_lower and "bought 0" not in result_lower:
            messages.append(("#karmakadabra", "Just bought raw logs from kk-karma-hello. Processing skills now."))
        if "profiles processed" in result_lower:
            messages.append(("#Execution-Market", "HAVE: Enriched skill profiles ready. $0.05 on EM."))

    elif agent_name == "kk-voice-extractor":
        if "0 raw data" in result_lower or "no matching" in result_lower:
            messages.append(("#Execution-Market", "NEED: Raw chat logs for voice analysis. @kk-karma-hello got data?"))
        if "bought" in result_lower and "bought 0" not in result_lower:
            messages.append(("#karmakadabra", "Bought raw logs. Extracting personality patterns now."))
        if "profiles processed" in result_lower:
            messages.append(("#Execution-Market", "HAVE: Personality profiles ready. $0.04 on EM."))

    elif agent_name == "kk-soul-extractor":
        if "0 skill" in result_lower and "0 voice" in result_lower:
            messages.append(("#Execution-Market", "NEED: Skill + voice profiles for SOUL.md synthesis. @kk-skill-extractor @kk-voice-extractor ready?"))
        if "bought skill" in result_lower or "bought voice" in result_lower:
            messages.append(("#karmakadabra", "Acquired enriched data. Merging into complete SOUL.md profiles."))
        if "souls merged" in result_lower:
            messages.append(("#Execution-Market", "HAVE: Complete SOUL.md profiles. Identity + personality + skills. $0.08 on EM."))

    # Consumer celebrating
    elif agent_name == "kk-juanjumagalp":
        if "purchased" in result_lower and "0 purchased" not in result_lower:
            messages.append(("#karmakadabra", "Data acquired! Building complete community member profiles."))
        if "no [kk data]" in result_lower or "0 discovered" in result_lower:
            messages.append(("#Execution-Market", "NEED: Any KK data products. @kk-karma-hello tienes logs nuevos?"))

    # Coordinator status
    elif agent_name == "kk-coordinator":
        if "agents monitored" in result_lower:
            messages.append(("#karmakadabra", f"Swarm health check: {action_result}"))

    # Validator announcements
    elif agent_name == "kk-validator":
        if "approved" in result_lower and "0 approved" not in result_lower:
            messages.append(("#Execution-Market", "VERIFIED: Data quality check passed."))

    return messages


async def check_irc_and_respond(
    data_dir: Path,
    agent_name: str,
    action: str,
    action_result: str,
) -> str:
    """Main IRC integration entry point for heartbeat.

    Called at the end of each heartbeat cycle:
      1. Reads new IRC messages from inbox
      2. Responds to mentions
      3. Announces significant heartbeat results
      4. Updates agent memory of other agents seen

    Returns:
        Summary string of IRC activity (e.g., "2 mentions, 1 announced").
    """
    state = _load_irc_state(data_dir)
    last_check = state.get("last_check_ts", 0)
    messages_sent = 0
    mentions_found = 0

    # Read new messages
    inbox_msgs = _read_inbox(data_dir, since_ts=last_check)

    # Update agent memory of others seen in IRC
    await _update_agent_memory(data_dir, inbox_msgs, agent_name)

    # Process mentions
    for msg in inbox_msgs:
        if messages_sent >= MAX_MESSAGES_PER_HEARTBEAT:
            break

        sender = msg.get("sender", "")
        channel = msg.get("channel", "")
        text = msg.get("message", "")

        if sender == agent_name:
            continue  # Skip own messages

        if _is_mention(text, agent_name):
            mentions_found += 1
            response = _generate_mention_response(agent_name, sender, text)
            if response:
                reply_target = channel if channel.startswith("#") else sender
                msg_hash = f"mention:{sender}:{text[:50]}"
                if not _was_recently_sent(state, msg_hash):
                    _write_outbox(data_dir, reply_target, response)
                    _record_sent(state, msg_hash)
                    messages_sent += 1

    # Announce significant heartbeat results to #Execution-Market
    if messages_sent < MAX_MESSAGES_PER_HEARTBEAT:
        announcement = _build_announcement(agent_name, action, action_result)
        if announcement:
            msg_hash = f"announce:{action}:{hash(action_result) % 10000}"
            if not _was_recently_sent(state, msg_hash):
                _write_outbox(data_dir, "#Execution-Market", announcement)
                _record_sent(state, msg_hash)
                messages_sent += 1

    # Send proactive messages based on agent state
    proactive = _proactive_messages(agent_name, action, action_result, data_dir)
    for target, msg in proactive:
        if messages_sent >= MAX_MESSAGES_PER_HEARTBEAT:
            break
        msg_hash = f"proactive:{target}:{hash(msg) % 10000}"
        if not _was_recently_sent(state, msg_hash):
            _write_outbox(data_dir, target, msg)
            _record_sent(state, msg_hash)
            messages_sent += 1

    # Update state
    state["last_check_ts"] = time.time()
    _save_irc_state(data_dir, state)

    if mentions_found == 0 and messages_sent == 0:
        return ""

    return f"{mentions_found} mentions, {messages_sent} sent"


def _generate_mention_response(
    agent_name: str, sender: str, message: str,
) -> str | None:
    """Generate a response to a mention. Template-based for simplicity."""
    msg_lower = message.lower()

    if "price" in msg_lower or "cost" in msg_lower or "how much" in msg_lower:
        prices = {
            "kk-karma-hello": "Raw logs $0.01, User stats $0.03, Topics $0.02",
            "kk-skill-extractor": "Skill profiles $0.05",
            "kk-voice-extractor": "Personality profiles $0.04",
            "kk-soul-extractor": "SOUL.md synthesis $0.08",
            "kk-validator": "Validation $0.001",
        }
        price_info = prices.get(agent_name, "Check my offerings on execution.market")
        return f"{sender}: {price_info}"

    if "status" in msg_lower or "alive" in msg_lower or "ping" in msg_lower:
        return f"{sender}: Online and operational. Check execution.market for my offerings."

    if "help" in msg_lower or "what do you" in msg_lower:
        roles = {
            "kk-karma-hello": "I collect and sell Twitch chat logs from Ultravioleta DAO streams.",
            "kk-skill-extractor": "I analyze chat logs and extract skill profiles.",
            "kk-voice-extractor": "I extract personality and voice patterns from chat data.",
            "kk-soul-extractor": "I synthesize SOUL.md profiles from skill + voice data.",
            "kk-validator": "I verify data quality for the KK supply chain.",
            "kk-coordinator": "I orchestrate the KK agent swarm.",
        }
        role = roles.get(agent_name, "I'm part of the KK agent swarm on execution.market.")
        return f"{sender}: {role}"

    # Generic acknowledgment for other mentions
    return f"{sender}: Got it. I'm {agent_name} from KK swarm."


def _build_announcement(agent_name: str, action: str, result: str) -> str | None:
    """Build an IRC announcement for significant heartbeat events.

    Each agent type gets announcement conditions based on its service output.
    """
    result_lower = result.lower()

    # --- karma-hello: seller of raw data ---
    if action == "karma_hello_service":
        if "published" in result and "0 published" not in result:
            return "HAVE: New data offerings published. Browse at execution.market"
        if "approved" in result and "0 approved" not in result:
            return f"DEAL: {agent_name} approved a data delivery"
        return None

    # --- community buyer (juanjumagalp): end consumer ---
    if action == "community_buyer":
        if ("purchased" in result and "0 purchased" not in result) or \
           ("bought" in result_lower and "bought 0" not in result_lower):
            return f"DEAL: {agent_name} purchased data on execution.market"
        return None

    # --- skill-extractor: buys raw logs, sells skill profiles ---
    if action == "skill_extractor_service":
        if "bought" in result_lower and "bought 0" not in result_lower:
            return f"WANT: {agent_name} bought raw data for skill extraction"
        if "published" in result_lower and "0 published" not in result_lower:
            return f"HAVE: {agent_name} published skill profiles on execution.market"
        return None

    # --- voice-extractor: buys raw logs, sells voice profiles ---
    if action == "voice_extractor_service":
        if "bought" in result_lower and "bought 0" not in result_lower:
            return f"WANT: {agent_name} bought raw data for voice analysis"
        if "published" in result_lower and "0 published" not in result_lower:
            return f"HAVE: {agent_name} published voice profiles on execution.market"
        return None

    # --- soul-extractor: buys skill+voice, sells SOUL.md ---
    if action == "soul_extractor_service":
        if "bought" in result_lower:
            return f"WANT: {agent_name} acquired data for SOUL.md synthesis"
        if "published" in result_lower or "generated" in result_lower:
            return f"HAVE: {agent_name} generated SOUL.md profiles on execution.market"
        return None

    # --- validator: reviews submissions ---
    if action == "validator_service":
        if "applied to" in result_lower:
            return f"AUDIT: {agent_name} applied to validate data on execution.market"
        if "approved" in result and "0 approved" not in result:
            return f"VERIFIED: {agent_name} validated a data submission"
        return None

    # --- coordinator: orchestrates swarm ---
    if action == "coordinator_service":
        if "assignments" in result_lower and "0 assignments" not in result_lower:
            return f"COORD: {agent_name} assigned tasks to swarm agents"
        return None

    # Fallback: check for generic significant events
    if "applied to" in result_lower:
        return f"WANT: {agent_name} is looking for data on execution.market"

    return None


async def _update_agent_memory(
    data_dir: Path, messages: list[dict], my_name: str,
) -> None:
    """Update memory of other agents seen in IRC.

    Maintains workspace/memory/agents.json with info about known agents.
    """
    if not messages:
        return

    memory_dir = data_dir / ".." / "workspaces" / my_name / "memory"
    if not memory_dir.exists():
        # Try alternate path inside container
        memory_dir = Path(f"/app/workspaces/{my_name}/memory")
        if not memory_dir.exists():
            return

    agents_file = memory_dir / "agents.json"
    known: dict = {}
    if agents_file.exists():
        try:
            known = json.loads(agents_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    now = datetime.now(timezone.utc).isoformat()
    changed = False

    for msg in messages:
        sender = msg.get("sender", "")
        if not sender or sender == my_name or not sender.startswith("kk-"):
            continue

        if sender not in known:
            known[sender] = {
                "first_seen": now,
                "last_seen": now,
                "message_count": 0,
            }
            changed = True

        known[sender]["last_seen"] = now
        known[sender]["message_count"] = known[sender].get("message_count", 0) + 1
        changed = True

    if changed:
        try:
            agents_file.write_text(
                json.dumps(known, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass
