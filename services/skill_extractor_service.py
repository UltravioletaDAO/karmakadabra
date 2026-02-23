"""
Karma Kadabra V2 — Task 5.2: Skill Extractor Service

The Skill Extractor agent operates as a data refinery:
  1. Discovers Karma Hello's raw log offerings on EM
  2. Buys raw logs ($0.01)
  3. Processes with skill extraction pipeline → enriched skill profiles
  4. Publishes enriched profiles as new EM offerings ($0.05)
  5. Other agents buy the enriched data

This creates a supply chain:
  Karma Hello (raw data) → Skill Extractor (enriched data) → Consumer agents

Usage:
  python skill_extractor_service.py                 # Full cycle
  python skill_extractor_service.py --discover      # Only discover offerings
  python skill_extractor_service.py --process       # Only process local data
  python skill_extractor_service.py --sell           # Only publish products
  python skill_extractor_service.py --dry-run       # Preview all actions
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
logger = logging.getLogger("kk.skill-extractor")


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

    logger.info(f"  Found {len(offerings)} raw data offerings from Karma Hello")
    for t in offerings:
        logger.info(f"    - {t.get('title', '?')} (${t.get('bounty_usdc', 0)})")

    return offerings


async def buy_data(
    client: EMClient,
    task: dict,
    dry_run: bool = False,
) -> dict | None:
    """Apply to buy data from Karma Hello."""
    task_id = task.get("id", "")
    bounty = task.get("bounty_usdc", 0)
    title = task.get("title", "?")

    if not client.agent.can_spend(bounty):
        logger.warning(f"  SKIP: Budget limit (${client.agent.daily_spent_usd:.2f} spent)")
        return None

    if dry_run:
        logger.info(f"  [DRY RUN] Would buy: {title}")
        return None

    if not client.agent.executor_id:
        logger.error("  Cannot buy: executor_id not set (register on EM first)")
        return None

    logger.info(f"  Buying: {title} (${bounty})")
    result = await client.apply_to_task(
        task_id=task_id,
        executor_id=client.agent.executor_id,
        message="Skill Extractor agent — buying raw logs for skill profile generation",
    )
    client.agent.record_spend(bounty)
    return result


async def process_skills(data_dir: Path) -> dict | None:
    """Run skill extraction on local data (already processed by pipeline)."""
    skills_dir = data_dir / "skills"
    if not skills_dir.exists():
        logger.warning(f"  No skills directory at {skills_dir}")
        return None

    profiles = list(skills_dir.glob("*.json"))
    logger.info(f"  Processing {len(profiles)} skill profiles")

    # Aggregate stats
    all_skills: dict[str, int] = {}
    for profile_path in profiles:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        for skill in profile.get("top_skills", []):
            name = skill.get("skill", "unknown")
            all_skills[name] = all_skills.get(name, 0) + 1

    top_skills = sorted(all_skills.items(), key=lambda x: -x[1])[:10]
    logger.info(f"  Top community skills: {', '.join(s[0] for s in top_skills[:5])}")

    return {
        "total_profiles": len(profiles),
        "unique_skills": len(all_skills),
        "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
    }


async def publish_enriched_profiles(
    client: EMClient,
    data_dir: Path,
    stats: dict,
    dry_run: bool = False,
) -> dict | None:
    """Publish enriched skill profiles on EM."""
    total = stats.get("total_profiles", 0)
    unique = stats.get("unique_skills", 0)

    title = f"[KK Data] Enriched Skill Profiles — {total} Community Members"
    description = (
        f"Machine-extracted skill profiles for {total} Ultravioleta DAO members.\n"
        f"Extracted from Twitch chat behavior analysis (not self-reported).\n\n"
        f"Per profile: top_skills (ranked with confidence), skill_categories, "
        f"languages_detected, monetizable_capabilities.\n"
        f"Unique skills detected: {unique}.\n\n"
        f"Enrichment: Cross-referenced with engagement metrics, voice patterns, "
        f"and interaction graphs for higher accuracy.\n\n"
        f"Format: JSON. Delivery: URL provided upon approval."
    )
    bounty = 0.05

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
        evidence_required=["text"],
    )

    task_id = result.get("task", {}).get("id") or result.get("id", "unknown")
    logger.info(f"  Published enriched profiles: task_id={task_id}")
    client.agent.record_spend(bounty)
    return result


async def main():
    parser = argparse.ArgumentParser(description="Skill Extractor — Data Refinery Service")
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--discover", action="store_true", help="Only discover offerings")
    parser.add_argument("--process", action="store_true", help="Only process local data")
    parser.add_argument("--sell", action="store_true", help="Only publish products")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = Path(args.workspace) if args.workspace else base / "data" / "workspaces" / "kk-skill-extractor"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-skill-extractor",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    print(f"\n{'=' * 60}")
    print(f"  Skill Extractor — Data Refinery Service")
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
                for offering in offerings[:1]:  # Buy only first match
                    await buy_data(client, offering, dry_run=args.dry_run)

        if args.process or run_all:
            logger.info("Phase: Process skill data")
            stats = await process_skills(data_dir)
            if stats:
                if args.sell or run_all:
                    logger.info("Phase: Publish enriched profiles")
                    await publish_enriched_profiles(client, data_dir, stats, dry_run=args.dry_run)

        logger.info(f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
