"""
Tests for lib/eip8128_signer.py — EIP-8128 HTTP Message Signature Signer

Covers:
  - Signer initialization and properties
  - Content digest computation
  - Signature params formatting
  - Signature base construction (RFC 9421)
  - Sign request (POST with body, GET without body)
  - Nonce fetching and fallback
  - Round-trip signing and verification
  - Edge cases and error handling
"""

import base64
import hashlib
import json
import secrets
import time
from unittest.mock import MagicMock, patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.eip8128_signer import EIP8128Signer, _format_param


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

# Hardhat account #0 — well-known deterministic key for testing
TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TEST_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
TEST_ADDRESS_LOWER = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"

# Hardhat account #1
TEST_PRIVATE_KEY_2 = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"


@pytest.fixture
def signer():
    """Create a signer with mocked nonce endpoint."""
    with patch("lib.eip8128_signer.requests") as mock_requests:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "nonce": "test-nonce-abc123",
            "ttl_seconds": 300,
        }
        mock_requests.get.return_value = mock_resp

        s = EIP8128Signer(
            TEST_PRIVATE_KEY,
            chain_id=8453,
            api_base="https://api.execution.market",
            validity_sec=60,
        )
        yield s


@pytest.fixture
def signer_no_mock():
    """Create a signer without mocking (nonce fetching will hit real network)."""
    return EIP8128Signer(
        TEST_PRIVATE_KEY,
        chain_id=8453,
        api_base="https://api.execution.market",
        validity_sec=60,
    )


# ═══════════════════════════════════════════════════════════════════
# TestSignerInit — Constructor and properties
# ═══════════════════════════════════════════════════════════════════


class TestSignerInit:
    """Signer initialization and basic properties."""

    def test_address_from_private_key(self, signer):
        assert signer.address == TEST_ADDRESS

    def test_address_lower(self, signer):
        assert signer.address_lower == TEST_ADDRESS_LOWER

    def test_keyid_format(self, signer):
        expected = f"erc8128:8453:{TEST_ADDRESS_LOWER}"
        assert signer.keyid == expected

    def test_custom_chain_id(self):
        with patch("lib.eip8128_signer.requests"):
            s = EIP8128Signer(TEST_PRIVATE_KEY, chain_id=1)
        assert s.keyid == f"erc8128:1:{TEST_ADDRESS_LOWER}"

    def test_validity_capped_at_300(self):
        with patch("lib.eip8128_signer.requests"):
            s = EIP8128Signer(TEST_PRIVATE_KEY, validity_sec=999)
        assert s._validity_sec == 300

    def test_validity_under_cap(self):
        with patch("lib.eip8128_signer.requests"):
            s = EIP8128Signer(TEST_PRIVATE_KEY, validity_sec=60)
        assert s._validity_sec == 60

    def test_api_base_trailing_slash_stripped(self):
        with patch("lib.eip8128_signer.requests"):
            s = EIP8128Signer(
                TEST_PRIVATE_KEY, api_base="https://api.example.com/"
            )
        assert s._api_base == "https://api.example.com"

    def test_key_without_0x_prefix(self):
        with patch("lib.eip8128_signer.requests"):
            s = EIP8128Signer(TEST_PRIVATE_KEY[2:])  # strip 0x
        assert s.address == TEST_ADDRESS

    def test_different_key_different_address(self):
        with patch("lib.eip8128_signer.requests"):
            s = EIP8128Signer(TEST_PRIVATE_KEY_2)
        assert s.address != TEST_ADDRESS


# ═══════════════════════════════════════════════════════════════════
# TestContentDigest — SHA-256 body hashing
# ═══════════════════════════════════════════════════════════════════


