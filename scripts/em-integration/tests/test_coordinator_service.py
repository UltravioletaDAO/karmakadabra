"""
Tests for coordinator_service.py
=================================

Comprehensive coverage of the KK V2 Coordinator — the brain that matches
tasks to agents using 6-factor enhanced matching (skill, reliability,
category, chain, budget, reputation).

Coverage targets:
- load_agent_skills: skill extraction from profiles + SOUL.md
- compute_skill_match: legacy skill-keyword matching
- load_performance_profiles: merging JSON + notes performance data
- coordination_cycle: full matching pipeline (with mocked I/O)
- Edge cases: empty workspaces, no tasks, no idle agents, stale agents
"""

import asyncio
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.coordinator_service import (
    load_agent_skills,
    compute_skill_match,
    load_performance_profiles,
    coordination_cycle,
)
from lib.performance_tracker import AgentPerformance


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_workspaces():
    """Create a temp workspaces directory with agent data."""
    d = tempfile.mkdtemp(prefix="test_coordinator_")
    ws = Path(d)

    # Agent 1: photographer with profile.json
    agent1_dir = ws / "kk-photographer" / "data"
    agent1_dir.mkdir(parents=True)
    (agent1_dir / "profile.json").write_text(json.dumps({
        "top_skills": [
            {"skill": "Photography", "category": "field_work"},
            {"skill": "Verification", "category": "quality"},
            {"skill": "GPS Navigation", "category": "logistics"},
        ]
    }))

    # Agent 2: data specialist with SOUL.md
    agent2_dir = ws / "kk-data-analyst"
    agent2_dir.mkdir(parents=True)
    (agent2_dir / "SOUL.md").write_text("""# KK Data Analyst

## Skills
- **research** (Data Collection)
- **data_entry** (Data Processing)
- **attention_to_detail** (Quality)

## Personality
Meticulous and thorough.
""")

    # Agent 3: empty workspace
    agent3_dir = ws / "kk-empty"
    agent3_dir.mkdir(parents=True)

    yield ws
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# load_agent_skills tests
# ---------------------------------------------------------------------------

class TestLoadAgentSkills:
    """Tests for skill extraction from agent workspaces."""

    def test_from_profile_json(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "kk-photographer")
        assert "photography" in skills
        assert "verification" in skills
        assert "gps navigation" in skills

    def test_from_soul_md(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "kk-data-analyst")
        assert "research" in skills
        assert "data_entry" in skills
        assert "attention_to_detail" in skills

    def test_empty_workspace(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "kk-empty")
        assert skills == set()

    def test_nonexistent_agent(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "kk-nonexistent")
        assert skills == set()

    def test_kk_prefix_fallback(self, tmp_workspaces):
        """When searching for 'photographer', tries 'kk-photographer' too."""
        skills = load_agent_skills(tmp_workspaces, "photographer")
        assert "photography" in skills

    def test_profile_json_preferred_over_soul(self, tmp_workspaces):
        """Profile JSON takes precedence when both exist."""
        # Add SOUL.md to photographer workspace
        agent_dir = tmp_workspaces / "kk-photographer"
        (agent_dir / "SOUL.md").write_text("""# Skills
## Skills
- **different_skill** (Other)
""")
        # Should still use profile.json
        skills = load_agent_skills(tmp_workspaces, "kk-photographer")
        assert "photography" in skills  # From profile.json

    def test_malformed_profile_json(self, tmp_workspaces):
        """Malformed JSON should fallback to SOUL.md if available."""
        agent_dir = tmp_workspaces / "kk-malformed" / "data"
        agent_dir.mkdir(parents=True)
        (agent_dir / "profile.json").write_text("not valid json {{{")

        # Add SOUL.md fallback
        ws_dir = tmp_workspaces / "kk-malformed"
        (ws_dir / "SOUL.md").write_text("""# Agent
## Skills
- **fallback_skill** (Type)
""")
        skills = load_agent_skills(tmp_workspaces, "kk-malformed")
        assert "fallback_skill" in skills

    def test_soul_md_skills_section_parsing(self, tmp_workspaces):
        """Skills section ends at next ## heading."""
        agent_dir = tmp_workspaces / "kk-section-test"
        agent_dir.mkdir(parents=True)
        (agent_dir / "SOUL.md").write_text("""# Agent

## Skills
- **real_skill** (Category)
- **another_skill** (Category)

## Personality
Not a skill section.
- **fake_skill** (NotASkill)
""")
        skills = load_agent_skills(tmp_workspaces, "kk-section-test")
        assert "real_skill" in skills
        assert "another_skill" in skills
        assert "fake_skill" not in skills


# ---------------------------------------------------------------------------
# compute_skill_match tests
# ---------------------------------------------------------------------------

