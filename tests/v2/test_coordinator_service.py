"""
Tests for coordinator_service.py — Swarm Brain

Covers:
  - Skill loading from workspace files (profile.json, SOUL.md)
  - Skill matching (legacy keyword mode)
  - Performance profile loading (JSON + notes merge)
  - Coordination cycle: legacy, enhanced, autojob modes
  - CoordinatorService class interface
  - load_coordinator_config from env vars
  - AutoJob bridge integration and fallback handling
  - Edge cases: no idle agents, no tasks, stale agents, system agent filtering
  - Dry run mode
  - Task description edge cases (None, empty)
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.coordinator_service import (
    CoordinatorService,
    compute_skill_match,
    coordination_cycle,
    load_agent_skills,
    load_coordinator_config,
    load_performance_profiles,
    _autojob_rank_to_coordinator,
    _build_autojob_bridge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_workspaces(tmp_path):
    """Create a temporary workspaces directory with agent data."""
    ws = tmp_path / "workspaces"
    ws.mkdir()

    # Agent with profile.json
    agent1 = ws / "kk-alpha"
    agent1.mkdir()
    (agent1 / "data").mkdir()
    (agent1 / "data" / "profile.json").write_text(json.dumps({
        "top_skills": [
            {"skill": "Photography", "confidence": 0.9},
            {"skill": "Data Analysis", "confidence": 0.8},
            {"skill": "Web3", "confidence": 0.7},
        ]
    }))

    # Agent with SOUL.md skills section
    agent2 = ws / "kk-beta"
    agent2.mkdir()
    (agent2 / "SOUL.md").write_text(
        "# Beta Agent\n\n"
        "## Skills\n"
        "- **Research** (Academic)\n"
        "- **Writing** (Content)\n"
        "- **NLP** (Technical)\n\n"
        "## Personality\n"
        "Friendly and helpful.\n"
    )

    # Agent with no skills data
    agent3 = ws / "kk-gamma"
    agent3.mkdir()

    return ws


@pytest.fixture
def mock_em_client():
    """Create a mock EMClient."""
    client = MagicMock()
    client.agent = MagicMock()
    client.agent.wallet_address = "0xCOORDINATOR"
    client.agent.name = "kk-coordinator"
    client.close = AsyncMock()
    client.browse_tasks = AsyncMock(return_value=[])
    return client


@pytest.fixture
def sample_tasks():
    """Sample EM tasks for matching tests."""
    return [
        {
            "id": "task-001", "title": "Take photos of local restaurant",
            "instructions": "Visit the restaurant and take 5 photos",
            "bounty_usd": 0.10, "category": "physical_verification",
            "payment_network": "base", "agent_wallet": "0xOTHER",
        },
        {
            "id": "task-002", "title": "Research DeFi yield opportunities",
            "instructions": "Find top 5 yield farming protocols on Base",
            "bounty_usd": 0.05, "category": "entrepreneur_research",
            "payment_network": "base", "agent_wallet": "0xOTHER",
        },
        {
            "id": "task-003", "title": "[KK Request] Raw chat data analysis",
            "instructions": "Analyze chat data for skill extraction patterns",
            "bounty_usd": 0.03, "category": "data_analysis",
            "payment_network": "base", "agent_wallet": "0xOTHER",
        },
    ]


def _patch_swarm(**overrides):
    """Create a context-manager that patches all swarm_state functions.

    Returns dict of mocks for inspection.
    """
    defaults = {
        "states": AsyncMock(return_value=[
            {"agent_name": "alpha", "status": "idle"},
            {"agent_name": "beta", "status": "idle"},
            {"agent_name": "kk-coordinator", "status": "idle"},
        ]),
        "stale": AsyncMock(return_value=[]),
        "summary": AsyncMock(return_value={
            "total_agents": 3, "idle_agents": 2, "total_published_tasks": 0,
        }),
        "claim": AsyncMock(return_value=True),
        "notify": AsyncMock(return_value=None),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Skill Loading Tests
# ---------------------------------------------------------------------------


class TestLoadAgentSkills:
    def test_load_from_profile_json(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "alpha")
        assert "photography" in skills
        assert "data analysis" in skills
        assert "web3" in skills

    def test_load_from_soul_md(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "beta")
        assert "research" in skills
        assert "writing" in skills
        assert "nlp" in skills

    def test_load_no_skills_data(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "gamma")
        assert skills == set()

    def test_load_nonexistent_agent(self, tmp_workspaces):
        skills = load_agent_skills(tmp_workspaces, "nonexistent")
        assert skills == set()

    def test_profile_json_takes_precedence(self, tmp_workspaces):
        agent = tmp_workspaces / "kk-dual"
        agent.mkdir()
        (agent / "data").mkdir()
        (agent / "data" / "profile.json").write_text(json.dumps({
            "top_skills": [{"skill": "Blockchain", "confidence": 0.9}]
        }))
        (agent / "SOUL.md").write_text("## Skills\n- **Cooking** (Culinary)\n")
        skills = load_agent_skills(tmp_workspaces, "dual")
        assert "blockchain" in skills
        assert "cooking" not in skills

    def test_corrupted_profile_json_fallback(self, tmp_workspaces):
        agent = tmp_workspaces / "kk-corrupt"
        agent.mkdir()
        (agent / "data").mkdir()
        (agent / "data" / "profile.json").write_text("NOT VALID JSON")
        (agent / "SOUL.md").write_text("## Skills\n- **Solidity** (Development)\n")
        skills = load_agent_skills(tmp_workspaces, "corrupt")
        assert "solidity" in skills

    def test_empty_profile_json(self, tmp_workspaces):
        agent = tmp_workspaces / "kk-empty"
        agent.mkdir()
        (agent / "data").mkdir()
        (agent / "data" / "profile.json").write_text(json.dumps({"top_skills": []}))
        skills = load_agent_skills(tmp_workspaces, "empty")
        assert skills == set()

    def test_soul_md_multiple_sections(self, tmp_workspaces):
        agent = tmp_workspaces / "kk-sections"
        agent.mkdir()
        (agent / "SOUL.md").write_text(
            "## About\nI am a test agent.\n\n"
            "## Skills\n- **Python** (Language)\n- **Docker** (DevOps)\n\n"
            "## Hobbies\n- **Gaming** (Fun)\n"
        )
        skills = load_agent_skills(tmp_workspaces, "sections")
        assert "python" in skills
        assert "docker" in skills
        assert "gaming" not in skills


# ---------------------------------------------------------------------------
# Skill Matching Tests (Legacy Mode)
# ---------------------------------------------------------------------------


class TestComputeSkillMatch:
    def test_exact_match(self):
        score = compute_skill_match({"photography", "verification"}, "Photo verification", "Verify photography")
        assert score > 0.0

    def test_no_match(self):
        score = compute_skill_match({"cooking", "gardening"}, "Smart contract audit", "Review Solidity code")
        assert score == 0.0

    def test_kk_tagged_task_gets_base_score(self):
        score = compute_skill_match({"cooking"}, "[KK Request] anything", "")
        assert score == 0.3

    def test_empty_skills_gives_minimal_score(self):
        score = compute_skill_match(set(), "Any task", "Any description")
        assert score == 0.1

    def test_multiple_matches(self):
        score = compute_skill_match({"data", "analysis", "research"}, "Data analysis research", "Comprehensive")
        assert score > 0.5

    def test_case_insensitive(self):
        score = compute_skill_match({"python"}, "Python Development", "Write Python scripts")
        assert score > 0.0

    def test_score_capped_at_one(self):
        score = compute_skill_match({"a", "b"}, "a b", "a b a b")
        assert score <= 1.0

    def test_partial_match(self):
        score_full = compute_skill_match({"photography", "data analysis", "web3"}, "photography data analysis web3", "")
        score_partial = compute_skill_match({"photography", "data analysis", "web3"}, "photography only", "")
        assert score_full >= score_partial


# ---------------------------------------------------------------------------
# Coordinator Config Tests
# ---------------------------------------------------------------------------


class TestLoadCoordinatorConfig:
    def test_defaults(self):
        config = load_coordinator_config()
        assert config["use_autojob"] is False
        assert config["dry_run"] is False
        assert config["use_legacy_matching"] is False
        assert config["autojob_path"] is None

    def test_dict_overrides(self):
        config = load_coordinator_config({"use_autojob": True, "dry_run": True})
        assert config["use_autojob"] is True
        assert config["dry_run"] is True

    def test_env_overrides(self):
        with patch.dict("os.environ", {"KK_USE_AUTOJOB": "true", "KK_DRY_RUN": "1"}):
            config = load_coordinator_config()
            assert config["use_autojob"] is True
            assert config["dry_run"] is True

    def test_env_false_values(self):
        with patch.dict("os.environ", {"KK_USE_AUTOJOB": "false"}):
            config = load_coordinator_config()
            assert config["use_autojob"] is False

    def test_env_path_override(self):
        with patch.dict("os.environ", {"KK_AUTOJOB_PATH": "/custom/path"}):
            config = load_coordinator_config()
            assert config["autojob_path"] == "/custom/path"

    def test_dict_overrides_env(self):
        with patch.dict("os.environ", {"KK_USE_AUTOJOB": "true"}):
            config = load_coordinator_config({"use_autojob": False})
            assert config["use_autojob"] is False


# ---------------------------------------------------------------------------
# AutoJob Rank Conversion Tests
# ---------------------------------------------------------------------------


class TestAutoJobRankToCoordinator:
    def test_basic_conversion(self):
        mock_result = MagicMock()
        r1 = MagicMock(); r1.agent_name = "alpha"; r1.final_score = 85.0
        r2 = MagicMock(); r2.agent_name = "beta"; r2.final_score = 60.0
        mock_result.rankings = [r1, r2]
        ranked = _autojob_rank_to_coordinator(mock_result, {"alpha", "beta"}, set(), set())
        assert len(ranked) == 2
        assert ranked[0] == ("alpha", 0.85)
        assert ranked[1] == ("beta", 0.60)

    def test_filters_system_agents(self):
        mock_result = MagicMock()
        r1 = MagicMock(); r1.agent_name = "kk-coordinator"; r1.final_score = 95.0
        mock_result.rankings = [r1]
        ranked = _autojob_rank_to_coordinator(mock_result, {"kk-coordinator"}, set(), {"kk-coordinator"})
        assert len(ranked) == 0

    def test_filters_assigned_agents(self):
        mock_result = MagicMock()
        r1 = MagicMock(); r1.agent_name = "alpha"; r1.final_score = 90.0
        mock_result.rankings = [r1]
        ranked = _autojob_rank_to_coordinator(mock_result, {"alpha"}, {"alpha"}, set())
        assert len(ranked) == 0

    def test_filters_non_idle_agents(self):
        mock_result = MagicMock()
        r1 = MagicMock(); r1.agent_name = "busy-agent"; r1.final_score = 90.0
        mock_result.rankings = [r1]
        ranked = _autojob_rank_to_coordinator(mock_result, {"alpha"}, set(), set())
        assert len(ranked) == 0

    def test_empty_rankings(self):
        mock_result = MagicMock()
        mock_result.rankings = []
        ranked = _autojob_rank_to_coordinator(mock_result, {"alpha"}, set(), set())
        assert len(ranked) == 0


# ---------------------------------------------------------------------------
# Coordination Cycle Tests (Legacy Mode)
# ---------------------------------------------------------------------------


class TestCoordinationCycleLegacy:
    @pytest.mark.asyncio
    async def test_legacy_no_tasks(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert result["assignments"] == []
        assert result["matching_mode"] == "legacy"

    @pytest.mark.asyncio
    async def test_legacy_dry_run(self, tmp_workspaces, mock_em_client, sample_tasks):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[sample_tasks[2]])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_agent_skills", return_value={"data", "analysis", "chat"}):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, dry_run=True, use_legacy_matching=True,
            )
        assignments = result["assignments"]
        if assignments:
            assert assignments[0]["dry_run"] is True
            assert assignments[0]["matching_mode"] == "legacy"

    @pytest.mark.asyncio
    async def test_legacy_skips_own_tasks(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        own_task = {
            "id": "own-001", "title": "My task", "instructions": "I created this",
            "bounty_usd": 0.10, "category": "test", "payment_network": "base",
            "agent_wallet": "0xCOORDINATOR",
        }
        mock_em_client.browse_tasks = AsyncMock(return_value=[own_task])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_legacy_filters_system_agents(self, tmp_workspaces, mock_em_client, sample_tasks):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[sample_tasks[0]])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_agent_skills", return_value={"photography", "verification"}):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        for a in result["assignments"]:
            assert a["agent"] not in ("kk-coordinator", "kk-validator")


# ---------------------------------------------------------------------------
# Coordination Cycle Tests (Enhanced Mode)
# ---------------------------------------------------------------------------


class TestCoordinationCycleEnhanced:
    @pytest.mark.asyncio
    async def test_enhanced_matching_mode(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_latest_snapshot", return_value=None), \
             patch("services.coordinator_service.save_performance", return_value=0):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=False,
            )
        assert result["matching_mode"] == "enhanced"
        assert result["performance_profiles_loaded"] >= 0

    @pytest.mark.asyncio
    async def test_enhanced_with_reputation_snapshot(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        rep_snap = {
            "alpha": {"composite_score": 85.0, "confidence": 0.8, "sources_available": ["on_chain"]},
            "beta": {"composite_score": 60.0, "confidence": 0.5, "sources_available": ["off_chain"]},
        }
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_latest_snapshot", return_value=rep_snap), \
             patch("services.coordinator_service.save_performance", return_value=0):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=False,
            )
        assert result["matching_mode"] == "enhanced"

    @pytest.mark.asyncio
    async def test_enhanced_saves_performance_on_live_run(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        save_perf = MagicMock(return_value=2)
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_latest_snapshot", return_value=None), \
             patch("services.coordinator_service.save_performance", save_perf):
            await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=False, dry_run=False,
            )
        save_perf.assert_called_once()

    @pytest.mark.asyncio
    async def test_enhanced_dry_run_skips_save(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        save_perf = MagicMock(return_value=0)
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_latest_snapshot", return_value=None), \
             patch("services.coordinator_service.save_performance", save_perf):
            await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=False, dry_run=True,
            )
        save_perf.assert_not_called()


# ---------------------------------------------------------------------------
# Stale Agent Handling
# ---------------------------------------------------------------------------


class TestStaleAgentHandling:
    @pytest.mark.asyncio
    async def test_stale_agents_reported(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[{"agent_name": "alpha", "status": "idle"}]),
            stale=AsyncMock(return_value=[
                {"agent_name": "stale-bob", "minutes_stale": 45},
                {"agent_name": "stale-charlie", "minutes_stale": 120},
            ]),
            summary=AsyncMock(return_value={"total_agents": 3}),
        )
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert "stale-bob" in result["stale_agents"]
        assert "stale-charlie" in result["stale_agents"]


# ---------------------------------------------------------------------------
# CoordinatorService Class Tests
# ---------------------------------------------------------------------------


class TestCoordinatorService:
    def test_init(self, tmp_workspaces, mock_em_client):
        svc = CoordinatorService(
            workspaces_dir=str(tmp_workspaces),
            em_client=mock_em_client,
            dry_run=True,
            max_assignments=10,
        )
        assert svc.dry_run is True
        assert svc.max_assignments == 10

    @pytest.mark.asyncio
    async def test_run_cycle_normalizes_output(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[]),
            summary=AsyncMock(return_value={
                "total_agents": 5, "idle_agents": 3, "total_published_tasks": 2,
            }),
        )
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_latest_snapshot", return_value=None), \
             patch("services.coordinator_service.save_performance", return_value=0):
            svc = CoordinatorService(
                workspaces_dir=str(tmp_workspaces), em_client=mock_em_client,
            )
            result = await svc.run_cycle()
        assert "tasks_found" in result
        assert "tasks_assigned" in result
        assert "agents_active" in result
        assert "agents_idle" in result
        assert "assignments" in result
        assert "matching_mode" in result
        assert result["agents_active"] == 5
        assert result["agents_idle"] == 3

    def test_autojob_mode_via_class(self, tmp_workspaces, mock_em_client):
        svc = CoordinatorService(
            workspaces_dir=str(tmp_workspaces), em_client=mock_em_client,
            use_autojob=True, autojob_path="/custom/path",
        )
        assert svc.use_autojob is True
        assert svc.autojob_path == "/custom/path"


# ---------------------------------------------------------------------------
# AutoJob Bridge Build Tests
# ---------------------------------------------------------------------------


class TestBuildAutoJobBridge:
    def test_no_wallets_file(self, tmp_path):
        with patch("services.coordinator_service.AutoJobBridge") as MockBridge:
            MockBridge.return_value.health.return_value = {"status": "healthy", "registered_workers": 0}
            bridge, wallet_map = _build_autojob_bridge(
                autojob_path=str(tmp_path), wallets_file=tmp_path / "nonexistent.json",
            )
        assert bridge is not None
        assert wallet_map == {}

    def test_with_wallets_file(self, tmp_path):
        wf = tmp_path / "wallets.json"
        wf.write_text(json.dumps({"wallets": [
            {"address": "0xAAA", "name": "alpha"},
            {"address": "0xBBB", "name": "beta"},
        ]}))
        with patch("services.coordinator_service.AutoJobBridge") as MockBridge:
            MockBridge.return_value.health.return_value = {"status": "healthy", "registered_workers": 2}
            bridge, wallet_map = _build_autojob_bridge(
                autojob_path=str(tmp_path), wallets_file=wf,
            )
        assert bridge is not None
        assert wallet_map["0xaaa"] == "alpha"
        assert wallet_map["0xbbb"] == "beta"

    def test_unhealthy_bridge_returns_none(self, tmp_path):
        with patch("services.coordinator_service.AutoJobBridge") as MockBridge:
            MockBridge.return_value.health.return_value = {"status": "unhealthy"}
            bridge, _ = _build_autojob_bridge(autojob_path=str(tmp_path))
        assert bridge is None

    def test_bridge_init_error_returns_none(self, tmp_path):
        with patch("services.coordinator_service.AutoJobBridge", side_effect=Exception("boom")):
            bridge, _ = _build_autojob_bridge(autojob_path=str(tmp_path))
        assert bridge is None

    def test_remote_mode_with_api_url(self, tmp_path):
        with patch("services.coordinator_service.AutoJobBridge") as MockBridge:
            MockBridge.return_value.health.return_value = {"status": "healthy", "registered_workers": 5}
            bridge, _ = _build_autojob_bridge(autojob_api="https://autojob.cc")
        call_kwargs = MockBridge.call_args.kwargs
        assert call_kwargs.get("mode") == "remote"


# ---------------------------------------------------------------------------
# Browse Tasks Error Handling
# ---------------------------------------------------------------------------


class TestBrowseTasksErrorHandling:
    @pytest.mark.asyncio
    async def test_browse_tasks_failure_continues(self, tmp_workspaces, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(side_effect=Exception("API timeout"))
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[{"agent_name": "alpha", "status": "idle"}]),
        )
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_claim_failure_skips_task(self, tmp_workspaces, mock_em_client, sample_tasks):
        mock_em_client.browse_tasks = AsyncMock(return_value=[sample_tasks[2]])
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[{"agent_name": "alpha", "status": "idle"}]),
            claim=AsyncMock(return_value=False),
        )
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_agent_skills", return_value={"data", "analysis"}):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert len(result["assignments"]) == 0


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_no_idle_agents(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[
                {"agent_name": "alpha", "status": "busy"},
                {"agent_name": "beta", "status": "busy"},
            ]),
            summary=AsyncMock(return_value={"total_agents": 2}),
        )
        mock_em_client.browse_tasks = AsyncMock(return_value=[{
            "id": "t1", "title": "test", "instructions": "do it",
            "bounty_usd": 1, "category": "test", "payment_network": "base",
            "agent_wallet": "0xOTHER",
        }])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_only_system_agents_idle(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[
                {"agent_name": "kk-coordinator", "status": "idle"},
                {"agent_name": "kk-validator", "status": "idle"},
            ]),
            summary=AsyncMock(return_value={"total_agents": 2}),
        )
        mock_em_client.browse_tasks = AsyncMock(return_value=[{
            "id": "t1", "title": "test", "instructions": "do it",
            "bounty_usd": 1, "category": "test", "payment_network": "base",
            "agent_wallet": "0xOTHER",
        }])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_multiple_tasks_assigns_different_agents(self, tmp_workspaces, mock_em_client):
        tasks = [
            {"id": f"t{i}", "title": f"[KK Request] task {i}", "instructions": f"task {i}",
             "bounty_usd": 0.01, "category": "test", "payment_network": "base",
             "agent_wallet": "0xOTHER"}
            for i in range(3)
        ]
        mock_em_client.browse_tasks = AsyncMock(return_value=tasks)
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[
                {"agent_name": "alpha", "status": "idle"},
                {"agent_name": "beta", "status": "idle"},
                {"agent_name": "gamma", "status": "idle"},
            ]),
            summary=AsyncMock(return_value={"total_agents": 3}),
        )
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_agent_skills", return_value={"task"}):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        agents = [a["agent"] for a in result["assignments"]]
        assert len(agents) == len(set(agents)), f"Duplicate assignments: {agents}"


# ---------------------------------------------------------------------------
# Performance Profile Loading Tests
# ---------------------------------------------------------------------------


class TestLoadPerformanceProfiles:
    def test_empty_workspaces(self, tmp_path):
        ws = tmp_path / "workspaces"
        ws.mkdir()
        with patch("services.coordinator_service.extract_performance_from_json", return_value={}), \
             patch("services.coordinator_service.extract_performance_from_notes", return_value={}):
            profiles = load_performance_profiles(ws)
        assert profiles == {}

    def test_json_takes_precedence_over_notes(self, tmp_path):
        ws = tmp_path / "workspaces"
        ws.mkdir()
        mj = MagicMock(); mj.tasks_attempted = 10; mj.agent_name = "alpha"
        mn = MagicMock(); mn.tasks_attempted = 3; mn.agent_name = "alpha"
        with patch("services.coordinator_service.extract_performance_from_json", return_value={"alpha": mj}), \
             patch("services.coordinator_service.extract_performance_from_notes", return_value={"alpha": mn}):
            profiles = load_performance_profiles(ws)
        assert profiles["alpha"] == mj

    def test_notes_fill_gaps(self, tmp_path):
        ws = tmp_path / "workspaces"
        ws.mkdir()
        mn = MagicMock(); mn.tasks_attempted = 5; mn.agent_name = "beta"
        with patch("services.coordinator_service.extract_performance_from_json", return_value={}), \
             patch("services.coordinator_service.extract_performance_from_notes", return_value={"beta": mn}):
            profiles = load_performance_profiles(ws)
        assert profiles["beta"] == mn

    def test_merge_both_sources(self, tmp_path):
        ws = tmp_path / "workspaces"
        ws.mkdir()
        mja = MagicMock(); mja.tasks_attempted = 10; mja.agent_name = "alpha"
        mnb = MagicMock(); mnb.tasks_attempted = 5; mnb.agent_name = "beta"
        with patch("services.coordinator_service.extract_performance_from_json", return_value={"alpha": mja}), \
             patch("services.coordinator_service.extract_performance_from_notes", return_value={"beta": mnb}):
            profiles = load_performance_profiles(ws)
        assert "alpha" in profiles
        assert "beta" in profiles


# ---------------------------------------------------------------------------
# Task Description Edge Cases
# ---------------------------------------------------------------------------


class TestTaskDescriptionEdgeCases:
    @pytest.mark.asyncio
    async def test_none_instructions_handled(self, tmp_workspaces, mock_em_client):
        task = {
            "id": "null-inst", "title": "Test task",
            "instructions": None, "description": None,
            "bounty_usd": 0.01, "category": "test",
            "payment_network": "base", "agent_wallet": "0xOTHER",
        }
        mock_em_client.browse_tasks = AsyncMock(return_value=[task])
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[{"agent_name": "alpha", "status": "idle"}]),
        )
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_agent_skills", return_value={"test"}):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_empty_title(self, tmp_workspaces, mock_em_client):
        task = {
            "id": "empty-title", "title": "", "instructions": "Do something",
            "bounty_usd": 0.01, "category": "test",
            "payment_network": "base", "agent_wallet": "0xOTHER",
        }
        mock_em_client.browse_tasks = AsyncMock(return_value=[task])
        mocks = _patch_swarm(
            states=AsyncMock(return_value=[{"agent_name": "alpha", "status": "idle"}]),
        )
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_agent_skills", return_value=set()):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Matching Mode Reporting Tests
# ---------------------------------------------------------------------------


class TestMatchingModeReporting:
    @pytest.mark.asyncio
    async def test_legacy_mode_reported(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=True,
            )
        assert result["matching_mode"] == "legacy"

    @pytest.mark.asyncio
    async def test_enhanced_mode_reported(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_latest_snapshot", return_value=None), \
             patch("services.coordinator_service.save_performance", return_value=0):
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client, use_legacy_matching=False,
            )
        assert result["matching_mode"] == "enhanced"

    @pytest.mark.asyncio
    async def test_autojob_mode_reported(self, tmp_workspaces, mock_em_client):
        mocks = _patch_swarm()
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        with patch("services.coordinator_service.get_agent_states", mocks["states"]), \
             patch("services.coordinator_service.get_stale_agents", mocks["stale"]), \
             patch("services.coordinator_service.get_swarm_summary", mocks["summary"]), \
             patch("services.coordinator_service.claim_task", mocks["claim"]), \
             patch("services.coordinator_service.send_notification", mocks["notify"]), \
             patch("services.coordinator_service.load_latest_snapshot", return_value=None), \
             patch("services.coordinator_service.save_performance", return_value=0), \
             patch("services.coordinator_service.AutoJobBridge") as MockBridge:
            MockBridge.return_value.health.return_value = {"status": "healthy", "registered_workers": 5}
            result = await coordination_cycle(
                tmp_workspaces, mock_em_client,
                use_legacy_matching=False, use_autojob=True,
            )
        assert result["matching_mode"] == "autojob"
        assert result["autojob"] is not None
        assert result["autojob"]["used"] is True
