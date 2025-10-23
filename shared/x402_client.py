#!/usr/bin/env python3
"""
x402 HTTP Client for Karmacadabra

Python client for x402 payment protocol - enables gasless micropayments
between AI agents using HTTP 402 Payment Required status code.

Protocol Flow:
1. Buyer creates signed payment authorization (EIP-712)
2. Buyer sends HTTP request with X-Payment header to Seller
3. Seller's middleware extracts payment, calls facilitator /verify
4. Facilitator verifies signature and funds
5. If valid, Seller returns data
6. Facilitator executes transferWithAuthorization() on-chain via /settle

Reference:
- x402 Protocol: https://github.com/TBD/x402-spec
- Facilitator API: x402-rs/src/handlers.rs
"""

import os
import json
import base64
import time
from typing import Dict, Optional, Tuple
from decimal import Decimal
import httpx
from web3 import Web3

try:
    from .payment_signer import PaymentSigner, sign_payment
except ImportError:
    from payment_signer import PaymentSigner, sign_payment


class X402Client:
    """
    x402 Protocol HTTP Client

    Features:
    - Payment header generation (X-Payment with base64-encoded payload)
    - Facilitator communication (/verify, /settle)
    - Retry logic with exponential backoff
    - Error handling for payment failures
    - Integration with PaymentSigner

    Example (Buyer):
        >>> client = X402Client(
        ...     facilitator_url="https://facilitator.ultravioletadao.xyz",
        ...     glue_token_address="0x3D19...",
        ...     private_key="0x..."
        ... )
        >>> # Buy data from seller
        >>> response = await client.buy_with_payment(
        ...     seller_url="https://karma-hello.xyz/api/logs",
        ...     seller_address="0xBob...",
        ...     amount_glue="0.01"
        ... )
    """

    def __init__(
        self,
        facilitator_url: str = None,
        glue_token_address: str = None,
        chain_id: int = 43113,
        private_key: str = None,
        from_address: str = None,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        """
        Initialize x402 Client

        Args:
            facilitator_url: x402 facilitator endpoint (default: from env)
            glue_token_address: GLUE Token address (default: from env)
            chain_id: Chain ID (default: 43113 for Fuji)
            private_key: Buyer's private key (for signing payments)
            from_address: Buyer's address (derived from private_key if not provided)
            timeout: HTTP timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.facilitator_url = facilitator_url or os.getenv(
            "FACILITATOR_URL",
            "https://facilitator.ultravioletadao.xyz"
        )
        self.glue_token_address = glue_token_address or os.getenv("GLUE_TOKEN_ADDRESS")
        self.chain_id = chain_id
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.glue_token_address:
            raise ValueError("GLUE_TOKEN_ADDRESS not provided or found in environment")

        # Initialize payment signer
        self.signer = PaymentSigner(
            glue_token_address=self.glue_token_address,
            chain_id=self.chain_id
        )

        # Buyer wallet (optional - only needed if making payments)
        self.private_key = private_key
        if from_address:
            self.from_address = Web3.to_checksum_address(from_address)
        elif private_key:
            from eth_account import Account
            account = Account.from_key(private_key)
            self.from_address = account.address
        else:
            self.from_address = None

        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # =========================================================================
    # PAYMENT HEADER GENERATION
    # =========================================================================

    def create_payment_payload(
        self,
        to_address: str,
        amount_glue: str,
        from_address: str = None,
        private_key: str = None
    ) -> Dict:
        """
        Create x402 payment payload

        Args:
            to_address: Payee's address (seller)
            amount_glue: Amount in GLUE (e.g., "0.01")
            from_address: Payer's address (default: self.from_address)
            private_key: Payer's private key (default: self.private_key)

        Returns:
            dict: x402 PaymentPayload structure
        """
        from_address = from_address or self.from_address
        private_key = private_key or self.private_key

        if not from_address or not private_key:
            raise ValueError("from_address and private_key required for creating payments")

        # Sign payment authorization
        signature = self.signer.sign_transfer_authorization(
            from_address=from_address,
            to_address=to_address,
            value=self.signer.glue_amount(amount_glue),
            private_key=private_key
        )

        # Build x402 PaymentPayload
        # Format: EIP-3009 transferWithAuthorization
        payment_payload = {
            "x402Version": "0.0.1",
            "scheme": "eip3009",
            "network": f"avalanche-fuji:{self.chain_id}",
            "payload": {
                "tokenAddress": self.glue_token_address,
                "from": signature['from'],
                "to": signature['to'],
                "value": str(signature['value']),
                "validAfter": str(signature['validAfter']),
                "validBefore": str(signature['validBefore']),
                "nonce": signature['nonce'],
                "v": signature['v'],
                "r": signature['r'],
                "s": signature['s']
            }
        }

        return payment_payload

    def encode_payment_header(self, payment_payload: Dict) -> str:
        """
        Encode payment payload as base64 for X-Payment header

        Args:
            payment_payload: PaymentPayload dict

        Returns:
            str: Base64-encoded JSON string
        """
        json_str = json.dumps(payment_payload, separators=(',', ':'))
        return base64.b64encode(json_str.encode('utf-8')).decode('ascii')

    # =========================================================================
    # FACILITATOR API
    # =========================================================================

    async def facilitator_health(self) -> Dict:
        """
        Check facilitator health

        Returns:
            dict: Health status
        """
        response = await self.http_client.get(f"{self.facilitator_url}/health")
        response.raise_for_status()
        return response.json()

    async def facilitator_supported(self) -> Dict:
        """
        Get supported payment schemes

        Returns:
            dict: Supported schemes and networks
        """
        response = await self.http_client.get(f"{self.facilitator_url}/supported")
        response.raise_for_status()
        return response.json()

    async def facilitator_verify(
        self,
        payment_payload: Dict,
        payment_requirements: Dict
    ) -> Dict:
        """
        Verify payment with facilitator

        Args:
            payment_payload: PaymentPayload
            payment_requirements: PaymentRequirements (price, receiver)

        Returns:
            dict: VerifyResponse (valid: bool, reason: Optional[str])
        """
        verify_request = {
            "x402Version": "0.0.1",
            "paymentPayload": payment_payload,
            "paymentRequirements": payment_requirements
        }

        response = await self.http_client.post(
            f"{self.facilitator_url}/verify",
            json=verify_request
        )
        response.raise_for_status()
        return response.json()

    async def facilitator_settle(
        self,
        payment_payload: Dict,
        payment_requirements: Dict
    ) -> Dict:
        """
        Settle payment on-chain via facilitator

        Args:
            payment_payload: PaymentPayload
            payment_requirements: PaymentRequirements

        Returns:
            dict: SettleResponse (txHash, success)
        """
        settle_request = {
            "x402Version": "0.0.1",
            "paymentPayload": payment_payload,
            "paymentRequirements": payment_requirements
        }

        response = await self.http_client.post(
            f"{self.facilitator_url}/settle",
            json=settle_request
        )
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # HIGH-LEVEL BUYER API
    # =========================================================================

    async def buy_with_payment(
        self,
        seller_url: str,
        seller_address: str,
        amount_glue: str,
        method: str = "GET",
        json_data: Dict = None,
        verify_first: bool = True
    ) -> Tuple[httpx.Response, Dict]:
        """
        Buy data from seller with x402 payment

        Args:
            seller_url: Seller's API endpoint
            seller_address: Seller's wallet address
            amount_glue: Payment amount in GLUE (e.g., "0.01")
            method: HTTP method (GET, POST, etc.)
            json_data: Optional JSON body for POST requests
            verify_first: Verify payment with facilitator before sending

        Returns:
            tuple: (response, settlement_result)

        Raises:
            httpx.HTTPStatusError: If request fails
            ValueError: If payment verification fails
        """
        # Create payment
        payment_payload = self.create_payment_payload(
            to_address=seller_address,
            amount_glue=amount_glue
        )

        payment_requirements = {
            "scheme": "eip3009",
            "network": f"avalanche-fuji:{self.chain_id}",
            "receiver": seller_address,
            "price": {
                "tokenAddress": self.glue_token_address,
                "amount": str(self.signer.glue_amount(amount_glue))
            }
        }

        # Optional: Verify payment first
        if verify_first:
            verify_result = await self.facilitator_verify(
                payment_payload=payment_payload,
                payment_requirements=payment_requirements
            )

            if not verify_result.get('valid'):
                raise ValueError(
                    f"Payment verification failed: {verify_result.get('reason', 'Unknown error')}"
                )

        # Encode payment header
        payment_header = self.encode_payment_header(payment_payload)

        # Send request with X-Payment header
        headers = {
            "X-Payment": payment_header,
            "Content-Type": "application/json"
        }

        if method.upper() == "GET":
            response = await self.http_client.get(seller_url, headers=headers)
        elif method.upper() == "POST":
            response = await self.http_client.post(
                seller_url,
                headers=headers,
                json=json_data or {}
            )
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Raise for HTTP errors
        response.raise_for_status()

        # Settle payment on-chain
        settle_result = await self.facilitator_settle(
            payment_payload=payment_payload,
            payment_requirements=payment_requirements
        )

        return response, settle_result

    async def buy_with_retry(
        self,
        seller_url: str,
        seller_address: str,
        amount_glue: str,
        **kwargs
    ) -> Tuple[httpx.Response, Dict]:
        """
        Buy with automatic retry on failure

        Args:
            seller_url: Seller's API endpoint
            seller_address: Seller's wallet address
            amount_glue: Payment amount
            **kwargs: Additional arguments for buy_with_payment

        Returns:
            tuple: (response, settlement_result)
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await self.buy_with_payment(
                    seller_url=seller_url,
                    seller_address=seller_address,
                    amount_glue=amount_glue,
                    **kwargs
                )
            except Exception as e:
                last_exception = e

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    print(f"[x402] Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"[x402] All {self.max_retries} attempts failed")

        raise last_exception

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def glue_amount(self, amount_human: str) -> int:
        """Convert human-readable GLUE to contract units"""
        return self.signer.glue_amount(amount_human)

    def glue_to_human(self, amount: int) -> str:
        """Convert contract units to human-readable GLUE"""
        return self.signer.glue_to_human(amount)


# Convenience function

async def buy_from_agent(
    seller_url: str,
    seller_address: str,
    amount_glue: str,
    buyer_private_key: str,
    method: str = "GET",
    json_data: Dict = None
) -> Tuple[bytes, Dict]:
    """
    Convenience function to buy data from an agent

    Args:
        seller_url: Seller's API endpoint
        seller_address: Seller's wallet address
        amount_glue: Payment amount (e.g., "0.01")
        buyer_private_key: Buyer's private key
        method: HTTP method
        json_data: Optional JSON body

    Returns:
        tuple: (response_data, settlement_result)

    Example:
        >>> data, settlement = await buy_from_agent(
        ...     seller_url="https://karma-hello.xyz/api/logs",
        ...     seller_address="0xBob...",
        ...     amount_glue="0.01",
        ...     buyer_private_key="0x..."
        ... )
    """
    async with X402Client(private_key=buyer_private_key) as client:
        response, settlement = await client.buy_with_payment(
            seller_url=seller_url,
            seller_address=seller_address,
            amount_glue=amount_glue,
            method=method,
            json_data=json_data
        )

        return response.content, settlement


# Example usage
if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from shared.payment_signer import PaymentSigner

    async def main():
        print("=" * 70)
        print("x402 Client Example")
        print("=" * 70)
        print()

        # Example wallet (DO NOT use in production)
        test_private_key = "0x" + "1" * 64
        glue_token = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"

        async with X402Client(
            private_key=test_private_key,
            glue_token_address=glue_token
        ) as client:
            print(f"[1] Client initialized")
            print(f"    Buyer address: {client.from_address}")
            print(f"    Facilitator: {client.facilitator_url}")
            print()

            # Check facilitator health
            print("[2] Checking facilitator health...")
            try:
                health = await client.facilitator_health()
                print(f"    Health: {health}")
            except Exception as e:
                print(f"    Error: {e}")
            print()

            # Get supported schemes
            print("[3] Getting supported payment schemes...")
            try:
                supported = await client.facilitator_supported()
                print(f"    Supported: {supported}")
            except Exception as e:
                print(f"    Error: {e}")
            print()

            # Create payment payload example
            print("[4] Creating payment payload...")
            try:
                payload = client.create_payment_payload(
                    to_address="0x0000000000000000000000000000000000000001",
                    amount_glue="0.01"
                )
                print(f"    Payload scheme: {payload['scheme']}")
                print(f"    Payment amount: 0.01 GLUE")
                print(f"    Encoded header length: {len(client.encode_payment_header(payload))} bytes")
            except Exception as e:
                print(f"    Error: {e}")

        print()
        print("=" * 70)
        print("Example complete!")
        print("=" * 70)

    asyncio.run(main())
