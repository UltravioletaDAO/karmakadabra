"""
Karma Kadabra V2 — Turnstile Client (aligned with MeshRelay official SDK)

Python client for MeshRelay's Turnstile premium channel access.
Mirrors the official JS SDK at meshrelay/turnstile/sdk/TurnstileClient.js.

Two URL modes:
  - Unified API (production): https://api.meshrelay.xyz/payments/*
  - Turnstile direct (dev/testing): http://54.156.88.5:8090/api/*

The client auto-detects which path prefix to use based on the base_url.

EIP-3009 signing: Domain name MUST be "USD Coin" (not "USDC"), version "2".
This is specific to USDC on Base — signatures will fail with wrong domain.

Usage:
    from lib.turnstile_client import TurnstileClient

    # Production (Unified API)
    client = TurnstileClient()
    channels = await client.list_channels()

    # With payment (requires eth_account)
    result = await client.request_access_with_wallet(
        channel="alpha-test",
        nick="kk-coordinator",
        private_key="0x...",
    )
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger("kk.turnstile")

# Production URLs
UNIFIED_API_URL = "https://api.meshrelay.xyz"
TURNSTILE_DIRECT_URL = "http://54.156.88.5:8090"
FACILITATOR_URL = "https://facilitator.ultravioletadao.xyz"

# USDC on Base mainnet
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6
BASE_CHAIN_ID = 8453

# EIP-712 domain for USDC transferWithAuthorization on Base
# CRITICAL: name MUST be "USD Coin" (not "USDC"), version MUST be "2"
USDC_EIP712_DOMAIN = {
    "name": "USD Coin",
    "version": "2",
    "chainId": BASE_CHAIN_ID,
    "verifyingContract": USDC_BASE_ADDRESS,
}

# EIP-3009 TransferWithAuthorization type definition
TRANSFER_AUTH_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}

# Retry config
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0


@dataclass
class ChannelInfo:
    """Premium channel metadata from Turnstile."""

    name: str
    price: str
    currency: str
    network: str
    duration_seconds: int
    max_slots: int
    active_slots: int
    description: str

    @property
    def price_float(self) -> float:
        return float(self.price)

    @property
    def available_slots(self) -> int:
        return self.max_slots - self.active_slots

    @property
    def is_available(self) -> bool:
        return self.active_slots < self.max_slots

    @property
    def channel_slug(self) -> str:
        """Channel name without # prefix, for URL params."""
        return self.name.lstrip("#")


@dataclass
class AccessResult:
    """Result of a channel access request."""

    success: bool
    channel: str = ""
    nick: str = ""
    expires_at: str = ""
    duration_seconds: int = 0
    session_id: int = 0
    error: str = ""

    # Payment requirement info (when 402)
    price: str = ""
    currency: str = ""
    network: str = ""
    pay_to: str = ""
    amount_raw: str = ""  # Raw amount in token smallest unit


@dataclass
class HealthStatus:
    """Turnstile health status."""

    ok: bool
    irc_connected: bool = False
    irc_oper: bool = False
    facilitator_reachable: bool = False
    channels_count: int = 0
    uptime: float = 0.0
    error: str = ""


