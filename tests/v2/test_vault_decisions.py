"""
Tests for lib/vault_decisions.py — Vault-based Decision Engine

Covers:
  - AGENT_ROLES mapping
  - UPSTREAM dependency map
  - prioritize_actions for all roles:
    - orchestrator → ["monitor"]
    - validator → ["validate"]
    - producer (karma-hello): extractors waiting vs default
    - refiner (skill/voice/soul extractor): upstream data, status
    - buyer (community agents): offerings available, active sellers
  - Edge cases: empty vault state, unknown agents, mixed signals
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from lib.vault_decisions import (
    AGENT_ROLES,
    DEFAULT_ROLE,
    UPSTREAM,
    prioritize_actions,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vault():
    """Mock VaultSync object."""
    vault = MagicMock()
    vault.read_supply_chain_status.return_value = {}
    vault.read_peer_offerings.return_value = []
    return vault


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_agent_roles_coverage(self):
        expected = {
            "kk-karma-hello": "producer",
            "kk-skill-extractor": "refiner",
            "kk-voice-extractor": "refiner",
            "kk-soul-extractor": "aggregator",
            "kk-coordinator": "orchestrator",
            "kk-validator": "validator",
        }
        assert AGENT_ROLES == expected

    def test_upstream_dependencies(self):
        assert UPSTREAM["kk-skill-extractor"] == ["kk-karma-hello"]
        assert UPSTREAM["kk-voice-extractor"] == ["kk-karma-hello"]
        assert set(UPSTREAM["kk-soul-extractor"]) == {"kk-skill-extractor", "kk-voice-extractor"}

    def test_default_role_is_buyer(self):
        assert DEFAULT_ROLE == "buyer"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def test_orchestrator_always_monitor(self, mock_vault):
        result = prioritize_actions(mock_vault, "kk-coordinator")
        assert result == ["monitor"]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class TestValidator:
    def test_validator_always_validate(self, mock_vault):
        result = prioritize_actions(mock_vault, "kk-validator")
        assert result == ["validate"]


# ---------------------------------------------------------------------------
# Producer (karma-hello)
# ---------------------------------------------------------------------------


class TestProducer:
    def test_default_order(self, mock_vault):
        """No extractors waiting → default order."""
        result = prioritize_actions(mock_vault, "kk-karma-hello")
        assert result == ["collect", "publish", "fulfill", "sell"]

    def test_extractors_idle(self, mock_vault):
        """Extractors idle → prioritize publish+fulfill."""
        mock_vault.read_supply_chain_status.return_value = {
            "kk-skill-extractor": "idle",
            "kk-voice-extractor": "processing",
        }
        result = prioritize_actions(mock_vault, "kk-karma-hello")
        assert result[0] == "publish"
        assert "fulfill" in result

    def test_extractors_waiting(self, mock_vault):
        mock_vault.read_supply_chain_status.return_value = {
            "kk-skill-extractor": "waiting for data",
        }
        result = prioritize_actions(mock_vault, "kk-karma-hello")
        assert result[0] == "publish"

    def test_no_extractors_in_chain(self, mock_vault):
        """No extractor status → default order."""
        mock_vault.read_supply_chain_status.return_value = {
            "kk-coordinator": "monitoring",
        }
        result = prioritize_actions(mock_vault, "kk-karma-hello")
        assert result == ["collect", "publish", "fulfill", "sell"]


# ---------------------------------------------------------------------------
# Refiner (skill-extractor, voice-extractor)
# ---------------------------------------------------------------------------


class TestRefiner:
    def test_upstream_has_offerings(self, mock_vault):
        """Upstream (karma-hello) has offerings → prioritize buy."""
        mock_vault.read_peer_offerings.return_value = [
            {"title": "Raw logs", "bounty": 0.01}
        ]
        result = prioritize_actions(mock_vault, "kk-skill-extractor")
        assert result[0] == "buy"
        assert "process" in result
        assert "sell" in result

    def test_upstream_active_status(self, mock_vault):
        """Upstream status shows 'active' → include buy."""
        mock_vault.read_peer_offerings.return_value = []
        mock_vault.read_supply_chain_status.return_value = {
            "kk-karma-hello": "active publishing",
        }
        result = prioritize_actions(mock_vault, "kk-skill-extractor")
        assert "buy" in result

    def test_upstream_publish_status(self, mock_vault):
        """Upstream status shows 'publish' → include buy."""
        mock_vault.read_peer_offerings.return_value = []
        mock_vault.read_supply_chain_status.return_value = {
            "kk-karma-hello": "publishing new data",
        }
        result = prioritize_actions(mock_vault, "kk-skill-extractor")
        assert "buy" in result

    def test_no_upstream_data(self, mock_vault):
        """No upstream offerings or activity → still process + sell."""
        result = prioritize_actions(mock_vault, "kk-skill-extractor")
        assert "process" in result
        assert "sell" in result

    def test_voice_extractor_same_logic(self, mock_vault):
        mock_vault.read_peer_offerings.return_value = [
            {"title": "Data", "bounty": 0.01}
        ]
        result = prioritize_actions(mock_vault, "kk-voice-extractor")
        assert result[0] == "buy"

    def test_soul_extractor_as_aggregator(self, mock_vault):
        """Soul extractor is 'aggregator' role but uses same refiner logic."""
        mock_vault.read_peer_offerings.return_value = [
            {"title": "Skill data", "bounty": 0.05}
        ]
        result = prioritize_actions(mock_vault, "kk-soul-extractor")
        assert result[0] == "buy"

    def test_soul_extractor_checks_both_upstreams(self, mock_vault):
        """Soul extractor's upstream is skill + voice extractors."""
        # No offerings from first upstream
        mock_vault.read_peer_offerings.side_effect = lambda name: (
            [{"title": "Voice data"}] if name == "kk-voice-extractor" else []
        )
        result = prioritize_actions(mock_vault, "kk-soul-extractor")
        assert "buy" in result

    def test_always_includes_process_and_sell(self, mock_vault):
        """Process and sell are always in the priority list."""
        result = prioritize_actions(mock_vault, "kk-skill-extractor")
        assert "process" in result
        assert "sell" in result


# ---------------------------------------------------------------------------
# Buyer (community/unknown agents)
# ---------------------------------------------------------------------------


class TestBuyer:
    def test_unknown_agent_is_buyer(self, mock_vault):
        """Agents not in AGENT_ROLES default to buyer."""
        result = prioritize_actions(mock_vault, "community-agent-42")
        assert "buy" in result

    def test_karma_hello_has_offerings(self, mock_vault):
        mock_vault.read_peer_offerings.return_value = [
            {"title": "Raw logs"}
        ]
        result = prioritize_actions(mock_vault, "community-agent")
        assert result == ["buy"]

    def test_active_sellers(self, mock_vault):
        mock_vault.read_peer_offerings.return_value = []
        mock_vault.read_supply_chain_status.return_value = {
            "kk-skill-extractor": "publishing new skill profiles",
        }
        result = prioritize_actions(mock_vault, "community-agent")
        assert result == ["buy"]

    def test_no_offerings_no_sellers(self, mock_vault):
        """Nothing available → buy + idle."""
        result = prioritize_actions(mock_vault, "community-agent")
        assert result == ["buy", "idle"]

    def test_own_status_not_counted(self, mock_vault):
        """Agent's own status shouldn't make it think there are active sellers."""
        mock_vault.read_peer_offerings.return_value = []
        mock_vault.read_supply_chain_status.return_value = {
            "community-agent": "active",  # own status
        }
        result = prioritize_actions(mock_vault, "community-agent")
        assert result == ["buy", "idle"]
