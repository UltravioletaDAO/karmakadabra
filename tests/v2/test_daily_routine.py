"""
Tests for cron/daily_routine.py — KK V2 Daily Activity Cron

Tests cover:
  - Phase definitions and scheduling
  - Browse phase (skill matching, budget constraints)
  - Review phase (submission approval)
  - Announce phase (IRC placeholder)
  - Publish phase (task creation)
  - Rate phase (completed interactions)
  - Summary phase (daily digest + budget reset)
  - Multi-agent orchestration with stagger
  - Daemon mode phase scheduling
  - Edge cases and error handling
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cron.daily_routine import (
    PHASES,
    phase_announce,
    phase_browse,
    phase_publish,
    phase_rate,
    phase_review,
    run_agent_daily,
    run_all_agents,
)


# ═══════════════════════════════════════════════════════════════════
# Phase Definitions
# ═══════════════════════════════════════════════════════════════════


class TestPhaseDefinitions:
    """Tests for phase scheduling constants."""

    def test_all_phases_have_hours(self):
        """Every phase must have a scheduled hour."""
        for name, config in PHASES.items():
            assert "hour" in config, f"Phase {name} missing hour"
            assert 0 <= config["hour"] <= 23

    def test_all_phases_have_descriptions(self):
        """Every phase must have a description."""
        for name, config in PHASES.items():
            assert "description" in config
            assert len(config["description"]) > 5

    def test_phases_ordered_chronologically(self):
        """Phases should be roughly ordered by hour."""
        hours = [config["hour"] for config in PHASES.values()]
        assert hours == sorted(hours), "Phases should be in chronological order"

    def test_expected_phases_exist(self):
        """All expected phases should be defined."""
        expected = {"browse", "review", "announce", "publish", "rate", "summary"}
        assert set(PHASES.keys()) == expected

    def test_browse_is_early_morning(self):
        """Browse phase should happen in early morning (UTC)."""
        assert PHASES["browse"]["hour"] <= 8

    def test_summary_is_late_evening(self):
        """Summary phase should happen in late evening (UTC)."""
        assert PHASES["summary"]["hour"] >= 20


# ═══════════════════════════════════════════════════════════════════
# Phase: Browse
# ═══════════════════════════════════════════════════════════════════


class TestPhaseBrowse:
    """Tests for the browse phase (task discovery + application)."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.wallet_address = "0xAgent123"
        client.agent.executor_id = "exec-1"
        client.agent.can_spend = MagicMock(return_value=True)
        client.browse_tasks = AsyncMock(return_value=[])
        client.apply_to_task = AsyncMock()
        return client

    @pytest.fixture
    def skills(self):
        return {
            "top_skills": [
                {"skill": "blockchain"},
                {"skill": "data analysis"},
            ]
        }

    @pytest.mark.asyncio
    async def test_no_tasks(self, mock_client, skills):
        result = await phase_browse(mock_client, skills, dry_run=False)
        assert result["applied"] == 0

    @pytest.mark.asyncio
    async def test_applies_to_matching_task(self, mock_client, skills):
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-1",
                "title": "blockchain analysis",
                "description": "analyze this",
                "bounty_usdc": 0.05,
                "agent_wallet": "0xOther",
            },
        ]
        result = await phase_browse(mock_client, skills, dry_run=False)
        assert result["applied"] == 1
        mock_client.apply_to_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_own_tasks(self, mock_client, skills):
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-own",
                "title": "blockchain stuff",
                "description": "...",
                "bounty_usdc": 0.01,
                "agent_wallet": "0xAgent123",
            },
        ]
        result = await phase_browse(mock_client, skills, dry_run=False)
        assert result["applied"] == 0

    @pytest.mark.asyncio
    async def test_max_3_applications(self, mock_client, skills):
        """Should apply to at most 3 tasks per browse cycle."""
        mock_client.browse_tasks.return_value = [
            {
                "id": f"task-{i}",
                "title": "blockchain analysis needed",
                "description": "...",
                "bounty_usdc": 0.01,
                "agent_wallet": "0xOther",
            }
            for i in range(10)
        ]
        result = await phase_browse(mock_client, skills, dry_run=False)
        assert result["applied"] == 3

    @pytest.mark.asyncio
    async def test_budget_check(self, mock_client, skills):
        mock_client.agent.can_spend = MagicMock(return_value=False)
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-1",
                "title": "blockchain",
                "description": "...",
                "bounty_usdc": 100.0,
                "agent_wallet": "0xOther",
            },
        ]
        result = await phase_browse(mock_client, skills, dry_run=False)
        assert result["applied"] == 0

    @pytest.mark.asyncio
    async def test_matches_kk_tagged_tasks(self, mock_client, skills):
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-kk",
                "title": "[kk data] internal exchange",
                "description": "agent internal",
                "bounty_usdc": 0.01,
                "agent_wallet": "0xOther",
            },
        ]
        result = await phase_browse(mock_client, skills, dry_run=False)
        assert result["applied"] == 1

    @pytest.mark.asyncio
    async def test_dry_run_counts_but_no_calls(self, mock_client, skills):
        mock_client.browse_tasks.return_value = [
            {
                "id": "task-1",
                "title": "blockchain",
                "description": "...",
                "bounty_usdc": 0.01,
                "agent_wallet": "0xOther",
            },
        ]
        result = await phase_browse(mock_client, skills, dry_run=True)
        assert result["applied"] == 1
        mock_client.apply_to_task.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# Phase: Review
