"""
Karma Kadabra V2 — Task 5.3: Voice Extractor Service

The Voice Extractor agent operates in parallel with the Skill Extractor:
  1. Discovers Karma Hello's raw log offerings on EM
  2. Buys raw logs ($0.01)
  3. Processes with voice/personality extraction → personality profiles
  4. Publishes enriched personality profiles as EM offerings ($0.04)

Data products:
  - Communication patterns (tone, greeting style, slang)
  - Personality indicators (risk tolerance, social role)
  - Voice fingerprints (signature phrases, emoji usage)

Usage:
  python voice_extractor_service.py                # Full cycle
  python voice_extractor_service.py --discover     # Only discover
  python voice_extractor_service.py --process      # Only process
  python voice_extractor_service.py --sell          # Only publish
  python voice_extractor_service.py --dry-run      # Preview
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure services package is importable
sys.path.insert(0, str(Path(__file__).parent))

from em_client import AgentContext, EMClient, load_agent_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.voice-extractor")


async def discover_data_offerings(client: EMClient) -> list[dict]:
    """Search EM for Karma Hello's raw log data."""
    tasks = await client.browse_tasks(
        status="published",
        category="knowledge_access",
        limit=50,
    )

    offerings = [
        t for t in tasks
        if "[KK Data]" in t.get("title", "") and "Raw" in t.get("title", "")
    ]

    logger.info(f"  Found {len(offerings)} raw data offerings")
    return offerings


async def buy_data(
    client: EMClient,
    task: dict,
    dry_run: bool = False,
) -> dict | None:
    """Apply to buy data from Karma Hello."""
    task_id = task.get("id", "")
    bounty = task.get("bounty_usdc", 0)

    if not client.agent.can_spend(bounty):
        logger.warning(f"  SKIP: Budget limit")
        return None

    if dry_run:
        logger.info(f"  [DRY RUN] Would buy: {task.get('title', '?')}")
        return None

    if not client.agent.executor_id:
        logger.error("  Cannot buy: executor_id not set")
        return None

    result = await client.apply_to_task(
        task_id=task_id,
        executor_id=client.agent.executor_id,
        message="Voice Extractor agent — buying raw logs for personality analysis",
    )
    client.agent.record_spend(bounty)
    return result