class TestContentDigest:
    """Content-Digest header computation."""

    def test_format(self, signer):
        digest = signer._compute_content_digest('{"test": true}')
        assert digest.startswith("sha-256=:")
        assert digest.endswith(":")

    def test_deterministic(self, signer):
        body = '{"title":"test","bounty_usd":0.10}'
        d1 = signer._compute_content_digest(body)
        d2 = signer._compute_content_digest(body)
        assert d1 == d2

    def test_different_bodies_different_digests(self, signer):
        d1 = signer._compute_content_digest("body1")
        d2 = signer._compute_content_digest("body2")
        assert d1 != d2

    def test_correct_sha256(self, signer):
        body = "hello world"
        expected_hash = hashlib.sha256(body.encode("utf-8")).digest()
        expected_b64 = base64.b64encode(expected_hash).decode("ascii")
        expected = f"sha-256=:{expected_b64}:"
        assert signer._compute_content_digest(body) == expected

    def test_empty_body(self, signer):
        digest = signer._compute_content_digest("")
        # SHA-256 of empty string is well-known
        empty_hash = hashlib.sha256(b"").digest()
        empty_b64 = base64.b64encode(empty_hash).decode("ascii")
        assert digest == f"sha-256=:{empty_b64}:"

    def test_unicode_body(self, signer):
        digest = signer._compute_content_digest('{"name":"José"}')
        assert "sha-256=:" in digest


# ═══════════════════════════════════════════════════════════════════
# TestFormatParam — Structured field parameter formatting
# ═══════════════════════════════════════════════════════════════════


class TestFormatParam:
    """_format_param helper function."""

    def test_integer_bare(self):
        assert _format_param("created", 1234567890) == "created=1234567890"

    def test_string_quoted(self):
        assert _format_param("nonce", "abc123") == 'nonce="abc123"'

    def test_keyid_quoted(self):
        result = _format_param("keyid", "erc8128:8453:0xabc")
        assert result == 'keyid="erc8128:8453:0xabc"'

    def test_zero_integer(self):
        assert _format_param("created", 0) == "created=0"

    def test_empty_string(self):
        assert _format_param("nonce", "") == 'nonce=""'


# ═══════════════════════════════════════════════════════════════════
# TestSignatureParams — @signature-params construction
# ═══════════════════════════════════════════════════════════════════


class TestSignatureParams:
    """Signature parameters structured field construction."""

    def test_basic_get_components(self, signer):
        covered = ["@method", "@authority", "@path"]
        params = {
            "created": 1000,
            "expires": 1300,
            "nonce": "testnonce",
            "keyid": "erc8128:8453:0xabc",
        }
        result = signer._build_signature_params(covered, params)
        assert result.startswith('("@method" "@authority" "@path")')
        assert "created=1000" in result
        assert "expires=1300" in result
        assert 'nonce="testnonce"' in result
        assert 'keyid="erc8128:8453:0xabc"' in result

    def test_with_content_digest_component(self, signer):
        covered = ["@method", "@authority", "@path", "content-digest"]
        params = {"created": 1000, "expires": 1300, "nonce": "n", "keyid": "k"}
        result = signer._build_signature_params(covered, params)
        assert '"content-digest"' in result

    def test_ordered_params(self, signer):
        """Parameters should be in order: created, expires, nonce, keyid."""
        covered = ["@method"]
        params = {
            "keyid": "k",
            "nonce": "n",
            "expires": 2,
            "created": 1,
        }
        result = signer._build_signature_params(covered, params)
        parts = result.split(";")
        # First part is components, then created, expires, nonce, keyid
        assert "created=1" in parts[1]
        assert "expires=2" in parts[2]
        assert 'nonce="n"' in parts[3]
        assert 'keyid="k"' in parts[4]

    def test_extra_params_sorted(self, signer):
        covered = ["@method"]
        params = {
            "created": 1,
            "expires": 2,
            "nonce": "n",
            "keyid": "k",
            "zebra": "z",
            "alpha": "a",
        }
        result = signer._build_signature_params(covered, params)
        parts = result.split(";")
        # After the 4 standard params, extras should be alpha, zebra
        assert 'alpha="a"' in parts[5]
        assert 'zebra="z"' in parts[6]


# ═══════════════════════════════════════════════════════════════════
# TestSignatureBase — RFC 9421 signature base string
# ═══════════════════════════════════════════════════════════════════


