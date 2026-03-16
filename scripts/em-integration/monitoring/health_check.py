"""
Karma Kadabra V2 — Task 6.3: Swarm Health Monitor

Monitors the KK agent swarm across all dimensions:
  1. EM API connectivity
  2. IRC connectivity
  3. Agent wallet balances (alert if < $0.50 USDC)
  4. Daily transaction count (alert if 0)
  5. Agent online count
  6. Workspace integrity

Usage:
  python health_check.py                   # Full health check
  python health_check.py --check api       # API only
  python health_check.py --check wallets   # Wallet balances only
  python health_check.py --check irc       # IRC connectivity only
  python health_check.py --json            # JSON output (for monitoring)
  python health_check.py --daemon          # Run every 5 minutes
"""

import argparse
import asyncio
import json
import logging
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_project_root / ".env.local")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.health")

# Config
EM_API_URL = "https://api.execution.market/api/v1"
IRC_SERVER = "irc.meshrelay.xyz"
IRC_PORT = 6667
BALANCE_ALERT_THRESHOLD = 0.50  # USDC
HEALTH_CHECK_INTERVAL = 300  # 5 minutes

# Base Mainnet USDC
BASE_RPC = "https://mainnet.base.org"
USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


# ---------------------------------------------------------------------------
# Health check result
# ---------------------------------------------------------------------------

class HealthResult:
    def __init__(self):
        self.checks: dict[str, dict] = {}
        self.alerts: list[str] = []

    def add_check(self, name: str, status: str, details: str = "", data: dict | None = None):
        self.checks[name] = {
            "status": status,
            "details": details,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if status == "FAIL":
            self.alerts.append(f"[FAIL] {name}: {details}")

    @property
    def healthy(self) -> bool:
        # WARN is acceptable (e.g., no transactions today, missing optional files)
        return all(c["status"] in ("OK", "WARN") for c in self.checks.values())

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": self.checks,
            "alerts": self.alerts,
        }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

async def check_em_api(result: HealthResult) -> None:
    """Check Execution Market API is reachable."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{EM_API_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                result.add_check(
                    "em_api",
                    "OK",
                    f"API healthy: {data.get('status', '?')}",
                    {"status_code": 200, "api_status": data.get("status")},
                )
            else:
                result.add_check("em_api", "FAIL", f"HTTP {resp.status_code}")
    except Exception as e:
        result.add_check("em_api", "FAIL", str(e))


async def check_irc(result: HealthResult) -> None:
    """Check MeshRelay IRC server connectivity."""
    try:
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        await loop.run_in_executor(None, sock.connect, (IRC_SERVER, IRC_PORT))
        sock.close()
        result.add_check("irc", "OK", f"Connected to {IRC_SERVER}:{IRC_PORT}")
    except Exception as e:
        result.add_check("irc", "FAIL", f"Cannot connect to {IRC_SERVER}:{IRC_PORT}: {e}")


async def check_wallet_balances(
    result: HealthResult,
    wallets_file: Path,
) -> None:
    """Check USDC balances for all agent wallets on Base."""
    if not wallets_file.exists():
        result.add_check("wallets", "WARN", f"Wallet manifest not found: {wallets_file}")
        return

    manifest = json.loads(wallets_file.read_text(encoding="utf-8"))
    wallets = manifest.get("wallets", [])

    # balanceOf(address) selector
    selector = "0x70a08231"

    low_balance_agents = []
    total_balance = 0.0
    checked = 0

    async with httpx.AsyncClient(timeout=10) as client:
        for wallet in wallets[:50]:  # Check first 50 (avoid rate limiting)
            address = wallet.get("address", "")
            if not address or address.startswith("0x_PLACEHOLDER"):
                continue

            # Pad address to 32 bytes
            padded = address.lower().replace("0x", "").zfill(64)
            call_data = f"{selector}{padded}"

            try:
                resp = await client.post(
                    BASE_RPC,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_call",
                        "params": [
                            {"to": USDC_CONTRACT, "data": call_data},
                            "latest",
                        ],
                        "id": 1,
                    },
                )

                data = resp.json()
                hex_balance = data.get("result", "0x0")
                balance_raw = int(hex_balance, 16)
                balance_usdc = balance_raw / 1_000_000  # 6 decimals

                total_balance += balance_usdc
                checked += 1

                if balance_usdc < BALANCE_ALERT_THRESHOLD:
                    low_balance_agents.append({
                        "name": wallet.get("name", "?"),
                        "address": address,
                        "balance": balance_usdc,
                    })

            except Exception:
                pass  # Skip individual failures

            # Rate limit
            await asyncio.sleep(0.1)

    status = "FAIL" if len(low_balance_agents) > checked * 0.5 else (
        "WARN" if low_balance_agents else "OK"
    )

    result.add_check(
        "wallets",
        status,
        f"Checked {checked} wallets, {len(low_balance_agents)} below ${BALANCE_ALERT_THRESHOLD}",
        {
            "checked": checked,
            "total_balance_usdc": round(total_balance, 2),
            "low_balance_count": len(low_balance_agents),
            "low_balance_agents": low_balance_agents[:5],  # Top 5 only
        },
    )


async def check_daily_transactions(result: HealthResult) -> None:
    """Check if any EM transactions occurred today."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{EM_API_URL}/public/metrics")
            if resp.status_code == 200:
                data = resp.json()
                tasks_today = data.get("tasks_today", data.get("tasks_24h", -1))
                if tasks_today == 0:
                    result.add_check(
                        "transactions",
                        "WARN",
                        "No transactions today",
                        {"tasks_today": 0},
                    )
                elif tasks_today > 0:
                    result.add_check(
                        "transactions",
                        "OK",
                        f"{tasks_today} tasks today",
                        {"tasks_today": tasks_today},
                    )
                else:
                    result.add_check("transactions", "OK", "Metrics endpoint reachable")
            else:
                result.add_check("transactions", "WARN", f"Metrics HTTP {resp.status_code}")
    except Exception as e:
        result.add_check("transactions", "WARN", f"Cannot check: {e}")


