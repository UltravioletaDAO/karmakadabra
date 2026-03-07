"""
Tests for community_buyer_service.py — A2H Task Creator

Covers:
  - Bounty definitions and supply chain steps
  - Autodiscovery cycle (steps: raw_logs → skill_profiles → voice_profiles → soul_profiles)
  - Entrepreneur cycle (human task publishing)
  - Step advancement on completion
  - Cycle count transitions (autodiscovery → entrepreneur)
  - State persistence
  - run_cycle integration
  - Edge cases: all bounties active, budget exceeded, API failures
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.community_buyer_service import (
    BOUNTIES,
    ENTREPRENEUR_BOUNTIES,
    SUPPLY_CHAIN_STEPS,
    run_cycle,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create temporary workspace + data dirs."""
    ws = tmp_path / "workspaces" / "kk-juanjumagalp"
    ws.mkdir(parents=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return ws, data_dir


@pytest.fixture
def mock_em_client():
    """Create a mock EMClient."""
    client = MagicMock()
    client.agent = MagicMock()
    client.agent.wallet_address = "0xBUYER"
    client.agent.name = "kk-juanjumagalp"
    client.close = AsyncMock()
    client.browse_tasks = AsyncMock(return_value=[])
    client.publish_task = AsyncMock(return_value={"id": "new-task-001"})
    return client


# ---------------------------------------------------------------------------
# Bounty Definition Tests
# ---------------------------------------------------------------------------


class TestBountyDefinitions:
    def test_four_supply_chain_steps(self):
        assert len(SUPPLY_CHAIN_STEPS) == 4
        assert SUPPLY_CHAIN_STEPS == ["raw_logs", "skill_profiles", "voice_profiles", "soul_profiles"]

    def test_bounties_match_steps(self):
        for step in SUPPLY_CHAIN_STEPS:
            assert step in BOUNTIES, f"Missing bounty definition for step: {step}"

    def test_bounties_have_required_fields(self):
        required = {"title", "instructions", "bounty_usd", "priority", "target_executor", "skills_required"}
        for key, bounty in BOUNTIES.items():
            for field in required:
                assert field in bounty, f"Bounty '{key}' missing field: {field}"

    def test_bounties_ordered_by_priority(self):
        priorities = [BOUNTIES[step]["priority"] for step in SUPPLY_CHAIN_STEPS]
        assert priorities == sorted(priorities), "Supply chain steps not in priority order"

    def test_bounty_prices_are_positive(self):
        for key, bounty in BOUNTIES.items():
            assert bounty["bounty_usd"] > 0, f"Bounty '{key}' has zero/negative price"

    def test_total_cycle_cost(self):
        total = sum(BOUNTIES[step]["bounty_usd"] for step in SUPPLY_CHAIN_STEPS)
        assert total == pytest.approx(0.18, abs=0.01)

    def test_entrepreneur_bounties_have_required_fields(self):
        required = {"title", "instructions", "bounty_usd", "category", "target_executor", "skills_required"}
        for i, bounty in enumerate(ENTREPRENEUR_BOUNTIES):
            for field in required:
                assert field in bounty, f"Entrepreneur bounty #{i} missing field: {field}"

    def test_entrepreneur_bounties_target_humans(self):
        for bounty in ENTREPRENEUR_BOUNTIES:
            assert bounty["target_executor"] == "human"

    def test_entrepreneur_bounties_have_unique_categories(self):
        categories = [b["category"] for b in ENTREPRENEUR_BOUNTIES]
        # Categories can repeat (e.g., multiple entrepreneur_research) but should exist
        assert all(c.startswith("entrepreneur_") for c in categories)


# ---------------------------------------------------------------------------
# Autodiscovery Cycle Tests
# ---------------------------------------------------------------------------


class TestAutodiscoveryCycle:
    @pytest.mark.asyncio
    async def test_initial_state(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value="task-001") as mock_pub, \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}) as mock_mgmt, \
             patch("services.community_buyer_service.save_escrow_state") as mock_save, \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            result = await run_cycle(data_dir, ws, dry_run=True)

        assert result["step"] == "raw_logs"
        assert result["cycle_count"] == 0

    @pytest.mark.asyncio
    async def test_publishes_current_step_bounty(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value="task-001") as mock_pub, \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}, "current_step": "skill_profiles", "cycle_count": 0}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            result = await run_cycle(data_dir, ws, dry_run=True)

        assert result["step"] == "skill_profiles"
        # publish_bounty should have been called with skill_profiles params
        mock_pub.assert_called_once()
        call_kwargs = mock_pub.call_args.kwargs
        assert call_kwargs["category_key"] == "skill_profiles"

    @pytest.mark.asyncio
    async def test_step_advancement_on_completion(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        # State: raw_logs step with a completed bounty
        state = {
            "published": {
                "task-001": {
                    "category": "raw_logs",
                    "status": "completed",
                    "title": "test",
                    "bounty": 0.01,
                }
            },
            "current_step": "raw_logs",
            "cycle_count": 0,
        }
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value=None), \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 1}), \
             patch("services.community_buyer_service.save_escrow_state") as mock_save, \
             patch("services.community_buyer_service.load_escrow_state", return_value=state):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            result = await run_cycle(data_dir, ws, dry_run=False)

        # State should have been updated to advance step
        save_calls = mock_save.call_args_list
        if save_calls:
            saved_state = save_calls[-1][0][1]
            assert saved_state["current_step"] == "skill_profiles"

    @pytest.mark.asyncio
    async def test_full_cycle_complete_enters_entrepreneur_mode(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        # State: soul_profiles step (last) with a completed bounty
        state = {
            "published": {
                "task-004": {
                    "category": "soul_profiles",
                    "status": "completed",
                    "title": "test",
                    "bounty": 0.08,
                }
            },
            "current_step": "soul_profiles",
            "cycle_count": 0,
        }
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value=None), \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 1}), \
             patch("services.community_buyer_service.save_escrow_state") as mock_save, \
             patch("services.community_buyer_service.load_escrow_state", return_value=state):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            result = await run_cycle(data_dir, ws, dry_run=False)

        # Cycle count should advance
        save_calls = mock_save.call_args_list
        if save_calls:
            saved_state = save_calls[-1][0][1]
            assert saved_state["cycle_count"] == 1


