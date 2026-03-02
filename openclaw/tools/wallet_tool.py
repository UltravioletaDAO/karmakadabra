#!/usr/bin/env python3
"""
OpenClaw Tool: Wallet & Budget Operations

Check USDC balance on Base, daily spending, and budget availability.
Reads JSON from stdin, outputs JSON to stdout.

Actions:
  balance    — check USDC balance on Base mainnet
  budget     — daily spending summary
  can_afford — check if amount is within daily budget
"""

import sys
sys.path.insert(0, "/app")

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("kk.tool.wallet")

BASE_RPC = "https://mainnet.base.org"
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BALANCE_OF_SELECTOR = "0x70a08231"
DEFAULT_DAILY_BUDGET = 2.00


def _load_wallet() -> dict:
    agent_name = os.environ.get("KK_AGENT_NAME", "unknown")
    wallet_file = Path(f"/app/workspaces/{agent_name}/data/wallet.json")
    if not wallet_file.exists():
        return {}
    return json.loads(wallet_file.read_text(encoding="utf-8"))


def _load_daily_spent() -> float:
    """Read daily spent from WORKING.md or escrow state."""
    agent_name = os.environ.get("KK_AGENT_NAME", "unknown")
    working_file = Path(f"/app/workspaces/{agent_name}/memory/WORKING.md")

    if working_file.exists():
        try:
            content = working_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if "Daily Spent" in line:
                    # Format: ## Daily Spent: $0.05
                    part = line.split("$")[-1].strip()
                    return float(part)
        except (ValueError, IndexError):
            pass

    # Fallback: count from escrow state
    state_file = Path("/app/data/escrow_state.json")
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            total = 0.0
            for task in state.get("published_bounties", []):
                ts = task.get("timestamp", "")
                if ts.startswith(today):
                    total += float(task.get("bounty_usd", 0))
            return total
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    return 0.0


def action_balance(params: dict) -> dict:
    """Check USDC balance on Base via raw eth_call (no web3 dependency)."""
    import httpx

    wallet = _load_wallet()
    address = wallet.get("address", "")
    if not address:
        return {"error": "No wallet address found"}

    padded = address.lower().replace("0x", "").zfill(64)
    call_data = f"{BALANCE_OF_SELECTOR}{padded}"

    try:
        resp = httpx.post(
            BASE_RPC,
            json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {"to": BASE_USDC, "data": call_data},
                    "latest",
                ],
                "id": 1,
            },
            timeout=15,
        )
        data = resp.json()
        hex_balance = data.get("result", "0x0")
        if hex_balance == "0x" or not hex_balance:
            balance = 0.0
        else:
            balance = int(hex_balance, 16) / 1_000_000  # USDC has 6 decimals

        return {
            "address": address,
            "chain": "base",
            "token": "USDC",
            "balance": round(balance, 6),
            "balance_display": f"${balance:.4f}",
        }
    except Exception as e:
        return {"error": f"RPC call failed: {e}"}


def action_budget(params: dict) -> dict:
    """Daily spending summary."""
    daily_spent = _load_daily_spent()
    daily_budget = params.get("daily_budget", DEFAULT_DAILY_BUDGET)
    remaining = max(0, daily_budget - daily_spent)

    return {
        "daily_budget_usd": daily_budget,
        "daily_spent_usd": round(daily_spent, 4),
        "remaining_usd": round(remaining, 4),
        "utilization_pct": round((daily_spent / daily_budget * 100) if daily_budget > 0 else 0, 1),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


def action_can_afford(params: dict) -> dict:
    """Check if an amount is within the remaining daily budget."""
    amount = params.get("amount", 0)
    if not amount or amount <= 0:
        return {"error": "amount must be a positive number"}

    daily_spent = _load_daily_spent()
    daily_budget = params.get("daily_budget", DEFAULT_DAILY_BUDGET)
    remaining = max(0, daily_budget - daily_spent)
    can_afford = amount <= remaining

    return {
        "amount_usd": amount,
        "can_afford": can_afford,
        "remaining_usd": round(remaining, 4),
        "daily_spent_usd": round(daily_spent, 4),
        "daily_budget_usd": daily_budget,
    }


ACTIONS = {
    "balance": action_balance,
    "budget": action_budget,
    "can_afford": action_can_afford,
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
        result = ACTIONS[action](params)
        print(json.dumps(result, default=str))
    except Exception as e:
        logger.exception("wallet_tool action failed")
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))


if __name__ == "__main__":
    main()
