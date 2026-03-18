"""
Tests for describe-net Chain Reader

Tests cover:
- DescribeNetReputation data model
- Score calculations and trust levels
- Evidence weight computation from seals
- Bridge format conversion
- Quadrant analysis (H2H, H2A, A2H, A2A)
- Cache behavior
- RPC call encoding
- Selector computation
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from lib.swarm.describenet_reader import (
    DescribeNetReader,
    DescribeNetReputation,
    SealScore,
    Quadrant,
    SEAL_TYPE_HASHES,
    QUADRANT_LABELS,
    read_describenet_for_bridge,
)


# ══════════════════════════════════════════════
# DescribeNetReputation Model
# ══════════════════════════════════════════════


class TestDescribeNetReputation:
    """Tests for the reputation data model."""

    def test_default_values(self):
        """New reputation has zeroed scores."""
        rep = DescribeNetReputation(wallet="0x1234")
        assert rep.overall_score == 0.0
        assert rep.overall_active_seals == 0
        assert rep.total_seals == 0
        assert rep.trust_level == "none"

    def test_total_seals_aggregation(self):
        """Total seals sums all quadrants."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            h2h_count=5,
            h2a_count=10,
            a2h_count=3,
            a2a_count=7,
        )
        assert rep.total_seals == 25

    def test_is_agent_detection(self):
        """Detects agents by quadrant distribution."""
        # Agent: mostly H2A + A2A seals
        agent = DescribeNetReputation(
            wallet="0xagent",
            h2a_count=15,
            a2a_count=10,
            h2h_count=0,
            a2h_count=2,
        )
        assert agent.is_agent

        # Human: mostly H2H + A2H seals
        human = DescribeNetReputation(
            wallet="0xhuman",
            h2h_count=10,
            a2h_count=8,
            h2a_count=1,
            a2a_count=0,
        )
        assert not human.is_agent

    def test_trust_level_none(self):
        """No seals = no trust."""
        rep = DescribeNetReputation(wallet="0x1234")
        assert rep.trust_level == "none"

    def test_trust_level_low(self):
        """Few seals = low trust."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            overall_active_seals=3,
            overall_score=70.0,
        )
        assert rep.trust_level == "low"

    def test_trust_level_medium(self):
        """Moderate seals + decent score = medium trust."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            overall_active_seals=10,
            overall_score=65.0,
        )
        assert rep.trust_level == "medium"

    def test_trust_level_high(self):
        """Many seals + high score = high trust."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            overall_active_seals=25,
            overall_score=85.0,
        )
        assert rep.trust_level == "high"

    def test_trust_level_high_seals_low_score(self):
        """Many seals but low score = not high trust."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            overall_active_seals=30,
            overall_score=50.0,
        )
        assert rep.trust_level != "high"

    def test_serialization(self):
        """Can serialize to dict."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            overall_score=75.0,
            read_at=datetime(2026, 2, 23, tzinfo=timezone.utc),
        )
        d = rep.to_dict()
        assert d["wallet"] == "0x1234"
        assert d["overall_score"] == 75.0
        assert isinstance(d["read_at"], str)

    def test_top_seal_types(self):
        """Top seal types stored correctly."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            top_seal_types=[
                SealScore(seal_type="SKILLFUL", average_score=85.0, count=10),
                SealScore(seal_type="RELIABLE", average_score=90.0, count=8),
            ],
        )
        assert len(rep.top_seal_types) == 2
        assert rep.top_seal_types[0].seal_type == "SKILLFUL"


# ══════════════════════════════════════════════
# Evidence Weight Computation
# ══════════════════════════════════════════════


