"""
Karma Kadabra V2 — Swarm Orchestrator

Top-level orchestration layer that combines all subsystems into
a self-healing, production-ready swarm management daemon:

  - Agent Lifecycle: state machine, circuit breaker, recovery
  - Coordinator: task matching + assignment (legacy/enhanced/autojob)
  - Reputation Bridge: unified scoring across chains
  - Observability: health monitoring + metrics
  - Dashboard: terminal/markdown/JSON status views

This is the entry point for running the KK V2 swarm. It manages:
  1. Startup sequence (system → core → user agents, in batches)
  2. Main loop (coordinator cycles with health checks between rounds)
  3. Self-healing (detect and recover failed agents)
  4. Graceful shutdown (drain active tasks, save state)
  5. Operational metrics and reporting

Usage:
  python swarm_orchestrator.py                    # Full swarm operation
  python swarm_orchestrator.py --dry-run          # Preview without executing
  python swarm_orchestrator.py --status           # Current swarm status
  python swarm_orchestrator.py --health           # Health report
  python swarm_orchestrator.py --leaderboard      # Reputation leaderboard
  python swarm_orchestrator.py --once             # Run single cycle then exit
  python swarm_orchestrator.py --interval 120     # Custom cycle interval (seconds)
  python swarm_orchestrator.py --autojob          # Enable AutoJob matching
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

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
    transition,
)
from lib.observability import (
    assess_agent_health,
    compute_swarm_metrics,
    generate_health_report,
    save_health_report,
)
from lib.reputation_bridge import (
    compute_swarm_reputation,
    format_leaderboard_text,
    generate_leaderboard,
    load_latest_snapshot,
    save_reputation_snapshot,
    UnifiedReputation,
    classify_tier,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.orchestrator")


# ═══════════════════════════════════════════════════════════════════
# Orchestrator State
# ═══════════════════════════════════════════════════════════════════


class OrchestratorPhase(Enum):
    """Lifecycle phases of the orchestrator."""
    INIT = "init"
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class CycleResult:
    """Result of a single orchestration cycle."""
    cycle_number: int
    phase: str
    started_at: str
    finished_at: str
    duration_ms: float
    tasks_found: int = 0
    tasks_assigned: int = 0
    agents_started: int = 0
    agents_recovered: int = 0
    agents_stopped: int = 0
    health_checks_run: int = 0
    matching_mode: str = "enhanced"
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    actions_taken: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cycle": self.cycle_number,
            "phase": self.phase,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "tasks_found": self.tasks_found,
            "tasks_assigned": self.tasks_assigned,
            "agents_started": self.agents_started,
            "agents_recovered": self.agents_recovered,
            "agents_stopped": self.agents_stopped,
            "health_checks_run": self.health_checks_run,
            "matching_mode": self.matching_mode,
            "errors": self.errors,
            "warnings": self.warnings,
            "actions_taken": self.actions_taken,
        }


@dataclass
class OrchestratorState:
    """Persistent state of the orchestrator between restarts."""
    phase: OrchestratorPhase = OrchestratorPhase.INIT
    started_at: Optional[str] = None
    total_cycles: int = 0
    total_tasks_assigned: int = 0
    total_agents_recovered: int = 0
    total_errors: int = 0
    last_cycle_at: Optional[str] = None
    last_health_check_at: Optional[str] = None
    last_reputation_sync_at: Optional[str] = None
    uptime_seconds: float = 0.0
    cycle_history: list = field(default_factory=list)  # Last N cycles

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "started_at": self.started_at,
            "total_cycles": self.total_cycles,
            "total_tasks_assigned": self.total_tasks_assigned,
            "total_agents_recovered": self.total_agents_recovered,
            "total_errors": self.total_errors,
            "last_cycle_at": self.last_cycle_at,
            "last_health_check_at": self.last_health_check_at,
            "last_reputation_sync_at": self.last_reputation_sync_at,
            "uptime_seconds": self.uptime_seconds,
            "recent_cycles": [c.to_dict() if hasattr(c, 'to_dict') else c
                              for c in self.cycle_history[-10:]],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestratorState":
        phase_str = data.get("phase", "init")
        try:
            phase = OrchestratorPhase(phase_str)
        except ValueError:
            phase = OrchestratorPhase.INIT
        return cls(
            phase=phase,
            started_at=data.get("started_at"),
            total_cycles=data.get("total_cycles", 0),
            total_tasks_assigned=data.get("total_tasks_assigned", 0),
            total_agents_recovered=data.get("total_agents_recovered", 0),
            total_errors=data.get("total_errors", 0),
            last_cycle_at=data.get("last_cycle_at"),
            last_health_check_at=data.get("last_health_check_at"),
            last_reputation_sync_at=data.get("last_reputation_sync_at"),
            uptime_seconds=data.get("uptime_seconds", 0.0),
            cycle_history=data.get("recent_cycles", []),
        )


@dataclass
class OrchestratorConfig:
    """Configuration for the swarm orchestrator."""
    cycle_interval_seconds: int = 60          # Time between coordination cycles
    health_check_interval_seconds: int = 300  # Time between full health checks
    reputation_sync_interval_seconds: int = 900  # Time between reputation syncs
    max_recovery_attempts: int = 3            # Max auto-recovery attempts per agent
    recovery_cooldown_seconds: int = 120      # Cooldown between recovery attempts
    drain_timeout_seconds: int = 300          # Max time to drain tasks on shutdown
    startup_batch_delay_seconds: int = 5      # Delay between startup batches
    max_cycle_history: int = 50               # Cycles to keep in history
    stale_heartbeat_minutes: int = 30         # Heartbeat staleness threshold
    low_balance_threshold_usdc: float = 0.50  # Alert threshold
    autojob_enabled: bool = False
    autojob_path: Optional[str] = None
    autojob_api: Optional[str] = None
    use_legacy_matching: bool = False
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "cycle_interval": self.cycle_interval_seconds,
            "health_check_interval": self.health_check_interval_seconds,
            "reputation_sync_interval": self.reputation_sync_interval_seconds,
            "max_recovery_attempts": self.max_recovery_attempts,
            "drain_timeout": self.drain_timeout_seconds,
            "autojob_enabled": self.autojob_enabled,
            "dry_run": self.dry_run,
        }


# ═══════════════════════════════════════════════════════════════════
# Agent Registry
# ═══════════════════════════════════════════════════════════════════


# KK V2 agents (from generate-workspaces.py + Terraform config)
AGENT_REGISTRY = [
    # System agents (start first, batch 0)
    {"name": "kk-coordinator", "type": "system"},
    {"name": "kk-validator", "type": "system"},
    # Core agents (start second, batch 1)
    {"name": "kk-karma-hello", "type": "core"},
    {"name": "kk-skill-extractor", "type": "core"},
    {"name": "kk-soul-extractor", "type": "core"},
    {"name": "kk-voice-extractor", "type": "core"},
    # User agents (start in batches of 4, batch 2+)
    {"name": "kk-abracadabra", "type": "user"},
    {"name": "kk-agent-3", "type": "user"},
    {"name": "kk-agent-4", "type": "user"},
    {"name": "kk-agent-5", "type": "user"},
    {"name": "kk-agent-6", "type": "user"},
    {"name": "kk-agent-7", "type": "user"},
    {"name": "kk-agent-8", "type": "user"},
    {"name": "kk-agent-9", "type": "user"},
    {"name": "kk-agent-10", "type": "user"},
    {"name": "kk-agent-11", "type": "user"},
    {"name": "kk-agent-12", "type": "user"},
    {"name": "kk-agent-13", "type": "user"},
    {"name": "kk-agent-14", "type": "user"},
    {"name": "kk-agent-15", "type": "user"},
    {"name": "kk-agent-16", "type": "user"},
    {"name": "kk-agent-17", "type": "user"},
    {"name": "kk-agent-18", "type": "user"},
    {"name": "kk-agent-19", "type": "user"},
]


# ═══════════════════════════════════════════════════════════════════
# Swarm Orchestrator
# ═══════════════════════════════════════════════════════════════════


class SwarmOrchestrator:
    """Production-ready swarm orchestrator with self-healing.

    Manages the full lifecycle of a KK V2 agent swarm:
    startup → coordination cycles → health monitoring → shutdown.
    """

    def __init__(
        self,
        data_dir: Path,
        config: OrchestratorConfig = None,
        agent_registry: list = None,
    ):
        self.data_dir = Path(data_dir)
        self.config = config or OrchestratorConfig()
        self.agent_registry = agent_registry or AGENT_REGISTRY
        self.lifecycle_config = LifecycleConfig()

        # Paths
        self.lifecycle_path = self.data_dir / "lifecycle_state.json"
        self.state_path = self.data_dir / "orchestrator_state.json"
        self.reports_dir = self.data_dir / "reports"
        self.reputation_dir = self.data_dir / "reputation"

        # Runtime state
        self.agents: list[AgentLifecycle] = []
        self.state = OrchestratorState()
        self._shutdown_requested = False
        self._start_time = None
        self._recovery_tracker: dict[str, list[float]] = {}  # agent → [timestamps]

    # ─── State Persistence ─────────────────────────────────────────

    def load_state(self) -> None:
        """Load persisted orchestrator + lifecycle state."""
        # Load agents
        if self.lifecycle_path.exists():
            self.agents = load_lifecycle_state(self.lifecycle_path)
            logger.info(f"Loaded {len(self.agents)} agents from state")
        else:
            self.agents = create_agent_roster(self.agent_registry)
            logger.info(f"Created new roster: {len(self.agents)} agents")

        # Load orchestrator state
        if self.state_path.exists():
            try:
                raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.state = OrchestratorState.from_dict(raw)
                logger.info(
                    f"Restored orchestrator state: {self.state.total_cycles} cycles, "
                    f"{self.state.total_tasks_assigned} tasks assigned"
                )
            except Exception as e:
                logger.warning(f"Failed to load orchestrator state: {e}")
                self.state = OrchestratorState()

    def save_state(self) -> None:
        """Persist all state to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Update uptime
        if self._start_time:
            self.state.uptime_seconds = time.time() - self._start_time

        # Save lifecycle
        save_lifecycle_state(self.agents, self.lifecycle_path)

        # Save orchestrator state
        self.state_path.write_text(
            json.dumps(self.state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ─── Startup Sequence ──────────────────────────────────────────

    async def startup(self) -> int:
        """Execute the startup sequence.

        Returns number of agents successfully started.
        """
        self.state.phase = OrchestratorPhase.STARTING
        self._start_time = time.time()
        self.state.started_at = datetime.now(timezone.utc).isoformat()
        started_count = 0

        logger.info("=" * 60)
        logger.info("  🐝 Karma Kadabra V2 — Swarm Startup")
        logger.info("=" * 60)

        # Plan startup order
        batches = plan_startup_order(self.agents, self.lifecycle_config)
        logger.info(f"Startup plan: {len(batches)} batches")

        now = datetime.now(timezone.utc)

        for batch_idx, batch_names in enumerate(batches):
            batch_type = "system" if batch_idx == 0 else (
                "core" if batch_idx == 1 else f"user-{batch_idx - 1}"
            )
            logger.info(f"Starting batch {batch_idx + 1} ({batch_type}): {batch_names}")

            for agent_name in batch_names:
                agent = self._find_agent(agent_name)
                if not agent:
                    logger.warning(f"Agent {agent_name} not in roster, skipping")
                    continue

                if agent.state in (AgentState.IDLE, AgentState.WORKING):
                    # Already running
                    started_count += 1
                    continue

                # Transition to STARTING → IDLE
                try:
                    transition(agent, TransitionReason.STARTUP, now=now)
                    # Simulate startup (in production: check heartbeat or poll)
                    transition(agent, TransitionReason.STARTUP, now=now)
                    started_count += 1
                    logger.info(f"  ✅ {agent_name} started")
                except Exception as e:
                    logger.error(f"  ❌ {agent_name} failed to start: {e}")
                    try:
                        transition(agent, TransitionReason.FATAL_ERROR, now=now)
                    except Exception:
                        pass

            # Delay between batches
            if batch_idx < len(batches) - 1 and self.config.startup_batch_delay_seconds > 0:
                await asyncio.sleep(self.config.startup_batch_delay_seconds)

        self.state.phase = OrchestratorPhase.RUNNING
        logger.info(f"Startup complete: {started_count}/{len(self.agents)} agents online")

        self.save_state()
        return started_count

    # ─── Health Monitoring ─────────────────────────────────────────

    def run_health_check(self) -> dict:
        """Run a comprehensive health check on all agents.

        Returns health summary dict.
        """
        now = datetime.now(timezone.utc)

        # Build per-agent health snapshots
        snapshots = []
        for agent in self.agents:
            snap = assess_agent_health(
                agent_name=agent.agent_name,
                last_heartbeat=agent.last_heartbeat or None,
                active_task_id=agent.current_task_id or None,
                tasks_completed_24h=agent.total_successes,
                tasks_failed_24h=agent.total_failures,
                balance_usdc=agent.usdc_balance,
                balance_eth=agent.eth_balance,
                now=now,
            )
            snapshots.append(snap)

        # Compute swarm metrics
        metrics = compute_swarm_metrics(snapshots, now=now)

        # Generate and save report
        report = generate_health_report(snapshots, metrics)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = save_health_report(report, self.reports_dir)

        # Assess swarm health
        health = assess_swarm_health(self.agents, self.lifecycle_config, now)

        self.state.last_health_check_at = now.isoformat()

        summary = {
            "timestamp": now.isoformat(),
            "total_agents": health.total_agents,
            "online": health.online_agents,
            "idle": health.idle_agents,
            "working": health.working_agents,
            "error": health.error_agents,
            "offline": health.offline_agents,
            "availability": health.availability_ratio,
            "success_rate": health.success_ratio,
            "low_balance": health.agents_with_low_balance,
            "stale_heartbeat": health.agents_with_stale_heartbeat,
            "report_path": str(report_path) if report_path else None,
        }

        logger.info(
            f"Health check: {health.online_agents}/{health.total_agents} online, "
            f"availability={health.availability_ratio:.0%}, "
            f"errors={health.error_agents}, stale={health.agents_with_stale_heartbeat}"
        )

        return summary

    # ─── Self-Healing ──────────────────────────────────────────────

    def attempt_recovery(self) -> list[str]:
        """Detect and attempt to recover failed/stale agents.

        Returns list of agents that were recovered.
        """
        now = datetime.now(timezone.utc)
        recovered = []

        for agent in self.agents:
            # Skip system agents (coordinator/validator manage themselves)
            if agent.agent_type == AgentType.SYSTEM:
                continue

            needs_recovery = False
            reason = ""

            # Case 1: Agent in ERROR state
            if agent.state == AgentState.ERROR:
                needs_recovery = True
                reason = "error_state"

            # Case 2: Stale heartbeat (agent unresponsive)
            elif agent.state in (AgentState.IDLE, AgentState.WORKING):
                if agent.last_heartbeat:
                    try:
                        last_hb = datetime.fromisoformat(agent.last_heartbeat)
                        if last_hb.tzinfo is None:
                            last_hb = last_hb.replace(tzinfo=timezone.utc)
                        stale_threshold = timedelta(
                            minutes=self.config.stale_heartbeat_minutes
                        )
                        if now - last_hb > stale_threshold:
                            needs_recovery = True
                            reason = "stale_heartbeat"
                    except (ValueError, TypeError):
                        pass

            # Case 3: Too many consecutive failures (circuit breaker)
            if (
                not needs_recovery
                and agent.consecutive_failures >= 3
                and agent.state != AgentState.COOLDOWN
            ):
                needs_recovery = True
                reason = "circuit_breaker"

            if not needs_recovery:
                continue

            # Check recovery rate limit
            if not self._can_recover(agent.agent_name):
                logger.warning(
                    f"  ⚠️ {agent.agent_name}: needs recovery ({reason}) "
                    f"but hit recovery limit"
                )
                continue

            # Attempt recovery
            try:
                logger.info(
                    f"  🔄 Recovering {agent.agent_name} (reason={reason})"
                )

                if reason == "circuit_breaker":
                    # Put in cooldown, don't restart
                    transition(agent, TransitionReason.CIRCUIT_BREAKER, now=now)
                elif agent.state == AgentState.ERROR:
                    # Restart from ERROR: ERROR → STARTING → IDLE
                    transition(agent, TransitionReason.RECOVERY, now=now)
                    transition(agent, TransitionReason.STARTUP, now=now)
                    agent.consecutive_failures = 0
                elif reason == "stale_heartbeat":
                    # Stale agent: force to ERROR first, then recover
                    transition(agent, TransitionReason.HEARTBEAT_TIMEOUT, now=now)
                    transition(agent, TransitionReason.RECOVERY, now=now)
                    transition(agent, TransitionReason.STARTUP, now=now)
                    agent.consecutive_failures = 0

                self._record_recovery(agent.agent_name)
                recovered.append(agent.agent_name)
                logger.info(f"  ✅ {agent.agent_name} recovered ({reason})")

            except Exception as e:
                logger.error(
                    f"  ❌ Recovery failed for {agent.agent_name}: {e}"
                )

        if recovered:
            self.state.total_agents_recovered += len(recovered)

        return recovered

    def _can_recover(self, agent_name: str) -> bool:
        """Check if an agent is within recovery rate limits."""
        now = time.time()
        attempts = self._recovery_tracker.get(agent_name, [])

        # Prune old attempts outside cooldown window
        window = self.config.recovery_cooldown_seconds * self.config.max_recovery_attempts
        attempts = [t for t in attempts if now - t < window]
        self._recovery_tracker[agent_name] = attempts

        if len(attempts) >= self.config.max_recovery_attempts:
            return False

        # Check minimum cooldown between attempts
        if attempts and now - attempts[-1] < self.config.recovery_cooldown_seconds:
            return False

        return True

    def _record_recovery(self, agent_name: str) -> None:
        """Record a recovery attempt timestamp."""
        if agent_name not in self._recovery_tracker:
            self._recovery_tracker[agent_name] = []
        self._recovery_tracker[agent_name].append(time.time())

    # ─── Reputation Sync ──────────────────────────────────────────

    def sync_reputation(self) -> dict:
        """Synchronize reputation data for all agents.

        Computes unified reputation from available sources and
        saves a snapshot for the coordinator to use.
        """
        now = datetime.now(timezone.utc)

        # Compute swarm reputation
        # compute_swarm_reputation expects dict[str, dict[str, Any]]
        agents_data = {}
        for agent in self.agents:
            agents_data[agent.agent_name] = {
                "state": agent.state.value,
                "total_successes": agent.total_successes,
                "total_failures": agent.total_failures,
                "usdc_balance": agent.usdc_balance,
            }
        reputations = compute_swarm_reputation(agents_data)

        if reputations:
            self.reputation_dir.mkdir(parents=True, exist_ok=True)
            save_reputation_snapshot(reputations, self.reputation_dir)
            logger.info(f"Reputation sync: {len(reputations)} agents scored")
        else:
            logger.info("Reputation sync: no data available yet")

        self.state.last_reputation_sync_at = now.isoformat()

        return {
            "agents_scored": len(reputations),
            "timestamp": now.isoformat(),
        }

    # ─── Main Coordination Cycle ──────────────────────────────────

    async def run_cycle(self) -> CycleResult:
        """Execute one complete orchestration cycle.

        A cycle consists of:
        1. Health check (if due)
        2. Self-healing (recover failed agents)
        3. Reputation sync (if due)
        4. Coordination (task matching + assignment)
        5. State persistence
        """
        cycle_start = time.time()
        now = datetime.now(timezone.utc)
        self.state.total_cycles += 1
        cycle_num = self.state.total_cycles

        result = CycleResult(
            cycle_number=cycle_num,
            phase=self.state.phase.value,
            started_at=now.isoformat(),
            finished_at="",
            duration_ms=0,
        )

        logger.info(f"─── Cycle {cycle_num} ───")

        try:
            # Step 1: Health check (if due)
            if self._is_due("health_check", self.config.health_check_interval_seconds):
                health = self.run_health_check()
                result.health_checks_run = 1
                result.actions_taken.append(f"health_check: {health.get('online', 0)} online")

            # Step 2: Self-healing
            recovered = self.attempt_recovery()
            result.agents_recovered = len(recovered)
            if recovered:
                result.actions_taken.append(f"recovered: {', '.join(recovered)}")

            # Step 3: Reputation sync (if due)
            if self._is_due("reputation_sync", self.config.reputation_sync_interval_seconds):
                rep_result = self.sync_reputation()
                result.actions_taken.append(
                    f"reputation_sync: {rep_result['agents_scored']} agents"
                )

            # Step 4: Coordination
            # In production this would call CoordinatorService.run_cycle()
            # For now, we track the available agents and run the lifecycle
            available = get_available_agents(self.agents)
            result.tasks_found = 0  # Would come from EM API
            result.tasks_assigned = 0  # Would come from coordinator

            # Determine matching mode
            if self.config.use_legacy_matching:
                result.matching_mode = "legacy"
            elif self.config.autojob_enabled:
                result.matching_mode = "autojob"
            else:
                result.matching_mode = "enhanced"

            # Step 5: Recommended actions (informational)
            actions = recommend_actions(self.agents, self.lifecycle_config, now)
            if actions:
                critical = [a for a in actions if a["priority"] == "critical"]
                if critical:
                    for a in critical[:3]:
                        result.warnings.append(
                            f"[{a['priority'].upper()}] {a['agent']}: {a['reason']}"
                        )

        except Exception as e:
            logger.error(f"Cycle {cycle_num} error: {e}")
            result.errors.append(str(e))
            self.state.total_errors += 1

        # Finalize cycle
        cycle_end = time.time()
        result.duration_ms = (cycle_end - cycle_start) * 1000
        result.finished_at = datetime.now(timezone.utc).isoformat()

        self.state.last_cycle_at = result.finished_at
        self.state.total_tasks_assigned += result.tasks_assigned

        # Add to history (bounded)
        self.state.cycle_history.append(result)
        if len(self.state.cycle_history) > self.config.max_cycle_history:
            self.state.cycle_history = self.state.cycle_history[
                -self.config.max_cycle_history:
            ]

        # Persist state
        self.save_state()

        logger.info(
            f"Cycle {cycle_num} complete: "
            f"{result.duration_ms:.0f}ms, "
            f"recovered={result.agents_recovered}, "
            f"errors={len(result.errors)}"
        )

        return result

    def _is_due(self, check_type: str, interval_seconds: int) -> bool:
        """Check if a periodic action is due based on last execution time."""
        now = datetime.now(timezone.utc)

        if check_type == "health_check":
            last = self.state.last_health_check_at
        elif check_type == "reputation_sync":
            last = self.state.last_reputation_sync_at
        else:
            return True

        if not last:
            return True

        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            return (now - last_dt).total_seconds() >= interval_seconds
        except (ValueError, TypeError):
            return True

    # ─── Shutdown ──────────────────────────────────────────────────

    async def shutdown(self) -> int:
        """Gracefully shut down the swarm.

        Drains active tasks, transitions agents to OFFLINE, saves state.
        Returns number of agents shut down.
        """
        self.state.phase = OrchestratorPhase.DRAINING
        logger.info("Initiating graceful shutdown...")

        now = datetime.now(timezone.utc)
        stopped = 0

        # Phase 1: Signal all working agents to drain
        working_agents = [
            a for a in self.agents
            if a.state == AgentState.WORKING
        ]
        if working_agents:
            logger.info(f"Draining {len(working_agents)} working agents...")
            for agent in working_agents:
                try:
                    transition(
                        agent, AgentState.DRAINING,
                        TransitionReason.MANUAL_STOP, now,
                    )
                except Exception:
                    pass

            # Wait for drain (with timeout)
            drain_start = time.time()
            while time.time() - drain_start < self.config.drain_timeout_seconds:
                still_draining = [
                    a for a in self.agents
                    if a.state == AgentState.DRAINING
                ]
                if not still_draining:
                    break
                await asyncio.sleep(1)

        # Phase 2: Stop all agents
        self.state.phase = OrchestratorPhase.STOPPING
        for agent in self.agents:
            if agent.state == AgentState.OFFLINE:
                continue
            try:
                # Route through valid transitions to reach OFFLINE
                if agent.state == AgentState.DRAINING:
                    transition(agent, TransitionReason.DRAIN_COMPLETE, now=now)
                elif agent.state == AgentState.STOPPING:
                    pass  # Already stopping
                elif agent.state == AgentState.ERROR:
                    transition(agent, TransitionReason.RECOVERY, now=now)
                    transition(agent, TransitionReason.STARTUP, now=now)
                    transition(agent, TransitionReason.MANUAL_STOP, now=now)
                elif agent.state == AgentState.COOLDOWN:
                    transition(agent, TransitionReason.MANUAL_STOP, now=now)
                elif agent.state in (AgentState.IDLE, AgentState.STARTING):
                    transition(agent, TransitionReason.MANUAL_STOP, now=now)
                elif agent.state == AgentState.WORKING:
                    transition(agent, TransitionReason.MANUAL_STOP, now=now)
                    transition(agent, TransitionReason.DRAIN_COMPLETE, now=now)
                else:
                    # Unknown state — force to stopping
                    transition(agent, TransitionReason.MANUAL_STOP, now=now)

                # Final transition to OFFLINE
                if agent.state == AgentState.STOPPING:
                    transition(agent, TransitionReason.MANUAL_STOP, now=now)
                stopped += 1
            except Exception as e:
                logger.error(f"Failed to stop {agent.agent_name}: {e}")

        self.state.phase = OrchestratorPhase.STOPPED
        self.save_state()

        logger.info(f"Shutdown complete: {stopped} agents stopped")
        return stopped

    # ─── Main Loop ────────────────────────────────────────────────

    async def run(self, once: bool = False) -> None:
        """Main orchestrator loop.

        Args:
            once: If True, run a single cycle then exit.
        """
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda: self._request_shutdown()
                )
            except (NotImplementedError, OSError):
                # Windows doesn't support add_signal_handler
                pass

        # Load state
        self.load_state()

        # Startup
        started = await self.startup()
        if started == 0:
            logger.error("No agents started, aborting")
            return

        # Main loop
        logger.info(
            f"Entering main loop (interval={self.config.cycle_interval_seconds}s, "
            f"autojob={self.config.autojob_enabled})"
        )

        try:
            while not self._shutdown_requested:
                result = await self.run_cycle()

                if once:
                    logger.info("Single cycle mode — exiting")
                    break

                # Sleep until next cycle (interruptible)
                try:
                    await asyncio.wait_for(
                        self._wait_for_shutdown(),
                        timeout=self.config.cycle_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    pass  # Normal — timeout means time for next cycle

        except asyncio.CancelledError:
            logger.info("Orchestrator cancelled")
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            self.state.phase = OrchestratorPhase.ERROR
            self.save_state()
            raise
        finally:
            if not once:
                await self.shutdown()

    def _request_shutdown(self) -> None:
        """Signal the main loop to shut down."""
        logger.info("Shutdown requested")
        self._shutdown_requested = True

    async def _wait_for_shutdown(self) -> None:
        """Wait indefinitely (until cancelled or shutdown requested)."""
        while not self._shutdown_requested:
            await asyncio.sleep(0.5)

    # ─── Helpers ──────────────────────────────────────────────────

    def _find_agent(self, name: str) -> Optional[AgentLifecycle]:
        """Find an agent by name."""
        for agent in self.agents:
            if agent.agent_name == name:
                return agent
        return None

    def get_status(self) -> dict:
        """Get current orchestrator status as a dict."""
        now = datetime.now(timezone.utc)
        health = assess_swarm_health(self.agents, self.lifecycle_config, now)

        return {
            "orchestrator": self.state.to_dict(),
            "config": self.config.to_dict(),
            "swarm_health": {
                "total_agents": health.total_agents,
                "online": health.online_agents,
                "idle": health.idle_agents,
                "working": health.working_agents,
                "error": health.error_agents,
                "availability": health.availability_ratio,
                "success_rate": health.success_ratio,
            },
            "agents": [
                {
                    "name": a.agent_name,
                    "type": a.agent_type.value,
                    "state": a.state.value,
                    "failures": a.consecutive_failures,
                    "task": a.current_task_id,
                }
                for a in self.agents
            ],
        }


# ═══════════════════════════════════════════════════════════════════
# Status Display (CLI)
# ═══════════════════════════════════════════════════════════════════


def display_status(agents: list[AgentLifecycle], config: LifecycleConfig) -> None:
    """Display current swarm status in a human-readable format."""
    now = datetime.now(timezone.utc)
    health = assess_swarm_health(agents, config, now)

    print(f"\n{'=' * 70}")
    print(f"  🐝 Karma Kadabra V2 — Swarm Status")
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'=' * 70}")
    print(f"\n  Agents: {health.total_agents} total")
    print(f"    🟢 Online: {health.online_agents} "
          f"(idle: {health.idle_agents}, working: {health.working_agents})")
    print(f"    ⏸️  Cooldown: {health.cooldown_agents}")
    print(f"    🔴 Error: {health.error_agents}")
    print(f"    ⬛ Offline: {health.offline_agents}")
    print(f"    🔄 Starting: {health.starting_agents}")
    print(f"\n  Availability: {health.availability_ratio:.0%}")
    print(f"  Success Rate: {health.success_ratio:.0%} "
          f"({health.total_successes} ✅ / {health.total_failures} ❌)")
    if health.agents_with_low_balance > 0:
        print(f"  ⚠️  Low Balance: {health.agents_with_low_balance} agents")
    if health.agents_with_stale_heartbeat > 0:
        print(f"  ⚠️  Stale Heartbeat: {health.agents_with_stale_heartbeat} agents")

    # Per-agent status
    print(f"\n  {'Agent':<25} {'State':<12} {'Failures':<10} {'Task'}")
    print(f"  {'-' * 65}")
    for agent in sorted(agents, key=lambda a: (a.agent_type.value, a.agent_name)):
        state_icon = {
            AgentState.IDLE: "🟢",
            AgentState.WORKING: "🔵",
            AgentState.COOLDOWN: "⏸️ ",
            AgentState.ERROR: "🔴",
            AgentState.OFFLINE: "⬛",
            AgentState.STARTING: "🔄",
            AgentState.STOPPING: "🛑",
            AgentState.DRAINING: "💧",
        }.get(agent.state, "❓")

        task = agent.current_task_id[:15] if agent.current_task_id else "-"
        failures = f"{agent.consecutive_failures}/{agent.total_failures}"
        print(f"  {state_icon} {agent.agent_name:<23} {agent.state.value:<12} {failures:<10} {task}")

    # Recommended actions
    actions = recommend_actions(agents, config, now)
    if actions:
        print(f"\n  📋 Recommended Actions:")
        for action in actions[:5]:
            icon = {"critical": "🚨", "high": "⚠️", "medium": "📌", "low": "💡"}.get(
                action["priority"], ""
            )
            print(f"    {icon} [{action['priority'].upper()}] {action['agent']}: {action['reason']}")

    print(f"\n{'=' * 70}\n")


def display_leaderboard(data_dir: Path) -> None:
    """Display the reputation leaderboard."""
    rep_dir = data_dir / "reputation"
    snapshot = load_latest_snapshot(rep_dir)

    if not snapshot:
        print("\n  No reputation data available yet.")
        print("  Run a coordination cycle to generate reputation snapshots.\n")
        return

    reps = {}
    for name, data in snapshot.items():
        rep = UnifiedReputation(
            agent_name=name,
            composite_score=data.get("composite_score", 50.0),
            effective_confidence=data.get("confidence", 0.0),
            on_chain_score=data.get("layers", {}).get("on_chain", {}).get("score", 50.0),
            off_chain_score=data.get("layers", {}).get("off_chain", {}).get("score", 50.0),
            transactional_score=data.get("layers", {}).get("transactional", {}).get("score", 50.0),
            sources_available=data.get("sources_available", []),
        )
        rep.tier = classify_tier(rep.composite_score)
        reps[name] = rep

    lb = generate_leaderboard(reps)
    text = format_leaderboard_text(lb)
    print(f"\n{text}\n")


# ═══════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════


async def main():
    parser = argparse.ArgumentParser(description="KK V2 Swarm Orchestrator")
    parser.add_argument("--status", action="store_true", help="Show current swarm status")
    parser.add_argument("--health", action="store_true", help="Generate health report")
    parser.add_argument("--leaderboard", action="store_true", help="Show reputation leaderboard")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--once", action="store_true", help="Run single cycle then exit")
    parser.add_argument("--interval", type=int, default=60, help="Cycle interval (seconds)")
    parser.add_argument("--autojob", action="store_true", help="Enable AutoJob matching")
    parser.add_argument("--autojob-path", type=str, default=None)
    parser.add_argument("--autojob-api", type=str, default=None)
    parser.add_argument("--legacy", action="store_true", help="Use legacy matching")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory path")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    # Quick status/health/leaderboard modes
    if args.status or args.health or args.leaderboard:
        lifecycle_path = data_dir / "lifecycle_state.json"
        if lifecycle_path.exists():
            agents = load_lifecycle_state(lifecycle_path)
        else:
            agents = create_agent_roster(AGENT_REGISTRY)

        if args.status:
            display_status(agents, LifecycleConfig())
        elif args.leaderboard:
            display_leaderboard(data_dir)
        elif args.health:
            now = datetime.now(timezone.utc)
            snapshots = []
            for agent in agents:
                snap = assess_agent_health(
                    agent_name=agent.agent_name,
                    last_heartbeat=agent.last_heartbeat or None,
                    active_task_id=agent.current_task_id or None,
                    tasks_completed_24h=agent.total_successes,
                    tasks_failed_24h=agent.total_failures,
                    balance_usdc=agent.usdc_balance,
                    balance_eth=agent.eth_balance,
                    now=now,
                )
                snapshots.append(snap)
            metrics = compute_swarm_metrics(snapshots, now=now)
            report = generate_health_report(snapshots, metrics)
            report_dir = data_dir / "reports"
            path = save_health_report(report, report_dir)
            print(f"\n  Health report saved to: {path}")
            print(f"  Summary: {json.dumps(report['summary'], indent=2)}\n")
        return

    # Full orchestrator mode
    config = OrchestratorConfig(
        cycle_interval_seconds=args.interval,
        autojob_enabled=args.autojob,
        autojob_path=args.autojob_path,
        autojob_api=args.autojob_api,
        use_legacy_matching=args.legacy,
        dry_run=args.dry_run,
    )

    orchestrator = SwarmOrchestrator(data_dir=data_dir, config=config)

    print(f"\n{'=' * 70}")
    print(f"  🐝 Karma Kadabra V2 — Swarm Orchestrator")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    if args.once:
        print(f"  Run: SINGLE CYCLE")
    print(f"  Interval: {args.interval}s")
    matching = "autojob" if args.autojob else ("legacy" if args.legacy else "enhanced")
    print(f"  Matching: {matching}")
    print(f"{'=' * 70}\n")

    await orchestrator.run(once=args.once)


if __name__ == "__main__":
    asyncio.run(main())
