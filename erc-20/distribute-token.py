#!/usr/bin/env python3
"""
Token Distribution Script
Distributes tokens (GLUE/UVD/etc.) to agent wallets based on role:
- System agents (validator, karma-hello, abracadabra): 21,892 tokens each
- Client agents: 10,946 tokens each

Configure token address in .env as UVD_TOKEN_ADDRESS

Usage:
    python distribute-token.py
"""

import os
from web3 import Web3
from dotenv import load_dotenv
import json

# Load environment
load_dotenv()

# Configuration
RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
CHAIN_ID = 43113
UVD_TOKEN_ADDRESS = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"  # GLUE Token
OWNER_PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# Amount to distribute per agent (with 6 decimals)
# All agents get 55,000 GLUE each
AGENT_AMOUNTS = {
    "validator-agent": 55_000 * 10**6,      # 55,000.000000 GLUE
    "karma-hello-agent": 55_000 * 10**6,    # 55,000.000000 GLUE
    "abracadabra-agent": 55_000 * 10**6,    # 55,000.000000 GLUE
    "client-agent": 55_000 * 10**6,         # 55,000.000000 GLUE
    "voice-extractor-agent": 55_000 * 10**6, # 55,000.000000 GLUE
}

# Agent wallet addresses (extracted from .env files)
AGENT_WALLETS = {
    "validator-agent": None,  # Will be loaded from .env
    "karma-hello-agent": None,
    "abracadabra-agent": None,
    "client-agent": None,  # Generic buyer agent
    "voice-extractor-agent": None,  # Voice/personality extraction agent
}

# GLUE Token ABI (minimal - only transfer function needed)
# Note: Currently using UVD V2 deployment until GLUE is deployed
UVD_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def load_agent_wallets():
    """Load agent wallet addresses from .env files"""
    import re

    agent_dirs = {
        "validator-agent": "../validator-agent/.env",
        "karma-hello-agent": "../karma-hello-agent/.env",
        "abracadabra-agent": "../abracadabra-agent/.env",
        "client-agent": "../client-agent/.env",
        "voice-extractor-agent": "../voice-extractor-agent/.env"
    }

    for agent_name, env_path in agent_dirs.items():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for AGENT_WALLET_ADDRESS or derive from PRIVATE_KEY
                wallet_match = re.search(r'AGENT_WALLET_ADDRESS=(\w+)', content)
                if wallet_match:
                    AGENT_WALLETS[agent_name] = wallet_match.group(1)
                else:
                    # Try to derive from PRIVATE_KEY
                    pk_match = re.search(r'PRIVATE_KEY=(0x[a-fA-F0-9]{64})', content)
                    if pk_match:
                        pk = pk_match.group(1)
                        w3 = Web3()
                        account = w3.eth.account.from_key(pk)
                        AGENT_WALLETS[agent_name] = account.address
                        print(f"[+] Derived {agent_name} address: {account.address}")
        except FileNotFoundError:
            print(f"[!] {env_path} not found, skipping {agent_name}")

    return AGENT_WALLETS

