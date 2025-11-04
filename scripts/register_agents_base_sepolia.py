#!/usr/bin/env python3
"""
Register Agents on Base Sepolia Identity Registry
Registers all 5 system agents: validator, karma-hello, abracadabra, skill-extractor, voice-extractor
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from web3 import Web3
from eth_account import Account
import json
import boto3

print("=" * 80)
print("REGISTER AGENTS - BASE SEPOLIA")
print("=" * 80)
print()

# Configuration - Base Sepolia
RPC_URL = "https://base-sepolia.g.alchemy.com/v2/demo"
CHAIN_ID = 84532
IDENTITY_REGISTRY = "0x8a20f665c02a33562a0462a0908a64716Ed7463d"

# Identity Registry ABI (v0.3 - returns AgentInfo struct, not uint256)
IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "agentDomain", "type": "string"},
            {"internalType": "address", "name": "agentAddress", "type": "address"}
        ],
        "name": "newAgent",
        "outputs": [{"internalType": "uint256", "name": "agentId", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "agentAddress", "type": "address"}],
        "name": "resolveByAddress",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "agentId", "type": "uint256"},
                    {"internalType": "string", "name": "agentDomain", "type": "string"},
                    {"internalType": "address", "name": "agentAddress", "type": "address"}
                ],
                "internalType": "struct IIdentityRegistry.AgentInfo",
                "name": "agentInfo",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "REGISTRATION_FEE",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "AgentNotFound",
        "type": "error"
    }
]

# Agents to register (all 5 system agents)
AGENTS_TO_REGISTER = {
    'validator': {
        'address': '0x1219eF9484BF7E40E6479141B32634623d37d507',
        'domain': 'validator.karmacadabra.ultravioletadao.xyz'
    },
    'karma-hello': {
        'address': '0x2C3e071df446B25B821F59425152838ae4931E75',
        'domain': 'karma-hello.karmacadabra.ultravioletadao.xyz'
    },
    'abracadabra': {
        'address': '0x940DDDf6fB28E611b132FbBedbc4854CC7C22648',
        'domain': 'abracadabra.karmacadabra.ultravioletadao.xyz'
    },
    'skill-extractor': {
        'address': '0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9',
        'domain': 'skill-extractor.karmacadabra.ultravioletadao.xyz'
    },
    'voice-extractor': {
        'address': '0xDd63D5840090B98D9EB86f2c31974f9d6c270b17',  # Use Fuji address (has key in AWS)
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
            'karma-hello': 'karma-hello-agent',
            'abracadabra': 'abracadabra-agent',
            'skill-extractor': 'skill-extractor-agent',
            'voice-extractor': 'voice-extractor-agent'
        }

        secret_key = aws_key_map.get(agent_name)
        if secret_key and secret_key in secrets:
            return secrets[secret_key]['private_key']

    except Exception as e:
        print(f"[X] AWS error for {agent_name}: {e}")

    return None

def register_agent(w3, identity_registry, agent_name, info, registration_fee):
    """Register a single agent on-chain"""
    print(f"\n[*] Registering {agent_name}...")
    print(f"   Domain: {info['domain']}")
    print(f"   Address: {info['address']}")

    # Get agent's private key
    private_key = get_agent_private_key(agent_name)
    if not private_key:
        print(f"   [X] Could not get private key from AWS")
        return False

    account = Account.from_key(private_key)

    # Check if already registered (v0.3 contract reverts with AgentNotFound if not registered)
    try:
        agent_info = identity_registry.functions.resolveByAddress(
            Web3.to_checksum_address(info['address'])
        ).call()
        # If we get here, agent is already registered
        existing_id = agent_info[0]  # agentId is first element of tuple
        print(f"   [+] Already registered with ID #{existing_id}")
        return True
    except Exception as e:
        # AgentNotFound error means not registered yet - continue with registration
        if "AgentNotFound" in str(e) or "0xe93ba223" in str(e):
            pass  # Not registered, continue
        else:
            # Some other error
            print(f"   [X] Error checking registration: {e}")
            return False

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
            'value': registration_fee  # 0.005 ETH
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)

        # Handle both rawTransaction and raw_transaction attributes
        raw_tx = signed_tx.rawTransaction if hasattr(signed_tx, 'rawTransaction') else signed_tx.raw_transaction
        tx_hash = w3.eth.send_raw_transaction(raw_tx)

        print(f"   [+] Transaction sent: {tx_hash.hex()}")
        print(f"   [+] https://sepolia.basescan.org/tx/{tx_hash.hex()}")
        print(f"   [*] Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            # Get the new agent ID from contract (returns tuple: (agentId, domain, address))
            try:
                agent_info = identity_registry.functions.resolveByAddress(
                    Web3.to_checksum_address(info['address'])
                ).call()
                new_id = agent_info[0]  # agentId is first element
                print(f"   [+] Registered successfully! Agent ID: #{new_id}")
            except Exception as e:
                # Sometimes there's a timing issue reading immediately after registration
                print(f"   [+] Registered successfully! (could not read ID: {e})")
            return True
        else:
            print(f"   [X] Transaction failed")
            return False

    except Exception as e:
        print(f"   [X] Error: {e}")
        return False

def main():
    # Connect to Base Sepolia
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        print("[X] Failed to connect to Base Sepolia")
        return

    print(f"[+] Connected to Base Sepolia")
    print(f"   Latest block: {w3.eth.block_number:,}")
    print(f"   Identity Registry: {IDENTITY_REGISTRY}")

    # Load identity registry contract
    identity_registry = w3.eth.contract(
        address=Web3.to_checksum_address(IDENTITY_REGISTRY),
        abi=IDENTITY_REGISTRY_ABI
    )

    # Get registration fee
    registration_fee = identity_registry.functions.REGISTRATION_FEE().call()
    print(f"   Registration fee: {w3.from_wei(registration_fee, 'ether')} ETH")

    # Check if --confirm flag is provided
    if '--confirm' not in sys.argv:
        print("\n[*] DRY RUN - Add --confirm to execute registrations")
        print(f"\nAgents to register:")
        for name, info in AGENTS_TO_REGISTER.items():
            print(f"   {name}: {info['domain']}")
        print(f"\nTotal cost: {w3.from_wei(registration_fee * len(AGENTS_TO_REGISTER), 'ether')} ETH")
        print(f"\nRun with: python scripts/register_agents_base_sepolia.py --confirm")
        return

    print("\n[+] CONFIRMED - Proceeding with registrations...")
    print("=" * 80)

    # Register each agent
    results = {}
    for agent_name, info in AGENTS_TO_REGISTER.items():
        results[agent_name] = register_agent(w3, identity_registry, agent_name, info, registration_fee)

    # Summary
    print("\n" + "=" * 80)
    print("REGISTRATION SUMMARY")
    print("=" * 80)

    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)

    for agent_name, success in results.items():
        status = "[+]" if success else "[X]"
        print(f"{status} {agent_name}")

    print(f"\nRegistered: {success_count}/{total_count}")

    if success_count == total_count:
        print("\n[+] ALL AGENTS REGISTERED!")
        print("\nNext step: Verify contracts on Basescan (optional)")
    else:
        print("\n[X] Some registrations failed. Check errors above.")

if __name__ == "__main__":
    main()
