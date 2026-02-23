"""
Karma Kadabra V2 — Agent Lifecycle Manager

Manages the complete lifecycle of agents in the swarm:

  - State machine: OFFLINE → STARTING → IDLE → WORKING → STOPPING → OFFLINE
  - Circuit breaker: Consecutive failures trigger cooldown periods
  - Heartbeat tracking: Detect stale/dead agents
  - Recovery: Exponential backoff with jitter for failed agents
  - Startup ordering: System agents first, then user agents in batches
  - Graceful shutdown: Complete current tasks before stopping
  - Resource tracking: Memory/balance monitoring per agent

The lifecycle manager doesn't execute agents directly — it provides the
decision layer that tells the swarm runner what to do with each agent.

Design principles:
  - Pure functions where possible (state transitions are testable)
  - Configurable thresholds (circuit breaker limits, backoff params)
  - Event-sourced (all transitions logged as events)
  - Coordinator-ready (feeds into coordinator matching decisions)
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.lifecycle")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentState(Enum):
    """Agent lifecycle states."""
    OFFLINE = "offline"       # Not running, not scheduled
    STARTING = "starting"     # Initialization in progress
    IDLE = "idle"             # Running, waiting for task assignment
    WORKING = "working"       # Executing an assigned task
    STOPPING = "stopping"     # Graceful shutdown in progress
    COOLDOWN = "cooldown"     # Circuit breaker tripped, waiting
    ERROR = "error"           # Fatal error, needs manual intervention
    DRAINING = "draining"     # Finishing current task, then stopping


class AgentType(Enum):
    """Agent classification for startup ordering."""
    SYSTEM = "system"     # coordinator, validator — start first
    CORE = "core"         # karma-hello, extractors — start second
    USER = "user"         # Regular task workers — start last


class TransitionReason(Enum):
    """Why a state transition occurred."""
    STARTUP = "startup"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"
    CIRCUIT_BREAKER = "circuit_breaker"
    COOLDOWN_EXPIRED = "cooldown_expired"
    MANUAL_STOP = "manual_stop"
    MANUAL_START = "manual_start"
    DRAIN_COMPLETE = "drain_complete"
    FATAL_ERROR = "fatal_error"
    BALANCE_LOW = "balance_low"
    RECOVERY = "recovery"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LifecycleConfig:
    """Configuration for lifecycle management."""
    # Circuit breaker
    circuit_breaker_threshold: int = 3       # Consecutive failures before tripping
    circuit_breaker_reset_after: int = 5     # Successful tasks to fully reset

    # Cooldown (exponential backoff)
    cooldown_base_seconds: float = 60.0      # Base cooldown after circuit break
    cooldown_max_seconds: float = 3600.0     # Maximum cooldown (1 hour)
    cooldown_multiplier: float = 2.0         # Exponential multiplier
    cooldown_jitter: float = 0.2             # Random jitter factor (±20%)

    # Heartbeat
    heartbeat_interval_seconds: float = 300.0  # Expected heartbeat interval (5 min)
    stale_threshold_seconds: float = 600.0     # Stale after 10 min without heartbeat
    dead_threshold_seconds: float = 1800.0     # Dead after 30 min

    # Balance
    min_usdc_balance: float = 0.01           # Minimum USDC to remain active
    min_eth_balance: float = 0.0001          # Minimum ETH for gas

    # Startup
    startup_batch_size: int = 5              # Agents to start simultaneously
    startup_batch_delay_seconds: float = 10.0  # Delay between batches
    startup_timeout_seconds: float = 60.0    # Max time for agent to start

    # Task timeout
    task_timeout_seconds: float = 3600.0     # Max time for a single task (1 hour)
    drain_timeout_seconds: float = 300.0     # Max time to drain before force stop


# ---------------------------------------------------------------------------
# Agent Lifecycle State
# ---------------------------------------------------------------------------

@dataclass
class AgentLifecycle:
    """Complete lifecycle state for one agent."""
    agent_name: str
    agent_type: AgentType = AgentType.USER
    state: AgentState = AgentState.OFFLINE

    # Timing
    state_entered_at: str = ""        # ISO timestamp
    last_heartbeat: str = ""          # ISO timestamp
    last_task_completed: str = ""     # ISO timestamp

    # Current task
    current_task_id: str = ""
    current_task_started: str = ""    # ISO timestamp

    # Circuit breaker
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    circuit_breaker_trips: int = 0
    cooldown_until: str = ""          # ISO timestamp

    # Resource status
    usdc_balance: float = 0.0
    eth_balance: float = 0.0

    # Transition history (recent only, for debugging)
    recent_transitions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type.value,
            "state": self.state.value,
            "state_entered_at": self.state_entered_at,
            "last_heartbeat": self.last_heartbeat,
            "last_task_completed": self.last_task_completed,
            "current_task_id": self.current_task_id,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "circuit_breaker_trips": self.circuit_breaker_trips,
            "cooldown_until": self.cooldown_until,
            "usdc_balance": self.usdc_balance,
            "eth_balance": self.eth_balance,
            "recent_transitions": self.recent_transitions[-10:],  # Keep last 10
        }


@dataclass
class TransitionEvent:
    """Record of a state transition."""
    agent_name: str
    from_state: AgentState
    to_state: AgentState
    reason: TransitionReason
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent_name,
            "from": self.from_state.value,
            "to": self.to_state.value,
            "reason": self.reason.value,
            "timestamp": self.timestamp,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# State Machine — Valid Transitions
# ---------------------------------------------------------------------------

# Map of (current_state, reason) → allowed next_state
VALID_TRANSITIONS: dict[tuple[AgentState, TransitionReason], AgentState] = {
    # Startup flow
    (AgentState.OFFLINE, TransitionReason.STARTUP): AgentState.STARTING,
    (AgentState.OFFLINE, TransitionReason.MANUAL_START): AgentState.STARTING,
    (AgentState.STARTING, TransitionReason.STARTUP): AgentState.IDLE,

    # Task lifecycle
    (AgentState.IDLE, TransitionReason.TASK_ASSIGNED): AgentState.WORKING,
    (AgentState.WORKING, TransitionReason.TASK_COMPLETED): AgentState.IDLE,
    (AgentState.WORKING, TransitionReason.TASK_FAILED): AgentState.IDLE,

    # Circuit breaker
    (AgentState.IDLE, TransitionReason.CIRCUIT_BREAKER): AgentState.COOLDOWN,
    (AgentState.WORKING, TransitionReason.CIRCUIT_BREAKER): AgentState.COOLDOWN,
    (AgentState.COOLDOWN, TransitionReason.COOLDOWN_EXPIRED): AgentState.IDLE,

    # Shutdown
    (AgentState.IDLE, TransitionReason.MANUAL_STOP): AgentState.STOPPING,
    (AgentState.WORKING, TransitionReason.MANUAL_STOP): AgentState.DRAINING,
    (AgentState.DRAINING, TransitionReason.DRAIN_COMPLETE): AgentState.STOPPING,
    (AgentState.DRAINING, TransitionReason.TASK_COMPLETED): AgentState.STOPPING,
    (AgentState.DRAINING, TransitionReason.TASK_FAILED): AgentState.STOPPING,
    (AgentState.STOPPING, TransitionReason.MANUAL_STOP): AgentState.OFFLINE,
    (AgentState.COOLDOWN, TransitionReason.MANUAL_STOP): AgentState.STOPPING,

    # Error/recovery
    (AgentState.IDLE, TransitionReason.FATAL_ERROR): AgentState.ERROR,
    (AgentState.WORKING, TransitionReason.FATAL_ERROR): AgentState.ERROR,
    (AgentState.STARTING, TransitionReason.FATAL_ERROR): AgentState.ERROR,
    (AgentState.ERROR, TransitionReason.RECOVERY): AgentState.STARTING,
    (AgentState.ERROR, TransitionReason.MANUAL_START): AgentState.STARTING,

    # Heartbeat timeout
    (AgentState.IDLE, TransitionReason.HEARTBEAT_TIMEOUT): AgentState.ERROR,
    (AgentState.WORKING, TransitionReason.HEARTBEAT_TIMEOUT): AgentState.ERROR,

    # Balance low → cooldown (not fatal, can recover)
    (AgentState.IDLE, TransitionReason.BALANCE_LOW): AgentState.COOLDOWN,
    (AgentState.WORKING, TransitionReason.BALANCE_LOW): AgentState.DRAINING,
}


def is_valid_transition(
    current: AgentState,
    reason: TransitionReason,
) -> bool:
    """Check if a state transition is valid."""
    return (current, reason) in VALID_TRANSITIONS


def get_next_state(
    current: AgentState,
    reason: TransitionReason,
) -> AgentState | None:
    """Get the next state for a transition, or None if invalid."""
    return VALID_TRANSITIONS.get((current, reason))


# ---------------------------------------------------------------------------
# State Transition Engine
# ---------------------------------------------------------------------------

def transition(
    agent: AgentLifecycle,
    reason: TransitionReason,
    config: LifecycleConfig | None = None,
    now: datetime | None = None,
    details: dict[str, Any] | None = None,
) -> TransitionEvent | None:
    """Attempt a state transition for an agent.

    Mutates the agent in place. Returns a TransitionEvent if successful,
    None if the transition is invalid.

    Args:
        agent: The agent lifecycle state to transition.
        reason: Why the transition is happening.
        config: Lifecycle configuration.
        now: Current time (for testing).
        details: Additional details for the event.

    Returns:
        TransitionEvent if transition succeeded, None if invalid.
    """
    if config is None:
        config = LifecycleConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    next_state = get_next_state(agent.state, reason)
    if next_state is None:
        logger.warning(
            f"Invalid transition: {agent.agent_name} "
            f"{agent.state.value} --[{reason.value}]--> ???"
        )
        return None

    event = TransitionEvent(
        agent_name=agent.agent_name,
        from_state=agent.state,
        to_state=next_state,
        reason=reason,
        timestamp=now.isoformat(),
        details=details or {},
    )

    # Apply transition
    old_state = agent.state
    agent.state = next_state
    agent.state_entered_at = now.isoformat()

    # Side effects based on transition type
    _apply_transition_effects(agent, old_state, next_state, reason, config, now, details)

    # Record in history
    agent.recent_transitions.append(event.to_dict())
    if len(agent.recent_transitions) > 20:
        agent.recent_transitions = agent.recent_transitions[-20:]

    logger.info(
        f"Transition: {agent.agent_name} "
        f"{old_state.value} --[{reason.value}]--> {next_state.value}"
    )

    return event


def _apply_transition_effects(
    agent: AgentLifecycle,
    old_state: AgentState,
    new_state: AgentState,
    reason: TransitionReason,
    config: LifecycleConfig,
    now: datetime,
    details: dict[str, Any] | None,
) -> None:
    """Apply side effects of a state transition."""
    details = details or {}

    if reason == TransitionReason.TASK_ASSIGNED:
        agent.current_task_id = details.get("task_id", "")
        agent.current_task_started = now.isoformat()

    elif reason == TransitionReason.TASK_COMPLETED:
        agent.current_task_id = ""
        agent.current_task_started = ""
        agent.last_task_completed = now.isoformat()
        agent.total_successes += 1
        agent.consecutive_failures = 0  # Reset on success

    elif reason == TransitionReason.TASK_FAILED:
        agent.current_task_id = ""
        agent.current_task_started = ""
        agent.total_failures += 1
        agent.consecutive_failures += 1

        # Check circuit breaker
        if agent.consecutive_failures >= config.circuit_breaker_threshold:
            # Will need a separate circuit breaker transition
            pass

    elif reason == TransitionReason.CIRCUIT_BREAKER:
        agent.circuit_breaker_trips += 1
        cooldown = compute_cooldown(
            trip_count=agent.circuit_breaker_trips,
            base=config.cooldown_base_seconds,
            max_cooldown=config.cooldown_max_seconds,
            multiplier=config.cooldown_multiplier,
            jitter=config.cooldown_jitter,
        )
        agent.cooldown_until = (now + timedelta(seconds=cooldown)).isoformat()
        agent.current_task_id = ""
        agent.current_task_started = ""

    elif reason == TransitionReason.COOLDOWN_EXPIRED:
        agent.cooldown_until = ""

    elif reason == TransitionReason.RECOVERY:
        # Partial reset — keep history, clear error state
        agent.cooldown_until = ""

    elif new_state == AgentState.OFFLINE:
        # Full cleanup
        agent.current_task_id = ""
        agent.current_task_started = ""
        agent.cooldown_until = ""


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

def should_trip_circuit_breaker(
    agent: AgentLifecycle,
    config: LifecycleConfig | None = None,
) -> bool:
    """Check if the circuit breaker should trip for this agent.

    Returns True if consecutive failures exceed the threshold.
    """
    if config is None:
        config = LifecycleConfig()
    return agent.consecutive_failures >= config.circuit_breaker_threshold


def compute_cooldown(
    trip_count: int,
    base: float = 60.0,
    max_cooldown: float = 3600.0,
    multiplier: float = 2.0,
    jitter: float = 0.2,
) -> float:
    """Compute cooldown duration with exponential backoff and jitter.

    Args:
        trip_count: Number of times the circuit breaker has tripped.
        base: Base cooldown in seconds.
        max_cooldown: Maximum cooldown in seconds.
        multiplier: Exponential multiplier.
        jitter: Random jitter factor (±jitter%).

    Returns:
        Cooldown duration in seconds.
    """
    # Exponential backoff: base * multiplier^(trip_count - 1)
    raw = base * (multiplier ** max(0, trip_count - 1))
    capped = min(raw, max_cooldown)

    # Add jitter
    jitter_range = capped * jitter
    jittered = capped + random.uniform(-jitter_range, jitter_range)

    return max(0, jittered)


def is_cooldown_expired(
    agent: AgentLifecycle,
    now: datetime | None = None,
) -> bool:
    """Check if an agent's cooldown period has expired."""
    if not agent.cooldown_until:
        return True

    if now is None:
        now = datetime.now(timezone.utc)

    try:
        cooldown_end = datetime.fromisoformat(agent.cooldown_until.replace("Z", "+00:00"))
        return now >= cooldown_end
    except (ValueError, TypeError):
        return True  # Can't parse → treat as expired


