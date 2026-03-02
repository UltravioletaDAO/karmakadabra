"""
Karma Kadabra V2 — Swarm Brain (Unified Orchestrator)

The capstone integration layer that ties ALL subsystems into a single
coherent coordination system. This is the "brain" of the KK swarm.

Subsystems integrated:
  1. Agent Lifecycle  — State machine, startup, shutdown, circuit breakers
  2. Reputation Bridge — Tri-layer reputation scoring across chains
  3. Decision Engine   — Multi-factor task-agent matching with explainability
  4. Task Pipeline     — End-to-end task lifecycle (14 stages)
  5. Swarm Monitor     — Real-time alerting and health assessment
  6. Swarm Analytics   — Efficiency analysis, bottleneck detection, trends
  7. AutoJob Bridge    — External intelligence, skill DNA matching

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                        SWARM BRAIN                              │
    │                                                                 │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
    │  │ Lifecycle │  │ Decision │  │ Pipeline │  │ Monitor  │       │
    │  │ Manager  │→ │ Engine   │→ │ Service  │→ │ Service  │       │
    │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
    │       ↑              ↑             ↑             ↑             │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
    │  │Reputation│  │ AutoJob  │  │Analytics │                     │
    │  │ Bridge   │  │ Bridge   │  │ Engine   │                     │
    │  └──────────┘  └──────────┘  └──────────┘                     │
    └─────────────────────────────────────────────────────────────────┘

Main loop (one coordination cycle):
  1. HEALTH CHECK   — Monitor probes all subsystems, generates alerts
  2. SELF-HEAL      — Respond to critical alerts (restart agents, reassign tasks)
  3. DISCOVERY      — Fetch new tasks from EM marketplace
  4. MATCHING       — Decision engine ranks agents for each task
  5. ASSIGNMENT     — Feed matched tasks through pipeline
  6. PROGRESS CHECK — Monitor in-progress tasks (heartbeats, SLAs)
  7. COMPLETION     — Process submitted evidence, approve, pay, rate
  8. ANALYTICS      — Update efficiency scores, detect bottlenecks
  9. PERSISTENCE    — Save full system state

The brain runs N cycles per hour (configurable), with each cycle
taking 30-120 seconds depending on swarm size and task volume.

All coordination logic is pure (no side effects) except for:
  - EM API calls (discovery, approval, payment)
  - IRC notifications (status messages)
  - File I/O (state persistence)

Usage:
    brain = SwarmBrain(config)
    brain.initialize()
    cycle_result = brain.run_cycle()
    print(cycle_result.summary())

    # Or continuous:
    brain.run_forever(interval_seconds=120)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import sys
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
from lib.reputation_bridge import (
    UnifiedReputation,
    compute_swarm_reputation,
    format_leaderboard_text,
    generate_leaderboard,
    load_latest_snapshot,
    save_reputation_snapshot,
)
from lib.decision_engine import (
    AgentProfile,
    Decision,
    DecisionConfig,
    DecisionContext,
    DecisionEngine,
    OptimizationMode,
    ScoredAgent,
    TaskProfile,
)
from lib.swarm_analytics import (
    AgentEfficiency,
    CapacityForecast,
    StageBottleneck,
    TrendAnalysis as AnalyticsTrend,
    compute_agent_efficiency,
    detect_bottlenecks,
    forecast_capacity,
)
from services.task_pipeline import (
    PipelineEvent,
    PipelineStage,
    PipelineState,
    PipelineTask,
    TaskEvidence,
    TransitionError,
    execute_transition,
    AgentRanking,
)
from services.swarm_monitor import (
    AgentHealthSnapshot,
    Alert,
    AlertCategory,
    AlertLevel,
    MonitorConfig,
    MonitorStatus,
    PipelineSnapshot,
    StatusDigest,
    SwarmMonitor,
    SystemSnapshot,
    save_monitor_state,
)

logger = logging.getLogger("kk.brain")


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BrainConfig:
    """Top-level configuration for the swarm brain."""
    # Cycle timing
    cycle_interval_seconds: float = 120.0     # Time between cycles
    max_tasks_per_cycle: int = 10             # Max new tasks to process per cycle
    max_assignments_per_cycle: int = 5        # Max new assignments per cycle

    # Self-healing
    auto_restart_agents: bool = True          # Restart failed agents automatically
    auto_reassign_stuck: bool = True          # Reassign tasks past SLA
    max_auto_restarts_per_cycle: int = 3      # Don't restart too many at once
    stuck_task_threshold_hours: float = 6.0   # Hours before considering a task stuck

    # Analytics
    analytics_every_n_cycles: int = 5         # Run full analytics every N cycles
    leaderboard_every_n_cycles: int = 10      # Publish leaderboard every N cycles

    # Decision engine
    optimization_mode: OptimizationMode = OptimizationMode.BALANCED
    cold_start_friendly: bool = True          # Give new agents a chance

    # Pipeline
    max_offer_attempts: int = 3               # Max agents to try before giving up
    offer_timeout_minutes: float = 10.0       # Time to wait for agent to accept

    # Persistence
    state_dir: str = "data/brain"             # Where to save state
    save_every_n_cycles: int = 1              # Save state every N cycles

    # Sub-component configs
    lifecycle_config: LifecycleConfig = field(default_factory=LifecycleConfig)
    decision_config: DecisionConfig = field(default_factory=DecisionConfig)
    monitor_config: MonitorConfig = field(default_factory=MonitorConfig)


class CyclePhase(Enum):
    """Phases within a coordination cycle."""
    HEALTH_CHECK = "health_check"
    SELF_HEAL = "self_heal"
    DISCOVERY = "discovery"
    MATCHING = "matching"
    ASSIGNMENT = "assignment"
    PROGRESS_CHECK = "progress_check"
    COMPLETION = "completion"
    ANALYTICS = "analytics"
    PERSISTENCE = "persistence"


# ═══════════════════════════════════════════════════════════════════
# Cycle Results
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PhaseResult:
    """Result of one phase within a cycle."""
    phase: CyclePhase
    success: bool = True
    duration_ms: float = 0.0
    items_processed: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "success": self.success,
            "duration_ms": round(self.duration_ms, 1),
            "items_processed": self.items_processed,
            "details": self.details,
            "errors": self.errors,
        }


@dataclass
class CycleResult:
    """Complete result of one coordination cycle."""
    cycle_number: int
    started_at: str
    completed_at: str = ""
    total_duration_ms: float = 0.0

    # Phase results
    phases: list[PhaseResult] = field(default_factory=list)

    # Summary metrics
    tasks_discovered: int = 0
    tasks_matched: int = 0
    tasks_assigned: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    agents_restarted: int = 0
    tasks_reassigned: int = 0

    # Health
    swarm_status: str = "unknown"
    alerts_generated: int = 0
    critical_alerts: int = 0

    # Decisions made
    decisions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_number": self.cycle_number,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "phases": [p.to_dict() for p in self.phases],
            "summary": {
                "tasks_discovered": self.tasks_discovered,
                "tasks_matched": self.tasks_matched,
                "tasks_assigned": self.tasks_assigned,
                "tasks_completed": self.tasks_completed,
                "tasks_failed": self.tasks_failed,
                "agents_restarted": self.agents_restarted,
                "tasks_reassigned": self.tasks_reassigned,
            },
            "swarm_status": self.swarm_status,
            "alerts_generated": self.alerts_generated,
            "critical_alerts": self.critical_alerts,
            "decisions": self.decisions[:10],
        }

    def summary(self) -> str:
        """Human-readable cycle summary for IRC/Telegram."""
        status_icons = {
            "healthy": "🟢", "degraded": "🟡",
            "impaired": "🟠", "down": "🔴", "unknown": "❓",
        }
        icon = status_icons.get(self.swarm_status, "❓")

        lines = [
            f"{icon} Ciclo #{self.cycle_number} — {self.total_duration_ms:.0f}ms",
            f"   Estado: {self.swarm_status.upper()}",
        ]

        # Activity
        activity = []
        if self.tasks_discovered > 0:
            activity.append(f"📡 {self.tasks_discovered} descubiertas")
        if self.tasks_assigned > 0:
            activity.append(f"🎯 {self.tasks_assigned} asignadas")
        if self.tasks_completed > 0:
            activity.append(f"✅ {self.tasks_completed} completadas")
        if self.tasks_failed > 0:
            activity.append(f"❌ {self.tasks_failed} fallidas")
        if activity:
            lines.append(f"   Tareas: {', '.join(activity)}")

        # Self-healing
        healing = []
        if self.agents_restarted > 0:
            healing.append(f"🔄 {self.agents_restarted} agentes reiniciados")
        if self.tasks_reassigned > 0:
            healing.append(f"🔀 {self.tasks_reassigned} reasignadas")
        if healing:
            lines.append(f"   Auto-sanación: {', '.join(healing)}")

        # Alerts
        if self.critical_alerts > 0:
            lines.append(f"   🚨 {self.critical_alerts} alertas críticas")

        # Phase timing
        slowest = max(self.phases, key=lambda p: p.duration_ms) if self.phases else None
        if slowest and slowest.duration_ms > 100:
            lines.append(
                f"   ⏱️ Fase más lenta: {slowest.phase.value} ({slowest.duration_ms:.0f}ms)"
            )

        return "\n".join(lines)

    def summary_oneline(self) -> str:
        """Single-line summary for logs."""
        return (
            f"Cycle #{self.cycle_number}: {self.swarm_status} | "
            f"+{self.tasks_discovered}d/{self.tasks_assigned}a/"
            f"{self.tasks_completed}c/{self.tasks_failed}f | "
            f"{self.total_duration_ms:.0f}ms | "
            f"{self.alerts_generated} alerts"
        )


# ═══════════════════════════════════════════════════════════════════
# Helper: Build Agent Profiles for Decision Engine
# ═══════════════════════════════════════════════════════════════════

def build_agent_profile(
    agent: AgentLifecycle,
    reputation: UnifiedReputation | None = None,
    efficiency: AgentEfficiency | None = None,
    pipeline: PipelineState | None = None,
) -> AgentProfile:
    """Build a DecisionEngine AgentProfile from lifecycle + reputation + efficiency data.

    This is the bridge between the lifecycle layer and the decision layer.
    It unifies data from multiple subsystems into the format the engine expects.
    """
    # Count active tasks from pipeline
    active_count = 0
    if pipeline:
        active_count = len(pipeline.agent_active_tasks(agent.agent_name))

    # Determine availability
    is_available = (
        agent.state in (AgentState.IDLE, AgentState.WORKING)
        and not agent.state == AgentState.COOLDOWN
        and not agent.state == AgentState.ERROR
        and not agent.state == AgentState.OFFLINE
    )

    profile = AgentProfile(
        agent_name=agent.agent_name,
        agent_id=getattr(agent, "agent_id", 0),
        is_available=is_available,
        current_tasks=active_count,
        is_idle=(agent.state == AgentState.IDLE),
        consecutive_failures=agent.consecutive_failures,
        in_cooldown=(agent.state == AgentState.COOLDOWN),
        in_error=(agent.state == AgentState.ERROR),
    )

    # Merge reputation data
    if reputation:
        profile.reputation_score = reputation.composite_score
        profile.reputation_confidence = reputation.effective_confidence
        profile.reputation_tier = getattr(reputation, "tier", "Plata")
        if hasattr(reputation.tier, "value"):
            profile.reputation_tier = reputation.tier.value

    # Merge efficiency data
    if efficiency:
        profile.efficiency_score = efficiency.efficiency_score
        profile.avg_completion_hours = efficiency.avg_completion_hours
        profile.reliability = efficiency.reliability
        profile.throughput_per_day = efficiency.throughput_per_day
        profile.earnings_per_hour = efficiency.earnings_per_hour
        profile.tasks_completed = efficiency.tasks_completed
        profile.total_earned_usd = efficiency.total_earned_usd

    # Last task timestamp
    if agent.last_heartbeat:
        profile.last_task_completed_at = agent.last_heartbeat.isoformat()

    return profile


def build_task_profile(task: PipelineTask) -> TaskProfile:
    """Build a DecisionEngine TaskProfile from a PipelineTask.

    Bridges the pipeline layer to the decision layer.
    """
    # Infer complexity from bounty
    complexity = "medium"
    if task.bounty_usd < 0.50:
        complexity = "low"
    elif task.bounty_usd > 5.0:
        complexity = "high"
    elif task.bounty_usd > 20.0:
        complexity = "critical"

    return TaskProfile(
        task_id=task.task_id,
        category=task.category,
        bounty_usd=task.bounty_usd,
        complexity=complexity,
        required_chain=task.payment_network,
        evidence_types=[e.evidence_type for e in task.evidence],
    )


# ═══════════════════════════════════════════════════════════════════
# Helper: Build Monitor Snapshots
# ═══════════════════════════════════════════════════════════════════

def build_agent_health_snapshot(
    agent: AgentLifecycle,
    reputation: UnifiedReputation | None = None,
    efficiency: AgentEfficiency | None = None,
    now: datetime | None = None,
) -> AgentHealthSnapshot:
    """Build a monitor AgentHealthSnapshot from lifecycle data."""
    if now is None:
        now = datetime.now(timezone.utc)

    hb_age = -1.0
    if agent.last_heartbeat:
        hb_age = (now - agent.last_heartbeat).total_seconds()

    return AgentHealthSnapshot(
        agent_name=agent.agent_name,
        is_online=agent.state in (AgentState.IDLE, AgentState.WORKING, AgentState.STARTING),
        state=agent.state.value,
        consecutive_failures=agent.consecutive_failures,
        total_failures=agent.total_failures,
        total_successes=agent.total_successes,
        current_tasks=1 if agent.current_task_id else 0,
        last_heartbeat_age_seconds=hb_age,
        usdc_balance=agent.usdc_balance,
        eth_balance=agent.eth_balance,
        reputation_score=reputation.composite_score if reputation else 50.0,
        efficiency_score=efficiency.efficiency_score if efficiency else 50.0,
    )


def build_pipeline_snapshot(pipeline: PipelineState) -> PipelineSnapshot:
    """Build a monitor PipelineSnapshot from pipeline state."""
    by_stage: dict[str, int] = {}
    stuck = 0
    oldest_hours = 0.0
    now = datetime.now(timezone.utc)

    for task in pipeline.tasks.values():
        stage_name = task.stage.value.upper()
        by_stage[stage_name] = by_stage.get(stage_name, 0) + 1

        # Check for stuck tasks
        if task.stage_entered_at:
            try:
                entered = datetime.fromisoformat(task.stage_entered_at)
                age_hours = (now - entered).total_seconds() / 3600
                if age_hours > oldest_hours:
                    oldest_hours = age_hours
                # Simple SLA check: > 6 hours in non-terminal stage
                terminal = {PipelineStage.COMPLETED, PipelineStage.FAILED, PipelineStage.EXPIRED}
                if task.stage not in terminal and age_hours > 6:
                    stuck += 1
            except (ValueError, TypeError):
                pass

    total_recent = pipeline.total_completed + pipeline.total_failed
    completion_rate = pipeline.total_completed / max(total_recent, 1)
    failure_rate = pipeline.total_failed / max(total_recent, 1)

    return PipelineSnapshot(
        total_tasks=len(pipeline.active_tasks()),
        by_stage=by_stage,
        stuck_tasks=stuck,
        completion_rate_24h=completion_rate,
        failure_rate_24h=failure_rate,
        oldest_task_hours=oldest_hours,
    )


# ═══════════════════════════════════════════════════════════════════
# The Swarm Brain
# ═══════════════════════════════════════════════════════════════════

class SwarmBrain:
    """Unified orchestrator that coordinates all KK V2 subsystems.

    This is the top-level entry point for running the swarm.
    It maintains references to all subsystems and orchestrates
    their interaction through coordination cycles.
    """

    def __init__(
        self,
        config: BrainConfig | None = None,
        agents: list[AgentLifecycle] | None = None,
        pipeline: PipelineState | None = None,
        # Dependency injection for testing
        task_fetcher: Callable[[], list[dict[str, Any]]] | None = None,
        notifier: Callable[[str], None] | None = None,
    ):
        self.config = config or BrainConfig()

        # Core state
        self.agents: list[AgentLifecycle] = agents or []
        self.pipeline: PipelineState = pipeline or PipelineState()

        # Subsystems
        self.decision_engine = DecisionEngine(self.config.decision_config)
        self.monitor = SwarmMonitor(self.config.monitor_config)

        # Derived data (rebuilt each cycle)
        self.reputations: dict[str, UnifiedReputation] = {}
        self.efficiencies: dict[str, AgentEfficiency] = {}

        # Pluggable I/O (for testing)
        self._fetch_tasks = task_fetcher or (lambda: [])
        self._notify = notifier or (lambda msg: logger.info(f"[NOTIFY] {msg}"))

        # Cycle tracking
        self.cycle_count: int = 0
        self.last_cycle_at: Optional[datetime] = None
        self.cycle_history: list[CycleResult] = []

        # Performance tracking
        self._decisions_log: list[dict[str, Any]] = []
        self._outcomes_log: list[dict[str, Any]] = []

    # ───────────────────────────────────────────────────────────────
    # Initialization
    # ───────────────────────────────────────────────────────────────

    def initialize(
        self,
        agent_registry: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Initialize the swarm brain with agent roster.

        Creates agents from registry if none loaded, plans startup order,
        and boots subsystems.

        Returns initialization report.
        """
        now = datetime.now(timezone.utc)

        # Create roster if needed
        if not self.agents and agent_registry:
            self.agents = create_agent_roster(agent_registry)
            logger.info(f"Created roster with {len(self.agents)} agents")

        # Plan startup
        batches = plan_startup_order(self.agents, self.config.lifecycle_config)

        # Boot agents (transition OFFLINE → STARTING → IDLE)
        booted = 0
        for batch in batches:
            for agent_name in batch:
                agent = self._get_agent(agent_name)
                if agent and agent.state == AgentState.OFFLINE:
                    try:
                        transition(agent, TransitionReason.STARTUP, now=now)
                        transition(agent, TransitionReason.STARTUP, now=now)
                        booted += 1
                    except Exception as e:
                        logger.warning(f"Failed to boot {agent_name}: {e}")

        # Compute initial reputation
        self._refresh_reputations()

        return {
            "agents_total": len(self.agents),
            "agents_booted": booted,
            "startup_batches": len(batches),
            "pipeline_tasks": len(self.pipeline.tasks),
            "initialized_at": now.isoformat(),
        }

    # ───────────────────────────────────────────────────────────────
    # Main Coordination Cycle
    # ───────────────────────────────────────────────────────────────

    def run_cycle(
        self,
        new_tasks: list[dict[str, Any]] | None = None,
        now: datetime | None = None,
    ) -> CycleResult:
        """Execute one full coordination cycle.

        This is the heartbeat of the swarm. Each cycle:
          1. Checks health
          2. Self-heals (restart agents, reassign tasks)
          3. Discovers new tasks
          4. Matches tasks to agents via decision engine
          5. Assigns tasks through the pipeline
          6. Checks progress on active tasks
          7. Processes completions
          8. Runs analytics (periodically)
          9. Saves state

        Args:
            new_tasks: Optional pre-fetched tasks (if None, uses task_fetcher)
            now: Optional override for current time (for testing)

        Returns:
            CycleResult with full details of what happened.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        self.cycle_count += 1
        cycle_start = time.monotonic()

        result = CycleResult(
            cycle_number=self.cycle_count,
            started_at=now.isoformat(),
        )

        # ── Phase 1: Health Check ──
        phase_result = self._phase_health_check(now)
        result.phases.append(phase_result)
        result.swarm_status = phase_result.details.get("status", "unknown")
        result.alerts_generated = phase_result.details.get("alert_count", 0)
        result.critical_alerts = phase_result.details.get("critical_count", 0)

        # ── Phase 2: Self-Heal ──
        phase_result = self._phase_self_heal(now)
        result.phases.append(phase_result)
        result.agents_restarted = phase_result.details.get("agents_restarted", 0)
        result.tasks_reassigned = phase_result.details.get("tasks_reassigned", 0)

        # ── Phase 3: Discovery ──
        phase_result = self._phase_discovery(new_tasks, now)
        result.phases.append(phase_result)
        result.tasks_discovered = phase_result.items_processed

        # ── Phase 4: Matching ──
        phase_result = self._phase_matching(now)
        result.phases.append(phase_result)
        result.tasks_matched = phase_result.items_processed
        result.decisions = phase_result.details.get("decisions", [])

        # ── Phase 5: Assignment ──
        phase_result = self._phase_assignment(now)
        result.phases.append(phase_result)
        result.tasks_assigned = phase_result.items_processed

        # ── Phase 6: Progress Check ──
        phase_result = self._phase_progress_check(now)
        result.phases.append(phase_result)

        # ── Phase 7: Completion ──
        phase_result = self._phase_completion(now)
        result.phases.append(phase_result)
        result.tasks_completed = phase_result.details.get("completed", 0)
        result.tasks_failed = phase_result.details.get("failed", 0)

        # ── Phase 8: Analytics (periodic) ──
        if self.cycle_count % self.config.analytics_every_n_cycles == 0:
            phase_result = self._phase_analytics(now)
            result.phases.append(phase_result)

        # ── Phase 9: Persistence ──
        if self.cycle_count % self.config.save_every_n_cycles == 0:
            phase_result = self._phase_persistence(now)
            result.phases.append(phase_result)

        # Finalize
        cycle_end = time.monotonic()
        result.total_duration_ms = (cycle_end - cycle_start) * 1000
        result.completed_at = datetime.now(timezone.utc).isoformat()

        # Update pipeline timestamp
        self.pipeline.last_cycle_at = now.isoformat()
        self.last_cycle_at = now

        # Store in history
        self.cycle_history.append(result)
        if len(self.cycle_history) > 100:
            self.cycle_history = self.cycle_history[-100:]

        logger.info(result.summary_oneline())
        return result

    # ───────────────────────────────────────────────────────────────
    # Phase Implementations
    # ───────────────────────────────────────────────────────────────

    def _phase_health_check(self, now: datetime) -> PhaseResult:
        """Phase 1: Probe all subsystems and generate alerts."""
        start = time.monotonic()

        # Build snapshots for monitor
        agent_snapshots = [
            build_agent_health_snapshot(
                agent,
                self.reputations.get(agent.agent_name),
                self.efficiencies.get(agent.agent_name),
                now,
            )
            for agent in self.agents
        ]

        pipeline_snapshot = build_pipeline_snapshot(self.pipeline)

        # System health (simplified — in production, these would be real checks)
        system_snapshot = SystemSnapshot(
            em_api_healthy=True,
            base_rpc_healthy=True,
            irc_connected=True,
        )

        # Get current reputation scores for change detection
        rep_scores = {
            name: rep.composite_score
            for name, rep in self.reputations.items()
        }

        # Run all monitor checks
        alerts, digest = self.monitor.run_checks(
            agents=agent_snapshots,
            pipeline=pipeline_snapshot,
            system=system_snapshot,
            current_reputations=rep_scores,
            now=now,
        )

        critical_count = sum(1 for a in alerts if a.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY))

        # Notify on critical alerts
        if critical_count > 0:
            for alert in alerts:
                if alert.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY):
                    self._notify(alert.format_irc())

        return PhaseResult(
            phase=CyclePhase.HEALTH_CHECK,
            success=True,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=len(alerts),
            details={
                "status": digest.status.value,
                "alert_count": len(alerts),
                "critical_count": critical_count,
                "agents_online": digest.agents_online,
                "agents_total": digest.agents_total,
                "tasks_in_pipeline": digest.tasks_in_pipeline,
            },
        )

    def _phase_self_heal(self, now: datetime) -> PhaseResult:
        """Phase 2: Respond to alerts — restart agents, reassign tasks."""
        start = time.monotonic()
        agents_restarted = 0
        tasks_reassigned = 0
        errors = []

        if not self.config.auto_restart_agents and not self.config.auto_reassign_stuck:
            return PhaseResult(
                phase=CyclePhase.SELF_HEAL,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        # Restart failed/error agents
        if self.config.auto_restart_agents:
            for agent in self.agents:
                if agents_restarted >= self.config.max_auto_restarts_per_cycle:
                    break
                if agent.state == AgentState.ERROR:
                    try:
                        # Reset circuit breaker and restart
                        agent.consecutive_failures = 0
                        transition(agent, TransitionReason.RECOVERY, now=now)
                        transition(agent, TransitionReason.STARTUP, now=now)
                        agents_restarted += 1
                        logger.info(f"Auto-restarted agent: {agent.agent_name}")
                    except Exception as e:
                        errors.append(f"Failed to restart {agent.agent_name}: {e}")

        # Reassign stuck tasks
        if self.config.auto_reassign_stuck:
            threshold = timedelta(hours=self.config.stuck_task_threshold_hours)
            for task in self.pipeline.active_tasks():
                if task.stage in (PipelineStage.IN_PROGRESS, PipelineStage.OFFERED):
                    if task.stage_entered_at:
                        try:
                            entered = datetime.fromisoformat(task.stage_entered_at)
                            if (now - entered) > threshold:
                                # Mark as failed and re-discover
                                try:
                                    execute_transition(
                                        task, PipelineStage.FAILED,
                                        actor="brain:self_heal",
                                        details={"reason": "stuck_task_sla_breach"},
                                        now=now,
                                    )
                                    # Re-discover for retry
                                    execute_transition(
                                        task, PipelineStage.DISCOVERED,
                                        actor="brain:self_heal",
                                        details={"reason": "auto_retry"},
                                        now=now,
                                    )
                                    task.retry_count += 1
                                    tasks_reassigned += 1
                                    logger.info(
                                        f"Reassigned stuck task: {task.task_id} "
                                        f"(was assigned to {task.assigned_agent})"
                                    )
                                except TransitionError as e:
                                    errors.append(f"Failed to reassign {task.task_id}: {e}")
                        except (ValueError, TypeError):
                            pass

        return PhaseResult(
            phase=CyclePhase.SELF_HEAL,
            success=len(errors) == 0,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=agents_restarted + tasks_reassigned,
            details={
                "agents_restarted": agents_restarted,
                "tasks_reassigned": tasks_reassigned,
            },
            errors=errors,
        )

    def _phase_discovery(
        self,
        new_tasks: list[dict[str, Any]] | None,
        now: datetime,
    ) -> PhaseResult:
        """Phase 3: Discover new tasks from EM marketplace."""
        start = time.monotonic()
        errors = []

        # Fetch tasks (from injected fetcher or provided list)
        tasks = new_tasks if new_tasks is not None else []
        if new_tasks is None:
            try:
                tasks = self._fetch_tasks()
            except Exception as e:
                errors.append(f"Task fetch failed: {e}")
                tasks = []

        # Limit per cycle
        tasks = tasks[:self.config.max_tasks_per_cycle]

        # Ingest into pipeline
        discovered = 0
        for task_data in tasks:
            task_id = task_data.get("id", task_data.get("task_id", ""))
            if not task_id or task_id in self.pipeline.tasks:
                continue  # Skip duplicates

            pipeline_task = PipelineTask(
                task_id=task_id,
                stage=PipelineStage.DISCOVERED,
                title=task_data.get("title", ""),
                description=task_data.get("description", ""),
                category=task_data.get("category", ""),
                bounty_usd=float(task_data.get("bounty_usd", task_data.get("bounty", 0))),
                payment_network=task_data.get("payment_network", "base"),
                creator_wallet=task_data.get("creator_wallet", ""),
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
                stage_entered_at=now.isoformat(),
                max_offer_attempts=self.config.max_offer_attempts,
            )

            # Add discovery event
            pipeline_task.events.append(PipelineEvent(
                event_id=f"disc-{discovered}",
                task_id=task_id,
                timestamp=now.isoformat(),
                from_stage=None,
                to_stage=PipelineStage.DISCOVERED.value,
                actor="brain:discovery",
                details={"source": "em_marketplace"},
            ))

            self.pipeline.tasks[task_id] = pipeline_task
            self.pipeline.total_discovered += 1
            discovered += 1

        return PhaseResult(
            phase=CyclePhase.DISCOVERY,
            success=len(errors) == 0,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=discovered,
            details={"tasks_fetched": len(tasks), "tasks_ingested": discovered},
            errors=errors,
        )

    def _phase_matching(self, now: datetime) -> PhaseResult:
        """Phase 4: Use decision engine to match tasks to agents."""
        start = time.monotonic()
        errors = []
        decisions_made = []

        # Get tasks needing matching (DISCOVERED stage)
        unmatched = self.pipeline.tasks_in_stage(PipelineStage.DISCOVERED)

        # Refresh reputation and efficiency data
        self._refresh_reputations()
        self._refresh_efficiencies()

        # Build agent profiles
        agent_profiles = [
            build_agent_profile(
                agent,
                self.reputations.get(agent.agent_name),
                self.efficiencies.get(agent.agent_name),
                self.pipeline,
            )
            for agent in self.agents
        ]

        # Match each task
        for task in unmatched[:self.config.max_tasks_per_cycle]:
            task_profile = build_task_profile(task)

            context = DecisionContext(
                task=task_profile,
                agents=agent_profiles,
                timestamp=now,
            )

            try:
                decision = self.decision_engine.decide(context)

                if decision.chosen_agent:
                    # Store rankings on the task
                    task.rankings = [
                        AgentRanking(
                            agent_name=sa.agent.agent_name,
                            score=sa.total_score,
                            match_mode=decision.mode.value,
                            factors=sa.to_dict().get("factors", {}),
                        )
                        for sa in decision.rankings[:5]
                    ]

                    # Transition to EVALUATED
                    execute_transition(
                        task, PipelineStage.EVALUATED,
                        actor="brain:matching",
                        details={
                            "chosen_agent": decision.chosen_agent,
                            "score": decision.chosen_score,
                            "confidence": decision.confidence,
                            "alternatives": decision.alternatives,
                        },
                        now=now,
                    )

                    decisions_made.append(decision.to_dict())

                    # Log for decision quality tracking
                    self._decisions_log.append({
                        "task_id": task.task_id,
                        "chosen_agent": decision.chosen_agent,
                        "confidence": decision.confidence,
                        "risk_level": decision.risk_level,
                        "cycle": self.cycle_count,
                    })
                else:
                    logger.info(f"No suitable agent for task {task.task_id}")

            except Exception as e:
                errors.append(f"Matching failed for {task.task_id}: {e}")

        return PhaseResult(
            phase=CyclePhase.MATCHING,
            success=len(errors) == 0,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=len(decisions_made),
            details={
                "unmatched_count": len(unmatched),
                "decisions": decisions_made,
            },
            errors=errors,
        )

    def _phase_assignment(self, now: datetime) -> PhaseResult:
        """Phase 5: Offer tasks to chosen agents via pipeline."""
        start = time.monotonic()
        errors = []
        assigned = 0

        # Get evaluated tasks ready for assignment
        evaluated = self.pipeline.tasks_in_stage(PipelineStage.EVALUATED)

        for task in evaluated[:self.config.max_assignments_per_cycle]:
            if not task.rankings:
                continue

            # Pick the top-ranked agent
            top_agent_name = task.rankings[0].agent_name
            agent = self._get_agent(top_agent_name)

            if not agent:
                errors.append(f"Agent {top_agent_name} not found for task {task.task_id}")
                continue

            # Check agent is still available
            if agent.state not in (AgentState.IDLE, AgentState.WORKING):
                # Try next alternative
                offered = False
                for ranking in task.rankings[1:]:
                    alt_agent = self._get_agent(ranking.agent_name)
                    if alt_agent and alt_agent.state in (AgentState.IDLE, AgentState.WORKING):
                        top_agent_name = ranking.agent_name
                        agent = alt_agent
                        offered = True
                        break
                if not offered:
                    continue  # No available agent, try next cycle

            try:
                # Offer to agent
                execute_transition(
                    task, PipelineStage.OFFERED,
                    actor="brain:assignment",
                    details={"offered_to": top_agent_name},
                    now=now,
                )
                task.assigned_agent = top_agent_name
                task.offer_attempts += 1

                # Auto-accept (in production, agent would confirm)
                execute_transition(
                    task, PipelineStage.ACCEPTED,
                    actor=top_agent_name,
                    details={"auto_accept": True},
                    now=now,
                )

                # Start work
                execute_transition(
                    task, PipelineStage.IN_PROGRESS,
                    actor=top_agent_name,
                    now=now,
                )
                task.started_at = now.isoformat()

                # Update agent state
                if agent.state == AgentState.IDLE:
                    transition(agent, TransitionReason.TASK_ASSIGNED, now=now)
                agent.current_task_id = task.task_id

                assigned += 1
                logger.info(
                    f"Assigned task {task.task_id} to {top_agent_name} "
                    f"(score: {task.rankings[0].score:.1f})"
                )

            except (TransitionError, Exception) as e:
                errors.append(f"Assignment failed for {task.task_id}: {e}")

        return PhaseResult(
            phase=CyclePhase.ASSIGNMENT,
            success=len(errors) == 0,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=assigned,
            details={"evaluated_count": len(evaluated), "assigned": assigned},
            errors=errors,
        )

    def _phase_progress_check(self, now: datetime) -> PhaseResult:
        """Phase 6: Monitor in-progress tasks for SLA breaches."""
        start = time.monotonic()
        warnings = []

        in_progress = self.pipeline.tasks_in_stage(PipelineStage.IN_PROGRESS)

        for task in in_progress:
            if task.started_at:
                try:
                    started = datetime.fromisoformat(task.started_at)
                    elapsed_hours = (now - started).total_seconds() / 3600

                    # Warning at 50% of threshold
                    warn_threshold = self.config.stuck_task_threshold_hours * 0.5
                    if elapsed_hours > warn_threshold:
                        warnings.append(
                            f"Task {task.task_id} in progress for {elapsed_hours:.1f}h "
                            f"(agent: {task.assigned_agent})"
                        )
                except (ValueError, TypeError):
                    pass

        return PhaseResult(
            phase=CyclePhase.PROGRESS_CHECK,
            success=True,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=len(in_progress),
            details={
                "in_progress_count": len(in_progress),
                "warnings": warnings[:5],
            },
        )

    def _phase_completion(self, now: datetime) -> PhaseResult:
        """Phase 7: Process submitted evidence, approve, pay, rate."""
        start = time.monotonic()
        completed = 0
        failed = 0
        errors = []

        # Process SUBMITTED tasks
        submitted = self.pipeline.tasks_in_stage(PipelineStage.SUBMITTED)
        for task in submitted:
            try:
                # Auto-review (in production, this would validate evidence)
                execute_transition(
                    task, PipelineStage.UNDER_REVIEW,
                    actor="brain:completion",
                    now=now,
                )
            except TransitionError as e:
                errors.append(f"Review transition failed for {task.task_id}: {e}")

        # Process UNDER_REVIEW tasks (auto-approve for now)
        under_review = self.pipeline.tasks_in_stage(PipelineStage.UNDER_REVIEW)
        for task in under_review:
            try:
                if task.evidence:  # Has evidence → approve
                    execute_transition(
                        task, PipelineStage.APPROVED,
                        actor="brain:completion",
                        details={"auto_approved": True},
                        now=now,
                    )
                    task.approved_at = now.isoformat()
                else:  # No evidence → fail
                    execute_transition(
                        task, PipelineStage.FAILED,
                        actor="brain:completion",
                        details={"reason": "no_evidence"},
                        now=now,
                    )
                    task.failure_reason = "no_evidence"
                    failed += 1
            except TransitionError as e:
                errors.append(f"Approval failed for {task.task_id}: {e}")

        # Process APPROVED tasks (mark as paid)
        approved = self.pipeline.tasks_in_stage(PipelineStage.APPROVED)
        for task in approved:
            try:
                execute_transition(
                    task, PipelineStage.PAID,
                    actor="brain:completion",
                    details={"payment_simulated": True},
                    now=now,
                )
                task.paid_at = now.isoformat()
                self.pipeline.total_paid_usd += task.bounty_usd
            except TransitionError as e:
                errors.append(f"Payment failed for {task.task_id}: {e}")

        # Process PAID tasks (rate and complete)
        paid = self.pipeline.tasks_in_stage(PipelineStage.PAID)
        for task in paid:
            try:
                # Auto-rate
                execute_transition(
                    task, PipelineStage.RATED,
                    actor="brain:completion",
                    details={"auto_rated": True},
                    now=now,
                )
                task.agent_rating = 85.0  # Default positive rating
                task.creator_rating = 90.0

                # Complete
                execute_transition(
                    task, PipelineStage.COMPLETED,
                    actor="brain:completion",
                    now=now,
                )
                self.pipeline.total_completed += 1
                completed += 1

                # Update agent state
                if task.assigned_agent:
                    agent = self._get_agent(task.assigned_agent)
                    if agent:
                        agent.total_successes += 1
                        agent.consecutive_failures = 0
                        if agent.current_task_id == task.task_id:
                            agent.current_task_id = None
                        # Check if agent has other tasks
                        remaining = self.pipeline.agent_active_tasks(agent.agent_name)
                        if not remaining and agent.state == AgentState.WORKING:
                            transition(agent, TransitionReason.TASK_COMPLETED, now=now)

                # Log outcome for decision quality tracking
                self._outcomes_log.append({
                    "task_id": task.task_id,
                    "success": True,
                    "rating": task.agent_rating or 0,
                })

                logger.info(f"Task {task.task_id} completed by {task.assigned_agent}")

            except TransitionError as e:
                errors.append(f"Completion failed for {task.task_id}: {e}")

        return PhaseResult(
            phase=CyclePhase.COMPLETION,
            success=len(errors) == 0,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=completed + failed,
            details={
                "completed": completed,
                "failed": failed,
                "submitted_count": len(submitted),
                "review_count": len(under_review),
                "approved_count": len(approved),
                "paid_count": len(paid),
            },
            errors=errors,
        )

    def _phase_analytics(self, now: datetime) -> PhaseResult:
        """Phase 8: Run analytics, detect bottlenecks, update efficiencies."""
        start = time.monotonic()

        # Refresh efficiency data
        self._refresh_efficiencies()

        # Detect bottlenecks
        stage_times: dict[str, list[float]] = {}
        stage_slas: dict[str, float] = {}
        for task in self.pipeline.tasks.values():
            for event in task.events:
                if event.from_stage and event.to_stage:
                    stage = event.from_stage
                    # Calculate time in that stage (approximate)
                    if stage not in stage_times:
                        stage_times[stage] = []
                    stage_times[stage].append(5.0)  # Placeholder minutes

            # SLA defaults
            for stage in PipelineStage:
                stage_slas[stage.value] = 60.0  # 1 hour default

        bottlenecks = detect_bottlenecks(stage_times, stage_slas) if stage_times else []

        # Capacity forecast
        available = get_available_agents(self.agents)
        working_count = sum(1 for a in self.agents if a.state == AgentState.WORKING)
        idle_count = sum(1 for a in self.agents if a.state == AgentState.IDLE)
        offline_count = sum(1 for a in self.agents if a.state == AgentState.OFFLINE)
        capacity = forecast_capacity(
            total_agents=len(self.agents),
            working_agents=working_count,
            idle_agents=idle_count,
            offline_agents=offline_count,
            avg_tasks_per_day=5.0,
            avg_intake_per_day=3.0,
        )

        # Leaderboard (periodic)
        leaderboard_text = ""
        if self.cycle_count % self.config.leaderboard_every_n_cycles == 0 and self.reputations:
            leaderboard = generate_leaderboard(self.reputations)
            leaderboard_text = format_leaderboard_text(leaderboard)
            if leaderboard_text:
                self._notify(leaderboard_text)

        return PhaseResult(
            phase=CyclePhase.ANALYTICS,
            success=True,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=len(self.efficiencies),
            details={
                "bottlenecks": [b.to_dict() for b in bottlenecks[:3]],
                "capacity": capacity.to_dict() if capacity else {},
                "agents_analyzed": len(self.efficiencies),
                "leaderboard_published": bool(leaderboard_text),
            },
        )

    def _phase_persistence(self, now: datetime) -> PhaseResult:
        """Phase 9: Save full system state to disk."""
        start = time.monotonic()
        errors = []

        state_dir = Path(self.config.state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Save lifecycle state
            lifecycle_path = state_dir / "lifecycle_state.json"
            save_lifecycle_state(self.agents, lifecycle_path)
        except Exception as e:
            errors.append(f"Lifecycle save failed: {e}")

        try:
            # Save pipeline state
            pipeline_path = state_dir / "pipeline_state.json"
            pipeline_path.write_text(
                json.dumps(self.pipeline.to_dict(), indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            errors.append(f"Pipeline save failed: {e}")

        try:
            # Save monitor state
            monitor_path = state_dir / "monitor_state.json"
            save_monitor_state(self.monitor, monitor_path)
        except Exception as e:
            errors.append(f"Monitor save failed: {e}")

        try:
            # Save cycle history (last 20)
            history_path = state_dir / "cycle_history.json"
            history_path.write_text(
                json.dumps(
                    [c.to_dict() for c in self.cycle_history[-20:]],
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            errors.append(f"History save failed: {e}")

        return PhaseResult(
            phase=CyclePhase.PERSISTENCE,
            success=len(errors) == 0,
            duration_ms=(time.monotonic() - start) * 1000,
            items_processed=4 - len(errors),
            details={"state_dir": str(state_dir)},
            errors=errors,
        )

    # ───────────────────────────────────────────────────────────────
    # Internal Helpers
    # ───────────────────────────────────────────────────────────────

    def _get_agent(self, name: str) -> AgentLifecycle | None:
        """Find agent by name."""
        for agent in self.agents:
            if agent.agent_name == name:
                return agent
        return None

    def _refresh_reputations(self) -> None:
        """Refresh reputation data for all agents."""
        try:
            # Build minimal reputation from lifecycle data
            # In production, this calls compute_swarm_reputation with real chain data
            for agent in self.agents:
                if agent.agent_name not in self.reputations:
                    total = agent.total_successes + agent.total_failures
                    score = 50.0
                    confidence = 0.0
                    if total > 0:
                        score = (agent.total_successes / total) * 100
                        confidence = min(1.0, total / 20.0)

                    self.reputations[agent.agent_name] = UnifiedReputation(
                        agent_name=agent.agent_name,
                        composite_score=score,
                        effective_confidence=confidence,
                        on_chain_score=score,
                        off_chain_score=score,
                        transactional_score=score,
                        sources_available=["lifecycle"],
                    )
        except Exception as e:
            logger.warning(f"Reputation refresh failed: {e}")

    def _refresh_efficiencies(self) -> None:
        """Refresh efficiency data for all agents."""
        try:
            for agent in self.agents:
                self.efficiencies[agent.agent_name] = compute_agent_efficiency(
                    agent_name=agent.agent_name,
                    tasks_completed=agent.total_successes,
                    tasks_failed=agent.total_failures,
                    total_earned_usd=0.0,  # Would come from payment tracking
                    completion_times_hours=[],  # Would come from pipeline history
                    observation_days=7.0,
                )
        except Exception as e:
            logger.warning(f"Efficiency refresh failed: {e}")

    # ───────────────────────────────────────────────────────────────
    # Public Query API
    # ───────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Current swarm brain status snapshot."""
        now = datetime.now(timezone.utc)
        health = assess_swarm_health(self.agents, self.config.lifecycle_config, now)

        active_tasks = len(self.pipeline.active_tasks())
        completed = self.pipeline.total_completed
        failed = self.pipeline.total_failed

        latest_cycle = self.cycle_history[-1] if self.cycle_history else None

        return {
            "brain_cycle_count": self.cycle_count,
            "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
            "swarm": {
                "total_agents": len(self.agents),
                "online": health.online_agents,
                "idle": health.idle_agents,
                "working": health.working_agents,
                "error": health.error_agents,
                "availability": f"{health.availability_ratio:.0%}",
            },
            "pipeline": {
                "active_tasks": active_tasks,
                "total_completed": completed,
                "total_failed": failed,
                "total_paid_usd": f"${self.pipeline.total_paid_usd:.2f}",
            },
            "latest_cycle": latest_cycle.summary_oneline() if latest_cycle else "No cycles yet",
        }

    def status_text(self) -> str:
        """Human-readable status for IRC/Telegram."""
        s = self.status()
        swarm = s["swarm"]
        pipe = s["pipeline"]

        lines = [
            f"🧠 KK Swarm Brain — Ciclo #{s['brain_cycle_count']}",
            f"   Agentes: {swarm['online']}/{swarm['total_agents']} en línea "
            f"({swarm['idle']} idle, {swarm['working']} trabajando)",
            f"   Pipeline: {pipe['active_tasks']} activas | "
            f"{pipe['total_completed']} completadas | "
            f"{pipe['total_failed']} fallidas",
            f"   Pagado: {pipe['total_paid_usd']}",
        ]

        if s["latest_cycle"] != "No cycles yet":
            lines.append(f"   Último ciclo: {s['latest_cycle']}")

        return "\n".join(lines)

    def get_agent_report(self, agent_name: str) -> dict[str, Any]:
        """Detailed report for a specific agent."""
        agent = self._get_agent(agent_name)
        if not agent:
            return {"error": f"Agent {agent_name} not found"}

        rep = self.reputations.get(agent_name)
        eff = self.efficiencies.get(agent_name)
        active = self.pipeline.agent_active_tasks(agent_name)

        return {
            "agent_name": agent_name,
            "state": agent.state.value,
            "type": agent.agent_type.value,
            "successes": agent.total_successes,
            "failures": agent.total_failures,
            "consecutive_failures": agent.consecutive_failures,
            "reputation": rep.composite_score if rep else 50.0,
            "efficiency": eff.efficiency_score if eff else 50.0,
            "active_tasks": len(active),
            "current_task": agent.current_task_id,
        }

    def get_pipeline_report(self) -> dict[str, Any]:
        """Pipeline status report with stage breakdown."""
        by_stage = {}
        for stage in PipelineStage:
            count = len(self.pipeline.tasks_in_stage(stage))
            if count > 0:
                by_stage[stage.value] = count

        return {
            "total_tasks": len(self.pipeline.tasks),
            "active_tasks": len(self.pipeline.active_tasks()),
            "by_stage": by_stage,
            "total_completed": self.pipeline.total_completed,
            "total_failed": self.pipeline.total_failed,
            "total_paid_usd": self.pipeline.total_paid_usd,
        }

    # ───────────────────────────────────────────────────────────────
    # Persistence: Save / Load
    # ───────────────────────────────────────────────────────────────

    def save(self, state_dir: str | Path | None = None) -> Path:
        """Save complete brain state to disk."""
        path = Path(state_dir) if state_dir else Path(self.config.state_dir)
        path.mkdir(parents=True, exist_ok=True)

        # Save all components
        save_lifecycle_state(self.agents, path / "lifecycle_state.json")

        (path / "pipeline_state.json").write_text(
            json.dumps(self.pipeline.to_dict(), indent=2),
            encoding="utf-8",
        )

        save_monitor_state(self.monitor, path / "monitor_state.json")

        # Save brain metadata
        meta = {
            "cycle_count": self.cycle_count,
            "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "agent_count": len(self.agents),
            "pipeline_tasks": len(self.pipeline.tasks),
        }
        (path / "brain_meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

        return path

    @classmethod
    def load(
        cls,
        state_dir: str | Path,
        config: BrainConfig | None = None,
        **kwargs,
    ) -> "SwarmBrain":
        """Load brain state from disk."""
        path = Path(state_dir)
        cfg = config or BrainConfig(state_dir=str(path))

        # Load lifecycle
        lifecycle_path = path / "lifecycle_state.json"
        agents = load_lifecycle_state(lifecycle_path) if lifecycle_path.exists() else []

        # Load pipeline
        pipeline = PipelineState()
        pipeline_path = path / "pipeline_state.json"
        if pipeline_path.exists():
            try:
                data = json.loads(pipeline_path.read_text(encoding="utf-8"))
                pipeline.total_discovered = data.get("total_discovered", 0)
                pipeline.total_completed = data.get("total_completed", 0)
                pipeline.total_failed = data.get("total_failed", 0)
                pipeline.total_expired = data.get("total_expired", 0)
                pipeline.total_paid_usd = data.get("total_paid_usd", 0.0)
                pipeline.last_cycle_at = data.get("last_cycle_at")
                # Note: task reconstruction would need PipelineTask.from_dict()
            except Exception as e:
                logger.warning(f"Pipeline load failed: {e}")

        # Load brain metadata
        meta_path = path / "brain_meta.json"
        cycle_count = 0
        last_cycle_at = None
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                cycle_count = meta.get("cycle_count", 0)
                lc = meta.get("last_cycle_at")
                if lc:
                    last_cycle_at = datetime.fromisoformat(lc)
            except Exception as e:
                logger.warning(f"Brain meta load failed: {e}")

        brain = cls(config=cfg, agents=agents, pipeline=pipeline, **kwargs)
        brain.cycle_count = cycle_count
        brain.last_cycle_at = last_cycle_at

        return brain
