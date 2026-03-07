"""
Karma Kadabra V2 — AutoJob Enrichment Layer (Enhanced)

Bridges the KK V2 Decision Engine with AutoJob's SwarmRouter.
When AutoJob is available, enriches agent profiles with evidence-based
matching data before the decision engine runs.

This enrichment layer sits between:
  - KK's DecisionEngine (which selects the best agent for a task)
  - AutoJob's SwarmRouter (which computes evidence-based scores)

Data Flow:
    KK Coordinator → enrich_task_context() → DecisionEngine
                          ↓
                    AutoJob SwarmRouter
                          ↓
                    MatchResult + Skill DNA
                          ↓
                    Enriched agent profiles

The enrichment adds these fields to each agent profile:
  - autojob_score: Evidence-based match score (0-100)
  - autojob_tier: Reputation tier (diamante/oro/plata/bronce/registered)
  - autojob_confidence: Matching confidence (0-1)
  - predicted_quality: Expected output quality rating (1-5)
  - predicted_success: Completion probability (0-1)
  - skill_dna_match: Specific skill alignment details
  - evidence_types_experienced: Which evidence types they've done

Usage:
    enricher = AutoJobEnrichment(autojob_path="/path/to/autojob")
    context = enricher.enrich_task_context(task, agent_profiles)
    # context now has autojob data injected into each profile

    # Or for the decision engine directly:
    enriched = enricher.enrich_for_decision(task, agent_wallets)
    # Returns: dict[wallet, EnrichedProfile]
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kk.autojob_enrichment")


@dataclass
class EnrichedProfile:
    """Agent profile enriched with AutoJob matching data."""
    agent_name: str
    wallet: str
    autojob_score: float = 0.0          # 0-100
    autojob_tier: str = "unverified"
    autojob_confidence: float = 0.0     # 0-1
    predicted_quality: float = 3.0      # 1-5
    predicted_success: float = 0.5      # 0-1
    skill_match_details: dict = field(default_factory=dict)
    evidence_types_experienced: list = field(default_factory=list)
    categories_worked: list = field(default_factory=list)
    total_tasks_completed: int = 0
    composite_reputation: float = 50.0
    enrichment_source: str = "none"     # "autojob_local" | "autojob_remote" | "fallback" | "none"
    enrichment_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "wallet": self.wallet,
            "autojob_score": self.autojob_score,
            "autojob_tier": self.autojob_tier,
            "autojob_confidence": self.autojob_confidence,
            "predicted_quality": self.predicted_quality,
            "predicted_success": self.predicted_success,
            "skill_match_details": self.skill_match_details,
            "evidence_types_experienced": self.evidence_types_experienced,
            "categories_worked": self.categories_worked,
            "total_tasks_completed": self.total_tasks_completed,
            "composite_reputation": self.composite_reputation,
            "enrichment_source": self.enrichment_source,
            "enrichment_time_ms": self.enrichment_time_ms,
        }


@dataclass
class EnrichmentResult:
    """Result of enriching agents for a task."""
    task_id: str
    task_category: str
    profiles: dict  # agent_name -> EnrichedProfile
    total_agents: int
    enriched_agents: int
    source: str           # "autojob_local" | "autojob_remote" | "fallback"
    enrichment_time_ms: float = 0.0
    router_health: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_category": self.task_category,
            "total_agents": self.total_agents,
            "enriched_agents": self.enriched_agents,
            "source": self.source,
            "enrichment_time_ms": self.enrichment_time_ms,
            "router_health": self.router_health,
            "profiles": {
                name: p.to_dict() for name, p in self.profiles.items()
            },
        }


class AutoJobEnrichment:
    """Enriches KK agent profiles with AutoJob evidence-based data.

    Tries to use AutoJob's SwarmRouter locally first, falls back to
    the AutoJob Bridge (HTTP API), and finally to a default profile
    if neither is available.
    """

    def __init__(
        self,
        autojob_path: str = None,
        wallet_to_agent: dict = None,
        fallback_score: float = 50.0,
    ):
        """Initialize enrichment layer.

        Args:
            autojob_path: Path to AutoJob repo for local SwarmRouter import.
            wallet_to_agent: Mapping of wallet addresses to agent names.
            fallback_score: Default score when AutoJob is unavailable.
        """
        self.wallet_to_agent = wallet_to_agent or {}
        self.fallback_score = fallback_score
        self._router = None
        self._mode = "none"

        if autojob_path:
            self._init_router(autojob_path)

    def _init_router(self, autojob_path: str) -> None:
        """Try to import and initialize AutoJob's SwarmRouter."""
        try:
            path = str(Path(autojob_path).resolve())
            if path not in sys.path:
                sys.path.insert(0, path)

            from swarm_router import SwarmRouter

            self._router = SwarmRouter(
                workers_dir=str(Path(autojob_path) / "workers"),
            )
            self._mode = "autojob_local"
            logger.info(
                "AutoJob enrichment initialized (local SwarmRouter, "
                "workers_dir=%s)", str(Path(autojob_path) / "workers")
            )
        except (ImportError, OSError) as e:
            logger.warning(
                "AutoJob SwarmRouter not available (%s), "
                "enrichment will use fallback profiles", e
            )
            self._mode = "fallback"

    @property
    def is_available(self) -> bool:
        """Whether AutoJob enrichment is available."""
        return self._router is not None

    @property
    def mode(self) -> str:
        """Current enrichment mode."""
        return self._mode

    def enrich_for_decision(
        self,
        task: dict,
        agent_wallets: list[str],
        agent_names: dict[str, str] = None,
    ) -> EnrichmentResult:
        """Enrich agent profiles for a task assignment decision.

        This is the primary integration point with KK's DecisionEngine.
        It returns enriched profiles that the decision engine can use
        alongside its own matching factors.

        Args:
            task: EM task dict (id, title, category, bounty_usd, etc.)
            agent_wallets: List of candidate wallet addresses.
            agent_names: Optional mapping wallet → agent name.

        Returns:
            EnrichmentResult with enriched profiles for all agents.
        """
        start = time.time()
        task_id = task.get("id", "unknown")
        task_category = task.get("category", "unknown")
        names = agent_names or self.wallet_to_agent
        profiles = {}

        if self._router:
            try:
                result = self._router.route_task(
                    task=task,
                    candidate_wallets=agent_wallets,
                    limit=len(agent_wallets),
                )

                for ranking in result.get("rankings", []):
                    wallet = ranking.get("wallet", "")
                    agent_name = names.get(wallet.lower(), wallet[:10])

                    profile = EnrichedProfile(
                        agent_name=agent_name,
                        wallet=wallet,
                        autojob_score=ranking.get("final_score", 0),
                        autojob_tier=ranking.get("tier", "unverified"),
                        autojob_confidence=ranking.get("confidence", 0),
                        predicted_quality=ranking.get("predicted_quality", 3.0),
                        predicted_success=ranking.get("predicted_success", 0.5),
                        skill_match_details=ranking.get("skill_match", {}),
                        evidence_types_experienced=ranking.get("evidence_types", []),
                        categories_worked=ranking.get("categories_worked", []),
                        total_tasks_completed=ranking.get("total_tasks", 0),
                        composite_reputation=ranking.get("composite_reputation", 50.0),
                        enrichment_source="autojob_local",
                    )
                    profiles[agent_name] = profile

                # Fill in any agents not in AutoJob's results
                for wallet in agent_wallets:
                    agent_name = names.get(wallet.lower(), wallet[:10])
                    if agent_name not in profiles:
                        profiles[agent_name] = self._fallback_profile(
                            agent_name, wallet
                        )

                source = "autojob_local"
                health = self._router.health() if hasattr(self._router, 'health') else {}

            except Exception as e:
                logger.warning(f"AutoJob enrichment failed: {e}")
                profiles = self._fallback_all(agent_wallets, names)
                source = "fallback"
                health = {"error": str(e)}
        else:
            profiles = self._fallback_all(agent_wallets, names)
            source = "fallback"
            health = {}

        elapsed = (time.time() - start) * 1000

        return EnrichmentResult(
            task_id=task_id,
            task_category=task_category,
            profiles=profiles,
            total_agents=len(agent_wallets),
            enriched_agents=sum(
                1 for p in profiles.values()
                if p.enrichment_source != "fallback"
            ),
            source=source,
            enrichment_time_ms=elapsed,
            router_health=health,
        )

    def enrich_task_context(
        self,
        task: dict,
        agent_profiles: dict[str, dict],
    ) -> dict[str, dict]:
        """Inject AutoJob enrichment data into existing agent profiles.

        Used when the coordinator already has agent profiles and wants
        to add AutoJob scores to them.

        Args:
            task: EM task dict.
            agent_profiles: Dict of agent_name → profile dict.

        Returns:
            The same profiles dict with AutoJob fields injected.
        """
        wallets = []
        name_to_wallet = {}
        for name, profile in agent_profiles.items():
            wallet = profile.get("wallet", "")
            if wallet:
                wallets.append(wallet)
                name_to_wallet[name] = wallet

        if not wallets:
            return agent_profiles

        result = self.enrich_for_decision(
            task=task,
            agent_wallets=wallets,
            agent_names={w.lower(): n for n, w in name_to_wallet.items()},
        )

        # Inject enrichment into original profiles
        for name, profile in agent_profiles.items():
            enriched = result.profiles.get(name)
            if enriched:
                profile["autojob_score"] = enriched.autojob_score
                profile["autojob_tier"] = enriched.autojob_tier
                profile["autojob_confidence"] = enriched.autojob_confidence
                profile["predicted_quality"] = enriched.predicted_quality
                profile["predicted_success"] = enriched.predicted_success
                profile["enrichment_source"] = enriched.enrichment_source

        return agent_profiles

    def _fallback_profile(self, agent_name: str, wallet: str) -> EnrichedProfile:
        """Create a fallback profile when AutoJob data is unavailable."""
        return EnrichedProfile(
            agent_name=agent_name,
            wallet=wallet,
            autojob_score=self.fallback_score,
            autojob_tier="unverified",
            autojob_confidence=0.0,
            predicted_quality=3.0,
            predicted_success=0.5,
            enrichment_source="fallback",
        )

    def _fallback_all(
        self,
        wallets: list[str],
        names: dict[str, str],
    ) -> dict[str, EnrichedProfile]:
        """Create fallback profiles for all agents."""
        profiles = {}
        for wallet in wallets:
            name = names.get(wallet.lower(), wallet[:10])
            profiles[name] = self._fallback_profile(name, wallet)
        return profiles


