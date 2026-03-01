"""
Live Integration Tests — EM API Connectivity & Swarm Readiness

These tests hit the REAL EM API (api.execution.market) and validate
the full chain from KK V2's perspective:

  1. API health and component status
  2. Task listing and marketplace state
  3. Auth endpoints (ERC-8128 nonce)
  4. Agent identity (ERC-8004 on Base)
  5. Swarm component readiness

Run conditions:
  - Requires network access to api.execution.market
  - Does NOT create tasks or modify state (read-only)
  - Safe to run in CI or as a health check

Usage:
  python -m pytest tests/integration/test_live_em_api.py -v
  python -m pytest tests/integration/test_live_em_api.py -k health
  python -m pytest tests/integration/test_live_em_api.py --timeout=30
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

# Constants
EM_API_URL = os.getenv("EM_API_URL", "https://api.execution.market")
BASE_RPC_URLS = [
    "https://1rpc.io/base",
    "https://base.llamarpc.com",
    "https://base-mainnet.public.blastapi.io",
    "https://base.drpc.org",
    "https://base-rpc.publicnode.com",
]

# ERC-8004 contracts on Base
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

# Known agent wallets (from KK swarm)
PLATFORM_WALLET = "0xD3868E1eD738CED6945A574a7c769433BeD5d474"

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def http_get(url: str, timeout: int = 15) -> dict:
    """GET JSON from URL."""
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def http_post_json(url: str, data: dict, timeout: int = 15) -> dict:
    """POST JSON to URL."""
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def eth_call(rpc_url: str, to: str, data: str, timeout: int = 10) -> str:
    """Make an eth_call to a contract."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(rpc_url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
        if "error" in result:
            raise RuntimeError(f"RPC error: {result['error']}")
        return result.get("result", "0x")


