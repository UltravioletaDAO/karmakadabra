"""
EIP-8128 HTTP Message Signature Signer for KarmaCadabra Agents

Signs HTTP requests per ERC-8128 (Signed HTTP Requests with Ethereum)
so that the Execution Market server can authenticate agents by their
wallet address without API keys.

Produces three HTTP headers:
  - Content-Digest   (POST/PUT/PATCH with body only)
  - Signature-Input  (RFC 9421 structured field)
  - Signature        (65-byte secp256k1 signature, base64 in structured field)

The server verifier lives at mcp_server/integrations/erc8128/verifier.py.
This signer is its exact complement -- the signature base construction,
content digest format, and EIP-191 signing all mirror the verifier.

Reference:
  - ERC-8128: https://eip.tools/eip/8128
  - RFC 9421: https://www.rfc-editor.org/rfc/rfc9421
  - ERC-191:  https://eips.ethereum.org/EIPS/eip-191
"""

import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import urlparse

import requests
from eth_account import Account
from eth_account.messages import encode_defunct

logger = logging.getLogger("kk.eip8128_signer")

# Methods that carry a request body per HTTP semantics
_BODY_METHODS = {"POST", "PUT", "PATCH"}

# Default validity window in seconds (matches TypeScript signer and server max)
_DEFAULT_VALIDITY_SEC = 300


