"""
Swarm Orchestrator — Coordinate Multi-Agent Task Distribution & Economics

The orchestrator sits above the lifecycle manager and reputation bridge,
making high-level decisions about:
- Which agent handles which task (skill-based matching)
- Economic coordination (prevent duplicate spending, balance budgets)
- Agent-to-agent negotiation routing
- Swarm-level metrics and optimization

Architecture:
    ┌────────────────────────────────────┐
    │        Swarm Orchestrator          │
    │  (task routing, economics, metrics)│
    └───────────┬──────────┬────────────┘
                │          │
    ┌───────────▼──┐  ┌───▼────────────┐
    │  Lifecycle   │  │  Reputation    │
    │  Manager     │  │  Bridge        │
    └──────────────┘  └────────────────┘
                │          │
    ┌───────────▼──────────▼────────────┐
    │         Agent Fleet               │
    │  [aurora] [blaze] [cipher] ...    │
    └───────────────────────────────────┘
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, List, Tuple


logger = logging.getLogger(__name__)


# Import siblings
from .lifecycle_manager import LifecycleManager, AgentStatus
from .reputation_bridge import ReputationBridge, BridgedReputation


# ── Task Category → Agent Skill Mapping ──

TASK_CATEGORY_SKILLS = {
    "photo_verification": {
        "required": ["field_work", "photography"],
        "preferred": ["documentation", "attention_to_detail"],
        "agent_capable": False,  # Requires physical presence
    },
    "data_collection": {
        "required": ["research", "documentation"],
        "preferred": ["data_entry"],
        "agent_capable": True,
    },
    "content_creation": {
        "required": ["writing", "creativity"],
        "preferred": ["documentation"],
        "agent_capable": True,
    },
    "code_review": {
        "required": ["code_review"],
        "preferred": ["security", "testing"],
        "agent_capable": True,
    },
    "translation": {
        "required": ["languages", "documentation"],
        "preferred": ["communication"],
        "agent_capable": True,
    },
    "research": {
        "required": ["research", "analysis"],
        "preferred": ["documentation", "data_science"],
        "agent_capable": True,
    },
    "testing": {
        "required": ["qa_testing"],
        "preferred": ["documentation", "automation"],
        "agent_capable": True,
    },
    "design": {
        "required": ["design", "creativity"],
        "preferred": ["visual_communication"],
        "agent_capable": False,  # Agents can't do visual design well
    },
}


@dataclass
class AgentProfile:
    """Agent capabilities and match readiness."""

    agent_id: str
    wallet: str
    personality: str
    skills: List[str] = field(default_factory=list)
    specializations: List[str] = field(default_factory=list)
    reputation: Optional[BridgedReputation] = None

    # Match scoring
    availability_score: float = 1.0  # 0-1: how available (active + within budget)
    reputation_score: float = 50.0  # From reputation bridge
    skill_match_score: float = 0.0  # How well skills match a task
    recency_bonus: float = 0.0  # Bonus for recent good completions

    @property
    def composite_match_score(self) -> float:
        """Weighted composite score for task assignment ranking."""
        return (
            self.skill_match_score * 0.35
            + self.reputation_score / 100 * 0.30
            + self.availability_score * 0.20
            + self.recency_bonus * 0.15
        )


@dataclass
class TaskAssignment:
    """Result of orchestrator's task→agent matching."""

    task_id: str
    assigned_agent: Optional[str] = None
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    alternatives: List[dict] = field(default_factory=list)
    assignment_time: Optional[datetime] = None

    # If no suitable agent found
    unassigned_reason: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("assignment_time"):
            d["assignment_time"] = d["assignment_time"].isoformat()
        return d


class AssignmentStrategy(str, Enum):
    """How tasks get assigned to agents."""

    BEST_MATCH = "best_match"  # Highest skill match score
    ROUND_ROBIN = "round_robin"  # Distribute evenly
    REPUTATION = "reputation"  # Highest reputation first
    CHEAPEST = "cheapest"  # Lowest model cost agent
    RANDOM = "random"  # Random from eligible


