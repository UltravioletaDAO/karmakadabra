"""
Tests for reputation_bridge.py — Unified Reputation Scoring

Covers:
  - On-chain score computation (time-weighted seal aggregation)
  - Off-chain reputation extraction from performance data
  - Transactional reputation from API data
  - Unified reputation computation with confidence weighting
  - Tier classification
  - Coordinator integration (reputation boost)
  - Batch operations (swarm reputation, ranking)
  - Persistence (save/load snapshots)
  - Trend analysis
  - Leaderboard generation
  - Edge cases (empty data, single source, extreme values)
"""

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.reputation_bridge import (
    DEFAULT_WEIGHTS,
    QUADRANTS,
    SEAL_TYPES,
    DataSource,
    OffChainReputation,
    OnChainReputation,
    ReputationTier,
    SealScore,
    TransactionalReputation,
    UnifiedReputation,
    classify_tier,
    compute_on_chain_score,
    compute_swarm_reputation,
    compute_unified_reputation,
    extract_off_chain_reputation,
    extract_transactional_reputation,
    format_leaderboard_text,
    generate_leaderboard,
    compute_reputation_trend,
    load_latest_snapshot,
    load_reputation_snapshot,
    rank_by_reputation,
    reputation_boost_for_matching,
    save_reputation_snapshot,
    tier_emoji,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 2, 23, 0, 0, 0, tzinfo=timezone.utc)


def make_seal(
    seal_type: str = "SKILLFUL",
    quadrant: str = "A2H",
    score: int = 80,
    evaluator: str = "0xEval1",
    days_ago: float = 0,
    seal_id: int = 1,
) -> SealScore:
    """Helper to create a SealScore with relative timestamp."""
    ts = NOW - timedelta(days=days_ago)
    return SealScore(
        seal_type=seal_type,
        quadrant=quadrant,
        score=score,
        evaluator=evaluator,
        timestamp=ts.isoformat(),
        seal_id=seal_id,
    )


def make_performance_data(
    tasks_completed: int = 10,
    tasks_attempted: int = 12,
    avg_rating: float = 75.0,
    categories: dict | None = None,
    chains: dict | None = None,
    earned: float = 1.50,
) -> dict:
    """Helper to create performance tracker data dict."""
    return {
        "tasks_completed": tasks_completed,
        "tasks_attempted": tasks_attempted,
        "avg_rating_received": avg_rating,
        "reliability_score": tasks_completed / max(tasks_attempted, 1) * 0.6 + 0.4 * (avg_rating / 100),
        "category_completions": categories or {"simple_action": 5, "knowledge_access": 3},
        "category_attempts": categories or {"simple_action": 6, "knowledge_access": 3},
        "chain_tasks": chains or {"base": 8, "polygon": 4},
        "total_earned_usd": earned,
    }


def make_api_data(
    avg_rating: float = 80.0,
    total_ratings: int = 5,
    agent_id: int = 2106,
) -> dict:
    """Helper to create EM API reputation data dict."""
    return {
        "agent_id": agent_id,
        "avg_rating_received": avg_rating,
        "total_ratings_received": total_ratings,
        "avg_rating_given": 70.0,
        "total_ratings_given": 3,
        "recent_ratings": [
            {"score": 85, "from": "worker-1"},
            {"score": 75, "from": "worker-2"},
        ],
    }


# ---------------------------------------------------------------------------
# Tier Classification Tests
# ---------------------------------------------------------------------------

