#!/usr/bin/env python3
"""
Solana Load Test - SPEC-COMPLIANT Implementation
Based on facilitator golden source analysis (SOLANA_SPEC.md)

Transaction structure per facilitator requirements:
- Position 0: SetComputeUnitLimit (200,000)
- Position 1: SetComputeUnitPrice (1,000,000 microlamports, max 5M)
- Position 2: TransferChecked (source=buyer_ata, dest=seller_ata, authority=buyer)
- Facilitator as fee payer (required signer position 0)
- Buyer signs at position determined by account_keys ordering
- Recent blockhash from RPC (facilitator won't replace it)
"""
import argparse
import json
import os
import sys
import time
import base64
import logging
from typing import Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.signature import Signature as SoldersSignature
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from spl.token.instructions import transfer_checked, TransferCheckedParams, get_associated_token_address
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.rpc.api import Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration (per SOLANA_SPEC.md)
TEST_SELLER_URL = os.getenv(
    "TEST_SELLER_URL",
    "https://test-seller-solana.karmacadabra.ultravioletadao.xyz"
)
SELLER_PUBKEY = os.getenv("SELLER_PUBKEY")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
FACILITATOR_PUBKEY = Pubkey.from_string("F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq")
PRICE_USDC = 10000  # 0.01 USDC (6 decimals)
USDC_DECIMALS = 6
SOLANA_RPC = "https://api.mainnet-beta.solana.com"


def load_buyer_keypair_from_aws() -> Keypair:
    """Load buyer keypair from AWS Secrets Manager"""
    try:
        import boto3
        logger.info("Loading buyer keypair from AWS Secrets Manager...")
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        response = secrets_client.get_secret_value(SecretId='karmacadabra-test-buyer-solana')
        config = json.loads(response['SecretString'])

        keypair_data = config.get('keypair')
        if not keypair_data:
            raise ValueError("No 'keypair' field found in AWS secret")

        buyer = Keypair.from_bytes(bytes(keypair_data))
        logger.info(f"Loaded buyer keypair: {buyer.pubkey()}")
        return buyer

    except Exception as e:
        logger.error(f"Failed to load from AWS: {e}")
        raise


