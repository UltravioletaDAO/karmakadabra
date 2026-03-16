"""
Tests for kk/monitoring/balance_monitor.py

Tests wallet discovery and balance checking logic without
requiring actual RPC calls. All network I/O is mocked.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.balance_monitor import (
    CHAIN_CONFIG,
    DEFAULT_THRESHOLD,
    check_all_balances,
    check_balance,
    discover_wallets,
    format_table,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspaces_dir(tmp_path):
    """Create a mock workspaces directory with wallet.json files."""
    agents = [
        {"name": "kk-alice", "address": "0xAlice0000000000000000000000000000000001"},
        {"name": "kk-bob", "address": "0xBob00000000000000000000000000000000002"},
        {"name": "kk-charlie", "address": "0xCharlie000000000000000000000000000003"},
    ]
    ws_dir = tmp_path / "workspaces"

    for agent in agents:
        agent_dir = ws_dir / agent["name"] / "data"
        agent_dir.mkdir(parents=True)
        wallet_file = agent_dir / "wallet.json"
        wallet_file.write_text(json.dumps({"address": agent["address"]}))

    return ws_dir


@pytest.fixture
def workspaces_dir_with_placeholders(tmp_path):
    """Create workspaces with placeholder wallets (should be skipped)."""
    ws_dir = tmp_path / "workspaces"

    # Real wallet
    real_dir = ws_dir / "kk-real" / "data"
    real_dir.mkdir(parents=True)
    (real_dir / "wallet.json").write_text(
        json.dumps({"address": "0xReal0000000000000000000000000000000001"})
    )

    # Placeholder wallet
    placeholder_dir = ws_dir / "kk-placeholder" / "data"
    placeholder_dir.mkdir(parents=True)
    (placeholder_dir / "wallet.json").write_text(
        json.dumps({"address": "0x_PLACEHOLDER_NOT_FUNDED"})
    )

    # No wallet
    no_wallet_dir = ws_dir / "kk-nowallet"
    no_wallet_dir.mkdir(parents=True)

    # Hidden dir (underscore prefix)
    hidden_dir = ws_dir / "_manifest.json"
    hidden_dir.mkdir(parents=True)

    return ws_dir


# ---------------------------------------------------------------------------
# Tests: discover_wallets
# ---------------------------------------------------------------------------


class TestDiscoverWallets:
    def test_discovers_all_agents(self, workspaces_dir):
        wallets = discover_wallets(workspaces_dir)
        assert len(wallets) == 3
        names = {w["name"] for w in wallets}
        assert names == {"kk-alice", "kk-bob", "kk-charlie"}

    def test_returns_addresses(self, workspaces_dir):
        wallets = discover_wallets(workspaces_dir)
        for w in wallets:
            assert w["address"].startswith("0x")

    def test_skips_placeholders(self, workspaces_dir_with_placeholders):
        wallets = discover_wallets(workspaces_dir_with_placeholders)
        assert len(wallets) == 1
        assert wallets[0]["name"] == "kk-real"

    def test_skips_missing_wallets(self, workspaces_dir_with_placeholders):
        wallets = discover_wallets(workspaces_dir_with_placeholders)
        names = {w["name"] for w in wallets}
        assert "kk-nowallet" not in names

    def test_skips_underscore_dirs(self, workspaces_dir_with_placeholders):
        wallets = discover_wallets(workspaces_dir_with_placeholders)
        names = {w["name"] for w in wallets}
        assert "_manifest.json" not in names

    def test_nonexistent_dir(self, tmp_path):
        wallets = discover_wallets(tmp_path / "nope")
        assert wallets == []

    def test_empty_dir(self, tmp_path):
        ws = tmp_path / "empty"
        ws.mkdir()
        wallets = discover_wallets(ws)
        assert wallets == []

    def test_sorted_by_name(self, workspaces_dir):
        wallets = discover_wallets(workspaces_dir)
        names = [w["name"] for w in wallets]
        assert names == sorted(names)

    def test_malformed_wallet_json(self, tmp_path):
        ws_dir = tmp_path / "workspaces"
        agent_dir = ws_dir / "kk-bad" / "data"
        agent_dir.mkdir(parents=True)
        (agent_dir / "wallet.json").write_text("not json")

        wallets = discover_wallets(ws_dir)
        assert len(wallets) == 0


# ---------------------------------------------------------------------------
# Tests: check_balance
# ---------------------------------------------------------------------------


class TestCheckBalance:
    @pytest.mark.asyncio
    async def test_parse_hex_balance(self):
        """Test parsing a hex balance response."""
        mock_client = AsyncMock()
        # 1.5 USDC = 1,500,000 = 0x16E360
        mock_client.post.return_value = AsyncMock(
            json=lambda: {"jsonrpc": "2.0", "result": "0x16E360", "id": 1}
        )

        balance = await check_balance(
            mock_client,
            "https://rpc.example.com",
            "0xUSDC",
            "0xWALLET",
        )
        assert balance == 1.5

    @pytest.mark.asyncio
    async def test_zero_balance(self):
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(
            json=lambda: {"jsonrpc": "2.0", "result": "0x0", "id": 1}
        )

        balance = await check_balance(
            mock_client, "https://rpc.example.com", "0xUSDC", "0xWALLET"
        )
        assert balance == 0.0

    @pytest.mark.asyncio
    async def test_empty_result(self):
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(
            json=lambda: {"jsonrpc": "2.0", "result": "0x", "id": 1}
        )

        balance = await check_balance(
            mock_client, "https://rpc.example.com", "0xUSDC", "0xWALLET"
        )
        assert balance == 0.0

    @pytest.mark.asyncio
    async def test_large_balance(self):
        mock_client = AsyncMock()
        # 1,000,000 USDC = 1e12 = 0xE8D4A51000
        mock_client.post.return_value = AsyncMock(
            json=lambda: {"jsonrpc": "2.0", "result": "0xE8D4A51000", "id": 1}
        )

        balance = await check_balance(
            mock_client, "https://rpc.example.com", "0xUSDC", "0xWALLET"
        )
        assert balance == 1_000_000.0

    @pytest.mark.asyncio
    async def test_rpc_failure_returns_none(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("connection timeout")

        balance = await check_balance(
            mock_client, "https://rpc.example.com", "0xUSDC", "0xWALLET"
        )
        assert balance is None

    @pytest.mark.asyncio
    async def test_correct_calldata_format(self):
        """Verify the balanceOf calldata is properly formatted."""
        mock_client = AsyncMock()
        mock_client.post.return_value = AsyncMock(
            json=lambda: {"jsonrpc": "2.0", "result": "0x0", "id": 1}
        )

        address = "0x1234567890abcdef1234567890abcdef12345678"
        await check_balance(mock_client, "https://rpc.example.com", "0xUSDC", address)

        call_args = mock_client.post.call_args
        params = call_args.kwargs.get("json", call_args[1].get("json", {}))
        call_data = params["params"][0]["data"]

        # Should start with balanceOf selector
        assert call_data.startswith("0x70a08231")
        # Should contain padded address (64 hex chars)
        addr_part = call_data[10:]  # After selector
        assert len(addr_part) == 64


# ---------------------------------------------------------------------------
# Tests: check_all_balances
# ---------------------------------------------------------------------------


class TestCheckAllBalances:
    @pytest.mark.asyncio
    async def test_report_structure(self):
        """Verify report contains all expected fields."""
        wallets = [{"name": "test", "address": "0x1234"}]

        with patch(
            "monitoring.balance_monitor.check_balance",
            new_callable=AsyncMock,
            return_value=1.0,
        ):
            report = await check_all_balances(wallets, ["base"], threshold=0.50)

        assert "timestamp" in report
        assert "chains" in report
        assert "threshold" in report
        assert "total_wallets" in report
        assert "wallets" in report
        assert "alerts" in report
        assert report["total_wallets"] == 1

    @pytest.mark.asyncio
    async def test_alert_on_low_balance(self):
        wallets = [{"name": "low-agent", "address": "0x1234"}]

        with patch(
            "monitoring.balance_monitor.check_balance",
            new_callable=AsyncMock,
            return_value=0.01,
        ):
            report = await check_all_balances(wallets, ["base"], threshold=0.50)

        assert report["alerts_count"] == 1
        assert "low-agent" in report["alerts"][0]

    @pytest.mark.asyncio
    async def test_no_alert_when_healthy(self):
        wallets = [{"name": "rich-agent", "address": "0x1234"}]

        with patch(
            "monitoring.balance_monitor.check_balance",
            new_callable=AsyncMock,
            return_value=100.0,
        ):
            report = await check_all_balances(wallets, ["base"], threshold=0.50)

        assert report["alerts_count"] == 0

    @pytest.mark.asyncio
    async def test_total_balance_across_chains(self):
        wallets = [{"name": "multi-chain", "address": "0x1234"}]

        with patch(
            "monitoring.balance_monitor.check_balance",
            new_callable=AsyncMock,
            return_value=5.0,
        ):
            report = await check_all_balances(
                wallets, ["base", "polygon"], threshold=0.50
            )

        # 5.0 on each chain = 10.0 total
        assert report["total_balance_usdc"] == 10.0


# ---------------------------------------------------------------------------
# Tests: format_table
# ---------------------------------------------------------------------------


class TestFormatTable:
    def test_includes_agent_name(self):
        report = {
            "timestamp": "2026-02-22T01:00:00Z",
            "chains": ["base"],
            "threshold": 0.50,
            "total_wallets": 1,
            "checked": 1,
            "total_balance_usdc": 1.5,
            "alerts_count": 0,
            "alerts": [],
            "wallets": [
                {
                    "name": "kk-alice",
                    "address": "0x1234",
                    "balances": {"base": 1.5},
                    "total": 1.5,
                    "alert": False,
                }
            ],
        }
        output = format_table(report)
        assert "kk-alice" in output
        assert "Balance Monitor" in output

    def test_shows_alert_marker(self):
        report = {
            "timestamp": "2026-02-22T01:00:00Z",
            "chains": ["base"],
            "threshold": 0.50,
            "total_wallets": 1,
            "checked": 1,
            "total_balance_usdc": 0.01,
            "alerts_count": 1,
            "alerts": ["kk-broke: $0.01 < $0.50"],
            "wallets": [
                {
                    "name": "kk-broke",
                    "address": "0x1234",
                    "balances": {"base": 0.01},
                    "total": 0.01,
                    "alert": True,
                }
            ],
        }
        output = format_table(report)
        assert "[!]" in output

    def test_no_alerts_message(self):
        report = {
            "timestamp": "2026-02-22T01:00:00Z",
            "chains": ["base"],
            "threshold": 0.50,
            "total_wallets": 0,
            "checked": 0,
            "total_balance_usdc": 0,
            "alerts_count": 0,
            "alerts": [],
            "wallets": [],
        }
        output = format_table(report)
        assert "No balance alerts" in output


# ---------------------------------------------------------------------------
# Tests: chain config
# ---------------------------------------------------------------------------


class TestChainConfig:
    def test_all_chains_have_rpc(self):
        for chain, config in CHAIN_CONFIG.items():
            assert "rpc" in config, f"{chain} missing rpc"
            assert config["rpc"].startswith("https://"), f"{chain} rpc not https"

    def test_all_chains_have_usdc(self):
        for chain, config in CHAIN_CONFIG.items():
            assert "usdc" in config, f"{chain} missing usdc"
            assert config["usdc"].startswith("0x"), f"{chain} usdc not an address"

    def test_known_chains(self):
        expected = {"base", "polygon", "arbitrum", "avalanche"}
        assert set(CHAIN_CONFIG.keys()) == expected

    def test_default_threshold(self):
        assert DEFAULT_THRESHOLD == 0.50