class TestTierClassification:
    def test_diamante_threshold(self):
        assert classify_tier(81) == ReputationTier.DIAMANTE
        assert classify_tier(100) == ReputationTier.DIAMANTE
        assert classify_tier(95.5) == ReputationTier.DIAMANTE

    def test_oro_threshold(self):
        assert classify_tier(61) == ReputationTier.ORO
        assert classify_tier(80) == ReputationTier.ORO
        assert classify_tier(70) == ReputationTier.ORO

    def test_plata_threshold(self):
        assert classify_tier(31) == ReputationTier.PLATA
        assert classify_tier(60) == ReputationTier.PLATA
        assert classify_tier(50) == ReputationTier.PLATA

    def test_bronce_threshold(self):
        assert classify_tier(0) == ReputationTier.BRONCE
        assert classify_tier(30) == ReputationTier.BRONCE
        assert classify_tier(15) == ReputationTier.BRONCE

    def test_negative_score(self):
        assert classify_tier(-10) == ReputationTier.UNKNOWN

    def test_tier_emoji(self):
        assert tier_emoji(ReputationTier.DIAMANTE) == "💎"
        assert tier_emoji(ReputationTier.ORO) == "🥇"
        assert tier_emoji(ReputationTier.PLATA) == "🥈"
        assert tier_emoji(ReputationTier.BRONCE) == "🥉"
        assert tier_emoji(ReputationTier.UNKNOWN) == "❓"

    def test_boundary_values(self):
        """Test exact boundary values between tiers."""
        assert classify_tier(80.9) == ReputationTier.ORO
        assert classify_tier(81.0) == ReputationTier.DIAMANTE
        assert classify_tier(60.9) == ReputationTier.PLATA
        assert classify_tier(61.0) == ReputationTier.ORO
        assert classify_tier(30.9) == ReputationTier.BRONCE
        assert classify_tier(31.0) == ReputationTier.PLATA


# ---------------------------------------------------------------------------
# On-Chain Score Computation Tests
# ---------------------------------------------------------------------------

class TestOnChainScore:
    def test_empty_seals(self):
        rep = compute_on_chain_score([], now=NOW)
        assert rep.composite_score == 50.0
        assert rep.confidence == 0.0
        assert rep.seal_count == 0

    def test_single_seal(self):
        seals = [make_seal(score=85)]
        rep = compute_on_chain_score(seals, now=NOW)
        assert rep.composite_score == pytest.approx(85.0, abs=1.0)
        assert rep.confidence > 0.0
        assert rep.seal_count == 1
        assert "SKILLFUL" in rep.type_averages

    def test_multiple_seal_types(self):
        seals = [
            make_seal(seal_type="SKILLFUL", score=90),
            make_seal(seal_type="RELIABLE", score=70),
            make_seal(seal_type="THOROUGH", score=80),
        ]
        rep = compute_on_chain_score(seals, now=NOW)
        # Average of type averages: (90 + 70 + 80) / 3 = 80
        assert rep.composite_score == pytest.approx(80.0, abs=1.0)
        assert len(rep.type_averages) == 3

    def test_time_decay_recent_seals(self):
        """Recent seals should have more weight."""
        seals = [
            make_seal(seal_type="SKILLFUL", score=90, days_ago=0),    # Fresh
            make_seal(seal_type="SKILLFUL", score=30, days_ago=180),  # Old (2x half-life)
        ]
        rep = compute_on_chain_score(seals, time_decay_days=90, now=NOW)
        # Recent seal (weight ~1.0) should dominate over old seal (weight ~0.25)
        assert rep.type_averages["SKILLFUL"] > 70  # Closer to 90 than 30

    def test_time_decay_old_seals(self):
        """Very old seals should have minimal weight."""
        seals = [
            make_seal(seal_type="SKILLFUL", score=90, days_ago=365),
        ]
        rep = compute_on_chain_score(seals, time_decay_days=90, now=NOW)
        # Score is still 90 (only one seal), but confidence should reflect age
        assert rep.composite_score == pytest.approx(90.0, abs=0.5)

    def test_quadrant_aggregation(self):
        seals = [
            make_seal(quadrant="A2H", score=80),
            make_seal(quadrant="H2A", score=60),
            make_seal(quadrant="A2A", score=90),
        ]
        rep = compute_on_chain_score(seals, now=NOW)
        assert "A2H" in rep.quadrant_averages
        assert "H2A" in rep.quadrant_averages
        assert "A2A" in rep.quadrant_averages

    def test_confidence_scales_with_count(self):
        """More seals = higher confidence."""
        one_seal = compute_on_chain_score([make_seal()], now=NOW)
        five_seals = compute_on_chain_score(
            [make_seal(seal_id=i) for i in range(5)], now=NOW
        )
        twenty_seals = compute_on_chain_score(
            [make_seal(seal_id=i) for i in range(20)], now=NOW
        )
        assert one_seal.confidence < five_seals.confidence < twenty_seals.confidence

    def test_normalized_score_clamped(self):
        seals = [make_seal(score=100)]
        rep = compute_on_chain_score(seals, now=NOW)
        assert 0 <= rep.normalized_score <= 100

    def test_all_seal_types_present(self):
        """Verify all 13 seal types are defined."""
        assert len(SEAL_TYPES) == 13
        assert "SKILLFUL" in SEAL_TYPES
        assert "CREATIVE" in SEAL_TYPES
        assert "FRIENDLY" in SEAL_TYPES

    def test_invalid_timestamp_treated_as_fresh(self):
        seal = SealScore(
            seal_type="SKILLFUL", quadrant="A2H", score=75,
            evaluator="0x1", timestamp="not-a-date", seal_id=1,
        )
        rep = compute_on_chain_score([seal], now=NOW)
        assert rep.composite_score == pytest.approx(75.0, abs=0.5)


