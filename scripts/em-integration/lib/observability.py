"""
Karma Kadabra V2 — Agent Observability & Metrics

Provides swarm-wide visibility into agent health, task flow, and system performance.
Works standalone with local data; designed to plug into Acontext dashboard when available.

Key metrics tracked:
  - Agent health scores (heartbeat freshness, task completion, error rates)
  - Swarm throughput (tasks/hour, completion rate, earnings velocity)
  - Task flow analytics (discovery → application → assignment → completion funnel)
  - Cross-agent coordination efficiency (IRC message utilization, duplicate work detection)
  - System-level indicators (API health, chain connectivity, balance alerts)

Design principles:
  - Pure functions — no side effects, easily testable
  - Graceful degradation — works with partial data
  - Acontext-ready — outputs structured data compatible with Acontext sessions
  - Time-window aware — metrics computed over configurable windows (1h, 24h, 7d)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.observability")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HealthStatus(Enum):
    """Agent health classification."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class TaskPhase(Enum):
    """Task lifecycle phase for funnel analysis."""
    DISCOVERED = "discovered"
    APPLIED = "applied"
    ASSIGNED = "assigned"
    WORKING = "working"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class AgentHealthSnapshot:
    """Point-in-time health assessment for one agent."""
    agent_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    health_score: float = 0.0  # 0.0-1.0 composite score
    last_heartbeat: str = ""   # ISO timestamp
    heartbeat_age_seconds: int = -1
    active_task: bool = False
    tasks_completed_24h: int = 0
    tasks_failed_24h: int = 0
    errors_24h: int = 0
    balance_ok: bool = True
    irc_connected: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "health_score": round(self.health_score, 3),
            "last_heartbeat": self.last_heartbeat,
            "heartbeat_age_seconds": self.heartbeat_age_seconds,
            "active_task": self.active_task,
            "tasks_completed_24h": self.tasks_completed_24h,
            "tasks_failed_24h": self.tasks_failed_24h,
            "errors_24h": self.errors_24h,
            "balance_ok": self.balance_ok,
            "irc_connected": self.irc_connected,
            "details": self.details,
        }


@dataclass
class SwarmMetrics:
    """Aggregate swarm-level metrics for a time window."""
    window_start: str = ""
    window_end: str = ""
    window_hours: float = 24.0

    # Agent counts
    total_agents: int = 0
    healthy_agents: int = 0
    degraded_agents: int = 0
    offline_agents: int = 0

    # Task throughput
    tasks_discovered: int = 0
    tasks_applied: int = 0
    tasks_assigned: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_expired: int = 0

    # Financial
    total_earned_usd: float = 0.0
    total_spent_usd: float = 0.0
    avg_bounty_usd: float = 0.0

    # Efficiency
    completion_rate: float = 0.0    # completed / (completed + failed + expired)
    apply_to_assign_rate: float = 0.0  # assigned / applied
    assignment_to_complete_rate: float = 0.0  # completed / assigned
    avg_completion_hours: float = 0.0

    # Coordination
    irc_messages_sent: int = 0
    duplicate_applications: int = 0
    coordinator_interventions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": {
                "start": self.window_start,
                "end": self.window_end,
                "hours": self.window_hours,
            },
            "agents": {
                "total": self.total_agents,
                "healthy": self.healthy_agents,
                "degraded": self.degraded_agents,
                "offline": self.offline_agents,
                "health_ratio": round(self.healthy_agents / max(self.total_agents, 1), 3),
            },
            "tasks": {
                "discovered": self.tasks_discovered,
                "applied": self.tasks_applied,
                "assigned": self.tasks_assigned,
                "completed": self.tasks_completed,
                "failed": self.tasks_failed,
                "expired": self.tasks_expired,
                "throughput_per_hour": round(
                    self.tasks_completed / max(self.window_hours, 0.01), 2
                ),
            },
            "financial": {
                "total_earned_usd": round(self.total_earned_usd, 4),
                "total_spent_usd": round(self.total_spent_usd, 4),
                "avg_bounty_usd": round(self.avg_bounty_usd, 4),
                "net_usd": round(self.total_earned_usd - self.total_spent_usd, 4),
            },
            "efficiency": {
                "completion_rate": round(self.completion_rate, 3),
                "apply_to_assign_rate": round(self.apply_to_assign_rate, 3),
                "assignment_to_complete_rate": round(self.assignment_to_complete_rate, 3),
                "avg_completion_hours": round(self.avg_completion_hours, 2),
            },
            "coordination": {
                "irc_messages_sent": self.irc_messages_sent,
                "duplicate_applications": self.duplicate_applications,
                "coordinator_interventions": self.coordinator_interventions,
            },
        }


