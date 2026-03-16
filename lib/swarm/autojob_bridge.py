"""
AutoJob Bridge — Connect EM Swarm Orchestrator to AutoJob Intelligence
=======================================================================

The bridge between Execution Market's swarm orchestrator and AutoJob's
sophisticated matching engine. When AutoJob is available, the orchestrator
uses AutoJob's Skill DNA + ERC-8004 reputation scoring for task assignment.
When unavailable, it falls back gracefully to the orchestrator's built-in
skill matching.

Architecture:
    ┌────────────────────────┐
    │   Swarm Orchestrator   │
    │   (task assignment)    │
    └───────────┬────────────┘
                │
    ┌───────────▼────────────┐
    │   AutoJob Bridge       │ ← YOU ARE HERE
    │   (intelligent routing)│
    └───────────┬────────────┘
                │
    ┌───────────▼────────────────────┐
    │   AutoJob Swarm Router         │
    │   POST /api/swarm/route        │
    │   or direct Python import      │
    └────────────────────────────────┘

Integration modes:
    1. API mode:   Calls AutoJob server's /api/swarm/route endpoint
    2. Direct mode: Imports AutoJob's Python modules directly
    3. Fallback:   Uses orchestrator's built-in scoring (no AutoJob)

Usage:
    from mcp_server.swarm.autojob_bridge import AutoJobBridge

    bridge = AutoJobBridge(mode="api", autojob_url="http://localhost:7860")
    rankings = await bridge.route_task(task_dict)

    # Or with direct Python import (same machine)
    bridge = AutoJobBridge(mode="direct", workers_dir="/path/to/autojob/workers")
    rankings = await bridge.route_task(task_dict)
"""

import json
import logging
import ssl
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class BridgeMode(str, Enum):
    """How the bridge connects to AutoJob."""
    API = "api"         # HTTP calls to AutoJob server
    DIRECT = "direct"   # Direct Python import (same machine)
    FALLBACK = "fallback"  # No AutoJob, use built-in scoring


@dataclass
class AutoJobRanking:
    """A single worker ranking from AutoJob."""
    wallet: str
    final_score: float
    skill_score: float
    reputation_score: float
    reliability_score: float
    recency_score: float
    tier: str
    explanation: str
    on_chain_registered: bool = False
    agent_id: Optional[int] = None
    confidence: float = 0.0
    categories_worked: List[str] = field(default_factory=list)
    total_tasks: int = 0


@dataclass
class RoutingResult:
    """Full result from AutoJob routing."""
    task_id: str
    task_category: str
    rankings: List[AutoJobRanking]
    total_candidates: int
    qualified_candidates: int
    match_time_ms: float
    source: str  # "autojob_api", "autojob_direct", or "fallback"
    error: Optional[str] = None

    @property
    def best_match(self) -> Optional[AutoJobRanking]:
        return self.rankings[0] if self.rankings else None


# ---------------------------------------------------------------------------
# AutoJob Bridge
# ---------------------------------------------------------------------------

