#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 -- Multi-Chain Integration Test

Runs the KK integration test across multiple EVM chains to verify
agent-to-agent operations work on all deployed payment networks.

Supported chains:
  Base (8453)       -- primary, always tested first
  Polygon (137)     -- Fase 5 operator deployed
  Arbitrum (42161)  -- Fase 5 operator deployed
  Avalanche (43114) -- Fase 5 operator deployed

Usage:
    python scripts/kk/tests/test_multichain_integration.py                    # Base only (default)
    python scripts/kk/tests/test_multichain_integration.py --network polygon  # Single chain
    python scripts/kk/tests/test_multichain_integration.py --all              # All 4 chains
    python scripts/kk/tests/test_multichain_integration.py --all --live       # All 4, live ($0.40)
    python scripts/kk/tests/test_multichain_integration.py --dry-run          # Config check only

    pytest scripts/kk/tests/test_multichain_integration.py -v                 # Via pytest

Environment:
    EM_API_URL           -- API base (default: https://api.execution.market)
    EM_API_KEY           -- Agent API key
    EM_WORKER_WALLET     -- Worker wallet for Agent B
    EM_TEST_EXECUTOR_ID  -- Existing executor UUID
    EM_WORKER_PRIVATE_KEY -- Worker private key (for on-chain reputation)

Cost:
    Mock mode: $0.00 (no on-chain transactions)
    Live mode: ~$0.10 per chain (credit card model)
    --all --live: ~$0.40 total (4 chains x $0.10)
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
_script_dir = Path(__file__).parent
_project_root = _script_dir.parent.parent.parent
load_dotenv(_project_root / "mcp_server" / ".env")
load_dotenv(_project_root / ".env.local")

# Ensure sibling test module is importable regardless of working directory
sys.path.insert(0, str(_script_dir))

# Import from sibling test module
from test_integration import (
    DEFAULT_BOUNTY,
    IntegrationResults,
    _print_header,
    _print_kv,
    run_integration_test,
    ts,
)

# ---------------------------------------------------------------------------
# Chain configurations
# ---------------------------------------------------------------------------
SUPPORTED_CHAINS: Dict[str, Dict[str, Any]] = {
    "base": {
        "chain_id": 8453,
        "display_name": "Base",
        "operator": "0x271f9fa7f8907aCf178CCFB470076D9129D8F0Eb",
        "token": "USDC",
        "golden_flow_status": "PASS",
    },
    "polygon": {
        "chain_id": 137,
        "display_name": "Polygon",
        "operator": "0xB87F1ECC85f074e50df3DD16A1F40e4e1EC4102e",
        "token": "USDC",
        "golden_flow_status": "PASS",
    },
    "arbitrum": {
        "chain_id": 42161,
        "display_name": "Arbitrum",
        "operator": "0xC2377a9Db1de2520BD6b2756eD012f4E82F7938e",
        "token": "USDC",
        "golden_flow_status": "PASS",
    },
    "avalanche": {
        "chain_id": 43114,
        "display_name": "Avalanche",
        "operator": "0xC2377a9Db1de2520BD6b2756eD012f4E82F7938e",
        "token": "USDC",
        "golden_flow_status": "PASS",
    },
}

# Chains excluded from multi-chain testing (known SDK issues)
EXCLUDED_CHAINS: Dict[str, str] = {
    "monad": "SDK EIP-712 domain bug (USDC name mismatch)",
    "celo": "SDK EIP-712 domain bug (USDC name mismatch)",
    "optimism": "SDK missing chain_id 10 in ESCROW_CONTRACTS registry",
    "ethereum": "SDK factory label mismatch (pending BackTrack fix)",
}

DEFAULT_NETWORK = "base"


# ---------------------------------------------------------------------------
# Multi-chain result collector
# ---------------------------------------------------------------------------
class MultichainResults:
    """Collects per-chain integration test results."""

    def __init__(self):
        self.chain_results: Dict[str, IntegrationResults] = {}
        self.start_time = time.time()

    def add(self, network: str, results: IntegrationResults) -> None:
        self.chain_results[network] = results

    @property
    def all_passed(self) -> bool:
        return all(r.fail_count == 0 for r in self.chain_results.values())

    @property
    def chains_passed(self) -> int:
        return sum(1 for r in self.chain_results.values() if r.fail_count == 0)

    @property
    def chains_failed(self) -> int:
        return sum(1 for r in self.chain_results.values() if r.fail_count > 0)

    @property
    def overall(self) -> str:
        if not self.chain_results:
            return "EMPTY"
        if self.all_passed:
            return "PASS"
        if self.chains_passed > 0:
            return "PARTIAL"
        return "FAIL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chains_tested": list(self.chain_results.keys()),
            "chains_passed": self.chains_passed,
            "chains_failed": self.chains_failed,
            "overall": self.overall,
            "total_elapsed_s": round(time.time() - self.start_time, 2),
            "per_chain": {net: r.to_dict() for net, r in self.chain_results.items()},
        }


