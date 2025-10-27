#!/usr/bin/env python3
"""
Setup User Agents - Complete Infrastructure Setup

This script does EVERYTHING needed to activate ALL user agents in client-agents/ folder:
1. Generates wallets for all agents (or uses existing - IDEMPOTENT)
2. Stores ALL private keys in ONE AWS secret ('karmacadabra' → 'user-agents' key)
3. Updates all .env files (AGENT_ADDRESS only, NOT private keys)
4. Funds each with 0.05 AVAX (for ERC-8004 registration gas)
5. Distributes 1000 GLUE to each agent
6. Registers all agents on-chain

DYNAMIC: Automatically detects ALL agents in client-agents/ folder
IDEMPOTENT: Safe to run multiple times - checks existing state before acting
SCALABLE: Add new agents to client-agents/ folder and re-run

Uses ERC-20 deployer wallet (0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8)

SECURITY:
- Private keys are NEVER written to .env files
- All keys stored in single AWS secret: karmacadabra['user-agents']
- Each agent reads the shared secret at runtime and extracts its own key

Usage:
    python scripts/setup_user_agents.py                    # Dry-run (shows what will happen)
    python scripts/setup_user_agents.py --execute          # Actually do it
    python scripts/setup_user_agents.py --execute --skip-wallets  # Skip wallet generation (use existing)
"""

import os
import sys
from pathlib import Path
import json
import boto3
import time
import argparse
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv, set_key

# Configuration
load_dotenv(project_root / ".env")

RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
CHAIN_ID = 43113
IDENTITY_REGISTRY = os.getenv("IDENTITY_REGISTRY", "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618")
GLUE_TOKEN_ADDRESS = os.getenv("GLUE_TOKEN_ADDRESS", "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743")

# ERC-20 deployer wallet (has AVAX and GLUE)
DEPLOYER_WALLET = "0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8"

# Target balances (top up to these amounts)
TARGET_AVAX_BALANCE = 0.05   # Top up to 0.05 AVAX
TARGET_GLUE_BALANCE = 10946  # Top up to 10946 GLUE

# Web3 connection
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Get all user agent directories (DYNAMIC - automatically detects all agents)
CLIENT_AGENTS_DIR = project_root / "client-agents"
USER_AGENTS = sorted([d.name for d in CLIENT_AGENTS_DIR.iterdir() if d.is_dir() and d.name != "template"])

# Calculate total requirements dynamically
num_agents = len(USER_AGENTS)

# Calculate maximum possible need (if all agents have 0 balance)
TOTAL_AVAX_NEEDED = num_agents * TARGET_AVAX_BALANCE
TOTAL_GLUE_NEEDED = num_agents * TARGET_GLUE_BALANCE

print("=" * 80)
print("🚀 SETUP USER AGENTS - COMPLETE INFRASTRUCTURE")
print("=" * 80)
print(f"\n📁 Found {num_agents} user agents in client-agents/")
print(f"   {', '.join(USER_AGENTS[:5])}{f' ... and {num_agents - 5} more' if num_agents > 5 else ''}")
print(f"")
print(f"📊 Target Balances (will top up to):")
print(f"   AVAX: {TARGET_AVAX_BALANCE:.2f} AVAX per agent")
print(f"   GLUE: {TARGET_GLUE_BALANCE:,} GLUE per agent")
print(f"   Maximum AVAX needed: {TOTAL_AVAX_NEEDED:.2f} (if all agents at 0)")
print(f"   Maximum GLUE needed: {TOTAL_GLUE_NEEDED:,} (if all agents at 0)")
print(f"   Funding from: {DEPLOYER_WALLET}")
print("")


def get_deployer_private_key():
    """Get ERC-20 deployer private key from AWS Secrets Manager"""
    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='karmacadabra')
        secrets = json.loads(response['SecretString'])

        if 'erc-20' in secrets:
            return secrets['erc-20']['private_key']

        print("❌ ERROR: 'erc-20' key not found in AWS Secrets Manager")
        return None

    except Exception as e:
        print(f"❌ ERROR fetching deployer key from AWS: {e}")
        return None


