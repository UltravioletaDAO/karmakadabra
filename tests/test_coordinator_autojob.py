"""
Tests for KK Coordinator ↔ AutoJob Bridge Integration

Validates that the coordinator can:
1. Initialize AutoJob bridge from wallets.json
2. Use AutoJob rankings for task assignment
3. Fall back to enhanced matching when AutoJob fails
4. Convert AutoJob 0-100 scores to coordinator 0-1 scores
5. Filter AutoJob rankings to only idle/eligible agents
6. Handle edge cases (no matches, bridge errors, empty swarm)
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from lib.autojob_bridge import AgentRanking, AutoJobBridge, BridgeResult
from services.coordinator_service import (
    CoordinatorService,
    _autojob_rank_to_coordinator,
    _build_autojob_bridge,
    load_coordinator_config,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_wallets_json(tmp_path):
    """Create a sample wallets.json file."""
    wallets = {
        "version": "1.0",
        "wallets": [
            {"index": 0, "name": "kk-coordinator", "address": "0xAAA", "type": "system"},
            {"index": 1, "name": "kk-validator", "address": "0xBBB", "type": "system"},
            {"index": 6, "name": "kk-alpha", "address": "0xCCC", "type": "user"},
            {"index": 7, "name": "kk-beta", "address": "0xDDD", "type": "user"},
            {"index": 8, "name": "kk-gamma", "address": "0xEEE", "type": "user"},
        ],
    }
    wf = tmp_path / "wallets.json"
    wf.write_text(json.dumps(wallets))
    return wf


@pytest.fixture
def sample_bridge_result():
    """Create a sample BridgeResult with ranked agents."""
    rankings = [
        AgentRanking(
            agent_name="kk-alpha",
            wallet="0xCCC",
            final_score=85.0,
            skill_score=90.0,
            reputation_score=80.0,
            reliability_score=88.0,
            recency_score=92.0,
            tier="diamante",
            confidence=0.95,
            explanation="Top photographer, active on Base",
            predicted_quality=4.5,
            predicted_success=0.93,
            categories_worked=["photography", "verification"],
            total_tasks=45,
        ),
        AgentRanking(
            agent_name="kk-beta",
            wallet="0xDDD",
            final_score=72.0,
            skill_score=75.0,
            reputation_score=70.0,
            reliability_score=80.0,
            recency_score=60.0,
            tier="oro",
            confidence=0.80,
            explanation="Solid category experience",
            predicted_quality=3.8,
            predicted_success=0.78,
            categories_worked=["data_collection"],
            total_tasks=20,
        ),
        AgentRanking(
            agent_name="kk-gamma",
            wallet="0xEEE",
            final_score=45.0,
            skill_score=50.0,
            reputation_score=40.0,
            reliability_score=55.0,
            recency_score=30.0,
            tier="plata",
            confidence=0.50,
            explanation="New worker, limited history",
            predicted_quality=3.2,
            predicted_success=0.55,
            categories_worked=["simple_action"],
            total_tasks=5,
        ),
    ]
    return BridgeResult(
        task_id="task-001",
        task_category="photography",
        rankings=rankings,
        total_candidates=3,
        qualified_candidates=3,
        best_match=rankings[0],
        match_time_ms=15.0,
        mode="local",
    )


# ═══════════════════════════════════════════════════════════════════
# Test: _build_autojob_bridge
# ═══════════════════════════════════════════════════════════════════


class TestBuildAutojobBridge:
    """Tests for bridge initialization from config."""

    def test_loads_wallet_mappings(self, sample_wallets_json):
        """Wallet → agent name mappings are loaded from wallets.json."""
        with patch.object(AutoJobBridge, "__init__", return_value=None):
            with patch.object(
                AutoJobBridge,
                "health",
                return_value={"status": "healthy", "registered_workers": 0},
            ):
                bridge, mapping = _build_autojob_bridge(
                    autojob_path="/fake/path",
                    wallets_file=sample_wallets_json,
                )
                # Check lowercase mapping
                assert mapping.get("0xaaa") == "kk-coordinator"
                assert mapping.get("0xccc") == "kk-alpha"
                assert mapping.get("0xddd") == "kk-beta"
                assert mapping.get("0xeee") == "kk-gamma"

    def test_returns_none_on_unhealthy(self, sample_wallets_json):
        """Returns None bridge if health check fails."""
        with patch.object(AutoJobBridge, "__init__", return_value=None):
            with patch.object(
                AutoJobBridge,
                "health",
                return_value={"status": "degraded"},
            ):
                bridge, mapping = _build_autojob_bridge(
                    autojob_path="/fake/path",
                    wallets_file=sample_wallets_json,
                )
                assert bridge is None
                # Mapping still loaded even when bridge is unhealthy
                assert len(mapping) == 5

    def test_returns_none_on_init_error(self, sample_wallets_json):
        """Returns None bridge if initialization throws."""
        with patch.object(
            AutoJobBridge, "__init__", side_effect=Exception("init failed")
        ):
            bridge, mapping = _build_autojob_bridge(
                autojob_path="/fake/path",
                wallets_file=sample_wallets_json,
            )
            assert bridge is None

    def test_missing_wallets_file(self):
        """Handles missing wallets.json gracefully."""
        with patch.object(AutoJobBridge, "__init__", return_value=None):
            with patch.object(
                AutoJobBridge,
                "health",
                return_value={"status": "healthy", "registered_workers": 0},
            ):
                bridge, mapping = _build_autojob_bridge(
                    autojob_path="/fake/path",
                    wallets_file=Path("/nonexistent/wallets.json"),
                )
                assert bridge is not None
                assert len(mapping) == 0

    def test_remote_mode_with_api_url(self, sample_wallets_json):
        """Uses remote mode when autojob_api is provided."""
        with patch.object(AutoJobBridge, "__init__", return_value=None) as mock_init:
            with patch.object(
                AutoJobBridge,
                "health",
                return_value={"status": "healthy"},
            ):
                bridge, _ = _build_autojob_bridge(
                    autojob_api="https://autojob.cc",
                    wallets_file=sample_wallets_json,
                )
                assert bridge is not None
                # Verify remote mode was chosen
                mock_init.assert_called_once()
                call_kwargs = mock_init.call_args
                assert call_kwargs[1]["mode"] == "remote"


# ═══════════════════════════════════════════════════════════════════
# Test: _autojob_rank_to_coordinator
# ═══════════════════════════════════════════════════════════════════


class TestAutojobRankToCoordinator:
    """Tests for converting AutoJob rankings to coordinator format."""

    def test_basic_conversion(self, sample_bridge_result):
        """Converts AutoJob 0-100 scores to coordinator 0-1 scores."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names={"kk-alpha", "kk-beta", "kk-gamma"},
            assigned_agents=set(),
            system_agents=set(),
        )
        assert len(ranked) == 3
        # Scores should be 0-1
        assert ranked[0] == ("kk-alpha", 0.85)
        assert ranked[1] == ("kk-beta", 0.72)
        assert ranked[2] == ("kk-gamma", 0.45)

    def test_filters_system_agents(self, sample_bridge_result):
        """System agents are excluded from ranking."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names={"kk-alpha", "kk-beta", "kk-gamma"},
            assigned_agents=set(),
            system_agents={"kk-alpha"},  # Alpha is system
        )
        assert len(ranked) == 2
        assert ranked[0][0] == "kk-beta"

    def test_filters_assigned_agents(self, sample_bridge_result):
        """Already-assigned agents are excluded."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names={"kk-alpha", "kk-beta", "kk-gamma"},
            assigned_agents={"kk-beta"},  # Beta already assigned
            system_agents=set(),
        )
        assert len(ranked) == 2
        assert ranked[0][0] == "kk-alpha"
        assert ranked[1][0] == "kk-gamma"

    def test_filters_non_idle_agents(self, sample_bridge_result):
        """Non-idle agents (busy, offline) are excluded."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names={"kk-alpha"},  # Only alpha is idle
            assigned_agents=set(),
            system_agents=set(),
        )
        assert len(ranked) == 1
        assert ranked[0][0] == "kk-alpha"

    def test_empty_bridge_result(self):
        """Handles empty ranking gracefully."""
        empty_result = BridgeResult(
            task_id="task-empty",
            task_category="test",
            rankings=[],
            total_candidates=0,
            qualified_candidates=0,
        )
        ranked = _autojob_rank_to_coordinator(
            empty_result,
            idle_names={"kk-alpha"},
            assigned_agents=set(),
            system_agents=set(),
        )
        assert ranked == []

    def test_all_agents_filtered_returns_empty(self, sample_bridge_result):
        """Returns empty list when all agents are filtered out."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names=set(),  # No idle agents
            assigned_agents=set(),
            system_agents=set(),
        )
        assert ranked == []

    def test_score_normalization_boundary(self):
        """Score normalization handles edge cases (0 and 100)."""
        rankings = [
            AgentRanking(
                agent_name="kk-perfect",
                wallet="0xAAA",
                final_score=100.0,
                skill_score=100.0,
                reputation_score=100.0,
                reliability_score=100.0,
                recency_score=100.0,
                tier="diamante",
                confidence=1.0,
                explanation="Perfect",
                predicted_quality=5.0,
                predicted_success=0.99,
            ),
            AgentRanking(
                agent_name="kk-zero",
                wallet="0xBBB",
                final_score=0.0,
                skill_score=0.0,
                reputation_score=0.0,
                reliability_score=0.0,
                recency_score=0.0,
                tier="unverified",
                confidence=0.0,
                explanation="No data",
                predicted_quality=1.0,
                predicted_success=0.10,
            ),
        ]
        result = BridgeResult(
            task_id="test",
            task_category="test",
            rankings=rankings,
            total_candidates=2,
            qualified_candidates=2,
        )
        ranked = _autojob_rank_to_coordinator(
            result,
            idle_names={"kk-perfect", "kk-zero"},
            assigned_agents=set(),
            system_agents=set(),
        )
        assert ranked[0] == ("kk-perfect", 1.0)
        assert ranked[1] == ("kk-zero", 0.0)