# ---------------------------------------------------------------------------
# Multi-chain orchestrator
# ---------------------------------------------------------------------------
async def run_multichain_test(
    networks: List[str],
    bounty: float = DEFAULT_BOUNTY,
    live: bool = False,
    dry_run: bool = False,
) -> MultichainResults:
    """Run integration tests across multiple chains sequentially.

    Args:
        networks: List of chain names to test.
        bounty: Bounty amount in USD per chain.
        live: If True, creates real tasks on each chain.
        dry_run: If True, only show config.

    Returns:
        MultichainResults with per-chain outcomes.
    """
    total_cost = bounty * len(networks) if live else 0.0

    print("=" * 72)
    print("  KK V2 MULTI-CHAIN INTEGRATION TEST")
    print("=" * 72)
    _print_kv("Time", ts(), 2)
    _print_kv("Chains", ", ".join(networks), 2)
    _print_kv("Mode", "LIVE" if live else "MOCK", 2)
    _print_kv("Bounty/chain", f"${bounty:.2f}", 2)
    _print_kv("Total cost", f"${total_cost:.2f}" if live else "$0.00 (mock)", 2)

    if EXCLUDED_CHAINS:
        print("\n  Excluded chains (known SDK issues):")
        for chain, reason in EXCLUDED_CHAINS.items():
            print(f"    {chain}: {reason}")

    if dry_run:
        print("\nDRY RUN -- configuration shown above. Remove --dry-run to execute.")
        return MultichainResults()

    multi_results = MultichainResults()

    for i, network in enumerate(networks, 1):
        chain_info = SUPPORTED_CHAINS.get(network, {})
        chain_id = chain_info.get("chain_id", "?")
        display = chain_info.get("display_name", network)

        print()
        print(f"{'#' * 72}")
        print(f"  CHAIN {i}/{len(networks)}: {display} (chain_id={chain_id})")
        print(f"{'#' * 72}")

        try:
            chain_result = await run_integration_test(
                network=network,
                bounty=bounty,
                live=live,
                dry_run=False,
            )
            multi_results.add(network, chain_result)
        except Exception as e:
            # Create a failed result for this chain
            error_result = IntegrationResults(network)
            from test_integration import PhaseResult

            error_phase = PhaseResult("chain_error", f"Chain {network} error")
            error_phase.fail(f"Unhandled exception: {e}")
            error_result.add(error_phase)
            multi_results.add(network, error_result)
            print(f"\n  [ERROR] Chain {network} failed with exception: {e}")

        # Brief pause between chains to avoid rate limiting
        if i < len(networks):
            print(f"\n  Pausing 3s before next chain...")
            await asyncio.sleep(3)

    # Print multi-chain summary
    _print_multichain_summary(multi_results)

    # Save report
    _save_multichain_report(multi_results)

    return multi_results


def _print_multichain_summary(results: MultichainResults) -> None:
    """Print final multi-chain summary."""
    elapsed = round(time.time() - results.start_time, 2)

    print()
    _print_header("MULTI-CHAIN INTEGRATION SUMMARY")
    print(f"  Overall:    {results.overall}")
    print(
        f"  Chains:     {len(results.chain_results)} tested | "
        f"{results.chains_passed} passed | "
        f"{results.chains_failed} failed"
    )
    print(f"  Elapsed:    {elapsed}s")

    print("\n  Per-chain results:")
    for network, chain_result in results.chain_results.items():
        chain_info = SUPPORTED_CHAINS.get(network, {})
        display = chain_info.get("display_name", network)
        chain_id = chain_info.get("chain_id", "?")
        status = "PASS" if chain_result.fail_count == 0 else "FAIL"
        print(
            f"    [{status}] {display:12s} (chain {chain_id}) | "
            f"{chain_result.pass_count}P {chain_result.fail_count}F {chain_result.skip_count}S"
        )
        if chain_result.fail_count > 0:
            for p in chain_result.phases.values():
                if p.status == "FAIL":
                    print(f"           -> {p.name}: {p.error}")

    if results.overall == "PASS":
        print(
            f"\n  ** KK V2 MULTI-CHAIN: PASS ({results.chains_passed}/{len(results.chain_results)} chains) **"
        )
    elif results.overall == "PARTIAL":
        print(
            f"\n  ** KK V2 MULTI-CHAIN: PARTIAL "
            f"({results.chains_passed}/{len(results.chain_results)} chains passed) **"
        )
    else:
        print(f"\n  ** KK V2 MULTI-CHAIN: FAIL **")


