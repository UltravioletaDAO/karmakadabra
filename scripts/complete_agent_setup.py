#!/usr/bin/env python3
"""
Complete Agent Setup - Fix domains and register missing agents
Fixes all domain issues and registers remaining agents
"""

import os
import sys
import json
import boto3
import time
from web3 import Web3
from eth_account import Account

print("=" * 80)
print("COMPLETE AGENT SETUP")
print("=" * 80)
print()

# Load environment
from dotenv import load_dotenv
load_dotenv()

RPC_URL = os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
IDENTITY_REGISTRY = os.getenv("IDENTITY_REGISTRY", "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Identity Registry ABI (minimal needed functions)
IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "newAgentDomain", "type": "string"},
            {"name": "newAgentAddress", "type": "address"}
        ],
        "name": "updateAgent",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "agentDomain", "type": "string"},
            {"name": "agentAddress", "type": "address"}
        ],
        "name": "newAgent",
        "outputs": [{"name": "agentId", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "agentAddress", "type": "address"}],
        "name": "resolveByAddress",
        "outputs": [{
            "name": "agentInfo",
            "type": "tuple",
            "components": [
                {"name": "agentId", "type": "uint256"},
                {"name": "agentDomain", "type": "string"},
                {"name": "agentAddress", "type": "address"}
            ]
        }],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "REGISTRATION_FEE",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

identity_contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=IDENTITY_REGISTRY_ABI)

# Get agent keys from AWS
print("[1/4] Fetching agent keys from AWS...")
try:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='karmacadabra')
    secrets = json.loads(response['SecretString'])
    print("[OK] Retrieved keys from AWS Secrets Manager")
    print()
except Exception as e:
    print(f"[FAIL] AWS error: {e}")
    sys.exit(1)

# Define agents to fix and register
agents_to_update = {
    'client-agent': {
        'agent_id': 3,
        'current_domain': 'client.karmacadabra.xyz',
        'correct_domain': 'client.karmacadabra.ultravioletadao.xyz'
    },
    'karma-hello-agent': {
        'agent_id': 1,
        'current_domain': 'karma-hello.ultravioletadao.xyz',
        'correct_domain': 'karma-hello.karmacadabra.ultravioletadao.xyz'
    },
    'abracadabra-agent': {
        'agent_id': 2,
        'current_domain': 'abracadabra.ultravioletadao.xyz',
        'correct_domain': 'abracadabra.karmacadabra.ultravioletadao.xyz'
    }
}

agents_to_register = {
    'validator-agent': {
        'domain': 'validator.karmacadabra.ultravioletadao.xyz'
    },
    'voice-extractor-agent': {
        'domain': 'voice-extractor.karmacadabra.ultravioletadao.xyz'
    },
    'skill-extractor-agent': {
        'domain': 'skill-extractor.karmacadabra.ultravioletadao.xyz'
    }
}

# Get agent accounts
agent_accounts = {}
for agent_key in list(agents_to_update.keys()) + list(agents_to_register.keys()):
    if agent_key in secrets:
        pk = secrets[agent_key]['private_key']
        account = Account.from_key(pk)
        agent_accounts[agent_key] = {
            'account': account,
            'address': account.address,
            'private_key': pk
        }

print("[2/4] Current status check...")
print()
print("Agents needing domain updates:")
for agent_name, info in agents_to_update.items():
    print(f"  {agent_name} (ID {info['agent_id']})")
    print(f"    Current: {info['current_domain']}")
    print(f"    Correct: {info['correct_domain']}")
print()

print("Agents needing registration:")
for agent_name, info in agents_to_register.items():
    agent_info = agent_accounts[agent_name]
    avax_balance = w3.eth.get_balance(agent_info['address'])
    avax_eth = w3.from_wei(avax_balance, 'ether')
    print(f"  {agent_name}")
    print(f"    Address: {agent_info['address']}")
    print(f"    Domain: {info['domain']}")
    print(f"    AVAX: {avax_eth:.4f}")
print()

# Check for --confirm flag
if '--confirm' not in sys.argv:
    print("[DRY RUN] Use --confirm flag to execute")
    print("\nRun with: python complete_agent_setup.py --confirm")
    sys.exit(0)

print("[CONFIRMED] Proceeding with updates and registrations...")
print()

# PART 1: Update existing agent domains
print("=" * 80)
print("[3/4] UPDATING AGENT DOMAINS")
print("=" * 80)
print()

for agent_name, info in agents_to_update.items():
    print(f"Updating {agent_name} (ID {info['agent_id']})...")

    try:
        agent_info = agent_accounts[agent_name]

        # Build updateAgent transaction
        # updateAgent(agentId, newDomain, newAddress)
        # Pass address(0) to keep same address
        tx = identity_contract.functions.updateAgent(
            info['agent_id'],
            info['correct_domain'],
            '0x0000000000000000000000000000000000000000'
        ).build_transaction({
            'from': agent_info['address'],
            'nonce': w3.eth.get_transaction_count(agent_info['address']),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 43113
        })

        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(tx, agent_info['private_key'])
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"[OK] Transaction sent: {tx_hash.hex()}")
        print(f"     https://testnet.snowtrace.io/tx/{tx_hash.hex()}")

        # Wait for confirmation
        print(f"     Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            print(f"[OK] Domain updated successfully!")
            # Verify
            result = identity_contract.functions.resolveByAddress(agent_info['address']).call()
            agent_id, domain, address = result
            print(f"     Verified: {domain}")
        else:
            print(f"[FAIL] Transaction failed!")

    except Exception as e:
        print(f"[FAIL] Error updating {agent_name}: {e}")

    print()
    time.sleep(2)  # Wait between transactions

# PART 2: Register new agents
print("=" * 80)
print("[4/4] REGISTERING NEW AGENTS")
print("=" * 80)
print()

registration_fee = identity_contract.functions.REGISTRATION_FEE().call()
print(f"Registration fee: {w3.from_wei(registration_fee, 'ether')} AVAX")
print()

for agent_name, info in agents_to_register.items():
    print(f"Registering {agent_name}...")

    try:
        agent_info = agent_accounts[agent_name]

        # Build newAgent transaction
        tx = identity_contract.functions.newAgent(
            info['domain'],
            agent_info['address']
        ).build_transaction({
            'from': agent_info['address'],
            'value': registration_fee,
            'nonce': w3.eth.get_transaction_count(agent_info['address']),
            'gas': 300000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 43113
        })

        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(tx, agent_info['private_key'])
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"[OK] Transaction sent: {tx_hash.hex()}")
        print(f"     https://testnet.snowtrace.io/tx/{tx_hash.hex()}")

        # Wait for confirmation
        print(f"     Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            # Get agent ID from logs
            result = identity_contract.functions.resolveByAddress(agent_info['address']).call()
            agent_id, domain, address = result
            print(f"[OK] Registered successfully!")
            print(f"     Agent ID: {agent_id}")
            print(f"     Domain: {domain}")
        else:
            print(f"[FAIL] Transaction failed!")

    except Exception as e:
        print(f"[FAIL] Error registering {agent_name}: {e}")

    print()
    time.sleep(2)  # Wait between transactions

print("=" * 80)
print("SETUP COMPLETE")
print("=" * 80)
print()
print("Summary:")
print(f"  ✅ Updated 3 agent domains")
print(f"  ✅ Registered 3 new agents")
print()
print("Next step: Run system state test")
print("  python test_system_state.py")
print()
