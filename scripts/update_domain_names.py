#!/usr/bin/env python3
"""
Update Domain Names for Already-Registered Agents
Fixes: client, karma-hello, abracadabra
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
print("UPDATE AGENT DOMAIN NAMES")
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
            {"internalType": "uint256", "name": "_agentId", "type": "uint256"},
            {"internalType": "string", "name": "_newAgentDomain", "type": "string"},
            {"internalType": "address", "name": "_newAgentAddress", "type": "address"}
        ],
        "name": "updateAgent",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "_agentAddress", "type": "address"}],
        "name": "resolveByAddress",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "_agentId", "type": "uint256"}],
        "name": "agents",
        "outputs": [
            {"internalType": "string", "name": "agentDomain", "type": "string"},
            {"internalType": "address", "name": "agentAddress", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Agents to update (from SYSTEM_STATUS_REPORT.md)
AGENTS_TO_UPDATE = {
    'client': {
        'agent_id': 3,
        'address': '0xCf30021812F27132d36dc791E0eC17f34B4eE8BA',
        'old_domain': 'client.karmacadabra.xyz',
        'new_domain': 'client.karmacadabra.ultravioletadao.xyz'
    },
    'karma-hello': {
        'agent_id': 1,
        'address': '0x2C3e071df446B25B821F59425152838ae4931E75',
        'old_domain': 'karma-hello.ultravioletadao.xyz',
        'new_domain': 'karma-hello.karmacadabra.ultravioletadao.xyz'
    },
    'abracadabra': {
        'agent_id': 2,
        'address': '0x940DDDf6fB28E611b132FbBedbc4854CC7C22648',
        'old_domain': 'abracadabra.ultravioletadao.xyz',
        'new_domain': 'abracadabra.karmacadabra.ultravioletadao.xyz'
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
            'client': 'client-agent',
            'karma-hello': 'karma-hello-agent',
            'abracadabra': 'abracadabra-agent'
        }

        secret_key = aws_key_map.get(agent_name)
        if secret_key and secret_key in secrets:
            return secrets[secret_key]['private_key']

    except Exception as e:
        print(f"[FAIL] AWS error for {agent_name}: {e}")

    return None

def update_agent_domain(w3, agent_name, info):
    """Update a single agent's domain"""
    print(f"\nUpdating {agent_name} (ID #{info['agent_id']})...")
    print(f"  Current: {info['old_domain']}")
    print(f"  New:     {info['new_domain']}")
    print(f"  Address: {info['address']}")

    # Get agent's private key
    private_key = get_agent_private_key(agent_name)
    if not private_key:
        print(f"  [FAIL] Could not get private key from AWS")
        return False

    account = Account.from_key(private_key)

    # Verify address matches
    if account.address.lower() != info['address'].lower():
        print(f"  [FAIL] Private key address mismatch!")
        print(f"         Expected: {info['address']}")
        print(f"         Got: {account.address}")
        return False

    # Create contract instance
    identity_registry = w3.eth.contract(
        address=Web3.to_checksum_address(IDENTITY_REGISTRY),
        abi=IDENTITY_REGISTRY_ABI
    )

    # Verify current registration
    try:
        current_id = identity_registry.functions.resolveByAddress(
            Web3.to_checksum_address(info['address'])
        ).call()

        if current_id != info['agent_id']:
            print(f"  [FAIL] Agent ID mismatch! Expected {info['agent_id']}, got {current_id}")
            return False

        # Get current domain
        current_domain, _ = identity_registry.functions.agents(info['agent_id']).call()
        print(f"  Verified current domain: {current_domain}")

    except Exception as e:
        print(f"  [FAIL] Error verifying registration: {e}")
        return False

    # Update domain
    try:
        nonce = w3.eth.get_transaction_count(account.address)

        # updateAgent(_agentId, _newAgentDomain, _newAgentAddress)
        # Use 0x0000...0000 for address to keep it the same
        tx = identity_registry.functions.updateAgent(
            info['agent_id'],
            info['new_domain'],
            Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
        ).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price,
            'chainId': CHAIN_ID
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"  [OK] Transaction sent: {tx_hash.hex()}")
        print(f"       https://testnet.snowtrace.io/tx/{tx_hash.hex()}")
        print(f"       Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            # Verify update
            new_domain, _ = identity_registry.functions.agents(info['agent_id']).call()
            if new_domain == info['new_domain']:
                print(f"  [OK] Domain updated successfully!")
                print(f"       New domain: {new_domain}")
                return True
            else:
                print(f"  [FAIL] Domain update verification failed")
                print(f"        Expected: {info['new_domain']}")
                print(f"        Got: {new_domain}")
                return False
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
        print("\n[DRY RUN] Add --confirm to execute updates")
        print(f"\nAgents to update:")
        for name, info in AGENTS_TO_UPDATE.items():
            print(f"  - {name} (ID #{info['agent_id']})")
            print(f"    Old: {info['old_domain']}")
            print(f"    New: {info['new_domain']}")
        print(f"\nRun with: python scripts/update_domain_names.py --confirm")
        return

    print("\n[CONFIRMED] Proceeding with updates...")
    print("=" * 80)

    # Update each agent
    results = {}
    for agent_name, info in AGENTS_TO_UPDATE.items():
        results[agent_name] = update_agent_domain(w3, agent_name, info)

    # Summary
    print("\n" + "=" * 80)
    print("UPDATE SUMMARY")
    print("=" * 80)

    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)

    for agent_name, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        domain = AGENTS_TO_UPDATE[agent_name]['new_domain']
        print(f"{status} {agent_name}: {domain}")

    print(f"\nUpdated: {success_count}/{total_count}")

    if success_count == total_count:
        print("\n✅ ALL DOMAIN NAMES UPDATED!")
        print("\nNext step: Verify system status")
        print("  python scripts/check_system_ready.py")
    else:
        print("\n⚠️ Some updates failed. Check errors above.")

if __name__ == "__main__":
    main()