# ---------------------------------------------------------------------------
# Heartbeat Monitoring
# ---------------------------------------------------------------------------

def check_heartbeat(
    agent: AgentLifecycle,
    config: LifecycleConfig | None = None,
    now: datetime | None = None,
) -> str:
    """Check agent heartbeat status.

    Returns:
        "alive" — heartbeat is fresh
        "stale" — heartbeat is older than stale threshold
        "dead" — heartbeat is older than dead threshold
        "unknown" — no heartbeat recorded
    """
    if config is None:
        config = LifecycleConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    if not agent.last_heartbeat:
        return "unknown"

    try:
        hb_time = datetime.fromisoformat(agent.last_heartbeat.replace("Z", "+00:00"))
        age = (now - hb_time).total_seconds()
    except (ValueError, TypeError):
        return "unknown"

    if age > config.dead_threshold_seconds:
        return "dead"
    elif age > config.stale_threshold_seconds:
        return "stale"
    return "alive"


def record_heartbeat(
    agent: AgentLifecycle,
    now: datetime | None = None,
) -> None:
    """Record a heartbeat for an agent."""
    if now is None:
        now = datetime.now(timezone.utc)
    agent.last_heartbeat = now.isoformat()


# ---------------------------------------------------------------------------
# Balance Monitoring
# ---------------------------------------------------------------------------

