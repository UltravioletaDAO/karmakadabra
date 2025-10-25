#!/usr/bin/env python3
"""
Check if Karmacadabra system is ready for demo
Verifies: funding, registrations, agent availability
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from web3 import Web3
from dotenv import load_dotenv
import json

load_dotenv()

# Contract ABIs (minimal for checks)
IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "_agentAddress", "type": "address"}],
        "name": "resolveByAddress",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def check_agent_status(w3, agent_name, agent_address, identity_registry, glue_token):
    """Check single agent's funding and registration"""
    print(f"\n{agent_name}:")
    print(f"  Address: {agent_address}")

    # Check AVAX balance
    avax_balance = w3.eth.get_balance(agent_address)
    avax_balance_ether = w3.from_wei(avax_balance, 'ether')
    status = "✅" if avax_balance_ether >= 0.01 else "❌"
    print(f"  AVAX: {avax_balance_ether:.4f} {status}")

    # Check GLUE balance
    glue_balance = glue_token.functions.balanceOf(agent_address).call()
    glue_balance_tokens = glue_balance / 10**18
    print(f"  GLUE: {glue_balance_tokens:,.0f}")

    # Check registration
    try:
        agent_id = identity_registry.functions.resolveByAddress(agent_address).call()
        if agent_id > 0:
            print(f"  Registration: ✅ ID #{agent_id}")
        else:
            print(f"  Registration: ❌ NOT REGISTERED")
    except Exception as e:
        print(f"  Registration: ❌ ERROR - {e}")

    return {
        'has_avax': avax_balance_ether >= 0.01,
        'has_glue': glue_balance_tokens > 0,
        'registered': agent_id > 0 if 'agent_id' in locals() else False
    }

def main():
    print("=" * 80)
    print("KARMACADABRA SYSTEM STATUS CHECK")
    print("=" * 80)

    # Connect to blockchain
    rpc_url = os.getenv("RPC_URL_FUJI")
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print("❌ Failed to connect to Avalanche Fuji")
        return

    print(f"\n✅ Connected to Avalanche Fuji")
    print(f"Latest block: {w3.eth.block_number:,}")

    # Load contracts
    identity_registry_address = os.getenv("IDENTITY_REGISTRY")
    glue_token_address = os.getenv("GLUE_TOKEN_ADDRESS")

    identity_registry = w3.eth.contract(
        address=Web3.to_checksum_address(identity_registry_address),
        abi=IDENTITY_REGISTRY_ABI
    )

    glue_token = w3.eth.contract(
        address=Web3.to_checksum_address(glue_token_address),
        abi=ERC20_ABI
    )

    print(f"\nContracts:")
    print(f"  Identity Registry: {identity_registry_address}")
    print(f"  GLUE Token: {glue_token_address}")

    # Load agent addresses from .env files
    print("\n" + "=" * 80)
    print("SERVICE AGENTS (agents/ folder)")
    print("=" * 80)

    print("\nLoading agent addresses from .env files...")
    import re
    project_root = Path(__file__).parent.parent

    service_agents = {}
    agent_dirs = {
        'karma-hello': project_root / 'agents' / 'karma-hello' / '.env',
        'skill-extractor': project_root / 'agents' / 'skill-extractor' / '.env',
        'voice-extractor': project_root / 'agents' / 'voice-extractor' / '.env',
        'validator': project_root / 'agents' / 'validator' / '.env',
    }

    for agent_name, env_path in agent_dirs.items():
        try:
            with open(env_path, 'r') as f:
                content = f.read()
                # Look for AGENT_ADDRESS or VALIDATOR_WALLET
                addr_match = re.search(r'(?:AGENT_ADDRESS|VALIDATOR_WALLET)=(\s*)(0x[a-fA-F0-9]{40})', content)
                if addr_match:
                    service_agents[agent_name] = addr_match.group(2)
                else:
                    service_agents[agent_name] = None
        except FileNotFoundError:
            print(f"  [SKIP] {env_path} not found")
            service_agents[agent_name] = None

    results = {}
    for name, address in service_agents.items():
        if address:
            results[name] = check_agent_status(w3, name, address, identity_registry, glue_token)
        else:
            print(f"\n{name}: ❌ ADDRESS NOT SET IN .env")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    ready_count = sum(1 for r in results.values() if r['has_avax'] and r['registered'])
    total_count = len(results)

    print(f"\nAgents Ready: {ready_count}/{total_count}")

    if ready_count == total_count:
        print("\n✅ SYSTEM READY FOR DEMO!")
        print("\nRun demo:")
        print("  python scripts/demo_client_purchases.py")
    else:
        print("\n⚠️ SYSTEM NOT READY")
        print("\nTo fix:")
        not_funded = [name for name, r in results.items() if not r['has_avax']]
        not_registered = [name for name, r in results.items() if not r['registered']]

        if not_funded:
            print(f"  1. Fund agents: {', '.join(not_funded)}")
            print(f"     python erc-20/distribute-token.py --avax {' '.join(not_funded)}")

        if not_registered:
            print(f"  2. Register agents: {', '.join(not_registered)}")
            print(f"     python scripts/register_agents.py {' '.join(not_registered)}")

if __name__ == "__main__":
    main()
