"""
Tests for cron/heartbeat.py — KK V2 Agent Heartbeat Runner

Tests cover:
  - Stagger offset calculations (thundering herd prevention)
  - Individual heartbeat cycles (action routing, state management)
  - Agent-specific heartbeat behaviors (coordinator, karma-hello, etc.)
  - Error handling and graceful degradation
  - Working state persistence
  - IRC and vault integration (non-fatal paths)
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cron.heartbeat import (
    COMMUNITY_BASE_OFFSET,
    DEFAULT_INTERVAL,
    SYSTEM_AGENT_OFFSETS,
    action_browse_and_apply,
    action_check_own_tasks,
    action_resume_task,
    get_stagger_offset,
    heartbeat_once,
    run_all_heartbeats,
)
from lib.working_state import ActiveTask, WorkingState


# ═══════════════════════════════════════════════════════════════════
# Stagger Calculations
# ═══════════════════════════════════════════════════════════════════


class TestStaggerOffset:
    """Tests for thundering herd prevention via staggered scheduling."""

    def test_system_agents_have_fixed_offsets(self):
        """System agents use predefined offsets from SYSTEM_AGENT_OFFSETS."""
        for name, expected_offset in SYSTEM_AGENT_OFFSETS.items():
            assert get_stagger_offset(name, 0) == float(expected_offset)

    def test_coordinator_starts_first(self):
        """Coordinator gets offset 0 (starts immediately)."""
        assert get_stagger_offset("kk-coordinator", 0) == 0.0

    def test_community_agents_use_index_based_offset(self):
        """Community agents get COMMUNITY_BASE_OFFSET + index * 2."""
        for i in range(10):
            name = f"kk-community-{i}"
            expected = COMMUNITY_BASE_OFFSET + (i * 2)
            assert get_stagger_offset(name, i) == expected

    def test_no_overlapping_system_offsets(self):
        """System agents should not share the same offset."""
        offsets = list(SYSTEM_AGENT_OFFSETS.values())
        # Coordinator gets 0, others should be different from each other
        assert len(set(offsets)) >= len(offsets) - 1  # Allow at most one collision

    def test_community_offsets_are_positive(self):
        """All community agent offsets should be positive."""
        for i in range(20):
            assert get_stagger_offset(f"kk-agent-{i}", i) > 0

    def test_default_interval_is_15_minutes(self):
        """Default heartbeat interval should be 900 seconds (15 min)."""
        assert DEFAULT_INTERVAL == 900

    def test_community_base_offset_is_positive(self):
        """Community agents have a positive base offset."""
        assert COMMUNITY_BASE_OFFSET > 0


# ═══════════════════════════════════════════════════════════════════
# Action: Resume Task
# ═══════════════════════════════════════════════════════════════════


class TestActionResumeTask:
    """Tests for resuming tasks in various states."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.executor_id = "exec-123"
        client.get_task = AsyncMock()
        client.submit_evidence = AsyncMock()
        client.get_submissions = AsyncMock(return_value=[])
        client.approve_submission = AsyncMock()
        return client

    @pytest.fixture
    def working_state(self):
        state = WorkingState()
        state.active_task = ActiveTask(
            task_id="task-abc",
            title="Test Task",
            status="applied",
            started="2026-03-07T00:00:00Z",
            next_step="Wait for assignment",
        )
        return state

    @pytest.mark.asyncio
    async def test_applied_task_becomes_working_on_assignment(self, mock_client, working_state):
        """When EM shows task is in_progress with executor, transition to working."""
        mock_client.get_task.return_value = {
            "status": "in_progress",
            "executor_id": "exec-456",
        }
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "assigned" in result
        assert working_state.active_task.status == "working"

    @pytest.mark.asyncio
    async def test_applied_task_cleared_on_cancellation(self, mock_client, working_state):
        """When EM shows task is cancelled, clear active task."""
        mock_client.get_task.return_value = {"status": "cancelled", "executor_id": ""}
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "cancelled" in result

    @pytest.mark.asyncio
    async def test_applied_task_cleared_on_expiry(self, mock_client, working_state):
        """When EM shows task is expired, clear active task."""
        mock_client.get_task.return_value = {"status": "expired", "executor_id": ""}
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "expired" in result

    @pytest.mark.asyncio
    async def test_applied_task_waiting_on_pending(self, mock_client, working_state):
        """When EM shows task is still pending, keep waiting."""
        mock_client.get_task.return_value = {"status": "published", "executor_id": ""}
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "waiting" in result

    @pytest.mark.asyncio
    async def test_working_task_becomes_submitting(self, mock_client, working_state):
        """Working tasks transition to submitting on next heartbeat."""
        working_state.active_task.status = "working"
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert working_state.active_task.status == "submitting"

    @pytest.mark.asyncio
    async def test_working_task_dry_run(self, mock_client, working_state):
        """Dry run should not change task status."""
        working_state.active_task.status = "working"
        result = await action_resume_task(mock_client, working_state, dry_run=True)
        assert "DRY RUN" in result

    @pytest.mark.asyncio
    async def test_submitting_task_submits_evidence(self, mock_client, working_state):
        """Submitting tasks should submit evidence to EM."""
        working_state.active_task.status = "submitting"
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        mock_client.submit_evidence.assert_called_once()
        assert "evidence submitted" in result

    @pytest.mark.asyncio
    async def test_submitting_without_executor_id(self, mock_client, working_state):
        """Without executor_id, submission should be skipped."""
        working_state.active_task.status = "submitting"
        mock_client.agent.executor_id = None
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "no executor_id" in result

    @pytest.mark.asyncio
    async def test_submitted_task_completed(self, mock_client, working_state):
        """Submitted task that's completed on EM should be cleared."""
        working_state.active_task.status = "submitted"
        mock_client.get_task.return_value = {"status": "completed"}
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "completed and paid" in result

    @pytest.mark.asyncio
    async def test_submitted_task_still_reviewing(self, mock_client, working_state):
        """Submitted task still under review should keep waiting."""
        working_state.active_task.status = "submitted"
        mock_client.get_task.return_value = {"status": "in_review"}
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "under review" in result

    @pytest.mark.asyncio
    async def test_reviewing_task_approves_submission(self, mock_client, working_state):
        """Reviewing tasks should approve submissions with evidence."""
        working_state.active_task.status = "reviewing"
        mock_client.get_submissions.return_value = [
            {"id": "sub-1", "evidence_url": "https://evidence.example.com/1"},
        ]
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        mock_client.approve_submission.assert_called_once_with("sub-1", rating_score=80)
        assert "approved submission" in result

    @pytest.mark.asyncio
    async def test_reviewing_no_submissions(self, mock_client, working_state):
        """Reviewing with no submissions should report nothing actionable."""
        working_state.active_task.status = "reviewing"
        mock_client.get_submissions.return_value = []
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "no actionable" in result

    @pytest.mark.asyncio
    async def test_unknown_status_reports_gracefully(self, mock_client, working_state):
        """Unknown task status should report gracefully."""
        working_state.active_task.status = "phantom_state"
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "unknown task status" in result

    @pytest.mark.asyncio
    async def test_api_failure_on_check(self, mock_client, working_state):
        """API failures should be caught and reported."""
        mock_client.get_task.side_effect = Exception("connection timeout")
        result = await action_resume_task(mock_client, working_state, dry_run=False)
        assert "check failed" in result


