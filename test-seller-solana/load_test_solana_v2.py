#!/usr/bin/env python3
"""
Load Test for Solana Test Seller
Creates SPL Token transfer transactions and tests x402 payment flow
"""
import argparse
import json
import os
import sys
import time
import base64
from typing import Dict, Any
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Add parent directory to path for shared modules

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.system_program import ID as SYSTEM_PROGRAM_ID  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from solders.message import MessageV0  # type: ignore
from solders.instruction import Instruction, AccountMeta  # type: ignore
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore
from solders.hash import Hash  # type: ignore
from spl.token.instructions import (  # type: ignore
    transfer_checked,
    TransferCheckedParams,
    get_associated_token_address,
)
from spl.token.constants import TOKEN_PROGRAM_ID  # type: ignore

# Configuration
TEST_SELLER_URL = os.getenv(
    "TEST_SELLER_URL",
    "https://test-seller-solana.karmacadabra.ultravioletadao.xyz"
)
SELLER_PUBKEY = os.getenv("SELLER_PUBKEY")  # Set this or pass via arg
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
PRICE_USDC = 10000  # 0.01 USDC (6 decimals)
USDC_DECIMALS = 6


def load_buyer_keypair_from_aws() -> Keypair:
    """Load buyer keypair from AWS Secrets Manager"""
    try:
        import boto3

        logger.info("Loading buyer keypair from AWS Secrets Manager...")
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        response = secrets_client.get_secret_value(SecretId='karmacadabra-test-buyer-solana')
        config = json.loads(response['SecretString'])

        # Extract keypair array from secret
        keypair_data = config.get('keypair')
        if not keypair_data:
            raise ValueError("No 'keypair' field found in AWS secret")

        buyer = Keypair.from_bytes(bytes(keypair_data))
        logger.info(f"Loaded buyer keypair from AWS: {buyer.pubkey()}")
        return buyer

    except Exception as e:
        logger.error(f"Failed to load from AWS Secrets Manager: {e}")
        raise


