"""
Karma Kadabra V2 — Swarm Monitor Service

Real-time monitoring and alerting for the KK swarm. Watches all subsystems
and generates alerts, status reports, trend digests, and health snapshots.

Monitors:
  - Agent health (heartbeat freshness, error rates, circuit breakers)
  - Task pipeline flow (bottlenecks, SLA breaches, stuck tasks)
  - Reputation trends (sudden drops, tier changes)
  - System resources (API connectivity, chain RPC, balance alerts)
  - Decision quality (chosen agents' actual outcomes vs predictions)

Alert levels:
  - INFO: Routine status updates, trends
  - WARNING: Potential issues, approaching thresholds
  - CRITICAL: Requires immediate attention
  - EMERGENCY: System-level failure, swarm degraded

Outputs:
  - Structured alerts (for IRC/Telegram notification)
  - Status digests (periodic summaries)
  - Trend reports (daily/weekly performance)
  - Anomaly flags (unusual patterns)

All functions are pure except persistence (save/load).
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

logger = logging.getLogger("kk.monitor")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertCategory(Enum):
    """What subsystem generated the alert."""
    AGENT_HEALTH = "agent_health"
    TASK_PIPELINE = "task_pipeline"
    REPUTATION = "reputation"
    SYSTEM = "system"
    DECISION = "decision"
    FINANCIAL = "financial"
    PERFORMANCE = "performance"


class MonitorStatus(Enum):
    """Overall swarm status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    IMPAIRED = "impaired"
    DOWN = "down"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """A single monitoring alert."""
    level: AlertLevel
    category: AlertCategory
    title: str
    message: str
    agent_name: str = ""       # Empty for system-wide alerts
    task_id: str = ""
    timestamp: str = ""
    metric_value: float = 0.0  # The metric that triggered the alert
    threshold: float = 0.0     # The threshold that was breached
    suggested_action: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "agent_name": self.agent_name,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "metric_value": round(self.metric_value, 3),
            "threshold": round(self.threshold, 3),
            "suggested_action": self.suggested_action,
        }

    def format_irc(self) -> str:
        """Format alert for IRC/Telegram notification."""
        icons = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
            AlertLevel.EMERGENCY: "🔥",
        }
        icon = icons.get(self.level, "❓")
        agent_part = f" [{self.agent_name}]" if self.agent_name else ""
        return f"{icon}{agent_part} {self.title}: {self.message}"


@dataclass
class AgentHealthSnapshot:
    """Point-in-time health data for one agent."""
    agent_name: str
    is_online: bool = False
    state: str = "unknown"
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    current_tasks: int = 0
    last_heartbeat_age_seconds: float = -1  # -1 = no heartbeat
    usdc_balance: float = 0.0
    eth_balance: float = 0.0
    reputation_score: float = 50.0
    efficiency_score: float = 50.0


@dataclass
class PipelineSnapshot:
    """Point-in-time pipeline state."""
    total_tasks: int = 0
    by_stage: dict[str, int] = field(default_factory=dict)
    stuck_tasks: int = 0              # Tasks exceeding SLA
    avg_time_in_pipeline_hours: float = 0.0
    completion_rate_24h: float = 0.0
    failure_rate_24h: float = 0.0
    oldest_task_hours: float = 0.0


@dataclass
class SystemSnapshot:
    """System-level health indicators."""
    em_api_healthy: bool = True
    base_rpc_healthy: bool = True
    irc_connected: bool = True
    disk_usage_pct: float = 0.0
    uptime_hours: float = 0.0
    last_successful_cycle: str = ""


