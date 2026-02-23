"""
Karma Kadabra V2 — Reputation Bridge

Unified reputation scoring across three distinct data layers:

  1. ON-CHAIN (describe-net / ERC-8004):
     - SealRegistry scores (SKILLFUL, RELIABLE, THOROUGH, etc.)
     - Quadrant-aware (H2H, H2A, A2H, A2A)
     - Time-weighted decay (recent seals count more)
     - Immutable, verifiable, portable across platforms

  2. OFF-CHAIN (performance_tracker):
     - Historical completion rates, category specialization
     - Chain proficiency, budget fit, rating averages
     - Fast, local, updated every coordination cycle
     - Private to the swarm — competitive advantage data

  3. TRANSACTIONAL (EM API):
     - Per-task ratings (1-5 stars from task creators)
     - Bidirectional: agent→worker + worker→agent
     - Real-time, fresh from the most recent interactions
     - Public via API (anyone can query)

The bridge normalizes all three to a common 0-100 scale, computes a
weighted composite, and classifies agents into reputation tiers.

Design principles:
  - Pure functions — no side effects, easily testable
  - Graceful degradation — works with any subset of data sources
  - Configurable weights — tune the balance per use case
  - Coordinator-ready — output plugs directly into matching decisions
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.reputation_bridge")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# describe-net seal types (from SealRegistry.sol)
SEAL_TYPES = [
    "SKILLFUL", "RELIABLE", "THOROUGH", "ENGAGED", "HELPFUL",
    "CURIOUS", "FAIR", "ACCURATE", "RESPONSIVE", "ETHICAL",
    "CREATIVE", "PROFESSIONAL", "FRIENDLY",
]

# ERC-8004 quadrants
QUADRANTS = ["H2H", "H2A", "A2H", "A2A"]

# Reputation tiers (matching reputation-query.ts)
TIERS = [
    {"name": "Diamante", "emoji": "💎", "min": 81, "max": 100},
    {"name": "Oro", "emoji": "🥇", "min": 61, "max": 80},
    {"name": "Plata", "emoji": "🥈", "min": 31, "max": 60},
    {"name": "Bronce", "emoji": "🥉", "min": 0, "max": 30},
]

# Default weights for composite scoring
DEFAULT_WEIGHTS = {
    "on_chain": 0.30,     # 30% on-chain (immutable, verifiable)
    "off_chain": 0.40,    # 40% off-chain (rich historical data)
    "transactional": 0.30, # 30% transactional (fresh, real-time)
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReputationTier(Enum):
    """Reputation tier classification."""
    DIAMANTE = "Diamante"
    ORO = "Oro"
    PLATA = "Plata"
    BRONCE = "Bronce"
    UNKNOWN = "Unknown"


class DataSource(Enum):
    """Which reputation data source contributed."""
    ON_CHAIN = "on_chain"
    OFF_CHAIN = "off_chain"
    TRANSACTIONAL = "transactional"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SealScore:
    """A single on-chain seal score."""
    seal_type: str          # e.g., "SKILLFUL"
    quadrant: str           # e.g., "A2H"
    score: int              # 0-100
    evaluator: str          # wallet address
    timestamp: str          # ISO timestamp
    evidence_hash: str = "" # bytes32 hex
    seal_id: int = 0


@dataclass
class OnChainReputation:
    """Aggregated on-chain reputation from describe-net SealRegistry."""
    agent_address: str
    agent_id: int = 0
    seals: list[SealScore] = field(default_factory=list)
    seal_count: int = 0

    # Pre-computed aggregates (by seal type)
    type_averages: dict[str, float] = field(default_factory=dict)
    # Pre-computed aggregates (by quadrant)
    quadrant_averages: dict[str, float] = field(default_factory=dict)

    # Overall score (0-100)
    composite_score: float = 0.0
    confidence: float = 0.0  # 0-1, based on seal count

    @property
    def normalized_score(self) -> float:
        """Score normalized to 0-100."""
        return min(100.0, max(0.0, self.composite_score))


@dataclass
class OffChainReputation:
    """Reputation derived from performance_tracker data."""
    agent_name: str
    completion_rate: float = 0.5    # 0-1
    reliability_score: float = 0.5  # 0-1 (completion + ratings)
    avg_rating: float = 50.0        # 0-100 normalized
    tasks_completed: int = 0
    tasks_attempted: int = 0
    category_strengths: dict[str, float] = field(default_factory=dict)
    chain_experience: dict[str, float] = field(default_factory=dict)
    total_earned: float = 0.0

    @property
    def normalized_score(self) -> float:
        """Score normalized to 0-100."""
        # Weighted: 50% reliability, 30% rating, 20% experience breadth
        experience = min(1.0, len(self.category_strengths) / 5.0)  # More categories = more experienced
        raw = (
            0.50 * self.reliability_score * 100
            + 0.30 * self.avg_rating
            + 0.20 * experience * 100
        )
        return min(100.0, max(0.0, raw))

    @property
    def confidence(self) -> float:
        """Confidence in the off-chain score based on data volume."""
        if self.tasks_attempted == 0:
            return 0.0
        # Log scale: 1 task = 0.2, 5 = 0.5, 20 = 0.8, 50+ = 1.0
        return min(1.0, 0.2 + 0.3 * math.log(self.tasks_attempted + 1) / math.log(50))


@dataclass
class TransactionalReputation:
    """Reputation from EM API task ratings."""
    agent_id: int = 0
    agent_name: str = ""
    avg_rating_received: float = 0.0   # 0-100
    avg_rating_given: float = 0.0      # 0-100
    total_ratings_received: int = 0
    total_ratings_given: int = 0
    recent_ratings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def normalized_score(self) -> float:
        """Score normalized to 0-100."""
        if self.total_ratings_received == 0:
            return 50.0  # Neutral for unrated
        return min(100.0, max(0.0, self.avg_rating_received))

    @property
    def confidence(self) -> float:
        """Confidence based on number of ratings."""
        if self.total_ratings_received == 0:
            return 0.0
        return min(1.0, 0.3 + 0.3 * math.log(self.total_ratings_received + 1) / math.log(20))


@dataclass
class UnifiedReputation:
    """Combined reputation across all three layers."""
    agent_name: str
    agent_address: str = ""
    agent_id: int = 0

    # Individual layer scores (0-100)
    on_chain_score: float = 50.0
    off_chain_score: float = 50.0
    transactional_score: float = 50.0

    # Confidence per layer (0-1)
    on_chain_confidence: float = 0.0
    off_chain_confidence: float = 0.0
    transactional_confidence: float = 0.0

    # Composite
    composite_score: float = 50.0
    effective_confidence: float = 0.0  # Overall confidence
    tier: ReputationTier = ReputationTier.UNKNOWN

    # Which sources contributed
    sources_available: list[str] = field(default_factory=list)

    # Weights used
    weights_used: dict[str, float] = field(default_factory=dict)

    # Detailed breakdowns
    seal_type_scores: dict[str, float] = field(default_factory=dict)
    category_strengths: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_address": self.agent_address,
            "agent_id": self.agent_id,
            "composite_score": round(self.composite_score, 2),
            "tier": self.tier.value,
            "confidence": round(self.effective_confidence, 3),
            "layers": {
                "on_chain": {
                    "score": round(self.on_chain_score, 2),
                    "confidence": round(self.on_chain_confidence, 3),
                    "available": "on_chain" in self.sources_available,
                },
                "off_chain": {
                    "score": round(self.off_chain_score, 2),
                    "confidence": round(self.off_chain_confidence, 3),
                    "available": "off_chain" in self.sources_available,
                },
                "transactional": {
                    "score": round(self.transactional_score, 2),
                    "confidence": round(self.transactional_confidence, 3),
                    "available": "transactional" in self.sources_available,
                },
            },
            "weights_used": {k: round(v, 3) for k, v in self.weights_used.items()},
            "sources_available": self.sources_available,
            "seal_type_scores": {k: round(v, 2) for k, v in self.seal_type_scores.items()},
            "category_strengths": {k: round(v, 3) for k, v in self.category_strengths.items()},
        }


# ---------------------------------------------------------------------------
# Tier Classification
# ---------------------------------------------------------------------------

def classify_tier(score: float) -> ReputationTier:
    """Classify a 0-100 score into a reputation tier."""
    if score >= 81:
        return ReputationTier.DIAMANTE
    elif score >= 61:
        return ReputationTier.ORO
    elif score >= 31:
        return ReputationTier.PLATA
    elif score >= 0:
        return ReputationTier.BRONCE
    return ReputationTier.UNKNOWN


def tier_emoji(tier: ReputationTier) -> str:
    """Get the emoji for a reputation tier."""
    mapping = {
        ReputationTier.DIAMANTE: "💎",
        ReputationTier.ORO: "🥇",
        ReputationTier.PLATA: "🥈",
        ReputationTier.BRONCE: "🥉",
        ReputationTier.UNKNOWN: "❓",
    }
    return mapping.get(tier, "❓")


# ---------------------------------------------------------------------------
# On-Chain Score Computation
# ---------------------------------------------------------------------------

def compute_on_chain_score(
    seals: list[SealScore],
    time_decay_days: float = 90.0,
    now: datetime | None = None,
) -> OnChainReputation:
    """Compute aggregated on-chain reputation from seal scores.

    Uses time-weighted averaging: recent seals count more than old ones.
    Half-life for decay is configurable (default 90 days).

    Args:
        seals: List of SealScore entries from the SealRegistry.
        time_decay_days: Half-life in days for time weighting.
        now: Current time (for testing).

    Returns:
        OnChainReputation with aggregated scores.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    rep = OnChainReputation(
        agent_address=seals[0].evaluator if seals else "",
        seals=seals,
        seal_count=len(seals),
    )

    if not seals:
        rep.composite_score = 50.0  # Neutral
        rep.confidence = 0.0
        return rep

    # Time-weighted aggregation by seal type
    type_weighted_scores: dict[str, list[tuple[float, float]]] = {}  # type -> [(score, weight)]
    quadrant_weighted_scores: dict[str, list[tuple[float, float]]] = {}

    half_life_seconds = time_decay_days * 86400

    for seal in seals:
        # Compute time weight
        try:
            seal_time = datetime.fromisoformat(seal.timestamp.replace("Z", "+00:00"))
            age_seconds = max(0, (now - seal_time).total_seconds())
        except (ValueError, TypeError):
            age_seconds = 0  # Unknown timestamp = treat as fresh

        weight = math.exp(-0.693 * age_seconds / max(half_life_seconds, 1))

        # Aggregate by type
        if seal.seal_type not in type_weighted_scores:
            type_weighted_scores[seal.seal_type] = []
        type_weighted_scores[seal.seal_type].append((float(seal.score), weight))

        # Aggregate by quadrant
        if seal.quadrant not in quadrant_weighted_scores:
            quadrant_weighted_scores[seal.quadrant] = []
        quadrant_weighted_scores[seal.quadrant].append((float(seal.score), weight))

    # Compute weighted averages per type
    for seal_type, entries in type_weighted_scores.items():
        total_weight = sum(w for _, w in entries)
        if total_weight > 0:
            rep.type_averages[seal_type] = sum(s * w for s, w in entries) / total_weight

    # Compute weighted averages per quadrant
    for quadrant, entries in quadrant_weighted_scores.items():
        total_weight = sum(w for _, w in entries)
        if total_weight > 0:
            rep.quadrant_averages[quadrant] = sum(s * w for s, w in entries) / total_weight

    # Overall composite: average of all type averages
    if rep.type_averages:
        rep.composite_score = sum(rep.type_averages.values()) / len(rep.type_averages)
    else:
        rep.composite_score = 50.0

    # Confidence based on seal count (log scale)
    # 1 seal = 0.2, 5 = 0.5, 10 = 0.65, 20 = 0.8, 50+ = 0.95
    rep.confidence = min(1.0, 0.1 + 0.5 * math.log(len(seals) + 1) / math.log(20))

    return rep


