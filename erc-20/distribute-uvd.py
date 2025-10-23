#!/usr/bin/env python3
"""
UVD Token Distribution Script
Distributes 10,946 UVD to each agent wallet

Usage:
    python distribute-uvd.py
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
UVD_TOKEN_ADDRESS = "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425"
OWNER_PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# Amount to distribute: 10,946 UVD (with 6 decimals)
AMOUNT_PER_AGENT = 10_946 * 10**6  # 10,946.000000 UVD

# Agent wallet addresses (extracted from .env files)
AGENT_WALLETS = {
    "validator": None,  # Will be loaded from .env
    "karma-hello-agent": None,
    "abracadabra-agent": None,
    "client-agent": None,  # NEW: Generic buyer agent
}

# UVD Token ABI (minimal - only transfer function)
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
        "validator": "../validator/.env",
        "karma-hello-agent": "../karma-hello-agent/.env",
        "abracadabra-agent": "../abracadabra-agent/.env",
        "client-agent": "../client-agent/.env"
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

def distribute_uvd():
    """Main distribution function"""
    print("=" * 60)
    print("UVD Token Distribution to Agent Wallets")
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
    print(f"[BALANCE] Owner UVD Balance: {owner_balance_human:,.6f} UVD")
    print()

    # Load agent wallets
    print("[LOAD] Loading agent wallet addresses...")
    load_agent_wallets()
    print()

    # Calculate total needed
    active_agents = [addr for addr in AGENT_WALLETS.values() if addr]
    total_needed = len(active_agents) * AMOUNT_PER_AGENT
    total_needed_human = total_needed / 10**6

    print(f"[PLAN] Distribution Plan:")
    print(f"   Amount per agent: {AMOUNT_PER_AGENT / 10**6:,.6f} UVD")
    print(f"   Number of agents: {len(active_agents)}")
    print(f"   Total required: {total_needed_human:,.6f} UVD")
    print()

    if owner_balance < total_needed:
        print(f"[X] Insufficient balance! Need {total_needed_human:,.6f} UVD, have {owner_balance_human:,.6f} UVD")
        return

    # Confirm distribution
    print("[READY] Ready to distribute to:")
    for agent_name, wallet_address in AGENT_WALLETS.items():
        if wallet_address:
            current_balance = uvd_contract.functions.balanceOf(wallet_address).call()
            current_balance_human = current_balance / 10**6
            print(f"   - {agent_name}: {wallet_address}")
            print(f"     Current balance: {current_balance_human:,.6f} UVD")
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

        print(f"\n[SEND] Transferring {AMOUNT_PER_AGENT / 10**6:,.6f} UVD to {agent_name}...")
        print(f"   Address: {wallet_address}")

        try:
            # Build transaction
            nonce = w3.eth.get_transaction_count(owner_account.address)

            tx = uvd_contract.functions.transfer(
                wallet_address,
                AMOUNT_PER_AGENT
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
                print(f"   [BALANCE] New balance: {new_balance_human:,.6f} UVD")
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
            print(f"   {agent_name}: {balance_human:,.6f} UVD")

    owner_final = uvd_contract.functions.balanceOf(owner_account.address).call()
    owner_final_human = owner_final / 10**6
    print(f"   Owner (remaining): {owner_final_human:,.6f} UVD")

if __name__ == "__main__":
    distribute_uvd()
