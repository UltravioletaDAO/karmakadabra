"""
Karma Kadabra V2 — Swarm Analytics Engine

Intelligence layer that transforms raw pipeline and lifecycle data
into actionable insights for swarm optimization.

Features:
  - Agent efficiency scoring (throughput, quality, cost)
  - Trend analysis (rolling windows: 1h, 24h, 7d)
  - Bottleneck detection (where tasks get stuck)
  - Cost optimization (earnings vs operational cost)
  - Capacity planning (can the swarm handle more work?)
  - Agent pairing analysis (which agents work best together)
  - Anomaly detection (sudden drops in performance)
  - Predictive load balancing (anticipate demand patterns)

All functions are pure — no side effects, easily testable.
Designed for both real-time coordinator decisions and offline reporting.

Usage:
    from lib.swarm_analytics import SwarmAnalyzer

    analyzer = SwarmAnalyzer(pipeline_state, lifecycle_agents)
    report = analyzer.full_report()
    bottlenecks = analyzer.detect_bottlenecks()
    capacity = analyzer.capacity_forecast()
"""

from __future__ import annotations

import json
import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kk.analytics")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AgentEfficiency:
    """Efficiency metrics for a single agent."""
    agent_name: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_earned_usd: float = 0.0
    avg_completion_hours: float = 0.0
    throughput_per_day: float = 0.0  # tasks/day
    earnings_per_hour: float = 0.0  # $/hour of active work
    reliability: float = 0.0  # 0-1 completion rate
    efficiency_score: float = 0.0  # Composite 0-100

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "total_earned_usd": round(self.total_earned_usd, 2),
            "avg_completion_hours": round(self.avg_completion_hours, 2),
            "throughput_per_day": round(self.throughput_per_day, 2),
            "earnings_per_hour": round(self.earnings_per_hour, 2),
            "reliability": round(self.reliability, 3),
            "efficiency_score": round(self.efficiency_score, 1),
        }


@dataclass
class StageBottleneck:
    """Identifies a stage where tasks are getting stuck."""
    stage: str
    task_count: int
    avg_time_minutes: float
    sla_limit_minutes: float
    overflow_ratio: float  # avg_time / sla_limit
    blocked_value_usd: float  # Total bounty value stuck in this stage
    severity: str  # low, medium, high, critical

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "task_count": self.task_count,
            "avg_time_minutes": round(self.avg_time_minutes, 1),
            "sla_limit_minutes": round(self.sla_limit_minutes, 1),
            "overflow_ratio": round(self.overflow_ratio, 2),
            "blocked_value_usd": round(self.blocked_value_usd, 2),
            "severity": self.severity,
        }


@dataclass
class CapacityForecast:
    """Swarm capacity planning data."""
    current_utilization: float  # 0-1 (working agents / total agents)
    max_concurrent_tasks: int
    tasks_in_progress: int
    available_capacity: int  # Agents that could take work
    estimated_daily_throughput: float
    time_to_saturation_hours: Optional[float]  # At current intake rate
    recommendation: str  # "healthy", "monitor", "scale_up", "overloaded"

    def to_dict(self) -> dict:
        return {
            "current_utilization": round(self.current_utilization, 3),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "tasks_in_progress": self.tasks_in_progress,
            "available_capacity": self.available_capacity,
            "estimated_daily_throughput": round(self.estimated_daily_throughput, 1),
            "time_to_saturation_hours": (
                round(self.time_to_saturation_hours, 1)
                if self.time_to_saturation_hours is not None
                else None
            ),
            "recommendation": self.recommendation,
        }


@dataclass
class TrendPoint:
    """A data point in a time series."""
    timestamp: str
    value: float
    label: str = ""


@dataclass
class TrendAnalysis:
    """Trend analysis for a metric over time."""
    metric_name: str
    current_value: float
    previous_value: float
    change_pct: float  # Percentage change
    direction: str  # "up", "down", "stable"
    data_points: list[TrendPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "current_value": round(self.current_value, 2),
            "previous_value": round(self.previous_value, 2),
            "change_pct": round(self.change_pct, 1),
            "direction": self.direction,
        }


@dataclass
class AnomalyAlert:
    """An anomaly detected in swarm performance."""
    metric: str
    agent_name: Optional[str]
    severity: str  # info, warning, critical
    description: str
    current_value: float
    expected_range: tuple[float, float]
    detected_at: str

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "agent_name": self.agent_name,
            "severity": self.severity,
            "description": self.description,
            "current_value": round(self.current_value, 2),
            "expected_range": (round(self.expected_range[0], 2), round(self.expected_range[1], 2)),
            "detected_at": self.detected_at,
        }