# ---------------------------------------------------------------------------
# Off-Chain Score Extraction
# ---------------------------------------------------------------------------

def extract_off_chain_reputation(
    agent_name: str,
    performance_data: dict[str, Any] | None = None,
) -> OffChainReputation:
    """Extract off-chain reputation from performance tracker data.

    This bridges the performance_tracker.AgentPerformance dataclass
    into the reputation bridge's normalized format.

    Args:
        agent_name: Agent identifier.
        performance_data: Dict from performance.json or AgentPerformance.__dict__.

    Returns:
        OffChainReputation with normalized scores.
    """
    rep = OffChainReputation(agent_name=agent_name)

    if not performance_data:
        return rep

    rep.tasks_completed = performance_data.get("tasks_completed", 0)
    rep.tasks_attempted = performance_data.get("tasks_attempted", 0)
    rep.total_earned = performance_data.get("total_earned_usd", 0.0)

    # Completion rate
    if rep.tasks_attempted > 0:
        rep.completion_rate = rep.tasks_completed / rep.tasks_attempted
    else:
        rep.completion_rate = 0.5  # Neutral

    # Reliability score (from performance_tracker)
    rep.reliability_score = performance_data.get("reliability_score", 0.5)

    # Average rating (normalize to 0-100)
    avg_rating = performance_data.get("avg_rating_received", 0.0)
    if avg_rating > 0:
        rep.avg_rating = avg_rating  # Already 0-100 in our system
    else:
        rep.avg_rating = 50.0  # Neutral

    # Category strengths
    cat_completions = performance_data.get("category_completions", {})
    cat_attempts = performance_data.get("category_attempts", {})
    for cat in set(list(cat_completions.keys()) + list(cat_attempts.keys())):
        completed = cat_completions.get(cat, 0)
        attempted = cat_attempts.get(cat, 0)
        if attempted > 0:
            rep.category_strengths[cat] = completed / attempted
    
    # Chain experience
    chain_tasks = performance_data.get("chain_tasks", {})
    for chain, count in chain_tasks.items():
        if count > 0:
            rep.chain_experience[chain] = min(1.0, 0.3 + 0.3 * math.log(count + 1))

    return rep


