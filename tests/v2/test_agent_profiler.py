"""
Tests for the Agent Profiler — Performance Analytics & Recommendations.

Covers:
  - Skill rating computation from evidence history
  - Reliability, efficiency, and versatility scoring
  - Recommendation generation (strengths, weaknesses, actions)
  - Fleet-wide analytics
  - Best agent selection for task routing
  - Report formatting
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.agent_profiler import (
    AgentProfile,
    AgentProfiler,
    FleetAnalysis,
    SkillRating,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


def make_evidence(
    category: str = "research",
    approved: bool = True,
    bounty: float = 0.15,
    cost: float = 0.02,
    rating: int = 85,
    duration_ms: int = 5000,
    rejected: bool = False,
) -> dict:
    """Create a single evidence record."""
    return {
        "task_id": f"task-{id(category)}-{rating}",
        "category": category,
        "approved": approved,
        "rejected": rejected,
        "bounty_usd": bounty,
        "cost_usd": cost,
        "rating_score": rating,
        "duration_ms": duration_ms,
    }


def setup_workspace(
    tmpdir: str,
    agent_name: str,
    evidence: list[dict] = None,
    performance: dict = None,
):
    """Set up an agent workspace with test data."""
    ws = Path(tmpdir) / agent_name
    ws.mkdir(parents=True, exist_ok=True)

    if evidence is not None:
        (ws / "evidence_history.json").write_text(json.dumps(evidence))

    if performance is not None:
        (ws / "performance.json").write_text(json.dumps(performance))


# ═══════════════════════════════════════════════════════════════════
# SkillRating Tests
# ═══════════════════════════════════════════════════════════════════


class TestSkillRating:
    def test_success_rate(self):
        sr = SkillRating(category="research", tasks_completed=10, tasks_approved=8)
        assert sr.success_rate == 0.8

    def test_success_rate_zero_tasks(self):
        sr = SkillRating(category="research")
        assert sr.success_rate == 0.0

    def test_profit_per_task(self):
        sr = SkillRating(
            category="research",
            tasks_completed=5,
            total_revenue_usd=1.0,
            total_cost_usd=0.2,
        )
        assert sr.profit_per_task == pytest.approx(0.16)

    def test_margin(self):
        sr = SkillRating(
            category="code_review",
            total_revenue_usd=1.0,
            total_cost_usd=0.3,
        )
        assert sr.margin_pct == pytest.approx(70.0)

    def test_margin_zero_revenue(self):
        sr = SkillRating(category="test")
        assert sr.margin_pct == -100.0


# ═══════════════════════════════════════════════════════════════════
# AgentProfile Tests
# ═══════════════════════════════════════════════════════════════════


class TestAgentProfile:
    def test_basic_creation(self):
        p = AgentProfile(agent_name="aurora")
        assert p.agent_name == "aurora"
        assert p.total_tasks == 0
        assert p.success_rate == 0.0

    def test_success_rate(self):
        p = AgentProfile(agent_name="test", total_tasks=20, total_approved=16)
        assert p.success_rate == 0.8

    def test_profit(self):
        p = AgentProfile(
            agent_name="test",
            total_revenue_usd=5.0,
            total_cost_usd=1.5,
        )
        assert p.total_profit == pytest.approx(3.5)

    def test_to_dict(self):
        p = AgentProfile(
            agent_name="aurora",
            total_tasks=10,
            total_approved=9,
            overall_score=85.0,
        )
        d = p.to_dict()
        assert d["agent_name"] == "aurora"
        assert d["total_tasks"] == 10
        assert d["success_rate"] == 0.9
        assert d["overall_score"] == 85.0


# ═══════════════════════════════════════════════════════════════════
# Profiler: Skill Computation
# ═══════════════════════════════════════════════════════════════════


class TestSkillComputation:
    def test_compute_from_history(self):
        profiler = AgentProfiler()
        history = [
            make_evidence("research", approved=True, bounty=0.15, cost=0.02),
            make_evidence("research", approved=True, bounty=0.10, cost=0.01),
            make_evidence("research", approved=False, bounty=0.20, cost=0.03, rejected=True),
            make_evidence("code_review", approved=True, bounty=0.25, cost=0.05),
        ]
        skills = profiler._compute_skill_ratings(history)

        assert "research" in skills
        assert "code_review" in skills
        assert skills["research"].tasks_completed == 3
        assert skills["research"].tasks_approved == 2
        assert skills["research"].tasks_rejected == 1
        assert skills["code_review"].tasks_completed == 1
        assert skills["code_review"].tasks_approved == 1

    def test_empty_history(self):
        profiler = AgentProfiler()
        skills = profiler._compute_skill_ratings([])
        assert skills == {}

    def test_revenue_accumulation(self):
        profiler = AgentProfiler()
        history = [
            make_evidence("research", bounty=0.15, cost=0.02),
            make_evidence("research", bounty=0.20, cost=0.03),
        ]
        skills = profiler._compute_skill_ratings(history)
        assert skills["research"].total_revenue_usd == pytest.approx(0.35)
        assert skills["research"].total_cost_usd == pytest.approx(0.05)

    def test_trend_detection_improving(self):
        """Agent's last 5 tasks better than first 5 → improving."""
        profiler = AgentProfiler()
        # First 5: 2 approved, 3 rejected (40%)
        # Last 5: 5 approved (100%)
        history = []
        for i in range(5):
            history.append(make_evidence("research", approved=(i < 2), rejected=(i >= 2)))
        for i in range(5):
            history.append(make_evidence("research", approved=True))

        skills = profiler._compute_skill_ratings(history)
        assert skills["research"].trend == "improving"

    def test_trend_detection_declining(self):
        """Agent's last 5 tasks worse than first 5 → declining."""
        profiler = AgentProfiler()
        history = []
        for i in range(5):
            history.append(make_evidence("research", approved=True))
        for i in range(5):
            history.append(make_evidence("research", approved=(i < 1), rejected=(i >= 1)))

        skills = profiler._compute_skill_ratings(history)
        assert skills["research"].trend == "declining"

    def test_trend_stable_with_few_tasks(self):
        """Not enough tasks for trend → stable."""
        profiler = AgentProfiler()
        history = [make_evidence("research") for _ in range(5)]
        skills = profiler._compute_skill_ratings(history)
        assert skills["research"].trend == "stable"


