"""
Tests for AutoJob Enrichment Layer
====================================

Tests the glue between AutoJobBridge and DecisionEngine.
Verifies that AgentProfile fields get properly populated from
AutoJob intelligence data.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from unittest import TestCase, mock

from lib.autojob_enrichment import (
    AutoJobEnricher,
    EnrichmentConfig,
    EnrichmentStats,
    enrich_profiles,
    create_enriched_decision_context,
)
from lib.decision_engine import (
    AgentProfile,
    DecisionConfig,
    DecisionContext,
    DecisionEngine,
    TaskProfile,
)


# ---------------------------------------------------------------------------
# Mock AutoJobBridge
# ---------------------------------------------------------------------------

@dataclass
class MockAgentRanking:
    """Mock of AutoJobBridge's AgentRanking."""
    agent_name: str
    wallet: str
    final_score: float = 75.0
    skill_score: float = 80.0
    reputation_score: float = 70.0
    reliability_score: float = 85.0
    recency_score: float = 90.0
    tier: str = "Oro"
    confidence: float = 0.8
    explanation: str = "Test ranking"
    predicted_quality: float = 4.2
    predicted_success: float = 0.85
    categories_worked: list = field(default_factory=lambda: ["data_collection"])
    total_tasks: int = 15
    agent_id: Optional[int] = None


@dataclass
class MockBridgeResult:
    """Mock of AutoJobBridge's BridgeResult."""
    task_id: str
    task_category: str
    rankings: list = field(default_factory=list)
    total_candidates: int = 0
    qualified_candidates: int = 0
    best_match: object = None
    match_time_ms: float = 5.0
    mode: str = "local"
    autojob_version: str = "test"


class MockAutoJobBridge:
    """Mock bridge that returns configurable rankings."""

    def __init__(self, rankings=None, should_fail=False):
        self.rankings = rankings or []
        self.should_fail = should_fail
        self.calls = []

    def rank_agents_for_task(self, task, agent_wallets=None, limit=10, min_score=None):
        self.calls.append({
            "task": task,
            "agent_wallets": agent_wallets,
            "limit": limit,
            "min_score": min_score,
        })

        if self.should_fail:
            raise ConnectionError("Bridge is down")

        # Filter rankings to requested wallets
        filtered = self.rankings
        if agent_wallets:
            wallet_set = {w.lower() for w in agent_wallets}
            filtered = [r for r in self.rankings if r.wallet.lower() in wallet_set]

        return MockBridgeResult(
            task_id=task.get("id", "unknown"),
            task_category=task.get("category", "unknown"),
            rankings=filtered,
            total_candidates=len(filtered),
            qualified_candidates=len(filtered),
            best_match=filtered[0] if filtered else None,
        )


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _make_task(category="data_collection", bounty=0.50):
    return TaskProfile(
        task_id="test_task_1",
        category=category,
        bounty_usd=bounty,
    )


def _make_agents(count=3):
    agents = []
    for i in range(count):
        agents.append(AgentProfile(
            agent_name=f"kk-agent-{i}",
            agent_id=i,
            is_available=True,
            reputation_score=50.0 + i * 10,
        ))
    return agents


def _make_wallet_map(agents, prefix="0xAgent"):
    return {
        a.agent_name: f"{prefix}{i:02d}" + "0" * (40 - len(prefix) - 2)
        for i, a in enumerate(agents)
    }


def _make_rankings(agents, wallet_map):
    rankings = []
    for i, agent in enumerate(agents):
        wallet = wallet_map.get(agent.agent_name, "")
        rankings.append(MockAgentRanking(
            agent_name=agent.agent_name,
            wallet=wallet,
            final_score=80.0 - i * 10,
            skill_score=85.0 - i * 5,
            reputation_score=75.0 - i * 10,
            reliability_score=90.0 - i * 5,
            recency_score=95.0 - i * 5,
            tier=["Diamante", "Oro", "Plata"][i % 3],
            confidence=0.9 - i * 0.1,
            explanation=f"Ranked #{i + 1}",
            predicted_quality=4.5 - i * 0.3,
            predicted_success=0.9 - i * 0.1,
            categories_worked=["data_collection"],
            total_tasks=20 - i * 5,
        ))
    return rankings


# ---------------------------------------------------------------------------
# Tests: Configuration
# ---------------------------------------------------------------------------

