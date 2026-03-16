"""
Swarm Analytics — Performance Intelligence for Agent Fleets
============================================================

Transforms raw swarm metrics into actionable insights:
- Agent performance scoring and ranking
- Cost efficiency analysis (tokens per task, cost per completion)
- Throughput tracking (tasks/hour, completion velocity)
- Anomaly detection (budget spikes, success rate drops)
- Optimization recommendations (scaling, model selection, rebalancing)
- Historical trend analysis

This is the "brain" that helps the swarm get smarter over time.

Usage:
    analytics = SwarmAnalytics(orchestrator, lifecycle)
    
    # Get a complete performance report
    report = analytics.generate_report()
    
    # Get optimization recommendations
    recs = analytics.get_recommendations()
    
    # Score a specific agent
    score = analytics.score_agent("aurora")
    
    # Detect anomalies
    anomalies = analytics.detect_anomalies()
"""

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════


class PerformanceTier(str, Enum):
    """Agent performance classification."""
    ELITE = "elite"         # Top 10% — highest efficiency
    HIGH = "high"           # Top 25% — consistently strong
    STANDARD = "standard"   # Middle 50% — normal operation
    LOW = "low"             # Bottom 25% — needs attention
    CRITICAL = "critical"   # Bottom 10% — failing, consider retire/retrain


class AnomalyType(str, Enum):
    """Types of anomalies detected in swarm behavior."""
    BUDGET_SPIKE = "budget_spike"       # Agent spending unusually fast
    SUCCESS_DROP = "success_drop"       # Success rate fell significantly
    IDLE_AGENT = "idle_agent"          # Agent active but doing nothing
    OVERLOADED = "overloaded"          # Agent handling too many tasks
    TOKEN_WASTE = "token_waste"        # High token usage, low completion
    COST_ANOMALY = "cost_anomaly"      # Per-task cost much higher than fleet avg


class RecommendationType(str, Enum):
    """Types of optimization recommendations."""
    SCALE_DOWN = "scale_down"          # Sleep underutilized agents
    SCALE_UP = "scale_up"             # Wake more agents for demand
    REBALANCE = "rebalance"           # Redistribute tasks across agents
    MODEL_SWITCH = "model_switch"      # Suggest cheaper/better model
    RETIRE = "retire"                  # Agent consistently underperforming
    BUDGET_ADJUST = "budget_adjust"    # Adjust daily budget allocation
    SKILL_GAP = "skill_gap"           # Fleet missing key capabilities


@dataclass
class AgentPerformanceScore:
    """Comprehensive performance score for one agent."""
    agent_id: str
    overall_score: float = 0.0        # 0-100 composite score
    efficiency_score: float = 0.0     # tasks completed / tokens used
    reliability_score: float = 0.0    # success rate + uptime
    speed_score: float = 0.0          # avg completion time
    cost_score: float = 0.0           # cost per completed task
    utilization_score: float = 0.0    # how busy vs idle
    tier: PerformanceTier = PerformanceTier.STANDARD
    
    # Raw data
    tasks_assigned: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tokens_used: int = 0
    usd_spent: float = 0.0
    usd_earned: float = 0.0
    avg_task_duration_sec: float = 0.0
    uptime_pct: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "overall_score": round(self.overall_score, 1),
            "scores": {
                "efficiency": round(self.efficiency_score, 1),
                "reliability": round(self.reliability_score, 1),
                "speed": round(self.speed_score, 1),
                "cost": round(self.cost_score, 1),
                "utilization": round(self.utilization_score, 1),
            },
            "tier": self.tier.value,
            "tasks": {
                "assigned": self.tasks_assigned,
                "completed": self.tasks_completed,
                "failed": self.tasks_failed,
                "success_rate": self.tasks_completed / max(self.tasks_assigned, 1),
            },
            "economics": {
                "tokens_used": self.tokens_used,
                "usd_spent": round(self.usd_spent, 4),
                "usd_earned": round(self.usd_earned, 4),
                "net": round(self.usd_earned - self.usd_spent, 4),
                "cost_per_task": round(
                    self.usd_spent / max(self.tasks_completed, 1), 4
                ),
            },
        }


