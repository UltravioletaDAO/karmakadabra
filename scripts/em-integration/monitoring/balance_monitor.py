"""
Karma Kadabra V2 — Phase 11: Cross-Chain Balance Monitor

Monitors USDC balances for all KK agent wallets across supported chains.
Reads wallet addresses from workspace data/wallet.json files and checks
on-chain balances via RPC eth_call (balanceOf).

Usage:
  python balance_monitor.py                               # All chains, all agents
  python balance_monitor.py --chain base                  # Base only
  python balance_monitor.py --chain polygon               # Polygon only
  python balance_monitor.py --threshold 1.00              # Custom alert threshold
  python balance_monitor.py --workspaces-dir /path/to/ws  # Custom workspace path
  python balance_monitor.py --json                        # JSON output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.balance_monitor")

# Chain configuration: name -> (rpc_url, usdc_contract)
CHAIN_CONFIG: dict[str, dict[str, str]] = {
    "base": {
        "rpc": "https://mainnet.base.org",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    },
    "polygon": {
        "rpc": "https://polygon-rpc.com",
        "usdc": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    },
    "arbitrum": {
        "rpc": "https://arb1.arbitrum.io/rpc",
        "usdc": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
    "avalanche": {
        "rpc": "https://api.avax.network/ext/bc/C/rpc",
        "usdc": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
    },
}

DEFAULT_THRESHOLD = 0.50  # USD
BALANCE_OF_SELECTOR = "0x70a08231"  # balanceOf(address)


# ---------------------------------------------------------------------------
# Wallet discovery
# ---------------------------------------------------------------------------


def discover_wallets(workspaces_dir: Path) -> list[dict[str, str]]:
    """Discover agent wallets from workspace data/wallet.json files.

    Returns:
        List of dicts with: name, address.
    """
    wallets = []

    if not workspaces_dir.exists():
        return wallets

    for ws in sorted(workspaces_dir.iterdir()):
        if not ws.is_dir() or ws.name.startswith("_"):
            continue

        wallet_file = ws / "data" / "wallet.json"
        if not wallet_file.exists():
            continue

        try:
            data = json.loads(wallet_file.read_text(encoding="utf-8"))
            address = data.get("address", "")
            if address and not address.startswith("0x_PLACEHOLDER"):
                wallets.append({
                    "name": ws.name,
                    "address": address,
                })
        except Exception:
            pass

    return wallets


# ---------------------------------------------------------------------------
# Balance checking
# ---------------------------------------------------------------------------


async def check_balance(
    client: httpx.AsyncClient,
    rpc_url: str,
    usdc_contract: str,
    wallet_address: str,
) -> float | None:
    """Check USDC balance for a single wallet on a single chain.

    Returns:
        Balance in USDC (float) or None on failure.
    """
    padded = wallet_address.lower().replace("0x", "").zfill(64)
    call_data = f"{BALANCE_OF_SELECTOR}{padded}"

    try:
        resp = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {"to": usdc_contract, "data": call_data},
                    "latest",
                ],
                "id": 1,
            },
        )
        data = resp.json()
        hex_balance = data.get("result", "0x0")
        if hex_balance == "0x" or not hex_balance:
            return 0.0
        balance_raw = int(hex_balance, 16)
        return balance_raw / 1_000_000  # USDC has 6 decimals
    except Exception as e:
        logger.debug(f"Balance check failed for {wallet_address}: {e}")
        return None


async def check_all_balances(
    wallets: list[dict[str, str]],
    chains: list[str],
    threshold: float,
) -> dict[str, Any]:
    """Check balances for all wallets across specified chains.

    Returns:
        Report dict with balances and alerts.
    """
    results: list[dict[str, Any]] = []
    alerts: list[str] = []
    total_balance = 0.0
    checked = 0

    async with httpx.AsyncClient(timeout=15) as client:
        for wallet in wallets:
            name = wallet["name"]
            address = wallet["address"]
            wallet_result: dict[str, Any] = {
                "name": name,
                "address": address,
                "balances": {},
                "total": 0.0,
                "alert": False,
            }

            for chain in chains:
                config = CHAIN_CONFIG.get(chain)
                if not config:
                    continue

                balance = await check_balance(
                    client, config["rpc"], config["usdc"], address
                )

                if balance is not None:
                    wallet_result["balances"][chain] = round(balance, 6)
                    wallet_result["total"] += balance
                    total_balance += balance
                    checked += 1
                else:
                    wallet_result["balances"][chain] = None

                # Rate limit between RPC calls
                await asyncio.sleep(0.1)

            wallet_result["total"] = round(wallet_result["total"], 6)

            if wallet_result["total"] < threshold:
                wallet_result["alert"] = True
                alerts.append(
                    f"{name} ({address[:10]}...): ${wallet_result['total']:.4f} < ${threshold:.2f}"
                )

            results.append(wallet_result)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chains": chains,
        "threshold": threshold,
        "total_wallets": len(wallets),
        "checked": checked,
        "total_balance_usdc": round(total_balance, 2),
        "alerts_count": len(alerts),
        "alerts": alerts,
        "wallets": results,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_table(report: dict[str, Any]) -> str:
    """Format report as a human-readable table."""
    lines = []
    chains = report["chains"]
    threshold = report["threshold"]

    lines.append(f"\n{'=' * 70}")
    lines.append(f"  Karma Kadabra -- Balance Monitor")
    lines.append(f"  Time: {report['timestamp'][:19]}Z")
    lines.append(f"  Chains: {', '.join(chains)}")
    lines.append(f"  Alert threshold: ${threshold:.2f} USDC")
    lines.append(f"{'=' * 70}")

    # Header
    chain_headers = "".join(f"{c:>12}" for c in chains)
    lines.append(f"\n  {'Agent':<25}{chain_headers}{'Total':>12}  Alert")
    lines.append(f"  {'-' * 25}{'-' * 12 * len(chains)}{'-' * 12}  -----")

    for w in report["wallets"]:
        name = w["name"][:25]
        chain_vals = ""
        for c in chains:
            bal = w["balances"].get(c)
            if bal is not None:
                chain_vals += f"  ${bal:>8.4f}"
            else:
                chain_vals += f"  {'--':>8}"
        total = f"  ${w['total']:>8.4f}"
        alert_mark = "  [!]" if w["alert"] else ""
        lines.append(f"  {name:<25}{chain_vals}{total}{alert_mark}")

    # Summary
    lines.append(f"\n  Total USDC across swarm: ${report['total_balance_usdc']:.2f}")
    lines.append(f"  Wallets checked: {report['total_wallets']}")

    if report["alerts"]:
        lines.append(f"\n  ALERTS ({report['alerts_count']}):")
        for alert in report["alerts"][:10]:
            lines.append(f"    [!] {alert}")
    else:
        lines.append(f"\n  No balance alerts.")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="KK Cross-Chain Balance Monitor")
    parser.add_argument(
        "--chain",
        choices=list(CHAIN_CONFIG.keys()) + ["all"],
        default="all",
        help="Chain to check (default: all)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Alert threshold in USDC (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument("--workspaces-dir", type=str, default=None)
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspaces_dir = (
        Path(args.workspaces_dir) if args.workspaces_dir else base / "data" / "workspaces"
    )

    chains = list(CHAIN_CONFIG.keys()) if args.chain == "all" else [args.chain]

    wallets = discover_wallets(workspaces_dir)
    if not wallets:
        print("No wallets found. Run generate-workspaces.py first.")
        return

    logger.info(f"Checking {len(wallets)} wallets on {', '.join(chains)}...")

    report = await check_all_balances(wallets, chains, args.threshold)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_table(report))


if __name__ == "__main__":
    asyncio.run(main())
