#!/usr/bin/env python3
"""
Base Sepolia Standalone Test - No dependencies on shared modules
Tests GLUE balances and agent endpoints on Base Sepolia
"""

from web3 import Web3
import requests

# Base Sepolia configuration
CHAIN_ID = 84532
RPC_URL = "https://sepolia.base.org"
GLUE_TOKEN = "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425"
IDENTITY_REGISTRY = "0x8a20f665c02a33562a0462a0908a64716Ed7463d"
REPUTATION_REGISTRY = "0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F"
VALIDATION_REGISTRY = "0x3C545DBeD1F587293fA929385442A459c2d316c4"

# Connect to Base Sepolia
w3 = Web3(Web3.HTTPProvider(RPC_URL))
print(f"\n{'='*80}")
print(f"BASE SEPOLIA LIVE VERIFICATION")
print(f"{'='*80}\n")

# Check connection
if not w3.is_connected():
    print("❌ ERROR: Cannot connect to Base Sepolia RPC")
    exit(1)

print(f"✅ Connected to Base Sepolia (Chain ID: {w3.eth.chain_id})")
print(f"   Latest block: {w3.eth.block_number}")

# GLUE token ABI (minimal)
GLUE_ABI = [
    {'inputs': [{'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'},
    {'inputs': [], 'name': 'totalSupply', 'outputs': [{'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'},
    {'inputs': [], 'name': 'name', 'outputs': [{'type': 'string'}], 'stateMutability': 'view', 'type': 'function'},
    {'inputs': [], 'name': 'symbol', 'outputs': [{'type': 'string'}], 'stateMutability': 'view', 'type': 'function'}
]

glue = w3.eth.contract(address=Web3.to_checksum_address(GLUE_TOKEN), abi=GLUE_ABI)

# Verify GLUE token
print(f"\n{'='*80}")
print("GLUE TOKEN")
print(f"{'='*80}")
print(f"Address:      {GLUE_TOKEN}")
print(f"Name:         {glue.functions.name().call()}")
print(f"Symbol:       {glue.functions.symbol().call()}")
print(f"Total Supply: {glue.functions.totalSupply().call() / 10**6:,.2f} GLUE")
print(f"Explorer:     https://sepolia.basescan.org/token/{GLUE_TOKEN}")

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
        glue_balance = glue.functions.balanceOf(Web3.to_checksum_address(address)).call()
        glue_formatted = glue_balance / 10**6

        eth_balance = w3.eth.get_balance(Web3.to_checksum_address(address))
        eth_formatted = float(w3.from_wei(eth_balance, 'ether'))

        status = "✅" if glue_balance > 0 else "⚠️"
        print(f"{status} {name:18s} | GLUE: {glue_formatted:>12,.2f} | ETH: {eth_formatted:.6f}")

    except Exception as e:
        print(f"❌ {name:18s} | ERROR: {e}")

# Verify contracts
print(f"\n{'='*80}")
print("ERC-8004 REGISTRIES")
print(f"{'='*80}")

contracts = [
    ("Identity", IDENTITY_REGISTRY),
    ("Reputation", REPUTATION_REGISTRY),
    ("Validation", VALIDATION_REGISTRY)
]

for name, address in contracts:
    try:
        code = w3.eth.get_code(Web3.to_checksum_address(address))
        if code and code != b'\x00':
            print(f"✅ {name:11s} | {address}")
        else:
            print(f"❌ {name:11s} | {address} (NO CODE)")
    except Exception as e:
        print(f"❌ {name:11s} | ERROR: {e}")

# Agent endpoints
print(f"\n{'='*80}")
print("AGENT ENDPOINTS")
print(f"{'='*80}")

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
        health = requests.get(f"{url}/health", timeout=5)
        health_ok = health.status_code == 200

        # Agent card
        card = requests.get(f"{url}/.well-known/agent-card", timeout=5)
        card_ok = card.status_code == 200

        if card_ok:
            card_data = card.json()
            network = card_data.get("blockchain", {}).get("network", "N/A")
            network_status = "✅ base-sepolia" if network == "base-sepolia" else f"⚠️ {network}"
        else:
            network_status = "❌ N/A"

        status = "✅" if health_ok and card_ok else "⚠️"
        print(f"{status} {name:18s} | Health: {'✅' if health_ok else '❌'} | Network: {network_status}")

    except Exception as e:
        print(f"❌ {name:18s} | ERROR: {str(e)[:40]}")

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"✅ Chain ID: {CHAIN_ID}")
print(f"✅ RPC: {RPC_URL}")
print(f"✅ GLUE Token: {GLUE_TOKEN}")
print(f"✅ Block Explorer: https://sepolia.basescan.org")
print(f"🔗 Facilitator: https://facilitator.ultravioletadao.xyz")

print(f"\n💡 Next step: Run a test transaction")
print(f"   cd test-seller && python load_test_smart.py")
print(f"   View transaction: https://sepolia.basescan.org/token/{GLUE_TOKEN}")
print(f"\n{'='*80}\n")
