"""
Agent Performance Tracker — Observability and Success Metrics for KK V2 Swarm

Tracks per-agent and swarm-wide performance metrics:
- Task completion rates (success/fail/timeout)
- Average response times
- Reputation trajectory (is the agent improving?)
- Cost efficiency (USD earned per USD spent)
- Category performance (which tasks does each agent excel at?)
- Anomaly detection (sudden drops in performance)

This feeds into the SwarmOrchestrator for better task assignment
and into AutoJob for Skill DNA enrichment.

Usage:
    tracker = AgentPerformanceTracker()
    tracker.record_task_start("aurora", "task_123", "photo_verification")
    # ... agent works ...
    tracker.record_task_complete("aurora", "task_123", success=True, rating=4.8)
    
    # Get metrics
    metrics = tracker.agent_metrics("aurora")
    report = tracker.swarm_report()
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger("kk.performance")


@dataclass
class TaskRecord:
    """Individual task execution record."""
    task_id: str
    agent_id: str
    category: str
    started_at: float  # Unix timestamp
    completed_at: Optional[float] = None
    success: Optional[bool] = None
    rating: Optional[float] = None  # 0-5 or 0-100
    bounty_usd: float = 0.0
    cost_usd: float = 0.0  # API/gas costs for this task
    chain: str = "base"
    error_reason: Optional[str] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None

    @property
    def profit_usd(self) -> float:
        return self.bounty_usd - self.cost_usd

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_seconds"] = self.duration_seconds
        d["profit_usd"] = self.profit_usd
        return d


@dataclass
class AgentMetrics:
    """Aggregated performance metrics for a single agent."""
    agent_id: str
    
    # Task counts
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    timed_out_tasks: int = 0
    
    # Performance
    avg_rating: float = 0.0
    avg_duration_seconds: float = 0.0
    p95_duration_seconds: float = 0.0
    
    # Economics
    total_earned_usd: float = 0.0
    total_cost_usd: float = 0.0
    net_profit_usd: float = 0.0
    
    # Category breakdown
    category_success_rates: Dict[str, float] = field(default_factory=dict)
    category_counts: Dict[str, int] = field(default_factory=dict)
    
    # Trend (last 7 days vs previous 7 days)
    rating_trend: str = "stable"  # "improving", "declining", "stable"
    completion_rate_trend: str = "stable"
    
    # Health signals
    consecutive_failures: int = 0
    last_success_at: Optional[float] = None
    anomaly_flags: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    @property
    def cost_efficiency(self) -> float:
        """ROI: earned per dollar spent."""
        if self.total_cost_usd == 0:
            return float('inf') if self.total_earned_usd > 0 else 0.0
        return self.total_earned_usd / self.total_cost_usd

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_rate"] = round(self.success_rate, 3)
        d["cost_efficiency"] = round(self.cost_efficiency, 2)
        return d


@dataclass
class SwarmReport:
    """Swarm-wide performance report."""
    generated_at: str
    
    # Fleet summary
    total_agents: int = 0
    active_agents: int = 0
    
    # Task summary
    total_tasks: int = 0
    total_successful: int = 0
    total_failed: int = 0
    swarm_success_rate: float = 0.0
    
    # Economics
    total_earned_usd: float = 0.0
    total_cost_usd: float = 0.0
    net_profit_usd: float = 0.0
    
    # Top performers
    top_agents_by_rating: List[dict] = field(default_factory=list)
    top_agents_by_volume: List[dict] = field(default_factory=list)
    top_agents_by_efficiency: List[dict] = field(default_factory=list)
    
    # Problem areas
    struggling_agents: List[dict] = field(default_factory=list)
    underutilized_agents: List[dict] = field(default_factory=list)
    
    # Category insights
    best_category: str = ""
    worst_category: str = ""
    category_breakdown: Dict[str, dict] = field(default_factory=dict)
    
    # Anomalies
    anomalies: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        """Generate human-readable markdown report."""
        lines = [
            f"# KK V2 Swarm Performance Report",
            f"*Generated: {self.generated_at}*",
            "",
            "## Fleet Summary",
            f"- **Active Agents:** {self.active_agents}/{self.total_agents}",
            f"- **Total Tasks:** {self.total_tasks}",
            f"- **Success Rate:** {self.swarm_success_rate:.1%}",
            f"- **Net Profit:** ${self.net_profit_usd:+.2f}",
            "",
            "## Top Performers (by Rating)",
        ]
        for agent in self.top_agents_by_rating[:5]:
            lines.append(
                f"- **{agent['agent_id']}**: {agent['avg_rating']:.1f}/5 "
                f"({agent['total_tasks']} tasks, {agent['success_rate']:.0%} success)"
            )
        
        lines.extend(["", "## Top Performers (by Volume)"])
        for agent in self.top_agents_by_volume[:5]:
            lines.append(
                f"- **{agent['agent_id']}**: {agent['total_tasks']} tasks "
                f"(${agent['total_earned_usd']:.2f} earned)"
            )
        
        if self.struggling_agents:
            lines.extend(["", "## ⚠️ Struggling Agents"])
            for agent in self.struggling_agents:
                lines.append(
                    f"- **{agent['agent_id']}**: {agent['reason']}"
                )
        
        if self.anomalies:
            lines.extend(["", "## 🚨 Anomalies"])
            for anomaly in self.anomalies:
                lines.append(f"- {anomaly}")
        
        lines.extend([
            "",
            "## Category Breakdown",
        ])
        for cat, data in sorted(
            self.category_breakdown.items(),
            key=lambda x: -x[1].get("count", 0)
        ):
            lines.append(
                f"- **{cat}**: {data.get('count', 0)} tasks, "
                f"{data.get('success_rate', 0):.0%} success, "
                f"${data.get('total_earned', 0):.2f} earned"
            )
        
        return "\n".join(lines)


class AgentPerformanceTracker:
    """
    Central performance tracking for the KK V2 Swarm.
    
    Records task-level events and computes aggregate metrics
    for both individual agents and the swarm as a whole.
    """

    ANOMALY_THRESHOLDS = {
        "consecutive_failures": 3,       # Flag after 3 failures in a row
        "rating_drop": 0.5,              # Flag if avg rating drops by 0.5+
        "success_rate_drop": 0.15,       # Flag if success rate drops by 15%+
        "cost_spike": 2.0,               # Flag if cost per task doubles
        "idle_hours": 24,                # Flag if no tasks in 24h
    }

    def __init__(self, persist_path: Optional[str] = None):
        """
        Args:
            persist_path: Optional path to persist records to JSON.
        """
        self.records: List[TaskRecord] = []
        self.active_tasks: Dict[str, TaskRecord] = {}  # task_id → record
        self.persist_path = Path(persist_path) if persist_path else None
        
        # Load existing records if available
        if self.persist_path and self.persist_path.exists():
            self._load()

    # ── Recording ──

    def record_task_start(
        self,
        agent_id: str,
        task_id: str,
        category: str = "general",
        bounty_usd: float = 0.0,
        chain: str = "base",
    ):
        """Record that an agent has started working on a task."""
        record = TaskRecord(
            task_id=task_id,
            agent_id=agent_id,
            category=category,
            started_at=time.time(),
            bounty_usd=bounty_usd,
            chain=chain,
        )
        self.active_tasks[task_id] = record
        logger.debug(f"Task {task_id} started by {agent_id} (category: {category})")

    def record_task_complete(
        self,
        agent_id: str,
        task_id: str,
        success: bool,
        rating: Optional[float] = None,
        cost_usd: float = 0.0,
        error_reason: Optional[str] = None,
    ):
        """Record task completion."""
        record = self.active_tasks.pop(task_id, None)
        
        if record is None:
            # Task wasn't tracked from start — create a retroactive record
            record = TaskRecord(
                task_id=task_id,
                agent_id=agent_id,
                category="unknown",
                started_at=time.time() - 60,  # Assume 1 min ago
            )
        
        record.completed_at = time.time()
        record.success = success
        record.rating = rating
        record.cost_usd = cost_usd
        record.error_reason = error_reason
        
        self.records.append(record)
        self._persist()
        
        logger.info(
            f"Task {task_id} completed by {agent_id}: "
            f"success={success}, rating={rating}, "
            f"duration={record.duration_seconds:.1f}s"
        )

    def record_task_timeout(self, task_id: str, timeout_seconds: float = 600):
        """Record that a task timed out."""
        record = self.active_tasks.pop(task_id, None)
        if record:
            record.completed_at = time.time()
            record.success = False
            record.error_reason = f"Timeout after {timeout_seconds:.0f}s"
            self.records.append(record)
            self._persist()
            logger.warning(f"Task {task_id} timed out for {record.agent_id}")

    # ── Agent Metrics ──

    def agent_metrics(
        self,
        agent_id: str,
        window_days: Optional[int] = None,
    ) -> AgentMetrics:
        """Compute aggregated metrics for a single agent."""
        cutoff = 0.0
        if window_days:
            cutoff = time.time() - (window_days * 86400)
        
        agent_records = [
            r for r in self.records
            if r.agent_id == agent_id and r.started_at >= cutoff
        ]
        
        metrics = AgentMetrics(agent_id=agent_id)
        metrics.total_tasks = len(agent_records)
        
        if not agent_records:
            return metrics
        
        # Counts
        metrics.successful_tasks = sum(1 for r in agent_records if r.success)
        metrics.failed_tasks = sum(1 for r in agent_records if r.success is False)
        metrics.timed_out_tasks = sum(
            1 for r in agent_records
            if r.success is False and r.error_reason and "Timeout" in r.error_reason
        )
        
        # Ratings
        rated = [r.rating for r in agent_records if r.rating is not None]
        if rated:
            metrics.avg_rating = sum(rated) / len(rated)
        
        # Durations
        durations = [
            r.duration_seconds for r in agent_records
            if r.duration_seconds is not None
        ]
        if durations:
            metrics.avg_duration_seconds = sum(durations) / len(durations)
            sorted_durations = sorted(durations)
            p95_idx = int(len(sorted_durations) * 0.95)
            metrics.p95_duration_seconds = sorted_durations[min(p95_idx, len(sorted_durations) - 1)]
        
        # Economics
        metrics.total_earned_usd = sum(r.bounty_usd for r in agent_records if r.success)
        metrics.total_cost_usd = sum(r.cost_usd for r in agent_records)
        metrics.net_profit_usd = metrics.total_earned_usd - metrics.total_cost_usd
        
        # Category breakdown
        category_tasks: Dict[str, List[TaskRecord]] = defaultdict(list)
        for r in agent_records:
            category_tasks[r.category].append(r)
        
        for cat, records in category_tasks.items():
            successful = sum(1 for r in records if r.success)
            metrics.category_success_rates[cat] = successful / len(records) if records else 0
            metrics.category_counts[cat] = len(records)
        
        # Consecutive failures
        for r in reversed(agent_records):
            if r.success:
                break
            metrics.consecutive_failures += 1
        
        # Last success
        successes = [r for r in agent_records if r.success]
        if successes:
            metrics.last_success_at = max(r.completed_at or r.started_at for r in successes)
        
        # Trends (compare last 7 days vs previous 7 days)
        metrics.rating_trend, metrics.completion_rate_trend = self._compute_trends(
            agent_id, agent_records
        )
        
        # Anomaly detection
        metrics.anomaly_flags = self._detect_anomalies(metrics)
        
        return metrics

    def _compute_trends(
        self,
        agent_id: str,
        records: List[TaskRecord],
    ) -> Tuple[str, str]:
        """Compare recent vs earlier performance to detect trends."""
        now = time.time()
        week_ago = now - 7 * 86400
        two_weeks_ago = now - 14 * 86400
        
        recent = [r for r in records if r.started_at >= week_ago]
        earlier = [r for r in records if two_weeks_ago <= r.started_at < week_ago]
        
        if not recent or not earlier:
            return "stable", "stable"
        
        # Rating trend
        recent_ratings = [r.rating for r in recent if r.rating is not None]
        earlier_ratings = [r.rating for r in earlier if r.rating is not None]
        
        rating_trend = "stable"
        if recent_ratings and earlier_ratings:
            recent_avg = sum(recent_ratings) / len(recent_ratings)
            earlier_avg = sum(earlier_ratings) / len(earlier_ratings)
            if recent_avg > earlier_avg + 0.3:
                rating_trend = "improving"
            elif recent_avg < earlier_avg - 0.3:
                rating_trend = "declining"
        
        # Completion rate trend
        recent_success = sum(1 for r in recent if r.success) / len(recent)
        earlier_success = sum(1 for r in earlier if r.success) / len(earlier)
        
        completion_trend = "stable"
        if recent_success > earlier_success + 0.1:
            completion_trend = "improving"
        elif recent_success < earlier_success - 0.1:
            completion_trend = "declining"
        
        return rating_trend, completion_trend

    def _detect_anomalies(self, metrics: AgentMetrics) -> List[str]:
        """Flag anomalous agent behavior."""
        flags = []
        
        if metrics.consecutive_failures >= self.ANOMALY_THRESHOLDS["consecutive_failures"]:
            flags.append(
                f"CONSECUTIVE_FAILURES: {metrics.consecutive_failures} failures in a row"
            )
        
        if metrics.rating_trend == "declining":
            flags.append("RATING_DECLINING: Average rating trending downward")
        
        if metrics.completion_rate_trend == "declining":
            flags.append("COMPLETION_RATE_DECLINING: Success rate trending downward")
        
        if metrics.total_tasks > 5 and metrics.success_rate < 0.5:
            flags.append(
                f"LOW_SUCCESS_RATE: {metrics.success_rate:.0%} success rate "
                f"({metrics.total_tasks} tasks)"
            )
        
        if (
            metrics.last_success_at
            and (time.time() - metrics.last_success_at) > self.ANOMALY_THRESHOLDS["idle_hours"] * 3600
        ):
            hours = (time.time() - metrics.last_success_at) / 3600
            flags.append(f"IDLE: No successful task in {hours:.0f} hours")
        
        return flags

    # ── Swarm Report ──

    def swarm_report(self, window_days: Optional[int] = None) -> SwarmReport:
        """Generate a comprehensive swarm-wide performance report."""
        # Get all unique agents
        all_agents = set(r.agent_id for r in self.records)
        
        report = SwarmReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_agents=len(all_agents),
        )
        
        # Compute per-agent metrics
        agent_metrics_map: Dict[str, AgentMetrics] = {}
        for agent_id in all_agents:
            m = self.agent_metrics(agent_id, window_days)
            agent_metrics_map[agent_id] = m
            
            report.total_tasks += m.total_tasks
            report.total_successful += m.successful_tasks
            report.total_failed += m.failed_tasks
            report.total_earned_usd += m.total_earned_usd
            report.total_cost_usd += m.total_cost_usd
        
        report.net_profit_usd = report.total_earned_usd - report.total_cost_usd
        report.swarm_success_rate = (
            report.total_successful / max(1, report.total_tasks)
        )
        
        # Active agents (had tasks in window)
        report.active_agents = sum(
            1 for m in agent_metrics_map.values() if m.total_tasks > 0
        )
        
        # Top performers by rating
        rated_agents = [
            m for m in agent_metrics_map.values()
            if m.avg_rating > 0 and m.total_tasks >= 3
        ]
        rated_agents.sort(key=lambda m: -m.avg_rating)
        report.top_agents_by_rating = [
            {
                "agent_id": m.agent_id,
                "avg_rating": round(m.avg_rating, 1),
                "total_tasks": m.total_tasks,
                "success_rate": round(m.success_rate, 2),
            }
            for m in rated_agents[:5]
        ]
        
        # Top performers by volume
        volume_agents = sorted(
            agent_metrics_map.values(), key=lambda m: -m.total_tasks
        )
        report.top_agents_by_volume = [
            {
                "agent_id": m.agent_id,
                "total_tasks": m.total_tasks,
                "total_earned_usd": round(m.total_earned_usd, 2),
                "success_rate": round(m.success_rate, 2),
            }
            for m in volume_agents[:5]
        ]
        
        # Top by cost efficiency
        efficient_agents = [
            m for m in agent_metrics_map.values()
            if m.total_cost_usd > 0 and m.total_tasks >= 3
        ]
        efficient_agents.sort(key=lambda m: -m.cost_efficiency)
        report.top_agents_by_efficiency = [
            {
                "agent_id": m.agent_id,
                "cost_efficiency": round(m.cost_efficiency, 2),
                "net_profit_usd": round(m.net_profit_usd, 2),
                "total_tasks": m.total_tasks,
            }
            for m in efficient_agents[:5]
        ]
        
        # Struggling agents
        for m in agent_metrics_map.values():
            if m.anomaly_flags:
                for flag in m.anomaly_flags:
                    report.struggling_agents.append({
                        "agent_id": m.agent_id,
                        "reason": flag,
                    })
        
        # Underutilized agents
        if report.active_agents > 0:
            avg_tasks = report.total_tasks / report.active_agents
            for m in agent_metrics_map.values():
                if m.total_tasks > 0 and m.total_tasks < avg_tasks * 0.25:
                    report.underutilized_agents.append({
                        "agent_id": m.agent_id,
                        "tasks": m.total_tasks,
                        "avg_fleet": round(avg_tasks, 1),
                    })
        
        # Category breakdown
        category_all: Dict[str, List[TaskRecord]] = defaultdict(list)
        cutoff = 0.0
        if window_days:
            cutoff = time.time() - (window_days * 86400)
        for r in self.records:
            if r.started_at >= cutoff:
                category_all[r.category].append(r)
        
        for cat, records in category_all.items():
            successful = sum(1 for r in records if r.success)
            earned = sum(r.bounty_usd for r in records if r.success)
            report.category_breakdown[cat] = {
                "count": len(records),
                "success_rate": round(successful / len(records), 2) if records else 0,
                "total_earned": round(earned, 2),
            }
        
        # Best/worst categories
        if report.category_breakdown:
            cats_with_volume = {
                k: v for k, v in report.category_breakdown.items()
                if v["count"] >= 3
            }
            if cats_with_volume:
                report.best_category = max(
                    cats_with_volume, key=lambda k: cats_with_volume[k]["success_rate"]
                )
                report.worst_category = min(
                    cats_with_volume, key=lambda k: cats_with_volume[k]["success_rate"]
                )
        
        # Anomalies
        all_anomalies = []
        for m in agent_metrics_map.values():
            for flag in m.anomaly_flags:
                all_anomalies.append(f"{m.agent_id}: {flag}")
        report.anomalies = all_anomalies
        
        return report

    # ── Persistence ──

    def _persist(self):
        """Save records to disk."""
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = [r.to_dict() for r in self.records[-10000:]]  # Keep last 10K
            self.persist_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to persist records: {e}")

    def _load(self):
        """Load records from disk."""
        try:
            data = json.loads(self.persist_path.read_text())
            for entry in data:
                record = TaskRecord(
                    task_id=entry["task_id"],
                    agent_id=entry["agent_id"],
                    category=entry.get("category", "unknown"),
                    started_at=entry["started_at"],
                    completed_at=entry.get("completed_at"),
                    success=entry.get("success"),
                    rating=entry.get("rating"),
                    bounty_usd=entry.get("bounty_usd", 0),
                    cost_usd=entry.get("cost_usd", 0),
                    chain=entry.get("chain", "base"),
                    error_reason=entry.get("error_reason"),
                )
                self.records.append(record)
            logger.info(f"Loaded {len(self.records)} records from {self.persist_path}")
        except Exception as e:
            logger.warning(f"Failed to load records: {e}")

    # ── Export ──

    def export_for_autojob(self, agent_id: str) -> List[dict]:
        """Export task records in AutoJob-compatible format.
        
        Returns a list of task dicts that can be fed to 
        em_evidence_parser.build_skill_dna_from_history().
        """
        agent_records = [r for r in self.records if r.agent_id == agent_id and r.success]
        return [
            {
                "task_id": r.task_id,
                "category": r.category,
                "bounty_usd": r.bounty_usd,
                "payment_network": r.chain,
                "status": "completed",
                "created_at": datetime.fromtimestamp(
                    r.started_at, tz=timezone.utc
                ).isoformat(),
            }
            for r in agent_records
        ]