def check_balance(
    agent: AgentLifecycle,
    config: LifecycleConfig | None = None,
) -> dict[str, bool]:
    """Check if agent balances are above minimum thresholds.

    Returns dict with 'usdc_ok', 'eth_ok', 'overall_ok'.
    """
    if config is None:
        config = LifecycleConfig()

    usdc_ok = agent.usdc_balance >= config.min_usdc_balance
    eth_ok = agent.eth_balance >= config.min_eth_balance

    return {
        "usdc_ok": usdc_ok,
        "eth_ok": eth_ok,
        "overall_ok": usdc_ok and eth_ok,
    }


def update_balance(
    agent: AgentLifecycle,
    usdc: float | None = None,
    eth: float | None = None,
) -> None:
    """Update agent balance information."""
    if usdc is not None:
        agent.usdc_balance = usdc
    if eth is not None:
        agent.eth_balance = eth


# ---------------------------------------------------------------------------
# Task Timeout Detection
# ---------------------------------------------------------------------------

def check_task_timeout(
    agent: AgentLifecycle,
    config: LifecycleConfig | None = None,
    now: datetime | None = None,
) -> bool:
    """Check if the agent's current task has exceeded the timeout.

    Returns True if timed out.
    """
    if config is None:
        config = LifecycleConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    if agent.state != AgentState.WORKING or not agent.current_task_started:
        return False

    try:
        start = datetime.fromisoformat(agent.current_task_started.replace("Z", "+00:00"))
        elapsed = (now - start).total_seconds()
        return elapsed > config.task_timeout_seconds
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Startup Planning
# ---------------------------------------------------------------------------

