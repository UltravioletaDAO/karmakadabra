#!/usr/bin/env python3
"""Apply to a task on Execution Market.

Usage:
    python apply_task.py --agent kk-karma-hello --task-id UUID [--message "I can do this"]
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
    if not identity or not identity.get("executor_id"):
        raise ValueError(f"Agent '{agent_name}' has no executor_id in identities.json")

    return AgentContext(
        name=agent_name,
        wallet_address=wallet["address"],
        workspace_dir=root / "data" / "workspaces" / agent_name,
        executor_id=identity["executor_id"],
    )


async def run(args):
    ctx = load_agent_context(args.agent)
    client = EMClient(ctx)
    try:
        result = await client.apply_to_task(
            task_id=args.task_id,
            executor_id=ctx.executor_id,
            message=args.message or "",
        )
        print(json.dumps(result, indent=2))
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="Apply to an EM task")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--task-id", required=True, help="Task UUID")
    parser.add_argument("--message", default="", help="Application message")
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