# ═══════════════════════════════════════════════════════════════════
# Profiler: Score Computation
# ═══════════════════════════════════════════════════════════════════


class TestScoreComputation:
    def setup_method(self):
        self.profiler = AgentProfiler()

    def test_reliability_high_success(self):
        p = AgentProfile(agent_name="test", total_tasks=20, total_approved=19)
        score = self.profiler._compute_reliability_score(p)
        assert score >= 90

    def test_reliability_low_success(self):
        p = AgentProfile(
            agent_name="test", total_tasks=10, total_approved=3, total_rejected=7
        )
        score = self.profiler._compute_reliability_score(p)
        assert score < 50

    def test_reliability_no_data(self):
        p = AgentProfile(agent_name="test")
        score = self.profiler._compute_reliability_score(p)
        assert score == 50.0  # Neutral

    def test_efficiency_high_margin(self):
        p = AgentProfile(
            agent_name="test",
            total_revenue_usd=10.0,
            total_cost_usd=2.0,
        )
        score = self.profiler._compute_efficiency_score(p)
        assert score >= 90

    def test_efficiency_negative_margin(self):
        p = AgentProfile(
            agent_name="test",
            total_revenue_usd=1.0,
            total_cost_usd=2.0,
        )
        score = self.profiler._compute_efficiency_score(p)
        assert score < 30

    def test_efficiency_no_revenue(self):
        p = AgentProfile(agent_name="test")
        score = self.profiler._compute_efficiency_score(p)
        assert score == 50.0

    def test_versatility_many_skills(self):
        p = AgentProfile(agent_name="test")
        for cat in ["research", "code_review", "content_creation", "data_collection", "translation"]:
            p.skills[cat] = SkillRating(
                category=cat, tasks_completed=5, tasks_approved=4
            )
        score = self.profiler._compute_versatility_score(p)
        assert score > 50

    def test_versatility_one_skill(self):
        p = AgentProfile(agent_name="test")
        p.skills["research"] = SkillRating(
            category="research", tasks_completed=20, tasks_approved=18
        )
        score = self.profiler._compute_versatility_score(p)
        # Only 1 out of 9 categories
        assert score < 20

    def test_versatility_no_skills(self):
        p = AgentProfile(agent_name="test")
        score = self.profiler._compute_versatility_score(p)
        assert score == 0.0


