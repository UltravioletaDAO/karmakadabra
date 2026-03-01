"""
Karma Kadabra V2 — Agent Profiler

Analyzes individual agent performance to generate:
  1. Skill profiles (what each agent is good/bad at)
  2. Efficiency ratings (cost per successful task)
  3. Improvement recommendations (which skills to develop)
  4. Optimal task routing suggestions (which agent for which task)
  5. Fleet-wide analytics (team composition, coverage gaps)

This is the intelligence layer that makes the swarm self-improving.
The profiler reads from evidence/performance data and produces
actionable insights for the coordinator.

Usage:
    profiler = AgentProfiler(workspaces_dir)
    profile = profiler.analyze_agent("aurora")
    fleet = profiler.analyze_fleet()
    recs = profiler.recommendations("aurora")
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kk.profiler")


# ═══════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SkillRating:
    """Rating for a specific skill category."""

    category: str
    tasks_completed: int = 0
    tasks_approved: int = 0
    tasks_rejected: int = 0
    avg_rating: float = 0.0
    total_cost_usd: float = 0.0
    total_revenue_usd: float = 0.0
    avg_duration_ms: int = 0
    trend: str = "stable"  # "improving", "stable", "declining"

    @property
    def success_rate(self) -> float:
        if self.tasks_completed == 0:
            return 0.0
        return self.tasks_approved / self.tasks_completed

    @property
    def profit_per_task(self) -> float:
        if self.tasks_completed == 0:
            return 0.0
        return (self.total_revenue_usd - self.total_cost_usd) / self.tasks_completed

    @property
    def margin_pct(self) -> float:
        if self.total_revenue_usd == 0:
            return -100.0
        return ((self.total_revenue_usd - self.total_cost_usd) / self.total_revenue_usd) * 100


@dataclass
class AgentProfile:
    """Complete performance profile for one agent."""

    agent_name: str
    agent_id: Optional[int] = None
    wallet_address: Optional[str] = None

    # Aggregate stats
    total_tasks: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    total_revenue_usd: float = 0.0
    total_cost_usd: float = 0.0
    active_since: Optional[str] = None
    last_task_at: Optional[str] = None

    # Skills breakdown
    skills: dict[str, SkillRating] = field(default_factory=dict)

    # Computed scores
    reliability_score: float = 0.0   # 0-100
    efficiency_score: float = 0.0    # 0-100 (revenue per cost unit)
    versatility_score: float = 0.0   # 0-100 (breadth of skills)
    overall_score: float = 0.0       # 0-100 (weighted composite)

    # Recommendations
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.total_approved / self.total_tasks

    @property
    def total_profit(self) -> float:
        return self.total_revenue_usd - self.total_cost_usd

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "agent_id": self.agent_id,
            "total_tasks": self.total_tasks,
            "total_approved": self.total_approved,
            "total_rejected": self.total_rejected,
            "success_rate": round(self.success_rate, 3),
            "total_revenue_usd": round(self.total_revenue_usd, 4),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_profit_usd": round(self.total_profit, 4),
            "reliability_score": round(self.reliability_score, 1),
            "efficiency_score": round(self.efficiency_score, 1),
            "versatility_score": round(self.versatility_score, 1),
            "overall_score": round(self.overall_score, 1),
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations,
            "skills": {
                k: {
                    "tasks": v.tasks_completed,
                    "approved": v.tasks_approved,
                    "success_rate": round(v.success_rate, 3),
                    "profit_per_task": round(v.profit_per_task, 4),
                    "trend": v.trend,
                }
                for k, v in self.skills.items()
            },
        }


@dataclass
class FleetAnalysis:
    """Fleet-wide analytics across all agents."""

    total_agents: int = 0
    active_agents: int = 0
    total_tasks: int = 0
    total_revenue_usd: float = 0.0
    total_cost_usd: float = 0.0
    avg_success_rate: float = 0.0
    category_coverage: dict[str, int] = field(default_factory=dict)
    coverage_gaps: list[str] = field(default_factory=list)
    top_performers: list[str] = field(default_factory=list)
    underperformers: list[str] = field(default_factory=list)
    fleet_recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_agents": self.total_agents,
            "active_agents": self.active_agents,
            "total_tasks": self.total_tasks,
            "total_revenue_usd": round(self.total_revenue_usd, 4),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_profit_usd": round(self.total_revenue_usd - self.total_cost_usd, 4),
            "avg_success_rate": round(self.avg_success_rate, 3),
            "category_coverage": self.category_coverage,
            "coverage_gaps": self.coverage_gaps,
            "top_performers": self.top_performers,
            "underperformers": self.underperformers,
            "fleet_recommendations": self.fleet_recommendations,
        }


# ═══════════════════════════════════════════════════════════════════
# Agent Profiler
# ═══════════════════════════════════════════════════════════════════


# All known task categories (from EM API)
ALL_CATEGORIES = [
    "knowledge_access",
    "content_creation",
    "data_collection",
    "code_review",
    "research",
    "translation",
    "testing",
    "photo_verification",
    "physical_presence",
]


class AgentProfiler:
    """
    Analyzes agent performance and generates actionable profiles.

    Data sources:
      - performance.json in each agent workspace
      - evidence_history.json in each workspace
      - WORKING.md state files
    """

    def __init__(self, workspaces_dir: str = "./workspaces"):
        self.workspaces_dir = Path(workspaces_dir)
        self._profiles: dict[str, AgentProfile] = {}

    def _discover_agents(self) -> list[str]:
        """Find all agent workspaces."""
        if not self.workspaces_dir.exists():
            return []
        agents = []
        for d in sorted(self.workspaces_dir.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                agents.append(d.name)
        return agents

    def _load_performance_data(self, agent_name: str) -> dict:
        """Load performance data from an agent's workspace."""
        perf_file = self.workspaces_dir / agent_name / "performance.json"
        if not perf_file.exists():
            return {}
        try:
            return json.loads(perf_file.read_text())
        except (json.JSONDecodeError, IOError):
            return {}

    def _load_evidence_history(self, agent_name: str) -> list[dict]:
        """Load evidence history from an agent's workspace."""
        hist_file = self.workspaces_dir / agent_name / "evidence_history.json"
        if not hist_file.exists():
            return []
        try:
            data = json.loads(hist_file.read_text())
            return data if isinstance(data, list) else data.get("completions", [])
        except (json.JSONDecodeError, IOError):
            return []

    def _compute_skill_ratings(self, history: list[dict]) -> dict[str, SkillRating]:
        """Compute skill ratings from evidence history."""
        skills: dict[str, SkillRating] = {}

        for entry in history:
            category = entry.get("category", "unknown")
            if category not in skills:
                skills[category] = SkillRating(category=category)

            s = skills[category]
            s.tasks_completed += 1

            if entry.get("approved", False):
                s.tasks_approved += 1
            if entry.get("rejected", False):
                s.tasks_rejected += 1

            s.total_cost_usd += entry.get("cost_usd", 0)
            s.total_revenue_usd += entry.get("bounty_usd", 0)

            duration = entry.get("duration_ms", 0)
            if duration > 0:
                # Running average
                prev_total = s.avg_duration_ms * (s.tasks_completed - 1)
                s.avg_duration_ms = int((prev_total + duration) / s.tasks_completed)

            rating = entry.get("rating_score", 0)
            if rating > 0:
                prev_total = s.avg_rating * (s.tasks_completed - 1)
                s.avg_rating = (prev_total + rating) / s.tasks_completed

        # Compute trends (last 5 vs first 5 success rates)
        for category, skill in skills.items():
            cat_entries = [e for e in history if e.get("category") == category]
            if len(cat_entries) >= 10:
                first_5 = cat_entries[:5]
                last_5 = cat_entries[-5:]
                first_rate = sum(1 for e in first_5 if e.get("approved")) / 5
                last_rate = sum(1 for e in last_5 if e.get("approved")) / 5
                if last_rate > first_rate + 0.1:
                    skill.trend = "improving"
                elif last_rate < first_rate - 0.1:
                    skill.trend = "declining"

        return skills

    def _compute_reliability_score(self, profile: AgentProfile) -> float:
        """
        0-100 score based on success rate + consistency.

        90%+ success → 80-100
        70-90% → 60-80
        50-70% → 40-60
        <50% → 0-40
        """
        if profile.total_tasks == 0:
            return 50.0  # No data = neutral

        base = profile.success_rate * 100

        # Bonus for volume (more tasks = more reliable data)
        volume_bonus = min(10, profile.total_tasks / 5)

        # Penalty for rejections (harsher than just inverse of success)
        rejection_penalty = 0
        if profile.total_rejected > 0:
            rejection_ratio = profile.total_rejected / profile.total_tasks
            rejection_penalty = rejection_ratio * 20

        return max(0, min(100, base + volume_bonus - rejection_penalty))

    def _compute_efficiency_score(self, profile: AgentProfile) -> float:
        """
        0-100 score based on profit margin.

        >70% margin → 90-100
        50-70% → 70-90
        30-50% → 50-70
        0-30% → 30-50
        <0% → 0-30
        """
        if profile.total_revenue_usd == 0:
            return 50.0  # No data

        margin = (profile.total_profit / profile.total_revenue_usd) * 100

        if margin > 70:
            return 90 + min(10, (margin - 70) / 3)
        elif margin > 50:
            return 70 + (margin - 50)
        elif margin > 30:
            return 50 + (margin - 30)
        elif margin > 0:
            return 30 + margin
        else:
            return max(0, 30 + margin)  # Negative margin → below 30

    def _compute_versatility_score(self, profile: AgentProfile) -> float:
        """
        0-100 score based on category breadth.

        Measures how many categories the agent can handle with >60% success.
        """
        if not profile.skills:
            return 0.0

        total_categories = len(ALL_CATEGORIES)
        competent_categories = sum(
            1 for s in profile.skills.values()
            if s.success_rate >= 0.6 and s.tasks_completed >= 2
        )

        return (competent_categories / total_categories) * 100

    def _generate_recommendations(self, profile: AgentProfile) -> tuple[list[str], list[str], list[str]]:
        """Generate strengths, weaknesses, and recommendations."""
        strengths = []
        weaknesses = []
        recommendations = []

        # Analyze skills
        for name, skill in profile.skills.items():
            if skill.tasks_completed < 2:
                continue
            if skill.success_rate >= 0.9:
                strengths.append(f"Excellent at {name} ({skill.success_rate:.0%} success)")
            elif skill.success_rate >= 0.7:
                strengths.append(f"Good at {name} ({skill.success_rate:.0%} success)")
            elif skill.success_rate < 0.5:
                weaknesses.append(f"Struggles with {name} ({skill.success_rate:.0%} success)")

            if skill.trend == "improving":
                strengths.append(f"{name} skill is improving")
            elif skill.trend == "declining":
                weaknesses.append(f"{name} performance declining")
                recommendations.append(f"Investigate {name} quality issues")

        # Cost efficiency
        if profile.total_profit < 0:
            weaknesses.append("Unprofitable overall")
            recommendations.append("Review model selection — use cheaper models for simple tasks")

        # Volume-based insights
        if profile.total_tasks < 5:
            recommendations.append("More task exposure needed for reliable profiling")

        # Coverage gaps
        covered = set(profile.skills.keys())
        uncovered = set(ALL_CATEGORIES) - covered
        learnable = [c for c in uncovered if c not in ("photo_verification", "physical_presence")]
        if learnable:
            recommendations.append(f"Expand into: {', '.join(sorted(learnable)[:3])}")

        # Specialization vs generalization
        if len(profile.skills) == 1 and profile.total_tasks >= 10:
            skill_name = list(profile.skills.keys())[0]
            recommendations.append(f"Heavily specialized in {skill_name} — consider diversifying")
        elif len(profile.skills) >= 5:
            strengths.append("Versatile across multiple categories")

        return strengths, weaknesses, recommendations

    def analyze_agent(self, agent_name: str) -> AgentProfile:
        """Generate a complete profile for one agent."""
        profile = AgentProfile(agent_name=agent_name)

        # Load data
        perf_data = self._load_performance_data(agent_name)
        history = self._load_evidence_history(agent_name)

        # Extract from performance data
        profile.agent_id = perf_data.get("agent_id")
        profile.wallet_address = perf_data.get("wallet_address")

        # Compute skills from history
        profile.skills = self._compute_skill_ratings(history)

        # Aggregate stats
        profile.total_tasks = sum(s.tasks_completed for s in profile.skills.values())
        profile.total_approved = sum(s.tasks_approved for s in profile.skills.values())
        profile.total_rejected = sum(s.tasks_rejected for s in profile.skills.values())
        profile.total_revenue_usd = sum(s.total_revenue_usd for s in profile.skills.values())
        profile.total_cost_usd = sum(s.total_cost_usd for s in profile.skills.values())

        # Or from perf_data if history is empty
        if profile.total_tasks == 0 and perf_data:
            profile.total_tasks = perf_data.get("total_tasks", 0)
            profile.total_approved = perf_data.get("total_approved", 0)
            profile.total_rejected = perf_data.get("total_rejected", 0)
            profile.total_revenue_usd = perf_data.get("total_revenue_usd", 0)
            profile.total_cost_usd = perf_data.get("total_cost_usd", 0)

        # Compute scores
        profile.reliability_score = self._compute_reliability_score(profile)
        profile.efficiency_score = self._compute_efficiency_score(profile)
        profile.versatility_score = self._compute_versatility_score(profile)

        # Weighted overall: 40% reliability, 30% efficiency, 30% versatility
        profile.overall_score = (
            profile.reliability_score * 0.4
            + profile.efficiency_score * 0.3
            + profile.versatility_score * 0.3
        )

        # Generate recommendations
        strengths, weaknesses, recs = self._generate_recommendations(profile)
        profile.strengths = strengths
        profile.weaknesses = weaknesses
        profile.recommendations = recs

        self._profiles[agent_name] = profile
        return profile

    def analyze_fleet(self) -> FleetAnalysis:
        """Analyze the entire fleet of agents."""
        agents = self._discover_agents()
        fleet = FleetAnalysis(total_agents=len(agents))

        profiles = []
        for agent_name in agents:
            profile = self.analyze_agent(agent_name)
            profiles.append(profile)

            if profile.total_tasks > 0:
                fleet.active_agents += 1

            fleet.total_tasks += profile.total_tasks
            fleet.total_revenue_usd += profile.total_revenue_usd
            fleet.total_cost_usd += profile.total_cost_usd

            # Track category coverage
            for cat in profile.skills:
                fleet.category_coverage[cat] = fleet.category_coverage.get(cat, 0) + 1

        # Success rate
        if fleet.total_tasks > 0:
            total_approved = sum(p.total_approved for p in profiles)
            fleet.avg_success_rate = total_approved / fleet.total_tasks

        # Coverage gaps
        for cat in ALL_CATEGORIES:
            if cat not in fleet.category_coverage:
                fleet.coverage_gaps.append(cat)

        # Top performers (top 20% by overall score)
        active = [p for p in profiles if p.total_tasks >= 3]
        if active:
            active.sort(key=lambda p: p.overall_score, reverse=True)
            top_n = max(1, len(active) // 5)
            fleet.top_performers = [p.agent_name for p in active[:top_n]]
            fleet.underperformers = [
                p.agent_name for p in active
                if p.overall_score < 40 or (p.total_profit < 0 and p.total_tasks >= 5)
            ]

        # Fleet recommendations
        if fleet.coverage_gaps:
            fleet.fleet_recommendations.append(
                f"Coverage gaps in: {', '.join(fleet.coverage_gaps[:3])}"
            )
        if fleet.active_agents < fleet.total_agents * 0.5:
            fleet.fleet_recommendations.append(
                f"Only {fleet.active_agents}/{fleet.total_agents} agents active — "
                f"activate more agents or reduce fleet size"
            )
        if fleet.total_revenue_usd > 0:
            fleet_margin = (fleet.total_revenue_usd - fleet.total_cost_usd) / fleet.total_revenue_usd
            if fleet_margin < 0.3:
                fleet.fleet_recommendations.append(
                    f"Fleet margin at {fleet_margin:.0%} — optimize model selection"
                )
        if fleet.underperformers:
            fleet.fleet_recommendations.append(
                f"Review underperformers: {', '.join(fleet.underperformers[:3])}"
            )

        return fleet

    def get_best_agent_for_task(
        self,
        category: str,
        bounty_usd: float = 0.0,
        exclude: Optional[list[str]] = None,
    ) -> Optional[str]:
        """
        Find the best available agent for a task category.

        Ranking criteria:
          1. Success rate in this category (40%)
          2. Overall reliability (30%)
          3. Cost efficiency (20%)
          4. Recent trend (10%)
        """
        exclude_set = set(exclude or [])
        candidates = []

        for name, profile in self._profiles.items():
            if name in exclude_set:
                continue
            if profile.total_tasks == 0:
                continue

            skill = profile.skills.get(category)

            # Category success rate (default 0.5 if no experience)
            cat_success = skill.success_rate if skill and skill.tasks_completed >= 1 else 0.5
            cat_tasks = skill.tasks_completed if skill else 0

            # Trend bonus
            trend_bonus = 0
            if skill:
                if skill.trend == "improving":
                    trend_bonus = 10
                elif skill.trend == "declining":
                    trend_bonus = -10

            # Compute composite score
            score = (
                cat_success * 100 * 0.4
                + profile.reliability_score * 0.3
                + profile.efficiency_score * 0.2
                + trend_bonus
            )

            # Experience bonus (small, to break ties)
            score += min(5, cat_tasks * 0.5)

            candidates.append((name, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def format_agent_report(self, agent_name: str) -> str:
        """Format a human-readable agent report."""
        if agent_name not in self._profiles:
            self.analyze_agent(agent_name)

        p = self._profiles.get(agent_name)
        if not p:
            return f"No profile data for {agent_name}"

        lines = [
            f"═══════════════════════════════════════════",
            f"  Agent Profile: {p.agent_name}",
            f"═══════════════════════════════════════════",
            "",
            f"  Overall Score: {p.overall_score:.0f}/100",
            f"  Reliability:   {p.reliability_score:.0f}/100",
            f"  Efficiency:    {p.efficiency_score:.0f}/100",
            f"  Versatility:   {p.versatility_score:.0f}/100",
            "",
            f"  Tasks: {p.total_tasks} ({p.total_approved} ✅ / {p.total_rejected} ❌)",
            f"  Success Rate: {p.success_rate:.0%}",
            f"  Revenue: ${p.total_revenue_usd:.4f}",
            f"  Cost:    ${p.total_cost_usd:.4f}",
            f"  Profit:  ${p.total_profit:.4f}",
            "",
        ]

        if p.skills:
            lines.append("  Skills:")
            for name, skill in sorted(p.skills.items(), key=lambda x: x[1].tasks_completed, reverse=True):
                emoji = "📈" if skill.trend == "improving" else "📉" if skill.trend == "declining" else "→"
                lines.append(
                    f"    {name}: {skill.success_rate:.0%} success "
                    f"({skill.tasks_completed} tasks) {emoji}"
                )
            lines.append("")

        if p.strengths:
            lines.append("  Strengths:")
            for s in p.strengths:
                lines.append(f"    ✅ {s}")
            lines.append("")

        if p.weaknesses:
            lines.append("  Weaknesses:")
            for w in p.weaknesses:
                lines.append(f"    ⚠️ {w}")
            lines.append("")

        if p.recommendations:
            lines.append("  Recommendations:")
            for r in p.recommendations:
                lines.append(f"    💡 {r}")
            lines.append("")

        lines.append("═══════════════════════════════════════════")
        return "\n".join(lines)

    def format_fleet_report(self) -> str:
        """Format a human-readable fleet report."""
        fleet = self.analyze_fleet()

        lines = [
            "═══════════════════════════════════════════",
            "  🐝 KK V2 Fleet Analysis",
            "═══════════════════════════════════════════",
            "",
            f"  Agents: {fleet.active_agents} active / {fleet.total_agents} total",
            f"  Tasks:  {fleet.total_tasks}",
            f"  Success Rate: {fleet.avg_success_rate:.0%}",
            f"  Revenue: ${fleet.total_revenue_usd:.4f}",
            f"  Cost:    ${fleet.total_cost_usd:.4f}",
            f"  Profit:  ${fleet.total_revenue_usd - fleet.total_cost_usd:.4f}",
            "",
        ]

        if fleet.category_coverage:
            lines.append("  Category Coverage:")
            for cat, count in sorted(fleet.category_coverage.items()):
                lines.append(f"    {cat}: {count} agents")
            lines.append("")

        if fleet.coverage_gaps:
            lines.append(f"  Coverage Gaps: {', '.join(fleet.coverage_gaps)}")
            lines.append("")

        if fleet.top_performers:
            lines.append(f"  Top Performers: {', '.join(fleet.top_performers)}")

        if fleet.underperformers:
            lines.append(f"  Underperformers: {', '.join(fleet.underperformers)}")

        if fleet.fleet_recommendations:
            lines.append("")
            lines.append("  Recommendations:")
            for r in fleet.fleet_recommendations:
                lines.append(f"    💡 {r}")

        lines.append("")
        lines.append("═══════════════════════════════════════════")
        return "\n".join(lines)
