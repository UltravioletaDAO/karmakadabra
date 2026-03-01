"""
Karma Kadabra V2 — Intelligence Synthesizer

The compound intelligence layer that creates exponential value by
aggregating all subsystem data into unified routing decisions.

This is the "brain" that sits above individual components:

  Agent Profiler  ─┐
  Reputation Bridge ├──→ Intelligence Synthesizer ──→ Coordinator
  Lifecycle State  ─┤
  Evidence History ─┘

Instead of the coordinator doing ad-hoc 6-factor matching, it calls
the synthesizer which produces a *holistic* routing recommendation
that accounts for:

  1. Skill fitness (from profiler)
  2. Reputation tier (from on-chain/off-chain/transactional)
  3. Operational readiness (from lifecycle — is agent healthy?)
  4. Learning trajectory (from evidence — improving or declining?)
  5. Economic viability (profitability at this bounty level)
  6. Swarm balance (avoid overloading top performers)
  7. Cold-start priority (new agents need exposure)

The synthesis creates multiplier effects:
  - An agent with improving trajectory + good reputation gets a BOOST
  - An agent in cooldown + declining performance gets SUPPRESSED
  - A new agent with strong on-chain rep gets FAST-TRACKED
  - A profitable agent approaching burnout gets PROTECTED

These compound signals are invisible to individual components but
emerge when their data is cross-referenced.

Usage:
    synth = IntelligenceSynthesizer(workspaces_dir)
    ranking = synth.rank_agents_for_task(task)
    report = synth.generate_intelligence_report()
    synth.save_snapshot()
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kk.intelligence")


# ═══════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AgentIntelligence:
    """Unified intelligence profile for one agent.

    This is the compound view — synthesized from all subsystems.
    """

    agent_name: str

    # From Agent Profiler
    profiler_overall: float = 50.0       # 0-100
    profiler_reliability: float = 50.0   # 0-100
    profiler_efficiency: float = 50.0    # 0-100
    profiler_versatility: float = 0.0    # 0-100
    skill_ratings: dict[str, float] = field(default_factory=dict)  # category → success rate
    skill_trends: dict[str, str] = field(default_factory=dict)     # category → improving/stable/declining

    # From Reputation Bridge
    reputation_composite: float = 50.0   # 0-100
    reputation_tier: str = "Bronce"
    reputation_confidence: float = 0.0   # 0-1
    on_chain_score: float = 50.0
    off_chain_score: float = 50.0
    transactional_score: float = 50.0

    # From Lifecycle Manager
    lifecycle_state: str = "offline"     # AgentState value
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    is_healthy: bool = False
    uptime_hours: float = 0.0

    # From Evidence Processor
    recent_task_count: int = 0           # Tasks in last 24h
    recent_approval_rate: float = 0.0    # Approval rate in last 24h
    learning_trajectory: str = "stable"  # improving/stable/declining
    last_task_at: Optional[str] = None

    # Compound signals (computed by synthesizer)
    compound_score: float = 50.0         # 0-100 final routing score
    momentum: float = 0.0               # -50 to +50 (trajectory modifier)
    burnout_risk: float = 0.0            # 0-1 (risk of overload)
    cold_start_bonus: float = 0.0        # 0-20 (bonus for new agents)
    availability: float = 1.0            # 0-1 (operational readiness)
    economic_viability: float = 0.5      # 0-1 (profitable at given bounty)

    # Synthesis metadata
    sources_available: list[str] = field(default_factory=list)
    synthesis_timestamp: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "compound_score": round(self.compound_score, 1),
            "profiler": {
                "overall": round(self.profiler_overall, 1),
                "reliability": round(self.profiler_reliability, 1),
                "efficiency": round(self.profiler_efficiency, 1),
                "versatility": round(self.profiler_versatility, 1),
            },
            "reputation": {
                "composite": round(self.reputation_composite, 1),
                "tier": self.reputation_tier,
                "confidence": round(self.reputation_confidence, 2),
            },
            "lifecycle": {
                "state": self.lifecycle_state,
                "healthy": self.is_healthy,
                "failures": self.consecutive_failures,
            },
            "signals": {
                "momentum": round(self.momentum, 1),
                "burnout_risk": round(self.burnout_risk, 2),
                "cold_start_bonus": round(self.cold_start_bonus, 1),
                "availability": round(self.availability, 2),
                "economic_viability": round(self.economic_viability, 2),
                "learning_trajectory": self.learning_trajectory,
            },
            "sources": self.sources_available,
            "warnings": self.warnings,
            "timestamp": self.synthesis_timestamp,
        }


@dataclass
class TaskRoutingRequest:
    """A task that needs agent routing."""

    task_id: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    bounty_usd: float = 0.0
    payment_network: str = "base"
    evidence_types: list[str] = field(default_factory=list)
    requires_physical: bool = False

    @classmethod
    def from_em_task(cls, task: dict) -> "TaskRoutingRequest":
        """Create from an EM API task response."""
        instructions = task.get("instructions", task.get("description", ""))
        evidence_types = task.get("evidence_types", [])
        requires_physical = any(
            e in ("photo_geo", "video", "signature", "measurement")
            for e in evidence_types
        )
        return cls(
            task_id=task.get("id", ""),
            title=task.get("title", ""),
            description=instructions,
            category=task.get("category", ""),
            bounty_usd=float(task.get("bounty_usd", 0)),
            payment_network=task.get("payment_network", "base"),
            evidence_types=evidence_types,
            requires_physical=requires_physical,
        )


@dataclass
class RoutingDecision:
    """The synthesizer's routing recommendation."""

    task_id: str
    ranked_agents: list[tuple[str, float]] = field(default_factory=list)  # (name, score)
    selected_agent: Optional[str] = None
    selection_score: float = 0.0
    reasoning: list[str] = field(default_factory=list)
    alternatives: int = 0
    confidence: float = 0.0    # 0-1 (how confident in the routing)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "selected_agent": self.selected_agent,
            "selection_score": round(self.selection_score, 3),
            "confidence": round(self.confidence, 2),
            "alternatives": self.alternatives,
            "reasoning": self.reasoning,
            "warnings": self.warnings,
            "top_5": [
                {"agent": name, "score": round(score, 3)}
                for name, score in self.ranked_agents[:5]
            ],
        }