# ═══════════════════════════════════════════════════════════════════
# Test: Coordinator cycle with AutoJob (integration-level)
# ═══════════════════════════════════════════════════════════════════


class TestCoordinatorAutojobIntegration:
    """Higher-level tests verifying the coordinator uses AutoJob correctly.

    These mock the async components (EM client, swarm state) but test
    the real matching logic path.
    """

    @pytest.fixture
    def mock_swarm_state(self):
        """Mock swarm_state functions."""
        with patch("services.coordinator_service.get_agent_states") as mock_agents, \
             patch("services.coordinator_service.get_stale_agents") as mock_stale, \
             patch("services.coordinator_service.get_swarm_summary") as mock_summary, \
             patch("services.coordinator_service.claim_task") as mock_claim, \
             patch("services.coordinator_service.send_notification") as mock_notify:

            mock_agents.return_value = [
                {"agent_name": "kk-alpha", "status": "idle"},
                {"agent_name": "kk-beta", "status": "idle"},
                {"agent_name": "kk-gamma", "status": "busy"},
                {"agent_name": "kk-coordinator", "status": "idle"},
            ]
            mock_stale.return_value = []
            mock_summary.return_value = {"total_agents": 4, "idle": 2, "busy": 1}
            mock_claim.return_value = True
            mock_notify.return_value = True

            yield {
                "agents": mock_agents,
                "stale": mock_stale,
                "summary": mock_summary,
                "claim": mock_claim,
                "notify": mock_notify,
            }

    @pytest.fixture
    def mock_em_client(self):
        """Mock EM API client."""
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.wallet_address = "0x000"  # Coordinator wallet
        client.browse_tasks = AsyncMock(return_value=[
            {
                "id": "task-photo-001",
                "title": "Photograph sunset at local park",
                "instructions": "Take a geotagged photo of the sunset",
                "category": "photography",
                "bounty_usd": 2.50,
                "payment_network": "base",
                "agent_wallet": "0x999",  # Some other agent's task
            },
        ])
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_autojob_mode_uses_bridge(
        self, mock_swarm_state, mock_em_client, sample_bridge_result, tmp_path
    ):
        """When --autojob is enabled, the bridge is used for ranking."""
        from services.coordinator_service import coordination_cycle

        workspaces_dir = tmp_path / "workspaces"
        workspaces_dir.mkdir(parents=True)

        with patch(
            "services.coordinator_service._build_autojob_bridge"
        ) as mock_build:
            mock_bridge = MagicMock()
            mock_bridge.rank_agents_for_task.return_value = sample_bridge_result
            mock_build.return_value = (mock_bridge, {"0xccc": "kk-alpha", "0xddd": "kk-beta"})

            result = await coordination_cycle(
                workspaces_dir,
                mock_em_client,
                dry_run=True,
                use_autojob=True,
            )

            assert result["matching_mode"] == "autojob"
            assert result["autojob"]["used"] is True
            assert result["autojob"]["tasks_matched"] >= 0
            # Bridge was called
            mock_bridge.rank_agents_for_task.assert_called()

    @pytest.mark.asyncio
    async def test_autojob_fallback_on_no_matches(
        self, mock_swarm_state, mock_em_client, tmp_path
    ):
        """Falls back to enhanced matching when AutoJob returns no matches."""
        from services.coordinator_service import coordination_cycle

        workspaces_dir = tmp_path / "workspaces"
        workspaces_dir.mkdir(parents=True)

        empty_result = BridgeResult(
            task_id="task-photo-001",
            task_category="photography",
            rankings=[],
            total_candidates=0,
            qualified_candidates=0,
        )

        with patch(
            "services.coordinator_service._build_autojob_bridge"
        ) as mock_build:
            mock_bridge = MagicMock()
            mock_bridge.rank_agents_for_task.return_value = empty_result
            mock_build.return_value = (mock_bridge, {})

            result = await coordination_cycle(
                workspaces_dir,
                mock_em_client,
                dry_run=True,
                use_autojob=True,
            )

            assert result["autojob"]["fallbacks"] >= 1

    @pytest.mark.asyncio
    async def test_autojob_fallback_on_exception(
        self, mock_swarm_state, mock_em_client, tmp_path
    ):
        """Falls back to enhanced matching when AutoJob throws."""
        from services.coordinator_service import coordination_cycle

        workspaces_dir = tmp_path / "workspaces"
        workspaces_dir.mkdir(parents=True)

        with patch(
            "services.coordinator_service._build_autojob_bridge"
        ) as mock_build:
            mock_bridge = MagicMock()
            mock_bridge.rank_agents_for_task.side_effect = RuntimeError("API timeout")
            mock_build.return_value = (mock_bridge, {})

            result = await coordination_cycle(
                workspaces_dir,
                mock_em_client,
                dry_run=True,
                use_autojob=True,
            )

            assert result["autojob"]["fallbacks"] >= 1

    @pytest.mark.asyncio
    async def test_no_autojob_uses_enhanced(
        self, mock_swarm_state, mock_em_client, tmp_path
    ):
        """Without --autojob, uses standard enhanced matching."""
        from services.coordinator_service import coordination_cycle

        workspaces_dir = tmp_path / "workspaces"
        workspaces_dir.mkdir(parents=True)

        result = await coordination_cycle(
            workspaces_dir,
            mock_em_client,
            dry_run=True,
            use_autojob=False,
        )

        assert result["matching_mode"] == "enhanced"
        assert result["autojob"] is None

    @pytest.mark.asyncio
    async def test_autojob_bridge_init_failure_degrades(
        self, mock_swarm_state, mock_em_client, tmp_path
    ):
        """When bridge init fails, degrades to enhanced matching."""
        from services.coordinator_service import coordination_cycle

        workspaces_dir = tmp_path / "workspaces"
        workspaces_dir.mkdir(parents=True)

        with patch(
            "services.coordinator_service._build_autojob_bridge"
        ) as mock_build:
            # Bridge failed to initialize
            mock_build.return_value = (None, {})

            result = await coordination_cycle(
                workspaces_dir,
                mock_em_client,
                dry_run=True,
                use_autojob=True,
            )

            # Should fall back to enhanced mode
            assert result["matching_mode"] == "enhanced"


