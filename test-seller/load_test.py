#!/usr/bin/env python3
"""
Load Testing Script for Test Seller
Generates valid EIP-712 signatures and hits test-seller.karmacadabra.ultravioletadao.xyz
"""

import os
import time
import random
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Any

import requests
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3


def safe_print(msg: str):
    """Print with fallback for Unicode encoding issues on Windows"""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Replace problematic characters with ASCII equivalents
        msg = msg.encode('ascii', 'replace').decode('ascii')
        print(msg)


# Configuration
TEST_SELLER_URL = "https://test-seller.karmacadabra.ultravioletadao.xyz"
FACILITATOR_URL = "https://facilitator.ultravioletadao.xyz"
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
SELLER_ADDRESS = "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19"
PRICE_USDC = "10000"  # $0.01 USDC


@dataclass
class LoadTestStats:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    total_cost_usdc: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def requests_per_second(self) -> float:
        return self.total_requests / self.duration if self.duration > 0 else 0

    @property
    def success_rate(self) -> float:
        return (self.successful / self.total_requests * 100) if self.total_requests > 0 else 0


class TestSellerLoadTest:
    def __init__(self, private_key: str = None):
        # Load from AWS Secrets Manager if no private key provided
        if private_key is None:
            private_key = self._load_private_key_from_aws()

        self.account = Account.from_key(private_key)
        self.w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
        self.stats = LoadTestStats()

        # USDC contract for balance checking
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_BASE_ADDRESS),
            abi=[{
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            }]
        )

        print(f"[INIT] Payer wallet: {self.account.address}")
        print(f"[INIT] Test seller: {TEST_SELLER_URL}")
        print(f"[INIT] Price per request: ${float(PRICE_USDC)/1000000:.2f} USDC")

    def _load_private_key_from_aws(self) -> str:
        """Load test-buyer private key from AWS Secrets Manager"""
        try:
            import boto3
            import json

            secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
            response = secrets_client.get_secret_value(SecretId='karmacadabra-test-buyer')
            config = json.loads(response['SecretString'])

            print("[INFO] Loaded test-buyer wallet from AWS Secrets Manager")
            return config['private_key']
        except Exception as e:
            print(f"[ERROR] Failed to load from AWS Secrets Manager: {e}")
            print("[ERROR] Please provide --private-key or configure AWS credentials")
            raise

    def get_balance(self, address: str) -> float:
        """Get USDC balance for an address"""
        try:
            balance = self.usdc_contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
            return balance / 1000000  # 6 decimals
        except Exception as e:
            print(f"[WARNING] Failed to get balance for {address}: {e}")
            return 0

    def create_eip712_domain(self) -> Dict[str, Any]:
        """Create EIP-712 domain for USDC on Base"""
        return {
            "name": "USD Coin",
            "version": "2",
            "chainId": 8453,  # Base mainnet
            "verifyingContract": USDC_BASE_ADDRESS,
        }

    def sign_transfer_authorization(self) -> tuple[str, Dict[str, Any]]:
        """Sign EIP-712 TransferWithAuthorization"""
        # Generate random nonce
        nonce = "0x" + os.urandom(32).hex()

        # Timestamps (EIP-3009 spec)
        valid_after = int(time.time()) - 60  # 1 minute ago (ensure immediate validity)
        valid_before = int(time.time()) + 600  # 10 minutes from now

        domain = self.create_eip712_domain()

        message = {
            "from": self.account.address,
            "to": SELLER_ADDRESS,
            "value": int(PRICE_USDC),
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
        }

        structured_data = {
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
            "domain": domain,
            "message": message,
        }

        encoded = encode_typed_data(full_message=structured_data)
        signed = self.account.sign_message(encoded)

        # Return signature and authorization (with timestamps as strings)
        authorization = {
            "from": self.account.address,
            "to": SELLER_ADDRESS,
            "value": PRICE_USDC,
            "validAfter": str(valid_after),
            "validBefore": str(valid_before),
            "nonce": nonce,
        }

        return signed.signature.hex(), authorization

    def make_paid_request(self, request_id: int, verbose: bool = False) -> bool:
        """Make a single paid request to test-seller"""
        try:
            # Sign payment authorization
            signature, authorization = self.sign_transfer_authorization()

            # Build x402 payment payload (facilitator expects direct structure without "x402Payment" wrapper)
            payload = {
                "paymentPayload": {
                    "x402Version": 1,
                    "scheme": "exact",
                    "network": "base",
                    "payload": {
                        "signature": signature,
                        "authorization": authorization,
                    },
                },
                "paymentRequirements": {
                    "scheme": "exact",
                    "network": "base",
                    "maxAmountRequired": PRICE_USDC,
                    "resource": f"{TEST_SELLER_URL}/hello",
                    "description": "Hello World message",
                    "mimeType": "application/json",
                    "payTo": SELLER_ADDRESS,
                    "maxTimeoutSeconds": 60,
                    "asset": USDC_BASE_ADDRESS,
                    "extra": {
                        "name": "USD Coin",
                        "version": "2",
                    },
                },
            }

            if verbose:
                print(f"\n[{request_id:04d}] ========== REQUEST DETAILS ==========")
                print(f"[{request_id:04d}] Nonce: {authorization['nonce']}")
                print(f"[{request_id:04d}] Signature: {signature[:20]}...{signature[-20:]}")
                print(f"[{request_id:04d}] Valid: {authorization['validAfter']} to {authorization['validBefore']}")
                print(f"[{request_id:04d}] Full x402Payment JSON:")
                import json
                print(json.dumps(payload, indent=2)[:1000])

            # Send POST request
            response = requests.post(
                f"{TEST_SELLER_URL}/hello",
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()

                if verbose:
                    safe_print(f"[{request_id:04d}] ========== RESPONSE ==========")
                    safe_print(f"[{request_id:04d}] Status: {response.status_code}")
                    safe_print(f"[{request_id:04d}] Message: {data.get('message')}")
                    safe_print(f"[{request_id:04d}] Price: {data.get('price')}")
                    safe_print(f"[{request_id:04d}] Payer: {data.get('payer')}")
                    safe_print(f"[{request_id:04d}] Seller: {data.get('seller')}")
                    safe_print(f"[{request_id:04d}] Network: {data.get('network')}")

                    # Try to get transaction hash from response headers or facilitator
                    tx_hash = data.get('transaction_hash') or data.get('tx_hash') or data.get('txHash')
                    if tx_hash:
                        safe_print(f"[{request_id:04d}] TX Hash: {tx_hash}")
                        safe_print(f"[{request_id:04d}] BaseScan: https://basescan.org/tx/{tx_hash}")

                    safe_print(f"[{request_id:04d}] =====================================\n")
                else:
                    safe_print(f"[{request_id:04d}] SUCCESS - {data.get('message')} - {data.get('price')} - Payer: {data.get('payer', 'unknown')[:10]}...")

                return True
            else:
                print(f"[{request_id:04d}] FAILED - HTTP {response.status_code}")

                if verbose:
                    print(f"[{request_id:04d}] ========== ERROR RESPONSE ==========")
                    try:
                        error_data = response.json()
                        print(f"[{request_id:04d}] Error: {json.dumps(error_data, indent=2)}")
                    except:
                        print(f"[{request_id:04d}] Response: {response.text[:500]}")
                    print(f"[{request_id:04d}] ===================================\n")
                else:
                    print(f"[{request_id:04d}] Response: {response.text[:100]}")

                return False

        except Exception as e:
            print(f"[{request_id:04d}] ERROR - {str(e)}")
            if verbose:
                import traceback
                print(f"[{request_id:04d}] Traceback: {traceback.format_exc()}")
            return False

    def run_sequential_test(self, num_requests: int, verbose: bool = False, check_balances: bool = False):
        """Run sequential load test (one request at a time)"""
        print(f"\n[START] Sequential test: {num_requests} requests")
        print("=" * 60)

        # Check initial balances
        if check_balances:
            print("\n[BALANCE CHECK] Getting initial balances...")
            buyer_initial = self.get_balance(self.account.address)
            seller_initial = self.get_balance(SELLER_ADDRESS)
            print(f"[BALANCE] Buyer (payer):  ${buyer_initial:.6f} USDC")
            print(f"[BALANCE] Seller (payee): ${seller_initial:.6f} USDC")
            print()

        self.stats = LoadTestStats()
        self.stats.start_time = time.time()

        for i in range(num_requests):
            self.stats.total_requests += 1
            if self.make_paid_request(i + 1, verbose=verbose):
                self.stats.successful += 1
                self.stats.total_cost_usdc += float(PRICE_USDC) / 1000000
            else:
                self.stats.failed += 1

            # Small delay to avoid overwhelming the service
            time.sleep(0.1)

        self.stats.end_time = time.time()

        # Check final balances
        if check_balances:
            print("\n[BALANCE CHECK] Getting final balances...")
            buyer_final = self.get_balance(self.account.address)
            seller_final = self.get_balance(SELLER_ADDRESS)
            buyer_change = buyer_final - buyer_initial
            seller_change = seller_final - seller_initial

            print(f"[BALANCE] Buyer (payer):  ${buyer_final:.6f} USDC (change: ${buyer_change:+.6f})")
            print(f"[BALANCE] Seller (payee): ${seller_final:.6f} USDC (change: ${seller_change:+.6f})")

            expected_change = self.stats.successful * float(PRICE_USDC) / 1000000
            print(f"[BALANCE] Expected transfer: ${expected_change:.6f} USDC")

            if abs(abs(buyer_change) - expected_change) < 0.000001:
                print(f"[BALANCE] [OK] Buyer balance change matches expected")
            else:
                print(f"[BALANCE] [WARNING] Buyer balance change (${abs(buyer_change):.6f}) doesn't match expected (${expected_change:.6f})")

            if abs(seller_change - expected_change) < 0.000001:
                print(f"[BALANCE] [OK] Seller balance change matches expected")
            else:
                print(f"[BALANCE] [WARNING] Seller balance change (${seller_change:.6f}) doesn't match expected (${expected_change:.6f})")

            print()

        self.print_stats()

    def run_concurrent_test(self, num_requests: int, max_workers: int = 10, verbose: bool = False, check_balances: bool = False):
        """Run concurrent load test (multiple requests in parallel)"""
        print(f"\n[START] Concurrent test: {num_requests} requests, {max_workers} workers")
        print("=" * 60)

        # Check initial balances
        if check_balances:
            print("\n[BALANCE CHECK] Getting initial balances...")
            buyer_initial = self.get_balance(self.account.address)
            seller_initial = self.get_balance(SELLER_ADDRESS)
            print(f"[BALANCE] Buyer (payer):  ${buyer_initial:.6f} USDC")
            print(f"[BALANCE] Seller (payee): ${seller_initial:.6f} USDC")
            print()

        self.stats = LoadTestStats()
        self.stats.start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.make_paid_request, i + 1, verbose): i
                for i in range(num_requests)
            }

            for future in as_completed(futures):
                self.stats.total_requests += 1
                if future.result():
                    self.stats.successful += 1
                    self.stats.total_cost_usdc += float(PRICE_USDC) / 1000000
                else:
                    self.stats.failed += 1

        self.stats.end_time = time.time()

        # Check final balances
        if check_balances:
            print("\n[BALANCE CHECK] Getting final balances...")
            buyer_final = self.get_balance(self.account.address)
            seller_final = self.get_balance(SELLER_ADDRESS)
            buyer_change = buyer_final - buyer_initial
            seller_change = seller_final - seller_initial

            print(f"[BALANCE] Buyer (payer):  ${buyer_final:.6f} USDC (change: ${buyer_change:+.6f})")
            print(f"[BALANCE] Seller (payee): ${seller_final:.6f} USDC (change: ${seller_change:+.6f})")

            expected_change = self.stats.successful * float(PRICE_USDC) / 1000000
            print(f"[BALANCE] Expected transfer: ${expected_change:.6f} USDC")

            if abs(abs(buyer_change) - expected_change) < 0.000001:
                print(f"[BALANCE] [OK] Buyer balance change matches expected")
            else:
                print(f"[BALANCE] [WARNING] Buyer balance change (${abs(buyer_change):.6f}) doesn't match expected (${expected_change:.6f})")

            if abs(seller_change - expected_change) < 0.000001:
                print(f"[BALANCE] [OK] Seller balance change matches expected")
            else:
                print(f"[BALANCE] [WARNING] Seller balance change (${seller_change:.6f}) doesn't match expected (${expected_change:.6f})")

            print()

        self.print_stats()

    def print_stats(self):
        """Print load test statistics"""
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print(f"Total Requests:    {self.stats.total_requests}")
        print(f"Successful:        {self.stats.successful} ({self.stats.success_rate:.1f}%)")
        print(f"Failed:            {self.stats.failed}")
        print(f"Duration:          {self.stats.duration:.2f}s")
        print(f"Requests/sec:      {self.stats.requests_per_second:.2f}")
        print(f"Total Cost:        ${self.stats.total_cost_usdc:.2f} USDC")
        print("=" * 60)