# ---------------------------------------------------------------------------
# Agent Efficiency Calculator
# ---------------------------------------------------------------------------

def compute_agent_efficiency(
    agent_name: str,
    tasks_completed: int,
    tasks_failed: int,
    total_earned_usd: float,
    completion_times_hours: list[float],
    observation_days: float = 7.0,
) -> AgentEfficiency:
    """Compute efficiency metrics for a single agent.

    The composite efficiency_score (0-100) weights:
      40% reliability
      30% throughput
      20% earnings efficiency
      10% speed
    """
    total_tasks = tasks_completed + tasks_failed
    reliability = tasks_completed / max(total_tasks, 1)

    avg_hours = (
        sum(completion_times_hours) / len(completion_times_hours)
        if completion_times_hours
        else 0
    )

    throughput = tasks_completed / max(observation_days, 0.1)

    total_hours = sum(completion_times_hours) if completion_times_hours else 0
    earnings_per_hour = total_earned_usd / max(total_hours, 0.1)

    # Normalize each factor to 0-1 range with reasonable caps
    reliability_norm = reliability  # Already 0-1

    # Throughput: 1 task/day = 0.5, 5+/day = 1.0
    throughput_norm = min(1.0, throughput / 5.0)

    # Earnings: $5/hour = 0.5, $20+/hour = 1.0
    earnings_norm = min(1.0, earnings_per_hour / 20.0)

    # Speed: 1 hour avg = 1.0, 8+ hours = 0.1
    speed_norm = max(0.1, 1.0 - (avg_hours / 8.0)) if avg_hours > 0 else 0.5

    # Weighted composite
    score = (
        reliability_norm * 40 +
        throughput_norm * 30 +
        earnings_norm * 20 +
        speed_norm * 10
    )

    return AgentEfficiency(
        agent_name=agent_name,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        total_earned_usd=total_earned_usd,
        avg_completion_hours=avg_hours,
        throughput_per_day=throughput,
        earnings_per_hour=earnings_per_hour,
        reliability=reliability,
        efficiency_score=score,
    )


# ---------------------------------------------------------------------------
# Bottleneck Detection
# ---------------------------------------------------------------------------

def detect_bottlenecks(
    stage_times: dict[str, list[float]],  # stage -> [minutes_in_stage, ...]
    stage_slas: dict[str, float],  # stage -> sla_minutes
    stage_values: Optional[dict[str, float]] = None,  # stage -> total_bounty_stuck
) -> list[StageBottleneck]:
    """Detect pipeline bottlenecks where tasks are getting stuck.

    A bottleneck is any stage where:
      - avg time > 50% of SLA (medium)
      - avg time > 100% of SLA (high)
      - avg time > 200% of SLA (critical)

    Returns list sorted by severity (critical first).
    """
    bottlenecks = []

    for stage, times in stage_times.items():
        if not times:
            continue

        sla = stage_slas.get(stage)
        if sla is None or sla <= 0:
            continue

        avg_time = sum(times) / len(times)
        ratio = avg_time / sla

        if ratio < 0.5:
            continue  # Under 50% — no bottleneck

        if ratio >= 2.0:
            severity = "critical"
        elif ratio >= 1.0:
            severity = "high"
        elif ratio >= 0.75:
            severity = "medium"
        else:
            severity = "low"

        value = (stage_values or {}).get(stage, 0.0)

        bottlenecks.append(StageBottleneck(
            stage=stage,
            task_count=len(times),
            avg_time_minutes=avg_time,
            sla_limit_minutes=sla,
            overflow_ratio=ratio,
            blocked_value_usd=value,
            severity=severity,
        ))

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    bottlenecks.sort(key=lambda b: (severity_order.get(b.severity, 4), -b.overflow_ratio))

    return bottlenecks


# ---------------------------------------------------------------------------
# Capacity Forecasting
# ---------------------------------------------------------------------------