# ═══════════════════════════════════════════════════════════════════


class TestPhaseReview:
    """Tests for the review phase (submission approval)."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.wallet_address = "0xAgent123"
        client.list_tasks = AsyncMock(return_value=[])
        client.get_submissions = AsyncMock(return_value=[])
        client.approve_submission = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_no_submitted_tasks(self, mock_client):
        result = await phase_review(mock_client, dry_run=False)
        assert result["reviewed"] == 0

    @pytest.mark.asyncio
    async def test_approves_submissions_with_evidence(self, mock_client):
        mock_client.list_tasks.return_value = [{"id": "task-1"}]
        mock_client.get_submissions.return_value = [
            {"id": "sub-1", "evidence_url": "https://evidence.example.com"},
        ]
        result = await phase_review(mock_client, dry_run=False)
        assert result["reviewed"] == 1
        mock_client.approve_submission.assert_called_once_with("sub-1", rating_score=80)

    @pytest.mark.asyncio
    async def test_dry_run_counts_but_no_approve(self, mock_client):
        mock_client.list_tasks.return_value = [{"id": "task-1"}]
        mock_client.get_submissions.return_value = [
            {"id": "sub-1", "evidence_url": "https://evidence.example.com"},
        ]
        result = await phase_review(mock_client, dry_run=True)
        assert result["reviewed"] == 1
        mock_client.approve_submission.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_submissions_without_evidence(self, mock_client):
        mock_client.list_tasks.return_value = [{"id": "task-1"}]
        mock_client.get_submissions.return_value = [
            {"id": "sub-1", "evidence_url": ""},
        ]
        result = await phase_review(mock_client, dry_run=False)
        assert result["reviewed"] == 0


# ═══════════════════════════════════════════════════════════════════
# Phase: Announce
# ═══════════════════════════════════════════════════════════════════


class TestPhaseAnnounce:
    """Tests for the IRC announcement phase."""

    @pytest.mark.asyncio
    async def test_announces_agent_availability(self):
        skills = {"top_skills": [{"skill": "AI"}, {"skill": "NLP"}]}
        result = await phase_announce("kk-test-agent", skills, dry_run=False)
        assert result["announced"] == 1

    @pytest.mark.asyncio
    async def test_dry_run_announce(self):
        skills = {"top_skills": [{"skill": "testing"}]}
        result = await phase_announce("kk-agent-5", skills, dry_run=True)
        assert result["announced"] == 1

    @pytest.mark.asyncio
    async def test_empty_skills(self):
        skills = {"top_skills": []}
        result = await phase_announce("kk-agent-x", skills, dry_run=False)
        assert result["announced"] == 1


# ═══════════════════════════════════════════════════════════════════
# Phase: Publish
# ═══════════════════════════════════════════════════════════════════


class TestPhasePublish:
    """Tests for the task publication phase."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.name = "kk-test-agent"
        client.agent.can_spend = MagicMock(return_value=True)
        client.agent.record_spend = MagicMock()
        client.publish_task = AsyncMock(return_value={"id": "new-task-1"})
        return client

    @pytest.mark.asyncio
    async def test_publishes_knowledge_request(self, mock_client):
        skills = {"top_skills": [{"skill": "blockchain"}]}
        result = await phase_publish(mock_client, skills, dry_run=False)
        assert result["published"] == 1
        mock_client.publish_task.assert_called_once()
        mock_client.agent.record_spend.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_budget(self, mock_client):
        mock_client.agent.can_spend = MagicMock(return_value=False)
        skills = {"top_skills": [{"skill": "x"}]}
        result = await phase_publish(mock_client, skills, dry_run=False)
        assert result["published"] == 0

    @pytest.mark.asyncio
    async def test_dry_run_publish(self, mock_client):
        skills = {"top_skills": [{"skill": "AI"}]}
        result = await phase_publish(mock_client, skills, dry_run=True)
        assert result["published"] == 1
        mock_client.publish_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_skill_name(self, mock_client):
        """Empty skills should use fallback topic."""
        skills = {"top_skills": []}
        result = await phase_publish(mock_client, skills, dry_run=True)
        assert result["published"] == 1

    @pytest.mark.asyncio
    async def test_publish_api_error(self, mock_client):
        mock_client.publish_task.side_effect = Exception("quota exceeded")
        skills = {"top_skills": [{"skill": "x"}]}
        result = await phase_publish(mock_client, skills, dry_run=False)
        assert result["published"] == 0


