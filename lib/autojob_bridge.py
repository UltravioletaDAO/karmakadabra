"""
Karma Kadabra V2 — AutoJob Intelligence Bridge

Connects KK's swarm coordinator with AutoJob's evidence-based
matching engine. Instead of KK doing its own simplified skill
matching, it delegates to AutoJob's ReputationMatcher which
has access to:

  1. Full Skill DNA profiles (from EM task history)
  2. ERC-8004 on-chain reputation data
  3. Multi-source evidence merging (insights, GitHub, resume, etc.)
  4. Predictive success modeling (from flywheel history)

Architecture:
    ┌─────────────────────┐     REST/import    ┌──────────────────────┐
    │  KK Coordinator     │ ───────────────→   │  AutoJob Matching    │
    │  (assigns tasks)    │                    │  Engine              │
    └─────────────────────┘                    │                      │
           ↑                                   │  - ReputationMatcher │
           │ ranked agents                     │  - WorkerRegistry    │
           │                                   │  - ERC8004Reader     │
    ┌─────────────────────┐                    │  - SkillDNA Engine   │
    │  Intelligence       │ ←──────────────    └──────────────────────┘
    │  Synthesizer        │   enhanced scores
    └─────────────────────┘

This bridge can operate in two modes:
  1. LOCAL: Direct Python import (when AutoJob is on the same machine)
  2. REMOTE: HTTP calls to autojob.cc/api/swarm/route (production)

Usage:
    bridge = AutoJobBridge(mode="local", autojob_path="/path/to/autojob")
    ranking = bridge.rank_agents_for_task(task, agent_wallets)

    # Or remote mode:
    bridge = AutoJobBridge(mode="remote", api_base="https://autojob.cc")
    ranking = bridge.rank_agents_for_task(task, agent_wallets)
"""

from __future__ import annotations

import json
import logging
import math
import ssl
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kk.autojob_bridge")


# ═══════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AgentRanking:
    """A ranked agent from AutoJob's matching engine."""
    agent_name: str
    wallet: str
    final_score: float          # 0-100 unified score
    skill_score: float          # AutoJob skill match component
    reputation_score: float     # ERC-8004 on-chain component
    reliability_score: float    # Historical reliability
    recency_score: float        # Activity recency
    tier: str                   # diamante/oro/plata/bronce/registered/unverified
    confidence: float           # How confident is this ranking (0-1)
    explanation: str            # Human-readable explanation
    predicted_quality: float    # Expected quality rating for this task type (1-5)
    predicted_success: float    # Probability of successful completion (0-1)
    categories_worked: list = field(default_factory=list)
    total_tasks: int = 0
    agent_id: Optional[int] = None


@dataclass
class BridgeResult:
    """Result of a bridge ranking call."""
    task_id: str
    task_category: str
    rankings: list              # List[AgentRanking]
    total_candidates: int
    qualified_candidates: int
    best_match: Optional[AgentRanking] = None
    match_time_ms: float = 0.0
    mode: str = "local"         # "local" or "remote"
    autojob_version: str = ""


# ═══════════════════════════════════════════════════════════════════
# Category Mapping: KK ↔ AutoJob
# ═══════════════════════════════════════════════════════════════════

# Maps EM task categories to skill requirements understood by AutoJob
KK_TO_AUTOJOB_CATEGORY = {
    "physical_verification": "physical_verification",
    "data_collection": "data_collection",
    "content_creation": "content_creation",
    "translation": "translation",
    "quality_assurance": "quality_assurance",
    "technical_task": "technical_task",
    "survey": "survey",
    "delivery": "delivery",
    "mystery_shopping": "mystery_shopping",
    "notarization": "notarization",
    "simple_action": "simple_action",
    # KK-specific categories that map to AutoJob equivalents
    "code_review": "technical_task",
    "research": "data_collection",
    "writing": "content_creation",
    "analysis": "data_collection",
}


# ═══════════════════════════════════════════════════════════════════
# AutoJob Bridge
# ═══════════════════════════════════════════════════════════════════