class TestSignatureBase:
    """Signature base string construction per RFC 9421."""

    def test_get_request_base(self, signer):
        base = signer._build_signature_base(
            method="GET",
            authority="api.execution.market",
            path="/api/v1/tasks",
            content_digest_value=None,
            covered=["@method", "@authority", "@path"],
            sig_params_str='("@method" "@authority" "@path");created=1;expires=2;nonce="n";keyid="k"',
        )
        lines = base.split("\n")
        assert '"@method": GET' in lines[0]
        assert '"@authority": api.execution.market' in lines[1]
        assert '"@path": /api/v1/tasks' in lines[2]
        assert '"@signature-params":' in lines[3]

    def test_post_request_base_includes_digest(self, signer):
        digest = "sha-256=:abc123=:"
        base = signer._build_signature_base(
            method="POST",
            authority="api.execution.market",
            path="/api/v1/tasks",
            content_digest_value=digest,
            covered=["@method", "@authority", "@path", "content-digest"],
            sig_params_str="test-params",
        )
        assert f'"content-digest": {digest}' in base

    def test_no_trailing_newline(self, signer):
        base = signer._build_signature_base(
            method="GET",
            authority="example.com",
            path="/",
            content_digest_value=None,
            covered=["@method"],
            sig_params_str="test",
        )
        assert not base.endswith("\n")

    def test_components_on_separate_lines(self, signer):
        base = signer._build_signature_base(
            method="GET",
            authority="example.com",
            path="/test",
            content_digest_value=None,
            covered=["@method", "@authority", "@path"],
            sig_params_str="params",
        )
        lines = base.split("\n")
        # 3 components + 1 @signature-params = 4 lines
        assert len(lines) == 4


# ═══════════════════════════════════════════════════════════════════
# TestResolveComponent — Component value resolution
# ═══════════════════════════════════════════════════════════════════


class TestResolveComponent:
    """_resolve_component static method."""

    def test_method(self):
        result = EIP8128Signer._resolve_component(
            "@method", "POST", "example.com", "/", None
        )
        assert result == "POST"

    def test_method_uppercase(self):
        result = EIP8128Signer._resolve_component(
            "@method", "get", "example.com", "/", None
        )
        assert result == "GET"

    def test_authority(self):
        result = EIP8128Signer._resolve_component(
            "@authority", "POST", "api.execution.market", "/", None
        )
        assert result == "api.execution.market"

    def test_path(self):
        result = EIP8128Signer._resolve_component(
            "@path", "POST", "example.com", "/api/v1/tasks", None
        )
        assert result == "/api/v1/tasks"

    def test_content_digest(self):
        digest = "sha-256=:abc=:"
        result = EIP8128Signer._resolve_component(
            "content-digest", "POST", "example.com", "/", digest
        )
        assert result == digest

    def test_content_digest_none(self):
        result = EIP8128Signer._resolve_component(
            "content-digest", "POST", "example.com", "/", None
        )
        assert result == ""

    def test_unknown_component(self):
        result = EIP8128Signer._resolve_component(
            "x-custom", "POST", "example.com", "/", None
        )
        assert result == ""


# ═══════════════════════════════════════════════════════════════════
# TestNonceFetching — Nonce endpoint interaction
# ═══════════════════════════════════════════════════════════════════


