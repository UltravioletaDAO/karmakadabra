#!/usr/bin/env python3
"""
EIP-712 Payment Signing for GLUE Token (EIP-3009)

Implements signing for transferWithAuthorization() to enable gasless payments.

EIP-3009 Flow:
1. Buyer signs payment authorization off-chain
2. Buyer sends HTTP request with X-Payment header to Seller
3. Seller's x402 middleware verifies signature
4. Facilitator executes transferWithAuthorization() on-chain
5. Transfer completes without buyer needing gas

Reference:
- EIP-712: https://eips.ethereum.org/EIPS/eip-712
- EIP-3009: https://eips.ethereum.org/EIPS/eip-3009
- GLUE Token: erc-20/src/GLUE.sol
"""

import os
import secrets
from typing import Dict, Tuple
from decimal import Decimal
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from eth_account.signers.local import LocalAccount
import time


# GLUE Token constants
GLUE_TOKEN_NAME = "Gasless Ultravioleta DAO Extended Token"
GLUE_TOKEN_VERSION = "1"  # From EIP-2612 Permit
GLUE_DECIMALS = 6


class PaymentSigner:
    """
    EIP-712 payment signer for GLUE Token transferWithAuthorization

    Features:
    - EIP-712 domain separator generation
    - transferWithAuthorization signature creation
    - Nonce generation (random 32 bytes)
    - Time window management (validAfter, validBefore)
    - Signature verification

    Example:
        >>> signer = PaymentSigner(
        ...     glue_token_address="0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
        ...     chain_id=43113
        ... )
        >>> signature = signer.sign_transfer_authorization(
        ...     from_address="0xAlice...",
        ...     to_address="0xBob...",
        ...     value=10_000,  # 0.01 GLUE (6 decimals)
        ...     private_key="0x..."
        ... )
        >>> print(signature)
    """

    def __init__(
        self,
        glue_token_address: str,
        chain_id: int = 43113,
        token_name: str = GLUE_TOKEN_NAME,
        token_version: str = GLUE_TOKEN_VERSION
    ):
        """
        Initialize PaymentSigner

        Args:
            glue_token_address: GLUE Token contract address
            chain_id: Chain ID (default: 43113 for Fuji)
            token_name: Token name for EIP-712 domain
            token_version: Token version for EIP-712 domain
        """
        self.glue_token_address = Web3.to_checksum_address(glue_token_address)
        self.chain_id = chain_id
        self.token_name = token_name
        self.token_version = token_version

        # EIP-712 domain separator
        self.domain_separator = self._build_domain_separator()

    def _build_domain_separator(self) -> Dict:
        """
        Build EIP-712 domain separator for GLUE Token

        Returns:
            dict: EIP-712 domain
        """
        return {
            "name": self.token_name,
            "version": self.token_version,
            "chainId": self.chain_id,
            "verifyingContract": self.glue_token_address
        }

    @staticmethod
    def generate_nonce() -> bytes:
        """
        Generate random nonce (32 bytes)

        EIP-3009 uses random nonces (not sequential) to prevent collisions
        and allow multiple pending authorizations.

        Returns:
            bytes: Random 32-byte nonce
        """
        return secrets.token_bytes(32)

    @staticmethod
    def glue_amount(amount_human: str) -> int:
        """
        Convert human-readable GLUE amount to contract units (6 decimals)

        Args:
            amount_human: Amount in GLUE (e.g., "0.01" for 1 cent)

        Returns:
            int: Amount in smallest units (e.g., 10000 for 0.01 GLUE)

        Example:
            >>> PaymentSigner.glue_amount("0.01")
            10000
            >>> PaymentSigner.glue_amount("1.5")
            1500000
        """
        return int(Decimal(amount_human) * Decimal(10 ** GLUE_DECIMALS))

    @staticmethod
    def glue_to_human(amount: int) -> str:
        """
        Convert contract units to human-readable GLUE amount

        Args:
            amount: Amount in smallest units

        Returns:
            str: Human-readable amount

        Example:
            >>> PaymentSigner.glue_to_human(10000)
            '0.010000'
        """
        return f"{Decimal(amount) / Decimal(10 ** GLUE_DECIMALS):.6f}"

    def sign_transfer_authorization(
        self,
        from_address: str,
        to_address: str,
        value: int,
        private_key: str,
        valid_after: int = None,
        valid_before: int = None,
        nonce: bytes = None
    ) -> Dict:
        """
        Sign transferWithAuthorization for GLUE Token

        Args:
            from_address: Payer's address (must match private_key)
            to_address: Payee's address
            value: Amount in smallest units (e.g., 10000 = 0.01 GLUE)
            private_key: Payer's private key (0x...)
            valid_after: Unix timestamp (default: now)
            valid_before: Unix timestamp (default: now + 1 hour)
            nonce: 32-byte nonce (default: random)

        Returns:
            dict: Signature data with all parameters needed for transferWithAuthorization

        Example:
            >>> sig = signer.sign_transfer_authorization(
            ...     from_address="0xAlice...",
            ...     to_address="0xBob...",
            ...     value=10_000,  # 0.01 GLUE
            ...     private_key="0x..."
            ... )
            >>> # Use sig['v'], sig['r'], sig['s'] for contract call
        """
        # Normalize addresses
        from_address = Web3.to_checksum_address(from_address)
        to_address = Web3.to_checksum_address(to_address)

        # Set time window (default: 1 minute ago to +1 hour for clock skew tolerance)
        if valid_after is None:
            valid_after = int(time.time()) - 60  # 1 minute ago for clock skew tolerance

        if valid_before is None:
            valid_before = int(time.time()) + 3600  # 1 hour

        # Generate nonce if not provided
        if nonce is None:
            nonce = self.generate_nonce()

        # Convert nonce to bytes32 if it's not already
        if isinstance(nonce, str):
            nonce = bytes.fromhex(nonce.replace('0x', ''))

        # Build EIP-712 structured data
        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
                ],
                "TransferWithAuthorization": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                    {"name": "nonce", "type": "bytes32"}
                ]
            },
            "primaryType": "TransferWithAuthorization",
            "domain": self.domain_separator,
            "message": {
                "from": from_address,
                "to": to_address,
                "value": value,
                "validAfter": valid_after,
                "validBefore": valid_before,
                "nonce": Web3.to_hex(nonce)
            }
        }

        # Create account from private key
        account: LocalAccount = Account.from_key(private_key)

        # Verify from_address matches private key
        if account.address != from_address:
            raise ValueError(
                f"Private key does not match from_address. "
                f"Expected {from_address}, got {account.address}"
            )

        # Sign structured data (EIP-712)
        encoded_data = encode_typed_data(full_message=structured_data)
        signed_message = account.sign_message(encoded_data)

        # Extract v, r, s from signature
        v = signed_message.v
        r = Web3.to_hex(signed_message.r)
        s = Web3.to_hex(signed_message.s)

        # Return all parameters needed for transferWithAuthorization
        return {
            # Authorization parameters
            "from": from_address,
            "to": to_address,
            "value": value,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": Web3.to_hex(nonce),
            # Signature
            "v": v,
            "r": r,
            "s": s,
            # Metadata (not used in contract call, but useful)
            "signature": signed_message.signature.hex(),
            "signer": account.address,
            "amount_human": self.glue_to_human(value),
            "valid_after_iso": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(valid_after)),
            "valid_before_iso": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(valid_before))
        }

    def verify_signature(
        self,
        from_address: str,
        to_address: str,
        value: int,
        valid_after: int,
        valid_before: int,
        nonce: bytes,
        v: int,
        r: bytes,
        s: bytes
    ) -> bool:
        """
        Verify transferWithAuthorization signature

        Args:
            from_address: Payer's address
            to_address: Payee's address
            value: Amount
            valid_after: Validity start timestamp
            valid_before: Validity end timestamp
            nonce: 32-byte nonce
            v: Signature parameter
            r: Signature parameter
            s: Signature parameter

        Returns:
            bool: True if signature is valid
        """
        # Normalize addresses
        from_address = Web3.to_checksum_address(from_address)
        to_address = Web3.to_checksum_address(to_address)

        # Convert nonce to hex if bytes
        if isinstance(nonce, bytes):
            nonce = Web3.to_hex(nonce)

        # Convert r, s to hex if bytes
        if isinstance(r, bytes):
            r = Web3.to_hex(r)
        if isinstance(s, bytes):
            s = Web3.to_hex(s)

        # Build EIP-712 structured data
        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
                ],
                "TransferWithAuthorization": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                    {"name": "nonce", "type": "bytes32"}
                ]
            },
            "primaryType": "TransferWithAuthorization",
            "domain": self.domain_separator,
            "message": {
                "from": from_address,
                "to": to_address,
                "value": value,
                "validAfter": valid_after,
                "validBefore": valid_before,
                "nonce": nonce
            }
        }

        # Encode structured data
        encoded_data = encode_typed_data(full_message=structured_data)

        # Recover signer from signature
        try:
            signer = Account.recover_message(
                encoded_data,
                vrs=(v, Web3.to_bytes(hexstr=r), Web3.to_bytes(hexstr=s))
            )

            # Verify signer matches from_address
            return signer.lower() == from_address.lower()

        except Exception:
            return False


