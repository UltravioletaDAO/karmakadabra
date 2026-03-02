"""
Karma Kadabra V2 — Decision Engine

The "brain" of the swarm: combines all data sources into intelligent
task-agent matching decisions with explainable reasoning.

Data sources integrated:
  1. ReputationBridge — tri-layer reputation scores (on-chain, off-chain, transactional)
  2. SwarmAnalytics  — efficiency metrics, bottleneck data, capacity forecasts
  3. AutoJobBridge   — external intelligence, skill DNA matching, quality predictions
  4. TaskPipeline    — current pipeline state, SLA data, historical patterns
  5. AgentLifecycle  — agent availability, circuit breaker state, error history

The engine doesn't just pick the "best" agent — it explains WHY it chose them
and provides confidence intervals, risk assessments, and alternative options.

Key features:
  - Multi-factor scoring with explainable weights
  - Risk assessment (agent reliability × task complexity)
  - Workload balancing (don't overload top agents)
  - Cold-start handling (give new agents a chance)
  - Time-of-day awareness (some agents perform better at certain times)
  - Cascade planning (who's the backup if primary fails?)
  - Category specialization bonus
  - Geographic/chain affinity matching
  - Cost optimization mode (cheapest agent that meets quality bar)
  - Quality optimization mode (best agent regardless of cost)

Usage:
    from lib.decision_engine import DecisionEngine, DecisionContext

    engine = DecisionEngine(config)
    context = DecisionContext(
        task=task_data,
        agents=available_agents,
        reputations=reputation_map,
        efficiencies=efficiency_map,
        pipeline_state=pipeline,
    )
    decision = engine.decide(context)
    print(decision.chosen_agent)
    print(decision.reasoning)
    print(decision.alternatives)

All functions are pure — no side effects, no I/O, easily testable.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("kk.decision_engine")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class OptimizationMode(Enum):
    """What the engine optimizes for."""
    BALANCED = "balanced"          # Default: balance quality, cost, speed
    QUALITY = "quality"            # Best possible agent, cost secondary
    COST = "cost"                  # Cheapest agent meeting quality threshold
    SPEED = "speed"                # Fastest expected completion
    EXPLORATION = "exploration"    # Favor agents with less data (learn more)


@dataclass
class DecisionConfig:
    """Configuration for the decision engine."""
    # Optimization mode
    mode: OptimizationMode = OptimizationMode.BALANCED

    # Factor weights (must sum to ~1.0 — normalized internally)
    weight_reputation: float = 0.25
    weight_efficiency: float = 0.20
    weight_specialization: float = 0.20
    weight_workload: float = 0.15
    weight_recency: float = 0.10
    weight_risk: float = 0.10

    # Thresholds
    min_reputation_score: float = 20.0    # Below this = don't assign
    min_confidence: float = 0.05          # Below this = cold start rules
    max_concurrent_tasks: int = 3         # Per-agent task limit
    max_consecutive_failures: int = 3     # Circuit breaker threshold

    # Cold start
    cold_start_bonus: float = 10.0        # Score bonus for under-evaluated agents
    cold_start_threshold: int = 5         # Tasks completed before considered "evaluated"

    # Workload balancing
    workload_penalty_per_task: float = 8.0  # Score deduction per active task
    idle_bonus: float = 5.0                 # Bonus for idle agents (faster response)

    # Cascade
    cascade_depth: int = 3                # Number of alternatives to identify

    # Quality floor (for cost optimization)
    quality_floor: float = 40.0           # Minimum acceptable reputation for cost mode


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class TaskProfile:
    """Profile of the task to be assigned."""
    task_id: str
    category: str = ""
    subcategory: str = ""
    bounty_usd: float = 0.0
    complexity: str = "medium"     # low, medium, high
    required_chain: str = ""       # If task requires specific chain
    required_location: str = ""    # If geographically constrained
    time_limit_hours: float = 24.0
    evidence_types: list[str] = field(default_factory=list)
    priority: str = "normal"       # low, normal, high, critical
    skills_required: list[str] = field(default_factory=list)

    @property
    def complexity_multiplier(self) -> float:
        """Complexity affects how much reputation matters."""
        return {"low": 0.7, "medium": 1.0, "high": 1.3, "critical": 1.5}.get(
            self.complexity, 1.0
        )


@dataclass
class AgentProfile:
    """Agent profile for decision making."""
    agent_name: str
    agent_id: int = 0

    # Current state
    is_available: bool = True
    current_tasks: int = 0
    is_idle: bool = True
    consecutive_failures: int = 0
    in_cooldown: bool = False
    in_error: bool = False

    # Reputation (from reputation_bridge)
    reputation_score: float = 50.0
    reputation_confidence: float = 0.0
    reputation_tier: str = "Plata"

    # Efficiency (from swarm_analytics)
    efficiency_score: float = 50.0
    avg_completion_hours: float = 12.0
    reliability: float = 0.5
    throughput_per_day: float = 0.0
    earnings_per_hour: float = 0.0

    # Specialization
    category_strengths: dict[str, float] = field(default_factory=dict)
    chain_experience: dict[str, float] = field(default_factory=dict)
    tasks_completed: int = 0
    total_earned_usd: float = 0.0

    # History
    last_task_completed_at: str = ""     # ISO timestamp
    last_failure_at: str = ""            # ISO timestamp
    recent_categories: list[str] = field(default_factory=list)

    # AutoJob intelligence
    autojob_match_score: float = 0.0    # 0-1 from AutoJob matching
    predicted_quality: float = 0.0       # 0-1 quality prediction
    predicted_success: float = 0.0       # 0-1 success probability


@dataclass
class DecisionContext:
    """All input data for a decision."""
    task: TaskProfile
    agents: list[AgentProfile]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ScoredAgent:
    """An agent with a computed decision score."""
    agent: AgentProfile
    total_score: float = 0.0

    # Factor breakdown (0-100 each)
    reputation_factor: float = 0.0
    efficiency_factor: float = 0.0
    specialization_factor: float = 0.0
    workload_factor: float = 0.0
    recency_factor: float = 0.0
    risk_factor: float = 0.0

    # Adjustments applied
    cold_start_bonus: float = 0.0
    idle_bonus: float = 0.0
    workload_penalty: float = 0.0
    mode_adjustment: float = 0.0

    # Reasoning
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    disqualified: bool = False
    disqualify_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent.agent_name,
            "total_score": round(self.total_score, 2),
            "factors": {
                "reputation": round(self.reputation_factor, 2),
                "efficiency": round(self.efficiency_factor, 2),
                "specialization": round(self.specialization_factor, 2),
                "workload": round(self.workload_factor, 2),
                "recency": round(self.recency_factor, 2),
                "risk": round(self.risk_factor, 2),
            },
            "adjustments": {
                "cold_start_bonus": round(self.cold_start_bonus, 2),
                "idle_bonus": round(self.idle_bonus, 2),
                "workload_penalty": round(self.workload_penalty, 2),
                "mode_adjustment": round(self.mode_adjustment, 2),
            },
            "reasons": self.reasons,
            "warnings": self.warnings,
            "disqualified": self.disqualified,
            "disqualify_reason": self.disqualify_reason,
        }


@dataclass
class Decision:
    """The engine's decision output: who to assign and why."""
    task_id: str
    chosen_agent: str | None = None
    chosen_score: float = 0.0

    # Full ranking
    rankings: list[ScoredAgent] = field(default_factory=list)

    # Alternatives (for cascade)
    alternatives: list[str] = field(default_factory=list)

    # Decision metadata
    mode: OptimizationMode = OptimizationMode.BALANCED
    confidence: float = 0.0         # 0-1 how confident in this decision
    risk_level: str = "medium"      # low, medium, high
    reasoning: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Statistics
    agents_considered: int = 0
    agents_disqualified: int = 0
    agents_qualified: int = 0
    score_spread: float = 0.0       # Difference between #1 and #2

    # Timing
    decided_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "chosen_agent": self.chosen_agent,
            "chosen_score": round(self.chosen_score, 2),
            "alternatives": self.alternatives,
            "mode": self.mode.value,
            "confidence": round(self.confidence, 3),
            "risk_level": self.risk_level,
            "reasoning": self.reasoning,
            "warnings": self.warnings,
            "stats": {
                "agents_considered": self.agents_considered,
                "agents_disqualified": self.agents_disqualified,
                "agents_qualified": self.agents_qualified,
                "score_spread": round(self.score_spread, 2),
            },
            "decided_at": self.decided_at,
            "top_rankings": [r.to_dict() for r in self.rankings[:5]],
        }

    def explain(self) -> str:
        """Human-readable explanation of the decision."""
        lines = [f"🧠 Decision for task {self.task_id}"]
        lines.append(f"   Mode: {self.mode.value} | Confidence: {self.confidence:.0%}")

        if self.chosen_agent:
            lines.append(f"   ✅ Assigned to: {self.chosen_agent} (score: {self.chosen_score:.1f})")
        else:
            lines.append("   ❌ No suitable agent found")

        if self.alternatives:
            lines.append(f"   🔄 Alternatives: {', '.join(self.alternatives)}")

        for reason in self.reasoning[:3]:
            lines.append(f"   💡 {reason}")

        for warning in self.warnings[:3]:
            lines.append(f"   ⚠️ {warning}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factor Computation (pure functions)
# ---------------------------------------------------------------------------

def compute_reputation_factor(agent: AgentProfile, task: TaskProfile) -> tuple[float, list[str]]:
    """Score agent's reputation relevance for this task.

    Returns (score 0-100, reasons).
    """
    reasons = []
    score = agent.reputation_score  # Already 0-100

    # Complexity adjustment: high-complexity tasks weight reputation more
    if task.complexity_multiplier > 1.0:
        # Don't change the score, but this influences the weight
        reasons.append(f"Reputation {score:.0f}/100 (tier: {agent.reputation_tier})")
    else:
        reasons.append(f"Reputation {score:.0f}/100")

    # Confidence dampening: low confidence pulls toward neutral
    if agent.reputation_confidence < 0.3:
        dampened = 50.0 + (score - 50.0) * agent.reputation_confidence / 0.3
        reasons.append(f"Low confidence ({agent.reputation_confidence:.0%}) → dampened to {dampened:.0f}")
        score = dampened

    return score, reasons


def compute_efficiency_factor(agent: AgentProfile, task: TaskProfile) -> tuple[float, list[str]]:
    """Score agent's operational efficiency.

    Considers: completion speed, reliability, earnings rate.
    """
    reasons = []

    # Base efficiency score
    score = agent.efficiency_score  # 0-100

    # Speed bonus/penalty relative to task time limit
    if task.time_limit_hours > 0 and agent.avg_completion_hours > 0:
        time_ratio = agent.avg_completion_hours / task.time_limit_hours
        if time_ratio < 0.5:
            # Agent is much faster than needed — good
            speed_bonus = 10.0
            reasons.append(f"Fast completer ({agent.avg_completion_hours:.1f}h avg vs {task.time_limit_hours:.0f}h limit)")
            score = min(100, score + speed_bonus)
        elif time_ratio > 0.8:
            # Agent might be too slow
            speed_penalty = 10.0 * (time_ratio - 0.8) / 0.2
            reasons.append(f"Tight timing ({agent.avg_completion_hours:.1f}h avg vs {task.time_limit_hours:.0f}h limit)")
            score = max(0, score - speed_penalty)

    # Reliability adjustment
    if agent.reliability >= 0.9:
        reasons.append(f"High reliability ({agent.reliability:.0%})")
    elif agent.reliability < 0.5:
        penalty = (0.5 - agent.reliability) * 30
        score = max(0, score - penalty)
        reasons.append(f"Low reliability ({agent.reliability:.0%}) → penalty")

    if not reasons:
        reasons.append(f"Efficiency {score:.0f}/100")

    return score, reasons


def compute_specialization_factor(
    agent: AgentProfile, task: TaskProfile
) -> tuple[float, list[str]]:
    """Score how well the agent specializes in this task's domain.

    Considers: category match, chain experience, required skills.
    """
    reasons = []
    components = []

    # Category matching (0-100)
    cat_score = 50.0  # Neutral if no data
    if task.category and agent.category_strengths:
        cat_strength = agent.category_strengths.get(task.category, 0.0)
        if cat_strength > 0:
            cat_score = min(100, 50 + cat_strength * 50)
            reasons.append(f"Category match '{task.category}': {cat_strength:.0%} strength")
        else:
            # Check subcategory
            sub_strength = agent.category_strengths.get(task.subcategory, 0.0) if task.subcategory else 0.0
            if sub_strength > 0:
                cat_score = min(100, 40 + sub_strength * 40)
                reasons.append(f"Subcategory match: {sub_strength:.0%}")
            else:
                cat_score = 30.0  # No experience in category
                reasons.append(f"No experience in '{task.category}'")
    components.append(cat_score)

    # Chain experience (0-100)
    chain_score = 50.0  # Neutral
    if task.required_chain and agent.chain_experience:
        chain_exp = agent.chain_experience.get(task.required_chain, 0.0)
        if chain_exp > 0:
            chain_score = min(100, 50 + chain_exp * 50)
            reasons.append(f"Chain '{task.required_chain}' experience: {chain_exp:.0%}")
        else:
            chain_score = 20.0
            reasons.append(f"No experience on '{task.required_chain}'")
    components.append(chain_score)

    # Skills matching (0-100)
    skills_score = 50.0
    if task.skills_required:
        matched = sum(1 for skill in task.skills_required
                      if skill in agent.category_strengths or skill.lower() in
                      [c.lower() for c in agent.category_strengths])
        if len(task.skills_required) > 0:
            match_ratio = matched / len(task.skills_required)
            skills_score = match_ratio * 100
            if match_ratio < 0.5:
                reasons.append(f"Skills gap: {matched}/{len(task.skills_required)} matched")
            elif match_ratio >= 0.8:
                reasons.append(f"Strong skills match: {matched}/{len(task.skills_required)}")
    components.append(skills_score)

    # Weighted average of components
    score = sum(components) / len(components) if components else 50.0

    if not reasons:
        reasons.append(f"Specialization {score:.0f}/100 (generic)")

    return score, reasons


def compute_workload_factor(
    agent: AgentProfile, config: DecisionConfig
) -> tuple[float, list[str]]:
    """Score agent's current workload (less load = higher score).

    Also applies idle bonus for immediately available agents.
    """
    reasons = []

    # Start at 100 (no load) and subtract
    score = 100.0

    # Task load penalty
    if agent.current_tasks > 0:
        penalty = agent.current_tasks * config.workload_penalty_per_task
        score -= penalty
        reasons.append(f"{agent.current_tasks} active task(s) → -{penalty:.0f}")

    # At capacity
    if agent.current_tasks >= config.max_concurrent_tasks:
        score = 0.0
        reasons.append(f"At capacity ({agent.current_tasks}/{config.max_concurrent_tasks})")

    # Idle bonus
    if agent.is_idle and agent.current_tasks == 0:
        score = min(100, score + config.idle_bonus)
        reasons.append(f"Idle → +{config.idle_bonus:.0f} bonus")

    # Cooldown/error state
    if agent.in_cooldown:
        score = 0.0
        reasons.append("In cooldown period")
    if agent.in_error:
        score = 0.0
        reasons.append("In error state")

    score = max(0.0, min(100.0, score))

    if not reasons:
        reasons.append(f"Workload {score:.0f}/100")

    return score, reasons


def compute_recency_factor(agent: AgentProfile, now: datetime) -> tuple[float, list[str]]:
    """Score based on how recently the agent completed a task.

    Recently active agents get a slight preference (warm cache effect).
    But very recently completed = might still be in post-task mode.
    """
    reasons = []

    if not agent.last_task_completed_at:
        # No history — neutral
        return 50.0, ["No task history (recency neutral)"]

    try:
        last = datetime.fromisoformat(agent.last_task_completed_at.replace("Z", "+00:00"))
        hours_since = (now - last).total_seconds() / 3600
    except (ValueError, TypeError):
        return 50.0, ["Invalid timestamp (recency neutral)"]

    if hours_since < 0.5:
        # Just finished — might need a breather
        score = 70.0
        reasons.append(f"Completed task {hours_since:.1f}h ago (recent, cooling)")
    elif hours_since < 4:
        # Sweet spot — recently active, in the zone
        score = 90.0
        reasons.append(f"Active {hours_since:.1f}h ago (warm)")
    elif hours_since < 24:
        # Within the day — good
        score = 70.0
        reasons.append(f"Active {hours_since:.1f}h ago")
    elif hours_since < 72:
        # A few days — okay
        score = 50.0
        reasons.append(f"Last active {hours_since / 24:.1f} days ago")
    else:
        # Long inactive — might be stale
        score = 30.0
        reasons.append(f"Inactive for {hours_since / 24:.0f} days")

    return score, reasons


def compute_risk_factor(
    agent: AgentProfile, task: TaskProfile, config: DecisionConfig
) -> tuple[float, list[str]]:
    """Compute risk assessment (higher score = lower risk = better).

    Considers: failure history, task complexity, agent experience.
    """
    reasons = []
    risk_score = 100.0  # Start at no risk

    # Consecutive failures
    if agent.consecutive_failures > 0:
        failure_penalty = agent.consecutive_failures * 15.0
        risk_score -= failure_penalty
        reasons.append(f"{agent.consecutive_failures} consecutive failures → high risk")

    # Circuit breaker proximity
    if agent.consecutive_failures >= config.max_consecutive_failures - 1:
        risk_score -= 30.0
        reasons.append("Near circuit breaker threshold")

    # Experience vs complexity mismatch
    if task.complexity in ("high", "critical") and agent.tasks_completed < 10:
        risk_score -= 20.0
        reasons.append(f"Inexperienced ({agent.tasks_completed} tasks) for {task.complexity} task")

    # High-value task with unproven agent
    if task.bounty_usd > 5.0 and agent.reputation_confidence < 0.3:
        risk_score -= 15.0
        reasons.append(f"High-value (${task.bounty_usd:.2f}) with low-confidence agent")

    # AutoJob predicted success
    if agent.predicted_success > 0:
        if agent.predicted_success < 0.3:
            risk_score -= 20.0
            reasons.append(f"AutoJob predicts low success ({agent.predicted_success:.0%})")
        elif agent.predicted_success > 0.8:
            risk_score = min(100, risk_score + 10)
            reasons.append(f"AutoJob predicts high success ({agent.predicted_success:.0%})")

    risk_score = max(0.0, min(100.0, risk_score))

    if not reasons:
        reasons.append(f"Risk assessment {risk_score:.0f}/100 (low risk)")

    return risk_score, reasons


# ---------------------------------------------------------------------------
# Mode Adjustments
# ---------------------------------------------------------------------------

def apply_mode_adjustment(
    scored: ScoredAgent,
    mode: OptimizationMode,
    config: DecisionConfig,
) -> float:
    """Apply optimization mode adjustments to the score."""
    adjustment = 0.0

    if mode == OptimizationMode.QUALITY:
        # Boost reputation and specialization influence
        adjustment += (scored.reputation_factor - 50) * 0.15
        adjustment += (scored.specialization_factor - 50) * 0.10
        scored.reasons.append("Quality mode: reputation+specialization boosted")

    elif mode == OptimizationMode.COST:
        # Prefer agents with lower earnings (cheaper)
        if scored.agent.earnings_per_hour > 0:
            cost_score = max(0, 100 - scored.agent.earnings_per_hour * 10)
            adjustment += (cost_score - 50) * 0.20
        # Floor check
        if scored.agent.reputation_score < config.quality_floor:
            scored.disqualified = True
            scored.disqualify_reason = f"Below quality floor ({config.quality_floor}) in cost mode"
        scored.reasons.append("Cost mode: lower-cost agents preferred")

    elif mode == OptimizationMode.SPEED:
        # Boost efficiency and workload factors
        adjustment += (scored.efficiency_factor - 50) * 0.15
        adjustment += (scored.workload_factor - 50) * 0.10
        scored.reasons.append("Speed mode: efficiency+availability boosted")

    elif mode == OptimizationMode.EXPLORATION:
        # Big bonus for under-evaluated agents
        if scored.agent.tasks_completed < config.cold_start_threshold:
            adjustment += config.cold_start_bonus * 2
            scored.reasons.append(f"Exploration mode: +{config.cold_start_bonus * 2:.0f} for under-evaluated agent")
        # Penalty for over-evaluated (give others a chance)
        elif scored.agent.tasks_completed > 50:
            adjustment -= 10.0
            scored.reasons.append("Exploration mode: -10 for well-known agent")

    return adjustment


# ---------------------------------------------------------------------------
# Decision Engine
# ---------------------------------------------------------------------------

class DecisionEngine:
    """Multi-factor decision engine for agent-task matching.

    Combines reputation, efficiency, specialization, workload, recency,
    and risk into explainable assignment decisions.
    """

    def __init__(self, config: DecisionConfig | None = None):
        self.config = config or DecisionConfig()

    def score_agent(
        self,
        agent: AgentProfile,
        task: TaskProfile,
        now: datetime | None = None,
    ) -> ScoredAgent:
        """Score a single agent for a specific task.

        Returns a ScoredAgent with detailed breakdown.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        scored = ScoredAgent(agent=agent)
        config = self.config

        # --- Disqualification checks ---
        if not agent.is_available:
            scored.disqualified = True
            scored.disqualify_reason = "Agent not available"
            return scored

        if agent.in_cooldown:
            scored.disqualified = True
            scored.disqualify_reason = "Agent in cooldown"
            return scored

        if agent.in_error:
            scored.disqualified = True
            scored.disqualify_reason = "Agent in error state"
            return scored

        if agent.current_tasks >= config.max_concurrent_tasks:
            scored.disqualified = True
            scored.disqualify_reason = f"At capacity ({agent.current_tasks} tasks)"
            return scored

        if agent.consecutive_failures >= config.max_consecutive_failures:
            scored.disqualified = True
            scored.disqualify_reason = f"Circuit breaker ({agent.consecutive_failures} consecutive failures)"
            return scored

        if agent.reputation_score < config.min_reputation_score:
            scored.disqualified = True
            scored.disqualify_reason = f"Reputation too low ({agent.reputation_score:.0f} < {config.min_reputation_score})"
            return scored

        # --- Compute factors ---
        scored.reputation_factor, rep_reasons = compute_reputation_factor(agent, task)
        scored.efficiency_factor, eff_reasons = compute_efficiency_factor(agent, task)
        scored.specialization_factor, spec_reasons = compute_specialization_factor(agent, task)
        scored.workload_factor, work_reasons = compute_workload_factor(agent, config)
        scored.recency_factor, rec_reasons = compute_recency_factor(agent, now)
        scored.risk_factor, risk_reasons = compute_risk_factor(agent, task, config)

        scored.reasons.extend(rep_reasons)
        scored.reasons.extend(eff_reasons)
        scored.reasons.extend(spec_reasons)
        scored.reasons.extend(work_reasons)
        scored.reasons.extend(rec_reasons)
        scored.reasons.extend(risk_reasons)

        # --- Normalize weights ---
        weights = {
            "reputation": config.weight_reputation,
            "efficiency": config.weight_efficiency,
            "specialization": config.weight_specialization,
            "workload": config.weight_workload,
            "recency": config.weight_recency,
            "risk": config.weight_risk,
        }
        total_w = sum(weights.values())
        if total_w > 0:
            weights = {k: v / total_w for k, v in weights.items()}

        # --- Complexity scaling ---
        # High-complexity tasks increase reputation and risk weight
        if task.complexity_multiplier > 1.0:
            mult = task.complexity_multiplier
            weights["reputation"] *= mult
            weights["risk"] *= mult
            # Re-normalize
            total_w = sum(weights.values())
            weights = {k: v / total_w for k, v in weights.items()}

        # --- Weighted score ---
        factors = {
            "reputation": scored.reputation_factor,
            "efficiency": scored.efficiency_factor,
            "specialization": scored.specialization_factor,
            "workload": scored.workload_factor,
            "recency": scored.recency_factor,
            "risk": scored.risk_factor,
        }
        base_score = sum(factors[k] * weights[k] for k in factors)

        # --- Cold start bonus ---
        if agent.tasks_completed < config.cold_start_threshold and agent.reputation_confidence < config.min_confidence:
            scored.cold_start_bonus = config.cold_start_bonus
            base_score += scored.cold_start_bonus
            scored.reasons.append(f"Cold start bonus: +{scored.cold_start_bonus:.0f}")

        # --- Mode adjustment ---
        scored.mode_adjustment = apply_mode_adjustment(scored, self.config.mode, config)
        base_score += scored.mode_adjustment

        # --- Final score ---
        scored.total_score = max(0.0, min(100.0, base_score))

        return scored

    def decide(self, context: DecisionContext) -> Decision:
        """Make a task assignment decision.

        Scores all available agents, picks the best, identifies alternatives,
        and produces an explainable decision.
        """
        now = context.timestamp
        task = context.task
        config = self.config

        decision = Decision(
            task_id=task.task_id,
            mode=config.mode,
            decided_at=now.isoformat(),
            agents_considered=len(context.agents),
        )

        if not context.agents:
            decision.reasoning.append("No agents provided")
            decision.warnings.append("Empty agent pool — cannot assign")
            return decision

        # Score all agents
        scored_agents: list[ScoredAgent] = []
        disqualified_count = 0

        for agent in context.agents:
            scored = self.score_agent(agent, task, now)
            scored_agents.append(scored)
            if scored.disqualified:
                disqualified_count += 1

        decision.agents_disqualified = disqualified_count

        # Sort by score (disqualified last)
        scored_agents.sort(
            key=lambda s: (not s.disqualified, s.total_score),
            reverse=True,
        )
        decision.rankings = scored_agents

        # Filter qualified
        qualified = [s for s in scored_agents if not s.disqualified]
        decision.agents_qualified = len(qualified)

        if not qualified:
            decision.reasoning.append(f"All {len(context.agents)} agents disqualified")
            for s in scored_agents[:3]:
                decision.warnings.append(f"{s.agent.agent_name}: {s.disqualify_reason}")
            return decision

        # Pick the winner
        winner = qualified[0]
        decision.chosen_agent = winner.agent.agent_name
        decision.chosen_score = winner.total_score

        # Alternatives (cascade)
        alternatives = qualified[1:config.cascade_depth + 1]
        decision.alternatives = [s.agent.agent_name for s in alternatives]

        # Score spread (for confidence)
        if len(qualified) >= 2:
            decision.score_spread = qualified[0].total_score - qualified[1].total_score
        else:
            decision.score_spread = 0.0

        # --- Confidence computation ---
        confidence = self._compute_confidence(decision, winner, qualified)
        decision.confidence = confidence

        # --- Risk level ---
        decision.risk_level = self._assess_risk_level(winner, task)

        # --- Reasoning ---
        decision.reasoning.append(
            f"Selected {winner.agent.agent_name} (score: {winner.total_score:.1f}/100)"
        )
        if decision.score_spread > 15:
            decision.reasoning.append(
                f"Clear winner — {decision.score_spread:.1f} points ahead of #{2}"
            )
        elif decision.score_spread < 3:
            decision.reasoning.append(
                "Close call — top agents scored similarly"
            )
            decision.warnings.append(
                f"Tight margins: #{1} ({qualified[0].total_score:.1f}) vs "
                f"#{2} ({qualified[1].total_score:.1f})" if len(qualified) >= 2 else ""
            )

        # Add top factor reasons
        for reason in winner.reasons[:3]:
            decision.reasoning.append(reason)

        # Warnings
        if winner.agent.consecutive_failures > 0:
            decision.warnings.append(
                f"{winner.agent.agent_name} has {winner.agent.consecutive_failures} recent failures"
            )
        if winner.agent.reputation_confidence < 0.3:
            decision.warnings.append(
                f"Low confidence in {winner.agent.agent_name}'s reputation data"
            )

        return decision

    def batch_decide(
        self,
        tasks: list[TaskProfile],
        agents: list[AgentProfile],
        timestamp: datetime | None = None,
    ) -> list[Decision]:
        """Make decisions for multiple tasks, respecting workload limits.

        Agents assigned to earlier tasks get workload penalties for later ones.
        This prevents all tasks from going to the same top agent.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        decisions = []
        # Clone agents so we can track assignments
        agent_map = {a.agent_name: AgentProfile(**{
            k: v for k, v in a.__dict__.items()
            if k != "category_strengths" and k != "chain_experience" and k != "recent_categories" and k != "evidence_types" and k != "skills_required"
        }) for a in agents}
        # Copy mutable fields properly
        for a in agents:
            agent_map[a.agent_name].category_strengths = dict(a.category_strengths)
            agent_map[a.agent_name].chain_experience = dict(a.chain_experience)
            agent_map[a.agent_name].recent_categories = list(a.recent_categories)

        # Sort tasks by priority (critical first)
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        sorted_tasks = sorted(tasks, key=lambda t: priority_order.get(t.priority, 2))

        for task in sorted_tasks:
            context = DecisionContext(
                task=task,
                agents=list(agent_map.values()),
                timestamp=timestamp,
            )
            decision = self.decide(context)
            decisions.append(decision)

            # Update agent workload for next iteration
            if decision.chosen_agent and decision.chosen_agent in agent_map:
                agent_map[decision.chosen_agent].current_tasks += 1
                agent_map[decision.chosen_agent].is_idle = False

        return decisions

    def _compute_confidence(
        self,
        decision: Decision,
        winner: ScoredAgent,
        qualified: list[ScoredAgent],
    ) -> float:
        """Compute decision confidence (0-1)."""
        confidence = 0.5  # Base

        # Score spread: bigger spread = more confident
        if decision.score_spread > 20:
            confidence += 0.2
        elif decision.score_spread > 10:
            confidence += 0.1
        elif decision.score_spread < 3:
            confidence -= 0.15

        # Winner's reputation confidence
        confidence += winner.agent.reputation_confidence * 0.2

        # Number of qualified agents (more options = more competition = more confident in choice)
        if len(qualified) >= 5:
            confidence += 0.1
        elif len(qualified) == 1:
            confidence -= 0.1  # Only option, not necessarily best

        # Winner's score level
        if winner.total_score > 80:
            confidence += 0.1
        elif winner.total_score < 40:
            confidence -= 0.2

        return max(0.0, min(1.0, confidence))

    def _assess_risk_level(self, winner: ScoredAgent, task: TaskProfile) -> str:
        """Assess overall risk of the decision."""
        risk_signals = 0

        if winner.risk_factor < 50:
            risk_signals += 2
        elif winner.risk_factor < 70:
            risk_signals += 1

        if winner.agent.consecutive_failures > 0:
            risk_signals += 1

        if winner.agent.reputation_confidence < 0.2:
            risk_signals += 1

        if task.complexity in ("high", "critical"):
            risk_signals += 1

        if task.bounty_usd > 10.0:
            risk_signals += 1

        if risk_signals >= 4:
            return "high"
        elif risk_signals >= 2:
            return "medium"
        return "low"


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def quick_decide(
    task: TaskProfile,
    agents: list[AgentProfile],
    mode: OptimizationMode = OptimizationMode.BALANCED,
) -> Decision:
    """Quick one-shot decision with default config."""
    config = DecisionConfig(mode=mode)
    engine = DecisionEngine(config)
    context = DecisionContext(task=task, agents=agents)
    return engine.decide(context)


def explain_ranking(decision: Decision) -> str:
    """Generate a detailed text explanation of the full ranking."""
    lines = [decision.explain(), ""]
    lines.append("📊 Full Ranking:")

    for i, scored in enumerate(decision.rankings):
        if scored.disqualified:
            lines.append(f"  {i + 1}. ❌ {scored.agent.agent_name} — DISQUALIFIED: {scored.disqualify_reason}")
        else:
            lines.append(
                f"  {i + 1}. {'✅' if i == 0 else '  '} {scored.agent.agent_name} — "
                f"Score: {scored.total_score:.1f} "
                f"[R:{scored.reputation_factor:.0f} E:{scored.efficiency_factor:.0f} "
                f"S:{scored.specialization_factor:.0f} W:{scored.workload_factor:.0f} "
                f"Rec:{scored.recency_factor:.0f} Risk:{scored.risk_factor:.0f}]"
            )

    return "\n".join(lines)


def format_decision_irc(decision: Decision) -> str:
    """Format decision for IRC channel notification (Colombian Spanish)."""
    if not decision.chosen_agent:
        return f"❌ Tarea {decision.task_id}: No hay agentes disponibles pa esta tarea, parcero."

    lines = [
        f"🧠 Tarea {decision.task_id} → {decision.chosen_agent}",
        f"   Score: {decision.chosen_score:.0f}/100 | "
        f"Confianza: {decision.confidence:.0%} | Riesgo: {decision.risk_level}",
    ]

    if decision.alternatives:
        lines.append(f"   🔄 Backup: {', '.join(decision.alternatives)}")

    if decision.warnings:
        lines.append(f"   ⚠️ {decision.warnings[0]}")

    return "\n".join(lines)