@dataclass
class MonitorConfig:
    """Configuration for monitoring thresholds."""
    # Agent health
    heartbeat_stale_seconds: float = 300    # 5 minutes
    heartbeat_dead_seconds: float = 900     # 15 minutes
    max_consecutive_failures: int = 3
    low_balance_usdc: float = 1.0
    low_balance_eth: float = 0.001
    reputation_drop_threshold: float = 10.0  # Points

    # Pipeline
    max_stuck_tasks: int = 5
    pipeline_sla_hours: dict[str, float] = field(default_factory=lambda: {
        "DISCOVERED": 1.0,
        "EVALUATED": 0.5,
        "OFFERED": 2.0,
        "ACCEPTED": 1.0,
        "IN_PROGRESS": 24.0,
        "SUBMITTED": 4.0,
        "UNDER_REVIEW": 8.0,
        "APPROVED": 2.0,
        "PAID": 1.0,
    })
    min_completion_rate: float = 0.5         # 50%
    max_failure_rate: float = 0.3            # 30%

    # System
    max_api_downtime_minutes: float = 5.0

    # Performance
    min_agents_online: int = 3
    min_availability_ratio: float = 0.3      # 30% of swarm online

    # Digest
    digest_interval_hours: float = 6.0


@dataclass
class StatusDigest:
    """Periodic status summary."""
    timestamp: str
    status: MonitorStatus
    agents_online: int = 0
    agents_total: int = 0
    tasks_in_pipeline: int = 0
    tasks_completed_period: int = 0
    tasks_failed_period: int = 0
    alerts_count: dict[str, int] = field(default_factory=dict)
    top_performer: str = ""
    bottleneck_stage: str = ""
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "status": self.status.value,
            "agents_online": self.agents_online,
            "agents_total": self.agents_total,
            "tasks_in_pipeline": self.tasks_in_pipeline,
            "tasks_completed_period": self.tasks_completed_period,
            "tasks_failed_period": self.tasks_failed_period,
            "alerts_count": self.alerts_count,
            "top_performer": self.top_performer,
            "bottleneck_stage": self.bottleneck_stage,
            "highlights": self.highlights,
        }

    def format_text(self) -> str:
        """Human-readable status digest."""
        status_icons = {
            MonitorStatus.HEALTHY: "🟢",
            MonitorStatus.DEGRADED: "🟡",
            MonitorStatus.IMPAIRED: "🟠",
            MonitorStatus.DOWN: "🔴",
        }
        icon = status_icons.get(self.status, "❓")

        lines = [
            f"{icon} KK Swarm Status Digest — {self.timestamp[:16]}",
            f"   Status: {self.status.value.upper()}",
            f"   Agents: {self.agents_online}/{self.agents_total} online",
            f"   Pipeline: {self.tasks_in_pipeline} active tasks",
            f"   Period: {self.tasks_completed_period} completed, {self.tasks_failed_period} failed",
        ]

        if self.top_performer:
            lines.append(f"   ⭐ Top performer: {self.top_performer}")
        if self.bottleneck_stage:
            lines.append(f"   🔍 Bottleneck: {self.bottleneck_stage}")

        alert_summary = ", ".join(f"{v} {k}" for k, v in self.alerts_count.items() if v > 0)
        if alert_summary:
            lines.append(f"   📋 Alerts: {alert_summary}")

        for highlight in self.highlights[:3]:
            lines.append(f"   💡 {highlight}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Alert Generation (pure functions)
# ---------------------------------------------------------------------------

def check_agent_health(
    agents: list[AgentHealthSnapshot],
    config: MonitorConfig,
    now: datetime | None = None,
) -> list[Alert]:
    """Generate alerts from agent health snapshots."""
    if now is None:
        now = datetime.now(timezone.utc)
    alerts = []

    for agent in agents:
        # Stale heartbeat
        if 0 <= agent.last_heartbeat_age_seconds >= config.heartbeat_dead_seconds:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                category=AlertCategory.AGENT_HEALTH,
                title="Agent unresponsive",
                message=f"No heartbeat for {agent.last_heartbeat_age_seconds / 60:.0f} minutes",
                agent_name=agent.agent_name,
                metric_value=agent.last_heartbeat_age_seconds,
                threshold=config.heartbeat_dead_seconds,
                suggested_action="Restart agent or check network connectivity",
            ))
        elif 0 <= agent.last_heartbeat_age_seconds >= config.heartbeat_stale_seconds:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.AGENT_HEALTH,
                title="Stale heartbeat",
                message=f"Last heartbeat {agent.last_heartbeat_age_seconds / 60:.0f}m ago",
                agent_name=agent.agent_name,
                metric_value=agent.last_heartbeat_age_seconds,
                threshold=config.heartbeat_stale_seconds,
                suggested_action="Monitor — may recover automatically",
            ))

        # Consecutive failures
        if agent.consecutive_failures >= config.max_consecutive_failures:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                category=AlertCategory.AGENT_HEALTH,
                title="Circuit breaker tripped",
                message=f"{agent.consecutive_failures} consecutive failures",
                agent_name=agent.agent_name,
                metric_value=float(agent.consecutive_failures),
                threshold=float(config.max_consecutive_failures),
                suggested_action="Investigate failure cause, then reset circuit breaker",
            ))
        elif agent.consecutive_failures >= config.max_consecutive_failures - 1:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.AGENT_HEALTH,
                title="Near circuit breaker",
                message=f"{agent.consecutive_failures}/{config.max_consecutive_failures} failures",
                agent_name=agent.agent_name,
                metric_value=float(agent.consecutive_failures),
                threshold=float(config.max_consecutive_failures),
                suggested_action="Consider reducing agent workload",
            ))

        # Low balance
        if agent.usdc_balance > 0 and agent.usdc_balance < config.low_balance_usdc:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.FINANCIAL,
                title="Low USDC balance",
                message=f"${agent.usdc_balance:.2f} USDC remaining",
                agent_name=agent.agent_name,
                metric_value=agent.usdc_balance,
                threshold=config.low_balance_usdc,
                suggested_action="Top up agent wallet",
            ))

        if agent.eth_balance > 0 and agent.eth_balance < config.low_balance_eth:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.FINANCIAL,
                title="Low ETH for gas",
                message=f"{agent.eth_balance:.4f} ETH remaining",
                agent_name=agent.agent_name,
                metric_value=agent.eth_balance,
                threshold=config.low_balance_eth,
                suggested_action="Send ETH for gas fees",
            ))

    # Swarm-wide checks
    online_count = sum(1 for a in agents if a.is_online)
    total_count = len(agents)

    if total_count > 0:
        availability = online_count / total_count
        if online_count < config.min_agents_online:
            alerts.append(Alert(
                level=AlertLevel.EMERGENCY if online_count == 0 else AlertLevel.CRITICAL,
                category=AlertCategory.AGENT_HEALTH,
                title="Swarm understaffed",
                message=f"Only {online_count}/{total_count} agents online",
                metric_value=float(online_count),
                threshold=float(config.min_agents_online),
                suggested_action="Start more agents or investigate offline agents",
            ))
        elif availability < config.min_availability_ratio:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.AGENT_HEALTH,
                title="Low availability",
                message=f"{availability:.0%} availability ({online_count}/{total_count})",
                metric_value=availability,
                threshold=config.min_availability_ratio,
                suggested_action="Scale up the swarm",
            ))

    return alerts


