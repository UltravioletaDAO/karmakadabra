#!/usr/bin/env python3
"""
Direct on-chain verification - no .env dependencies
Hardcodes addresses to verify blockchain state
"""

from web3 import Web3

# Hardcoded from docs/plans/SYSTEM_STATUS_REPORT.md
RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
IDENTITY_REGISTRY = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
GLUE_TOKEN = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Contract ABIs
IDENTITY_ABI = [
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
        "inputs": [{"internalType": "uint256", "name": "_agentId", "type": "uint256"}],
        "name": "getAgentDomain",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "_agentId", "type": "uint256"}],
        "name": "getAgentAddress",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
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
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

identity = w3.eth.contract(address=Web3.to_checksum_address(IDENTITY_REGISTRY), abi=IDENTITY_ABI)
glue = w3.eth.contract(address=Web3.to_checksum_address(GLUE_TOKEN), abi=ERC20_ABI)

print("=" * 80)
print("ON-CHAIN VERIFICATION (No .env dependencies)")
print("=" * 80)
print()

print("Connection:")
print(f"  RPC: {RPC_URL}")
print(f"  Connected: {w3.is_connected()}")
print(f"  Chain ID: {w3.eth.chain_id}")
print(f"  Latest Block: {w3.eth.block_number:,}")
print()

print("Contracts:")
print(f"  Identity Registry: {IDENTITY_REGISTRY}")
print(f"  GLUE Token: {GLUE_TOKEN}")
print()

# Check GLUE decimals and total supply
try:
    decimals = 6  # GLUE uses 6 decimals like USDC
    total_supply = glue.functions.totalSupply().call()
    print(f"GLUE Decimals: {decimals}")
    print(f"GLUE Total Supply: {total_supply / 10**decimals:,.0f} tokens")
    print(f"GLUE Total Supply (raw): {total_supply:,}")

    # Check owner wallet balance
    OWNER_WALLET = "0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8"
    owner_balance = glue.functions.balanceOf(Web3.to_checksum_address(OWNER_WALLET)).call()
    print(f"Owner Wallet ({OWNER_WALLET}): {owner_balance / 10**decimals:,.0f} GLUE")
except Exception as e:
    print(f"ERROR getting GLUE supply: {e}")
print()

# Agent addresses from docs/plans/SYSTEM_STATUS_REPORT.md
agents = {
    'client': '0xCf30021812F27132d36dc791E0eC17f34B4eE8BA',
    'karma-hello': '0x2C3e071df446B25B821F59425152838ae4931E75',
    'abracadabra': '0x940DDDf6fB28E611b132FbBedbc4854CC7C22648',
    'validator': '0x1219eF9484BF7E40E6479141B32634623d37d507',
    'voice-extractor': '0xDd63D5840090B98D9EB86f2c31974f9d6c270b17',
    'skill-extractor': '0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9'
}

print("=" * 80)
print("AGENT ON-CHAIN DATA")
print("=" * 80)
print()

for name, address in agents.items():
    print(f"{name.upper()}:")
    print(f"  Address: {address}")

    # AVAX balance
    avax_balance = w3.eth.get_balance(Web3.to_checksum_address(address))
    print(f"  AVAX: {w3.from_wei(avax_balance, 'ether'):.4f}")

    # GLUE balance (6 decimals)
    try:
        glue_balance = glue.functions.balanceOf(Web3.to_checksum_address(address)).call()
        print(f"  GLUE: {glue_balance / 10**6:,.2f}")
    except Exception as e:
        print(f"  GLUE ERROR: {e}")

    # Registration
    try:
        agent_info = identity.functions.resolveByAddress(Web3.to_checksum_address(address)).call()
        agent_id = agent_info[0]  # agentId
        domain = agent_info[1]     # agentDomain
        reg_address = agent_info[2]  # agentAddress

        if agent_id > 0:
            print(f"  Registered: YES (ID #{agent_id})")
            print(f"  Domain: {domain}")
        else:
            print(f"  Registered: NO (ID = 0)")
    except Exception as e:
        # Agent not registered - this is expected for some
        if "AgentNotFound" in str(e):
            print(f"  Registered: NO")
        else:
            print(f"  Registration ERROR: {e}")

    print()

print("=" * 80)
print("CHECKING AGENT IDs 1-10")
print("=" * 80)
print()

for agent_id in range(1, 11):
    try:
        address = identity.functions.getAgentAddress(agent_id).call()
        domain = identity.functions.getAgentDomain(agent_id).call()

        if address != "0x0000000000000000000000000000000000000000":
            print(f"ID #{agent_id}:")
            print(f"  Address: {address}")
            print(f"  Domain: {domain}")
            print()
    except Exception as e:
        # ID doesn't exist
        pass

print("=" * 80)
