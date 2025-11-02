#!/usr/bin/env python3
"""
Async Parallel Load Test for Test Seller
Uses asyncio and aiohttp for true concurrent requests
"""
import asyncio
import aiohttp
import time
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List
import argparse

# Import from load_test for wallet management
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from load_test import TestSellerLoadTest, SELLER_ADDRESS, PRICE_USDC, TEST_SELLER_URL


@dataclass
class AsyncTestResult:
    """Result of an async test request"""
    request_id: int
    buyer_address: str
    success: bool
    duration: float  # seconds
    status_code: int = None
    error_message: str = None
    tx_hash: str = None


class AsyncLoadTester:
    """Async parallel load tester"""

    def __init__(self):
        """Initialize with 3 buyer wallets"""
        print("[INIT] Loading 3 buyer wallets...")
        self.buyers = []
        for buyer_id in [0, 1, 2]:
            buyer = TestSellerLoadTest(buyer_id=buyer_id)
            self.buyers.append(buyer)
            print(f"[INIT] Buyer {buyer_id}: {buyer.account.address}")

        self.results: List[AsyncTestResult] = []

    async def make_async_request(self, session: aiohttp.ClientSession, buyer: TestSellerLoadTest,
                                 request_id: int, verbose: bool = False) -> AsyncTestResult:
        """Make a single async payment request

        Args:
            session: aiohttp session
            buyer: Buyer instance to use for signing
            request_id: Unique request identifier
            verbose: Print detailed logs
        """
        start_time = time.time()
        buyer_address = buyer.account.address

        try:
            # Generate payment signature
            signature, authorization = buyer.sign_transfer_authorization()

            # Construct payment payload (matching load_test.py format)
            payment = {
                "x402Version": 1,  # Root level (VerifyRequest struct) - must be int
                "paymentPayload": {
                    "scheme": "exact",
                    "x402Version": 1,  # Inside paymentPayload (PaymentPayload struct) - REQUIRED!
                    "network": "base",
                    "payload": {
                        "signature": signature,
                        "authorization": authorization,
                    }
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
                    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC Base
                    "extra": {
                        "name": "USD Coin",
                        "version": "2"
                    }
                }
            }

            # Make async POST request
            async with session.post(
                f"{TEST_SELLER_URL}/hello",
                json=payment,
                timeout=aiohttp.ClientTimeout(total=90),  # 90s timeout
                headers={'Content-Type': 'application/json'}
            ) as response:
                duration = time.time() - start_time
                status_code = response.status

                if status_code == 200:
                    data = await response.json()
                    tx_hash = data.get('tx_hash') or data.get('transaction_hash')

                    if verbose:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        print(f"[{request_id:04d}] [{timestamp}] SUCCESS - {buyer_address[:10]}... - {duration:.2f}s")
                        if tx_hash:
                            print(f"[{request_id:04d}] [{timestamp}] TX: {tx_hash}")

                    return AsyncTestResult(
                        request_id=request_id,
                        buyer_address=buyer_address,
                        success=True,
                        duration=duration,
                        status_code=status_code,
                        tx_hash=tx_hash
                    )
                else:
                    error_text = await response.text()
                    if verbose:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        print(f"[{request_id:04d}] [{timestamp}] FAILED - HTTP {status_code} - {buyer_address[:10]}... - {duration:.2f}s")
                        print(f"[{request_id:04d}] [{timestamp}] Error: {error_text[:200]}")

                    return AsyncTestResult(
                        request_id=request_id,
                        buyer_address=buyer_address,
                        success=False,
                        duration=duration,
                        status_code=status_code,
                        error_message=error_text[:200]
                    )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            if verbose:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{request_id:04d}] [{timestamp}] TIMEOUT - {buyer_address[:10]}... - {duration:.2f}s")

            return AsyncTestResult(
                request_id=request_id,
                buyer_address=buyer_address,
                success=False,
                duration=duration,
                error_message="Timeout after 90s"
            )

        except Exception as e:
            duration = time.time() - start_time
            if verbose:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{request_id:04d}] [{timestamp}] ERROR - {buyer_address[:10]}... - {str(e)}")

            return AsyncTestResult(
                request_id=request_id,
                buyer_address=buyer_address,
                success=False,
                duration=duration,
                error_message=str(e)
            )

    async def run_parallel_batch(self, batch_size: int, total_requests: int,
                                 verbose: bool = False, stagger_ms: int = 0):
        """Run parallel requests in batches

        Args:
            batch_size: Number of concurrent requests per batch
            total_requests: Total number of requests to make
            verbose: Print detailed logs
            stagger_ms: Delay in milliseconds between starting each request in a batch (default: 0)
        """
        print(f"\n[START] Async Parallel Test")
        print(f"  Total Requests: {total_requests}")
        print(f"  Batch Size: {batch_size} concurrent requests")
        print(f"  Stagger: {stagger_ms}ms between requests in batch")
        print("=" * 80)

        start_time = time.time()
        request_id = 1

        async with aiohttp.ClientSession() as session:
            for batch_num in range(0, total_requests, batch_size):
                batch_count = min(batch_size, total_requests - batch_num)
                print(f"\n[BATCH {batch_num // batch_size + 1}] Starting {batch_count} concurrent requests...")

                # Create tasks for this batch
                tasks = []
                for i in range(batch_count):
                    buyer = self.buyers[request_id % len(self.buyers)]
                    task = self.make_async_request(session, buyer, request_id, verbose)
                    tasks.append(task)
                    request_id += 1

                    # Stagger requests if specified
                    if stagger_ms > 0 and i < batch_count - 1:
                        await asyncio.sleep(stagger_ms / 1000.0)

                # Wait for all tasks in this batch to complete
                batch_results = await asyncio.gather(*tasks)
                self.results.extend(batch_results)

                # Print batch summary
                batch_success = sum(1 for r in batch_results if r.success)
                batch_failed = len(batch_results) - batch_success
                avg_duration = sum(r.duration for r in batch_results) / len(batch_results)

                print(f"[BATCH COMPLETE] Success: {batch_success}/{batch_count}, Failed: {batch_failed}, Avg Duration: {avg_duration:.2f}s")

                # Small delay between batches to avoid overwhelming the service
                if batch_num + batch_size < total_requests:
                    await asyncio.sleep(2.0)

        end_time = time.time()
        duration = end_time - start_time

        # Print final summary
        self.print_summary(duration)

    def print_summary(self, total_duration: float):
        """Print test summary"""
        print(f"\n{'='*80}")
        print("ASYNC LOAD TEST RESULTS")
        print(f"{'='*80}")

        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful

        print(f"Total Requests:    {total}")
        print(f"Successful:        {successful} ({successful/total*100:.1f}%)")
        print(f"Failed:            {failed} ({failed/total*100:.1f}%)")
        print(f"Total Duration:    {total_duration:.2f}s")
        print(f"Requests/sec:      {total/total_duration:.2f}")

        if successful > 0:
            avg_duration = sum(r.duration for r in self.results if r.success) / successful
            min_duration = min(r.duration for r in self.results if r.success)
            max_duration = max(r.duration for r in self.results if r.success)

            print(f"\nSuccess Timings:")
            print(f"  Average:         {avg_duration:.2f}s")
            print(f"  Min:             {min_duration:.2f}s")
            print(f"  Max:             {max_duration:.2f}s")

        if failed > 0:
            print(f"\nFailure Breakdown:")
            timeouts = sum(1 for r in self.results if not r.success and "Timeout" in (r.error_message or ""))
            errors = sum(1 for r in self.results if not r.success and r.status_code and r.status_code >= 500)
            client_errors = sum(1 for r in self.results if not r.success and r.status_code and 400 <= r.status_code < 500)

            if timeouts > 0:
                print(f"  Timeouts:        {timeouts}")
            if errors > 0:
                print(f"  Server Errors:   {errors}")
            if client_errors > 0:
                print(f"  Client Errors:   {client_errors}")

        # Show transaction hashes
        tx_hashes = [r.tx_hash for r in self.results if r.success and r.tx_hash]
        if tx_hashes:
            print(f"\nTransaction Hashes ({len(tx_hashes)}):")
            for i, tx_hash in enumerate(tx_hashes[:10], 1):  # Show first 10
                print(f"  {i}. https://basescan.org/tx/{tx_hash}")
            if len(tx_hashes) > 10:
                print(f"  ... and {len(tx_hashes) - 10} more")

        print(f"{'='*80}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async parallel load test for test-seller")
    parser.add_argument("--num-requests", type=int, default=10, help="Total number of requests (default: 10)")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of concurrent requests per batch (default: 5)")
    parser.add_argument("--stagger-ms", type=int, default=0, help="Milliseconds to stagger requests within a batch (default: 0)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output for each request")

    args = parser.parse_args()

    print("=" * 80)
    print("ASYNC PARALLEL LOAD TESTER - Test Seller x402 Payment System")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  Total Requests:  {args.num_requests}")
    print(f"  Batch Size:      {args.batch_size}")
    print(f"  Stagger:         {args.stagger_ms}ms")
    print(f"  Verbose:         {args.verbose}")
    print()

    tester = AsyncLoadTester()
    asyncio.run(tester.run_parallel_batch(
        batch_size=args.batch_size,
        total_requests=args.num_requests,
        verbose=args.verbose,
        stagger_ms=args.stagger_ms
    ))