# Convenience functions

def sign_payment(
    from_address: str,
    to_address: str,
    amount_glue: str,
    private_key: str,
    glue_token_address: str = None,
    chain_id: int = 43113
) -> Dict:
    """
    Convenience function to sign a GLUE payment

    Args:
        from_address: Payer's address
        to_address: Payee's address
        amount_glue: Amount in GLUE (e.g., "0.01")
        private_key: Payer's private key
        glue_token_address: GLUE Token address (default: from env)
        chain_id: Chain ID (default: 43113 for Fuji)

    Returns:
        dict: Signed payment authorization

    Example:
        >>> sig = sign_payment(
        ...     from_address="0xAlice...",
        ...     to_address="0xBob...",
        ...     amount_glue="0.01",
        ...     private_key="0x..."
        ... )
    """
    if glue_token_address is None:
        glue_token_address = os.getenv("GLUE_TOKEN_ADDRESS")
        if not glue_token_address:
            raise ValueError("GLUE_TOKEN_ADDRESS not provided or found in environment")

    signer = PaymentSigner(glue_token_address=glue_token_address, chain_id=chain_id)

    value = signer.glue_amount(amount_glue)

    return signer.sign_transfer_authorization(
        from_address=from_address,
        to_address=to_address,
        value=value,
        private_key=private_key
    )


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("EIP-712 Payment Signing Example")
    print("=" * 70)
    print()

    # Example wallet (DO NOT use in production)
    test_private_key = "0x" + "1" * 64
    test_account = Account.from_key(test_private_key)

    print(f"Test Account: {test_account.address}")
    print()

    # Initialize signer
    signer = PaymentSigner(
        glue_token_address="0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
        chain_id=43113
    )

    # Sign payment: 0.01 GLUE
    print("[1] Signing payment: 0.01 GLUE")
    signature = signer.sign_transfer_authorization(
        from_address=test_account.address,
        to_address="0x0000000000000000000000000000000000000001",
        value=signer.glue_amount("0.01"),
        private_key=test_private_key
    )

    print(f"    From: {signature['from']}")
    print(f"    To: {signature['to']}")
    print(f"    Amount: {signature['amount_human']} GLUE")
    print(f"    Valid: {signature['valid_after_iso']} to {signature['valid_before_iso']}")
    print(f"    Nonce: {signature['nonce']}")
    print(f"    v: {signature['v']}")
    print(f"    r: {signature['r'][:20]}...")
    print(f"    s: {signature['s'][:20]}...")
    print()

    # Verify signature
    print("[2] Verifying signature...")
    is_valid = signer.verify_signature(
        from_address=signature['from'],
        to_address=signature['to'],
        value=signature['value'],
        valid_after=signature['validAfter'],
        valid_before=signature['validBefore'],
        nonce=signature['nonce'],
        v=signature['v'],
        r=signature['r'],
        s=signature['s']
    )

    if is_valid:
        print("    [OK] Signature is valid!")
    else:
        print("    [ERROR] Signature is invalid!")

    print()
    print("=" * 70)
