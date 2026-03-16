"""
Tests for ERC-8004 Live Bridge

Covers:
  - ABI encoding/decoding helpers
  - Identity resolution (wallet → agent ID)
  - Identity building from raw data
  - On-chain reputation construction
  - Cache operations (get, set, eviction, TTL)
  - Swarm batch queries
  - Identity summary generation
  - Cache persistence (save/load)
  - Integration with reputation_bridge
  - Error handling and graceful degradation
"""

import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.erc8004_live_bridge import (
    # Pure functions
    _encode_address,
    _encode_uint256,
    _decode_uint256,
    _decode_address,
    parse_balance_response,
    parse_owner_response,
    resolve_agent_id_from_wallet,
    build_identity_from_data,
    build_on_chain_reputation_from_identity,
    prepare_swarm_identity_queries,
    aggregate_swarm_identities,
    swarm_identity_summary,
    # Data classes
    AgentIdentity,
    BridgeConfig,
    CacheEntry,
    # Bridge class
    ERC8004LiveBridge,
    # Constants
    IDENTITY_REGISTRY,
    KK_AGENT_IDS,
    WALLET_TO_AGENT,
    SEL_BALANCE_OF,
)
from lib.reputation_bridge import (
    OnChainReputation,
    SealScore,
    compute_unified_reputation,
    compute_on_chain_score,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def bridge():
    """Bridge with default config (won't make real RPC calls in unit tests)."""
    return ERC8004LiveBridge(BridgeConfig(rpc_url="http://localhost:8545"))


# ===========================================================================
# Test: ABI Encoding / Decoding
# ===========================================================================

class TestABIEncoding:
    def test_encode_address(self):
        result = _encode_address("0xD3868E1eD738CED6945a574a7c769433BeD5d474")
        assert len(result) == 64
        assert result.endswith("d3868e1ed738ced6945a574a7c769433bed5d474")

    def test_encode_address_lowercase(self):
        result = _encode_address("0xd3868e1ed738ced6945a574a7c769433bed5d474")
        assert len(result) == 64

    def test_encode_uint256_zero(self):
        result = _encode_uint256(0)
        assert result == "0" * 64

    def test_encode_uint256_one(self):
        result = _encode_uint256(1)
        assert result == "0" * 63 + "1"

    def test_encode_uint256_large(self):
        result = _encode_uint256(2106)
        assert len(result) == 64
        assert _decode_uint256("0x" + result) == 2106

    def test_decode_uint256_zero(self):
        assert _decode_uint256("0x0") == 0
        assert _decode_uint256("0x" + "0" * 64) == 0

    def test_decode_uint256_one(self):
        assert _decode_uint256("0x1") == 1
        assert _decode_uint256("0x" + "0" * 63 + "1") == 1

    def test_decode_uint256_empty(self):
        assert _decode_uint256("") == 0
        assert _decode_uint256("0x") == 0
        assert _decode_uint256(None) == 0

    def test_decode_address(self):
        hex_word = "0x" + "0" * 24 + "d3868e1ed738ced6945a574a7c769433bed5d474"
        result = _decode_address(hex_word)
        assert result == "0xd3868e1ed738ced6945a574a7c769433bed5d474"

    def test_decode_address_zero(self):
        result = _decode_address("0x" + "0" * 64)
        assert result == "0x" + "0" * 40

    def test_decode_address_empty(self):
        result = _decode_address("")
        assert result == "0x" + "0" * 40

    def test_encode_decode_roundtrip(self):
        original = 18775
        encoded = _encode_uint256(original)
        decoded = _decode_uint256("0x" + encoded)
        assert decoded == original


# ===========================================================================
# Test: Balance Response Parsing
# ===========================================================================

class TestBalanceParsing:
    def test_parse_zero_balance(self):
        assert parse_balance_response("0x" + "0" * 64) == 0

    def test_parse_nonzero_balance(self):
        # 35 tokens
        hex_35 = "0x" + "0" * 62 + "23"
        assert parse_balance_response(hex_35) == 35

    def test_parse_one_balance(self):
        hex_1 = "0x" + "0" * 63 + "1"
        assert parse_balance_response(hex_1) == 1

    def test_parse_none_response(self):
        assert parse_balance_response(None) == 0

    def test_parse_empty_response(self):
        assert parse_balance_response("") == 0
        assert parse_balance_response("0x") == 0


# ===========================================================================
# Test: Owner Response Parsing
# ===========================================================================

class TestOwnerParsing:
    def test_parse_valid_owner(self):
        hex_owner = "0x" + "0" * 24 + "d3868e1ed738ced6945a574a7c769433bed5d474"
        result = parse_owner_response(hex_owner)
        assert result == "0xd3868e1ed738ced6945a574a7c769433bed5d474"

    def test_parse_zero_address(self):
        result = parse_owner_response("0x" + "0" * 64)
        assert result is None  # Zero address = not owned

    def test_parse_none(self):
        result = parse_owner_response(None)
        assert result is None


# ===========================================================================
# Test: Agent ID Resolution
# ===========================================================================

class TestAgentResolution:
    def test_resolve_known_platform_wallet(self):
        agent_id = resolve_agent_id_from_wallet(
            "0xD3868E1eD738CED6945a574a7c769433BeD5d474"
        )
        assert agent_id == 2106

    def test_resolve_known_coordinator_wallet(self):
        agent_id = resolve_agent_id_from_wallet(
            "0xe66C0a23E0721b77E22B6F0Ef30C8eAeB14B3e22"
        )
        assert agent_id == 18775

    def test_resolve_case_insensitive(self):
        agent_id = resolve_agent_id_from_wallet(
            "0xd3868e1ed738ced6945a574a7c769433bed5d474"
        )
        assert agent_id == 2106

    def test_resolve_unknown_wallet(self):
        agent_id = resolve_agent_id_from_wallet("0x" + "1" * 40)
        assert agent_id is None


# ===========================================================================
# Test: Identity Building
# ===========================================================================

class TestIdentityBuilding:
    def test_build_registered_identity(self):
        identity = build_identity_from_data(
            wallet="0xD3868E1eD738CED6945a574a7c769433BeD5d474",
            balance=5,
            known_agent_id=2106,
            token_uri="ipfs://QmZJaHCf123456",
            network="base",
        )
        assert identity.registered is True
        assert identity.token_count == 5
        assert identity.agent_id == 2106
        assert identity.metadata_url == "https://ipfs.io/ipfs/QmZJaHCf123456"

    def test_build_unregistered_identity(self):
        identity = build_identity_from_data(
            wallet="0x" + "a" * 40,
            balance=0,
            known_agent_id=None,
        )
        assert identity.registered is False
        assert identity.token_count == 0
        assert identity.agent_id == 0

    def test_build_identity_wallet_lowercased(self):
        identity = build_identity_from_data(
            wallet="0xABCD1234" + "0" * 32,
            balance=1,
            known_agent_id=None,
        )
        assert identity.wallet == ("0xabcd1234" + "0" * 32).lower()

    def test_build_identity_no_ipfs(self):
        identity = build_identity_from_data(
            wallet="0x" + "0" * 40,
            balance=1,
            known_agent_id=42,
            token_uri="https://example.com/metadata.json",
        )
        assert identity.token_uri == "https://example.com/metadata.json"
        assert identity.metadata_url == ""  # Only IPFS gets gateway URL

    def test_build_identity_no_token_uri(self):
        identity = build_identity_from_data(
            wallet="0x" + "0" * 40,
            balance=1,
            known_agent_id=None,
        )
        assert identity.token_uri == ""
        assert identity.metadata_url == ""


# ===========================================================================
# Test: On-Chain Reputation Building
# ===========================================================================

class TestOnChainReputation:
    def test_registered_without_seals(self):
        identity = AgentIdentity(
            wallet="0xd3868e1ed738ced6945a574a7c769433bed5d474",
            registered=True,
            agent_id=2106,
            token_count=5,
        )
        rep = build_on_chain_reputation_from_identity(identity)
        assert rep.composite_score == 55.0  # Slightly above neutral
        assert rep.confidence == 0.15
        assert rep.agent_id == 2106

    def test_unregistered_neutral(self):
        identity = AgentIdentity(
            wallet="0x" + "0" * 40,
            registered=False,
        )
        rep = build_on_chain_reputation_from_identity(identity)
        assert rep.composite_score == 50.0
        assert rep.confidence == 0.0

    def test_with_seal_data(self):
        now = datetime.now(timezone.utc)
        identity = AgentIdentity(
            wallet="0xd3868e",
            registered=True,
            agent_id=2106,
        )
        seals = [
            {"seal_type": "SKILLFUL", "quadrant": "A2H", "score": 90,
             "evaluator": "0x123", "timestamp": now.isoformat()},
            {"seal_type": "RELIABLE", "quadrant": "A2H", "score": 85,
             "evaluator": "0x456", "timestamp": now.isoformat()},
        ]
        rep = build_on_chain_reputation_from_identity(identity, seal_data=seals)
        assert rep.seal_count == 2
        assert rep.composite_score > 80  # High score from seals
        assert rep.confidence > 0

    def test_integration_with_unified_reputation(self):
        """Test that on-chain reputation flows into unified scoring."""
        identity = AgentIdentity(
            wallet="0xd3868e",
            registered=True,
            agent_id=2106,
        )
        on_chain = build_on_chain_reputation_from_identity(identity)

        unified = compute_unified_reputation(
            agent_name="test-agent",
            on_chain=on_chain,
        )
        assert unified.composite_score > 0
        assert "on_chain" in unified.sources_available


# ===========================================================================
# Test: Cache Operations
# ===========================================================================

class TestCacheOperations:
    def test_cache_entry_not_expired(self):
        entry = CacheEntry(data="test", timestamp=time.time(), ttl=300.0)
        assert entry.expired is False

    def test_cache_entry_expired(self):
        entry = CacheEntry(data="test", timestamp=time.time() - 400, ttl=300.0)
        assert entry.expired is True

    def test_bridge_cache_set_get(self, bridge):
        bridge._cache_set("key1", "value1")
        assert bridge._cache_get("key1") == "value1"

    def test_bridge_cache_miss(self, bridge):
        assert bridge._cache_get("nonexistent") is None

    def test_bridge_cache_expired(self, bridge):
        bridge._cache["key1"] = CacheEntry(
            data="old", timestamp=time.time() - 1000, ttl=300.0
        )
        assert bridge._cache_get("key1") is None

    def test_bridge_cache_eviction(self):
        config = BridgeConfig(cache_max_entries=3)
        bridge = ERC8004LiveBridge(config)

        bridge._cache_set("a", 1)
        bridge._cache_set("b", 2)
        bridge._cache_set("c", 3)
        bridge._cache_set("d", 4)  # Should evict oldest

        assert len(bridge._cache) == 3
        assert bridge._cache_get("d") == 4

    def test_bridge_clear_cache(self, bridge):
        bridge._cache_set("a", 1)
        bridge._cache_set("b", 2)
        count = bridge.clear_cache()
        assert count == 2
        assert len(bridge._cache) == 0


# ===========================================================================
# Test: Cache Persistence
# ===========================================================================

class TestCachePersistence:
    def test_save_and_load_cache(self, bridge, tmp_dir):
        identity = AgentIdentity(
            wallet="0xd3868e1ed738ced6945a574a7c769433bed5d474",
            registered=True,
            agent_id=2106,
            token_count=5,
            token_uri="ipfs://QmTest",
            metadata_url="https://ipfs.io/ipfs/QmTest",
            network="base",
        )
        bridge._cache_set("identity:0xd3868e", identity)

        path = tmp_dir / "cache.json"
        bridge.save_cache(path)
        assert path.exists()

        # Load into new bridge
        new_bridge = ERC8004LiveBridge()
        loaded = new_bridge.load_cache(path)
        assert loaded == 1

        cached = new_bridge._cache_get("identity:0xd3868e")
        assert cached is not None
        assert cached.wallet == identity.wallet
        assert cached.agent_id == 2106

    def test_load_nonexistent_cache(self, bridge, tmp_dir):
        loaded = bridge.load_cache(tmp_dir / "nonexistent.json")
        assert loaded == 0

    def test_load_corrupted_cache(self, bridge, tmp_dir):
        path = tmp_dir / "bad.json"
        path.write_text("not json{{{")
        loaded = bridge.load_cache(path)
        assert loaded == 0

    def test_save_skips_expired_entries(self, bridge, tmp_dir):
        bridge._cache["fresh"] = CacheEntry(
            data=AgentIdentity(wallet="0x1"),
            timestamp=time.time(),
            ttl=300.0,
        )
        bridge._cache["expired"] = CacheEntry(
            data=AgentIdentity(wallet="0x2"),
            timestamp=time.time() - 1000,
            ttl=300.0,
        )

        path = tmp_dir / "cache.json"
        bridge.save_cache(path)

        data = json.loads(path.read_text())
        assert "fresh" in data
        assert "expired" not in data


# ===========================================================================
# Test: Swarm Batch Operations
# ===========================================================================

class TestSwarmOperations:
    def test_prepare_queries(self):
        wallets = {
            "agent-1": "0xD3868E1eD738CED6945a574a7c769433BeD5d474",
            "agent-2": "0xe66C0a23E0721b77E22B6F0Ef30C8eAeB14B3e22",
        }
        queries = prepare_swarm_identity_queries(wallets)
        assert len(queries) == 2
        assert queries[0]["agent_name"] == "agent-1"
        assert queries[0]["call_data"].startswith(SEL_BALANCE_OF)

    def test_aggregate_identities(self):
        results = [
            ("agent-1", AgentIdentity(wallet="0x1", registered=True)),
            ("agent-2", AgentIdentity(wallet="0x2", registered=False)),
        ]
        agg = aggregate_swarm_identities(results)
        assert len(agg) == 2
        assert agg["agent-1"].registered is True
        assert agg["agent-2"].registered is False

    def test_swarm_summary(self):
        identities = {
            "a1": AgentIdentity(wallet="0x1", registered=True, agent_id=100, token_count=3),
            "a2": AgentIdentity(wallet="0x2", registered=True, agent_id=101, token_count=1),
            "a3": AgentIdentity(wallet="0x3", registered=False),
            "a4": AgentIdentity(wallet="0x4", registered=False, error="RPC failed"),
        }
        summary = swarm_identity_summary(identities)
        assert summary["total_agents"] == 4
        assert summary["registered_on_chain"] == 2
        assert summary["registration_rate"] == 0.5
        assert summary["with_known_agent_id"] == 2
        assert summary["query_errors"] == 1

    def test_swarm_summary_empty(self):
        summary = swarm_identity_summary({})
        assert summary["total_agents"] == 0
        assert summary["registration_rate"] == 0.0

    def test_swarm_summary_all_registered(self):
        identities = {
            f"agent-{i}": AgentIdentity(
                wallet=f"0x{i:040x}",
                registered=True,
                agent_id=i,
            )
            for i in range(10)
        }
        summary = swarm_identity_summary(identities)
        assert summary["registration_rate"] == 1.0
        assert summary["registered_on_chain"] == 10


# ===========================================================================
# Test: Bridge with Mocked RPC
# ===========================================================================

class TestBridgeWithMockedRPC:
    @patch("lib.erc8004_live_bridge._eth_call")
    def test_check_identity_registered(self, mock_eth_call):
        """Test identity check for a registered wallet."""
        mock_eth_call.return_value = "0x" + "0" * 63 + "5"  # balance = 5

        bridge = ERC8004LiveBridge()
        identity = bridge.check_identity(
            "0xD3868E1eD738CED6945a574a7c769433BeD5d474"
        )

        assert identity.registered is True
        assert identity.token_count == 5
        assert identity.agent_id == 2106  # Known wallet
        assert identity.error is None

    @patch("lib.erc8004_live_bridge._eth_call")
    def test_check_identity_not_registered(self, mock_eth_call):
        mock_eth_call.return_value = "0x" + "0" * 64  # balance = 0

        bridge = ERC8004LiveBridge()
        identity = bridge.check_identity("0x" + "a" * 40)

        assert identity.registered is False
        assert identity.token_count == 0

    @patch("lib.erc8004_live_bridge._eth_call")
    def test_check_identity_rpc_failure(self, mock_eth_call):
        mock_eth_call.return_value = None  # RPC failed

        bridge = ERC8004LiveBridge()
        identity = bridge.check_identity("0x" + "b" * 40)

        assert identity.registered is False
        assert identity.error == "RPC call failed"

    @patch("lib.erc8004_live_bridge._eth_call")
    def test_identity_cached(self, mock_eth_call):
        mock_eth_call.return_value = "0x" + "0" * 63 + "1"

        bridge = ERC8004LiveBridge()

        # First call hits RPC
        id1 = bridge.check_identity("0x" + "c" * 40)
        assert mock_eth_call.call_count == 1

        # Second call hits cache
        id2 = bridge.check_identity("0x" + "c" * 40)
        assert mock_eth_call.call_count == 1  # NOT called again
        assert id1.wallet == id2.wallet

    @patch("lib.erc8004_live_bridge._eth_call")
    def test_get_on_chain_reputation(self, mock_eth_call):
        mock_eth_call.return_value = "0x" + "0" * 63 + "3"

        bridge = ERC8004LiveBridge()
        rep = bridge.get_on_chain_reputation(
            "0xD3868E1eD738CED6945a574a7c769433BeD5d474"
        )

        assert isinstance(rep, OnChainReputation)
        assert rep.composite_score == 55.0  # Registered, no seals
        assert rep.agent_id == 2106

    @patch("lib.erc8004_live_bridge._eth_call")
    def test_query_swarm(self, mock_eth_call):
        mock_eth_call.return_value = "0x" + "0" * 63 + "1"

        bridge = ERC8004LiveBridge()
        wallets = {
            "agent-1": "0xD3868E1eD738CED6945a574a7c769433BeD5d474",
            "agent-2": "0xe66C0a23E0721b77E22B6F0Ef30C8eAeB14B3e22",
        }
        results = bridge.query_swarm(wallets)
        assert len(results) == 2
        assert results["agent-1"].registered is True
        assert results["agent-2"].registered is True

    @patch("lib.erc8004_live_bridge._eth_call")
    def test_get_swarm_summary(self, mock_eth_call):
        mock_eth_call.return_value = "0x" + "0" * 63 + "2"

        bridge = ERC8004LiveBridge()
        summary = bridge.get_swarm_summary({
            "coordinator": "0xD3868E1eD738CED6945a574a7c769433BeD5d474",
        })
        assert summary["total_agents"] == 1
        assert summary["registered_on_chain"] == 1


# ===========================================================================
# Test: AgentIdentity Serialization
# ===========================================================================

class TestIdentitySerialization:
    def test_to_dict(self):
        identity = AgentIdentity(
            wallet="0xd3868e1ed738ced6945a574a7c769433bed5d474",
            registered=True,
            agent_id=2106,
            token_count=5,
            token_uri="ipfs://QmTest",
            metadata_url="https://ipfs.io/ipfs/QmTest",
            network="base",
        )
        d = identity.to_dict()
        assert d["wallet"] == "0xd3868e1ed738ced6945a574a7c769433bed5d474"
        assert d["registered"] is True
        assert d["agent_id"] == 2106
        assert d["network"] == "base"

    def test_to_dict_with_error(self):
        identity = AgentIdentity(
            wallet="0x" + "0" * 40,
            error="RPC timeout",
        )
        d = identity.to_dict()
        assert d["error"] == "RPC timeout"

    def test_json_serializable(self):
        identity = AgentIdentity(
            wallet="0xabc",
            registered=True,
            agent_id=42,
        )
        # Should not raise
        json_str = json.dumps(identity.to_dict())
        loaded = json.loads(json_str)
        assert loaded["agent_id"] == 42


# ===========================================================================
# Test: Constants Integrity
# ===========================================================================

class TestConstants:
    def test_identity_registry_address(self):
        assert IDENTITY_REGISTRY.startswith("0x")
        assert len(IDENTITY_REGISTRY) == 42

    def test_kk_agent_ids_known(self):
        assert 2106 in KK_AGENT_IDS
        assert 18775 in KK_AGENT_IDS
        assert KK_AGENT_IDS[18775]["name"] == "kk-coordinator"

    def test_wallet_reverse_index_populated(self):
        assert len(WALLET_TO_AGENT) > 0
        # EM Platform wallet should resolve
        assert "0xd3868e1ed738ced6945a574a7c769433bed5d474" in WALLET_TO_AGENT

    def test_function_selectors_correct_length(self):
        assert SEL_BALANCE_OF.startswith("0x")
        assert len(SEL_BALANCE_OF) == 10  # "0x" + 8 hex chars
