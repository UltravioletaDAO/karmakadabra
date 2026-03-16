"""
Tests for AgentPerformanceTracker — KK V2 Swarm Performance Metrics

Covers:
  - TaskRecord: properties, profit calculation, duration, serialization
  - AgentMetrics: success_rate, cost_efficiency, serialization
  - SwarmReport: generation, markdown output
  - AgentPerformanceTracker:
    - record_task_start / record_task_complete / record_task_timeout
    - agent_metrics computation (counts, ratings, durations, economics)
    - category breakdowns
    - trend computation (improving/declining/stable)
    - anomaly detection (consecutive failures, low success rate, idle, trends)
    - swarm_report generation (top performers, struggling, underutilized)
    - persistence (save/load from JSON)
    - export_for_autojob (AutoJob-compatible format)
  - Edge cases: empty data, single task, all failures, all successes
"""

import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.agent_performance_tracker import (
    TaskRecord,
    AgentMetrics,
    SwarmReport,
    AgentPerformanceTracker,
)


# ═══════════════════════════════════════════════════════════════════
# TaskRecord Tests
# ═══════════════════════════════════════════════════════════════════


class TestTaskRecord:
    """Tests for the TaskRecord dataclass."""

    def test_basic_creation(self):
        r = TaskRecord(
            task_id="task_001",
            agent_id="aurora",
            category="photo_verification",
            started_at=1000.0,
        )
        assert r.task_id == "task_001"
        assert r.agent_id == "aurora"
        assert r.category == "photo_verification"
        assert r.started_at == 1000.0
        assert r.completed_at is None
        assert r.success is None
        assert r.rating is None
        assert r.bounty_usd == 0.0
        assert r.cost_usd == 0.0
        assert r.chain == "base"
        assert r.error_reason is None

    def test_duration_seconds(self):
        r = TaskRecord(
            task_id="t", agent_id="a", category="c",
            started_at=1000.0, completed_at=1060.0,
        )
        assert r.duration_seconds == 60.0

    def test_duration_none_when_not_completed(self):
        r = TaskRecord(task_id="t", agent_id="a", category="c", started_at=1000.0)
        assert r.duration_seconds is None

    def test_profit_calculation(self):
        r = TaskRecord(
            task_id="t", agent_id="a", category="c",
            started_at=1000.0, bounty_usd=5.0, cost_usd=1.5,
        )
        assert r.profit_usd == 3.5

    def test_profit_negative(self):
        r = TaskRecord(
            task_id="t", agent_id="a", category="c",
            started_at=1000.0, bounty_usd=0.10, cost_usd=0.50,
        )
        assert r.profit_usd == pytest.approx(-0.40)

    def test_to_dict(self):
        r = TaskRecord(
            task_id="task_001", agent_id="aurora", category="data_collection",
            started_at=1000.0, completed_at=1120.0,
            success=True, rating=4.5, bounty_usd=2.0, cost_usd=0.3,
            chain="polygon", error_reason=None,
        )
        d = r.to_dict()
        assert d["task_id"] == "task_001"
        assert d["agent_id"] == "aurora"
        assert d["duration_seconds"] == 120.0
        assert d["profit_usd"] == pytest.approx(1.7)
        assert d["success"] is True
        assert d["rating"] == 4.5
        assert d["chain"] == "polygon"

    def test_to_dict_incomplete(self):
        r = TaskRecord(task_id="t", agent_id="a", category="c", started_at=1000.0)
        d = r.to_dict()
        assert d["duration_seconds"] is None
        assert d["profit_usd"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# AgentMetrics Tests
# ═══════════════════════════════════════════════════════════════════


class TestAgentMetrics:
    """Tests for the AgentMetrics dataclass."""

    def test_success_rate_empty(self):
        m = AgentMetrics(agent_id="test")
        assert m.success_rate == 0.0

    def test_success_rate_all_success(self):
        m = AgentMetrics(agent_id="test", total_tasks=10, successful_tasks=10)
        assert m.success_rate == 1.0

    def test_success_rate_mixed(self):
        m = AgentMetrics(agent_id="test", total_tasks=20, successful_tasks=15)
        assert m.success_rate == 0.75

    def test_cost_efficiency_no_cost(self):
        m = AgentMetrics(agent_id="test", total_earned_usd=10.0, total_cost_usd=0.0)
        assert m.cost_efficiency == float('inf')

    def test_cost_efficiency_no_earnings(self):
        m = AgentMetrics(agent_id="test", total_earned_usd=0.0, total_cost_usd=0.0)
        assert m.cost_efficiency == 0.0

    def test_cost_efficiency_normal(self):
        m = AgentMetrics(agent_id="test", total_earned_usd=10.0, total_cost_usd=2.0)
        assert m.cost_efficiency == 5.0

    def test_to_dict(self):
        m = AgentMetrics(
            agent_id="aurora",
            total_tasks=10,
            successful_tasks=8,
            total_earned_usd=5.0,
            total_cost_usd=1.0,
        )
        d = m.to_dict()
        assert d["agent_id"] == "aurora"
        assert d["success_rate"] == 0.8
        assert d["cost_efficiency"] == 5.0


# ═══════════════════════════════════════════════════════════════════
# SwarmReport Tests
# ═══════════════════════════════════════════════════════════════════


class TestSwarmReport:
    """Tests for the SwarmReport dataclass."""

    def test_empty_report(self):
        r = SwarmReport(generated_at="2026-02-26T00:00:00Z")
        assert r.total_agents == 0
        assert r.total_tasks == 0
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["generated_at"] == "2026-02-26T00:00:00Z"

    def test_to_markdown(self):
        r = SwarmReport(
            generated_at="2026-02-26T00:00:00Z",
            total_agents=5,
            active_agents=3,
            total_tasks=100,
            total_successful=85,
            swarm_success_rate=0.85,
            net_profit_usd=42.50,
            top_agents_by_rating=[
                {"agent_id": "aurora", "avg_rating": 4.8, "total_tasks": 30, "success_rate": 0.95},
            ],
            top_agents_by_volume=[
                {"agent_id": "aurora", "total_tasks": 30, "total_earned_usd": 15.0, "success_rate": 0.95},
            ],
            struggling_agents=[
                {"agent_id": "stale_bot", "reason": "CONSECUTIVE_FAILURES: 5 failures in a row"},
            ],
            anomalies=["stale_bot: CONSECUTIVE_FAILURES"],
            category_breakdown={
                "photo_verification": {"count": 40, "success_rate": 0.90, "total_earned": 20.0},
            },
        )
        md = r.to_markdown()
        assert "# KK V2 Swarm Performance Report" in md
        assert "aurora" in md
        assert "85.0%" in md
        assert "$42.50" in md or "+42.50" in md
        assert "stale_bot" in md
        assert "photo_verification" in md


# ═══════════════════════════════════════════════════════════════════
# AgentPerformanceTracker — Recording
# ═══════════════════════════════════════════════════════════════════


class TestTrackerRecording:
    """Tests for task recording functionality."""

    def test_record_start_creates_active_task(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "task_001", "photo_verification", bounty_usd=1.0)
        assert "task_001" in t.active_tasks
        assert t.active_tasks["task_001"].agent_id == "aurora"
        assert t.active_tasks["task_001"].bounty_usd == 1.0

    def test_record_complete_moves_to_records(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "task_001", "data_collection", bounty_usd=2.0)
        t.record_task_complete("aurora", "task_001", success=True, rating=4.5, cost_usd=0.3)
        assert "task_001" not in t.active_tasks
        assert len(t.records) == 1
        assert t.records[0].success is True
        assert t.records[0].rating == 4.5
        assert t.records[0].cost_usd == 0.3

    def test_record_complete_without_start(self):
        """Completing a task that wasn't started creates a retroactive record."""
        t = AgentPerformanceTracker()
        t.record_task_complete("aurora", "task_ghost", success=True)
        assert len(t.records) == 1
        assert t.records[0].task_id == "task_ghost"
        assert t.records[0].category == "unknown"

    def test_record_timeout(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "task_slow", "photo_verification")
        t.record_task_timeout("task_slow", timeout_seconds=300)
        assert "task_slow" not in t.active_tasks
        assert len(t.records) == 1
        assert t.records[0].success is False
        assert "Timeout" in t.records[0].error_reason

    def test_record_timeout_unknown_task(self):
        """Timeout for a task that wasn't started is a no-op."""
        t = AgentPerformanceTracker()
        t.record_task_timeout("nonexistent")
        assert len(t.records) == 0

    def test_record_failed_task(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "task_fail", "mystery_shopping")
        t.record_task_complete(
            "aurora", "task_fail", success=False,
            error_reason="Evidence quality too low",
        )
        assert len(t.records) == 1
        assert t.records[0].success is False
        assert t.records[0].error_reason == "Evidence quality too low"

    def test_multiple_tasks_different_agents(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "t1", "photo")
        t.record_task_start("spark", "t2", "data")
        t.record_task_start("aurora", "t3", "photo")
        t.record_task_complete("aurora", "t1", success=True)
        t.record_task_complete("spark", "t2", success=True)
        t.record_task_complete("aurora", "t3", success=False)
        assert len(t.records) == 3
        aurora_records = [r for r in t.records if r.agent_id == "aurora"]
        assert len(aurora_records) == 2


# ═══════════════════════════════════════════════════════════════════
# AgentPerformanceTracker — Agent Metrics
# ═══════════════════════════════════════════════════════════════════


class TestTrackerAgentMetrics:
    """Tests for agent_metrics computation."""

    def _build_tracker_with_tasks(self):
        """Helper: build a tracker with a mix of tasks."""
        t = AgentPerformanceTracker()
        tasks = [
            ("aurora", "t1", "photo", True, 4.5, 1.0, 0.1, "base"),
            ("aurora", "t2", "data", True, 4.0, 0.5, 0.05, "polygon"),
            ("aurora", "t3", "photo", False, None, 0.0, 0.2, "base"),
            ("aurora", "t4", "photo", True, 5.0, 2.0, 0.1, "base"),
            ("spark", "t5", "data", True, 3.5, 0.5, 0.1, "base"),
            ("spark", "t6", "data", False, None, 0.0, 0.1, "base"),
        ]
        for agent, tid, cat, success, rating, bounty, cost, chain in tasks:
            t.record_task_start(agent, tid, cat, bounty_usd=bounty, chain=chain)
            time.sleep(0.001)  # Ensure different timestamps
            t.record_task_complete(agent, tid, success=success, rating=rating, cost_usd=cost)
        return t

    def test_empty_agent_metrics(self):
        t = AgentPerformanceTracker()
        m = t.agent_metrics("nonexistent")
        assert m.total_tasks == 0
        assert m.success_rate == 0.0
        assert m.avg_rating == 0.0

    def test_task_counts(self):
        t = self._build_tracker_with_tasks()
        m = t.agent_metrics("aurora")
        assert m.total_tasks == 4
        assert m.successful_tasks == 3
        assert m.failed_tasks == 1

    def test_ratings(self):
        t = self._build_tracker_with_tasks()
        m = t.agent_metrics("aurora")
        # Aurora's ratings: 4.5, 4.0, None, 5.0 → avg of 4.5, 4.0, 5.0 = 4.5
        assert m.avg_rating == pytest.approx(4.5, abs=0.01)

    def test_durations(self):
        t = self._build_tracker_with_tasks()
        m = t.agent_metrics("aurora")
        assert m.avg_duration_seconds > 0
        assert m.p95_duration_seconds >= m.avg_duration_seconds

    def test_economics(self):
        t = self._build_tracker_with_tasks()
        m = t.agent_metrics("aurora")
        # Earned: t1(1.0) + t2(0.5) + t4(2.0) = 3.5 (only successful)
        assert m.total_earned_usd == pytest.approx(3.5)
        # Cost: 0.1 + 0.05 + 0.2 + 0.1 = 0.45 (all tasks)
        assert m.total_cost_usd == pytest.approx(0.45)
        assert m.net_profit_usd == pytest.approx(3.05)

    def test_category_breakdown(self):
        t = self._build_tracker_with_tasks()
        m = t.agent_metrics("aurora")
        # Photo: 3 tasks (2 success, 1 fail) = 66.7%
        assert m.category_counts["photo"] == 3
        assert m.category_success_rates["photo"] == pytest.approx(2 / 3, abs=0.01)
        # Data: 1 task (1 success) = 100%
        assert m.category_counts["data"] == 1
        assert m.category_success_rates["data"] == 1.0

    def test_success_rate(self):
        t = self._build_tracker_with_tasks()
        m = t.agent_metrics("aurora")
        assert m.success_rate == 0.75

    def test_spark_metrics(self):
        t = self._build_tracker_with_tasks()
        m = t.agent_metrics("spark")
        assert m.total_tasks == 2
        assert m.successful_tasks == 1
        assert m.success_rate == 0.5

    def test_window_filtering(self):
        t = AgentPerformanceTracker()
        # Old task (30 days ago)
        r_old = TaskRecord(
            task_id="old", agent_id="aurora", category="photo",
            started_at=time.time() - 30 * 86400,
            completed_at=time.time() - 30 * 86400 + 60,
            success=True, bounty_usd=1.0,
        )
        t.records.append(r_old)
        # Recent task
        t.record_task_start("aurora", "recent", "photo", bounty_usd=2.0)
        t.record_task_complete("aurora", "recent", success=True)
        
        # All time: 2 tasks
        m_all = t.agent_metrics("aurora")
        assert m_all.total_tasks == 2
        
        # Last 7 days: 1 task
        m_week = t.agent_metrics("aurora", window_days=7)
        assert m_week.total_tasks == 1

    def test_consecutive_failures_at_end(self):
        t = AgentPerformanceTracker()
        # Success, then 3 failures
        for i, success in enumerate([True, False, False, False]):
            t.record_task_start("aurora", f"t{i}", "photo")
            t.record_task_complete("aurora", f"t{i}", success=success)
        m = t.agent_metrics("aurora")
        assert m.consecutive_failures == 3

    def test_consecutive_failures_reset_by_success(self):
        t = AgentPerformanceTracker()
        for i, success in enumerate([False, False, True, False]):
            t.record_task_start("aurora", f"t{i}", "photo")
            t.record_task_complete("aurora", f"t{i}", success=success)
        m = t.agent_metrics("aurora")
        assert m.consecutive_failures == 1

    def test_last_success_timestamp(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "t1", "photo")
        t.record_task_complete("aurora", "t1", success=True)
        success_time = t.records[0].completed_at
        t.record_task_start("aurora", "t2", "photo")
        t.record_task_complete("aurora", "t2", success=False)
        m = t.agent_metrics("aurora")
        assert m.last_success_at == success_time


# ═══════════════════════════════════════════════════════════════════
# AgentPerformanceTracker — Trends
# ═══════════════════════════════════════════════════════════════════


class TestTrackerTrends:
    """Tests for trend computation (recent vs earlier)."""

    def test_stable_trend_no_earlier_data(self):
        t = AgentPerformanceTracker()
        # Only recent tasks
        t.record_task_start("aurora", "t1", "photo")
        t.record_task_complete("aurora", "t1", success=True, rating=4.0)
        m = t.agent_metrics("aurora")
        assert m.rating_trend == "stable"
        assert m.completion_rate_trend == "stable"

    def test_improving_rating_trend(self):
        t = AgentPerformanceTracker()
        now = time.time()
        # Earlier period (8-14 days ago): low ratings
        for i in range(5):
            r = TaskRecord(
                task_id=f"old_{i}", agent_id="aurora", category="photo",
                started_at=now - 10 * 86400 + i,
                completed_at=now - 10 * 86400 + i + 60,
                success=True, rating=3.0,
            )
            t.records.append(r)
        # Recent period (last 7 days): high ratings
        for i in range(5):
            r = TaskRecord(
                task_id=f"new_{i}", agent_id="aurora", category="photo",
                started_at=now - 3 * 86400 + i,
                completed_at=now - 3 * 86400 + i + 60,
                success=True, rating=4.5,
            )
            t.records.append(r)
        m = t.agent_metrics("aurora")
        assert m.rating_trend == "improving"

    def test_declining_completion_trend(self):
        t = AgentPerformanceTracker()
        now = time.time()
        # Earlier period: all success
        for i in range(5):
            r = TaskRecord(
                task_id=f"old_{i}", agent_id="aurora", category="photo",
                started_at=now - 10 * 86400 + i,
                completed_at=now - 10 * 86400 + i + 60,
                success=True,
            )
            t.records.append(r)
        # Recent period: mostly failures
        for i in range(5):
            r = TaskRecord(
                task_id=f"new_{i}", agent_id="aurora", category="photo",
                started_at=now - 3 * 86400 + i,
                completed_at=now - 3 * 86400 + i + 60,
                success=(i == 0),  # Only 1/5 success = 20%
            )
            t.records.append(r)
        m = t.agent_metrics("aurora")
        assert m.completion_rate_trend == "declining"


# ═══════════════════════════════════════════════════════════════════
# AgentPerformanceTracker — Anomaly Detection
# ═══════════════════════════════════════════════════════════════════


class TestTrackerAnomalies:
    """Tests for anomaly detection."""

    def test_consecutive_failure_anomaly(self):
        t = AgentPerformanceTracker()
        for i in range(5):
            t.record_task_start("aurora", f"t{i}", "photo")
            t.record_task_complete("aurora", f"t{i}", success=False)
        m = t.agent_metrics("aurora")
        assert any("CONSECUTIVE_FAILURES" in f for f in m.anomaly_flags)

    def test_low_success_rate_anomaly(self):
        t = AgentPerformanceTracker()
        for i in range(10):
            t.record_task_start("aurora", f"t{i}", "photo")
            t.record_task_complete("aurora", f"t{i}", success=(i < 3))
        m = t.agent_metrics("aurora")
        # 3/10 = 30% success rate
        assert any("LOW_SUCCESS_RATE" in f for f in m.anomaly_flags)

    def test_no_anomaly_for_good_agent(self):
        t = AgentPerformanceTracker()
        for i in range(10):
            t.record_task_start("aurora", f"t{i}", "photo")
            t.record_task_complete("aurora", f"t{i}", success=True, rating=4.5)
        m = t.agent_metrics("aurora")
        assert len(m.anomaly_flags) == 0

    def test_idle_anomaly(self):
        t = AgentPerformanceTracker()
        # One successful task 48 hours ago
        r = TaskRecord(
            task_id="old", agent_id="aurora", category="photo",
            started_at=time.time() - 48 * 3600,
            completed_at=time.time() - 48 * 3600 + 60,
            success=True,
        )
        t.records.append(r)
        m = t.agent_metrics("aurora")
        assert any("IDLE" in f for f in m.anomaly_flags)

    def test_few_tasks_no_low_success_anomaly(self):
        """Agents with ≤5 tasks don't get LOW_SUCCESS_RATE anomaly."""
        t = AgentPerformanceTracker()
        for i in range(3):
            t.record_task_start("aurora", f"t{i}", "photo")
            t.record_task_complete("aurora", f"t{i}", success=False)
        m = t.agent_metrics("aurora")
        # 3 tasks with 0% success — but under the 5-task threshold
        assert not any("LOW_SUCCESS_RATE" in f for f in m.anomaly_flags)
        # But consecutive failures should still trigger
        assert any("CONSECUTIVE_FAILURES" in f for f in m.anomaly_flags)


# ═══════════════════════════════════════════════════════════════════
# AgentPerformanceTracker — Swarm Report
# ═══════════════════════════════════════════════════════════════════


class TestTrackerSwarmReport:
    """Tests for swarm-wide reporting."""

    def test_empty_swarm_report(self):
        t = AgentPerformanceTracker()
        r = t.swarm_report()
        assert r.total_agents == 0
        assert r.total_tasks == 0
        assert r.swarm_success_rate == 0.0

    def test_swarm_report_basic(self):
        t = AgentPerformanceTracker()
        for i in range(5):
            t.record_task_start("aurora", f"a{i}", "photo", bounty_usd=1.0)
            t.record_task_complete("aurora", f"a{i}", success=True, rating=4.5, cost_usd=0.1)
        for i in range(3):
            t.record_task_start("spark", f"s{i}", "data", bounty_usd=0.5)
            t.record_task_complete("spark", f"s{i}", success=(i < 2), cost_usd=0.05)
        
        r = t.swarm_report()
        assert r.total_agents == 2
        assert r.active_agents == 2
        assert r.total_tasks == 8
        assert r.total_successful == 7
        assert r.swarm_success_rate == pytest.approx(7 / 8)

    def test_swarm_report_economics(self):
        t = AgentPerformanceTracker()
        for i in range(4):
            t.record_task_start("aurora", f"t{i}", "photo", bounty_usd=2.0)
            t.record_task_complete("aurora", f"t{i}", success=True, cost_usd=0.2)
        r = t.swarm_report()
        assert r.total_earned_usd == pytest.approx(8.0)
        assert r.total_cost_usd == pytest.approx(0.8)
        assert r.net_profit_usd == pytest.approx(7.2)

    def test_swarm_report_top_performers(self):
        t = AgentPerformanceTracker()
        # Aurora: 5 tasks, high rating
        for i in range(5):
            t.record_task_start("aurora", f"a{i}", "photo", bounty_usd=1.0)
            t.record_task_complete("aurora", f"a{i}", success=True, rating=4.8, cost_usd=0.1)
        # Spark: 3 tasks, lower rating
        for i in range(3):
            t.record_task_start("spark", f"s{i}", "data", bounty_usd=0.5)
            t.record_task_complete("spark", f"s{i}", success=True, rating=3.5, cost_usd=0.05)
        
        r = t.swarm_report()
        assert len(r.top_agents_by_rating) >= 2
        assert r.top_agents_by_rating[0]["agent_id"] == "aurora"
        assert len(r.top_agents_by_volume) >= 2
        assert r.top_agents_by_volume[0]["agent_id"] == "aurora"

    def test_swarm_report_struggling_agents(self):
        t = AgentPerformanceTracker()
        for i in range(5):
            t.record_task_start("bad_bot", f"t{i}", "photo")
            t.record_task_complete("bad_bot", f"t{i}", success=False)
        r = t.swarm_report()
        assert len(r.struggling_agents) > 0
        agent_ids = [a["agent_id"] for a in r.struggling_agents]
        assert "bad_bot" in agent_ids

    def test_swarm_report_category_breakdown(self):
        t = AgentPerformanceTracker()
        for i in range(5):
            t.record_task_start("aurora", f"p{i}", "photo", bounty_usd=1.0)
            t.record_task_complete("aurora", f"p{i}", success=True)
        for i in range(3):
            t.record_task_start("aurora", f"d{i}", "data", bounty_usd=0.5)
            t.record_task_complete("aurora", f"d{i}", success=(i < 1))
        r = t.swarm_report()
        assert "photo" in r.category_breakdown
        assert "data" in r.category_breakdown
        assert r.category_breakdown["photo"]["count"] == 5

    def test_swarm_report_best_worst_category(self):
        t = AgentPerformanceTracker()
        for i in range(5):
            t.record_task_start("a", f"p{i}", "photo")
            t.record_task_complete("a", f"p{i}", success=True)
        for i in range(5):
            t.record_task_start("a", f"d{i}", "data")
            t.record_task_complete("a", f"d{i}", success=(i < 1))
        r = t.swarm_report()
        assert r.best_category == "photo"
        assert r.worst_category == "data"

    def test_swarm_report_markdown(self):
        t = AgentPerformanceTracker()
        for i in range(5):
            t.record_task_start("aurora", f"t{i}", "photo", bounty_usd=1.0)
            t.record_task_complete("aurora", f"t{i}", success=True, rating=4.5, cost_usd=0.1)
        r = t.swarm_report()
        md = r.to_markdown()
        assert "# KK V2 Swarm Performance Report" in md
        assert "aurora" in md

    def test_swarm_report_underutilized(self):
        t = AgentPerformanceTracker()
        # Aurora: lots of tasks
        for i in range(20):
            t.record_task_start("aurora", f"a{i}", "photo")
            t.record_task_complete("aurora", f"a{i}", success=True)
        # Lazy bot: only 1 task
        t.record_task_start("lazy", "l1", "data")
        t.record_task_complete("lazy", "l1", success=True)
        r = t.swarm_report()
        lazy_ids = [a["agent_id"] for a in r.underutilized_agents]
        assert "lazy" in lazy_ids

    def test_swarm_report_window_days(self):
        t = AgentPerformanceTracker()
        # Old tasks
        for i in range(5):
            r = TaskRecord(
                task_id=f"old_{i}", agent_id="aurora", category="photo",
                started_at=time.time() - 30 * 86400 + i,
                completed_at=time.time() - 30 * 86400 + i + 60,
                success=True, bounty_usd=1.0,
            )
            t.records.append(r)
        # Recent tasks
        for i in range(3):
            t.record_task_start("aurora", f"new_{i}", "photo", bounty_usd=2.0)
            t.record_task_complete("aurora", f"new_{i}", success=True)
        
        r_all = t.swarm_report()
        r_week = t.swarm_report(window_days=7)
        assert r_all.total_tasks == 8
        assert r_week.total_tasks == 3


# ═══════════════════════════════════════════════════════════════════
# AgentPerformanceTracker — Persistence
# ═══════════════════════════════════════════════════════════════════


class TestTrackerPersistence:
    """Tests for save/load functionality."""

    def test_persist_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        
        try:
            t1 = AgentPerformanceTracker(persist_path=path)
            for i in range(5):
                t1.record_task_start("aurora", f"t{i}", "photo", bounty_usd=1.0)
                t1.record_task_complete("aurora", f"t{i}", success=True, rating=4.5)
            
            # Load from persisted file
            t2 = AgentPerformanceTracker(persist_path=path)
            assert len(t2.records) == 5
            m = t2.agent_metrics("aurora")
            assert m.total_tasks == 5
            assert m.avg_rating == pytest.approx(4.5)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_persist_file_format(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        
        try:
            t = AgentPerformanceTracker(persist_path=path)
            t.record_task_start("aurora", "t1", "photo", bounty_usd=1.0, chain="polygon")
            t.record_task_complete("aurora", "t1", success=True, rating=4.5, cost_usd=0.1)
            
            data = json.loads(Path(path).read_text())
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["task_id"] == "t1"
            assert data[0]["chain"] == "polygon"
            assert data[0]["rating"] == 4.5
        finally:
            Path(path).unlink(missing_ok=True)

    def test_persist_no_path(self):
        """No error when persist_path is None."""
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "t1", "photo")
        t.record_task_complete("aurora", "t1", success=True)
        # Should not raise
        assert len(t.records) == 1


# ═══════════════════════════════════════════════════════════════════
# AgentPerformanceTracker — AutoJob Export
# ═══════════════════════════════════════════════════════════════════


class TestTrackerAutoJobExport:
    """Tests for export_for_autojob."""

    def test_export_only_successful_tasks(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "t1", "photo", bounty_usd=1.0, chain="base")
        t.record_task_complete("aurora", "t1", success=True)
        t.record_task_start("aurora", "t2", "data", bounty_usd=0.5)
        t.record_task_complete("aurora", "t2", success=False)
        
        export = t.export_for_autojob("aurora")
        assert len(export) == 1
        assert export[0]["task_id"] == "t1"
        assert export[0]["status"] == "completed"
        assert export[0]["category"] == "photo"

    def test_export_empty_for_unknown_agent(self):
        t = AgentPerformanceTracker()
        export = t.export_for_autojob("nonexistent")
        assert export == []

    def test_export_format(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "t1", "photo_verification", bounty_usd=2.0, chain="polygon")
        t.record_task_complete("aurora", "t1", success=True)
        
        export = t.export_for_autojob("aurora")
        assert len(export) == 1
        record = export[0]
        assert "task_id" in record
        assert "category" in record
        assert "bounty_usd" in record
        assert "payment_network" in record
        assert "status" in record
        assert "created_at" in record
        assert record["payment_network"] == "polygon"

    def test_export_doesnt_include_other_agents(self):
        t = AgentPerformanceTracker()
        t.record_task_start("aurora", "t1", "photo", bounty_usd=1.0)
        t.record_task_complete("aurora", "t1", success=True)
        t.record_task_start("spark", "t2", "data", bounty_usd=0.5)
        t.record_task_complete("spark", "t2", success=True)
        
        export = t.export_for_autojob("aurora")
        assert len(export) == 1
        assert export[0]["task_id"] == "t1"


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_task_agent(self):
        t = AgentPerformanceTracker()
        t.record_task_start("solo", "t1", "photo", bounty_usd=5.0)
        t.record_task_complete("solo", "t1", success=True, rating=5.0, cost_usd=0.5)
        m = t.agent_metrics("solo")
        assert m.total_tasks == 1
        assert m.success_rate == 1.0
        assert m.avg_rating == 5.0
        assert m.cost_efficiency == 10.0

    def test_all_failures_agent(self):
        t = AgentPerformanceTracker()
        for i in range(10):
            t.record_task_start("fail_bot", f"t{i}", "photo")
            t.record_task_complete("fail_bot", f"t{i}", success=False)
        m = t.agent_metrics("fail_bot")
        assert m.total_tasks == 10
        assert m.success_rate == 0.0
        assert m.total_earned_usd == 0.0
        assert m.consecutive_failures == 10

    def test_high_volume_agent(self):
        t = AgentPerformanceTracker()
        for i in range(100):
            t.record_task_start("machine", f"t{i}", "data", bounty_usd=0.1)
            t.record_task_complete(
                "machine", f"t{i}", success=(i % 10 != 0),
                rating=4.0 + (i % 5) * 0.2, cost_usd=0.01,
            )
        m = t.agent_metrics("machine")
        assert m.total_tasks == 100
        assert m.successful_tasks == 90
        assert m.success_rate == 0.9
        assert m.total_cost_usd == pytest.approx(1.0)

    def test_zero_bounty_tasks(self):
        t = AgentPerformanceTracker()
        t.record_task_start("free_worker", "t1", "test")
        t.record_task_complete("free_worker", "t1", success=True)
        m = t.agent_metrics("free_worker")
        assert m.total_earned_usd == 0.0
        assert m.net_profit_usd == 0.0

    def test_multiple_chains(self):
        t = AgentPerformanceTracker()
        chains = ["base", "polygon", "arbitrum", "optimism"]
        for i, chain in enumerate(chains):
            t.record_task_start("multi", f"t{i}", "photo", bounty_usd=1.0, chain=chain)
            t.record_task_complete("multi", f"t{i}", success=True)
        export = t.export_for_autojob("multi")
        exported_chains = {r["payment_network"] for r in export}
        assert exported_chains == set(chains)

    def test_concurrent_active_tasks(self):
        t = AgentPerformanceTracker()
        # Start 3 tasks, complete them in different order
        t.record_task_start("multi", "t1", "photo")
        t.record_task_start("multi", "t2", "data")
        t.record_task_start("multi", "t3", "photo")
        assert len(t.active_tasks) == 3
        t.record_task_complete("multi", "t2", success=True)
        assert len(t.active_tasks) == 2
        t.record_task_complete("multi", "t3", success=False)
        t.record_task_complete("multi", "t1", success=True)
        assert len(t.active_tasks) == 0
        assert len(t.records) == 3