@dataclass
class TaskFunnelStep:
    """One step in the task funnel analysis."""
    phase: TaskPhase
    count: int = 0
    conversion_from_previous: float = 0.0  # 0.0-1.0


@dataclass
class TaskFunnel:
    """Full task lifecycle funnel."""
    steps: list[TaskFunnelStep] = field(default_factory=list)
    bottleneck: str = ""  # Phase with worst conversion
    bottleneck_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [
                {
                    "phase": s.phase.value,
                    "count": s.count,
                    "conversion": round(s.conversion_from_previous, 3),
                }
                for s in self.steps
            ],
            "bottleneck": self.bottleneck,
            "bottleneck_rate": round(self.bottleneck_rate, 3),
        }


# ---------------------------------------------------------------------------
# Health Assessment
# ---------------------------------------------------------------------------


def assess_agent_health(
    agent_name: str,
    last_heartbeat: str | None = None,
    active_task_id: str | None = None,
    tasks_completed_24h: int = 0,
    tasks_failed_24h: int = 0,
    error_count_24h: int = 0,
    balance_usdc: float | None = None,
    balance_eth: float | None = None,
    irc_connected: bool = False,
    min_usdc: float = 0.01,
    min_eth: float = 0.0001,
    stale_threshold_seconds: int = 600,
    offline_threshold_seconds: int = 3600,
    now: datetime | None = None,
) -> AgentHealthSnapshot:
    """Assess the current health of a single agent.

    Health score is a weighted composite:
      - 40% heartbeat freshness (decays exponentially)
      - 25% task success rate (completed / (completed + failed))
      - 15% error rate (inverse)
      - 10% balance health
      - 10% connectivity (IRC)

    Args:
        agent_name: Agent identifier.
        last_heartbeat: ISO timestamp of last heartbeat (None = never seen).
        active_task_id: Current task being worked (None = idle).
        tasks_completed_24h: Tasks completed in last 24h.
        tasks_failed_24h: Tasks failed in last 24h.
        error_count_24h: Errors logged in last 24h.
        balance_usdc: USDC balance (None = unknown).
        balance_eth: ETH balance for gas (None = unknown).
        irc_connected: Whether agent is connected to IRC.
        min_usdc: Minimum USDC threshold.
        min_eth: Minimum ETH threshold for gas.
        stale_threshold_seconds: Seconds before heartbeat is "stale".
        offline_threshold_seconds: Seconds before agent is "offline".
        now: Current time (for testing).

    Returns:
        AgentHealthSnapshot with computed health score and status.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    snap = AgentHealthSnapshot(
        agent_name=agent_name,
        active_task=bool(active_task_id),
        tasks_completed_24h=tasks_completed_24h,
        tasks_failed_24h=tasks_failed_24h,
        errors_24h=error_count_24h,
        irc_connected=irc_connected,
    )

    # --- Heartbeat freshness (40%) ---
    heartbeat_score = 0.0
    if last_heartbeat:
        snap.last_heartbeat = last_heartbeat
        try:
            hb_time = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
            age = (now - hb_time).total_seconds()
            snap.heartbeat_age_seconds = max(0, int(age))

            if age < 0:
                age = 0  # Future timestamps treated as fresh
            # Exponential decay: half-life = stale_threshold
            heartbeat_score = math.exp(-0.693 * age / max(stale_threshold_seconds, 1))
        except (ValueError, TypeError):
            heartbeat_score = 0.0
            snap.heartbeat_age_seconds = -1
    else:
        heartbeat_score = 0.0
        snap.heartbeat_age_seconds = -1

    # --- Task success rate (25%) ---
    total_tasks = tasks_completed_24h + tasks_failed_24h
    if total_tasks > 0:
        task_score = tasks_completed_24h / total_tasks
    else:
        task_score = 0.5  # Neutral for idle agents

    # --- Error rate (15%) ---
    if error_count_24h == 0:
        error_score = 1.0
    else:
        # Diminishing returns: 1 error = 0.7, 5 errors = 0.3, 10+ = ~0.1
        error_score = max(0.0, 1.0 - 0.3 * math.log(error_count_24h + 1))

    # --- Balance health (10%) ---
    balance_ok = True
    if balance_usdc is not None and balance_usdc < min_usdc:
        balance_ok = False
    if balance_eth is not None and balance_eth < min_eth:
        balance_ok = False
    snap.balance_ok = balance_ok
    balance_score = 1.0 if balance_ok else 0.2

    # --- Connectivity (10%) ---
    connectivity_score = 1.0 if irc_connected else 0.3

    # --- Composite health score ---
    health_score = (
        0.40 * heartbeat_score
        + 0.25 * task_score
        + 0.15 * error_score
        + 0.10 * balance_score
        + 0.10 * connectivity_score
    )
    snap.health_score = min(1.0, max(0.0, health_score))

    # --- Status classification ---
    if snap.heartbeat_age_seconds < 0:
        snap.status = HealthStatus.UNKNOWN
    elif snap.heartbeat_age_seconds > offline_threshold_seconds:
        snap.status = HealthStatus.OFFLINE
    elif snap.heartbeat_age_seconds > stale_threshold_seconds:
        snap.status = HealthStatus.STALE
    elif snap.health_score < 0.4:
        snap.status = HealthStatus.DEGRADED
    else:
        snap.status = HealthStatus.HEALTHY

    snap.details = {
        "heartbeat_score": round(heartbeat_score, 3),
        "task_score": round(task_score, 3),
        "error_score": round(error_score, 3),
        "balance_score": round(balance_score, 3),
        "connectivity_score": round(connectivity_score, 3),
    }

    return snap


# ---------------------------------------------------------------------------
# Swarm Metrics Aggregation
# ---------------------------------------------------------------------------


def compute_swarm_metrics(
    agent_snapshots: list[AgentHealthSnapshot],
    task_events: list[dict[str, Any]] | None = None,
    window_hours: float = 24.0,
    now: datetime | None = None,
) -> SwarmMetrics:
    """Aggregate individual agent snapshots into swarm-level metrics.

    Args:
        agent_snapshots: List of AgentHealthSnapshot for each agent.
        task_events: Optional list of task event dicts with keys:
            - phase: TaskPhase value string
            - agent: agent name
            - timestamp: ISO timestamp
            - bounty_usd: float (optional)
            - completion_hours: float (optional)
        window_hours: Time window for metrics.
        now: Current time (for testing).

    Returns:
        SwarmMetrics with aggregated data.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    metrics = SwarmMetrics(
        window_start=(now - timedelta(hours=window_hours)).isoformat(),
        window_end=now.isoformat(),
        window_hours=window_hours,
        total_agents=len(agent_snapshots),
    )

    # Aggregate agent health
    for snap in agent_snapshots:
        if snap.status == HealthStatus.HEALTHY:
            metrics.healthy_agents += 1
        elif snap.status == HealthStatus.DEGRADED:
            metrics.degraded_agents += 1
        elif snap.status in (HealthStatus.OFFLINE, HealthStatus.STALE):
            metrics.offline_agents += 1

        metrics.tasks_completed += snap.tasks_completed_24h
        metrics.tasks_failed += snap.tasks_failed_24h

    # Process task events if provided
    if task_events:
        completion_hours_list: list[float] = []
        bounties: list[float] = []
        seen_tasks: dict[str, set[str]] = {}  # task_id → set of applying agents

        for event in task_events:
            phase_str = event.get("phase", "")
            try:
                phase = TaskPhase(phase_str)
            except ValueError:
                continue

            if phase == TaskPhase.DISCOVERED:
                metrics.tasks_discovered += 1
            elif phase == TaskPhase.APPLIED:
                metrics.tasks_applied += 1
                # Track duplicate applications
                task_id = event.get("task_id", "")
                agent = event.get("agent", "")
                if task_id:
                    if task_id not in seen_tasks:
                        seen_tasks[task_id] = set()
                    if agent in seen_tasks[task_id]:
                        metrics.duplicate_applications += 1
                    seen_tasks[task_id].add(agent)
            elif phase == TaskPhase.ASSIGNED:
                metrics.tasks_assigned += 1
            elif phase == TaskPhase.COMPLETED:
                # Already counted from agent snapshots above
                hours = event.get("completion_hours")
                if hours is not None:
                    completion_hours_list.append(float(hours))
            elif phase == TaskPhase.EXPIRED:
                metrics.tasks_expired += 1

            bounty = event.get("bounty_usd")
            if bounty is not None and phase == TaskPhase.COMPLETED:
                bounties.append(float(bounty))
                metrics.total_earned_usd += float(bounty)

        if completion_hours_list:
            metrics.avg_completion_hours = sum(completion_hours_list) / len(completion_hours_list)

        if bounties:
            metrics.avg_bounty_usd = sum(bounties) / len(bounties)

    # Compute efficiency rates
    total_resolved = metrics.tasks_completed + metrics.tasks_failed + metrics.tasks_expired
    if total_resolved > 0:
        metrics.completion_rate = metrics.tasks_completed / total_resolved

    if metrics.tasks_applied > 0:
        metrics.apply_to_assign_rate = metrics.tasks_assigned / metrics.tasks_applied

    if metrics.tasks_assigned > 0:
        metrics.assignment_to_complete_rate = metrics.tasks_completed / metrics.tasks_assigned

    return metrics