@dataclass
class SwarmIntelligenceReport:
    """Fleet-wide intelligence synthesis."""

    timestamp: str = ""
    total_agents: int = 0
    healthy_agents: int = 0
    working_agents: int = 0
    idle_agents: int = 0
    cooldown_agents: int = 0

    # Compound metrics
    swarm_health_score: float = 0.0       # 0-100
    intelligence_coverage: float = 0.0     # 0-1 (% of agents with full data)
    avg_compound_score: float = 0.0
    momentum_trend: str = "stable"         # overall swarm direction

    # Patterns detected
    bottlenecks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    # Agent tiers (from compound scoring)
    elite: list[str] = field(default_factory=list)       # top 10%
    reliable: list[str] = field(default_factory=list)     # 60-90th percentile
    developing: list[str] = field(default_factory=list)   # 30-60th percentile
    underperforming: list[str] = field(default_factory=list)  # bottom 30%

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "health": {
                "total": self.total_agents,
                "healthy": self.healthy_agents,
                "working": self.working_agents,
                "idle": self.idle_agents,
                "cooldown": self.cooldown_agents,
                "score": round(self.swarm_health_score, 1),
            },
            "intelligence": {
                "coverage": round(self.intelligence_coverage, 2),
                "avg_compound": round(self.avg_compound_score, 1),
                "momentum": self.momentum_trend,
            },
            "tiers": {
                "elite": self.elite,
                "reliable": self.reliable,
                "developing": self.developing,
                "underperforming": self.underperforming,
            },
            "patterns": {
                "bottlenecks": self.bottlenecks,
                "opportunities": self.opportunities,
                "risks": self.risks,
            },
        }


# ═══════════════════════════════════════════════════════════════════
# Intelligence Synthesizer
# ═══════════════════════════════════════════════════════════════════


# Synthesis weights — how much each data source contributes to compound score
SYNTHESIS_WEIGHTS = {
    "profiler": 0.30,         # 30% from profiler (skill fitness + history)
    "reputation": 0.20,       # 20% from reputation (cross-platform credibility)
    "lifecycle": 0.15,        # 15% from lifecycle (operational readiness)
    "evidence": 0.15,         # 15% from evidence (recent performance)
    "momentum": 0.10,         # 10% from learning trajectory
    "economics": 0.10,        # 10% from economic viability
}

# Momentum decay — how quickly trends lose influence
MOMENTUM_WINDOW_TASKS = 10    # Look at last N tasks for trajectory
MOMENTUM_MAX_BOOST = 15.0     # Maximum momentum bonus/penalty

# Burnout thresholds
BURNOUT_TASK_THRESHOLD = 8    # Tasks in last 24h before burnout risk
BURNOUT_MAX_PENALTY = 0.3     # Max reduction in availability

# Cold-start settings
COLD_START_TASK_THRESHOLD = 5  # Below this → agent is in cold-start
COLD_START_MAX_BONUS = 15.0    # Maximum cold-start boost