class AutoJobBridge:
    """Bridge between EM Swarm Orchestrator and AutoJob's matching engine.

    Provides intelligent task routing by leveraging AutoJob's:
    - Skill DNA (multi-source, evidence-based worker profiles)
    - ERC-8004 reputation (on-chain identity and feedback)
    - Multi-factor scoring (skill 45%, reputation 25%, reliability 20%, recency 10%)

    The bridge auto-detects the best available mode:
    1. If AutoJob Python modules are importable → direct mode
    2. If AutoJob API URL is set → API mode
    3. Otherwise → fallback to built-in scoring
    """

    def __init__(
        self,
        mode: Optional[str] = None,
        autojob_url: str = "http://localhost:7860",
        workers_dir: str = None,
        timeout: int = 10,
    ):
        """
        Initialize the AutoJob bridge.

        Args:
            mode: "api", "direct", or "fallback" (None = auto-detect)
            autojob_url: AutoJob server URL (for API mode)
            workers_dir: Path to AutoJob workers directory (for direct mode)
            timeout: HTTP request timeout in seconds
        """
        self.autojob_url = autojob_url.rstrip("/")
        self.workers_dir = workers_dir
        self.timeout = timeout

        # Auto-detect mode if not specified
        if mode is None:
            self.mode = self._detect_mode()
        else:
            self.mode = BridgeMode(mode)

        # Cache for direct mode imports
        self._route_fn = None
        self._matcher = None

        # Stats
        self.total_routes: int = 0
        self.total_fallbacks: int = 0
        self.total_errors: int = 0

        logger.info(f"AutoJob bridge initialized: mode={self.mode.value}")

    def _detect_mode(self) -> BridgeMode:
        """Auto-detect the best available bridge mode."""
        # Try direct import first (fastest)
        try:
            from em_event_listener import route_task_to_best_agent  # noqa: F401
            logger.info("AutoJob bridge: direct mode available (Python import)")
            return BridgeMode.DIRECT
        except ImportError:
            pass

        # Try API mode (check if server is reachable)
        try:
            req = urllib.request.Request(
                f"{self.autojob_url}/api/listener/status",
                headers={"User-Agent": "EM-SwarmBridge/1.0"},
            )
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
                if resp.status == 200:
                    logger.info("AutoJob bridge: API mode available")
                    return BridgeMode.API
        except Exception:
            pass

        logger.info("AutoJob bridge: fallback mode (AutoJob not available)")
        return BridgeMode.FALLBACK

    # -------------------------------------------------------------------
    # Main routing method
    # -------------------------------------------------------------------

    async def route_task(
        self,
        task: dict,
        limit: int = 5,
        min_score: float = 20.0,
        enrich_reputation: bool = True,
    ) -> RoutingResult:
        """Route a task to the best agent(s) using AutoJob intelligence.

        This is the primary method the SwarmOrchestrator should call
        when assigning tasks.

        Args:
            task: EM task dict (id, title, category, bounty_usd, etc.)
            limit: Max candidates to return
            min_score: Minimum score threshold
            enrich_reputation: Include ERC-8004 on-chain data

        Returns:
            RoutingResult with ranked agents
        """
        self.total_routes += 1

        try:
            if self.mode == BridgeMode.DIRECT:
                return await self._route_direct(task, limit, min_score, enrich_reputation)
            elif self.mode == BridgeMode.API:
                return await self._route_api(task, limit, min_score)
            else:
                self.total_fallbacks += 1
                return self._route_fallback(task)
        except Exception as e:
            self.total_errors += 1
            logger.error(f"AutoJob bridge routing failed: {e}")
            self.total_fallbacks += 1
            return self._route_fallback(task, error=str(e))

    # -------------------------------------------------------------------
    # Direct mode (Python import)
    # -------------------------------------------------------------------

    async def _route_direct(
        self,
        task: dict,
        limit: int,
        min_score: float,
        enrich_reputation: bool,
    ) -> RoutingResult:
        """Route via direct Python import (same machine)."""
        import time as _time

        start = _time.time()

        # Lazy import
        if self._route_fn is None:
            from em_event_listener import route_task_to_best_agent
            self._route_fn = route_task_to_best_agent

        workers_dir = self.workers_dir or "workers"
        raw_rankings = self._route_fn(
            task=task,
            workers_dir=workers_dir,
            limit=limit,
            enrich_reputation=enrich_reputation,
        )

        elapsed = (_time.time() - start) * 1000

        rankings = [
            AutoJobRanking(
                wallet=r["wallet"],
                final_score=r["final_score"],
                skill_score=r["skill_score"],
                reputation_score=r["reputation_score"],
                reliability_score=r["reliability_score"],
                recency_score=r["recency_score"],
                tier=r["tier"],
                explanation=r["explanation"],
                on_chain_registered=r.get("on_chain", False),
                agent_id=r.get("agent_id"),
                confidence=r.get("confidence", 0),
            )
            for r in raw_rankings
        ]

        return RoutingResult(
            task_id=str(task.get("id", task.get("task_id", "unknown"))),
            task_category=task.get("category", "unknown"),
            rankings=rankings,
            total_candidates=len(raw_rankings),
            qualified_candidates=len([r for r in rankings if r.final_score >= min_score]),
            match_time_ms=round(elapsed, 2),
            source="autojob_direct",
        )

    # -------------------------------------------------------------------
    # API mode (HTTP)
    # -------------------------------------------------------------------

    async def _route_api(
        self,
        task: dict,
        limit: int,
        min_score: float,
    ) -> RoutingResult:
        """Route via AutoJob API server."""
        import time as _time

        start = _time.time()

        payload = json.dumps({
            "task": task,
            "limit": limit,
            "min_score": min_score,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.autojob_url}/api/swarm/route",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "EM-SwarmBridge/1.0",
            },
        )

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        elapsed = (_time.time() - start) * 1000

        if not data.get("success"):
            raise RuntimeError(f"AutoJob API error: {data}")

        rankings = [
            AutoJobRanking(
                wallet=r["wallet"],
                final_score=r["final_score"],
                skill_score=r["skill_score"],
                reputation_score=r["reputation_score"],
                reliability_score=r["reliability_score"],
                recency_score=r["recency_score"],
                tier=r["tier"],
                explanation=r["explanation"],
                on_chain_registered=r.get("on_chain_registered", False),
                agent_id=r.get("agent_id"),
                confidence=r.get("confidence", 0),
                categories_worked=r.get("categories_worked", []),
                total_tasks=r.get("total_tasks", 0),
            )
            for r in data.get("rankings", [])
        ]

        return RoutingResult(
            task_id=data.get("task_id", "unknown"),
            task_category=data.get("task_category", "unknown"),
            rankings=rankings,
            total_candidates=data.get("total_candidates", 0),
            qualified_candidates=data.get("qualified_candidates", 0),
            match_time_ms=round(elapsed, 2),
            source="autojob_api",
        )

    # -------------------------------------------------------------------
    # Fallback mode
    # -------------------------------------------------------------------

    def _route_fallback(
        self,
        task: dict,
        error: Optional[str] = None,
    ) -> RoutingResult:
        """Return empty result when AutoJob is unavailable.

        The swarm orchestrator will use its built-in scoring instead.
        """
        return RoutingResult(
            task_id=str(task.get("id", task.get("task_id", "unknown"))),
            task_category=task.get("category", "unknown"),
            rankings=[],
            total_candidates=0,
            qualified_candidates=0,
            match_time_ms=0,
            source="fallback",
            error=error or "AutoJob not available",
        )

    # -------------------------------------------------------------------
    # Sync methods (for evidence flywheel integration)
    # -------------------------------------------------------------------

    async def sync_task_completion(
        self,
        task: dict,
        worker_wallet: str,
    ) -> bool:
        """Notify AutoJob that a task was completed.

        This feeds the evidence flywheel: completed task evidence
        gets parsed into the worker's Skill DNA.

        Args:
            task: Completed task dict
            worker_wallet: Worker's Ethereum wallet

        Returns:
            True if sync was successful
        """
        if self.mode == BridgeMode.API:
            try:
                payload = json.dumps({
                    "wallet": worker_wallet,
                    "enrich_reputation": True,
                }).encode("utf-8")

                req = urllib.request.Request(
                    f"{self.autojob_url}/api/listener/sync-worker",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "EM-SwarmBridge/1.0",
                    },
                )

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("success", False)

            except Exception as e:
                logger.warning(f"AutoJob sync failed for {worker_wallet}: {e}")
                return False

        elif self.mode == BridgeMode.DIRECT:
            try:
                from em_event_listener import sync_worker
                result = sync_worker(
                    wallet=worker_wallet,
                    enrich_reputation=True,
                    workers_dir=self.workers_dir or "workers",
                    verbose=False,
                )
                return result.get("tasks", 0) > 0
            except Exception as e:
                logger.warning(f"AutoJob direct sync failed: {e}")
                return False

        return False

    async def get_leaderboard(
        self,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[dict]:
        """Get worker leaderboard from AutoJob.

        Args:
            category: Optional category filter
            limit: Max results

        Returns:
            List of leaderboard entries
        """
        if self.mode == BridgeMode.API:
            try:
                params = f"?limit={limit}"
                if category:
                    params += f"&category={category}"

                req = urllib.request.Request(
                    f"{self.autojob_url}/api/swarm/leaderboard{params}",
                    headers={"User-Agent": "EM-SwarmBridge/1.0"},
                )

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("leaderboard", [])

            except Exception as e:
                logger.warning(f"AutoJob leaderboard failed: {e}")
                return []

        elif self.mode == BridgeMode.DIRECT:
            try:
                from reputation_matcher import ReputationMatcher
                from worker_registry import WorkerRegistry

                registry = WorkerRegistry(storage_dir=self.workers_dir or "workers")
                matcher = ReputationMatcher(registry)
                return matcher.get_leaderboard(category=category, limit=limit)
            except Exception as e:
                logger.warning(f"AutoJob direct leaderboard failed: {e}")
                return []

        return []

    # -------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------

    def status(self) -> dict:
        """Get bridge status and statistics."""
        return {
            "mode": self.mode.value,
            "autojob_url": self.autojob_url if self.mode == BridgeMode.API else None,
            "workers_dir": self.workers_dir if self.mode == BridgeMode.DIRECT else None,
            "total_routes": self.total_routes,
            "total_fallbacks": self.total_fallbacks,
            "total_errors": self.total_errors,
            "fallback_rate": (
                self.total_fallbacks / max(1, self.total_routes)
            ),
        }
