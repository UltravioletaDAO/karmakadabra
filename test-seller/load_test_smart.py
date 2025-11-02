#!/usr/bin/env python3
"""
Smart Load Test for Test Seller with exponential backoff and adaptive delays
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from load_test import TestSellerLoadTest, LoadTestStats, SELLER_ADDRESS, PRICE_USDC
import time
import argparse

class SmartLoadTester(TestSellerLoadTest):
    """Enhanced load tester with smart delays and exponential backoff"""

    def run_smart_sequential_test(self, num_requests: int, verbose: bool = False,
                                  check_balances: bool = False, round_robin: bool = True):
        """Run sequential test with smart delays and exponential backoff

        Features:
        - Exponential backoff on consecutive failures (5s -> 10s -> 20s -> 40s -> max 60s)
        - Resets delay to base (5s) after a successful request
        - Round-robin across 3 buyer wallets to avoid single-wallet rate limiting
        """
        print(f"\n[START] Smart Sequential Test: {num_requests} requests")
        if round_robin:
            print("[MODE] Round-robin across 3 buyer wallets with smart delays")
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

        # Load all 3 buyers for round-robin
        buyers = []
        if round_robin:
            print("[INIT] Loading 3 buyer wallets for round-robin...")
            for buyer_id in [0, 1, 2]:
                try:
                    # Suppress buyer init output
                    import sys
                    from io import StringIO
                    old_stdout = sys.stdout
                    sys.stdout = StringIO()

                    buyer = TestSellerLoadTest(buyer_id=buyer_id)

                    sys.stdout = old_stdout
                    buyers.append(buyer)
                    print(f"[INIT] Buyer {buyer_id}: {buyer.account.address}")
                except Exception as e:
                    sys.stdout = old_stdout
                    print(f"[WARNING] Could not load buyer {buyer_id}: {e}")

            if not buyers:
                print("[ERROR] No buyers could be loaded. Falling back to single buyer.")
                buyers = [self]
            else:
                print(f"[INIT] Loaded {len(buyers)} buyer wallets")
        else:
            buyers = [self]

        # Smart delay tracking
        consecutive_failures = 0
        base_delay = 5.0  # Base delay between requests
        last_request_time = time.time()

        for i in range(num_requests):
            # Select buyer (round-robin if multiple buyers)
            buyer = buyers[i % len(buyers)] if len(buyers) > 1 else self

            self.stats.total_requests += 1
            success = buyer.make_paid_request(i + 1, verbose=verbose)

            if success:
                self.stats.successful += 1
                self.stats.total_cost_usdc += float(PRICE_USDC) / 1000000
                consecutive_failures = 0  # Reset failure counter on success
            else:
                self.stats.failed += 1
                consecutive_failures += 1

            # Don't sleep after the last request
            if i < num_requests - 1:
                # Smart delay with exponential backoff on failures
                if consecutive_failures > 0:
                    # Exponential backoff: 5s, 10s, 20s, 40s, max 60s
                    delay = min(base_delay * (2 ** (consecutive_failures - 1)), 60.0)
                    if consecutive_failures > 1:
                        print(f"[BACKOFF] {consecutive_failures} consecutive failures, waiting {delay:.1f}s before next request")
                else:
                    delay = base_delay

                time.sleep(delay)
                last_request_time = time.time()

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

        # Print summary
        self.stats.print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart load test for test-seller")
    parser.add_argument("--num-requests", type=int, default=10, help="Number of requests to make (default: 10)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output for each request")
    parser.add_argument("--check-balances", action="store_true", help="Check USDC balances before/after test")
    parser.add_argument("--single-wallet", action="store_true", help="Use only 1 wallet instead of round-robin (default: round-robin)")
    parser.add_argument("--buyer-id", type=int, default=0, choices=[0, 1, 2], help="Buyer wallet ID (0, 1, or 2) - only used with --single-wallet")

    args = parser.parse_args()

    print("=" * 80)
    print("SMART LOAD TESTER - Test Seller x402 Payment System")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  Requests: {args.num_requests}")
    print(f"  Verbose: {args.verbose}")
    print(f"  Check Balances: {args.check_balances}")
    print(f"  Mode: {'Single Wallet' if args.single_wallet else 'Round-Robin (3 wallets)'}")
    if args.single_wallet:
        print(f"  Buyer ID: {args.buyer_id}")
    print()

    tester = SmartLoadTester(buyer_id=args.buyer_id if args.single_wallet else 0)
    tester.run_smart_sequential_test(
        num_requests=args.num_requests,
        verbose=args.verbose,
        check_balances=args.check_balances,
        round_robin=not args.single_wallet
    )