class SolanaLoadTestV4:
    """
    Spec-compliant load tester for Solana x402 payments

    Implementation follows SOLANA_SPEC.md derived from facilitator source code.
    """

    def __init__(self, seller_pubkey: str, buyer_keypair: Keypair):
        self.buyer = buyer_keypair
        self.seller = Pubkey.from_string(seller_pubkey)
        self.rpc_client = Client(SOLANA_RPC)

        print(f"\n{'='*60}")
        print(f"SPEC-COMPLIANT SOLANA LOAD TEST v4.0.0")
        print(f"{'='*60}")
        print(f"Buyer:       {self.buyer.pubkey()}")
        print(f"Seller:      {self.seller}")
        print(f"Facilitator: {FACILITATOR_PUBKEY}")
        print(f"Test Seller: {TEST_SELLER_URL}")
        print(f"Price:       {PRICE_USDC / 1_000_000} USDC")
        print(f"Spec:        SOLANA_SPEC.md (facilitator golden source)")
        print(f"{'='*60}\n")

    def create_transfer_transaction(self) -> str:
        """
        Create partially-signed Solana transaction per facilitator spec.

        Per SOLANA_SPEC.md (solana.rs:391-405, 607-615):
        - Position 0: SetComputeUnitLimit
        - Position 1: SetComputeUnitPrice
        - Position 2: TransferChecked
        - Facilitator as fee payer (required signer #0)
        - Buyer signs at correct position
        - Recent blockhash from RPC (NOT Hash.default())

        Returns:
            Base64-encoded partially-signed VersionedTransaction
        """
        # Get ATAs
        buyer_ata = get_associated_token_address(self.buyer.pubkey(), USDC_MINT)
        seller_ata = get_associated_token_address(self.seller, USDC_MINT)

        # Instructions (per facilitator validation order)
        instructions = [
            # Position 0: compute_limit
            set_compute_unit_limit(200_000),

            # Position 1: compute_price (max 5_000_000 per spec)
            # Using 5M for maximum priority to ensure confirmation
            set_compute_unit_price(5_000_000),

            # Position 2: transfer_checked
            transfer_checked(TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=buyer_ata,
                mint=USDC_MINT,
                dest=seller_ata,
                owner=self.buyer.pubkey(),  # Authority (reported as payer)
                amount=PRICE_USDC,
                decimals=USDC_DECIMALS,
            ))
        ]

        # Get RECENT blockhash (facilitator won't replace it per spec line 410)
        recent_blockhash_response = self.rpc_client.get_latest_blockhash()
        recent_blockhash = recent_blockhash_response.value.blockhash

        # Facilitator as fee payer (makes it required signer #0 per spec)
        message = MessageV0.try_compile(
            payer=FACILITATOR_PUBKEY,
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash,
        )

        # Find buyer position in required signers (per spec lines 607-615)
        num_required_signatures = message.header.num_required_signatures
        static_keys = list(message.account_keys)
        buyer_pos = static_keys[:num_required_signatures].index(self.buyer.pubkey())

        # Create signature list with placeholders
        signatures = [SoldersSignature.default()] * num_required_signatures

        # Buyer signs the message
        msg_bytes = bytes(message)
        buyer_signature = self.buyer.sign_message(msg_bytes)
        signatures[buyer_pos] = buyer_signature

        # Debug info
        logger.debug(f"Transaction structure:")
        logger.debug(f"  Fee payer (pos 0): {message.account_keys[0]}")
        logger.debug(f"  Required signatures: {num_required_signatures}")
        logger.debug(f"  Buyer position: {buyer_pos}")
        logger.debug(f"  Blockhash: {recent_blockhash}")
        logger.debug(f"  Facilitator placeholder: {signatures[0] == SoldersSignature.default()}")
        logger.debug(f"  Buyer signed: {signatures[buyer_pos] != SoldersSignature.default()}")

        # Create partial transaction
        tx = VersionedTransaction.populate(message, signatures)

        # Serialize to base64
        tx_bytes = bytes(tx)
        tx_base64 = base64.b64encode(tx_bytes).decode('utf-8')

        return tx_base64

    def make_paid_request(self, request_id: int, verbose: bool = False) -> bool:
        """
        Make a single paid request to test-seller

        Args:
            request_id: Unique identifier for this request
            verbose: Print detailed request/response info

        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Create transaction
            transaction_b64 = self.create_transfer_transaction()

            # Build x402 payment payload (per SOLANA_SPEC.md)
            payload = {
                "x402Version": 1,
                "paymentPayload": {
                    "x402Version": 1,
                    "scheme": "exact",
                    "network": "solana",
                    "payload": {
                        "transaction": transaction_b64
                    }
                },
                "paymentRequirements": {
                    "scheme": "exact",
                    "network": "solana",
                    "maxAmountRequired": str(PRICE_USDC),  # String per spec
                    "resource": f"{TEST_SELLER_URL}/hello",
                    "description": "Hello World message",
                    "mimeType": "application/json",
                    "payTo": str(self.seller),
                    "maxTimeoutSeconds": 60,
                    "asset": str(USDC_MINT),
                    "extra": {
                        "name": "USD Coin",
                        "decimals": USDC_DECIMALS
                    }
                }
            }

            if verbose:
                print(f"\n[{request_id:04d}] [{timestamp}] REQUEST DETAILS")
                print(f"  Buyer: {self.buyer.pubkey()}")
                print(f"  Seller: {self.seller}")
                print(f"  Amount: {PRICE_USDC / 1_000_000} USDC")
                print(f"  Transaction: {transaction_b64[:60]}...")

            # Make HTTP request
            response = requests.post(
                f"{TEST_SELLER_URL}/hello",
                json=payload,
                timeout=120  # 120s timeout for Solana
            )

            if response.status_code == 200:
                data = response.json()
                tx_hash = data.get('tx_hash')
                payer = data.get('payer')

                if verbose:
                    print(f"[{request_id:04d}] [{timestamp}] SUCCESS")
                    print(f"  Message: {data.get('message')}")
                    print(f"  Payer: {payer}")
                    if tx_hash:
                        print(f"  TX: https://solscan.io/tx/{tx_hash}")
                else:
                    print(f"[{request_id:04d}] SUCCESS - {data.get('message')} - Payer: {str(payer)[:12]}...")

                return True
            else:
                error_text = response.text
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                if verbose:
                    print(f"[{request_id:04d}] [{timestamp}] FAILED - HTTP {response.status_code}")
                    print(f"  Error: {error_text[:200]}")
                else:
                    print(f"[{request_id:04d}] FAILED - HTTP {response.status_code}: {error_text[:80]}")

                return False

        except requests.exceptions.Timeout:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{request_id:04d}] [{timestamp}] TIMEOUT - Request exceeded 120s")
            return False
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{request_id:04d}] [{timestamp}] ERROR - {str(e)}")
            if verbose:
                import traceback
                traceback.print_exc()
            return False

    def run_sequential_test(self, num_requests: int, verbose: bool = False):
        """Run sequential load test"""
        print(f"\n[START] Sequential test: {num_requests} requests")
        print("=" * 60)

        start_time = time.time()
        successful = 0
        failed = 0

        for i in range(1, num_requests + 1):
            success = self.make_paid_request(i, verbose=verbose)
            if success:
                successful += 1
            else:
                failed += 1

            # Small delay between requests
            if i < num_requests:
                time.sleep(5)

        end_time = time.time()
        duration = end_time - start_time

        # Print summary
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print(f"Total Requests:    {num_requests}")
        print(f"Successful:        {successful} ({successful/num_requests*100:.1f}%)")
        print(f"Failed:            {failed}")
        print(f"Duration:          {duration:.2f}s")
        print(f"Requests/sec:      {num_requests/duration:.2f}")
        print(f"Total Cost:        ${successful * PRICE_USDC / 1_000_000:.2f} USDC")
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Spec-compliant Solana load tester (SOLANA_SPEC.md)"
    )
    parser.add_argument("--seller", type=str, help="Seller's Solana public key")
    parser.add_argument("--num-requests", type=int, default=5, help="Number of requests (default: 5)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output")

    args = parser.parse_args()

    # Get seller pubkey
    seller_pubkey = args.seller or SELLER_PUBKEY
    if not seller_pubkey:
        print("ERROR: Seller public key not provided")
        print("Set SELLER_PUBKEY environment variable or use --seller argument")
        sys.exit(1)

    print("=" * 60)
    print("SOLANA LOAD TESTER v4.0.0 - Spec-Compliant")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Test Seller:  {TEST_SELLER_URL}")
    print(f"  Seller:       {seller_pubkey}")
    print(f"  Facilitator:  {FACILITATOR_PUBKEY}")
    print(f"  Requests:     {args.num_requests}")
    print(f"  Verbose:      {args.verbose}")
    print(f"  Spec:         SOLANA_SPEC.md")
    print()

    # Load buyer keypair from AWS
    buyer_keypair = load_buyer_keypair_from_aws()

    # Create tester
    tester = SolanaLoadTestV4(seller_pubkey=seller_pubkey, buyer_keypair=buyer_keypair)

    # Run test
    tester.run_sequential_test(args.num_requests, verbose=args.verbose)