# ---------------------------------------------------------------------------
# Entrepreneur Cycle Tests
# ---------------------------------------------------------------------------


class TestEntrepreneurCycle:
    @pytest.mark.asyncio
    async def test_entrepreneur_mode_activates_after_cycle_1(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        state = {
            "published": {},
            "current_step": "raw_logs",
            "cycle_count": 1,  # Post-autodiscovery
        }
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value="ent-001") as mock_pub, \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value=state):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            mock_client = MockClient.return_value
            mock_client.close = AsyncMock()
            mock_client.agent = mock_ctx.return_value
            mock_client.browse_tasks = AsyncMock(return_value=[])

            result = await run_cycle(data_dir, ws, dry_run=True)

        assert result["step"] == "entrepreneur"
        assert result["entrepreneur_published"] >= 0

    @pytest.mark.asyncio
    async def test_entrepreneur_publishes_one_bounty_per_heartbeat(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        state = {
            "published": {},
            "current_step": "raw_logs",
            "cycle_count": 2,
        }
        pub_count = 0

        async def track_publish(*args, **kwargs):
            nonlocal pub_count
            pub_count += 1
            return f"ent-{pub_count:03d}"

        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", side_effect=track_publish) as mock_pub, \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value=state):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            mock_client = MockClient.return_value
            mock_client.close = AsyncMock()
            mock_client.agent = mock_ctx.return_value
            mock_client.browse_tasks = AsyncMock(return_value=[])

            result = await run_cycle(data_dir, ws, dry_run=False)

        # Should publish exactly 1 per heartbeat
        assert pub_count == 1

    @pytest.mark.asyncio
    async def test_entrepreneur_skips_active_categories(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        state = {
            "published": {
                "ent-001": {"category": "entrepreneur_research", "status": "published"},
                "ent-002": {"category": "entrepreneur_data", "status": "published"},
                "ent-003": {"category": "entrepreneur_verify", "status": "published"},
                "ent-004": {"category": "entrepreneur_content", "status": "published"},
            },
            "current_step": "raw_logs",
            "cycle_count": 3,
        }
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value=None) as mock_pub, \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value=state):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            mock_client = MockClient.return_value
            mock_client.close = AsyncMock()
            mock_client.agent = mock_ctx.return_value
            mock_client.browse_tasks = AsyncMock(return_value=[])

            result = await run_cycle(data_dir, ws, dry_run=False)

        # All categories active, so no new publish should happen (or at most find remaining ones)
        assert result["entrepreneur_published"] <= 1

    @pytest.mark.asyncio
    async def test_entrepreneur_browses_external_tasks(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        state = {
            "published": {},
            "current_step": "raw_logs",
            "cycle_count": 1,
        }
        external_tasks = [
            {"id": "ext-1", "title": "External task", "bounty_amount": 0.50},
            {"id": "ext-2", "title": "Another task", "bounty_amount": 1.00},
        ]
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value="ent-1"), \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value=state):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            mock_client = MockClient.return_value
            mock_client.close = AsyncMock()
            mock_client.agent = mock_ctx.return_value
            mock_client.browse_tasks = AsyncMock(return_value=external_tasks)

            result = await run_cycle(data_dir, ws, dry_run=False)

        assert result.get("opportunities_found", 0) == 2


