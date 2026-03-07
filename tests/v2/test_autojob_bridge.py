"""
Tests for lib/autojob_bridge.py — AutoJob Intelligence Bridge

Covers:
  - Data structures (AgentRanking, BridgeResult)
  - KK_TO_AUTOJOB_CATEGORY mapping
  - AutoJobBridge construction (local, remote, fallback)
  - rank_agents_for_task (local mode with mocked matcher)
  - rank_agents_for_task (remote mode with mocked HTTP)
  - _predict_quality (skill × reliability → 3.0-5.0 range)
  - _predict_success (weighted combo, cold start penalty)
  - sync_agent_dna (local only, task history → DNA)
  - get_agent_dna, get_leaderboard
  - health check (local + remote modes)
  - Error handling: API failures, import failures, empty results
"""

import json
import sys
from dataclasses import fields
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from lib.autojob_bridge import (
    AgentRanking,
    AutoJobBridge,
    BridgeResult,
    KK_TO_AUTOJOB_CATEGORY,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ranking():
    """Create a mock WorkerRanking (AutoJob format)."""
    wr = MagicMock()
    wr.wallet = "0xABCDEF1234567890"
    wr.final_score = 85.0
    wr.skill_score = 80.0
    wr.reputation_score = 90.0
    wr.reliability_score = 88.0
    wr.recency_score = 75.0
    wr.tier = "oro"
    wr.confidence = 0.8
    wr.match_explanation = "Strong match: Python + DeFi"
    wr.categories_worked = ["technical_task", "data_collection"]
    wr.total_tasks = 15
    wr.agent_id = 42
    return wr


@pytest.fixture
def mock_match_result(mock_ranking):
    """Create a mock match result from AutoJob."""
    result = MagicMock()
    result.rankings = [mock_ranking]
    result.total_candidates = 10
    result.qualified_candidates = 3
    return result


@pytest.fixture
def sample_task():
    """Sample EM task for ranking."""
    return {
        "id": "task-123",
        "title": "Analyze smart contract",
        "category": "technical_task",
        "bounty_usd": 0.50,
        "instructions": "Review Solidity code for vulnerabilities",
    }


@pytest.fixture
def bridge_remote():
    """Create a remote-mode bridge (no local imports)."""
    return AutoJobBridge(mode="remote", api_base="https://autojob.test")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


class TestDataStructures:
    def test_agent_ranking_fields(self):
        ranking = AgentRanking(
            agent_name="kk-agent",
            wallet="0x123",
            final_score=85.0,
            skill_score=80.0,
            reputation_score=90.0,
            reliability_score=88.0,
            recency_score=75.0,
            tier="oro",
            confidence=0.8,
            explanation="Good match",
            predicted_quality=4.2,
            predicted_success=0.85,
        )
        assert ranking.agent_name == "kk-agent"
        assert ranking.final_score == 85.0
        assert ranking.tier == "oro"
        assert ranking.categories_worked == []
        assert ranking.total_tasks == 0
        assert ranking.agent_id is None

    def test_agent_ranking_with_optional_fields(self):
        ranking = AgentRanking(
            agent_name="test",
            wallet="0x",
            final_score=50.0,
            skill_score=40.0,
            reputation_score=60.0,
            reliability_score=55.0,
            recency_score=30.0,
            tier="bronce",
            confidence=0.3,
            explanation="New agent",
            predicted_quality=3.0,
            predicted_success=0.5,
            categories_worked=["survey"],
            total_tasks=2,
            agent_id=99,
        )
        assert ranking.categories_worked == ["survey"]
        assert ranking.total_tasks == 2
        assert ranking.agent_id == 99

    def test_bridge_result_defaults(self):
        result = BridgeResult(
            task_id="t1",
            task_category="simple_action",
            rankings=[],
            total_candidates=0,
            qualified_candidates=0,
        )
        assert result.best_match is None
        assert result.match_time_ms == 0.0
        assert result.mode == "local"
        assert result.autojob_version == ""


# ---------------------------------------------------------------------------
# Category Mapping
# ---------------------------------------------------------------------------


class TestCategoryMapping:
    def test_standard_categories(self):
        assert KK_TO_AUTOJOB_CATEGORY["physical_verification"] == "physical_verification"
        assert KK_TO_AUTOJOB_CATEGORY["data_collection"] == "data_collection"
        assert KK_TO_AUTOJOB_CATEGORY["simple_action"] == "simple_action"

    def test_kk_specific_mappings(self):
        assert KK_TO_AUTOJOB_CATEGORY["code_review"] == "technical_task"
        assert KK_TO_AUTOJOB_CATEGORY["research"] == "data_collection"
        assert KK_TO_AUTOJOB_CATEGORY["writing"] == "content_creation"
        assert KK_TO_AUTOJOB_CATEGORY["analysis"] == "data_collection"


# ---------------------------------------------------------------------------
# Bridge Construction
# ---------------------------------------------------------------------------


class TestBridgeConstruction:
    def test_remote_mode(self):
        bridge = AutoJobBridge(mode="remote", api_base="https://api.test")
        assert bridge.mode == "remote"
        assert bridge.api_base == "https://api.test"

    def test_remote_strips_trailing_slash(self):
        bridge = AutoJobBridge(mode="remote", api_base="https://api.test/")
        assert bridge.api_base == "https://api.test"

    def test_wallet_to_agent_mapping(self):
        mapping = {"0xABC": "alice", "0xDEF": "bob"}
        bridge = AutoJobBridge(mode="remote", wallet_to_agent=mapping)
        assert bridge.wallet_to_agent == mapping

    def test_local_mode_fallback_on_import_error(self):
        """Falls back to remote if local imports fail."""
        bridge = AutoJobBridge(mode="local", autojob_path="/nonexistent/path")
        assert bridge.mode == "remote"  # falls back

    def test_default_empty_wallet_mapping(self):
        bridge = AutoJobBridge(mode="remote")
        assert bridge.wallet_to_agent == {}


# ---------------------------------------------------------------------------
# Prediction Helpers
# ---------------------------------------------------------------------------


class TestPredictions:
    def test_predict_quality_high_scores(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 90.0
        ranking.reliability_score = 95.0
        quality = bridge._predict_quality(ranking, "technical_task")
        assert 4.0 <= quality <= 5.0

    def test_predict_quality_low_scores(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 10.0
        ranking.reliability_score = 10.0
        quality = bridge._predict_quality(ranking, "simple_action")
        assert 3.0 <= quality <= 3.5

    def test_predict_quality_clamped_to_range(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 100.0
        ranking.reliability_score = 100.0
        quality = bridge._predict_quality(ranking, "technical_task")
        assert quality <= 5.0

    def test_predict_quality_min_bound(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 0.0
        ranking.reliability_score = 0.0
        quality = bridge._predict_quality(ranking, "simple_action")
        assert quality >= 1.0

    def test_predict_success_high_scores(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 90.0
        ranking.reliability_score = 95.0
        ranking.reputation_score = 85.0
        ranking.confidence = 0.9
        prob = bridge._predict_success(ranking, "technical_task")
        assert 0.80 <= prob <= 0.99

    def test_predict_success_cold_start_penalty(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 80.0
        ranking.reliability_score = 80.0
        ranking.reputation_score = 80.0
        ranking.confidence = 0.2  # very low confidence

        prob = bridge._predict_success(ranking, "simple_action")
        # Should have 30% penalty applied
        assert prob < 0.6

    def test_predict_success_no_penalty_high_confidence(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 80.0
        ranking.reliability_score = 80.0
        ranking.reputation_score = 80.0
        ranking.confidence = 0.5  # above 0.3 threshold

        prob = bridge._predict_success(ranking, "simple_action")
        assert prob >= 0.6  # no penalty

    def test_predict_success_clamped_range(self):
        bridge = AutoJobBridge(mode="remote")
        ranking = MagicMock()
        ranking.skill_score = 100.0
        ranking.reliability_score = 100.0
        ranking.reputation_score = 100.0
        ranking.confidence = 1.0
        prob = bridge._predict_success(ranking, "technical_task")
        assert prob <= 0.99

        ranking.skill_score = 0.0
        ranking.reliability_score = 0.0
        ranking.reputation_score = 0.0
        ranking.confidence = 0.0
        prob = bridge._predict_success(ranking, "simple_action")
        assert prob >= 0.10


# ---------------------------------------------------------------------------
# rank_agents_for_task — Remote mode
# ---------------------------------------------------------------------------


class TestRankRemote:
    def test_remote_api_success(self, bridge_remote, sample_task):
        response_data = json.dumps({
            "rankings": [
                {
                    "wallet": "0xABCD",
                    "score": 85.0,
                    "skill_score": 80.0,
                    "reputation_score": 90.0,
                    "reliability_score": 88.0,
                    "recency_score": 75.0,
                    "tier": "oro",
                    "confidence": 0.8,
                    "explanation": "Strong match",
                    "predicted_quality": 4.2,
                    "predicted_success": 0.85,
                    "categories_worked": ["technical_task"],
                    "total_tasks": 10,
                    "agent_id": 42,
                }
            ],
            "total_candidates": 20,
            "qualified_candidates": 5,
            "version": "1.2.0",
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("lib.autojob_bridge.urllib.request.urlopen", return_value=mock_response):
            result = bridge_remote.rank_agents_for_task(sample_task)
            assert result.task_category == "technical_task"
            assert len(result.rankings) == 1
            assert result.rankings[0].wallet == "0xABCD"
            assert result.rankings[0].final_score == 85.0
            assert result.total_candidates == 20
            assert result.mode == "remote"
            assert result.autojob_version == "1.2.0"
            assert result.best_match is not None

    def test_remote_api_failure(self, bridge_remote, sample_task):
        with patch("lib.autojob_bridge.urllib.request.urlopen", side_effect=Exception("connection refused")):
            result = bridge_remote.rank_agents_for_task(sample_task)
            assert result.rankings == []
            assert result.total_candidates == 0
            assert result.mode == "remote"

    def test_remote_wallet_to_agent_mapping(self, sample_task):
        bridge = AutoJobBridge(
            mode="remote",
            wallet_to_agent={"0xABCD": "alice-agent"},
        )
        response_data = json.dumps({
            "rankings": [{"wallet": "0xABCD", "score": 80}],
            "total_candidates": 1,
            "qualified_candidates": 1,
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("lib.autojob_bridge.urllib.request.urlopen", return_value=mock_response):
            result = bridge.rank_agents_for_task(sample_task)
            assert result.rankings[0].agent_name == "alice-agent"

    def test_remote_unknown_wallet(self, bridge_remote, sample_task):
        response_data = json.dumps({
            "rankings": [{"wallet": "0xUNKNOWN123456789", "score": 50}],
            "total_candidates": 1,
            "qualified_candidates": 1,
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("lib.autojob_bridge.urllib.request.urlopen", return_value=mock_response):
            result = bridge_remote.rank_agents_for_task(sample_task)
            assert result.rankings[0].agent_name == "0xUNKNOWN1..."

    def test_remote_category_mapping(self, bridge_remote):
        task = {"id": "t1", "category": "code_review"}
        with patch("lib.autojob_bridge.urllib.request.urlopen", side_effect=Exception("test")):
            result = bridge_remote.rank_agents_for_task(task)
            assert result.task_category == "technical_task"  # mapped

    def test_remote_no_rankings(self, bridge_remote, sample_task):
        response_data = json.dumps({
            "rankings": [],
            "total_candidates": 0,
            "qualified_candidates": 0,
        }).encode()

        mock_response = MagicMock()
        mock_response.read.return_value = response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("lib.autojob_bridge.urllib.request.urlopen", return_value=mock_response):
            result = bridge_remote.rank_agents_for_task(sample_task)
            assert result.best_match is None
            assert result.rankings == []

    def test_match_time_ms_tracked(self, bridge_remote, sample_task):
        with patch("lib.autojob_bridge.urllib.request.urlopen", side_effect=Exception("fail")):
            result = bridge_remote.rank_agents_for_task(sample_task)
            assert result.match_time_ms >= 0


# ---------------------------------------------------------------------------
# rank_agents_for_task — Local mode
# ---------------------------------------------------------------------------


class TestRankLocal:
    def test_local_ranking(self, mock_ranking, mock_match_result, sample_task):
        bridge = AutoJobBridge(mode="remote")  # start remote
        bridge.mode = "local"  # override
        bridge._local_matcher = MagicMock()
        bridge._local_matcher.rank_workers_for_task.return_value = mock_match_result
        bridge.wallet_to_agent = {"0xABCDEF1234567890": "alice"}

        result = bridge.rank_agents_for_task(sample_task)
        assert result.mode == "local"
        assert len(result.rankings) == 1
        assert result.rankings[0].agent_name == "alice"
        assert result.rankings[0].final_score == 85.0
        assert result.best_match is not None

    def test_local_empty_result(self, sample_task):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_matcher = MagicMock()
        empty_result = MagicMock()
        empty_result.rankings = []
        empty_result.total_candidates = 0
        empty_result.qualified_candidates = 0
        bridge._local_matcher.rank_workers_for_task.return_value = empty_result

        result = bridge.rank_agents_for_task(sample_task)
        assert result.best_match is None
        assert result.rankings == []


# ---------------------------------------------------------------------------
# sync_agent_dna
# ---------------------------------------------------------------------------


class TestSyncAgentDNA:
    def test_sync_not_local_mode(self):
        bridge = AutoJobBridge(mode="remote")
        result = bridge.sync_agent_dna("0x123", "test", [])
        assert result is False

    def test_sync_no_registry(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = None
        result = bridge.sync_agent_dna("0x123", "test", [])
        assert result is False


# ---------------------------------------------------------------------------
# get_agent_dna / get_leaderboard
# ---------------------------------------------------------------------------


class TestAccessors:
    def test_get_agent_dna_local(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.get.return_value = {"merged_dna": {"skills": ["Python"]}}
        result = bridge.get_agent_dna("0x123")
        assert result == {"skills": ["Python"]}

    def test_get_agent_dna_not_found(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.get.return_value = None
        result = bridge.get_agent_dna("0xUNKNOWN")
        assert result is None

    def test_get_agent_dna_remote_returns_none(self):
        bridge = AutoJobBridge(mode="remote")
        result = bridge.get_agent_dna("0x123")
        assert result is None

    def test_get_leaderboard_local(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.list_workers.return_value = [
            {"wallet": "0x1", "metadata": {"update_count": 10}},
            {"wallet": "0x2", "metadata": {"update_count": 25}},
            {"wallet": "0x3", "metadata": {"update_count": 5}},
        ]
        result = bridge.get_leaderboard(limit=2)
        assert len(result) == 2
        assert result[0]["metadata"]["update_count"] == 25  # sorted desc

    def test_get_leaderboard_remote_returns_empty(self):
        bridge = AutoJobBridge(mode="remote")
        result = bridge.get_leaderboard()
        assert result == []


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_local_healthy(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = MagicMock()
        bridge._local_registry.list_workers.return_value = [{"w": 1}, {"w": 2}]
        bridge._local_matcher = MagicMock()
        bridge.wallet_to_agent = {"0x1": "a", "0x2": "b"}

        health = bridge.health()
        assert health["mode"] == "local"
        assert health["status"] == "healthy"
        assert health["registered_workers"] == 2
        assert health["wallet_mappings"] == 2

    def test_health_local_degraded(self):
        bridge = AutoJobBridge(mode="remote")
        bridge.mode = "local"
        bridge._local_registry = None
        bridge._local_matcher = None

        health = bridge.health()
        assert health["status"] == "degraded"

    def test_health_remote_success(self):
        bridge = AutoJobBridge(mode="remote", api_base="https://api.test")
        response_data = json.dumps({"status": "ok", "sources": 3}).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("lib.autojob_bridge.urllib.request.urlopen", return_value=mock_response):
            health = bridge.health()
            assert health["status"] == "healthy"
            assert health["api_status"] == "ok"

    def test_health_remote_unreachable(self):
        bridge = AutoJobBridge(mode="remote", api_base="https://api.test")
        with patch("lib.autojob_bridge.urllib.request.urlopen", side_effect=Exception("timeout")):
            health = bridge.health()
            assert health["status"] == "unreachable"
            assert "timeout" in health["error"]