def forecast_capacity(
    total_agents: int,
    working_agents: int,
    idle_agents: int,
    offline_agents: int,
    avg_tasks_per_day: float,
    avg_intake_per_day: float,
) -> CapacityForecast:
    """Forecast swarm capacity and saturation.

    Uses current utilization and intake rate to predict when
    the swarm will reach capacity.
    """
    available = total_agents - offline_agents
    utilization = working_agents / max(available, 1)

    available_capacity = idle_agents
    estimated_throughput = avg_tasks_per_day

    # Time to saturation: how long until all agents are busy
    # based on the net intake rate (intake - completion)
    net_intake = avg_intake_per_day - avg_tasks_per_day
    if net_intake > 0 and available_capacity > 0:
        # At current net intake, how long until we run out of idle agents?
        days_to_sat = available_capacity / net_intake
        time_to_saturation = days_to_sat * 24
    else:
        time_to_saturation = None  # Not saturating

    # Recommendation
    if utilization >= 0.9:
        recommendation = "overloaded"
    elif utilization >= 0.7:
        recommendation = "scale_up"
    elif utilization >= 0.4:
        recommendation = "monitor"
    else:
        recommendation = "healthy"

    return CapacityForecast(
        current_utilization=utilization,
        max_concurrent_tasks=available,
        tasks_in_progress=working_agents,
        available_capacity=available_capacity,
        estimated_daily_throughput=estimated_throughput,
        time_to_saturation_hours=time_to_saturation,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------

def compute_trend(
    metric_name: str,
    current_window: list[float],
    previous_window: list[float],
) -> TrendAnalysis:
    """Compare two time windows to determine trend direction.

    current_window: values from the recent period
    previous_window: values from the prior period
    """
    current_avg = sum(current_window) / len(current_window) if current_window else 0
    previous_avg = sum(previous_window) / len(previous_window) if previous_window else 0

    if previous_avg == 0:
        change_pct = 100.0 if current_avg > 0 else 0.0
    else:
        change_pct = ((current_avg - previous_avg) / previous_avg) * 100

    if abs(change_pct) < 5:
        direction = "stable"
    elif change_pct > 0:
        direction = "up"
    else:
        direction = "down"

    return TrendAnalysis(
        metric_name=metric_name,
        current_value=current_avg,
        previous_value=previous_avg,
        change_pct=change_pct,
        direction=direction,
    )


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

def detect_anomalies(
    agent_metrics: dict[str, dict[str, float]],
    now: Optional[datetime] = None,
) -> list[AnomalyAlert]:
    """Detect anomalies across agent metrics using simple statistical methods.

    For each metric, compute mean and std dev across agents.
    Flag agents that are >2 std devs from the mean.

    agent_metrics: {agent_name: {metric_name: value, ...}, ...}
    """
    if now is None:
        now = datetime.now(timezone.utc)

    now_iso = now.isoformat()
    alerts = []

    # Collect all metric names
    all_metrics: set[str] = set()
    for metrics in agent_metrics.values():
        all_metrics.update(metrics.keys())

    for metric in all_metrics:
        values = []
        agent_values: list[tuple[str, float]] = []
        for agent, metrics in agent_metrics.items():
            if metric in metrics:
                v = metrics[metric]
                values.append(v)
                agent_values.append((agent, v))

        if len(values) < 3:
            continue  # Not enough data for anomaly detection

        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0

        if stdev == 0:
            continue  # All values identical

        for agent, value in agent_values:
            z_score = abs(value - mean) / stdev

            if z_score < 2.0:
                continue

            severity = "critical" if z_score >= 3.0 else "warning"
            direction = "above" if value > mean else "below"

            alerts.append(AnomalyAlert(
                metric=metric,
                agent_name=agent,
                severity=severity,
                description=(
                    f"{agent}'s {metric} ({value:.2f}) is {z_score:.1f} std devs "
                    f"{direction} the swarm mean ({mean:.2f})"
                ),
                current_value=value,
                expected_range=(mean - 2 * stdev, mean + 2 * stdev),
                detected_at=now_iso,
            ))

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 3))

    return alerts


# ---------------------------------------------------------------------------
# Cost Optimizer
# ---------------------------------------------------------------------------