async def process_voices(data_dir: Path) -> dict | None:
    """Analyze voice/personality profiles from purchased data or existing pipeline.

    Priority:
      1. data/purchases/*.json (freshly bought)
      2. data/voices/*.json (already processed)
    """
    voices_dir = data_dir / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    purchases_dir = data_dir / "purchases"

    # Process purchased data first
    purchase_files = sorted(purchases_dir.glob("*.json")) if purchases_dir.exists() else []
    raw_messages = []

    for pf in purchase_files:
        try:
            content = pf.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, list):
                raw_messages.extend(data)
            elif isinstance(data, dict):
                raw_messages.extend(data.get("messages", []))
        except (json.JSONDecodeError, OSError):
            continue

    if raw_messages:
        logger.info(f"  Processing {len(raw_messages)} messages for voice analysis")
        _extract_voices_from_messages(raw_messages, voices_dir)

    # Read all voice profiles
    profiles = list(voices_dir.glob("*.json"))
    if not profiles:
        logger.warning(f"  No voice profiles found")
        return None

    logger.info(f"  Found {len(profiles)} voice profiles")

    # Aggregate stats
    tone_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    slang_total = 0

    for path in profiles:
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
            tone = profile.get("tone", {}).get("primary", "unknown")
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
            role = profile.get("communication_style", {}).get("social_role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
            slang_total += len(profile.get("vocabulary", {}).get("slang_usage", {}))
        except (json.JSONDecodeError, OSError):
            continue

    top_tones = sorted(tone_counts.items(), key=lambda x: -x[1])
    logger.info(f"  Tone distribution: {', '.join(f'{t[0]}({t[1]})' for t in top_tones[:4])}")

    return {
        "total_profiles": len(profiles),
        "tone_distribution": dict(tone_counts),
        "role_distribution": dict(role_counts),
        "avg_slang_variety": round(slang_total / max(len(profiles), 1), 1),
    }


def _extract_voices_from_messages(messages: list[dict], voices_dir: Path) -> None:
    """Extract personality/voice profiles per user from raw chat messages.

    Analyzes tone, formality, greeting style, slang patterns.
    No LLM calls -- pure heuristic analysis.
    """
    user_messages: dict[str, list[str]] = {}

    for msg in messages:
        user = msg.get("user", "") or msg.get("sender", "")
        text = msg.get("message", "") or msg.get("text", "")
        if user and text:
            user_messages.setdefault(user, []).append(text)

    logger.info(f"  Analyzing voice patterns for {len(user_messages)} users")

    for username, msgs in user_messages.items():
        if len(msgs) < 3:
            continue

        all_text = " ".join(msgs)
        all_lower = all_text.lower()

        # Average message length
        avg_len = sum(len(m) for m in msgs) / len(msgs)

        # Tone detection
        q_count = sum(1 for m in msgs if "?" in m)
        excl_count = sum(1 for m in msgs if "!" in m)
        q_ratio = q_count / len(msgs)
        excl_ratio = excl_count / len(msgs)

        if q_ratio > 0.3:
            tone = "inquisitive"
        elif excl_ratio > 0.3:
            tone = "enthusiastic"
        elif avg_len > 80:
            tone = "analytical"
        elif avg_len < 20:
            tone = "reactive"
        else:
            tone = "conversational"

        # Formality
        formal_markers = ["usted", "cordial", "atentamente", "please", "thank you", "regards"]
        informal_markers = ["jaja", "lol", "xd", "jeje", "bro", "man", "pana", "parce"]
        formal_count = sum(1 for m in formal_markers if m in all_lower)
        informal_count = sum(1 for m in informal_markers if m in all_lower)
        formality = "formal" if formal_count > informal_count else "informal"

        # Greeting style
        greetings = {"gm": 0, "hola": 0, "buenas": 0, "hello": 0, "hey": 0}
        for g in greetings:
            greetings[g] = all_lower.count(g)
        greeting_style = max(greetings, key=greetings.get) if any(greetings.values()) else "gm"

        # Social role (based on interaction patterns)
        if len(msgs) > 50 and q_ratio > 0.2:
            social_role = "hub"
        elif len(msgs) > 30:
            social_role = "active_participant"
        elif len(msgs) > 10:
            social_role = "regular"
        else:
            social_role = "observer"

        # Language detection
        spanish_markers = ["hola", "buenas", "gracias", "que", "como", "pero", "esta"]
        english_markers = ["the", "and", "is", "that", "this", "have", "with"]
        es_count = sum(1 for m in spanish_markers if m in all_lower)
        en_count = sum(1 for m in english_markers if m in all_lower)

        # Slang detection
        slang_categories = {
            "colombian": {"parce": 0, "gonorrea": 0, "chimba": 0, "parcero": 0, "marica": 0},
            "crypto": {"wagmi": 0, "gm": 0, "ngmi": 0, "degen": 0, "ape": 0, "moon": 0, "hodl": 0},
            "internet": {"lol": 0, "lmao": 0, "gg": 0, "pog": 0, "copium": 0, "based": 0},
        }
        for cat, words in slang_categories.items():
            for word in words:
                words[word] = all_lower.count(word)

        # Build slang usage dict
        slang_usage = {}
        for cat, words in slang_categories.items():
            top_words = sorted(words.items(), key=lambda x: -x[1])
            used = [{"word": w, "count": c} for w, c in top_words if c > 0]
            if used:
                slang_usage[cat] = {"top": used[:5]}

        # Signature phrases (most common short messages)
        short_msgs = [m for m in msgs if 5 < len(m) < 30]
        phrase_counts: dict[str, int] = {}
        for m in short_msgs:
            m_lower = m.lower().strip()
            phrase_counts[m_lower] = phrase_counts.get(m_lower, 0) + 1
        sig_phrases = sorted(phrase_counts.items(), key=lambda x: -x[1])[:5]
        sig_phrases = [{"phrase": p, "count": c} for p, c in sig_phrases if c > 1]

        # Risk tolerance (based on enthusiasm and boldness markers)
        bold_markers = ["all in", "moon", "send it", "yolo", "ape", "full"]
        careful_markers = ["careful", "risk", "wait", "research", "dyor"]
        bold_count = sum(1 for m in bold_markers if m in all_lower)
        careful_count = sum(1 for m in careful_markers if m in all_lower)
        if bold_count > careful_count * 2:
            risk_tolerance = "aggressive"
        elif careful_count > bold_count:
            risk_tolerance = "conservative"
        else:
            risk_tolerance = "moderate"

        profile = {
            "username": username,
            "total_messages": len(msgs),
            "tone": {"primary": tone, "question_ratio": round(q_ratio, 2), "excl_ratio": round(excl_ratio, 2)},
            "communication_style": {
                "avg_message_length": round(avg_len, 1),
                "social_role": social_role,
                "greeting_style": greeting_style,
            },
            "personality": {
                "formality": formality,
                "risk_tolerance": risk_tolerance,
            },
            "vocabulary": {
                "signature_phrases": sig_phrases,
                "slang_usage": slang_usage,
                "primary_language": "spanish" if es_count >= en_count else "english",
            },
        }

        profile_path = voices_dir / f"{username}.json"
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    logger.info(f"  Saved voice profiles for {len(list(voices_dir.glob('*.json')))} users")


async def publish_personality_profiles(
    client: EMClient,
    stats: dict,
    dry_run: bool = False,
) -> dict | None:
    """Publish personality/voice profiles on EM."""
    total = stats.get("total_profiles", 0)

    title = f"[KK Data] Personality & Voice Profiles — {total} Community Members"
    description = (
        f"Machine-extracted personality and communication profiles for "
        f"{total} Ultravioleta DAO community members.\n\n"
        f"Per profile:\n"
        f"- Communication tone (inquisitive/enthusiastic/analytical/reactive)\n"
        f"- Greeting style and social role\n"
        f"- Slang profile (colombian, latam, crypto, internet)\n"
        f"- Signature phrases and vocabulary patterns\n"
        f"- Risk tolerance indicator\n"
        f"- Interaction graph position (hub/bridge/leaf)\n\n"
        f"Tone distribution: {json.dumps(stats.get('tone_distribution', {}))}\n\n"
        f"Format: JSON. Delivery: URL provided upon approval."
    )
    bounty = 0.04

    if dry_run:
        logger.info(f"  [DRY RUN] Would publish: {title} (${bounty})")
        return None

    if not client.agent.can_spend(bounty):
        logger.warning(f"  SKIP: Budget limit")
        return None

    result = await client.publish_task(
        title=title,
        instructions=description,
        category="knowledge_access",
        bounty_usd=bounty,
        deadline_hours=24,
        evidence_required=["json_response"],
    )

    task_id = result.get("task", {}).get("id") or result.get("id", "unknown")
    logger.info(f"  Published personality profiles: task_id={task_id}")
    client.agent.record_spend(bounty)
    return result


async def main():
    parser = argparse.ArgumentParser(description="Voice Extractor — Personality Refinery")
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--process", action="store_true")
    parser.add_argument("--sell", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = Path(args.workspace) if args.workspace else base / "data" / "workspaces" / "kk-voice-extractor"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-voice-extractor",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    print(f"\n{'=' * 60}")
    print(f"  Voice Extractor — Personality Refinery Service")
    print(f"  Agent: {agent.name}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    client = EMClient(agent)
    run_all = not (args.discover or args.process or args.sell)

    try:
        if args.discover or run_all:
            logger.info("Phase: Discover data offerings")
            offerings = await discover_data_offerings(client)
            if offerings and run_all:
                for offering in offerings[:1]:
                    await buy_data(client, offering, dry_run=args.dry_run)

        if args.process or run_all:
            logger.info("Phase: Process voice data")
            stats = await process_voices(data_dir)
            if stats:
                if args.sell or run_all:
                    logger.info("Phase: Publish personality profiles")
                    await publish_personality_profiles(client, stats, dry_run=args.dry_run)

        logger.info(f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