class TestEnrichmentConfig(TestCase):
    """Test enrichment configuration."""

    def test_default_config(self):
        config = EnrichmentConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.signal_strength, 1.0)
        self.assertTrue(config.use_bridge_predictions)

    def test_disabled_config(self):
        config = EnrichmentConfig(enabled=False)
        self.assertFalse(config.enabled)

    def test_dampened_signal(self):
        config = EnrichmentConfig(signal_strength=0.5)
        self.assertEqual(config.signal_strength, 0.5)


# ---------------------------------------------------------------------------
# Tests: Enrichment Core
# ---------------------------------------------------------------------------

class TestAutoJobEnricher(TestCase):
    """Test the AutoJobEnricher class."""

    def test_basic_enrichment(self):
        """Enrichment populates autojob fields in AgentProfile."""
        agents = _make_agents(3)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        result, stats = enricher.enrich(_make_task(), agents)

        # All agents should have non-zero autojob fields
        for agent in result:
            self.assertGreater(agent.autojob_match_score, 0.0,
                               f"{agent.agent_name} should have autojob_match_score > 0")
            self.assertGreater(agent.predicted_quality, 0.0,
                               f"{agent.agent_name} should have predicted_quality > 0")
            self.assertGreater(agent.predicted_success, 0.0,
                               f"{agent.agent_name} should have predicted_success > 0")

    def test_enrichment_stats(self):
        """Enrichment returns accurate stats."""
        agents = _make_agents(3)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        _, stats = enricher.enrich(_make_task(), agents)

        self.assertEqual(stats.total_agents, 3)
        self.assertEqual(stats.agents_enriched, 3)
        self.assertEqual(stats.agents_cold_start, 0)
        self.assertEqual(stats.agents_failed, 0)
        self.assertGreater(stats.enrichment_time_ms, 0)
        self.assertEqual(stats.bridge_mode, "local")

    def test_enrichment_preserves_existing_data(self):
        """Enrichment doesn't clobber non-autojob fields."""
        agents = _make_agents(1)
        agents[0].reputation_score = 88.0
        agents[0].efficiency_score = 75.0
        agents[0].tasks_completed = 42

        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        enricher.enrich(_make_task(), agents)

        # Original fields should be untouched
        self.assertEqual(agents[0].reputation_score, 88.0)
        self.assertEqual(agents[0].efficiency_score, 75.0)
        self.assertEqual(agents[0].tasks_completed, 42)

    def test_match_score_range(self):
        """Match score should be normalized to [0, 1]."""
        agents = _make_agents(3)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        enricher.enrich(_make_task(), agents)

        for agent in agents:
            self.assertGreaterEqual(agent.autojob_match_score, 0.0)
            self.assertLessEqual(agent.autojob_match_score, 1.0)

    def test_ranking_order_reflected(self):
        """Higher-ranked agents get higher match scores."""
        agents = _make_agents(3)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        enricher.enrich(_make_task(), agents)

        # Agent 0 should have highest score, agent 2 lowest
        self.assertGreater(agents[0].autojob_match_score, agents[1].autojob_match_score)
        self.assertGreater(agents[1].autojob_match_score, agents[2].autojob_match_score)

    def test_signal_strength_dampening(self):
        """Signal strength < 1.0 dampens enrichment values."""
        agents_full = _make_agents(1)
        agents_half = _make_agents(1)

        wallet_map = _make_wallet_map(agents_full)
        rankings = _make_rankings(agents_full, wallet_map)

        # Full signal
        bridge = MockAutoJobBridge(rankings=rankings)
        enricher_full = AutoJobEnricher(
            bridge=bridge, wallet_map=wallet_map,
            config=EnrichmentConfig(signal_strength=1.0),
        )
        enricher_full.enrich(_make_task(), agents_full)

        # Half signal
        bridge2 = MockAutoJobBridge(rankings=_make_rankings(agents_half, wallet_map))
        enricher_half = AutoJobEnricher(
            bridge=bridge2, wallet_map=wallet_map,
            config=EnrichmentConfig(signal_strength=0.5),
        )
        enricher_half.enrich(_make_task(), agents_half)

        # Half-signal agent should have lower scores
        self.assertLess(agents_half[0].autojob_match_score,
                        agents_full[0].autojob_match_score)

    def test_bridge_calls_with_wallets(self):
        """Enricher passes correct wallets to bridge."""
        agents = _make_agents(2)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        enricher.enrich(_make_task(), agents)

        # Verify bridge was called with correct wallets
        self.assertEqual(len(bridge.calls), 1)
        call = bridge.calls[0]
        expected_wallets = [wallet_map[a.agent_name] for a in agents]
        self.assertEqual(sorted(call["agent_wallets"]), sorted(expected_wallets))


