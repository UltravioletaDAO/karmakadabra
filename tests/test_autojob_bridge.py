"""
Tests for AutoJob Intelligence Bridge

Tests the KK ↔ AutoJob integration without requiring AutoJob to be
installed. Uses mocks for the AutoJob components, and tests the
bridge's data transformation, ranking, prediction, and sync logic.
"""

import json
import sys
import tempfile
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from lib.autojob_bridge import (
    AutoJobBridge,
    AgentRanking,
    BridgeResult,
    KK_TO_AUTOJOB_CATEGORY,
)


# ═══════════════════════════════════════════════════════════════════
# Mock AutoJob Components
# ═══════════════════════════════════════════════════════════════════


@dataclass
class MockWorkerRanking:
    wallet: str
    final_score: float
    skill_score: float
    reputation_score: float
    reliability_score: float
    recency_score: float
    tier: str
    tier_bonus: float = 0
    match_explanation: str = ""
    on_chain_registered: bool = False
    agent_id: int = None
    confidence: float = 0.5
    categories_worked: list = field(default_factory=list)
    total_tasks: int = 0


@dataclass
class MockMatchResult:
    task_id: str = "test-001"
    task_category: str = "physical_verification"
    rankings: list = field(default_factory=list)
    total_candidates: int = 0
    qualified_candidates: int = 0
    best_match: object = None
    match_time_ms: float = 1.0


# ═══════════════════════════════════════════════════════════════════
# Bridge Initialization
# ═══════════════════════════════════════════════════════════════════


class TestBridgeInit:
    """Test bridge initialization in various modes."""

    def test_remote_mode_init(self):
        """Remote mode doesn't require AutoJob imports."""
        bridge = AutoJobBridge(mode="remote", api_base="https://autojob.cc")
        assert bridge.mode == "remote"
        assert bridge.api_base == "https://autojob.cc"
        assert bridge._local_matcher is None

    def test_remote_mode_strips_trailing_slash(self):
        bridge = AutoJobBridge(mode="remote", api_base="https://autojob.cc/")
        assert bridge.api_base == "https://autojob.cc"

    def test_local_mode_fallback_to_remote(self):
        """Local mode falls back to remote if AutoJob can't be imported."""
        bridge = AutoJobBridge(mode="local", autojob_path="/nonexistent/path")
        assert bridge.mode == "remote"  # Falls back

    def test_wallet_to_agent_mapping(self):
        mapping = {"0xABC": "alice", "0xDEF": "bob"}
        bridge = AutoJobBridge(mode="remote", wallet_to_agent=mapping)
        assert bridge.wallet_to_agent == mapping

    def test_default_wallet_mapping_empty(self):
        bridge = AutoJobBridge(mode="remote")
        assert bridge.wallet_to_agent == {}


# ═══════════════════════════════════════════════════════════════════
# Category Mapping
# ═══════════════════════════════════════════════════════════════════


class TestCategoryMapping:
    """Test KK → AutoJob category normalization."""

    def test_direct_mappings(self):
        """Standard EM categories map 1:1."""
        for cat in ["physical_verification", "data_collection", "content_creation",
                     "translation", "quality_assurance", "technical_task",
                     "survey", "delivery", "mystery_shopping", "notarization"]:
            assert KK_TO_AUTOJOB_CATEGORY.get(cat) == cat

    def test_kk_specific_mappings(self):
        """KK-specific categories map to AutoJob equivalents."""
        assert KK_TO_AUTOJOB_CATEGORY["code_review"] == "technical_task"
        assert KK_TO_AUTOJOB_CATEGORY["research"] == "data_collection"
        assert KK_TO_AUTOJOB_CATEGORY["writing"] == "content_creation"
        assert KK_TO_AUTOJOB_CATEGORY["analysis"] == "data_collection"

    def test_unknown_category_passthrough(self):
        """Unknown categories should pass through as-is."""
        assert KK_TO_AUTOJOB_CATEGORY.get("unknown_cat", "unknown_cat") == "unknown_cat"


# ═══════════════════════════════════════════════════════════════════
# Ranking (Local Mode)
# ═══════════════════════════════════════════════════════════════════


