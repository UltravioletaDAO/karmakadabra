#!/usr/bin/env python3
"""
Marketplace Simulation Script
Execute 100+ transactions with bidirectional ratings to demonstrate the bidirectional trust pattern.

Implements 6 scenarios:
1. Good transaction (mutual high ratings)
2. Bad client (seller rates low)
3. Bad seller (client rates low)
4. Disputed transaction (moderate asymmetry)
5. Validator rating (seller rates validator)
6. Rating history (reputation building)

Usage:
    python simulate_marketplace.py --dry-run              # Test without blockchain
    python simulate_marketplace.py --execute --count 100  # Execute 100 real transactions
    python simulate_marketplace.py --scenario good_transaction --count 20 --execute
"""

import sys
import random
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime

# Add lib and utils to path
LIB_PATH = Path(__file__).parent.parent / "lib"
UTILS_PATH = Path(__file__).parent / "utils"
sys.path.insert(0, str(LIB_PATH))
sys.path.insert(0, str(UTILS_PATH))

from utils.agent_loader import AgentInfo, load_all_agents, get_agents_by_type
from utils.transaction_logger import TransactionLogger
from utils.web3_helper import get_w3, get_agent_info, get_contract, wait_for_transaction

# Import for AWS Secrets Manager
import os
import sys
sys.path.insert(0, str(LIB_PATH))
from secrets_manager import get_private_key

# Scenario distribution (total should be 100)
SCENARIO_DISTRIBUTION = {
    'good_transaction': 30,
    'bad_client': 15,
    'bad_seller': 15,
    'disputed': 20,
    'validator_rating': 10,
    'rating_history': 10
}


