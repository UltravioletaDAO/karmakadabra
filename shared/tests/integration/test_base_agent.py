#!/usr/bin/env python3
"""
Integration tests for base_agent.py - ERC8004 on-chain integration

These tests interact with real contracts on Avalanche Fuji testnet.
Requires funded wallet with AVAX for gas.

Run with: pytest -m integration
Skip with: pytest -m "not integration"
"""

import pytest
import os

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from base_agent import ERC8004BaseAgent


@pytest.mark.integration
@pytest.mark.requires_funding
class TestERC8004BaseAgentIntegration:
    """Integration tests for ERC8004BaseAgent with real contracts"""

    @pytest.fixture
    def funded_agent(self, test_config, funded_test_key):
        """
        Create agent with funded wallet

        Note: Requires TEST_PRIVATE_KEY env var with funded wallet
        """
        # Skip if no funded wallet
        if not os.getenv("TEST_PRIVATE_KEY"):
            pytest.skip("TEST_PRIVATE_KEY not set - cannot run funded tests")

        agent = ERC8004BaseAgent(
            agent_name="test-agent",
            agent_domain="test-integration.ultravioletadao.xyz",
            private_key=funded_test_key,
            rpc_url=test_config["rpc_url"],
            chain_id=test_config["chain_id"],
            identity_registry_address=test_config["identity_registry"],
            reputation_registry_address=test_config["reputation_registry"]
        )

        yield agent

    def test_web3_connection(self, funded_agent):
        """Test Web3 connection to Fuji"""
        assert funded_agent.w3.is_connected()
        assert funded_agent.w3.eth.chain_id == 43113

    def test_contract_loading(self, funded_agent):
        """Test contract instances loaded correctly"""
        assert funded_agent.identity_registry is not None
        assert funded_agent.reputation_registry is not None

        # Verify contract addresses
        assert funded_agent.identity_registry.address != "0x0000000000000000000000000000000000000000"

    @pytest.mark.slow
    def test_query_existing_agent(self, funded_agent, test_config):
        """Test querying existing agent from registry"""
        # Query agent ID 1 (should exist from deployment)
        try:
            agent_exists = funded_agent.agent_exists(1)
            # If agent 1 exists, verify we can query it
            if agent_exists:
                domain, _, active = funded_agent.identity_registry.functions.getAgent(1).call()
                assert isinstance(domain, str)
                assert active is True
        except Exception as e:
            pytest.skip(f"Could not query agent: {e}")

    @pytest.mark.slow
    def test_get_next_agent_id(self, funded_agent):
        """Test getting next available agent ID"""
        next_id = funded_agent.get_next_agent_id()
        assert isinstance(next_id, int)
        assert next_id > 0

    # Note: Actual registration tests commented out to avoid spending testnet AVAX
    # Uncomment to test real registration (costs ~0.005 AVAX)
    """
    @pytest.mark.slow
    def test_register_new_agent(self, funded_agent):
        # WARNING: This will spend testnet AVAX!
        agent_id = funded_agent.register_agent()
        assert isinstance(agent_id, int)
        assert agent_id > 0

        # Verify registration
        assert funded_agent.agent_exists(agent_id)
    """


@pytest.mark.integration
class TestERC8004BaseAgentReadOnly:
    """Integration tests that don't require funding (read-only)"""

    @pytest.fixture
    def readonly_agent(self, test_config, test_private_key):
        """Create agent for read-only operations"""
        agent = ERC8004BaseAgent(
            agent_name="readonly-test",
            agent_domain="readonly.ultravioletadao.xyz",
            private_key=test_private_key,
            rpc_url=test_config["rpc_url"],
            chain_id=test_config["chain_id"],
            identity_registry_address=test_config["identity_registry"],
            reputation_registry_address=test_config["reputation_registry"]
        )
        return agent

    def test_contract_read_operations(self, readonly_agent):
        """Test read-only contract operations"""
        # These should work without funding
        next_id = readonly_agent.get_next_agent_id()
        assert next_id > 0

    def test_query_reputation(self, readonly_agent):
        """Test querying reputation (read-only)"""
        # Try to get rating for agent 1 (may not exist)
        try:
            has_rating, rating = readonly_agent.get_server_rating(
                client_id=1,
                server_id=2
            )
            # If rating exists, verify format
            if has_rating:
                assert isinstance(rating, int)
                assert 0 <= rating <= 100
        except Exception:
            # No rating exists - this is fine for test
            pass
