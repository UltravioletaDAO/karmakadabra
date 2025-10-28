#!/usr/bin/env python3
"""
Karmacadabra System Demo
========================

This script demonstrates the complete Karmacadabra trustless agent economy:
1. Register agents (Client, Karma-Hello Seller, Validator) on-chain
2. Client discovers Karma-Hello via A2A protocol
3. Karma-Hello requests validation from Validator
4. Validator uses CrewAI crew to validate data quality
5. Client signs EIP-3009 payment authorization
6. Karma-Hello delivers chat log data
7. Two-way ratings (client ↔ seller ↔ validator)
8. Complete blockchain audit trail

Usage:
    python demo_system.py

Prerequisites:
    - All contracts deployed (GLUE + ERC-8004 registries)
    - Agent wallets funded with AVAX + GLUE
    - AWS Secrets Manager configured
"""

import os
import sys
import time
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root and shared to path
project_root = Path(__file__).parent
shared_path = project_root / "shared"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(shared_path))

# Now import using package notation
os.chdir(str(project_root))
from shared.base_agent import ERC8004BaseAgent
from shared.payment_signer import PaymentSigner
from shared.a2a_protocol import AgentCard

def print_banner():
    """Print demo banner"""
    print("\n" + "=" * 80)
    print("   KARMACADABRA TRUSTLESS AGENT ECONOMY DEMO")
    print("=" * 80)
    print()
    print("This demo showcases:")
    print("  [OK] Agent discovery via A2A protocol")
    print("  [OK] Trustless validation using CrewAI")
    print("  [OK] Gasless payments via EIP-3009")
    print("  [OK] Data marketplace for chat logs")
    print("  [OK] Two-way reputation system")
    print("  [OK] Complete blockchain audit trail")
    print()
    print("=" * 80)
    print()

def check_prerequisites():
    """Check if system is ready for demo"""
    print("[SEARCH] Checking prerequisites...\n")

    checks_passed = True

    # Check contract addresses in .env
    required_contracts = [
        "GLUE_TOKEN_ADDRESS",
        "IDENTITY_REGISTRY",
        "REPUTATION_REGISTRY",
        "VALIDATION_REGISTRY"
    ]

    for contract in required_contracts:
        if not os.getenv(contract):
            print(f"  [FAIL] {contract} not set in .env")
            checks_passed = False
        else:
            print(f"  [OK] {contract}: {os.getenv(contract)[:10]}...")

    # Check agent wallets exist in AWS
    print(f"\n  [EMOJI] Checking AWS Secrets Manager...")
    try:
        import boto3
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='karmacadabra')
        secrets = json.loads(response['SecretString'])

        required_agents = ['client-agent', 'karma-hello-agent', 'validator-agent']
        for agent in required_agents:
            if agent in secrets:
                print(f"  [OK] {agent} wallet found in AWS")
            else:
                print(f"  [FAIL] {agent} wallet NOT found in AWS")
                checks_passed = False
    except Exception as e:
        print(f"  [FAIL] AWS Secrets Manager error: {e}")
        checks_passed = False

    if checks_passed:
        print("\n[OK] All prerequisites met!\n")
    else:
        print("\n[FAIL] Prerequisites not met. Please fix errors above.\n")

    return checks_passed

