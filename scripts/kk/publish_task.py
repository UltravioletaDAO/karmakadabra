#!/usr/bin/env python3
"""Publish a new task on Execution Market.

Usage:
    python publish_task.py --agent kk-karma-hello --title "Chat logs bundle" \
        --instructions "Bundle of 100 chat messages" --category knowledge_access \
        --bounty 0.01 [--deadline-hours 24]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.em_client import AgentContext, EMClient


def load_agent_context(agent_name: str) -> AgentContext:
    root = Path(__file__).parent.parent.parent
    wallets = json.loads((root / "data" / "config" / "wallets.json").read_text(encoding="utf-8"))
    identities = json.loads((root / "data" / "config" / "identities.json").read_text(encoding="utf-8"))

    wallet = None
    for w in wallets["wallets"]:
        if w["name"] == agent_name:
            wallet = w
            break
    if not wallet:
        raise ValueError(f"Agent '{agent_name}' not found in wallets.json")

    identity = None
    for a in identities["agents"]:
        if a["name"] == agent_name:
            identity = a
            break

    return AgentContext(
        name=agent_name,
        wallet_address=wallet["address"],
        workspace_dir=root / "data" / "workspaces" / agent_name,
        executor_id=identity["executor_id"] if identity else None,
    )


async def run(args):
    ctx = load_agent_context(args.agent)
    client = EMClient(ctx)
    try:
        result = await client.publish_task(
            title=args.title,
            instructions=args.instructions,
            category=args.category,
            bounty_usd=args.bounty,
            deadline_hours=args.deadline_hours,
        )
        print(json.dumps(result, indent=2))
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="Publish a task on EM")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--title", required=True, help="Task title")
    parser.add_argument("--instructions", required=True, help="Task instructions")
    parser.add_argument("--category", required=True, help="Task category")
    parser.add_argument("--bounty", type=float, required=True, help="Bounty in USD")
    parser.add_argument("--deadline-hours", type=int, default=24, help="Deadline in hours")
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