@dataclass
class Anomaly:
    """A detected anomaly in swarm behavior."""
    anomaly_type: AnomalyType
    agent_id: Optional[str]        # None for fleet-wide anomalies
    severity: str                  # info, warning, critical
    message: str
    value: float                   # The anomalous value
    threshold: float              # The threshold it exceeded
    detected_at: str = ""
    
    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return {
            "type": self.anomaly_type.value,
            "agent_id": self.agent_id,
            "severity": self.severity,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "detected_at": self.detected_at,
        }


@dataclass
class Recommendation:
    """An optimization recommendation."""
    rec_type: RecommendationType
    priority: str                  # low, medium, high, critical
    agent_id: Optional[str]
    message: str
    expected_impact: str          # e.g., "Save ~$0.50/day"
    action: str                    # Specific action to take
    
    def to_dict(self) -> dict:
        return {
            "type": self.rec_type.value,
            "priority": self.priority,
            "agent_id": self.agent_id,
            "message": self.message,
            "expected_impact": self.expected_impact,
            "action": self.action,
        }


@dataclass
class SwarmReport:
    """Complete swarm performance report."""
    generated_at: str = ""
    period: str = "today"
    
    # Fleet summary
    total_agents: int = 0
    active_agents: int = 0
    total_tasks_assigned: int = 0
    total_tasks_completed: int = 0
    fleet_success_rate: float = 0.0
    total_tokens_used: int = 0
    total_usd_spent: float = 0.0
    total_usd_earned: float = 0.0
    net_pnl: float = 0.0
    
    # Performance breakdown
    agent_scores: List[AgentPerformanceScore] = field(default_factory=list)
    tier_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Intelligence
    anomalies: List[Anomaly] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    
    # Efficiency metrics
    avg_tokens_per_task: float = 0.0
    avg_cost_per_task: float = 0.0
    avg_task_duration_sec: float = 0.0
    budget_utilization_pct: float = 0.0
    
    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "period": self.period,
            "fleet": {
                "total_agents": self.total_agents,
                "active_agents": self.active_agents,
                "tasks_assigned": self.total_tasks_assigned,
                "tasks_completed": self.total_tasks_completed,
                "success_rate": round(self.fleet_success_rate, 3),
                "tokens_used": self.total_tokens_used,
                "usd_spent": round(self.total_usd_spent, 4),
                "usd_earned": round(self.total_usd_earned, 4),
                "net_pnl": round(self.net_pnl, 4),
            },
            "efficiency": {
                "avg_tokens_per_task": round(self.avg_tokens_per_task, 0),
                "avg_cost_per_task": round(self.avg_cost_per_task, 4),
                "avg_task_duration_sec": round(self.avg_task_duration_sec, 1),
                "budget_utilization_pct": round(self.budget_utilization_pct, 1),
            },
            "tier_distribution": self.tier_distribution,
            "agent_scores": [s.to_dict() for s in self.agent_scores],
            "anomalies": [a.to_dict() for a in self.anomalies],
            "recommendations": [r.to_dict() for r in self.recommendations],
        }
    
    def to_markdown(self) -> str:
        """Generate a Markdown summary for Telegram/docs."""
        lines = [
            f"# 🐝 Swarm Performance Report",
            f"*Generated: {self.generated_at[:16]} UTC*",
            "",
            "## Fleet Summary",
            f"- **Agents:** {self.active_agents}/{self.total_agents} active",
            f"- **Tasks:** {self.total_tasks_completed}/{self.total_tasks_assigned} completed "
            f"({self.fleet_success_rate*100:.1f}%)",
            f"- **Net P&L:** ${self.net_pnl:.2f} "
            f"(earned ${self.total_usd_earned:.2f}, spent ${self.total_usd_spent:.2f})",
            "",
            "## Efficiency",
            f"- Avg tokens/task: {self.avg_tokens_per_task:,.0f}",
            f"- Avg cost/task: ${self.avg_cost_per_task:.4f}",
            f"- Budget utilization: {self.budget_utilization_pct:.0f}%",
            "",
        ]
        
        if self.agent_scores:
            lines.append("## Top Performers")
            top = sorted(self.agent_scores, key=lambda s: -s.overall_score)[:5]
            for i, s in enumerate(top, 1):
                emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
                lines.append(
                    f"{emoji} **{s.agent_id}** — {s.overall_score:.0f}/100 "
                    f"({s.tier.value}) | {s.tasks_completed} tasks | "
                    f"${s.usd_earned - s.usd_spent:.4f} net"
                )
            lines.append("")
        
        if self.anomalies:
            lines.append("## ⚠️ Anomalies")
            for a in self.anomalies:
                sev_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(
                    a.severity, "❓"
                )
                lines.append(f"- {sev_emoji} {a.message}")
            lines.append("")
        
        if self.recommendations:
            lines.append("## 💡 Recommendations")
            for r in self.recommendations:
                pri_emoji = {
                    "low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"
                }.get(r.priority, "⚪")
                lines.append(f"- {pri_emoji} **{r.message}** — {r.expected_impact}")
            lines.append("")
        
        return "\n".join(lines)