def check_pipeline_health(
    pipeline: PipelineSnapshot,
    config: MonitorConfig,
) -> list[Alert]:
    """Generate alerts from pipeline state."""
    alerts = []

    # Stuck tasks
    if pipeline.stuck_tasks > config.max_stuck_tasks:
        alerts.append(Alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.TASK_PIPELINE,
            title="Tasks stuck in pipeline",
            message=f"{pipeline.stuck_tasks} tasks exceeding SLA",
            metric_value=float(pipeline.stuck_tasks),
            threshold=float(config.max_stuck_tasks),
            suggested_action="Review stuck tasks, reassign or escalate",
        ))
    elif pipeline.stuck_tasks > 0:
        alerts.append(Alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.TASK_PIPELINE,
            title="SLA breach",
            message=f"{pipeline.stuck_tasks} task(s) past SLA",
            metric_value=float(pipeline.stuck_tasks),
            threshold=float(config.max_stuck_tasks),
            suggested_action="Monitor — may resolve naturally",
        ))

    # High failure rate
    if pipeline.failure_rate_24h > config.max_failure_rate:
        alerts.append(Alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.TASK_PIPELINE,
            title="High failure rate",
            message=f"{pipeline.failure_rate_24h:.0%} task failure rate (24h)",
            metric_value=pipeline.failure_rate_24h,
            threshold=config.max_failure_rate,
            suggested_action="Investigate common failure causes",
        ))

    # Low completion rate
    if 0 < pipeline.completion_rate_24h < config.min_completion_rate:
        alerts.append(Alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.TASK_PIPELINE,
            title="Low completion rate",
            message=f"{pipeline.completion_rate_24h:.0%} completion (24h)",
            metric_value=pipeline.completion_rate_24h,
            threshold=config.min_completion_rate,
            suggested_action="Check agent capacity and task difficulty",
        ))

    # Stage bottlenecks
    for stage, count in pipeline.by_stage.items():
        sla = config.pipeline_sla_hours.get(stage, 24.0)
        if count > 10 and stage not in ("COMPLETED", "FAILED", "EXPIRED"):
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.TASK_PIPELINE,
                title=f"Bottleneck at {stage}",
                message=f"{count} tasks queued at {stage} stage",
                metric_value=float(count),
                threshold=10.0,
                suggested_action=f"Increase throughput at {stage} stage",
            ))

    # Very old task
    if pipeline.oldest_task_hours > 72:
        alerts.append(Alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.TASK_PIPELINE,
            title="Stale task detected",
            message=f"Oldest task is {pipeline.oldest_task_hours:.0f}h old",
            metric_value=pipeline.oldest_task_hours,
            threshold=72.0,
            suggested_action="Review and expire or reassign",
        ))

    return alerts


