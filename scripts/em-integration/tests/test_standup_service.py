"""
Karma Kadabra V2 — Phase 11: Tests for Standup Service

Tests the daily standup report generator with mocked swarm state
and workspace data. Verifies all output formats and edge cases.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent paths for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.standup_service import (
    categorize_agents,
    compute_budget_summary,
    format_irc,
    format_markdown,
    format_stdout,
    generate_standup,
    read_workspace_notes,
    read_workspace_states,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_workspaces(tmp_path: Path) -> Path:
    """Create a temporary workspaces directory with sample data."""
    ws_dir = tmp_path / "workspaces"
    ws_dir.mkdir()

    # Agent 1: has completed task in daily notes
    agent1 = ws_dir / "kk-agent-alpha"
    agent1.mkdir()
    notes_dir = agent1 / "memory" / "notes"
    notes_dir.mkdir(parents=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (notes_dir / f"{today}.md").write_text(
        f"# Daily Activity -- {today}\n\n"
        "- `10:00:00` completed task for kk-agent-beta -> approved\n"
        "- `10:15:00` browse -> no matching tasks found\n",
        encoding="utf-8",
    )
    # WORKING.md for agent1
    working_dir = agent1 / "memory"
    (working_dir / "WORKING.md").write_text(
        "# Current State\n\n## Active Task\n- Status: idle\n\n"
        "## Pending\n- (none)\n\n"
        "## Budget\n- Daily spent: $0.10 / $2.00\n"
        "- Active escrows: 0 ($0.00)\n\n"
        "## Last Heartbeat\n- Time: 2026-02-19T10:15:00+00:00\n"
        "- Action: browse\n- Result: no matching tasks found\n",
        encoding="utf-8",
    )

    # Agent 2: has active task
    agent2 = ws_dir / "kk-agent-beta"
    agent2.mkdir()
    notes_dir2 = agent2 / "memory" / "notes"
    notes_dir2.mkdir(parents=True)
    (notes_dir2 / f"{today}.md").write_text(
        f"# Daily Activity -- {today}\n\n"
        "- `09:00:00` applied to task -> waiting for assignment\n",
        encoding="utf-8",
    )
    working_dir2 = agent2 / "memory"
    (working_dir2 / "WORKING.md").write_text(
        "# Current State\n\n## Active Task\n"
        "- Task ID: abc-123\n- Title: Test task\n"
        "- Status: working\n- Started: 2026-02-19T09:00:00+00:00\n"
        "- Next step: Submit evidence\n\n"
        "## Pending\n- (none)\n\n"
        "## Budget\n- Daily spent: $0.05 / $2.00\n"
        "- Active escrows: 1 ($0.10)\n\n"
        "## Last Heartbeat\n- Time: 2026-02-19T09:30:00+00:00\n"
        "- Action: resume:working\n- Result: ready for submission\n",
        encoding="utf-8",
    )

    # Agent 3: empty workspace (no notes, no working)
    agent3 = ws_dir / "kk-agent-gamma"
    agent3.mkdir()

    return ws_dir


@pytest.fixture
def sample_swarm_agents() -> list[dict]:
    return [
        {
            "agent_name": "kk-agent-alpha",
            "status": "idle",
            "task_id": "",
            "last_heartbeat": "2026-02-19T10:15:00+00:00",
            "daily_spent_usd": 0.10,
            "notes": "",
        },
        {
            "agent_name": "kk-agent-beta",
            "status": "busy",
            "task_id": "abc-123",
            "last_heartbeat": "2026-02-19T09:30:00+00:00",
            "daily_spent_usd": 0.05,
            "notes": "",
        },
        {
            "agent_name": "kk-agent-gamma",
            "status": "idle",
            "task_id": "",
            "last_heartbeat": "2026-02-18T20:00:00+00:00",
            "daily_spent_usd": 0.0,
            "notes": "waiting for chat logs",
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadWorkspaceNotes:
    def test_reads_notes_for_today(self, tmp_workspaces: Path):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        notes = read_workspace_notes(tmp_workspaces, today)

        assert "kk-agent-alpha" in notes
        assert len(notes["kk-agent-alpha"]) == 2
        assert "completed" in notes["kk-agent-alpha"][0].lower()

    def test_returns_empty_for_nonexistent_date(self, tmp_workspaces: Path):
        notes = read_workspace_notes(tmp_workspaces, "2020-01-01")
        assert len(notes) == 0

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path):
        notes = read_workspace_notes(tmp_path / "nonexistent", "2026-02-19")
        assert len(notes) == 0


class TestReadWorkspaceStates:
    def test_reads_states_from_workspaces(self, tmp_workspaces: Path):
        states = read_workspace_states(tmp_workspaces)

        assert "kk-agent-alpha" in states
        assert "kk-agent-beta" in states
        # gamma has no WORKING.md
        assert "kk-agent-gamma" not in states

    def test_active_task_detected(self, tmp_workspaces: Path):
        states = read_workspace_states(tmp_workspaces)
        beta = states["kk-agent-beta"]

        assert beta.has_active_task
        assert beta.active_task.task_id == "abc-123"
        assert beta.active_task.status == "working"


class TestCategorizeAgents:
    def test_categorizes_correctly(
        self, tmp_workspaces: Path, sample_swarm_agents: list[dict]
    ):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        notes = read_workspace_notes(tmp_workspaces, today)
        states = read_workspace_states(tmp_workspaces)

        stale = [
            {
                "agent_name": "kk-agent-gamma",
                "minutes_stale": 900.0,
            }
        ]

        cats = categorize_agents(sample_swarm_agents, notes, states, stale)

        assert "completed" in cats
        assert "in_progress" in cats
        assert "blocked" in cats
        assert "idle" in cats
        assert "offline" in cats

        # gamma is stale -> offline
        offline_names = [a["name"] for a in cats["offline"]]
        assert "kk-agent-gamma" in offline_names

    def test_empty_swarm_produces_valid_categories(self):
        cats = categorize_agents([], {}, {}, [])
        assert cats["completed"] == []
        assert cats["in_progress"] == []
        assert cats["blocked"] == []
        assert cats["idle"] == []
        assert cats["offline"] == []


class TestBudgetSummary:
    def test_sums_correctly(self, sample_swarm_agents: list[dict]):
        budget = compute_budget_summary(sample_swarm_agents)

        assert budget["total_spent"] == 0.15
        assert budget["daily_budget"] == 78.0
        assert budget["remaining"] == 77.85

    def test_empty_agents(self):
        budget = compute_budget_summary([])
        assert budget["total_spent"] == 0.0
        assert budget["remaining"] == 78.0


class TestFormatStdout:
    def test_includes_all_sections(self):
        report = {
            "date": "2026-02-19",
            "categories": {
                "completed": [{"name": "kk-a", "task_id": "abc-12345678", "notes": "done"}],
                "in_progress": [{"name": "kk-b", "status": "busy", "notes": "working"}],
                "blocked": [],
                "idle": [],
                "offline": [],
            },
            "budget": {"total_spent": 1.50, "daily_budget": 78.0, "remaining": 76.50},
            "health": {
                "total_agents": 5,
                "active_agents": 4,
                "offline_agents": ["kk-offline-1"],
                "em_api": "OK",
            },
            "workspace_notes": {},
        }

        output = format_stdout(report)
        assert "DAILY STANDUP" in output
        assert "COMPLETED TODAY" in output
        assert "IN PROGRESS" in output
        assert "BLOCKED" in output
        assert "BUDGET SUMMARY" in output
        assert "HEALTH" in output
        assert "$1.50" in output

    def test_empty_report(self):
        report = {
            "date": "2026-02-19",
            "categories": {
                "completed": [],
                "in_progress": [],
                "blocked": [],
                "idle": [],
                "offline": [],
            },
            "budget": {"total_spent": 0.0, "daily_budget": 78.0, "remaining": 78.0},
            "health": {
                "total_agents": 0,
                "active_agents": 0,
                "offline_agents": [],
                "em_api": "OK",
            },
            "workspace_notes": {},
        }

        output = format_stdout(report)
        assert "DAILY STANDUP" in output
        assert "(none)" in output


class TestFormatIrc:
    def test_irc_format_under_500_chars(self):
        report = {
            "date": "2026-02-19",
            "categories": {
                "completed": [{"name": "a"}] * 12,
                "in_progress": [{"name": "b"}] * 4,
                "blocked": [{"name": "c"}],
                "idle": [],
                "offline": [],
            },
            "budget": {"total_spent": 2.40, "daily_budget": 78.0, "remaining": 75.60},
            "health": {
                "total_agents": 39,
                "active_agents": 37,
                "offline_agents": ["kk-user31", "kk-user34"],
                "em_api": "OK",
            },
        }

        output = format_irc(report)
        assert len(output) <= 500
        assert "[KK STANDUP" in output
        assert "Done: 12" in output
        assert "WIP: 4" in output
        assert "Blocked: 1" in output

    def test_irc_empty_report(self):
        report = {
            "date": "2026-02-19",
            "categories": {
                "completed": [],
                "in_progress": [],
                "blocked": [],
                "idle": [],
                "offline": [],
            },
            "budget": {"total_spent": 0.0, "daily_budget": 78.0, "remaining": 78.0},
            "health": {
                "total_agents": 0,
                "active_agents": 0,
                "offline_agents": [],
                "em_api": "OK",
            },
        }

        output = format_irc(report)
        assert len(output) <= 500
        assert "Done: 0" in output


class TestFormatMarkdown:
    def test_markdown_has_headers(self):
        report = {
            "date": "2026-02-19",
            "categories": {
                "completed": [],
                "in_progress": [],
                "blocked": [],
                "idle": [],
                "offline": [],
            },
            "budget": {"total_spent": 0.0, "daily_budget": 78.0, "remaining": 78.0},
            "health": {
                "total_agents": 0,
                "active_agents": 0,
                "offline_agents": [],
                "em_api": "OK",
            },
            "workspace_notes": {},
        }

        output = format_markdown(report)
        assert "# Daily Standup" in output
        assert "## Completed Today" in output
        assert "## In Progress" in output
        assert "## Blocked" in output
        assert "## Budget Summary" in output
        assert "## Health" in output


class TestGenerateStandup:
    @pytest.mark.asyncio
    async def test_dry_run_produces_valid_report(self, tmp_workspaces: Path):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = await generate_standup(tmp_workspaces, today, dry_run=True)

        assert report["date"] == today
        assert "categories" in report
        assert "budget" in report
        assert "health" in report

    @pytest.mark.asyncio
    async def test_date_filtering_works(self, tmp_workspaces: Path):
        # Use a date with no data
        report = await generate_standup(tmp_workspaces, "2020-01-01", dry_run=True)

        assert report["date"] == "2020-01-01"
        # No workspace notes for 2020
        assert len(report["workspace_notes"]) == 0

    @pytest.mark.asyncio
    async def test_nonexistent_workspace_produces_empty(self, tmp_path: Path):
        fake_dir = tmp_path / "nonexistent"
        report = await generate_standup(fake_dir, "2026-02-19", dry_run=True)

        assert report["categories"]["completed"] == []
        assert report["categories"]["in_progress"] == []
        assert report["budget"]["total_spent"] == 0.0


class TestStaleAgentDetection:
    def test_stale_agents_marked_offline(self):
        agents = [
            {
                "agent_name": "kk-stale-1",
                "status": "idle",
                "task_id": "",
                "daily_spent_usd": 0,
                "notes": "",
            },
        ]
        stale = [{"agent_name": "kk-stale-1", "minutes_stale": 60.0}]

        cats = categorize_agents(agents, {}, {}, stale)
        assert len(cats["offline"]) == 1
        assert cats["offline"][0]["name"] == "kk-stale-1"