# ═══════════════════════════════════════════════════════════════════
# Compatibility aliases for test_full_chain_integration
# ═══════════════════════════════════════════════════════════════════


@dataclass
class EnrichmentConfig:
    """Configuration for enrichment (compatibility alias)."""
    autojob_path: Optional[str] = None
    fallback_score: float = 50.0


@dataclass
class EnrichmentStats:
    """Statistics from an enrichment run."""
    total_agents: int = 0
    agents_enriched: int = 0
    agents_cold_start: int = 0
    agents_failed: int = 0
    enrichment_time_ms: float = 0.0
    bridge_mode: str = "none"


def create_enriched_decision_context(
    bridge,
    task,  # TaskProfile from decision_engine
    profiles: list,
    wallet_map: dict,
) -> tuple:
    """Create a DecisionContext enriched with AutoJob data.

    Supports both AutoJobEnrichment (new API) and legacy bridge objects
    that have rank_agents_for_task (e.g., AutoJobBridge, MockAutoJobBridge).

    Args:
        bridge: AutoJobEnrichment instance or any bridge with rank_agents_for_task.
        task: TaskProfile for the decision.
        profiles: List of AgentProfile objects.
        wallet_map: Dict mapping agent_name → wallet address.

    Returns:
        (DecisionContext, EnrichmentStats) tuple.
    """
    from lib.decision_engine import DecisionContext

    start = time.time()

    wallets = list(wallet_map.values())
    name_to_wallet = wallet_map
    wallet_to_name = {w.lower(): n for n, w in wallet_map.items()}

    # Build task dict from TaskProfile
    task_dict = {
        "id": task.task_id,
        "category": getattr(task, "category", ""),
        "bounty_usd": getattr(task, "bounty_usd", 0),
    }

    enriched_count = 0
    cold_start_count = 0
    bridge_mode = "local"

    if hasattr(bridge, 'enrich_for_decision'):
        # New API: AutoJobEnrichment
        result = bridge.enrich_for_decision(
            task=task_dict,
            agent_wallets=wallets,
            agent_names=wallet_to_name,
        )
        for profile in profiles:
            enriched = result.profiles.get(profile.agent_name)
            if enriched and enriched.enrichment_source != "fallback":
                profile.autojob_match_score = enriched.autojob_score
                profile.predicted_quality = enriched.predicted_quality
                profile.predicted_success = enriched.predicted_success
                enriched_count += 1
            else:
                cold_start_count += 1
        bridge_mode = getattr(bridge, 'mode', 'local')
        if bridge_mode == "none":
            bridge_mode = "local"

    elif hasattr(bridge, 'rank_agents_for_task'):
        # Legacy API: AutoJobBridge / MockAutoJobBridge
        try:
            result_obj = bridge.rank_agents_for_task(
                task=task_dict,
                agent_wallets=wallets,
                limit=len(profiles),
            )
            # Handle both list results and result objects with .rankings
            if hasattr(result_obj, 'rankings'):
                rankings = result_obj.rankings
            elif isinstance(result_obj, list):
                rankings = result_obj
            else:
                rankings = []

            # Build lookup: agent_name → ranking
            rank_map = {}
            for r in rankings:
                name = getattr(r, 'agent_name', None)
                if name:
                    rank_map[name] = r

            for profile in profiles:
                ranking = rank_map.get(profile.agent_name)
                if ranking:
                    profile.autojob_match_score = getattr(ranking, 'final_score', 0)
                    profile.predicted_quality = getattr(ranking, 'predicted_quality', 0)
                    profile.predicted_success = getattr(ranking, 'predicted_success', 0)
                    enriched_count += 1
                else:
                    cold_start_count += 1
            bridge_mode = getattr(bridge, 'mode', 'local')
        except Exception as e:
            logger.warning(f"Bridge ranking failed: {e}")
            cold_start_count = 0
            bridge_mode = "error"
            # All agents are considered "failed" when bridge errors
            failed_count = len(profiles)
    else:
        cold_start_count = len(profiles)
        bridge_mode = "none"

    elapsed = (time.time() - start) * 1000

    context = DecisionContext(task=task, agents=profiles)
    stats = EnrichmentStats(
        total_agents=len(profiles),
        agents_enriched=enriched_count,
        agents_cold_start=cold_start_count,
        agents_failed=locals().get("failed_count", 0),
        enrichment_time_ms=elapsed,
        bridge_mode=bridge_mode,
    )

    return context, stats