# ---------------------------------------------------------------------------
# Off-Chain Reputation Tests
# ---------------------------------------------------------------------------

class TestOffChainReputation:
    def test_empty_data(self):
        rep = extract_off_chain_reputation("kk-agent-1")
        assert rep.agent_name == "kk-agent-1"
        assert rep.completion_rate == 0.5
        # 0.50 * 0.5 * 100 + 0.30 * 50 + 0.20 * 0 = 25 + 15 + 0 = 40
        assert rep.normalized_score == pytest.approx(40.0, abs=2)

    def test_good_performance(self):
        data = make_performance_data(tasks_completed=20, tasks_attempted=22, avg_rating=85)
        rep = extract_off_chain_reputation("kk-agent-1", data)
        assert rep.completion_rate == pytest.approx(20 / 22, abs=0.01)
        assert rep.avg_rating == 85.0
        assert rep.normalized_score > 60  # Should be in Oro range

    def test_poor_performance(self):
        data = make_performance_data(tasks_completed=2, tasks_attempted=10, avg_rating=30)
        rep = extract_off_chain_reputation("kk-agent-1", data)
        assert rep.completion_rate == pytest.approx(0.2, abs=0.01)
        assert rep.normalized_score < 40  # Should be in Bronce range

    def test_category_strengths(self):
        data = make_performance_data()
        data["category_completions"] = {"simple_action": 8, "knowledge_access": 2}
        data["category_attempts"] = {"simple_action": 10, "knowledge_access": 5}
        rep = extract_off_chain_reputation("kk-agent-1", data)
        assert rep.category_strengths["simple_action"] == pytest.approx(0.8, abs=0.01)
        assert rep.category_strengths["knowledge_access"] == pytest.approx(0.4, abs=0.01)

    def test_chain_experience(self):
        data = make_performance_data()
        data["chain_tasks"] = {"base": 10, "polygon": 1}
        rep = extract_off_chain_reputation("kk-agent-1", data)
        assert rep.chain_experience["base"] > rep.chain_experience["polygon"]

    def test_confidence_zero_for_no_tasks(self):
        rep = extract_off_chain_reputation("kk-agent-1", {"tasks_attempted": 0})
        assert rep.confidence == 0.0

    def test_confidence_grows_with_tasks(self):
        low = extract_off_chain_reputation("a", make_performance_data(tasks_completed=1, tasks_attempted=1))
        mid = extract_off_chain_reputation("b", make_performance_data(tasks_completed=10, tasks_attempted=12))
        high = extract_off_chain_reputation("c", make_performance_data(tasks_completed=40, tasks_attempted=50))
        assert low.confidence < mid.confidence < high.confidence

    def test_none_data(self):
        rep = extract_off_chain_reputation("agent", None)
        assert rep.tasks_completed == 0
        assert rep.normalized_score == pytest.approx(40.0, abs=2)


# ---------------------------------------------------------------------------
# Transactional Reputation Tests
# ---------------------------------------------------------------------------