# ═══════════════════════════════════════════════════════════════════
# Profiler: Recommendations
# ═══════════════════════════════════════════════════════════════════


class TestRecommendations:
    def setup_method(self):
        self.profiler = AgentProfiler()

    def test_identifies_strengths(self):
        p = AgentProfile(agent_name="test")
        p.skills["research"] = SkillRating(
            category="research", tasks_completed=10, tasks_approved=9
        )
        strengths, _, _ = self.profiler._generate_recommendations(p)
        assert any("research" in s.lower() for s in strengths)

    def test_identifies_weaknesses(self):
        p = AgentProfile(agent_name="test")
        p.skills["code_review"] = SkillRating(
            category="code_review", tasks_completed=10, tasks_approved=3, tasks_rejected=7
        )
        _, weaknesses, _ = self.profiler._generate_recommendations(p)
        assert any("code_review" in w.lower() for w in weaknesses)

    def test_unprofitable_recommendation(self):
        p = AgentProfile(
            agent_name="test",
            total_revenue_usd=1.0,
            total_cost_usd=2.0,
        )
        _, weaknesses, recs = self.profiler._generate_recommendations(p)
        assert any("unprofitable" in w.lower() for w in weaknesses)
        assert any("model" in r.lower() for r in recs)

    def test_low_volume_recommendation(self):
        p = AgentProfile(agent_name="test", total_tasks=2)
        _, _, recs = self.profiler._generate_recommendations(p)
        assert any("exposure" in r.lower() for r in recs)

    def test_specialization_warning(self):
        p = AgentProfile(agent_name="test", total_tasks=15)
        p.skills["research"] = SkillRating(
            category="research", tasks_completed=15, tasks_approved=12
        )
        _, _, recs = self.profiler._generate_recommendations(p)
        assert any("specialized" in r.lower() or "diversify" in r.lower() for r in recs)

    def test_declining_trend_flagged(self):
        p = AgentProfile(agent_name="test")
        p.skills["research"] = SkillRating(
            category="research", tasks_completed=10, tasks_approved=5, trend="declining"
        )
        _, weaknesses, recs = self.profiler._generate_recommendations(p)
        assert any("declining" in w.lower() for w in weaknesses)
        assert any("investigate" in r.lower() for r in recs)


# ═══════════════════════════════════════════════════════════════════
# Profiler: Full Analysis
# ═══════════════════════════════════════════════════════════════════


class TestFullAnalysis:
    def test_analyze_agent_with_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence = [
                make_evidence("research", approved=True, bounty=0.15, cost=0.02),
                make_evidence("research", approved=True, bounty=0.10, cost=0.01),
                make_evidence("code_review", approved=True, bounty=0.25, cost=0.05),
                make_evidence("code_review", approved=False, bounty=0.20, cost=0.03, rejected=True),
            ]
            setup_workspace(tmpdir, "aurora", evidence=evidence)

            profiler = AgentProfiler(tmpdir)
            profile = profiler.analyze_agent("aurora")

            assert profile.total_tasks == 4
            assert profile.total_approved == 3
            assert profile.total_rejected == 1
            assert profile.overall_score > 0

    def test_analyze_agent_no_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_workspace(tmpdir, "empty_agent")
            profiler = AgentProfiler(tmpdir)
            profile = profiler.analyze_agent("empty_agent")
            assert profile.total_tasks == 0
            assert profile.reliability_score == 50.0  # neutral

    def test_analyze_agent_perf_data_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            perf = {"total_tasks": 15, "total_approved": 12, "total_rejected": 3}
            setup_workspace(tmpdir, "perf_agent", performance=perf)

            profiler = AgentProfiler(tmpdir)
            profile = profiler.analyze_agent("perf_agent")
            assert profile.total_tasks == 15

    def test_fleet_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Agent 1: good at research
            setup_workspace(tmpdir, "aurora", evidence=[
                make_evidence("research", approved=True) for _ in range(8)
            ])
            # Agent 2: good at code review
            setup_workspace(tmpdir, "nexus", evidence=[
                make_evidence("code_review", approved=True) for _ in range(6)
            ])
            # Agent 3: no tasks
            setup_workspace(tmpdir, "idle_agent")

            profiler = AgentProfiler(tmpdir)
            fleet = profiler.analyze_fleet()

            assert fleet.total_agents == 3
            assert fleet.active_agents == 2
            assert fleet.total_tasks == 14

    def test_fleet_coverage_gaps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Only covers "research"
            setup_workspace(tmpdir, "solo", evidence=[
                make_evidence("research", approved=True) for _ in range(5)
            ])

            profiler = AgentProfiler(tmpdir)
            fleet = profiler.analyze_fleet()

            # Many categories uncovered
            assert len(fleet.coverage_gaps) > 5


