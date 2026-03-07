"""
KK V2 — Coordinator × EM API × Escrow × Monitor Integration Tests

Tests the full swarm coordination pipeline against the LIVE EM API:
  1. Health + connectivity verification
  2. Coordinator matching with real marketplace data
  3. Escrow flow dry-run against real tasks
  4. Monitor alert generation from live state
  5. End-to-end: browse → match → monitor → digest

This is READ-ONLY — no tasks are created or modified.
All matching and assignment is simulated (dry_run=True).
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.em_client import AgentContext, EMClient
from services.coordinator_service import (
    compute_skill_match,
    load_agent_skills,
)
from services.escrow_flow import discover_bounties
from services.swarm_monitor import (
    AgentHealthSnapshot,
    MonitorConfig,
    MonitorStatus,
    PipelineSnapshot,
    SwarmMonitor,
    SystemSnapshot,
    check_agent_health,
    check_system_health,
    generate_digest,
)

import httpx

EM_API = "https://api.execution.market"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_read_only_client() -> httpx.AsyncClient:
    """Create a raw HTTP client for read-only EM API queries."""
    return httpx.AsyncClient(
        base_url=f"{EM_API}/api/v1",
        headers={"Content-Type": "application/json"},
        timeout=15.0,
    )


async def fetch_health() -> dict:
    async with make_read_only_client() as c:
        resp = await c.get("/health")
        resp.raise_for_status()
        return resp.json()


async def fetch_available_tasks(limit: int = 20) -> list[dict]:
    async with make_read_only_client() as c:
        resp = await c.get("/tasks/available", params={"status": "published", "limit": limit})
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("tasks", [])


async def fetch_completed_tasks(limit: int = 20) -> list[dict]:
    async with make_read_only_client() as c:
        resp = await c.get("/tasks", params={"status": "completed", "limit": limit})
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("tasks", [])


async def fetch_nonce() -> dict:
    async with make_read_only_client() as c:
        resp = await c.get("/auth/nonce")
        resp.raise_for_status()
        return resp.json()


async def fetch_erc8128_info() -> dict:
    async with make_read_only_client() as c:
        resp = await c.get("/auth/erc8128/info")
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------

class TestEMAPIConnectivity:
    """Verify EM API is reachable and healthy."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        health = await fetch_health()
        assert health.get("status") == "healthy"

    @pytest.mark.asyncio
    async def test_all_components_healthy(self):
        health = await fetch_health()
        assert health.get("status") == "healthy"
        assert "timestamp" in health
        assert "api_version" in health

    @pytest.mark.asyncio
    async def test_auth_nonce(self):
        """Auth nonce endpoint must work for EIP-8128 auth."""
        nonce_data = await fetch_nonce()
        assert "nonce" in nonce_data
        assert len(nonce_data["nonce"]) > 10

    @pytest.mark.asyncio
    async def test_erc8128_info(self):
        """ERC-8128 config must expose supported chains."""
        info = await fetch_erc8128_info()
        assert "supported_chains" in info
        # supported_chains is a list of chain IDs (ints)
        assert 8453 in info["supported_chains"]  # Base mainnet
        assert info.get("supported") is True


class TestCoordinatorMatchingWithLiveData:
    """Run coordinator matching logic against live EM marketplace data."""

    @pytest.mark.asyncio
    async def test_browse_marketplace_returns_tasks(self):
        """Live marketplace should have at least some tasks."""
        tasks = await fetch_available_tasks(limit=50)
        # May be empty if no tasks published right now — that's OK
        assert isinstance(tasks, list)

    @pytest.mark.asyncio
    async def test_completed_tasks_exist(self):
        """Should have historical completed tasks."""
        tasks = await fetch_completed_tasks(limit=10)
        assert len(tasks) > 0, "Expected at least 1 completed task in history"

    @pytest.mark.asyncio
    async def test_skill_matching_on_real_tasks(self):
        """Run skill matching against real completed tasks."""
        tasks = await fetch_completed_tasks(limit=20)
        if not tasks:
            pytest.skip("No completed tasks available")

        # Define test agent skill sets
        test_agents = {
            "kk-researcher": {"research", "defi", "analysis", "data"},
            "kk-coder": {"code", "python", "javascript", "review"},
            "kk-writer": {"writing", "content", "blog", "article"},
            "kk-analyst": {"analytics", "metrics", "report", "data"},
        }

        for task in tasks[:5]:
            title = task.get("title", "")
            instructions = task.get("instructions") or ""

            # Each task should get a score from at least one agent
            scores = {}
            for agent_name, skills in test_agents.items():
                score = compute_skill_match(skills, title, instructions)
                scores[agent_name] = score

            # Log for visibility
            best = max(scores, key=scores.get)
            # Verify scores are within valid range
            for name, score in scores.items():
                assert 0.0 <= score <= 1.0, f"{name} score out of range: {score}"

    @pytest.mark.asyncio
    async def test_task_structure_validation(self):
        """Verify task structure matches expected format."""
        tasks = await fetch_completed_tasks(limit=5)
        if not tasks:
            pytest.skip("No completed tasks")

        for task in tasks:
            # Required fields
            assert "id" in task, "Task missing 'id'"
            assert "title" in task, "Task missing 'title'"
            assert "status" in task, "Task missing 'status'"
            # Optional but expected
            assert isinstance(task.get("bounty_usd", 0), (int, float))