class TurnstileClient:
    """Client for MeshRelay Turnstile premium channel access.

    Aligned with the official JS SDK (turnstile/sdk/TurnstileClient.js).
    Supports both Unified API and direct Turnstile endpoints.
    """

    def __init__(
        self,
        base_url: str = UNIFIED_API_URL,
        facilitator_url: str = FACILITATOR_URL,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.facilitator_url = facilitator_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

        # Auto-detect path prefix based on URL
        # Unified API: /payments/channels, /payments/access/...
        # Direct Turnstile: /api/channels, /api/access/...
        if "api.meshrelay.xyz" in self.base_url:
            self._prefix = "/payments"
            self._health_url = f"{self.base_url}/health"
        else:
            self._prefix = "/api"
            self._health_url = f"{self.base_url}/health"

    def _url(self, path: str) -> str:
        """Build full URL with correct prefix."""
        return f"{self.base_url}{self._prefix}{path}"

    async def check_health(self) -> HealthStatus:
        """Check Turnstile service health."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self._health_url) as resp:
                    if resp.status != 200:
                        return HealthStatus(ok=False, error=f"HTTP {resp.status}")
                    data = await resp.json()
                    return HealthStatus(
                        ok=data.get("status") == "ok",
                        irc_connected=data.get("irc", {}).get("connected", False),
                        irc_oper=data.get("irc", {}).get("oper", False),
                        facilitator_reachable=data.get("facilitator", {}).get(
                            "reachable", False
                        ),
                        channels_count=data.get("channels", 0),
                        uptime=data.get("uptime", 0.0),
                    )
        except Exception as e:
            return HealthStatus(ok=False, error=str(e))

    async def list_channels(self) -> list[ChannelInfo]:
        """List all premium channels with pricing."""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(self._url("/channels")) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return [
                    ChannelInfo(
                        name=ch["name"],
                        price=ch["price"],
                        currency=ch["currency"],
                        network=ch["network"],
                        duration_seconds=ch["durationSeconds"],
                        max_slots=ch["maxSlots"],
                        active_slots=ch.get("activeSlots", 0),
                        description=ch.get("description", ""),
                    )
                    for ch in data.get("channels", [])
                ]

    async def get_channel(self, channel_name: str) -> ChannelInfo | None:
        """Get info for a specific channel. Returns None if not found."""
        channels = await self.list_channels()
        target = channel_name if channel_name.startswith("#") else f"#{channel_name}"
        for ch in channels:
            if ch.name == target:
                return ch
        return None

    async def get_sessions(self, nick: str) -> list[dict]:
        """Get active sessions for an IRC nick."""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(self._url(f"/sessions/{nick}")) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("sessions", [])

    async def get_payment_requirements(
        self, channel: str
    ) -> dict[str, Any] | None:
        """Get payment requirements for a channel (402 response).

        Sends a request without payment to get the x402 requirements:
        payTo address, amount, network, scheme.
        """
        slug = channel.lstrip("#")
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self._url(f"/access/{slug}"),
                    json={"nick": "price-check"},
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    if resp.status == 402:
                        return await resp.json()
                    return None
        except Exception:
            return None

    async def request_access(
        self,
        channel: str,
        nick: str,
        payment_signature: str,
    ) -> AccessResult:
        """Request access with a pre-signed payment signature.

        For most users, prefer request_access_with_wallet() which handles
        the full 402 → sign → pay flow automatically.
        """
        slug = channel.lstrip("#")

        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        self._url(f"/access/{slug}"),
                        json={"nick": nick},
                        headers={
                            "Content-Type": "application/json",
                            "Payment-Signature": payment_signature,
                        },
                    ) as resp:
                        data = await resp.json()

                        if resp.status == 200:
                            return AccessResult(
                                success=True,
                                channel=data.get("channel", f"#{slug}"),
                                nick=data.get("nick", nick),
                                expires_at=data.get("expiresAt", ""),
                                duration_seconds=data.get("durationSeconds", 0),
                                session_id=data.get("sessionId", 0),
                            )
                        elif resp.status == 402:
                            accepts = data.get("accepts", [{}])
                            req = accepts[0] if accepts else {}
                            return AccessResult(
                                success=False,
                                channel=f"#{slug}",
                                error="Payment required",
                                price=req.get("amount", ""),
                                currency="USDC",
                                network=req.get("network", ""),
                                pay_to=req.get("payTo", ""),
                                amount_raw=req.get("amount", ""),
                            )
                        else:
                            error_msg = data.get("error", data.get("message", f"HTTP {resp.status}"))
                            if attempt < MAX_RETRIES - 1 and resp.status >= 500:
                                wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                                logger.warning(
                                    f"Turnstile error (attempt {attempt + 1}): "
                                    f"{error_msg}. Retrying in {wait:.0f}s..."
                                )
                                await asyncio.sleep(wait)
                                continue
                            return AccessResult(
                                success=False,
                                channel=f"#{slug}",
                                error=error_msg,
                            )

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        f"Turnstile request failed (attempt {attempt + 1}): "
                        f"{e}. Retrying in {wait:.0f}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    return AccessResult(
                        success=False, channel=f"#{slug}", error=str(e)
                    )

        return AccessResult(success=False, error="Max retries exceeded")

    async def request_access_with_wallet(
        self,
        channel: str,
        nick: str,
        private_key: str,
    ) -> AccessResult:
        """Full flow: get 402 requirements → sign EIP-3009 → pay → get access.

        This mirrors the official JS SDK's requestAccess() method.
        Requires eth_account package.

        Args:
            channel: Channel name (e.g., "alpha-test" or "#alpha-test").
            nick: IRC nick (must be connected to irc.meshrelay.xyz).
            private_key: Hex private key of wallet with USDC on Base.
        """
        slug = channel.lstrip("#")

        # Step 1: Get payment requirements (402)
        reqs = await self.get_payment_requirements(slug)
        if not reqs:
            return AccessResult(
                success=False,
                channel=f"#{slug}",
                error="Could not get payment requirements (expected 402)",
            )

        accepts = reqs.get("accepts", [])
        if not accepts:
            return AccessResult(
                success=False,
                channel=f"#{slug}",
                error="No payment requirements in 402 response",
            )

        payment_req = accepts[0]
        pay_to = payment_req.get("payTo", "")
        amount = payment_req.get("amount", "0")
        network = payment_req.get("network", "eip155:8453")
        scheme = payment_req.get("scheme", "exact")

        if not pay_to:
            return AccessResult(
                success=False,
                channel=f"#{slug}",
                error="Missing payTo in payment requirements",
            )

        # Step 2: Sign EIP-3009 transferWithAuthorization
        payment_sig = sign_eip3009_payment(
            private_key=private_key,
            pay_to=pay_to,
            amount=amount,
            network=network,
            scheme=scheme,
        )

        # Step 3: Send payment
        logger.info(
            f"Signing EIP-3009 payment: {amount} raw USDC to {pay_to[:10]}..."
        )
        return await self.request_access(
            channel=slug,
            nick=nick,
            payment_signature=payment_sig,
        )


def sign_eip3009_payment(
    private_key: str,
    pay_to: str,
    amount: str,
    network: str = "eip155:8453",
    scheme: str = "exact",
) -> str:
    """Sign an EIP-3009 TransferWithAuthorization for USDC on Base.

    Produces a base64-encoded x402 payment payload matching the official
    MeshRelay Turnstile SDK format.

    CRITICAL: Uses domain name "USD Coin" (not "USDC") and version "2".

    Requires: pip install eth-account
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError:
        raise ImportError(
            "eth_account required for x402 payments: pip install eth-account"
        )

    account = Account.from_key(private_key)
    from_addr = account.address

    now_sec = int(time.time())
    nonce_bytes = os.urandom(32)
    nonce_hex = "0x" + nonce_bytes.hex()

    # Build EIP-712 typed data
    # NOTE: eth_account expects bytes for bytes32, not hex string
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": USDC_EIP712_DOMAIN,
        "message": {
            "from": from_addr,
            "to": pay_to,
            "value": int(amount),
            "validAfter": 0,
            "validBefore": now_sec + 3600,  # 1 hour validity
            "nonce": nonce_bytes,  # bytes, not hex string
        },
    }

    # Sign using the full_message parameter of encode_typed_data
    signable = encode_typed_data(full_message=typed_data)
    signed = Account.sign_message(signable, private_key=private_key)

    # Build x402 payload (matches official JS SDK format)
    # Authorization fields are strings for JSON serialization
    # Facilitator expects signature WITHOUT "0x" prefix
    sig_hex = signed.signature.hex()
    if sig_hex.startswith("0x"):
        sig_hex = sig_hex[2:]

    payload = {
        "x402Version": 1,
        "scheme": scheme,
        "network": network,
        "payload": {
            "signature": sig_hex,
            "authorization": {
                "from": from_addr,
                "to": pay_to,
                "value": str(amount),
                "validAfter": "0",
                "validBefore": str(now_sec + 3600),
                "nonce": nonce_hex,
            },
        },
        "userAddress": from_addr,
    }

    return base64.b64encode(json.dumps(payload).encode()).decode()