class TestTransactionalReputation:
    def test_empty_data(self):
        rep = extract_transactional_reputation("agent")
        assert rep.normalized_score == 50.0
        assert rep.confidence == 0.0

    def test_good_ratings(self):
        data = make_api_data(avg_rating=90, total_ratings=10)
        rep = extract_transactional_reputation("agent", data)
        assert rep.normalized_score == 90.0
        assert rep.confidence > 0.5

    def test_low_ratings(self):
        data = make_api_data(avg_rating=25, total_ratings=3)
        rep = extract_transactional_reputation("agent", data)
        assert rep.normalized_score == 25.0

    def test_confidence_scales_with_count(self):
        few = extract_transactional_reputation("a", make_api_data(total_ratings=1))
        many = extract_transactional_reputation("b", make_api_data(total_ratings=15))
        assert few.confidence < many.confidence

    def test_agent_id_extraction(self):
        data = make_api_data(agent_id=18775)
        rep = extract_transactional_reputation("agent", data)
        assert rep.agent_id == 18775

    def test_recent_ratings_preserved(self):
        data = make_api_data()
        rep = extract_transactional_reputation("agent", data)
        assert len(rep.recent_ratings) == 2


# ---------------------------------------------------------------------------
# Unified Reputation Tests
# ---------------------------------------------------------------------------

class TestUnifiedReputation:
    def test_no_sources(self):
        rep = compute_unified_reputation("agent")
        assert rep.composite_score == 50.0
        assert rep.tier == ReputationTier.PLATA
        assert rep.effective_confidence == 0.0
        assert len(rep.sources_available) == 0

    def test_single_source_on_chain(self):
        on_chain = compute_on_chain_score([make_seal(score=85)], now=NOW)
        rep = compute_unified_reputation("agent", on_chain=on_chain)
        assert rep.composite_score == pytest.approx(85.0, abs=2.0)
        assert "on_chain" in rep.sources_available
        assert len(rep.sources_available) == 1

    def test_single_source_off_chain(self):
        off_chain = extract_off_chain_reputation("agent", make_performance_data())
        rep = compute_unified_reputation("agent", off_chain=off_chain)
        assert rep.composite_score > 0
        assert "off_chain" in rep.sources_available

    def test_single_source_transactional(self):
        tx = extract_transactional_reputation("agent", make_api_data(avg_rating=90))
        rep = compute_unified_reputation("agent", transactional=tx)
        assert rep.composite_score == pytest.approx(90.0, abs=2.0)
        assert "transactional" in rep.sources_available

    def test_all_three_sources(self):
        on_chain = compute_on_chain_score([make_seal(score=80)], now=NOW)
        off_chain = extract_off_chain_reputation("agent", make_performance_data(avg_rating=70))
        tx = extract_transactional_reputation("agent", make_api_data(avg_rating=90))

        rep = compute_unified_reputation("agent", on_chain=on_chain, off_chain=off_chain, transactional=tx)
        assert len(rep.sources_available) == 3
        assert 60 < rep.composite_score < 95  # Blend of 80, ~65, 90
        assert rep.effective_confidence > 0

    def test_custom_weights(self):
        on_chain = compute_on_chain_score([make_seal(score=100)], now=NOW)
        off_chain = extract_off_chain_reputation("agent", make_performance_data(avg_rating=0))
        tx = extract_transactional_reputation("agent", make_api_data(avg_rating=0, total_ratings=1))

        # Heavily weight on-chain
        heavy_on_chain = compute_unified_reputation(
            "agent", on_chain=on_chain, off_chain=off_chain, transactional=tx,
            weights={"on_chain": 0.8, "off_chain": 0.1, "transactional": 0.1},
        )
        # Heavily weight off-chain
        heavy_off_chain = compute_unified_reputation(
            "agent", on_chain=on_chain, off_chain=off_chain, transactional=tx,
            weights={"on_chain": 0.1, "off_chain": 0.8, "transactional": 0.1},
        )
        assert heavy_on_chain.composite_score > heavy_off_chain.composite_score

    def test_confidence_boost_effect(self):
        """High-confidence sources should have more influence when confidence_boost=True."""
        # On-chain with 20 seals (high confidence)
        seals = [make_seal(score=90, seal_id=i) for i in range(20)]
        on_chain = compute_on_chain_score(seals, now=NOW)

        # Off-chain with 1 task (low confidence)
        off_chain = extract_off_chain_reputation("agent", make_performance_data(
            tasks_completed=1, tasks_attempted=1, avg_rating=20
        ))

        with_boost = compute_unified_reputation(
            "agent", on_chain=on_chain, off_chain=off_chain, confidence_boost=True,
        )
        without_boost = compute_unified_reputation(
            "agent", on_chain=on_chain, off_chain=off_chain, confidence_boost=False,
        )
        # With boost, high-confidence on-chain should pull score higher
        assert with_boost.composite_score >= without_boost.composite_score - 5

    def test_tier_assigned(self):
        on_chain = compute_on_chain_score([make_seal(score=95)], now=NOW)
        rep = compute_unified_reputation("agent", on_chain=on_chain)
        assert rep.tier == ReputationTier.DIAMANTE

    def test_to_dict_completeness(self):
        on_chain = compute_on_chain_score([make_seal(score=80)], now=NOW)
        off_chain = extract_off_chain_reputation("agent", make_performance_data())
        tx = extract_transactional_reputation("agent", make_api_data())

        rep = compute_unified_reputation("agent", on_chain=on_chain, off_chain=off_chain, transactional=tx)
        d = rep.to_dict()

        assert "composite_score" in d
        assert "tier" in d
        assert "confidence" in d
        assert "layers" in d
        assert "on_chain" in d["layers"]
        assert "off_chain" in d["layers"]
        assert "transactional" in d["layers"]
        assert "weights_used" in d
        assert "sources_available" in d

    def test_agent_address_propagation(self):
        on_chain = OnChainReputation(
            agent_address="0xABC123", agent_id=42, composite_score=80, confidence=0.5
        )
        rep = compute_unified_reputation("agent", on_chain=on_chain)
        assert rep.agent_address == "0xABC123"
        assert rep.agent_id == 42