class TestComputeSkillMatch:
    """Tests for legacy skill-keyword matching."""

    def test_perfect_match(self):
        skills = {"photography", "verification", "gps"}
        score = compute_skill_match(skills, "Photo verification with GPS", "Take geotagged photos")
        assert score > 0.5

    def test_no_match(self):
        skills = {"cooking", "baking", "recipes"}
        score = compute_skill_match(skills, "Write Python code", "Build an API endpoint")
        assert score == 0.0

    def test_partial_match(self):
        skills = {"photography", "writing", "cooking"}
        score = compute_skill_match(skills, "Photography assignment", "Take photos of food")
        assert 0 < score < 1.0

    def test_kk_tagged_task(self):
        """[KK] tasks should give a base score even without skill match."""
        skills = {"cooking"}
        score = compute_skill_match(skills, "[KK] Generic task", "Do something")
        assert score == 0.3  # KK base score

    def test_empty_skills(self):
        score = compute_skill_match(set(), "Any task", "Any description")
        assert score == 0.1  # Minimal score for unknown agents

    def test_case_insensitive(self):
        skills = {"photography"}
        score = compute_skill_match(skills, "PHOTOGRAPHY Task", "Take PHOTOS")
        assert score > 0

    def test_score_scales_with_matches(self):
        skills = {"a", "b", "c", "d", "e"}
        score1 = compute_skill_match(skills, "a only", "just a")
        score3 = compute_skill_match(skills, "a and b and c", "task needs a b c")
        assert score3 > score1

    def test_score_capped_at_one(self):
        skills = {"a"}
        score = compute_skill_match(skills, "a a a a a a a", "a a a a a")
        assert score <= 1.0


# ---------------------------------------------------------------------------
# load_performance_profiles tests
# ---------------------------------------------------------------------------

class TestLoadPerformanceProfiles:
    """Tests for performance profile merging."""

    def test_empty_workspaces(self, tmp_workspaces):
        profiles = load_performance_profiles(tmp_workspaces)
        # May return empty or profiles with zero tasks
        assert isinstance(profiles, dict)

    def test_returns_agent_performance_objects(self, tmp_workspaces):
        # Create performance JSON file
        perf_dir = tmp_workspaces / "kk-photographer" / "data"
        perf_dir.mkdir(parents=True, exist_ok=True)
        (perf_dir / "performance.json").write_text(json.dumps({
            "agent_name": "kk-photographer",
            "tasks_attempted": 10,
            "tasks_completed": 9,
            "total_earned_usd": 4.50,
            "categories": {"physical_verification": 5, "data_collection": 3, "survey": 1},
            "chains": {"base": 7, "polygon": 2},
            "ratings": [4.5, 4.0, 5.0, 4.5, 4.0, 4.5, 3.5, 4.0, 4.5],
        }))
        profiles = load_performance_profiles(tmp_workspaces)
        assert isinstance(profiles, dict)


# ---------------------------------------------------------------------------
# coordination_cycle tests (with mocked I/O)
# ---------------------------------------------------------------------------