def _save_multichain_report(results: MultichainResults) -> None:
    """Save JSON report to docs/reports/."""
    report_dir = _project_root / "docs" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / "KK_MULTICHAIN_INTEGRATION_REPORT.json"
    json_data = results.to_dict()
    json_path.write_text(json.dumps(json_data, indent=2, default=str), encoding="utf-8")
    print(f"\n  Report (JSON): {json_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
async def main() -> int:
    bounty = DEFAULT_BOUNTY
    dry_run = "--dry-run" in sys.argv
    live = "--live" in sys.argv
    run_all = "--all" in sys.argv

    # Parse --bounty
    for i, arg in enumerate(sys.argv):
        if arg == "--bounty" and i + 1 < len(sys.argv):
            try:
                bounty = float(sys.argv[i + 1])
            except ValueError:
                print(f"Invalid bounty: {sys.argv[i + 1]}")
                return 1

    # Parse --network (single chain override)
    network = None
    for i, arg in enumerate(sys.argv):
        if arg == "--network" and i + 1 < len(sys.argv):
            network = sys.argv[i + 1]

    # Determine chains to test
    if run_all:
        networks = list(SUPPORTED_CHAINS.keys())
    elif network:
        if network not in SUPPORTED_CHAINS:
            available = ", ".join(SUPPORTED_CHAINS.keys())
            print(f"Unknown network '{network}'. Available: {available}")
            if network in EXCLUDED_CHAINS:
                print(f"Note: '{network}' is excluded: {EXCLUDED_CHAINS[network]}")
            return 1
        networks = [network]
    else:
        networks = [DEFAULT_NETWORK]

    results = await run_multichain_test(
        networks=networks, bounty=bounty, live=live, dry_run=dry_run
    )

    if dry_run:
        return 0
    return 0 if results.chains_failed == 0 else 1


# ---------------------------------------------------------------------------
# Pytest integration
# ---------------------------------------------------------------------------
try:
    import pytest

    @pytest.fixture
    def event_loop():
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.mark.asyncio
    async def test_multichain_base_mock():
        """Run multi-chain integration on Base in mock mode (free)."""
        results = await run_multichain_test(networks=["base"], bounty=0.10, live=False)
        assert results.chains_failed == 0, f"Base integration failed: " + str(
            {
                net: [
                    f"{p.name}: {p.error}"
                    for p in r.phases.values()
                    if p.status == "FAIL"
                ]
                for net, r in results.chain_results.items()
            }
        )

    @pytest.mark.asyncio
    async def test_multichain_all_mock():
        """Run multi-chain integration on all 4 chains in mock mode (free)."""
        results = await run_multichain_test(
            networks=list(SUPPORTED_CHAINS.keys()), bounty=0.10, live=False
        )
        assert results.chains_failed == 0, (
            f"Multi-chain integration failed ({results.chains_failed} chains): "
            + str(
                {
                    net: [
                        f"{p.name}: {p.error}"
                        for p in r.phases.values()
                        if p.status == "FAIL"
                    ]
                    for net, r in results.chain_results.items()
                    if r.fail_count > 0
                }
            )
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("network", list(SUPPORTED_CHAINS.keys()))
    async def test_multichain_per_chain_mock(network: str):
        """Parameterized: run integration test per chain in mock mode."""
        results = await run_multichain_test(networks=[network], bounty=0.10, live=False)
        chain_result = results.chain_results.get(network)
        assert chain_result is not None, f"No results for {network}"
        assert chain_result.fail_count == 0, (
            f"{network} integration failed: "
            + ", ".join(
                f"{p.name}: {p.error}"
                for p in chain_result.phases.values()
                if p.status == "FAIL"
            )
        )

except ImportError:
    # pytest not installed -- standalone mode only
    pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
