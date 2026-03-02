"""
Tests for SwarmAnalytics — Performance intelligence engine.

Tests organized by feature:
  1. Agent Efficiency Calculation
  2. Bottleneck Detection
  3. Capacity Forecasting
  4. Trend Analysis
  5. Anomaly Detection
  6. Cost Analysis
  7. Swarm Analyzer (unified interface)
  8. Report Formatting
  9. Persistence
  10. Edge Cases
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.swarm_analytics import (
    AgentEfficiency,
    AnomalyAlert,
    CapacityForecast,
    CostAnalysis,
    StageBottleneck,
    SwarmAnalyzer,
    TrendAnalysis,
    analyze_costs,
    compute_agent_efficiency,
    compute_trend,
    detect_anomalies,
    detect_bottlenecks,
    forecast_capacity,
    format_analytics_text,
    save_analytics_report,
)


# ---------------------------------------------------------------------------
# Test Data Factories
# ---------------------------------------------------------------------------

def make_agents(n: int = 10, working: int = 3, offline: int = 1) -> list[dict]:
    """Create sample lifecycle agent data."""
    agents = []
    for i in range(n):
        if i < working:
            state = "working"
        elif i < n - offline:
            state = "idle"
        else:
            state = "offline"

        agents.append({
            "agent_name": f"kk-agent-{i}",
            "name": f"kk-agent-{i}",
            "state": state,
            "total_successes": max(0, 10 - i),
            "total_failures": max(0, i - 5),
            "consecutive_failures": 0 if i < 7 else i - 6,
        })

    return agents


def make_completed_task(
    task_id: str,
    agent: str,
    bounty: float = 5.0,
    hours_ago: float = 24.0,
) -> dict:
    """Create a completed task dict for analytics."""
    now = datetime.now(timezone.utc)
    created = (now - timedelta(hours=hours_ago)).isoformat()
    completed = (now - timedelta(hours=hours_ago - 2)).isoformat()

    return {
        "task_id": task_id,
        "stage": "completed",
        "title": f"Task {task_id}",
        "category": "photo_verification",
        "bounty_usd": bounty,
        "assigned_agent": agent,
        "created_at": created,
        "stage_entered_at": completed,
        "events": [
            {"timestamp": created, "to_stage": "discovered"},
            {"timestamp": completed, "to_stage": "completed"},
        ],
    }


def make_active_task(
    task_id: str,
    agent: str,
    stage: str = "in_progress",
    bounty: float = 5.0,
    minutes_ago: float = 30.0,
) -> dict:
    """Create an active task dict for analytics."""
    now = datetime.now(timezone.utc)
    entered = (now - timedelta(minutes=minutes_ago)).isoformat()

    return {
        "task_id": task_id,
        "stage": stage,
        "title": f"Task {task_id}",
        "category": "simple_action",
        "bounty_usd": bounty,
        "assigned_agent": agent,
        "created_at": entered,
        "stage_entered_at": entered,
        "events": [
            {"timestamp": entered, "to_stage": "discovered"},
            {"timestamp": entered, "to_stage": stage},
        ],
    }


# ---------------------------------------------------------------------------
# 1. Agent Efficiency Calculation
# ---------------------------------------------------------------------------

class TestAgentEfficiency:
    def test_basic_efficiency(self):
        eff = compute_agent_efficiency(
            agent_name="kk-agent-1",
            tasks_completed=10,
            tasks_failed=2,
            total_earned_usd=50.0,
            completion_times_hours=[1.0, 2.0, 1.5, 2.5],
            observation_days=7.0,
        )
        assert eff.agent_name == "kk-agent-1"
        assert eff.tasks_completed == 10
        assert eff.reliability == pytest.approx(10 / 12, abs=0.01)
        assert eff.throughput_per_day == pytest.approx(10 / 7, abs=0.01)
        assert eff.efficiency_score > 0

    def test_perfect_agent(self):
        eff = compute_agent_efficiency(
            agent_name="perfect",
            tasks_completed=35,
            tasks_failed=0,
            total_earned_usd=175.0,
            completion_times_hours=[0.5] * 35,
            observation_days=7.0,
        )
        assert eff.reliability == 1.0
        assert eff.throughput_per_day == 5.0
        assert eff.efficiency_score >= 80

    def test_new_agent_neutral_score(self):
        eff = compute_agent_efficiency(
            agent_name="newbie",
            tasks_completed=0,
            tasks_failed=0,
            total_earned_usd=0.0,
            completion_times_hours=[],
            observation_days=7.0,
        )
        assert eff.reliability == 0.0  # 0/0 but max(total, 1) = 0/1
        assert eff.efficiency_score >= 0

    def test_unreliable_agent_low_score(self):
        eff = compute_agent_efficiency(
            agent_name="unreliable",
            tasks_completed=2,
            tasks_failed=8,
            total_earned_usd=10.0,
            completion_times_hours=[6.0, 7.0],
            observation_days=7.0,
        )
        assert eff.reliability == 0.2
        assert eff.efficiency_score < 30

    def test_to_dict(self):
        eff = compute_agent_efficiency(
            agent_name="test",
            tasks_completed=5,
            tasks_failed=1,
            total_earned_usd=25.0,
            completion_times_hours=[1.0, 2.0],
        )
        d = eff.to_dict()
        assert d["agent_name"] == "test"
        assert isinstance(d["efficiency_score"], float)


# ---------------------------------------------------------------------------
# 2. Bottleneck Detection
# ---------------------------------------------------------------------------

class TestBottleneckDetection:
    def test_no_bottlenecks_under_threshold(self):
        stage_times = {"discovered": [5.0, 3.0, 4.0]}
        slas = {"discovered": 15.0}
        bottlenecks = detect_bottlenecks(stage_times, slas)
        assert len(bottlenecks) == 0

    def test_medium_bottleneck(self):
        stage_times = {"discovered": [12.0, 13.0, 11.0]}  # avg ~12 min
        slas = {"discovered": 15.0}  # 80% of SLA
        bottlenecks = detect_bottlenecks(stage_times, slas)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].severity == "medium"

    def test_high_bottleneck(self):
        stage_times = {"offered": [12.0, 15.0, 18.0]}  # avg 15 min
        slas = {"offered": 10.0}  # 150% of SLA
        bottlenecks = detect_bottlenecks(stage_times, slas)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].severity == "high"

    def test_critical_bottleneck(self):
        stage_times = {"in_progress": [500.0, 600.0]}  # avg 550 min
        slas = {"in_progress": 240.0}  # 229% of SLA
        bottlenecks = detect_bottlenecks(stage_times, slas)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].severity == "critical"

    def test_multiple_bottlenecks_sorted(self):
        stage_times = {
            "discovered": [12.0],   # medium (80% of 15)
            "offered": [25.0],      # critical (250% of 10)
            "submitted": [40.0],    # high (133% of 30)
        }
        slas = {"discovered": 15.0, "offered": 10.0, "submitted": 30.0}
        bottlenecks = detect_bottlenecks(stage_times, slas)
        assert bottlenecks[0].severity == "critical"
        assert bottlenecks[0].stage == "offered"

    def test_bottleneck_blocked_value(self):
        stage_times = {"offered": [25.0]}
        slas = {"offered": 10.0}
        values = {"offered": 150.0}
        bottlenecks = detect_bottlenecks(stage_times, slas, values)
        assert bottlenecks[0].blocked_value_usd == 150.0

    def test_empty_stage_times(self):
        bottlenecks = detect_bottlenecks({}, {})
        assert len(bottlenecks) == 0


# ---------------------------------------------------------------------------
# 3. Capacity Forecasting
# ---------------------------------------------------------------------------

class TestCapacityForecasting:
    def test_healthy_capacity(self):
        cap = forecast_capacity(
            total_agents=20,
            working_agents=4,
            idle_agents=14,
            offline_agents=2,
            avg_tasks_per_day=10.0,
            avg_intake_per_day=8.0,
        )
        assert cap.recommendation == "healthy"
        assert cap.current_utilization == pytest.approx(4 / 18, abs=0.01)
        assert cap.available_capacity == 14

    def test_monitor_capacity(self):
        cap = forecast_capacity(
            total_agents=10,
            working_agents=5,
            idle_agents=4,
            offline_agents=1,
            avg_tasks_per_day=5.0,
            avg_intake_per_day=7.0,
        )
        assert cap.recommendation == "monitor"

    def test_scale_up_capacity(self):
        cap = forecast_capacity(
            total_agents=10,
            working_agents=7,
            idle_agents=2,
            offline_agents=1,
            avg_tasks_per_day=5.0,
            avg_intake_per_day=8.0,
        )
        assert cap.recommendation == "scale_up"

    def test_overloaded_capacity(self):
        cap = forecast_capacity(
            total_agents=10,
            working_agents=9,
            idle_agents=0,
            offline_agents=1,
            avg_tasks_per_day=3.0,
            avg_intake_per_day=10.0,
        )
        assert cap.recommendation == "overloaded"

    def test_saturation_time_calculated(self):
        cap = forecast_capacity(
            total_agents=10,
            working_agents=5,
            idle_agents=4,
            offline_agents=1,
            avg_tasks_per_day=5.0,
            avg_intake_per_day=9.0,  # Net +4/day
        )
        # 4 idle / 4 net intake = 1 day = 24 hours
        assert cap.time_to_saturation_hours == pytest.approx(24.0, abs=0.1)

    def test_no_saturation_when_completing_faster(self):
        cap = forecast_capacity(
            total_agents=10,
            working_agents=3,
            idle_agents=6,
            offline_agents=1,
            avg_tasks_per_day=10.0,
            avg_intake_per_day=5.0,
        )
        assert cap.time_to_saturation_hours is None

    def test_to_dict(self):
        cap = forecast_capacity(10, 3, 6, 1, 5.0, 5.0)
        d = cap.to_dict()
        assert "recommendation" in d
        assert isinstance(d["current_utilization"], float)


# ---------------------------------------------------------------------------
# 4. Trend Analysis
# ---------------------------------------------------------------------------

class TestTrendAnalysis:
    def test_upward_trend(self):
        trend = compute_trend("volume", [10, 12, 15], [5, 6, 7])
        assert trend.direction == "up"
        assert trend.change_pct > 0

    def test_downward_trend(self):
        trend = compute_trend("volume", [3, 4, 2], [10, 12, 11])
        assert trend.direction == "down"
        assert trend.change_pct < 0

    def test_stable_trend(self):
        trend = compute_trend("rate", [0.80, 0.82, 0.81], [0.79, 0.81, 0.80])
        assert trend.direction == "stable"
        assert abs(trend.change_pct) < 5

    def test_zero_previous_window(self):
        trend = compute_trend("tasks", [5, 10], [])
        assert trend.previous_value == 0

    def test_both_empty(self):
        trend = compute_trend("nothing", [], [])
        assert trend.current_value == 0
        assert trend.direction == "stable"

    def test_to_dict(self):
        trend = compute_trend("test", [10], [5])
        d = trend.to_dict()
        assert d["metric_name"] == "test"


# ---------------------------------------------------------------------------
# 5. Anomaly Detection
# ---------------------------------------------------------------------------

class TestAnomalyDetection:
    def test_no_anomalies_in_uniform_data(self):
        metrics = {
            f"agent-{i}": {"success_rate": 0.85 + i * 0.01}
            for i in range(5)
        }
        alerts = detect_anomalies(metrics)
        assert len(alerts) == 0

    def test_detect_outlier_agent(self):
        # Need enough data with clear outlier — use more agents for better stdev
        metrics = {
            "agent-0": {"failures": 2},
            "agent-1": {"failures": 3},
            "agent-2": {"failures": 1},
            "agent-3": {"failures": 2},
            "agent-4": {"failures": 2},
            "agent-5": {"failures": 3},
            "agent-6": {"failures": 1},
            "agent-outlier": {"failures": 50},  # Extreme outlier
        }
        alerts = detect_anomalies(metrics)
        assert len(alerts) >= 1
        outlier_alert = next(a for a in alerts if a.agent_name == "agent-outlier")
        assert outlier_alert.severity in ("warning", "critical")

    def test_insufficient_data_skipped(self):
        """Need at least 3 agents for anomaly detection."""
        metrics = {
            "agent-0": {"failures": 2},
            "agent-1": {"failures": 100},
        }
        alerts = detect_anomalies(metrics)
        assert len(alerts) == 0

    def test_identical_values_no_anomaly(self):
        metrics = {f"a{i}": {"score": 50.0} for i in range(10)}
        alerts = detect_anomalies(metrics)
        assert len(alerts) == 0

    def test_anomaly_severity_levels(self):
        # Create data where one agent is extremely outlier (>3 stdev)
        metrics = {f"a{i}": {"score": 50.0 + i * 0.5} for i in range(10)}
        metrics["outlier"] = {"score": 500.0}  # Way out there
        alerts = detect_anomalies(metrics)
        critical = [a for a in alerts if a.severity == "critical"]
        assert len(critical) >= 1


# ---------------------------------------------------------------------------
# 6. Cost Analysis
# ---------------------------------------------------------------------------

class TestCostAnalysis:
    def test_basic_cost_analysis(self):
        costs = analyze_costs(
            total_revenue_usd=100.0,
            total_tasks=20,
            total_agents=10,
        )
        assert costs.total_revenue_usd == 100.0
        assert costs.platform_fees_usd == pytest.approx(13.0, abs=0.01)
        assert costs.net_profit_usd > 0
        assert costs.profit_margin > 0

    def test_gas_cost_calculation(self):
        costs = analyze_costs(
            total_revenue_usd=50.0,
            total_tasks=10,
            total_agents=5,
            gas_cost_per_tx=0.01,
            transactions_per_task=3,
        )
        # 10 tasks * 3 tx * $0.01 = $0.30 gas
        assert costs.total_gas_cost_usd == pytest.approx(0.30, abs=0.01)

    def test_zero_revenue(self):
        costs = analyze_costs(
            total_revenue_usd=0.0,
            total_tasks=0,
            total_agents=10,
        )
        assert costs.net_profit_usd == 0.0

    def test_roi_calculation(self):
        costs = analyze_costs(
            total_revenue_usd=1000.0,
            total_tasks=100,
            total_agents=20,
        )
        assert costs.roi > 0
        # ROI = profit / cost; with 13% fee, profit ~87%, so ROI should be high
        assert costs.roi > 5

    def test_to_dict(self):
        costs = analyze_costs(100.0, 10, 5)
        d = costs.to_dict()
        assert "net_profit_usd" in d
        assert isinstance(d["roi"], float)


# ---------------------------------------------------------------------------
# 7. Swarm Analyzer (Unified)
# ---------------------------------------------------------------------------

class TestSwarmAnalyzer:
    def test_empty_analyzer(self):
        analyzer = SwarmAnalyzer()
        report = analyzer.full_report()
        assert report["summary"]["total_agents"] == 0
        assert report["summary"]["total_tasks"] == 0

    def test_full_report_structure(self):
        tasks = [
            make_completed_task(f"t{i}", f"kk-agent-{i % 3}", bounty=5.0)
            for i in range(10)
        ]
        agents = make_agents(10, working=3, offline=1)

        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=agents)
        report = analyzer.full_report()

        assert "summary" in report
        assert "agent_efficiency" in report
        assert "bottlenecks" in report
        assert "capacity" in report
        assert "anomalies" in report
        assert "costs" in report
        assert "trends" in report
        assert "generated_at" in report

    def test_agent_efficiency_report(self):
        tasks = [
            make_completed_task("t1", "kk-agent-0", bounty=10.0),
            make_completed_task("t2", "kk-agent-0", bounty=15.0),
            make_completed_task("t3", "kk-agent-1", bounty=5.0),
        ]
        analyzer = SwarmAnalyzer(pipeline_tasks=tasks)
        efficiencies = analyzer.agent_efficiency_report()

        assert len(efficiencies) == 2
        # kk-agent-0 should be ranked higher (more tasks, more earned)
        assert efficiencies[0].agent_name == "kk-agent-0"
        assert efficiencies[0].tasks_completed == 2
        assert efficiencies[0].total_earned_usd == 25.0

    def test_bottleneck_report_with_stuck_tasks(self):
        # Create tasks stuck in stages for a long time
        tasks = [
            make_active_task("t1", "kk-agent-0", stage="offered", minutes_ago=60),
            make_active_task("t2", "kk-agent-1", stage="offered", minutes_ago=45),
        ]
        analyzer = SwarmAnalyzer(pipeline_tasks=tasks)
        bottlenecks = analyzer.bottleneck_report()

        # offered SLA is 10 min, 45-60 min is critical
        assert len(bottlenecks) >= 1
        assert bottlenecks[0].stage == "offered"
        assert bottlenecks[0].severity in ("critical", "high")

    def test_capacity_report(self):
        agents = make_agents(20, working=5, offline=2)
        tasks = [make_completed_task(f"t{i}", "a") for i in range(14)]

        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=agents)
        cap = analyzer.capacity_report()

        assert cap.max_concurrent_tasks == 18  # 20 - 2 offline
        assert cap.tasks_in_progress == 5
        assert cap.recommendation in ("healthy", "monitor")

    def test_cost_report(self):
        tasks = [make_completed_task(f"t{i}", "a", bounty=10.0) for i in range(5)]
        agents = make_agents(5)

        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=agents)
        costs = analyzer.cost_report()

        assert costs.total_revenue_usd == 50.0
        assert costs.platform_fees_usd == pytest.approx(6.5, abs=0.01)

    def test_trend_report(self):
        tasks = [
            make_completed_task(f"recent-{i}", "a", hours_ago=12)
            for i in range(5)
        ] + [
            make_completed_task(f"old-{i}", "a", hours_ago=120)
            for i in range(2)
        ]

        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, observation_days=14)
        trends = analyzer.trend_report()

        assert len(trends) >= 2
        volume_trend = next(t for t in trends if t.metric_name == "task_volume")
        assert volume_trend.direction == "up"  # More recent tasks


# ---------------------------------------------------------------------------
# 8. Report Formatting
# ---------------------------------------------------------------------------

class TestReportFormatting:
    def test_format_empty_report(self):
        analyzer = SwarmAnalyzer()
        report = analyzer.full_report()
        text = format_analytics_text(report)
        assert "📊" in text
        assert "KK Swarm Analytics" in text

    def test_format_report_with_data(self):
        tasks = [make_completed_task(f"t{i}", f"kk-agent-{i}") for i in range(5)]
        agents = make_agents(5)

        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=agents)
        report = analyzer.full_report()
        text = format_analytics_text(report)

        assert "Agents:" in text
        assert "Tasks:" in text
        assert "Net Profit:" in text

    def test_format_report_with_bottlenecks(self):
        tasks = [
            make_active_task("t1", "a", stage="offered", minutes_ago=60),
        ]
        agents = make_agents(5)

        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=agents)
        report = analyzer.full_report()
        text = format_analytics_text(report)
        assert "🚨" in text or "Bottleneck" in text


# ---------------------------------------------------------------------------
# 9. Persistence
# ---------------------------------------------------------------------------

class TestAnalyticsPersistence:
    def test_save_report(self):
        analyzer = SwarmAnalyzer(
            pipeline_tasks=[make_completed_task("t1", "a")],
            lifecycle_agents=make_agents(3),
        )
        report = analyzer.full_report()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_analytics_report(report, Path(tmpdir))
            assert path.exists()

            loaded = json.loads(path.read_text())
            assert "summary" in loaded
            assert loaded["summary"]["total_tasks"] == 1


# ---------------------------------------------------------------------------
# 10. Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_single_agent_no_anomalies(self):
        """With only 1 agent, anomaly detection should be empty."""
        agents = make_agents(1)
        analyzer = SwarmAnalyzer(lifecycle_agents=agents)
        anomalies = analyzer.anomaly_report()
        assert len(anomalies) == 0

    def test_all_tasks_failed(self):
        tasks = [
            {"task_id": f"t{i}", "stage": "failed", "bounty_usd": 5.0,
             "assigned_agent": "a", "created_at": datetime.now(timezone.utc).isoformat(),
             "stage_entered_at": datetime.now(timezone.utc).isoformat(), "events": []}
            for i in range(5)
        ]
        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=make_agents(3))
        report = analyzer.full_report()
        assert report["costs"]["total_revenue_usd"] == 0

    def test_no_lifecycle_agents(self):
        tasks = [make_completed_task("t1", "a")]
        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=[])
        cap = analyzer.capacity_report()
        assert cap.recommendation == "healthy"  # 0 of 0 utilized

    def test_large_swarm(self):
        """Test with realistic swarm size (24 agents, 100 tasks)."""
        agents = make_agents(24, working=8, offline=2)
        tasks = [
            make_completed_task(f"t{i}", f"kk-agent-{i % 22}", bounty=3.0 + i * 0.1)
            for i in range(100)
        ]
        analyzer = SwarmAnalyzer(pipeline_tasks=tasks, lifecycle_agents=agents)
        report = analyzer.full_report()

        assert report["summary"]["total_agents"] == 24
        assert report["summary"]["total_tasks"] == 100
        assert len(report["agent_efficiency"]) > 0
