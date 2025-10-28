#!/usr/bin/env python3
"""
Pytest configuration and fixtures for Karmacadabra shared utilities

This module provides common fixtures for both unit and integration tests.
"""

import os
import pytest
from unittest.mock import Mock, MagicMock
from web3 import Web3
from eth_account import Account


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

@pytest.fixture(scope="session")
def test_config():
    """
    Test configuration from environment

    Returns:
        dict: Configuration values for tests
    """
    return {
        "rpc_url": os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com"),
        "chain_id": int(os.getenv("CHAIN_ID", "43113")),
        "identity_registry": os.getenv("IDENTITY_REGISTRY", "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"),
        "reputation_registry": os.getenv("REPUTATION_REGISTRY", "0x932d32194C7A47c0fe246C1d61caF244A4804C6a"),
        "validation_registry": os.getenv("VALIDATION_REGISTRY", "0x9aF4590035C109859B4163fd8f2224b820d11bc2"),
        "glue_token": os.getenv("GLUE_TOKEN_ADDRESS", "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"),
        "facilitator_url": os.getenv("FACILITATOR_URL", "https://facilitator.ultravioletadao.xyz"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
    }


# =============================================================================
# WALLET FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def test_private_key():
    """
    Generate a test private key (NOT for production use)

    Returns:
        str: Hex-encoded private key
    """
    # Generate random test wallet
    account = Account.create()
    return account.key.hex()


@pytest.fixture(scope="session")
def test_address(test_private_key):
    """
    Get address for test private key

    Returns:
        str: Checksummed Ethereum address
    """
    account = Account.from_key(test_private_key)
    return account.address


@pytest.fixture(scope="session")
def funded_test_key():
    """
    Get funded test wallet key (from env or generate)

    For integration tests that require gas/tokens.
    Set TEST_PRIVATE_KEY env var with funded wallet.

    Returns:
        str: Hex-encoded private key
    """
    key = os.getenv("TEST_PRIVATE_KEY")
    if not key:
        # Generate new wallet - user must fund it
        account = Account.create()
        return account.key.hex()
    return key


# =============================================================================
# WEB3 FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def w3(test_config):
    """
    Web3 instance connected to Fuji testnet

    Returns:
        Web3: Connected Web3 instance
    """
    w3_instance = Web3(Web3.HTTPProvider(test_config["rpc_url"]))
    assert w3_instance.is_connected(), "Failed to connect to Fuji RPC"
    return w3_instance


@pytest.fixture
def mock_w3():
    """
    Mock Web3 instance for unit tests

    Returns:
        Mock: Mock Web3 instance
    """
    mock = MagicMock()
    mock.eth.chain_id = 43113
    mock.is_connected.return_value = True
    mock.to_checksum_address = Web3.to_checksum_address
    mock.to_hex = Web3.to_hex
    mock.keccak = Web3.keccak
    return mock


# =============================================================================
# CONTRACT FIXTURES
# =============================================================================

@pytest.fixture
def mock_identity_registry():
    """
    Mock IdentityRegistry contract

    Returns:
        Mock: Mock contract instance
    """
    mock = MagicMock()
    mock.functions.register.return_value.transact.return_value = b"0x" + b"1" * 32
    mock.functions.getAgent.return_value.call.return_value = ("test-domain.xyz", 1, True)
    return mock


@pytest.fixture
def mock_reputation_registry():
    """
    Mock ReputationRegistry contract

    Returns:
        Mock: Mock contract instance
    """
    mock = MagicMock()
    mock.functions.rateServer.return_value.transact.return_value = b"0x" + b"1" * 32
    mock.functions.getServerRating.return_value.call.return_value = (True, 85)
    return mock


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_logs_data():
    """
    Sample Twitch logs data

    Returns:
        dict: Sample log data
    """
    import time
    return {
        "stream_id": "12345",
        "messages": [
            {
                "timestamp": int(time.time() - 3600),
                "user": "alice",
                "message": "Great stream!"
            },
            {
                "timestamp": int(time.time() - 3000),
                "user": "bob",
                "message": "PogChamp"
            },
            {
                "timestamp": int(time.time() - 2400),
                "user": "carol",
                "message": "Love this content"
            }
        ]
    }


@pytest.fixture
def sample_transcript_data():
    """
    Sample transcript data

    Returns:
        dict: Sample transcript
    """
    return {
        "stream_id": "67890",
        "transcript": "This is a sample transcript of the stream...",
        "duration": 7200,
        "language": "es",
        "segments": [
            {"start": 0, "end": 120, "text": "Introduction..."},
            {"start": 120, "end": 240, "text": "Main content..."}
        ]
    }


@pytest.fixture
def sample_agent_card():
    """
    Sample AgentCard data

    Returns:
        dict: AgentCard dictionary
    """
    return {
        "agentId": 1,
        "name": "Test Agent",
        "description": "Test agent for unit tests",
        "version": "1.0.0",
        "domain": "test-agent.ultravioletadao.xyz",
        "skills": [
            {
                "skillId": "test_skill",
                "name": "Test Skill",
                "description": "Test skill description",
                "price": {"amount": "0.01", "currency": "GLUE"},
                "inputSchema": {},
                "outputSchema": {},
                "endpoint": "/api/test_skill"
            }
        ],
        "trustModels": ["erc-8004"],
        "paymentMethods": ["x402-eip3009-GLUE"],
        "registrations": [
            {
                "contract": "IdentityRegistry",
                "address": "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618",
                "agentId": 1,
                "network": "avalanche-fuji:43113"
            }
        ]
    }


# =============================================================================
# PYTEST MARKERS
# =============================================================================

def pytest_configure(config):
    """
    Register custom pytest markers

    Markers:
    - unit: Fast unit tests with mocking (default)
    - integration: Integration tests requiring blockchain/network
    - slow: Tests that take >5 seconds
    - requires_funding: Tests requiring funded wallets
    - requires_openai: Tests requiring OpenAI API key
    """
    config.addinivalue_line("markers", "unit: Fast unit tests with mocking")
    config.addinivalue_line("markers", "integration: Integration tests requiring blockchain/network")
    config.addinivalue_line("markers", "slow: Tests that take more than 5 seconds")
    config.addinivalue_line("markers", "requires_funding: Tests requiring funded wallets")
    config.addinivalue_line("markers", "requires_openai: Tests requiring OpenAI API key")


# =============================================================================
# TEST HELPERS
# =============================================================================

@pytest.fixture
def assert_valid_tx_hash():
    """
    Helper to validate transaction hash format

    Returns:
        callable: Validation function
    """
    def _validate(tx_hash):
        assert isinstance(tx_hash, (str, bytes))
        if isinstance(tx_hash, str):
            assert tx_hash.startswith("0x")
            assert len(tx_hash) == 66  # 0x + 64 hex chars
        else:
            assert len(tx_hash) == 32  # 32 bytes
        return True
    return _validate