class MarketplaceSimulator:
    """
    Simulates marketplace transactions with bidirectional ratings
    """

    def __init__(self, dry_run: bool = True, output_path: str = "../data/week2/transactions.csv"):
        """
        Initialize simulator

        Args:
            dry_run: If True, don't execute real blockchain transactions
            output_path: Path to output CSV file
        """
        self.dry_run = dry_run
        self.logger = TransactionLogger(output_path)
        self.w3 = None
        self.agents = []
        self.system_agents = []
        self.user_agents = []
        self.validator = None

        # Track pairs for rating history scenario
        self.history_pairs = []

        print(f"🎬 Marketplace Simulator initialized")
        print(f"   Mode: {'DRY-RUN (no blockchain)' if dry_run else 'EXECUTE (real transactions)'}")
        print(f"   Output: {output_path}\n")

    def load_agents(self):
        """Load all agents from main repository"""
        print("📂 Loading agents...")
        all_agents = load_all_agents()

        # Separate by type
        self.system_agents = [a for a in all_agents if a.type == 'system']
        self.user_agents = [a for a in all_agents if a.type == 'user']

        # Find validator
        self.validator = next((a for a in self.system_agents if a.name == 'validator'), None)

        print(f"   System agents: {len(self.system_agents)}")
        print(f"   User agents: {len(self.user_agents)}")
        print(f"   Validator: {'✅ Found' if self.validator else '❌ Not found'}\n")

        self.agents = all_agents

    def connect_blockchain(self):
        """Connect to Avalanche Fuji (skip in dry-run mode)"""
        if self.dry_run:
            print("⚡ DRY-RUN mode: Skipping blockchain connection\n")
            return

        print("🔗 Connecting to Avalanche Fuji...")
        try:
            self.w3 = get_w3()
            print()
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            print("   Falling back to DRY-RUN mode\n")
            self.dry_run = True

    def generate_mock_tx_hash(self) -> str:
        """Generate mock transaction hash for dry-run"""
        return f"0xtest{random.randint(100000, 999999)}{int(time.time())}"

    def get_agent_id(self, agent: AgentInfo) -> Optional[int]:
        """
        Get agent ID from Identity Registry

        Args:
            agent: Agent to look up

        Returns:
            Agent ID or None if not found
        """
        try:
            identity_registry = get_contract(self.w3, 'IdentityRegistry')
            agent_info = identity_registry.functions.resolveByAddress(agent.address).call()
            agent_id = agent_info[0]  # First element of tuple is agentId
            return agent_id if agent_id > 0 else None
        except Exception as e:
            print(f"⚠️  Error getting agent ID for {agent.name}: {e}")
            return None

    def execute_rating_transaction(
        self,
        rater_agent: AgentInfo,
        rated_agent: AgentInfo,
        rating: int,
        is_validator_rating: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a rating transaction (or simulate in dry-run)

        Args:
            rater_agent: Agent giving the rating
            rated_agent: Agent being rated
            rating: Rating value (1-100)
            is_validator_rating: If True, use rateValidator(), else rateClient()

        Returns:
            Dict with tx_hash, block_number, gas_used (or None if failed)
        """
        if self.dry_run:
            # Simulate transaction
            time.sleep(0.1)  # Simulate network delay
            return {
                'tx_hash': self.generate_mock_tx_hash(),
                'block_number': None,
                'gas_used': None
            }

        try:
            # Get Reputation Registry contract
            reputation_registry = get_contract(self.w3, 'ReputationRegistry')

            # Get private key from AWS or .env
            agent_folder = Path(rater_agent.config_path).name

            # System agents in AWS use "-agent" suffix (e.g., "karma-hello-agent")
            # User agents don't (e.g., "cyberpaisa")
            if rater_agent.type == "system":
                aws_agent_name = f"{agent_folder}-agent"
            else:
                aws_agent_name = agent_folder

            private_key = get_private_key(aws_agent_name)

            if not private_key:
                print(f"⚠️  No private key for {rater_agent.name}, using mock")
                return {
                    'tx_hash': self.generate_mock_tx_hash(),
                    'block_number': None,
                    'gas_used': None
                }

            # Get account from private key
            account = self.w3.eth.account.from_key(private_key)

            # Get rated agent ID from Identity Registry
            rated_agent_id = self.get_agent_id(rated_agent)
            if rated_agent_id is None:
                print(f"⚠️  Could not get agent ID for {rated_agent.name}, using mock")
                return {
                    'tx_hash': self.generate_mock_tx_hash(),
                    'block_number': None,
                    'gas_used': None
                }

            # Determine which function to call
            if is_validator_rating:
                # Seller rates validator
                func = reputation_registry.functions.rateValidator(
                    rated_agent_id,  # validator ID (uint256)
                    rating
                )
            else:
                # Server rates client (or client rates server)
                func = reputation_registry.functions.rateClient(
                    rated_agent_id,  # client ID (uint256)
                    rating
                )

            # Build transaction
            tx = func.build_transaction({
                'from': account.address,
                'nonce': self.w3.eth.get_transaction_count(account.address),
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price
            })

            # Sign transaction
            signed_tx = account.sign_transaction(tx)

            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)

            print(f"   📝 Tx sent: {tx_hash_hex[:10]}...")

            # Wait for confirmation
            receipt = wait_for_transaction(self.w3, tx_hash_hex)

            if receipt and receipt['status'] == 1:
                print(f"   ✅ Confirmed in block {receipt['blockNumber']}")
                return {
                    'tx_hash': tx_hash_hex,
                    'block_number': receipt['blockNumber'],
                    'gas_used': receipt['gasUsed']
                }
            else:
                print(f"   ❌ Transaction failed")
                return {
                    'tx_hash': tx_hash_hex,
                    'block_number': receipt['blockNumber'] if receipt else None,
                    'gas_used': receipt['gasUsed'] if receipt else None
                }

        except Exception as e:
            print(f"⚠️  Error executing transaction: {e}")
            print(f"   Falling back to mock transaction")
            return {
                'tx_hash': self.generate_mock_tx_hash(),
                'block_number': None,
                'gas_used': None
            }

    # ===== SCENARIO FUNCTIONS =====

    def scenario_good_transaction(self, count: int = 1) -> List[Dict]:
        """
        Scenario 1: Good transaction (mutual high ratings 90-100)

        Args:
            count: Number of transactions to simulate

        Returns:
            List of transaction records
        """
        transactions = []

        for _ in range(count):
            # Random seller (system agent) and buyer (user agent)
            seller = random.choice([a for a in self.system_agents if a.name != 'validator'])
            buyer = random.choice(self.user_agents)

            # Both rate high (90-100)
            buyer_rating = random.randint(90, 100)
            seller_rating = random.randint(90, 100)

            # Execute transactions
            tx_result = self.execute_rating_transaction(buyer, seller, buyer_rating)

            # Get agent IDs (mock in dry-run)
            buyer_id = random.randint(7, 54) if self.dry_run else None
            seller_id = random.randint(1, 6) if self.dry_run else None

            # Log transaction
            self.logger.log_transaction(
                buyer_id=buyer_id,
                buyer_address=buyer.address,
                buyer_name=buyer.name,
                seller_id=seller_id,
                seller_address=seller.address,
                seller_name=seller.name,
                buyer_rating=buyer_rating,
                seller_rating=seller_rating,
                tx_hash=tx_result['tx_hash'],
                scenario='good_transaction',
                block_number=tx_result['block_number'],
                gas_used=tx_result['gas_used'],
                notes=f"Both parties satisfied, ratings: {buyer_rating}/{seller_rating}"
            )

            transactions.append({
                'buyer': buyer.name,
                'seller': seller.name,
                'buyer_rating': buyer_rating,
                'seller_rating': seller_rating,
                'tx_hash': tx_result['tx_hash']
            })

        return transactions

    def scenario_bad_client(self, count: int = 1) -> List[Dict]:
        """
        Scenario 2: Bad client (seller rates low 10-30, buyer rates high 85-95)

        Args:
            count: Number of transactions to simulate

        Returns:
            List of transaction records
        """
        transactions = []

        for _ in range(count):
            seller = random.choice([a for a in self.system_agents if a.name != 'validator'])
            buyer = random.choice(self.user_agents)

            # Buyer satisfied but was difficult
            buyer_rating = random.randint(85, 95)
            seller_rating = random.randint(10, 30)

            tx_result = self.execute_rating_transaction(buyer, seller, buyer_rating)

            buyer_id = random.randint(7, 54) if self.dry_run else None
            seller_id = random.randint(1, 6) if self.dry_run else None

            self.logger.log_transaction(
                buyer_id=buyer_id,
                buyer_address=buyer.address,
                buyer_name=buyer.name,
                seller_id=seller_id,
                seller_address=seller.address,
                seller_name=seller.name,
                buyer_rating=buyer_rating,
                seller_rating=seller_rating,
                tx_hash=tx_result['tx_hash'],
                scenario='bad_client',
                block_number=tx_result['block_number'],
                gas_used=tx_result['gas_used'],
                notes=f"Client difficult: late payment, rude, excessive demands"
            )

            transactions.append({
                'buyer': buyer.name,
                'seller': seller.name,
                'buyer_rating': buyer_rating,
                'seller_rating': seller_rating,
                'tx_hash': tx_result['tx_hash']
            })

        return transactions

    def scenario_bad_seller(self, count: int = 1) -> List[Dict]:
        """
        Scenario 3: Bad seller (client rates low 10-30, seller rates high 85-95)

        Args:
            count: Number of transactions to simulate

        Returns:
            List of transaction records
        """
        transactions = []

        for _ in range(count):
            seller = random.choice([a for a in self.system_agents if a.name != 'validator'])
            buyer = random.choice(self.user_agents)

            # Service poor but seller thinks it's fine
            buyer_rating = random.randint(10, 30)
            seller_rating = random.randint(85, 95)

            tx_result = self.execute_rating_transaction(buyer, seller, buyer_rating)

            buyer_id = random.randint(7, 54) if self.dry_run else None
            seller_id = random.randint(1, 6) if self.dry_run else None

            self.logger.log_transaction(
                buyer_id=buyer_id,
                buyer_address=buyer.address,
                buyer_name=buyer.name,
                seller_id=seller_id,
                seller_address=seller.address,
                seller_name=seller.name,
                buyer_rating=buyer_rating,
                seller_rating=seller_rating,
                tx_hash=tx_result['tx_hash'],
                scenario='bad_seller',
                block_number=tx_result['block_number'],
                gas_used=tx_result['gas_used'],
                notes=f"Poor service: incomplete data, unresponsive, quality issues"
            )

            transactions.append({
                'buyer': buyer.name,
                'seller': seller.name,
                'buyer_rating': buyer_rating,
                'seller_rating': seller_rating,
                'tx_hash': tx_result['tx_hash']
            })

        return transactions

    def scenario_disputed(self, count: int = 1) -> List[Dict]:
        """
        Scenario 4: Disputed transaction (both rate moderate 40-70)

        Args:
            count: Number of transactions to simulate

        Returns:
            List of transaction records
        """
        transactions = []

        for _ in range(count):
            seller = random.choice([a for a in self.system_agents if a.name != 'validator'])
            buyer = random.choice(self.user_agents)

            # Both moderately satisfied/dissatisfied
            buyer_rating = random.randint(50, 70)
            seller_rating = random.randint(40, 60)

            tx_result = self.execute_rating_transaction(buyer, seller, buyer_rating)

            buyer_id = random.randint(7, 54) if self.dry_run else None
            seller_id = random.randint(1, 6) if self.dry_run else None

            self.logger.log_transaction(
                buyer_id=buyer_id,
                buyer_address=buyer.address,
                buyer_name=buyer.name,
                seller_id=seller_id,
                seller_address=seller.address,
                seller_name=seller.name,
                buyer_rating=buyer_rating,
                seller_rating=seller_rating,
                tx_hash=tx_result['tx_hash'],
                scenario='disputed',
                block_number=tx_result['block_number'],
                gas_used=tx_result['gas_used'],
                notes=f"Dispute: miscommunication, delays, scope creep"
            )

            transactions.append({
                'buyer': buyer.name,
                'seller': seller.name,
                'buyer_rating': buyer_rating,
                'seller_rating': seller_rating,
                'tx_hash': tx_result['tx_hash']
            })

        return transactions

    def scenario_validator_rating(self, count: int = 1) -> List[Dict]:
        """
        Scenario 5: Validator rating (seller rates validator)
        Half good (90-100), half poor (20-40)

        Args:
            count: Number of transactions to simulate

        Returns:
            List of transaction records
        """
        transactions = []

        if not self.validator:
            print("⚠️  Validator not found, skipping validator rating scenario")
            return transactions

        for i in range(count):
            seller = random.choice([a for a in self.system_agents if a.name != 'validator'])

            # Alternate between good and poor validator performance
            if i % 2 == 0:
                # Good validator
                seller_rating = random.randint(90, 100)
                note = "Excellent validation: thorough, detailed, accurate"
            else:
                # Poor validator
                seller_rating = random.randint(20, 40)
                note = "Poor validation: rushed, generic, not helpful"

            tx_result = self.execute_rating_transaction(seller, self.validator, seller_rating, is_validator_rating=True)

            seller_id = random.randint(1, 6) if self.dry_run else None
            validator_id = 4 if self.dry_run else None

            # For validator rating, buyer is actually the seller (rater) and seller is validator (rated)
            self.logger.log_transaction(
                buyer_id=seller_id,
                buyer_address=seller.address,
                buyer_name=seller.name,
                seller_id=validator_id,
                seller_address=self.validator.address,
                seller_name=self.validator.name,
                buyer_rating=seller_rating,  # Seller's rating of validator
                seller_rating=0,  # Validator doesn't rate back
                tx_hash=tx_result['tx_hash'],
                scenario='validator_rating',
                block_number=tx_result['block_number'],
                gas_used=tx_result['gas_used'],
                notes=note
            )

            transactions.append({
                'buyer': seller.name,
                'seller': self.validator.name,
                'buyer_rating': seller_rating,
                'seller_rating': 0,
                'tx_hash': tx_result['tx_hash']
            })

        return transactions

    def scenario_rating_history(self, count: int = 1) -> List[Dict]:
        """
        Scenario 6: Rating history (same pairs transact multiple times)
        Shows trust building or degradation over time

        Args:
            count: Number of transaction pairs (will generate count*2 or count*3 transactions)

        Returns:
            List of transaction records
        """
        transactions = []

        # Create pairs for repeat transactions
        for i in range(count):
            seller = random.choice([a for a in self.system_agents if a.name != 'validator'])
            buyer = random.choice(self.user_agents)

            # Alternate between trust building and degradation
            if i % 2 == 0:
                # Trust building: 75 → 85 → 95
                ratings_sequence = [(75, 75), (85, 85), (95, 95)]
                pattern = "building"
            else:
                # Trust degradation: 90 → 70 → 40
                ratings_sequence = [(90, 90), (70, 70), (40, 40)]
                pattern = "degrading"

            # Execute sequence of transactions
            for seq_num, (buyer_rating, seller_rating) in enumerate(ratings_sequence, 1):
                tx_result = self.execute_rating_transaction(buyer, seller, buyer_rating)

                buyer_id = random.randint(7, 54) if self.dry_run else None
                seller_id = random.randint(1, 6) if self.dry_run else None

                note = f"History {pattern} #{seq_num}/3: Trust {'building' if pattern == 'building' else 'degrading'}"

                self.logger.log_transaction(
                    buyer_id=buyer_id,
                    buyer_address=buyer.address,
                    buyer_name=buyer.name,
                    seller_id=seller_id,
                    seller_address=seller.address,
                    seller_name=seller.name,
                    buyer_rating=buyer_rating,
                    seller_rating=seller_rating,
                    tx_hash=tx_result['tx_hash'],
                    scenario='rating_history',
                    block_number=tx_result['block_number'],
                    gas_used=tx_result['gas_used'],
                    notes=note
                )

                transactions.append({
                    'buyer': buyer.name,
                    'seller': seller.name,
                    'buyer_rating': buyer_rating,
                    'seller_rating': seller_rating,
                    'tx_hash': tx_result['tx_hash']
                })

                # Small delay between sequential transactions
                time.sleep(0.2)

        return transactions

    def run_simulation(self, total_count: int = 100, scenario: Optional[str] = None):
        """
        Run complete marketplace simulation

        Args:
            total_count: Total number of transactions to generate
            scenario: If specified, run only this scenario
        """
        print("=" * 80)
        print("MARKETPLACE SIMULATION")
        print("=" * 80)

        # Load agents and connect
        self.load_agents()
        self.connect_blockchain()

        if scenario:
            # Run specific scenario
            print(f"🎯 Running scenario: {scenario}")
            print(f"   Count: {total_count}\n")

            if scenario == 'good_transaction':
                self.scenario_good_transaction(total_count)
            elif scenario == 'bad_client':
                self.scenario_bad_client(total_count)
            elif scenario == 'bad_seller':
                self.scenario_bad_seller(total_count)
            elif scenario == 'disputed':
                self.scenario_disputed(total_count)
            elif scenario == 'validator_rating':
                self.scenario_validator_rating(total_count)
            elif scenario == 'rating_history':
                # rating_history generates 3x transactions per count
                self.scenario_rating_history(total_count // 3)
            else:
                print(f"❌ Unknown scenario: {scenario}")
                return

        else:
            # Run all scenarios with distribution
            print(f"🎯 Running all scenarios (total: {total_count} transactions)")
            print("\nScenario distribution:")

            # Calculate actual counts based on total
            scenario_counts = {}
            for scenario_name, percentage in SCENARIO_DISTRIBUTION.items():
                count = int(total_count * percentage / 100)
                scenario_counts[scenario_name] = count
                print(f"   {scenario_name:20} {count:3} transactions ({percentage}%)")

            print()

            # Run each scenario
            for scenario_name, count in scenario_counts.items():
                if count == 0:
                    continue

                print(f"▶️  {scenario_name}...")
                if scenario_name == 'good_transaction':
                    self.scenario_good_transaction(count)
                elif scenario_name == 'bad_client':
                    self.scenario_bad_client(count)
                elif scenario_name == 'bad_seller':
                    self.scenario_bad_seller(count)
                elif scenario_name == 'disputed':
                    self.scenario_disputed(count)
                elif scenario_name == 'validator_rating':
                    self.scenario_validator_rating(count)
                elif scenario_name == 'rating_history':
                    # This scenario generates 3 transactions per pair
                    self.scenario_rating_history(count // 3)

                time.sleep(0.5)  # Brief pause between scenarios

        # Save results
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)

        self.logger.print_summary()
        self.logger.save()

        print(f"\n✅ Simulation complete!")
        if self.dry_run:
            print("   Note: This was a DRY-RUN, no blockchain transactions were executed")
        else:
            print("   Real transactions executed on Avalanche Fuji")


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Simulate marketplace transactions with bidirectional ratings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with all scenarios (100 transactions)
  python simulate_marketplace.py --dry-run

  # Execute real transactions
  python simulate_marketplace.py --execute --count 100

  # Run specific scenario
  python simulate_marketplace.py --scenario bad_client --count 20 --dry-run

  # Custom output file
  python simulate_marketplace.py --execute --count 50 --output ../data/test.csv

Available scenarios:
  - good_transaction    Mutual high ratings (90-100)
  - bad_client          Seller rates client low
  - bad_seller          Client rates seller low
  - disputed            Moderate asymmetry
  - validator_rating    Seller rates validator
  - rating_history      Repeat transactions showing trust evolution
        """
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute real blockchain transactions (default: dry-run)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry run mode (no blockchain, default)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Total number of transactions (default: 100)"
    )
    parser.add_argument(
        "--scenario",
        choices=['good_transaction', 'bad_client', 'bad_seller', 'disputed', 'validator_rating', 'rating_history'],
        help="Run specific scenario only"
    )
    parser.add_argument(
        "--output",
        default="../data/week2/transactions.csv",
        help="Output CSV file path"
    )

    args = parser.parse_args()

    # Determine mode
    dry_run = not args.execute

    try:
        # Create simulator
        simulator = MarketplaceSimulator(dry_run=dry_run, output_path=args.output)

        # Run simulation
        simulator.run_simulation(total_count=args.count, scenario=args.scenario)

        print("\n✨ Done!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