def plan_startup_order(
    agents: list[AgentLifecycle],
    config: LifecycleConfig | None = None,
) -> list[list[str]]:
    """Plan the order in which agents should be started.

    Returns list of batches (each batch is a list of agent names).
    System agents start first, then core, then user agents in batches.
    """
    if config is None:
        config = LifecycleConfig()

    # Group by type
    system_agents = [a.agent_name for a in agents if a.agent_type == AgentType.SYSTEM]
    core_agents = [a.agent_name for a in agents if a.agent_type == AgentType.CORE]
    user_agents = [a.agent_name for a in agents if a.agent_type == AgentType.USER]

    batches: list[list[str]] = []

    # System agents first (all at once, they're critical)
    if system_agents:
        batches.append(system_agents)

    # Core agents second (all at once, usually few)
    if core_agents:
        batches.append(core_agents)

    # User agents in batches
    for i in range(0, len(user_agents), config.startup_batch_size):
        batch = user_agents[i:i + config.startup_batch_size]
        batches.append(batch)

    return batches


# ---------------------------------------------------------------------------
# Swarm Health Assessment
# ---------------------------------------------------------------------------

@dataclass
class SwarmHealth:
    """Overall swarm health assessment."""
    total_agents: int = 0
    online_agents: int = 0     # IDLE + WORKING
    working_agents: int = 0
    idle_agents: int = 0
    cooldown_agents: int = 0
    error_agents: int = 0
    offline_agents: int = 0
    starting_agents: int = 0

    # Aggregate metrics
    total_failures: int = 0
    total_successes: int = 0
    agents_with_low_balance: int = 0
    agents_with_stale_heartbeat: int = 0

    # Computed
    availability_ratio: float = 0.0  # online / total
    success_ratio: float = 0.0       # successes / (successes + failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_agents": self.total_agents,
            "online": self.online_agents,
            "working": self.working_agents,
            "idle": self.idle_agents,
            "cooldown": self.cooldown_agents,
            "error": self.error_agents,
            "offline": self.offline_agents,
            "starting": self.starting_agents,
            "availability_ratio": round(self.availability_ratio, 3),
            "success_ratio": round(self.success_ratio, 3),
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "agents_low_balance": self.agents_with_low_balance,
            "agents_stale_heartbeat": self.agents_with_stale_heartbeat,
        }