# ---------------------------------------------------------------------------
# Coordinator Integration Tests
# ---------------------------------------------------------------------------

class TestReputationBoost:
    def test_neutral_reputation_no_change(self):
        rep = UnifiedReputation(
            agent_name="agent", composite_score=50.0, effective_confidence=0.5
        )
        boosted = reputation_boost_for_matching(rep, base_match_score=0.7)
        # Should be close to original since reputation is neutral
        assert abs(boosted - 0.7) < 0.1

    def test_high_reputation_boosts_score(self):
        rep = UnifiedReputation(
            agent_name="agent", composite_score=95.0, effective_confidence=0.9
        )
        boosted = reputation_boost_for_matching(rep, base_match_score=0.5)
        assert boosted > 0.5  # Should be boosted

    def test_low_reputation_reduces_score(self):
        rep = UnifiedReputation(
            agent_name="agent", composite_score=10.0, effective_confidence=0.9
        )
        boosted = reputation_boost_for_matching(rep, base_match_score=0.8)
        assert boosted < 0.8  # Should be reduced

    def test_low_confidence_dampens_effect(self):
        high_conf = UnifiedReputation(
            agent_name="a", composite_score=95.0, effective_confidence=0.9
        )
        low_conf = UnifiedReputation(
            agent_name="b", composite_score=95.0, effective_confidence=0.1
        )
        boost_high = reputation_boost_for_matching(high_conf, 0.5)
        boost_low = reputation_boost_for_matching(low_conf, 0.5)
        # High confidence should have more impact
        assert boost_high > boost_low

    def test_custom_weight(self):
        rep = UnifiedReputation(
            agent_name="agent", composite_score=100.0, effective_confidence=1.0
        )
        light = reputation_boost_for_matching(rep, 0.5, reputation_weight=0.05)
        heavy = reputation_boost_for_matching(rep, 0.5, reputation_weight=0.50)
        assert heavy > light  # More weight = more influence

    def test_result_clamped(self):
        rep = UnifiedReputation(
            agent_name="agent", composite_score=100.0, effective_confidence=1.0
        )
        result = reputation_boost_for_matching(rep, 1.0)
        assert result <= 1.0

    def test_zero_base_score(self):
        rep = UnifiedReputation(
            agent_name="agent", composite_score=90.0, effective_confidence=0.8
        )
        result = reputation_boost_for_matching(rep, 0.0)
        assert result >= 0.0


# ---------------------------------------------------------------------------
# Batch Operations Tests
# ---------------------------------------------------------------------------