# ═══════════════════════════════════════════════════════════════════
# Phase: Rate
# ═══════════════════════════════════════════════════════════════════


class TestPhaseRate:
    """Tests for the rating phase."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.wallet_address = "0xAgent123"
        client.list_tasks = AsyncMock(return_value=[])
        return client

    @pytest.mark.asyncio
    async def test_no_completed_tasks(self, mock_client):
        result = await phase_rate(mock_client, dry_run=False)
        assert result["rated"] == 0

    @pytest.mark.asyncio
    async def test_rates_completed_tasks(self, mock_client):
        mock_client.list_tasks.return_value = [
            {"id": f"task-{i}"} for i in range(3)
        ]
        result = await phase_rate(mock_client, dry_run=False)
        assert result["rated"] == 3

    @pytest.mark.asyncio
    async def test_max_5_ratings(self, mock_client):
        """Should rate at most 5 tasks per cycle."""
        mock_client.list_tasks.return_value = [
            {"id": f"task-{i}"} for i in range(10)
        ]
        result = await phase_rate(mock_client, dry_run=False)
        assert result["rated"] == 5


# ═══════════════════════════════════════════════════════════════════
# Agent Daily Routine (Integration)
# ═══════════════════════════════════════════════════════════════════


class TestRunAgentDaily:
    """Tests for running daily routine on a single agent."""

    @pytest.fixture
    def workspace_dir(self, tmp_path):
        ws = tmp_path / "kk-test-agent"
        ws.mkdir()
        return ws

    @pytest.fixture
    def data_dir(self, tmp_path):
        dd = tmp_path / "data"
        dd.mkdir()
        (dd / "skills").mkdir()
        (dd / "skills" / "test-agent.json").write_text(
            json.dumps({"top_skills": [{"skill": "testing"}]}),
            encoding="utf-8",
        )
        return dd

    @pytest.mark.asyncio
    async def test_single_phase(self, workspace_dir, data_dir):
        """Running a single phase should complete without error."""
        with patch("cron.daily_routine.load_agent_context") as mock_lac, \
             patch("cron.daily_routine.EMClient") as mock_emc_cls:

            mock_agent = MagicMock()
            mock_agent.name = "kk-test-agent"
            mock_agent.wallet_address = "0xTest"
            mock_agent.executor_id = "exec-1"
            mock_agent.can_spend = MagicMock(return_value=True)
            mock_lac.return_value = mock_agent

            mock_client = MagicMock()
            mock_client.browse_tasks = AsyncMock(return_value=[])
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            results = await run_agent_daily(workspace_dir, data_dir, "browse", dry_run=True)
            assert "browse" in results
            assert results["browse"]["applied"] == 0

    @pytest.mark.asyncio
    async def test_all_phases(self, workspace_dir, data_dir):
        """Running all phases should execute each one."""
        with patch("cron.daily_routine.load_agent_context") as mock_lac, \
             patch("cron.daily_routine.EMClient") as mock_emc_cls:

            mock_agent = MagicMock()
            mock_agent.name = "kk-test-agent"
            mock_agent.wallet_address = "0xTest"
            mock_agent.executor_id = "exec-1"
            mock_agent.can_spend = MagicMock(return_value=True)
            mock_agent.daily_spent_usd = 0.0
            mock_agent.daily_budget_usd = 1.0
            mock_agent.workspace_dir = workspace_dir
            mock_agent.reset_daily_budget = MagicMock()
            mock_lac.return_value = mock_agent

            mock_client = MagicMock()
            mock_client.browse_tasks = AsyncMock(return_value=[])
            mock_client.list_tasks = AsyncMock(return_value=[])
            mock_client.publish_task = AsyncMock(return_value={"id": "t-1"})
            mock_client.close = AsyncMock()
            mock_emc_cls.return_value = mock_client

            results = await run_agent_daily(workspace_dir, data_dir, None, dry_run=True)
            # All phases should have run
            assert "browse" in results
            assert "review" in results
            assert "announce" in results
            assert "publish" in results
            assert "rate" in results
            assert "summary" in results


# ═══════════════════════════════════════════════════════════════════
# Multi-Agent Orchestration
# ═══════════════════════════════════════════════════════════════════


class TestRunAllAgents:
    """Tests for multi-agent daily routine orchestration."""

    @pytest.fixture
    def workspaces_dir(self, tmp_path):
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir()
        for name in ["kk-agent-1", "kk-agent-2", "kk-agent-3"]:
            (ws_dir / name).mkdir()
        return ws_dir

    @pytest.fixture
    def data_dir(self, tmp_path):
        dd = tmp_path / "data"
        dd.mkdir()
        (dd / "skills").mkdir()
        return dd

    @pytest.mark.asyncio
    async def test_runs_all_agents(self, workspaces_dir, data_dir):
        """Should run daily routine for all discovered agents."""
        with patch("cron.daily_routine.run_agent_daily", new_callable=AsyncMock) as mock_rad:
            mock_rad.return_value = {"browse": {"applied": 0}}
            await run_all_agents(
                workspaces_dir, data_dir, "browse", None, None, dry_run=True,
            )
            assert mock_rad.call_count == 3

    @pytest.mark.asyncio
    async def test_single_agent_filter(self, workspaces_dir, data_dir):
        """Should filter to single agent when agent_name specified."""
        with patch("cron.daily_routine.run_agent_daily", new_callable=AsyncMock) as mock_rad:
            mock_rad.return_value = {"browse": {"applied": 0}}
            await run_all_agents(
                workspaces_dir, data_dir, "browse", "kk-agent-2", None, dry_run=True,
            )
            assert mock_rad.call_count == 1

    @pytest.mark.asyncio
    async def test_max_agents_limit(self, workspaces_dir, data_dir):
        """Should respect max_agents limit."""
        with patch("cron.daily_routine.run_agent_daily", new_callable=AsyncMock) as mock_rad:
            mock_rad.return_value = {"browse": {"applied": 0}}
            await run_all_agents(
                workspaces_dir, data_dir, "browse", None, 2, dry_run=True,
            )
            assert mock_rad.call_count == 2

    @pytest.mark.asyncio
    async def test_manifest_based_discovery(self, workspaces_dir, data_dir):
        """Should use _manifest.json for community agent discovery."""
        manifest = workspaces_dir / "_manifest.json"
        manifest.write_text(json.dumps({
            "workspaces": [
                {"name": "kk-agent-1", "type": "community"},
                {"name": "kk-agent-3", "type": "community"},
            ],
        }), encoding="utf-8")

        with patch("cron.daily_routine.run_agent_daily", new_callable=AsyncMock) as mock_rad:
            mock_rad.return_value = {"browse": {"applied": 0}}
            await run_all_agents(
                workspaces_dir, data_dir, "browse", None, None, dry_run=True,
            )
            assert mock_rad.call_count == 2
