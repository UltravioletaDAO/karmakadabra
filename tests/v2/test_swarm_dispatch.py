"""
KK V2 — Swarm Dispatch Service Tests

Tests for the operational dispatch layer that bridges
coordinator intelligence to agent execution.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.swarm_dispatch import (
    DispatchQueue,
    DispatchRecord,
    check_stalled_tasks,
    dispatch_cycle,
    dispatch_task,
    display_queue_status,
    format_irc_assignment,
    format_irc_reassignment,
    format_irc_stall_warning,
    load_dispatch_queue,
    mark_acknowledged,
    mark_completed,
    reassign_failed_task,
    save_dispatch_queue,
)


# ===================================================================
# DispatchRecord Tests
# ===================================================================


class TestDispatchRecord:
    def test_defaults(self):
        r = DispatchRecord(task_id="t1", agent_name="kk-agent-3", dispatched_at="2026-03-01T00:00:00Z")
        assert r.status == "dispatched"
        assert r.bounty_usd == 0.0
        assert r.irc_notified is False
        assert r.em_assigned is False
        assert r.stall_checks == 0
        assert r.reassigned_to is None

    def test_full_record(self):
        r = DispatchRecord(
            task_id="t2",
            agent_name="kk-karma-hello",
            dispatched_at="2026-03-01T00:00:00Z",
            status="in_progress",
            bounty_usd=0.05,
            title="Analyze IRC logs",
            category="knowledge_access",
            match_score=0.85,
            match_mode="enhanced",
            irc_notified=True,
            em_assigned=True,
        )
        assert r.match_score == 0.85
        assert r.em_assigned is True


# ===================================================================
# Persistence Tests
# ===================================================================


class TestPersistence:
    def test_save_and_load(self, tmp_path: Path):
        queue = DispatchQueue()
        queue.active.append(
            DispatchRecord(
                task_id="t1",
                agent_name="kk-agent-3",
                dispatched_at="2026-03-01T00:00:00Z",
                bounty_usd=0.05,
                title="Test Task",
                match_score=0.75,
            )
        )
        queue.total_dispatched = 1

        path = tmp_path / "dispatch_queue.json"
        save_dispatch_queue(queue, path)
        assert path.exists()

        loaded = load_dispatch_queue(path)
        assert len(loaded.active) == 1
        assert loaded.active[0].task_id == "t1"
        assert loaded.active[0].agent_name == "kk-agent-3"
        assert loaded.total_dispatched == 1

    def test_load_nonexistent(self, tmp_path: Path):
        queue = load_dispatch_queue(tmp_path / "nonexistent.json")
        assert len(queue.active) == 0
        assert queue.total_dispatched == 0

    def test_load_corrupt_json(self, tmp_path: Path):
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json{{{")
        queue = load_dispatch_queue(path)
        assert len(queue.active) == 0

    def test_completed_trimmed_on_save(self, tmp_path: Path):
        """Only last 50 completed records are saved."""
        queue = DispatchQueue()
        for i in range(100):
            queue.completed.append(
                DispatchRecord(
                    task_id=f"t{i}",
                    agent_name=f"kk-agent-{i % 20}",
                    dispatched_at="2026-03-01T00:00:00Z",
                )
            )

        path = tmp_path / "queue.json"
        save_dispatch_queue(queue, path)
        loaded = load_dispatch_queue(path)
        assert len(loaded.completed) == 50

    def test_failed_trimmed_on_save(self, tmp_path: Path):
        """Only last 20 failed records are saved."""
        queue = DispatchQueue()
        for i in range(30):
            queue.failed.append(
                DispatchRecord(
                    task_id=f"t{i}",
                    agent_name=f"kk-agent-{i}",
                    dispatched_at="2026-03-01T00:00:00Z",
                )
            )

        path = tmp_path / "queue.json"
        save_dispatch_queue(queue, path)
        loaded = load_dispatch_queue(path)
        assert len(loaded.failed) == 20


# ===================================================================
# IRC Formatting Tests
# ===================================================================


class TestIRCFormatting:
    def test_assignment_message(self):
        r = DispatchRecord(
            task_id="t1",
            agent_name="kk-skill-extractor",
            dispatched_at="2026-03-01T00:00:00Z",
            bounty_usd=0.05,
            title="Extract Python Skills",
            match_score=0.85,
        )
        msg = format_irc_assignment(r)
        assert "kk-skill-extractor" in msg
        assert "Extract Python Skills" in msg
        assert "$0.05" in msg
        assert "85%" in msg

    def test_stall_warning_message(self):
        r = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-5",
            dispatched_at="2026-03-01T00:00:00Z",
            title="A very long task title that should be truncated properly",
        )
        msg = format_irc_stall_warning(r, 45)
        assert "kk-agent-5" in msg
        assert "45 min" in msg

    def test_reassignment_message(self):
        msg = format_irc_reassignment("kk-agent-3", "kk-agent-7", "Analyze Data Patterns")
        assert "kk-agent-3" in msg
        assert "kk-agent-7" in msg
        assert "Analyze Data" in msg

    def test_assignment_templates_rotate(self):
        """Different stall_checks produce different message templates."""
        r = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
            bounty_usd=0.10,
            title="Test",
            match_score=0.5,
        )
        messages = set()
        for i in range(3):
            r.stall_checks = i
            messages.add(format_irc_assignment(r))
        # Should produce at least 2 different messages (3 templates)
        assert len(messages) >= 2


# ===================================================================
# Dispatch Logic Tests
# ===================================================================


class TestDispatchTask:
    @pytest.mark.asyncio
    async def test_dispatch_dry_run(self):
        queue = DispatchQueue()
        record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="",
            bounty_usd=0.05,
            title="Dry Run Task",
        )
        result = await dispatch_task(record, queue, dry_run=True)
        # Dry run should not add to queue
        assert len(queue.active) == 0

    @pytest.mark.asyncio
    async def test_dispatch_with_irc(self):
        queue = DispatchQueue()
        irc_fn = AsyncMock()
        record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="",
            bounty_usd=0.05,
            title="IRC Test Task",
            match_score=0.8,
        )
        result = await dispatch_task(record, queue, irc_send_fn=irc_fn)
        assert result.irc_notified is True
        assert result.status == "dispatched"
        assert queue.total_dispatched == 1
        assert len(queue.active) == 1
        irc_fn.assert_called_once()
        call_args = irc_fn.call_args
        assert call_args[0][0] == "#karmakadabra"

    @pytest.mark.asyncio
    async def test_dispatch_with_em_client(self):
        queue = DispatchQueue()
        em_client = AsyncMock()
        em_client.assign_task = AsyncMock()
        record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="",
            title="EM Test Task",
        )
        result = await dispatch_task(record, queue, em_client=em_client)
        assert result.em_assigned is True
        em_client.assign_task.assert_called_once_with("t1", "kk-agent-3")

    @pytest.mark.asyncio
    async def test_dispatch_em_409_not_error(self):
        """409 (already assigned) should not be treated as an error."""
        queue = DispatchQueue()
        em_client = AsyncMock()
        em_client.assign_task = AsyncMock(side_effect=Exception("409 Conflict: already assigned"))
        record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="",
            title="Already Assigned Task",
        )
        result = await dispatch_task(record, queue, em_client=em_client)
        assert result.em_assigned is True  # 409 = already assigned = success

    @pytest.mark.asyncio
    async def test_dispatch_em_real_error(self):
        """Real EM errors should be recorded."""
        queue = DispatchQueue()
        em_client = AsyncMock()
        em_client.assign_task = AsyncMock(side_effect=Exception("500 Internal Server Error"))
        record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="",
            title="Error Task",
        )
        result = await dispatch_task(record, queue, em_client=em_client)
        assert result.em_assigned is False
        assert result.error is not None
        assert "500" in result.error


# ===================================================================
# Stall Detection Tests
# ===================================================================


class TestStallDetection:
    @pytest.mark.asyncio
    async def test_no_stalls_when_recent(self):
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at=datetime.now(timezone.utc).isoformat(),
            title="Fresh Task",
        ))
        stalled = await check_stalled_tasks(queue, stall_threshold_minutes=30)
        assert len(stalled) == 0

    @pytest.mark.asyncio
    async def test_stall_detected_after_threshold(self):
        queue = DispatchQueue()
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at=old_time,
            title="Old Task",
        ))
        stalled = await check_stalled_tasks(queue, stall_threshold_minutes=30)
        assert len(stalled) == 1
        assert stalled[0].stall_checks == 1

    @pytest.mark.asyncio
    async def test_stall_increments_check_count(self):
        queue = DispatchQueue()
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at=old_time,
            title="Stalling Task",
            stall_checks=1,  # Already warned once
        )
        queue.active.append(record)
        stalled = await check_stalled_tasks(queue, stall_threshold_minutes=30)
        assert len(stalled) == 1
        assert stalled[0].stall_checks == 2

    @pytest.mark.asyncio
    async def test_stall_marks_failed_after_max_checks(self):
        queue = DispatchQueue()
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat()
        record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at=old_time,
            title="Hopeless Task",
            stall_checks=2,  # One more and it fails
        )
        queue.active.append(record)
        stalled = await check_stalled_tasks(queue, stall_threshold_minutes=30, max_stall_checks=3)
        assert len(stalled) == 1
        assert stalled[0].status == "failed"
        assert len(queue.active) == 0
        assert len(queue.failed) == 1
        assert queue.total_failed == 1

    @pytest.mark.asyncio
    async def test_stall_sends_irc_warning(self):
        queue = DispatchQueue()
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at=old_time,
            title="Warning Task",
        ))
        irc_fn = AsyncMock()
        stalled = await check_stalled_tasks(
            queue, stall_threshold_minutes=30, irc_send_fn=irc_fn
        )
        assert len(stalled) == 1
        irc_fn.assert_called_once()
        msg = irc_fn.call_args[0][1]
        assert "kk-agent-3" in msg


# ===================================================================
# Task Completion / Acknowledgment Tests
# ===================================================================


class TestCompletionTracking:
    def test_mark_completed(self):
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
            title="Completable Task",
        ))

        result = mark_completed(queue, "t1", "kk-agent-3")
        assert result is not None
        assert result.status == "completed"
        assert result.completed_at is not None
        assert len(queue.active) == 0
        assert len(queue.completed) == 1
        assert queue.total_completed == 1

    def test_mark_completed_wrong_agent(self):
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
        ))

        result = mark_completed(queue, "t1", "kk-agent-7")
        assert result is None
        assert len(queue.active) == 1

    def test_mark_completed_wrong_task(self):
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
        ))

        result = mark_completed(queue, "t999", "kk-agent-3")
        assert result is None

    def test_mark_acknowledged(self):
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
        ))

        result = mark_acknowledged(queue, "t1", "kk-agent-3")
        assert result is not None
        assert result.status == "acknowledged"
        assert result.acknowledged_at is not None
        assert len(queue.active) == 1  # Still active, just acknowledged


# ===================================================================
# Reassignment Tests
# ===================================================================


class TestReassignment:
    @pytest.mark.asyncio
    async def test_reassign_creates_new_record(self):
        queue = DispatchQueue()
        old_record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
            title="Reassignable Task",
            bounty_usd=0.05,
            status="failed",
        )

        new_record = await reassign_failed_task(
            old_record, "kk-agent-7", 0.9, queue
        )

        assert old_record.status == "reassigned"
        assert old_record.reassigned_to == "kk-agent-7"
        assert new_record.agent_name == "kk-agent-7"
        assert new_record.match_score == 0.9
        assert new_record.task_id == "t1"
        assert queue.total_reassigned == 1
        assert len(queue.active) == 1

    @pytest.mark.asyncio
    async def test_reassign_with_irc_notification(self):
        queue = DispatchQueue()
        old_record = DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
            title="Notifiable Reassign",
            status="failed",
        )
        irc_fn = AsyncMock()

        await reassign_failed_task(
            old_record, "kk-agent-7", 0.8, queue, irc_send_fn=irc_fn
        )

        # Should be called at least twice: assignment + reassignment notice
        assert irc_fn.call_count >= 2


# ===================================================================
# Full Dispatch Cycle Tests
# ===================================================================


class TestDispatchCycle:
    @pytest.mark.asyncio
    async def test_basic_cycle(self):
        queue = DispatchQueue()
        tasks = [
            {"id": "t1", "title": "Task One", "bounty_usd": 0.05, "category": "research"},
            {"id": "t2", "title": "Task Two", "bounty_usd": 0.10, "category": "data"},
        ]
        rankings = {
            "t1": [("kk-agent-3", 0.85), ("kk-agent-5", 0.60)],
            "t2": [("kk-agent-7", 0.92), ("kk-agent-3", 0.70)],
        }

        results = await dispatch_cycle(
            queue, tasks, rankings, set()
        )

        assert results["dispatched"] == 2
        assert len(queue.active) == 2
        assert queue.total_dispatched == 2

    @pytest.mark.asyncio
    async def test_cycle_skips_already_active(self):
        """Tasks already in dispatch queue are not re-dispatched."""
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at="2026-03-01T00:00:00Z",
        ))

        tasks = [{"id": "t1", "title": "Already Active", "bounty_usd": 0.05}]
        rankings = {"t1": [("kk-agent-5", 0.80)]}

        results = await dispatch_cycle(queue, tasks, rankings, set())
        assert results["dispatched"] == 0

    @pytest.mark.asyncio
    async def test_cycle_skips_assigned_agents(self):
        """Agents already assigned in this cycle are skipped."""
        queue = DispatchQueue()
        tasks = [
            {"id": "t1", "title": "Task One", "bounty_usd": 0.05},
            {"id": "t2", "title": "Task Two", "bounty_usd": 0.10},
        ]
        rankings = {
            "t1": [("kk-agent-3", 0.85)],
            "t2": [("kk-agent-3", 0.90)],  # Same agent — should be skipped
        }

        results = await dispatch_cycle(queue, tasks, rankings, set())
        assert results["dispatched"] == 1  # Only one task per agent

    @pytest.mark.asyncio
    async def test_cycle_respects_max_assignments(self):
        """Dispatch cycle stops after max_assignments_per_cycle."""
        queue = DispatchQueue()
        tasks = [
            {"id": f"t{i}", "title": f"Task {i}", "bounty_usd": 0.05}
            for i in range(10)
        ]
        rankings = {
            f"t{i}": [(f"kk-agent-{i+3}", 0.80)]
            for i in range(10)
        }

        results = await dispatch_cycle(
            queue, tasks, rankings, set(), max_assignments_per_cycle=3
        )
        assert results["dispatched"] == 3

    @pytest.mark.asyncio
    async def test_cycle_falls_through_rankings(self):
        """If top-ranked agent is unavailable, use next in ranking."""
        queue = DispatchQueue()
        tasks = [{"id": "t1", "title": "Fallthrough Task", "bounty_usd": 0.05}]
        rankings = {
            "t1": [("kk-agent-3", 0.95), ("kk-agent-5", 0.80), ("kk-agent-7", 0.60)],
        }

        # kk-agent-3 is already assigned
        results = await dispatch_cycle(
            queue, tasks, rankings, {"kk-agent-3"}
        )
        assert results["dispatched"] == 1
        assert queue.active[0].agent_name == "kk-agent-5"

    @pytest.mark.asyncio
    async def test_cycle_empty_tasks(self):
        queue = DispatchQueue()
        results = await dispatch_cycle(queue, [], {}, set())
        assert results["dispatched"] == 0

    @pytest.mark.asyncio
    async def test_cycle_with_stalled_tasks(self):
        """Cycle detects stalled tasks from previous cycles."""
        queue = DispatchQueue()
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
        queue.active.append(DispatchRecord(
            task_id="t-old",
            agent_name="kk-agent-3",
            dispatched_at=old_time,
            title="Stalled From Last Cycle",
        ))

        results = await dispatch_cycle(queue, [], {}, set())
        assert results["stalled"] == 1

    @pytest.mark.asyncio
    async def test_cycle_updates_last_cycle_at(self):
        queue = DispatchQueue()
        assert queue.last_cycle_at is None

        await dispatch_cycle(queue, [], {}, set())
        assert queue.last_cycle_at is not None


# ===================================================================
# Display (smoke test)
# ===================================================================


class TestDisplay:
    def test_display_empty_queue(self, capsys):
        queue = DispatchQueue()
        display_queue_status(queue)
        captured = capsys.readouterr()
        assert "Dispatch Queue" in captured.out
        assert "Dispatched: 0" in captured.out

    def test_display_with_data(self, capsys):
        queue = DispatchQueue()
        queue.active.append(DispatchRecord(
            task_id="t1",
            agent_name="kk-agent-3",
            dispatched_at=datetime.now(timezone.utc).isoformat(),
            title="Active Task for Display",
            bounty_usd=0.05,
            match_score=0.85,
        ))
        queue.total_dispatched = 5
        queue.total_completed = 3
        queue.total_failed = 1

        display_queue_status(queue)
        captured = capsys.readouterr()
        assert "Active (1)" in captured.out
        assert "kk-agent-3" in captured.out
        assert "Dispatched: 5" in captured.out