def distribute_tokens():
    """Main token distribution function (supports GLUE, UVD, or other ERC-20 tokens)"""
    print("=" * 60)
    print("Token Distribution to Agent Wallets")
    print("=" * 60)
    print()

    # Check owner private key
    if not OWNER_PRIVATE_KEY:
        print("[X] Error: PRIVATE_KEY not found in .env")
        return

    # Connect to blockchain
    print(f"[*] Connecting to Avalanche Fuji...")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        print("[X] Failed to connect to Avalanche Fuji")
        return

    print(f"[OK] Connected to Fuji (Chain ID: {w3.eth.chain_id})")
    print()

    # Load owner account
    owner_account = w3.eth.account.from_key(OWNER_PRIVATE_KEY)
    print(f"[OWNER] Address: {owner_account.address}")

    # Load UVD token contract
    uvd_contract = w3.eth.contract(address=UVD_TOKEN_ADDRESS, abi=UVD_ABI)

    # Check owner balance
    owner_balance = uvd_contract.functions.balanceOf(owner_account.address).call()
    owner_balance_human = owner_balance / 10**6
    print(f"[BALANCE] Owner GLUE Balance: {owner_balance_human:,.6f} GLUE")
    print()

    # Load agent wallets
    print("[LOAD] Loading agent wallet addresses...")
    load_agent_wallets()
    print()

    # Calculate total needed
    active_agents = [(name, addr) for name, addr in AGENT_WALLETS.items() if addr]
    total_needed = sum(AGENT_AMOUNTS[name] for name, _ in active_agents)
    total_needed_human = total_needed / 10**6

    print(f"[PLAN] Distribution Plan:")
    for agent_name, _ in active_agents:
        amount_human = AGENT_AMOUNTS[agent_name] / 10**6
        print(f"   {agent_name}: {amount_human:,.6f} GLUE")
    print(f"   Number of agents: {len(active_agents)}")
    print(f"   Total required: {total_needed_human:,.6f} GLUE")
    print()

    if owner_balance < total_needed:
        print(f"[X] Insufficient balance! Need {total_needed_human:,.6f} GLUE, have {owner_balance_human:,.6f} GLUE")
        return

    # Confirm distribution
    print("[READY] Ready to distribute to:")
    for agent_name, wallet_address in AGENT_WALLETS.items():
        if wallet_address:
            current_balance = uvd_contract.functions.balanceOf(wallet_address).call()
            current_balance_human = current_balance / 10**6
            print(f"   - {agent_name}: {wallet_address}")
            print(f"     Current balance: {current_balance_human:,.6f} GLUE")
    print()

    # Auto-proceed with distribution
    # Uncomment below to add manual confirmation:
    # response = input("Continue with distribution? (yes/no): ")
    # if response.lower() not in ['yes', 'y']:
    #     print("[X] Distribution cancelled")
    #     return
    print("[AUTO] Proceeding with distribution...")

    print()
    print("[START] Starting distribution...")
    print("-" * 60)

    # Distribute to each agent
    for agent_name, wallet_address in AGENT_WALLETS.items():
        if not wallet_address:
            print(f"[SKIP] Skipping {agent_name} (no wallet address)")
            continue

        amount_to_send = AGENT_AMOUNTS[agent_name]
        print(f"\n[SEND] Transferring {amount_to_send / 10**6:,.6f} GLUE to {agent_name}...")
        print(f"   Address: {wallet_address}")

        try:
            # Build transaction
            nonce = w3.eth.get_transaction_count(owner_account.address)

            tx = uvd_contract.functions.transfer(
                wallet_address,
                amount_to_send
            ).build_transaction({
                'from': owner_account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': CHAIN_ID
            })

            # Sign transaction
            signed_tx = w3.eth.account.sign_transaction(tx, OWNER_PRIVATE_KEY)

            # Send transaction
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"   TX Hash: {tx_hash.hex()}")

            # Wait for receipt
            print(f"   [WAIT] Waiting for confirmation...")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"   [OK] SUCCESS!")
                print(f"   [LINK] https://testnet.snowtrace.io/tx/{tx_hash.hex()}")

                # Check new balance
                new_balance = uvd_contract.functions.balanceOf(wallet_address).call()
                new_balance_human = new_balance / 10**6
                print(f"   [BALANCE] New balance: {new_balance_human:,.6f} GLUE")
            else:
                print(f"   [X] Transaction failed!")

        except Exception as e:
            print(f"   [X] Error: {e}")

    print()
    print("=" * 60)
    print("[OK] Distribution Complete!")
    print("=" * 60)

    # Final balances
    print("\n[SUMMARY] Final Balances:")
    for agent_name, wallet_address in AGENT_WALLETS.items():
        if wallet_address:
            balance = uvd_contract.functions.balanceOf(wallet_address).call()
            balance_human = balance / 10**6
            print(f"   {agent_name}: {balance_human:,.6f} GLUE")

    owner_final = uvd_contract.functions.balanceOf(owner_account.address).call()
    owner_final_human = owner_final / 10**6
    print(f"   Owner (remaining): {owner_final_human:,.6f} GLUE")

if __name__ == "__main__":
    distribute_tokens()