# ═══════════════════════════════════════════════════════════════════
# Action: Browse and Apply
# ═══════════════════════════════════════════════════════════════════


class TestActionBrowseAndApply:
    """Tests for browsing EM and applying to matching tasks."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.wallet_address = "0xAgent123"
        client.agent.executor_id = "exec-123"
        client.agent.name = "kk-test-agent"
        client.browse_tasks = AsyncMock(return_value=[])
        client.apply_to_task = AsyncMock()
        return client

    @pytest.fixture
    def working_state(self):
        state = WorkingState()
        # active_task defaults to empty ActiveTask, so has_active_task is False
        # daily_budget=2.0 - daily_spent=0.0 → can_spend = 2.0
        return state

    @pytest.fixture
    def skills(self):
        return {
            "top_skills": [
                {"skill": "data analysis"},
                {"skill": "content creation"},
            ]
        }

    @pytest.mark.asyncio
    async def test_no_tasks_available(self, mock_client, working_state, skills):
        """When no tasks available, report accordingly."""
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=False)
        assert "no matching tasks" in result

    @pytest.mark.asyncio
    async def test_matches_by_skill(self, mock_client, working_state, skills):
        """Should match tasks containing agent's skill keywords."""
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-1",
                "title": "Need data analysis help",
                "instructions": "Analyze this dataset",
                "bounty_usd": 0.05,
                "agent_wallet": "0xOtherAgent",
            },
        ]
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=False)
        mock_client.apply_to_task.assert_called_once()
        assert "applied to" in result

    @pytest.mark.asyncio
    async def test_skips_own_tasks(self, mock_client, working_state, skills):
        """Agent should not apply to its own tasks."""
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-own",
                "title": "data analysis task",
                "instructions": "...",
                "bounty_usd": 0.01,
                "agent_wallet": "0xAgent123",  # Same as mock agent
            },
        ]
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=False)
        mock_client.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_over_budget(self, mock_client, working_state, skills):
        """Should skip tasks that exceed spending budget."""
        working_state.daily_spent = working_state.daily_budget - 0.01  # can_spend = 0.01
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-expensive",
                "title": "data analysis",
                "instructions": "...",
                "bounty_usd": 100.0,
                "agent_wallet": "0xOther",
            },
        ]
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=False)
        mock_client.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_no_application(self, mock_client, working_state, skills):
        """Dry run should preview but not actually apply."""
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-1",
                "title": "data analysis needed",
                "instructions": "...",
                "bounty_usd": 0.02,
                "agent_wallet": "0xOther",
            },
        ]
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=True)
        mock_client.apply_to_task.assert_not_called()
        assert "DRY RUN" in result

    @pytest.mark.asyncio
    async def test_no_executor_id(self, mock_client, working_state, skills):
        """Without executor_id, cannot apply."""
        mock_client.agent.executor_id = None
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-1",
                "title": "data analysis needed",
                "instructions": "...",
                "bounty_usd": 0.02,
                "agent_wallet": "0xOther",
            },
        ]
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=False)
        assert "no executor_id" in result

    @pytest.mark.asyncio
    async def test_matches_kk_tagged_tasks(self, mock_client, working_state, skills):
        """Tasks tagged with [kk should match regardless of skills."""
        skills = {"top_skills": []}  # No skills
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-kk",
                "title": "[kk data] Some internal task",
                "instructions": "...",
                "bounty_usd": 0.01,
                "agent_wallet": "0xOther",
            },
        ]
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=False)
        mock_client.apply_to_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_error_on_browse(self, mock_client, working_state, skills):
        """API errors during browse should be caught."""
        mock_client.browse_tasks.side_effect = Exception("API down")
        result = await action_browse_and_apply(mock_client, working_state, skills, dry_run=False)
        assert "browse failed" in result