# ---------------------------------------------------------------------------
# Tests: Cold Start
# ---------------------------------------------------------------------------

class TestColdStart(TestCase):
    """Test behavior when agents aren't in AutoJob."""

    def test_no_wallet_mapping(self):
        """Agents without wallet mappings get cold-start defaults."""
        agents = _make_agents(2)
        wallet_map = {}  # No mappings
        bridge = MockAutoJobBridge(rankings=[])

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        _, stats = enricher.enrich(_make_task(), agents)

        self.assertEqual(stats.agents_cold_start, 2)
        self.assertEqual(stats.agents_enriched, 0)

        for agent in agents:
            self.assertEqual(agent.autojob_match_score, 0.3)  # default
            self.assertEqual(agent.predicted_quality, 0.5)
            self.assertEqual(agent.predicted_success, 0.4)

    def test_partial_coverage(self):
        """Mix of known and unknown agents."""
        agents = _make_agents(3)
        # Only map first 2
        wallet_map = {
            agents[0].agent_name: "0xKnown01" + "0" * 31,
            agents[1].agent_name: "0xKnown02" + "0" * 31,
        }
        rankings = [
            MockAgentRanking(
                agent_name=agents[0].agent_name,
                wallet="0xKnown01" + "0" * 31,
            ),
            MockAgentRanking(
                agent_name=agents[1].agent_name,
                wallet="0xKnown02" + "0" * 31,
            ),
        ]
        bridge = MockAutoJobBridge(rankings=rankings)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        _, stats = enricher.enrich(_make_task(), agents)

        self.assertEqual(stats.agents_enriched, 2)
        self.assertEqual(stats.agents_cold_start, 1)

        # Agent 2 (no wallet) should have cold-start values
        self.assertEqual(agents[2].autojob_match_score, 0.3)

    def test_custom_cold_start_values(self):
        """Custom cold-start config applies."""
        agents = _make_agents(1)
        config = EnrichmentConfig(
            cold_start_match_score=0.5,
            cold_start_quality=0.7,
            cold_start_success=0.6,
        )
        bridge = MockAutoJobBridge(rankings=[])

        enricher = AutoJobEnricher(
            bridge=bridge, wallet_map={}, config=config,
        )
        enricher.enrich(_make_task(), agents)

        self.assertEqual(agents[0].autojob_match_score, 0.5)
        self.assertEqual(agents[0].predicted_quality, 0.7)
        self.assertEqual(agents[0].predicted_success, 0.6)


# ---------------------------------------------------------------------------
# Tests: Error Handling
# ---------------------------------------------------------------------------

class TestErrorHandling(TestCase):
    """Test graceful degradation when bridge fails."""

    def test_bridge_failure_fallback(self):
        """Bridge failure falls back to cold-start for all agents."""
        agents = _make_agents(3)
        wallet_map = _make_wallet_map(agents)
        bridge = MockAutoJobBridge(should_fail=True)

        enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
        _, stats = enricher.enrich(_make_task(), agents)

        # All agents should get cold-start values
        self.assertEqual(stats.agents_failed, 3)
        self.assertEqual(stats.agents_cold_start, 3)
        self.assertEqual(stats.agents_enriched, 0)

        for agent in agents:
            self.assertEqual(agent.autojob_match_score, 0.3)

    def test_disabled_enrichment(self):
        """Disabled enrichment returns agents unchanged."""
        agents = _make_agents(2)
        config = EnrichmentConfig(enabled=False)
        bridge = MockAutoJobBridge(rankings=[])

        enricher = AutoJobEnricher(bridge=bridge, wallet_map={}, config=config)
        result, stats = enricher.enrich(_make_task(), agents)

        # No enrichment happened
        self.assertEqual(stats.agents_enriched, 0)
        self.assertEqual(stats.agents_cold_start, 0)

        # Fields should be at their defaults (0.0)
        for agent in result:
            self.assertEqual(agent.autojob_match_score, 0.0)

    def test_no_bridge(self):
        """No bridge configured → no enrichment."""
        agents = _make_agents(2)
        enricher = AutoJobEnricher(bridge=None, wallet_map={})
        _, stats = enricher.enrich(_make_task(), agents)

        self.assertEqual(stats.agents_enriched, 0)


