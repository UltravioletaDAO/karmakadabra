"""
Swarm Context Injector — Dynamic Agent Context from AutoJob + ERC-8004
======================================================================

The bridge between AutoJob's Skill DNA, ERC-8004 on-chain reputation,
and the actual context that gets injected into each agent before task
execution.

This module answers the question: "What should this specific agent know
about itself before starting this specific task?"

Architecture:
    ┌───────────────┐     ┌──────────────────┐     ┌──────────────┐
    │ AutoJob       │     │ Reputation       │     │ Lifecycle    │
    │ Bridge        │     │ Bridge           │     │ Manager      │
    │ (Skill DNA)   │     │ (ERC-8004)       │     │ (state)      │
    └───────┬───────┘     └────────┬─────────┘     └──────┬───────┘
            │                      │                      │
            └──────────┬───────────┘──────────────────────┘
                       │
            ┌──────────▼──────────┐
            │ Swarm Context       │ ← YOU ARE HERE
            │ Injector            │
            │                     │
            │ Builds per-agent    │
            │ context blocks      │
            └──────────┬──────────┘
                       │
                       ▼
            Context injected into agent prompt
            before task execution

The context injector generates:
    1. Capability Profile — what the agent is good at (from Skill DNA)
    2. Reputation Badge — how the agent is perceived (from ERC-8004)
    3. Task Fitness Score — how well this agent fits THIS task
    4. Swarm Awareness — what other agents are doing (anti-duplication)
    5. Budget Context — resource limits and current usage

Usage:
    injector = SwarmContextInjector(autojob_bridge, reputation_bridge, lifecycle_mgr)

    # Get full context for agent before task assignment
    context = await injector.build_agent_context(
        agent_id="agent_aurora",
        task={"title": "Verify storefront", "category": "physical_verification"},
    )

    # Inject into agent system prompt
    system_prompt = f"{base_prompt}\n\n{context}"
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier display mappings
# ---------------------------------------------------------------------------

TIER_DISPLAY = {
    "elite": "⭐ Elite",
    "diamante": "💎 Diamante",
    "oro": "🥇 Oro",
    "trusted": "🛡️ Trusted",
    "plata": "🥈 Plata",
    "established": "🏅 Established",
    "bronce": "🥉 Bronce",
    "new": "🆕 New",
    "registered": "📝 Registered",
    "at_risk": "⚠️ At Risk",
    "unverified": "❓ Unverified",
}

SCORE_EMOJI = {
    (90, 101): "🟢",
    (70, 90): "🔵",
    (50, 70): "🟡",
    (30, 50): "🟠",
    (0, 30): "🔴",
}


def _score_bar(score: float, width: int = 20) -> str:
    """Generate a text progress bar for a score (0-100)."""
    filled = int(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _score_emoji(score: float) -> str:
    """Get emoji for a score range."""
    for (lo, hi), emoji in SCORE_EMOJI.items():
        if lo <= score < hi:
            return emoji
    return "🔵"


# ---------------------------------------------------------------------------
# Agent Context Block (the output)
# ---------------------------------------------------------------------------

@dataclass
class AgentContextBlock:
    """The complete context block to inject into an agent's prompt."""

    agent_id: str
    wallet: str

    # Sections (each is a formatted string)
    capability_profile: str = ""
    reputation_badge: str = ""
    task_fitness: str = ""
    swarm_awareness: str = ""
    budget_context: str = ""

    # Metadata
    total_tokens_estimate: int = 0
    generated_at: Optional[datetime] = None
    sources_used: List[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Render the full context block for injection into a system prompt.

        Returns a clean, structured markdown block that any LLM can parse.
        """
        sections = []

        if self.capability_profile:
            sections.append(self.capability_profile)
        if self.reputation_badge:
            sections.append(self.reputation_badge)
        if self.task_fitness:
            sections.append(self.task_fitness)
        if self.swarm_awareness:
            sections.append(self.swarm_awareness)
        if self.budget_context:
            sections.append(self.budget_context)

        if not sections:
            return ""

        header = f"## 🤖 Agent Intelligence Context (#{self.agent_id})\n"
        footer = f"\n_Generated: {self.generated_at.strftime('%H:%M UTC') if self.generated_at else 'unknown'} | Sources: {', '.join(self.sources_used)}_"

        return header + "\n---\n".join(sections) + footer

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "agent_id": self.agent_id,
            "wallet": self.wallet,
            "sections": {
                "capability_profile": self.capability_profile,
                "reputation_badge": self.reputation_badge,
                "task_fitness": self.task_fitness,
                "swarm_awareness": self.swarm_awareness,
                "budget_context": self.budget_context,
            },
            "total_tokens_estimate": self.total_tokens_estimate,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "sources_used": self.sources_used,
        }


# ---------------------------------------------------------------------------
# Swarm Context Injector
# ---------------------------------------------------------------------------

class SwarmContextInjector:
    """Builds dynamic context blocks for each agent in the swarm.

    Combines data from:
    - AutoJob Bridge → Skill DNA, worker registry, matching scores
    - Reputation Bridge → ERC-8004 on-chain reputation, composite scores
    - Lifecycle Manager → agent status, budget usage, active hours

    The output is a structured markdown block that gets injected into
    the agent's system prompt before task execution.
    """

    def __init__(
        self,
        autojob_bridge=None,
        reputation_bridge=None,
        lifecycle_manager=None,
        active_tasks: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the context injector.

        All dependencies are optional — the injector degrades gracefully
        when a source is unavailable.

        Args:
            autojob_bridge: AutoJobBridge instance (Skill DNA + matching)
            reputation_bridge: ReputationBridge instance (ERC-8004)
            lifecycle_manager: LifecycleManager instance (agent state)
            active_tasks: Dict of task_id → agent_id for swarm awareness
        """
        self.autojob = autojob_bridge
        self.reputation = reputation_bridge
        self.lifecycle = lifecycle_manager
        self.active_tasks = active_tasks or {}

        # Cache for built contexts (avoid rebuilding within same cycle)
        self._cache: Dict[str, AgentContextBlock] = {}
        self._cache_ttl = 60  # seconds
        self._cache_timestamps: Dict[str, float] = {}

    async def build_agent_context(
        self,
        agent_id: str,
        wallet: str = "",
        task: Optional[dict] = None,
        include_swarm: bool = True,
        include_budget: bool = True,
        max_tokens: int = 800,
    ) -> AgentContextBlock:
        """Build a complete context block for an agent.

        Args:
            agent_id: Agent identifier
            wallet: Agent's Ethereum wallet address
            task: Optional task dict (for task-specific fitness scoring)
            include_swarm: Include swarm awareness section
            include_budget: Include budget context section
            max_tokens: Approximate max tokens for the context block

        Returns:
            AgentContextBlock ready for injection
        """
        now = datetime.now(timezone.utc)
        block = AgentContextBlock(
            agent_id=agent_id,
            wallet=wallet,
            generated_at=now,
        )

        # 1. Capability Profile (from AutoJob Skill DNA)
        block.capability_profile = await self._build_capability_profile(
            agent_id, wallet
        )
        if block.capability_profile:
            block.sources_used.append("autojob")

        # 2. Reputation Badge (from ERC-8004)
        block.reputation_badge = await self._build_reputation_badge(wallet)
        if block.reputation_badge:
            block.sources_used.append("erc8004")

        # 3. Task Fitness (if task provided)
        if task:
            block.task_fitness = await self._build_task_fitness(
                agent_id, wallet, task
            )
            if block.task_fitness:
                block.sources_used.append("task_match")

        # 4. Swarm Awareness (what other agents are doing)
        if include_swarm:
            block.swarm_awareness = self._build_swarm_awareness(agent_id)
            if block.swarm_awareness:
                block.sources_used.append("swarm")

        # 5. Budget Context (resource limits)
        if include_budget:
            block.budget_context = self._build_budget_context(agent_id)
            if block.budget_context:
                block.sources_used.append("lifecycle")

        # Estimate token count (~4 chars per token for English text)
        total_chars = sum(
            len(s)
            for s in [
                block.capability_profile,
                block.reputation_badge,
                block.task_fitness,
                block.swarm_awareness,
                block.budget_context,
            ]
        )
        block.total_tokens_estimate = total_chars // 4

        return block

    # -------------------------------------------------------------------
    # Section builders
    # -------------------------------------------------------------------

    async def _build_capability_profile(
        self, agent_id: str, wallet: str
    ) -> str:
        """Build the capability profile section from AutoJob Skill DNA.

        Shows the agent what it's good at, based on evidence from
        completed tasks — not static config.
        """
        if not self.autojob:
            return ""

        try:
            # Try to get leaderboard data for this specific wallet
            leaderboard = await self.autojob.get_leaderboard(limit=50)
            agent_entry = None
            for entry in leaderboard:
                if entry.get("wallet", "").lower() == wallet.lower():
                    agent_entry = entry
                    break

            if not agent_entry:
                return ""

            lines = ["### 🧬 Your Capability Profile\n"]

            # Overall position
            rank = leaderboard.index(agent_entry) + 1 if agent_entry in leaderboard else "?"
            lines.append(
                f"**Swarm Rank:** #{rank} of {len(leaderboard)} "
                f"({_score_emoji(agent_entry.get('overall_score', 0))} "
                f"{agent_entry.get('overall_score', 0):.1f}/100)"
            )

            # Tier
            tier = agent_entry.get("tier", "unverified")
            tier_display = TIER_DISPLAY.get(tier, tier)
            lines.append(f"**Tier:** {tier_display}")

            # Reliability
            reliability = agent_entry.get("reliability", 0)
            lines.append(f"**Reliability:** {_score_bar(reliability)} {reliability:.0f}%")

            # Recency
            recency = agent_entry.get("recency", 0)
            lines.append(f"**Activity:** {_score_bar(recency)} {recency:.0f}%")

            # Evidence weight
            ew = agent_entry.get("evidence_weight", 0)
            lines.append(f"**Evidence Strength:** {ew:.0%}")

            # Task count
            total_tasks = agent_entry.get("total_tasks", 0)
            lines.append(f"**Verified Tasks:** {total_tasks}")

            lines.append("")
            lines.append(
                "_This profile is derived from your verified task completion history._"
            )

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Failed to build capability profile for {agent_id}: {e}")
            return ""

    async def _build_reputation_badge(self, wallet: str) -> str:
        """Build the on-chain reputation badge section.

        Shows the agent its ERC-8004 identity and reputation,
        which is portable and immutable.
        """
        if not self.reputation or not wallet:
            return ""

        try:
            bridged = await self.reputation.get_bridged_reputation(wallet)

            if not bridged or bridged.confidence == 0:
                return ""

            lines = ["### ⛓️ On-Chain Identity\n"]

            # Agent ID
            if bridged.agent_id:
                lines.append(f"**ERC-8004 Agent ID:** #{bridged.agent_id}")

            # Composite score
            score = bridged.composite_score
            lines.append(
                f"**Reputation:** {_score_emoji(score)} {score:.1f}/100 "
                f"({_score_bar(score, 15)})"
            )

            # Tier
            tier = bridged.tier
            tier_display = TIER_DISPLAY.get(tier, tier)
            lines.append(f"**Tier:** {tier_display}")

            # Confidence
            conf = bridged.confidence
            if conf >= 0.8:
                conf_label = "High (extensive history)"
            elif conf >= 0.5:
                conf_label = "Medium (growing history)"
            elif conf >= 0.2:
                conf_label = "Low (limited data)"
            else:
                conf_label = "Very low (new identity)"
            lines.append(f"**Confidence:** {conf:.0%} — {conf_label}")

            # EM track record
            if bridged.em_total_tasks > 0:
                success_rate = (
                    bridged.em_successful_tasks / bridged.em_total_tasks * 100
                    if bridged.em_total_tasks > 0
                    else 0
                )
                lines.append(
                    f"**EM Track Record:** {bridged.em_successful_tasks}/"
                    f"{bridged.em_total_tasks} tasks ({success_rate:.0f}% success)"
                )

            # On-chain ratings
            if bridged.chain_total_ratings > 0:
                lines.append(
                    f"**On-Chain Ratings:** {bridged.chain_total_ratings} total"
                )
                if bridged.chain_as_worker_avg > 0:
                    lines.append(
                        f"  As Worker: ⭐ {bridged.chain_as_worker_avg:.1f}/5.0"
                    )
                if bridged.chain_as_requester_avg > 0:
                    lines.append(
                        f"  As Requester: ⭐ {bridged.chain_as_requester_avg:.1f}/5.0"
                    )

            # Evidence weight for matching
            ew = bridged.evidence_weight
            lines.append(f"**Evidence Weight:** {ew:.0%} (for skill matching)")

            lines.append("")
            lines.append(
                "_This reputation is on-chain (Base) and portable to any ERC-8004 platform._"
            )

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Failed to build reputation badge for {wallet}: {e}")
            return ""

    async def _build_task_fitness(
        self, agent_id: str, wallet: str, task: dict
    ) -> str:
        """Build the task fitness section — how well this agent matches the task.

        Gives the agent self-awareness about whether it's a good fit,
        which helps it decide how to approach the work.
        """
        if not self.autojob:
            return ""

        try:
            result = await self.autojob.route_task(task, limit=10)

            if not result.rankings:
                return ""

            # Find this agent in the rankings
            my_ranking = None
            my_position = None
            for i, r in enumerate(result.rankings):
                if r.wallet.lower() == wallet.lower():
                    my_ranking = r
                    my_position = i + 1
                    break

            lines = ["### 🎯 Task Fitness\n"]

            task_title = task.get("title", "Unknown")[:50]
            task_cat = task.get("category", "unknown")
            lines.append(f"**Task:** {task_title}")
            lines.append(f"**Category:** {task_cat}")

            if my_ranking:
                score = my_ranking.final_score
                lines.append(
                    f"**Your Match:** {_score_emoji(score)} {score:.1f}/100 "
                    f"(#{my_position} of {result.qualified_candidates} qualified)"
                )
                lines.append(f"**Breakdown:** {my_ranking.explanation}")

                # Guidance based on score
                if score >= 80:
                    lines.append(
                        "\n✅ **Excellent fit.** You have strong evidence "
                        "for this type of task. Execute with confidence."
                    )
                elif score >= 60:
                    lines.append(
                        "\n🟡 **Good fit.** You have relevant experience. "
                        "Pay extra attention to areas where your score is lower."
                    )
                elif score >= 40:
                    lines.append(
                        "\n🟠 **Moderate fit.** Consider whether another agent "
                        "might be better suited. If proceeding, be thorough."
                    )
                else:
                    lines.append(
                        "\n🔴 **Weak fit.** You may lack experience in this area. "
                        "Flag this for reassignment if possible."
                    )
            else:
                lines.append("**Your Match:** Not ranked for this task")
                lines.append(
                    "\n⚠️ You don't appear in the qualified candidates. "
                    "Consider requesting reassignment."
                )

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Failed to build task fitness for {agent_id}: {e}")
            return ""

    def _build_swarm_awareness(self, agent_id: str) -> str:
        """Build swarm awareness section.

        Shows what other agents are working on to prevent duplication
        and enable coordination.
        """
        if not self.active_tasks and not self.lifecycle:
            return ""

        lines = ["### 🐝 Swarm Status\n"]

        # Active task claims
        if self.active_tasks:
            other_tasks = {
                tid: aid
                for tid, aid in self.active_tasks.items()
                if aid != agent_id
            }
            if other_tasks:
                lines.append(
                    f"**Tasks in progress by other agents:** {len(other_tasks)}"
                )
                for tid, aid in list(other_tasks.items())[:5]:
                    lines.append(f"  - `{tid[:12]}…` → {aid}")
                lines.append(
                    "\n⚠️ **Do NOT work on tasks already claimed above.**"
                )
            else:
                lines.append("No other tasks currently in progress.")

        # Agent fleet status from lifecycle manager
        if self.lifecycle:
            try:
                health = self.lifecycle.health_check()
                active = health.get("active", 0)
                sleeping = health.get("sleeping", 0)
                total = health.get("total_agents", 0)
                lines.append(
                    f"\n**Fleet:** {active} active / {sleeping} sleeping / {total} total"
                )

                budget_pct = health.get("budget_remaining_pct", 1.0)
                lines.append(
                    f"**Fleet Budget:** {budget_pct:.0%} remaining"
                )
            except Exception as e:
                logger.debug(f"Lifecycle health check failed: {e}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def _build_budget_context(self, agent_id: str) -> str:
        """Build budget context section.

        Shows the agent its resource limits to encourage efficient operation.
        """
        if not self.lifecycle:
            return ""

        agent_state = self.lifecycle.get_agent(agent_id)
        if not agent_state:
            return ""

        lines = ["### 💰 Resource Budget\n"]

        util = agent_state.budget_utilization()
        budget = agent_state.budget
        usage = agent_state.usage

        # Token budget
        token_pct = util.get("tokens", 0)
        lines.append(
            f"**Tokens:** {usage.tokens_today:,} / {budget.max_tokens_per_day:,} "
            f"({token_pct:.0%} used)"
        )

        # USD budget
        usd_pct = util.get("usd", 0)
        lines.append(
            f"**USDC Spend:** ${usage.usd_spent_today:.2f} / "
            f"${budget.max_usd_spend_per_day:.2f} "
            f"({usd_pct:.0%} used)"
        )

        # Task budget
        task_pct = util.get("tasks", 0)
        lines.append(
            f"**Tasks Created:** {usage.tasks_created_today} / "
            f"{budget.max_tasks_per_day} "
            f"({task_pct:.0%} used)"
        )

        # API calls
        api_pct = util.get("api_calls", 0)
        lines.append(
            f"**API Calls (this hour):** {usage.api_calls_this_hour} / "
            f"{budget.max_api_calls_per_hour}"
        )

        # Warnings
        max_pct = max(util.values()) if util else 0
        if max_pct >= 0.9:
            lines.append(
                "\n🔴 **Budget nearly exhausted.** Complete current task "
                "and prepare for sleep."
            )
        elif max_pct >= 0.7:
            lines.append(
                "\n🟡 **Budget 70%+ used.** Prioritize efficiency. "
                "Use cheaper models where possible."
            )

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Batch operations
    # -------------------------------------------------------------------

    async def build_all_agent_contexts(
        self,
        agents: List[dict],
        task: Optional[dict] = None,
    ) -> Dict[str, AgentContextBlock]:
        """Build context blocks for all agents in the swarm.

        Useful for the Swarm Coordinator to compare agents before assignment.

        Args:
            agents: List of {"agent_id": str, "wallet": str} dicts
            task: Optional task for fitness scoring

        Returns:
            Dict of agent_id → AgentContextBlock
        """
        results = {}
        for agent in agents:
            agent_id = agent.get("agent_id", "unknown")
            wallet = agent.get("wallet", "")
            try:
                block = await self.build_agent_context(
                    agent_id=agent_id,
                    wallet=wallet,
                    task=task,
                )
                results[agent_id] = block
            except Exception as e:
                logger.warning(f"Failed to build context for {agent_id}: {e}")
                results[agent_id] = AgentContextBlock(
                    agent_id=agent_id,
                    wallet=wallet,
                    generated_at=datetime.now(timezone.utc),
                )

        return results

    def update_active_tasks(self, task_id: str, agent_id: str):
        """Register that an agent has claimed a task."""
        self.active_tasks[task_id] = agent_id

    def complete_active_task(self, task_id: str):
        """Mark a task as completed (removes from active tracking)."""
        self.active_tasks.pop(task_id, None)

    def status(self) -> dict:
        """Get injector status."""
        return {
            "autojob_available": self.autojob is not None,
            "reputation_available": self.reputation is not None,
            "lifecycle_available": self.lifecycle is not None,
            "active_tasks": len(self.active_tasks),
            "cached_contexts": len(self._cache),
            "autojob_mode": (
                self.autojob.mode.value if self.autojob else "unavailable"
            ),
        }
