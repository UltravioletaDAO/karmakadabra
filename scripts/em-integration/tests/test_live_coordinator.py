"""
Tests for SwarmLiveCoordinator — Live EM API Integration

Tests the coordinator's logic with mocked API responses 
matching the actual EM API shape from production.
"""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
# execution-market root (for mcp_server imports)
_em_root = str(Path(__file__).parent.parent.parent.parent)
if _em_root not in sys.path:
    sys.path.insert(0, _em_root)

from lib.swarm_live_coordinator import (
    SwarmLiveCoordinator,
    EMTaskView,
    _api_get,
)
from mcp_server.swarm import SwarmOrchestrator, LifecycleManager, ReputationBridge


# ── Sample API Responses (matching actual EM API) ──

SAMPLE_PUBLISHED_TASKS = [
    {
        "id": "ec8f4770-15c8-4e46-9250-3fe1e9248e66",
        "title": "[MULTICHAIN GF] Optimism - 20260221-1729",
        "status": "published",
        "category": "simple_action",
        "bounty_usd": 0.10,
        "deadline": "2026-02-22T18:29:59.262007Z",
        "created_at": "2026-02-21T17:29:59.324764Z",
        "agent_id": "2106",
        "erc8004_agent_id": "2106",
        "payment_network": "optimism",
        "payment_token": "USDC",
        "instructions": "Verify the Optimism transaction hash",
        "evidence_schema": None,
        "location_hint": None,
        "min_reputation": 0,
    },
    {
        "id": "b1234567-aaaa-bbbb-cccc-ddddeeeeffff",
        "title": "Photo Verify - 123 Main St",
        "status": "published",
        "category": "physical_verification",
        "bounty_usd": 0.50,
        "deadline": "2026-02-22T20:00:00Z",
        "created_at": "2026-02-22T15:00:00Z",
        "agent_id": "2106",
        "erc8004_agent_id": "2106",
        "payment_network": "base",
        "payment_token": "USDC",
        "instructions": "Take photo of storefront with GPS",
        "evidence_schema": ["photo_geo", "text_response"],
        "location_hint": "123 Main St, Denver CO",
        "min_reputation": 50,
    },
    {
        "id": "c9876543-1111-2222-3333-444455556666",
        "title": "Research: DeFi Protocols Comparison",
        "status": "published",
        "category": "research",
        "bounty_usd": 2.00,
        "deadline": "2026-02-25T00:00:00Z",
        "created_at": "2026-02-22T10:00:00Z",
        "agent_id": "2106",
        "erc8004_agent_id": "2106",
        "payment_network": "base",
        "payment_token": "USDC",
        "instructions": "Compare top 5 DeFi protocols on Base",
        "evidence_schema": ["text_response", "document"],
        "location_hint": None,
        "min_reputation": 0,
    },
]

SAMPLE_COMPLETED_TASKS = [
    {
        "id": "d1111111-aaaa-bbbb-cccc-111111111111",
        "title": "[MULTICHAIN GF] Base - completed",
        "status": "completed",
        "category": "simple_action",
        "bounty_usd": 0.10,
        "payment_network": "base",
        "payment_token": "USDC",
        "created_at": "2026-02-20T12:00:00Z",
        "agent_id": "2106",
        "instructions": None,
        "evidence_schema": None,
        "location_hint": None,
    },
    {
        "id": "d2222222-aaaa-bbbb-cccc-222222222222",
        "title": "[MULTICHAIN GF] Polygon - completed",
        "status": "completed",
        "category": "simple_action",
        "bounty_usd": 0.10,
        "payment_network": "polygon",
        "payment_token": "USDC",
        "created_at": "2026-02-20T14:00:00Z",
        "agent_id": "2106",
        "instructions": None,
        "evidence_schema": None,
        "location_hint": None,
    },
]

SAMPLE_HEALTH = {
    "status": "healthy",
    "overall": True,
    "components": {
        "api": True,
        "database": True,
        "blockchain": True,
    },
}


# ── Fixtures ──

