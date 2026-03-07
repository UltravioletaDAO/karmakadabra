"""
Karma Kadabra V2 — Lifecycle Manager Service

Production service that wraps ``lib.agent_lifecycle`` state machine logic
with persistent storage, batch operations, recovery management, and
integration with the swarm monitor.

Responsibilities:
  - Persist agent lifecycle state to disk (JSON per agent)
  - Batch start/stop operations for swarm deployment
  - Monitor heartbeats and detect stale/dead agents
  - Trigger circuit breaker and recovery flows
  - Generate health reports for the swarm monitor
  - Track operational statistics (uptime, MTBF, availability)

This service is the bridge between the pure-function lifecycle library
and the production swarm runner / orchestrator.

Usage:
    manager = LifecycleManagerService(state_dir=Path("data/lifecycle"))
    manager.start_agent("kk-researcher")
    manager.heartbeat("kk-researcher")
    manager.report_success("kk-researcher", task_id="t-123")
    stale = manager.check_heartbeats()
    report = manager.health_report()
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.lifecycle_manager")

# Import library state machine
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    TransitionReason,
    assess_swarm_health,
    create_agent_roster,
    get_available_agents,
    load_lifecycle_state,
    plan_startup_order,
    recommend_actions,
    save_lifecycle_state,
    transition as lib_transition,
    update_balance,
)


# ---------------------------------------------------------------------------
# Operational statistics
# ---------------------------------------------------------------------------

@dataclass
class AgentStats:
    """Runtime statistics for one agent."""
    agent_name: str
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    total_heartbeats: int = 0
    total_circuit_breaks: int = 0
    total_recoveries: int = 0
    first_started_at: str = ""
    last_active_at: str = ""
    uptime_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.total_tasks_completed + self.total_tasks_failed
        return self.total_tasks_completed / total if total > 0 else 0.0

    @property
    def mtbf_hours(self) -> float:
        """Mean time between failures (hours)."""
        if self.total_circuit_breaks == 0:
            return float("inf")
        return self.uptime_seconds / (self.total_circuit_breaks * 3600)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "tasks_completed": self.total_tasks_completed,
            "tasks_failed": self.total_tasks_failed,
            "success_rate": round(self.success_rate, 3),
            "circuit_breaks": self.total_circuit_breaks,
            "recoveries": self.total_recoveries,
            "heartbeats": self.total_heartbeats,
            "uptime_hours": round(self.uptime_seconds / 3600, 2),
            "mtbf_hours": round(self.mtbf_hours, 2) if self.mtbf_hours != float("inf") else "inf",
        }


# ---------------------------------------------------------------------------
# Lifecycle Manager Service
# ---------------------------------------------------------------------------

class LifecycleManagerService:
    """Production lifecycle manager with persistent state.

    Wraps the pure-function ``lib.agent_lifecycle`` state machine
    with disk persistence, batch operations, and statistics tracking.
    """

    def __init__(
        self,
        state_dir: str | Path = "data/lifecycle_state",
        config: LifecycleConfig | None = None,
    ):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or LifecycleConfig()
        self._stats: dict[str, AgentStats] = {}
        self._load_stats()

    # ----- State persistence -----

    def _agent_file(self, agent_name: str) -> Path:
        return self.state_dir / f"{agent_name}.json"

    def _stats_file(self) -> Path:
        return self.state_dir / "_stats.json"

    def _load_agent(self, agent_name: str) -> AgentLifecycle:
        """Load agent lifecycle from disk, creating default if needed."""
        file_path = self._agent_file(agent_name)
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                return AgentLifecycle(
                    agent_name=data.get("agent_name", agent_name),
                    agent_type=AgentType(data.get("agent_type", "user")),
                    state=AgentState(data.get("state", "offline")),
                    state_entered_at=data.get("state_entered_at", ""),
                    last_heartbeat=data.get("last_heartbeat", ""),
                    last_task_completed=data.get("last_task_completed", ""),
                    current_task_id=data.get("current_task_id", ""),
                    current_task_started=data.get("current_task_started", ""),
                    consecutive_failures=data.get("consecutive_failures", 0),
                    total_failures=data.get("total_failures", 0),
                    total_successes=data.get("total_successes", 0),
                    circuit_breaker_trips=data.get("circuit_breaker_trips", 0),
                    cooldown_until=data.get("cooldown_until", ""),
                    usdc_balance=data.get("usdc_balance", 0.0),
                    eth_balance=data.get("eth_balance", 0.0),
                    recent_transitions=data.get("recent_transitions", [])[-20:],
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Corrupt state for {agent_name}, creating fresh: {e}")

        return AgentLifecycle(
            agent_name=agent_name,
            agent_type=AgentType.USER,
            state=AgentState.OFFLINE,
        )

    def _save_agent(self, agent: AgentLifecycle) -> None:
        """Persist agent lifecycle state to disk."""
        data = {
            "agent_name": agent.agent_name,
            "agent_type": agent.agent_type.value,
            "state": agent.state.value,
            "state_entered_at": agent.state_entered_at,
            "last_heartbeat": agent.last_heartbeat,
            "last_task_completed": agent.last_task_completed,
            "current_task_id": agent.current_task_id,
            "current_task_started": agent.current_task_started,
            "consecutive_failures": agent.consecutive_failures,
            "total_failures": agent.total_failures,
            "total_successes": agent.total_successes,
            "circuit_breaker_trips": agent.circuit_breaker_trips,
            "cooldown_until": agent.cooldown_until,
            "usdc_balance": agent.usdc_balance,
            "eth_balance": agent.eth_balance,
            "recent_transitions": agent.recent_transitions[-20:],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self._agent_file(agent.agent_name).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _load_stats(self) -> None:
        """Load operational statistics from disk."""
        path = self._stats_file()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for name, stats_data in data.items():
                    self._stats[name] = AgentStats(
                        agent_name=name,
                        total_tasks_completed=stats_data.get("tasks_completed", 0),
                        total_tasks_failed=stats_data.get("tasks_failed", 0),
                        total_heartbeats=stats_data.get("heartbeats", 0),
                        total_circuit_breaks=stats_data.get("circuit_breaks", 0),
                        total_recoveries=stats_data.get("recoveries", 0),
                        first_started_at=stats_data.get("first_started_at", ""),
                        last_active_at=stats_data.get("last_active_at", ""),
                        uptime_seconds=stats_data.get("uptime_seconds", 0.0),
                    )
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_stats(self) -> None:
        """Persist operational statistics."""
        data = {name: s.to_dict() for name, s in self._stats.items()}
        self._stats_file().write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _get_stats(self, agent_name: str) -> AgentStats:
        """Get or create stats for an agent."""
        if agent_name not in self._stats:
            self._stats[agent_name] = AgentStats(agent_name=agent_name)
        return self._stats[agent_name]

    # ----- Core operations -----

    def start_agent(
        self,
        agent_name: str,
        agent_type: AgentType = AgentType.USER,
    ) -> AgentLifecycle:
        """Start an agent (OFFLINE → STARTING → IDLE).

        Returns the updated lifecycle state.
        """
        agent = self._load_agent(agent_name)
        agent.agent_type = agent_type

        if agent.state not in (AgentState.OFFLINE, AgentState.ERROR, AgentState.COOLDOWN):
            logger.info(f"{agent_name} already in state {agent.state.value}, skipping start")
            return agent

        # Check cooldown
        if agent.state == AgentState.COOLDOWN and agent.cooldown_until:
            now_iso = datetime.now(timezone.utc).isoformat()
            if now_iso < agent.cooldown_until:
                logger.info(f"{agent_name} still in cooldown until {agent.cooldown_until}")
                return agent

        # Reason-based transitions: OFFLINE → STARTING → IDLE
        reason = TransitionReason.STARTUP
        if agent.state == AgentState.ERROR:
            reason = TransitionReason.RECOVERY
        elif agent.state == AgentState.COOLDOWN:
            reason = TransitionReason.COOLDOWN_EXPIRED

        lib_transition(agent, reason, self.config)
        # If we went to STARTING, now go to IDLE
        if agent.state == AgentState.STARTING:
            lib_transition(agent, TransitionReason.STARTUP, self.config)

        now = datetime.now(timezone.utc).isoformat()
        agent.last_heartbeat = now

        stats = self._get_stats(agent_name)
        if not stats.first_started_at:
            stats.first_started_at = now
        stats.last_active_at = now

        self._save_agent(agent)
        self._save_stats()
        logger.info(f"Started {agent_name} (type={agent_type.value})")
        return agent

    def stop_agent(
        self,
        agent_name: str,
        reason: TransitionReason = TransitionReason.MANUAL_STOP,
        drain: bool = True,
    ) -> AgentLifecycle:
        """Stop an agent gracefully.

        If drain=True and agent is WORKING, transitions to DRAINING first.
        """
        agent = self._load_agent(agent_name)

        if agent.state == AgentState.OFFLINE:
            return agent

        # WORKING + drain → DRAINING (stays in draining until task completes)
        if drain and agent.state == AgentState.WORKING:
            lib_transition(agent, reason, self.config)
            # The state machine maps WORKING + MANUAL_STOP → DRAINING
        else:
            lib_transition(agent, reason, self.config)
            # If now in STOPPING, go to OFFLINE
            if agent.state == AgentState.STOPPING:
                lib_transition(agent, reason, self.config)

        self._save_agent(agent)
        logger.info(f"Stopped {agent_name} (reason={reason.value})")
        return agent

    def heartbeat(self, agent_name: str) -> bool:
        """Register heartbeat for an agent.

        Returns True if heartbeat was recorded, False if agent not found.
        """
        file_path = self._agent_file(agent_name)
        if not file_path.exists():
            return False

        agent = self._load_agent(agent_name)
        now = datetime.now(timezone.utc).isoformat()
        agent.last_heartbeat = now

        stats = self._get_stats(agent_name)
        stats.total_heartbeats += 1
        stats.last_active_at = now

        self._save_agent(agent)
        return True

    def report_success(
        self,
        agent_name: str,
        task_id: str = "",
    ) -> AgentLifecycle:
        """Report that an agent completed a task successfully."""
        agent = self._load_agent(agent_name)
        lib_transition(agent, TransitionReason.TASK_COMPLETED, self.config)
        agent.current_task_id = ""
        now = datetime.now(timezone.utc).isoformat()
        agent.last_task_completed = now

        stats = self._get_stats(agent_name)
        stats.total_tasks_completed += 1
        stats.last_active_at = now

        self._save_agent(agent)
        self._save_stats()
        logger.info(f"{agent_name} completed task {task_id}")
        return agent

    def report_failure(
        self,
        agent_name: str,
        task_id: str = "",
        error: str = "",
    ) -> AgentLifecycle:
        """Report that an agent failed a task.

        May trigger circuit breaker if consecutive failures exceed threshold.
        """
        agent = self._load_agent(agent_name)
        lib_transition(agent, TransitionReason.TASK_FAILED, self.config)
        agent.current_task_id = ""

        stats = self._get_stats(agent_name)
        stats.total_tasks_failed += 1

        # Check circuit breaker
        if agent.consecutive_failures >= self.config.circuit_breaker_threshold:
            lib_transition(agent, TransitionReason.CIRCUIT_BREAKER, self.config)
            stats.total_circuit_breaks += 1
            logger.warning(
                f"{agent_name} circuit breaker tripped "
                f"({agent.consecutive_failures} consecutive failures)"
            )

        self._save_agent(agent)
        self._save_stats()
        logger.info(f"{agent_name} failed task {task_id}: {error}")
        return agent

    def assign_task(
        self,
        agent_name: str,
        task_id: str,
    ) -> AgentLifecycle:
        """Assign a task to an agent (IDLE → WORKING)."""
        agent = self._load_agent(agent_name)

        if agent.state != AgentState.IDLE:
            logger.warning(
                f"Cannot assign task to {agent_name}: "
                f"state is {agent.state.value}, expected idle"
            )
            return agent

        lib_transition(agent, TransitionReason.TASK_ASSIGNED, self.config)
        agent.current_task_id = task_id

        self._save_agent(agent)
        logger.info(f"Assigned task {task_id} to {agent_name}")
        return agent

    def recover_agent(self, agent_name: str) -> AgentLifecycle:
        """Attempt to recover an agent from COOLDOWN or ERROR state."""
        agent = self._load_agent(agent_name)

        if agent.state not in (AgentState.COOLDOWN, AgentState.ERROR):
            logger.info(f"{agent_name} not in recoverable state ({agent.state.value})")
            return agent

        # Check cooldown expiry
        if agent.state == AgentState.COOLDOWN and agent.cooldown_until:
            now_iso = datetime.now(timezone.utc).isoformat()
            if now_iso < agent.cooldown_until:
                logger.info(f"{agent_name} cooldown not expired yet")
                return agent

        if agent.state == AgentState.ERROR:
            lib_transition(agent, TransitionReason.RECOVERY, self.config)
            # ERROR → STARTING → IDLE
            if agent.state == AgentState.STARTING:
                lib_transition(agent, TransitionReason.STARTUP, self.config)
        elif agent.state == AgentState.COOLDOWN:
            lib_transition(agent, TransitionReason.COOLDOWN_EXPIRED, self.config)

        agent.last_heartbeat = datetime.now(timezone.utc).isoformat()

        stats = self._get_stats(agent_name)
        stats.total_recoveries += 1

        self._save_agent(agent)
        self._save_stats()
        logger.info(f"Recovered {agent_name}")
        return agent

    # ----- Batch operations -----

    def start_batch(
        self,
        agent_names: list[str],
        agent_types: dict[str, AgentType] | None = None,
    ) -> list[AgentLifecycle]:
        """Start multiple agents in order (system → core → user)."""
        types = agent_types or {}
        agents_with_types = [
            (name, types.get(name, AgentType.USER))
            for name in agent_names
        ]
        # Sort by priority: system first, then core, then user
        priority = {AgentType.SYSTEM: 0, AgentType.CORE: 1, AgentType.USER: 2}
        agents_with_types.sort(key=lambda x: priority.get(x[1], 2))

        results = []
        for name, agent_type in agents_with_types:
            result = self.start_agent(name, agent_type)
            results.append(result)
        return results

    def stop_all(
        self,
        drain: bool = True,
    ) -> list[AgentLifecycle]:
        """Stop all agents."""
        results = []
        for file_path in self.state_dir.glob("*.json"):
            if file_path.name.startswith("_"):
                continue
            agent_name = file_path.stem
            result = self.stop_agent(agent_name, drain=drain)
            results.append(result)
        return results

    # ----- Monitoring -----

    def check_heartbeats(self, timeout_seconds: float = 300) -> list[str]:
        """Return names of agents with stale heartbeats."""
        stale = []
        now = datetime.now(timezone.utc)

        for file_path in self.state_dir.glob("*.json"):
            if file_path.name.startswith("_"):
                continue
            agent = self._load_agent(file_path.stem)
            if agent.state in (AgentState.OFFLINE, AgentState.COOLDOWN, AgentState.ERROR):
                continue
            if not agent.last_heartbeat:
                stale.append(agent.agent_name)
                continue
            try:
                last_hb = datetime.fromisoformat(agent.last_heartbeat)
                if last_hb.tzinfo is None:
                    last_hb = last_hb.replace(tzinfo=timezone.utc)
                age = (now - last_hb).total_seconds()
                if age > timeout_seconds:
                    stale.append(agent.agent_name)
            except (ValueError, TypeError):
                stale.append(agent.agent_name)

        return stale

    def get_agent_state(self, agent_name: str) -> dict:
        """Get current state of a specific agent."""
        agent = self._load_agent(agent_name)
        stats = self._get_stats(agent_name)
        return {
            "agent_name": agent.agent_name,
            "state": agent.state.value,
            "type": agent.agent_type.value,
            "consecutive_failures": agent.consecutive_failures,
            "total_successes": agent.total_successes,
            "total_failures": agent.total_failures,
            "current_task": agent.current_task_id,
            "last_heartbeat": agent.last_heartbeat,
            "cooldown_until": agent.cooldown_until,
            "stats": stats.to_dict(),
        }

    def get_all_states(self) -> list[dict]:
        """Get state of all tracked agents."""
        states = []
        for file_path in self.state_dir.glob("*.json"):
            if file_path.name.startswith("_"):
                continue
            states.append(self.get_agent_state(file_path.stem))
        return states

    def health_report(self) -> dict:
        """Generate a health report for the swarm monitor."""
        all_states = self.get_all_states()

        by_state = {}
        for s in all_states:
            state = s["state"]
            by_state[state] = by_state.get(state, 0) + 1

        online = sum(
            1 for s in all_states
            if s["state"] in ("idle", "working", "draining")
        )
        total = len(all_states)

        stale = self.check_heartbeats(self.config.stale_threshold_seconds)
        dead = self.check_heartbeats(self.config.dead_threshold_seconds)

        # Aggregate stats
        total_completed = sum(
            self._get_stats(s["agent_name"]).total_tasks_completed
            for s in all_states
        )
        total_failed = sum(
            self._get_stats(s["agent_name"]).total_tasks_failed
            for s in all_states
        )
        total_cb = sum(
            self._get_stats(s["agent_name"]).total_circuit_breaks
            for s in all_states
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agents_online": online,
            "agents_total": total,
            "by_state": by_state,
            "stale_agents": stale,
            "dead_agents": dead,
            "total_tasks_completed": total_completed,
            "total_tasks_failed": total_failed,
            "total_circuit_breaks": total_cb,
            "swarm_success_rate": round(
                total_completed / max(total_completed + total_failed, 1), 3
            ),
        }

    def summary_text(self) -> str:
        """Human-readable summary for IRC/Telegram."""
        report = self.health_report()
        lines = [
            f"🤖 KK Lifecycle Report — {report['timestamp'][:16]}",
            f"   Online: {report['agents_online']}/{report['agents_total']}",
            f"   States: {report['by_state']}",
            f"   Tasks: {report['total_tasks_completed']} done, "
            f"{report['total_tasks_failed']} failed "
            f"({report['swarm_success_rate']:.0%} success)",
        ]
        if report["stale_agents"]:
            lines.append(f"   ⚠️ Stale: {', '.join(report['stale_agents'])}")
        if report["dead_agents"]:
            lines.append(f"   🔴 Dead: {', '.join(report['dead_agents'])}")
        if report["total_circuit_breaks"] > 0:
            lines.append(f"   🔧 Circuit breaks: {report['total_circuit_breaks']}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------

class AgentLifecycleManager(LifecycleManagerService):
    """Backward-compatible alias for the old lifecycle manager.

    Preserves the old ``transition()`` and ``get_stale_agents()`` API
    while delegating to the new service underneath.
    """

    def transition(self, agent_id: str, new_state: str, context: dict | None = None) -> dict:
        """Legacy transition method — maps string states to reason-based transitions."""
        # Map target state to appropriate reason
        reason_map = {
            "INIT": TransitionReason.STARTUP,
            "IDLE": TransitionReason.STARTUP,  # covers STARTING → IDLE
            "SEEKING_WORK": TransitionReason.STARTUP,
            "WORKING": TransitionReason.TASK_ASSIGNED,
            "VERIFYING": TransitionReason.TASK_ASSIGNED,
            "COOLDOWN": TransitionReason.CIRCUIT_BREAKER,
            "ERROR": TransitionReason.FATAL_ERROR,
            "OFFLINE": TransitionReason.MANUAL_STOP,
        }
        reason = reason_map.get(new_state.upper(), TransitionReason.STARTUP)

        agent = self._load_agent(agent_id)

        # For IDLE target from OFFLINE, do startup flow
        if new_state.upper() in ("INIT", "IDLE", "SEEKING_WORK"):
            if agent.state == AgentState.OFFLINE:
                lib_transition(agent, TransitionReason.STARTUP, self.config)
            if agent.state == AgentState.STARTING:
                lib_transition(agent, TransitionReason.STARTUP, self.config)
        else:
            lib_transition(agent, reason, self.config)

        self._save_agent(agent)
        return self.get_agent_state(agent_id)

    def get_stale_agents(self, timeout_seconds: int = 300) -> list[str]:
        """Legacy method — delegates to check_heartbeats."""
        return self.check_heartbeats(timeout_seconds=float(timeout_seconds))