class TestBatchOperations:
    def test_compute_swarm_reputation(self):
        agents = {
            "kk-agent-1": {
                "on_chain": [
                    {"seal_type": "SKILLFUL", "quadrant": "A2H", "score": 90,
                     "evaluator": "0x1", "timestamp": NOW.isoformat()},
                ],
                "off_chain": make_performance_data(tasks_completed=15, tasks_attempted=18),
                "transactional": make_api_data(avg_rating=85),
            },
            "kk-agent-2": {
                "off_chain": make_performance_data(tasks_completed=3, tasks_attempted=5),
            },
            "kk-agent-3": {},  # No data at all
        }
        results = compute_swarm_reputation(agents)
        assert len(results) == 3
        assert results["kk-agent-1"].composite_score > results["kk-agent-3"].composite_score
        assert len(results["kk-agent-1"].sources_available) == 3
        assert len(results["kk-agent-2"].sources_available) == 1
        assert len(results["kk-agent-3"].sources_available) == 0

    def test_rank_by_reputation(self):
        reps = {
            "high": UnifiedReputation(agent_name="high", composite_score=90, effective_confidence=0.8),
            "mid": UnifiedReputation(agent_name="mid", composite_score=60, effective_confidence=0.5),
            "low": UnifiedReputation(agent_name="low", composite_score=30, effective_confidence=0.3),
        }
        ranked = rank_by_reputation(reps)
        assert ranked[0][0] == "high"
        assert ranked[1][0] == "mid"
        assert ranked[2][0] == "low"

    def test_rank_with_min_confidence(self):
        reps = {
            "confident": UnifiedReputation(agent_name="confident", composite_score=70, effective_confidence=0.6),
            "uncertain": UnifiedReputation(agent_name="uncertain", composite_score=90, effective_confidence=0.1),
        }
        ranked = rank_by_reputation(reps, min_confidence=0.5)
        assert len(ranked) == 1
        assert ranked[0][0] == "confident"

    def test_swarm_reputation_with_seal_objects(self):
        """Test that SealScore objects pass through correctly."""
        agents = {
            "agent-1": {
                "on_chain": [make_seal(score=88)],
            },
        }
        results = compute_swarm_reputation(agents)
        assert results["agent-1"].on_chain_score == pytest.approx(88.0, abs=1)

    def test_swarm_reputation_with_prebuilt_objects(self):
        """Test passing pre-built reputation objects."""
        agents = {
            "agent-1": {
                "on_chain": OnChainReputation(
                    agent_address="0x1", composite_score=75, confidence=0.6
                ),
                "off_chain": OffChainReputation(
                    agent_name="agent-1", reliability_score=0.8, avg_rating=70
                ),
            },
        }
        results = compute_swarm_reputation(agents)
        assert len(results["agent-1"].sources_available) == 2


# ---------------------------------------------------------------------------
# Persistence Tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load_snapshot(self, tmp_path):
        reps = {
            "agent-1": UnifiedReputation(
                agent_name="agent-1", composite_score=85,
                tier=ReputationTier.DIAMANTE, effective_confidence=0.7,
                sources_available=["on_chain", "off_chain"],
            ),
            "agent-2": UnifiedReputation(
                agent_name="agent-2", composite_score=55,
                tier=ReputationTier.PLATA, effective_confidence=0.4,
            ),
        }
        path = save_reputation_snapshot(reps, tmp_path)
        assert path.exists()

        loaded = load_reputation_snapshot(path)
        assert "agent-1" in loaded
        assert "agent-2" in loaded
        assert loaded["agent-1"]["composite_score"] == 85

    def test_load_latest_snapshot(self, tmp_path):
        # Save two snapshots
        reps1 = {"a": UnifiedReputation(agent_name="a", composite_score=60)}
        reps2 = {"a": UnifiedReputation(agent_name="a", composite_score=80)}

        save_reputation_snapshot(reps1, tmp_path)
        # Ensure different timestamp
        import time; time.sleep(0.01)
        save_reputation_snapshot(reps2, tmp_path)

        latest = load_latest_snapshot(tmp_path)
        assert latest["a"]["composite_score"] == 80  # Most recent

    def test_load_nonexistent_directory(self, tmp_path):
        result = load_latest_snapshot(tmp_path / "nope")
        assert result == {}

    def test_load_nonexistent_file(self, tmp_path):
        result = load_reputation_snapshot(tmp_path / "nope.json")
        assert result == {}

    def test_snapshot_contains_leaderboard(self, tmp_path):
        reps = {
            "high": UnifiedReputation(agent_name="high", composite_score=90, effective_confidence=0.8),
            "low": UnifiedReputation(agent_name="low", composite_score=30, effective_confidence=0.3),
        }
        path = save_reputation_snapshot(reps, tmp_path)
        data = json.loads(path.read_text())
        assert "leaderboard" in data
        assert data["leaderboard"][0]["agent"] == "high"
        assert data["leaderboard"][0]["rank"] == 1