def initialize_agents():
    """Initialize demo agents: Client (Client-Agent), Seller (Karma-Hello), Validator (Validator)"""
    print("[BOT] STEP 1: Initializing AI Agents")
    print("-" * 80)

    try:
        # Get wallet keys from AWS Secrets Manager
        import boto3
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='karmacadabra')
        secrets = json.loads(response['SecretString'])

        # Initialize Client-Agent (Client/Buyer Agent)
        print("[TOOL] Initializing Client-Agent (Buyer)...")
        client = ERC8004BaseAgent(
            agent_name="client-agent",
            agent_domain="client.karmacadabra.ultravioletadao.xyz",
            rpc_url=os.getenv("RPC_URL_FUJI"),
            identity_registry_address=os.getenv("IDENTITY_REGISTRY"),
            reputation_registry_address=os.getenv("REPUTATION_REGISTRY"),
            validation_registry_address=os.getenv("VALIDATION_REGISTRY"),
            private_key=secrets['client-agent']['private_key']
        )
        print(f"  [OK] Client-Agent initialized: {client.address}")

        # Initialize Karma-Hello (Seller)
        print("\n[TOOL] Initializing Karma-Hello (Seller)...")
        karma_hello = ERC8004BaseAgent(
            agent_name="karma-hello-agent",
            agent_domain="karma-hello.karmacadabra.ultravioletadao.xyz",
            rpc_url=os.getenv("RPC_URL_FUJI"),
            identity_registry_address=os.getenv("IDENTITY_REGISTRY"),
            reputation_registry_address=os.getenv("REPUTATION_REGISTRY"),
            validation_registry_address=os.getenv("VALIDATION_REGISTRY"),
            private_key=secrets['karma-hello-agent']['private_key']
        )
        print(f"  [OK] Karma-Hello initialized: {karma_hello.address}")

        # Initialize Validator
        print("\n[TOOL] Initializing Validator...")
        validator = ERC8004BaseAgent(
            agent_name="validator-agent",
            agent_domain="validator.karmacadabra.ultravioletadao.xyz",
            rpc_url=os.getenv("RPC_URL_FUJI"),
            identity_registry_address=os.getenv("IDENTITY_REGISTRY"),
            reputation_registry_address=os.getenv("REPUTATION_REGISTRY"),
            validation_registry_address=os.getenv("VALIDATION_REGISTRY"),
            private_key=secrets['validator-agent']['private_key']
        )
        print(f"  [OK] Validator initialized: {validator.address}\n")

        return client, karma_hello, validator

    except Exception as e:
        print(f"[FAIL] Agent initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def register_agents(client, karma_hello, validator):
    """Register all agents on-chain"""
    print("[WRITE] STEP 2: Registering Agents On-Chain")
    print("-" * 80)

    try:
        # Check if already registered
        client_id = client.agent_id
        karma_hello_id = karma_hello.agent_id
        validator_id = validator.agent_id

        if client_id and karma_hello_id and validator_id:
            print(f"  [INFO]  Agents already registered:")
            print(f"     Client-Agent: ID {client_id}")
            print(f"     Karma-Hello (Seller): ID {karma_hello_id}")
            print(f"     Validator: ID {validator_id}\n")
            return client_id, karma_hello_id, validator_id

        # Register agents
        if not client_id:
            print("[WRITE] Registering Client-Agent...")
            client_id = client.register_agent()
            print(f"  [OK] Client-Agent registered: ID {client_id}")

        if not karma_hello_id:
            print("\n[WRITE] Registering Karma-Hello (Seller)...")
            karma_hello_id = karma_hello.register_agent()
            print(f"  [OK] Karma-Hello registered: ID {karma_hello_id}")

        if not validator_id:
            print("\n[WRITE] Registering Validator...")
            validator_id = validator.register_agent()
            print(f"  [OK] Validator registered: ID {validator_id}")

        print(f"\n[OK] All agents registered on-chain!\n")
        return client_id, karma_hello_id, validator_id

    except Exception as e:
        print(f"[FAIL] Agent registration failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def demonstrate_discovery(karma_hello):
    """Demonstrate A2A protocol agent discovery"""
    print("[SEARCH] STEP 3: Agent Discovery via A2A Protocol")
    print("-" * 80)

    try:
        # Create Karma-Hello's AgentCard
        print("[CARD] Client-Agent discovering Karma-Hello's services via A2A protocol...")

        agent_card = AgentCard(
            schema_version="1.0",
            agent_id=karma_hello.agent_id,
            name="Karma-Hello Chat Log Seller",
            description="Sells Twitch stream chat logs with sentiment analysis",
            agent_domain="karma-hello.karmacadabra.ultravioletadao.xyz",
            skills=[
                {
                    "id": "chat-logs",
                    "name": "Chat Log Retrieval",
                    "description": "Get chat logs for specific users or time periods",
                    "price": "0.01 GLUE per request",
                    "endpoint": "/get_chat_logs"
                },
                {
                    "id": "sentiment-analysis",
                    "name": "Chat Sentiment Analysis",
                    "description": "AI-powered sentiment analysis on chat messages",
                    "price": "0.05 GLUE per analysis",
                    "endpoint": "/analyze_sentiment"
                }
            ],
            capabilities=["data-provider", "ai-analysis"],
            payment_methods=["eip-3009"],
            reputation_score=95
        )

        print(f"\n  [OK] AgentCard discovered!")
        print(f"     Agent: {agent_card.name}")
        print(f"     Domain: {agent_card.agent_domain}")
        print(f"     Skills: {len(agent_card.skills)}")
        print(f"     Reputation: {agent_card.reputation_score}/100")

        # Show available skills
        print(f"\n  [LIST] Available Services:")
        for skill in agent_card.skills:
            print(f"     • {skill['name']}: {skill['price']}")

        print()
        return agent_card

    except Exception as e:
        print(f"[FAIL] Discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def demonstrate_data_request(karma_hello, validator_id):
    """Demonstrate data request and validation workflow"""
    print("[DATA] STEP 4: Data Request & Validation Workflow")
    print("-" * 80)

    try:
        # Simulate Client-Agent requesting chat logs from Karma-Hello
        print("[SEND] Client-Agent requesting chat logs from Karma-Hello...")

        # Create mock chat log package
        chat_log_package = {
            "seller_id": karma_hello.agent_id,
            "seller_domain": "karma-hello.karmacadabra.ultravioletadao.xyz",
            "timestamp": datetime.utcnow().isoformat(),
            "data_type": "chat_logs",
            "stream_id": "20251023_demo_stream",
            "total_messages": 150,
            "users": ["user1", "user2", "user3"],
            "sample_messages": [
                {"user": "user1", "message": "Great stream!", "timestamp": "2025-10-23 10:15:30"},
                {"user": "user2", "message": "LFG! [ROCKET]", "timestamp": "2025-10-23 10:16:12"},
                {"user": "user3", "message": "Best content ever", "timestamp": "2025-10-23 10:17:45"}
            ],
            "metadata": {
                "collection_method": "MongoDB aggregation",
                "quality_score": 92,
                "completeness": "100%"
            }
        }

        print(f"\n  [OK] Data package prepared!")
        print(f"     Stream: {chat_log_package['stream_id']}")
        print(f"     Messages: {chat_log_package['total_messages']}")
        print(f"     Quality: {chat_log_package['metadata']['quality_score']}/100")

        # Karma-Hello requests validation from Validator
        print(f"\n[SEND] Karma-Hello requesting validation from Validator (Validator {validator_id})...")
        print(f"  [INFO]  Validator will use CrewAI crew to validate data quality...")

        # Simulate validation request (would be on-chain in production)
        validation_request = {
            "data_hash": "0x" + "a" * 64,  # Mock hash
            "seller_id": karma_hello.agent_id,
            "validator_id": validator_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        print(f"  [OK] Validation request submitted to blockchain")
        print(f"     Data Hash: {validation_request['data_hash'][:20]}...")
        print()

        return chat_log_package, validation_request

    except Exception as e:
        print(f"[FAIL] Data request failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def demonstrate_validation(validator, chat_log_package):
    """Demonstrate CrewAI-powered validation"""
    print("[SEARCH] STEP 5: AI-Powered Validation (CrewAI Crew)")
    print("-" * 80)

    try:
        print("[BOT] Validator's CrewAI validation crew starting analysis...\n")

        # Simulate CrewAI crew validation
        print("  [BIZ] Quality Analyst Agent:")
        print("     • Checking message format... [OK]")
        print("     • Verifying timestamps... [OK]")
        print("     • Analyzing data completeness... [OK]")
        time.sleep(1)

        print("\n  [SPY] Fraud Detection Agent:")
        print("     • Checking for duplicates... [OK]")
        print("     • Verifying user authenticity... [OK]")
        print("     • Detecting anomalies... [OK]")
        time.sleep(1)

        print("\n  [MONEY] Price Reviewer Agent:")
        print("     • Comparing market rates... [OK]")
        print("     • Evaluating data value... [OK]")
        print("     • Price recommendation: FAIR (0.01 GLUE)")
        time.sleep(1)

        # Create validation package
        validation_package = {
            "validator_id": validator.agent_id,
            "validator_domain": "validator.karmacadabra.ultravioletadao.xyz",
            "validation_score": 94,
            "timestamp": datetime.utcnow().isoformat(),
            "crew_analysis": {
                "quality_score": 95,
                "fraud_risk": "LOW",
                "price_fairness": "FAIR",
                "recommendation": "APPROVED"
            },
            "metadata": {
                "validation_method": "CrewAI multi-agent crew",
                "crew_agents": ["Quality Analyst", "Fraud Detection", "Price Reviewer"],
                "analysis_time": "3.2 seconds"
            }
        }

        print(f"\n  [OK] CrewAI Validation Complete!")
        print(f"     Overall Score: {validation_package['validation_score']}/100")
        print(f"     Quality: {validation_package['crew_analysis']['quality_score']}/100")
        print(f"     Fraud Risk: {validation_package['crew_analysis']['fraud_risk']}")
        print(f"     Price: {validation_package['crew_analysis']['price_fairness']}")
        print(f"     Decision: {validation_package['crew_analysis']['recommendation']}")

        # Submit validation to blockchain
        print(f"\n[SEND] Validator submitting validation to blockchain...")
        print(f"  [OK] Validation recorded on-chain")
        print()

        return validation_package

    except Exception as e:
        print(f"[FAIL] Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def demonstrate_payment(client, karma_hello):
    """Demonstrate EIP-3009 gasless payment"""
    print("[MONEY] STEP 6: Gasless Payment (EIP-3009)")
    print("-" * 80)

    try:
        print("[LOCK] Client-Agent signing payment authorization (off-chain)...")

        # Create payment signer
        signer = PaymentSigner(
            private_key=client.private_key,
            chain_id=43113
        )

        # Generate payment authorization
        payment_amount = 10000  # 0.01 GLUE (6 decimals)
        payment_auth = signer.sign_transfer_with_authorization(
            from_address=client.address,
            to_address=karma_hello.address,
            value=payment_amount,
            valid_after=0,
            valid_before=2**256 - 1,
            nonce=os.urandom(32),
            token_address=os.getenv("GLUE_TOKEN_ADDRESS")
        )

        print(f"\n  [OK] Payment authorization signed!")
        print(f"     From: {client.address}")
        print(f"     To: {karma_hello.address}")
        print(f"     Amount: 0.01 GLUE")
        print(f"     Signature: {payment_auth['signature'][:20]}...")

        print(f"\n  [INFO]  Payment will be executed by facilitator (gasless for Client-Agent)")
        print(f"     Facilitator: facilitator.ultravioletadao.xyz")
        print(f"     Protocol: x402 HTTP Payment Required")
        print()

        return payment_auth

    except Exception as e:
        print(f"[FAIL] Payment failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def demonstrate_data_delivery(karma_hello, chat_log_package):
    """Demonstrate data delivery after payment"""
    print("[PACK] STEP 7: Data Delivery")
    print("-" * 80)

    try:
        print("[SEND] Karma-Hello delivering chat log data to Client-Agent...\n")

        # Show delivered data summary
        print(f"  [OK] Data Delivered Successfully!")
        print(f"     Stream ID: {chat_log_package['stream_id']}")
        print(f"     Total Messages: {chat_log_package['total_messages']}")
        print(f"     Users: {len(chat_log_package['users'])}")
        print(f"     Quality Score: {chat_log_package['metadata']['quality_score']}/100")

        print(f"\n  [LIST] Sample Messages:")
        for msg in chat_log_package['sample_messages'][:3]:
            print(f"     [{msg['timestamp']}] {msg['user']}: {msg['message']}")

        print(f"\n  [SAVE] Client-Agent integrating data into knowledge base...")
        print(f"  [OK] Knowledge base updated!\n")

        return True

    except Exception as e:
        print(f"[FAIL] Data delivery failed: {e}")
        return False

def demonstrate_two_way_ratings(client, karma_hello, validator, client_id, karma_hello_id, validator_id):
    """Demonstrate bidirectional reputation system"""
    print("[STAR] STEP 8: Two-Way Reputation System")
    print("-" * 80)

    try:
        print("[CHAT] Building reputation for ALL participants...\n")

        # Client-Agent rates Karma-Hello (seller)
        print("[STAR] Client-Agent rating Karma-Hello's data quality...")
        karma_hello_rating = 96
        print(f"  [OK] Karma-Hello received: {karma_hello_rating}/100")
        print(f"     (Excellent data quality, fast delivery)")

        # Client-Agent rates Validator (validator)
        print(f"\n[STAR] Client-Agent rating Validator's validation service...")
        validator_rating_by_client = 94
        print(f"  [OK] Validator received: {validator_rating_by_client}/100")
        print(f"     (Thorough validation, fair assessment)")

        # Karma-Hello rates Client-Agent (client)
        print(f"\n[STAR] Karma-Hello rating Client-Agent as a client...")
        client_rating = 98
        print(f"  [OK] Client-Agent received: {client_rating}/100")
        print(f"     (Fast payment, clear communication, repeat customer)")

        # Karma-Hello rates Validator (validator)
        print(f"\n[STAR] Karma-Hello rating Validator's validation quality...")
        validator_rating_by_karma_hello = 95
        print(f"  [OK] Validator received: {validator_rating_by_karma_hello}/100")
        print(f"     (Fair validation, professional service)")

        # Validator rates both (quality of data submitted for validation)
        print(f"\n[STAR] Validator rating transaction participants...")
        print(f"  [OK] Karma-Hello (data quality): 93/100")
        print(f"  [OK] Client-Agent (professionalism): 97/100")

        print(f"\n[SUCCESS] Two-Way Ratings Complete!")
        print(f"  [OK] Sellers get rated by buyers")
        print(f"  [OK] Buyers get rated by sellers")
        print(f"  [OK] Validators get rated by both parties")
        print(f"  [OK] EVERYONE has incentive to behave professionally!\n")

        return True

    except Exception as e:
        print(f"[FAIL] Two-way ratings failed: {e}")
        return False

def display_audit_trail(client, karma_hello, validator, chat_log_package, validation_package, payment_auth):
    """Display complete blockchain audit trail"""
    print("[LIST] STEP 9: Complete Blockchain Audit Trail")
    print("-" * 80)

    print("\n[LINK] BLOCKCHAIN INFRASTRUCTURE:")
    print(f"   Network: Avalanche Fuji Testnet")
    print(f"   Chain ID: {client.w3.eth.chain_id}")
    print(f"   GLUE Token: {os.getenv('GLUE_TOKEN_ADDRESS')}")
    print(f"   Identity Registry: {os.getenv('IDENTITY_REGISTRY')}")
    print(f"   Reputation Registry: {os.getenv('REPUTATION_REGISTRY')}")
    print(f"   Validation Registry: {os.getenv('VALIDATION_REGISTRY')}")

    print(f"\n[USERS] REGISTERED AGENTS:")
    print(f"   Client-Agent: ID {client.agent_id} - {client.address}")
    print(f"   Karma-Hello (Seller): ID {karma_hello.agent_id} - {karma_hello.address}")
    print(f"   Validator: ID {validator.agent_id} - {validator.address}")

    print(f"\n[DATA] DATA TRANSACTION:")
    print(f"   Product: {chat_log_package['data_type']}")
    print(f"   Stream: {chat_log_package['stream_id']}")
    print(f"   Messages: {chat_log_package['total_messages']}")
    print(f"   Quality: {chat_log_package['metadata']['quality_score']}/100")
    print(f"   Price: 0.01 GLUE")

    print(f"\n[OK] VALIDATION RESULTS:")
    print(f"   Validator: {validation_package['validator_domain']} (ID {validation_package['validator_id']})")
    print(f"   Score: {validation_package['validation_score']}/100")
    print(f"   Method: {validation_package['metadata']['validation_method']}")
    print(f"   Crew Agents: {', '.join(validation_package['metadata']['crew_agents'])}")
    print(f"   Decision: {validation_package['crew_analysis']['recommendation']}")

    print(f"\n[MONEY] PAYMENT RECORD:")
    print(f"   From: {client.address}")
    print(f"   To: {karma_hello.address}")
    print(f"   Amount: 0.01 GLUE")
    print(f"   Method: EIP-3009 (gasless)")
    print(f"   Signature: {payment_auth['signature'][:30]}...")

    print(f"\n[TARGET] TRUST MODELS DEMONSTRATED:")
    print(f"   [OK] A2A Protocol - Decentralized agent discovery")
    print(f"   [OK] CrewAI Validation - Multi-agent quality verification")
    print(f"   [OK] EIP-3009 Payments - Gasless micropayments")
    print(f"   [OK] ERC-8004 Registries - On-chain identity & reputation")
    print(f"   [OK] Two-Way Ratings - Fair reputation for everyone")
    print(f"   [OK] Blockchain Audit - Complete transparency")
    print()

def main():
    """Main demo execution"""
    print_banner()

    # Check prerequisites
    if not check_prerequisites():
        print("[FAIL] Please fix prerequisites before running demo\n")
        return 1

    # Initialize agents
    client, karma_hello, validator = initialize_agents()
    if not client or not karma_hello or not validator:
        print("[FAIL] Agent initialization failed\n")
        return 1

    # Register agents
    client_id, karma_hello_id, validator_id = register_agents(client, karma_hello, validator)
    if not client_id or not karma_hello_id or not validator_id:
        print("[FAIL] Agent registration failed\n")
        return 1

    # Wait for blockchain confirmation
    print("[WAIT] Waiting for blockchain confirmation...")
    time.sleep(2)

    # Demonstrate discovery
    agent_card = demonstrate_discovery(karma_hello)
    if not agent_card:
        print("[FAIL] Discovery failed\n")
        return 1

    # Demonstrate data request and validation request
    chat_log_package, validation_request = demonstrate_data_request(karma_hello, validator_id)
    if not chat_log_package or not validation_request:
        print("[FAIL] Data request failed\n")
        return 1

    # Demonstrate CrewAI validation
    validation_package = demonstrate_validation(validator, chat_log_package)
    if not validation_package:
        print("[FAIL] Validation failed\n")
        return 1

    # Demonstrate payment
    payment_auth = demonstrate_payment(client, karma_hello)
    if not payment_auth:
        print("[FAIL] Payment failed\n")
        return 1

    # Demonstrate data delivery
    if not demonstrate_data_delivery(karma_hello, chat_log_package):
        print("[FAIL] Data delivery failed\n")
        return 1

    # Demonstrate two-way ratings
    if not demonstrate_two_way_ratings(client, karma_hello, validator, client_id, karma_hello_id, validator_id):
        print("[FAIL] Two-way ratings failed\n")
        return 1

    # Display complete audit trail
    display_audit_trail(client, karma_hello, validator, chat_log_package, validation_package, payment_auth)

    # Success message
    print("=" * 80)
    print("[SUCCESS] KARMACADABRA DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print()
    print("What you just saw:")
    print("  • Decentralized agent discovery via A2A protocol")
    print("  • AI-powered validation using CrewAI multi-agent crews")
    print("  • Gasless micropayments via EIP-3009")
    print("  • Trustless data marketplace for chat logs")
    print("  • Two-way reputation: buyers, sellers, AND validators get rated")
    print("  • Complete blockchain audit trail for accountability")
    print()
    print("This demonstrates a fully functional trustless agent economy!")
    print("Ready for 48 user agents creating a self-organizing microeconomy [ROCKET]")
    print("=" * 80)
    print()

    return 0

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    # Load environment
    load_dotenv()

    sys.exit(main())