# Category keyword mapping for skill matching
CATEGORY_KEYWORDS = {
    "knowledge_access": {"knowledge", "question", "answer", "lookup", "information",
                         "explain", "wiki", "reference", "fact"},
    "content_creation": {"content", "write", "blog", "article", "creative", "copywriting",
                         "draft", "compose", "generate"},
    "data_collection": {"data", "collect", "survey", "scrape", "gather", "extract",
                        "database", "record", "compile"},
    "code_review": {"code", "review", "bug", "pr", "pull request", "audit", "security",
                    "vulnerability", "lint", "debug"},
    "research": {"research", "analyze", "study", "investigate", "compare", "evaluate",
                 "market", "competitive", "benchmark"},
    "translation": {"translate", "translation", "language", "localize", "i18n",
                    "multilingual", "español", "chinese"},
    "testing": {"test", "qa", "quality", "verify", "validation", "regression",
                "acceptance", "e2e", "integration"},
    "photo_verification": {"photo", "picture", "image", "verify", "location",
                           "proof", "visual"},
    "physical_presence": {"physical", "presence", "in-person", "location",
                          "meetup", "on-site", "local"},
}


class IntelligenceSynthesizer:
    """
    Aggregates all subsystem data into compound intelligence.

    The synthesizer doesn't own any data — it reads from:
      - Agent Profiler (performance profiles)
      - Reputation Bridge (reputation snapshots)
      - Lifecycle Manager (agent states)
      - Evidence Processor (completion history)

    And produces:
      - Per-agent compound intelligence (AgentIntelligence)
      - Task routing decisions (RoutingDecision)
      - Fleet intelligence reports (SwarmIntelligenceReport)
    """

    def __init__(self, workspaces_dir: str | Path = "./workspaces"):
        self.workspaces_dir = Path(workspaces_dir)
        self.data_dir = self.workspaces_dir.parent if self.workspaces_dir.name == "workspaces" else self.workspaces_dir / "data"
        self._intelligence: dict[str, AgentIntelligence] = {}
        self._last_synthesis: Optional[str] = None

    # ─────────────────────────────────────────────────
    # Data Loading (from each subsystem)
    # ─────────────────────────────────────────────────

    def _load_profiler_data(self) -> dict[str, dict]:
        """Load Agent Profiler output (performance.json in each workspace)."""
        profiles = {}
        if not self.workspaces_dir.exists():
            return profiles
        for d in self.workspaces_dir.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue
            perf_file = d / "performance.json"
            if perf_file.exists():
                try:
                    profiles[d.name] = json.loads(perf_file.read_text())
                except (json.JSONDecodeError, IOError):
                    pass
            # Also check evidence_history.json
            hist_file = d / "evidence_history.json"
            if hist_file.exists():
                try:
                    hist = json.loads(hist_file.read_text())
                    if d.name not in profiles:
                        profiles[d.name] = {}
                    if isinstance(hist, list):
                        profiles[d.name]["_evidence_history"] = hist
                    elif isinstance(hist, dict):
                        profiles[d.name]["_evidence_history"] = hist.get("completions", [])
                except (json.JSONDecodeError, IOError):
                    pass
        return profiles

    def _load_reputation_data(self) -> dict[str, dict]:
        """Load Reputation Bridge snapshots."""
        rep_dir = self.data_dir / "reputation"
        if not rep_dir.exists():
            return {}
        # Find latest snapshot
        snapshots = sorted(rep_dir.glob("snapshot_*.json"), reverse=True)
        if not snapshots:
            return {}
        try:
            return json.loads(snapshots[0].read_text())
        except (json.JSONDecodeError, IOError):
            return {}

    def _load_lifecycle_data(self) -> dict[str, dict]:
        """Load Lifecycle Manager state."""
        state_file = self.data_dir / "lifecycle_state.json"
        if not state_file.exists():
            return {}
        try:
            data = json.loads(state_file.read_text())
            agents = data if isinstance(data, list) else data.get("agents", [])
            return {a.get("agent_name", ""): a for a in agents if isinstance(a, dict)}
        except (json.JSONDecodeError, IOError):
            return {}

    def _load_evidence_data(self) -> dict[str, list]:
        """Load recent evidence history for all agents."""
        evidence = {}
        if not self.workspaces_dir.exists():
            return evidence
        for d in self.workspaces_dir.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue
            hist_file = d / "evidence_history.json"
            if hist_file.exists():
                try:
                    data = json.loads(hist_file.read_text())
                    entries = data if isinstance(data, list) else data.get("completions", [])
                    evidence[d.name] = entries
                except (json.JSONDecodeError, IOError):
                    pass
        return evidence

    # ─────────────────────────────────────────────────
    # Compound Signal Computation
    # ─────────────────────────────────────────────────

    def _compute_momentum(self, evidence: list[dict]) -> tuple[float, str]:
        """Compute learning trajectory from evidence history.

        Compares recent performance to historical average.
        Returns (momentum_value, trajectory_label).
        """
        if len(evidence) < 4:
            return 0.0, "stable"

        # Split into halves
        mid = len(evidence) // 2
        recent = evidence[mid:]
        older = evidence[:mid]

        recent_rate = sum(1 for e in recent if e.get("approved")) / max(len(recent), 1)
        older_rate = sum(1 for e in older if e.get("approved")) / max(len(older), 1)

        delta = recent_rate - older_rate

        if delta > 0.15:
            trajectory = "improving"
            momentum = min(MOMENTUM_MAX_BOOST, delta * 100)
        elif delta < -0.15:
            trajectory = "declining"
            momentum = max(-MOMENTUM_MAX_BOOST, delta * 100)
        else:
            trajectory = "stable"
            momentum = delta * 50  # Small nudge

        return momentum, trajectory

    def _compute_burnout_risk(self, evidence: list[dict], lifecycle: dict) -> float:
        """Compute burnout risk based on recent workload.

        Returns 0-1 risk score.
        """
        # Count tasks in last 24 hours
        now = time.time()
        cutoff = now - 86400
        recent_count = 0
        for e in evidence:
            ts = e.get("completed_at", e.get("timestamp", ""))
            if isinstance(ts, (int, float)) and ts > cutoff:
                recent_count += 1
            elif isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.timestamp() > cutoff:
                        recent_count += 1
                except (ValueError, TypeError):
                    pass

        # Consecutive failures also increase burnout
        failures = lifecycle.get("consecutive_failures", 0)

        # Risk formula
        workload_risk = min(1.0, recent_count / BURNOUT_TASK_THRESHOLD)
        failure_risk = min(1.0, failures / 5) * 0.3

        return min(1.0, workload_risk * 0.7 + failure_risk)

    def _compute_cold_start_bonus(self, total_tasks: int) -> float:
        """Give new agents a bonus to ensure they get task exposure.

        Without this, the coordinator would always prefer experienced agents,
        creating a rich-get-richer dynamic that starves new agents of data.
        """
        if total_tasks >= COLD_START_TASK_THRESHOLD:
            return 0.0

        # Linear decay from max bonus to 0 as tasks increase
        factor = 1.0 - (total_tasks / COLD_START_TASK_THRESHOLD)
        return COLD_START_MAX_BONUS * factor

    def _compute_availability(self, lifecycle: dict) -> float:
        """Compute operational readiness from lifecycle state.

        Returns 0-1 score where 1 = fully available.
        """
        state = lifecycle.get("state", "offline")
        state_scores = {
            "idle": 1.0,        # Available
            "working": 0.0,     # Busy (can't take new tasks)
            "starting": 0.3,    # Coming online
            "cooldown": 0.1,    # Circuit breaker tripped
            "draining": 0.0,    # Finishing up
            "stopping": 0.0,    # Shutting down
            "error": 0.0,       # Broken
            "offline": 0.0,     # Not running
        }
        return state_scores.get(state, 0.0)

    def _compute_economic_viability(
        self, profiler_data: dict, bounty_usd: float
    ) -> float:
        """Estimate whether a task is profitable for this agent.

        Returns 0-1 where 1 = highly profitable.
        """
        if bounty_usd <= 0:
            return 0.3  # Unknown bounty → neutral

        # Estimate cost from historical data
        total_tasks = profiler_data.get("total_tasks", 0)
        total_cost = profiler_data.get("total_cost_usd", 0)

        if total_tasks == 0 or total_cost == 0:
            return 0.5  # No data → assume neutral

        avg_cost = total_cost / total_tasks
        estimated_margin = (bounty_usd - avg_cost) / bounty_usd

        if estimated_margin > 0.7:
            return 1.0
        elif estimated_margin > 0.4:
            return 0.8
        elif estimated_margin > 0.1:
            return 0.6
        elif estimated_margin > 0:
            return 0.4
        else:
            return max(0.1, 0.3 + estimated_margin)  # Negative margin

    def _infer_task_category(self, title: str, description: str) -> str:
        """Infer task category from title and description keywords."""
        text = (title + " " + description).lower()
        best_cat = ""
        best_count = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text)
            if count > best_count:
                best_count = count
                best_cat = category
        return best_cat

    def _compute_skill_fitness(
        self, intel: AgentIntelligence, category: str, title: str, description: str
    ) -> float:
        """Compute how well an agent's skills match a specific task.

        Returns 0-100 fitness score.
        """
        if not category:
            category = self._infer_task_category(title, description)

        if not category:
            return 50.0  # No category → use base profiler score

        # Direct category match
        cat_rate = intel.skill_ratings.get(category, -1)
        if cat_rate >= 0:
            base = cat_rate * 100

            # Trend modifier
            trend = intel.skill_trends.get(category, "stable")
            if trend == "improving":
                base = min(100, base + 5)
            elif trend == "declining":
                base = max(0, base - 5)

            return base

        # No direct experience — fall back to profiler overall
        return intel.profiler_overall * 0.6  # Penalty for no category data

    # ─────────────────────────────────────────────────
    # Main Synthesis
    # ─────────────────────────────────────────────────

    def synthesize(self) -> dict[str, AgentIntelligence]:
        """Run the full intelligence synthesis across all agents.

        Loads data from all subsystems and produces compound intelligence
        profiles for every known agent.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Load all data sources
        profiler_data = self._load_profiler_data()
        reputation_data = self._load_reputation_data()
        lifecycle_data = self._load_lifecycle_data()
        evidence_data = self._load_evidence_data()

        # Discover all known agents
        all_agents = set()
        all_agents.update(profiler_data.keys())
        all_agents.update(reputation_data.keys())
        all_agents.update(lifecycle_data.keys())
        all_agents.update(evidence_data.keys())

        # Remove empty-string key if present
        all_agents.discard("")

        logger.info(
            f"Synthesizing intelligence for {len(all_agents)} agents "
            f"(profiler={len(profiler_data)}, reputation={len(reputation_data)}, "
            f"lifecycle={len(lifecycle_data)}, evidence={len(evidence_data)})"
        )

        for agent_name in all_agents:
            intel = AgentIntelligence(agent_name=agent_name, synthesis_timestamp=now)

            # --- Ingest Profiler Data ---
            prof = profiler_data.get(agent_name, {})
            if prof:
                intel.sources_available.append("profiler")
                intel.profiler_overall = prof.get("overall_score", 50.0)
                intel.profiler_reliability = prof.get("reliability_score",
                                                       prof.get("reliability", 50.0))
                intel.profiler_efficiency = prof.get("efficiency_score",
                                                      prof.get("efficiency", 50.0))
                intel.profiler_versatility = prof.get("versatility_score",
                                                       prof.get("versatility", 0.0))

                # Extract per-category skill ratings from evidence history
                history = prof.get("_evidence_history", [])
                if history:
                    cats: dict[str, list[bool]] = {}
                    for entry in history:
                        cat = entry.get("category", "")
                        if cat:
                            approved = entry.get("approved", False)
                            if cat not in cats:
                                cats[cat] = []
                            cats[cat].append(approved)
                    for cat, outcomes in cats.items():
                        intel.skill_ratings[cat] = sum(outcomes) / len(outcomes)
                        # Trend: compare last half vs first half
                        if len(outcomes) >= 6:
                            mid = len(outcomes) // 2
                            recent = sum(outcomes[mid:]) / len(outcomes[mid:])
                            older = sum(outcomes[:mid]) / len(outcomes[:mid])
                            if recent > older + 0.1:
                                intel.skill_trends[cat] = "improving"
                            elif recent < older - 0.1:
                                intel.skill_trends[cat] = "declining"
                            else:
                                intel.skill_trends[cat] = "stable"

            # --- Ingest Reputation Data ---
            rep = reputation_data.get(agent_name, {})
            if rep:
                intel.sources_available.append("reputation")
                intel.reputation_composite = rep.get("composite_score", 50.0)
                intel.reputation_tier = rep.get("tier", "Bronce")
                intel.reputation_confidence = rep.get("confidence", 0.0)
                layers = rep.get("layers", {})
                intel.on_chain_score = layers.get("on_chain", {}).get("score", 50.0)
                intel.off_chain_score = layers.get("off_chain", {}).get("score", 50.0)
                intel.transactional_score = layers.get("transactional", {}).get("score", 50.0)

            # --- Ingest Lifecycle Data ---
            lc = lifecycle_data.get(agent_name, {})
            if lc:
                intel.sources_available.append("lifecycle")
                intel.lifecycle_state = lc.get("state", "offline")
                intel.consecutive_failures = lc.get("consecutive_failures", 0)
                intel.total_successes = lc.get("total_successes", 0)
                intel.total_failures = lc.get("total_failures", 0)
                intel.is_healthy = intel.lifecycle_state in ("idle", "working")

            # --- Ingest Evidence Data ---
            ev = evidence_data.get(agent_name, [])
            if ev:
                intel.sources_available.append("evidence")
                intel.recent_task_count = len(ev)
                approved = sum(1 for e in ev if e.get("approved"))
                intel.recent_approval_rate = approved / max(len(ev), 1)

                # Last task timestamp
                for entry in reversed(ev):
                    ts = entry.get("completed_at", entry.get("timestamp"))
                    if ts:
                        intel.last_task_at = str(ts)
                        break

            # --- Compute Compound Signals ---
            intel.momentum, intel.learning_trajectory = self._compute_momentum(ev)
            intel.burnout_risk = self._compute_burnout_risk(ev, lc)

            total_tasks = prof.get("total_tasks", 0) + len(ev)
            intel.cold_start_bonus = self._compute_cold_start_bonus(total_tasks)

            intel.availability = self._compute_availability(lc)

            # --- Compute Compound Score ---
            # Weighted synthesis of all signals
            profiler_contrib = intel.profiler_overall * SYNTHESIS_WEIGHTS["profiler"]
            reputation_contrib = intel.reputation_composite * SYNTHESIS_WEIGHTS["reputation"]

            # Lifecycle: healthy = full weight, unhealthy = 0
            lifecycle_score = 100.0 if intel.is_healthy else (
                50.0 if intel.lifecycle_state == "starting" else 0.0
            )
            lifecycle_contrib = lifecycle_score * SYNTHESIS_WEIGHTS["lifecycle"]

            # Evidence: recent approval rate
            evidence_score = intel.recent_approval_rate * 100 if ev else 50.0
            evidence_contrib = evidence_score * SYNTHESIS_WEIGHTS["evidence"]

            # Momentum
            momentum_contrib = intel.momentum  # Already scaled

            # Economics (base — will be task-specific in route_task)
            econ_score = intel.profiler_efficiency
            econ_contrib = econ_score * SYNTHESIS_WEIGHTS["economics"]

            raw_score = (
                profiler_contrib
                + reputation_contrib
                + lifecycle_contrib
                + evidence_contrib
                + momentum_contrib
                + econ_contrib
            )

            # Apply cold-start bonus
            raw_score += intel.cold_start_bonus

            # Apply burnout penalty
            raw_score *= (1.0 - intel.burnout_risk * BURNOUT_MAX_PENALTY)

            intel.compound_score = max(0, min(100, raw_score))

            # --- Warnings ---
            if intel.burnout_risk > 0.7:
                intel.warnings.append("High burnout risk — reduce workload")
            if intel.consecutive_failures >= 3:
                intel.warnings.append("Circuit breaker may trip — investigate failures")
            if not intel.sources_available:
                intel.warnings.append("No data sources available — cold start")
            if intel.learning_trajectory == "declining":
                intel.warnings.append("Performance declining — review task assignments")

            self._intelligence[agent_name] = intel

        self._last_synthesis = now
        logger.info(f"Synthesis complete: {len(self._intelligence)} agents profiled")
        return self._intelligence

    # ─────────────────────────────────────────────────
    # Task Routing
    # ─────────────────────────────────────────────────

    def route_task(
        self,
        task: TaskRoutingRequest,
        exclude_agents: Optional[set[str]] = None,
        min_score: float = 10.0,
    ) -> RoutingDecision:
        """Route a task to the best available agent.

        Uses compound intelligence for holistic ranking.
        """
        if not self._intelligence:
            self.synthesize()

        exclude = exclude_agents or set()
        decision = RoutingDecision(task_id=task.task_id)

        # Physical tasks: only human-routable agents or skip
        if task.requires_physical:
            decision.warnings.append("Task requires physical presence — routing to human worker")
            decision.reasoning.append("Physical task detected — no AI agent eligible")
            return decision

        candidates = []
        for name, intel in self._intelligence.items():
            if name in exclude:
                continue
            if intel.availability <= 0:
                continue

            # Compute task-specific fitness
            skill_fitness = self._compute_skill_fitness(
                intel, task.category, task.title, task.description
            )

            # Economic viability for this specific bounty
            prof_data = {}
            perf_file = self.workspaces_dir / name / "performance.json"
            if perf_file.exists():
                try:
                    prof_data = json.loads(perf_file.read_text())
                except (json.JSONDecodeError, IOError):
                    pass
            econ = self._compute_economic_viability(prof_data, task.bounty_usd)

            # Task-specific compound score
            task_score = (
                skill_fitness * 0.35           # Skill fit for THIS task
                + intel.reputation_composite * 0.15  # Credibility
                + intel.profiler_reliability * 0.15  # Track record
                + econ * 100 * 0.10             # Profitability
                + intel.momentum                # Learning trajectory
                + intel.cold_start_bonus        # Cold-start exploration
            )

            # Availability gate
            task_score *= intel.availability

            # Burnout protection
            task_score *= (1.0 - intel.burnout_risk * BURNOUT_MAX_PENALTY)

            if task_score >= min_score:
                candidates.append((name, task_score))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        decision.ranked_agents = candidates
        decision.alternatives = max(0, len(candidates) - 1)

        if candidates:
            best_name, best_score = candidates[0]
            decision.selected_agent = best_name
            decision.selection_score = best_score

            # Confidence: based on data availability and score margin
            intel = self._intelligence[best_name]
            data_confidence = len(intel.sources_available) / 4  # 4 possible sources
            margin_confidence = 1.0
            if len(candidates) >= 2:
                gap = candidates[0][1] - candidates[1][1]
                margin_confidence = min(1.0, gap / 20)  # Larger gap = more confident
            decision.confidence = (data_confidence * 0.6 + margin_confidence * 0.4)

            # Reasoning
            decision.reasoning.append(
                f"Selected {best_name} (score={best_score:.1f}, "
                f"sources={intel.sources_available})"
            )
            if intel.learning_trajectory == "improving":
                decision.reasoning.append(f"{best_name} is on an improving trajectory")
            if intel.cold_start_bonus > 0:
                decision.reasoning.append(
                    f"{best_name} gets cold-start bonus (+{intel.cold_start_bonus:.1f}) "
                    f"for exploration"
                )
            if intel.burnout_risk > 0.5:
                decision.warnings.append(
                    f"{best_name} has elevated burnout risk ({intel.burnout_risk:.0%})"
                )
        else:
            decision.reasoning.append("No eligible agents found")
            decision.warnings.append(
                f"All agents excluded, unavailable, or below min_score={min_score}"
            )

        return decision

    # ─────────────────────────────────────────────────
    # Fleet Intelligence
    # ─────────────────────────────────────────────────

    def generate_intelligence_report(self) -> SwarmIntelligenceReport:
        """Generate a fleet-wide intelligence report.

        Identifies patterns, bottlenecks, and opportunities that are
        invisible to individual subsystems.
        """
        if not self._intelligence:
            self.synthesize()

        report = SwarmIntelligenceReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_agents=len(self._intelligence),
        )

        scores = []
        momentums = []

        for name, intel in self._intelligence.items():
            scores.append(intel.compound_score)
            momentums.append(intel.momentum)

            # Count states
            if intel.is_healthy:
                report.healthy_agents += 1
            if intel.lifecycle_state == "working":
                report.working_agents += 1
            elif intel.lifecycle_state == "idle":
                report.idle_agents += 1
            elif intel.lifecycle_state == "cooldown":
                report.cooldown_agents += 1

            # Intelligence coverage
            if len(intel.sources_available) == 4:
                report.intelligence_coverage += 1

        if report.total_agents > 0:
            report.intelligence_coverage /= report.total_agents

        # Health score
        if report.total_agents > 0:
            report.swarm_health_score = (
                (report.healthy_agents / report.total_agents) * 50
                + min(50, sum(scores) / len(scores))
            )

        # Average compound score
        if scores:
            report.avg_compound_score = sum(scores) / len(scores)

        # Overall momentum trend
        if momentums:
            avg_momentum = sum(momentums) / len(momentums)
            if avg_momentum > 3:
                report.momentum_trend = "improving"
            elif avg_momentum < -3:
                report.momentum_trend = "declining"

        # Tier classification
        sorted_agents = sorted(
            self._intelligence.items(),
            key=lambda x: x[1].compound_score,
            reverse=True,
        )
        total = len(sorted_agents)
        for i, (name, intel) in enumerate(sorted_agents):
            pct = i / max(total, 1)
            if pct < 0.10:
                report.elite.append(name)
            elif pct < 0.40:
                report.reliable.append(name)
            elif pct < 0.70:
                report.developing.append(name)
            else:
                report.underperforming.append(name)

        # Pattern detection
        declining_count = sum(
            1 for i in self._intelligence.values()
            if i.learning_trajectory == "declining"
        )
        if declining_count > total * 0.3:
            report.risks.append(
                f"{declining_count} agents declining — possible systemic issue"
            )

        burnout_count = sum(
            1 for i in self._intelligence.values()
            if i.burnout_risk > 0.6
        )
        if burnout_count > 0:
            report.risks.append(
                f"{burnout_count} agents at burnout risk — workload rebalancing needed"
            )

        cold_count = sum(
            1 for i in self._intelligence.values()
            if i.cold_start_bonus > 0
        )
        if cold_count > total * 0.5:
            report.opportunities.append(
                f"{cold_count} agents in cold-start — fleet is underutilized"
            )

        # Bottleneck: too few idle agents relative to workload
        if report.idle_agents == 0 and report.working_agents > 0:
            report.bottlenecks.append(
                "No idle agents — swarm is at capacity"
            )
        elif report.idle_agents < 3 and report.total_agents > 10:
            report.bottlenecks.append(
                f"Only {report.idle_agents} idle agents — approaching capacity"
            )

        # Opportunity: skill gaps
        all_categories = set(CATEGORY_KEYWORDS.keys())
        covered_categories = set()
        for intel in self._intelligence.values():
            covered_categories.update(intel.skill_ratings.keys())
        uncovered = all_categories - covered_categories
        if uncovered:
            report.opportunities.append(
                f"Uncovered categories: {', '.join(sorted(uncovered))}"
            )

        return report

    # ─────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────

    def save_snapshot(self, output_dir: Optional[Path] = None) -> Path:
        """Save intelligence snapshot to disk."""
        out = output_dir or self.data_dir / "intelligence"
        out.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = out / f"intelligence_{ts}.json"

        snapshot = {
            "timestamp": self._last_synthesis,
            "agents": {
                name: intel.to_dict()
                for name, intel in self._intelligence.items()
            },
            "report": self.generate_intelligence_report().to_dict(),
        }

        path.write_text(json.dumps(snapshot, indent=2))
        logger.info(f"Intelligence snapshot saved to {path}")
        return path

    def load_latest_snapshot(self, input_dir: Optional[Path] = None) -> Optional[dict]:
        """Load the most recent intelligence snapshot."""
        src = input_dir or self.data_dir / "intelligence"
        if not src.exists():
            return None
        snapshots = sorted(src.glob("intelligence_*.json"), reverse=True)
        if not snapshots:
            return None
        try:
            return json.loads(snapshots[0].read_text())
        except (json.JSONDecodeError, IOError):
            return None

    # ─────────────────────────────────────────────────
    # Report Formatting
    # ─────────────────────────────────────────────────

    def format_intelligence_report(self) -> str:
        """Human-readable intelligence report."""
        report = self.generate_intelligence_report()

        lines = [
            "═" * 65,
            "  🧠 KK V2 — Swarm Intelligence Report",
            f"  {report.timestamp}",
            "═" * 65,
            "",
            f"  Health Score: {report.swarm_health_score:.0f}/100",
            f"  Intelligence Coverage: {report.intelligence_coverage:.0%}",
            f"  Average Compound Score: {report.avg_compound_score:.0f}/100",
            f"  Momentum: {report.momentum_trend}",
            "",
            f"  Agents: {report.total_agents} total",
            f"    🟢 Healthy: {report.healthy_agents} "
            f"({report.working_agents} working, {report.idle_agents} idle)",
            f"    ⏸️  Cooldown: {report.cooldown_agents}",
            "",
        ]

        if report.elite:
            lines.append(f"  💎 Elite: {', '.join(report.elite)}")
        if report.reliable:
            lines.append(f"  🥇 Reliable: {', '.join(report.reliable)}")
        if report.developing:
            lines.append(f"  🔵 Developing: {', '.join(report.developing)}")
        if report.underperforming:
            lines.append(f"  ⚠️  Underperforming: {', '.join(report.underperforming)}")

        if report.bottlenecks or report.opportunities or report.risks:
            lines.append("")
            lines.append("  Patterns Detected:")
            for b in report.bottlenecks:
                lines.append(f"    🚧 Bottleneck: {b}")
            for o in report.opportunities:
                lines.append(f"    💡 Opportunity: {o}")
            for r in report.risks:
                lines.append(f"    ⚠️  Risk: {r}")

        lines.extend(["", "═" * 65])
        return "\n".join(lines)

    def format_routing_decision(self, decision: RoutingDecision) -> str:
        """Human-readable routing decision."""
        lines = [
            f"  Routing Decision: task={decision.task_id}",
            f"  Selected: {decision.selected_agent or 'NONE'} "
            f"(score={decision.selection_score:.1f}, confidence={decision.confidence:.0%})",
        ]
        for r in decision.reasoning:
            lines.append(f"    → {r}")
        for w in decision.warnings:
            lines.append(f"    ⚠️  {w}")
        if decision.alternatives > 0:
            lines.append(f"    ({decision.alternatives} alternatives available)")
        return "\n".join(lines)