def check_system_health(
    system: SystemSnapshot,
    config: MonitorConfig,
) -> list[Alert]:
    """Generate alerts from system health indicators."""
    alerts = []

    if not system.em_api_healthy:
        alerts.append(Alert(
            level=AlertLevel.EMERGENCY,
            category=AlertCategory.SYSTEM,
            title="EM API unreachable",
            message="Cannot connect to Execution Market API",
            suggested_action="Check https://api.execution.market/health",
        ))

    if not system.base_rpc_healthy:
        alerts.append(Alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.SYSTEM,
            title="Base RPC unhealthy",
            message="On-chain operations may fail",
            suggested_action="Check RPC provider status, switch to backup",
        ))

    if not system.irc_connected:
        alerts.append(Alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.SYSTEM,
            title="IRC disconnected",
            message="Agent coordination channel offline",
            suggested_action="Reconnect to IRC bridge",
        ))

    return alerts


def check_reputation_changes(
    current: dict[str, float],
    previous: dict[str, float],
    config: MonitorConfig,
) -> list[Alert]:
    """Detect significant reputation changes between snapshots."""
    alerts = []

    for agent_name, current_score in current.items():
        prev_score = previous.get(agent_name)
        if prev_score is None:
            continue

        delta = current_score - prev_score

        if delta <= -config.reputation_drop_threshold:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.REPUTATION,
                title="Reputation drop",
                message=f"Score dropped {abs(delta):.1f} points ({prev_score:.0f} → {current_score:.0f})",
                agent_name=agent_name,
                metric_value=delta,
                threshold=-config.reputation_drop_threshold,
                suggested_action="Review recent task quality",
            ))
        elif delta >= config.reputation_drop_threshold:
            alerts.append(Alert(
                level=AlertLevel.INFO,
                category=AlertCategory.REPUTATION,
                title="Reputation improvement",
                message=f"Score rose {delta:.1f} points ({prev_score:.0f} → {current_score:.0f})",
                agent_name=agent_name,
                metric_value=delta,
                threshold=config.reputation_drop_threshold,
            ))

    return alerts