# ═══════════════════════════════════════════════════════════════════
# Test: Edge cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests for the AutoJob coordinator integration."""

    def test_multiple_system_agents_filtered(self, sample_bridge_result):
        """Multiple system agents in rankings are all filtered."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names={"kk-alpha", "kk-beta", "kk-gamma", "kk-coordinator", "kk-validator"},
            assigned_agents=set(),
            system_agents={"kk-coordinator", "kk-validator", "kk-alpha"},
        )
        assert len(ranked) == 2
        assert all(name not in {"kk-coordinator", "kk-validator", "kk-alpha"} for name, _ in ranked)

    def test_duplicate_filtering_assigned_and_system(self, sample_bridge_result):
        """Agent in both system and assigned sets is properly filtered."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names={"kk-alpha", "kk-beta", "kk-gamma"},
            assigned_agents={"kk-alpha"},
            system_agents={"kk-alpha"},  # Double-filtered
        )
        assert "kk-alpha" not in [name for name, _ in ranked]

    def test_preserves_ranking_order(self, sample_bridge_result):
        """Rankings maintain AutoJob's ordering."""
        ranked = _autojob_rank_to_coordinator(
            sample_bridge_result,
            idle_names={"kk-alpha", "kk-beta", "kk-gamma"},
            assigned_agents=set(),
            system_agents=set(),
        )
        scores = [s for _, s in ranked]
        assert scores == sorted(scores, reverse=True)