class EIP8128Signer:
    """Sign HTTP requests with EIP-8128 wallet-based authentication.

    The signer derives the wallet address from the private key and
    constructs RFC 9421-compliant signature base strings signed with
    EIP-191 personal_sign.

    Args:
        private_key: Hex-encoded Ethereum private key (with or without 0x prefix).
        chain_id: EVM chain ID for the keyid (default: 8453 = Base Mainnet).
        api_base: Base URL of the Execution Market API. Used for nonce fetching.
        validity_sec: Signature validity window in seconds (default: 60, max 300).
    """

    def __init__(
        self,
        private_key: str,
        chain_id: int = 8453,
        api_base: str = "https://api.execution.market",
        validity_sec: int = _DEFAULT_VALIDITY_SEC,
    ):
        self._account = Account.from_key(private_key)
        self._chain_id = chain_id
        self._api_base = api_base.rstrip("/")
        self._validity_sec = min(validity_sec, 300)  # Server max is 300s

    @property
    def address(self) -> str:
        """Wallet address (checksummed)."""
        return self._account.address

    @property
    def address_lower(self) -> str:
        """Wallet address (lowercase, as used in keyid)."""
        return self._account.address.lower()

    @property
    def keyid(self) -> str:
        """ERC-8128 keyid string: ``erc8128:<chainId>:<0xaddress>``."""
        return f"erc8128:{self._chain_id}:{self.address_lower}"

    def sign_request(
        self,
        method: str,
        url: str,
        body: str = "",
    ) -> dict[str, str]:
        """Sign an HTTP request and return the authentication headers.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.).
            url: Full request URL (e.g. ``https://api.execution.market/api/v1/tasks``).
            body: Request body string. Only relevant for POST/PUT/PATCH.

        Returns:
            Dictionary of headers to merge into the outgoing request:
            ``content-digest``, ``signature-input``, ``signature``.
            For GET/DELETE/HEAD (no body), ``content-digest`` is omitted.
        """
        method_upper = method.upper()
        parsed = urlparse(url)
        authority = parsed.netloc  # e.g. "api.execution.market"
        path = parsed.path or "/"

        # --- 1. Content-Digest (only for methods with a body) ----------------
        has_body = method_upper in _BODY_METHODS and len(body) > 0
        content_digest_value: str | None = None
        if has_body:
            content_digest_value = self._compute_content_digest(body)

        # --- 2. Covered components -------------------------------------------
        covered: list[str] = ["@method", "@authority", "@path"]
        if has_body:
            covered.append("content-digest")

        # --- 3. Signature parameters -----------------------------------------
        nonce, server_ttl = self._fetch_nonce()
        now = int(time.time())
        created = now
        validity = server_ttl if server_ttl else self._validity_sec
        expires = now + min(validity, 300)

        params: dict[str, object] = {
            "created": created,
            "expires": expires,
            "nonce": nonce,
            "keyid": self.keyid,
        }

        sig_params_str = self._build_signature_params(covered, params)

        # --- 4. Signature base (RFC 9421) ------------------------------------
        sig_base = self._build_signature_base(
            method=method_upper,
            authority=authority,
            path=path,
            content_digest_value=content_digest_value,
            covered=covered,
            sig_params_str=sig_params_str,
        )

        # --- 5. EIP-191 sign ------------------------------------------------
        sig_bytes = self._eip191_sign(sig_base)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        # --- 6. Build response headers ---------------------------------------
        headers: dict[str, str] = {}
        if content_digest_value is not None:
            headers["content-digest"] = content_digest_value
        headers["signature-input"] = f"eth={sig_params_str}"
        headers["signature"] = f"eth=:{sig_b64}:"

        return headers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_nonce(self) -> tuple[str, int | None]:
        """Fetch a fresh nonce from the server.

        Calls ``GET /api/v1/auth/erc8128/nonce`` on the Execution Market API.
        If the endpoint is unavailable (404, network error, etc.),
        falls back to a locally generated nonce.

        Returns:
            Tuple of (nonce_string, ttl_seconds). ttl_seconds is None when
            the server did not provide a TTL or the endpoint was unavailable.
        """
        nonce_url = f"{self._api_base}/api/v1/auth/erc8128/nonce"
        try:
            resp = requests.get(nonce_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                nonce = data.get("nonce")
                if nonce:
                    ttl = data.get("ttl_seconds")
                    return str(nonce), ttl if isinstance(ttl, int) else None
        except Exception as exc:
            logger.debug("Nonce endpoint unavailable (%s), using local nonce", exc)

        # Fallback: generate a locally unique nonce
        return secrets.token_urlsafe(24), None

    def _build_signature_base(
        self,
        method: str,
        authority: str,
        path: str,
        content_digest_value: str | None,
        covered: list[str],
        sig_params_str: str,
    ) -> str:
        """Build the RFC 9421 signature base string.

        This mirrors ``_build_signature_base()`` in the server verifier
        (``mcp_server/integrations/erc8128/verifier.py``).

        Format (each component on its own line, no trailing newline)::

            "@method": POST
            "@authority": api.execution.market
            "@path": /api/v1/tasks
            "content-digest": sha-256=:base64hash:
            "@signature-params": ("@method" ...);created=...;...

        Args:
            method: HTTP method (uppercase).
            authority: Request authority (host[:port]).
            path: Request path.
            content_digest_value: Full Content-Digest header value, or None.
            covered: List of covered component identifiers.
            sig_params_str: Pre-built @signature-params value string.

        Returns:
            The signature base string ready for EIP-191 signing.
        """
        lines: list[str] = []

        for component in covered:
            value = self._resolve_component(
                component, method, authority, path, content_digest_value
            )
            lines.append(f'"{component}": {value}')

        lines.append(f'"@signature-params": {sig_params_str}')

        return "\n".join(lines)

    @staticmethod
    def _resolve_component(
        component: str,
        method: str,
        authority: str,
        path: str,
        content_digest_value: str | None,
    ) -> str:
        """Resolve a single covered component's value.

        This mirrors ``_resolve_component()`` in the server verifier.
        """
        if component == "@method":
            return method.upper()
        if component == "@authority":
            return authority
        if component == "@path":
            return path
        if component == "content-digest":
            return content_digest_value or ""
        # Unknown component -- return empty string for forward compatibility
        return ""

    @staticmethod
    def _build_signature_params(covered: list[str], params: dict[str, object]) -> str:
        """Build the @signature-params structured field value.

        This mirrors ``_build_signature_params()`` in the server verifier.
        Parameter order: created, expires, nonce, keyid (then any extras
        sorted alphabetically).

        Returns:
            String like ``("@method" "@authority" "@path");created=N;expires=N;nonce="v";keyid="erc8128:..."``
        """
        comp_str = " ".join(f'"{c}"' for c in covered)
        parts: list[str] = [f"({comp_str})"]

        ordered_keys = ["created", "expires", "nonce", "keyid"]
        for key in ordered_keys:
            if key in params:
                parts.append(_format_param(key, params[key]))
        for key in sorted(params.keys()):
            if key not in ordered_keys:
                parts.append(_format_param(key, params[key]))

        return ";".join(parts)

    @staticmethod
    def _compute_content_digest(body: str) -> str:
        """Compute the Content-Digest header value for a request body.

        Format: ``sha-256=:base64(sha256(body)):``

        This mirrors ``_verify_content_digest()`` in the server verifier --
        the verifier expects the body hashed as raw bytes and the digest
        encoded in ``sha-256=:base64:`` format (RFC 9530).

        Args:
            body: The request body as a string.

        Returns:
            The full Content-Digest header value.
        """
        body_bytes = body.encode("utf-8")
        digest = hashlib.sha256(body_bytes).digest()
        b64 = base64.b64encode(digest).decode("ascii")
        return f"sha-256=:{b64}:"

    def _eip191_sign(self, message: str) -> bytes:
        """Sign a message with EIP-191 personal_sign.

        Per ERC-8128 Section 3.4.3::

            H = keccak256("\\x19Ethereum Signed Message:\\n" + len(M) + M)

        The server verifier uses ``encode_defunct(text=message)`` from
        eth_account, which produces the same EIP-191 prefix. We use the
        same function here for exact parity.

        Args:
            message: The signature base string to sign.

        Returns:
            65-byte signature (r[32] + s[32] + v[1]).
        """
        msg = encode_defunct(text=message)
        signed = self._account.sign_message(msg)
        return bytes(signed.signature)


def _format_param(key: str, value: object) -> str:
    """Format a single parameter for @signature-params.

    Integers are bare, everything else is quoted.
    Mirrors ``_format_param()`` in the server verifier.
    """
    if isinstance(value, int):
        return f"{key}={value}"
    return f'{key}="{value}"'


# ======================================================================
# Round-trip test
# ======================================================================

if __name__ == "__main__":
    import sys

    # Use a well-known test private key (Hardhat account #0)
    TEST_PK = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

    signer = EIP8128Signer(
        TEST_PK,
        chain_id=8453,
        api_base="https://api.execution.market",
    )

    print(f"Signer address: {signer.address}")
    print(f"Signer keyid:   {signer.keyid}")
    print()

    # --- Test 1: POST with body ---
    print("=== POST /api/v1/tasks (with body) ===")
    post_headers = signer.sign_request(
        "POST",
        "https://api.execution.market/api/v1/tasks",
        '{"title":"test","bounty_usd":0.10}',
    )
    for k, v in post_headers.items():
        print(f"  {k}: {v}")
    print()

    # --- Test 2: GET without body ---
    print("=== GET /api/v1/tasks/available (no body) ===")
    get_headers = signer.sign_request(
        "GET",
        "https://api.execution.market/api/v1/tasks/available",
    )
    for k, v in get_headers.items():
        print(f"  {k}: {v}")
    print()

    # --- Test 3: Verify round-trip with the server verifier ---
    print("=== Round-trip verification against server verifier ===")
    try:
        sys.path.insert(
            0,
            str(
                __import__("pathlib")
                .Path(__file__)
                .resolve()
                .parent.parent.parent.parent
                / "mcp_server"
            ),
        )
        import asyncio
        from integrations.erc8128.verifier import verify_erc8128_request, VerifyPolicy
        from integrations.erc8128.nonce_store import InMemoryNonceStore

        class _MockURL:
            def __init__(self, path: str, query: str, netloc: str):
                self.path = path
                self.query = query
                self.netloc = netloc

        class _MockRequest:
            def __init__(
                self, method: str, url: _MockURL, headers: dict, body_bytes: bytes
            ):
                self.method = method
                self.url = url
                self.headers = headers
                self._body = body_bytes

            async def body(self):
                return self._body

        async def _verify():
            store = InMemoryNonceStore()

            # POST with body
            body_str = '{"title":"roundtrip","bounty_usd":0.05}'
            headers = signer.sign_request(
                "POST",
                "https://api.execution.market/api/v1/tasks",
                body_str,
            )
            all_headers = {**headers}
            req = _MockRequest(
                method="POST",
                url=_MockURL(
                    path="/api/v1/tasks",
                    query="",
                    netloc="api.execution.market",
                ),
                headers=all_headers,
                body_bytes=body_str.encode("utf-8"),
            )
            result = await verify_erc8128_request(
                req,
                nonce_store=store,
                policy=VerifyPolicy(allow_replayable=False),
            )
            if result.ok:
                print(
                    f"  POST verify: PASS (address={result.address}, chain={result.chain_id})"
                )
            else:
                print(f"  POST verify: FAIL ({result.reason})")
                sys.exit(1)

            # GET without body
            get_hdrs = signer.sign_request(
                "GET",
                "https://api.execution.market/api/v1/tasks/available",
            )
            req2 = _MockRequest(
                method="GET",
                url=_MockURL(
                    path="/api/v1/tasks/available",
                    query="",
                    netloc="api.execution.market",
                ),
                headers=get_hdrs,
                body_bytes=b"",
            )
            result2 = await verify_erc8128_request(
                req2,
                nonce_store=store,
                policy=VerifyPolicy(allow_replayable=False),
            )
            if result2.ok:
                print(
                    f"  GET  verify: PASS (address={result2.address}, chain={result2.chain_id})"
                )
            else:
                print(f"  GET  verify: FAIL ({result2.reason})")
                sys.exit(1)

            print()
            print("All round-trip verifications passed.")

        asyncio.run(_verify())

    except ImportError as exc:
        print(f"  Skipping round-trip (import error: {exc})")
        print("  Run from project root with mcp_server deps installed to verify.")