@pytest.fixture
def mock_api():
    """Mock EM API calls."""
    def _mock_get(endpoint, params=None):
        params = params or {}
        if params.get("status") == "published":
            return SAMPLE_PUBLISHED_TASKS
        if params.get("status") == "completed":
            return SAMPLE_COMPLETED_TASKS
        if endpoint == "/health":
            return SAMPLE_HEALTH
        return {}
    
    with patch("lib.swarm_live_coordinator._api_get", side_effect=_mock_get):
        yield


@pytest.fixture
def orchestrator_with_agents():
    """SwarmOrchestrator with agents registered."""
    from mcp_server.swarm.lifecycle_manager import ResourceBudget
    
    lifecycle = LifecycleManager(max_agents=48)
    bridge = ReputationBridge(dry_run=True)
    orch = SwarmOrchestrator(lifecycle=lifecycle, bridge=bridge)
    
    budget = ResourceBudget(max_usd_spend_per_day=5.00, max_tokens_per_day=1_000_000)
    
    # Register some agents with sufficient budgets
    orch.register_agent(
        "aurora", wallet="0x1111111111111111111111111111111111111111",
        personality="explorer",
        skills=["research", "analysis", "documentation"],
        specializations=["research", "data_collection"],
        budget=budget,
    )
    orch.register_agent(
        "blaze", wallet="0x2222222222222222222222222222222222222222",
        personality="builder",
        skills=["code_review", "testing", "documentation"],
        specializations=["code_review", "testing"],
        budget=budget,
    )
    orch.register_agent(
        "cipher", wallet="0x3333333333333333333333333333333333333333",
        personality="analyst",
        skills=["research", "data_science", "documentation"],
        specializations=["research"],
        budget=budget,
    )
    
    # Boot and activate agents
    for agent_id in ["aurora", "blaze", "cipher"]:
        lifecycle.boot_agent(agent_id)
        lifecycle.activate_agent(agent_id)
    
    return orch


@pytest.fixture
def coordinator(mock_api, orchestrator_with_agents):
    """Fully configured live coordinator with mocked API."""
    return SwarmLiveCoordinator(
        orchestrator=orchestrator_with_agents,
        dry_run=True,
    )


# ── EMTaskView Tests ──

class TestEMTaskView:
    def test_basic_parsing(self):
        view = EMTaskView(SAMPLE_PUBLISHED_TASKS[0])
        assert view.id == "ec8f4770-15c8-4e46-9250-3fe1e9248e66"
        assert view.category == "simple_action"
        assert view.bounty_usd == 0.10
        assert view.chain == "optimism"

    def test_agent_capable_simple_action(self):
        view = EMTaskView(SAMPLE_PUBLISHED_TASKS[0])
        assert view.is_agent_capable is True

    def test_agent_incapable_physical(self):
        view = EMTaskView(SAMPLE_PUBLISHED_TASKS[1])
        # physical_verification with location = not agent-capable
        assert view.is_agent_capable is False

    def test_agent_capable_research(self):
        view = EMTaskView(SAMPLE_PUBLISHED_TASKS[2])
        assert view.is_agent_capable is True

    def test_required_skills(self):
        view = EMTaskView(SAMPLE_PUBLISHED_TASKS[2])
        assert "research" in view.required_skills
        assert "analysis" in view.required_skills

    def test_null_evidence_schema(self):
        view = EMTaskView(SAMPLE_PUBLISHED_TASKS[0])
        assert view.evidence_schema == []

    def test_repr(self):
        view = EMTaskView(SAMPLE_PUBLISHED_TASKS[0])
        r = repr(view)
        assert "EMTask" in r
        assert "simple_action" in r


# ── Coordinator Tests ──