def assess_swarm_health(
    agents: list[AgentLifecycle],
    config: LifecycleConfig | None = None,
    now: datetime | None = None,
) -> SwarmHealth:
    """Assess the overall health of the swarm.

    Args:
        agents: List of all agent lifecycle states.
        config: Lifecycle configuration.
        now: Current time (for testing).

    Returns:
        SwarmHealth with aggregate metrics.
    """
    if config is None:
        config = LifecycleConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    health = SwarmHealth(total_agents=len(agents))

    for agent in agents:
        # Count by state
        if agent.state == AgentState.IDLE:
            health.idle_agents += 1
            health.online_agents += 1
        elif agent.state == AgentState.WORKING:
            health.working_agents += 1
            health.online_agents += 1
        elif agent.state == AgentState.COOLDOWN:
            health.cooldown_agents += 1
        elif agent.state == AgentState.ERROR:
            health.error_agents += 1
        elif agent.state == AgentState.OFFLINE:
            health.offline_agents += 1
        elif agent.state == AgentState.STARTING:
            health.starting_agents += 1

        # Aggregate metrics
        health.total_failures += agent.total_failures
        health.total_successes += agent.total_successes

        # Balance check
        balance = check_balance(agent, config)
        if not balance["overall_ok"]:
            health.agents_with_low_balance += 1

        # Heartbeat check
        hb_status = check_heartbeat(agent, config, now)
        if hb_status in ("stale", "dead"):
            health.agents_with_stale_heartbeat += 1

    # Computed ratios
    if health.total_agents > 0:
        health.availability_ratio = health.online_agents / health.total_agents

    total_tasks = health.total_successes + health.total_failures
    if total_tasks > 0:
        health.success_ratio = health.total_successes / total_tasks

    return health


