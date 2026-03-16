"""
Agent Lifecycle Manager — Boot → Active → Sleep → Wake → Retire

Manages the full lifecycle of swarm agents, including:
- State machine (boot, active, sleeping, waking, retired, error)
- Health monitoring and heartbeat tracking
- Resource budget enforcement (tokens, USDC, API calls)
- Graceful degradation (sleep agents that exceed budgets)
- Scaling decisions (when to wake/sleep agents)

State Machine:
    ┌──────────┐     boot()     ┌──────────┐
    │ INACTIVE │ ──────────────► │ BOOTING  │
    └──────────┘                └─────┬────┘
                                      │ ready()
                                      ▼
    ┌──────────┐     sleep()    ┌──────────┐
    │ SLEEPING │ ◄──────────── │  ACTIVE   │◄──── wake()
    └────┬─────┘                └─────┬────┘         │
         │ wake()                     │ error()      │
         └────────────────────────────│──────────────┘
                                      ▼
                                ┌──────────┐
                                │  ERROR   │
                                └─────┬────┘
                                      │ recover() or retire()
                                      ▼
                                ┌──────────┐
                                │ RETIRED  │
                                └──────────┘
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Callable


logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent lifecycle states."""

    INACTIVE = "inactive"  # Not yet booted
    BOOTING = "booting"  # Starting up, loading context
    ACTIVE = "active"  # Running, processing tasks
    SLEEPING = "sleeping"  # Suspended (budget/schedule)
    WAKING = "waking"  # Transitioning from sleep to active
    ERROR = "error"  # Unhealthy, needs attention
    RETIRED = "retired"  # Permanently stopped


@dataclass
class ResourceBudget:
    """Daily resource limits for an agent."""

    max_tokens_per_day: int = 500_000  # ~$0.50 on Haiku, ~$7.50 on Sonnet
    max_usd_spend_per_day: float = 1.00  # USDC spend on EM tasks
    max_api_calls_per_hour: int = 60  # Rate limit guard
    max_tasks_per_day: int = 20  # EM task creation limit
    max_errors_per_hour: int = 5  # Error threshold before auto-sleep

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResourceUsage:
    """Current resource usage tracking."""

    tokens_today: int = 0
    usd_spent_today: float = 0.0
    api_calls_this_hour: int = 0
    tasks_created_today: int = 0
    errors_this_hour: int = 0
    last_reset_date: str = ""  # YYYY-MM-DD
    last_hour_reset: float = 0.0  # timestamp

    def reset_daily(self):
        """Reset daily counters."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.last_reset_date != today:
            self.tokens_today = 0
            self.usd_spent_today = 0.0
            self.tasks_created_today = 0
            self.last_reset_date = today

    def reset_hourly(self):
        """Reset hourly counters."""
        now = time.time()
        if now - self.last_hour_reset >= 3600:
            self.api_calls_this_hour = 0
            self.errors_this_hour = 0
            self.last_hour_reset = now


@dataclass
class AgentState:
    """Complete state of a swarm agent."""

    # Identity
    agent_id: str  # e.g., "agent_aurora"
    wallet: str  # Ethereum wallet address
    personality: str = ""  # Personality archetype (explorer, builder, etc.)
    erc8004_id: Optional[int] = None  # On-chain identity token ID

    # Status
    status: AgentStatus = AgentStatus.INACTIVE
    status_since: Optional[datetime] = None
    status_reason: str = ""

    # Health
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    uptime_seconds: float = 0.0

    # Resources
    budget: ResourceBudget = field(default_factory=ResourceBudget)
    usage: ResourceUsage = field(default_factory=ResourceUsage)

    # Schedule (cron-based activity windows)
    active_hours_utc: List[int] = field(default_factory=lambda: list(range(6, 23)))
    stagger_offset_minutes: int = 0  # Offset to avoid API stampede

    # Metadata
    model: str = "anthropic/claude-haiku-4-5"
    server: str = ""  # Which Cherry server
    created_at: Optional[datetime] = None

    def is_healthy(self) -> bool:
        """Check if agent is responsive."""
        if not self.last_heartbeat:
            return False
        age = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        return age < 600  # Healthy if heartbeat within 10 minutes

    def is_within_budget(self) -> bool:
        """Check if agent is within all resource limits."""
        self.usage.reset_daily()
        self.usage.reset_hourly()
        return (
            self.usage.tokens_today < self.budget.max_tokens_per_day
            and self.usage.usd_spent_today < self.budget.max_usd_spend_per_day
            and self.usage.api_calls_this_hour < self.budget.max_api_calls_per_hour
            and self.usage.tasks_created_today < self.budget.max_tasks_per_day
            and self.usage.errors_this_hour < self.budget.max_errors_per_hour
        )

    def is_active_hour(self) -> bool:
        """Check if current UTC hour is in agent's active window."""
        current_hour = datetime.now(timezone.utc).hour
        return current_hour in self.active_hours_utc

    def budget_utilization(self) -> dict:
        """Get budget utilization percentages."""
        self.usage.reset_daily()
        return {
            "tokens": self.usage.tokens_today / max(1, self.budget.max_tokens_per_day),
            "usd": self.usage.usd_spent_today
            / max(0.01, self.budget.max_usd_spend_per_day),
            "api_calls": self.usage.api_calls_this_hour
            / max(1, self.budget.max_api_calls_per_hour),
            "tasks": self.usage.tasks_created_today
            / max(1, self.budget.max_tasks_per_day),
        }

    def to_dict(self) -> dict:
        """Serialize for API/storage."""
        d = asdict(self)
        for key in ("status_since", "last_heartbeat", "created_at"):
            if d.get(key):
                d[key] = d[key].isoformat()
        d["status"] = self.status.value
        d["is_healthy"] = self.is_healthy()
        d["is_within_budget"] = self.is_within_budget()
        d["budget_utilization"] = self.budget_utilization()
        return d