class AutoJobBridge:
    """Bridge between KK coordinator and AutoJob's matching engine.

    Supports local (direct import) and remote (HTTP API) modes.
    Local mode is preferred for same-machine deployment (lower latency).
    Remote mode works with autojob.cc API for distributed deployments.
    """

    def __init__(
        self,
        mode: str = "local",
        autojob_path: str = None,
        api_base: str = "https://autojob.cc",
        workers_dir: str = None,
        wallet_to_agent: dict = None,
    ):
        """Initialize the bridge.

        Args:
            mode: "local" (import) or "remote" (HTTP API)
            autojob_path: Path to AutoJob repo (for local mode)
            api_base: AutoJob API URL (for remote mode)
            workers_dir: Override workers directory (for local mode)
            wallet_to_agent: Mapping of wallet addresses to agent names
        """
        self.mode = mode
        self.api_base = api_base.rstrip("/")
        self.wallet_to_agent = wallet_to_agent or {}
        self._local_matcher = None
        self._local_registry = None
        self._local_reader = None

        if mode == "local":
            self._init_local(autojob_path, workers_dir)

    def _init_local(self, autojob_path: str = None, workers_dir: str = None):
        """Initialize local AutoJob imports."""
        if autojob_path:
            autojob_path = str(Path(autojob_path).resolve())
            if autojob_path not in sys.path:
                sys.path.insert(0, autojob_path)

        try:
            from reputation_matcher import ReputationMatcher
            from worker_registry import WorkerRegistry
            from erc8004_reader import ERC8004Reader

            wdir = workers_dir or (
                str(Path(autojob_path) / "workers") if autojob_path else "workers"
            )
            self._local_registry = WorkerRegistry(storage_dir=wdir)
            self._local_reader = ERC8004Reader(network="base")
            self._local_matcher = ReputationMatcher(
                self._local_registry, self._local_reader
            )
            logger.info(
                "AutoJob bridge initialized (local mode, workers_dir=%s)", wdir
            )
        except ImportError as e:
            logger.warning(
                "AutoJob local import failed (%s), falling back to remote mode", e
            )
            self.mode = "remote"

    # ───────────────────────────────────────────────────────────────
    # Core ranking API
    # ───────────────────────────────────────────────────────────────

    def rank_agents_for_task(
        self,
        task: dict,
        agent_wallets: list = None,
        limit: int = 10,
        min_score: float = None,
    ) -> BridgeResult:
        """Rank agents for a task using AutoJob's evidence-based matching.

        Args:
            task: EM task dict (id, title, category, bounty_usd, etc.)
            agent_wallets: Optional list of wallet addresses to consider
                           (if None, considers all registered workers)
            limit: Max rankings to return
            min_score: Minimum score threshold

        Returns:
            BridgeResult with ranked agents
        """
        start = time.monotonic()

        if self.mode == "local" and self._local_matcher:
            result = self._rank_local(task, agent_wallets, limit, min_score)
        else:
            result = self._rank_remote(task, agent_wallets, limit, min_score)

        result.match_time_ms = (time.monotonic() - start) * 1000
        return result

    def _rank_local(
        self, task: dict, agent_wallets: list, limit: int, min_score: float
    ) -> BridgeResult:
        """Rank using local AutoJob imports."""
        # Normalize category
        raw_cat = task.get("category", "simple_action")
        autojob_cat = KK_TO_AUTOJOB_CATEGORY.get(raw_cat, raw_cat)
        task_normalized = {**task, "category": autojob_cat}

        match_result = self._local_matcher.rank_workers_for_task(
            task_normalized, limit=limit, min_score=min_score
        )

        # Convert AutoJob WorkerRankings to KK AgentRankings
        rankings = []
        for wr in match_result.rankings:
            agent_name = self.wallet_to_agent.get(wr.wallet, wr.wallet[:10] + "...")
            rankings.append(AgentRanking(
                agent_name=agent_name,
                wallet=wr.wallet,
                final_score=wr.final_score,
                skill_score=wr.skill_score,
                reputation_score=wr.reputation_score,
                reliability_score=wr.reliability_score,
                recency_score=wr.recency_score,
                tier=wr.tier,
                confidence=wr.confidence,
                explanation=wr.match_explanation,
                predicted_quality=self._predict_quality(wr, autojob_cat),
                predicted_success=self._predict_success(wr, autojob_cat),
                categories_worked=wr.categories_worked,
                total_tasks=wr.total_tasks,
                agent_id=wr.agent_id,
            ))

        best = rankings[0] if rankings else None

        return BridgeResult(
            task_id=task.get("id", "unknown"),
            task_category=autojob_cat,
            rankings=rankings,
            total_candidates=match_result.total_candidates,
            qualified_candidates=match_result.qualified_candidates,
            best_match=best,
            mode="local",
        )

    def _rank_remote(
        self, task: dict, agent_wallets: list, limit: int, min_score: float
    ) -> BridgeResult:
        """Rank using AutoJob's remote API."""
        raw_cat = task.get("category", "simple_action")
        autojob_cat = KK_TO_AUTOJOB_CATEGORY.get(raw_cat, raw_cat)

        payload = {
            "task": {**task, "category": autojob_cat},
            "limit": limit,
        }
        if agent_wallets:
            payload["wallets"] = agent_wallets
        if min_score is not None:
            payload["min_score"] = min_score

        try:
            body = json.dumps(payload).encode()
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                f"{self.api_base}/api/swarm/route",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read().decode())

            rankings = []
            for r in data.get("rankings", []):
                agent_name = self.wallet_to_agent.get(
                    r.get("wallet", ""), r.get("wallet", "")[:10] + "..."
                )
                rankings.append(AgentRanking(
                    agent_name=agent_name,
                    wallet=r.get("wallet", ""),
                    final_score=r.get("score", 0),
                    skill_score=r.get("skill_score", 0),
                    reputation_score=r.get("reputation_score", 0),
                    reliability_score=r.get("reliability_score", 0),
                    recency_score=r.get("recency_score", 0),
                    tier=r.get("tier", "unverified"),
                    confidence=r.get("confidence", 0),
                    explanation=r.get("explanation", ""),
                    predicted_quality=r.get("predicted_quality", 3.0),
                    predicted_success=r.get("predicted_success", 0.5),
                    categories_worked=r.get("categories_worked", []),
                    total_tasks=r.get("total_tasks", 0),
                    agent_id=r.get("agent_id"),
                ))

            best = rankings[0] if rankings else None

            return BridgeResult(
                task_id=task.get("id", "unknown"),
                task_category=autojob_cat,
                rankings=rankings,
                total_candidates=data.get("total_candidates", 0),
                qualified_candidates=data.get("qualified_candidates", 0),
                best_match=best,
                mode="remote",
                autojob_version=data.get("version", ""),
            )

        except Exception as e:
            logger.error("AutoJob remote API failed: %s", e)
            return BridgeResult(
                task_id=task.get("id", "unknown"),
                task_category=autojob_cat,
                rankings=[],
                total_candidates=0,
                qualified_candidates=0,
                mode="remote",
            )

    # ───────────────────────────────────────────────────────────────
    # Prediction helpers
    # ───────────────────────────────────────────────────────────────

    def _predict_quality(self, ranking, category: str) -> float:
        """Predict expected quality rating for this worker on this category.

        Uses the skill/reliability scores as proxies:
        - High skill score + high reliability → high expected quality
        - Low skill → lower expected quality (but not terrible)
        """
        # Base quality from skill match (3.0 - 5.0 range)
        skill_factor = ranking.skill_score / 100.0  # 0-1
        reliability_factor = ranking.reliability_score / 100.0  # 0-1

        # Quality prediction: 3.0 base + up to 2.0 from skill/reliability
        predicted = 3.0 + (skill_factor * 1.2) + (reliability_factor * 0.8)
        return round(min(5.0, max(1.0, predicted)), 2)

    def _predict_success(self, ranking, category: str) -> float:
        """Predict probability of successful completion.

        Based on:
        - Historical reliability (most important)
        - Skill match (can they do it?)
        - Reputation tier (trusted?)
        """
        reliability = ranking.reliability_score / 100.0
        skill = ranking.skill_score / 100.0
        rep = ranking.reputation_score / 100.0

        # Success probability: weighted combo
        prob = (reliability * 0.50) + (skill * 0.30) + (rep * 0.20)

        # Cold start penalty: low confidence = lower prediction
        if ranking.confidence < 0.3:
            prob *= 0.7  # 30% penalty for very new workers

        return round(min(0.99, max(0.10, prob)), 3)

    # ───────────────────────────────────────────────────────────────
    # Bulk operations
    # ───────────────────────────────────────────────────────────────

    def sync_agent_dna(
        self, wallet: str, agent_name: str, task_history: list
    ) -> bool:
        """Sync an agent's task history into AutoJob's WorkerRegistry.

        Call this periodically to keep AutoJob's view of each KK agent
        current with their latest task completions.

        Args:
            wallet: Agent's Ethereum wallet address
            agent_name: KK agent name (for mapping)
            task_history: List of completed task dicts from EM

        Returns:
            True if sync succeeded
        """
        if self.mode != "local" or not self._local_registry:
            logger.warning("sync_agent_dna only works in local mode")
            return False

        try:
            from em_evidence_parser import EMEvidenceParser
            parser = EMEvidenceParser()

            # Adapt tasks to expected format
            adapted = []
            for t in task_history:
                adapted.append({
                    "task_id": t.get("id", t.get("task_id", "")),
                    "worker_address": wallet,
                    "category": t.get("category", "simple_action"),
                    "evidence_types": t.get("evidence_types", ["text_response"]),
                    "quality_rating": t.get("rating", t.get("quality_rating", 4.0)),
                    "completion_time_minutes": t.get("completion_time_minutes", 15),
                    "on_time": t.get("on_time", True),
                    "bounty_usd": t.get("bounty_usd", 0.10),
                    "chain": t.get("payment_network", t.get("chain", "base")),
                    "timestamp": t.get("created_at", t.get("timestamp", "")),
                    "requester_type": t.get("requester_type", "agent"),
                    "requester_reputation": t.get("requester_reputation", 80.0),
                })

            profile = parser.parse_task_history(adapted)
            dna = parser.profile_to_skill_dna(profile)

            # Register in AutoJob
            self._local_registry.upsert(wallet, dna, source="execution_market")

            # Update wallet-to-agent mapping
            self.wallet_to_agent[wallet] = agent_name

            logger.info(
                "Synced %s (%s): %d tasks → %d skills",
                agent_name, wallet[:10], len(adapted),
                len(dna.get("technical_skills", {}))
            )
            return True

        except Exception as e:
            logger.error("Failed to sync DNA for %s: %s", agent_name, e)
            return False

    def get_agent_dna(self, wallet: str) -> Optional[dict]:
        """Get an agent's current Skill DNA from AutoJob."""
        if self.mode == "local" and self._local_registry:
            profile = self._local_registry.get(wallet)
            if profile:
                return profile.get("merged_dna")
        return None

    def get_leaderboard(self, limit: int = 20) -> list:
        """Get the swarm leaderboard (all agents ranked by overall score)."""
        if self.mode == "local" and self._local_registry:
            workers = self._local_registry.list_workers()
            # Sort by update count (proxy for activity)
            workers.sort(
                key=lambda w: w.get("metadata", {}).get("update_count", 0),
                reverse=True
            )
            return workers[:limit]
        return []

    # ───────────────────────────────────────────────────────────────
    # Health and diagnostics
    # ───────────────────────────────────────────────────────────────

    def health(self) -> dict:
        """Check bridge health and connectivity."""
        if self.mode == "local":
            registry_ok = self._local_registry is not None
            matcher_ok = self._local_matcher is not None
            workers = len(self._local_registry.list_workers()) if registry_ok else 0
            return {
                "mode": "local",
                "status": "healthy" if (registry_ok and matcher_ok) else "degraded",
                "registry": registry_ok,
                "matcher": matcher_ok,
                "registered_workers": workers,
                "wallet_mappings": len(self.wallet_to_agent),
            }
        else:
            try:
                ctx = ssl.create_default_context()
                req = urllib.request.Request(f"{self.api_base}/health")
                with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                    data = json.loads(resp.read().decode())
                return {
                    "mode": "remote",
                    "status": "healthy",
                    "api_base": self.api_base,
                    "api_status": data.get("status", "unknown"),
                    "sources": data.get("sources", 0),
                }
            except Exception as e:
                return {
                    "mode": "remote",
                    "status": "unreachable",
                    "api_base": self.api_base,
                    "error": str(e),
                }