def get_existing_wallets_from_aws():
    """Get existing user agent wallets from AWS Secrets Manager

    Returns:
        dict: Username → wallet mapping, or empty dict if no wallets exist
    """
    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='karmacadabra')
        secrets = json.loads(response['SecretString'])

        if 'user-agents' in secrets:
            return secrets['user-agents']

        return {}

    except client.exceptions.ResourceNotFoundException:
        # Secret doesn't exist yet
        return {}
    except Exception as e:
        print(f"⚠️  WARNING: Could not fetch existing wallets from AWS: {e}")
        return {}


def generate_wallet():
    """Generate new Ethereum wallet"""
    account = Account.create()
    return {
        "address": account.address,
        "private_key": account.key.hex()
    }


def store_all_wallets_in_aws(wallets_dict):
    """Store all user agent wallets in ONE AWS secret

    Stores wallets in the existing 'karmacadabra' secret under a 'user-agents' key.
    DYNAMIC: Works with any number of agents.

    Structure:
    {
        "user-agents": {
            "cyberpaisa": {"private_key": "0x...", "address": "0x..."},
            "0xultravioleta": {"private_key": "0x...", "address": "0x..."},
            ... (as many agents as exist in client-agents/ folder)
        }
    }
    """
    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        secret_name = 'karmacadabra'

        # Get existing secret
        try:
            response = client.get_secret_value(SecretId=secret_name)
            existing_secrets = json.loads(response['SecretString'])
        except client.exceptions.ResourceNotFoundException:
            # Secret doesn't exist yet, create it
            existing_secrets = {}

        # Add user-agents section
        existing_secrets['user-agents'] = wallets_dict

        # Update the secret
        client.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(existing_secrets, indent=2)
        )

        print(f"✅ Stored all {len(wallets_dict)} wallets in AWS secret '{secret_name}' under 'user-agents' key")
        return True

    except Exception as e:
        print(f"❌ ERROR storing wallets in AWS: {e}")
        return False


def update_env_file(username, wallet):
    """Update .env file for user agent

    IMPORTANT: Does NOT write PRIVATE_KEY to .env file.
    Private keys are stored in AWS Secrets Manager and read at runtime.
    Only updates AGENT_ADDRESS for convenience.
    """
    env_path = CLIENT_AGENTS_DIR / username / ".env"

    if not env_path.exists():
        print(f"   ⚠️  WARNING: {env_path} not found")
        return False

    try:
        # Update AGENT_ADDRESS (public address is safe to store)
        set_key(str(env_path), "AGENT_ADDRESS", wallet["address"])

        # Ensure PRIVATE_KEY is empty (will be fetched from AWS at runtime)
        set_key(str(env_path), "PRIVATE_KEY", "")

        return True

    except Exception as e:
        print(f"   ❌ ERROR updating {username}/.env: {e}")
        return False