class TestCoordinationCycle:
    """Tests for the full coordination cycle."""

    @pytest.mark.asyncio
    async def test_dry_run_no_assignments(self, tmp_workspaces):
        """Dry run should preview but not execute assignments."""
        mock_client = AsyncMock()
        mock_client.browse_tasks = AsyncMock(return_value=[])
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 0, "by_status": {}, "stale_agents": 0,
                 "active_claims": 0, "total_daily_spent_usd": 0.0
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=True)

        assert result["assignments"] == []
        assert "summary" in result
        assert result["matching_mode"] == "enhanced"

    @pytest.mark.asyncio
    async def test_with_idle_agents_and_tasks(self, tmp_workspaces):
        """When there are idle agents and tasks, assignments should happen."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task_1",
                "title": "Verify storefront",
                "description": "Take a geotagged photo",
                "instructions": "Go to location and verify",
                "bounty_usd": 0.50,
                "category": "physical_verification",
                "payment_network": "base",
                "agent_wallet": "0xOther",
            }
        ])

        idle_agents = [
            {"agent_name": "kk-photographer", "status": "idle"},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=idle_agents), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.claim_task", new_callable=AsyncMock, return_value=True), \
             patch("services.coordinator_service.send_notification", new_callable=AsyncMock, return_value=True), \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 1, "by_status": {"idle": 1}, "stale_agents": 0,
                 "active_claims": 1, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=False)

        # Should attempt to assign
        assert result["matching_mode"] == "enhanced"

    @pytest.mark.asyncio
    async def test_dry_run_with_tasks(self, tmp_workspaces):
        """Dry run should preview assignments without claiming."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task_1",
                "title": "Collect data",
                "instructions": "Research and collect market data",
                "bounty_usd": 0.30,
                "category": "data_collection",
                "payment_network": "base",
                "agent_wallet": "0xOther",
            }
        ])

        idle_agents = [
            {"agent_name": "kk-data-analyst", "status": "idle"},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=idle_agents), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.claim_task", new_callable=AsyncMock) as mock_claim, \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 1, "by_status": {"idle": 1}, "stale_agents": 0,
                 "active_claims": 0, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=True)

        # Claim should NOT be called in dry run
        mock_claim.assert_not_called()
        # But assignments should still be returned as preview
        for a in result["assignments"]:
            assert a.get("dry_run") is True

    @pytest.mark.asyncio
    async def test_legacy_mode(self, tmp_workspaces):
        """Legacy mode should use simple skill-keyword matching."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task_1",
                "title": "Photography verification",
                "instructions": "Take photos with GPS",
                "bounty_usd": 0.50,
                "category": "physical_verification",
                "payment_network": "base",
                "agent_wallet": "0xOther",
            }
        ])

        idle_agents = [
            {"agent_name": "kk-photographer", "status": "idle"},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=idle_agents), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.claim_task", new_callable=AsyncMock, return_value=True), \
             patch("services.coordinator_service.send_notification", new_callable=AsyncMock, return_value=True), \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 1, "by_status": {"idle": 1}, "stale_agents": 0,
                 "active_claims": 1, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(
                tmp_workspaces, mock_client, dry_run=False, use_legacy_matching=True
            )

        assert result["matching_mode"] == "legacy"
        assert result["performance_profiles_loaded"] == 0

    @pytest.mark.asyncio
    async def test_skips_own_tasks(self, tmp_workspaces):
        """Coordinator should not assign its own tasks."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task_own",
                "title": "Self task",
                "instructions": "This is from the coordinator",
                "bounty_usd": 0.50,
                "category": "survey",
                "payment_network": "base",
                "agent_wallet": "0xCoordinator",  # Same as coordinator!
            }
        ])

        idle_agents = [
            {"agent_name": "kk-photographer", "status": "idle"},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=idle_agents), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.claim_task", new_callable=AsyncMock) as mock_claim, \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 1, "by_status": {"idle": 1}, "stale_agents": 0,
                 "active_claims": 0, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=False)

        mock_claim.assert_not_called()
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_skips_system_agents(self, tmp_workspaces):
        """System agents (coordinator, validator) should not be assigned tasks."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task_1",
                "title": "Some task",
                "instructions": "Do something",
                "bounty_usd": 0.50,
                "category": "survey",
                "payment_network": "base",
                "agent_wallet": "0xOther",
            }
        ])

        # Only system agents are idle
        idle_agents = [
            {"agent_name": "kk-coordinator", "status": "idle"},
            {"agent_name": "kk-validator", "status": "idle"},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=idle_agents), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.claim_task", new_callable=AsyncMock) as mock_claim, \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 2, "by_status": {"idle": 2}, "stale_agents": 0,
                 "active_claims": 0, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=False)

        mock_claim.assert_not_called()
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_handles_browse_failure(self, tmp_workspaces):
        """Should handle EM API failures gracefully."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(side_effect=ConnectionError("EM API down"))

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 0, "by_status": {}, "stale_agents": 0,
                 "active_claims": 0, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=False)

        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_stale_agents_reported(self, tmp_workspaces):
        """Stale agents should appear in the result."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[])

        stale = [
            {"agent_name": "kk-ghost", "status": "idle", "minutes_stale": 45.0},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=stale), \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 1, "by_status": {"idle": 1}, "stale_agents": 1,
                 "active_claims": 0, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=False)

        assert "kk-ghost" in result["stale_agents"]

    @pytest.mark.asyncio
    async def test_already_claimed_task(self, tmp_workspaces):
        """If task is already claimed, should skip gracefully."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task_claimed",
                "title": "Already taken task",
                "instructions": "Someone got here first",
                "bounty_usd": 0.50,
                "category": "physical_verification",
                "payment_network": "base",
                "agent_wallet": "0xOther",
            }
        ])

        idle_agents = [
            {"agent_name": "kk-photographer", "status": "idle"},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=idle_agents), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.claim_task", new_callable=AsyncMock, return_value=False), \
             patch("services.coordinator_service.send_notification", new_callable=AsyncMock) as mock_notify, \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 1, "by_status": {"idle": 1}, "stale_agents": 0,
                 "active_claims": 0, "total_daily_spent_usd": 0.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=False)

        # Should not notify if claim failed
        mock_notify.assert_not_called()
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_no_idle_agents(self, tmp_workspaces):
        """No idle agents means no assignments."""
        mock_client = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.wallet_address = "0xCoordinator"
        mock_client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task_1",
                "title": "Waiting task",
                "instructions": "Nobody to do this",
                "bounty_usd": 0.50,
                "category": "survey",
                "payment_network": "base",
                "agent_wallet": "0xOther",
            }
        ])

        # All agents busy
        all_agents = [
            {"agent_name": "kk-photographer", "status": "working"},
            {"agent_name": "kk-data-analyst", "status": "working"},
        ]

        with patch("services.coordinator_service.get_agent_states", new_callable=AsyncMock, return_value=all_agents), \
             patch("services.coordinator_service.get_stale_agents", new_callable=AsyncMock, return_value=[]), \
             patch("services.coordinator_service.get_swarm_summary", new_callable=AsyncMock, return_value={
                 "total_agents": 2, "by_status": {"working": 2}, "stale_agents": 0,
                 "active_claims": 2, "total_daily_spent_usd": 1.0,
             }):
            result = await coordination_cycle(tmp_workspaces, mock_client, dry_run=False)

        assert result["assignments"] == []