# ═══════════════════════════════════════════════════════════════════
# Profiler: Best Agent Selection
# ═══════════════════════════════════════════════════════════════════


class TestBestAgentSelection:
    def test_selects_specialist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Aurora: great at research
            setup_workspace(tmpdir, "aurora", evidence=[
                make_evidence("research", approved=True) for _ in range(10)
            ])
            # Nexus: great at code review, mediocre at research
            setup_workspace(tmpdir, "nexus", evidence=[
                make_evidence("code_review", approved=True) for _ in range(10)
            ] + [make_evidence("research", approved=False) for _ in range(5)])

            profiler = AgentProfiler(tmpdir)
            profiler.analyze_fleet()

            best = profiler.get_best_agent_for_task("research")
            assert best == "aurora"

    def test_selects_different_specialist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_workspace(tmpdir, "aurora", evidence=[
                make_evidence("research", approved=True) for _ in range(10)
            ])
            setup_workspace(tmpdir, "nexus", evidence=[
                make_evidence("code_review", approved=True) for _ in range(10)
            ])

            profiler = AgentProfiler(tmpdir)
            profiler.analyze_fleet()

            best = profiler.get_best_agent_for_task("code_review")
            assert best == "nexus"

    def test_exclude_agent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_workspace(tmpdir, "aurora", evidence=[
                make_evidence("research", approved=True) for _ in range(10)
            ])
            setup_workspace(tmpdir, "nexus", evidence=[
                make_evidence("research", approved=True) for _ in range(5)
            ])

            profiler = AgentProfiler(tmpdir)
            profiler.analyze_fleet()

            best = profiler.get_best_agent_for_task("research", exclude=["aurora"])
            assert best == "nexus"

    def test_no_candidates(self):
        profiler = AgentProfiler("/nonexistent")
        best = profiler.get_best_agent_for_task("research")
        assert best is None


# ═══════════════════════════════════════════════════════════════════
# Report Formatting
# ═══════════════════════════════════════════════════════════════════


class TestReporting:
    def test_agent_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_workspace(tmpdir, "aurora", evidence=[
                make_evidence("research", approved=True, bounty=0.15, cost=0.02)
                for _ in range(5)
            ])

            profiler = AgentProfiler(tmpdir)
            report = profiler.format_agent_report("aurora")

            assert "aurora" in report
            assert "Score" in report
            assert "research" in report

    def test_fleet_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_workspace(tmpdir, "aurora", evidence=[
                make_evidence("research", approved=True) for _ in range(5)
            ])
            setup_workspace(tmpdir, "nexus", evidence=[
                make_evidence("code_review", approved=True) for _ in range(5)
            ])

            profiler = AgentProfiler(tmpdir)
            report = profiler.format_fleet_report()

            assert "Fleet Analysis" in report
            assert "2 active" in report

    def test_agent_report_no_data(self):
        profiler = AgentProfiler("/nonexistent")
        report = profiler.format_agent_report("ghost")
        assert "No profile data" in report or "ghost" in report

    def test_fleet_to_dict(self):
        fleet = FleetAnalysis(
            total_agents=24,
            active_agents=18,
            total_tasks=150,
        )
        d = fleet.to_dict()
        assert d["total_agents"] == 24
        assert d["active_agents"] == 18