# ---------------------------------------------------------------------------
# Trend Analysis Tests
# ---------------------------------------------------------------------------

class TestTrendAnalysis:
    def test_insufficient_data(self):
        result = compute_reputation_trend([], "agent")
        assert result["trend"] == "insufficient_data"

    def test_improving_trend(self):
        snapshots = [
            {"agent": {"composite_score": 80, "layers": {}}},  # Recent
            {"agent": {"composite_score": 60, "layers": {}}},  # Old
        ]
        result = compute_reputation_trend(snapshots, "agent")
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_declining_trend(self):
        snapshots = [
            {"agent": {"composite_score": 40, "layers": {}}},  # Recent
            {"agent": {"composite_score": 70, "layers": {}}},  # Old
        ]
        result = compute_reputation_trend(snapshots, "agent")
        assert result["trend"] == "declining"
        assert result["delta"] < 0

    def test_stable_trend(self):
        snapshots = [
            {"agent": {"composite_score": 72, "layers": {}}},
            {"agent": {"composite_score": 70, "layers": {}}},
        ]
        result = compute_reputation_trend(snapshots, "agent")
        assert result["trend"] == "stable"

    def test_unknown_agent(self):
        snapshots = [{"other": {"composite_score": 80}}]
        result = compute_reputation_trend(snapshots, "missing")
        assert result["trend"] == "insufficient_data"

    def test_layer_trends(self):
        snapshots = [
            {"agent": {"composite_score": 80, "layers": {
                "on_chain": {"score": 90},
                "off_chain": {"score": 70},
            }}},
            {"agent": {"composite_score": 60, "layers": {
                "on_chain": {"score": 60},
                "off_chain": {"score": 65},
            }}},
        ]
        result = compute_reputation_trend(snapshots, "agent")
        assert "on_chain" in result["layer_trends"]
        assert result["layer_trends"]["on_chain"]["direction"] == "up"


# ---------------------------------------------------------------------------
# Leaderboard Tests
# ---------------------------------------------------------------------------