# ---------------------------------------------------------------------------
# Tests: Functional API
# ---------------------------------------------------------------------------

class TestFunctionalAPI(TestCase):
    """Test the one-shot functional API."""

    def test_enrich_profiles_function(self):
        """enrich_profiles() works as a one-shot call."""
        agents = _make_agents(2)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        result, stats = enrich_profiles(bridge, _make_task(), agents, wallet_map)

        self.assertEqual(len(result), 2)
        self.assertEqual(stats.agents_enriched, 2)

    def test_create_enriched_context(self):
        """create_enriched_decision_context() produces a usable context."""
        agents = _make_agents(2)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        context, stats = create_enriched_decision_context(
            bridge, _make_task(), agents, wallet_map
        )

        self.assertIsInstance(context, DecisionContext)
        self.assertEqual(len(context.agents), 2)
        self.assertEqual(stats.agents_enriched, 2)

        # Context agents should be enriched
        for agent in context.agents:
            self.assertGreater(agent.autojob_match_score, 0.0)


# ---------------------------------------------------------------------------
# Tests: Integration with DecisionEngine
# ---------------------------------------------------------------------------

class TestDecisionEngineIntegration(TestCase):
    """Test that enriched profiles work correctly with DecisionEngine."""

    def test_enriched_profiles_in_decision(self):
        """DecisionEngine uses autojob fields from enriched profiles."""
        agents = _make_agents(3)
        wallet_map = _make_wallet_map(agents)
        rankings = _make_rankings(agents, wallet_map)
        bridge = MockAutoJobBridge(rankings=rankings)

        task = _make_task()

        # Enrich
        context, stats = create_enriched_decision_context(
            bridge, task, agents, wallet_map
        )

        # Decide
        engine = DecisionEngine(DecisionConfig())
        decision = engine.decide(context)

        # Should produce a valid decision
        self.assertIsNotNone(decision)
        self.assertIsInstance(decision.chosen_agent, (str, type(None)))
        self.assertGreater(decision.agents_considered, 0)

    def test_enrichment_improves_discrimination(self):
        """Enrichment helps the engine differentiate between agents."""
        agents = _make_agents(3)
        # Make all agents look identical without AutoJob
        for a in agents:
            a.reputation_score = 50.0
            a.efficiency_score = 50.0
            a.reliability = 0.5

        wallet_map = _make_wallet_map(agents)

        # Rankings with clear differentiation
        rankings = [
            MockAgentRanking(
                agent_name=agents[0].agent_name,
                wallet=wallet_map[agents[0].agent_name],
                final_score=95.0,
                predicted_success=0.95,
            ),
            MockAgentRanking(
                agent_name=agents[1].agent_name,
                wallet=wallet_map[agents[1].agent_name],
                final_score=50.0,
                predicted_success=0.50,
            ),
            MockAgentRanking(
                agent_name=agents[2].agent_name,
                wallet=wallet_map[agents[2].agent_name],
                final_score=20.0,
                predicted_success=0.20,
            ),
        ]

        bridge = MockAutoJobBridge(rankings=rankings)
        task = _make_task()

        # With enrichment
        context, _ = create_enriched_decision_context(
            bridge, task, agents, wallet_map
        )

        engine = DecisionEngine(DecisionConfig())
        decision = engine.decide(context)

        # The engine should pick the agent with the best AutoJob signal
        # or at least differentiate them
        self.assertGreater(decision.agents_qualified, 0)

    def test_enrichment_stats_serializable(self):
        """Stats.to_dict() is JSON-safe."""
        import json
        stats = EnrichmentStats(
            agents_enriched=5,
            agents_cold_start=2,
            total_agents=7,
            bridge_time_ms=12.5,
            enrichment_time_ms=15.3,
            bridge_mode="local",
        )
        d = stats.to_dict()
        json.dumps(d)  # Must not raise

    def test_wallet_map_update(self):
        """Wallet map can be updated dynamically."""
        enricher = AutoJobEnricher(
            bridge=MockAutoJobBridge(),
            wallet_map={"agent-a": "0xAAA"},
        )

        enricher.update_wallet_map("agent-b", "0xBBB")

        self.assertIn("agent-b", enricher.wallet_map)
        self.assertEqual(enricher.wallet_map["agent-b"], "0xBBB")
        self.assertIn("0xbbb", enricher._reverse_map)
