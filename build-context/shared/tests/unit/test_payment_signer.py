#!/usr/bin/env python3
"""
Unit tests for payment_signer.py - EIP-712 payment signing
"""

import pytest
import time
from web3 import Web3
from eth_account import Account

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from payment_signer import PaymentSigner, sign_payment


@pytest.mark.unit
class TestPaymentSigner:
    """Test suite for PaymentSigner class"""

    def test_initialize_signer(self, test_config):
        """Test PaymentSigner initialization"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        assert signer.glue_token_address == test_config["glue_token"]
        assert signer.chain_id == test_config["chain_id"]
        assert signer.domain_separator is not None

    def test_glue_amount_conversion(self, test_config):
        """Test GLUE amount unit conversion"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        # Test standard amounts
        assert signer.glue_amount("0.01") == 10000  # 0.01 GLUE = 10,000 units
        assert signer.glue_amount("1") == 1000000  # 1 GLUE = 1,000,000 units
        assert signer.glue_amount("0.001") == 1000  # 0.001 GLUE = 1,000 units

    def test_glue_to_human_conversion(self, test_config):
        """Test GLUE unit to human-readable conversion"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        # Test reverse conversion
        assert signer.glue_to_human(10000) == "0.010000"
        assert signer.glue_to_human(1000000) == "1.000000"
        assert signer.glue_to_human(1000) == "0.001000"

    def test_generate_nonce(self, test_config):
        """Test nonce generation"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        # Generate multiple nonces
        nonce1 = signer.generate_nonce()
        nonce2 = signer.generate_nonce()

        # Check format
        assert isinstance(nonce1, bytes)
        assert len(nonce1) == 32  # 32 bytes

        # Check uniqueness
        assert nonce1 != nonce2

    def test_sign_transfer_authorization(self, test_config, test_private_key, test_address):
        """Test EIP-712 signature creation"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        # Create signature
        signature = signer.sign_transfer_authorization(
            from_address=test_address,
            to_address="0x0000000000000000000000000000000000000001",
            value=signer.glue_amount("0.01"),
            private_key=test_private_key
        )

        # Validate signature structure
        assert "from" in signature
        assert "to" in signature
        assert "value" in signature
        assert "validAfter" in signature
        assert "validBefore" in signature
        assert "nonce" in signature
        assert "v" in signature
        assert "r" in signature
        assert "s" in signature

        # Validate values
        assert signature["from"] == test_address
        assert signature["to"] == "0x0000000000000000000000000000000000000001"
        assert signature["value"] == 10000  # 0.01 GLUE

        # Validate signature components
        assert isinstance(signature["v"], int)
        assert signature["v"] in [27, 28]  # Valid v values
        assert signature["r"].startswith("0x")
        assert len(signature["r"]) == 66  # 0x + 64 hex chars
        assert signature["s"].startswith("0x")
        assert len(signature["s"]) == 66

    def test_signature_verification(self, test_config, test_private_key, test_address):
        """Test signature verification"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        # Create signature
        signature = signer.sign_transfer_authorization(
            from_address=test_address,
            to_address="0x0000000000000000000000000000000000000001",
            value=signer.glue_amount("0.01"),
            private_key=test_private_key
        )

        # Verify signature
        is_valid = signer.verify_signature(
            from_address=signature["from"],
            to_address=signature["to"],
            value=signature["value"],
            valid_after=signature["validAfter"],
            valid_before=signature["validBefore"],
            nonce=Web3.to_bytes(hexstr=signature["nonce"]),
            v=signature["v"],
            r=Web3.to_bytes(hexstr=signature["r"]),
            s=Web3.to_bytes(hexstr=signature["s"])
        )
        assert is_valid is True

    def test_signature_verification_wrong_signer(self, test_config, test_private_key):
        """Test signature verification with wrong signer"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        # Create signature with one account
        account1 = Account.from_key(test_private_key)
        signature = signer.sign_transfer_authorization(
            from_address=account1.address,
            to_address="0x0000000000000000000000000000000000000001",
            value=signer.glue_amount("0.01"),
            private_key=test_private_key
        )

        # Try to verify with different account (should fail since signature is from account1)
        account2 = Account.create()

        # Modify signature to claim it's from account2 (should fail verification)
        is_valid = signer.verify_signature(
            from_address=account2.address,  # Wrong from_address
            to_address=signature["to"],
            value=signature["value"],
            valid_after=signature["validAfter"],
            valid_before=signature["validBefore"],
            nonce=Web3.to_bytes(hexstr=signature["nonce"]),
            v=signature["v"],
            r=Web3.to_bytes(hexstr=signature["r"]),
            s=Web3.to_bytes(hexstr=signature["s"])
        )
        assert is_valid is False

    def test_custom_time_window(self, test_config, test_private_key, test_address):
        """Test custom validAfter/validBefore"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        now = int(time.time())
        valid_after = now - 60  # Valid from 1 minute ago
        valid_before = now + 3600  # Valid for 1 hour

        signature = signer.sign_transfer_authorization(
            from_address=test_address,
            to_address="0x0000000000000000000000000000000000000001",
            value=signer.glue_amount("0.01"),
            private_key=test_private_key,
            valid_after=valid_after,
            valid_before=valid_before
        )

        assert signature["validAfter"] == valid_after
        assert signature["validBefore"] == valid_before

    def test_custom_nonce(self, test_config, test_private_key, test_address):
        """Test custom nonce"""
        signer = PaymentSigner(
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        custom_nonce = b"\x01" * 32  # Custom 32-byte nonce

        signature = signer.sign_transfer_authorization(
            from_address=test_address,
            to_address="0x0000000000000000000000000000000000000001",
            value=signer.glue_amount("0.01"),
            private_key=test_private_key,
            nonce=custom_nonce
        )

        assert signature["nonce"] == Web3.to_hex(custom_nonce)

    def test_sign_payment_convenience_function(self, test_config, test_private_key, test_address):
        """Test sign_payment convenience function"""
        signature = sign_payment(
            from_address=test_address,
            to_address="0x0000000000000000000000000000000000000001",
            amount_glue="0.01",
            private_key=test_private_key,
            glue_token_address=test_config["glue_token"],
            chain_id=test_config["chain_id"]
        )

        # Validate signature was created
        assert "v" in signature
        assert "r" in signature
        assert "s" in signature
        assert signature["value"] == 10000  # 0.01 GLUE