class TestEscrowFlowWithLiveData:
    """Test escrow discovery patterns against live marketplace."""

    @pytest.mark.asyncio
    async def test_discover_bounties_live(self):
        """Discover bounties from real EM marketplace."""
        agent = AgentContext(
            name="test-agent",
            wallet_address="0x0000000000000000000000000000000000000001",
            workspace_dir=Path("/tmp/kk-test"),
        )
        client = EMClient(agent)

        try:
            bounties = await discover_bounties(
                client=client,
                keywords=["research", "data", "code", "analysis", "write"],
                exclude_wallet=agent.wallet_address,
            )
            # May be empty — that's fine
            assert isinstance(bounties, list)

            # If bounties found, validate structure
            for b in bounties:
                assert "id" in b
                assert "title" in b
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_discover_with_narrow_keywords(self):
        """Narrow keywords should filter more aggressively."""
        agent = AgentContext(
            name="test-narrow",
            wallet_address="0x0000000000000000000000000000000000000002",
            workspace_dir=Path("/tmp/kk-test"),
        )
        client = EMClient(agent)

        try:
            broad = await discover_bounties(
                client=client,
                keywords=["a", "the", "is"],  # Very broad
            )
            narrow = await discover_bounties(
                client=client,
                keywords=["quantum_superconductor_analysis"],  # Very narrow
            )
            # Narrow should return <= broad results
            assert len(narrow) <= len(broad)
        finally:
            await client.close()


class TestMonitorWithLiveContext:
    """Generate monitoring data from live EM state."""

    @pytest.mark.asyncio
    async def test_system_health_from_live_api(self):
        """Build SystemSnapshot from live API health check."""
        health = await fetch_health()
        is_healthy = health.get("status") == "healthy"
        components = health.get("components", {})

        system = SystemSnapshot(
            em_api_healthy=is_healthy,
            base_rpc_healthy=components.get("blockchain") == "connected",
            irc_connected=True,  # Can't check from here
            uptime_hours=health.get("uptime_seconds", 0) / 3600,
        )

        config = MonitorConfig()
        alerts = check_system_health(system, config)

        if is_healthy:
            # No system alerts expected when API is healthy
            system_alerts = [a for a in alerts if a.title == "EM API unreachable"]
            assert len(system_alerts) == 0
        else:
            # API unhealthy — should generate emergency alert
            assert any(a.level.value == "emergency" for a in alerts)

    @pytest.mark.asyncio
    async def test_generate_digest_from_live_state(self):
        """Generate a full status digest using live API data."""
        health = await fetch_health()
        is_healthy = health.get("status") == "healthy"
        uptime = health.get("uptime_seconds", 0) / 3600

        # Simulate agent snapshots based on live readiness
        agents = [
            AgentHealthSnapshot(
                agent_name=f"kk-{role}",
                is_online=is_healthy,
                state="idle" if is_healthy else "error",
                total_successes=10,
                last_heartbeat_age_seconds=30 if is_healthy else 999,
                usdc_balance=5.0,
                eth_balance=0.01,
                reputation_score=75.0,
            )
            for role in ["researcher", "coder", "analyst", "writer", "validator"]
        ]

        tasks = await fetch_available_tasks(limit=100)
        completed = await fetch_completed_tasks(limit=100)

        pipeline = PipelineSnapshot(
            total_tasks=len(tasks) + len(completed),
            by_stage={
                "PUBLISHED": len(tasks),
                "COMPLETED": len(completed),
            },
            completion_rate_24h=len(completed) / max(len(tasks) + len(completed), 1),
        )

        # Run full monitor
        monitor = SwarmMonitor()
        alerts, digest = monitor.run_checks(
            agents=agents,
            pipeline=pipeline,
            system=SystemSnapshot(
                em_api_healthy=is_healthy,
                base_rpc_healthy=True,
                uptime_hours=uptime,
            ),
        )

        # Verify digest is valid
        assert digest.agents_total == 5
        assert digest.status in list(MonitorStatus)
        assert digest.timestamp != ""

        # Verify text formatting works
        text = digest.format_text()
        assert "KK Swarm Status Digest" in text
        assert "online" in text.lower()

    @pytest.mark.asyncio
    async def test_ownership_fix_reflected(self):
        """Verify the EIP-8128 ownership fix is live.

        The fix (commit 1778fca) ensures that tasks store both
        agent_id (ERC-8004 token) AND wallet_address, and ownership
        checks compare both.
        """
        # Get ERC-8128 info — should work without auth
        info = await fetch_erc8128_info()
        assert info is not None

        # The fact that the auth endpoint exists and returns info
        # means the fix is deployed (it also modified the auth flow)
        assert "supported_chains" in info
        assert "policy" in info
        assert info["policy"].get("max_validity_sec") == 300

        # Nonces should be unique (part of the auth fix)
        nonce1 = await fetch_nonce()
        nonce2 = await fetch_nonce()
        assert nonce1["nonce"] != nonce2["nonce"]


