#!/usr/bin/env python3
"""Bootstrap the KK economy with seed offerings.

Publishes initial data products and tasks on Execution Market
so the swarm has work from day one.

Usage:
    python bootstrap_economy.py [--dry-run]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.em_client import AgentContext, EMClient

ROOT = Path(__file__).parent.parent.parent

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

KARMA_HELLO_OFFERINGS = [
    {
        "title": "Chat Logs Bundle #1 - General Chat",
        "instructions": "Bundle of recent general chat messages from Twitch/Discord. Raw text, timestamped, anonymized.",
        "category": "knowledge_access",
        "bounty_usd": 0.01,
    },
    {
        "title": "Chat Logs Bundle #2 - Technical Discussion",
        "instructions": "Bundle of technical discussion logs covering crypto, smart contracts, and development topics.",
        "category": "knowledge_access",
        "bounty_usd": 0.01,
    },
    {
        "title": "Chat Logs Bundle #3 - Community Events",
        "instructions": "Bundle of chat logs from community events, AMAs, and special broadcasts.",
        "category": "knowledge_access",
        "bounty_usd": 0.01,
    },
    {
        "title": "Chat Logs Bundle #4 - Gaming Sessions",
        "instructions": "Bundle of chat logs from gaming streams with viewer interactions and reactions.",
        "category": "knowledge_access",
        "bounty_usd": 0.01,
    },
    {
        "title": "Chat Logs Bundle #5 - AMA Highlights",
        "instructions": "Curated bundle of questions and answers from AMA sessions with notable guests.",
        "category": "knowledge_access",
        "bounty_usd": 0.01,
    },
]

COORDINATOR_TASKS = [
    {
        "title": "Extract skill profile from chat logs",
        "instructions": "Analyze a bundle of chat logs and extract a structured skill profile (JSON). Identify technical skills, communication patterns, and expertise areas.",
        "category": "knowledge_access",
        "bounty_usd": 0.02,
    },
    {
        "title": "Extract voice/personality profile",
        "instructions": "Analyze chat logs to build a voice/personality profile. Capture tone, vocabulary patterns, humor style, and communication preferences.",
        "category": "knowledge_access",
        "bounty_usd": 0.02,
    },
    {
        "title": "Validate data product quality",
        "instructions": "Review a submitted data product for quality, completeness, and accuracy. Provide a quality score (0-100) and detailed feedback.",
        "category": "knowledge_access",
        "bounty_usd": 0.001,
    },
    {
        "title": "Generate SOUL.md identity document",
        "instructions": "Using available skill and voice profiles, generate a complete SOUL.md identity document for a community agent. Follow the SOUL.md template format.",
        "category": "knowledge_access",
        "bounty_usd": 0.08,
    },
    {
        "title": "Market analysis report",
        "instructions": "Analyze current Execution Market activity and produce a brief report: trending categories, average bounties, most active agents, and opportunities.",
        "category": "knowledge_access",
        "bounty_usd": 0.05,
    },
]


def _load_agent_context(agent_name: str) -> AgentContext:
    """Build AgentContext from wallets.json + identities.json."""
    wallets = json.loads(
        (ROOT / "data" / "config" / "wallets.json").read_text(encoding="utf-8")
    )
    identities = json.loads(
        (ROOT / "data" / "config" / "identities.json").read_text(encoding="utf-8")
    )

    wallet = None
    for w in wallets["wallets"]:
        if w["name"] == agent_name:
            wallet = w
            break
    if not wallet:
        raise ValueError(f"Agent '{agent_name}' not found in wallets.json")

    executor_id = None
    for a in identities["agents"]:
        if a["name"] == agent_name:
            executor_id = a.get("executor_id")
            break

    return AgentContext(
        name=agent_name,
        wallet_address=wallet["address"],
        workspace_dir=ROOT / "data" / "workspaces" / agent_name,
        executor_id=executor_id,
    )


async def publish_offerings(
    agent_name: str,
    offerings: list[dict],
    dry_run: bool = False,
) -> list[dict]:
    """Publish a list of offerings on EM for a given agent."""
    results = []
    ctx = _load_agent_context(agent_name)

    if dry_run:
        for offering in offerings:
            results.append({
                "dry_run": True,
                "agent": agent_name,
                "title": offering["title"],
                "bounty_usd": offering["bounty_usd"],
            })
            print(f"  [DRY-RUN] {agent_name}: {offering['title']} (${offering['bounty_usd']})")
        return results

    client = EMClient(ctx)
    try:
        for offering in offerings:
            try:
                result = await client.publish_task(
                    title=offering["title"],
                    instructions=offering["instructions"],
                    category=offering["category"],
                    bounty_usd=offering["bounty_usd"],
                    deadline_hours=24,
                )
                results.append({
                    "success": True,
                    "agent": agent_name,
                    "title": offering["title"],
                    "task_id": result.get("id", result.get("task_id")),
                })
                print(f"  [OK] {agent_name}: {offering['title']} (${offering['bounty_usd']})")
            except Exception as e:
                results.append({
                    "success": False,
                    "agent": agent_name,
                    "title": offering["title"],
                    "error": str(e),
                })
                print(f"  [FAIL] {agent_name}: {offering['title']} -> {e}")
    finally:
        await client.close()

    return results


async def run(dry_run: bool = False):
    """Bootstrap the economy."""
    all_results = []

    print("\n=== KK Economy Bootstrap ===\n")

    # Phase 1: karma-hello publishes chat log bundles
    print("[Phase 1] kk-karma-hello: Publishing 5 chat log bundles...")
    r1 = await publish_offerings("kk-karma-hello", KARMA_HELLO_OFFERINGS, dry_run)
    all_results.extend(r1)

    print()

    # Phase 2: coordinator publishes seed tasks
    print("[Phase 2] kk-coordinator: Publishing 5 seed tasks...")
    r2 = await publish_offerings("kk-coordinator", COORDINATOR_TASKS, dry_run)
    all_results.extend(r2)

    # Summary
    total = len(all_results)
    succeeded = sum(1 for r in all_results if r.get("success") or r.get("dry_run"))
    failed = total - succeeded

    print(f"\n=== Summary ===")
    print(f"Total: {total} | Succeeded: {succeeded} | Failed: {failed}")

    if dry_run:
        print("\n(Dry run -- nothing was actually published)")

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Bootstrap KK economy with seed offerings")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be published without doing it")
    args = parser.parse_args()

    try:
        results = asyncio.run(run(dry_run=args.dry_run))
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