class TestSwarmLiveCoordinator:
    def test_fetch_published(self, coordinator):
        tasks = coordinator.fetch_published_tasks()
        assert len(tasks) == 3
        assert all(isinstance(t, EMTaskView) for t in tasks)

    def test_fetch_completed(self, coordinator):
        tasks = coordinator.fetch_completed_tasks()
        assert len(tasks) == 2

    def test_fetch_health(self, coordinator):
        health = coordinator.fetch_api_health()
        assert health.get("status") == "healthy"

    @pytest.mark.asyncio
    async def test_scan_and_match(self, coordinator):
        results = await coordinator.scan_and_match()
        assert len(results) == 3
        
        # Research task should get matched
        research_result = next(r for r in results if r["category"] == "research")
        assert research_result["agent_capable"] is True
        assert research_result.get("assignment") is not None

    @pytest.mark.asyncio
    async def test_physical_task_skipped(self, coordinator):
        results = await coordinator.scan_and_match()
        
        physical = next(r for r in results if r["category"] == "physical_verification")
        assert physical["agent_capable"] is False
        assert physical.get("skip_reason") is not None

    @pytest.mark.asyncio
    async def test_run_cycle(self, coordinator):
        result = await coordinator.run_cycle()
        assert result["status"] == "completed"
        assert result["tasks_available"] == 3
        assert result["dry_run"] is True
        assert result["duration_ms"] >= 0
        assert result["cycle"] == 1

    @pytest.mark.asyncio
    async def test_multiple_cycles(self, coordinator):
        r1 = await coordinator.run_cycle()
        r2 = await coordinator.run_cycle()
        assert r1["cycle"] == 1
        assert r2["cycle"] == 2

    @pytest.mark.asyncio
    async def test_health_report(self, coordinator):
        report = await coordinator.health_report()
        assert "api" in report
        assert "swarm" in report
        assert "economics" in report
        assert report["api"]["status"] == "healthy"

    def test_category_analysis(self, coordinator):
        analysis = coordinator.task_category_analysis()
        assert "categories" in analysis
        assert "recommendations" in analysis
        assert analysis["total_analyzed"] == 2  # completed tasks

    @pytest.mark.asyncio
    async def test_unhealthy_api(self, orchestrator_with_agents):
        with patch("lib.swarm_live_coordinator._api_get", return_value={}):
            coord = SwarmLiveCoordinator(
                orchestrator=orchestrator_with_agents,
                dry_run=True,
            )
            result = await coord.run_cycle()
            assert result["status"] == "api_unhealthy"


# ── No-Agent Edge Cases ──

class TestNoAgents:
    def test_coordinator_without_agents(self):
        with patch("lib.swarm_live_coordinator._api_get", return_value=SAMPLE_PUBLISHED_TASKS):
            coord = SwarmLiveCoordinator(dry_run=True)
            tasks = coord.fetch_published_tasks()
            assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_scan_without_agents(self):
        def _mock_get(endpoint, params=None):
            params = params or {}
            if params.get("status") == "published":
                return SAMPLE_PUBLISHED_TASKS
            if endpoint == "/health":
                return SAMPLE_HEALTH
            return {}

        with patch("lib.swarm_live_coordinator._api_get", side_effect=_mock_get):
            coord = SwarmLiveCoordinator(dry_run=True)
            results = await coord.scan_and_match()
            # Should not crash, just skip matching
            assert len(results) == 3
            for r in results:
                if r.get("agent_capable", True):
                    assert r.get("skip_reason") == "No agents registered"


# ── Integration with Orchestrator ──

class TestOrchestratorIntegration:
    @pytest.mark.asyncio
    async def test_task_assignment_recorded(self, coordinator):
        results = await coordinator.scan_and_match()
        
        # Check orchestrator tracked the assignments
        matched = [r for r in results if r.get("assignment") and r["assignment"].get("assigned_agent")]
        assert len(matched) > 0
        
        # Verify orchestrator's active tasks
        assert coordinator.orchestrator.total_tasks_assigned > 0

    @pytest.mark.asyncio  
    async def test_best_agent_for_research(self, coordinator):
        results = await coordinator.scan_and_match()
        
        research = next(
            r for r in results
            if r["category"] == "research" and r.get("assignment")
        )
        assignment = research["assignment"]
        
        # aurora or cipher should get research (they have research skills)
        assert assignment["assigned_agent"] in ["aurora", "cipher"]
