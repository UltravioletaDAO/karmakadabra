#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 -- Agent-to-Agent Integration Test

Tests the COMPLETE agent-to-agent lifecycle on Execution Market:
  Health -> Register Workers -> Publish Task -> Apply -> Assign -> Submit -> Approve -> Reputation

Simulates 3 KK agents (A=publisher, B=worker, C=observer) collaborating
through the EM API, validating the full lifecycle that the KK swarm will execute.

Usage:
    python scripts/kk/tests/test_integration.py                  # Mock mode (free)
    python scripts/kk/tests/test_integration.py --live            # Live mode ($0.10)
    python scripts/kk/tests/test_integration.py --dry-run         # Config check only
    python scripts/kk/tests/test_integration.py --bounty 0.05     # Custom bounty

    pytest scripts/kk/tests/test_integration.py -v                # Run via pytest

Environment:
    EM_API_URL           -- API base (default: https://api.execution.market)
    EM_API_KEY           -- Agent API key (optional if EM_REQUIRE_API_KEY=false)
    EM_WORKER_WALLET     -- Worker wallet for Agent B (default: 0x52E0...)
    EM_TEST_EXECUTOR_ID  -- Existing executor UUID (skips registration)
    EM_WORKER_PRIVATE_KEY -- Worker private key (for on-chain reputation)

Cost:
    Mock mode: $0.00 (no on-chain transactions)
    Live mode: ~$0.10 per run (credit card model: fee deducted from bounty)
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment from project root
# ---------------------------------------------------------------------------
_script_dir = Path(__file__).parent
_project_root = _script_dir.parent.parent.parent
load_dotenv(_project_root / "mcp_server" / ".env")
load_dotenv(_project_root / ".env.local")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = os.environ.get("EM_API_URL", "https://api.execution.market").rstrip("/")
API_KEY = os.environ.get("EM_API_KEY", "")

WORKER_WALLET = os.environ.get(
    "EM_WORKER_WALLET", "0x52E05C8e45a32eeE169639F6d2cA40f8887b5A15"
)
EXISTING_EXECUTOR_ID = os.environ.get("EM_TEST_EXECUTOR_ID", "")

DEFAULT_BOUNTY = 0.10
PLATFORM_FEE_PCT = Decimal("0.13")
WORKER_PCT = Decimal("0.87")
EM_AGENT_ID = 2106

# Agent personas for the integration test
AGENT_A_NAME = "KK-Agent-Alpha"
AGENT_B_NAME = "KK-Agent-Bravo"
AGENT_C_NAME = "KK-Agent-Charlie"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def ts_short() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")


def _icon(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _print_header(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def _print_kv(key: str, value: Any, indent: int = 4) -> None:
    prefix = " " * indent
    print(f"{prefix}{key}: {value}")


# ---------------------------------------------------------------------------
# Phase result collector (same pattern as golden_flow)
# ---------------------------------------------------------------------------
class PhaseResult:
    """Structured result for a single test phase."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = "PENDING"
        self.details: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.start_time = time.time()
        self.elapsed_s = 0.0

    def pass_(self, **kwargs: Any) -> "PhaseResult":
        self.status = "PASS"
        self.details.update(kwargs)
        self.elapsed_s = round(time.time() - self.start_time, 2)
        return self

    def fail(self, error: str, **kwargs: Any) -> "PhaseResult":
        self.status = "FAIL"
        self.error = error
        self.details.update(kwargs)
        self.elapsed_s = round(time.time() - self.start_time, 2)
        return self

    def skip(self, reason: str, **kwargs: Any) -> "PhaseResult":
        self.status = "SKIP"
        self.error = reason
        self.details.update(kwargs)
        self.elapsed_s = round(time.time() - self.start_time, 2)
        return self

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "elapsed_s": self.elapsed_s,
        }
        if self.error:
            d["error"] = self.error
        d.update(self.details)
        return d

    def print_result(self) -> None:
        icon = _icon(self.status == "PASS")
        if self.status == "SKIP":
            icon = "SKIP"
        print(f"  [{icon}] Phase: {self.description} ({self.elapsed_s}s)")
        if self.error:
            print(f"         Note: {self.error}")


class IntegrationResults:
    """Collects all phase results for the integration test."""

    def __init__(self, network: str = "base"):
        self.network = network
        self.phases: Dict[str, PhaseResult] = {}
        self.start_time = time.time()

    def add(self, result: PhaseResult) -> None:
        self.phases[result.name] = result
        result.print_result()

    @property
    def all_passed(self) -> bool:
        return all(
            p.status in ("PASS", "SKIP") for p in self.phases.values()
        )

    @property
    def pass_count(self) -> int:
        return sum(1 for p in self.phases.values() if p.status == "PASS")

    @property
    def fail_count(self) -> int:
        return sum(1 for p in self.phases.values() if p.status == "FAIL")

    @property
    def skip_count(self) -> int:
        return sum(1 for p in self.phases.values() if p.status == "SKIP")

    @property
    def overall(self) -> str:
        if self.all_passed:
            return "PASS"
        return "FAIL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "network": self.network,
            "api_base": API_BASE,
            "phases": {name: phase.to_dict() for name, phase in self.phases.items()},
            "overall": self.overall,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "skip_count": self.skip_count,
            "total_elapsed_s": round(time.time() - self.start_time, 2),
        }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _auth_headers() -> Dict[str, str]:
    """Build authentication headers."""
    headers: Dict[str, str] = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
        headers["X-API-Key"] = API_KEY
    return headers


async def api_call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_data: Optional[dict] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> dict:
    """Call /api/v1/* endpoint with auth headers."""
    url = f"{API_BASE}/api/v1{path}"
    headers = _auth_headers()
    if extra_headers:
        headers.update(extra_headers)
    resp = await client.request(method, url, json=json_data, headers=headers)
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text, "status_code": resp.status_code}
    data["_http_status"] = resp.status_code
    return data


async def raw_get(client: httpx.AsyncClient, path: str) -> dict:
    """GET a path relative to API_BASE (not under /api/v1/)."""
    url = f"{API_BASE}{path}"
    resp = await client.request("GET", url)
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    data["_http_status"] = resp.status_code
    return data


# ---------------------------------------------------------------------------
# Phase 1: Health Check
# ---------------------------------------------------------------------------
async def phase_health(
    client: httpx.AsyncClient,
    results: IntegrationResults,
) -> PhaseResult:
    """Phase 1: Verify API is reachable and healthy."""
    phase = PhaseResult("health", "API Health Check")
    _print_header("PHASE 1: HEALTH CHECK")

    try:
        print("  [1/2] Checking health endpoint...")
        health = await raw_get(client, "/health/")
        h_status = health.get("_http_status")
        print(f"         Health: HTTP {h_status}")
        print(f"         Status: {health.get('status', 'N/A')}")

        if h_status != 200:
            return phase.fail(f"Health endpoint returned HTTP {h_status}")

        print("  [2/2] Checking config endpoint...")
        config = await api_call(client, "GET", "/config")
        c_status = config.get("_http_status")
        networks = config.get("supported_networks", [])
        print(f"         Config: HTTP {c_status}")
        print(f"         Networks: {networks}")

        if c_status != 200:
            return phase.fail(f"Config endpoint returned HTTP {c_status}")

        return phase.pass_(
            health_status=health.get("status"),
            supported_networks=networks,
        )

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Phase 2: Worker Registration (Agent B registers as worker)
# ---------------------------------------------------------------------------
async def phase_worker_registration(
    client: httpx.AsyncClient,
    results: IntegrationResults,
) -> PhaseResult:
    """Phase 2: Register Agent B as a worker on EM."""
    phase = PhaseResult("worker_registration", "Agent B Worker Registration")
    _print_header("PHASE 2: WORKER REGISTRATION (Agent B)")

    executor_id = EXISTING_EXECUTOR_ID

    try:
        if executor_id:
            print(f"  [1/1] Using existing executor: {executor_id}")
        else:
            print(f"  [1/1] Registering {AGENT_B_NAME} as worker...")
            url = f"{API_BASE}/api/v1/executors/register"
            resp = await client.post(
                url,
                json={
                    "wallet_address": WORKER_WALLET,
                    "display_name": f"{AGENT_B_NAME} (KK Integration Test)",
                },
                headers=_auth_headers(),
            )
            try:
                reg_data = resp.json()
            except Exception:
                reg_data = {"raw": resp.text}
            reg_data["_http_status"] = resp.status_code

            reg_status = reg_data.get("_http_status")
            print(f"         Register: HTTP {reg_status}")

            if reg_status not in (200, 201):
                err = reg_data.get("detail", str(reg_data)[:200])
                return phase.fail(f"Worker registration failed: {err}")

            executor_obj = reg_data.get("executor", {})
            executor_id = executor_obj.get("id", "")
            created = reg_data.get("created", False)
            print(f"         Executor ID: {executor_id}")
            print(f"         Created new: {created}")

        if not executor_id:
            return phase.fail("No executor ID obtained")

        return phase.pass_(executor_id=executor_id)

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Phase 3: Task Browsing (Agent C browses available tasks, free operation)
# ---------------------------------------------------------------------------
async def phase_task_browsing(
    client: httpx.AsyncClient,
    results: IntegrationResults,
) -> PhaseResult:
    """Phase 3: Agent C browses available tasks (observer role, free)."""
    phase = PhaseResult("task_browsing", "Agent C Browses Tasks")
    _print_header("PHASE 3: TASK BROWSING (Agent C, observer)")

    try:
        print("  [1/2] Browsing available tasks...")
        browse_data = await api_call(
            client, "GET", "/tasks/available?status=published&limit=5"
        )
        b_status = browse_data.get("_http_status")
        print(f"         Browse: HTTP {b_status}")

        if b_status != 200:
            return phase.fail(f"Browse endpoint returned HTTP {b_status}")

        tasks = browse_data.get("tasks", [])
        if isinstance(browse_data, list):
            tasks = browse_data
        task_count = len(tasks)
        print(f"         Available tasks: {task_count}")

        print("  [2/2] Checking ERC-8004 identity info...")
        rep_data = await api_call(client, "GET", "/reputation/info")
        r_status = rep_data.get("_http_status")
        agent_id = rep_data.get("em_agent_id", "N/A")
        print(f"         Reputation info: HTTP {r_status}")
        print(f"         EM Agent ID: {agent_id}")

        return phase.pass_(
            available_tasks=task_count,
            em_agent_id=agent_id,
        )

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Phase 4: Task Publication (Agent A publishes task -- costs USDC in live mode)
# ---------------------------------------------------------------------------
async def phase_task_publication(
    client: httpx.AsyncClient,
    results: IntegrationResults,
    bounty: float,
    network: str = "base",
    live: bool = False,
) -> PhaseResult:
    """Phase 4: Agent A publishes a task. Skipped in mock mode."""
    phase = PhaseResult("task_publication", f"Agent A Publishes Task (${bounty}, {network})")
    _print_header(f"PHASE 4: TASK PUBLICATION (Agent A, {'LIVE' if live else 'MOCK'})")

    if not live:
        print("  [SKIP] Mock mode -- task publication skipped (costs USDC)")
        return phase.skip("Mock mode: task publication skipped to avoid spending USDC")

    try:
        print(f"  [1/1] Publishing task on {network} (${bounty} bounty)...")
        task_data = await api_call(
            client,
            "POST",
            "/tasks",
            {
                "title": f"[KK-INTEG] {AGENT_A_NAME} test - {ts_short()}",
                "instructions": (
                    f"Integration test task from {AGENT_A_NAME}. "
                    "Respond with: kk_integration_complete"
                ),
                "category": "simple_action",
                "bounty_usd": bounty,
                "deadline_hours": 1,
                "evidence_required": ["text_response"],
                "location_hint": "Any location",
                "payment_network": network,
                "payment_token": "USDC",
            },
        )

        http_status = task_data.get("_http_status")
        print(f"         HTTP status: {http_status}")

        if http_status != 201:
            err = task_data.get("detail", task_data.get("error", str(task_data)[:200]))
            return phase.fail(f"Task creation failed: HTTP {http_status} - {err}")

        task_id = task_data.get("id")
        task_status = task_data.get("status")
        print(f"         Task ID: {task_id}")
        print(f"         Status:  {task_status}")

        if task_status != "published":
            return phase.fail(
                f"Task status is '{task_status}', expected 'published'",
                task_id=task_id,
            )

        return phase.pass_(task_id=task_id, task_status=task_status)

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Phase 5: Task Lifecycle (Apply -> Assign -> Submit)
# ---------------------------------------------------------------------------
async def phase_task_lifecycle(
    client: httpx.AsyncClient,
    results: IntegrationResults,
    task_id: str,
    executor_id: str,
) -> PhaseResult:
    """Phase 5: Agent B applies, gets assigned, and submits evidence."""
    phase = PhaseResult("task_lifecycle", "Task Lifecycle (Apply -> Assign -> Submit)")
    _print_header("PHASE 5: TASK LIFECYCLE (Agent B)")
    print(f"    Task:     {task_id}")
    print(f"    Executor: {executor_id}")

    try:
        # Step 1: Agent B applies
        print(f"  [1/3] {AGENT_B_NAME} applying to task...")
        apply_data = await api_call(
            client,
            "POST",
            f"/tasks/{task_id}/apply",
            {
                "executor_id": executor_id,
                "message": f"{AGENT_B_NAME} ready to execute -- KK integration test",
            },
        )
        apply_status = apply_data.get("_http_status")
        print(f"         Apply: HTTP {apply_status}")

        if apply_status not in (200, 201):
            err = apply_data.get("detail", str(apply_data)[:200])
            return phase.fail(f"Apply failed: {err}")

        application_id = (apply_data.get("data") or {}).get("application_id")
        print(f"         Application ID: {application_id}")

        # Step 2: Agent A assigns Agent B (escrow lock happens here in direct_release)
        print(f"  [2/3] {AGENT_A_NAME} assigning {AGENT_B_NAME}...")
        assign_data = await api_call(
            client,
            "POST",
            f"/tasks/{task_id}/assign",
            {
                "executor_id": executor_id,
                "notes": "KK integration test assignment",
            },
        )
        assign_status = assign_data.get("_http_status")
        print(f"         Assign: HTTP {assign_status}")

        if assign_status not in (200, 201):
            err = assign_data.get("detail", str(assign_data)[:200])
            return phase.fail(f"Assign failed: {err}")

        # Extract escrow info
        assign_resp = assign_data.get("data") or {}
        escrow_info = assign_resp.get("escrow") or {}
        escrow_tx = escrow_info.get("escrow_tx")
        if escrow_tx:
            print(f"         Escrow TX: {escrow_tx}")

        # Step 3: Agent B submits evidence
        print(f"  [3/3] {AGENT_B_NAME} submitting evidence...")
        submit_data = await api_call(
            client,
            "POST",
            f"/tasks/{task_id}/submit",
            {
                "executor_id": executor_id,
                "evidence": {
                    "text_response": "kk_integration_complete",
                },
                "notes": f"Automated submission from {AGENT_B_NAME}",
            },
        )
        submit_status = submit_data.get("_http_status")
        print(f"         Submit: HTTP {submit_status}")

        if submit_status not in (200, 201):
            err = submit_data.get("detail", str(submit_data)[:200])
            return phase.fail(f"Submit failed: {err}")

        # Find submission ID
        submission_id = (submit_data.get("data") or {}).get("submission_id")
        if not submission_id:
            subs_data = await api_call(client, "GET", f"/tasks/{task_id}/submissions")
            subs_list = subs_data.get("submissions") or subs_data.get("data") or []
            if isinstance(subs_list, list) and subs_list:
                submission_id = subs_list[0].get("id")

        if not submission_id:
            return phase.fail("Could not find submission ID after submit")

        print(f"         Submission ID: {submission_id}")

        return phase.pass_(
            application_id=application_id,
            submission_id=submission_id,
            escrow_tx=escrow_tx,
        )

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Phase 6: Approval & Payment
# ---------------------------------------------------------------------------
async def phase_approval_payment(
    client: httpx.AsyncClient,
    results: IntegrationResults,
    submission_id: str,
    bounty: float,
) -> PhaseResult:
    """Phase 6: Agent A approves submission, payment settles."""
    phase = PhaseResult("approval_payment", "Agent A Approves + Payment")
    worker_net = float(Decimal(str(bounty)) * WORKER_PCT)
    fee = float(Decimal(str(bounty)) * PLATFORM_FEE_PCT)

    _print_header("PHASE 6: APPROVAL & PAYMENT (Agent A)")
    print(f"    Submission: {submission_id}")
    print(f"    Bounty:     ${bounty:.2f} (lock amount)")
    print(f"    Worker net: ${worker_net:.6f} (87%)")
    print(f"    Fee:        ${fee:.6f} (13%)")

    try:
        print("  [1/1] Approving submission...")
        t0 = time.time()
        approve_data = await api_call(
            client,
            "POST",
            f"/submissions/{submission_id}/approve",
            {
                "notes": f"{AGENT_A_NAME} approves -- KK integration test",
                "rating_score": 85,
            },
        )
        t_approve = time.time() - t0
        approve_status = approve_data.get("_http_status")
        print(f"         Approve: HTTP {approve_status} ({t_approve:.2f}s)")
        print(f"         Message: {approve_data.get('message', 'N/A')}")

        if approve_status != 200:
            err = approve_data.get(
                "detail", approve_data.get("error", str(approve_data)[:200])
            )
            return phase.fail(f"Approval failed: HTTP {approve_status} - {err}")

        resp_data = approve_data.get("data") or {}
        payment_tx = resp_data.get("payment_tx")
        payment_mode = resp_data.get("payment_mode", "unknown")
        worker_net_actual = resp_data.get("worker_net_usdc")
        platform_fee_actual = resp_data.get("platform_fee_usdc")

        if payment_tx:
            print(f"         Payment TX: {payment_tx}")
        if worker_net_actual is not None:
            print(f"         Worker net: ${worker_net_actual:.6f} (87%)")
        if platform_fee_actual is not None:
            print(f"         Fee:        ${platform_fee_actual:.6f} (13%)")
        print(f"         Mode:       {payment_mode}")

        return phase.pass_(
            payment_tx=payment_tx,
            payment_mode=payment_mode,
            worker_net_usdc=worker_net_actual,
            platform_fee_usdc=platform_fee_actual,
            approve_time_s=round(t_approve, 2),
        )

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Phase 7: Reputation (bidirectional rating)
# ---------------------------------------------------------------------------
async def phase_reputation(
    client: httpx.AsyncClient,
    results: IntegrationResults,
    task_id: str,
) -> PhaseResult:
    """Phase 7: Agent A rates Agent B (score 85), Agent B rates Agent A (score 90)."""
    phase = PhaseResult("reputation", "Bidirectional Reputation (A rates B, B rates A)")
    _print_header("PHASE 7: REPUTATION (Bidirectional)")

    try:
        # Step 1: Agent A rates Agent B (worker)
        print(f"  [1/2] {AGENT_A_NAME} rating {AGENT_B_NAME} (score: 85)...")
        rate_worker_data = await api_call(
            client,
            "POST",
            "/reputation/workers/rate",
            {
                "task_id": task_id,
                "score": 85,
                "comment": f"KK integration test -- {AGENT_A_NAME} rates {AGENT_B_NAME}",
            },
        )
        rw_status = rate_worker_data.get("_http_status")
        rw_success = rate_worker_data.get("success", False)
        rw_tx = rate_worker_data.get("transaction_hash")
        rw_error = rate_worker_data.get("error")
        print(f"         Rate worker: HTTP {rw_status}, success={rw_success}")
        if rw_tx:
            print(f"         TX: {rw_tx}")
        if rw_error:
            print(f"         Note: {rw_error}")

        # Step 2: Agent B rates Agent A (via prepare-feedback + confirm)
        print(f"  [2/2] {AGENT_B_NAME} rating {AGENT_A_NAME} (score: 90)...")
        prepare_data = await api_call(
            client,
            "POST",
            "/reputation/prepare-feedback",
            {
                "agent_id": EM_AGENT_ID,
                "task_id": task_id,
                "score": 90,
                "comment": f"KK integration test -- {AGENT_B_NAME} rates {AGENT_A_NAME}",
                "worker_address": WORKER_WALLET,
            },
        )
        prep_status = prepare_data.get("_http_status")
        print(f"         Prepare feedback: HTTP {prep_status}")

        ra_success = False
        ra_tx = None

        if prep_status == 200:
            prepare_id = prepare_data.get("prepare_id", "")
            print(f"         Prepare ID: {prepare_id[:24]}..." if prepare_id else "         Prepare ID: N/A")

            # Try on-chain signing if worker private key is available
            worker_private_key = os.environ.get("EM_WORKER_PRIVATE_KEY", "")
            if worker_private_key:
                try:
                    contract_address = prepare_data.get("contract_address", "")
                    chain_id = prepare_data.get("chain_id", 8453)
                    agent_id_param = prepare_data.get("agent_id", EM_AGENT_ID)
                    value_param = prepare_data.get("value", 90)
                    tag1 = prepare_data.get("tag1", "agent_rating")
                    tag2 = prepare_data.get("tag2", "execution-market")
                    endpoint_param = prepare_data.get(
                        "endpoint", f"task:{task_id}"
                    )
                    feedback_uri = prepare_data.get("feedback_uri", "")
                    feedback_hash = prepare_data.get(
                        "feedback_hash", "0x" + "00" * 32
                    )

                    from web3 import Web3

                    try:
                        from web3.middleware import ExtraDataToPOAMiddleware as _poa
                    except ImportError:
                        from web3.middleware import geth_poa_middleware as _poa

                    rpc_url = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
                    w3 = Web3(Web3.HTTPProvider(rpc_url))
                    try:
                        w3.middleware_onion.inject(_poa, layer=0)
                    except Exception:
                        pass

                    GIVE_FEEDBACK_ABI = [
                        {
                            "inputs": [
                                {"name": "agentId", "type": "uint256"},
                                {"name": "value", "type": "int128"},
                                {"name": "valueDecimals", "type": "uint8"},
                                {"name": "tag1", "type": "string"},
                                {"name": "tag2", "type": "string"},
                                {"name": "endpoint", "type": "string"},
                                {"name": "feedbackURI", "type": "string"},
                                {"name": "feedbackHash", "type": "bytes32"},
                            ],
                            "name": "giveFeedback",
                            "outputs": [],
                            "stateMutability": "nonpayable",
                            "type": "function",
                        }
                    ]

                    registry = w3.eth.contract(
                        address=Web3.to_checksum_address(contract_address),
                        abi=GIVE_FEEDBACK_ABI,
                    )

                    acct = w3.eth.account.from_key(worker_private_key)
                    nonce = w3.eth.get_transaction_count(acct.address, "pending")

                    if isinstance(feedback_hash, str):
                        fb_hash_bytes = bytes.fromhex(
                            feedback_hash.replace("0x", "").ljust(64, "0")
                        )
                    else:
                        fb_hash_bytes = feedback_hash

                    tx = registry.functions.giveFeedback(
                        agent_id_param,
                        value_param,
                        0,
                        tag1,
                        tag2,
                        endpoint_param,
                        feedback_uri,
                        fb_hash_bytes,
                    ).build_transaction(
                        {
                            "from": acct.address,
                            "nonce": nonce,
                            "gas": 250000,
                            "maxFeePerGas": w3.to_wei(0.5, "gwei"),
                            "maxPriorityFeePerGas": w3.to_wei(0.1, "gwei"),
                            "chainId": chain_id,
                        }
                    )

                    signed = acct.sign_transaction(tx)
                    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                    ra_tx = tx_hash.hex()
                    print(f"         TX sent: {ra_tx}")

                    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                    if receipt["status"] == 1:
                        print(f"         TX confirmed! Gas: {receipt['gasUsed']}")
                        ra_success = True
                    else:
                        print("         TX REVERTED")

                    # Confirm with API
                    if ra_success and ra_tx:
                        confirm_data = await api_call(
                            client,
                            "POST",
                            "/reputation/confirm-feedback",
                            {
                                "prepare_id": prepare_id,
                                "task_id": task_id,
                                "tx_hash": ra_tx,
                            },
                        )
                        cf_status = confirm_data.get("_http_status")
                        print(f"         Confirm: HTTP {cf_status}")

                except Exception as e:
                    print(f"         On-chain signing error: {e}")
            else:
                print("         EM_WORKER_PRIVATE_KEY not set -- skipping on-chain signing")

        # Both ratings attempted; agent->worker is sufficient for PASS
        if rw_status == 200 and rw_success:
            return phase.pass_(
                agent_rates_worker_tx=rw_tx,
                worker_rates_agent_tx=ra_tx,
                agent_rates_worker_success=rw_success,
                worker_rates_agent_success=ra_success,
            )
        else:
            return phase.fail(
                f"Agent->Worker rating failed: HTTP {rw_status}, success={rw_success}, error={rw_error}"
            )

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Phase 8: Reputation Verification
# ---------------------------------------------------------------------------
async def phase_reputation_verification(
    client: httpx.AsyncClient,
    results: IntegrationResults,
) -> PhaseResult:
    """Phase 8: Verify reputation scores are queryable."""
    phase = PhaseResult("reputation_verification", "Reputation Score Verification")
    _print_header("PHASE 8: REPUTATION VERIFICATION")

    try:
        print(f"  [1/1] Querying reputation for {WORKER_WALLET[:12]}...")
        rep_data = await api_call(
            client, "GET", f"/reputation/score/{WORKER_WALLET}"
        )
        r_status = rep_data.get("_http_status")
        print(f"         Reputation query: HTTP {r_status}")

        if r_status == 200:
            score = rep_data.get("score", rep_data.get("average_score", "N/A"))
            total = rep_data.get("total_ratings", rep_data.get("count", "N/A"))
            print(f"         Score: {score}")
            print(f"         Total ratings: {total}")
            return phase.pass_(score=score, total_ratings=total)
        elif r_status == 404:
            print("         No reputation data found (may be first test)")
            return phase.pass_(score=None, note="No reputation data yet")
        else:
            err = rep_data.get("detail", str(rep_data)[:200])
            return phase.fail(f"Reputation query failed: {err}")

    except Exception as e:
        return phase.fail(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
async def run_integration_test(
    network: str = "base",
    bounty: float = DEFAULT_BOUNTY,
    live: bool = False,
    dry_run: bool = False,
) -> IntegrationResults:
    """Run the full integration test.

    Args:
        network: Chain name (base, polygon, arbitrum, avalanche).
        bounty: Bounty amount in USD.
        live: If True, creates real tasks (costs USDC). If False, mock mode.
        dry_run: If True, only show config and exit.

    Returns:
        IntegrationResults with all phase outcomes.
    """
    worker_net = float(Decimal(str(bounty)) * WORKER_PCT)
    fee = float(Decimal(str(bounty)) * PLATFORM_FEE_PCT)

    print("=" * 72)
    print(f"  KK V2 INTEGRATION TEST ({network.upper()}, {'LIVE' if live else 'MOCK'})")
    print("=" * 72)
    _print_kv("API", API_BASE, 2)
    _print_kv("Time", ts(), 2)
    _print_kv("Network", network, 2)
    _print_kv("Mode", "LIVE (on-chain)" if live else "MOCK (free)", 2)
    _print_kv("Bounty", f"${bounty:.2f}", 2)
    _print_kv("Worker net (87%)", f"${worker_net:.6f}", 2)
    _print_kv("Fee (13%)", f"${fee:.6f}", 2)
    _print_kv("Worker wallet", WORKER_WALLET, 2)
    _print_kv("Auth", "API key set" if API_KEY else "Anonymous", 2)
    if EXISTING_EXECUTOR_ID:
        _print_kv("Executor", EXISTING_EXECUTOR_ID, 2)

    if dry_run:
        print("\nDRY RUN -- configuration shown above. Remove --dry-run to execute.")
        results = IntegrationResults(network)
        return results

    results = IntegrationResults(network)
    timeout = httpx.Timeout(180.0, connect=15.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Phase 1: Health
        p1 = await phase_health(client, results)
        results.add(p1)
        if p1.status == "FAIL":
            print("\n  [ABORT] Health check failed. Cannot continue.")
            return results

        # Phase 2: Worker Registration
        p2 = await phase_worker_registration(client, results)
        results.add(p2)
        executor_id = p2.details.get("executor_id") or EXISTING_EXECUTOR_ID
        if not executor_id:
            print("\n  [ABORT] No executor ID. Cannot continue.")
            return results

        await asyncio.sleep(1)

        # Phase 3: Task Browsing (Agent C, free)
        p3 = await phase_task_browsing(client, results)
        results.add(p3)

        await asyncio.sleep(1)

        # Phase 4: Task Publication (Agent A, costs USDC in live mode)
        p4 = await phase_task_publication(client, results, bounty, network, live)
        results.add(p4)

        task_id = p4.details.get("task_id")
        if not task_id and live:
            print("\n  [ABORT] No task ID (live mode). Cannot continue lifecycle.")
            return results

        # Phases 5-8 only run in live mode (require a real task)
        if not live or not task_id:
            print("\n  [INFO] Mock mode -- phases 5-8 skipped (no real task)")
            _skip_remaining_phases(results)
            _print_integration_summary(results)
            return results

        await asyncio.sleep(2)

        # Phase 5: Task Lifecycle (Apply -> Assign -> Submit)
        p5 = await phase_task_lifecycle(client, results, task_id, executor_id)
        results.add(p5)

        submission_id = p5.details.get("submission_id")
        if not submission_id:
            print("\n  [ABORT] No submission ID. Cannot continue.")
            _print_integration_summary(results)
            return results

        await asyncio.sleep(2)

        # Phase 6: Approval & Payment
        p6 = await phase_approval_payment(client, results, submission_id, bounty)
        results.add(p6)

        await asyncio.sleep(3)

        # Phase 7: Reputation
        p7 = await phase_reputation(client, results, task_id)
        results.add(p7)

        await asyncio.sleep(2)

        # Phase 8: Reputation Verification
        p8 = await phase_reputation_verification(client, results)
        results.add(p8)

    _print_integration_summary(results)
    return results


def _skip_remaining_phases(results: IntegrationResults) -> None:
    """Mark phases 5-8 as skipped in mock mode."""
    for name, desc in [
        ("task_lifecycle", "Task Lifecycle (Apply -> Assign -> Submit)"),
        ("approval_payment", "Agent A Approves + Payment"),
        ("reputation", "Bidirectional Reputation (A rates B, B rates A)"),
        ("reputation_verification", "Reputation Score Verification"),
    ]:
        phase = PhaseResult(name, desc)
        phase.skip("Mock mode: skipped (requires live task)")
        results.add(phase)


def _print_integration_summary(results: IntegrationResults) -> None:
    """Print final summary to console."""
    total = len(results.phases)
    elapsed = round(time.time() - results.start_time, 2)

    print()
    _print_header("KK V2 INTEGRATION TEST SUMMARY")
    print(f"  Network:  {results.network}")
    print(f"  Overall:  {results.overall}")
    print(
        f"  Phases:   {total} total | "
        f"{results.pass_count} passed | "
        f"{results.fail_count} failed | "
        f"{results.skip_count} skipped"
    )
    print(f"  Elapsed:  {elapsed}s")

    if results.overall == "PASS":
        print("\n  ** KK V2 INTEGRATION: PASS **")
    else:
        print("\n  ** KK V2 INTEGRATION: FAIL **")
        for p in results.phases.values():
            if p.status == "FAIL":
                print(f"     - {p.name}: {p.error}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
async def main() -> int:
    bounty = DEFAULT_BOUNTY
    dry_run = "--dry-run" in sys.argv
    live = "--live" in sys.argv
    network = "base"

    for i, arg in enumerate(sys.argv):
        if arg == "--bounty" and i + 1 < len(sys.argv):
            try:
                bounty = float(sys.argv[i + 1])
            except ValueError:
                print(f"Invalid bounty: {sys.argv[i + 1]}")
                return 1
        if arg == "--network" and i + 1 < len(sys.argv):
            network = sys.argv[i + 1]

    results = await run_integration_test(
        network=network, bounty=bounty, live=live, dry_run=dry_run
    )

    if dry_run:
        return 0
    return 0 if results.fail_count == 0 else 1


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
    async def test_kk_integration_mock():
        """Run KK integration test in mock mode (free, no USDC spent)."""
        results = await run_integration_test(
            network="base", bounty=0.10, live=False
        )
        # In mock mode, phases 5-8 are skipped, only 1-4 run
        assert results.fail_count == 0, (
            f"Integration test failed: {results.fail_count} failures. "
            + ", ".join(
                f"{p.name}: {p.error}"
                for p in results.phases.values()
                if p.status == "FAIL"
            )
        )

    @pytest.mark.asyncio
    async def test_kk_integration_health():
        """Verify API health check passes."""
        results = IntegrationResults("base")
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            p1 = await phase_health(client, results)
            results.add(p1)
        assert p1.status == "PASS", f"Health check failed: {p1.error}"

except ImportError:
    # pytest not installed -- standalone mode only
    pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