class TestLeaderboard:
    def test_generate_leaderboard(self):
        reps = {
            "alpha": UnifiedReputation(
                agent_name="alpha", composite_score=90,
                tier=ReputationTier.DIAMANTE, effective_confidence=0.8,
                on_chain_score=85, off_chain_score=90, transactional_score=95,
                sources_available=["on_chain", "off_chain", "transactional"],
            ),
            "beta": UnifiedReputation(
                agent_name="beta", composite_score=55,
                tier=ReputationTier.PLATA, effective_confidence=0.3,
                sources_available=["off_chain"],
            ),
        }
        lb = generate_leaderboard(reps)
        assert len(lb) == 2
        assert lb[0]["rank"] == 1
        assert lb[0]["agent"] == "alpha"
        assert lb[0]["tier"] == "Diamante"

    def test_leaderboard_top_n(self):
        reps = {f"agent-{i}": UnifiedReputation(
            agent_name=f"agent-{i}", composite_score=100 - i * 10
        ) for i in range(10)}
        lb = generate_leaderboard(reps, top_n=3)
        assert len(lb) == 3

    def test_leaderboard_min_confidence(self):
        reps = {
            "good": UnifiedReputation(agent_name="good", composite_score=90, effective_confidence=0.7),
            "bad": UnifiedReputation(agent_name="bad", composite_score=95, effective_confidence=0.01),
        }
        lb = generate_leaderboard(reps, min_confidence=0.5)
        assert len(lb) == 1
        assert lb[0]["agent"] == "good"

    def test_format_leaderboard_text(self):
        reps = {
            "alpha": UnifiedReputation(
                agent_name="alpha", composite_score=90,
                tier=ReputationTier.DIAMANTE, effective_confidence=0.8,
                on_chain_score=85, off_chain_score=90, transactional_score=95,
                sources_available=["on_chain", "off_chain", "transactional"],
            ),
        }
        lb = generate_leaderboard(reps)
        text = format_leaderboard_text(lb)
        assert "Leaderboard" in text
        assert "alpha" in text
        assert "Diamante" in text
        assert "💎" in text

    def test_format_empty_leaderboard(self):
        text = format_leaderboard_text([])
        assert "No reputation data" in text


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_seal_score_zero(self):
        rep = compute_on_chain_score([make_seal(score=0)], now=NOW)
        assert rep.composite_score == pytest.approx(0.0, abs=0.5)

    def test_seal_score_100(self):
        rep = compute_on_chain_score([make_seal(score=100)], now=NOW)
        assert rep.composite_score == pytest.approx(100.0, abs=0.5)

    def test_many_seals_same_type(self):
        """50 seals of the same type should average correctly."""
        seals = [make_seal(seal_type="RELIABLE", score=70 + (i % 20), seal_id=i) for i in range(50)]
        rep = compute_on_chain_score(seals, now=NOW)
        assert 70 < rep.composite_score < 90
        assert rep.confidence > 0.7  # 50 seals → high confidence

    def test_all_quadrants(self):
        seals = [make_seal(quadrant=q, score=50 + i * 10, seal_id=i)
                 for i, q in enumerate(QUADRANTS)]
        rep = compute_on_chain_score(seals, now=NOW)
        assert len(rep.quadrant_averages) == 4

    def test_unified_with_extreme_scores(self):
        on_chain = OnChainReputation(
            agent_address="0x1", composite_score=100, confidence=1.0
        )
        off_chain = OffChainReputation(
            agent_name="agent", reliability_score=0.0, avg_rating=0.0,
            tasks_completed=0, tasks_attempted=50,
        )
        rep = compute_unified_reputation("agent", on_chain=on_chain, off_chain=off_chain)
        assert 0 <= rep.composite_score <= 100

    def test_default_weights_sum_to_one(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=0.001)

    def test_reputation_boost_with_zero_confidence(self):
        rep = UnifiedReputation(
            agent_name="agent", composite_score=100.0, effective_confidence=0.0
        )
        # With zero confidence, reputation should have minimal effect
        result = reputation_boost_for_matching(rep, 0.5)
        assert abs(result - 0.5) < 0.1  # Close to base score

    def test_off_chain_normalized_score_has_experience_component(self):
        """More diverse category experience should boost score."""
        narrow = extract_off_chain_reputation("a", {
            "tasks_completed": 10, "tasks_attempted": 10,
            "reliability_score": 0.8, "avg_rating_received": 80,
            "category_completions": {"simple_action": 10},
            "category_attempts": {"simple_action": 10},
            "chain_tasks": {}, "total_earned_usd": 1.0,
        })
        diverse = extract_off_chain_reputation("b", {
            "tasks_completed": 10, "tasks_attempted": 10,
            "reliability_score": 0.8, "avg_rating_received": 80,
            "category_completions": {"simple_action": 3, "knowledge_access": 3, "verification": 2, "digital_physical": 2},
            "category_attempts": {"simple_action": 3, "knowledge_access": 3, "verification": 2, "digital_physical": 2},
            "chain_tasks": {}, "total_earned_usd": 1.0,
        })
        assert diverse.normalized_score >= narrow.normalized_score

    def test_json_roundtrip(self, tmp_path):
        """Test that serialization/deserialization preserves data."""
        reps = {
            "test": UnifiedReputation(
                agent_name="test", composite_score=77.5,
                tier=ReputationTier.ORO, effective_confidence=0.65,
                on_chain_score=80, off_chain_score=75, transactional_score=77,
                sources_available=["on_chain", "off_chain", "transactional"],
                weights_used={"on_chain": 0.3, "off_chain": 0.4, "transactional": 0.3},
            ),
        }
        path = save_reputation_snapshot(reps, tmp_path)
        loaded = load_reputation_snapshot(path)
        assert loaded["test"]["composite_score"] == 77.5
        assert loaded["test"]["tier"] == "Oro"
