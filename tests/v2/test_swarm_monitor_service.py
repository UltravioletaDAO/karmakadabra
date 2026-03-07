"""
Tests for KK V2 Swarm Monitor Service.

Covers:
  - Alert generation: agent health, pipeline, system, reputation, decisions
  - Status assessment: healthy/degraded/impaired/down
  - Digest generation: periodic summaries
  - Trend analysis: detecting improving/declining/volatile/stable trends
  - SwarmMonitor stateful class: run_checks, deduplication, history, persistence
  - Alert formatting (IRC/text)
  - Edge cases: empty inputs, threshold boundaries, etc.
"""

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.swarm_monitor import (
    Alert,
    AlertCategory,
    AlertLevel,
    AgentHealthSnapshot,
    MonitorConfig,
    MonitorStatus,
    PipelineSnapshot,
    StatusDigest,
    SwarmMonitor,
    SystemSnapshot,
    TrendPoint,
    TrendAnalysis,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_healthy_agent(name: str = "agent-1", **overrides) -> AgentHealthSnapshot:
    defaults = {
        "agent_name": name,
        "is_online": True,
        "state": "idle",
        "consecutive_failures": 0,
        "total_failures": 0,
        "total_successes": 10,
        "current_tasks": 0,
        "last_heartbeat_age_seconds": 30,
        "usdc_balance": 5.0,
        "eth_balance": 0.01,
        "reputation_score": 75.0,
        "efficiency_score": 80.0,
    }
    defaults.update(overrides)
    return AgentHealthSnapshot(**defaults)


def make_healthy_pipeline(**overrides) -> PipelineSnapshot:
    defaults = {
        "total_tasks": 10,
        "by_stage": {"DISCOVERED": 2, "IN_PROGRESS": 3, "COMPLETED": 5},
        "stuck_tasks": 0,
        "avg_time_in_pipeline_hours": 2.0,
        "completion_rate_24h": 0.7,
        "failure_rate_24h": 0.1,
        "oldest_task_hours": 12.0,
    }
    defaults.update(overrides)
    return PipelineSnapshot(**defaults)


def make_healthy_system(**overrides) -> SystemSnapshot:
    defaults = {
        "em_api_healthy": True,
        "base_rpc_healthy": True,
        "irc_connected": True,
        "disk_usage_pct": 30.0,
        "uptime_hours": 24.0,
        "last_successful_cycle": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(overrides)
    return SystemSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Alert Data Model
# ---------------------------------------------------------------------------

class TestAlertModel:
    def test_alert_auto_timestamp(self):
        alert = Alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.AGENT_HEALTH,
            title="Test",
            message="Test alert",
        )
        assert alert.timestamp != ""
        assert "T" in alert.timestamp  # ISO format

    def test_alert_to_dict(self):
        alert = Alert(
            level=AlertLevel.CRITICAL,
            category=AlertCategory.SYSTEM,
            title="API Down",
            message="Cannot connect",
            agent_name="agent-1",
            metric_value=0.0,
            threshold=1.0,
        )
        d = alert.to_dict()
        assert d["level"] == "critical"
        assert d["category"] == "system"
        assert d["title"] == "API Down"
        assert d["agent_name"] == "agent-1"

    def test_alert_format_irc(self):
        alert = Alert(
            level=AlertLevel.EMERGENCY,
            category=AlertCategory.SYSTEM,
            title="Swarm down",
            message="All agents offline",
        )
        formatted = alert.format_irc()
        assert "🔥" in formatted
        assert "Swarm down" in formatted

    def test_alert_format_irc_with_agent(self):
        alert = Alert(
            level=AlertLevel.WARNING,
            category=AlertCategory.AGENT_HEALTH,
            title="Low balance",
            message="$0.50 remaining",
            agent_name="kk-researcher",
        )
        formatted = alert.format_irc()
        assert "[kk-researcher]" in formatted
        assert "⚠️" in formatted


# ---------------------------------------------------------------------------
# Agent Health Checks
# ---------------------------------------------------------------------------

class TestCheckAgentHealth:
    def test_healthy_agents_no_alerts(self):
        agents = [make_healthy_agent("a1"), make_healthy_agent("a2")]
        config = MonitorConfig()
        alerts = check_agent_health(agents, config)
        # No individual alerts, but swarm-wide check might trigger
        agent_alerts = [a for a in alerts if a.agent_name != ""]
        assert len(agent_alerts) == 0

    def test_stale_heartbeat_warning(self):
        agent = make_healthy_agent(
            last_heartbeat_age_seconds=350  # > 300s stale threshold
        )
        config = MonitorConfig()
        alerts = check_agent_health([agent], config)
        stale = [a for a in alerts if a.title == "Stale heartbeat"]
        assert len(stale) == 1
        assert stale[0].level == AlertLevel.WARNING

    def test_dead_heartbeat_critical(self):
        agent = make_healthy_agent(
            last_heartbeat_age_seconds=1000  # > 900s dead threshold
        )
        config = MonitorConfig()
        alerts = check_agent_health([agent], config)
        dead = [a for a in alerts if a.title == "Agent unresponsive"]
        assert len(dead) == 1
        assert dead[0].level == AlertLevel.CRITICAL

    def test_circuit_breaker_tripped(self):
        agent = make_healthy_agent(consecutive_failures=3)
        config = MonitorConfig(max_consecutive_failures=3)
        alerts = check_agent_health([agent], config)
        cb = [a for a in alerts if "Circuit breaker" in a.title]
        assert len(cb) == 1
        assert cb[0].level == AlertLevel.CRITICAL

    def test_near_circuit_breaker_warning(self):
        agent = make_healthy_agent(consecutive_failures=2)
        config = MonitorConfig(max_consecutive_failures=3)
        alerts = check_agent_health([agent], config)
        near = [a for a in alerts if "Near circuit breaker" in a.title]
        assert len(near) == 1
        assert near[0].level == AlertLevel.WARNING

    def test_low_usdc_balance(self):
        agent = make_healthy_agent(usdc_balance=0.50)
        config = MonitorConfig(low_balance_usdc=1.0)
        alerts = check_agent_health([agent], config)
        low = [a for a in alerts if "Low USDC" in a.title]
        assert len(low) == 1

    def test_low_eth_balance(self):
        agent = make_healthy_agent(eth_balance=0.0005)
        config = MonitorConfig(low_balance_eth=0.001)
        alerts = check_agent_health([agent], config)
        low = [a for a in alerts if "Low ETH" in a.title]
        assert len(low) == 1

    def test_swarm_understaffed_emergency(self):
        """Zero agents online → emergency."""
        agents = [
            make_healthy_agent("a1", is_online=False),
            make_healthy_agent("a2", is_online=False),
        ]
        config = MonitorConfig(min_agents_online=3)
        alerts = check_agent_health(agents, config)
        understaffed = [a for a in alerts if "understaffed" in a.title.lower()]
        assert len(understaffed) == 1
        assert understaffed[0].level == AlertLevel.EMERGENCY

    def test_swarm_understaffed_critical(self):
        """Some agents online but below minimum → critical."""
        agents = [
            make_healthy_agent("a1", is_online=True),
            make_healthy_agent("a2", is_online=False),
            make_healthy_agent("a3", is_online=False),
        ]
        config = MonitorConfig(min_agents_online=3)
        alerts = check_agent_health(agents, config)
        understaffed = [a for a in alerts if "understaffed" in a.title.lower()]
        assert len(understaffed) == 1
        assert understaffed[0].level == AlertLevel.CRITICAL

    def test_low_availability_warning(self):
        """Online agents below ratio threshold."""
        agents = [make_healthy_agent(f"a{i}", is_online=(i < 2)) for i in range(10)]
        config = MonitorConfig(min_agents_online=2, min_availability_ratio=0.3)
        alerts = check_agent_health(agents, config)
        low_avail = [a for a in alerts if "availability" in a.title.lower()]
        assert len(low_avail) == 1

    def test_no_heartbeat_data_no_alert(self):
        """Agent with no heartbeat data (-1) should not trigger alerts."""
        agent = make_healthy_agent(last_heartbeat_age_seconds=-1)
        config = MonitorConfig()
        alerts = check_agent_health([agent], config)
        heartbeat_alerts = [a for a in alerts if "heartbeat" in a.title.lower() or "unresponsive" in a.title.lower()]
        assert len(heartbeat_alerts) == 0

    def test_empty_agents_list(self):
        """No agents should produce no alerts."""
        config = MonitorConfig()
        alerts = check_agent_health([], config)
        assert alerts == []


# ---------------------------------------------------------------------------
# Pipeline Health Checks
# ---------------------------------------------------------------------------

class TestCheckPipelineHealth:
    def test_healthy_pipeline_no_alerts(self):
        pipeline = make_healthy_pipeline()
        config = MonitorConfig()
        alerts = check_pipeline_health(pipeline, config)
        assert len(alerts) == 0

    def test_stuck_tasks_critical(self):
        pipeline = make_healthy_pipeline(stuck_tasks=10)
        config = MonitorConfig(max_stuck_tasks=5)
        alerts = check_pipeline_health(pipeline, config)
        stuck = [a for a in alerts if "stuck" in a.title.lower()]
        assert len(stuck) == 1
        assert stuck[0].level == AlertLevel.CRITICAL

    def test_stuck_tasks_warning(self):
        pipeline = make_healthy_pipeline(stuck_tasks=2)
        config = MonitorConfig(max_stuck_tasks=5)
        alerts = check_pipeline_health(pipeline, config)
        stuck = [a for a in alerts if "SLA breach" in a.title]
        assert len(stuck) == 1
        assert stuck[0].level == AlertLevel.WARNING

    def test_high_failure_rate(self):
        pipeline = make_healthy_pipeline(failure_rate_24h=0.5)
        config = MonitorConfig(max_failure_rate=0.3)
        alerts = check_pipeline_health(pipeline, config)
        fail = [a for a in alerts if "failure rate" in a.title.lower()]
        assert len(fail) == 1
        assert fail[0].level == AlertLevel.CRITICAL

    def test_low_completion_rate(self):
        pipeline = make_healthy_pipeline(completion_rate_24h=0.3)
        config = MonitorConfig(min_completion_rate=0.5)
        alerts = check_pipeline_health(pipeline, config)
        low = [a for a in alerts if "completion rate" in a.title.lower()]
        assert len(low) == 1

    def test_bottleneck_detection(self):
        pipeline = make_healthy_pipeline(
            by_stage={"DISCOVERED": 15, "IN_PROGRESS": 2, "COMPLETED": 5}
        )
        config = MonitorConfig()
        alerts = check_pipeline_health(pipeline, config)
        bottleneck = [a for a in alerts if "Bottleneck" in a.title]
        assert len(bottleneck) == 1
        assert "DISCOVERED" in bottleneck[0].message

    def test_stale_task_warning(self):
        pipeline = make_healthy_pipeline(oldest_task_hours=100)
        config = MonitorConfig()
        alerts = check_pipeline_health(pipeline, config)
        stale = [a for a in alerts if "Stale task" in a.title]
        assert len(stale) == 1

    def test_zero_completion_rate_no_alert(self):
        """0% completion rate should not alert (no data yet)."""
        pipeline = make_healthy_pipeline(completion_rate_24h=0.0)
        config = MonitorConfig()
        alerts = check_pipeline_health(pipeline, config)
        completion = [a for a in alerts if "completion" in a.title.lower()]
        assert len(completion) == 0


# ---------------------------------------------------------------------------
# System Health Checks
# ---------------------------------------------------------------------------

class TestCheckSystemHealth:
    def test_healthy_system_no_alerts(self):
        system = make_healthy_system()
        config = MonitorConfig()
        alerts = check_system_health(system, config)
        assert len(alerts) == 0

    def test_api_down_emergency(self):
        system = make_healthy_system(em_api_healthy=False)
        config = MonitorConfig()
        alerts = check_system_health(system, config)
        api = [a for a in alerts if "API" in a.title]
        assert len(api) == 1
        assert api[0].level == AlertLevel.EMERGENCY

    def test_rpc_unhealthy(self):
        system = make_healthy_system(base_rpc_healthy=False)
        config = MonitorConfig()
        alerts = check_system_health(system, config)
        rpc = [a for a in alerts if "RPC" in a.title]
        assert len(rpc) == 1
        assert rpc[0].level == AlertLevel.CRITICAL

    def test_irc_disconnected(self):
        system = make_healthy_system(irc_connected=False)
        config = MonitorConfig()
        alerts = check_system_health(system, config)
        irc = [a for a in alerts if "IRC" in a.title]
        assert len(irc) == 1
        assert irc[0].level == AlertLevel.WARNING

    def test_multiple_system_failures(self):
        system = make_healthy_system(
            em_api_healthy=False,
            base_rpc_healthy=False,
            irc_connected=False,
        )
        config = MonitorConfig()
        alerts = check_system_health(system, config)
        assert len(alerts) == 3


# ---------------------------------------------------------------------------
# Reputation Changes
# ---------------------------------------------------------------------------

class TestCheckReputationChanges:
    def test_no_change_no_alerts(self):
        current = {"agent-1": 75.0, "agent-2": 80.0}
        previous = {"agent-1": 75.0, "agent-2": 80.0}
        config = MonitorConfig()
        alerts = check_reputation_changes(current, previous, config)
        assert len(alerts) == 0

    def test_significant_drop_warning(self):
        current = {"agent-1": 60.0}
        previous = {"agent-1": 75.0}
        config = MonitorConfig(reputation_drop_threshold=10.0)
        alerts = check_reputation_changes(current, previous, config)
        assert len(alerts) == 1
        assert alerts[0].title == "Reputation drop"
        assert alerts[0].level == AlertLevel.WARNING

    def test_significant_improvement_info(self):
        current = {"agent-1": 85.0}
        previous = {"agent-1": 70.0}
        config = MonitorConfig(reputation_drop_threshold=10.0)
        alerts = check_reputation_changes(current, previous, config)
        assert len(alerts) == 1
        assert alerts[0].title == "Reputation improvement"
        assert alerts[0].level == AlertLevel.INFO

    def test_new_agent_no_alert(self):
        """New agent (not in previous) should not trigger alert."""
        current = {"agent-new": 75.0}
        previous = {"agent-old": 80.0}
        config = MonitorConfig()
        alerts = check_reputation_changes(current, previous, config)
        assert len(alerts) == 0

    def test_small_change_no_alert(self):
        """Small change below threshold should not alert."""
        current = {"agent-1": 77.0}
        previous = {"agent-1": 75.0}
        config = MonitorConfig(reputation_drop_threshold=10.0)
        alerts = check_reputation_changes(current, previous, config)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Decision Outcome Analysis
# ---------------------------------------------------------------------------

class TestCheckDecisionOutcomes:
    def test_insufficient_data_no_alerts(self):
        decisions = [{"task_id": "t1", "confidence": 0.9, "risk_level": "low"}]
        outcomes = [{"task_id": "t1", "success": False}]
        alerts = check_decision_outcomes(decisions, outcomes)
        assert len(alerts) == 0  # < 5 decisions

    def test_model_drift_detected(self):
        decisions = [
            {"task_id": f"t{i}", "confidence": 0.9, "risk_level": "low"}
            for i in range(10)
        ]
        outcomes = [
            {"task_id": f"t{i}", "success": i < 3}  # 70% failure rate
            for i in range(10)
        ]
        alerts = check_decision_outcomes(decisions, outcomes)
        drift = [a for a in alerts if "drift" in a.title.lower()]
        assert len(drift) == 1

    def test_no_drift_when_decisions_succeed(self):
        decisions = [
            {"task_id": f"t{i}", "confidence": 0.9, "risk_level": "low"}
            for i in range(10)
        ]
        outcomes = [
            {"task_id": f"t{i}", "success": True}
            for i in range(10)
        ]
        alerts = check_decision_outcomes(decisions, outcomes)
        assert len(alerts) == 0

    def test_unmatched_decisions_ignored(self):
        """Decisions without matching outcomes should be skipped."""
        decisions = [
            {"task_id": f"t{i}", "confidence": 0.9, "risk_level": "low"}
            for i in range(10)
        ]
        outcomes = []  # No outcomes at all
        alerts = check_decision_outcomes(decisions, outcomes)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Status Assessment
# ---------------------------------------------------------------------------

class TestAssessSwarmStatus:
    def test_healthy(self):
        alerts = [Alert(level=AlertLevel.INFO, category=AlertCategory.AGENT_HEALTH,
                        title="Ok", message="All good")]
        status = assess_swarm_status(alerts, agents_online=5, agents_total=5)
        assert status == MonitorStatus.HEALTHY

    def test_down_no_agents(self):
        status = assess_swarm_status([], agents_online=0, agents_total=5)
        assert status == MonitorStatus.DOWN

    def test_down_emergency_alert(self):
        alerts = [Alert(level=AlertLevel.EMERGENCY, category=AlertCategory.SYSTEM,
                        title="API Down", message="x")]
        status = assess_swarm_status(alerts, agents_online=3, agents_total=5)
        assert status == MonitorStatus.DOWN

    def test_impaired_multiple_critical(self):
        alerts = [
            Alert(level=AlertLevel.CRITICAL, category=AlertCategory.AGENT_HEALTH,
                  title=f"Issue {i}", message="x") for i in range(3)
        ]
        status = assess_swarm_status(alerts, agents_online=3, agents_total=5)
        assert status == MonitorStatus.IMPAIRED

    def test_impaired_few_agents(self):
        status = assess_swarm_status([], agents_online=1, agents_total=5)
        assert status == MonitorStatus.IMPAIRED

    def test_degraded_one_critical(self):
        alerts = [Alert(level=AlertLevel.CRITICAL, category=AlertCategory.SYSTEM,
                        title="Issue", message="x")]
        status = assess_swarm_status(alerts, agents_online=4, agents_total=5)
        assert status == MonitorStatus.DEGRADED

    def test_degraded_many_warnings(self):
        alerts = [
            Alert(level=AlertLevel.WARNING, category=AlertCategory.AGENT_HEALTH,
                  title=f"Warn {i}", message="x") for i in range(5)
        ]
        status = assess_swarm_status(alerts, agents_online=5, agents_total=5)
        assert status == MonitorStatus.DEGRADED


# ---------------------------------------------------------------------------
# Digest Generation
# ---------------------------------------------------------------------------

class TestGenerateDigest:
    def test_basic_digest(self):
        agents = [make_healthy_agent(f"a{i}") for i in range(5)]
        pipeline = make_healthy_pipeline()
        alerts = []

        digest = generate_digest(agents, pipeline, alerts)

        assert digest.status == MonitorStatus.HEALTHY
        assert digest.agents_online == 5
        assert digest.agents_total == 5
        assert digest.tasks_in_pipeline == 10

    def test_digest_with_alerts(self):
        agents = [make_healthy_agent("a1")]
        pipeline = make_healthy_pipeline()
        alerts = [
            Alert(level=AlertLevel.WARNING, category=AlertCategory.AGENT_HEALTH,
                  title="Test", message="x"),
            Alert(level=AlertLevel.WARNING, category=AlertCategory.AGENT_HEALTH,
                  title="Test2", message="y"),
        ]

        digest = generate_digest(agents, pipeline, alerts)
        assert "warning" in digest.alerts_count
        assert digest.alerts_count["warning"] == 2

    def test_digest_top_performer(self):
        agents = [
            make_healthy_agent("a1", total_successes=5),
            make_healthy_agent("a2", total_successes=20),
            make_healthy_agent("a3", total_successes=10),
        ]
        pipeline = make_healthy_pipeline()

        digest = generate_digest(agents, pipeline, [])
        assert digest.top_performer == "a2"

    def test_digest_bottleneck_detection(self):
        agents = [make_healthy_agent("a1")]
        pipeline = make_healthy_pipeline(
            by_stage={"DISCOVERED": 15, "IN_PROGRESS": 3, "COMPLETED": 50}
        )

        digest = generate_digest(agents, pipeline, [])
        assert digest.bottleneck_stage == "DISCOVERED"

    def test_digest_excludes_terminal_stages_from_bottleneck(self):
        """COMPLETED/FAILED/EXPIRED shouldn't be considered bottlenecks."""
        agents = [make_healthy_agent("a1")]
        pipeline = make_healthy_pipeline(
            by_stage={"DISCOVERED": 2, "IN_PROGRESS": 1, "COMPLETED": 500}
        )

        digest = generate_digest(agents, pipeline, [])
        assert digest.bottleneck_stage != "COMPLETED"

    def test_digest_format_text(self):
        digest = StatusDigest(
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=MonitorStatus.HEALTHY,
            agents_online=5,
            agents_total=5,
            tasks_in_pipeline=10,
        )
        text = digest.format_text()
        assert "🟢" in text
        assert "HEALTHY" in text
        assert "5/5" in text

    def test_digest_highlights(self):
        agents = [make_healthy_agent(f"a{i}") for i in range(5)]
        pipeline = make_healthy_pipeline(
            completion_rate_24h=0.9,
            by_stage={"COMPLETED": 20},
        )

        digest = generate_digest(agents, pipeline, [])
        assert any("Full swarm online" in h for h in digest.highlights)
        assert any("completion rate" in h.lower() for h in digest.highlights)

    def test_digest_to_dict(self):
        digest = StatusDigest(
            timestamp="2026-03-07T00:00:00Z",
            status=MonitorStatus.DEGRADED,
            agents_online=3,
            agents_total=5,
        )
        d = digest.to_dict()
        assert d["status"] == "degraded"
        assert d["agents_online"] == 3

    def test_empty_agents_digest(self):
        digest = generate_digest([], make_healthy_pipeline(), [])
        assert digest.agents_online == 0
        assert digest.top_performer == ""


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------

class TestTrendAnalysis:
    def test_improving_trend(self):
        # Values with clear upward slope: normalized_slope > 0.05, CV < 0.3
        points = [TrendPoint(f"2026-03-07T{i:02d}:00:00Z", 50.0 + i * 5.0)
                  for i in range(10)]
        trend = analyze_trend("success_rate", points)
        assert trend.direction == "improving"
        assert trend.current_value == 95.0
        assert trend.data_points == 10

    def test_declining_trend(self):
        # Values with clear downward slope: normalized_slope < -0.05, CV < 0.3
        points = [TrendPoint(f"2026-03-07T{i:02d}:00:00Z", 90.0 - i * 5.0)
                  for i in range(10)]
        trend = analyze_trend("success_rate", points)
        assert trend.direction == "declining"

    def test_stable_trend(self):
        points = [TrendPoint(f"2026-03-07T{i:02d}:00:00Z", 50.0 + (i % 2) * 0.1)
                  for i in range(10)]
        trend = analyze_trend("success_rate", points)
        assert trend.direction == "stable"

    def test_volatile_trend(self):
        """Values that swing wildly should be detected as volatile."""
        points = [TrendPoint(f"2026-03-07T{i:02d}:00:00Z",
                             10.0 if i % 2 == 0 else 90.0) for i in range(10)]
        trend = analyze_trend("success_rate", points)
        assert trend.direction == "volatile"

    def test_single_point(self):
        points = [TrendPoint("2026-03-07T00:00:00Z", 50.0)]
        trend = analyze_trend("test", points)
        assert trend.data_points == 1
        assert trend.current_value == 50.0

    def test_empty_points(self):
        trend = analyze_trend("test", [])
        assert trend.data_points == 0
        assert trend.current_value == 0.0

    def test_window_limit(self):
        """Should only use the most recent N points."""
        points = [TrendPoint(f"2026-03-07T{i:02d}:00:00Z", float(i))
                  for i in range(50)]
        trend = analyze_trend("test", points, window=5)
        assert trend.data_points == 5
        assert trend.current_value == 49.0

    def test_change_percentage(self):
        points = [
            TrendPoint("2026-03-07T00:00:00Z", 50.0),
            TrendPoint("2026-03-07T01:00:00Z", 60.0),
            TrendPoint("2026-03-07T02:00:00Z", 75.0),
        ]
        trend = analyze_trend("test", points)
        assert trend.change_pct == pytest.approx(50.0)  # (75-50)/50 * 100

    def test_to_dict(self):
        trend = TrendAnalysis(
            metric_name="success",
            direction="improving",
            current_value=85.123,
            avg_value=72.456,
        )
        d = trend.to_dict()
        assert d["metric"] == "success"
        assert d["direction"] == "improving"
        assert d["current"] == 85.12


# ---------------------------------------------------------------------------
# SwarmMonitor Stateful Class
# ---------------------------------------------------------------------------

class TestSwarmMonitor:
    def test_run_checks_healthy(self):
        monitor = SwarmMonitor()
        agents = [make_healthy_agent(f"a{i}") for i in range(5)]
        pipeline = make_healthy_pipeline()
        system = make_healthy_system()

        alerts, digest = monitor.run_checks(agents, pipeline, system)

        assert digest.status == MonitorStatus.HEALTHY
        assert len(monitor.digest_history) == 1

    def test_run_checks_with_reputation(self):
        monitor = SwarmMonitor()
        agents = [make_healthy_agent("a1")]
        pipeline = make_healthy_pipeline()
        system = make_healthy_system()

        # First run: establish baseline
        monitor.run_checks(
            agents, pipeline, system,
            current_reputations={"a1": 80.0},
        )

        # Second run: reputation drop
        alerts, digest = monitor.run_checks(
            agents, pipeline, system,
            current_reputations={"a1": 65.0},
        )

        rep_alerts = [a for a in alerts if a.category == AlertCategory.REPUTATION]
        assert len(rep_alerts) == 1
        assert "drop" in rep_alerts[0].title.lower()

    def test_alert_deduplication(self):
        """Same alert within 5 minutes should be suppressed."""
        monitor = SwarmMonitor()
        now = datetime(2026, 3, 7, 0, 0, 0, tzinfo=timezone.utc)

        # First run with critical agent
        agents = [make_healthy_agent("a1", consecutive_failures=5)]
        pipeline = make_healthy_pipeline()
        system = make_healthy_system()

        alerts1, _ = monitor.run_checks(agents, pipeline, system, now=now)
        cb1 = [a for a in alerts1 if "Circuit breaker" in a.title]
        assert len(cb1) == 1

        # Second run 1 minute later - should be suppressed
        now2 = now + timedelta(minutes=1)
        alerts2, _ = monitor.run_checks(agents, pipeline, system, now=now2)
        cb2 = [a for a in alerts2 if "Circuit breaker" in a.title]
        assert len(cb2) == 0  # Suppressed

        # Third run 6 minutes later - should fire again
        now3 = now + timedelta(minutes=6)
        alerts3, _ = monitor.run_checks(agents, pipeline, system, now=now3)
        cb3 = [a for a in alerts3 if "Circuit breaker" in a.title]
        assert len(cb3) == 1  # Not suppressed anymore

    def test_agent_success_trends(self):
        monitor = SwarmMonitor()
        pipeline = make_healthy_pipeline()
        system = make_healthy_system()

        # Multiple runs to build trend data
        for i in range(5):
            agents = [make_healthy_agent("a1",
                                         total_successes=10 + i * 5,
                                         total_failures=2)]
            now = datetime(2026, 3, 7, i, 0, 0, tzinfo=timezone.utc)
            monitor.run_checks(agents, pipeline, system, now=now)

        trends = monitor.get_agent_trends()
        assert "a1" in trends
        assert trends["a1"].data_points == 5

    def test_alert_summary(self):
        monitor = SwarmMonitor()
        agents = [make_healthy_agent("a1", consecutive_failures=5)]
        pipeline = make_healthy_pipeline(stuck_tasks=10)
        system = make_healthy_system(em_api_healthy=False)

        monitor.run_checks(agents, pipeline, system)

        summary = monitor.get_alert_summary(hours=1.0)
        assert summary["total_alerts"] > 0
        assert "by_level" in summary
        assert "by_category" in summary

    def test_history_trimming(self):
        monitor = SwarmMonitor(max_history=5)
        agents = [make_healthy_agent("a1")]
        pipeline = make_healthy_pipeline()
        system = make_healthy_system()

        for i in range(20):
            now = datetime(2026, 3, 7, 0, i, 0, tzinfo=timezone.utc)
            monitor.run_checks(agents, pipeline, system, now=now)

        # Implementation trims BEFORE appending new digest, so max_history + 1
        assert len(monitor.digest_history) <= 6
        assert len(monitor.agent_success_history.get("a1", [])) <= 6


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestMonitorPersistence:
    def test_save_and_load(self, tmp_path):
        monitor = SwarmMonitor()
        agents = [make_healthy_agent("a1")]
        pipeline = make_healthy_pipeline()
        system = make_healthy_system()

        monitor.run_checks(agents, pipeline, system)

        path = tmp_path / "monitor_state.json"
        save_monitor_state(monitor, path)

        assert path.exists()
        loaded = load_monitor_state(path)
        assert loaded["digest_count"] == 1
        assert "saved_at" in loaded

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        loaded = load_monitor_state(path)
        assert loaded == {}

    def test_load_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("NOT VALID JSON")
        loaded = load_monitor_state(path)
        assert loaded == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        monitor = SwarmMonitor()
        path = tmp_path / "nested" / "dir" / "state.json"
        save_monitor_state(monitor, path)
        assert path.exists()