class TestNonceFetching:
    """Nonce fetching from server with fallback."""

    def test_successful_nonce_fetch(self):
        with patch("lib.eip8128_signer.requests") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "nonce": "server-nonce-xyz",
                "ttl_seconds": 120,
            }
            mock_req.get.return_value = mock_resp

            s = EIP8128Signer(TEST_PRIVATE_KEY)
            nonce, ttl = s._fetch_nonce()
            assert nonce == "server-nonce-xyz"
            assert ttl == 120

    def test_nonce_fetch_404_falls_back(self):
        with patch("lib.eip8128_signer.requests") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_req.get.return_value = mock_resp

            s = EIP8128Signer(TEST_PRIVATE_KEY)
            nonce, ttl = s._fetch_nonce()
            assert isinstance(nonce, str)
            assert len(nonce) > 0
            assert ttl is None

    def test_nonce_fetch_network_error_falls_back(self):
        with patch("lib.eip8128_signer.requests") as mock_req:
            mock_req.get.side_effect = ConnectionError("Connection refused")

            s = EIP8128Signer(TEST_PRIVATE_KEY)
            nonce, ttl = s._fetch_nonce()
            assert isinstance(nonce, str)
            assert len(nonce) > 0
            assert ttl is None

    def test_nonce_fetch_empty_nonce_falls_back(self):
        with patch("lib.eip8128_signer.requests") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"nonce": "", "ttl_seconds": 60}
            mock_req.get.return_value = mock_resp

            s = EIP8128Signer(TEST_PRIVATE_KEY)
            nonce, ttl = s._fetch_nonce()
            assert isinstance(nonce, str)
            assert len(nonce) > 0  # Generated fallback nonce

    def test_nonce_fetch_no_ttl(self):
        with patch("lib.eip8128_signer.requests") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"nonce": "no-ttl-nonce"}
            mock_req.get.return_value = mock_resp

            s = EIP8128Signer(TEST_PRIVATE_KEY)
            nonce, ttl = s._fetch_nonce()
            assert nonce == "no-ttl-nonce"
            assert ttl is None

    def test_nonce_fetch_string_ttl_returns_none(self):
        with patch("lib.eip8128_signer.requests") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "nonce": "typed-ttl",
                "ttl_seconds": "not-an-int",
            }
            mock_req.get.return_value = mock_resp

            s = EIP8128Signer(TEST_PRIVATE_KEY)
            nonce, ttl = s._fetch_nonce()
            assert nonce == "typed-ttl"
            assert ttl is None

    def test_nonce_url_uses_api_base(self):
        with patch("lib.eip8128_signer.requests") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_req.get.return_value = mock_resp

            s = EIP8128Signer(
                TEST_PRIVATE_KEY, api_base="https://custom.api.com"
            )
            s._fetch_nonce()
            mock_req.get.assert_called_once_with(
                "https://custom.api.com/api/v1/auth/erc8128/nonce", timeout=5
            )


# ═══════════════════════════════════════════════════════════════════
# TestSignRequest — Full request signing flow
# ═══════════════════════════════════════════════════════════════════


class TestSignRequest:
    """End-to-end sign_request tests."""

    def test_post_returns_three_headers(self, signer):
        headers = signer.sign_request(
            "POST",
            "https://api.execution.market/api/v1/tasks",
            '{"title":"test"}',
        )
        assert "content-digest" in headers
        assert "signature-input" in headers
        assert "signature" in headers

    def test_get_returns_two_headers(self, signer):
        headers = signer.sign_request(
            "GET",
            "https://api.execution.market/api/v1/tasks",
        )
        assert "content-digest" not in headers
        assert "signature-input" in headers
        assert "signature" in headers

    def test_delete_no_content_digest(self, signer):
        headers = signer.sign_request(
            "DELETE",
            "https://api.execution.market/api/v1/tasks/123",
        )
        assert "content-digest" not in headers

    def test_put_with_body_has_content_digest(self, signer):
        headers = signer.sign_request(
            "PUT",
            "https://api.execution.market/api/v1/tasks/123",
            '{"status":"done"}',
        )
        assert "content-digest" in headers

    def test_patch_with_body_has_content_digest(self, signer):
        headers = signer.sign_request(
            "PATCH",
            "https://api.execution.market/api/v1/tasks/123",
            '{"title":"updated"}',
        )
        assert "content-digest" in headers

    def test_post_empty_body_no_digest(self, signer):
        headers = signer.sign_request(
            "POST",
            "https://api.execution.market/api/v1/tasks",
            "",
        )
        assert "content-digest" not in headers

    def test_signature_input_format(self, signer):
        headers = signer.sign_request(
            "GET",
            "https://api.execution.market/api/v1/tasks",
        )
        sig_input = headers["signature-input"]
        assert sig_input.startswith("eth=")
        assert '"@method"' in sig_input
        assert '"@authority"' in sig_input
        assert '"@path"' in sig_input
        assert "created=" in sig_input
        assert "expires=" in sig_input
        assert "nonce=" in sig_input
        assert "keyid=" in sig_input

    def test_signature_format(self, signer):
        headers = signer.sign_request(
            "GET",
            "https://api.execution.market/api/v1/tasks",
        )
        sig = headers["signature"]
        assert sig.startswith("eth=:")
        assert sig.endswith(":")
        # Extract base64 and verify it decodes
        b64_part = sig[len("eth=:") : -1]
        sig_bytes = base64.b64decode(b64_part)
        assert len(sig_bytes) == 65  # r(32) + s(32) + v(1)

    def test_keyid_in_signature_input(self, signer):
        headers = signer.sign_request(
            "GET",
            "https://api.execution.market/api/v1/tasks",
        )
        assert signer.keyid in headers["signature-input"]

    def test_different_urls_different_signatures(self, signer):
        h1 = signer.sign_request("GET", "https://api.execution.market/api/v1/tasks")
        h2 = signer.sign_request("GET", "https://api.execution.market/api/v1/health")
        assert h1["signature"] != h2["signature"]

    def test_lowercase_method_handled(self, signer):
        headers = signer.sign_request(
            "get",
            "https://api.execution.market/api/v1/tasks",
        )
        assert "signature" in headers