def check_decision_outcomes(
    decisions: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> list[Alert]:
    """Compare decision predictions vs actual outcomes to detect drift.

    decisions: list of {"task_id", "chosen_agent", "confidence", "risk_level"}
    outcomes: list of {"task_id", "success": bool, "rating": float}
    """
    alerts = []

    if len(decisions) < 5:
        return alerts  # Not enough data

    outcome_map = {o["task_id"]: o for o in outcomes}
    high_confidence_failures = 0
    low_risk_failures = 0
    total_matched = 0

    for dec in decisions:
        outcome = outcome_map.get(dec.get("task_id"))
        if not outcome:
            continue

        total_matched += 1
        if not outcome.get("success", True):
            if dec.get("confidence", 0) > 0.7:
                high_confidence_failures += 1
            if dec.get("risk_level") == "low":
                low_risk_failures += 1

    if total_matched > 0:
        failure_ratio = (high_confidence_failures + low_risk_failures) / total_matched
        if failure_ratio > 0.3:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                category=AlertCategory.DECISION,
                title="Decision model drift",
                message=f"{failure_ratio:.0%} of confident decisions failed ({total_matched} sample)",
                metric_value=failure_ratio,
                threshold=0.3,
                suggested_action="Recalibrate decision engine weights",
            ))

    return alerts


# ---------------------------------------------------------------------------
# Status Assessment
# ---------------------------------------------------------------------------

def assess_swarm_status(
    alerts: list[Alert],
    agents_online: int,
    agents_total: int,
) -> MonitorStatus:
    """Determine overall swarm status from alerts."""
    emergency_count = sum(1 for a in alerts if a.level == AlertLevel.EMERGENCY)
    critical_count = sum(1 for a in alerts if a.level == AlertLevel.CRITICAL)
    warning_count = sum(1 for a in alerts if a.level == AlertLevel.WARNING)

    if emergency_count > 0 or agents_online == 0:
        return MonitorStatus.DOWN
    if critical_count >= 3 or agents_online < 2:
        return MonitorStatus.IMPAIRED
    if critical_count > 0 or warning_count >= 5:
        return MonitorStatus.DEGRADED
    return MonitorStatus.HEALTHY


# ---------------------------------------------------------------------------
# Status Digest
# ---------------------------------------------------------------------------

def generate_digest(
    agents: list[AgentHealthSnapshot],
    pipeline: PipelineSnapshot,
    alerts: list[Alert],
    now: datetime | None = None,
) -> StatusDigest:
    """Generate a periodic status digest."""
    if now is None:
        now = datetime.now(timezone.utc)

    online = sum(1 for a in agents if a.is_online)
    total = len(agents)

    status = assess_swarm_status(alerts, online, total)

    # Alert counts by level
    alert_counts = {}
    for level in AlertLevel:
        count = sum(1 for a in alerts if a.level == level)
        if count > 0:
            alert_counts[level.value] = count

    # Top performer (most successes)
    top = max(agents, key=lambda a: a.total_successes) if agents else None
    top_name = top.agent_name if top and top.total_successes > 0 else ""

    # Bottleneck detection
    bottleneck = ""
    if pipeline.by_stage:
        # Exclude terminal stages
        active_stages = {k: v for k, v in pipeline.by_stage.items()
                         if k not in ("COMPLETED", "FAILED", "EXPIRED", "RATED")}
        if active_stages:
            bottleneck = max(active_stages, key=active_stages.get)

    # Highlights
    highlights = []
    if pipeline.completion_rate_24h > 0.8:
        highlights.append(f"Excellent completion rate: {pipeline.completion_rate_24h:.0%}")
    if online == total and total > 0:
        highlights.append("Full swarm online ✅")
    if any(a.level == AlertLevel.EMERGENCY for a in alerts):
        highlights.append("⚠️ EMERGENCY alerts active — immediate action needed")

    # Agent with most failures
    problem_agents = [a for a in agents if a.consecutive_failures >= 2]
    if problem_agents:
        highlights.append(
            f"{len(problem_agents)} agent(s) with repeated failures"
        )

    return StatusDigest(
        timestamp=now.isoformat(),
        status=status,
        agents_online=online,
        agents_total=total,
        tasks_in_pipeline=pipeline.total_tasks,
        tasks_completed_period=sum(
            pipeline.by_stage.get(s, 0)
            for s in ("COMPLETED", "RATED", "PAID")
        ),
        tasks_failed_period=pipeline.by_stage.get("FAILED", 0),
        alerts_count=alert_counts,
        top_performer=top_name,
        bottleneck_stage=bottleneck,
        highlights=highlights,
    )


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------

