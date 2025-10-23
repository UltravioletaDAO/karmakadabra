#!/usr/bin/env python3
"""
Transaction Logger Usage Example
Demonstrates how agents log transactions on-chain

Based on Karma-Hello's transaction logging pattern
"""

import os
from transaction_logger import TransactionLogger, create_payment_message
from dotenv import load_dotenv

load_dotenv()

# Example: Karma-Hello Agent sells chat logs to Client Agent
def example_karma_hello_sells_logs():
    """
    Example: Client Agent buys chat logs from Karma-Hello Agent

    Flow:
    1. Client signs payment authorization (EIP-3009)
    2. Client sends request to Karma-Hello with payment
    3. Facilitator executes transfer (gasless for both agents)
    4. Karma-Hello returns chat logs
    5. BOTH agents log the transaction on-chain
    """

    # Initialize loggers for both agents
    client_logger = TransactionLogger(
        agent_private_key=os.getenv("CLIENT_AGENT_PRIVATE_KEY"),
        agent_name="client-agent"
    )

    karma_hello_logger = TransactionLogger(
        agent_private_key=os.getenv("KARMA_HELLO_AGENT_PRIVATE_KEY"),
        agent_name="karma-hello-agent"
    )

    # Simulate payment transaction hash (this would come from the facilitator)
    payment_tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

    # Log from client's perspective (buyer)
    print("\n[CLIENT AGENT] Logging payment...")
    client_result = client_logger.log_payment(
        payment_tx_hash=payment_tx_hash,
        from_agent="client-agent",
        to_agent="karma-hello-agent",
        amount_glue=0.01,
        service="Chat Logs for 2025-10-21",
        from_address="0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",  # client-agent
        to_address="0x2C3e071df446B25B821F59425152838ae4931E75"   # karma-hello-agent
    )

    # Log from Karma-Hello's perspective (seller)
    print("\n[KARMA-HELLO AGENT] Logging received payment...")
    kh_result = karma_hello_logger.log_payment(
        payment_tx_hash=payment_tx_hash,
        from_agent="client-agent",
        to_agent="karma-hello-agent",
        amount_glue=0.01,
        service="Chat Logs for 2025-10-21",
        from_address="0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
        to_address="0x2C3e071df446B25B821F59425152838ae4931E75"
    )

    print("\n" + "=" * 60)
    print("Transaction Logged by Both Agents!")
    print("=" * 60)
    print(f"Payment TX: https://testnet.snowtrace.io/tx/{payment_tx_hash}")
    print(f"Client Log TX: https://testnet.snowtrace.io/tx/{client_result['log_tx']}")
    print(f"Seller Log TX: https://testnet.snowtrace.io/tx/{kh_result['log_tx']}")
    print("\nThese logs are now PERMANENT on Avalanche Fuji blockchain!")


# Example: Validator validates data quality
def example_validator_validates_data():
    """
    Example: Validator Agent validates data quality

    Flow:
    1. Validator receives validation request
    2. Validator analyzes data with CrewAI
    3. Validator submits validation score on-chain
    4. Validator logs the validation event
    """

    validator_logger = TransactionLogger(
        agent_private_key=os.getenv("VALIDATOR_AGENT_PRIVATE_KEY"),
        agent_name="validator-agent"
    )

    # Simulate validation transaction hash
    validation_tx_hash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

    print("\n[VALIDATOR AGENT] Logging validation...")
    result = validator_logger.log_validation(
        validation_tx_hash=validation_tx_hash,
        target_address="0x2C3e071df446B25B821F59425152838ae4931E75",  # karma-hello-agent
        score=95,
        details="High quality chat logs - Well formatted, complete timestamps, accurate user attribution"
    )

    print("\n" + "=" * 60)
    print("Validation Logged!")
    print("=" * 60)
    print(f"Validation TX: https://testnet.snowtrace.io/tx/{validation_tx_hash}")
    print(f"Log TX: https://testnet.snowtrace.io/tx/{result['log_tx']}")


# Example: Multiple transactions in sequence
def example_transaction_chain():
    """
    Example: Chain of transactions

    1. Client → Karma-Hello (0.01 GLUE for logs)
    2. Client → Abracadabra (0.02 GLUE for transcript)
    3. Client → Validator (0.001 GLUE for validation)
    """

    client_logger = TransactionLogger(
        agent_private_key=os.getenv("CLIENT_AGENT_PRIVATE_KEY"),
        agent_name="client-agent"
    )

    transactions = [
        {
            'to_agent': 'karma-hello-agent',
            'to_address': '0x2C3e071df446B25B821F59425152838ae4931E75',
            'amount': 0.01,
            'service': 'Chat Logs - Full Day 2025-10-21'
        },
        {
            'to_agent': 'abracadabra-agent',
            'to_address': '0x940DDDf6fB28E611b132FbBedbc4854CC7C22648',
            'amount': 0.02,
            'service': 'Stream Transcript with AI Analysis'
        },
        {
            'to_agent': 'validator-agent',
            'to_address': '0x1219eF9484BF7E40E6479141B32634623d37d507',
            'amount': 0.001,
            'service': 'Data Quality Validation'
        }
    ]

    print("\n[CLIENT AGENT] Logging transaction chain...")
    print("=" * 60)

    for i, tx in enumerate(transactions, 1):
        # Simulate tx hash
        fake_tx_hash = f"0x{'1' * (64 - len(str(i)))}{i}"

        print(f"\n[{i}/3] Payment to {tx['to_agent']}...")
        result = client_logger.log_payment(
            payment_tx_hash=fake_tx_hash,
            from_agent="client-agent",
            to_agent=tx['to_agent'],
            amount_glue=tx['amount'],
            service=tx['service'],
            from_address="0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
            to_address=tx['to_address']
        )
        print(f"    ✓ Logged: https://testnet.snowtrace.io/tx/{result['log_tx']}")

    print("\n" + "=" * 60)
    print("All transactions in chain logged on-chain!")
    print("Every transaction is now traceable forever on Avalanche Fuji")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════╗
║         TRANSACTION LOGGER EXAMPLE - KARMACADABRA            ║
║                                                               ║
║  All agent transactions are logged on-chain with UTF-8        ║
║  messages that appear in Snowtrace forever.                   ║
║                                                               ║
║  Based on Karma-Hello's transaction logging pattern.         ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    print("\nAvailable Examples:")
    print("1. Karma-Hello sells logs to Client (example_karma_hello_sells_logs)")
    print("2. Validator validates data (example_validator_validates_data)")
    print("3. Transaction chain (example_transaction_chain)")
    print("\nTo run examples, uncomment the function calls below:")
    print()

    # Uncomment to run examples:
    # example_karma_hello_sells_logs()
    # example_validator_validates_data()
    # example_transaction_chain()

    print("\nTransaction Logger Ready!")
    print(f"Contract: 0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654")
    print(f"Network: Avalanche Fuji Testnet")
    print(f"View on Snowtrace: https://testnet.snowtrace.io/address/0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654")
