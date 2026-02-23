"""
Tests for kk/monitoring/health_check.py

Tests health check components without actual network calls.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.health_check import (
    HealthResult,
    check_daily_transactions,
    check_em_api,
    check_irc,
    check_wallet_balances,
    check_workspaces,
    run_health_check,
)


# ---------------------------------------------------------------------------
# Tests: HealthResult
# ---------------------------------------------------------------------------


class TestHealthResult:
    def test_empty_result_is_healthy(self):
        result = HealthResult()
        assert result.healthy is True

    def test_ok_check_keeps_healthy(self):
        result = HealthResult()
        result.add_check("test", "OK", "all good")
        assert result.healthy is True

    def test_warn_check_keeps_healthy(self):
        result = HealthResult()
        result.add_check("test", "WARN", "minor issue")
        assert result.healthy is True

    def test_fail_check_makes_unhealthy(self):
        result = HealthResult()
        result.add_check("test", "FAIL", "something broke")
        assert result.healthy is False

    def test_fail_generates_alert(self):
        result = HealthResult()
        result.add_check("api", "FAIL", "connection refused")
        assert len(result.alerts) == 1
        assert "[FAIL]" in result.alerts[0]
        assert "api" in result.alerts[0]

    def test_ok_no_alert(self):
        result = HealthResult()
        result.add_check("api", "OK", "healthy")
        assert len(result.alerts) == 0

    def test_multiple_checks(self):
        result = HealthResult()
        result.add_check("api", "OK", "healthy")
        result.add_check("irc", "WARN", "slow")
        result.add_check("wallets", "FAIL", "broke")
        assert result.healthy is False
        assert len(result.alerts) == 1

    def test_to_dict_structure(self):
        result = HealthResult()
        result.add_check("api", "OK", "healthy", {"status_code": 200})

        d = result.to_dict()
        assert d["healthy"] is True
        assert "timestamp" in d
        assert "checks" in d
        assert "alerts" in d
        assert d["checks"]["api"]["status"] == "OK"
        assert d["checks"]["api"]["data"]["status_code"] == 200

    def test_check_has_timestamp(self):
        result = HealthResult()
        result.add_check("test", "OK", "fine")
        assert "timestamp" in result.checks["test"]

    def test_mixed_ok_and_warn_healthy(self):
        result = HealthResult()
        result.add_check("a", "OK")
        result.add_check("b", "WARN")
        result.add_check("c", "OK")
        assert result.healthy is True


# ---------------------------------------------------------------------------
# Tests: check_em_api
# ---------------------------------------------------------------------------


class TestCheckEmApi:
    def _make_mock_client(self, get_return=None, get_side_effect=None):
        """Helper to create properly structured httpx.AsyncClient mock."""
        client = AsyncMock()
        if get_side_effect:
            client.get = AsyncMock(side_effect=get_side_effect)
        else:
            client.get = AsyncMock(return_value=get_return)
        # The key: make the instance itself work as an async context manager
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    @pytest.mark.asyncio
    async def test_api_healthy(self):
        result = HealthResult()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        cm = self._make_mock_client(get_return=mock_response)
        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            await check_em_api(result)

        assert "em_api" in result.checks
        assert result.checks["em_api"]["status"] == "OK"

    @pytest.mark.asyncio
    async def test_api_down(self):
        result = HealthResult()

        cm = self._make_mock_client(get_side_effect=Exception("connection refused"))
        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            await check_em_api(result)

        assert result.checks["em_api"]["status"] == "FAIL"

    @pytest.mark.asyncio
    async def test_api_500(self):
        result = HealthResult()
        mock_response = MagicMock()
        mock_response.status_code = 500

        cm = self._make_mock_client(get_return=mock_response)
        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            await check_em_api(result)

        assert result.checks["em_api"]["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Tests: check_irc
# ---------------------------------------------------------------------------


class TestCheckIrc:
    @pytest.mark.asyncio
    async def test_irc_connected(self):
        result = HealthResult()

        with patch("monitoring.health_check.socket.socket") as MockSocket:
            mock_sock = MagicMock()
            MockSocket.return_value = mock_sock

            await check_irc(result)

        assert result.checks["irc"]["status"] == "OK"

    @pytest.mark.asyncio
    async def test_irc_refused(self):
        result = HealthResult()

        with patch("monitoring.health_check.socket.socket") as MockSocket:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError("refused")
            MockSocket.return_value = mock_sock

            await check_irc(result)

        assert result.checks["irc"]["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Tests: check_workspaces
# ---------------------------------------------------------------------------


class TestCheckWorkspaces:
    @pytest.mark.asyncio
    async def test_valid_workspaces(self, tmp_path):
        result = HealthResult()
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir()

        # Create manifest
        manifest = {"total_agents": 2}
        (ws_dir / "_manifest.json").write_text(json.dumps(manifest))

        # Create agent dirs with SOUL.md
        for name in ["kk-alice", "kk-bob"]:
            agent_dir = ws_dir / name
            agent_dir.mkdir()
            (agent_dir / "SOUL.md").write_text(f"# {name}")

        await check_workspaces(result, ws_dir)

        assert result.checks["workspaces"]["status"] == "OK"

    @pytest.mark.asyncio
    async def test_missing_soul_files(self, tmp_path):
        result = HealthResult()
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir()

        manifest = {"total_agents": 2}
        (ws_dir / "_manifest.json").write_text(json.dumps(manifest))

        # Create dirs WITHOUT SOUL.md
        for name in ["kk-alice", "kk-bob"]:
            (ws_dir / name).mkdir()

        await check_workspaces(result, ws_dir)

        assert result.checks["workspaces"]["status"] == "WARN"

    @pytest.mark.asyncio
    async def test_missing_dir(self, tmp_path):
        result = HealthResult()
        await check_workspaces(result, tmp_path / "nonexistent")
        assert result.checks["workspaces"]["status"] == "FAIL"

    @pytest.mark.asyncio
    async def test_no_manifest(self, tmp_path):
        result = HealthResult()
        ws_dir = tmp_path / "workspaces"
        ws_dir.mkdir()

        await check_workspaces(result, ws_dir)
        assert result.checks["workspaces"]["status"] == "WARN"


# ---------------------------------------------------------------------------
# Tests: check_daily_transactions
# ---------------------------------------------------------------------------


class TestCheckDailyTransactions:
    def _make_mock_client(self, get_return=None, get_side_effect=None):
        client = AsyncMock()
        if get_side_effect:
            client.get = AsyncMock(side_effect=get_side_effect)
        else:
            client.get = AsyncMock(return_value=get_return)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    @pytest.mark.asyncio
    async def test_has_transactions(self):
        result = HealthResult()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tasks_today": 15}

        cm = self._make_mock_client(get_return=mock_response)
        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            await check_daily_transactions(result)

        assert result.checks["transactions"]["status"] == "OK"

    @pytest.mark.asyncio
    async def test_zero_transactions(self):
        result = HealthResult()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tasks_today": 0}

        cm = self._make_mock_client(get_return=mock_response)
        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            await check_daily_transactions(result)

        assert result.checks["transactions"]["status"] == "WARN"


# ---------------------------------------------------------------------------
# Tests: check_wallet_balances
# ---------------------------------------------------------------------------


class TestCheckWalletBalances:
    @pytest.mark.asyncio
    async def test_wallets_not_found(self, tmp_path):
        result = HealthResult()
        await check_wallet_balances(result, tmp_path / "nonexistent.json")
        assert result.checks["wallets"]["status"] == "WARN"

    @pytest.mark.asyncio
    async def test_healthy_wallets(self, tmp_path):
        result = HealthResult()

        wallets_file = tmp_path / "wallets.json"
        wallets_file.write_text(json.dumps({
            "wallets": [
                {"name": "agent-1", "address": "0x1234567890abcdef1234567890abcdef12345678"},
            ]
        }))

        # Mock the RPC call to return a healthy balance (10 USDC)
        mock_response = MagicMock()
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": "0x989680", "id": 1}

        client = AsyncMock()
        client.post = AsyncMock(return_value=mock_response)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            await check_wallet_balances(result, wallets_file)

        assert result.checks["wallets"]["status"] == "OK"

    @pytest.mark.asyncio
    async def test_skip_placeholder_wallets(self, tmp_path):
        result = HealthResult()

        wallets_file = tmp_path / "wallets.json"
        wallets_file.write_text(json.dumps({
            "wallets": [
                {"name": "agent-1", "address": "0x_PLACEHOLDER_NOT_FUNDED"},
            ]
        }))

        client = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            await check_wallet_balances(result, wallets_file)

        # Should not have called post (no valid wallets)
        assert result.checks["wallets"]["data"]["checked"] == 0


# ---------------------------------------------------------------------------
# Tests: run_health_check
# ---------------------------------------------------------------------------


class TestRunHealthCheck:
    @pytest.mark.asyncio
    async def test_specific_check(self, tmp_path):
        """Running with specific checks only runs those."""
        wallets = tmp_path / "wallets.json"
        workspaces = tmp_path / "workspaces"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        client = AsyncMock()
        client.get = AsyncMock(return_value=mock_response)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch("monitoring.health_check.httpx.AsyncClient", return_value=cm):
            result = await run_health_check(["api"], wallets, workspaces)

        assert "em_api" in result.checks
        assert "irc" not in result.checks
        assert "wallets" not in result.checks
