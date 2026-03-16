"""
Tests for TurnstileClient — MeshRelay premium channel access.

Tests both mocked (unit) and live (integration) scenarios.
Aligned with MeshRelay official SDK (Unified API, x402 accepts[] format).

Run with: pytest scripts/kk/tests/test_turnstile_client.py -v
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.turnstile_client import (
    AccessResult,
    ChannelInfo,
    HealthStatus,
    TurnstileClient,
    USDC_EIP712_DOMAIN,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TurnstileClient(base_url="http://localhost:8090")


@pytest.fixture
def unified_client():
    """Client configured for Unified API (production paths)."""
    return TurnstileClient(base_url="https://api.meshrelay.xyz")


@pytest.fixture
def mock_channels_response():
    return {
        "channels": [
            {
                "name": "#alpha-test",
                "price": "0.10",
                "currency": "USDC",
                "network": "eip155:8453",
                "durationSeconds": 1800,
                "maxSlots": 20,
                "activeSlots": 0,
                "description": "Alpha test channel",
            },
            {
                "name": "#kk-alpha",
                "price": "1.00",
                "currency": "USDC",
                "network": "eip155:8453",
                "durationSeconds": 3600,
                "maxSlots": 50,
                "activeSlots": 5,
                "description": "KK Alpha trading",
            },
        ]
    }


@pytest.fixture
def mock_health_response():
    return {
        "status": "ok",
        "irc": {"connected": True, "oper": True, "nick": "Turnstile"},
        "facilitator": {
            "url": "https://facilitator.ultravioletadao.xyz",
            "reachable": True,
        },
        "channels": 4,
        "uptime": 3600.0,
    }


@pytest.fixture
def mock_access_success():
    return {
        "status": "granted",
        "channel": "#alpha-test",
        "nick": "kk-coordinator",
        "expiresAt": "2026-02-22T05:30:00.000Z",
        "durationSeconds": 1800,
        "sessionId": 1,
    }


@pytest.fixture
def mock_access_402():
    """402 response with x402 accepts[] format (matches official SDK)."""
    return {
        "status": 402,
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "amount": "100000",
                "payTo": "0xe4dc963c56979E0260fc146b87eE24F18220e545",
            }
        ],
    }


@pytest.fixture
def mock_sessions_response():
    return {
        "sessions": [
            {
                "channel": "#alpha-test",
                "nick": "kk-coordinator",
                "expires_at": "2026-02-22T05:30:00.000Z",
                "session_id": 1,
            }
        ]
    }


# ---------------------------------------------------------------------------
# Unit Tests (Mocked)
# ---------------------------------------------------------------------------


class TestURLDetection:
    """Test auto-detection of URL prefix based on base_url."""

    def test_unified_api_prefix(self):
        client = TurnstileClient(base_url="https://api.meshrelay.xyz")
        assert client._prefix == "/payments"

    def test_direct_api_prefix(self):
        client = TurnstileClient(base_url="http://54.156.88.5:8090")
        assert client._prefix == "/api"

    def test_localhost_prefix(self):
        client = TurnstileClient(base_url="http://localhost:8090")
        assert client._prefix == "/api"

    def test_url_construction(self):
        client = TurnstileClient(base_url="https://api.meshrelay.xyz")
        assert client._url("/channels") == "https://api.meshrelay.xyz/payments/channels"
        assert client._url("/access/alpha-test") == "https://api.meshrelay.xyz/payments/access/alpha-test"

    def test_url_construction_direct(self):
        client = TurnstileClient(base_url="http://54.156.88.5:8090")
        assert client._url("/channels") == "http://54.156.88.5:8090/api/channels"


class TestEIP712Domain:
    """Test that EIP-712 domain constants match official SDK."""

    def test_domain_name(self):
        assert USDC_EIP712_DOMAIN["name"] == "USD Coin"

    def test_domain_version(self):
        assert USDC_EIP712_DOMAIN["version"] == "2"

    def test_domain_chain_id(self):
        assert USDC_EIP712_DOMAIN["chainId"] == 8453

    def test_domain_verifying_contract(self):
        assert USDC_EIP712_DOMAIN["verifyingContract"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_ok(self, client, mock_health_response):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_health_response)

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
            mock_session_cls.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())

            health = await client.check_health()
            assert health.ok is True
            assert health.irc_connected is True
            assert health.irc_oper is True
            assert health.facilitator_reachable is True
            assert health.channels_count == 4
            assert health.uptime == 3600.0

    @pytest.mark.asyncio
    async def test_health_error(self, client):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
            mock_session_cls.return_value.__aexit__ = AsyncMock()

            health = await client.check_health()
            assert health.ok is False
            assert "refused" in health.error.lower() or health.error != ""


class TestListChannels:
    @pytest.mark.asyncio
    async def test_list_channels(self, client, mock_channels_response):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_channels_response)
            mock_resp.raise_for_status = MagicMock()

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
            mock_session_cls.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())

            channels = await client.list_channels()
            assert len(channels) == 2
            assert channels[0].name == "#alpha-test"
            assert channels[0].price == "0.10"
            assert channels[0].price_float == 0.10
            assert channels[0].duration_seconds == 1800
            assert channels[0].is_available is True
            assert channels[0].channel_slug == "alpha-test"

            assert channels[1].name == "#kk-alpha"
            assert channels[1].active_slots == 5
            assert channels[1].available_slots == 45


class TestGetSessions:
    @pytest.mark.asyncio
    async def test_get_sessions(self, client, mock_sessions_response):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_sessions_response)

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
            mock_session_cls.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())

            sessions = await client.get_sessions("kk-coordinator")
            assert len(sessions) == 1
            assert sessions[0]["channel"] == "#alpha-test"
            assert sessions[0]["nick"] == "kk-coordinator"

    @pytest.mark.asyncio
    async def test_get_sessions_empty(self, client):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_resp = AsyncMock()
            mock_resp.status = 404

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
            mock_session_cls.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())

            sessions = await client.get_sessions("unknown-nick")
            assert sessions == []


class TestRequestAccess:
    @pytest.mark.asyncio
    async def test_access_success(self, client, mock_access_success):
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_access_success)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
            mock_session_cls.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())

            result = await client.request_access(
                channel="alpha-test",
                nick="kk-coordinator",
                payment_signature="base64sig==",
            )
            assert result.success is True
            assert result.channel == "#alpha-test"
            assert result.nick == "kk-coordinator"
            assert result.session_id == 1
            assert result.duration_seconds == 1800

    @pytest.mark.asyncio
    async def test_access_payment_required_accepts_format(self, client, mock_access_402):
        """Test 402 response with x402 accepts[] array format."""
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_resp = AsyncMock()
            mock_resp.status = 402
            mock_resp.json = AsyncMock(return_value=mock_access_402)

            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
            mock_session_cls.return_value = AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())

            result = await client.request_access(
                channel="alpha-test",
                nick="kk-coordinator",
                payment_signature="invalid",
            )
            assert result.success is False
            assert result.error == "Payment required"
            assert result.amount_raw == "100000"
            assert result.pay_to == "0xe4dc963c56979E0260fc146b87eE24F18220e545"
            assert result.network == "eip155:8453"


class TestChannelInfo:
    def test_channel_slug(self):
        ch = ChannelInfo(
            name="#kk-alpha",
            price="1.00",
            currency="USDC",
            network="eip155:8453",
            duration_seconds=3600,
            max_slots=50,
            active_slots=10,
            description="Test",
        )
        assert ch.channel_slug == "kk-alpha"
        assert ch.price_float == 1.0
        assert ch.available_slots == 40
        assert ch.is_available is True

    def test_channel_full(self):
        ch = ChannelInfo(
            name="#full",
            price="0.50",
            currency="USDC",
            network="eip155:8453",
            duration_seconds=1800,
            max_slots=5,
            active_slots=5,
            description="Full channel",
        )
        assert ch.is_available is False
        assert ch.available_slots == 0


class TestAccessResult:
    def test_default_values(self):
        r = AccessResult(success=True)
        assert r.channel == ""
        assert r.nick == ""
        assert r.session_id == 0
        assert r.error == ""

    def test_success_result(self):
        r = AccessResult(
            success=True,
            channel="#alpha-test",
            nick="test-nick",
            expires_at="2026-02-22T06:00:00Z",
            duration_seconds=1800,
            session_id=42,
        )
        assert r.success is True
        assert r.session_id == 42

    def test_error_result(self):
        r = AccessResult(
            success=False,
            channel="#alpha-test",
            error="Nick not connected to IRC",
        )
        assert r.success is False
        assert "not connected" in r.error


# ---------------------------------------------------------------------------
# Live Integration Tests (require Turnstile running)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not pytest.importorskip("aiohttp", reason="aiohttp not installed"),
    reason="aiohttp required",
)
class TestLiveIntegration:
    """Run against live Turnstile via Unified API. Skip if unreachable."""

    @pytest.fixture
    def live_client(self):
        return TurnstileClient()  # Default: https://api.meshrelay.xyz

    @pytest.mark.asyncio
    async def test_live_health(self, live_client):
        health = await live_client.check_health()
        if not health.ok:
            pytest.skip("Turnstile not reachable")
        # Unified API /health reports gateway status, not Turnstile IRC status.
        # IRC details may be absent when going through the proxy.
        assert health.ok is True
        assert health.uptime > 0

    @pytest.mark.asyncio
    async def test_live_list_channels(self, live_client):
        try:
            channels = await live_client.list_channels()
        except Exception:
            pytest.skip("Turnstile not reachable")
        assert len(channels) >= 1
        assert all(ch.name.startswith("#") for ch in channels)
        assert all(ch.currency == "USDC" for ch in channels)

    @pytest.mark.asyncio
    async def test_live_get_channel(self, live_client):
        try:
            ch = await live_client.get_channel("alpha-test")
        except Exception:
            pytest.skip("Turnstile not reachable")
        if ch is None:
            pytest.skip("alpha-test channel not configured")
        assert ch.name == "#alpha-test"
        assert ch.price_float == 0.10

    @pytest.mark.asyncio
    async def test_live_payment_requirements(self, live_client):
        try:
            reqs = await live_client.get_payment_requirements("alpha-test")
        except Exception:
            pytest.skip("Turnstile not reachable")
        if reqs is None:
            pytest.skip("Could not get payment requirements")
        # Verify x402 accepts[] format
        assert "accepts" in reqs
        accepts = reqs["accepts"]
        assert len(accepts) >= 1
        assert "payTo" in accepts[0]
        assert "amount" in accepts[0]
        assert "network" in accepts[0]

    @pytest.mark.asyncio
    async def test_live_sessions_unknown_nick(self, live_client):
        try:
            sessions = await live_client.get_sessions("nonexistent-nick-12345")
        except Exception:
            pytest.skip("Turnstile not reachable")
        assert isinstance(sessions, list)
