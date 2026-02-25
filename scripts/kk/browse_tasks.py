#!/usr/bin/env python3
"""Browse available tasks on Execution Market.

Usage:
    python browse_tasks.py --agent kk-karma-hello [--category knowledge_access] [--limit 10]
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
        tasks = await client.browse_tasks(
            category=args.category,
            limit=args.limit,
        )
        print(json.dumps(tasks, indent=2))
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="Browse EM tasks")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--category", default=None, help="Task category filter")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
