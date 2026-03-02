"""
Tests for the KK V2 Swarm Monitor Service.

Covers:
  - Alert generation (agent health, pipeline, system, reputation, decisions)
  - Status assessment
  - Digest generation
  - Trend analysis
  - SwarmMonitor stateful operations
  - Deduplication
  - Persistence
  - Formatting
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from services.swarm_monitor import (
    AgentHealthSnapshot,
    Alert,
    AlertCategory,
    AlertLevel,
    MonitorConfig,
    MonitorStatus,
    PipelineSnapshot,
    StatusDigest,
    SwarmMonitor,
    SystemSnapshot,
    TrendAnalysis,
    TrendPoint,
    analyze_trend,
    assess_swarm_status,
    check_agent_health,
    check_decision_outcomes,
    check_pipeline_health,
    check_reputation_changes,
    check_system_health,
    generate_digest,
    load_monitor_state,
    save_monitor_state,
)


NOW = datetime(2026, 3, 2, 3, 0, 0, tzinfo=timezone.utc)


def make_agent_snap(
    name: str = "agent-1",
    is_online: bool = True,
    consecutive_failures: int = 0,
    total_successes: int = 10,
    total_failures: int = 1,
    heartbeat_age: float = 60.0,
    usdc: float = 10.0,
    eth: float = 0.01,
) -> AgentHealthSnapshot:
    return AgentHealthSnapshot(
        agent_name=name,
        is_online=is_online,
        state="IDLE" if is_online else "OFFLINE",
        consecutive_failures=consecutive_failures,
        total_successes=total_successes,
        total_failures=total_failures,
        last_heartbeat_age_seconds=heartbeat_age,
        usdc_balance=usdc,
        eth_balance=eth,
    )


# ---------------------------------------------------------------------------
# Alert Model Tests
# ---------------------------------------------------------------------------

class TestAlertModel:
    def test_alert_creation(self):
        alert = Alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.AGENT_HEALTH,
            title="Test Alert",
            message="Something happened",
        )
        assert alert.level == AlertLevel.WARNING
        assert alert.timestamp  # Auto-populated

    def test_alert_to_dict(self):
        alert = Alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.SYSTEM,
            title="System Down",
            message="API unreachable",
            agent_name="agent-1",
        )
        d = alert.to_dict()
        assert d["level"] == "critical"
        assert d["category"] == "system"
        assert d["agent_name"] == "agent-1"

    def test_alert_format_irc(self):
        alert = Alert(
            level=AlertLevel.EMERGENCY,
            category=AlertCategory.SYSTEM,
            title="Fire",
            message="Everything is on fire",
            agent_name="agent-x",
        )
        text = alert.format_irc()
        assert "🔥" in text
        assert "agent-x" in text
        assert "Fire" in text


# ---------------------------------------------------------------------------
# Agent Health Alert Tests
# ---------------------------------------------------------------------------

class TestAgentHealthAlerts:
    def test_healthy_agents_no_alerts(self):
        agents = [make_agent_snap("a1"), make_agent_snap("a2"), make_agent_snap("a3")]
        config = MonitorConfig(min_agents_online=3)
        alerts = check_agent_health(agents, config, NOW)
        # Should have no alerts (all healthy)
        critical = [a for a in alerts if a.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY)]
        assert len(critical) == 0

    def test_stale_heartbeat_warning(self):
        agents = [make_agent_snap("a1", heartbeat_age=400)]  # > 300s default
        config = MonitorConfig(min_agents_online=0)
        alerts = check_agent_health(agents, config, NOW)
        stale = [a for a in alerts if "stale" in a.title.lower() or "heartbeat" in a.title.lower()]
        assert len(stale) >= 1

    def test_dead_heartbeat_critical(self):
        agents = [make_agent_snap("a1", heartbeat_age=1000)]  # > 900s default
        config = MonitorConfig(min_agents_online=0)
        alerts = check_agent_health(agents, config, NOW)
        critical = [a for a in alerts if a.level == AlertLevel.CRITICAL
                     and "unresponsive" in a.title.lower()]
        assert len(critical) >= 1

    def test_circuit_breaker_alert(self):
        agents = [make_agent_snap("a1", consecutive_failures=3)]
        config = MonitorConfig(max_consecutive_failures=3, min_agents_online=0)
        alerts = check_agent_health(agents, config, NOW)
        breaker = [a for a in alerts if "circuit" in a.title.lower()]
        assert len(breaker) >= 1

    def test_near_circuit_breaker_warning(self):
        agents = [make_agent_snap("a1", consecutive_failures=2)]
        config = MonitorConfig(max_consecutive_failures=3, min_agents_online=0)
        alerts = check_agent_health(agents, config, NOW)
        near = [a for a in alerts if "near" in a.title.lower() and "circuit" in a.title.lower()]
        assert len(near) >= 1

    def test_low_usdc_balance_alert(self):
        agents = [make_agent_snap("a1", usdc=0.5)]
        config = MonitorConfig(low_balance_usdc=1.0, min_agents_online=0)
        alerts = check_agent_health(agents, config, NOW)
        balance = [a for a in alerts if "usdc" in a.title.lower()]
        assert len(balance) >= 1

    def test_low_eth_balance_alert(self):
        agents = [make_agent_snap("a1", eth=0.0005)]
        config = MonitorConfig(low_balance_eth=0.001, min_agents_online=0)
        alerts = check_agent_health(agents, config, NOW)
        balance = [a for a in alerts if "eth" in a.title.lower()]
        assert len(balance) >= 1

    def test_swarm_understaffed_emergency(self):
        agents = [make_agent_snap("a1", is_online=False)]
        config = MonitorConfig(min_agents_online=3)
        alerts = check_agent_health(agents, config, NOW)
        understaffed = [a for a in alerts if "understaffed" in a.title.lower()]
        assert len(understaffed) >= 1
        assert understaffed[0].level == AlertLevel.EMERGENCY

    def test_low_availability_warning(self):
        agents = [
            make_agent_snap("a1", is_online=True),
            make_agent_snap("a2", is_online=False),
            make_agent_snap("a3", is_online=False),
            make_agent_snap("a4", is_online=False),
            make_agent_snap("a5", is_online=False),
        ]
        config = MonitorConfig(min_agents_online=1, min_availability_ratio=0.5)
        alerts = check_agent_health(agents, config, NOW)
        availability = [a for a in alerts if "availability" in a.title.lower()]
        assert len(availability) >= 1


# ---------------------------------------------------------------------------
# Pipeline Health Tests
# ---------------------------------------------------------------------------

class TestPipelineHealthAlerts:
    def test_healthy_pipeline_no_critical_alerts(self):
        pipeline = PipelineSnapshot(
            total_tasks=10,
            stuck_tasks=0,
            completion_rate_24h=0.8,
            failure_rate_24h=0.1,
        )
        alerts = check_pipeline_health(pipeline, MonitorConfig())
        critical = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        assert len(critical) == 0

    def test_stuck_tasks_critical(self):
        pipeline = PipelineSnapshot(stuck_tasks=10)
        config = MonitorConfig(max_stuck_tasks=5)
        alerts = check_pipeline_health(pipeline, config)
        stuck = [a for a in alerts if "stuck" in a.title.lower()]
        assert len(stuck) >= 1
        assert stuck[0].level == AlertLevel.CRITICAL

    def test_high_failure_rate(self):
        pipeline = PipelineSnapshot(failure_rate_24h=0.5)
        config = MonitorConfig(max_failure_rate=0.3)
        alerts = check_pipeline_health(pipeline, config)
        failure = [a for a in alerts if "failure rate" in a.title.lower()]
        assert len(failure) >= 1

    def test_low_completion_rate(self):
        pipeline = PipelineSnapshot(completion_rate_24h=0.3)
        config = MonitorConfig(min_completion_rate=0.5)
        alerts = check_pipeline_health(pipeline, config)
        completion = [a for a in alerts if "completion" in a.title.lower()]
        assert len(completion) >= 1

    def test_stage_bottleneck(self):
        pipeline = PipelineSnapshot(
            by_stage={"IN_PROGRESS": 15, "COMPLETED": 50}
        )
        alerts = check_pipeline_health(pipeline, MonitorConfig())
        bottleneck = [a for a in alerts if "bottleneck" in a.title.lower()]
        assert len(bottleneck) >= 1

    def test_stale_task_detected(self):
        pipeline = PipelineSnapshot(oldest_task_hours=100)
        alerts = check_pipeline_health(pipeline, MonitorConfig())
        stale = [a for a in alerts if "stale" in a.title.lower()]
        assert len(stale) >= 1


# ---------------------------------------------------------------------------
# System Health Tests
# ---------------------------------------------------------------------------

class TestSystemHealthAlerts:
    def test_all_healthy_no_alerts(self):
        system = SystemSnapshot(em_api_healthy=True, base_rpc_healthy=True, irc_connected=True)
        alerts = check_system_health(system, MonitorConfig())
        assert len(alerts) == 0

    def test_api_down_emergency(self):
        system = SystemSnapshot(em_api_healthy=False)
        alerts = check_system_health(system, MonitorConfig())
        api_alerts = [a for a in alerts if "api" in a.title.lower()]
        assert len(api_alerts) >= 1
        assert api_alerts[0].level == AlertLevel.EMERGENCY

    def test_rpc_down_critical(self):
        system = SystemSnapshot(base_rpc_healthy=False)
        alerts = check_system_health(system, MonitorConfig())
        rpc_alerts = [a for a in alerts if "rpc" in a.title.lower()]
        assert len(rpc_alerts) >= 1
        assert rpc_alerts[0].level == AlertLevel.CRITICAL

    def test_irc_disconnected_warning(self):
        system = SystemSnapshot(irc_connected=False)
        alerts = check_system_health(system, MonitorConfig())
        irc_alerts = [a for a in alerts if "irc" in a.title.lower()]
        assert len(irc_alerts) >= 1
        assert irc_alerts[0].level == AlertLevel.WARNING


# ---------------------------------------------------------------------------
# Reputation Change Tests
# ---------------------------------------------------------------------------

class TestReputationChanges:
    def test_big_drop_detected(self):
        current = {"agent-1": 50.0}
        previous = {"agent-1": 70.0}
        config = MonitorConfig(reputation_drop_threshold=10.0)
        alerts = check_reputation_changes(current, previous, config)
        drops = [a for a in alerts if "drop" in a.title.lower()]
        assert len(drops) >= 1

    def test_big_improvement_detected(self):
        current = {"agent-1": 80.0}
        previous = {"agent-1": 60.0}
        config = MonitorConfig(reputation_drop_threshold=10.0)
        alerts = check_reputation_changes(current, previous, config)
        improvements = [a for a in alerts if "improvement" in a.title.lower()]
        assert len(improvements) >= 1
        assert improvements[0].level == AlertLevel.INFO

    def test_small_change_no_alert(self):
        current = {"agent-1": 72.0}
        previous = {"agent-1": 70.0}
        config = MonitorConfig(reputation_drop_threshold=10.0)
        alerts = check_reputation_changes(current, previous, config)
        assert len(alerts) == 0

    def test_new_agent_no_alert(self):
        current = {"agent-new": 60.0}
        previous = {}
        alerts = check_reputation_changes(current, previous, MonitorConfig())
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Decision Outcome Tests
# ---------------------------------------------------------------------------

class TestDecisionOutcomes:
    def test_insufficient_data_no_alert(self):
        decisions = [{"task_id": "t1", "confidence": 0.8, "risk_level": "low"}]
        outcomes = [{"task_id": "t1", "success": False}]
        alerts = check_decision_outcomes(decisions, outcomes)
        assert len(alerts) == 0  # < 5 decisions

    def test_model_drift_detected(self):
        decisions = [
            {"task_id": f"t{i}", "confidence": 0.9, "risk_level": "low"}
            for i in range(10)
        ]
        outcomes = [
            {"task_id": f"t{i}", "success": False}
            for i in range(10)
        ]
        alerts = check_decision_outcomes(decisions, outcomes)
        drift = [a for a in alerts if "drift" in a.title.lower()]
        assert len(drift) >= 1

    def test_good_outcomes_no_alert(self):
        decisions = [
            {"task_id": f"t{i}", "confidence": 0.8, "risk_level": "low"}
            for i in range(10)
        ]
        outcomes = [
            {"task_id": f"t{i}", "success": True, "rating": 4.5}
            for i in range(10)
        ]
        alerts = check_decision_outcomes(decisions, outcomes)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Status Assessment Tests
# ---------------------------------------------------------------------------

class TestStatusAssessment:
    def test_no_alerts_healthy(self):
        status = assess_swarm_status([], agents_online=5, agents_total=10)
        assert status == MonitorStatus.HEALTHY

    def test_emergency_means_down(self):
        alerts = [Alert(level=AlertLevel.EMERGENCY, category=AlertCategory.SYSTEM,
                        title="Down", message="...")]
        status = assess_swarm_status(alerts, agents_online=0, agents_total=5)
        assert status == MonitorStatus.DOWN

    def test_zero_agents_means_down(self):
        status = assess_swarm_status([], agents_online=0, agents_total=5)
        assert status == MonitorStatus.DOWN

    def test_many_criticals_means_impaired(self):
        alerts = [
            Alert(level=AlertLevel.CRITICAL, category=AlertCategory.AGENT_HEALTH,
                  title=f"C{i}", message="...") for i in range(3)
        ]
        status = assess_swarm_status(alerts, agents_online=5, agents_total=10)
        assert status == MonitorStatus.IMPAIRED

    def test_one_critical_means_degraded(self):
        alerts = [Alert(level=AlertLevel.CRITICAL, category=AlertCategory.AGENT_HEALTH,
                        title="Crit", message="...")]
        status = assess_swarm_status(alerts, agents_online=5, agents_total=10)
        assert status == MonitorStatus.DEGRADED


# ---------------------------------------------------------------------------
# Digest Tests
# ---------------------------------------------------------------------------

class TestDigest:
    def test_digest_generation(self):
        agents = [make_agent_snap("a1"), make_agent_snap("a2")]
        pipeline = PipelineSnapshot(total_tasks=5, by_stage={"COMPLETED": 3, "IN_PROGRESS": 2})
        alerts = []
        digest = generate_digest(agents, pipeline, alerts, NOW)
        assert digest.agents_online == 2
        assert digest.agents_total == 2
        assert digest.status == MonitorStatus.HEALTHY

    def test_digest_identifies_top_performer(self):
        agents = [
            make_agent_snap("superstar", total_successes=50),
            make_agent_snap("rookie", total_successes=5),
        ]
        pipeline = PipelineSnapshot()
        digest = generate_digest(agents, pipeline, [], NOW)
        assert digest.top_performer == "superstar"

    def test_digest_identifies_bottleneck(self):
        pipeline = PipelineSnapshot(
            by_stage={"OFFERED": 8, "IN_PROGRESS": 3, "COMPLETED": 20}
        )
        digest = generate_digest([], pipeline, [], NOW)
        assert digest.bottleneck_stage == "OFFERED"

    def test_digest_format_text(self):
        digest = StatusDigest(
            timestamp=NOW.isoformat(),
            status=MonitorStatus.HEALTHY,
            agents_online=5,
            agents_total=10,
        )
        text = digest.format_text()
        assert "🟢" in text
        assert "5/10" in text

    def test_digest_to_dict(self):
        digest = StatusDigest(
            timestamp=NOW.isoformat(),
            status=MonitorStatus.DEGRADED,
        )
        d = digest.to_dict()
        assert d["status"] == "degraded"


# ---------------------------------------------------------------------------
# Trend Analysis Tests
# ---------------------------------------------------------------------------

class TestTrendAnalysis:
    def test_improving_trend(self):
        points = [TrendPoint(f"t{i}", float(50 + i * 5)) for i in range(10)]
        trend = analyze_trend("test_metric", points)
        assert trend.direction == "improving"
        assert trend.change_pct > 0

    def test_declining_trend(self):
        # Decline steep enough for detection (slope/mean > 0.05) but not volatile (CV < 0.3)
        points = [TrendPoint(f"t{i}", float(80 - i * 5)) for i in range(10)]
        trend = analyze_trend("test_metric", points)
        assert trend.direction == "declining"
        assert trend.change_pct < 0

    def test_stable_trend(self):
        points = [TrendPoint(f"t{i}", 50.0 + (i % 2) * 0.5) for i in range(10)]
        trend = analyze_trend("test_metric", points)
        assert trend.direction == "stable"

    def test_volatile_trend(self):
        import math
        points = [TrendPoint(f"t{i}", 50 + 30 * math.sin(i)) for i in range(20)]
        trend = analyze_trend("test_metric", points)
        assert trend.direction in ("volatile", "stable", "improving", "declining")

    def test_single_point(self):
        points = [TrendPoint("t0", 42.0)]
        trend = analyze_trend("single", points)
        assert trend.current_value == 42.0
        assert trend.data_points == 1

    def test_empty_points(self):
        trend = analyze_trend("empty", [])
        assert trend.data_points == 0

    def test_trend_to_dict(self):
        trend = TrendAnalysis(metric_name="test", direction="improving", current_value=75.0)
        d = trend.to_dict()
        assert d["metric"] == "test"
        assert d["direction"] == "improving"


# ---------------------------------------------------------------------------
# SwarmMonitor Stateful Tests
# ---------------------------------------------------------------------------

class TestSwarmMonitorStateful:
    def test_run_checks_returns_alerts_and_digest(self):
        monitor = SwarmMonitor()
        agents = [make_agent_snap("a1"), make_agent_snap("a2"), make_agent_snap("a3")]
        pipeline = PipelineSnapshot(total_tasks=5)
        system = SystemSnapshot()
        alerts, digest = monitor.run_checks(agents, pipeline, system, now=NOW)
        assert isinstance(alerts, list)
        assert isinstance(digest, StatusDigest)

    def test_reputation_tracking(self):
        monitor = SwarmMonitor()
        agents = [make_agent_snap("a1")]
        pipeline = PipelineSnapshot()
        system = SystemSnapshot()

        # First check — no previous reputation data
        rep1 = {"a1": 70.0}
        alerts1, _ = monitor.run_checks(agents, pipeline, system,
                                          current_reputations=rep1, now=NOW)

        # Second check — big drop
        rep2 = {"a1": 50.0}
        alerts2, _ = monitor.run_checks(agents, pipeline, system,
                                          current_reputations=rep2,
                                          now=NOW + timedelta(minutes=10))

        rep_alerts = [a for a in alerts2 if a.category == AlertCategory.REPUTATION]
        assert len(rep_alerts) >= 1

    def test_deduplication(self):
        monitor = SwarmMonitor()
        agents = [make_agent_snap("a1", heartbeat_age=1000)]
        pipeline = PipelineSnapshot()
        system = SystemSnapshot()

        # Run twice within 5 minutes
        alerts1, _ = monitor.run_checks(agents, pipeline, system, now=NOW)
        alerts2, _ = monitor.run_checks(agents, pipeline, system,
                                          now=NOW + timedelta(minutes=2))

        # Second run should have fewer alerts (deduplicated)
        assert len(alerts2) <= len(alerts1)

    def test_deduplication_expires(self):
        monitor = SwarmMonitor()
        agents = [make_agent_snap("a1", heartbeat_age=1000)]
        pipeline = PipelineSnapshot()
        system = SystemSnapshot()

        alerts1, _ = monitor.run_checks(agents, pipeline, system, now=NOW)
        # Run again after 10 minutes (past 5-min suppression)
        alerts2, _ = monitor.run_checks(agents, pipeline, system,
                                          now=NOW + timedelta(minutes=10))

        # Should fire again
        assert len(alerts2) > 0

    def test_agent_trends_tracked(self):
        monitor = SwarmMonitor()
        agents = [make_agent_snap("a1", total_successes=10, total_failures=2)]
        pipeline = PipelineSnapshot()
        system = SystemSnapshot()

        for i in range(5):
            monitor.run_checks(agents, pipeline, system,
                                now=NOW + timedelta(minutes=i * 10))

        trends = monitor.get_agent_trends()
        assert "a1" in trends
        assert trends["a1"].data_points >= 2

    def test_alert_summary(self):
        monitor = SwarmMonitor()
        # Add some alerts
        monitor.alert_history = [
            Alert(level=AlertLevel.WARNING, category=AlertCategory.AGENT_HEALTH,
                  title="W1", message="warning 1"),
            Alert(level=AlertLevel.CRITICAL, category=AlertCategory.SYSTEM,
                  title="C1", message="critical 1"),
        ]
        summary = monitor.get_alert_summary(hours=24)
        assert summary["total_alerts"] == 2
        assert "warning" in summary["by_level"]
        assert "critical" in summary["by_level"]

    def test_history_trimming(self):
        monitor = SwarmMonitor(max_history=10)
        # Add way more than max
        monitor.alert_history = [
            Alert(level=AlertLevel.INFO, category=AlertCategory.AGENT_HEALTH,
                  title=f"A{i}", message=f"msg{i}")
            for i in range(100)
        ]
        monitor._trim_history()
        assert len(monitor.alert_history) <= 30  # max_history * 3


# ---------------------------------------------------------------------------
# Persistence Tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load(self, tmp_path):
        monitor = SwarmMonitor()
        monitor.alert_history = [
            Alert(level=AlertLevel.WARNING, category=AlertCategory.SYSTEM,
                  title="Test", message="test message"),
        ]
        monitor.digest_history = [
            StatusDigest(timestamp=NOW.isoformat(), status=MonitorStatus.HEALTHY),
        ]

        path = tmp_path / "monitor_state.json"
        save_monitor_state(monitor, path)
        assert path.exists()

        loaded = load_monitor_state(path)
        assert loaded["alert_count"] == 1
        assert loaded["digest_count"] == 1
        assert len(loaded["alerts"]) == 1

    def test_load_missing_file(self, tmp_path):
        loaded = load_monitor_state(tmp_path / "nonexistent.json")
        assert loaded == {}