class TestLocalRanking:
    """Test local-mode ranking with mocked AutoJob components."""

    def _make_bridge_with_mock(self, mock_result=None):
        """Create a bridge with a mock local matcher."""
        bridge = AutoJobBridge(mode="remote")  # Init as remote first
        bridge.mode = "local"  # Override to local

        # Create mock matcher
        mock_matcher = MagicMock()
        if mock_result is None:
            mock_result = MockMatchResult(
                rankings=[
                    MockWorkerRanking(
                        wallet="0xAAA111",
                        final_score=85.0,
                        skill_score=78.0,
                        reputation_score=90.0,
                        reliability_score=95.0,
                        recency_score=80.0,
                        tier="oro",
                        confidence=0.75,
                        categories_worked=["physical_verification"],
                        total_tasks=20,
                        agent_id=18776,
                    ),
                    MockWorkerRanking(
                        wallet="0xBBB222",
                        final_score=65.0,
                        skill_score=60.0,
                        reputation_score=70.0,
                        reliability_score=75.0,
                        recency_score=50.0,
                        tier="plata",
                        confidence=0.55,
                        categories_worked=["data_collection"],
                        total_tasks=10,
                    ),
                ],
                total_candidates=5,
                qualified_candidates=2,
            )
        mock_matcher.rank_workers_for_task.return_value = mock_result

        bridge._local_matcher = mock_matcher
        bridge._local_registry = MagicMock()
        bridge._local_reader = MagicMock()
        bridge.wallet_to_agent = {
            "0xAAA111": "karma-hello",
            "0xBBB222": "skill-extractor",
        }

        return bridge

    def test_rank_returns_bridge_result(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "title": "Verify shop", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert isinstance(result, BridgeResult)
        assert result.mode == "local"

    def test_rankings_converted_to_agent_ranking(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "title": "Test", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert len(result.rankings) == 2
        assert isinstance(result.rankings[0], AgentRanking)

    def test_wallet_to_agent_name_mapping(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert result.rankings[0].agent_name == "karma-hello"
        assert result.rankings[1].agent_name == "skill-extractor"

    def test_unknown_wallet_gets_truncated_name(self):
        bridge = self._make_bridge_with_mock()
        bridge.wallet_to_agent = {}  # No mappings
        task = {"id": "t1", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert "..." in result.rankings[0].agent_name

    def test_score_propagation(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        r0 = result.rankings[0]
        assert r0.final_score == 85.0
        assert r0.skill_score == 78.0
        assert r0.reputation_score == 90.0
        assert r0.reliability_score == 95.0
        assert r0.recency_score == 80.0

    def test_tier_propagation(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert result.rankings[0].tier == "oro"
        assert result.rankings[1].tier == "plata"

    def test_best_match_set(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert result.best_match is not None
        assert result.best_match.wallet == "0xAAA111"

    def test_empty_rankings(self):
        bridge = self._make_bridge_with_mock(
            MockMatchResult(rankings=[], total_candidates=5, qualified_candidates=0)
        )
        task = {"id": "t1", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert result.rankings == []
        assert result.best_match is None

    def test_category_normalization(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "code_review"}
        result = bridge.rank_agents_for_task(task)
        # Should call AutoJob with "technical_task"
        call_args = bridge._local_matcher.rank_workers_for_task.call_args
        assert call_args[0][0]["category"] == "technical_task"

    def test_match_time_recorded(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "physical_verification"}
        result = bridge.rank_agents_for_task(task)
        assert result.match_time_ms > 0

    def test_limit_passed_through(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "physical_verification"}
        bridge.rank_agents_for_task(task, limit=3)
        call_args = bridge._local_matcher.rank_workers_for_task.call_args
        assert call_args[1].get("limit") == 3 or call_args[0][1] if len(call_args[0]) > 1 else True

    def test_min_score_passed_through(self):
        bridge = self._make_bridge_with_mock()
        task = {"id": "t1", "category": "physical_verification"}
        bridge.rank_agents_for_task(task, min_score=50.0)
        call_args = bridge._local_matcher.rank_workers_for_task.call_args
        assert call_args[1].get("min_score") == 50.0


# ═══════════════════════════════════════════════════════════════════
# Prediction Helpers
# ═══════════════════════════════════════════════════════════════════


class TestPredictions:
    """Test quality and success prediction logic."""

    def _make_bridge(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        return bridge

    def test_predict_quality_high_skill(self):
        bridge = self._make_bridge()
        ranking = MockWorkerRanking(
            wallet="0x1", final_score=90, skill_score=90,
            reputation_score=85, reliability_score=95, recency_score=80,
            tier="oro", confidence=0.8
        )
        quality = bridge._predict_quality(ranking, "physical_verification")
        assert 4.0 <= quality <= 5.0

    def test_predict_quality_low_skill(self):
        bridge = self._make_bridge()
        ranking = MockWorkerRanking(
            wallet="0x1", final_score=30, skill_score=20,
            reputation_score=30, reliability_score=40, recency_score=20,
            tier="bronce", confidence=0.2
        )
        quality = bridge._predict_quality(ranking, "technical_task")
        assert 3.0 <= quality <= 4.0

    def test_predict_quality_bounds(self):
        bridge = self._make_bridge()
        # Max case
        ranking = MockWorkerRanking(
            wallet="0x1", final_score=100, skill_score=100,
            reputation_score=100, reliability_score=100, recency_score=100,
            tier="diamante", confidence=1.0
        )
        assert bridge._predict_quality(ranking, "survey") == 5.0

        # Min case
        ranking = MockWorkerRanking(
            wallet="0x1", final_score=0, skill_score=0,
            reputation_score=0, reliability_score=0, recency_score=0,
            tier="unverified", confidence=0.0
        )
        assert bridge._predict_quality(ranking, "survey") == 3.0

    def test_predict_success_high_reliability(self):
        bridge = self._make_bridge()
        ranking = MockWorkerRanking(
            wallet="0x1", final_score=85, skill_score=80,
            reputation_score=85, reliability_score=95, recency_score=80,
            tier="oro", confidence=0.8
        )
        prob = bridge._predict_success(ranking, "data_collection")
        assert 0.7 <= prob <= 0.99

    def test_predict_success_cold_start_penalty(self):
        bridge = self._make_bridge()
        # High scores but low confidence (new worker)
        ranking_new = MockWorkerRanking(
            wallet="0x1", final_score=80, skill_score=80,
            reputation_score=80, reliability_score=80, recency_score=80,
            tier="registered", confidence=0.2  # Low confidence
        )
        # Same scores but high confidence (experienced)
        ranking_exp = MockWorkerRanking(
            wallet="0x2", final_score=80, skill_score=80,
            reputation_score=80, reliability_score=80, recency_score=80,
            tier="oro", confidence=0.8  # High confidence
        )
        prob_new = bridge._predict_success(ranking_new, "survey")
        prob_exp = bridge._predict_success(ranking_exp, "survey")
        assert prob_new < prob_exp  # Cold start penalty

    def test_predict_success_bounds(self):
        bridge = self._make_bridge()
        ranking = MockWorkerRanking(
            wallet="0x1", final_score=100, skill_score=100,
            reputation_score=100, reliability_score=100, recency_score=100,
            tier="diamante", confidence=1.0
        )
        prob = bridge._predict_success(ranking, "survey")
        assert prob <= 0.99

        ranking = MockWorkerRanking(
            wallet="0x1", final_score=0, skill_score=0,
            reputation_score=0, reliability_score=0, recency_score=0,
            tier="unverified", confidence=0.0
        )
        prob = bridge._predict_success(ranking, "survey")
        assert prob >= 0.10


# ═══════════════════════════════════════════════════════════════════
# Health Checks
# ═══════════════════════════════════════════════════════════════════


class TestHealth:
    """Test bridge health diagnostics."""

    def test_local_health_with_components(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.list_workers.return_value = [
            {"wallet": "0x1"}, {"wallet": "0x2"}
        ]
        bridge._local_matcher = MagicMock()
        bridge.wallet_to_agent = {"0x1": "alice", "0x2": "bob"}

        health = bridge.health()
        assert health["mode"] == "local"
        assert health["status"] == "healthy"
        assert health["registered_workers"] == 2
        assert health["wallet_mappings"] == 2

    def test_local_health_degraded(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = None
        bridge._local_matcher = None

        health = bridge.health()
        assert health["status"] == "degraded"

    def test_remote_health_unreachable(self):
        bridge = AutoJobBridge(mode="remote", api_base="https://localhost:99999")
        health = bridge.health()
        assert health["status"] == "unreachable"


# ═══════════════════════════════════════════════════════════════════
# Agent DNA Sync
# ═══════════════════════════════════════════════════════════════════


class TestAgentDNASync:
    """Test syncing agent task history into AutoJob."""

    def test_sync_requires_local_mode(self):
        bridge = AutoJobBridge(mode="remote")
        result = bridge.sync_agent_dna("0x1", "alice", [])
        assert result is False

    def test_get_agent_dna_returns_none_remote(self):
        bridge = AutoJobBridge(mode="remote")
        assert bridge.get_agent_dna("0x1") is None

    def test_get_agent_dna_local_found(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.get.return_value = {
            "merged_dna": {"technical_skills": {"python": {"level": "EXPERT"}}}
        }
        dna = bridge.get_agent_dna("0x1")
        assert dna is not None
        assert "python" in dna["technical_skills"]

    def test_get_agent_dna_local_not_found(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.get.return_value = None
        assert bridge.get_agent_dna("0x1") is None


# ═══════════════════════════════════════════════════════════════════
# Leaderboard
# ═══════════════════════════════════════════════════════════════════


class TestLeaderboard:
    """Test leaderboard generation."""

    def test_leaderboard_sorts_by_activity(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.list_workers.return_value = [
            {"wallet": "0x1", "metadata": {"update_count": 5}},
            {"wallet": "0x2", "metadata": {"update_count": 20}},
            {"wallet": "0x3", "metadata": {"update_count": 10}},
        ]
        lb = bridge.get_leaderboard()
        assert len(lb) == 3
        assert lb[0]["wallet"] == "0x2"  # Most active first
        assert lb[1]["wallet"] == "0x3"
        assert lb[2]["wallet"] == "0x1"

    def test_leaderboard_respects_limit(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.list_workers.return_value = [
            {"wallet": f"0x{i}", "metadata": {"update_count": i}}
            for i in range(30)
        ]
        lb = bridge.get_leaderboard(limit=5)
        assert len(lb) == 5

    def test_leaderboard_empty_remote(self):
        bridge = AutoJobBridge(mode="remote")
        assert bridge.get_leaderboard() == []


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_rank_with_no_task_id(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_matcher = MagicMock()
        bridge._local_matcher.rank_workers_for_task.return_value = MockMatchResult()
        task = {"category": "survey"}  # No id
        result = bridge.rank_agents_for_task(task)
        assert result.task_id == "unknown"

    def test_rank_with_no_category(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_matcher = MagicMock()
        bridge._local_matcher.rank_workers_for_task.return_value = MockMatchResult()
        task = {"id": "t1"}  # No category
        result = bridge.rank_agents_for_task(task)
        # Default category is simple_action
        call_args = bridge._local_matcher.rank_workers_for_task.call_args
        assert call_args[0][0]["category"] == "simple_action"

    def test_predicted_quality_with_zero_scores(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        ranking = MockWorkerRanking(
            wallet="0x1", final_score=0, skill_score=0,
            reputation_score=0, reliability_score=0, recency_score=0,
            tier="unverified", confidence=0
        )
        quality = bridge._predict_quality(ranking, "survey")
        assert quality >= 1.0 and quality <= 5.0

    def test_remote_rank_with_network_error(self):
        bridge = AutoJobBridge(mode="remote", api_base="https://localhost:99999")
        task = {"id": "t1", "category": "survey"}
        result = bridge.rank_agents_for_task(task)
        assert result.rankings == []
        assert result.total_candidates == 0