# ══════════════════════════════════════════════
# Analytics Engine
# ══════════════════════════════════════════════


class SwarmAnalytics:
    """
    Performance intelligence engine for agent swarms.
    
    Takes raw data from the orchestrator and lifecycle manager
    and produces actionable insights.
    """
    
    # Score weights (must sum to 1.0)
    WEIGHTS = {
        "efficiency": 0.25,
        "reliability": 0.30,
        "speed": 0.15,
        "cost": 0.20,
        "utilization": 0.10,
    }
    
    # Tier thresholds (overall_score)
    TIER_THRESHOLDS = {
        PerformanceTier.ELITE: 85,
        PerformanceTier.HIGH: 70,
        PerformanceTier.STANDARD: 45,
        PerformanceTier.LOW: 25,
        PerformanceTier.CRITICAL: 0,
    }
    
    # Anomaly thresholds
    BUDGET_SPIKE_THRESHOLD = 0.9     # >90% budget used
    SUCCESS_DROP_THRESHOLD = 0.7     # <70% success rate
    IDLE_THRESHOLD_MINUTES = 30      # No tasks in 30 min while active
    OVERLOAD_THRESHOLD = 5           # >5 concurrent tasks
    TOKEN_WASTE_RATIO = 50000        # >50K tokens per task
    COST_ANOMALY_MULTIPLIER = 3.0    # >3x fleet average cost/task
    
    def __init__(self, orchestrator=None, lifecycle=None):
        """
        Args:
            orchestrator: SwarmOrchestrator instance
            lifecycle: LifecycleManager instance
        """
        self.orchestrator = orchestrator
        self.lifecycle = lifecycle
        self._history: List[SwarmReport] = []
    
    # ── Agent Scoring ──
    
    def score_agent(self, agent_id: str) -> AgentPerformanceScore:
        """
        Calculate comprehensive performance score for an agent.
        
        Scoring Formula:
            overall = (efficiency × 0.25) + (reliability × 0.30) +
                      (speed × 0.15) + (cost × 0.20) + (utilization × 0.10)
        
        Each component is normalized to 0-100.
        """
        score = AgentPerformanceScore(agent_id=agent_id)
        
        # Get agent data from lifecycle
        agent = self.lifecycle.agents.get(agent_id) if self.lifecycle else None
        profile = (
            self.orchestrator.profiles.get(agent_id)
            if self.orchestrator else None
        )
        
        if not agent:
            return score
        
        # Gather raw data
        score.tasks_assigned = getattr(agent, "total_tasks_completed", 0) + \
                              getattr(agent, "total_tasks_failed", 0)
        score.tasks_completed = getattr(agent, "total_tasks_completed", 0)
        score.tasks_failed = getattr(agent, "total_tasks_failed", 0)
        
        if agent.usage:
            score.tokens_used = agent.usage.tokens_today
            score.usd_spent = agent.usage.usd_spent_today
        
        if profile:
            score.usd_earned = getattr(profile, "total_earned_usd", 0.0)
        
        # Calculate component scores
        score.efficiency_score = self._calc_efficiency(score)
        score.reliability_score = self._calc_reliability(score, agent)
        score.speed_score = self._calc_speed(score)
        score.cost_score = self._calc_cost(score)
        score.utilization_score = self._calc_utilization(score, agent)
        
        # Weighted composite
        score.overall_score = (
            score.efficiency_score * self.WEIGHTS["efficiency"] +
            score.reliability_score * self.WEIGHTS["reliability"] +
            score.speed_score * self.WEIGHTS["speed"] +
            score.cost_score * self.WEIGHTS["cost"] +
            score.utilization_score * self.WEIGHTS["utilization"]
        )
        
        # Assign tier
        score.tier = self._classify_tier(score.overall_score)
        
        return score
    
    def score_all_agents(self) -> List[AgentPerformanceScore]:
        """Score all agents in the swarm."""
        if not self.lifecycle:
            return []
        return [
            self.score_agent(agent_id)
            for agent_id in self.lifecycle.agents
        ]
    
    # ── Anomaly Detection ──
    
    def detect_anomalies(self) -> List[Anomaly]:
        """
        Scan the swarm for anomalous behavior.
        
        Checks:
        - Budget spikes (agent spending too fast)
        - Success rate drops
        - Idle agents (active but no tasks)
        - Token waste (high usage, low output)
        - Cost anomalies (much higher than fleet average)
        """
        anomalies = []
        
        if not self.lifecycle or not self.orchestrator:
            return anomalies
        
        # Fleet-wide stats for comparison
        fleet_stats = self._fleet_stats()
        
        for agent_id, agent in self.lifecycle.agents.items():
            if agent.status.value != "active":
                continue
            
            profile = self.orchestrator.profiles.get(agent_id)
            
            # Budget spike detection
            if agent.budget and agent.usage:
                budget_pct = (
                    agent.usage.usd_spent_today / 
                    max(agent.budget.max_usd_spend_per_day, 0.01)
                )
                if budget_pct > self.BUDGET_SPIKE_THRESHOLD:
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.BUDGET_SPIKE,
                        agent_id=agent_id,
                        severity="warning" if budget_pct < 0.95 else "critical",
                        message=f"Agent {agent_id} at {budget_pct*100:.0f}% daily budget",
                        value=budget_pct,
                        threshold=self.BUDGET_SPIKE_THRESHOLD,
                    ))
            
            # Success rate drop
            total = getattr(agent, "total_tasks_completed", 0) + \
                    getattr(agent, "total_tasks_failed", 0)
            if total >= 3:  # Need at least 3 tasks for meaningful rate
                success_rate = getattr(agent, "total_tasks_completed", 0) / total
                if success_rate < self.SUCCESS_DROP_THRESHOLD:
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.SUCCESS_DROP,
                        agent_id=agent_id,
                        severity="warning" if success_rate > 0.5 else "critical",
                        message=f"Agent {agent_id} success rate at {success_rate*100:.0f}% "
                                f"({total} tasks)",
                        value=success_rate,
                        threshold=self.SUCCESS_DROP_THRESHOLD,
                    ))
            
            # Token waste detection
            completed = getattr(agent, "total_tasks_completed", 0)
            if completed > 0 and agent.usage:
                tokens_per_task = agent.usage.tokens_today / completed
                if tokens_per_task > self.TOKEN_WASTE_RATIO:
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.TOKEN_WASTE,
                        agent_id=agent_id,
                        severity="warning",
                        message=f"Agent {agent_id} using {tokens_per_task:,.0f} tokens/task "
                                f"(threshold: {self.TOKEN_WASTE_RATIO:,})",
                        value=tokens_per_task,
                        threshold=self.TOKEN_WASTE_RATIO,
                    ))
            
            # Cost anomaly (compared to fleet average)
            if completed > 0 and agent.usage and fleet_stats["avg_cost_per_task"] > 0:
                cost_per_task = agent.usage.usd_spent_today / completed
                if cost_per_task > fleet_stats["avg_cost_per_task"] * self.COST_ANOMALY_MULTIPLIER:
                    anomalies.append(Anomaly(
                        anomaly_type=AnomalyType.COST_ANOMALY,
                        agent_id=agent_id,
                        severity="warning",
                        message=f"Agent {agent_id} costs ${cost_per_task:.4f}/task "
                                f"(fleet avg: ${fleet_stats['avg_cost_per_task']:.4f})",
                        value=cost_per_task,
                        threshold=fleet_stats["avg_cost_per_task"] * self.COST_ANOMALY_MULTIPLIER,
                    ))
        
        # Fleet-wide anomalies
        health = self.lifecycle.health_check()
        if health["active"] == 0 and health["total_agents"] > 0:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.IDLE_AGENT,
                agent_id=None,
                severity="critical",
                message="No active agents! Swarm is offline.",
                value=0,
                threshold=1,
            ))
        
        return anomalies
    
    # ── Recommendations ──
    
    def get_recommendations(self) -> List[Recommendation]:
        """
        Generate optimization recommendations based on current state.
        
        Analyzes:
        - Agent utilization patterns
        - Cost efficiency
        - Skill coverage gaps
        - Model selection optimization
        - Scaling decisions
        """
        recs = []
        
        if not self.lifecycle or not self.orchestrator:
            return recs
        
        scores = self.score_all_agents()
        health = self.lifecycle.health_check()
        fleet_stats = self._fleet_stats()
        
        # 1. Scale down: Sleep underperforming agents to save budget
        critical_agents = [s for s in scores if s.tier == PerformanceTier.CRITICAL]
        if critical_agents:
            for agent_score in critical_agents:
                recs.append(Recommendation(
                    rec_type=RecommendationType.RETIRE,
                    priority="high",
                    agent_id=agent_score.agent_id,
                    message=f"Agent {agent_score.agent_id} in critical tier "
                            f"(score: {agent_score.overall_score:.0f}/100)",
                    expected_impact=f"Save ~${agent_score.usd_spent:.2f}/day",
                    action=f"Sleep or retire agent {agent_score.agent_id}",
                ))
        
        # 2. Budget rebalancing: Move budget from underutilized to overloaded
        low_util = [s for s in scores if s.utilization_score < 20 and s.tasks_assigned == 0]
        if len(low_util) > 3:
            total_wasted = sum(
                s.usd_spent for s in low_util 
                if hasattr(s, 'usd_spent')
            )
            recs.append(Recommendation(
                rec_type=RecommendationType.SCALE_DOWN,
                priority="medium",
                agent_id=None,
                message=f"{len(low_util)} agents with zero tasks today",
                expected_impact=f"Sleep idle agents to save ~${total_wasted:.2f}/day",
                action="Sleep agents with no tasks for >2 hours",
            ))
        
        # 3. Model switch: Agents on expensive models with simple tasks
        for agent_id, agent in self.lifecycle.agents.items():
            if (agent.model and "sonnet" in agent.model and 
                getattr(agent, "total_tasks_completed", 0) > 0):
                score = next((s for s in scores if s.agent_id == agent_id), None)
                if score and score.cost_score < 30:
                    recs.append(Recommendation(
                        rec_type=RecommendationType.MODEL_SWITCH,
                        priority="medium",
                        agent_id=agent_id,
                        message=f"Agent {agent_id} on Sonnet with low cost efficiency",
                        expected_impact="Switching to Haiku could reduce costs by ~80%",
                        action=f"Switch {agent_id} from Sonnet to Haiku for data tasks",
                    ))
        
        # 4. Scale up: If demand exceeds capacity
        metrics = self.orchestrator.metrics()
        if metrics["tasks"]["active"] > health["active"] * 2:
            sleeping = health.get("sleeping", 0)
            if sleeping > 0:
                recs.append(Recommendation(
                    rec_type=RecommendationType.SCALE_UP,
                    priority="high",
                    agent_id=None,
                    message=f"{metrics['tasks']['active']} active tasks with only "
                            f"{health['active']} agents",
                    expected_impact=f"Wake {min(sleeping, 3)} sleeping agents to reduce queue",
                    action="Wake sleeping agents to handle task backlog",
                ))
        
        # 5. Budget adjustment: Consistently hitting limits
        for agent_id, agent in self.lifecycle.agents.items():
            if agent.budget and agent.usage:
                util = (
                    agent.usage.usd_spent_today /
                    max(agent.budget.max_usd_spend_per_day, 0.01)
                )
                if util > 0.95 and getattr(agent, "total_tasks_completed", 0) > 0:
                    recs.append(Recommendation(
                        rec_type=RecommendationType.BUDGET_ADJUST,
                        priority="medium",
                        agent_id=agent_id,
                        message=f"Agent {agent_id} at {util*100:.0f}% budget "
                                f"with tasks still pending",
                        expected_impact="Increase budget by 50% to avoid throttling",
                        action=f"Raise {agent_id} daily budget from "
                               f"${agent.budget.max_usd_spend_per_day:.2f} to "
                               f"${agent.budget.max_usd_spend_per_day * 1.5:.2f}",
                    ))
        
        return recs
    
    # ── Report Generation ──
    
    def generate_report(self, period: str = "today") -> SwarmReport:
        """
        Generate a complete swarm performance report.
        
        Args:
            period: "today", "week", or "all"
            
        Returns:
            SwarmReport with all metrics, scores, anomalies, and recommendations
        """
        report = SwarmReport(period=period)
        
        if not self.lifecycle or not self.orchestrator:
            return report
        
        health = self.lifecycle.health_check()
        metrics = self.orchestrator.metrics()
        economics = self.orchestrator.economic_summary()
        
        # Fleet summary
        report.total_agents = health["total_agents"]
        report.active_agents = health["active"]
        report.total_tasks_assigned = metrics["tasks"]["total_assigned"]
        report.total_tasks_completed = metrics["tasks"]["total_completed"]
        report.fleet_success_rate = metrics["tasks"]["success_rate"]
        report.total_usd_spent = economics["total_spent_usd"]
        report.total_usd_earned = economics["total_earned_usd"]
        report.net_pnl = economics["net_usd"]
        
        # Calculate fleet-wide token usage
        total_tokens = 0
        for agent_id, agent in self.lifecycle.agents.items():
            if agent.usage:
                total_tokens += agent.usage.tokens_today
        report.total_tokens_used = total_tokens
        
        # Efficiency metrics
        completed = max(report.total_tasks_completed, 1)
        report.avg_tokens_per_task = total_tokens / completed
        report.avg_cost_per_task = report.total_usd_spent / completed
        report.budget_utilization_pct = (
            1 - health["budget_remaining_pct"]
        ) * 100
        
        # Score all agents
        report.agent_scores = self.score_all_agents()
        report.agent_scores.sort(key=lambda s: -s.overall_score)
        
        # Tier distribution
        tier_dist = {}
        for score in report.agent_scores:
            tier = score.tier.value
            tier_dist[tier] = tier_dist.get(tier, 0) + 1
        report.tier_distribution = tier_dist
        
        # Anomalies and recommendations
        report.anomalies = self.detect_anomalies()
        report.recommendations = self.get_recommendations()
        
        # Store in history
        self._history.append(report)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        
        return report
    
    # ── Comparison & Trends ──
    
    def compare_periods(
        self, 
        current: SwarmReport, 
        previous: SwarmReport,
    ) -> dict:
        """
        Compare two report periods and calculate deltas.
        
        Returns:
            dict with changes in key metrics
        """
        def pct_change(new, old):
            if old == 0:
                return 100.0 if new > 0 else 0.0
            return ((new - old) / old) * 100
        
        return {
            "tasks_completed_delta": (
                current.total_tasks_completed - previous.total_tasks_completed
            ),
            "success_rate_delta": (
                current.fleet_success_rate - previous.fleet_success_rate
            ),
            "cost_delta_usd": (
                current.total_usd_spent - previous.total_usd_spent
            ),
            "earnings_delta_usd": (
                current.total_usd_earned - previous.total_usd_earned
            ),
            "pnl_delta_usd": (
                current.net_pnl - previous.net_pnl
            ),
            "efficiency_change_pct": pct_change(
                current.avg_cost_per_task, 
                previous.avg_cost_per_task
            ),
            "active_agents_delta": (
                current.active_agents - previous.active_agents
            ),
        }
    
    # ── Private Helpers ──
    
    def _calc_efficiency(self, score: AgentPerformanceScore) -> float:
        """
        Efficiency = completed tasks / tokens used.
        Higher = better. Normalized to 0-100.
        """
        if score.tokens_used == 0:
            return 50.0  # No data — neutral score
        
        tasks_per_1k_tokens = (score.tasks_completed * 1000) / score.tokens_used
        # Benchmark: 1 task per 5K tokens = 100, 1 per 50K = 10
        return min(100, max(0, tasks_per_1k_tokens * 500))
    
    def _calc_reliability(
        self, score: AgentPerformanceScore, agent
    ) -> float:
        """
        Reliability = success rate + uptime stability.
        """
        total = score.tasks_assigned
        if total == 0:
            return 50.0  # No data
        
        success_rate = score.tasks_completed / total
        
        # Penalize consecutive failures
        consecutive = getattr(agent, "consecutive_failures", 0)
        penalty = min(30, consecutive * 10)
        
        return min(100, max(0, success_rate * 100 - penalty))
    
    def _calc_speed(self, score: AgentPerformanceScore) -> float:
        """
        Speed score based on average task duration.
        Lower duration = higher score.
        """
        if score.avg_task_duration_sec == 0:
            return 50.0  # No data
        
        # Benchmark: 30s = 100, 300s = 50, 600s+ = 10
        if score.avg_task_duration_sec <= 30:
            return 100.0
        elif score.avg_task_duration_sec <= 300:
            return 100 - (score.avg_task_duration_sec - 30) / 270 * 50
        else:
            return max(10, 50 - (score.avg_task_duration_sec - 300) / 300 * 40)
    
    def _calc_cost(self, score: AgentPerformanceScore) -> float:
        """
        Cost efficiency = earnings / spending ratio.
        Higher earnings relative to spending = better.
        """
        if score.usd_spent == 0:
            return 50.0  # No data
        
        if score.tasks_completed == 0:
            return 10.0  # Spending without completing = bad
        
        cost_per_task = score.usd_spent / score.tasks_completed
        
        # Benchmark: <$0.001/task = 100, $0.01 = 50, $0.10+ = 10
        if cost_per_task < 0.001:
            return 100.0
        elif cost_per_task < 0.01:
            return 100 - (cost_per_task - 0.001) / 0.009 * 50
        elif cost_per_task < 0.10:
            return 50 - (cost_per_task - 0.01) / 0.09 * 40
        else:
            return max(0, 10 - (cost_per_task - 0.10) / 0.10 * 10)
    
    def _calc_utilization(
        self, score: AgentPerformanceScore, agent
    ) -> float:
        """
        Utilization = how busy the agent is vs idle.
        Based on tasks assigned relative to budget capacity.
        """
        if not agent.budget:
            return 50.0
        
        max_tasks = agent.budget.max_tasks_per_day
        if max_tasks == 0:
            return 50.0
        
        utilization = score.tasks_assigned / max_tasks
        
        # Sweet spot is 50-80% utilization
        if utilization < 0.1:
            return 20.0  # Underutilized
        elif utilization < 0.5:
            return 20 + (utilization - 0.1) / 0.4 * 60
        elif utilization <= 0.8:
            return 80 + (utilization - 0.5) / 0.3 * 20
        elif utilization <= 1.0:
            return 90.0  # Slightly over-utilized but OK
        else:
            return max(50, 90 - (utilization - 1.0) * 100)  # Overloaded
    
    def _classify_tier(self, overall_score: float) -> PerformanceTier:
        """Classify an overall score into a performance tier."""
        for tier, threshold in self.TIER_THRESHOLDS.items():
            if overall_score >= threshold:
                return tier
        return PerformanceTier.CRITICAL
    
    def _fleet_stats(self) -> dict:
        """Calculate fleet-wide stats for anomaly comparison."""
        total_spent = 0.0
        total_completed = 0
        active_count = 0
        
        for agent_id, agent in self.lifecycle.agents.items():
            if agent.status.value != "active":
                continue
            active_count += 1
            if agent.usage:
                total_spent += agent.usage.usd_spent_today
            total_completed += getattr(agent, "total_tasks_completed", 0)
        
        return {
            "total_spent": total_spent,
            "total_completed": total_completed,
            "active_count": active_count,
            "avg_cost_per_task": (
                total_spent / max(total_completed, 1)
            ),
        }
