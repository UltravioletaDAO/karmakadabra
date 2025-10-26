#!/usr/bin/env python3
"""
Register Missing Agents on Identity Registry
Registers: validator, skill-extractor, voice-extractor
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import json
import boto3

load_dotenv()

print("=" * 80)
print("REGISTER MISSING AGENTS")
print("=" * 80)
print()

# Configuration
RPC_URL = os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
CHAIN_ID = 43113
IDENTITY_REGISTRY = os.getenv("IDENTITY_REGISTRY")

# Identity Registry ABI
IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "_agentDomain", "type": "string"},
            {"internalType": "address", "name": "_agentAddress", "type": "address"}
        ],
        "name": "newAgent",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "_agentAddress", "type": "address"}],
        "name": "resolveByAddress",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Agents to register
AGENTS_TO_REGISTER = {
    'validator': {
        'address': '0x1219eF9484BF7E40E6479141B32634623d37d507',
        'domain': 'validator.karmacadabra.ultravioletadao.xyz'
    },
    'skill-extractor': {
        'address': '0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9',
        'domain': 'skill-extractor.karmacadabra.ultravioletadao.xyz'
    },
    'voice-extractor': {
        'address': '0xDd63D5840090B98D9EB86f2c31974f9d6c270b17',
        'domain': 'voice-extractor.karmacadabra.ultravioletadao.xyz'
    }
}

def get_agent_private_key(agent_name):
    """Get agent private key from AWS Secrets Manager"""
    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='karmacadabra')
        secrets = json.loads(response['SecretString'])

        # Map agent names to AWS secret keys
        aws_key_map = {
            'validator': 'validator-agent',
            'skill-extractor': 'skill-extractor-agent',
            'voice-extractor': 'voice-extractor-agent'
        }

        secret_key = aws_key_map.get(agent_name)
        if secret_key and secret_key in secrets:
            return secrets[secret_key]['private_key']

    except Exception as e:
        print(f"[FAIL] AWS error for {agent_name}: {e}")

    return None

def register_agent(w3, agent_name, info):
    """Register a single agent on-chain"""
    print(f"\nRegistering {agent_name}...")
    print(f"  Domain: {info['domain']}")
    print(f"  Address: {info['address']}")

    # Get agent's private key
    private_key = get_agent_private_key(agent_name)
    if not private_key:
        print(f"  [FAIL] Could not get private key from AWS")
        return False

    account = Account.from_key(private_key)

    # Check if already registered
    identity_registry = w3.eth.contract(
        address=Web3.to_checksum_address(IDENTITY_REGISTRY),
        abi=IDENTITY_REGISTRY_ABI
    )

    existing_id = identity_registry.functions.resolveByAddress(
        Web3.to_checksum_address(info['address'])
    ).call()

    if existing_id > 0:
        print(f"  [SKIP] Already registered with ID #{existing_id}")
        return True

    # Register
    try:
        nonce = w3.eth.get_transaction_count(account.address)

        tx = identity_registry.functions.newAgent(
            info['domain'],
            Web3.to_checksum_address(info['address'])
        ).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price,
            'chainId': CHAIN_ID,
            'value': w3.to_wei(0.01, 'ether')  # Registration fee
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"  [OK] Transaction sent: {tx_hash.hex()}")
        print(f"       https://testnet.snowtrace.io/tx/{tx_hash.hex()}")
        print(f"       Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            # Get the new agent ID from logs
            new_id = identity_registry.functions.resolveByAddress(
                Web3.to_checksum_address(info['address'])
            ).call()
            print(f"  [OK] Registered successfully! Agent ID: #{new_id}")
            return True
        else:
            print(f"  [FAIL] Transaction failed")
            return False

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False

def main():
    # Connect to blockchain
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        print("[FAIL] Failed to connect to Avalanche Fuji")
        return

    print(f"[OK] Connected to Avalanche Fuji")
    print(f"     Latest block: {w3.eth.block_number:,}")
    print(f"     Identity Registry: {IDENTITY_REGISTRY}")

    # Check if --confirm flag is provided
    if '--confirm' not in sys.argv:
        print("\n[DRY RUN] Add --confirm to execute registrations")
        print(f"\nAgents to register:")
        for name, info in AGENTS_TO_REGISTER.items():
            print(f"  - {name}: {info['domain']}")
        print(f"\nRun with: python scripts/register_missing_agents.py --confirm")
        return

    print("\n[CONFIRMED] Proceeding with registrations...")
    print("=" * 80)

    # Register each agent
    results = {}
    for agent_name, info in AGENTS_TO_REGISTER.items():
        results[agent_name] = register_agent(w3, agent_name, info)

    # Summary
    print("\n" + "=" * 80)
    print("REGISTRATION SUMMARY")
    print("=" * 80)

    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)

    for agent_name, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {agent_name}")

    print(f"\nRegistered: {success_count}/{total_count}")

    if success_count == total_count:
        print("\n✅ ALL AGENTS REGISTERED!")
        print("\nNext step: Update domain names for existing agents")
        print("  python scripts/update_domain_names.py --confirm")
    else:
        print("\n⚠️ Some registrations failed. Check errors above.")

if __name__ == "__main__":
    main()
