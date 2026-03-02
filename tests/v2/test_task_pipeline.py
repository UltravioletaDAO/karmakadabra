"""
Tests for TaskPipeline — End-to-end task lifecycle management.

Tests organized by feature:
  1. Pipeline Creation & Discovery
  2. Stage Transitions (happy path)
  3. Invalid Transitions
  4. SLA Monitoring
  5. Offer/Reject Cycle
  6. Full Happy Path (discover → complete)
  7. Failure & Recovery
  8. Dispute Resolution
  9. Funnel Analysis
  10. Pipeline Analytics
  11. Persistence (save/load round-trip)
  12. Batch Operations
  13. Edge Cases
  14. Transition Hooks
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.task_pipeline import (
    AgentRanking,
    DEFAULT_SLAS,
    PipelineEvent,
    PipelineStage,
    PipelineState,
    PipelineTask,
    SLAViolation,
    TaskEvidence,
    TaskPipeline,
    TransitionError,
    VALID_TRANSITIONS,
    check_sla_violations,
    compute_pipeline_metrics,
    execute_transition,
    format_pipeline_notification,
    load_pipeline_state,
    save_pipeline_state,
    validate_transition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rankings(n: int = 3) -> list[AgentRanking]:
    """Create sample agent rankings."""
    return [
        AgentRanking(agent_name=f"kk-agent-{i}", score=0.9 - i * 0.15)
        for i in range(n)
    ]


def make_evidence(n: int = 1) -> list[TaskEvidence]:
    """Create sample evidence."""
    return [
        TaskEvidence(
            evidence_type="photo_geo",
            content_url=f"https://example.com/evidence_{i}.jpg",
            metadata={"lat": 40.7, "lon": -74.0},
        )
        for i in range(n)
    ]


def advance_to_in_progress(pipeline: TaskPipeline, task_id: str = "task-001") -> PipelineTask:
    """Helper to advance a task to IN_PROGRESS quickly."""
    pipeline.discover(task_id, title="Test Task", bounty_usd=5.0, category="photo")
    pipeline.evaluate(task_id, make_rankings())
    pipeline.offer(task_id)
    pipeline.accept(task_id)
    pipeline.start_work(task_id)
    return pipeline.get_task(task_id)


def full_happy_path(pipeline: TaskPipeline, task_id: str = "task-001") -> PipelineTask:
    """Run a task through the entire happy path."""
    pipeline.discover(task_id, title="Test Task", bounty_usd=5.0, category="photo")
    pipeline.evaluate(task_id, make_rankings())
    pipeline.offer(task_id)
    pipeline.accept(task_id)
    pipeline.start_work(task_id)
    pipeline.submit(task_id, make_evidence(2))
    pipeline.review(task_id)
    pipeline.approve(task_id)
    pipeline.pay(task_id, tx_hash="0xabc123")
    pipeline.rate(task_id, agent_rating=90.0, creator_rating=85.0)
    pipeline.complete(task_id)
    return pipeline.get_task(task_id)


# ---------------------------------------------------------------------------
# 1. Pipeline Creation & Discovery
# ---------------------------------------------------------------------------

class TestPipelineCreation:
    def test_create_empty_pipeline(self):
        p = TaskPipeline()
        assert len(p.state.tasks) == 0
        assert p.state.total_discovered == 0

    def test_discover_task(self):
        p = TaskPipeline()
        task = p.discover("t1", title="Walk dog", bounty_usd=5.0, category="simple_action")
        assert task.task_id == "t1"
        assert task.stage == PipelineStage.DISCOVERED
        assert task.title == "Walk dog"
        assert task.bounty_usd == 5.0
        assert p.state.total_discovered == 1

    def test_discover_duplicate_returns_existing(self):
        p = TaskPipeline()
        t1 = p.discover("t1", title="First")
        t2 = p.discover("t1", title="Second")
        assert t1 is t2
        assert t1.title == "First"
        assert p.state.total_discovered == 1

    def test_discover_creates_initial_event(self):
        p = TaskPipeline()
        task = p.discover("t1", title="Test")
        assert len(task.events) == 1
        assert task.events[0].to_stage == "discovered"
        assert task.events[0].from_stage is None

    def test_discover_sets_timestamps(self):
        p = TaskPipeline()
        task = p.discover("t1")
        assert task.created_at != ""
        assert task.updated_at != ""
        assert task.stage_entered_at != ""

    def test_multiple_discoveries(self):
        p = TaskPipeline()
        for i in range(10):
            p.discover(f"t{i}", title=f"Task {i}", bounty_usd=i * 1.0)
        assert len(p.state.tasks) == 10
        assert p.state.total_discovered == 10


# ---------------------------------------------------------------------------
# 2. Stage Transitions (Happy Path)
# ---------------------------------------------------------------------------

class TestStageTransitions:
    def test_discovered_to_evaluated(self):
        p = TaskPipeline()
        p.discover("t1")
        task = p.evaluate("t1", make_rankings())
        assert task.stage == PipelineStage.EVALUATED
        assert len(task.rankings) == 3

    def test_evaluated_to_offered(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings())
        task = p.offer("t1")
        assert task.stage == PipelineStage.OFFERED
        assert task.assigned_agent == "kk-agent-0"

    def test_offered_to_accepted(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings())
        p.offer("t1")
        task = p.accept("t1")
        assert task.stage == PipelineStage.ACCEPTED

    def test_accepted_to_in_progress(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings())
        p.offer("t1")
        p.accept("t1")
        task = p.start_work("t1")
        assert task.stage == PipelineStage.IN_PROGRESS
        assert task.started_at is not None

    def test_in_progress_to_submitted(self):
        task = advance_to_in_progress(TaskPipeline())
        p = TaskPipeline(state=PipelineState(tasks={task.task_id: task}))
        p.submit(task.task_id, make_evidence(2))
        assert task.stage == PipelineStage.SUBMITTED
        assert len(task.evidence) == 2

    def test_submitted_to_under_review(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence())
        task = p.review("task-001")
        assert task.stage == PipelineStage.UNDER_REVIEW

    def test_under_review_to_approved(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence())
        p.review("task-001")
        task = p.approve("task-001")
        assert task.stage == PipelineStage.APPROVED
        assert task.approved_at is not None

    def test_approved_to_paid(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence())
        p.review("task-001")
        p.approve("task-001")
        task = p.pay("task-001", tx_hash="0xdeadbeef")
        assert task.stage == PipelineStage.PAID
        assert task.payment_tx == "0xdeadbeef"
        assert p.state.total_paid_usd == 5.0

    def test_paid_to_rated(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence())
        p.review("task-001")
        p.approve("task-001")
        p.pay("task-001", "0xabc")
        task = p.rate("task-001", agent_rating=95.0)
        assert task.stage == PipelineStage.RATED
        assert task.agent_rating == 95.0

    def test_rated_to_completed(self):
        p = TaskPipeline()
        task = full_happy_path(p)
        assert task.stage == PipelineStage.COMPLETED
        assert p.state.total_completed == 1

    def test_event_trail_records_all_transitions(self):
        p = TaskPipeline()
        task = full_happy_path(p)
        # 1 initial + 10 transitions (discovered→evaluated→offered→accepted→
        #   in_progress→submitted→under_review→approved→paid→rated→completed)
        assert len(task.events) == 11
        stages = [e.to_stage for e in task.events]
        assert stages[0] == "discovered"
        assert stages[-1] == "completed"


# ---------------------------------------------------------------------------
# 3. Invalid Transitions
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    def test_skip_stages_raises(self):
        p = TaskPipeline()
        p.discover("t1")
        with pytest.raises(TransitionError):
            # Can't go discovered → offered without evaluate first.
            # This raises either "Invalid transition" or "No eligible agents"
            # depending on whether rankings are empty.
            p.offer("t1")

    def test_backward_transition_raises(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings())
        with pytest.raises(TransitionError):
            execute_transition(
                p.get_task("t1"), PipelineStage.DISCOVERED, actor="test"
            )

    def test_completed_is_terminal(self):
        p = TaskPipeline()
        task = full_happy_path(p)
        with pytest.raises(TransitionError):
            execute_transition(task, PipelineStage.DISCOVERED)

    def test_nonexistent_task_raises(self):
        p = TaskPipeline()
        with pytest.raises(KeyError, match="not found"):
            p.evaluate("nonexistent", make_rankings())

    def test_validate_transition_returns_bool(self):
        task = PipelineTask(task_id="t1", stage=PipelineStage.DISCOVERED)
        assert validate_transition(task, PipelineStage.EVALUATED) is True
        assert validate_transition(task, PipelineStage.COMPLETED) is False

    def test_all_valid_transitions_consistent(self):
        """Every stage in the enum should appear in VALID_TRANSITIONS."""
        for stage in PipelineStage:
            assert stage in VALID_TRANSITIONS, f"Missing transitions for {stage}"


# ---------------------------------------------------------------------------
# 4. SLA Monitoring
# ---------------------------------------------------------------------------

class TestSLAMonitoring:
    def test_no_violations_for_fresh_tasks(self):
        p = TaskPipeline()
        p.discover("t1")
        violations = p.check_slas()
        assert len(violations) == 0

    def test_warning_at_50_pct_sla(self):
        p = TaskPipeline()
        p.discover("t1")
        task = p.get_task("t1")
        # Set stage_entered_at to 10 minutes ago (SLA for discovered = 15min)
        past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        task.stage_entered_at = past

        violations = p.check_slas()
        assert len(violations) == 1
        assert violations[0].severity == "warning"

    def test_breach_at_100_pct_sla(self):
        p = TaskPipeline()
        p.discover("t1")
        task = p.get_task("t1")
        past = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        task.stage_entered_at = past

        violations = p.check_slas()
        assert len(violations) == 1
        assert violations[0].severity == "breach"

    def test_critical_at_200_pct_sla(self):
        p = TaskPipeline()
        p.discover("t1")
        task = p.get_task("t1")
        past = (datetime.now(timezone.utc) - timedelta(minutes=35)).isoformat()
        task.stage_entered_at = past

        violations = p.check_slas()
        assert len(violations) == 1
        assert violations[0].severity == "critical"

    def test_multiple_violations_sorted_by_severity(self):
        p = TaskPipeline()
        now = datetime.now(timezone.utc)

        p.discover("t1")
        p.get_task("t1").stage_entered_at = (now - timedelta(minutes=35)).isoformat()

        p.discover("t2")
        p.get_task("t2").stage_entered_at = (now - timedelta(minutes=10)).isoformat()

        violations = p.check_slas()
        assert len(violations) == 2
        assert violations[0].severity == "critical"
        assert violations[1].severity == "warning"


# ---------------------------------------------------------------------------
# 5. Offer/Reject Cycle
# ---------------------------------------------------------------------------

class TestOfferRejectCycle:
    def test_reject_returns_to_evaluated(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings(3))
        p.offer("t1")
        assert p.get_task("t1").assigned_agent == "kk-agent-0"

        task = p.reject_offer("t1")
        assert task.stage == PipelineStage.EVALUATED
        assert task.assigned_agent is None
        assert task.offer_attempts == 1

    def test_second_offer_goes_to_next_agent(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings(3))
        p.offer("t1")  # kk-agent-0
        p.reject_offer("t1")
        task = p.offer("t1")  # Should pick kk-agent-1
        assert task.assigned_agent == "kk-agent-1"

    def test_exhausted_offers_fail_task(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings(3))

        # 3 offers, 3 rejections (max_offer_attempts = 3)
        for _ in range(3):
            p.offer("t1")
            p.reject_offer("t1")

        # Task should be FAILED after exhausting all attempts
        task = p.get_task("t1")
        assert task.stage == PipelineStage.FAILED

    def test_explicit_agent_offer(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings())
        task = p.offer("t1", agent_name="kk-agent-2")
        assert task.assigned_agent == "kk-agent-2"


# ---------------------------------------------------------------------------
# 6. Full Happy Path
# ---------------------------------------------------------------------------

class TestFullHappyPath:
    def test_discover_to_complete(self):
        p = TaskPipeline()
        task = full_happy_path(p)
        assert task.stage == PipelineStage.COMPLETED
        assert task.payment_tx == "0xabc123"
        assert task.agent_rating == 90.0
        assert task.creator_rating == 85.0
        assert p.state.total_completed == 1
        assert p.state.total_paid_usd == 5.0

    def test_pipeline_summary_after_completion(self):
        p = TaskPipeline()
        full_happy_path(p)
        summary = p.pipeline_summary()
        assert summary["total_tasks"] == 1
        assert summary["total_completed"] == 1
        assert summary["completion_rate"] == 1.0

    def test_multiple_tasks_in_parallel(self):
        p = TaskPipeline()
        for i in range(5):
            full_happy_path(p, f"task-{i}")
        assert p.state.total_completed == 5
        assert p.state.total_paid_usd == 25.0


# ---------------------------------------------------------------------------
# 7. Failure & Recovery
# ---------------------------------------------------------------------------

class TestFailureRecovery:
    def test_fail_in_progress_task(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        task = p.fail("task-001", reason="Agent crashed")
        assert task.stage == PipelineStage.FAILED
        assert task.failure_reason == "Agent crashed"
        assert p.state.total_failed == 1

    def test_fail_discovered_task(self):
        p = TaskPipeline()
        p.discover("t1")
        task = p.fail("t1", reason="Task withdrawn")
        assert task.stage == PipelineStage.FAILED

    def test_expire_task(self):
        p = TaskPipeline()
        p.discover("t1")
        task = p.expire("t1")
        assert task.stage == PipelineStage.EXPIRED
        assert p.state.total_expired == 1

    def test_retry_failed_task(self):
        p = TaskPipeline()
        p.discover("t1", title="Retryable")
        p.fail("t1", reason="Temporary error")

        # Re-discover should retry
        task = p.discover("t1")
        assert task.stage == PipelineStage.DISCOVERED
        assert task.retry_count == 1

    def test_retry_expired_task(self):
        p = TaskPipeline()
        p.discover("t1")
        p.expire("t1")
        task = p.discover("t1")
        assert task.stage == PipelineStage.DISCOVERED
        assert task.retry_count == 1


# ---------------------------------------------------------------------------
# 8. Dispute Resolution
# ---------------------------------------------------------------------------

class TestDisputeResolution:
    def test_dispute_in_progress_task(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        task = p.dispute("task-001", reason="Work quality concern")
        assert task.stage == PipelineStage.DISPUTED
        assert task.dispute_reason == "Work quality concern"

    def test_dispute_can_resolve_to_approved(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence())
        p.review("task-001")
        # Dispute during review
        p.dispute("task-001", reason="Missing evidence")

        # Resolve dispute favorably
        task = p.approve("task-001")
        assert task.stage == PipelineStage.APPROVED

    def test_dispute_can_resolve_to_failed(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.dispute("task-001", reason="Fraud detected")
        task = p.fail("task-001", reason="Dispute upheld: fraud")
        assert task.stage == PipelineStage.FAILED


# ---------------------------------------------------------------------------
# 9. Funnel Analysis
# ---------------------------------------------------------------------------

class TestFunnelAnalysis:
    def test_empty_pipeline_funnel(self):
        p = TaskPipeline()
        funnel = p.funnel_analysis()
        assert funnel["terminal"]["completed"] == 0

    def test_full_path_funnel(self):
        p = TaskPipeline()
        full_happy_path(p)
        funnel = p.funnel_analysis()
        assert funnel["stage_counts"]["discovered"] == 1
        assert funnel["stage_counts"]["completed"] == 1
        assert funnel["terminal"]["completed"] == 1

    def test_partial_funnel_shows_dropoff(self):
        p = TaskPipeline()
        # 3 tasks discovered
        for i in range(3):
            p.discover(f"t{i}", title=f"Task {i}")

        # Only 2 evaluated
        p.evaluate("t0", make_rankings())
        p.evaluate("t1", make_rankings())

        # Only 1 offered
        p.offer("t0")

        funnel = p.funnel_analysis()
        assert funnel["stage_counts"]["discovered"] == 3
        assert funnel["stage_counts"]["evaluated"] == 2
        assert funnel["stage_counts"]["offered"] == 1

        # Check conversion rates
        disc_to_eval = next(
            c for c in funnel["conversions"]
            if c["from"] == "discovered" and c["to"] == "evaluated"
        )
        assert disc_to_eval["rate"] == pytest.approx(2 / 3, abs=0.01)


# ---------------------------------------------------------------------------
# 10. Pipeline Analytics
# ---------------------------------------------------------------------------

class TestPipelineAnalytics:
    def test_compute_metrics_empty(self):
        state = PipelineState()
        metrics = compute_pipeline_metrics(state)
        assert metrics.get("empty") is True

    def test_compute_metrics_with_data(self):
        p = TaskPipeline()
        for i in range(5):
            full_happy_path(p, f"task-{i}")
        p.discover("task-fail")
        p.fail("task-fail", reason="test")

        metrics = compute_pipeline_metrics(p.state)
        assert metrics["total_tasks"] == 6
        assert metrics["completed"] == 5
        assert metrics["failed"] == 1
        assert metrics["total_paid_usd"] == 25.0

    def test_agent_workload(self):
        p = TaskPipeline()
        advance_to_in_progress(p, "task-001")
        workload = p.agent_workload()
        assert "kk-agent-0" in workload
        assert workload["kk-agent-0"]["active"] == 1


# ---------------------------------------------------------------------------
# 11. Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_load_roundtrip(self):
        p = TaskPipeline()
        full_happy_path(p, "task-001")
        advance_to_in_progress(p, "task-002")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipeline.json"
            save_pipeline_state(p.state, path)

            loaded = load_pipeline_state(path)
            assert len(loaded.tasks) == 2
            assert loaded.total_completed == 1
            assert loaded.total_paid_usd == 5.0

            t1 = loaded.tasks["task-001"]
            assert t1.stage == PipelineStage.COMPLETED
            assert t1.payment_tx == "0xabc123"
            assert t1.agent_rating == 90.0

            t2 = loaded.tasks["task-002"]
            assert t2.stage == PipelineStage.IN_PROGRESS

    def test_load_nonexistent_returns_empty(self):
        state = load_pipeline_state(Path("/nonexistent/pipeline.json"))
        assert len(state.tasks) == 0

    def test_save_preserves_events(self):
        p = TaskPipeline()
        full_happy_path(p)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipeline.json"
            save_pipeline_state(p.state, path)
            loaded = load_pipeline_state(path)
            task = loaded.tasks["task-001"]
            assert len(task.events) == 11

    def test_save_preserves_rankings(self):
        p = TaskPipeline()
        p.discover("t1")
        p.evaluate("t1", make_rankings(3))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipeline.json"
            save_pipeline_state(p.state, path)
            loaded = load_pipeline_state(path)
            task = loaded.tasks["t1"]
            assert len(task.rankings) == 3
            assert task.rankings[0].agent_name == "kk-agent-0"

    def test_save_preserves_evidence(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence(3))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipeline.json"
            save_pipeline_state(p.state, path)
            loaded = load_pipeline_state(path)
            task = loaded.tasks["task-001"]
            assert len(task.evidence) == 3
            assert task.evidence[0].evidence_type == "photo_geo"


# ---------------------------------------------------------------------------
# 12. Batch Operations
# ---------------------------------------------------------------------------

class TestBatchOperations:
    def test_expire_stale_tasks(self):
        p = TaskPipeline()
        now = datetime.now(timezone.utc)

        # Create tasks with old stage_entered_at
        p.discover("old1")
        p.get_task("old1").stage_entered_at = (now - timedelta(hours=2)).isoformat()

        p.discover("old2")
        p.get_task("old2").stage_entered_at = (now - timedelta(hours=2)).isoformat()

        p.discover("fresh")  # This one is fresh

        expired = p.expire_stale_tasks(now=now)
        assert len(expired) == 2
        assert "old1" in expired
        assert "old2" in expired
        assert p.get_task("fresh").stage == PipelineStage.DISCOVERED

    def test_expire_only_expirable_stages(self):
        p = TaskPipeline()
        now = datetime.now(timezone.utc)

        # In-progress tasks should NOT be expired by batch
        advance_to_in_progress(p, "active")
        p.get_task("active").stage_entered_at = (now - timedelta(hours=24)).isoformat()

        expired = p.expire_stale_tasks(now=now)
        assert len(expired) == 0
        assert p.get_task("active").stage == PipelineStage.IN_PROGRESS


# ---------------------------------------------------------------------------
# 13. Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_heartbeat_updates_timestamp(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        old_hb = p.get_task("task-001").last_heartbeat
        import time
        time.sleep(0.01)
        p.heartbeat("task-001")
        new_hb = p.get_task("task-001").last_heartbeat
        assert new_hb >= old_hb

    def test_paid_can_skip_rated_to_completed(self):
        """Some tasks might complete without ratings."""
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence())
        p.review("task-001")
        p.approve("task-001")
        p.pay("task-001", "0xabc")
        # Skip rating, go directly to completed
        task = p.complete("task-001")
        assert task.stage == PipelineStage.COMPLETED

    def test_zero_bounty_task(self):
        p = TaskPipeline()
        task = p.discover("t1", title="Free task", bounty_usd=0.0)
        assert task.bounty_usd == 0.0

    def test_large_evidence_set(self):
        p = TaskPipeline()
        advance_to_in_progress(p)
        p.submit("task-001", make_evidence(50))
        assert len(p.get_task("task-001").evidence) == 50

    def test_pipeline_state_active_tasks(self):
        p = TaskPipeline()
        p.discover("t1")
        p.discover("t2")
        full_happy_path(p, "t3")

        active = p.state.active_tasks()
        assert len(active) == 2  # t1 and t2 are active, t3 is completed

    def test_agent_active_tasks(self):
        p = TaskPipeline()
        advance_to_in_progress(p, "task-001")
        advance_to_in_progress(p, "task-002")
        agent_tasks = p.state.agent_active_tasks("kk-agent-0")
        assert len(agent_tasks) == 2


# ---------------------------------------------------------------------------
# 14. Transition Hooks
# ---------------------------------------------------------------------------

class TestTransitionHooks:
    def test_hook_fires_on_transition(self):
        events_received = []

        def my_hook(task, event):
            events_received.append((task.task_id, event.to_stage))

        p = TaskPipeline(on_transition=my_hook)
        p.discover("t1")
        p.evaluate("t1", make_rankings())

        # discover fires hook for initial event, evaluate fires for transition
        assert len(events_received) == 2
        assert events_received[0] == ("t1", "discovered")
        assert events_received[1] == ("t1", "evaluated")

    def test_hook_failure_doesnt_break_pipeline(self):
        def bad_hook(task, event):
            raise RuntimeError("Hook crashed!")

        p = TaskPipeline(on_transition=bad_hook)
        task = p.discover("t1")  # Should not raise
        assert task.stage == PipelineStage.DISCOVERED


# ---------------------------------------------------------------------------
# 15. IRC Notification Formatting
# ---------------------------------------------------------------------------

class TestNotificationFormatting:
    def test_offered_notification(self):
        task = PipelineTask(task_id="t1", title="Walk the dog", bounty_usd=5.0)
        event = PipelineEvent(
            event_id="e1", task_id="t1", timestamp="",
            from_stage="evaluated", to_stage="offered",
            actor="dispatcher", details={"agent": "kk-agent-3", "score": 0.85},
        )
        msg = format_pipeline_notification(task, event)
        assert "kk-agent-3" in msg
        assert "$5.00" in msg

    def test_paid_notification(self):
        task = PipelineTask(
            task_id="t1", title="Photo verification",
            bounty_usd=3.50, assigned_agent="kk-agent-5",
        )
        event = PipelineEvent(
            event_id="e1", task_id="t1", timestamp="",
            from_stage="approved", to_stage="paid",
            actor="payment", details={"tx_hash": "0xabcdef123456"},
        )
        msg = format_pipeline_notification(task, event)
        assert "💰" in msg
        assert "$3.50" in msg
        assert "0xabcdef1234" in msg

    def test_completed_notification(self):
        task = PipelineTask(task_id="t1", title="Test", assigned_agent="kk-agent-1")
        event = PipelineEvent(
            event_id="e1", task_id="t1", timestamp="",
            from_stage="rated", to_stage="completed", actor="pipeline",
        )
        msg = format_pipeline_notification(task, event)
        assert "🎉" in msg

    def test_no_notification_for_evaluated(self):
        task = PipelineTask(task_id="t1", title="Test")
        event = PipelineEvent(
            event_id="e1", task_id="t1", timestamp="",
            from_stage="discovered", to_stage="evaluated", actor="coordinator",
        )
        msg = format_pipeline_notification(task, event)
        assert msg is None