class SwarmOrchestrator:
    """
    Coordinates the KarmaKadabra agent swarm.

    Responsibilities:
    - Register and profile agents
    - Match tasks to agents based on skills, reputation, and availability
    - Prevent duplicate work (claim-before-work protocol)
    - Track swarm economics (total spend, revenue, balance)
    - Provide metrics and observability
    """

    def __init__(
        self,
        lifecycle: Optional[LifecycleManager] = None,
        bridge: Optional[ReputationBridge] = None,
        strategy: AssignmentStrategy = AssignmentStrategy.BEST_MATCH,
        max_concurrent_tasks_per_agent: int = 3,
    ):
        """
        Initialize orchestrator.

        Args:
            lifecycle: Lifecycle manager instance
            bridge: Reputation bridge instance
            strategy: Default task assignment strategy
            max_concurrent_tasks_per_agent: Max tasks an agent can work on simultaneously
        """
        self.lifecycle = lifecycle or LifecycleManager()
        self.bridge = bridge or ReputationBridge(dry_run=True)
        self.strategy = strategy
        self.max_concurrent_tasks = max_concurrent_tasks_per_agent

        # Agent profiles (enriched beyond lifecycle state)
        self.profiles: Dict[str, AgentProfile] = {}

        # Task tracking
        self.active_tasks: Dict[str, str] = {}  # task_id → agent_id
        self.task_history: List[dict] = []  # completed assignments

        # Economics
        self.total_tasks_assigned: int = 0
        self.total_tasks_completed: int = 0
        self.total_usd_spent: float = 0.0
        self.total_usd_earned: float = 0.0

        # Claim tracking (prevent duplicate work)
        self._claims: Dict[str, str] = {}  # task_id → agent_id that claimed it
        self._claim_timestamps: Dict[str, float] = {}  # task_id → claim time
        self.CLAIM_TIMEOUT = 600  # 10 minutes to start work after claiming

    # ── Agent Management ──

    def register_agent(
        self,
        agent_id: str,
        wallet: str,
        personality: str = "",
        skills: Optional[List[str]] = None,
        specializations: Optional[List[str]] = None,
        **lifecycle_kwargs,
    ) -> AgentProfile:
        """
        Register agent in both lifecycle manager and orchestrator.

        Args:
            agent_id: Unique agent ID
            wallet: Ethereum wallet
            personality: Personality archetype
            skills: List of skill names
            specializations: Task categories this agent specializes in
            **lifecycle_kwargs: Passed to lifecycle.register_agent

        Returns:
            AgentProfile
        """
        # Register in lifecycle manager
        self.lifecycle.register_agent(
            agent_id=agent_id,
            wallet=wallet,
            personality=personality,
            **lifecycle_kwargs,
        )

        # Create enriched profile
        profile = AgentProfile(
            agent_id=agent_id,
            wallet=wallet.lower(),
            personality=personality,
            skills=skills or [],
            specializations=specializations or [],
        )

        self.profiles[agent_id] = profile
        logger.info(
            f"Orchestrator registered {agent_id}: "
            f"skills={skills}, specializations={specializations}"
        )
        return profile

    async def refresh_profile(self, agent_id: str) -> Optional[AgentProfile]:
        """
        Refresh an agent's profile with latest reputation data.

        Args:
            agent_id: Agent to refresh

        Returns:
            Updated AgentProfile
        """
        profile = self.profiles.get(agent_id)
        if not profile:
            return None

        # Fetch bridged reputation
        rep = await self.bridge.get_bridged_reputation(profile.wallet)
        profile.reputation = rep
        profile.reputation_score = rep.composite_score

        # Update availability score
        state = self.lifecycle.get_agent(agent_id)
        if state:
            if state.status == AgentStatus.ACTIVE and state.is_healthy():
                budget_util = state.budget_utilization()
                # Availability decreases as budget is consumed
                avg_util = sum(budget_util.values()) / max(1, len(budget_util))
                profile.availability_score = max(0.0, 1.0 - avg_util)
            else:
                profile.availability_score = 0.0

        return profile

    # ── Task Assignment ──

    async def assign_task(
        self,
        task_id: str,
        category: str = "general",
        required_skills: Optional[List[str]] = None,
        bounty_usd: float = 0.0,
        agent_only: bool = True,
        strategy: Optional[AssignmentStrategy] = None,
    ) -> TaskAssignment:
        """
        Assign a task to the best available agent.

        The orchestrator:
        1. Filters eligible agents (active, within budget, not at max tasks)
        2. Scores each agent against the task
        3. Assigns to the highest scorer
        4. Records the claim (prevents duplicate work)

        Args:
            task_id: EM task ID
            category: Task category (maps to skill requirements)
            required_skills: Override skill requirements
            bounty_usd: Task bounty (for budget checking)
            agent_only: Only assign to AI agents (not humans)
            strategy: Override assignment strategy

        Returns:
            TaskAssignment with assigned agent and reasoning
        """
        strategy = strategy or self.strategy
        assignment = TaskAssignment(task_id=task_id)

        # Check if task already assigned
        if task_id in self._claims:
            existing = self._claims[task_id]
            claim_time = self._claim_timestamps.get(task_id, 0)
            if time.time() - claim_time < self.CLAIM_TIMEOUT:
                assignment.unassigned_reason = f"Already claimed by {existing}"
                return assignment
            else:
                # Claim expired, remove it
                del self._claims[task_id]
                del self._claim_timestamps[task_id]

        # Get task skill requirements
        task_skills = self._get_task_skills(category, required_skills)

        # Filter eligible agents
        eligible = await self._get_eligible_agents(bounty_usd, agent_only)

        if not eligible:
            assignment.unassigned_reason = "No eligible agents available"
            return assignment

        # Score agents against task
        scored_agents = []
        for profile in eligible:
            score, reasons = self._score_agent_for_task(profile, task_skills, category)
            scored_agents.append((profile, score, reasons))

        # Sort by composite score (descending)
        scored_agents.sort(key=lambda x: -x[1])

        # Apply strategy
        if strategy == AssignmentStrategy.BEST_MATCH:
            winner = scored_agents[0]
        elif strategy == AssignmentStrategy.ROUND_ROBIN:
            winner = self._round_robin_pick(scored_agents)
        elif strategy == AssignmentStrategy.REPUTATION:
            scored_agents.sort(key=lambda x: -x[0].reputation_score)
            winner = scored_agents[0]
        elif strategy == AssignmentStrategy.CHEAPEST:
            scored_agents.sort(
                key=lambda x: self._model_cost(
                    self.lifecycle.get_agent(x[0].agent_id).model
                    if self.lifecycle.get_agent(x[0].agent_id)
                    else "anthropic/claude-haiku-4-5"
                )
            )
            winner = scored_agents[0]
        else:
            import random

            winner = random.choice(scored_agents)

        winning_profile, winning_score, winning_reasons = winner

        # Record assignment
        assignment.assigned_agent = winning_profile.agent_id
        assignment.score = round(winning_score * 100, 1)
        assignment.reasons = winning_reasons
        assignment.assignment_time = datetime.now(timezone.utc)

        # Record alternatives (top 3 excluding winner)
        for profile, score, reasons in scored_agents[1:4]:
            assignment.alternatives.append(
                {
                    "agent_id": profile.agent_id,
                    "score": round(score * 100, 1),
                    "reasons": reasons[:2],
                }
            )

        # Claim the task
        self._claims[task_id] = winning_profile.agent_id
        self._claim_timestamps[task_id] = time.time()
        self.active_tasks[task_id] = winning_profile.agent_id
        self.total_tasks_assigned += 1

        logger.info(
            f"Task {task_id} assigned to {winning_profile.agent_id} "
            f"(score: {assignment.score}%, strategy: {strategy.value})"
        )

        return assignment

    async def complete_task(
        self,
        task_id: str,
        success: bool,
        earnings_usd: float = 0.0,
        rating: Optional[float] = None,
    ) -> dict:
        """
        Record task completion and update agent metrics.

        Args:
            task_id: Completed task ID
            success: Whether task was successful
            earnings_usd: Amount earned (if worker)
            rating: Rating received (0-100)

        Returns:
            Summary of completion impact
        """
        agent_id = self.active_tasks.pop(task_id, None)
        self._claims.pop(task_id, None)
        self._claim_timestamps.pop(task_id, None)

        if not agent_id:
            return {"error": "task not tracked"}

        # Update lifecycle state
        agent = self.lifecycle.get_agent(agent_id)
        if agent:
            if success:
                agent.total_tasks_completed += 1
                agent.consecutive_failures = 0
            else:
                agent.total_tasks_failed += 1

        # Update economics
        self.total_tasks_completed += 1
        self.total_usd_earned += earnings_usd

        # Record in history
        self.task_history.append(
            {
                "task_id": task_id,
                "agent_id": agent_id,
                "success": success,
                "earnings_usd": earnings_usd,
                "rating": rating,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Sync reputation if rating provided
        if rating is not None and agent:
            profile = self.profiles.get(agent_id)
            if profile:
                await self.bridge.sync_em_to_chain(
                    wallet=profile.wallet,
                    em_reputation={
                        "bayesian_score": rating,
                        "total_tasks": agent.total_tasks_completed
                        + agent.total_tasks_failed,
                    },
                    task_id=task_id,
                    reason="task_completed" if success else "task_failed",
                )

        logger.info(
            f"Task {task_id} completed by {agent_id}: "
            f"success={success}, earned=${earnings_usd:.2f}"
        )

        return {
            "agent_id": agent_id,
            "success": success,
            "earnings_usd": earnings_usd,
            "total_completed": self.total_tasks_completed,
        }

    # ── Economics ──

    def economic_summary(self) -> dict:
        """
        Get swarm economic summary.

        Returns:
            {
                "total_assigned": 150,
                "total_completed": 142,
                "completion_rate": 0.947,
                "total_spent_usd": 23.50,
                "total_earned_usd": 18.40,
                "net_usd": -5.10,
                "active_tasks": 8,
                "avg_earnings_per_task": 0.13,
                "top_earners": [...],
                "budget_status": {...}
            }
        """
        completion_rate = self.total_tasks_completed / max(1, self.total_tasks_assigned)
        avg_earnings = self.total_usd_earned / max(1, self.total_tasks_completed)

        # Top earners
        agent_earnings: Dict[str, float] = {}
        for entry in self.task_history:
            aid = entry.get("agent_id", "")
            agent_earnings[aid] = agent_earnings.get(aid, 0) + entry.get(
                "earnings_usd", 0
            )

        top_earners = sorted(
            agent_earnings.items(),
            key=lambda x: -x[1],
        )[:5]

        # Budget status
        lifecycle_health = self.lifecycle.health_check()

        return {
            "total_assigned": self.total_tasks_assigned,
            "total_completed": self.total_tasks_completed,
            "completion_rate": round(completion_rate, 3),
            "total_spent_usd": round(self.total_usd_spent, 2),
            "total_earned_usd": round(self.total_usd_earned, 2),
            "net_usd": round(self.total_usd_earned - self.total_usd_spent, 2),
            "active_tasks": len(self.active_tasks),
            "avg_earnings_per_task": round(avg_earnings, 4),
            "top_earners": [
                {"agent_id": aid, "earned_usd": round(earned, 2)}
                for aid, earned in top_earners
            ],
            "fleet_health": {
                "active": lifecycle_health["active"],
                "total": lifecycle_health["total_agents"],
                "budget_remaining_pct": lifecycle_health["budget_remaining_pct"],
            },
        }

    # ── Metrics & Observability ──

    def metrics(self) -> dict:
        """
        Get comprehensive orchestrator metrics.

        Suitable for monitoring dashboards and alerting.
        """
        now = datetime.now(timezone.utc)

        # Task rate (last hour)
        recent_completions = [
            e
            for e in self.task_history
            if datetime.fromisoformat(e["completed_at"]).replace(tzinfo=timezone.utc)
            > now - timedelta(hours=1)
        ]
        tasks_per_hour = len(recent_completions)

        # Success rate (last 100 tasks)
        recent = self.task_history[-100:]
        recent_success = sum(1 for e in recent if e.get("success", False))
        success_rate = recent_success / max(1, len(recent))

        # Agent utilization
        active_agents = self.lifecycle.active_agent_count()
        total_agents = len(self.lifecycle.agents)
        utilization = active_agents / max(1, total_agents)

        # Task distribution (how evenly spread)
        agent_task_counts: Dict[str, int] = {}
        for entry in self.task_history[-500:]:
            aid = entry.get("agent_id", "")
            agent_task_counts[aid] = agent_task_counts.get(aid, 0) + 1

        distribution_variance = 0.0
        if agent_task_counts:
            values = list(agent_task_counts.values())
            mean = sum(values) / len(values)
            distribution_variance = sum((v - mean) ** 2 for v in values) / len(values)

        return {
            "timestamp": now.isoformat(),
            "tasks": {
                "active": len(self.active_tasks),
                "claimed": len(self._claims),
                "total_assigned": self.total_tasks_assigned,
                "total_completed": self.total_tasks_completed,
                "per_hour": tasks_per_hour,
                "success_rate": round(success_rate, 3),
            },
            "agents": {
                "total": total_agents,
                "active": active_agents,
                "utilization": round(utilization, 3),
                "distribution_variance": round(distribution_variance, 2),
            },
            "economics": {
                "total_spent_usd": round(self.total_usd_spent, 2),
                "total_earned_usd": round(self.total_usd_earned, 2),
                "net_usd": round(self.total_usd_earned - self.total_usd_spent, 2),
            },
        }

    # ── Private: Scoring ──

    def _get_task_skills(
        self,
        category: str,
        override_skills: Optional[List[str]] = None,
    ) -> dict:
        """Get skill requirements for a task."""
        if override_skills:
            return {
                "required": override_skills,
                "preferred": [],
                "agent_capable": True,
            }
        return TASK_CATEGORY_SKILLS.get(
            category,
            {
                "required": [],
                "preferred": [],
                "agent_capable": True,
            },
        )

    async def _get_eligible_agents(
        self,
        bounty_usd: float,
        agent_only: bool,
    ) -> List[AgentProfile]:
        """Get agents eligible for task assignment."""
        eligible = []

        for agent_id, profile in self.profiles.items():
            state = self.lifecycle.get_agent(agent_id)
            if not state:
                continue

            # Must be active
            if state.status != AgentStatus.ACTIVE:
                continue

            # Must be healthy
            if not state.is_healthy():
                continue

            # Must have budget for the bounty
            if (
                state.usage.usd_spent_today + bounty_usd
                > state.budget.max_usd_spend_per_day
            ):
                continue

            # Must not be at max concurrent tasks
            current_tasks = sum(
                1 for tid, aid in self.active_tasks.items() if aid == agent_id
            )
            if current_tasks >= self.max_concurrent_tasks:
                continue

            # Refresh availability score
            budget_util = state.budget_utilization()
            avg_util = sum(budget_util.values()) / max(1, len(budget_util))
            profile.availability_score = max(0.0, 1.0 - avg_util)

            eligible.append(profile)

        return eligible

    def _score_agent_for_task(
        self,
        profile: AgentProfile,
        task_skills: dict,
        category: str,
    ) -> Tuple[float, List[str]]:
        """
        Score an agent's fitness for a specific task.

        Scoring dimensions:
        - Skill match (0.35): How many required/preferred skills the agent has
        - Reputation (0.30): Agent's composite reputation score
        - Availability (0.20): How much budget/capacity remains
        - Recency (0.15): Bonus for recent successful completions in same category

        Returns:
            (score: 0.0-1.0, reasons: List[str])
        """
        reasons = []
        required = task_skills.get("required", [])
        preferred = task_skills.get("preferred", [])

        # Skill match score
        if required:
            required_matches = sum(1 for s in required if s in profile.skills)
            skill_score = required_matches / len(required)
            if required_matches == len(required):
                reasons.append(f"All {len(required)} required skills match")
            elif required_matches > 0:
                reasons.append(
                    f"{required_matches}/{len(required)} required skills match"
                )
        else:
            skill_score = 0.5  # No requirements = neutral
            reasons.append("No specific skill requirements")

        # Preferred skill bonus
        if preferred:
            preferred_matches = sum(1 for s in preferred if s in profile.skills)
            skill_score += (preferred_matches / len(preferred)) * 0.2
            if preferred_matches > 0:
                reasons.append(f"{preferred_matches} preferred skills match")

        # Specialization bonus
        if category in profile.specializations:
            skill_score += 0.15
            reasons.append(f"Specializes in {category}")

        skill_score = min(1.0, skill_score)
        profile.skill_match_score = skill_score

        # Reputation score (normalized 0-1)
        rep_score = profile.reputation_score / 100
        if rep_score > 0.75:
            reasons.append(f"High reputation ({profile.reputation_score:.0f})")

        # Availability score (already updated)
        avail_score = profile.availability_score
        if avail_score < 0.3:
            reasons.append("Low availability (budget nearly spent)")

        # Recency bonus: recent completions in same category
        recency = 0.0
        recent = self.task_history[-50:]
        same_category_completions = [
            e
            for e in recent
            if e.get("agent_id") == profile.agent_id and e.get("success", False)
        ]
        if same_category_completions:
            recency = min(1.0, len(same_category_completions) * 0.2)
            reasons.append(f"{len(same_category_completions)} recent successful tasks")

        # Composite
        composite = (
            skill_score * 0.35 + rep_score * 0.30 + avail_score * 0.20 + recency * 0.15
        )

        return composite, reasons

    def _round_robin_pick(
        self,
        scored_agents: List[Tuple[AgentProfile, float, List[str]]],
    ) -> Tuple[AgentProfile, float, List[str]]:
        """Pick using round-robin from eligible agents."""
        # Find agent with fewest recent assignments
        task_counts: Dict[str, int] = {}
        for entry in self.task_history[-200:]:
            aid = entry.get("agent_id", "")
            task_counts[aid] = task_counts.get(aid, 0) + 1

        scored_agents.sort(key=lambda x: task_counts.get(x[0].agent_id, 0))
        return scored_agents[0]

    def _model_cost(self, model: str) -> float:
        """Estimated cost per 1K tokens for a model."""
        costs = {
            "anthropic/claude-haiku-4-5": 0.001,
            "anthropic/claude-sonnet-4-20250514": 0.003,
            "anthropic/claude-opus-4-6": 0.015,
        }
        return costs.get(model, 0.005)
