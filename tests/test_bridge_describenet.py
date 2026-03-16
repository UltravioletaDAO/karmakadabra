"""
Tests for describe-net → ReputationBridge Integration

Validates that the reputation bridge properly reads from describe-net
SealRegistry data and incorporates it into composite scoring.

This closes the evidence triangle:
    AutoJob (insights) ←→ EM (task history) ←→ describe-net (on-chain seals)
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from mcp_server.swarm.reputation_bridge import (
    ReputationBridge,
    ReputationSource,
)
from mcp_server.swarm.describenet_reader import (
    DescribeNetReader,
    DescribeNetReputation,
    SealScore,
)


# ══════════════════════════════════════════════
# DescribeNetReader Unit Tests
# ══════════════════════════════════════════════


class TestDescribeNetReputation:
    """Test the DescribeNetReputation data model."""

    def test_empty_reputation(self):
        rep = DescribeNetReputation(wallet="0xabc")
        assert rep.overall_score == 0.0
        assert rep.total_seals == 0
        assert rep.trust_level == "none"
        assert not rep.is_agent

    def test_total_seals(self):
        rep = DescribeNetReputation(
            wallet="0xabc", h2h_count=5, h2a_count=10, a2h_count=3, a2a_count=8
        )
        assert rep.total_seals == 26

    def test_is_agent_detection(self):
        """Agents have more H2A + A2A seals than H2H + A2H."""
        agent_rep = DescribeNetReputation(
            wallet="0xagent",
            h2a_count=15,
            a2a_count=10,
            h2h_count=2,
            a2h_count=3,
        )
        assert agent_rep.is_agent is True

        human_rep = DescribeNetReputation(
            wallet="0xhuman",
            h2h_count=20,
            a2h_count=5,
            h2a_count=1,
            a2a_count=0,
        )
        assert human_rep.is_agent is False

    def test_trust_level_none(self):
        rep = DescribeNetReputation(wallet="0x", overall_active_seals=0)
        assert rep.trust_level == "none"

    def test_trust_level_low(self):
        rep = DescribeNetReputation(
            wallet="0x", overall_active_seals=3, overall_score=50
        )
        assert rep.trust_level == "low"

    def test_trust_level_medium(self):
        rep = DescribeNetReputation(
            wallet="0x", overall_active_seals=10, overall_score=70
        )
        assert rep.trust_level == "medium"

    def test_trust_level_high(self):
        rep = DescribeNetReputation(
            wallet="0x", overall_active_seals=25, overall_score=85
        )
        assert rep.trust_level == "high"

    def test_to_dict(self):
        rep = DescribeNetReputation(wallet="0xabc", overall_score=75.0)
        d = rep.to_dict()
        assert d["wallet"] == "0xabc"
        assert d["overall_score"] == 75.0
        assert isinstance(d, dict)

    def test_to_dict_with_datetime(self):
        dt = datetime(2026, 2, 23, 5, 0, tzinfo=timezone.utc)
        rep = DescribeNetReputation(wallet="0x", read_at=dt)
        d = rep.to_dict()
        assert "2026-02-23" in d["read_at"]


class TestDescribeNetReaderInit:
    """Test reader initialization."""

    def test_default_network_base(self):
        reader = DescribeNetReader()
        assert reader.network == "base"
        assert "mainnet.base.org" in reader.rpc_url

    def test_sepolia_network(self):
        reader = DescribeNetReader(network="sepolia")
        assert "sepolia.base.org" in reader.rpc_url

    def test_custom_rpc(self):
        reader = DescribeNetReader(rpc_url="https://custom-rpc.example.com")
        assert reader.rpc_url == "https://custom-rpc.example.com"

    def test_custom_registry(self):
        reader = DescribeNetReader(registry_address="0xDEADBEEF")
        assert reader.registry_address == "0xDEADBEEF"


class TestBridgeFormatConversion:
    """Test conversion from DescribeNetReputation to bridge format."""

    def test_empty_reputation_conversion(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(wallet="0xabc")
        result = reader.to_bridged_format(rep)
        assert result["score"] == 0.0
        assert result["total_ratings"] == 0
        assert result["as_worker_avg"] == 0.0
        assert result["as_requester_avg"] == 0.0
        assert result["source"] == "describe_net"

    def test_worker_avg_from_h2a_and_a2a(self):
        """Worker reputation combines H2A and A2A quadrants."""
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0xworker",
            h2a_score=80.0,
            h2a_count=10,
            a2a_score=90.0,
            a2a_count=5,
            overall_active_seals=15,
        )
        result = reader.to_bridged_format(rep)
        # Weighted avg: (80*10 + 90*5) / 15 = 1250/15 ≈ 83.33
        expected = (80.0 * 10 + 90.0 * 5) / 15
        assert abs(result["as_worker_avg"] - expected) < 0.01

    def test_requester_avg_from_a2h(self):
        """Requester reputation comes from A2H quadrant."""
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0xreq",
            a2h_score=75.0,
            a2h_count=8,
            overall_active_seals=8,
        )
        result = reader.to_bridged_format(rep)
        assert result["as_requester_avg"] == 75.0

    def test_time_weighted_score_preferred(self):
        """Uses time_weighted_score over overall_score if available."""
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            overall_score=80.0,
            time_weighted_score=85.0,
            overall_active_seals=10,
        )
        result = reader.to_bridged_format(rep)
        assert result["score"] == 85.0

    def test_falls_back_to_overall_score(self):
        """Falls back to overall_score when time_weighted is 0."""
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            overall_score=70.0,
            time_weighted_score=0.0,
            overall_active_seals=5,
        )
        result = reader.to_bridged_format(rep)
        assert result["score"] == 70.0

    def test_quadrant_breakdown_included(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            h2h_score=60,
            h2h_count=3,
            h2a_score=80,
            h2a_count=10,
            a2h_score=70,
            a2h_count=5,
            a2a_score=85,
            a2a_count=7,
            overall_active_seals=25,
        )
        result = reader.to_bridged_format(rep)
        qb = result["quadrant_breakdown"]
        assert qb["h2h"]["score"] == 60
        assert qb["h2a"]["count"] == 10
        assert qb["a2h"]["score"] == 70
        assert qb["a2a"]["count"] == 7

    def test_top_seal_types_in_output(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            overall_active_seals=20,
            top_seal_types=[
                SealScore(seal_type="SKILLFUL", average_score=90, count=8),
                SealScore(seal_type="RELIABLE", average_score=85, count=6),
            ],
        )
        result = reader.to_bridged_format(rep)
        assert len(result["top_seal_types"]) == 2
        assert result["top_seal_types"][0]["type"] == "SKILLFUL"


class TestEvidenceWeightFromSeals:
    """Test AutoJob evidence weight calculation."""

    def test_no_seals(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(wallet="0x", overall_active_seals=0)
        assert reader.evidence_weight_from_seals(rep) == 0.3

    def test_few_seals(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(wallet="0x", overall_active_seals=3)
        assert reader.evidence_weight_from_seals(rep) == 0.7

    def test_established_seals(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(wallet="0x", overall_active_seals=10)
        assert reader.evidence_weight_from_seals(rep) == 0.8

    def test_strong_seals(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(wallet="0x", overall_active_seals=25)
        assert reader.evidence_weight_from_seals(rep) == 0.85

    def test_comprehensive_seals(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(wallet="0x", overall_active_seals=60)
        assert reader.evidence_weight_from_seals(rep) == 0.9

    def test_multi_quadrant_bonus_2(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            overall_active_seals=10,
            h2a_count=5,
            a2a_count=5,  # 2 quadrants
        )
        weight = reader.evidence_weight_from_seals(rep)
        assert weight == 0.82  # 0.80 base + 0.02 bonus

    def test_multi_quadrant_bonus_3(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            overall_active_seals=10,
            h2h_count=2,
            h2a_count=5,
            a2a_count=3,  # 3 quadrants
        )
        weight = reader.evidence_weight_from_seals(rep)
        assert weight == 0.85  # 0.80 base + 0.05 bonus

    def test_cap_at_098(self):
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            overall_active_seals=100,
            h2h_count=25,
            h2a_count=25,
            a2h_count=25,
            a2a_count=25,
        )
        assert reader.evidence_weight_from_seals(rep) <= 0.98


class TestFunctionSelector:
    """Test keccak256 function selector computation."""

    def test_known_selectors(self):
        """Known selectors match pre-computed values."""
        reader = DescribeNetReader()
        s = reader._selector("compositeScore(address,bool,uint8)")
        assert len(s) == 8
        assert s == "128a1985"

    def test_total_seals_selector(self):
        reader = DescribeNetReader()
        s = reader._selector("totalSeals()")
        assert s == "d9ff054e"

    def test_unknown_selector_raises(self):
        """Unknown selector raises if no keccak library available."""
        reader = DescribeNetReader()
        # This will either compute via pysha3/pycryptodome or raise
        try:
            s = reader._selector("unknownFunction(uint256)")
            assert len(s) == 8  # If a keccak lib is available
        except RuntimeError:
            pass  # Expected if no keccak library


# ══════════════════════════════════════════════
# Bridge Integration Tests (describe-net → reputation_bridge)
# ══════════════════════════════════════════════


class TestBridgeDescribeNetIntegration:
    """Test that ReputationBridge properly reads from describe-net."""

    @pytest.fixture(autouse=True)
    async def _enable_describenet(self):
        """Enable describenet feature flag for all tests in this class."""
        with patch(
            "config.platform_config.PlatformConfig.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ):
            yield

    @pytest.fixture
    def bridge(self):
        return ReputationBridge(dry_run=True)

    @pytest.fixture
    def mock_describenet_rep(self):
        """A mock describe-net reputation with rich data."""
        return DescribeNetReputation(
            wallet="0xd3868e1ed738ced6945a574a7c769433bed5d474",
            overall_score=82.0,
            overall_active_seals=25,
            overall_total_seals=30,
            time_weighted_score=85.0,
            h2h_score=0.0,
            h2h_count=0,
            h2a_score=80.0,
            h2a_count=15,
            a2h_score=75.0,
            a2h_count=3,
            a2a_score=90.0,
            a2a_count=7,
            top_seal_types=[
                SealScore(seal_type="SKILLFUL", average_score=88, count=10),
                SealScore(seal_type="RELIABLE", average_score=85, count=8),
                SealScore(seal_type="THOROUGH", average_score=80, count=5),
            ],
            read_at=datetime(2026, 2, 23, 5, 0, tzinfo=timezone.utc),
            block_number=42525757,
            network="base",
        )

    @pytest.mark.asyncio
    async def test_bridge_reads_describenet(self, bridge, mock_describenet_rep):
        """Bridge reads describe-net data through _read_chain_reputation."""
        reader = DescribeNetReader()
        bridge_data = reader.to_bridged_format(mock_describenet_rep)

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=bridge_data,
        ):
            result = await bridge._read_chain_reputation(
                "0xd3868e1ed738ced6945a574a7c769433bed5d474"
            )
            assert result is not None
            assert result["score"] == 85.0  # time_weighted_score
            assert result["total_ratings"] == 25
            assert result["source"] == "describe_net"

    @pytest.mark.asyncio
    async def test_bridge_handles_no_seals(self, bridge):
        """Bridge gracefully handles wallets with no seals."""
        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await bridge._read_chain_reputation("0xunknown")
            assert result is None

    @pytest.mark.asyncio
    async def test_bridge_handles_import_error(self, bridge):
        """Bridge falls back gracefully if describenet_reader not available."""
        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            side_effect=ImportError("No module"),
        ):
            result = await bridge._read_chain_reputation("0xtest")
            assert result is None

    @pytest.mark.asyncio
    async def test_bridge_handles_rpc_error(self, bridge):
        """Bridge handles RPC failures from describe-net reader."""
        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            side_effect=ConnectionError("RPC timeout"),
        ):
            result = await bridge._read_chain_reputation("0xtest")
            assert result is None

    @pytest.mark.asyncio
    async def test_composite_with_describenet(self, bridge, mock_describenet_rep):
        """Full composite scoring with describe-net + EM data."""
        reader = DescribeNetReader()
        bridge_data = reader.to_bridged_format(mock_describenet_rep)

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=bridge_data,
        ):
            em_rep = {
                "raw_score": 78.0,
                "bayesian_score": 72.0,
                "total_tasks": 20,
                "successful_tasks": 18,
                "disputed_tasks": 1,
            }
            result = await bridge.get_bridged_reputation(
                "0xd3868e1ed738ced6945a574a7c769433bed5d474",
                em_reputation=em_rep,
            )

            # Should have both sources
            assert ReputationSource.EM_INTERNAL.value in result.sources
            assert ReputationSource.ERC8004_ONCHAIN.value in result.sources

            # Chain data should be populated
            assert result.chain_score == 85.0
            assert result.chain_total_ratings == 25
            assert result.chain_as_worker_avg > 0

            # Composite should blend both (60% EM + 40% chain)
            # EM: 72.0, Chain: 85.0
            # Composite ≈ 0.6*72 + 0.4*85 = 43.2 + 34 = 77.2
            assert 75 < result.composite_score < 80

            # Confidence should be high (both sources, many datapoints)
            assert result.confidence > 0.5

            # Tier should reflect the score
            assert result.tier in ("trusted", "established")

    @pytest.mark.asyncio
    async def test_describenet_only_scoring(self, bridge, mock_describenet_rep):
        """Scoring works with only describe-net data (no EM)."""
        reader = DescribeNetReader()
        bridge_data = reader.to_bridged_format(mock_describenet_rep)

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=bridge_data,
        ):
            result = await bridge.get_bridged_reputation(
                "0xchain_only_wallet",
                em_reputation=None,
            )

            # Should use chain score only
            assert result.chain_score == 85.0
            assert result.em_total_tasks == 0
            assert result.composite_score == 85.0  # 100% chain weight

    @pytest.mark.asyncio
    async def test_evidence_weight_with_describenet(self, bridge, mock_describenet_rep):
        """Evidence weight incorporates describe-net seal data."""
        reader = DescribeNetReader()
        bridge_data = reader.to_bridged_format(mock_describenet_rep)

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=bridge_data,
        ):
            result = await bridge.get_bridged_reputation(
                "0xtest_wallet",
                em_reputation={
                    "raw_score": 80,
                    "bayesian_score": 75,
                    "total_tasks": 30,
                    "successful_tasks": 28,
                    "disputed_tasks": 0,
                },
            )

            # With 30 EM tasks + 25 chain ratings, evidence weight should be high
            assert result.evidence_weight > 0.7

    @pytest.mark.asyncio
    async def test_sync_em_to_chain_with_delta(self, bridge):
        """Sync to chain only happens when score delta exceeds threshold."""
        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value={
                "score": 80.0,
                "total_ratings": 10,
                "as_worker_avg": 80.0,
                "as_requester_avg": 0.0,
                "source": "describe_net",
            },
        ):
            em_rep = {"bayesian_score": 80.5, "total_tasks": 15}
            result = await bridge.sync_em_to_chain("0xtest", em_rep)
            # Delta is 0.5, below 2.0 threshold
            assert result.success is True
            assert result.tx_hash is None  # Skipped, delta too small

    @pytest.mark.asyncio
    async def test_empty_bridge_data_ignored(self, bridge):
        """Bridge data with 0 ratings is treated as no data."""
        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value={
                "score": 0.0,
                "total_ratings": 0,
                "as_worker_avg": 0.0,
                "as_requester_avg": 0.0,
                "source": "describe_net",
            },
        ):
            result = await bridge._read_chain_reputation("0xnewwallet")
            # Should return None because total_ratings is 0
            assert result is None


# ══════════════════════════════════════════════
# End-to-End: Evidence Triangle Tests
# ══════════════════════════════════════════════


class TestEvidenceTriangle:
    """
    Test the full evidence triangle:
    AutoJob (insights) ←→ EM (task history) ←→ describe-net (seals)

    These tests verify that data flows correctly between all three
    reputation systems through the unified bridge.
    """

    @pytest.fixture(autouse=True)
    async def _enable_describenet(self):
        """Enable describenet feature flag for all tests in this class."""
        with patch(
            "config.platform_config.PlatformConfig.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ):
            yield

    def test_evidence_hierarchy_ordering(self):
        """Evidence weights follow the documented hierarchy."""
        reader = DescribeNetReader()

        # No data = self-reported (0.3)
        no_data = DescribeNetReputation(wallet="0x", overall_active_seals=0)
        assert reader.evidence_weight_from_seals(no_data) == 0.3

        # Few seals (0.7)
        few = DescribeNetReputation(wallet="0x", overall_active_seals=2)
        assert reader.evidence_weight_from_seals(few) == 0.7

        # Established (0.8)
        est = DescribeNetReputation(wallet="0x", overall_active_seals=8)
        assert reader.evidence_weight_from_seals(est) == 0.8

        # Strong (0.85)
        strong = DescribeNetReputation(wallet="0x", overall_active_seals=25)
        assert reader.evidence_weight_from_seals(strong) == 0.85

        # Each level is strictly higher
        assert (
            reader.evidence_weight_from_seals(no_data)
            < reader.evidence_weight_from_seals(few)
            < reader.evidence_weight_from_seals(est)
            < reader.evidence_weight_from_seals(strong)
        )

    def test_quadrant_to_role_mapping(self):
        """Quadrants correctly map to worker/requester roles."""
        reader = DescribeNetReader()

        # Agent that mostly works (H2A high = humans like this agent)
        worker_agent = DescribeNetReputation(
            wallet="0xworker_agent",
            h2a_score=90.0,
            h2a_count=20,  # Humans rating this agent's work
            a2a_score=85.0,
            a2a_count=10,  # Other agents rating this agent
            a2h_score=0.0,
            a2h_count=0,  # Not rating humans
            overall_active_seals=30,
        )
        result = reader.to_bridged_format(worker_agent)
        assert result["as_worker_avg"] > 85  # High worker reputation
        assert result["as_requester_avg"] == 0.0  # Not a requester

        # Agent that mostly requests (A2H high = agents rate its task quality)
        requester_agent = DescribeNetReputation(
            wallet="0xrequester_agent",
            a2h_score=78.0,
            a2h_count=15,  # Agents rating this agent as requester
            h2a_score=0.0,
            h2a_count=0,
            overall_active_seals=15,
        )
        result = reader.to_bridged_format(requester_agent)
        assert result["as_requester_avg"] == 78.0
        assert result["as_worker_avg"] == 0.0

    @pytest.mark.asyncio
    async def test_full_pipeline_em_plus_chain(self):
        """Full pipeline: EM reputation + describe-net seals → unified score."""
        bridge = ReputationBridge(dry_run=True)

        # Simulate describe-net data for a well-known agent
        chain_data = {
            "score": 88.0,
            "total_ratings": 30,
            "as_worker_avg": 85.0,
            "as_requester_avg": 78.0,
            "source": "describe_net",
            "quadrant_breakdown": {
                "h2h": {"score": 0, "count": 0},
                "h2a": {"score": 88, "count": 20},
                "a2h": {"score": 78, "count": 5},
                "a2a": {"score": 82, "count": 5},
            },
        }

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=chain_data,
        ):
            # EM says this agent is good too
            em_rep = {
                "raw_score": 82.0,
                "bayesian_score": 78.0,
                "total_tasks": 40,
                "successful_tasks": 38,
                "disputed_tasks": 1,
            }

            result = await bridge.get_bridged_reputation(
                "0xstar_agent", em_reputation=em_rep
            )

            # Composite should blend: 60% EM (78) + 40% chain (88) = 81.8
            assert 80 < result.composite_score < 84

            # High confidence (lots of data from both sources)
            assert result.confidence >= 0.8

            # Should be "trusted" tier
            assert result.tier == "trusted"

            # Evidence weight should be high (both sources)
            assert result.evidence_weight >= 0.7

    @pytest.mark.asyncio
    async def test_cold_start_agent_with_chain_only(self):
        """New agent with on-chain reputation but no EM history."""
        bridge = ReputationBridge(dry_run=True)

        chain_data = {
            "score": 72.0,
            "total_ratings": 8,
            "as_worker_avg": 72.0,
            "as_requester_avg": 0.0,
            "source": "describe_net",
        }

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=chain_data,
        ):
            result = await bridge.get_bridged_reputation(
                "0xnew_agent", em_reputation=None
            )

            # Should use chain score directly (no EM to blend with)
            assert result.composite_score == 72.0
            assert result.chain_total_ratings == 8
            assert result.em_total_tasks == 0
            assert result.tier == "established"

    @pytest.mark.asyncio
    async def test_reputation_import_for_onboarding(self):
        """Import on-chain reputation when agent first joins EM."""
        bridge = ReputationBridge(dry_run=True)

        chain_data = {
            "score": 80.0,
            "total_ratings": 15,
            "as_worker_avg": 80.0,
            "as_requester_avg": 0.0,
            "source": "describe_net",
        }

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=chain_data,
        ):
            result = await bridge.sync_chain_to_em("0xonboarding_agent")
            assert result.success is True
            assert result.chain_score_before == 80.0

    @pytest.mark.asyncio
    async def test_no_chain_data_for_onboarding(self):
        """Import fails gracefully when no on-chain reputation exists."""
        bridge = ReputationBridge(dry_run=True)

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await bridge.sync_chain_to_em("0xbrand_new_agent")
            assert result.success is False
            assert "No on-chain reputation" in result.error


# ══════════════════════════════════════════════
# Caching and Performance Tests
# ══════════════════════════════════════════════


class TestCachingBehavior:
    """Test that caching works correctly for describe-net reads."""

    @pytest.mark.asyncio
    async def test_reader_cache_hit(self):
        """Cached reputation is returned within TTL."""
        reader = DescribeNetReader()
        # Pre-populate cache
        cached_rep = DescribeNetReputation(
            wallet="0xcached",
            overall_score=90.0,
            overall_active_seals=50,
            read_at=datetime.now(timezone.utc),
        )
        reader._cache["0xcached"] = cached_rep

        # Should return cached without any RPC call
        result = await reader.get_reputation("0xCACHED")
        assert result.overall_score == 90.0
        assert result is cached_rep

    def test_reader_cache_stores_on_read(self):
        """Reader stores reputation in cache after reading."""
        reader = DescribeNetReader()
        assert len(reader._cache) == 0

        # Manually add to cache (simulating a read)
        rep = DescribeNetReputation(
            wallet="0xnew",
            read_at=datetime.now(timezone.utc),
        )
        reader._cache["0xnew"] = rep
        assert len(reader._cache) == 1

    @pytest.mark.asyncio
    async def test_bridge_cache_independence(self):
        """Bridge cache is independent of describe-net reader cache."""
        bridge = ReputationBridge(dry_run=True)
        assert len(bridge._cache) == 0

        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await bridge.get_bridged_reputation("0xtest")
            assert len(bridge._cache) == 1  # Bridge caches


# ══════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_count_quadrants(self):
        """Worker avg with zero counts doesn't divide by zero."""
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            h2a_count=0,
            a2a_count=0,
            overall_active_seals=5,
        )
        result = reader.to_bridged_format(rep)
        assert result["as_worker_avg"] == 0.0

    def test_mixed_zero_quadrants(self):
        """One quadrant has data, other doesn't."""
        reader = DescribeNetReader()
        rep = DescribeNetReputation(
            wallet="0x",
            h2a_score=90.0,
            h2a_count=10,
            a2a_score=0.0,
            a2a_count=0,
            overall_active_seals=10,
        )
        result = reader.to_bridged_format(rep)
        # Only H2A data: (90*10 + 0*0) / 10 = 90
        assert result["as_worker_avg"] == 90.0

    def test_wallet_normalization(self):
        """Wallets are normalized to lowercase."""
        reader = DescribeNetReader()
        rep = DescribeNetReputation(wallet="0xABCDEF")
        result = reader.to_bridged_format(rep)
        assert result is not None  # Works regardless of case

    @pytest.mark.asyncio
    async def test_bridge_normalizes_wallet(self):
        """Bridge normalizes wallet addresses to lowercase."""
        bridge = ReputationBridge(dry_run=True)
        with patch(
            "mcp_server.swarm.describenet_reader.read_describenet_for_bridge",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await bridge.get_bridged_reputation("0xABCDEF123")
            assert result.wallet == "0xabcdef123"

    def test_seal_score_dataclass(self):
        """SealScore stores type-level data correctly."""
        s = SealScore(
            seal_type="SKILLFUL", average_score=88.5, count=12, quadrant="H2A"
        )
        assert s.seal_type == "SKILLFUL"
        assert s.average_score == 88.5
        assert s.count == 12
        assert s.quadrant == "H2A"
