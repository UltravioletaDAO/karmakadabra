#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 — Tests for working_state.py

Comprehensive tests for WORKING.md parse/write cycle, state mutations,
and edge cases. These are the core state management tests.

Usage:
    pytest scripts/kk/tests/test_working_state.py -v
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.working_state import (
    ActiveTask,
    WorkingState,
    clear_active_task,
    create_initial_working_md,
    parse_working_md,
    set_active_task,
    update_heartbeat,
    write_working_md,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_working_md(tmp_dir):
    """Create a sample WORKING.md with known content."""
    content = """\
# Current State

## Active Task
- Task ID: abc-123-def
- Title: Verify on-chain fee distribution
- Status: working
- Started: 2026-02-22T00:00:00+00:00
- Next step: Submit evidence photo

## Pending
- Check daily budget remaining
- Review new task notifications

## Budget
- Daily spent: $0.15 / $2.00
- Active escrows: 1 ($0.10)

## Last Heartbeat
- Time: 2026-02-22T00:15:00+00:00
- Action: submitted evidence
- Result: awaiting approval
"""
    path = tmp_dir / "WORKING.md"
    path.write_text(content)
    return path


@pytest.fixture
def idle_working_md(tmp_dir):
    """Create a WORKING.md with idle state."""
    content = """\
# Current State

## Active Task
- Status: idle

## Pending
- (none)

## Budget
- Daily spent: $0.00 / $2.00
- Active escrows: 0 ($0.00)

## Last Heartbeat
- Time: 2026-02-22T00:00:00+00:00
- Action: workspace initialized
- Result: ok
"""
    path = tmp_dir / "WORKING.md"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# Parse Tests
# ---------------------------------------------------------------------------


class TestParseWorkingMd:
    """Tests for parse_working_md()."""

    def test_parse_active_task(self, sample_working_md):
        state = parse_working_md(sample_working_md)
        assert state.active_task.task_id == "abc-123-def"
        assert state.active_task.title == "Verify on-chain fee distribution"
        assert state.active_task.status == "working"
        assert "2026-02-22" in state.active_task.started
        assert state.active_task.next_step == "Submit evidence photo"

    def test_parse_pending_items(self, sample_working_md):
        state = parse_working_md(sample_working_md)
        assert len(state.pending) == 2
        assert "Check daily budget remaining" in state.pending
        assert "Review new task notifications" in state.pending

    def test_parse_budget(self, sample_working_md):
        state = parse_working_md(sample_working_md)
        assert state.daily_spent == 0.15
        assert state.daily_budget == 2.0
        assert state.active_escrows == 1
        assert state.escrow_total == 0.10

    def test_parse_heartbeat(self, sample_working_md):
        state = parse_working_md(sample_working_md)
        assert "2026-02-22T00:15:00" in state.last_heartbeat_time
        assert state.last_heartbeat_action == "submitted evidence"
        assert state.last_heartbeat_result == "awaiting approval"

    def test_parse_idle_state(self, idle_working_md):
        state = parse_working_md(idle_working_md)
        assert state.active_task.status == "idle"
        assert state.active_task.task_id == ""
        assert not state.has_active_task

    def test_parse_nonexistent_file(self, tmp_dir):
        state = parse_working_md(tmp_dir / "nonexistent.md")
        assert state.active_task.status == "idle"
        assert state.daily_spent == 0.0
        assert state.daily_budget == 2.0

    def test_parse_empty_file(self, tmp_dir):
        path = tmp_dir / "empty.md"
        path.write_text("")
        state = parse_working_md(path)
        assert not state.has_active_task

    def test_parse_malformed_budget(self, tmp_dir):
        """Handles gracefully if budget line has unexpected format."""
        content = """\
# Current State

## Budget
- Daily spent: lots of money
- Active escrows: many
"""
        path = tmp_dir / "WORKING.md"
        path.write_text(content)
        state = parse_working_md(path)
        # Should default to 0.0 when regex fails
        assert state.daily_spent == 0.0
        assert state.active_escrows == 0


# ---------------------------------------------------------------------------
# Write Tests
# ---------------------------------------------------------------------------


class TestWriteWorkingMd:
    """Tests for write_working_md()."""

    def test_write_read_roundtrip(self, tmp_dir):
        """Write state, read it back, verify roundtrip."""
        path = tmp_dir / "WORKING.md"
        original = WorkingState(
            active_task=ActiveTask(
                task_id="xyz-789",
                title="Index IRC transcripts",
                status="applied",
                started="2026-02-22T01:00:00+00:00",
                next_step="Wait for assignment",
            ),
            pending=["Monitor inbox", "Update MEMORY.md"],
            daily_spent=0.05,
            daily_budget=1.50,
            active_escrows=0,
            escrow_total=0.0,
            last_heartbeat_time="2026-02-22T01:00:00+00:00",
            last_heartbeat_action="applied to task",
            last_heartbeat_result="pending assignment",
        )

        write_working_md(path, original)
        assert path.exists()

        parsed = parse_working_md(path)
        assert parsed.active_task.task_id == "xyz-789"
        assert parsed.active_task.title == "Index IRC transcripts"
        assert parsed.active_task.status == "applied"
        assert parsed.daily_spent == 0.05
        assert parsed.daily_budget == 1.50
        assert len(parsed.pending) == 2
        assert parsed.last_heartbeat_action == "applied to task"

    def test_write_idle_state(self, tmp_dir):
        """Write idle state and verify."""
        path = tmp_dir / "WORKING.md"
        state = WorkingState()
        write_working_md(path, state)

        content = path.read_text()
        assert "Status: idle" in content
        assert "(none)" in content

    def test_write_creates_parent_dirs(self, tmp_dir):
        """write_working_md creates parent directories if needed."""
        path = tmp_dir / "deep" / "nested" / "WORKING.md"
        state = WorkingState()
        write_working_md(path, state)
        assert path.exists()

    def test_write_overwrites_existing(self, sample_working_md):
        """Writing to existing file replaces content."""
        new_state = WorkingState(
            active_task=ActiveTask(task_id="new-id", title="New Task", status="working"),
            daily_spent=1.00,
        )
        write_working_md(sample_working_md, new_state)
        parsed = parse_working_md(sample_working_md)
        assert parsed.active_task.task_id == "new-id"
        assert parsed.daily_spent == 1.00


# ---------------------------------------------------------------------------
# State Mutation Tests
# ---------------------------------------------------------------------------


class TestStateMutations:
    """Tests for state mutation helpers."""

    def test_has_active_task_true(self):
        state = WorkingState(
            active_task=ActiveTask(task_id="abc", status="working")
        )
        assert state.has_active_task is True

    def test_has_active_task_false_idle(self):
        state = WorkingState(
            active_task=ActiveTask(task_id="abc", status="idle")
        )
        assert state.has_active_task is False

    def test_has_active_task_false_empty(self):
        state = WorkingState()
        assert state.has_active_task is False

    def test_can_spend(self):
        state = WorkingState(daily_spent=0.50, daily_budget=2.00)
        assert state.can_spend == 1.50

    def test_can_spend_at_limit(self):
        state = WorkingState(daily_spent=2.00, daily_budget=2.00)
        assert state.can_spend == 0.0

    def test_can_spend_over_limit(self):
        state = WorkingState(daily_spent=2.50, daily_budget=2.00)
        assert state.can_spend == -0.50

    def test_set_active_task(self):
        state = WorkingState()
        set_active_task(state, "task-1", "My Task", status="browsing", next_step="Review")
        assert state.active_task.task_id == "task-1"
        assert state.active_task.title == "My Task"
        assert state.active_task.status == "browsing"
        assert state.active_task.next_step == "Review"
        assert state.active_task.started != ""  # Should be set automatically

    def test_clear_active_task(self):
        state = WorkingState(
            active_task=ActiveTask(task_id="abc", title="Old", status="working")
        )
        assert state.has_active_task
        clear_active_task(state)
        assert not state.has_active_task
        assert state.active_task.task_id == ""

    def test_update_heartbeat(self):
        state = WorkingState()
        update_heartbeat(state, "browsed EM", "found 3 tasks")
        assert state.last_heartbeat_action == "browsed EM"
        assert state.last_heartbeat_result == "found 3 tasks"
        assert state.last_heartbeat_time != ""


# ---------------------------------------------------------------------------
# Create Initial Tests
# ---------------------------------------------------------------------------


class TestCreateInitialWorkingMd:
    """Tests for create_initial_working_md()."""

    def test_creates_file(self, tmp_dir):
        path = tmp_dir / "WORKING.md"
        create_initial_working_md(path)
        assert path.exists()

    def test_template_content(self, tmp_dir):
        path = tmp_dir / "WORKING.md"
        create_initial_working_md(path)
        content = path.read_text()
        assert "# Current State" in content
        assert "Status: idle" in content
        assert "$2.00" in content

    def test_custom_budget(self, tmp_dir):
        path = tmp_dir / "WORKING.md"
        create_initial_working_md(path, daily_budget=5.0)
        content = path.read_text()
        assert "$5.00" in content

    def test_creates_parent_dirs(self, tmp_dir):
        path = tmp_dir / "workspace" / "data" / "WORKING.md"
        create_initial_working_md(path)
        assert path.exists()

    def test_parseable_after_creation(self, tmp_dir):
        """Initial template should parse cleanly."""
        path = tmp_dir / "WORKING.md"
        create_initial_working_md(path)
        state = parse_working_md(path)
        assert not state.has_active_task
        assert state.daily_budget == 2.0
        assert state.daily_spent == 0.0


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_unicode_task_title(self, tmp_dir):
        """Unicode characters in task title survive roundtrip."""
        path = tmp_dir / "WORKING.md"
        state = WorkingState(
            active_task=ActiveTask(
                task_id="uni-1",
                title="Traducir documentación al español ñ é ü",
                status="working",
            )
        )
        write_working_md(path, state)
        parsed = parse_working_md(path)
        assert "español" in parsed.active_task.title
        assert "ñ" in parsed.active_task.title

    def test_large_pending_list(self, tmp_dir):
        """Many pending items survive roundtrip."""
        path = tmp_dir / "WORKING.md"
        items = [f"Pending item {i}" for i in range(50)]
        state = WorkingState(pending=items)
        write_working_md(path, state)
        parsed = parse_working_md(path)
        assert len(parsed.pending) == 50

    def test_zero_budget(self, tmp_dir):
        """Zero budget edge case."""
        path = tmp_dir / "WORKING.md"
        state = WorkingState(daily_spent=0.0, daily_budget=0.0)
        write_working_md(path, state)
        parsed = parse_working_md(path)
        assert parsed.daily_budget == 0.0
        assert parsed.can_spend == 0.0

    def test_high_precision_budget(self, tmp_dir):
        """Budget amounts with many decimal places."""
        path = tmp_dir / "WORKING.md"
        state = WorkingState(daily_spent=0.123456, daily_budget=10.0)
        write_working_md(path, state)
        parsed = parse_working_md(path)
        # After formatting to 2 decimal places, precision is truncated
        assert abs(parsed.daily_spent - 0.12) < 0.01

    def test_colons_in_title(self, tmp_dir):
        """Task title with colons doesn't break parsing."""
        path = tmp_dir / "WORKING.md"
        state = WorkingState(
            active_task=ActiveTask(
                task_id="colon-1",
                title="Task: Important: Do This: Now",
                status="working",
            )
        )
        write_working_md(path, state)
        parsed = parse_working_md(path)
        assert "Task:" in parsed.active_task.title
        assert "Now" in parsed.active_task.title