@dataclass
class CostAnalysis:
    """Cost-benefit analysis of swarm operations."""
    total_revenue_usd: float
    total_gas_cost_usd: float
    platform_fees_usd: float
    net_profit_usd: float
    profit_margin: float
    cost_per_task_usd: float
    revenue_per_agent_usd: float
    roi: float  # Return on investment (profit / cost)

    def to_dict(self) -> dict:
        return {
            "total_revenue_usd": round(self.total_revenue_usd, 2),
            "total_gas_cost_usd": round(self.total_gas_cost_usd, 2),
            "platform_fees_usd": round(self.platform_fees_usd, 2),
            "net_profit_usd": round(self.net_profit_usd, 2),
            "profit_margin": round(self.profit_margin, 3),
            "cost_per_task_usd": round(self.cost_per_task_usd, 4),
            "revenue_per_agent_usd": round(self.revenue_per_agent_usd, 2),
            "roi": round(self.roi, 2),
        }


def analyze_costs(
    total_revenue_usd: float,
    total_tasks: int,
    total_agents: int,
    gas_cost_per_tx: float = 0.001,  # Base L2 gas is cheap
    transactions_per_task: int = 3,  # escrow + release + reputation
    platform_fee_rate: float = 0.13,  # 13% EM platform fee
) -> CostAnalysis:
    """Analyze the cost efficiency of swarm operations.

    Considers:
      - Gas costs (Base L2 transactions)
      - Platform fees (EM's 13% cut)
      - Revenue distribution
    """
    total_gas = gas_cost_per_tx * transactions_per_task * total_tasks
    platform_fees = total_revenue_usd * platform_fee_rate
    total_cost = total_gas + platform_fees
    net_profit = total_revenue_usd - total_cost

    return CostAnalysis(
        total_revenue_usd=total_revenue_usd,
        total_gas_cost_usd=total_gas,
        platform_fees_usd=platform_fees,
        net_profit_usd=net_profit,
        profit_margin=net_profit / max(total_revenue_usd, 0.01),
        cost_per_task_usd=total_cost / max(total_tasks, 1),
        revenue_per_agent_usd=total_revenue_usd / max(total_agents, 1),
        roi=net_profit / max(total_cost, 0.01),
    )


# ---------------------------------------------------------------------------
# Swarm Analyzer (Unified Interface)
# ---------------------------------------------------------------------------