class SolanaLoadTest:
    """Load tester for Solana x402 payment system"""

    def __init__(self, seller_pubkey: str, buyer_keypair_path: Optional[str] = None, buyer_keypair: Optional[Keypair] = None):
        """
        Initialize load tester

        Args:
            seller_pubkey: Seller's Solana public key
            buyer_keypair_path: Path to buyer's Solana keypair JSON file (optional)
            buyer_keypair: Buyer's Keypair object (optional, if not loading from file)
        """
        # Load buyer keypair from path or use provided keypair
        if buyer_keypair:
            self.buyer = buyer_keypair
        elif buyer_keypair_path:
            with open(buyer_keypair_path, 'r') as f:
                keypair_data = json.load(f)
            self.buyer = Keypair.from_bytes(bytes(keypair_data))
        else:
            raise ValueError("Either buyer_keypair_path or buyer_keypair must be provided")

        self.seller = Pubkey.from_string(seller_pubkey)

        print(f"[INIT] Buyer pubkey: {self.buyer.pubkey()}")
        print(f"[INIT] Seller pubkey: {self.seller}")
        print(f"[INIT] Test seller: {TEST_SELLER_URL}")
        print(f"[INIT] Price per request: {PRICE_USDC / 1_000_000} USDC")

    def create_transfer_transaction(self) -> str:
        """
        Create a SPL Token transfer transaction

        Returns:
            Base64-encoded serialized VersionedTransaction
        """
        # Get buyer's USDC token account (ATA)
        buyer_ata = get_associated_token_address(self.buyer.pubkey(), USDC_MINT)

        # Get seller's USDC token account (ATA)
        seller_ata = get_associated_token_address(self.seller, USDC_MINT)

        # Create instructions
        instructions = []

        # 1. Set compute unit limit (required by facilitator)
        compute_limit_ix = set_compute_unit_limit(200_000)
        instructions.append(compute_limit_ix)

        # 2. Set compute unit price (required by facilitator, max 5_000_000 microlamports)
        compute_price_ix = set_compute_unit_price(1_000_000)  # 1M microlamports
        instructions.append(compute_price_ix)

        # 3. Transfer USDC (TransferChecked)
        transfer_ix = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=buyer_ata,
                mint=USDC_MINT,
                dest=seller_ata,
                owner=self.buyer.pubkey(),
                amount=PRICE_USDC,
                decimals=USDC_DECIMALS,
            )
        )
        instructions.append(transfer_ix)

        # Create message with placeholder blockhash
        # Facilitator will replace this with a recent blockhash before signing
        recent_blockhash = Hash.default()

        message = MessageV0.try_compile(
            payer=self.buyer.pubkey(),
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash,
        )

        # Create transaction and sign with buyer's key
        tx = VersionedTransaction(message, [self.buyer])

        # Serialize to bytes then base64
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

            # Build x402 payment payload
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
                    "maxAmountRequired": str(PRICE_USDC),
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
                print(f"\n[{request_id:04d}] [{timestamp}] ========== REQUEST DETAILS ==========")
                print(f"[{request_id:04d}] Buyer: {self.buyer.pubkey()}")
                print(f"[{request_id:04d}] Seller: {self.seller}")
                print(f"[{request_id:04d}] Amount: {PRICE_USDC / 1_000_000} USDC")
                print(f"[{request_id:04d}] Transaction (base64): {transaction_b64[:50]}...")

            # Make HTTP request
            response = requests.post(
                f"{TEST_SELLER_URL}/hello",
                json=payload,
                timeout=120  # 120s timeout for Solana
            )

            if response.status_code == 200:
                data = response.json()
                tx_hash = data.get('tx_hash')

                if verbose:
                    print(f"[{request_id:04d}] [{timestamp}] ✓ SUCCESS")
                    print(f"[{request_id:04d}] Response: {data.get('message')}")
                    if tx_hash:
                        print(f"[{request_id:04d}] TX: https://solscan.io/tx/{tx_hash}")
                else:
                    print(f"[{request_id:04d}] SUCCESS - {data.get('message')} - {PRICE_USDC / 1_000_000} USDC - Payer: {str(self.buyer.pubkey())[:10]}...")

                return True
            else:
                error_text = response.text
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                if verbose:
                    print(f"[{request_id:04d}] [{timestamp}] ✗ FAILED - HTTP {response.status_code}")
                    print(f"[{request_id:04d}] Error: {error_text[:200]}")
                else:
                    print(f"[{request_id:04d}] [{timestamp}] FAILED - HTTP {response.status_code}")
                    print(f"[{request_id:04d}] Error: {error_text[:100]}")

                return False

        except requests.exceptions.Timeout:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{request_id:04d}] [{timestamp}] ERROR - Request timeout after 120s")
            return False
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{request_id:04d}] [{timestamp}] ERROR - {str(e)}")
            if verbose:
                import traceback
                traceback.print_exc()
            return False

    def run_sequential_test(self, num_requests: int, verbose: bool = False):
        """
        Run sequential load test

        Args:
            num_requests: Number of requests to make
            verbose: Print detailed logs
        """
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
    parser = argparse.ArgumentParser(description="Load test for Solana test-seller")
    parser.add_argument("--keypair", type=str, help="Path to buyer keypair JSON file (optional, loads from AWS Secrets Manager if not provided)")
    parser.add_argument("--seller", type=str, help="Seller's Solana public key (overrides SELLER_PUBKEY env)")
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
    print("SOLANA LOAD TESTER - Test Seller x402 Payment System")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Test Seller:  {TEST_SELLER_URL}")
    print(f"  Seller:       {seller_pubkey}")
    print(f"  Requests:     {args.num_requests}")
    print(f"  Verbose:      {args.verbose}")
    print()

    # Load buyer keypair from AWS if not provided via --keypair
    buyer_keypair = None
    if not args.keypair:
        logger.info("No --keypair provided, loading from AWS Secrets Manager...")
        buyer_keypair = load_buyer_keypair_from_aws()

    # Create tester
    if buyer_keypair:
        tester = SolanaLoadTest(seller_pubkey=seller_pubkey, buyer_keypair=buyer_keypair)
    else:
        tester = SolanaLoadTest(seller_pubkey=seller_pubkey, buyer_keypair_path=args.keypair)

    tester.run_sequential_test(args.num_requests, verbose=args.verbose)
