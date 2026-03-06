"""
Karma Kadabra V2 — AutoJob Enrichment Layer

The missing glue between AutoJobBridge and DecisionEngine.

This module provides functions that:
  1. Take DecisionEngine's AgentProfile + TaskProfile
  2. Call AutoJobBridge for evidence-based intelligence
  3. Populate the autojob_* fields in AgentProfile
  4. Return enriched profiles ready for DecisionEngine.decide()

The enrichment happens BEFORE the decision engine runs, giving it
access to AutoJob's Skill DNA matching, ERC-8004 reputation, and
predictive models.

Architecture:
    ┌─────────────────┐    enrich()    ┌──────────────────┐
    │ AgentProfiles    │ ────────────→ │ AutoJobBridge     │
    │ (autojob_*=0)   │               │ (SwarmRouter)     │
    └─────────────────┘               └──────────────────┘
              ↓                                ↓
    ┌─────────────────┐               ┌──────────────────┐
    │ AgentProfiles    │ ←──────────── │ EnrichmentResult  │
    │ (autojob_*=real) │   populate    │ (scores, tiers)  │
    └─────────────────┘               └──────────────────┘
              ↓
    ┌─────────────────┐
    │ DecisionEngine   │
    │ .decide()        │
    │ (uses autojob_*) │
    └─────────────────┘

Usage:
    from lib.autojob_enrichment import AutoJobEnricher

    enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map)
    enriched_profiles = enricher.enrich(task_profile, agent_profiles)
    # Now pass enriched_profiles to DecisionEngine

    # Or as a one-shot function:
    from lib.autojob_enrichment import enrich_profiles

    profiles = enrich_profiles(bridge, task, agents, wallet_map)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("kk.autojob_enrichment")


# Avoid circular imports — use string references
# These are imported at function call time if needed
_AgentProfile = None
_TaskProfile = None


def _ensure_imports():
    """Lazy import DecisionEngine types to avoid circular dependencies."""
    global _AgentProfile, _TaskProfile
    if _AgentProfile is None:
        from lib.decision_engine import AgentProfile, TaskProfile
        _AgentProfile = AgentProfile
        _TaskProfile = TaskProfile


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class EnrichmentConfig:
    """Configuration for AutoJob enrichment."""

    # Whether to enable enrichment (can be turned off for testing)
    enabled: bool = True

    # Timeout for bridge calls (seconds)
    timeout_seconds: float = 10.0

    # Minimum score to consider from AutoJob (filter noise)
    min_score: float = 0.0

    # How much to weight AutoJob intelligence in the overall profile
    # This doesn't change DecisionEngine weights — it controls how
    # much of the AutoJob signal gets through to the profile fields.
    signal_strength: float = 1.0  # 1.0 = full signal, 0.5 = dampened

    # Whether to use the bridge's predicted_quality and predicted_success
    # or compute our own
    use_bridge_predictions: bool = True

    # Cold-start handling: what to do for agents not in AutoJob
    cold_start_match_score: float = 0.3  # Neutral-ish
    cold_start_quality: float = 0.5  # Unknown = assume average
    cold_start_success: float = 0.4  # Slightly below average


# ---------------------------------------------------------------------------
# Enrichment Stats
# ---------------------------------------------------------------------------

@dataclass
class EnrichmentStats:
    """Stats from an enrichment run."""
    agents_enriched: int = 0
    agents_cold_start: int = 0
    agents_failed: int = 0
    total_agents: int = 0
    bridge_time_ms: float = 0.0
    enrichment_time_ms: float = 0.0
    bridge_mode: str = ""

    def to_dict(self) -> dict:
        return {
            "agents_enriched": self.agents_enriched,
            "agents_cold_start": self.agents_cold_start,
            "agents_failed": self.agents_failed,
            "total_agents": self.total_agents,
            "bridge_time_ms": round(self.bridge_time_ms, 2),
            "enrichment_time_ms": round(self.enrichment_time_ms, 2),
            "bridge_mode": self.bridge_mode,
        }


# ---------------------------------------------------------------------------
# AutoJob Enricher
# ---------------------------------------------------------------------------

class AutoJobEnricher:
    """Enriches DecisionEngine's AgentProfiles with AutoJob intelligence.

    This is the adapter layer that bridges KK's decision-making with
    AutoJob's evidence-based matching. Initialize once, call enrich()
    before each decision cycle.
    """

    def __init__(
        self,
        bridge=None,
        wallet_map: dict[str, str] | None = None,
        config: EnrichmentConfig | None = None,
    ):
        """Initialize the enricher.

        Args:
            bridge: AutoJobBridge instance (local or remote)
            wallet_map: Mapping {agent_name: wallet_address}
            config: Enrichment configuration
        """
        self.bridge = bridge
        self.wallet_map = wallet_map or {}
        self.config = config or EnrichmentConfig()

        # Reverse map: wallet → agent_name
        self._reverse_map = {v.lower(): k for k, v in self.wallet_map.items()}

    def enrich(
        self,
        task,  # TaskProfile from decision_engine
        agents: list,  # List[AgentProfile]
    ) -> tuple[list, EnrichmentStats]:
        """Enrich agent profiles with AutoJob intelligence.

        Mutates the AgentProfile objects in-place AND returns them.
        Also returns EnrichmentStats for monitoring.

        Args:
            task: TaskProfile from DecisionEngine
            agents: List of AgentProfile to enrich

        Returns:
            (enriched_agents, stats)
        """
        stats = EnrichmentStats(total_agents=len(agents))

        if not self.config.enabled or self.bridge is None:
            logger.debug("AutoJob enrichment disabled or no bridge configured")
            return agents, stats

        start = time.monotonic()

        # Build EM-format task for the bridge
        em_task = self._task_profile_to_em(task)

        # Collect wallets for agents that have them
        wallet_list = []
        agent_by_wallet = {}
        for agent in agents:
            wallet = self.wallet_map.get(agent.agent_name)
            if wallet:
                wallet_list.append(wallet)
                agent_by_wallet[wallet.lower()] = agent

        if not wallet_list:
            logger.debug("No wallet mappings found for any agents — using cold-start defaults")
            for agent in agents:
                self._apply_cold_start(agent)
                stats.agents_cold_start += 1
            stats.enrichment_time_ms = (time.monotonic() - start) * 1000
            return agents, stats

        # Call bridge for all wallets at once
        try:
            bridge_start = time.monotonic()
            bridge_result = self.bridge.rank_agents_for_task(
                em_task,
                agent_wallets=wallet_list,
                limit=len(wallet_list),
                min_score=self.config.min_score,
            )
            stats.bridge_time_ms = (time.monotonic() - bridge_start) * 1000
            stats.bridge_mode = bridge_result.mode
        except Exception as e:
            logger.warning(f"AutoJob bridge call failed: {e}")
            # Fall back to cold-start for all
            for agent in agents:
                self._apply_cold_start(agent)
                stats.agents_cold_start += 1
            stats.agents_failed = len(agents)
            stats.enrichment_time_ms = (time.monotonic() - start) * 1000
            return agents, stats

        # Build a map of wallet → ranking for quick lookup
        ranking_by_wallet = {}
        for r in bridge_result.rankings:
            ranking_by_wallet[r.wallet.lower()] = r

        # Apply enrichment to each agent
        for agent in agents:
            wallet = self.wallet_map.get(agent.agent_name, "").lower()

            if wallet and wallet in ranking_by_wallet:
                ranking = ranking_by_wallet[wallet]
                self._apply_ranking(agent, ranking)
                stats.agents_enriched += 1
            else:
                self._apply_cold_start(agent)
                stats.agents_cold_start += 1

        stats.enrichment_time_ms = (time.monotonic() - start) * 1000

        logger.info(
            "AutoJob enrichment: %d/%d enriched, %d cold-start, %.1fms bridge, %.1fms total",
            stats.agents_enriched, stats.total_agents,
            stats.agents_cold_start, stats.bridge_time_ms,
            stats.enrichment_time_ms,
        )

        return agents, stats

    def _apply_ranking(self, agent, ranking) -> None:
        """Apply AutoJob ranking data to an AgentProfile."""
        strength = self.config.signal_strength

        # Match score: normalized 0-1
        agent.autojob_match_score = (ranking.final_score / 100.0) * strength

        # Predictions
        if self.config.use_bridge_predictions:
            agent.predicted_quality = ranking.predicted_quality * strength
            agent.predicted_success = ranking.predicted_success * strength
        else:
            # Simple derived predictions
            agent.predicted_quality = (ranking.skill_score / 100.0) * strength
            agent.predicted_success = (
                ranking.reliability_score * 0.5 +
                ranking.skill_score * 0.3 +
                ranking.reputation_score * 0.2
            ) / 100.0 * strength

        # Bonus: update category strengths if we got new data
        if hasattr(ranking, 'categories_worked') and ranking.categories_worked:
            for cat in ranking.categories_worked:
                if cat not in agent.category_strengths:
                    agent.category_strengths[cat] = 0.3  # Baseline from AutoJob

    def _apply_cold_start(self, agent) -> None:
        """Apply cold-start defaults when agent isn't in AutoJob."""
        agent.autojob_match_score = self.config.cold_start_match_score
        agent.predicted_quality = self.config.cold_start_quality
        agent.predicted_success = self.config.cold_start_success

    def _task_profile_to_em(self, task) -> dict:
        """Convert DecisionEngine's TaskProfile to EM task dict."""
        return {
            "id": task.task_id,
            "category": task.category,
            "title": f"KK task: {task.category}",
            "description": "",
            "bounty_usd": task.bounty_usd,
            "payment_network": task.required_chain or "base",
            "evidence_types": task.evidence_types,
            "skills_required": task.skills_required,
        }

    def update_wallet_map(self, agent_name: str, wallet: str) -> None:
        """Update the wallet mapping for an agent."""
        self.wallet_map[agent_name] = wallet
        self._reverse_map[wallet.lower()] = agent_name