class SwarmAnalyzer:
    """Unified analytics interface for the KK swarm.

    Combines all analytics functions into a single report generator.
    Accepts pipeline state and lifecycle data as inputs.
    """

    def __init__(
        self,
        pipeline_tasks: Optional[list[dict]] = None,
        lifecycle_agents: Optional[list[dict]] = None,
        observation_days: float = 7.0,
    ):
        self.tasks = pipeline_tasks or []
        self.agents = lifecycle_agents or []
        self.observation_days = observation_days

    def agent_efficiency_report(self) -> list[AgentEfficiency]:
        """Compute efficiency for all agents with task history."""
        # Group tasks by agent
        agent_tasks: dict[str, list[dict]] = {}
        for task in self.tasks:
            agent = task.get("assigned_agent")
            if agent:
                agent_tasks.setdefault(agent, []).append(task)

        efficiencies = []
        for agent_name, tasks in agent_tasks.items():
            completed = [t for t in tasks if t.get("stage") == "completed"]
            failed = [t for t in tasks if t.get("stage") == "failed"]
            earned = sum(t.get("bounty_usd", 0) for t in completed)

            # Extract completion times from events
            times = []
            for t in completed:
                created = t.get("created_at")
                events = t.get("events", [])
                if created and events:
                    try:
                        start = datetime.fromisoformat(created)
                        end = datetime.fromisoformat(events[-1].get("timestamp", created))
                        hours = (end - start).total_seconds() / 3600
                        if 0 < hours < 168:  # Cap at 1 week
                            times.append(hours)
                    except (ValueError, TypeError):
                        pass

            eff = compute_agent_efficiency(
                agent_name=agent_name,
                tasks_completed=len(completed),
                tasks_failed=len(failed),
                total_earned_usd=earned,
                completion_times_hours=times,
                observation_days=self.observation_days,
            )
            efficiencies.append(eff)

        # Sort by efficiency score
        efficiencies.sort(key=lambda e: e.efficiency_score, reverse=True)
        return efficiencies

    # Default SLA targets per pipeline stage (in minutes)
    _DEFAULT_SLA_MINUTES: dict[str, float] = {
        "discovered": 15,
        "evaluated": 5,
        "offered": 10,
        "accepted": 5,
        "in_progress": 240,
        "submitted": 30,
        "under_review": 60,
        "approved": 15,
        "paid": 10,
        "rated": 1440,
    }

    def bottleneck_report(self) -> list[StageBottleneck]:
        """Detect pipeline bottlenecks from task data."""
        stage_times: dict[str, list[float]] = {}
        stage_values: dict[str, float] = {}

        for task in self.tasks:
            stage = task.get("stage", "")
            entered = task.get("stage_entered_at")
            if not entered:
                continue

            try:
                entered_dt = datetime.fromisoformat(entered)
                now = datetime.now(timezone.utc)
                minutes = (now - entered_dt).total_seconds() / 60
                stage_times.setdefault(stage, []).append(minutes)
                stage_values[stage] = stage_values.get(stage, 0) + task.get("bounty_usd", 0)
            except (ValueError, TypeError):
                pass

        return detect_bottlenecks(stage_times, self._DEFAULT_SLA_MINUTES, stage_values)

    def capacity_report(self) -> CapacityForecast:
        """Forecast swarm capacity from lifecycle data."""
        total = len(self.agents)
        working = sum(1 for a in self.agents if a.get("state") == "working")
        idle = sum(1 for a in self.agents if a.get("state") == "idle")
        offline = sum(1 for a in self.agents if a.get("state") in ("offline", "error"))

        # Estimate throughput from completed tasks
        completed = [t for t in self.tasks if t.get("stage") == "completed"]
        completed_count = len(completed)
        avg_tasks_per_day = completed_count / max(self.observation_days, 1)

        # Estimate intake from discovered tasks
        discovered_count = len(self.tasks)
        avg_intake_per_day = discovered_count / max(self.observation_days, 1)

        return forecast_capacity(
            total_agents=total,
            working_agents=working,
            idle_agents=idle,
            offline_agents=offline,
            avg_tasks_per_day=avg_tasks_per_day,
            avg_intake_per_day=avg_intake_per_day,
        )

    def anomaly_report(self) -> list[AnomalyAlert]:
        """Detect anomalies across agent performance."""
        # Build metrics per agent
        agent_metrics: dict[str, dict[str, float]] = {}

        for agent in self.agents:
            name = agent.get("agent_name", agent.get("name", ""))
            if not name:
                continue
            agent_metrics[name] = {
                "total_successes": agent.get("total_successes", 0),
                "total_failures": agent.get("total_failures", 0),
                "consecutive_failures": agent.get("consecutive_failures", 0),
            }

        # Add task-based metrics
        agent_tasks: dict[str, list[dict]] = {}
        for task in self.tasks:
            agent = task.get("assigned_agent")
            if agent:
                agent_tasks.setdefault(agent, []).append(task)

        for name, tasks in agent_tasks.items():
            if name not in agent_metrics:
                agent_metrics[name] = {}
            completed = sum(1 for t in tasks if t.get("stage") == "completed")
            failed = sum(1 for t in tasks if t.get("stage") == "failed")
            agent_metrics[name]["pipeline_completed"] = completed
            agent_metrics[name]["pipeline_failed"] = failed

        return detect_anomalies(agent_metrics)

    def cost_report(self) -> CostAnalysis:
        """Analyze cost efficiency of the swarm."""
        completed = [t for t in self.tasks if t.get("stage") == "completed"]
        total_revenue = sum(t.get("bounty_usd", 0) for t in completed)

        return analyze_costs(
            total_revenue_usd=total_revenue,
            total_tasks=len(completed),
            total_agents=len(self.agents),
        )

    def trend_report(self) -> list[TrendAnalysis]:
        """Compute trends comparing recent vs prior performance.

        Splits the observation period in half and compares.
        """
        # Split tasks by time
        now = datetime.now(timezone.utc)
        midpoint = now - timedelta(days=self.observation_days / 2)

        recent_tasks = []
        prior_tasks = []

        for task in self.tasks:
            created = task.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created)
                if dt >= midpoint:
                    recent_tasks.append(task)
                else:
                    prior_tasks.append(task)
            except (ValueError, TypeError):
                recent_tasks.append(task)  # Default to recent

        trends = []

        # Task volume trend
        trends.append(compute_trend(
            "task_volume",
            [1.0] * len(recent_tasks),
            [1.0] * len(prior_tasks),
        ))

        # Completion rate trend
        recent_completed = sum(1 for t in recent_tasks if t.get("stage") == "completed")
        prior_completed = sum(1 for t in prior_tasks if t.get("stage") == "completed")
        recent_rate = recent_completed / max(len(recent_tasks), 1)
        prior_rate = prior_completed / max(len(prior_tasks), 1)
        trends.append(compute_trend(
            "completion_rate",
            [recent_rate],
            [prior_rate],
        ))

        # Average bounty trend
        recent_bounties = [t.get("bounty_usd", 0) for t in recent_tasks if t.get("bounty_usd", 0) > 0]
        prior_bounties = [t.get("bounty_usd", 0) for t in prior_tasks if t.get("bounty_usd", 0) > 0]
        trends.append(compute_trend(
            "avg_bounty_usd",
            recent_bounties or [0],
            prior_bounties or [0],
        ))

        return trends

    def full_report(self) -> dict:
        """Generate a comprehensive analytics report.

        This is the main entry point for analytics — call this for a
        complete picture of swarm performance.
        """
        efficiencies = self.agent_efficiency_report()
        bottlenecks = self.bottleneck_report()
        capacity = self.capacity_report()
        anomalies = self.anomaly_report()
        costs = self.cost_report()
        trends = self.trend_report()

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "observation_days": self.observation_days,
            "summary": {
                "total_agents": len(self.agents),
                "total_tasks": len(self.tasks),
                "top_agent": efficiencies[0].agent_name if efficiencies else None,
                "top_efficiency": efficiencies[0].efficiency_score if efficiencies else 0,
                "bottleneck_count": len(bottlenecks),
                "critical_bottlenecks": sum(1 for b in bottlenecks if b.severity == "critical"),
                "anomaly_count": len(anomalies),
                "capacity_status": capacity.recommendation,
                "net_profit_usd": costs.net_profit_usd,
                "profit_margin": costs.profit_margin,
            },
            "agent_efficiency": [e.to_dict() for e in efficiencies],
            "bottlenecks": [b.to_dict() for b in bottlenecks],
            "capacity": capacity.to_dict(),
            "anomalies": [a.to_dict() for a in anomalies],
            "costs": costs.to_dict(),
            "trends": [t.to_dict() for t in trends],
        }