class TestEvidenceWeight:
    """Tests for evidence weight from seal data."""

    def setup_method(self):
        self.reader = DescribeNetReader()

    def test_no_seals_weight(self):
        """Zero seals = self-reported weight."""
        rep = DescribeNetReputation(wallet="0x1234", overall_active_seals=0)
        assert self.reader.evidence_weight_from_seals(rep) == 0.3

    def test_few_seals_weight(self):
        """1-4 seals = some on-chain evidence."""
        rep = DescribeNetReputation(wallet="0x1234", overall_active_seals=3)
        assert self.reader.evidence_weight_from_seals(rep) == 0.70

    def test_moderate_seals_weight(self):
        """5-19 seals = established."""
        rep = DescribeNetReputation(wallet="0x1234", overall_active_seals=12)
        assert self.reader.evidence_weight_from_seals(rep) == 0.80

    def test_many_seals_weight(self):
        """20+ seals = strong evidence."""
        rep = DescribeNetReputation(wallet="0x1234", overall_active_seals=25)
        assert self.reader.evidence_weight_from_seals(rep) == 0.85

    def test_very_many_seals_weight(self):
        """50+ seals = comprehensive."""
        rep = DescribeNetReputation(wallet="0x1234", overall_active_seals=60)
        assert self.reader.evidence_weight_from_seals(rep) == 0.90

    def test_multi_quadrant_bonus(self):
        """Multiple quadrants increase evidence weight."""
        # Single quadrant
        single = DescribeNetReputation(
            wallet="0x1",
            overall_active_seals=25,
            h2a_count=25,
        )
        w_single = self.reader.evidence_weight_from_seals(single)

        # Two quadrants
        dual = DescribeNetReputation(
            wallet="0x2",
            overall_active_seals=25,
            h2a_count=15,
            a2a_count=10,
        )
        w_dual = self.reader.evidence_weight_from_seals(dual)

        # Three quadrants
        triple = DescribeNetReputation(
            wallet="0x3",
            overall_active_seals=25,
            h2a_count=10,
            a2a_count=10,
            h2h_count=5,
        )
        w_triple = self.reader.evidence_weight_from_seals(triple)

        assert w_dual > w_single
        assert w_triple > w_dual

    def test_evidence_weight_cap(self):
        """Evidence weight caps at 0.98."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            overall_active_seals=1000,
            h2a_count=300,
            a2a_count=300,
            h2h_count=200,
            a2h_count=200,
        )
        assert self.reader.evidence_weight_from_seals(rep) <= 0.98


# ══════════════════════════════════════════════
# Bridge Format Conversion
# ══════════════════════════════════════════════


class TestBridgeConversion:
    """Tests for converting to reputation bridge format."""

    def setup_method(self):
        self.reader = DescribeNetReader()

    def test_empty_reputation(self):
        """Empty reputation converts to zero scores."""
        rep = DescribeNetReputation(wallet="0x1234")
        bridge = self.reader.to_bridged_format(rep)
        assert bridge["score"] == 0.0
        assert bridge["total_ratings"] == 0
        assert bridge["source"] == "describe_net"

    def test_agent_reputation_conversion(self):
        """Agent reputation correctly maps quadrants to roles."""
        rep = DescribeNetReputation(
            wallet="0xagent",
            overall_score=80.0,
            overall_active_seals=30,
            time_weighted_score=78.0,
            h2a_score=85.0,
            h2a_count=15,
            a2a_score=75.0,
            a2a_count=10,
            a2h_score=70.0,
            a2h_count=5,
        )
        bridge = self.reader.to_bridged_format(rep)

        # Score uses time-weighted when available
        assert bridge["score"] == 78.0

        # Worker avg = weighted average of H2A and A2A
        expected_worker = (85.0 * 15 + 75.0 * 10) / 25
        assert abs(bridge["as_worker_avg"] - expected_worker) < 0.1

        # Requester avg = A2H score
        assert bridge["as_requester_avg"] == 70.0

        # Total ratings = active seals
        assert bridge["total_ratings"] == 30

    def test_uses_overall_score_when_no_time_weighted(self):
        """Falls back to overall score when time-weighted is 0."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            overall_score=72.0,
            time_weighted_score=0.0,
            overall_active_seals=10,
        )
        bridge = self.reader.to_bridged_format(rep)
        assert bridge["score"] == 72.0

    def test_quadrant_breakdown_included(self):
        """Bridge format includes quadrant breakdown."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            h2h_score=60.0,
            h2h_count=5,
            h2a_score=80.0,
            h2a_count=10,
        )
        bridge = self.reader.to_bridged_format(rep)
        assert "quadrant_breakdown" in bridge
        assert bridge["quadrant_breakdown"]["h2a"]["score"] == 80.0
        assert bridge["quadrant_breakdown"]["h2a"]["count"] == 10

    def test_top_seal_types_included(self):
        """Bridge format includes top seal types."""
        rep = DescribeNetReputation(
            wallet="0x1234",
            top_seal_types=[
                SealScore(seal_type="SKILLFUL", average_score=85.0, count=10),
            ],
        )
        bridge = self.reader.to_bridged_format(rep)
        assert len(bridge["top_seal_types"]) == 1
        assert bridge["top_seal_types"][0]["type"] == "SKILLFUL"

    def test_worker_avg_with_no_agent_seals(self):
        """Worker avg is 0 when no H2A or A2A seals."""
        rep = DescribeNetReputation(
            wallet="0xhuman",
            h2h_score=75.0,
            h2h_count=20,
        )
        bridge = self.reader.to_bridged_format(rep)
        assert bridge["as_worker_avg"] == 0.0


# ══════════════════════════════════════════════
# Reader Initialization & Cache
# ══════════════════════════════════════════════


class TestReaderInit:
    """Tests for reader initialization and configuration."""

    def test_default_base_mainnet(self):
        """Default network is Base mainnet."""
        reader = DescribeNetReader()
        assert reader.network == "base"
        assert "mainnet.base.org" in reader.rpc_url

    def test_sepolia_network(self):
        """Can configure for Base Sepolia."""
        reader = DescribeNetReader(network="sepolia")
        assert "sepolia.base.org" in reader.rpc_url

    def test_custom_rpc(self):
        """Can use custom RPC URL."""
        reader = DescribeNetReader(rpc_url="https://custom-rpc.example.com")
        assert reader.rpc_url == "https://custom-rpc.example.com"

    def test_custom_registry_address(self):
        """Can specify custom registry address."""
        addr = "0x1234567890abcdef1234567890abcdef12345678"
        reader = DescribeNetReader(registry_address=addr)
        assert reader.registry_address == addr

    @pytest.mark.asyncio
    async def test_cache_returns_recent(self):
        """Cache returns recent results without RPC calls."""
        reader = DescribeNetReader()

        # Manually populate cache
        cached_rep = DescribeNetReputation(
            wallet="0xtest",
            overall_score=80.0,
            read_at=datetime.now(timezone.utc),  # Just cached
        )
        reader._cache["0xtest"] = cached_rep

        result = await reader.get_reputation("0xtest")
        assert result.overall_score == 80.0

    @pytest.mark.asyncio
    async def test_cache_expires(self):
        """Cache expires after TTL."""
        reader = DescribeNetReader()

        # Cache entry from 10 minutes ago
        old_rep = DescribeNetReputation(
            wallet="0xtest",
            overall_score=80.0,
            read_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        reader._cache["0xtest"] = old_rep

        # Should make new RPC call (but contract is 0x0, so returns empty)
        result = await reader.get_reputation("0xtest")
        # With 0x0 contract, returns empty
        assert result.overall_score == 0.0


# ══════════════════════════════════════════════
# RPC Encoding
# ══════════════════════════════════════════════


class TestRPCEncoding:
    """Tests for ABI encoding of RPC calls."""

    def test_selector_lookup(self):
        """Known selectors are returned from lookup table."""
        reader = DescribeNetReader()
        # These should not raise
        sel = reader._selector("compositeScore(address,bool,uint8)")
        assert len(sel) == 8  # 4 bytes = 8 hex chars

    def test_selector_different_functions(self):
        """Different functions have different selectors."""
        reader = DescribeNetReader()
        sel1 = reader._selector("compositeScore(address,bool,uint8)")
        sel2 = reader._selector("totalSeals()")
        assert sel1 != sel2

    def test_unknown_selector_computed(self):
        """Unknown selector is computed via crypto library if available."""
        reader = DescribeNetReader()
        # Should either compute via pycryptodome/pysha3 or raise RuntimeError
        try:
            sel = reader._selector("unknownFunction(uint256)")
            assert len(sel) == 8  # 4 bytes = 8 hex chars
        except RuntimeError:
            pass  # Also acceptable if no crypto library


# ══════════════════════════════════════════════
# Constants & Configuration
# ══════════════════════════════════════════════


class TestConstants:
    """Tests for module constants and configuration."""

    def test_seal_types_count(self):
        """All 13 seal types defined."""
        assert len(SEAL_TYPE_HASHES) == 13

    def test_seal_type_hash_length(self):
        """Each seal type hash is 32 bytes."""
        for name, h in SEAL_TYPE_HASHES.items():
            assert len(h) == 32, f"{name} hash is {len(h)} bytes, expected 32"

    def test_quadrant_labels(self):
        """All 4 quadrants have labels."""
        assert len(QUADRANT_LABELS) == 4
        assert Quadrant.H2H in QUADRANT_LABELS
        assert Quadrant.A2A in QUADRANT_LABELS

    def test_quadrant_int_values(self):
        """Quadrant values match Solidity enum ordering."""
        assert int(Quadrant.H2H) == 0
        assert int(Quadrant.H2A) == 1
        assert int(Quadrant.A2H) == 2
        assert int(Quadrant.A2A) == 3

    def test_half_life_default(self):
        """Default half-life is 90 days."""
        reader = DescribeNetReader()
        assert reader.DEFAULT_HALF_LIFE == 90 * 24 * 3600


# ══════════════════════════════════════════════
# Integration: read_describenet_for_bridge()
# ══════════════════════════════════════════════


class TestBridgeIntegration:
    """Tests for the convenience bridge integration function."""

    @pytest.mark.asyncio
    async def test_returns_none_for_no_data(self):
        """Returns None when wallet has no seals."""
        result = await read_describenet_for_bridge("0xempty")
        assert result is None

    @pytest.mark.asyncio
    async def test_with_custom_reader(self):
        """Accepts custom reader instance."""
        reader = DescribeNetReader(network="sepolia")
        result = await read_describenet_for_bridge("0xtest", reader=reader)
        assert result is None  # No deployed contract

    @pytest.mark.asyncio
    async def test_returns_dict_with_data(self):
        """Returns bridge-format dict when seals exist."""
        reader = DescribeNetReader()

        # Mock the get_reputation to return data
        mock_rep = DescribeNetReputation(
            wallet="0xrich",
            overall_score=85.0,
            overall_active_seals=20,
            time_weighted_score=82.0,
            h2a_score=88.0,
            h2a_count=12,
            a2a_score=80.0,
            a2a_count=8,
            read_at=datetime.now(timezone.utc),
        )
        reader._cache["0xrich"] = mock_rep

        with patch(
            "config.platform_config.PlatformConfig.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await read_describenet_for_bridge("0xrich", reader=reader)
        assert result is not None
        assert result["score"] == 82.0
        assert result["total_ratings"] == 20
        assert result["source"] == "describe_net"


# ══════════════════════════════════════════════
# Quadrant Analysis
# ══════════════════════════════════════════════


class TestQuadrantAnalysis:
    """Tests for quadrant-specific reputation analysis."""

    def setup_method(self):
        self.reader = DescribeNetReader()

    def test_agent_identity_from_quadrants(self):
        """Can determine if wallet is agent or human from seal distribution."""
        # AI agent: rated by humans (H2A) and other agents (A2A)
        ai_agent = DescribeNetReputation(
            wallet="0xbot",
            h2a_score=90.0,
            h2a_count=50,
            a2a_score=85.0,
            a2a_count=30,
            h2h_count=0,
            a2h_count=5,
        )
        assert ai_agent.is_agent

        # Human worker: rated by humans (H2H) and agents (A2H)
        human = DescribeNetReputation(
            wallet="0xhuman",
            h2h_score=75.0,
            h2h_count=40,
            a2h_score=80.0,
            a2h_count=20,
            h2a_count=0,
            a2a_count=0,
        )
        assert not human.is_agent

    def test_worker_score_weighting(self):
        """Worker score weights H2A and A2A by count."""
        rep = DescribeNetReputation(
            wallet="0xworker",
            h2a_score=90.0,
            h2a_count=30,  # 90 * 30 = 2700
            a2a_score=70.0,
            a2a_count=10,  # 70 * 10 = 700
        )
        bridge = self.reader.to_bridged_format(rep)
        # Expected: (2700 + 700) / 40 = 85.0
        assert abs(bridge["as_worker_avg"] - 85.0) < 0.1

    def test_requester_score_from_a2h(self):
        """Requester reputation comes from A2H quadrant."""
        rep = DescribeNetReputation(
            wallet="0xrequester",
            a2h_score=92.0,
            a2h_count=15,
        )
        bridge = self.reader.to_bridged_format(rep)
        assert bridge["as_requester_avg"] == 92.0

    def test_symmetric_evaluation(self):
        """Wallet can be both worker and requester."""
        rep = DescribeNetReputation(
            wallet="0xboth",
            h2a_score=85.0,
            h2a_count=20,  # Worker rating
            a2h_score=78.0,
            a2h_count=10,  # Requester rating
        )
        bridge = self.reader.to_bridged_format(rep)
        assert bridge["as_worker_avg"] == 85.0
        assert bridge["as_requester_avg"] == 78.0