def check_balance(address):
    """Check AVAX and GLUE balances"""
    try:
        # AVAX balance
        avax_wei = w3.eth.get_balance(address)
        avax = float(w3.from_wei(avax_wei, 'ether'))

        # GLUE balance
        glue_abi = [{"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]
        glue_contract = w3.eth.contract(address=GLUE_TOKEN_ADDRESS, abi=glue_abi)
        glue_balance = glue_contract.functions.balanceOf(address).call()
        glue = float(glue_balance) / 1e6  # 6 decimals

        return avax, glue

    except Exception as e:
        return 0.0, 0.0


def send_avax(from_key, to_address, amount_avax):
    """Send AVAX from deployer to user agent"""
    try:
        account = Account.from_key(from_key)
        nonce = w3.eth.get_transaction_count(account.address)
        amount_wei = w3.to_wei(amount_avax, 'ether')

        tx = {
            'from': account.address,
            'to': to_address,
            'value': amount_wei,
            'gas': 21000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'chainId': CHAIN_ID
        }

        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return receipt.status == 1, tx_hash.hex()

    except Exception as e:
        return False, str(e)


def send_glue(from_key, to_address, amount_glue):
    """Send GLUE tokens from deployer to user agent"""
    try:
        account = Account.from_key(from_key)

        # GLUE Token ABI
        glue_abi = [
            {"inputs": [{"name": "recipient", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"}
        ]

        glue_contract = w3.eth.contract(address=GLUE_TOKEN_ADDRESS, abi=glue_abi)
        amount_wei = int(amount_glue * 1e6)  # 6 decimals

        tx = glue_contract.functions.transfer(to_address, amount_wei).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'chainId': CHAIN_ID
        })

        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return receipt.status == 1, tx_hash.hex()

    except Exception as e:
        return False, str(e)


def batch_send_avax(from_key, recipients_data):
    """
    Send AVAX to multiple recipients in parallel using nonce management

    Args:
        from_key: Private key of sender
        recipients_data: List of dicts with {'username': str, 'address': str, 'amount': float, 'index': int}

    Returns:
        Generator yielding (username, index, success, tx_hash) as confirmations arrive
    """
    account = Account.from_key(from_key)
    base_nonce = w3.eth.get_transaction_count(account.address)

    # Prepare all transactions with sequential nonces
    pending_txs = []
    for i, recipient in enumerate(recipients_data):
        try:
            amount_wei = int(recipient['amount'] * 1e18)
            nonce = base_nonce + i

            tx = {
                'from': account.address,
                'to': recipient['address'],
                'value': amount_wei,
                'gas': 21000,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
                'chainId': CHAIN_ID
            }

            signed_tx = account.sign_transaction(tx)
            pending_txs.append({
                'username': recipient['username'],
                'index': recipient['index'],
                'signed_tx': signed_tx,
                'address': recipient['address']
            })
        except Exception as e:
            yield (recipient['username'], recipient['index'], False, str(e))

    # Send all transactions immediately (don't wait for confirmations)
    for tx_data in pending_txs:
        try:
            tx_hash = w3.eth.send_raw_transaction(tx_data['signed_tx'].raw_transaction)
            tx_data['tx_hash'] = tx_hash
        except Exception as e:
            yield (tx_data['username'], tx_data['index'], False, str(e))

    # Wait for confirmations in parallel
    def wait_for_confirmation(tx_data):
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_data['tx_hash'], timeout=120)
            return (tx_data['username'], tx_data['index'], receipt.status == 1, tx_data['tx_hash'].hex())
        except Exception as e:
            return (tx_data['username'], tx_data['index'], False, str(e))

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(wait_for_confirmation, tx_data) for tx_data in pending_txs if 'tx_hash' in tx_data]
        for future in as_completed(futures):
            yield future.result()


def batch_send_glue(from_key, recipients_data):
    """
    Send GLUE to multiple recipients in parallel using nonce management

    Args:
        from_key: Private key of sender
        recipients_data: List of dicts with {'username': str, 'address': str, 'amount': int, 'index': int}

    Returns:
        Generator yielding (username, index, success, tx_hash) as confirmations arrive
    """
    account = Account.from_key(from_key)
    base_nonce = w3.eth.get_transaction_count(account.address)

    # GLUE Token ABI
    glue_abi = [
        {"inputs": [{"name": "recipient", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"}
    ]
    glue_contract = w3.eth.contract(address=GLUE_TOKEN_ADDRESS, abi=glue_abi)

    # Prepare all transactions with sequential nonces
    pending_txs = []
    for i, recipient in enumerate(recipients_data):
        try:
            amount_wei = int(recipient['amount'] * 1e6)  # 6 decimals
            nonce = base_nonce + i

            tx = glue_contract.functions.transfer(recipient['address'], amount_wei).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': CHAIN_ID
            })

            signed_tx = account.sign_transaction(tx)
            pending_txs.append({
                'username': recipient['username'],
                'index': recipient['index'],
                'signed_tx': signed_tx,
                'address': recipient['address']
            })
        except Exception as e:
            yield (recipient['username'], recipient['index'], False, str(e))

    # Send all transactions immediately (don't wait for confirmations)
    for tx_data in pending_txs:
        try:
            tx_hash = w3.eth.send_raw_transaction(tx_data['signed_tx'].raw_transaction)
            tx_data['tx_hash'] = tx_hash
        except Exception as e:
            yield (tx_data['username'], tx_data['index'], False, str(e))

    # Wait for confirmations in parallel
    def wait_for_confirmation(tx_data):
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_data['tx_hash'], timeout=120)
            return (tx_data['username'], tx_data['index'], receipt.status == 1, tx_data['tx_hash'].hex())
        except Exception as e:
            return (tx_data['username'], tx_data['index'], False, str(e))

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(wait_for_confirmation, tx_data) for tx_data in pending_txs if 'tx_hash' in tx_data]
        for future in as_completed(futures):
            yield future.result()


