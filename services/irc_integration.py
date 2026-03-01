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

    Two channels, two purposes:
      #Execution-Market — Business: HAVE/NEED/DEAL, negotiations, service offers
      #karmakadabra     — Social: gossip, celebrations, personality expression

    Returns list of (channel, message) tuples.
    """
    messages = []
    result_lower = action_result.lower()
    EM = "#Execution-Market"
    KK = "#karmakadabra"

    # --- karma-hello: Data producer, origin of all logs ---
    if agent_name == "kk-karma-hello":
        if "published" in result_lower and "0 published" not in result_lower:
            messages.append((EM, "HAVE: Fresh Twitch chat log bundles on EM. 834 unique users, raw data. $0.01 per bundle. First come first served."))
        if "approved" in result_lower and "0 approved" not in result_lower:
            messages.append((EM, "DEAL: Data delivered to buyer. S3 link sent. The supply chain is moving."))
            messages.append((KK, "Just delivered data. Another buyer served. La cadena sigue."))
        if "0 new msgs" in result_lower and "0 published" in result_lower:
            messages.append((EM, "HAVE: Chat log archives available. 469K messages from Ultravioleta DAO streams. Ping me for bulk pricing."))
        if "seller:" in result_lower:
            # karma-hello seller mode: looking for bounties requesting raw data
            if "found" in result_lower and "0 found" not in result_lower:
                messages.append((EM, "Saw a request for raw data on EM. Checking if I can fulfill it."))

    # --- skill-extractor: Buys raw logs, sells skill profiles ---
    elif agent_name == "kk-skill-extractor":
        if "found=0" in result_lower or "0 found" in result_lower:
            messages.append((EM, "NEED: Raw chat logs for skill extraction. I analyze 12 skill categories (Python, DeFi, Trading, etc). @kk-karma-hello got fresh data?"))
        if "applied=1" in result_lower or "applied" in result_lower and "0 applied" not in result_lower:
            messages.append((EM, "Applied to a bounty. Ready to deliver skill profiles -- keyword analysis across 12 categories."))
        if "submitted=1" in result_lower or "submitted" in result_lower and "0 submitted" not in result_lower:
            messages.append((KK, "Just submitted skill profiles! Users ranked by: DeFi, Trading, Python, Solidity, AI/ML, DevOps and more."))
            messages.append((EM, "HAVE: Enriched skill profiles delivered. $0.05 on EM. Tells you what each community member knows."))
        if "profiles processed" in result_lower:
            messages.append((EM, "HAVE: Skill profiles ready. 12 categories analyzed per user. $0.05 on EM."))

    # --- voice-extractor: Buys raw logs, sells personality profiles ---
    elif agent_name == "kk-voice-extractor":
        if "found=0" in result_lower or "0 found" in result_lower:
            messages.append((EM, "NEED: Raw chat logs for voice analysis. I extract personality patterns, tone, communication style. @kk-karma-hello publishing?"))
        if "applied=1" in result_lower or "applied" in result_lower and "0 applied" not in result_lower:
            messages.append((EM, "Applied to a bounty. I deliver personality profiles -- tone, formality, slang, language patterns."))
        if "submitted=1" in result_lower or "submitted" in result_lower and "0 submitted" not in result_lower:
            messages.append((KK, "Personality profiles submitted! Who's inquisitive? Who's enthusiastic? Who's the aggressive trader? Now you know."))
            messages.append((EM, "HAVE: Voice/personality profiles delivered. $0.04 on EM. Know how each person talks and thinks."))
        if "profiles processed" in result_lower:
            messages.append((EM, "HAVE: Personality profiles ready. Tone + style + slang + risk profile per user. $0.04 on EM."))

    # --- soul-extractor: Buys skill+voice, sells complete SOUL.md ---
    elif agent_name == "kk-soul-extractor":
        if "found=0" in result_lower or "0 found" in result_lower:
            messages.append((EM, "NEED: Skill profiles + voice profiles to synthesize SOUL.md. @kk-skill-extractor @kk-voice-extractor got data?"))
        if "applied" in result_lower and "0 applied" not in result_lower:
            messages.append((EM, "Applied to a bounty. I merge skills + personality into complete SOUL.md identity documents."))
        if "submitted" in result_lower and "0 submitted" not in result_lower:
            messages.append((KK, "SOUL.md profiles synthesized! Complete digital identities -- who they are, what they know, how they talk."))
            messages.append((EM, "HAVE: Complete SOUL.md profiles. Identity + skills + personality fused. $0.08 on EM. The full picture."))
        if "souls merged" in result_lower:
            messages.append((EM, "HAVE: SOUL.md bundles ready. Each profile = skills + voice + identity merged. $0.08 on EM."))

    # --- juanjumagalp (Humaga): End consumer, community buyer ---
    elif agent_name == "kk-juanjumagalp":
        step = ""
        if "step=" in result_lower:
            step = result_lower.split("step=")[1].split(",")[0].strip()

        if "published=1" in result_lower:
            step_labels = {
                "raw_logs": "raw chat logs",
                "skill_profiles": "skill extraction services",
                "voice_profiles": "personality analysis services",
                "soul_profiles": "SOUL.md synthesis services",
            }
            label = step_labels.get(step, step)
            messages.append((EM, f"NEED: Looking for {label}. Published bounty on EM. Who can deliver?"))
        if "assigned=1" in result_lower or "assigned" in result_lower and "0 assigned" not in result_lower:
            messages.append((KK, f"Found a seller for {step.replace('_', ' ')}! Assigned and waiting for delivery."))
        if "approved=1" in result_lower or "approved" in result_lower and "0 approved" not in result_lower:
            messages.append((EM, f"DEAL: Approved delivery for {step.replace('_', ' ')}. Rated the seller. Supply chain works."))
            messages.append((KK, f"Data received and approved! One step closer to building my complete community profile."))
        if "completed=1" in result_lower or "completed" in result_lower and "0 completed" not in result_lower:
            messages.append((KK, f"Step complete! Moving to next phase of profile assembly. Let's go!"))
        if step == "complete":
            messages.append((KK, "COMPLETE: Full community profile assembled! Logs + skills + voice + SOUL.md. The chain delivered."))
            messages.append((EM, "DONE: Full profile cycle completed. All data products acquired. Thanks to the KK supply chain."))

    # --- coordinator: Swarm orchestrator ---
    elif agent_name == "kk-coordinator":
        if "agents monitored" in result_lower:
            messages.append((KK, f"Swarm status: {action_result}"))
        if "assignments" in result_lower and "0 assignments" not in result_lower:
            messages.append((EM, f"COORD: Routed tasks to available agents. Swarm is coordinated."))

    # --- validator: QA auditor ---
    elif agent_name == "kk-validator":
        if "applied to" in result_lower:
            messages.append((EM, "AUDIT: Picked up a validation task. Checking data quality."))
        if "approved" in result_lower and "0 approved" not in result_lower:
            messages.append((EM, "VERIFIED: Data quality check passed. Submission is legit."))

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
            "kk-karma-hello": "Raw logs $0.01, User stats $0.03, Topics $0.02. Browse execution.market",
            "kk-skill-extractor": "Skill profiles $0.05. 12 categories per user. Browse execution.market",
            "kk-voice-extractor": "Personality profiles $0.04. Tone + style + slang. Browse execution.market",
            "kk-soul-extractor": "SOUL.md synthesis $0.08. Complete identity documents. Browse execution.market",
            "kk-validator": "Validation $0.001 per check. Quality assurance for data products.",
        }
        price_info = prices.get(agent_name, "Check my offerings on execution.market")
        return f"{sender}: {price_info}"

    if "status" in msg_lower or "alive" in msg_lower or "ping" in msg_lower:
        return f"{sender}: Online and operational. Check execution.market for my offerings."

    if "help" in msg_lower or "what do you" in msg_lower:
        roles = {
            "kk-karma-hello": "I collect and sell Twitch chat logs from Ultravioleta DAO streams. 469K messages, 834 users. $0.01/bundle.",
            "kk-skill-extractor": "I analyze chat logs and extract skill profiles. Python, DeFi, Trading, Solidity + 8 more categories. $0.05.",
            "kk-voice-extractor": "I extract personality and voice patterns from chat data. Tone, formality, slang, language. $0.04.",
            "kk-soul-extractor": "I synthesize SOUL.md profiles merging skills + personality into complete identity documents. $0.08.",
            "kk-validator": "I verify data quality for the KK supply chain. Audit submissions for completeness and accuracy.",
            "kk-coordinator": "I orchestrate the KK agent swarm. Monitor health, route tasks, coordinate the supply chain.",
        }
        role = roles.get(agent_name, "I'm part of the KK agent swarm on execution.market.")
        return f"{sender}: {role}"

    # Respond to HAVE/NEED messages from other agents
    if "have:" in msg_lower or "selling" in msg_lower:
        # Another agent is offering something — if we're a buyer, show interest
        buyer_responses = {
            "kk-skill-extractor": f"{sender}: Interested. I need raw chat logs for skill extraction. Publishing on EM?",
            "kk-voice-extractor": f"{sender}: Interested. I need raw logs for voice analysis. How fresh is the data?",
            "kk-soul-extractor": f"{sender}: Interested. I need skill + voice profiles for SOUL.md synthesis. What's available?",
            "kk-juanjumagalp": f"{sender}: Interested! Checking your offerings on EM now.",
        }
        return buyer_responses.get(agent_name)

    if "need:" in msg_lower or "looking for" in msg_lower or "want:" in msg_lower:
        # Another agent needs something — if we sell it, pitch
        seller_responses = {
            "kk-karma-hello": f"{sender}: I have raw chat logs. 469K messages, 834 users. $0.01/bundle on EM.",
            "kk-skill-extractor": f"{sender}: I sell skill profiles. 12 categories analyzed per user. $0.05 on EM.",
            "kk-voice-extractor": f"{sender}: I sell personality profiles. Tone, style, slang per user. $0.04 on EM.",
            "kk-soul-extractor": f"{sender}: I sell complete SOUL.md identity docs. Skills + voice merged. $0.08 on EM.",
        }
        return seller_responses.get(agent_name)

    # Skip generic acknowledgment if the mention is from another KK agent
    # (they're just announcing, not asking a question)
    if sender.startswith("kk-"):
        return None

    # Generic acknowledgment for non-KK mentions only
    return f"{sender}: I'm {agent_name}, part of the KK data supply chain on execution.market."


def _build_announcement(agent_name: str, action: str, result: str) -> str | None:
    """Build an IRC announcement for significant heartbeat events.

    Returns None for quiet heartbeats (no significant events).
    Proactive messages cover most cases; this is the fallback for
    action types not already handled by _proactive_messages().
    """
    # Proactive messages now handle most cases.
    # This function only fires for actions not covered above.
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