def check_balance(wallet_address: str):
    """Check USDC balance on Base for the payer wallet"""
    print(f"\n[INFO] Checking USDC balance for {wallet_address}...")

    # Base mainnet RPC
    rpc_url = "https://mainnet.base.org"
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # USDC contract ABI (balanceOf)
    usdc_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_BASE_ADDRESS),
        abi=[{
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        }]
    )

    try:
        balance = usdc_contract.functions.balanceOf(wallet_address).call()
        balance_usdc = balance / 1000000  # 6 decimals
        print(f"[INFO] USDC Balance: ${balance_usdc:.2f} USDC")
        return balance_usdc
    except Exception as e:
        print(f"[ERROR] Failed to check balance: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Load test the test-seller endpoint")
    parser.add_argument(
        "--private-key",
        required=False,
        default=None,
        help="Private key of payer wallet (defaults to test-buyer from AWS Secrets Manager)",
    )
    parser.add_argument(
        "--num-requests",
        type=int,
        default=10,
        help="Number of requests to send (default: 10)",
    )
    parser.add_argument(
        "--concurrent",
        action="store_true",
        help="Run concurrent test (default: sequential)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of concurrent workers (default: 10)",
    )
    parser.add_argument(
        "--check-balance",
        action="store_true",
        help="Check USDC balances before AND after test, validate that transfers occurred correctly",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed request/response information including nonce, signature, and facilitator responses",
    )

    args = parser.parse_args()

    # Initialize load tester
    tester = TestSellerLoadTest(args.private_key)

    # Check balance if requested
    if args.check_balance:
        balance = check_balance(tester.account.address)
        required = (args.num_requests * float(PRICE_USDC)) / 1000000
        print(f"[INFO] Required for {args.num_requests} requests: ${required:.2f} USDC")

        if balance < required:
            print(f"[WARNING] Insufficient balance! Need ${required - balance:.2f} more USDC")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("[EXIT] Aborting test")
                return

    # Run test (enable balance checking if --check-balance was used)
    if args.concurrent:
        tester.run_concurrent_test(args.num_requests, args.workers, verbose=args.verbose, check_balances=args.check_balance)
    else:
        tester.run_sequential_test(args.num_requests, verbose=args.verbose, check_balances=args.check_balance)


if __name__ == "__main__":
    main()