# ---------------------------------------------------------------------------
# Action Recommendations
# ---------------------------------------------------------------------------

def recommend_actions(
    agents: list[AgentLifecycle],
    config: LifecycleConfig | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Generate recommended actions based on agent lifecycle states.

    Returns a list of action dicts with keys:
      - action: "start", "stop", "recover", "trip_breaker", "cooldown_release", "task_timeout"
      - agent: agent name
      - reason: human-readable reason
      - priority: "critical", "high", "medium", "low"
    """
    if config is None:
        config = LifecycleConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    actions = []

    for agent in agents:
        # Check for expired cooldowns
        if agent.state == AgentState.COOLDOWN and is_cooldown_expired(agent, now):
            actions.append({
                "action": "cooldown_release",
                "agent": agent.agent_name,
                "reason": f"Cooldown expired (trips: {agent.circuit_breaker_trips})",
                "priority": "medium",
            })

        # Check for task timeouts
        if check_task_timeout(agent, config, now):
            actions.append({
                "action": "task_timeout",
                "agent": agent.agent_name,
                "reason": f"Task {agent.current_task_id} exceeded timeout",
                "priority": "high",
            })

        # Check for circuit breaker trips needed
        if agent.state in (AgentState.IDLE, AgentState.WORKING):
            if should_trip_circuit_breaker(agent, config):
                actions.append({
                    "action": "trip_breaker",
                    "agent": agent.agent_name,
                    "reason": f"{agent.consecutive_failures} consecutive failures",
                    "priority": "high",
                })

        # Check heartbeat
        if agent.state in (AgentState.IDLE, AgentState.WORKING):
            hb = check_heartbeat(agent, config, now)
            if hb == "dead":
                actions.append({
                    "action": "recover",
                    "agent": agent.agent_name,
                    "reason": "Agent presumed dead (no heartbeat)",
                    "priority": "critical",
                })
            elif hb == "stale":
                actions.append({
                    "action": "check",
                    "agent": agent.agent_name,
                    "reason": "Heartbeat is stale",
                    "priority": "low",
                })

        # Check balance
        if agent.state in (AgentState.IDLE, AgentState.WORKING):
            balance = check_balance(agent, config)
            if not balance["overall_ok"]:
                details = []
                if not balance["usdc_ok"]:
                    details.append(f"USDC: {agent.usdc_balance}")
                if not balance["eth_ok"]:
                    details.append(f"ETH: {agent.eth_balance}")
                actions.append({
                    "action": "balance_alert",
                    "agent": agent.agent_name,
                    "reason": f"Low balance: {', '.join(details)}",
                    "priority": "high",
                })

        # Error agents that might be recoverable
        if agent.state == AgentState.ERROR:
            actions.append({
                "action": "recover",
                "agent": agent.agent_name,
                "reason": "Agent in error state",
                "priority": "medium",
            })

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda a: priority_order.get(a["priority"], 4))

    return actions


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_lifecycle_state(
    agents: list[AgentLifecycle],
    output_path: Path,
) -> None:
    """Save lifecycle state for all agents."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "agent_count": len(agents),
        "agents": {a.agent_name: a.to_dict() for a in agents},
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_lifecycle_state(
    input_path: Path,
) -> list[AgentLifecycle]:
    """Load lifecycle state from a JSON file.

    Returns list of AgentLifecycle objects.
    """
    if not input_path.exists():
        return []

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load lifecycle state: {e}")
        return []

    agents = []
    for name, agent_data in data.get("agents", {}).items():
        agent = AgentLifecycle(
            agent_name=name,
            agent_type=AgentType(agent_data.get("agent_type", "user")),
            state=AgentState(agent_data.get("state", "offline")),
            state_entered_at=agent_data.get("state_entered_at", ""),
            last_heartbeat=agent_data.get("last_heartbeat", ""),
            last_task_completed=agent_data.get("last_task_completed", ""),
            current_task_id=agent_data.get("current_task_id", ""),
            consecutive_failures=agent_data.get("consecutive_failures", 0),
            total_failures=agent_data.get("total_failures", 0),
            total_successes=agent_data.get("total_successes", 0),
            circuit_breaker_trips=agent_data.get("circuit_breaker_trips", 0),
            cooldown_until=agent_data.get("cooldown_until", ""),
            usdc_balance=agent_data.get("usdc_balance", 0.0),
            eth_balance=agent_data.get("eth_balance", 0.0),
            recent_transitions=agent_data.get("recent_transitions", []),
        )
        agents.append(agent)

    return agents


# ---------------------------------------------------------------------------
# Swarm Runner Helper
# ---------------------------------------------------------------------------

def create_agent_roster(
    agent_configs: list[dict[str, Any]],
) -> list[AgentLifecycle]:
    """Create a roster of agents from configuration data.

    Args:
        agent_configs: List of dicts with at minimum 'name' and optionally:
            - 'type': "system", "core", or "user"
            - 'usdc_balance': float
            - 'eth_balance': float

    Returns:
        List of AgentLifecycle objects in OFFLINE state.
    """
    agents = []
    for cfg in agent_configs:
        agent = AgentLifecycle(
            agent_name=cfg["name"],
            agent_type=AgentType(cfg.get("type", "user")),
        )
        if "usdc_balance" in cfg:
            agent.usdc_balance = cfg["usdc_balance"]
        if "eth_balance" in cfg:
            agent.eth_balance = cfg["eth_balance"]
        agents.append(agent)
    return agents


def get_available_agents(
    agents: list[AgentLifecycle],
) -> list[AgentLifecycle]:
    """Get agents that are available for task assignment."""
    return [a for a in agents if a.state == AgentState.IDLE]


def get_agents_by_state(
    agents: list[AgentLifecycle],
    state: AgentState,
) -> list[AgentLifecycle]:
    """Get agents in a specific state."""
    return [a for a in agents if a.state == state]
