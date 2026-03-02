#!/usr/bin/env python3
"""
OpenClaw Tool: Execution Market Operations

Wraps services/em_client.py for OpenClaw subprocess calls.
Reads JSON from stdin, outputs JSON to stdout.

Actions:
  browse   — list available tasks
  publish  — publish a task/bounty
  apply    — apply to a task
  submit   — submit evidence
  approve  — approve a submission
  status   — list my active tasks
  history  — get purchase history
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
logger = logging.getLogger("kk.tool.em")


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


async def action_browse(params: dict) -> dict:
    from services.em_client import EMClient

    ctx = _load_context()
    client = EMClient(ctx)
    try:
        tasks = await client.browse_tasks(
            status=params.get("status", "published"),
            category=params.get("category"),
            limit=params.get("limit", 20),
            target_executor=params.get("target_executor"),
            skills=params.get("skills"),
        )
        return {"tasks": tasks, "count": len(tasks)}
    finally:
        await client.close()


async def action_publish(params: dict) -> dict:
    from services.em_client import EMClient

    ctx = _load_context()
    client = EMClient(ctx)
    try:
        required_fields = ["title", "instructions", "category", "bounty_usd"]
        for f in required_fields:
            if f not in params:
                return {"error": f"Missing required field: {f}"}

        result = await client.publish_task(
            title=params["title"],
            instructions=params["instructions"],
            category=params["category"],
            bounty_usd=float(params["bounty_usd"]),
            evidence_required=params.get("evidence_required", ["json_response"]),
            target_executor=params.get("target_executor", "any"),
            skills_required=params.get("skills_required"),
        )
        return {"published": True, "task": result}
    finally:
        await client.close()


async def action_apply(params: dict) -> dict:
    from services.em_client import EMClient

    ctx = _load_context()
    if not ctx.executor_id:
        return {"error": "No executor_id found in wallet.json"}

    client = EMClient(ctx)
    try:
        task_id = params.get("task_id")
        if not task_id:
            return {"error": "Missing required field: task_id"}

        result = await client.apply_to_task(
            task_id=task_id,
            executor_id=ctx.executor_id,
            message=params.get("message", ""),
        )
        return {"applied": True, "result": result}
    finally:
        await client.close()


async def action_submit(params: dict) -> dict:
    from services.em_client import EMClient

    ctx = _load_context()
    if not ctx.executor_id:
        return {"error": "No executor_id found in wallet.json"}

    client = EMClient(ctx)
    try:
        task_id = params.get("task_id")
        if not task_id:
            return {"error": "Missing required field: task_id"}

        evidence = params.get("evidence", {})
        if not isinstance(evidence, dict):
            return {"error": "evidence must be a dict keyed by evidence type"}

        result = await client.submit_evidence(
            task_id=task_id,
            executor_id=ctx.executor_id,
            evidence=evidence,
            notes=params.get("notes", ""),
        )
        return {"submitted": True, "result": result}
    finally:
        await client.close()


async def action_approve(params: dict) -> dict:
    from services.em_client import EMClient

    ctx = _load_context()
    client = EMClient(ctx)
    try:
        submission_id = params.get("submission_id")
        if not submission_id:
            return {"error": "Missing required field: submission_id"}

        result = await client.approve_submission(
            submission_id=submission_id,
            rating_score=params.get("rating_score", 80),
            notes=params.get("notes", ""),
        )
        return {"approved": True, "result": result}
    finally:
        await client.close()


async def action_status(params: dict) -> dict:
    from services.em_client import EMClient

    ctx = _load_context()
    client = EMClient(ctx)
    try:
        tasks = await client.list_tasks(status=params.get("status"))
        return {"tasks": tasks, "count": len(tasks)}
    finally:
        await client.close()


async def action_history(params: dict) -> dict:
    """Read purchase history from escrow state file."""
    agent_name = os.environ.get("KK_AGENT_NAME", "unknown")
    data_dir = Path("/app/data")
    state_file = data_dir / "escrow_state.json"

    if not state_file.exists():
        return {"purchases": [], "count": 0}

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        # escrow_state.json has published_bounties and applied_tasks
        published = state.get("published_bounties", [])
        applied = state.get("applied_tasks", [])
        completed = [t for t in published if t.get("status") == "completed"]
        return {
            "published_bounties": len(published),
            "applied_tasks": len(applied),
            "completed_tasks": len(completed),
            "recent_published": published[-10:],
            "recent_applied": applied[-10:],
        }
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Failed to read escrow state: {e}"}


ACTIONS = {
    "browse": action_browse,
    "publish": action_publish,
    "apply": action_apply,
    "submit": action_submit,
    "approve": action_approve,
    "status": action_status,
    "history": action_history,
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
        logger.exception("em_tool action failed")
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))


if __name__ == "__main__":
    main()
