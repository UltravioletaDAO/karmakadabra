#!/usr/bin/env python3
"""
Verify User Agent Setup

DYNAMIC: Checks ALL user agents in client-agents/ folder are properly set up:
- Wallet exists in .env
- AVAX balance ≥ 0.05
- GLUE balance ≥ 1000
- Registered on-chain

IDEMPOTENT: Safe to run multiple times to check status

Usage:
    python scripts/verify_user_agents.py
"""

import os
import sys
from pathlib import Path
from decimal import Decimal

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web3 import Web3
from eth_account import Account
from dotenv import dotenv_values

# Configuration
RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
IDENTITY_REGISTRY = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
GLUE_TOKEN_ADDRESS = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Get all user agents (DYNAMIC - automatically detects all agents)
CLIENT_AGENTS_DIR = project_root / "client-agents"
USER_AGENTS = sorted([d.name for d in CLIENT_AGENTS_DIR.iterdir() if d.is_dir() and d.name != "template"])
num_agents = len(USER_AGENTS)

print("=" * 80)
print(f"🔍 VERIFY USER AGENTS SETUP ({num_agents} agents)")
print("=" * 80)
print("")


def check_balance(address):
    """Check AVAX and GLUE balances"""
    try:
        # AVAX
        avax_wei = w3.eth.get_balance(address)
        avax = float(w3.from_wei(avax_wei, 'ether'))

        # GLUE
        glue_abi = [{"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]
        glue_contract = w3.eth.contract(address=GLUE_TOKEN_ADDRESS, abi=glue_abi)
        glue_balance = glue_contract.functions.balanceOf(address).call()
        glue = float(glue_balance) / 1e6

        return avax, glue
    except:
        return 0.0, 0.0


def check_registration(address):
    """Check if agent is registered on-chain"""
    try:
        # resolveByAddress returns AgentInfo struct: (agentId, agentDomain, agentAddress)
        abi = [{
            "inputs": [{"name": "agentAddress", "type": "address"}],
            "name": "resolveByAddress",
            "outputs": [{
                "components": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "agentDomain", "type": "string"},
                    {"name": "agentAddress", "type": "address"}
                ],
                "name": "agentInfo",
                "type": "tuple"
            }],
            "stateMutability": "view",
            "type": "function"
        }]
        contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=abi)
        agent_info = contract.functions.resolveByAddress(address).call()
        agent_id = agent_info[0]  # Extract agentId from tuple
        return agent_id > 0, agent_id
    except:
        return False, 0


results = {
    "wallet_ok": 0,
    "avax_ok": 0,
    "glue_ok": 0,
    "registered": 0,
    "total": len(USER_AGENTS)
}

issues = []

print(f"Checking {num_agents} user agents...")
print("")

for i, username in enumerate(USER_AGENTS, 1):
    env_path = CLIENT_AGENTS_DIR / username / ".env"

    # Check .env exists
    if not env_path.exists():
        issues.append(f"{username}: No .env file")
        continue

    # Load config
    config = dotenv_values(env_path)
    agent_address = config.get('AGENT_ADDRESS', '').strip()

    # Check wallet address
    if not agent_address:
        issues.append(f"{username}: No AGENT_ADDRESS in .env")
        continue

    # Validate address format
    if not agent_address.startswith('0x') or len(agent_address) != 42:
        issues.append(f"{username}: Invalid AGENT_ADDRESS format")
        continue

    results["wallet_ok"] += 1

    # Check balances
    avax, glue = check_balance(agent_address)

    status = []

    # AVAX check
    if avax >= 0.05:
        results["avax_ok"] += 1
        status.append(f"✅ AVAX: {avax:.4f}")
    else:
        status.append(f"❌ AVAX: {avax:.4f} (need ≥0.05)")
        issues.append(f"{username}: Insufficient AVAX ({avax:.4f})")

    # GLUE check
    if glue >= 1000:
        results["glue_ok"] += 1
        status.append(f"✅ GLUE: {glue:,.0f}")
    else:
        status.append(f"❌ GLUE: {glue:,.0f} (need ≥1000)")
        issues.append(f"{username}: Insufficient GLUE ({glue:,.0f})")

    # Registration check
    is_registered, agent_id = check_registration(agent_address)
    if is_registered:
        results["registered"] += 1
        status.append(f"✅ Registered (ID: {agent_id})")
    else:
        status.append(f"❌ Not registered")
        issues.append(f"{username}: Not registered on-chain")

    # Print status line
    status_line = " | ".join(status)
    print(f"[{i:2d}/{num_agents}] {username:20s} | {status_line}")

print("")
print("=" * 80)
print("📊 SUMMARY")
print("=" * 80)
print(f"Total agents:     {results['total']}")
print(f"Wallets OK:       {results['wallet_ok']}/{results['total']} ({results['wallet_ok']/results['total']*100:.0f}%)")
print(f"AVAX OK:          {results['avax_ok']}/{results['total']} ({results['avax_ok']/results['total']*100:.0f}%)")
print(f"GLUE OK:          {results['glue_ok']}/{results['total']} ({results['glue_ok']/results['total']*100:.0f}%)")
print(f"Registered:       {results['registered']}/{results['total']} ({results['registered']/results['total']*100:.0f}%)")
print("")

if issues:
    print("⚠️  ISSUES FOUND:")
    print("-" * 80)
    for issue in issues:
        print(f"  • {issue}")
    print("")
    print("To fix issues:")
    print("  python scripts/setup_user_agents.py --execute")
    print("")
    sys.exit(1)
else:
    print("✅ ALL CHECKS PASSED!")
    print("")
    print(f"All {num_agents} user agents are ready for the marketplace.")
    print("")
    print("Next steps:")
    print("  1. Test one agent: python tests/test_cyberpaisa_client.py")
    print("  2. Start marketplace: python scripts/bootstrap_marketplace.py")
    print("")
    sys.exit(0)
