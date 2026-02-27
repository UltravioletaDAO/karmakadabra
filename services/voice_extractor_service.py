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
    """Analyze voice profiles from local pipeline data."""
    voices_dir = data_dir / "voices"
    if not voices_dir.exists():
        logger.warning(f"  No voices directory at {voices_dir}")
        return None

    profiles = list(voices_dir.glob("*.json"))
    logger.info(f"  Processing {len(profiles)} voice profiles")

    # Aggregate stats
    tone_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    slang_total = 0

    for path in profiles:
        profile = json.loads(path.read_text(encoding="utf-8"))
        # tone is a dict with "primary" key, not a string
        tone = profile.get("tone", {}).get("primary", "unknown")
        tone_counts[tone] = tone_counts.get(tone, 0) + 1
        role = profile.get("communication_style", {}).get("social_role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
        slang_total += len(profile.get("vocabulary", {}).get("slang_usage", {}))

    top_tones = sorted(tone_counts.items(), key=lambda x: -x[1])
    logger.info(f"  Tone distribution: {', '.join(f'{t[0]}({t[1]})' for t in top_tones[:4])}")

    return {
        "total_profiles": len(profiles),
        "tone_distribution": dict(tone_counts),
        "role_distribution": dict(role_counts),
        "avg_slang_variety": round(slang_total / max(len(profiles), 1), 1),
    }


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