# ---------------------------------------------------------------------------
# Report Formatting
# ---------------------------------------------------------------------------

def format_analytics_text(report: dict) -> str:
    """Format an analytics report as human-readable text.

    Suitable for IRC or Telegram delivery.
    """
    lines = []
    summary = report.get("summary", {})

    lines.append("📊 KK Swarm Analytics Report")
    lines.append(f"   Period: {report.get('observation_days', 7)} days")
    lines.append("")

    # Summary
    lines.append(f"🤖 Agents: {summary.get('total_agents', 0)}")
    lines.append(f"📋 Tasks: {summary.get('total_tasks', 0)}")
    lines.append(f"💰 Net Profit: ${summary.get('net_profit_usd', 0):.2f} ({summary.get('profit_margin', 0):.0%} margin)")
    lines.append(f"🏆 Top Agent: {summary.get('top_agent', 'N/A')} (score {summary.get('top_efficiency', 0):.0f}/100)")
    lines.append(f"⚡ Capacity: {summary.get('capacity_status', 'unknown')}")

    # Bottlenecks
    bottlenecks = report.get("bottlenecks", [])
    critical = [b for b in bottlenecks if b.get("severity") in ("critical", "high")]
    if critical:
        lines.append("")
        lines.append("🚨 Bottlenecks:")
        for b in critical[:3]:
            lines.append(
                f"   {b['stage']}: {b['task_count']} tasks stuck "
                f"({b['avg_time_minutes']:.0f}min avg, SLA {b['sla_limit_minutes']:.0f}min)"
            )

    # Anomalies
    anomalies = report.get("anomalies", [])
    critical_anomalies = [a for a in anomalies if a.get("severity") == "critical"]
    if critical_anomalies:
        lines.append("")
        lines.append("⚠️ Anomalies:")
        for a in critical_anomalies[:3]:
            lines.append(f"   {a['description']}")

    # Trends
    trends = report.get("trends", [])
    notable = [t for t in trends if abs(t.get("change_pct", 0)) >= 10]
    if notable:
        lines.append("")
        lines.append("📈 Trends:")
        for t in notable:
            arrow = "↑" if t["direction"] == "up" else "↓" if t["direction"] == "down" else "→"
            lines.append(f"   {arrow} {t['metric_name']}: {t['change_pct']:+.0f}%")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_analytics_report(report: dict, path: Path) -> Path:
    """Save analytics report to timestamped JSON file."""
    path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = path / f"analytics_{ts}.json"
    filepath.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return filepath