class LifecycleManager:
    """
    Manages lifecycle of all agents in the swarm.

    Responsibilities:
    - Track agent states
    - Enforce budgets (auto-sleep agents that exceed limits)
    - Schedule activity windows (stagger to prevent stampedes)
    - Health monitoring (heartbeat tracking)
    - Scaling decisions (which agents to wake/sleep)
    """

    def __init__(
        self,
        max_agents: int = 48,
        state_file: Optional[str] = None,
    ):
        """
        Initialize lifecycle manager.

        Args:
            max_agents: Maximum concurrent active agents
            state_file: Path to persist state (JSON)
        """
        self.max_agents = max_agents
        self.state_file = state_file
        self.agents: Dict[str, AgentState] = {}
        self._event_handlers: List[Callable] = []

        # Load persisted state
        if state_file:
            self._load_state()

    # ── Agent Registration ──

    def register_agent(
        self,
        agent_id: str,
        wallet: str,
        personality: str = "",
        model: str = "anthropic/claude-haiku-4-5",
        budget: Optional[ResourceBudget] = None,
        active_hours: Optional[List[int]] = None,
        stagger_offset: int = 0,
    ) -> AgentState:
        """
        Register a new agent in the swarm.

        Args:
            agent_id: Unique agent identifier
            wallet: Ethereum wallet address
            personality: Agent personality archetype
            model: LLM model to use
            budget: Resource budget (defaults to standard)
            active_hours: Active hours in UTC
            stagger_offset: Minutes offset for cron staggering

        Returns:
            New AgentState
        """
        if agent_id in self.agents:
            logger.warning(f"Agent {agent_id} already registered, updating")

        state = AgentState(
            agent_id=agent_id,
            wallet=wallet.lower(),
            personality=personality,
            model=model,
            budget=budget or ResourceBudget(),
            active_hours_utc=active_hours or list(range(6, 23)),
            stagger_offset_minutes=stagger_offset,
            created_at=datetime.now(timezone.utc),
        )

        self.agents[agent_id] = state
        self._persist_state()
        self._emit_event("agent_registered", agent_id)

        logger.info(
            f"Registered agent {agent_id} (wallet={wallet[:10]}..., model={model})"
        )
        return state

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove agent from swarm."""
        if agent_id not in self.agents:
            return False

        agent = self.agents[agent_id]
        if agent.status == AgentStatus.ACTIVE:
            self.sleep_agent(agent_id, reason="unregistered")

        del self.agents[agent_id]
        self._persist_state()
        self._emit_event("agent_unregistered", agent_id)
        return True

    # ── State Transitions ──

    def boot_agent(self, agent_id: str) -> bool:
        """
        Start booting an agent.

        Transitions: INACTIVE/SLEEPING → BOOTING
        """
        agent = self.agents.get(agent_id)
        if not agent:
            logger.error(f"Agent {agent_id} not registered")
            return False

        if agent.status not in (AgentStatus.INACTIVE, AgentStatus.SLEEPING):
            logger.warning(f"Cannot boot {agent_id} from status {agent.status}")
            return False

        # Check if we have capacity
        active_count = self.active_agent_count()
        if active_count >= self.max_agents:
            logger.warning(
                f"Cannot boot {agent_id}: at capacity ({active_count}/{self.max_agents})"
            )
            return False

        agent.status = AgentStatus.BOOTING
        agent.status_since = datetime.now(timezone.utc)
        agent.status_reason = "boot_requested"
        agent.consecutive_failures = 0

        self._persist_state()
        self._emit_event("agent_booting", agent_id)
        logger.info(f"Agent {agent_id} booting")
        return True

    def activate_agent(self, agent_id: str) -> bool:
        """
        Mark agent as fully active.

        Transitions: BOOTING/WAKING → ACTIVE
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        if agent.status not in (AgentStatus.BOOTING, AgentStatus.WAKING):
            logger.warning(f"Cannot activate {agent_id} from status {agent.status}")
            return False

        agent.status = AgentStatus.ACTIVE
        agent.status_since = datetime.now(timezone.utc)
        agent.status_reason = "ready"
        agent.last_heartbeat = datetime.now(timezone.utc)

        self._persist_state()
        self._emit_event("agent_activated", agent_id)
        logger.info(f"Agent {agent_id} now ACTIVE")
        return True

    def sleep_agent(self, agent_id: str, reason: str = "scheduled") -> bool:
        """
        Put agent to sleep (suspend).

        Transitions: ACTIVE/ERROR → SLEEPING
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        if agent.status not in (AgentStatus.ACTIVE, AgentStatus.ERROR):
            logger.warning(f"Cannot sleep {agent_id} from status {agent.status}")
            return False

        # Calculate uptime
        if agent.status_since:
            delta = (datetime.now(timezone.utc) - agent.status_since).total_seconds()
            agent.uptime_seconds += delta

        agent.status = AgentStatus.SLEEPING
        agent.status_since = datetime.now(timezone.utc)
        agent.status_reason = reason

        self._persist_state()
        self._emit_event("agent_sleeping", agent_id, reason=reason)
        logger.info(f"Agent {agent_id} sleeping (reason: {reason})")
        return True

    def wake_agent(self, agent_id: str) -> bool:
        """
        Wake a sleeping agent.

        Transitions: SLEEPING → WAKING → (then activate_agent for ACTIVE)
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        if agent.status != AgentStatus.SLEEPING:
            logger.warning(f"Cannot wake {agent_id} from status {agent.status}")
            return False

        active_count = self.active_agent_count()
        if active_count >= self.max_agents:
            logger.warning(f"Cannot wake {agent_id}: at capacity")
            return False

        agent.status = AgentStatus.WAKING
        agent.status_since = datetime.now(timezone.utc)
        agent.status_reason = "wake_requested"

        self._persist_state()
        self._emit_event("agent_waking", agent_id)
        logger.info(f"Agent {agent_id} waking")
        return True

    def error_agent(self, agent_id: str, error: str) -> bool:
        """
        Mark agent as errored.

        Transitions: ACTIVE/BOOTING/WAKING → ERROR
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        agent.status = AgentStatus.ERROR
        agent.status_since = datetime.now(timezone.utc)
        agent.status_reason = error
        agent.consecutive_failures += 1

        # Auto-retire after 10 consecutive failures
        if agent.consecutive_failures >= 10:
            self.retire_agent(
                agent_id,
                f"Auto-retired: {agent.consecutive_failures} consecutive failures",
            )
            return True

        self._persist_state()
        self._emit_event("agent_error", agent_id, error=error)
        logger.error(
            f"Agent {agent_id} ERROR: {error} (failures: {agent.consecutive_failures})"
        )
        return True

    def retire_agent(self, agent_id: str, reason: str = "manual") -> bool:
        """
        Permanently retire an agent.

        Transitions: ANY → RETIRED
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        agent.status = AgentStatus.RETIRED
        agent.status_since = datetime.now(timezone.utc)
        agent.status_reason = reason

        self._persist_state()
        self._emit_event("agent_retired", agent_id, reason=reason)
        logger.info(f"Agent {agent_id} RETIRED: {reason}")
        return True

    # ── Heartbeat & Health ──

    def heartbeat(self, agent_id: str, usage_delta: Optional[dict] = None) -> dict:
        """
        Record agent heartbeat and check health.

        Called periodically by each agent. Returns directives.

        Args:
            agent_id: Reporting agent
            usage_delta: Resource usage since last heartbeat
                {tokens: int, usd: float, api_calls: int, errors: int}

        Returns:
            dict with directives:
                {"action": "continue"} - keep working
                {"action": "sleep", "reason": "budget_exceeded"} - go to sleep
                {"action": "wake"} - you should be active
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return {"action": "error", "reason": "unknown_agent"}

        # Update heartbeat timestamp
        agent.last_heartbeat = datetime.now(timezone.utc)

        # Update usage counters
        if usage_delta:
            agent.usage.reset_daily()
            agent.usage.reset_hourly()
            agent.usage.tokens_today += usage_delta.get("tokens", 0)
            agent.usage.usd_spent_today += usage_delta.get("usd", 0)
            agent.usage.api_calls_this_hour += usage_delta.get("api_calls", 0)
            agent.usage.errors_this_hour += usage_delta.get("errors", 0)

        # Check budget
        if not agent.is_within_budget():
            over = self._identify_budget_violation(agent)
            self.sleep_agent(agent_id, reason=f"budget_exceeded: {over}")
            return {"action": "sleep", "reason": f"budget_exceeded: {over}"}

        # Check schedule
        if not agent.is_active_hour() and agent.status == AgentStatus.ACTIVE:
            self.sleep_agent(agent_id, reason="outside_active_hours")
            return {"action": "sleep", "reason": "outside_active_hours"}

        # Agent is sleeping but should be active
        if (
            agent.status == AgentStatus.SLEEPING
            and agent.is_active_hour()
            and agent.is_within_budget()
        ):
            return {"action": "wake"}

        self._persist_state()
        return {"action": "continue"}

    def health_check(self) -> dict:
        """
        Get swarm health overview.

        Returns:
            {
                "total_agents": 48,
                "active": 35,
                "sleeping": 10,
                "error": 2,
                "retired": 1,
                "healthy": 33,
                "unhealthy": 2,
                "budget_remaining_pct": 0.65,
                "agents": [...]
            }
        """
        status_counts = {}
        healthy_count = 0
        total_budget_used = 0.0
        total_budget_max = 0.0

        agent_summaries = []

        for agent_id, agent in self.agents.items():
            status = agent.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

            if agent.status == AgentStatus.ACTIVE and agent.is_healthy():
                healthy_count += 1

            total_budget_used += agent.usage.usd_spent_today
            total_budget_max += agent.budget.max_usd_spend_per_day

            agent_summaries.append(
                {
                    "agent_id": agent_id,
                    "status": status,
                    "healthy": agent.is_healthy(),
                    "budget_pct": round(
                        agent.usage.usd_spent_today
                        / max(0.01, agent.budget.max_usd_spend_per_day),
                        3,
                    ),
                    "tasks_today": agent.usage.tasks_created_today,
                    "last_heartbeat": agent.last_heartbeat.isoformat()
                    if agent.last_heartbeat
                    else None,
                }
            )

        budget_remaining = 1.0 - (total_budget_used / max(0.01, total_budget_max))

        return {
            "total_agents": len(self.agents),
            "status_counts": status_counts,
            "active": status_counts.get("active", 0),
            "sleeping": status_counts.get("sleeping", 0),
            "error": status_counts.get("error", 0),
            "retired": status_counts.get("retired", 0),
            "healthy": healthy_count,
            "unhealthy": status_counts.get("active", 0) - healthy_count,
            "budget_remaining_pct": round(budget_remaining, 3),
            "agents": agent_summaries,
        }

    # ── Scheduling ──

    def get_agents_to_wake(self) -> List[str]:
        """Get list of agents that should be woken up right now."""
        to_wake = []
        for agent_id, agent in self.agents.items():
            if (
                agent.status == AgentStatus.SLEEPING
                and agent.is_active_hour()
                and agent.is_within_budget()
                and agent.consecutive_failures < 5
            ):
                to_wake.append(agent_id)
        return to_wake

    def get_agents_to_sleep(self) -> List[str]:
        """Get list of agents that should be put to sleep."""
        to_sleep = []
        for agent_id, agent in self.agents.items():
            if agent.status == AgentStatus.ACTIVE:
                if not agent.is_active_hour():
                    to_sleep.append(agent_id)
                elif not agent.is_within_budget():
                    to_sleep.append(agent_id)
                elif not agent.is_healthy():
                    # Unhealthy for more than 30 minutes
                    if agent.last_heartbeat:
                        age = (
                            datetime.now(timezone.utc) - agent.last_heartbeat
                        ).total_seconds()
                        if age > 1800:
                            to_sleep.append(agent_id)
        return to_sleep

    def auto_manage(self) -> dict:
        """
        Automatic lifecycle management tick.

        Call this every few minutes (e.g., from a cron job).
        Handles waking, sleeping, and error recovery.

        Returns:
            Summary of actions taken
        """
        actions = {"woken": [], "slept": [], "recovered": [], "retired": []}

        # Wake eligible agents
        for agent_id in self.get_agents_to_wake():
            active_count = self.active_agent_count()
            if active_count < self.max_agents:
                if self.wake_agent(agent_id):
                    self.activate_agent(agent_id)  # Skip WAKING for auto-manage
                    actions["woken"].append(agent_id)

        # Sleep agents that should be sleeping
        for agent_id in self.get_agents_to_sleep():
            reason = "auto_manage"
            agent = self.agents[agent_id]
            if not agent.is_active_hour():
                reason = "outside_active_hours"
            elif not agent.is_within_budget():
                reason = f"budget_exceeded: {self._identify_budget_violation(agent)}"
            elif not agent.is_healthy():
                reason = "unhealthy"

            if self.sleep_agent(agent_id, reason=reason):
                actions["slept"].append(agent_id)

        # Recover errored agents (if they've been errored for > 5 min)
        for agent_id, agent in self.agents.items():
            if agent.status == AgentStatus.ERROR and agent.status_since:
                error_duration = (
                    datetime.now(timezone.utc) - agent.status_since
                ).total_seconds()
                if error_duration > 300 and agent.consecutive_failures < 5:
                    # Try to recover
                    agent.status = AgentStatus.SLEEPING
                    agent.status_reason = "auto_recovered"
                    actions["recovered"].append(agent_id)

        self._persist_state()

        if any(v for v in actions.values()):
            logger.info(f"Auto-manage: {actions}")

        return actions

    # ── Helpers ──

    def active_agent_count(self) -> int:
        """Count currently active (or booting/waking) agents."""
        active_states = {AgentStatus.ACTIVE, AgentStatus.BOOTING, AgentStatus.WAKING}
        return sum(1 for a in self.agents.values() if a.status in active_states)

    def get_agent(self, agent_id: str) -> Optional[AgentState]:
        """Get agent state by ID."""
        return self.agents.get(agent_id)

    def get_agents_by_status(self, status: AgentStatus) -> List[AgentState]:
        """Get all agents in a given status."""
        return [a for a in self.agents.values() if a.status == status]

    def on_event(self, handler: Callable):
        """Register an event handler."""
        self._event_handlers.append(handler)

    def _emit_event(self, event: str, agent_id: str, **kwargs):
        """Emit lifecycle event to all handlers."""
        for handler in self._event_handlers:
            try:
                handler(event, agent_id, **kwargs)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def _identify_budget_violation(self, agent: AgentState) -> str:
        """Identify which budget was exceeded."""
        violations = []
        if agent.usage.tokens_today >= agent.budget.max_tokens_per_day:
            violations.append("tokens")
        if agent.usage.usd_spent_today >= agent.budget.max_usd_spend_per_day:
            violations.append("usd")
        if agent.usage.api_calls_this_hour >= agent.budget.max_api_calls_per_hour:
            violations.append("api_calls")
        if agent.usage.tasks_created_today >= agent.budget.max_tasks_per_day:
            violations.append("tasks")
        if agent.usage.errors_this_hour >= agent.budget.max_errors_per_hour:
            violations.append("errors")
        return ", ".join(violations) or "unknown"

    # ── State Persistence ──

    def _persist_state(self):
        """Save state to disk."""
        if not self.state_file:
            return
        try:
            data = {}
            for agent_id, agent in self.agents.items():
                data[agent_id] = agent.to_dict()

            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

    def _load_state(self):
        """Load state from disk."""
        if not self.state_file:
            return
        try:
            with open(self.state_file) as f:
                data = json.load(f)
            for agent_id, agent_dict in data.items():
                try:
                    # Restore enum
                    if "status" in agent_dict and isinstance(agent_dict["status"], str):
                        agent_dict["status"] = AgentStatus(agent_dict["status"])
                    # Restore datetimes
                    for dt_key in ("status_since", "last_heartbeat", "created_at"):
                        if agent_dict.get(dt_key) and isinstance(
                            agent_dict[dt_key], str
                        ):
                            agent_dict[dt_key] = datetime.fromisoformat(
                                agent_dict[dt_key]
                            )
                    # Remove computed fields (not part of dataclass)
                    for computed in (
                        "is_healthy",
                        "is_within_budget",
                        "budget_utilization",
                    ):
                        agent_dict.pop(computed, None)
                    # Restore nested dataclasses
                    if "budget" in agent_dict and isinstance(
                        agent_dict["budget"], dict
                    ):
                        agent_dict["budget"] = ResourceBudget(**agent_dict["budget"])
                    if "usage" in agent_dict and isinstance(agent_dict["usage"], dict):
                        agent_dict["usage"] = ResourceUsage(**agent_dict["usage"])
                    self.agents[agent_id] = AgentState(**agent_dict)
                except Exception as e:
                    logger.warning(f"Failed to deserialize agent {agent_id}: {e}")
            logger.info(f"Loaded state for {len(self.agents)} agents")
        except FileNotFoundError:
            logger.info("No state file found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