# ---------------------------------------------------------------------------
# Task Funnel Analysis
# ---------------------------------------------------------------------------


def build_task_funnel(
    discovered: int = 0,
    applied: int = 0,
    assigned: int = 0,
    working: int = 0,
    submitted: int = 0,
    completed: int = 0,
    failed: int = 0,
    expired: int = 0,
) -> TaskFunnel:
    """Build a task lifecycle funnel from aggregate counts.

    The funnel shows conversion rates at each phase, identifying bottlenecks.

    Returns:
        TaskFunnel with steps and identified bottleneck.
    """
    phases = [
        (TaskPhase.DISCOVERED, discovered),
        (TaskPhase.APPLIED, applied),
        (TaskPhase.ASSIGNED, assigned),
        (TaskPhase.WORKING, working),
        (TaskPhase.SUBMITTED, submitted),
        (TaskPhase.COMPLETED, completed),
    ]

    steps: list[TaskFunnelStep] = []
    worst_phase = ""
    worst_rate = 1.0

    for i, (phase, count) in enumerate(phases):
        if i == 0:
            conversion = 1.0
        else:
            prev_count = phases[i - 1][1]
            if prev_count > 0:
                conversion = min(1.0, count / prev_count)
            else:
                conversion = 0.0 if count == 0 else 1.0

        step = TaskFunnelStep(
            phase=phase,
            count=count,
            conversion_from_previous=conversion,
        )
        steps.append(step)

        # Track bottleneck (skip first step, and only consider where prev > 0)
        if i > 0 and phases[i - 1][1] > 0 and conversion < worst_rate:
            worst_rate = conversion
            worst_phase = phase.value

    funnel = TaskFunnel(steps=steps)
    if worst_phase:
        funnel.bottleneck = worst_phase
        funnel.bottleneck_rate = worst_rate

    return funnel


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------


