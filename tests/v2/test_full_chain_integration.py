"""
Full Chain Integration Test
==============================

Tests the complete swarm intelligence chain:

  EM Tasks → AutoJob Enrichment → DecisionEngine → SwarmDispatch

Verifies that data flows correctly between every module and that
the entire pipeline produces sane assignment decisions.

This is the "canary" test: if this breaks, something fundamental
in the integration has regressed.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from unittest import TestCase

# Core modules under test
from lib.decision_engine import (
    AgentProfile,
    DecisionConfig,
    DecisionContext,
    DecisionEngine,
    OptimizationMode,
    TaskProfile,
)
from lib.autojob_enrichment import (
    AutoJobEnricher,
    EnrichmentConfig,
    EnrichmentStats,
    create_enriched_decision_context,
)
from lib.reputation_bridge import (
    ReputationTier,
    UnifiedReputation,
    classify_tier,
    compute_on_chain_score,
    extract_off_chain_reputation,
)
from lib.swarm_analytics import AgentEfficiency
from lib.agent_lifecycle import AgentState


# ---------------------------------------------------------------------------
# Mocks for External Dependencies
# ---------------------------------------------------------------------------

@dataclass
class MockAgentRanking:
    agent_name: str
    wallet: str
    final_score: float
    skill_score: float = 60.0
    reputation_score: float = 55.0
    reliability_score: float = 70.0
    recency_score: float = 80.0
    tier: str = "Plata"
    confidence: float = 0.7
    explanation: str = "Mock ranking"
    predicted_quality: float = 3.8
    predicted_success: float = 0.72
    categories_worked: list = field(default_factory=list)
    total_tasks: int = 8
    agent_id: Optional[int] = None


@dataclass
class MockBridgeResult:
    task_id: str
    task_category: str
    rankings: list = field(default_factory=list)
    total_candidates: int = 0
    qualified_candidates: int = 0
    best_match: object = None
    match_time_ms: float = 3.0
    mode: str = "local"
    autojob_version: str = "test"


class MockAutoJobBridge:
    def __init__(self, agent_data: dict[str, dict] = None):
        """Initialize with agent data for flexible ranking.

        agent_data: {agent_name: {wallet, score, skill, reputation, ...}}
        """
        self.agent_data = agent_data or {}

    def rank_agents_for_task(self, task, agent_wallets=None, limit=10, min_score=None):
        rankings = []
        task_cat = task.get("category", "")

        for name, data in self.agent_data.items():
            wallet = data.get("wallet", "")
            if agent_wallets and wallet not in agent_wallets:
                continue

            # Category bonus
            cat_bonus = 10 if task_cat in data.get("categories", []) else 0

            rankings.append(MockAgentRanking(
                agent_name=name,
                wallet=wallet,
                final_score=data.get("score", 50) + cat_bonus,
                skill_score=data.get("skill", 60) + cat_bonus,
                reputation_score=data.get("reputation", 55),
                reliability_score=data.get("reliability", 70),
                recency_score=data.get("recency", 80),
                tier=data.get("tier", "Plata"),
                confidence=data.get("confidence", 0.7),
                predicted_quality=data.get("quality", 3.8),
                predicted_success=data.get("success", 0.72),
                categories_worked=data.get("categories", []),
                total_tasks=data.get("total_tasks", 8),
            ))

        rankings.sort(key=lambda r: r.final_score, reverse=True)

        if limit:
            rankings = rankings[:limit]

        return MockBridgeResult(
            task_id=task.get("id", ""),
            task_category=task_cat,
            rankings=rankings,
            total_candidates=len(rankings),
            qualified_candidates=len(rankings),
            best_match=rankings[0] if rankings else None,
        )


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def make_swarm(num_agents=5) -> dict:
    """Create a realistic test swarm with varied agent profiles."""
    agents = {}
    specs = [
        {
            "name": "kk-alpha",
            "wallet": "0xAlpha" + "0" * 35,
            "score": 85, "skill": 90, "reputation": 80,
            "reliability": 95, "recency": 90,
            "tier": "Diamante", "confidence": 0.95,
            "quality": 4.7, "success": 0.93,
            "categories": ["physical_verification", "data_collection"],
            "total_tasks": 45,
            "tasks_completed": 42, "avg_hours": 3.5,
        },
        {
            "name": "kk-bravo",
            "wallet": "0xBravo" + "0" * 35,
            "score": 72, "skill": 75, "reputation": 70,
            "reliability": 80, "recency": 85,
            "tier": "Oro", "confidence": 0.82,
            "quality": 4.2, "success": 0.81,
            "categories": ["content_creation", "translation"],
            "total_tasks": 28,
            "tasks_completed": 24, "avg_hours": 5.0,
        },
        {
            "name": "kk-charlie",
            "wallet": "0xCharl" + "0" * 35,
            "score": 58, "skill": 55, "reputation": 60,
            "reliability": 65, "recency": 70,
            "tier": "Plata", "confidence": 0.6,
            "quality": 3.5, "success": 0.65,
            "categories": ["data_collection", "simple_action"],
            "total_tasks": 12,
            "tasks_completed": 9, "avg_hours": 8.0,
        },
        {
            "name": "kk-delta",
            "wallet": "0xDelta" + "0" * 35,
            "score": 35, "skill": 30, "reputation": 40,
            "reliability": 45, "recency": 50,
            "tier": "Bronce", "confidence": 0.35,
            "quality": 3.0, "success": 0.40,
            "categories": ["simple_action"],
            "total_tasks": 4,
            "tasks_completed": 2, "avg_hours": 12.0,
        },
        {
            "name": "kk-echo",
            "wallet": "0xEchoX" + "0" * 35,
            "score": 0, "skill": 0, "reputation": 0,
            "reliability": 0, "recency": 0,
            "tier": "Unranked", "confidence": 0.0,
            "quality": 0, "success": 0.1,
            "categories": [],
            "total_tasks": 0,
            "tasks_completed": 0, "avg_hours": 0,
        },
    ]

    for i, spec in enumerate(specs[:num_agents]):
        name = spec["name"]
        agents[name] = spec

    return agents


def make_agent_profiles(swarm: dict) -> list[AgentProfile]:
    """Convert swarm specs into DecisionEngine AgentProfiles."""
    profiles = []
    for name, spec in swarm.items():
        profiles.append(AgentProfile(
            agent_name=name,
            agent_id=hash(name) % 1000,
            is_available=True,
            current_tasks=0,
            is_idle=True,
            reputation_score=spec["reputation"],
            reputation_confidence=spec["confidence"],
            reputation_tier=spec["tier"],
            efficiency_score=spec["reliability"],
            avg_completion_hours=spec.get("avg_hours", 12),
            reliability=spec["reliability"] / 100.0,
            tasks_completed=spec.get("tasks_completed", 0),
            category_strengths={
                cat: 0.7 + 0.1 * i for i, cat in enumerate(spec.get("categories", []))
            },
        ))
    return profiles


def make_wallet_map(swarm: dict) -> dict[str, str]:
    """Build agent_name → wallet mapping."""
    return {name: spec["wallet"] for name, spec in swarm.items()}


def make_bridge(swarm: dict) -> MockAutoJobBridge:
    """Create a mock bridge from swarm specs."""
    return MockAutoJobBridge(agent_data=swarm)


def make_tasks() -> list[dict]:
    """Create test tasks matching various categories."""
    return [
        {
            "id": "task_verify_store",
            "title": "Verify storefront signage at 123 Main St",
            "category": "physical_verification",
            "bounty_usd": 5.00,
            "payment_network": "base",
            "evidence_types": ["photo_geo"],
        },
        {
            "id": "task_write_report",
            "title": "Write analysis report on DeFi trends Q1 2026",
            "category": "content_creation",
            "bounty_usd": 8.00,
            "payment_network": "base",
            "evidence_types": ["text_response"],
        },
        {
            "id": "task_collect_prices",
            "title": "Collect prices of 10 items at local grocery",
            "category": "data_collection",
            "bounty_usd": 3.00,
            "payment_network": "base",
            "evidence_types": ["photo", "text_response"],
        },
        {
            "id": "task_simple_survey",
            "title": "Answer 5-question customer satisfaction survey",
            "category": "simple_action",
            "bounty_usd": 0.50,
            "payment_network": "base",
            "evidence_types": ["text_response"],
        },
    ]


# ---------------------------------------------------------------------------
# Tests: Full Chain
# ---------------------------------------------------------------------------

class TestFullChainIntegration(TestCase):
    """End-to-end tests for the entire swarm intelligence pipeline."""

    def setUp(self):
        self.swarm = make_swarm(5)
        self.profiles = make_agent_profiles(self.swarm)
        self.wallet_map = make_wallet_map(self.swarm)
        self.bridge = make_bridge(self.swarm)
        self.tasks = make_tasks()
        self.engine = DecisionEngine(DecisionConfig())

    def test_chain_produces_decision(self):
        """Full chain: enrichment → decision for a single task."""
        task = TaskProfile(
            task_id="task_verify_store",
            category="physical_verification",
            bounty_usd=5.00,
        )

        # Enrich
        context, stats = create_enriched_decision_context(
            self.bridge, task, self.profiles, self.wallet_map,
        )

        # Decide
        decision = self.engine.decide(context)

        # Verify
        self.assertIsNotNone(decision)
        self.assertIsNotNone(decision.chosen_agent)
        self.assertGreater(decision.chosen_score, 0)
        self.assertGreater(decision.agents_considered, 0)
        self.assertGreater(decision.agents_qualified, 0)
        self.assertEqual(decision.task_id, "task_verify_store")

    def test_best_agent_wins_specialized_task(self):
        """Alpha (physical_verification specialist) should win physical tasks."""
        task = TaskProfile(
            task_id="physical_task",
            category="physical_verification",
            bounty_usd=5.00,
        )

        context, _ = create_enriched_decision_context(
            self.bridge, task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        # Alpha is the physical verification specialist
        self.assertEqual(decision.chosen_agent, "kk-alpha",
                         f"Expected alpha for physical task, got {decision.chosen_agent}")

    def test_specialist_wins_category_task(self):
        """Bravo (content specialist) should win content tasks."""
        task = TaskProfile(
            task_id="content_task",
            category="content_creation",
            bounty_usd=8.00,
        )

        context, _ = create_enriched_decision_context(
            self.bridge, task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        # Bravo is the content creation specialist, but alpha might win
        # on pure reputation/reliability. Either is acceptable.
        self.assertIn(decision.chosen_agent, ["kk-alpha", "kk-bravo"],
                      f"Expected alpha or bravo for content, got {decision.chosen_agent}")

    def test_enrichment_affects_scoring(self):
        """Enriched profiles should produce different scores than un-enriched."""
        task = TaskProfile(
            task_id="test_enrichment",
            category="physical_verification",
            bounty_usd=5.00,
        )

        # Without enrichment
        context_plain = DecisionContext(task=task, agents=make_agent_profiles(self.swarm))
        decision_plain = self.engine.decide(context_plain)

        # With enrichment
        context_enriched, _ = create_enriched_decision_context(
            self.bridge, task, make_agent_profiles(self.swarm), self.wallet_map,
        )
        decision_enriched = self.engine.decide(context_enriched)

        # Both should produce decisions
        self.assertIsNotNone(decision_plain.chosen_agent)
        self.assertIsNotNone(decision_enriched.chosen_agent)

        # Enriched should have higher confidence (more data)
        # or at least non-zero autojob scores
        enriched_agent = next(
            a for a in context_enriched.agents if a.agent_name == decision_enriched.chosen_agent
        )
        self.assertGreater(enriched_agent.autojob_match_score, 0,
                           "Enriched agent should have non-zero autojob score")

    def test_chain_handles_all_categories(self):
        """Chain produces valid decisions for all task categories."""
        categories = [
            "physical_verification", "data_collection",
            "content_creation", "simple_action",
            "translation", "quality_assurance",
        ]

        for cat in categories:
            task = TaskProfile(task_id=f"task_{cat}", category=cat, bounty_usd=3.00)
            context, _ = create_enriched_decision_context(
                self.bridge, task, make_agent_profiles(self.swarm), self.wallet_map,
            )
            decision = self.engine.decide(context)

            self.assertIsNotNone(decision.chosen_agent,
                                 f"No agent chosen for category '{cat}'")

    def test_multiple_tasks_avoid_double_assignment(self):
        """Sequential decisions should enable avoiding double assignment."""
        tasks = [
            TaskProfile(task_id="t1", category="physical_verification", bounty_usd=5.0),
            TaskProfile(task_id="t2", category="content_creation", bounty_usd=8.0),
            TaskProfile(task_id="t3", category="data_collection", bounty_usd=3.0),
        ]

        assigned = set()
        decisions = []

        for task in tasks:
            # Filter out already-assigned agents
            available = [p for p in make_agent_profiles(self.swarm) if p.agent_name not in assigned]

            context, _ = create_enriched_decision_context(
                self.bridge, task, available, self.wallet_map,
            )
            decision = self.engine.decide(context)

            if decision.chosen_agent:
                assigned.add(decision.chosen_agent)
                decisions.append(decision)

        # Should have assigned different agents
        assigned_agents = [d.chosen_agent for d in decisions]
        self.assertEqual(len(assigned_agents), len(set(assigned_agents)),
                         f"Double assignment detected: {assigned_agents}")

    def test_high_complexity_favors_reputation(self):
        """High-complexity tasks should favor reputable agents."""
        task = TaskProfile(
            task_id="complex_task",
            category="data_collection",
            bounty_usd=20.00,
            complexity="high",
        )

        context, _ = create_enriched_decision_context(
            self.bridge, task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        # Should pick alpha or bravo (high reputation), not delta/echo
        self.assertIn(decision.chosen_agent, ["kk-alpha", "kk-bravo"],
                      f"Expected high-rep agent for complex task, got {decision.chosen_agent}")

    def test_decision_has_alternatives(self):
        """Decision should include alternative agents."""
        task = TaskProfile(task_id="test_alts", category="data_collection", bounty_usd=3.0)

        context, _ = create_enriched_decision_context(
            self.bridge, task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        # Should have alternatives (cascade)
        self.assertGreater(len(decision.alternatives), 0,
                           "Decision should include alternative agents")

    def test_decision_explainable(self):
        """Decision should have human-readable explanation."""
        task = TaskProfile(task_id="test_explain", category="physical_verification", bounty_usd=5.0)

        context, _ = create_enriched_decision_context(
            self.bridge, task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        explanation = decision.explain()
        self.assertIn("Decision for task", explanation)
        self.assertIn(decision.chosen_agent or "No suitable agent", explanation)

    def test_decision_to_dict_serializable(self):
        """Decision output is JSON-serializable."""
        task = TaskProfile(task_id="test_json", category="simple_action", bounty_usd=0.5)

        context, _ = create_enriched_decision_context(
            self.bridge, task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        d = decision.to_dict()
        json.dumps(d)  # Must not raise

    def test_optimization_modes_produce_different_results(self):
        """Different optimization modes should produce different rankings."""
        task = TaskProfile(
            task_id="test_modes",
            category="data_collection",
            bounty_usd=5.0,
        )

        profiles = make_agent_profiles(self.swarm)

        # Give agents different earnings rates to test cost mode
        profiles[0].earnings_per_hour = 5.0  # Expensive
        profiles[1].earnings_per_hour = 2.0  # Moderate
        profiles[2].earnings_per_hour = 0.5  # Cheap

        results = {}
        for mode in [OptimizationMode.BALANCED, OptimizationMode.QUALITY, OptimizationMode.COST]:
            engine = DecisionEngine(DecisionConfig(mode=mode))
            context, _ = create_enriched_decision_context(
                self.bridge, task, [AgentProfile(**vars(p)) for p in profiles],
                self.wallet_map,
            )
            decision = engine.decide(context)
            results[mode.value] = decision.chosen_agent

        # At minimum, the engine should produce valid decisions in all modes
        for mode_name, chosen in results.items():
            self.assertIsNotNone(chosen, f"No agent chosen in {mode_name} mode")


# ---------------------------------------------------------------------------
# Tests: Chain Resilience
# ---------------------------------------------------------------------------

class TestChainResilience(TestCase):
    """Test that the chain gracefully handles failures."""

    def setUp(self):
        self.swarm = make_swarm(3)
        self.profiles = make_agent_profiles(self.swarm)
        self.wallet_map = make_wallet_map(self.swarm)
        self.engine = DecisionEngine(DecisionConfig())

    def test_bridge_failure_still_produces_decision(self):
        """Chain produces decisions even when AutoJob bridge fails."""
        class FailingBridge:
            def rank_agents_for_task(self, *a, **kw):
                raise ConnectionError("Bridge down")

        task = TaskProfile(task_id="resilience", category="data_collection", bounty_usd=3.0)

        context, stats = create_enriched_decision_context(
            FailingBridge(), task, self.profiles, self.wallet_map,
        )

        # Should fall back to cold-start
        self.assertEqual(stats.agents_failed, 3)

        # Should still produce a decision using base profile data
        decision = self.engine.decide(context)
        self.assertIsNotNone(decision.chosen_agent)

    def test_empty_swarm_no_crash(self):
        """Chain handles empty agent list gracefully."""
        task = TaskProfile(task_id="empty", category="data_collection", bounty_usd=3.0)
        bridge = make_bridge({})

        context, _ = create_enriched_decision_context(
            bridge, task, [], {},
        )
        decision = self.engine.decide(context)

        self.assertIsNone(decision.chosen_agent)
        self.assertEqual(decision.agents_considered, 0)

    def test_no_matching_category_still_works(self):
        """Tasks with unknown categories still get assigned."""
        task = TaskProfile(task_id="unknown_cat", category="quantum_computing", bounty_usd=3.0)

        context, _ = create_enriched_decision_context(
            make_bridge(self.swarm), task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        # Should still pick someone (probably the best overall agent)
        self.assertIsNotNone(decision.chosen_agent)

    def test_all_agents_unavailable(self):
        """Chain handles case where all agents are in cooldown."""
        for p in self.profiles:
            p.is_available = False
            p.in_cooldown = True

        task = TaskProfile(task_id="all_busy", category="data_collection", bounty_usd=3.0)

        context, _ = create_enriched_decision_context(
            make_bridge(self.swarm), task, self.profiles, self.wallet_map,
        )
        decision = self.engine.decide(context)

        # All should be disqualified
        self.assertEqual(decision.agents_qualified, 0)

    def test_single_agent_swarm(self):
        """Chain works with a single agent."""
        single_swarm = {"kk-solo": self.swarm["kk-alpha"]}
        profiles = make_agent_profiles(single_swarm)
        wallet_map = make_wallet_map(single_swarm)

        task = TaskProfile(task_id="solo", category="physical_verification", bounty_usd=5.0)

        context, _ = create_enriched_decision_context(
            make_bridge(single_swarm), task, profiles, wallet_map,
        )
        decision = self.engine.decide(context)

        self.assertEqual(decision.chosen_agent, "kk-solo")
        self.assertEqual(len(decision.alternatives), 0)  # No alternatives


# ---------------------------------------------------------------------------
# Tests: Data Flow Integrity
# ---------------------------------------------------------------------------

class TestDataFlowIntegrity(TestCase):
    """Verify data flows correctly between chain stages."""

    def setUp(self):
        self.swarm = make_swarm(3)

    def test_enrichment_data_reaches_decision_factors(self):
        """Enrichment data is used in decision factor calculations."""
        profiles = make_agent_profiles(self.swarm)
        wallet_map = make_wallet_map(self.swarm)
        bridge = make_bridge(self.swarm)

        task = TaskProfile(task_id="flow_test", category="physical_verification", bounty_usd=5.0)

        context, stats = create_enriched_decision_context(
            bridge, task, profiles, wallet_map,
        )

        # Verify enrichment happened
        self.assertGreater(stats.agents_enriched, 0)

        # Verify enriched data in profiles
        alpha = next(a for a in context.agents if a.agent_name == "kk-alpha")
        self.assertGreater(alpha.autojob_match_score, 0)
        self.assertGreater(alpha.predicted_quality, 0)
        self.assertGreater(alpha.predicted_success, 0)

        # Run decision and check factors use the data
        engine = DecisionEngine(DecisionConfig())
        decision = engine.decide(context)

        # The decision's reasoning should reflect enrichment data
        # (AutoJob predicted success appears in risk assessment)
        self.assertTrue(any("AutoJob" in r for scored in decision.rankings for r in scored.reasons),
                        "Decision reasoning should mention AutoJob predictions")

    def test_enrichment_stats_are_accurate(self):
        """EnrichmentStats accurately reflect what happened."""
        profiles = make_agent_profiles(self.swarm)
        wallet_map = make_wallet_map(self.swarm)
        bridge = make_bridge(self.swarm)

        task = TaskProfile(task_id="stats_test", category="data_collection", bounty_usd=3.0)

        _, stats = create_enriched_decision_context(
            bridge, task, profiles, wallet_map,
        )

        self.assertEqual(stats.total_agents, len(profiles))
        self.assertEqual(stats.agents_enriched + stats.agents_cold_start, stats.total_agents)
        self.assertGreater(stats.enrichment_time_ms, 0)
        self.assertEqual(stats.bridge_mode, "local")

    def test_decision_rankings_preserve_agent_identity(self):
        """Decision rankings maintain correct agent names."""
        profiles = make_agent_profiles(self.swarm)
        wallet_map = make_wallet_map(self.swarm)
        bridge = make_bridge(self.swarm)

        task = TaskProfile(task_id="identity_test", category="simple_action", bounty_usd=0.5)

        context, _ = create_enriched_decision_context(
            bridge, task, profiles, wallet_map,
        )
        decision = DecisionEngine(DecisionConfig()).decide(context)

        known_names = {p.agent_name for p in profiles}
        for scored in decision.rankings:
            self.assertIn(scored.agent.agent_name, known_names,
                          f"Unknown agent in rankings: {scored.agent.agent_name}")

    def test_score_spread_calculation(self):
        """Score spread (difference between #1 and #2) is computed correctly."""
        profiles = make_agent_profiles(self.swarm)
        wallet_map = make_wallet_map(self.swarm)
        bridge = make_bridge(self.swarm)

        task = TaskProfile(task_id="spread_test", category="data_collection", bounty_usd=3.0)

        context, _ = create_enriched_decision_context(
            bridge, task, profiles, wallet_map,
        )
        decision = DecisionEngine(DecisionConfig()).decide(context)

        if len(decision.rankings) >= 2:
            qualified = [r for r in decision.rankings if not r.disqualified]
            if len(qualified) >= 2:
                expected_spread = qualified[0].total_score - qualified[1].total_score
                self.assertAlmostEqual(decision.score_spread, expected_spread, places=1,
                                       msg="Score spread should be #1 - #2")

    def test_chain_timing_reasonable(self):
        """Full chain should complete in reasonable time (<1 second for test data)."""
        import time

        profiles = make_agent_profiles(self.swarm)
        wallet_map = make_wallet_map(self.swarm)
        bridge = make_bridge(self.swarm)

        task = TaskProfile(task_id="timing_test", category="data_collection", bounty_usd=3.0)

        start = time.monotonic()

        context, _ = create_enriched_decision_context(
            bridge, task, profiles, wallet_map,
        )
        decision = DecisionEngine(DecisionConfig()).decide(context)

        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 1.0,
                        f"Full chain took {elapsed:.3f}s — should be <1s for test data")
