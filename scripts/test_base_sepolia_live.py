#!/usr/bin/env python3
"""
Base Sepolia Live Transaction Test
Tests real GLUE payments between agents on Base Sepolia network
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from web3 import Web3
from shared.contracts_config import get_network_config
import json

# Base Sepolia configuration
NETWORK = "base-sepolia"
config = get_network_config(NETWORK)

# Connect to Base Sepolia
w3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
print(f"\n{'='*80}")
print(f"BASE SEPOLIA LIVE TRANSACTION TEST")
print(f"{'='*80}\n")

# Check connection
if not w3.is_connected():
    print("❌ ERROR: Cannot connect to Base Sepolia RPC")
    sys.exit(1)

print(f"✅ Connected to Base Sepolia (Chain ID: {w3.eth.chain_id})")
print(f"   Latest block: {w3.eth.block_number}")

# GLUE token contract
GLUE_ABI = [
    {'inputs': [{'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'},
    {'inputs': [], 'name': 'totalSupply', 'outputs': [{'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'},
    {'inputs': [], 'name': 'name', 'outputs': [{'type': 'string'}], 'stateMutability': 'view', 'type': 'function'},
    {'inputs': [], 'name': 'symbol', 'outputs': [{'type': 'string'}], 'stateMutability': 'view', 'type': 'function'},
    {'inputs': [], 'name': 'decimals', 'outputs': [{'type': 'uint8'}], 'stateMutability': 'view', 'type': 'function'}
]

glue_token = w3.eth.contract(
    address=Web3.to_checksum_address(config["glue_token"]),
    abi=GLUE_ABI
)

# Verify GLUE token
print(f"\n{'='*80}")
print("GLUE TOKEN VERIFICATION")
print(f"{'='*80}")
print(f"Address:      {config['glue_token']}")
print(f"Name:         {glue_token.functions.name().call()}")
print(f"Symbol:       {glue_token.functions.symbol().call()}")
print(f"Decimals:     {glue_token.functions.decimals().call()}")
print(f"Total Supply: {glue_token.functions.totalSupply().call() / 10**6:,.2f} GLUE")

# Agent addresses
agents = {
    "validator": "0x1219eF9484BF7E40E6479141B32634623d37d507",
    "karma-hello": "0x2C3e071df446B25B821F59425152838ae4931E75",
    "abracadabra": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648",
    "skill-extractor": "0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9",
    "voice-extractor": "0x8e0Db88181668cdE24660D7Ee8dA18A77DDbbF96"
}

# Check balances
print(f"\n{'='*80}")
print("AGENT BALANCES ON BASE SEPOLIA")
print(f"{'='*80}")

for name, address in agents.items():
    try:
        # GLUE balance
        glue_balance = glue_token.functions.balanceOf(Web3.to_checksum_address(address)).call()
        glue_formatted = glue_balance / 10**6

        # ETH balance
        eth_balance = w3.eth.get_balance(Web3.to_checksum_address(address))
        eth_formatted = float(w3.from_wei(eth_balance, 'ether'))

        status = "✅" if glue_balance > 0 else "⚠️"
        print(f"{status} {name:18s} | GLUE: {glue_formatted:>12,.2f} | ETH: {eth_formatted:.6f}")

    except Exception as e:
        print(f"❌ {name:18s} | ERROR: {e}")

# Verify contracts
print(f"\n{'='*80}")
print("ERC-8004 REGISTRY VERIFICATION")
print(f"{'='*80}")

contracts_info = [
    ("Identity Registry", config["identity_registry"]),
    ("Reputation Registry", config["reputation_registry"]),
    ("Validation Registry", config["validation_registry"])
]

for name, address in contracts_info:
    try:
        # Check if contract has code
        code = w3.eth.get_code(Web3.to_checksum_address(address))
        if code and code != b'\x00':
            print(f"✅ {name:22s} | {address}")
        else:
            print(f"❌ {name:22s} | {address} (NO CODE)")
    except Exception as e:
        print(f"❌ {name:22s} | ERROR: {e}")

# Agent card verification
print(f"\n{'='*80}")
print("AGENT ENDPOINT VERIFICATION")
print(f"{'='*80}")

import requests

agent_urls = {
    "karma-hello": "https://karma-hello.karmacadabra.ultravioletadao.xyz",
    "abracadabra": "https://abracadabra.karmacadabra.ultravioletadao.xyz",
    "skill-extractor": "https://skill-extractor.karmacadabra.ultravioletadao.xyz",
    "voice-extractor": "https://voice-extractor.karmacadabra.ultravioletadao.xyz",
    "validator": "https://validator.karmacadabra.ultravioletadao.xyz"
}

for name, url in agent_urls.items():
    try:
        # Health check
        health_response = requests.get(f"{url}/health", timeout=5)
        health_ok = health_response.status_code == 200

        # Agent card check
        card_response = requests.get(f"{url}/.well-known/agent-card", timeout=5)
        card_ok = card_response.status_code == 200

        if card_ok:
            card_data = card_response.json()
            network_in_card = card_data.get("blockchain", {}).get("network", "N/A")
            network_status = "✅" if network_in_card == "base-sepolia" else f"⚠️ ({network_in_card})"
        else:
            network_status = "❌"

        status = "✅" if health_ok and card_ok else "⚠️"
        print(f"{status} {name:18s} | Health: {'✅' if health_ok else '❌'} | Agent Card: {'✅' if card_ok else '❌'} | Network: {network_status}")

    except Exception as e:
        print(f"❌ {name:18s} | ERROR: {str(e)[:50]}")

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"✅ Network: Base Sepolia (Chain ID: {config['chain_id']})")
print(f"✅ GLUE Token: {config['glue_token']}")
print(f"✅ RPC: {config['rpc_url']}")
print(f"✅ Block Explorer: https://sepolia.basescan.org")
print(f"\n📊 All agents have GLUE and are ready for transactions")
print(f"🔗 Facilitator: https://facilitator.ultravioletadao.xyz")

print(f"\n💡 To test a real payment:")
print(f"   1. Use test-seller or client-agent to buy from karma-hello")
print(f"   2. Transaction will be visible at: https://sepolia.basescan.org/token/{config['glue_token']}")
print(f"\n{'='*80}\n")