# ---------------------------------------------------------------------------
# Functional API (for one-shot use)
# ---------------------------------------------------------------------------

def enrich_profiles(
    bridge,
    task,
    agents: list,
    wallet_map: dict[str, str],
    config: EnrichmentConfig | None = None,
) -> tuple[list, EnrichmentStats]:
    """One-shot enrichment function.

    Convenience wrapper around AutoJobEnricher for callers that don't
    want to manage an enricher instance.

    Args:
        bridge: AutoJobBridge instance
        task: TaskProfile
        agents: List of AgentProfile
        wallet_map: {agent_name: wallet_address}
        config: Optional EnrichmentConfig

    Returns:
        (enriched_agents, stats)
    """
    enricher = AutoJobEnricher(bridge=bridge, wallet_map=wallet_map, config=config)
    return enricher.enrich(task, agents)


def create_enriched_decision_context(
    bridge,
    task,
    agents: list,
    wallet_map: dict[str, str],
    config: EnrichmentConfig | None = None,
):
    """Create a DecisionContext with AutoJob-enriched profiles.

    This is the recommended entry point for KK's coordination loop:

        context = create_enriched_decision_context(
            bridge=autojob_bridge,
            task=task_profile,
            agents=agent_profiles,
            wallet_map=wallet_map,
        )
        decision = engine.decide(context)

    Returns:
        (DecisionContext, EnrichmentStats)
    """
    _ensure_imports()
    from lib.decision_engine import DecisionContext

    enriched_agents, stats = enrich_profiles(bridge, task, agents, wallet_map, config)
    context = DecisionContext(task=task, agents=enriched_agents)
    return context, stats
