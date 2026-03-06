"""
Tests for KK V2 AutoJob Enrichment Layer

Tests the bridge between KK's decision engine and AutoJob's SwarmRouter,
covering both local mode (SwarmRouter available) and fallback mode.
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.autojob_enrichment import (
    AutoJobEnrichment,
    EnrichedProfile,
    EnrichmentResult,
)


# ═══════════════════════════════════════════════════════════════════
# EnrichedProfile Tests
# ═══════════════════════════════════════════════════════════════════


class TestEnrichedProfile:
    """Test EnrichedProfile data class."""

    def test_default_values(self):
        p = EnrichedProfile(agent_name="alice", wallet="0xABC")
        assert p.autojob_score == 0.0
        assert p.autojob_tier == "unverified"
        assert p.autojob_confidence == 0.0
        assert p.predicted_quality == 3.0
        assert p.predicted_success == 0.5
        assert p.enrichment_source == "none"

    def test_to_dict(self):
        p = EnrichedProfile(
            agent_name="alice",
            wallet="0xABC",
            autojob_score=85.5,
            autojob_tier="oro",
            enrichment_source="autojob_local",
        )
        d = p.to_dict()
        assert d["agent_name"] == "alice"
        assert d["autojob_score"] == 85.5
        assert d["autojob_tier"] == "oro"
        assert d["enrichment_source"] == "autojob_local"

    def test_custom_values(self):
        p = EnrichedProfile(
            agent_name="bob",
            wallet="0xDEF",
            autojob_score=92.0,
            autojob_tier="diamante",
            autojob_confidence=0.95,
            predicted_quality=4.5,
            predicted_success=0.9,
            categories_worked=["physical_verification", "data_collection"],
            total_tasks_completed=42,
            composite_reputation=88.0,
        )
        assert p.total_tasks_completed == 42
        assert len(p.categories_worked) == 2
        assert p.composite_reputation == 88.0


class TestEnrichmentResult:
    """Test EnrichmentResult data class."""

    def test_to_dict(self):
        profile = EnrichedProfile(agent_name="alice", wallet="0xABC")
        result = EnrichmentResult(
            task_id="task_123",
            task_category="physical_verification",
            profiles={"alice": profile},
            total_agents=3,
            enriched_agents=1,
            source="autojob_local",
            enrichment_time_ms=15.5,
        )
        d = result.to_dict()
        assert d["task_id"] == "task_123"
        assert d["total_agents"] == 3
        assert d["enriched_agents"] == 1
        assert "alice" in d["profiles"]

    def test_empty_result(self):
        result = EnrichmentResult(
            task_id="",
            task_category="",
            profiles={},
            total_agents=0,
            enriched_agents=0,
            source="fallback",
        )
        assert result.enrichment_time_ms == 0.0
        assert result.router_health == {}


# ═══════════════════════════════════════════════════════════════════
# AutoJobEnrichment - Fallback Mode Tests
# ═══════════════════════════════════════════════════════════════════


class TestFallbackMode:
    """Test enrichment when AutoJob is not available."""

    def test_init_without_autojob(self):
        e = AutoJobEnrichment()
        assert not e.is_available
        assert e.mode == "none"

    def test_init_with_nonexistent_path(self):
        e = AutoJobEnrichment(autojob_path="/nonexistent/path/autojob")
        assert not e.is_available
        assert e.mode == "fallback"

    def test_fallback_enrichment(self):
        e = AutoJobEnrichment(fallback_score=55.0)
        task = {"id": "task_1", "category": "data_collection", "title": "Test task"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA", "0xBBB", "0xCCC"],
            agent_names={"0xaaa": "alice", "0xbbb": "bob", "0xccc": "carol"},
        )

        assert result.task_id == "task_1"
        assert result.task_category == "data_collection"
        assert result.total_agents == 3
        assert result.enriched_agents == 0  # All fallback
        assert result.source == "fallback"
        assert len(result.profiles) == 3

        # All profiles should have fallback score
        for name, profile in result.profiles.items():
            assert profile.autojob_score == 55.0
            assert profile.autojob_tier == "unverified"
            assert profile.enrichment_source == "fallback"

    def test_fallback_profile_values(self):
        e = AutoJobEnrichment(fallback_score=40.0)
        p = e._fallback_profile("alice", "0xABC")

        assert p.agent_name == "alice"
        assert p.wallet == "0xABC"
        assert p.autojob_score == 40.0
        assert p.predicted_quality == 3.0
        assert p.predicted_success == 0.5
        assert p.enrichment_source == "fallback"

    def test_wallet_name_mapping(self):
        e = AutoJobEnrichment(
            wallet_to_agent={"0xaaa": "alice", "0xbbb": "bob"}
        )
        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA", "0xBBB"],
        )

        names = set(result.profiles.keys())
        assert "alice" in names
        assert "bob" in names

    def test_unknown_wallet_uses_prefix(self):
        e = AutoJobEnrichment()
        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xDEADBEEF123456"],
        )

        # Should use first 10 chars of wallet as name
        assert len(result.profiles) == 1


# ═══════════════════════════════════════════════════════════════════
# AutoJobEnrichment - Local Mode Tests (Mocked SwarmRouter)
# ═══════════════════════════════════════════════════════════════════


class TestLocalMode:
    """Test enrichment with a mocked SwarmRouter."""

    @pytest.fixture
    def mock_router(self):
        router = MagicMock()
        router.route_task.return_value = {
            "best_match": {"wallet": "0xAAA", "final_score": 92.0},
            "rankings": [
                {
                    "wallet": "0xAAA",
                    "final_score": 92.0,
                    "tier": "diamante",
                    "confidence": 0.95,
                    "predicted_quality": 4.5,
                    "predicted_success": 0.88,
                    "skill_match": {"photography": 0.95, "geo": 0.80},
                    "evidence_types": ["photo_geo", "video"],
                    "categories_worked": ["physical_verification"],
                    "total_tasks": 42,
                    "composite_reputation": 88.5,
                },
                {
                    "wallet": "0xBBB",
                    "final_score": 75.0,
                    "tier": "oro",
                    "confidence": 0.7,
                    "predicted_quality": 3.8,
                    "predicted_success": 0.72,
                    "skill_match": {"photography": 0.6},
                    "evidence_types": ["photo"],
                    "categories_worked": ["content_creation"],
                    "total_tasks": 15,
                    "composite_reputation": 72.0,
                },
            ],
        }
        router.health.return_value = {"status": "healthy", "workers": 10}
        return router

    def test_local_enrichment(self, mock_router):
        e = AutoJobEnrichment()
        e._router = mock_router
        e._mode = "autojob_local"

        task = {
            "id": "task_photo",
            "category": "physical_verification",
            "title": "Verify storefront",
        }

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA", "0xBBB"],
            agent_names={"0xaaa": "alice", "0xbbb": "bob"},
        )

        assert result.source == "autojob_local"
        assert result.enriched_agents == 2
        assert result.total_agents == 2

        alice = result.profiles["alice"]
        assert alice.autojob_score == 92.0
        assert alice.autojob_tier == "diamante"
        assert alice.predicted_quality == 4.5
        assert alice.enrichment_source == "autojob_local"

        bob = result.profiles["bob"]
        assert bob.autojob_score == 75.0
        assert bob.autojob_tier == "oro"

    def test_local_with_missing_agents(self, mock_router):
        """Agents not in AutoJob results get fallback profiles."""
        e = AutoJobEnrichment(fallback_score=50.0)
        e._router = mock_router
        e._mode = "autojob_local"

        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA", "0xBBB", "0xCCC"],
            agent_names={
                "0xaaa": "alice",
                "0xbbb": "bob",
                "0xccc": "carol",
            },
        )

        assert result.total_agents == 3
        assert result.enriched_agents == 2  # alice + bob
        carol = result.profiles["carol"]
        assert carol.enrichment_source == "fallback"
        assert carol.autojob_score == 50.0

    def test_local_error_falls_back(self, mock_router):
        """Router error falls back to default profiles."""
        mock_router.route_task.side_effect = Exception("Network error")
        e = AutoJobEnrichment()
        e._router = mock_router
        e._mode = "autojob_local"

        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA"],
            agent_names={"0xaaa": "alice"},
        )

        assert result.source == "fallback"
        assert result.enriched_agents == 0

    def test_enrichment_time_tracked(self, mock_router):
        e = AutoJobEnrichment()
        e._router = mock_router
        e._mode = "autojob_local"

        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA"],
            agent_names={"0xaaa": "alice"},
        )

        assert result.enrichment_time_ms >= 0

    def test_router_health_included(self, mock_router):
        e = AutoJobEnrichment()
        e._router = mock_router
        e._mode = "autojob_local"

        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA"],
            agent_names={"0xaaa": "alice"},
        )

        assert result.router_health.get("status") == "healthy"


# ═══════════════════════════════════════════════════════════════════
# Context Injection Tests
# ═══════════════════════════════════════════════════════════════════


class TestContextInjection:
    """Test injecting enrichment into existing agent profiles."""

    @pytest.fixture
    def mock_enrichment(self):
        e = AutoJobEnrichment(fallback_score=60.0)
        return e

    def test_inject_into_profiles(self, mock_enrichment):
        task = {"id": "t1", "category": "data_collection"}
        profiles = {
            "alice": {"wallet": "0xAAA", "skills": ["research"], "reliability": 0.9},
            "bob": {"wallet": "0xBBB", "skills": ["writing"], "reliability": 0.8},
        }

        result = mock_enrichment.enrich_task_context(task, profiles)

        # Original fields preserved
        assert result["alice"]["skills"] == ["research"]
        assert result["alice"]["reliability"] == 0.9

        # Enrichment fields added
        assert "autojob_score" in result["alice"]
        assert "autojob_tier" in result["alice"]
        assert result["alice"]["enrichment_source"] == "fallback"

    def test_inject_with_no_wallets(self, mock_enrichment):
        task = {"id": "t1", "category": "survey"}
        profiles = {
            "alice": {"skills": ["survey"]},  # No wallet field
        }

        result = mock_enrichment.enrich_task_context(task, profiles)

        # Should return profiles unchanged (no wallets to look up)
        assert result == profiles

    def test_inject_preserves_original(self, mock_enrichment):
        task = {"id": "t1", "category": "survey"}
        profiles = {
            "alice": {
                "wallet": "0xAAA",
                "custom_field": "preserved",
                "nested": {"data": 42},
            },
        }

        result = mock_enrichment.enrich_task_context(task, profiles)
        assert result["alice"]["custom_field"] == "preserved"
        assert result["alice"]["nested"]["data"] == 42


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_wallet_list(self):
        e = AutoJobEnrichment()
        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(task=task, agent_wallets=[])
        assert result.total_agents == 0
        assert result.enriched_agents == 0
        assert len(result.profiles) == 0

    def test_single_agent(self):
        e = AutoJobEnrichment()
        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA"],
            agent_names={"0xaaa": "solo"},
        )
        assert len(result.profiles) == 1
        assert "solo" in result.profiles

    def test_task_with_missing_fields(self):
        e = AutoJobEnrichment()
        task = {}  # Empty task

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA"],
        )
        assert result.task_id == "unknown"
        assert result.task_category == "unknown"

    def test_large_agent_list(self):
        e = AutoJobEnrichment()
        task = {"id": "t1", "category": "survey"}
        wallets = [f"0x{i:040x}" for i in range(100)]
        names = {f"0x{i:040x}": f"agent-{i}" for i in range(100)}

        result = e.enrich_for_decision(task=task, agent_wallets=wallets, agent_names=names)
        assert result.total_agents == 100
        assert len(result.profiles) == 100

    def test_duplicate_wallets(self):
        e = AutoJobEnrichment()
        task = {"id": "t1", "category": "survey"}

        result = e.enrich_for_decision(
            task=task,
            agent_wallets=["0xAAA", "0xAAA"],
        )
        # Should handle duplicates gracefully
        assert result.total_agents == 2

    def test_is_available_property(self):
        e = AutoJobEnrichment()
        assert not e.is_available

    def test_mode_property(self):
        e = AutoJobEnrichment()
        assert e.mode == "none"

        e2 = AutoJobEnrichment(autojob_path="/nonexistent")
        assert e2.mode == "fallback"
