"""
Tests for Karma Kadabra V2 — Agent Observability & Metrics

Covers:
  - Agent health assessment (heartbeat, tasks, errors, balance, connectivity)
  - Swarm metrics aggregation
  - Task funnel analysis
  - Report generation and persistence
  - Trend analysis across reports
  - Acontext integration formatting
"""

import json
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lib.observability import (
    AgentHealthSnapshot,
    HealthStatus,
    SwarmMetrics,
    TaskFunnel,
    TaskFunnelStep,
    TaskPhase,
    assess_agent_health,
    build_task_funnel,
    compute_health_trend,
    compute_swarm_metrics,
    format_agent_event,
    format_for_acontext_session,
    generate_health_report,
    load_health_reports,
    save_health_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def now():
    return datetime(2026, 2, 22, 3, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fresh_heartbeat(now):
    """A heartbeat from 30 seconds ago."""
    return (now - timedelta(seconds=30)).isoformat()


@pytest.fixture
def stale_heartbeat(now):
    """A heartbeat from 15 minutes ago."""
    return (now - timedelta(minutes=15)).isoformat()


@pytest.fixture
def old_heartbeat(now):
    """A heartbeat from 2 hours ago."""
    return (now - timedelta(hours=2)).isoformat()


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ---------------------------------------------------------------------------
# AgentHealthSnapshot Tests
# ---------------------------------------------------------------------------


class TestAgentHealthSnapshot:
    def test_default_values(self):
        snap = AgentHealthSnapshot(agent_name="test")
        assert snap.agent_name == "test"
        assert snap.status == HealthStatus.UNKNOWN
        assert snap.health_score == 0.0
        assert not snap.is_healthy
        assert snap.balance_ok is True

    def test_is_healthy(self):
        snap = AgentHealthSnapshot(agent_name="test", status=HealthStatus.HEALTHY)
        assert snap.is_healthy

    def test_is_not_healthy(self):
        for status in [HealthStatus.DEGRADED, HealthStatus.STALE, HealthStatus.OFFLINE, HealthStatus.UNKNOWN]:
            snap = AgentHealthSnapshot(agent_name="test", status=status)
            assert not snap.is_healthy

    def test_to_dict(self):
        snap = AgentHealthSnapshot(
            agent_name="alice",
            status=HealthStatus.HEALTHY,
            health_score=0.85,
            tasks_completed_24h=5,
        )
        d = snap.to_dict()
        assert d["agent_name"] == "alice"
        assert d["status"] == "healthy"
        assert d["health_score"] == 0.85
        assert d["tasks_completed_24h"] == 5

    def test_to_dict_has_all_fields(self):
        snap = AgentHealthSnapshot(agent_name="test")
        d = snap.to_dict()
        expected_keys = {
            "agent_name", "status", "health_score", "last_heartbeat",
            "heartbeat_age_seconds", "active_task", "tasks_completed_24h",
            "tasks_failed_24h", "errors_24h", "balance_ok", "irc_connected",
            "details",
        }
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Health Assessment Tests
# ---------------------------------------------------------------------------


class TestAssessAgentHealth:
    """Tests for assess_agent_health — the core health scoring function."""

    def test_fresh_heartbeat_healthy(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            agent_name="alice",
            last_heartbeat=fresh_heartbeat,
            irc_connected=True,
            now=now,
        )
        assert snap.status == HealthStatus.HEALTHY
        assert snap.health_score > 0.6
        assert snap.heartbeat_age_seconds == 30

    def test_stale_heartbeat(self, now, stale_heartbeat):
        snap = assess_agent_health(
            agent_name="bob",
            last_heartbeat=stale_heartbeat,
            now=now,
        )
        assert snap.status == HealthStatus.STALE
        assert snap.heartbeat_age_seconds == 900

    def test_old_heartbeat_offline(self, now, old_heartbeat):
        snap = assess_agent_health(
            agent_name="carol",
            last_heartbeat=old_heartbeat,
            now=now,
        )
        assert snap.status == HealthStatus.OFFLINE
        assert snap.heartbeat_age_seconds == 7200

    def test_no_heartbeat_unknown(self, now):
        snap = assess_agent_health(
            agent_name="dave",
            last_heartbeat=None,
            now=now,
        )
        assert snap.status == HealthStatus.UNKNOWN
        assert snap.heartbeat_age_seconds == -1

    def test_active_task_tracked(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            agent_name="eve",
            last_heartbeat=fresh_heartbeat,
            active_task_id="task-123",
            now=now,
        )
        assert snap.active_task is True

    def test_no_active_task(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            agent_name="frank",
            last_heartbeat=fresh_heartbeat,
            active_task_id=None,
            now=now,
        )
        assert snap.active_task is False

    def test_high_completion_boosts_score(self, now, fresh_heartbeat):
        high = assess_agent_health(
            agent_name="good",
            last_heartbeat=fresh_heartbeat,
            tasks_completed_24h=10,
            tasks_failed_24h=0,
            irc_connected=True,
            now=now,
        )
        low = assess_agent_health(
            agent_name="bad",
            last_heartbeat=fresh_heartbeat,
            tasks_completed_24h=1,
            tasks_failed_24h=9,
            irc_connected=True,
            now=now,
        )
        assert high.health_score > low.health_score

    def test_errors_reduce_score(self, now, fresh_heartbeat):
        clean = assess_agent_health(
            agent_name="clean",
            last_heartbeat=fresh_heartbeat,
            error_count_24h=0,
            now=now,
        )
        errored = assess_agent_health(
            agent_name="errored",
            last_heartbeat=fresh_heartbeat,
            error_count_24h=10,
            now=now,
        )
        assert clean.health_score > errored.health_score

    def test_low_balance_detected(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            agent_name="broke",
            last_heartbeat=fresh_heartbeat,
            balance_usdc=0.001,
            balance_eth=0.00001,
            min_usdc=0.01,
            min_eth=0.0001,
            now=now,
        )
        assert snap.balance_ok is False

    def test_sufficient_balance(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            agent_name="rich",
            last_heartbeat=fresh_heartbeat,
            balance_usdc=1.0,
            balance_eth=0.01,
            now=now,
        )
        assert snap.balance_ok is True

    def test_none_balance_is_ok(self, now, fresh_heartbeat):
        """Unknown balance treated as OK (can't penalize missing data)."""
        snap = assess_agent_health(
            agent_name="unknown",
            last_heartbeat=fresh_heartbeat,
            balance_usdc=None,
            balance_eth=None,
            now=now,
        )
        assert snap.balance_ok is True

    def test_irc_connected_boosts_score(self, now, fresh_heartbeat):
        connected = assess_agent_health(
            agent_name="connected",
            last_heartbeat=fresh_heartbeat,
            irc_connected=True,
            now=now,
        )
        disconnected = assess_agent_health(
            agent_name="disconnected",
            last_heartbeat=fresh_heartbeat,
            irc_connected=False,
            now=now,
        )
        assert connected.health_score > disconnected.health_score

    def test_health_score_bounded(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            agent_name="bounded",
            last_heartbeat=fresh_heartbeat,
            tasks_completed_24h=100,
            irc_connected=True,
            now=now,
        )
        assert 0.0 <= snap.health_score <= 1.0

    def test_degraded_status_on_low_score(self, now, stale_heartbeat):
        """Stale heartbeat + terrible metrics → degraded."""
        snap = assess_agent_health(
            agent_name="degraded",
            last_heartbeat=stale_heartbeat,
            tasks_completed_24h=0,
            tasks_failed_24h=20,
            error_count_24h=50,
            balance_usdc=0.0,
            irc_connected=False,
            now=now,
        )
        # Stale heartbeat puts status as STALE or DEGRADED depending on score
        assert snap.health_score < 0.4
        assert snap.status in (HealthStatus.DEGRADED, HealthStatus.STALE)

    def test_details_included(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            agent_name="detailed",
            last_heartbeat=fresh_heartbeat,
            now=now,
        )
        assert "heartbeat_score" in snap.details
        assert "task_score" in snap.details
        assert "error_score" in snap.details
        assert "balance_score" in snap.details
        assert "connectivity_score" in snap.details

    def test_custom_thresholds(self, now):
        """Custom stale/offline thresholds."""
        hb = (now - timedelta(seconds=120)).isoformat()

        # With default thresholds (600s stale, 3600s offline), 120s is healthy
        default = assess_agent_health("test", last_heartbeat=hb, now=now)
        assert default.status == HealthStatus.HEALTHY

        # With strict thresholds (60s stale, 180s offline), 120s is stale
        strict = assess_agent_health(
            "test",
            last_heartbeat=hb,
            stale_threshold_seconds=60,
            offline_threshold_seconds=180,
            now=now,
        )
        assert strict.status == HealthStatus.STALE

    def test_invalid_heartbeat_timestamp(self, now):
        snap = assess_agent_health(
            agent_name="bad_ts",
            last_heartbeat="not-a-timestamp",
            now=now,
        )
        assert snap.heartbeat_age_seconds == -1
        assert snap.status == HealthStatus.UNKNOWN

    def test_future_heartbeat_treated_as_fresh(self, now):
        """Heartbeat in the future (clock skew) shouldn't crash."""
        future_hb = (now + timedelta(seconds=30)).isoformat()
        snap = assess_agent_health("future", last_heartbeat=future_hb, now=now)
        assert snap.heartbeat_age_seconds == 0

    def test_idle_agent_neutral_task_score(self, now, fresh_heartbeat):
        """Agent with no tasks gets neutral 0.5 task score."""
        snap = assess_agent_health(
            "idle",
            last_heartbeat=fresh_heartbeat,
            tasks_completed_24h=0,
            tasks_failed_24h=0,
            now=now,
        )
        assert snap.details["task_score"] == 0.5


# ---------------------------------------------------------------------------
# Swarm Metrics Tests
# ---------------------------------------------------------------------------


class TestComputeSwarmMetrics:
    def test_empty_swarm(self, now):
        metrics = compute_swarm_metrics([], now=now)
        assert metrics.total_agents == 0
        assert metrics.healthy_agents == 0

    def test_agent_health_counts(self, now):
        snapshots = [
            AgentHealthSnapshot(agent_name="a", status=HealthStatus.HEALTHY),
            AgentHealthSnapshot(agent_name="b", status=HealthStatus.HEALTHY),
            AgentHealthSnapshot(agent_name="c", status=HealthStatus.DEGRADED),
            AgentHealthSnapshot(agent_name="d", status=HealthStatus.OFFLINE),
        ]
        metrics = compute_swarm_metrics(snapshots, now=now)
        assert metrics.total_agents == 4
        assert metrics.healthy_agents == 2
        assert metrics.degraded_agents == 1
        assert metrics.offline_agents == 1

    def test_task_counts_from_snapshots(self, now):
        snapshots = [
            AgentHealthSnapshot(agent_name="a", tasks_completed_24h=5, tasks_failed_24h=1),
            AgentHealthSnapshot(agent_name="b", tasks_completed_24h=3, tasks_failed_24h=0),
        ]
        metrics = compute_swarm_metrics(snapshots, now=now)
        assert metrics.tasks_completed == 8
        assert metrics.tasks_failed == 1

    def test_task_events_processing(self, now):
        snapshots = [AgentHealthSnapshot(agent_name="a")]
        events = [
            {"phase": "discovered", "agent": "a"},
            {"phase": "discovered", "agent": "a"},
            {"phase": "applied", "agent": "a", "task_id": "t1"},
            {"phase": "assigned", "agent": "a"},
            {"phase": "completed", "agent": "a", "bounty_usd": 0.10, "completion_hours": 0.5},
            {"phase": "expired", "agent": "a"},
        ]
        metrics = compute_swarm_metrics(snapshots, task_events=events, now=now)
        assert metrics.tasks_discovered == 2
        assert metrics.tasks_applied == 1
        assert metrics.tasks_assigned == 1
        assert metrics.tasks_expired == 1
        assert metrics.total_earned_usd == 0.10
        assert metrics.avg_bounty_usd == 0.10
        assert metrics.avg_completion_hours == 0.5

    def test_duplicate_applications_detected(self, now):
        snapshots = [AgentHealthSnapshot(agent_name="a")]
        events = [
            {"phase": "applied", "agent": "a", "task_id": "t1"},
            {"phase": "applied", "agent": "a", "task_id": "t1"},  # Duplicate!
        ]
        metrics = compute_swarm_metrics(snapshots, task_events=events, now=now)
        assert metrics.duplicate_applications == 1

    def test_completion_rate(self, now):
        snapshots = [
            AgentHealthSnapshot(agent_name="a", tasks_completed_24h=7, tasks_failed_24h=3),
        ]
        events = [{"phase": "expired"}]
        metrics = compute_swarm_metrics(snapshots, task_events=events, now=now)
        # completed=7, failed=3, expired=1 → 7/11
        assert abs(metrics.completion_rate - 7 / 11) < 0.01

    def test_apply_to_assign_rate(self, now):
        snapshots = [AgentHealthSnapshot(agent_name="a")]
        events = [
            {"phase": "applied", "agent": "a", "task_id": "t1"},
            {"phase": "applied", "agent": "a", "task_id": "t2"},
            {"phase": "applied", "agent": "a", "task_id": "t3"},
            {"phase": "assigned", "agent": "a"},
            {"phase": "assigned", "agent": "a"},
        ]
        metrics = compute_swarm_metrics(snapshots, task_events=events, now=now)
        assert abs(metrics.apply_to_assign_rate - 2 / 3) < 0.01

    def test_to_dict_structure(self, now):
        metrics = compute_swarm_metrics([], now=now)
        d = metrics.to_dict()
        assert "window" in d
        assert "agents" in d
        assert "tasks" in d
        assert "financial" in d
        assert "efficiency" in d
        assert "coordination" in d

    def test_throughput_per_hour(self, now):
        snapshots = [
            AgentHealthSnapshot(agent_name="a", tasks_completed_24h=48),
        ]
        metrics = compute_swarm_metrics(snapshots, window_hours=24.0, now=now)
        d = metrics.to_dict()
        assert d["tasks"]["throughput_per_hour"] == 2.0

    def test_invalid_phase_ignored(self, now):
        snapshots = [AgentHealthSnapshot(agent_name="a")]
        events = [{"phase": "invalid_phase"}]
        metrics = compute_swarm_metrics(snapshots, task_events=events, now=now)
        assert metrics.tasks_discovered == 0


# ---------------------------------------------------------------------------
# Task Funnel Tests
# ---------------------------------------------------------------------------


class TestBuildTaskFunnel:
    def test_perfect_funnel(self):
        funnel = build_task_funnel(
            discovered=100, applied=100, assigned=100,
            working=100, submitted=100, completed=100,
        )
        assert len(funnel.steps) == 6
        assert all(s.conversion_from_previous == 1.0 for s in funnel.steps)

    def test_leaky_funnel(self):
        funnel = build_task_funnel(
            discovered=100, applied=50, assigned=25,
            working=20, submitted=15, completed=10,
        )
        assert funnel.steps[1].conversion_from_previous == 0.5  # discovered → applied
        assert funnel.steps[2].conversion_from_previous == 0.5  # applied → assigned

    def test_bottleneck_detection(self):
        funnel = build_task_funnel(
            discovered=100, applied=90, assigned=10,  # 11% conversion = bottleneck
            working=10, submitted=10, completed=10,
        )
        assert funnel.bottleneck == "assigned"
        assert abs(funnel.bottleneck_rate - 10 / 90) < 0.02

    def test_empty_funnel(self):
        funnel = build_task_funnel()
        assert len(funnel.steps) == 6
        assert all(s.count == 0 for s in funnel.steps)

    def test_to_dict(self):
        funnel = build_task_funnel(discovered=10, applied=5, completed=3)
        d = funnel.to_dict()
        assert "steps" in d
        assert "bottleneck" in d
        assert len(d["steps"]) == 6

    def test_zero_previous_no_division_error(self):
        """Zero in previous step shouldn't cause division by zero."""
        funnel = build_task_funnel(
            discovered=0, applied=0, assigned=0,
            working=0, submitted=0, completed=0,
        )
        # Should not raise

    def test_increasing_counts_capped(self):
        """More assigned than applied → conversion capped at 1.0."""
        funnel = build_task_funnel(
            discovered=10, applied=5, assigned=8,
        )
        assert funnel.steps[2].conversion_from_previous == 1.0


# ---------------------------------------------------------------------------
# Report Generation Tests
# ---------------------------------------------------------------------------


class TestGenerateHealthReport:
    def test_basic_report(self, now, fresh_heartbeat):
        snap = assess_agent_health("alice", last_heartbeat=fresh_heartbeat, now=now)
        report = generate_health_report([snap])
        assert "agents" in report
        assert "alice" in report["agents"]
        assert "summary" in report
        assert report["summary"]["total_agents"] == 1

    def test_report_with_metrics(self, now, fresh_heartbeat):
        snap = assess_agent_health("alice", last_heartbeat=fresh_heartbeat, now=now)
        metrics = compute_swarm_metrics([snap], now=now)
        report = generate_health_report([snap], swarm_metrics=metrics)
        assert "swarm_metrics" in report

    def test_report_with_funnel(self, now, fresh_heartbeat):
        snap = assess_agent_health("alice", last_heartbeat=fresh_heartbeat, now=now)
        funnel = build_task_funnel(discovered=10, completed=8)
        report = generate_health_report([snap], funnel=funnel)
        assert "task_funnel" in report

    def test_summary_counts(self, now, fresh_heartbeat, stale_heartbeat):
        healthy = assess_agent_health("alice", last_heartbeat=fresh_heartbeat, irc_connected=True, now=now)
        stale = assess_agent_health("bob", last_heartbeat=stale_heartbeat, now=now)
        report = generate_health_report([healthy, stale])
        assert report["summary"]["total_agents"] == 2
        assert report["summary"]["healthy_agents"] == 1

    def test_empty_report(self):
        report = generate_health_report([])
        assert report["summary"]["total_agents"] == 0


# ---------------------------------------------------------------------------
# Report Persistence Tests
# ---------------------------------------------------------------------------


class TestReportPersistence:
    def test_save_and_load(self, tmp_dir):
        report = {"generated_at": "2026-02-22", "summary": {"total_agents": 5}}
        path = save_health_report(report, tmp_dir)
        assert path.exists()
        assert "health_report_" in path.name

        loaded = load_health_reports(tmp_dir, limit=1)
        assert len(loaded) == 1
        assert loaded[0]["summary"]["total_agents"] == 5

    def test_load_multiple_reports(self, tmp_dir):
        for i in range(5):
            # Write directly with unique names to avoid timing issues
            path = tmp_dir / f"health_report_20260222_0300{i:02d}_000000.json"
            path.write_text(json.dumps({"index": i, "summary": {}}))

        loaded = load_health_reports(tmp_dir, limit=3)
        assert len(loaded) == 3

    def test_load_from_empty_dir(self, tmp_dir):
        loaded = load_health_reports(tmp_dir)
        assert loaded == []

    def test_load_from_nonexistent_dir(self):
        loaded = load_health_reports(Path("/nonexistent"))
        assert loaded == []


# ---------------------------------------------------------------------------
# Trend Analysis Tests
# ---------------------------------------------------------------------------


class TestComputeHealthTrend:
    def test_insufficient_data(self):
        trend = compute_health_trend([])
        assert trend["trend"] == "insufficient_data"

        trend = compute_health_trend([{"summary": {}}])
        assert trend["trend"] == "insufficient_data"

    def test_improving_trend(self):
        reports = [
            # Recent (better)
            {"summary": {"avg_health_score": 0.9, "health_ratio": 1.0}, "swarm_metrics": {"efficiency": {"completion_rate": 0.9}}},
            {"summary": {"avg_health_score": 0.85, "health_ratio": 0.9}, "swarm_metrics": {"efficiency": {"completion_rate": 0.8}}},
            # Older (worse)
            {"summary": {"avg_health_score": 0.5, "health_ratio": 0.6}, "swarm_metrics": {"efficiency": {"completion_rate": 0.5}}},
            {"summary": {"avg_health_score": 0.4, "health_ratio": 0.5}, "swarm_metrics": {"efficiency": {"completion_rate": 0.4}}},
        ]
        trend = compute_health_trend(reports)
        assert trend["trend"] == "improving"
        assert trend["score_delta"] > 0

    def test_degrading_trend(self):
        reports = [
            # Recent (worse)
            {"summary": {"avg_health_score": 0.3, "health_ratio": 0.3}, "swarm_metrics": {"efficiency": {"completion_rate": 0.3}}},
            {"summary": {"avg_health_score": 0.35, "health_ratio": 0.4}, "swarm_metrics": {"efficiency": {"completion_rate": 0.3}}},
            # Older (better)
            {"summary": {"avg_health_score": 0.9, "health_ratio": 1.0}, "swarm_metrics": {"efficiency": {"completion_rate": 0.9}}},
            {"summary": {"avg_health_score": 0.85, "health_ratio": 0.9}, "swarm_metrics": {"efficiency": {"completion_rate": 0.8}}},
        ]
        trend = compute_health_trend(reports)
        assert trend["trend"] == "degrading"
        assert trend["score_delta"] < 0

    def test_stable_trend(self):
        reports = [
            {"summary": {"avg_health_score": 0.8, "health_ratio": 0.9}, "swarm_metrics": {"efficiency": {"completion_rate": 0.8}}},
            {"summary": {"avg_health_score": 0.81, "health_ratio": 0.9}, "swarm_metrics": {"efficiency": {"completion_rate": 0.8}}},
            {"summary": {"avg_health_score": 0.79, "health_ratio": 0.9}, "swarm_metrics": {"efficiency": {"completion_rate": 0.8}}},
            {"summary": {"avg_health_score": 0.80, "health_ratio": 0.9}, "swarm_metrics": {"efficiency": {"completion_rate": 0.8}}},
        ]
        trend = compute_health_trend(reports)
        assert trend["trend"] == "stable"

    def test_trend_report_count(self):
        reports = [
            {"summary": {"avg_health_score": 0.8}, "swarm_metrics": {"efficiency": {}}},
            {"summary": {"avg_health_score": 0.7}, "swarm_metrics": {"efficiency": {}}},
            {"summary": {"avg_health_score": 0.6}, "swarm_metrics": {"efficiency": {}}},
        ]
        trend = compute_health_trend(reports)
        assert trend["reports_analyzed"] == 3


# ---------------------------------------------------------------------------
# Acontext Integration Format Tests
# ---------------------------------------------------------------------------


class TestAcontextFormatting:
    def test_format_for_session(self):
        report = {
            "generated_at": "2026-02-22T03:00:00",
            "summary": {"total_agents": 24, "health_ratio": 0.92},
        }
        formatted = format_for_acontext_session(report)
        assert formatted["role"] == "system"
        assert formatted["metadata"]["type"] == "health_report"
        assert formatted["metadata"]["agent_count"] == 24
        assert formatted["metadata"]["health_ratio"] == 0.92

    def test_format_agent_event(self, now):
        event = format_agent_event(
            agent_name="alice",
            event_type="task_complete",
            details={"task_id": "t1", "bounty": 0.10},
            now=now,
        )
        assert event["agent"] == "alice"
        assert event["event"] == "task_complete"
        assert event["details"]["task_id"] == "t1"
        assert event["timestamp"] == now.isoformat()

    def test_format_event_default_time(self):
        event = format_agent_event("bob", "heartbeat")
        assert "timestamp" in event
        assert event["details"] == {}

    def test_format_event_no_details(self, now):
        event = format_agent_event("carol", "irc_connect", now=now)
        assert event["details"] == {}


# ---------------------------------------------------------------------------
# SwarmMetrics Tests
# ---------------------------------------------------------------------------


class TestSwarmMetrics:
    def test_to_dict_structure(self):
        m = SwarmMetrics(total_agents=10, healthy_agents=8)
        d = m.to_dict()
        assert d["agents"]["total"] == 10
        assert d["agents"]["healthy"] == 8
        assert d["agents"]["health_ratio"] == 0.8

    def test_health_ratio_zero_agents(self):
        m = SwarmMetrics(total_agents=0)
        d = m.to_dict()
        assert d["agents"]["health_ratio"] == 0.0

    def test_net_financial(self):
        m = SwarmMetrics(total_earned_usd=1.50, total_spent_usd=0.30)
        d = m.to_dict()
        assert d["financial"]["net_usd"] == 1.20


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_all_agents_offline(self, now):
        snapshots = [
            AgentHealthSnapshot(agent_name=f"agent-{i}", status=HealthStatus.OFFLINE)
            for i in range(5)
        ]
        metrics = compute_swarm_metrics(snapshots, now=now)
        assert metrics.healthy_agents == 0
        assert metrics.offline_agents == 5
        d = metrics.to_dict()
        assert d["agents"]["health_ratio"] == 0.0

    def test_single_agent_swarm(self, now, fresh_heartbeat):
        snap = assess_agent_health(
            "solo", last_heartbeat=fresh_heartbeat,
            tasks_completed_24h=1, irc_connected=True, now=now,
        )
        metrics = compute_swarm_metrics([snap], now=now)
        assert metrics.total_agents == 1
        report = generate_health_report([snap], swarm_metrics=metrics)
        assert report["summary"]["total_agents"] == 1

    def test_large_swarm(self, now, fresh_heartbeat):
        snapshots = [
            assess_agent_health(
                f"agent-{i}",
                last_heartbeat=fresh_heartbeat,
                tasks_completed_24h=i,
                irc_connected=True,
                now=now,
            )
            for i in range(100)
        ]
        metrics = compute_swarm_metrics(snapshots, now=now)
        assert metrics.total_agents == 100
        assert metrics.healthy_agents == 100
