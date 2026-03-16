"""
Tests for AgentPerformanceTracker — Observability and Success Metrics

Tests cover:
- Task recording (start, complete, timeout)
- Agent-level metrics computation
- Swarm-wide report generation
- Trend detection (improving/declining/stable)
- Anomaly detection
- Category breakdown
- AutoJob export format
- Persistence (save/load)
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

# Adjust path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.agent_performance_tracker import (
    AgentPerformanceTracker,
    TaskRecord,
    AgentMetrics,
    SwarmReport,
)


# ── Fixtures ──

@pytest.fixture
def tracker():
    """Fresh tracker with no persistence."""
    return AgentPerformanceTracker()


@pytest.fixture
def tracker_with_data():
    """Tracker pre-loaded with sample data."""
    t = AgentPerformanceTracker()
    
    # Simulate 20 tasks across 3 agents
    agents = ["aurora", "blaze", "cipher"]
    categories = ["data_collection", "research", "code_review", "photo_verification"]
    
    for i in range(20):
        agent = agents[i % 3]
        category = categories[i % 4]
        task_id = f"task_{i:03d}"
        
        record = TaskRecord(
            task_id=task_id,
            agent_id=agent,
            category=category,
            started_at=time.time() - (20 - i) * 3600,  # Spread over 20 hours
            completed_at=time.time() - (20 - i) * 3600 + 300,  # 5 min each
            success=i % 5 != 0,  # 80% success rate
            rating=4.0 + (i % 5) * 0.2 if i % 5 != 0 else None,
            bounty_usd=0.50,
            cost_usd=0.05,
            chain="base" if i % 2 == 0 else "polygon",
        )
        t.records.append(record)
    
    return t


@pytest.fixture
def persistent_tracker(tmp_path):
    """Tracker with file persistence."""
    path = tmp_path / "performance.json"
    return AgentPerformanceTracker(persist_path=str(path))


# ── Task Recording Tests ──

class TestTaskRecording:
    def test_record_start(self, tracker):
        tracker.record_task_start("aurora", "task_001", "research", bounty_usd=0.50)
        assert "task_001" in tracker.active_tasks
        assert tracker.active_tasks["task_001"].agent_id == "aurora"
        assert tracker.active_tasks["task_001"].category == "research"
        assert tracker.active_tasks["task_001"].bounty_usd == 0.50

    def test_record_complete_success(self, tracker):
        tracker.record_task_start("aurora", "task_001", "research")
        tracker.record_task_complete("aurora", "task_001", success=True, rating=4.5)
        
        assert "task_001" not in tracker.active_tasks
        assert len(tracker.records) == 1
        assert tracker.records[0].success is True
        assert tracker.records[0].rating == 4.5

    def test_record_complete_failure(self, tracker):
        tracker.record_task_start("aurora", "task_001", "research")
        tracker.record_task_complete(
            "aurora", "task_001", 
            success=False, 
            error_reason="Evidence rejected"
        )
        
        assert tracker.records[0].success is False
        assert tracker.records[0].error_reason == "Evidence rejected"

    def test_record_complete_without_start(self, tracker):
        """Should create a retroactive record."""
        tracker.record_task_complete("aurora", "task_001", success=True)
        
        assert len(tracker.records) == 1
        assert tracker.records[0].agent_id == "aurora"
        assert tracker.records[0].category == "unknown"

    def test_record_timeout(self, tracker):
        tracker.record_task_start("aurora", "task_001", "research")
        tracker.record_task_timeout("task_001", timeout_seconds=600)
        
        assert "task_001" not in tracker.active_tasks
        assert len(tracker.records) == 1
        assert tracker.records[0].success is False
        assert "Timeout" in tracker.records[0].error_reason

    def test_task_duration(self, tracker):
        tracker.record_task_start("aurora", "task_001", "research")
        time.sleep(0.01)  # Small delay
        tracker.record_task_complete("aurora", "task_001", success=True)
        
        duration = tracker.records[0].duration_seconds
        assert duration is not None
        assert duration >= 0.01

    def test_task_profit(self):
        record = TaskRecord(
            task_id="t1", agent_id="aurora", category="research",
            started_at=100.0, bounty_usd=0.50, cost_usd=0.05
        )
        assert record.profit_usd == 0.45


# ── Agent Metrics Tests ──

class TestAgentMetrics:
    def test_empty_agent(self, tracker):
        m = tracker.agent_metrics("nonexistent")
        assert m.total_tasks == 0
        assert m.success_rate == 0.0

    def test_basic_metrics(self, tracker_with_data):
        m = tracker_with_data.agent_metrics("aurora")
        assert m.total_tasks > 0
        assert m.successful_tasks > 0
        assert m.success_rate > 0

    def test_success_rate(self, tracker):
        for i in range(10):
            record = TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category="research",
                started_at=time.time() - i * 60,
                completed_at=time.time() - i * 60 + 30,
                success=i < 7,  # 7/10 = 70% success
            )
            tracker.records.append(record)
        
        m = tracker.agent_metrics("aurora")
        assert m.total_tasks == 10
        assert m.successful_tasks == 7
        assert abs(m.success_rate - 0.7) < 0.01

    def test_rating_average(self, tracker):
        ratings = [4.0, 4.5, 5.0, 3.5, 4.0]
        for i, rating in enumerate(ratings):
            record = TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category="research",
                started_at=time.time(), completed_at=time.time() + 60,
                success=True, rating=rating,
            )
            tracker.records.append(record)
        
        m = tracker.agent_metrics("aurora")
        expected_avg = sum(ratings) / len(ratings)
        assert abs(m.avg_rating - expected_avg) < 0.01

    def test_economics(self, tracker):
        for i in range(5):
            record = TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category="research",
                started_at=time.time(), completed_at=time.time() + 60,
                success=True, bounty_usd=0.50, cost_usd=0.05,
            )
            tracker.records.append(record)
        
        m = tracker.agent_metrics("aurora")
        assert abs(m.total_earned_usd - 2.50) < 0.01
        assert abs(m.total_cost_usd - 0.25) < 0.01
        assert abs(m.net_profit_usd - 2.25) < 0.01
        assert m.cost_efficiency == 10.0  # $2.50 / $0.25

    def test_category_breakdown(self, tracker):
        categories = ["research", "research", "code_review", "research", "code_review"]
        successes = [True, True, True, False, True]
        
        for i, (cat, success) in enumerate(zip(categories, successes)):
            record = TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category=cat,
                started_at=time.time(), completed_at=time.time() + 60,
                success=success,
            )
            tracker.records.append(record)
        
        m = tracker.agent_metrics("aurora")
        assert m.category_counts["research"] == 3
        assert m.category_counts["code_review"] == 2
        assert abs(m.category_success_rates["research"] - 2/3) < 0.01
        assert abs(m.category_success_rates["code_review"] - 1.0) < 0.01

    def test_consecutive_failures(self, tracker):
        for i in range(5):
            record = TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category="research",
                started_at=time.time() - (5-i) * 60,
                completed_at=time.time() - (5-i) * 60 + 30,
                success=i < 2,  # First 2 succeed, last 3 fail
            )
            tracker.records.append(record)
        
        m = tracker.agent_metrics("aurora")
        assert m.consecutive_failures == 3

    def test_cost_efficiency_no_cost(self, tracker):
        """Agent with earnings but no cost → infinite efficiency."""
        record = TaskRecord(
            task_id="t1", agent_id="aurora", category="research",
            started_at=time.time(), completed_at=time.time() + 60,
            success=True, bounty_usd=0.50, cost_usd=0.0,
        )
        tracker.records.append(record)
        
        m = tracker.agent_metrics("aurora")
        assert m.cost_efficiency == float('inf')

    def test_window_filtering(self, tracker):
        """Only count tasks within the window."""
        # Old task (15 days ago)
        tracker.records.append(TaskRecord(
            task_id="old", agent_id="aurora", category="research",
            started_at=time.time() - 15 * 86400,
            completed_at=time.time() - 15 * 86400 + 60,
            success=True,
        ))
        # Recent task (1 day ago)
        tracker.records.append(TaskRecord(
            task_id="new", agent_id="aurora", category="research",
            started_at=time.time() - 86400,
            completed_at=time.time() - 86400 + 60,
            success=True,
        ))
        
        m_all = tracker.agent_metrics("aurora")
        m_week = tracker.agent_metrics("aurora", window_days=7)
        
        assert m_all.total_tasks == 2
        assert m_week.total_tasks == 1

    def test_anomaly_consecutive_failures(self, tracker):
        for i in range(5):
            tracker.records.append(TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category="research",
                started_at=time.time() - (5-i) * 60,
                completed_at=time.time() - (5-i) * 60 + 30,
                success=False,
            ))
        
        m = tracker.agent_metrics("aurora")
        assert any("CONSECUTIVE_FAILURES" in f for f in m.anomaly_flags)

    def test_anomaly_low_success_rate(self, tracker):
        for i in range(10):
            tracker.records.append(TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category="research",
                started_at=time.time() - i * 60,
                completed_at=time.time() - i * 60 + 30,
                success=i < 3,  # 30% success rate
            ))
        
        m = tracker.agent_metrics("aurora")
        assert any("LOW_SUCCESS_RATE" in f for f in m.anomaly_flags)


# ── Swarm Report Tests ──

class TestSwarmReport:
    def test_empty_report(self, tracker):
        report = tracker.swarm_report()
        assert report.total_agents == 0
        assert report.total_tasks == 0
        assert report.swarm_success_rate == 0

    def test_basic_report(self, tracker_with_data):
        report = tracker_with_data.swarm_report()
        assert report.total_agents == 3
        assert report.total_tasks == 20
        assert report.active_agents == 3
        assert report.swarm_success_rate > 0
        assert report.total_earned_usd > 0

    def test_top_performers(self, tracker_with_data):
        report = tracker_with_data.swarm_report()
        # Should have top agents (may or may not have enough rated tasks)
        assert isinstance(report.top_agents_by_volume, list)
        assert len(report.top_agents_by_volume) > 0

    def test_category_breakdown(self, tracker_with_data):
        report = tracker_with_data.swarm_report()
        assert len(report.category_breakdown) > 0
        for cat, data in report.category_breakdown.items():
            assert "count" in data
            assert "success_rate" in data
            assert "total_earned" in data

    def test_report_markdown(self, tracker_with_data):
        report = tracker_with_data.swarm_report()
        md = report.to_markdown()
        assert "# KK V2 Swarm Performance Report" in md
        assert "Fleet Summary" in md
        assert "Active Agents" in md

    def test_report_dict(self, tracker_with_data):
        report = tracker_with_data.swarm_report()
        d = report.to_dict()
        assert "total_agents" in d
        assert "total_tasks" in d
        assert "category_breakdown" in d

    def test_window_filtering(self, tracker):
        """Swarm report respects window_days."""
        # Old task
        tracker.records.append(TaskRecord(
            task_id="old", agent_id="aurora", category="research",
            started_at=time.time() - 30 * 86400,
            completed_at=time.time() - 30 * 86400 + 60,
            success=True, bounty_usd=1.00,
        ))
        # Recent task
        tracker.records.append(TaskRecord(
            task_id="new", agent_id="aurora", category="research",
            started_at=time.time() - 86400,
            completed_at=time.time() - 86400 + 60,
            success=True, bounty_usd=0.50,
        ))
        
        report_all = tracker.swarm_report()
        report_week = tracker.swarm_report(window_days=7)
        
        assert report_all.total_tasks == 2
        assert report_week.total_tasks == 1


# ── Persistence Tests ──

class TestPersistence:
    def test_persist_and_load(self, tmp_path):
        path = tmp_path / "perf.json"
        
        # Create and populate
        t1 = AgentPerformanceTracker(persist_path=str(path))
        t1.record_task_start("aurora", "task_001", "research", bounty_usd=0.50)
        t1.record_task_complete("aurora", "task_001", success=True, rating=4.5)
        
        assert path.exists()
        
        # Load in new tracker
        t2 = AgentPerformanceTracker(persist_path=str(path))
        assert len(t2.records) == 1
        assert t2.records[0].task_id == "task_001"
        assert t2.records[0].success is True
        assert t2.records[0].rating == 4.5

    def test_persist_truncates(self, tmp_path):
        """Should keep only last 10K records."""
        path = tmp_path / "perf.json"
        t = AgentPerformanceTracker(persist_path=str(path))
        
        # Add many records
        for i in range(100):
            t.records.append(TaskRecord(
                task_id=f"t{i}", agent_id="aurora", category="research",
                started_at=time.time(), completed_at=time.time() + 60,
                success=True,
            ))
        t._persist()
        
        data = json.loads(path.read_text())
        assert len(data) == 100  # Under 10K limit

    def test_no_persist_path(self, tracker):
        """Should not fail when no persist path."""
        tracker.record_task_start("aurora", "task_001", "research")
        tracker.record_task_complete("aurora", "task_001", success=True)
        # No error


# ── AutoJob Export Tests ──

class TestAutoJobExport:
    def test_export_format(self, tracker):
        tracker.records.append(TaskRecord(
            task_id="task_001", agent_id="aurora", category="research",
            started_at=time.time() - 3600, completed_at=time.time(),
            success=True, bounty_usd=0.50, chain="base",
        ))
        tracker.records.append(TaskRecord(
            task_id="task_002", agent_id="aurora", category="code_review",
            started_at=time.time() - 1800, completed_at=time.time(),
            success=False, bounty_usd=0.25, chain="polygon",
        ))
        
        export = tracker.export_for_autojob("aurora")
        
        # Only successful tasks
        assert len(export) == 1
        assert export[0]["task_id"] == "task_001"
        assert export[0]["category"] == "research"
        assert export[0]["bounty_usd"] == 0.50
        assert export[0]["payment_network"] == "base"
        assert export[0]["status"] == "completed"
        assert "created_at" in export[0]

    def test_export_empty(self, tracker):
        export = tracker.export_for_autojob("nonexistent")
        assert export == []


# ── TaskRecord Tests ──

class TestTaskRecord:
    def test_to_dict(self):
        record = TaskRecord(
            task_id="t1", agent_id="aurora", category="research",
            started_at=100.0, completed_at=400.0,
            success=True, bounty_usd=0.50, cost_usd=0.05,
        )
        d = record.to_dict()
        assert d["duration_seconds"] == 300.0
        assert d["profit_usd"] == 0.45

    def test_no_completion(self):
        record = TaskRecord(
            task_id="t1", agent_id="aurora", category="research",
            started_at=100.0,
        )
        assert record.duration_seconds is None
        assert record.profit_usd == 0.0


# ── Trend Detection Tests ──

class TestTrends:
    def test_improving_trend(self, tracker):
        now = time.time()
        
        # Older records (2 weeks ago) — low ratings
        for i in range(5):
            tracker.records.append(TaskRecord(
                task_id=f"old_{i}", agent_id="aurora", category="research",
                started_at=now - 12 * 86400 + i * 3600,
                completed_at=now - 12 * 86400 + i * 3600 + 300,
                success=True, rating=3.0,
            ))
        
        # Recent records (3 days ago) — high ratings
        for i in range(5):
            tracker.records.append(TaskRecord(
                task_id=f"new_{i}", agent_id="aurora", category="research",
                started_at=now - 3 * 86400 + i * 3600,
                completed_at=now - 3 * 86400 + i * 3600 + 300,
                success=True, rating=4.8,
            ))
        
        m = tracker.agent_metrics("aurora")
        assert m.rating_trend == "improving"

    def test_declining_trend(self, tracker):
        now = time.time()
        
        # Older records — high ratings
        for i in range(5):
            tracker.records.append(TaskRecord(
                task_id=f"old_{i}", agent_id="aurora", category="research",
                started_at=now - 12 * 86400 + i * 3600,
                completed_at=now - 12 * 86400 + i * 3600 + 300,
                success=True, rating=4.8,
            ))
        
        # Recent records — low ratings
        for i in range(5):
            tracker.records.append(TaskRecord(
                task_id=f"new_{i}", agent_id="aurora", category="research",
                started_at=now - 3 * 86400 + i * 3600,
                completed_at=now - 3 * 86400 + i * 3600 + 300,
                success=True, rating=3.0,
            ))
        
        m = tracker.agent_metrics("aurora")
        assert m.rating_trend == "declining"

    def test_stable_trend(self, tracker):
        now = time.time()
        
        # All records have similar ratings
        for week_offset in [12, 3]:
            for i in range(5):
                tracker.records.append(TaskRecord(
                    task_id=f"t_{week_offset}_{i}", agent_id="aurora",
                    category="research",
                    started_at=now - week_offset * 86400 + i * 3600,
                    completed_at=now - week_offset * 86400 + i * 3600 + 300,
                    success=True, rating=4.2,
                ))
        
        m = tracker.agent_metrics("aurora")
        assert m.rating_trend == "stable"
