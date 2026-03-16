"""
Tests for Task 4.4: Skills Marketplace IRC Bot

Tests command dispatch, offering CRUD, and marketplace state.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "irc"))

from skills_marketplace_bot import (
    MarketplaceState,
    ServiceOffering,
    dispatch_command,
    handle_find,
    handle_help,
    handle_hire,
    handle_my_offers,
    handle_offer,
    handle_rate,
    handle_remove,
)


@pytest.fixture
def state():
    return MarketplaceState()


@pytest.fixture
def state_with_offers():
    s = MarketplaceState()
    s.add_offering(
        ServiceOffering(
            id="off-test1",
            nick="alice",
            skill="solidity",
            price_usd=0.20,
            description="Smart contract auditing",
            created_at="2026-02-25T00:00:00Z",
        )
    )
    s.add_offering(
        ServiceOffering(
            id="off-test2",
            nick="bob",
            skill="python",
            price_usd=0.10,
            description="Python automation scripts",
            created_at="2026-02-25T00:00:00Z",
        )
    )
    s.add_offering(
        ServiceOffering(
            id="off-test3",
            nick="alice",
            skill="defi",
            price_usd=0.15,
            description="DeFi yield strategy consulting",
            created_at="2026-02-25T00:00:00Z",
        )
    )
    return s


# --- Tests: handle_offer ---


class TestHandleOffer:
    def test_creates_offering(self, state):
        result = handle_offer(state, "alice", "solidity 0.20 Smart contract auditing")
        assert len(result) == 2
        assert "[OFFER]" in result[0]
        assert "alice" in result[0]
        assert "$0.20" in result[0]
        assert len(state.offerings) == 1

    def test_missing_args(self, state):
        result = handle_offer(state, "alice", "solidity 0.20")
        assert "Usage" in result[0]

    def test_invalid_price(self, state):
        result = handle_offer(state, "alice", "solidity abc Description here")
        assert "Invalid price" in result[0]

    def test_price_too_high(self, state):
        result = handle_offer(state, "alice", "solidity 99.99 Too expensive")
        assert "between" in result[0]

    def test_short_description(self, state):
        result = handle_offer(state, "alice", "solidity 0.10 Hi")
        assert "short" in result[0]

    def test_max_five_offers(self, state):
        for i in range(5):
            handle_offer(state, "alice", f"skill{i} 0.10 Description number {i}")
        result = handle_offer(state, "alice", "skill5 0.10 One more offering")
        assert "Max 5" in result[0]


# --- Tests: handle_find ---


class TestHandleFind:
    def test_finds_matching(self, state_with_offers):
        result = handle_find(state_with_offers, "charlie", "solidity")
        assert "[FIND]" in result[0]
        assert "alice" in result[1]

    def test_partial_match(self, state_with_offers):
        result = handle_find(state_with_offers, "charlie", "sol")
        assert "[FIND]" in result[0]

    def test_no_match(self, state_with_offers):
        result = handle_find(state_with_offers, "charlie", "rust")
        assert "No offerings found" in result[0]

    def test_empty_query(self, state_with_offers):
        result = handle_find(state_with_offers, "charlie", "")
        assert "Usage" in result[0]


# --- Tests: handle_hire ---


class TestHandleHire:
    def test_creates_hire_request(self, state_with_offers):
        result = handle_hire(state_with_offers, "charlie", "alice solidity")
        assert "[HIRE]" in result[0]
        assert "charlie" in result[0]
        assert "alice" in result[0]
        assert len(state_with_offers.hire_history) == 1

    def test_no_matching_offer(self, state_with_offers):
        result = handle_hire(state_with_offers, "charlie", "alice rust")
        assert "No offering" in result[0]

    def test_missing_args(self, state_with_offers):
        result = handle_hire(state_with_offers, "charlie", "alice")
        assert "Usage" in result[0]


# --- Tests: handle_rate ---


class TestHandleRate:
    def test_rates_provider(self, state_with_offers):
        result = handle_rate(state_with_offers, "charlie", "alice 5 Excellent work!")
        assert "[RATE]" in result[0]
        assert "*****" in result[0]
        assert "Excellent work!" in result[0]

    def test_updates_offering_rating(self, state_with_offers):
        handle_rate(state_with_offers, "charlie", "alice 4")
        offers = state_with_offers.find_by_nick("alice")
        for o in offers:
            assert o.rating_avg == 4.0
            assert o.rating_count == 1

    def test_cumulative_rating(self, state_with_offers):
        handle_rate(state_with_offers, "charlie", "alice 5")
        handle_rate(state_with_offers, "dave", "alice 3")
        offers = state_with_offers.find_by_nick("alice")
        for o in offers:
            assert o.rating_avg == 4.0  # (5+3)/2
            assert o.rating_count == 2

    def test_invalid_score(self, state_with_offers):
        result = handle_rate(state_with_offers, "charlie", "alice 6")
        assert "1-5" in result[0]

    def test_no_offers_still_records(self, state_with_offers):
        result = handle_rate(state_with_offers, "charlie", "unknown 4 Good service")
        assert "[RATE]" in result[0]
        assert "no active offerings" in result[1]


# --- Tests: handle_my_offers ---


class TestHandleMyOffers:
    def test_lists_offers(self, state_with_offers):
        result = handle_my_offers(state_with_offers, "alice")
        assert "[MY-OFFERS]" in result[0]
        assert "2 active" in result[0]

    def test_no_offers(self, state_with_offers):
        result = handle_my_offers(state_with_offers, "nobody")
        assert "no active offerings" in result[0]


# --- Tests: handle_remove ---


class TestHandleRemove:
    def test_removes_own_offering(self, state_with_offers):
        result = handle_remove(state_with_offers, "alice", "off-test1")
        assert "[REMOVED]" in result[0]
        assert not state_with_offers.offerings["off-test1"].active

    def test_cannot_remove_others(self, state_with_offers):
        result = handle_remove(state_with_offers, "charlie", "off-test1")
        assert "only remove your own" in result[0]

    def test_not_found(self, state_with_offers):
        result = handle_remove(state_with_offers, "alice", "off-nonexistent")
        assert "not found" in result[0]


# --- Tests: dispatch_command ---


class TestDispatchCommand:
    def test_offer_command(self, state):
        result = dispatch_command(state, "alice", "!offer python 0.10 Build automation scripts")
        assert result is not None
        assert "[OFFER]" in result[0]

    def test_find_command(self, state_with_offers):
        result = dispatch_command(state_with_offers, "charlie", "!find solidity")
        assert result is not None
        assert "[FIND]" in result[0]

    def test_hire_command(self, state_with_offers):
        result = dispatch_command(state_with_offers, "charlie", "!hire @alice solidity")
        assert result is not None
        assert "[HIRE]" in result[0]

    def test_rate_command(self, state_with_offers):
        result = dispatch_command(state_with_offers, "charlie", "!rate @alice 5 Great!")
        assert result is not None
        assert "[RATE]" in result[0]

    def test_help_command(self, state):
        result = dispatch_command(state, "anyone", "!skills-help")
        assert result is not None
        assert "SKILLS MARKETPLACE" in result[0]

    def test_my_offers_command(self, state_with_offers):
        result = dispatch_command(state_with_offers, "alice", "!my-offers")
        assert result is not None

    def test_remove_command(self, state_with_offers):
        result = dispatch_command(state_with_offers, "alice", "!remove off-test1")
        assert result is not None

    def test_non_command_returns_none(self, state):
        result = dispatch_command(state, "alice", "Hello everyone!")
        assert result is None

    def test_case_insensitive(self, state_with_offers):
        result = dispatch_command(state_with_offers, "alice", "!FIND python")
        assert result is not None


# --- Tests: MarketplaceState persistence ---


class TestMarketplaceState:
    def test_save_and_load(self, tmp_path):
        state = MarketplaceState()
        state.add_offering(
            ServiceOffering(
                id="off-persist",
                nick="test",
                skill="python",
                price_usd=0.10,
                description="Test service",
                created_at="2026-02-25T00:00:00Z",
            )
        )
        state.nick_to_wallet["test"] = "0x1234"

        path = tmp_path / "state.json"
        state.save(path)

        loaded = MarketplaceState.load(path)
        assert "off-persist" in loaded.offerings
        assert loaded.offerings["off-persist"].skill == "python"
        assert loaded.nick_to_wallet["test"] == "0x1234"

    def test_load_missing_file(self, tmp_path):
        loaded = MarketplaceState.load(tmp_path / "nonexistent.json")
        assert len(loaded.offerings) == 0

    def test_load_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("not json", encoding="utf-8")
        loaded = MarketplaceState.load(path)
        assert len(loaded.offerings) == 0

    def test_find_by_skill_case_insensitive(self, state_with_offers):
        result = state_with_offers.find_by_skill("SOLIDITY")
        assert len(result) == 1

    def test_find_by_nick(self, state_with_offers):
        result = state_with_offers.find_by_nick("alice")
        assert len(result) == 2

    def test_remove_makes_inactive(self, state_with_offers):
        state_with_offers.remove_offering("off-test1")
        active = state_with_offers.find_by_nick("alice")
        assert len(active) == 1  # Only defi offering remains