@dataclass
class TrendPoint:
    """A single data point in a time series."""
    timestamp: str
    value: float


@dataclass
class TrendAnalysis:
    """Analysis of a metric trend over time."""
    metric_name: str
    direction: str = "stable"   # improving, declining, stable, volatile
    current_value: float = 0.0
    avg_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    change_pct: float = 0.0     # Percentage change
    data_points: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric_name,
            "direction": self.direction,
            "current": round(self.current_value, 2),
            "avg": round(self.avg_value, 2),
            "min": round(self.min_value, 2),
            "max": round(self.max_value, 2),
            "change_pct": round(self.change_pct, 1),
            "data_points": self.data_points,
        }


def analyze_trend(
    metric_name: str,
    points: list[TrendPoint],
    window: int = 10,
) -> TrendAnalysis:
    """Analyze a metric's trend from time-series data.

    Args:
        metric_name: Name of the metric.
        points: Time-series data (newest first or oldest first).
        window: Number of recent points to analyze.
    """
    analysis = TrendAnalysis(metric_name=metric_name)

    if len(points) < 2:
        analysis.data_points = len(points)
        if points:
            analysis.current_value = points[-1].value
            analysis.avg_value = points[-1].value
        return analysis

    # Use the most recent window
    recent = points[-window:] if len(points) > window else points
    values = [p.value for p in recent]

    analysis.data_points = len(recent)
    analysis.current_value = values[-1]
    analysis.avg_value = sum(values) / len(values)
    analysis.min_value = min(values)
    analysis.max_value = max(values)

    # Change percentage (first → last in window)
    if values[0] != 0:
        analysis.change_pct = ((values[-1] - values[0]) / abs(values[0])) * 100
    elif values[-1] != 0:
        analysis.change_pct = 100.0
    else:
        analysis.change_pct = 0.0

    # Direction detection
    if len(values) >= 3:
        # Simple linear regression slope
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator > 0:
            slope = numerator / denominator
            # Normalize slope relative to average value
            normalized_slope = slope / max(abs(y_mean), 1.0)

            if normalized_slope > 0.05:
                analysis.direction = "improving"
            elif normalized_slope < -0.05:
                analysis.direction = "declining"
            else:
                analysis.direction = "stable"

            # Check for volatility
            if len(values) >= 4:
                std_dev = math.sqrt(
                    sum((v - y_mean) ** 2 for v in values) / len(values)
                )
                cv = std_dev / max(abs(y_mean), 1.0)
                if cv > 0.3:
                    analysis.direction = "volatile"

    return analysis


# ---------------------------------------------------------------------------
# Swarm Monitor (Stateful)
# ---------------------------------------------------------------------------