def check_registration(agent_address):
    """Check if agent is already registered on Identity Registry

    Returns:
        tuple: (is_registered: bool, agent_id: int)
    """
    try:
        # resolveByAddress returns AgentInfo struct: (agentId, agentDomain, agentAddress)
        abi = [{
            "inputs": [{"name": "agentAddress", "type": "address"}],
            "name": "resolveByAddress",
            "outputs": [{
                "components": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "agentDomain", "type": "string"},
                    {"name": "agentAddress", "type": "address"}
                ],
                "name": "agentInfo",
                "type": "tuple"
            }],
            "stateMutability": "view",
            "type": "function"
        }]
        contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=abi)
        agent_info = contract.functions.resolveByAddress(agent_address).call()
        agent_id = agent_info[0]  # Extract agentId from tuple
        return agent_id > 0, agent_id
    except:
        # Agent not registered or other error
        return False, 0


def register_agent(agent_key, agent_address, domain):
    """Register agent on Identity Registry"""
    try:
        account = Account.from_key(agent_key)

        # Identity Registry ABI
        abi = [
            {"inputs": [{"name": "_agentDomain", "type": "string"}, {"name": "_agentAddress", "type": "address"}], "name": "newAgent", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "payable", "type": "function"},
            {"inputs": [], "name": "REGISTRATION_FEE", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
        ]

        contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=abi)
        reg_fee = contract.functions.REGISTRATION_FEE().call()

        tx = contract.functions.newAgent(domain, agent_address).build_transaction({
            'from': account.address,
            'value': reg_fee,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price,
            'chainId': CHAIN_ID
        })

        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return receipt.status == 1, tx_hash.hex()

    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Setup all user agents dynamically")
    parser.add_argument("--execute", action="store_true", help="Actually execute (default is dry-run)")
    parser.add_argument("--skip-wallets", action="store_true", help="Skip wallet generation (use existing)")
    parser.add_argument("--skip-avax", action="store_true", help="Skip AVAX distribution")
    parser.add_argument("--skip-glue", action="store_true", help="Skip GLUE distribution")
    parser.add_argument("--skip-registration", action="store_true", help="Skip on-chain registration")

    args = parser.parse_args()

    if not args.execute:
        print("🔍 DRY-RUN MODE (use --execute to actually run)")
        print("")

    # Step 1: Get deployer key
    print("📋 Step 1: Get deployer wallet credentials")
    print("-" * 80)

    deployer_key = get_deployer_private_key()
    if not deployer_key:
        print("❌ Cannot continue without deployer key")
        return 1

    deployer_avax, deployer_glue = check_balance(DEPLOYER_WALLET)
    print(f"✅ Deployer wallet: {DEPLOYER_WALLET}")
    print(f"   💎 AVAX: {deployer_avax:.4f}")
    print(f"   💎 GLUE: {deployer_glue:,.2f}")

    if deployer_avax < TOTAL_AVAX_NEEDED:
        print(f"⚠️  WARNING: Insufficient AVAX (have {deployer_avax:.4f}, need {TOTAL_AVAX_NEEDED:.2f})")

    if deployer_glue < TOTAL_GLUE_NEEDED:
        print(f"⚠️  WARNING: Insufficient GLUE (have {deployer_glue:,.0f}, need {TOTAL_GLUE_NEEDED:,.0f})")

    print("")

    # Step 2: Generate or load wallets (IDEMPOTENT)
    if not args.skip_wallets:
        print("📋 Step 2: Generate/Load wallets for all agents")
        print("-" * 80)

        # Get existing wallets from AWS (idempotent - don't regenerate)
        existing_wallets = get_existing_wallets_from_aws()
        print(f"Found {len(existing_wallets)} existing wallets in AWS")
        print("")

        wallets = {}
        new_count = 0
        existing_count = 0

        for username in USER_AGENTS:
            if username in existing_wallets:
                # Use existing wallet
                wallets[username] = existing_wallets[username]
                existing_count += 1
                if args.execute:
                    print(f"✅ {username:20s} → {wallets[username]['address']} (existing)")
                else:
                    print(f"📝 {username:20s} → Would use existing wallet")

                # Update .env with existing address (idempotent)
                if args.execute:
                    if update_env_file(username, wallets[username]):
                        print(f"   ✅ Updated .env file (AGENT_ADDRESS)")
                    else:
                        print(f"   ❌ Failed to update .env")

            else:
                # Generate new wallet
                if args.execute:
                    wallet = generate_wallet()
                    wallets[username] = wallet
                    new_count += 1
                    print(f"✅ {username:20s} → {wallet['address']} (NEW)")

                    # Update .env (only stores public address, not private key)
                    if update_env_file(username, wallet):
                        print(f"   ✅ Updated .env file (AGENT_ADDRESS)")
                    else:
                        print(f"   ❌ Failed to update .env")
                else:
                    print(f"📝 Would generate NEW wallet for: {username}")

        # Store ALL wallets in ONE AWS secret (after generating all)
        if args.execute and new_count > 0:
            print("")
            print(f"📋 Storing {new_count} new wallets + {existing_count} existing in AWS Secrets Manager...")
            print("-" * 80)

            # Convert to format expected by AWS
            aws_wallets = {
                username: {
                    "private_key": wallet["private_key"],
                    "address": wallet["address"]
                }
                for username, wallet in wallets.items()
            }

            if store_all_wallets_in_aws(aws_wallets):
                print(f"✅ All {len(aws_wallets)} wallets stored in 'karmacadabra' secret under 'user-agents' key")
                print(f"   ({new_count} new, {existing_count} existing)")
            else:
                print(f"❌ Failed to store wallets in AWS - cannot continue")
                return 1
        elif args.execute and new_count == 0:
            print("")
            print(f"⏭️  All {len(USER_AGENTS)} agents already have wallets - skipping AWS update")

        print(f"\n✅ {len(USER_AGENTS)} wallets ready ({existing_count} existing, {new_count} new)")
        print("")
    else:
        print("⏭️  Skipping wallet generation (--skip-wallets)")
        print("")

    # Step 3: Distribute AVAX
    if not args.skip_avax:
        print("📋 Step 3: Distribute AVAX (top up to 0.05 per agent)")
        print("-" * 80)

        # Get wallets from AWS (needed for Steps 3-5)
        all_wallets = get_existing_wallets_from_aws()
        if not all_wallets:
            print("❌ No wallets found in AWS. Run without --skip-wallets first.")
            print("")
        else:
            if args.execute:
                # Collect all agents that need topping up
                recipients = []
                agent_info = {}  # username -> (index, address, current_balance, amount_needed)

                for i, username in enumerate(USER_AGENTS, 1):
                    if username not in all_wallets:
                        print(f"⏭️  Skipping {username} - no wallet in AWS")
                        continue

                    wallet = all_wallets[username]
                    agent_address = wallet['address']
                    avax, _ = check_balance(agent_address)

                    if avax >= TARGET_AVAX_BALANCE:
                        print(f"[{i}/{num_agents}] {username:20s} → {agent_address}")
                        print(f"   ⏭️  Already has {avax:.4f} AVAX (≥{TARGET_AVAX_BALANCE})")
                    else:
                        amount_to_send = TARGET_AVAX_BALANCE - avax
                        recipients.append({
                            'username': username,
                            'address': agent_address,
                            'amount': amount_to_send,
                            'index': i
                        })
                        agent_info[username] = (i, agent_address, avax, amount_to_send)

                # Batch send to all recipients
                if recipients:
                    print(f"\n🚀 Batch sending AVAX to {len(recipients)} agents...")
                    print("")

                    for username, index, success, tx_hash in batch_send_avax(deployer_key, recipients):
                        i, address, current_balance, amount = agent_info[username]
                        print(f"[{i}/{num_agents}] {username:20s} → {address}")
                        print(f"   💰 Current: {current_balance:.4f} AVAX → Topping up {amount:.4f} AVAX to reach {TARGET_AVAX_BALANCE}")
                        if success:
                            print(f"   ✅ Sent {amount:.4f} AVAX (tx: {tx_hash[:10]}...)")
                        else:
                            print(f"   ❌ Failed: {tx_hash}")
            else:
                # Dry run - show potential top-ups
                for i, username in enumerate(USER_AGENTS, 1):
                    if username not in all_wallets:
                        continue

                    wallet = all_wallets[username]
                    agent_address = wallet['address']
                    avax, _ = check_balance(agent_address)

                    if avax >= TARGET_AVAX_BALANCE:
                        print(f"[{i}/{num_agents}] {username:20s} already has {avax:.4f} AVAX")
                    else:
                        amount_needed = TARGET_AVAX_BALANCE - avax
                        print(f"[{i}/{num_agents}] Would send {amount_needed:.4f} AVAX to {username} (has {avax:.4f})")

        print(f"\n✅ AVAX distribution complete")
        print("")
    else:
        print("⏭️  Skipping AVAX distribution (--skip-avax)")
        print("")

    # Step 4: Distribute GLUE
    if not args.skip_glue:
        print("📋 Step 4: Distribute GLUE (top up to 10946 per agent)")
        print("-" * 80)

        # Get wallets from AWS (needed for Steps 3-5)
        all_wallets = get_existing_wallets_from_aws()
        if not all_wallets:
            print("❌ No wallets found in AWS. Run without --skip-wallets first.")
            print("")
        else:
            if args.execute:
                # Collect all agents that need topping up
                recipients = []
                agent_info = {}  # username -> (index, address, current_balance, amount_needed)

                for i, username in enumerate(USER_AGENTS, 1):
                    if username not in all_wallets:
                        print(f"⏭️  Skipping {username} - no wallet in AWS")
                        continue

                    wallet = all_wallets[username]
                    agent_address = wallet['address']
                    _, glue = check_balance(agent_address)

                    if glue >= TARGET_GLUE_BALANCE:
                        print(f"[{i}/{num_agents}] {username:20s} → {agent_address}")
                        print(f"   ⏭️  Already has {glue:,.0f} GLUE (≥{TARGET_GLUE_BALANCE:,})")
                    else:
                        amount_to_send = int(TARGET_GLUE_BALANCE - glue)
                        recipients.append({
                            'username': username,
                            'address': agent_address,
                            'amount': amount_to_send,
                            'index': i
                        })
                        agent_info[username] = (i, agent_address, glue, amount_to_send)

                # Batch send to all recipients
                if recipients:
                    print(f"\n🚀 Batch sending GLUE to {len(recipients)} agents...")
                    print("")

                    for username, index, success, tx_hash in batch_send_glue(deployer_key, recipients):
                        i, address, current_balance, amount = agent_info[username]
                        print(f"[{i}/{num_agents}] {username:20s} → {address}")
                        print(f"   💰 Current: {current_balance:,.0f} GLUE → Topping up {amount:,} GLUE to reach {TARGET_GLUE_BALANCE:,}")
                        if success:
                            print(f"   ✅ Sent {amount:,} GLUE (tx: {tx_hash[:10]}...)")
                        else:
                            print(f"   ❌ Failed: {tx_hash}")
            else:
                # Dry run - show potential top-ups
                for i, username in enumerate(USER_AGENTS, 1):
                    if username not in all_wallets:
                        continue

                    wallet = all_wallets[username]
                    agent_address = wallet['address']
                    _, glue = check_balance(agent_address)

                    if glue >= TARGET_GLUE_BALANCE:
                        print(f"[{i}/{num_agents}] {username:20s} already has {glue:,.0f} GLUE")
                    else:
                        amount_needed = int(TARGET_GLUE_BALANCE - glue)
                        print(f"[{i}/{num_agents}] Would send {amount_needed:,} GLUE to {username} (has {glue:,.0f})")

        print(f"\n✅ GLUE distribution complete")
        print("")
    else:
        print("⏭️  Skipping GLUE distribution (--skip-glue)")
        print("")

    # Step 5: Register on-chain (IDEMPOTENT)
    if not args.skip_registration:
        print("📋 Step 5: Register agents on Identity Registry")
        print("-" * 80)

        # Get wallets from AWS (needed for Steps 3-5)
        all_wallets = get_existing_wallets_from_aws()
        if not all_wallets:
            print("❌ No wallets found in AWS. Run without --skip-wallets first.")
            print("")
        else:
            for i, username in enumerate(USER_AGENTS, 1):
                if username not in all_wallets:
                    print(f"⏭️  Skipping {username} - no wallet in AWS")
                    continue

                wallet = all_wallets[username]
                agent_key = wallet['private_key']
                agent_address = wallet['address']

                # Get domain from .env or use default
                env_path = CLIENT_AGENTS_DIR / username / ".env"
                domain = f"{username}.karmacadabra.ultravioletadao.xyz"
                if env_path.exists():
                    from dotenv import dotenv_values
                    config = dotenv_values(env_path)
                    domain = config.get('AGENT_DOMAIN', domain)

                if args.execute:
                    print(f"[{i}/{num_agents}] {username:20s} → {domain}")

                    # Check if already registered (idempotent)
                    is_registered, agent_id = check_registration(agent_address)
                    if is_registered:
                        print(f"   ⏭️  Already registered (Agent ID: {agent_id})")
                        continue

                    # Register
                    success, tx_hash = register_agent(agent_key, agent_address, domain)
                    if success:
                        print(f"   ✅ Registered on-chain (tx: {tx_hash[:10]}...)")
                    else:
                        print(f"   ❌ Failed: {tx_hash}")

                    time.sleep(2)  # Rate limiting
                else:
                    print(f"[{i}/{num_agents}] Would register {username} at {domain}")

        print(f"\n✅ Registration complete")
        print("")
    else:
        print("⏭️  Skipping registration (--skip-registration)")
        print("")

    # Summary
    print("=" * 80)
    print("✅ SETUP COMPLETE!")
    print("=" * 80)
    print("")
    if not args.execute:
        print("This was a DRY-RUN. Use --execute to actually run the setup.")
        print("")
        print("Command:")
        print("  python scripts/setup_user_agents.py --execute")
        print("")
    else:
        print(f"All {num_agents} user agents are now ready!")
        print("")
        print("Next steps:")
        print("  1. Verify setup: python scripts/verify_user_agents.py")
        print("  2. Test one agent: python tests/test_cyberpaisa_client.py")
        print("  3. Bootstrap marketplace: python scripts/bootstrap_marketplace.py")
        print("")

    return 0


if __name__ == "__main__":
    sys.exit(main())
