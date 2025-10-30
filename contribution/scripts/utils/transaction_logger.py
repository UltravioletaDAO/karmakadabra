#!/usr/bin/env python3
"""
Transaction Logger Utility
Log bidirectional rating transactions to CSV for analysis.

Handles logging all transaction data including:
- Buyer/seller IDs and addresses
- Bidirectional ratings
- Transaction hashes
- Timestamps
- Scenario types
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class TransactionLogger:
    """
    Log transactions to CSV and JSON formats
    """

    def __init__(self, output_path: str = "../data/week2/transactions.csv"):
        """
        Initialize transaction logger

        Args:
            output_path: Path to output CSV file (relative to scripts/)
        """
        # Convert to absolute path
        self.csv_path = Path(__file__).parent.parent / output_path
        self.json_path = self.csv_path.with_suffix('.json')

        # Ensure output directory exists
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Transaction buffer
        self.transactions: List[Dict] = []

        # CSV columns
        self.columns = [
            'timestamp',
            'buyer_id',
            'buyer_address',
            'buyer_name',
            'seller_id',
            'seller_address',
            'seller_name',
            'buyer_rating',
            'seller_rating',
            'rating_diff',  # Calculated: buyer_rating - seller_rating
            'tx_hash',
            'scenario',
            'block_number',
            'gas_used',
            'notes'
        ]

        print(f"Transaction logger initialized: {self.csv_path}")

    def log_transaction(
        self,
        buyer_id: int,
        buyer_address: str,
        buyer_name: str,
        seller_id: int,
        seller_address: str,
        seller_name: str,
        buyer_rating: int,
        seller_rating: int,
        tx_hash: str,
        scenario: str,
        block_number: Optional[int] = None,
        gas_used: Optional[int] = None,
        notes: str = ""
    ):
        """
        Log a single transaction

        Args:
            buyer_id: Buyer agent ID from registry
            buyer_address: Buyer wallet address
            buyer_name: Buyer agent name
            seller_id: Seller agent ID from registry
            seller_address: Seller wallet address
            seller_name: Seller agent name
            buyer_rating: Rating buyer gave to seller (1-100)
            seller_rating: Rating seller gave to buyer (1-100)
            tx_hash: Transaction hash
            scenario: Scenario type (e.g., "good_transaction", "bad_client")
            block_number: Block number (optional)
            gas_used: Gas used (optional)
            notes: Additional notes (optional)
        """
        transaction = {
            'timestamp': datetime.now().isoformat(),
            'buyer_id': buyer_id,
            'buyer_address': buyer_address,
            'buyer_name': buyer_name,
            'seller_id': seller_id,
            'seller_address': seller_address,
            'seller_name': seller_name,
            'buyer_rating': buyer_rating,
            'seller_rating': seller_rating,
            'rating_diff': buyer_rating - seller_rating,
            'tx_hash': tx_hash,
            'scenario': scenario,
            'block_number': block_number or '',
            'gas_used': gas_used or '',
            'notes': notes
        }

        self.transactions.append(transaction)
        print(f"✅ Logged: {buyer_name} ↔ {seller_name} | {buyer_rating}/{seller_rating} | {scenario}")

    def save_csv(self):
        """Save transactions to CSV file"""
        if not self.transactions:
            print("⚠️  No transactions to save")
            return

        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns)
            writer.writeheader()
            writer.writerows(self.transactions)

        print(f"💾 Saved {len(self.transactions)} transactions to {self.csv_path}")

    def save_json(self):
        """Save transactions to JSON file"""
        if not self.transactions:
            print("⚠️  No transactions to save")
            return

        with open(self.json_path, 'w') as f:
            json.dump(self.transactions, f, indent=2)

        print(f"💾 Saved {len(self.transactions)} transactions to {self.json_path}")

    def save(self):
        """Save transactions to both CSV and JSON"""
        self.save_csv()
        self.save_json()

    def get_summary(self) -> Dict:
        """
        Get summary statistics of logged transactions

        Returns:
            Dictionary with summary stats
        """
        if not self.transactions:
            return {}

        # Calculate stats
        total = len(self.transactions)
        scenarios = {}
        rating_diffs = []

        for tx in self.transactions:
            # Count scenarios
            scenario = tx['scenario']
            scenarios[scenario] = scenarios.get(scenario, 0) + 1

            # Collect rating differences
            rating_diffs.append(tx['rating_diff'])

        # Calculate rating statistics
        avg_diff = sum(rating_diffs) / len(rating_diffs)
        max_diff = max(rating_diffs)
        min_diff = min(rating_diffs)

        # Count asymmetric ratings (diff > 10)
        asymmetric = sum(1 for diff in rating_diffs if abs(diff) > 10)

        return {
            'total_transactions': total,
            'scenarios': scenarios,
            'rating_stats': {
                'avg_difference': round(avg_diff, 2),
                'max_difference': max_diff,
                'min_difference': min_diff,
                'asymmetric_count': asymmetric,
                'asymmetric_percent': round(asymmetric / total * 100, 1)
            }
        }

    def print_summary(self):
        """Print summary statistics to console"""
        summary = self.get_summary()

        if not summary:
            print("No transactions logged yet")
            return

        print("\n" + "=" * 60)
        print("TRANSACTION SUMMARY")
        print("=" * 60)
        print(f"Total transactions: {summary['total_transactions']}")

        print("\nBy scenario:")
        for scenario, count in summary['scenarios'].items():
            percent = count / summary['total_transactions'] * 100
            print(f"  {scenario:20} {count:3} ({percent:5.1f}%)")

        print("\nRating differences (buyer - seller):")
        stats = summary['rating_stats']
        print(f"  Average difference:  {stats['avg_difference']:+.2f}")
        print(f"  Max difference:      {stats['max_difference']:+d}")
        print(f"  Min difference:      {stats['min_difference']:+d}")
        print(f"  Asymmetric (>10):    {stats['asymmetric_count']} ({stats['asymmetric_percent']:.1f}%)")
        print("=" * 60 + "\n")

    def clear(self):
        """Clear transaction buffer"""
        self.transactions = []
        print("🗑️  Transaction buffer cleared")

    def load_from_csv(self, csv_path: str):
        """
        Load transactions from existing CSV file

        Args:
            csv_path: Path to CSV file
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            print(f"❌ CSV file not found: {csv_path}")
            return

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            self.transactions = list(reader)

        print(f"📂 Loaded {len(self.transactions)} transactions from {csv_path}")


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transaction Logger Utility")
    parser.add_argument("--test", action="store_true", help="Run test with sample data")
    parser.add_argument("--load", help="Load transactions from CSV file")
    parser.add_argument("--summary", help="Show summary of CSV file")

    args = parser.parse_args()

    if args.test:
        print("Running test with sample data...\n")

        logger = TransactionLogger("../data/week2/test_transactions.csv")

        # Log some sample transactions
        logger.log_transaction(
            buyer_id=3, buyer_address="0xCf3...", buyer_name="client",
            seller_id=1, seller_address="0x2C3...", seller_name="karma-hello",
            buyer_rating=95, seller_rating=92,
            tx_hash="0xabc123...",
            scenario="good_transaction",
            notes="Test transaction"
        )

        logger.log_transaction(
            buyer_id=3, buyer_address="0xCf3...", buyer_name="client",
            seller_id=2, seller_address="0x940...", seller_name="abracadabra",
            buyer_rating=88, seller_rating=15,
            tx_hash="0xdef456...",
            scenario="bad_client",
            notes="Client was difficult"
        )

        logger.log_transaction(
            buyer_id=7, buyer_address="0xF8f...", buyer_name="0xultravioleta",
            seller_id=1, seller_address="0x2C3...", seller_name="karma-hello",
            buyer_rating=20, seller_rating=95,
            tx_hash="0xghi789...",
            scenario="bad_seller",
            notes="Poor quality service"
        )

        # Show summary
        logger.print_summary()

        # Save to files
        logger.save()

        print("\n✅ Test complete!")

    elif args.load:
        logger = TransactionLogger()
        logger.load_from_csv(args.load)
        logger.print_summary()

    elif args.summary:
        logger = TransactionLogger()
        logger.load_from_csv(args.summary)
        logger.print_summary()

    else:
        parser.print_help()
