#!/usr/bin/env python3
"""
OpenClaw Tool: Reputation Operations

Query and submit agent reputation ratings via EM API.
Intended for coordinator and validator agents.
Reads JSON from stdin, outputs JSON to stdout.

Actions:
  check_reputation — query agent reputation
  rate_agent       — rate an agent after a transaction
"""

import sys
sys.path.insert(0, "/app")

import asyncio
import json
import logging
import os
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("kk.tool.reputation")


def _load_context():
    """Load AgentContext from workspace wallet.json."""
    from services.em_client import AgentContext

    agent_name = os.environ.get("KK_AGENT_NAME", "unknown")
    workspace = Path(f"/app/workspaces/{agent_name}")
    wallet_file = workspace / "data" / "wallet.json"

    wallet_data = {}
    if wallet_file.exists():
        wallet_data = json.loads(wallet_file.read_text(encoding="utf-8"))

    return AgentContext(
        name=agent_name,
        wallet_address=wallet_data.get("address", ""),
        workspace_dir=workspace,
        private_key=wallet_data.get("private_key", ""),
        chain_id=int(wallet_data.get("chain_id", 8453)),
        executor_id=wallet_data.get("executor_id"),
    )


async def action_check_reputation(params: dict) -> dict:
    """Query reputation for an agent by wallet or agent ID."""
    from services.em_client import EMClient

    agent_id = params.get("agent_id")
    if not agent_id:
        return {"error": "Missing required field: agent_id (wallet address or ERC-8004 ID)"}

    ctx = _load_context()
    client = EMClient(ctx)
    try:
        result = await client.get_agent_reputation(agent_id)
        return {"agent_id": agent_id, "reputation": result}
    except Exception as e:
        return {"error": f"Failed to get reputation: {e}"}
    finally:
        await client.close()


async def action_rate_agent(params: dict) -> dict:
    """Rate an agent after completing a transaction.

    Supports rating both as buyer (rate_worker) and as seller (rate_agent).
    Detects which method to use based on the presence of worker_wallet vs agent_id.
    """
    from services.em_client import EMClient

    task_id = params.get("task_id")
    if not task_id:
        return {"error": "Missing required field: task_id"}

    score = params.get("score", 5)
    if not (1 <= score <= 5):
        return {"error": "score must be between 1 and 5"}

    comment = params.get("comment", "")
    agent_id_or_wallet = params.get("agent_id_or_wallet", "")
    if not agent_id_or_wallet:
        return {"error": "Missing required field: agent_id_or_wallet"}

    ctx = _load_context()
    client = EMClient(ctx)
    try:
        # If it looks like a wallet address (0x...), rate as worker
        # If it looks like a numeric ID, rate as agent
        if agent_id_or_wallet.startswith("0x"):
            result = await client.rate_worker(
                task_id=task_id,
                worker_wallet=agent_id_or_wallet,
                score=score,
                comment=comment,
            )
            return {"rated": True, "type": "worker", "result": result}
        else:
            result = await client.rate_agent(
                task_id=task_id,
                agent_id=agent_id_or_wallet,
                score=score,
                comment=comment,
            )
            return {"rated": True, "type": "agent", "result": result}
    except Exception as e:
        return {"error": f"Rating failed: {e}"}
    finally:
        await client.close()


ACTIONS = {
    "check_reputation": action_check_reputation,
    "rate_agent": action_rate_agent,
}


def main():
    try:
        raw = sys.stdin.read()
        request = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        return

    action = request.get("action", "")
    params = request.get("params", {})

    if action not in ACTIONS:
        print(json.dumps({
            "error": f"Unknown action: {action}",
            "available": list(ACTIONS.keys()),
        }))
        return

    try:
        result = asyncio.run(ACTIONS[action](params))
        print(json.dumps(result, default=str))
    except Exception as e:
        logger.exception("reputation_tool action failed")
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))


if __name__ == "__main__":
    main()