# ---------------------------------------------------------------------------
# Transactional Score Extraction
# ---------------------------------------------------------------------------

def extract_transactional_reputation(
    agent_name: str,
    api_data: dict[str, Any] | None = None,
) -> TransactionalReputation:
    """Extract transactional reputation from EM API data.

    Args:
        agent_name: Agent identifier.
        api_data: Dict from EM API reputation endpoint.

    Returns:
        TransactionalReputation with normalized scores.
    """
    rep = TransactionalReputation(agent_name=agent_name)

    if not api_data:
        return rep

    rep.agent_id = api_data.get("agent_id", 0)

    # Ratings received
    rep.avg_rating_received = api_data.get("avg_rating_received", 0.0)
    rep.total_ratings_received = api_data.get("total_ratings_received", 0)

    # Ratings given
    rep.avg_rating_given = api_data.get("avg_rating_given", 0.0)
    rep.total_ratings_given = api_data.get("total_ratings_given", 0)

    # Recent ratings (for trend analysis)
    rep.recent_ratings = api_data.get("recent_ratings", [])

    return rep


# ---------------------------------------------------------------------------
# Unified Reputation Computation
# ---------------------------------------------------------------------------

def compute_unified_reputation(
    agent_name: str,
    on_chain: OnChainReputation | None = None,
    off_chain: OffChainReputation | None = None,
    transactional: TransactionalReputation | None = None,
    weights: dict[str, float] | None = None,
    confidence_boost: bool = True,
) -> UnifiedReputation:
    """Compute unified reputation across all available data sources.

    Uses confidence-weighted scoring: sources with higher confidence
    get proportionally more influence. If confidence_boost is True,
    weights are adjusted based on how much data each source has.

    Args:
        agent_name: Agent identifier.
        on_chain: On-chain reputation data (optional).
        off_chain: Off-chain reputation data (optional).
        transactional: Transactional reputation data (optional).
        weights: Custom weights (keys: on_chain, off_chain, transactional).
        confidence_boost: If True, adjust weights by confidence levels.

    Returns:
        UnifiedReputation with composite score and tier.
    """
    w = dict(weights or DEFAULT_WEIGHTS)
    unified = UnifiedReputation(agent_name=agent_name)
    unified.sources_available = []

    # Extract scores and confidences from available sources
    scores: dict[str, float] = {}
    confidences: dict[str, float] = {}

    if on_chain is not None:
        unified.on_chain_score = on_chain.normalized_score
        unified.on_chain_confidence = on_chain.confidence
        unified.agent_address = on_chain.agent_address
        unified.agent_id = on_chain.agent_id
        unified.seal_type_scores = dict(on_chain.type_averages)
        scores["on_chain"] = on_chain.normalized_score
        confidences["on_chain"] = on_chain.confidence
        unified.sources_available.append("on_chain")

    if off_chain is not None:
        unified.off_chain_score = off_chain.normalized_score
        unified.off_chain_confidence = off_chain.confidence
        unified.category_strengths = dict(off_chain.category_strengths)
        scores["off_chain"] = off_chain.normalized_score
        confidences["off_chain"] = off_chain.confidence
        unified.sources_available.append("off_chain")

    if transactional is not None:
        unified.transactional_score = transactional.normalized_score
        unified.transactional_confidence = transactional.confidence
        scores["transactional"] = transactional.normalized_score
        confidences["transactional"] = transactional.confidence
        unified.sources_available.append("transactional")

    if not scores:
        # No data at all — return neutral
        unified.composite_score = 50.0
        unified.tier = ReputationTier.PLATA
        unified.effective_confidence = 0.0
        unified.weights_used = w
        return unified

    # Compute effective weights
    if confidence_boost and len(scores) > 1:
        # Adjust weights by confidence: high-confidence sources get more weight
        effective_weights = {}
        for source in scores:
            base_weight = w.get(source, 1.0 / len(scores))
            confidence = confidences.get(source, 0.0)
            # Blend: 50% base weight + 50% confidence-adjusted
            effective_weights[source] = base_weight * (0.5 + 0.5 * confidence)

        # Normalize weights to sum to 1.0
        total_weight = sum(effective_weights.values())
        if total_weight > 0:
            effective_weights = {k: v / total_weight for k, v in effective_weights.items()}
        else:
            effective_weights = {k: 1.0 / len(scores) for k in scores}
    else:
        # Simple: just use base weights for available sources, normalized
        effective_weights = {k: w.get(k, 1.0 / len(scores)) for k in scores}
        total_weight = sum(effective_weights.values())
        if total_weight > 0:
            effective_weights = {k: v / total_weight for k, v in effective_weights.items()}

    unified.weights_used = effective_weights

    # Compute composite score
    composite = sum(scores[k] * effective_weights[k] for k in scores)
    unified.composite_score = min(100.0, max(0.0, composite))

    # Overall confidence: weighted average of individual confidences
    unified.effective_confidence = sum(
        confidences.get(k, 0.0) * effective_weights.get(k, 0.0) for k in scores
    )

    # Classify tier
    unified.tier = classify_tier(unified.composite_score)

    return unified