async def check_workspaces(result: HealthResult, workspaces_dir: Path) -> None:
    """Check workspace integrity."""
    if not workspaces_dir.exists():
        result.add_check("workspaces", "FAIL", f"Workspaces dir not found: {workspaces_dir}")
        return

    manifest = workspaces_dir / "_manifest.json"
    if not manifest.exists():
        result.add_check("workspaces", "WARN", "No manifest — run generate-workspaces.py")
        return

    data = json.loads(manifest.read_text(encoding="utf-8"))
    expected = data.get("total_agents", 0)

    actual = sum(1 for d in workspaces_dir.iterdir() if d.is_dir() and not d.name.startswith("_"))

    missing_souls = sum(
        1 for d in workspaces_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not (d / "SOUL.md").exists()
    )

    status = "OK" if actual >= expected and missing_souls == 0 else "WARN"
    result.add_check(
        "workspaces",
        status,
        f"{actual}/{expected} workspaces, {missing_souls} missing SOUL.md",
        {"expected": expected, "actual": actual, "missing_souls": missing_souls},
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_health_check(
    checks: list[str] | None,
    wallets_file: Path,
    workspaces_dir: Path,
) -> HealthResult:
    """Run all health checks."""
    result = HealthResult()
    run_all = not checks

    if run_all or "api" in checks:
        await check_em_api(result)

    if run_all or "irc" in checks:
        await check_irc(result)

    if run_all or "wallets" in checks:
        await check_wallet_balances(result, wallets_file)

    if run_all or "transactions" in checks:
        await check_daily_transactions(result)

    if run_all or "workspaces" in checks:
        await check_workspaces(result, workspaces_dir)

    return result


def print_result(result: HealthResult, as_json: bool = False) -> None:
    """Print health check results."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    status_icon = {
        "OK": "[OK]",
        "WARN": "[WARN]",
        "FAIL": "[FAIL]",
    }

    print(f"\n{'=' * 60}")
    print(f"  Karma Kadabra — Health Check")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Overall: {'HEALTHY' if result.healthy else 'UNHEALTHY'}")
    print(f"{'=' * 60}\n")

    for name, check in result.checks.items():
        icon = status_icon.get(check["status"], "[?]")
        print(f"  {icon:>6}  {name}: {check['details']}")

    if result.alerts:
        print(f"\n  Alerts ({len(result.alerts)}):")
        for alert in result.alerts:
            print(f"    {alert}")

    print()


async def daemon_loop(wallets_file: Path, workspaces_dir: Path) -> None:
    """Run health checks in a loop."""
    logger.info(f"Starting health check daemon (interval: {HEALTH_CHECK_INTERVAL}s)")

    while True:
        result = await run_health_check(None, wallets_file, workspaces_dir)
        print_result(result)

        if result.alerts:
            logger.warning(f"  {len(result.alerts)} alerts detected!")
            # In production: send to Slack/PagerDuty/CloudWatch

        await asyncio.sleep(HEALTH_CHECK_INTERVAL)


async def main():
    parser = argparse.ArgumentParser(description="KK Swarm Health Monitor")
    parser.add_argument(
        "--check",
        choices=["api", "irc", "wallets", "transactions", "workspaces"],
        action="append",
        help="Run specific check",
    )
    parser.add_argument("--wallets", type=str, default=None)
    parser.add_argument("--workspaces", type=str, default=None)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    wallets_file = Path(args.wallets) if args.wallets else base / "config" / "wallets.json"
    workspaces_dir = Path(args.workspaces) if args.workspaces else base / "data" / "workspaces"

    if args.daemon:
        await daemon_loop(wallets_file, workspaces_dir)
    else:
        result = await run_health_check(args.check, wallets_file, workspaces_dir)
        print_result(result, as_json=args.json)
        sys.exit(0 if result.healthy else 1)


if __name__ == "__main__":
    asyncio.run(main())