def generate_health_report(
    snapshots: list[AgentHealthSnapshot],
    swarm_metrics: SwarmMetrics | None = None,
    funnel: TaskFunnel | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive health report for the swarm.

    Returns a dict suitable for JSON serialization or Acontext storage.
    """
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": {},
        "summary": {},
    }

    # Agent details
    for snap in snapshots:
        report["agents"][snap.agent_name] = snap.to_dict()

    # Summary
    total = len(snapshots)
    healthy = sum(1 for s in snapshots if s.is_healthy)
    avg_score = sum(s.health_score for s in snapshots) / max(total, 1)

    report["summary"] = {
        "total_agents": total,
        "healthy_agents": healthy,
        "health_ratio": round(healthy / max(total, 1), 3),
        "avg_health_score": round(avg_score, 3),
        "agents_with_active_tasks": sum(1 for s in snapshots if s.active_task),
        "agents_with_errors": sum(1 for s in snapshots if s.errors_24h > 0),
        "agents_low_balance": sum(1 for s in snapshots if not s.balance_ok),
    }

    if swarm_metrics:
        report["swarm_metrics"] = swarm_metrics.to_dict()

    if funnel:
        report["task_funnel"] = funnel.to_dict()

    return report


def save_health_report(report: dict[str, Any], output_dir: Path) -> Path:
    """Save health report to a timestamped JSON file.

    Returns the path to the saved file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"health_report_{timestamp}.json"
    path = output_dir / filename

    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return path


def load_health_reports(
    output_dir: Path,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Load recent health reports for trend analysis.

    Returns list of report dicts, most recent first.
    """
    if not output_dir.exists():
        return []

    files = sorted(output_dir.glob("health_report_*.json"), reverse=True)[:limit]
    reports: list[dict[str, Any]] = []

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            reports.append(data)
        except Exception:
            continue

    return reports


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------


def compute_health_trend(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze health trends across multiple reports.

    Returns trend data showing whether the swarm is improving or degrading.
    """
    if len(reports) < 2:
        return {"trend": "insufficient_data", "reports_analyzed": len(reports)}

    scores = []
    completion_rates = []
    healthy_ratios = []

    for r in reports:
        summary = r.get("summary", {})
        scores.append(summary.get("avg_health_score", 0))
        healthy_ratios.append(summary.get("health_ratio", 0))

        metrics = r.get("swarm_metrics", {})
        efficiency = metrics.get("efficiency", {})
        completion_rates.append(efficiency.get("completion_rate", 0))

    # Simple trend: compare first half vs second half
    mid = len(scores) // 2
    recent_avg = sum(scores[:mid]) / max(mid, 1)  # More recent
    older_avg = sum(scores[mid:]) / max(len(scores) - mid, 1)

    if recent_avg > older_avg + 0.05:
        trend = "improving"
    elif recent_avg < older_avg - 0.05:
        trend = "degrading"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "reports_analyzed": len(reports),
        "recent_avg_score": round(recent_avg, 3),
        "older_avg_score": round(older_avg, 3),
        "score_delta": round(recent_avg - older_avg, 3),
        "latest_health_ratio": healthy_ratios[0] if healthy_ratios else 0,
        "latest_completion_rate": completion_rates[0] if completion_rates else 0,
    }


# ---------------------------------------------------------------------------
# Acontext Integration Helpers
# ---------------------------------------------------------------------------


def format_for_acontext_session(
    report: dict[str, Any],
) -> dict[str, Any]:
    """Format a health report as an Acontext session interaction.

    This produces a structured blob that Acontext can store, compress,
    and use for observability dashboards.
    """
    return {
        "role": "system",
        "content": json.dumps(report, default=str),
        "metadata": {
            "type": "health_report",
            "generated_at": report.get("generated_at", ""),
            "agent_count": report.get("summary", {}).get("total_agents", 0),
            "health_ratio": report.get("summary", {}).get("health_ratio", 0),
        },
    }


def format_agent_event(
    agent_name: str,
    event_type: str,
    details: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Format a single agent event for Acontext logging.

    Event types: heartbeat, task_start, task_complete, task_fail,
                 error, balance_alert, irc_connect, irc_disconnect.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    return {
        "timestamp": now.isoformat(),
        "agent": agent_name,
        "event": event_type,
        "details": details or {},
    }