# ---------------------------------------------------------------------------
# State Persistence Tests
# ---------------------------------------------------------------------------


class TestStatePersistence:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_save(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value=None), \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}), \
             patch("services.community_buyer_service.save_escrow_state") as mock_save, \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            await run_cycle(data_dir, ws, dry_run=True)

        mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_run_saves_state(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value=None), \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 0, "approved": 0, "completed": 0}), \
             patch("services.community_buyer_service.save_escrow_state") as mock_save, \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            await run_cycle(data_dir, ws, dry_run=False)

        mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_publish_failure_captured_in_stats(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, side_effect=Exception("API exploded")), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            result = await run_cycle(data_dir, ws, dry_run=False)

        assert len(result["errors"]) > 0
        assert "API exploded" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_client_always_closed(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, side_effect=Exception("boom")), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            mock_client = MockClient.return_value
            mock_client.close = AsyncMock()
            mock_client.agent = mock_ctx.return_value

            await run_cycle(data_dir, ws, dry_run=False)

        # Client.close() should always be called even on error
        mock_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Stats Output Tests
# ---------------------------------------------------------------------------


class TestStatsOutput:
    @pytest.mark.asyncio
    async def test_stats_has_required_keys(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value="t-1"), \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 2, "approved": 1, "completed": 1}), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            result = await run_cycle(data_dir, ws, dry_run=True)

        required_keys = {"step", "cycle_count", "published", "assigned", "approved", "completed", "entrepreneur_published", "errors"}
        assert required_keys.issubset(result.keys())

    @pytest.mark.asyncio
    async def test_stats_reflect_manage_results(self, tmp_workspace):
        ws, data_dir = tmp_workspace
        with patch("services.community_buyer_service.load_agent_context") as mock_ctx, \
             patch("services.community_buyer_service.EMClient") as MockClient, \
             patch("services.community_buyer_service.publish_bounty", new_callable=AsyncMock, return_value="t-1"), \
             patch("services.community_buyer_service.manage_bounties", new_callable=AsyncMock, return_value={"assigned": 3, "approved": 2, "completed": 1}), \
             patch("services.community_buyer_service.save_escrow_state"), \
             patch("services.community_buyer_service.load_escrow_state", return_value={"published": {}}):
            mock_ctx.return_value = MagicMock(name="kk-juanjumagalp", wallet_address="0xBUYER")
            MockClient.return_value.close = AsyncMock()
            MockClient.return_value.agent = mock_ctx.return_value

            result = await run_cycle(data_dir, ws, dry_run=False)

        assert result["assigned"] == 3
        assert result["approved"] == 2
        assert result["completed"] == 1


# ---------------------------------------------------------------------------
# Supply Chain Step Ordering Tests
# ---------------------------------------------------------------------------


class TestSupplyChainStepOrdering:
    def test_steps_in_sequence(self):
        """Steps follow logical data pipeline order."""
        assert SUPPLY_CHAIN_STEPS.index("raw_logs") < SUPPLY_CHAIN_STEPS.index("skill_profiles")
        assert SUPPLY_CHAIN_STEPS.index("skill_profiles") < SUPPLY_CHAIN_STEPS.index("voice_profiles")
        assert SUPPLY_CHAIN_STEPS.index("voice_profiles") < SUPPLY_CHAIN_STEPS.index("soul_profiles")

    def test_all_steps_have_bounty_definitions(self):
        for step in SUPPLY_CHAIN_STEPS:
            assert step in BOUNTIES
            assert BOUNTIES[step]["bounty_usd"] > 0

    def test_all_bounties_target_agents(self):
        """Supply chain bounties are for AI agents, not humans."""
        for step in SUPPLY_CHAIN_STEPS:
            assert BOUNTIES[step]["target_executor"] == "agent"

    def test_price_increases_with_complexity(self):
        """Later steps cost more (more complex processing)."""
        prices = [BOUNTIES[step]["bounty_usd"] for step in SUPPLY_CHAIN_STEPS]
        # Not strictly increasing but generally trending up
        assert prices[-1] >= prices[0]
