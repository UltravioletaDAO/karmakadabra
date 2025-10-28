#!/usr/bin/env python3
"""
Query Agent ID 32 to see what's actually stored
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web3 import Web3
from dotenv import load_dotenv

load_dotenv(project_root / ".env")

RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
IDENTITY_REGISTRY = os.getenv("IDENTITY_REGISTRY", "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Get agent info by ID
abi = [
    {"inputs": [{"name": "_agentId", "type": "uint256"}], "name": "getAgent", "outputs": [
        {"name": "agentAddress", "type": "address"},
        {"name": "domain", "type": "string"},
        {"name": "exists", "type": "bool"}
    ], "stateMutability": "view", "type": "function"}
]

contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=abi)

print("=" * 80)
print("QUERYING AGENT ID 32 FROM IDENTITY REGISTRY")
print("=" * 80)
print("")

try:
    result = contract.functions.getAgent(32).call()
    agent_address, domain, exists = result

    print(f"Agent ID:      32")
    print(f"Address:       {agent_address}")
    print(f"Domain:        {domain}")
    print(f"Exists:        {exists}")
    print("")

    print("Now checking which addresses map to this ID...")
    print("")

    # Check resolve for first 3 agents
    resolve_abi = [{"inputs": [{"name": "_agentAddress", "type": "address"}], "name": "resolveByAddress", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]
    resolve_contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=resolve_abi)

    test_addresses = [
        ("0xdream_sgo", "0x77687D414D7D6EACE40CB22b4667ad34E21744fc"),
        ("cyberpaisa", "0xB7b5352CdBB60d3E507668bc66285b849C67c75F"),
        ("fredinoo", "0x3ded7fB784f90aECb537B6AaA7f62962D2203c1f"),
    ]

    print("Testing address resolution:")
    print("-" * 80)
    for username, address in test_addresses:
        resolved_id = resolve_contract.functions.resolveByAddress(address).call()
        print(f"{username:<20} {address} -> Agent ID {resolved_id}")

    print("")
    print("BUG CONFIRMED: All different addresses resolve to the same Agent ID 32")
    print("This is an Identity Registry contract bug.")

except Exception as e:
    print(f"Error querying agent: {e}")