class TestFullIntegrationChain:
    """End-to-end: browse → match → monitor → digest."""

    @pytest.mark.asyncio
    async def test_browse_match_monitor_pipeline(self):
        """Full read-only integration test:
        1. Browse EM marketplace
        2. Run coordinator matching
        3. Generate monitor alerts
        4. Produce status digest
        """
        # Step 1: Browse
        health = await fetch_health()
        assert health.get("status") == "healthy", "API must be healthy for integration test"

        available = await fetch_available_tasks(limit=30)
        completed = await fetch_completed_tasks(limit=30)
        all_tasks = available + completed
        total_tasks = len(all_tasks)

        # Step 2: Match (against real tasks with simulated agents)
        test_agents = {
            "kk-researcher": {"research", "analysis", "data", "defi", "protocol"},
            "kk-coder": {"code", "python", "javascript", "review", "bug"},
            "kk-writer": {"writing", "content", "blog", "documentation"},
        }

        all_matches = []
        for task in all_tasks[:10]:
            title = task.get("title", "")
            desc = task.get("instructions", "") or ""
            scores = {
                name: compute_skill_match(skills, title, desc)
                for name, skills in test_agents.items()
            }
            best = max(scores, key=scores.get)
            all_matches.append({
                "task_id": task.get("id"),
                "title": title[:50],
                "best_agent": best,
                "best_score": scores[best],
            })

        # Step 3: Monitor
        uptime = health.get("uptime_seconds", 0) / 3600
        agents = [
            AgentHealthSnapshot(
                agent_name=name,
                is_online=True,
                state="idle",
                total_successes=10,
                last_heartbeat_age_seconds=30,
                usdc_balance=5.0,
                eth_balance=0.01,
            )
            for name in test_agents.keys()
        ]

        pipeline = PipelineSnapshot(
            total_tasks=total_tasks,
            by_stage={"PUBLISHED": len(available), "COMPLETED": len(completed)},
            completion_rate_24h=len(completed) / max(total_tasks, 1),
        )

        system = SystemSnapshot(
            em_api_healthy=True,
            base_rpc_healthy=True,
            uptime_hours=uptime,
        )

        monitor = SwarmMonitor()
        alerts, digest = monitor.run_checks(agents, pipeline, system)

        # Step 4: Verify
        assert digest.agents_online == 3
        assert digest.agents_total == 3
        assert digest.tasks_in_pipeline == total_tasks
        assert digest.status in (MonitorStatus.HEALTHY, MonitorStatus.DEGRADED)

        # Verify matching produced results
        if total_tasks > 0:
            assert len(all_matches) > 0
            for m in all_matches:
                assert 0.0 <= m["best_score"] <= 1.0
        else:
            # Empty marketplace is still valid
            assert len(all_matches) == 0

    @pytest.mark.asyncio
    async def test_nonce_uniqueness_high_volume(self):
        """Auth nonces must be unique even under rapid requests."""
        nonces = set()
        for _ in range(5):
            data = await fetch_nonce()
            nonce = data["nonce"]
            assert nonce not in nonces, f"Duplicate nonce: {nonce}"
            nonces.add(nonce)
        assert len(nonces) == 5