# ═══════════════════════════════════════════════════════════════════
# Action: Check Own Tasks
# ═══════════════════════════════════════════════════════════════════


class TestActionCheckOwnTasks:
    """Tests for checking submissions on agent's published tasks."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.wallet_address = "0xAgent123"
        client.list_tasks = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def working_state(self):
        state = WorkingState()
        # Default state: no active task, has_active_task is False
        return state

    @pytest.mark.asyncio
    async def test_no_submissions(self, mock_client, working_state):
        """No submissions means nothing to review."""
        result = await action_check_own_tasks(mock_client, working_state, dry_run=False)
        assert "no submissions to review" in result

    @pytest.mark.asyncio
    async def test_found_submission(self, mock_client, working_state):
        """Finding a submitted task should set it as active for review."""
        mock_client.list_tasks.return_value = [
            {"id": "task-review", "title": "My Data Task"},
        ]
        result = await action_check_own_tasks(mock_client, working_state, dry_run=False)
        assert "found submission to review" in result
        assert working_state.has_active_task

    @pytest.mark.asyncio
    async def test_api_error(self, mock_client, working_state):
        """API errors should be caught gracefully."""
        mock_client.list_tasks.side_effect = Exception("timeout")
        result = await action_check_own_tasks(mock_client, working_state, dry_run=False)
        assert "list tasks failed" in result


# ═══════════════════════════════════════════════════════════════════
# Heartbeat Once (Integration-Level)
# ═══════════════════════════════════════════════════════════════════


class TestHeartbeatOnce:
    """Tests for the full heartbeat_once cycle (mocked dependencies)."""

    @pytest.fixture
    def workspace_dir(self, tmp_path):
        ws = tmp_path / "kk-test-agent"
        ws.mkdir()
        memory_dir = ws / "memory"
        memory_dir.mkdir()
        # Create minimal WORKING.md
        working_path = memory_dir / "WORKING.md"
        working_path.write_text(
            "# WORKING.md\n\n## Status\nidle\n\n## Budget\n"
            "daily_budget: 1.00\ndaily_spent: 0.00\n",
            encoding="utf-8",
        )
        return ws

    @pytest.fixture
    def data_dir(self, tmp_path):
        dd = tmp_path / "data"
        dd.mkdir()
        skills_dir = dd / "skills"
        skills_dir.mkdir()
        # Write a skills file
        (skills_dir / "test-agent.json").write_text(
            json.dumps({"top_skills": [{"skill": "testing"}]}),
            encoding="utf-8",
        )
        return dd

    @pytest.mark.asyncio
    async def test_basic_heartbeat_dry_run(self, workspace_dir, data_dir):
        """Basic heartbeat should complete in dry-run mode without errors."""
        with patch("cron.heartbeat.load_agent_context") as mock_lac, \
             patch("cron.heartbeat.EMClient") as mock_emc_cls, \
             patch("cron.heartbeat.poll_notifications", new_callable=AsyncMock, return_value=[]), \
             patch("cron.heartbeat.check_irc_and_respond", new_callable=AsyncMock, return_value=""):

            mock_agent = MagicMock()
            mock_agent.name = "kk-test-agent"
            mock_agent.wallet_address = "0xTestAgent"
            mock_agent.executor_id = "exec-test"
            mock_lac.return_value = mock_agent

            mock_client = MagicMock()
            mock_client.browse_tasks = AsyncMock(return_value=[])
            mock_client.list_tasks = AsyncMock(return_value=[])
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            result = await heartbeat_once(workspace_dir, data_dir, dry_run=True)

            assert result["agent"] == "kk-test-agent"
            assert "action" in result
            assert "result" in result

    @pytest.mark.asyncio
    async def test_coordinator_heartbeat(self, workspace_dir, data_dir):
        """Coordinator agent should run coordination_cycle."""
        # Rename workspace to coordinator
        coord_ws = workspace_dir.parent / "kk-coordinator"
        workspace_dir.rename(coord_ws)

        with patch("cron.heartbeat.load_agent_context") as mock_lac, \
             patch("cron.heartbeat.EMClient") as mock_emc_cls, \
             patch("cron.heartbeat.poll_notifications", new_callable=AsyncMock, return_value=[]), \
             patch("cron.heartbeat.run_coordinator_cycle", new_callable=AsyncMock) as mock_coord, \
             patch("cron.heartbeat.check_irc_and_respond", new_callable=AsyncMock, return_value=""):

            mock_agent = MagicMock()
            mock_agent.name = "kk-coordinator"
            mock_agent.wallet_address = "0xCoord"
            mock_lac.return_value = mock_agent

            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            mock_coord.return_value = {
                "assignments": [{"agent": "kk-1", "task": "t-1"}],
                "summary": {"total_agents": 5},
            }

            result = await heartbeat_once(coord_ws, data_dir, dry_run=True)
            assert result["action"] == "coordinator_service"
            assert "1 assignments" in result["result"]

    @pytest.mark.asyncio
    async def test_notification_driven_task_assignment(self, workspace_dir, data_dir):
        """Coordinator notifications should assign tasks automatically."""
        with patch("cron.heartbeat.load_agent_context") as mock_lac, \
             patch("cron.heartbeat.EMClient") as mock_emc_cls, \
             patch("cron.heartbeat.poll_notifications", new_callable=AsyncMock) as mock_poll, \
             patch("cron.heartbeat.check_irc_and_respond", new_callable=AsyncMock, return_value=""):

            mock_agent = MagicMock()
            mock_agent.name = "kk-test-agent"
            mock_agent.wallet_address = "0xTest"
            mock_agent.executor_id = "exec-123"
            mock_lac.return_value = mock_agent

            mock_client = MagicMock()
            mock_client.browse_tasks = AsyncMock(return_value=[])
            mock_client.list_tasks = AsyncMock(return_value=[])
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            # Simulate coordinator notification
            mock_poll.return_value = [
                {
                    "content": json.dumps({
                        "type": "task_assignment",
                        "task_id": "task-coord-1",
                        "title": "Assigned by coordinator",
                    }),
                },
            ]

            result = await heartbeat_once(workspace_dir, data_dir, dry_run=True)
            # The notification should have set the active task
            assert result["agent"] == "kk-test-agent"

    @pytest.mark.asyncio
    async def test_notification_poll_failure_nonfatal(self, workspace_dir, data_dir):
        """Notification poll failures should not crash the heartbeat."""
        with patch("cron.heartbeat.load_agent_context") as mock_lac, \
             patch("cron.heartbeat.EMClient") as mock_emc_cls, \
             patch("cron.heartbeat.poll_notifications", new_callable=AsyncMock) as mock_poll, \
             patch("cron.heartbeat.check_irc_and_respond", new_callable=AsyncMock, return_value=""):

            mock_agent = MagicMock()
            mock_agent.name = "kk-test-agent"
            mock_agent.wallet_address = "0xTest"
            mock_agent.executor_id = "exec-123"
            mock_lac.return_value = mock_agent

            mock_client = MagicMock()
            mock_client.browse_tasks = AsyncMock(return_value=[])
            mock_client.list_tasks = AsyncMock(return_value=[])
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            mock_poll.side_effect = ConnectionError("IRC down")

            result = await heartbeat_once(workspace_dir, data_dir, dry_run=True)
            # Should still complete despite notification failure
            assert result["agent"] == "kk-test-agent"


# ═══════════════════════════════════════════════════════════════════
# Run All Heartbeats (Orchestration)
# ═══════════════════════════════════════════════════════════════════


class TestRunAllHeartbeats:
    """Tests for multi-agent heartbeat orchestration."""

    @pytest.fixture
    def workspaces_dir(self, tmp_path):
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir()
        # Create multiple agent workspaces
        for name in ["kk-coordinator", "kk-karma-hello", "kk-agent-3"]:
            agent_dir = ws_dir / name
            agent_dir.mkdir()
            memory_dir = agent_dir / "memory"
            memory_dir.mkdir()
            (memory_dir / "WORKING.md").write_text(
                "# WORKING.md\n\n## Status\nidle\n",
                encoding="utf-8",
            )
        return ws_dir

    @pytest.fixture
    def data_dir(self, tmp_path):
        dd = tmp_path / "data"
        dd.mkdir()
        (dd / "skills").mkdir()
        return dd

    @pytest.mark.asyncio
    async def test_discovers_agents_from_directory(self, workspaces_dir, data_dir):
        """Should discover agents from workspace directory."""
        with patch("cron.heartbeat.heartbeat_once", new_callable=AsyncMock) as mock_hb:
            mock_hb.return_value = {"agent": "test", "action": "idle", "result": "ok"}
            results = await run_all_heartbeats(
                workspaces_dir, data_dir, None, None, dry_run=True, stagger=False,
            )
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_single_agent_mode(self, workspaces_dir, data_dir):
        """Should run only specified agent when agent_name is given."""
        with patch("cron.heartbeat.heartbeat_once", new_callable=AsyncMock) as mock_hb:
            mock_hb.return_value = {"agent": "kk-coordinator", "action": "idle", "result": "ok"}
            results = await run_all_heartbeats(
                workspaces_dir, data_dir, "kk-coordinator", None, dry_run=True, stagger=False,
            )
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_max_agents_limit(self, workspaces_dir, data_dir):
        """Should limit agent count when max_agents is specified."""
        with patch("cron.heartbeat.heartbeat_once", new_callable=AsyncMock) as mock_hb:
            mock_hb.return_value = {"agent": "test", "action": "idle", "result": "ok"}
            results = await run_all_heartbeats(
                workspaces_dir, data_dir, None, 2, dry_run=True, stagger=False,
            )
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_manifest_based_discovery(self, workspaces_dir, data_dir):
        """Should use _manifest.json if available."""
        manifest = workspaces_dir / "_manifest.json"
        manifest.write_text(json.dumps({
            "workspaces": [
                {"name": "kk-coordinator"},
                {"name": "kk-karma-hello"},
            ],
        }), encoding="utf-8")

        with patch("cron.heartbeat.heartbeat_once", new_callable=AsyncMock) as mock_hb:
            mock_hb.return_value = {"agent": "test", "action": "idle", "result": "ok"}
            results = await run_all_heartbeats(
                workspaces_dir, data_dir, None, None, dry_run=True, stagger=False,
            )
            assert len(results) == 2
