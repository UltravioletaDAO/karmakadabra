#!/usr/bin/env python3
"""
Debug script to check agent registrations on-chain
"""

import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

IDENTITY_REGISTRY = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
GLUE_TOKEN = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"

# ABI for resolveByAddress
IDENTITY_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "_agentAddress", "type": "address"}],
        "name": "resolveByAddress",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "_agentId", "type": "uint256"}],
        "name": "getAgentDomain",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
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

identity = w3.eth.contract(address=Web3.to_checksum_address(IDENTITY_REGISTRY), abi=IDENTITY_ABI)
glue = w3.eth.contract(address=Web3.to_checksum_address(GLUE_TOKEN), abi=ERC20_ABI)

agents = {
    'karma-hello': '0x2C3e071df446B25B821F59425152838ae4931E75',
    'skill-extractor': '0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9',
    'voice-extractor': '0xDd63D5840090B98D9EB86f2c31974f9d6c270b17',
    'validator': '0x1219eF9484BF7E40E6479141B32634623d37d507',
    'abracadabra': '0x940DDDf6fB28E611b132FbBedbc4854CC7C22648',
    'client': '0xCf30021812F27132d36dc791E0eC17f34B4eE8BA'
}

print("=" * 80)
print("DEBUGGING AGENT REGISTRATIONS")
print("=" * 80)
print()

for name, address in agents.items():
    print(f"{name}:")
    print(f"  Address: {address}")

    # Check registration
    try:
        agent_id = identity.functions.resolveByAddress(Web3.to_checksum_address(address)).call()
        print(f"  Agent ID: {agent_id}")

        if agent_id > 0:
            # Get domain
            domain = identity.functions.getAgentDomain(agent_id).call()
            print(f"  Domain: {domain}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Check GLUE balance
    try:
        balance = glue.functions.balanceOf(Web3.to_checksum_address(address)).call()
        balance_tokens = balance / 10**18
        print(f"  GLUE Balance: {balance_tokens:,.2f}")
    except Exception as e:
        print(f"  GLUE ERROR: {e}")

    print()

print("=" * 80)
print("CHECKING IF ID #32 EXISTS")
print("=" * 80)
try:
    domain_32 = identity.functions.getAgentDomain(32).call()
    print(f"ID #32 Domain: {domain_32}")
except Exception as e:
    print(f"ERROR getting ID #32: {e}")