class SwarmMonitor:
    """Stateful swarm monitor that tracks history and generates insights.

    Maintains a rolling history of snapshots and alerts for trend analysis.
    """

    def __init__(self, config: MonitorConfig | None = None, max_history: int = 100):
        self.config = config or MonitorConfig()
        self.max_history = max_history
        self.alert_history: list[Alert] = []
        self.digest_history: list[StatusDigest] = []
        self.reputation_history: list[dict[str, float]] = []
        self.agent_success_history: dict[str, list[TrendPoint]] = {}
        self._suppressed: dict[str, str] = {}  # key → last_timestamp (dedup)

    def run_checks(
        self,
        agents: list[AgentHealthSnapshot],
        pipeline: PipelineSnapshot,
        system: SystemSnapshot,
        current_reputations: dict[str, float] | None = None,
        now: datetime | None = None,
    ) -> tuple[list[Alert], StatusDigest]:
        """Run all monitoring checks and return alerts + digest.

        This is the main entry point for periodic monitoring.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        all_alerts = []

        # Agent health
        all_alerts.extend(check_agent_health(agents, self.config, now))

        # Pipeline
        all_alerts.extend(check_pipeline_health(pipeline, self.config))

        # System
        all_alerts.extend(check_system_health(system, self.config))

        # Reputation changes
        if current_reputations and self.reputation_history:
            prev = self.reputation_history[-1]
            all_alerts.extend(
                check_reputation_changes(current_reputations, prev, self.config)
            )

        # Stamp all alerts with the provided now time (for consistent dedup)
        now_iso = now.isoformat()
        for alert in all_alerts:
            alert.timestamp = now_iso

        # Deduplicate alerts (same title+agent within 5 minutes)
        deduped = self._deduplicate_alerts(all_alerts)

        # Update history
        self.alert_history.extend(deduped)
        self._trim_history()

        if current_reputations:
            self.reputation_history.append(current_reputations)

        # Track per-agent success trends
        for agent in agents:
            if agent.agent_name not in self.agent_success_history:
                self.agent_success_history[agent.agent_name] = []
            total = agent.total_successes + agent.total_failures
            rate = agent.total_successes / total if total > 0 else 0.5
            self.agent_success_history[agent.agent_name].append(
                TrendPoint(timestamp=now.isoformat(), value=rate)
            )

        # Generate digest
        digest = generate_digest(agents, pipeline, deduped, now)
        self.digest_history.append(digest)

        return deduped, digest

    def get_agent_trends(self) -> dict[str, TrendAnalysis]:
        """Get success rate trends for all tracked agents."""
        trends = {}
        for name, points in self.agent_success_history.items():
            if len(points) >= 2:
                trends[name] = analyze_trend(f"{name}_success_rate", points)
        return trends

    def get_alert_summary(self, hours: float = 24.0) -> dict[str, Any]:
        """Summarize alerts from the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        recent = [a for a in self.alert_history if a.timestamp >= cutoff_str]

        by_level = {}
        by_category = {}
        by_agent = {}

        for alert in recent:
            level = alert.level.value
            by_level[level] = by_level.get(level, 0) + 1

            cat = alert.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            if alert.agent_name:
                by_agent[alert.agent_name] = by_agent.get(alert.agent_name, 0) + 1

        return {
            "period_hours": hours,
            "total_alerts": len(recent),
            "by_level": by_level,
            "by_category": by_category,
            "by_agent": by_agent,
            "most_recent": [a.to_dict() for a in recent[-5:]],
        }

    def _deduplicate_alerts(self, alerts: list[Alert]) -> list[Alert]:
        """Remove duplicate alerts (same title+agent within suppression window)."""
        deduped = []
        for alert in alerts:
            key = f"{alert.title}:{alert.agent_name}"
            last = self._suppressed.get(key)
            if last:
                try:
                    last_dt = datetime.fromisoformat(last)
                    alert_dt = datetime.fromisoformat(alert.timestamp)
                    if (alert_dt - last_dt).total_seconds() < 300:  # 5-min suppression
                        continue
                except (ValueError, TypeError):
                    pass

            self._suppressed[key] = alert.timestamp
            deduped.append(alert)

        return deduped

    def _trim_history(self):
        """Keep history bounded."""
        if len(self.alert_history) > self.max_history * 5:
            self.alert_history = self.alert_history[-self.max_history * 3:]
        if len(self.digest_history) > self.max_history:
            self.digest_history = self.digest_history[-self.max_history:]
        if len(self.reputation_history) > self.max_history:
            self.reputation_history = self.reputation_history[-self.max_history:]
        for name in self.agent_success_history:
            if len(self.agent_success_history[name]) > self.max_history:
                self.agent_success_history[name] = \
                    self.agent_success_history[name][-self.max_history:]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_monitor_state(monitor: SwarmMonitor, path: Path) -> Path:
    """Save monitor state to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "alert_count": len(monitor.alert_history),
        "digest_count": len(monitor.digest_history),
        "alerts": [a.to_dict() for a in monitor.alert_history[-50:]],
        "digests": [d.to_dict() for d in monitor.digest_history[-10:]],
        "reputation_snapshots": len(monitor.reputation_history),
        "agent_trend_count": len(monitor.agent_success_history),
    }

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_monitor_state(path: Path) -> dict[str, Any]:
    """Load monitor state from JSON."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to load monitor state: {e}")
        return {}
