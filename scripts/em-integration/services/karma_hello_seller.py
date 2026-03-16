"""
Karma Kadabra V2 — Task 5.1: Karma Hello Log Sales Service

Karma Hello agent publishes Twitch log data as purchasable tasks on
Execution Market.  Other agents browse EM, find the offerings, buy
the data packages via x402 payment.

Data products:
  - raw_logs:     Raw chat messages (JSON)        $0.01
  - user_stats:   Per-user engagement statistics   $0.03
  - topic_map:    Topic analysis per date          $0.02
  - skill_profile: Extracted skill profiles        $0.05

Usage:
  python karma_hello_seller.py                          # Publish all offerings
  python karma_hello_seller.py --product user_stats     # Publish one product
  python karma_hello_seller.py --dry-run                # Preview without publishing
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure services package is importable
sys.path.insert(0, str(Path(__file__).parent))

from em_client import AgentContext, EMClient, load_agent_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.karma-hello-seller")


# ---------------------------------------------------------------------------
# Data Products Catalog
# ---------------------------------------------------------------------------

PRODUCTS = {
    "raw_logs": {
        "title": "[KK Data] Raw Twitch Chat Logs — {date_range}",
        "description": (
            "Raw Twitch chat logs from Ultravioleta DAO community.\n"
            "Format: JSON array of {total_messages} messages across {total_dates} sessions.\n"
            "Includes: timestamp, username, message text.\n"
            "Source: Karma Hello live collector.\n\n"
            "Delivery: JSON file URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.01,
        "evidence_type": "text",
    },
    "user_stats": {
        "title": "[KK Data] Community Engagement Stats — {user_count} Users",
        "description": (
            "Per-user engagement statistics for Ultravioleta DAO community.\n"
            "Fields: total_messages, active_dates, avg_message_length, "
            "vocabulary_richness, top_topics, engagement_score, rank.\n"
            "Format: JSON with {user_count} ranked user profiles.\n\n"
            "Delivery: JSON file URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.03,
        "evidence_type": "text",
    },
    "topic_map": {
        "title": "[KK Data] Topic Analysis — {total_dates} Sessions",
        "description": (
            "Topic frequency analysis extracted from community chat logs.\n"
            "Covers: Programming, Blockchain, AI/ML, Design, Business, Community.\n"
            "Format: JSON with per-date and aggregate topic distributions.\n\n"
            "Delivery: JSON file URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.02,
        "evidence_type": "text",
    },
    "skill_profile": {
        "title": "[KK Data] Extracted Skill Profiles — {user_count} Users",
        "description": (
            "Machine-extracted skill profiles from chat behavior analysis.\n"
            "Per user: top_skills (ranked), skill categories, confidence scores, "
            "languages detected, monetizable capabilities.\n"
            "Format: JSON with {user_count} detailed skill profiles.\n\n"
            "Delivery: JSON file URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.05,
        "evidence_type": "text",
    },
}


def load_data_stats(data_dir: Path) -> dict:
    """Load stats from pipeline output to fill product templates."""
    stats = {
        "total_messages": 0,
        "total_dates": 0,
        "user_count": 0,
        "date_range": "unknown",
    }

    # Aggregate stats — file is "aggregated.json" not "aggregated_logs.json"
    agg_file = data_dir / "aggregated.json"
    if agg_file.exists():
        agg = json.loads(agg_file.read_text(encoding="utf-8"))
        agg_stats = agg.get("stats", {})
        stats["total_messages"] = agg_stats.get("total_messages", 0)
        stats["total_dates"] = agg_stats.get("date_count", 0)
        dates = sorted(agg_stats.get("dates", []))
        if dates:
            stats["date_range"] = f"{dates[0]} to {dates[-1]}"

    # User stats
    user_stats_file = data_dir / "user-stats.json"
    if user_stats_file.exists():
        us = json.loads(user_stats_file.read_text(encoding="utf-8"))
        stats["user_count"] = len(us.get("ranking", []))

    return stats


async def publish_product(
    client: EMClient,
    product_key: str,
    product: dict,
    stats: dict,
    dry_run: bool = False,
) -> dict | None:
    """Publish a single data product as a task on EM."""
    title = product["title"].format(**stats)
    description = product["description"].format(**stats)
    bounty = product["bounty"]

    logger.info(f"  Publishing: {title} (${bounty})")

    if dry_run:
        logger.info(f"    [DRY RUN] Would publish: {title}")
        return None

    if not client.agent.can_spend(bounty):
        logger.warning(f"    SKIP: Daily budget exhausted (spent ${client.agent.daily_spent_usd:.2f})")
        return None

    result = await client.publish_task(
        title=title,
        instructions=description,
        category=product["category"],
        bounty_usd=bounty,
        deadline_hours=24,
        evidence_required=["text"],
    )

    task_id = result.get("task", {}).get("id") or result.get("id", "unknown")
    logger.info(f"    Published: task_id={task_id}")
    client.agent.record_spend(bounty)
    return result


async def check_and_fulfill_purchases(
    client: EMClient,
    data_dir: Path,
) -> None:
    """Check for accepted tasks (purchases) and deliver data."""
    my_tasks = await client.list_tasks(
        agent_wallet=client.agent.wallet_address,
        status="submitted",
    )

    for task in my_tasks:
        task_id = task.get("id", "")
        title = task.get("title", "")

        if not title.startswith("[KK Data]"):
            continue

        logger.info(f"  Reviewing submission for: {title}")
        submissions = await client.get_submissions(task_id)

        for sub in submissions:
            sub_id = sub.get("id", "")
            # Auto-approve data deliveries from our own pipeline
            logger.info(f"    Approving submission {sub_id}")
            await client.approve_submission(sub_id, rating_score=90, notes="Data delivered successfully")


async def main():
    parser = argparse.ArgumentParser(description="Karma Hello — EM Log Sales Service")
    parser.add_argument("--product", type=str, choices=list(PRODUCTS.keys()), help="Publish specific product only")
    parser.add_argument("--workspace", type=str, default=None, help="Workspace directory")
    parser.add_argument("--data-dir", type=str, default=None, help="Pipeline data directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without publishing")
    parser.add_argument("--fulfill", action="store_true", help="Check and fulfill pending purchases")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = Path(args.workspace) if args.workspace else base / "data" / "workspaces" / "kk-karma-hello"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    # Load agent context
    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-karma-hello",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    stats = load_data_stats(data_dir)

    print(f"\n{'=' * 60}")
    print(f"  Karma Hello — Log Sales Service")
    print(f"  Agent: {agent.name}")
    print(f"  Wallet: {agent.wallet_address or 'NOT SET'}")
    print(f"  Data: {stats['total_messages']} messages, {stats['user_count']} users")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    client = EMClient(agent)

    try:
        # Health check
        health = await client.health()
        logger.info(f"  EM API: {health.get('status', 'unknown')}")

        if args.fulfill:
            await check_and_fulfill_purchases(client, data_dir)
            return

        # Publish products
        products_to_publish = (
            {args.product: PRODUCTS[args.product]} if args.product else PRODUCTS
        )

        published = 0
        for key, product in products_to_publish.items():
            result = await publish_product(client, key, product, stats, args.dry_run)
            if result:
                published += 1

        print(f"\n  Published: {published} data products")
        print(f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
