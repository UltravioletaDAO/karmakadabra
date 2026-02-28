"""
Live Integration Tests — Intelligence Synthesizer against EM API

Validates the full intelligence chain:
  EM API → Task Data → Intelligence Synthesizer → Routing Decisions

These tests hit the live production API (api.execution.market).
Tests that require specific marketplace state gracefully skip.

Run with:
    python -m pytest tests/v2/test_live_intelligence.py -v
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from intelligence_synthesizer import (
    IntelligenceSynthesizer,
    TaskRoutingRequest,
    AgentIntelligence,
    SwarmIntelligenceReport,
)


# EM API base URL
EM_API = "https://api.execution.market"

# Skip if network unavailable
try:
    import urllib.request
    req = urllib.request.Request(f"{EM_API}/health", method="GET")
    req.add_header("User-Agent", "KK-Intelligence-Test/1.0")
    with urllib.request.urlopen(req, timeout=5) as resp:
        health = json.loads(resp.read())
    API_AVAILABLE = health.get("status") == "healthy"
except Exception:
    API_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not API_AVAILABLE,
    reason="EM API not available"
)


def api_get(path: str, params: dict = None) -> dict:
    """Helper to GET from EM API."""
    import urllib.parse
    url = f"{EM_API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "KK-Intelligence-Test/1.0")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ═══════════════════════════════════════════════════════════════════
# API Health & Connectivity
# ═══════════════════════════════════════════════════════════════════


class TestAPIConnectivity:
    """Verify EM API is reachable and healthy."""

    def test_health_endpoint(self):
        data = api_get("/health")
        assert data["status"] == "healthy"

    def test_all_components_healthy(self):
        data = api_get("/health")
        for name, comp in data["components"].items():
            assert comp["status"] == "healthy", f"{name} is {comp['status']}"

    def test_blockchain_connected(self):
        data = api_get("/health")
        block = data["components"]["blockchain"]["details"]["block_number"]
        assert block > 42_000_000, "Block number too low"

    def test_database_connected(self):
        data = api_get("/health")
        db_latency = data["components"]["database"]["latency_ms"]
        assert db_latency < 5000, f"DB latency too high: {db_latency}ms"


# ═══════════════════════════════════════════════════════════════════
# Marketplace Intelligence
# ═══════════════════════════════════════════════════════════════════


class TestMarketplaceIntelligence:
    """Test intelligence synthesis from live marketplace data."""

    def test_browse_marketplace(self):
        """Verify marketplace API returns valid structure."""
        data = api_get("/api/v1/tasks", {"status": "published", "limit": 10})
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    def test_completed_tasks_exist(self):
        """Verify completed tasks are accessible (evidence source)."""
        data = api_get("/api/v1/tasks", {"status": "completed", "limit": 5})
        assert "tasks" in data
        # May be 0 if no recent completions — that's OK

    def test_task_routing_request_from_api(self):
        """TaskRoutingRequest can be created from API response structure."""
        data = api_get("/api/v1/tasks", {"limit": 5})
        for task in data.get("tasks", []):
            req = TaskRoutingRequest.from_em_task(task)
            assert req.task_id != ""
            assert isinstance(req.bounty_usd, float)
            assert isinstance(req.requires_physical, bool)


# ═══════════════════════════════════════════════════════════════════
# Intelligence Synthesizer with Live Data
# ═══════════════════════════════════════════════════════════════════


class TestSynthesizerWithLiveContext:
    """Test the synthesizer using simulated agent data in context of live EM."""

    @pytest.fixture
    def live_synth(self, tmp_path):
        """Create a synthesizer with test agents and live API context."""
        base = tmp_path / "data"
        base.mkdir()
        workspaces = base / "workspaces"
        workspaces.mkdir()
        (base / "reputation").mkdir()

        # Create agents with varying profiles
        agents = {
            "kk-researcher": {
                "perf": {"total_tasks": 15, "total_approved": 13, "total_cost_usd": 0.75,
                         "total_revenue_usd": 3.00, "overall_score": 80.0,
                         "reliability_score": 85.0, "efficiency_score": 75.0},
                "evidence": [
                    {"category": "research", "approved": True, "bounty_usd": 0.25, "cost_usd": 0.05}
                ] * 8 + [
                    {"category": "research", "approved": False, "bounty_usd": 0.20, "cost_usd": 0.06}
                ] * 2,
                "lifecycle": {"state": "idle", "consecutive_failures": 0, "total_successes": 13},
                "reputation": {"composite_score": 75.0, "tier": "Oro", "confidence": 0.7,
                               "sources_available": ["off_chain", "transactional"],
                               "layers": {"on_chain": {"score": 50}, "off_chain": {"score": 80}, "transactional": {"score": 70}}},
            },
            "kk-coder": {
                "perf": {"total_tasks": 20, "total_approved": 18, "total_cost_usd": 2.00,
                         "total_revenue_usd": 8.00, "overall_score": 85.0,
                         "reliability_score": 90.0, "efficiency_score": 80.0},
                "evidence": [
                    {"category": "code_review", "approved": True, "bounty_usd": 0.50, "cost_usd": 0.10}
                ] * 12 + [
                    {"category": "code_review", "approved": False, "bounty_usd": 0.50, "cost_usd": 0.15}
                ] * 2,
                "lifecycle": {"state": "idle", "consecutive_failures": 0, "total_successes": 18},
                "reputation": {"composite_score": 85.0, "tier": "Diamante", "confidence": 0.9,
                               "sources_available": ["on_chain", "off_chain", "transactional"],
                               "layers": {"on_chain": {"score": 88}, "off_chain": {"score": 85}, "transactional": {"score": 82}}},
            },
            "kk-newbie": {
                "perf": {"total_tasks": 1, "total_approved": 1, "overall_score": 55.0},
                "evidence": [
                    {"category": "content_creation", "approved": True, "bounty_usd": 0.10, "cost_usd": 0.02}
                ],
                "lifecycle": {"state": "idle", "consecutive_failures": 0, "total_successes": 1},
                "reputation": {"composite_score": 50.0, "tier": "Plata", "confidence": 0.1,
                               "sources_available": [],
                               "layers": {"on_chain": {"score": 50}, "off_chain": {"score": 50}, "transactional": {"score": 50}}},
            },
        }

        # Write data files
        lifecycle_list = []
        rep_data = {}
        for name, data in agents.items():
            ws = workspaces / name
            ws.mkdir()
            (ws / "performance.json").write_text(json.dumps(data["perf"]))
            (ws / "evidence_history.json").write_text(json.dumps(data["evidence"]))
            lifecycle_list.append({"agent_name": name, **data["lifecycle"]})
            rep_data[name] = data["reputation"]

        (base / "lifecycle_state.json").write_text(json.dumps(lifecycle_list))
        (base / "reputation" / "snapshot_latest.json").write_text(json.dumps(rep_data))

        return IntelligenceSynthesizer(workspaces)

    def test_synthesize_produces_compound_profiles(self, live_synth):
        result = live_synth.synthesize()
        assert len(result) == 3
        for name, intel in result.items():
            assert intel.compound_score > 0
            assert len(intel.sources_available) > 0

    def test_route_research_task(self, live_synth):
        """Route a research task — researcher should rank highest."""
        live_synth.synthesize()
        task = TaskRoutingRequest(
            task_id="live-001",
            title="Analyze DeFi market trends",
            description="Research current DeFi protocols",
            category="research",
            bounty_usd=0.25,
        )
        decision = live_synth.route_task(task)
        assert decision.selected_agent == "kk-researcher"
        assert decision.confidence > 0

    def test_route_code_review_task(self, live_synth):
        """Route a code review — coder should rank highest."""
        live_synth.synthesize()
        task = TaskRoutingRequest(
            task_id="live-002",
            title="Review Solidity smart contract",
            description="Security audit of ERC-20 code",
            category="code_review",
            bounty_usd=0.50,
        )
        decision = live_synth.route_task(task)
        assert decision.selected_agent == "kk-coder"

    def test_newbie_gets_cold_start_bonus(self, live_synth):
        result = live_synth.synthesize()
        newbie = result["kk-newbie"]
        assert newbie.cold_start_bonus > 0
        assert newbie.cold_start_bonus > result["kk-researcher"].cold_start_bonus

    def test_fleet_intelligence_report(self, live_synth):
        live_synth.synthesize()
        report = live_synth.generate_intelligence_report()
        assert report.total_agents == 3
        assert report.healthy_agents == 3
        assert report.swarm_health_score > 0

    def test_route_from_live_tasks(self, live_synth):
        """Route actual live marketplace tasks if available."""
        data = api_get("/api/v1/tasks", {"limit": 5})
        tasks = data.get("tasks", [])
        if not tasks:
            pytest.skip("No tasks in marketplace")

        live_synth.synthesize()
        for task_data in tasks:
            req = TaskRoutingRequest.from_em_task(task_data)
            decision = live_synth.route_task(req)
            # Should always produce a decision (even if no agent selected)
            assert decision.task_id == req.task_id
            assert len(decision.reasoning) > 0

    def test_save_and_load_snapshot(self, live_synth):
        live_synth.synthesize()
        path = live_synth.save_snapshot()
        assert path.exists()

        loaded = live_synth.load_latest_snapshot()
        assert loaded is not None
        assert "agents" in loaded
        assert "report" in loaded

    def test_format_report_readable(self, live_synth):
        live_synth.synthesize()
        text = live_synth.format_intelligence_report()
        assert "Intelligence Report" in text
        assert "kk-researcher" in text or "kk-coder" in text


# ═══════════════════════════════════════════════════════════════════
# Auth Endpoint Verification
# ═══════════════════════════════════════════════════════════════════


class TestAuthEndpoints:
    """Verify ERC-8128 auth endpoints are operational."""

    def test_nonce_generation(self):
        data = api_get("/api/v1/auth/nonce")
        assert "nonce" in data
        assert len(data["nonce"]) > 10

    def test_nonce_uniqueness(self):
        n1 = api_get("/api/v1/auth/nonce")["nonce"]
        n2 = api_get("/api/v1/auth/nonce")["nonce"]
        assert n1 != n2

    def test_erc8128_info(self):
        data = api_get("/api/v1/auth/erc8128/info")
        assert "supported_chains" in data or "chains" in data or "algorithms" in data