# ---------------------------------------------------------------------------
# Batch Operations
# ---------------------------------------------------------------------------

def compute_swarm_reputation(
    agents: dict[str, dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> dict[str, UnifiedReputation]:
    """Compute unified reputation for all agents in the swarm.

    Args:
        agents: Dict mapping agent_name to a dict with optional keys:
            - "on_chain": list of SealScore dicts or OnChainReputation
            - "off_chain": performance data dict or OffChainReputation
            - "transactional": API data dict or TransactionalReputation
        weights: Custom weights for all agents.

    Returns:
        Dict mapping agent_name to UnifiedReputation.
    """
    results: dict[str, UnifiedReputation] = {}

    for agent_name, data in agents.items():
        # Extract or build each layer
        on_chain = None
        off_chain = None
        transactional = None

        # On-chain
        on_chain_data = data.get("on_chain")
        if isinstance(on_chain_data, OnChainReputation):
            on_chain = on_chain_data
        elif isinstance(on_chain_data, list) and on_chain_data:
            # Convert list of dicts to SealScore objects
            seals = []
            for s in on_chain_data:
                if isinstance(s, SealScore):
                    seals.append(s)
                elif isinstance(s, dict):
                    seals.append(SealScore(
                        seal_type=s.get("seal_type", ""),
                        quadrant=s.get("quadrant", "A2H"),
                        score=s.get("score", 50),
                        evaluator=s.get("evaluator", ""),
                        timestamp=s.get("timestamp", ""),
                        evidence_hash=s.get("evidence_hash", ""),
                        seal_id=s.get("seal_id", 0),
                    ))
            if seals:
                on_chain = compute_on_chain_score(seals)

        # Off-chain
        off_chain_data = data.get("off_chain")
        if isinstance(off_chain_data, OffChainReputation):
            off_chain = off_chain_data
        elif isinstance(off_chain_data, dict):
            off_chain = extract_off_chain_reputation(agent_name, off_chain_data)

        # Transactional
        tx_data = data.get("transactional")
        if isinstance(tx_data, TransactionalReputation):
            transactional = tx_data
        elif isinstance(tx_data, dict):
            transactional = extract_transactional_reputation(agent_name, tx_data)

        results[agent_name] = compute_unified_reputation(
            agent_name=agent_name,
            on_chain=on_chain,
            off_chain=off_chain,
            transactional=transactional,
            weights=weights,
        )

    return results


def rank_by_reputation(
    reputations: dict[str, UnifiedReputation],
    min_confidence: float = 0.0,
) -> list[tuple[str, float, ReputationTier]]:
    """Rank agents by unified reputation score.

    Args:
        reputations: Dict of agent_name -> UnifiedReputation.
        min_confidence: Minimum confidence threshold to include.

    Returns:
        Sorted list of (agent_name, score, tier) tuples, highest first.
    """
    rankings = []
    for name, rep in reputations.items():
        if rep.effective_confidence >= min_confidence:
            rankings.append((name, rep.composite_score, rep.tier))

    rankings.sort(key=lambda x: x[1], reverse=True)
    return rankings


# ---------------------------------------------------------------------------
# Coordinator Integration
# ---------------------------------------------------------------------------

def reputation_boost_for_matching(
    reputation: UnifiedReputation,
    base_match_score: float,
    reputation_weight: float = 0.15,
) -> float:
    """Boost a coordinator match score using reputation data.

    This is designed to integrate with the existing 5-factor matching
    in coordinator_service.py. The reputation becomes a 6th factor.

    Args:
        reputation: Agent's unified reputation.
        base_match_score: The original 5-factor match score (0-1).
        reputation_weight: How much reputation influences the final score.

    Returns:
        Adjusted match score (0-1).
    """
    # Normalize reputation to 0-1
    rep_score = reputation.composite_score / 100.0

    # Apply confidence dampening: low confidence → less influence
    effective_rep = 0.5 + (rep_score - 0.5) * reputation.effective_confidence

    # Blend with base score
    boosted = base_match_score * (1 - reputation_weight) + effective_rep * reputation_weight

    return min(1.0, max(0.0, boosted))


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_reputation_snapshot(
    reputations: dict[str, UnifiedReputation],
    output_dir: Path,
) -> Path:
    """Save a reputation snapshot for all agents.

    Returns path to the saved JSON file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"reputation_snapshot_{timestamp}.json"
    path = output_dir / filename

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent_count": len(reputations),
        "agents": {name: rep.to_dict() for name, rep in reputations.items()},
        "leaderboard": [
            {"rank": i + 1, "agent": name, "score": round(score, 2), "tier": tier.value}
            for i, (name, score, tier) in enumerate(rank_by_reputation(reputations))
        ],
    }

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_reputation_snapshot(path: Path) -> dict[str, dict[str, Any]]:
    """Load a reputation snapshot from JSON.

    Returns raw dict (not UnifiedReputation objects) for flexibility.
    """
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("agents", {})
    except Exception as e:
        logger.warning(f"Failed to load reputation snapshot: {e}")
        return {}


def load_latest_snapshot(output_dir: Path) -> dict[str, dict[str, Any]]:
    """Load the most recent reputation snapshot from a directory."""
    if not output_dir.exists():
        return {}

    files = sorted(output_dir.glob("reputation_snapshot_*.json"), reverse=True)
    if not files:
        return {}

    return load_reputation_snapshot(files[0])


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------

def compute_reputation_trend(
    snapshots: list[dict[str, dict[str, Any]]],
    agent_name: str,
) -> dict[str, Any]:
    """Analyze how an agent's reputation has changed over time.

    Args:
        snapshots: List of snapshot dicts (most recent first).
        agent_name: Agent to analyze.

    Returns:
        Trend data with direction, delta, and per-layer trends.
    """
    if len(snapshots) < 2:
        return {"trend": "insufficient_data", "snapshots": len(snapshots)}

    scores = []
    for snap in snapshots:
        agent_data = snap.get(agent_name, {})
        scores.append(agent_data.get("composite_score", 50.0))

    if not scores or len(scores) < 2:
        return {"trend": "no_data", "agent": agent_name}

    # Compare most recent vs oldest
    delta = scores[0] - scores[-1]

    if delta > 5:
        trend = "improving"
    elif delta < -5:
        trend = "declining"
    else:
        trend = "stable"

    # Per-layer trends
    layer_trends = {}
    for layer in ["on_chain", "off_chain", "transactional"]:
        layer_scores = []
        for snap in snapshots:
            agent_data = snap.get(agent_name, {})
            layers = agent_data.get("layers", {})
            layer_data = layers.get(layer, {})
            layer_scores.append(layer_data.get("score", 50.0))

        if len(layer_scores) >= 2:
            layer_delta = layer_scores[0] - layer_scores[-1]
            layer_trends[layer] = {
                "current": round(layer_scores[0], 2),
                "delta": round(layer_delta, 2),
                "direction": "up" if layer_delta > 2 else ("down" if layer_delta < -2 else "flat"),
            }

    return {
        "trend": trend,
        "current_score": round(scores[0], 2),
        "delta": round(delta, 2),
        "snapshots_analyzed": len(scores),
        "layer_trends": layer_trends,
    }


# ---------------------------------------------------------------------------
# Leaderboard Generation
# ---------------------------------------------------------------------------

def generate_leaderboard(
    reputations: dict[str, UnifiedReputation],
    top_n: int = 0,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """Generate a formatted leaderboard from reputation data.

    Args:
        reputations: Dict of agent_name -> UnifiedReputation.
        top_n: Limit to top N agents (0 = all).
        min_confidence: Minimum confidence to include.

    Returns:
        List of leaderboard entry dicts.
    """
    ranked = rank_by_reputation(reputations, min_confidence)
    if top_n > 0:
        ranked = ranked[:top_n]

    leaderboard = []
    for i, (name, score, tier) in enumerate(ranked):
        rep = reputations[name]
        leaderboard.append({
            "rank": i + 1,
            "agent": name,
            "score": round(score, 2),
            "tier": tier.value,
            "emoji": tier_emoji(tier),
            "confidence": round(rep.effective_confidence, 3),
            "sources": len(rep.sources_available),
            "on_chain": round(rep.on_chain_score, 1),
            "off_chain": round(rep.off_chain_score, 1),
            "transactional": round(rep.transactional_score, 1),
        })

    return leaderboard


def format_leaderboard_text(leaderboard: list[dict[str, Any]]) -> str:
    """Format a leaderboard as human-readable text.

    Returns multi-line string suitable for IRC, Telegram, etc.
    """
    if not leaderboard:
        return "No reputation data available."

    lines = ["🏆 KK Swarm Reputation Leaderboard", ""]

    for entry in leaderboard:
        lines.append(
            f"  {entry['rank']:>2}. {entry['emoji']} {entry['agent']:<20} "
            f"Score: {entry['score']:>5.1f} ({entry['tier']}) "
            f"[{entry['sources']} sources, conf: {entry['confidence']:.1%}]"
        )
        lines.append(
            f"      On-chain: {entry['on_chain']:>5.1f} | "
            f"Off-chain: {entry['off_chain']:>5.1f} | "
            f"Transactional: {entry['transactional']:>5.1f}"
        )

    return "\n".join(lines)