# ═══════════════════════════════════════════════════════════════════
# Test: CoordinatorService class wrapper
# ═══════════════════════════════════════════════════════════════════


class TestCoordinatorService:
    """Tests for the class-based CoordinatorService interface."""

    @pytest.fixture
    def mock_em_client(self):
        """Mock EM API client."""
        client = MagicMock()
        client.agent = MagicMock()
        client.agent.wallet_address = "0x000"
        client.browse_tasks = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    def test_init_with_defaults(self, mock_em_client, tmp_path):
        """CoordinatorService initializes with default settings."""
        svc = CoordinatorService(
            workspaces_dir=str(tmp_path),
            em_client=mock_em_client,
        )
        assert svc.dry_run is False
        assert svc.use_autojob is False
        assert svc.use_legacy_matching is False

    def test_init_with_autojob(self, mock_em_client, tmp_path):
        """CoordinatorService accepts AutoJob parameters."""
        svc = CoordinatorService(
            workspaces_dir=str(tmp_path),
            em_client=mock_em_client,
            use_autojob=True,
            autojob_path="/path/to/autojob",
        )
        assert svc.use_autojob is True
        assert svc.autojob_path == "/path/to/autojob"

    @pytest.mark.asyncio
    async def test_run_cycle_returns_normalized_result(self, mock_em_client, tmp_path):
        """run_cycle returns swarm_runner-compatible result dict."""
        (tmp_path / "workspaces").mkdir(exist_ok=True)
        workspaces = tmp_path / "workspaces"

        with patch("services.coordinator_service.get_agent_states") as mock_agents, \
             patch("services.coordinator_service.get_stale_agents") as mock_stale, \
             patch("services.coordinator_service.get_swarm_summary") as mock_summary:

            mock_agents.return_value = []
            mock_stale.return_value = []
            mock_summary.return_value = {"total_agents": 0, "idle_agents": 0}

            svc = CoordinatorService(
                workspaces_dir=str(workspaces),
                em_client=mock_em_client,
                dry_run=True,
            )
            result = await svc.run_cycle()

            # Verify standardized keys
            assert "tasks_found" in result
            assert "tasks_assigned" in result
            assert "agents_active" in result
            assert "agents_idle" in result
            assert "assignments" in result
            assert "matching_mode" in result