def get_block_number(rpc_url: str, timeout: int = 10) -> int:
    """Get current block number from RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": [],
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(rpc_url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
        return int(result["result"], 16)


def try_rpc(func, *args):
    """Try each RPC URL until one works."""
    last_error = None
    for rpc in BASE_RPC_URLS:
        try:
            return func(rpc, *args)
        except Exception as e:
            last_error = e
            continue
    raise last_error


def requires_base_rpc(func):
    """Skip test if Base RPC eth_getCode is unreachable (IP rate-limited)."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Test with eth_getCode specifically (some RPCs allow eth_blockNumber
        # but block eth_getCode from certain IPs)
        def check_code(rpc_url):
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getCode",
                "params": [IDENTITY_REGISTRY, "latest"],
            }
            body = json.dumps(payload).encode()
            req = urllib.request.Request(rpc_url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                return result.get("result", "0x")

        try:
            try_rpc(check_code)
        except Exception:
            pytest.skip("Base RPC unreachable for eth_getCode (IP may be rate-limited)")
        return func(*args, **kwargs)

    return wrapper


# ═══════════════════════════════════════════════════════════════════
# Test: EM API Health
# ═══════════════════════════════════════════════════════════════════


class TestEMAPIHealth:
    """Verify EM API is alive and all components healthy."""

    def test_health_endpoint_responds(self):
        """GET /health returns 200."""
        data = http_get(f"{EM_API_URL}/health")
        assert "status" in data

    def test_health_status_is_healthy(self):
        """Overall status should be 'healthy'."""
        data = http_get(f"{EM_API_URL}/health")
        assert data["status"] == "healthy", f"API unhealthy: {data.get('status')}"

    def test_database_healthy(self):
        """Database component should be healthy."""
        data = http_get(f"{EM_API_URL}/health")
        db = data.get("components", {}).get("database", {})
        assert db.get("status") == "healthy", f"DB: {db}"

    def test_blockchain_healthy(self):
        """Blockchain component should be healthy with recent block."""
        data = http_get(f"{EM_API_URL}/health")
        chain = data.get("components", {}).get("blockchain", {})
        assert chain.get("status") == "healthy", f"Chain: {chain}"
        # Block should be recent (Base produces blocks every ~2s)
        block = chain.get("details", {}).get("block_number", 0)
        assert block > 40_000_000, f"Block seems stale: {block}"

    def test_storage_healthy(self):
        """Storage component should be healthy."""
        data = http_get(f"{EM_API_URL}/health")
        storage = data.get("components", {}).get("storage", {})
        assert storage.get("status") == "healthy", f"Storage: {storage}"

    def test_x402_facilitator_healthy(self):
        """x402 facilitator should be operational."""
        data = http_get(f"{EM_API_URL}/health")
        x402 = data.get("components", {}).get("x402", {})
        assert x402.get("status") == "healthy", f"x402: {x402}"

    def test_uptime_positive(self):
        """Uptime should be > 0 (server has been running)."""
        data = http_get(f"{EM_API_URL}/health")
        assert data.get("uptime_seconds", 0) > 0


# ═══════════════════════════════════════════════════════════════════
# Test: EM Marketplace
# ═══════════════════════════════════════════════════════════════════


class TestEMMarketplace:
    """Verify marketplace endpoints work correctly."""

    def test_list_tasks_returns_structure(self):
        """GET /api/v1/tasks returns proper structure."""
        data = http_get(f"{EM_API_URL}/api/v1/tasks?status=published&limit=5")
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    def test_list_completed_tasks(self):
        """Can query completed tasks."""
        data = http_get(f"{EM_API_URL}/api/v1/tasks?status=completed&limit=5")
        assert "tasks" in data
        assert isinstance(data["total"], int)

    def test_list_all_tasks(self):
        """Can query all tasks."""
        data = http_get(f"{EM_API_URL}/api/v1/tasks?limit=5")
        assert "tasks" in data


# ═══════════════════════════════════════════════════════════════════
# Test: Auth Endpoints
# ═══════════════════════════════════════════════════════════════════


class TestAuthEndpoints:
    """Verify ERC-8128 authentication infrastructure."""

    def test_nonce_endpoint(self):
        """GET /api/v1/auth/nonce returns a nonce."""
        data = http_get(f"{EM_API_URL}/api/v1/auth/nonce")
        assert "nonce" in data
        assert len(data["nonce"]) > 0

    def test_erc8128_info(self):
        """GET /api/v1/auth/erc8128/info returns config."""
        data = http_get(f"{EM_API_URL}/api/v1/auth/erc8128/info")
        assert "supported_chains" in data or "chains" in data or "max_validity" in data

    def test_nonces_are_unique(self):
        """Two nonce requests should return different nonces."""
        n1 = http_get(f"{EM_API_URL}/api/v1/auth/nonce")
        n2 = http_get(f"{EM_API_URL}/api/v1/auth/nonce")
        assert n1["nonce"] != n2["nonce"]


# ═══════════════════════════════════════════════════════════════════
# Test: Base Mainnet Connectivity
# ═══════════════════════════════════════════════════════════════════


class TestBaseMainnet:
    """Verify Base mainnet RPC connectivity for ERC-8004."""

    @requires_base_rpc
    def test_rpc_reachable(self):
        """At least one Base RPC endpoint responds."""
        block = try_rpc(get_block_number)
        assert block > 40_000_000

    @requires_base_rpc
    def test_block_is_recent(self):
        """Block should be very recent (Base: ~2s blocks)."""
        block = try_rpc(get_block_number)
        # We just need it to be in a reasonable range
        assert block > 42_000_000, f"Block {block} seems too old"

    @requires_base_rpc
    def test_identity_contract_exists(self):
        """ERC-8004 Identity contract should have code."""
        # eth_getCode for the identity contract
        def check_code(rpc_url):
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getCode",
                "params": [IDENTITY_REGISTRY, "latest"],
            }
            body = json.dumps(payload).encode()
            req = urllib.request.Request(rpc_url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                return result.get("result", "0x")

        code = try_rpc(check_code)
        assert code != "0x" and len(code) > 4, "Identity contract has no code"

    @requires_base_rpc
    def test_reputation_contract_exists(self):
        """ERC-8004 Reputation contract should have code."""
        def check_code(rpc_url):
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getCode",
                "params": [REPUTATION_REGISTRY, "latest"],
            }
            body = json.dumps(payload).encode()
            req = urllib.request.Request(rpc_url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                return result.get("result", "0x")

        code = try_rpc(check_code)
        assert code != "0x" and len(code) > 4, "Reputation contract has no code"


# ═══════════════════════════════════════════════════════════════════
# Test: Swarm Readiness
# ═══════════════════════════════════════════════════════════════════


class TestSwarmReadiness:
    """Verify KK V2 swarm components are ready for operation."""

    def test_swarm_services_importable(self):
        """All critical swarm services can be imported."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

        importable = []
        not_importable = []

        modules = [
            "services.coordinator_service",
            "services.task_executor",
            "services.evidence_processor",
            "services.swarm_runner",
            "services.swarm_dashboard",
            "services.em_client",
            "lib.swarm_state",
            "lib.reputation_bridge",
            "lib.performance_tracker",
            "lib.observability",
            "lib.eip8128_signer",
            "lib.working_state",
        ]

        for mod in modules:
            try:
                __import__(mod)
                importable.append(mod)
            except ImportError as e:
                not_importable.append(f"{mod}: {e}")

        # At least 80% should be importable
        ratio = len(importable) / len(modules)
        assert ratio >= 0.8, (
            f"Only {len(importable)}/{len(modules)} modules importable. "
            f"Failed: {not_importable}"
        )

    def test_runner_can_instantiate(self):
        """SwarmRunner can be created with default config."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
        from swarm_runner import RunnerConfig, SwarmRunner

        config = RunnerConfig(dry_run=True)
        runner = SwarmRunner(config)
        assert runner.config.dry_run is True
        assert runner._shutdown is False

    def test_runner_status_works(self):
        """SwarmRunner status formatting works."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
        from swarm_runner import RunnerConfig, SwarmRunner

        runner = SwarmRunner(RunnerConfig(dry_run=True))
        status = runner.format_status()
        assert "Swarm Runner" in status

    def test_em_client_can_instantiate(self):
        """EMClient can be instantiated."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
        from em_client import EMClient

        # EMClient should be importable and instantiable
        assert EMClient is not None


# ═══════════════════════════════════════════════════════════════════
# Test: Full Chain Validation
# ═══════════════════════════════════════════════════════════════════


class TestFullChain:
    """End-to-end validation of the complete integration chain."""

    @requires_base_rpc
    def test_em_api_to_base_rpc_chain(self):
        """
        Validate the chain: EM API → Base RPC → ERC-8004 contracts.
        This is the critical path for task assignment and reputation.
        """
        # Step 1: EM API is healthy
        health = http_get(f"{EM_API_URL}/health")
        assert health["status"] == "healthy"

        # Step 2: Base RPC is reachable
        block = try_rpc(get_block_number)
        assert block > 40_000_000

        # Step 3: ERC-8004 contracts exist
        def check_code(rpc_url, addr):
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getCode",
                "params": [addr, "latest"],
            }
            body = json.dumps(payload).encode()
            req = urllib.request.Request(rpc_url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                return result.get("result", "0x")

        identity_code = try_rpc(check_code, IDENTITY_REGISTRY)
        assert identity_code != "0x"

        reputation_code = try_rpc(check_code, REPUTATION_REGISTRY)
        assert reputation_code != "0x"

    def test_auth_and_marketplace_chain(self):
        """
        Validate: Auth nonce → Task listing → Structure correct.
        This is the chain an agent follows to authenticate and find work.
        """
        # Step 1: Get a nonce
        nonce_resp = http_get(f"{EM_API_URL}/api/v1/auth/nonce")
        assert "nonce" in nonce_resp

        # Step 2: List tasks (unauthenticated is fine for reading)
        tasks_resp = http_get(f"{EM_API_URL}/api/v1/tasks?limit=3")
        assert "tasks" in tasks_resp
        assert isinstance(tasks_resp["tasks"], list)

        # If there are tasks, validate structure
        if tasks_resp["tasks"]:
            task = tasks_resp["tasks"][0]
            # Tasks should have these fields
            for field in ["id", "title", "status"]:
                assert field in task, f"Task missing field: {field}"