# ═══════════════════════════════════════════════════════════════════
# TestEIP191Sign — EIP-191 personal_sign
# ═══════════════════════════════════════════════════════════════════


class TestEIP191Sign:
    """EIP-191 signing."""

    def test_signature_length(self, signer):
        sig = signer._eip191_sign("test message")
        assert len(sig) == 65

    def test_signature_is_bytes(self, signer):
        sig = signer._eip191_sign("test message")
        assert isinstance(sig, bytes)

    def test_deterministic(self, signer):
        s1 = signer._eip191_sign("same message")
        s2 = signer._eip191_sign("same message")
        assert s1 == s2

    def test_different_messages_different_signatures(self, signer):
        s1 = signer._eip191_sign("message 1")
        s2 = signer._eip191_sign("message 2")
        assert s1 != s2

    def test_recoverable(self, signer):
        """Verify we can recover the signer address from the signature."""
        message = "test recovery"
        sig = signer._eip191_sign(message)

        # Use web3/eth_account to recover
        msg = encode_defunct(text=message)
        recovered = Account.recover_message(msg, signature=sig)
        assert recovered.lower() == signer.address_lower


# ═══════════════════════════════════════════════════════════════════
# TestEdgeCases — Unusual inputs and boundary conditions
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and error conditions."""

    def test_url_with_port(self, signer):
        headers = signer.sign_request(
            "GET",
            "https://api.execution.market:8443/api/v1/tasks",
        )
        # Authority is in the signature base (signed data), not in signature-input header
        assert "signature-input" in headers
        assert "signature" in headers

    def test_url_root_path(self, signer):
        headers = signer.sign_request(
            "GET",
            "https://api.execution.market/",
        )
        assert "signature" in headers

    def test_large_body(self, signer):
        large_body = json.dumps({"data": "x" * 10000})
        headers = signer.sign_request(
            "POST",
            "https://api.execution.market/api/v1/tasks",
            large_body,
        )
        assert "content-digest" in headers
        assert "signature" in headers

    def test_body_with_unicode(self, signer):
        body = json.dumps({"title": "Tarea en español: ¡Hola! 🎉"})
        headers = signer.sign_request(
            "POST",
            "https://api.execution.market/api/v1/tasks",
            body,
        )
        assert "content-digest" in headers

    def test_head_method_no_body(self, signer):
        headers = signer.sign_request(
            "HEAD",
            "https://api.execution.market/api/v1/health",
        )
        assert "content-digest" not in headers

    def test_url_with_query_string(self, signer):
        """Query string is present in URL but not a covered component."""
        headers = signer.sign_request(
            "GET",
            "https://api.execution.market/api/v1/tasks?status=open&limit=10",
        )
        assert "signature" in headers