# ═══════════════════════════════════════════════════════════════════
# Test: load_coordinator_config
# ═══════════════════════════════════════════════════════════════════


class TestLoadCoordinatorConfig:
    """Tests for coordinator configuration loading."""

    def test_defaults(self):
        """Returns sensible defaults when no overrides provided."""
        config = load_coordinator_config()
        assert config["use_autojob"] is False
        assert config["dry_run"] is False
        assert config["use_legacy_matching"] is False
        assert config["autojob_path"] is None
        assert config["autojob_api"] is None

    def test_dict_overrides(self):
        """Provided dict overrides defaults."""
        config = load_coordinator_config({
            "use_autojob": True,
            "autojob_path": "/opt/autojob",
        })
        assert config["use_autojob"] is True
        assert config["autojob_path"] == "/opt/autojob"
        # Other defaults remain
        assert config["dry_run"] is False

    def test_env_overrides(self, monkeypatch):
        """Environment variables override defaults."""
        monkeypatch.setenv("KK_USE_AUTOJOB", "true")
        monkeypatch.setenv("KK_AUTOJOB_PATH", "/env/autojob")
        config = load_coordinator_config()
        assert config["use_autojob"] is True
        assert config["autojob_path"] == "/env/autojob"

    def test_dict_takes_precedence_over_env(self, monkeypatch):
        """Explicit dict overrides override env vars."""
        monkeypatch.setenv("KK_USE_AUTOJOB", "true")
        config = load_coordinator_config({"use_autojob": False})
        assert config["use_autojob"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