async def _demo():
    """Quick demo — list channels and check health."""
    client = TurnstileClient()

    print("=== Turnstile Health (Unified API) ===")
    health = await client.check_health()
    print(f"  Status: {'OK' if health.ok else f'ERROR: {health.error}'}")
    print(f"  IRC: connected={health.irc_connected}, oper={health.irc_oper}")
    print(f"  Facilitator: reachable={health.facilitator_reachable}")
    print(f"  Channels: {health.channels_count}")
    print(f"  Uptime: {health.uptime:.0f}s")

    print("\n=== Premium Channels ===")
    channels = await client.list_channels()
    for ch in channels:
        slots = f"{ch.active_slots}/{ch.max_slots}"
        duration = f"{ch.duration_seconds // 60}min"
        print(
            f"  {ch.name}: ${ch.price} {ch.currency} / {duration} "
            f"[{slots} slots] — {ch.description}"
        )

    print("\n=== Payment Requirements (#alpha-test) ===")
    reqs = await client.get_payment_requirements("alpha-test")
    if reqs:
        accepts = reqs.get("accepts", [{}])
        if accepts:
            r = accepts[0]
            print(f"  payTo: {r.get('payTo', '?')}")
            print(f"  amount: {r.get('amount', '?')} (raw)")
            print(f"  network: {r.get('network', '?')}")
            print(f"  scheme: {r.get('scheme', '?')}")
    else:
        print("  Could not retrieve (Turnstile may require connected nick)")


if __name__ == "__main__":
    asyncio.run(_demo())
