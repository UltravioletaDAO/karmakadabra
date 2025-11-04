#!/usr/bin/env python3
"""
GLUE Token Distribution Script - Base Sepolia
Distributes 55,000 GLUE tokens to each of the 5 system agents on Base Sepolia.

Usage:
    python distribute_glue_base_sepolia.py
"""

import os
import sys
from web3 import Web3
import json
import boto3

# Configuration - Base Sepolia
RPC_URL = "https://base-sepolia.g.alchemy.com/v2/demo"
CHAIN_ID = 84532
GLUE_TOKEN_ADDRESS = "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425"

# Agent wallet addresses (funded wallets from deployment)
AGENT_WALLETS = {
    "validator": "0x1219eF9484BF7E40E6479141B32634623d37d507",
    "karma-hello": "0x2C3e071df446B25B821F59425152838ae4931E75",
    "abracadabra": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648",
    "skill-extractor": "0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9",
    "voice-extractor": "0x8E0Db88181668cDe24660d7eE8Da18a77DdBBF96"
}

# Amount to distribute per agent (55,000 GLUE with 6 decimals)
AGENT_AMOUNT = 55_000 * 10**6  # 55,000.000000 GLUE

# Get owner private key from AWS Secrets Manager
def get_owner_private_key():
    """Get erc-20 deployer private key from AWS Secrets Manager"""
    try:
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='karmacadabra')
        secrets = json.loads(response['SecretString'])
        if 'erc-20' in secrets:
            return secrets['erc-20']['private_key']
    except Exception as e:
        print(f"[!] Failed to get key from AWS: {e}")
        sys.exit(1)
    return None

# GLUE Token ABI (minimal - only transfer and balanceOf needed)
GLUE_ABI = [
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

def distribute_tokens():
    """Main token distribution function"""
    print("=" * 60)
    print("GLUE Token Distribution - Base Sepolia")
    print("=" * 60)
    print()

    # Get owner private key
    OWNER_PRIVATE_KEY = get_owner_private_key()
    if not OWNER_PRIVATE_KEY:
        print("[X] Error: Could not get private key from AWS Secrets Manager")
        return

    # Connect to Base Sepolia
    print(f"[*] Connecting to Base Sepolia...")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        print("[X] Failed to connect to Base Sepolia")
        return

    print(f"[+] Connected to Base Sepolia (Chain ID: {w3.eth.chain_id})")
    print()

    # Load owner account
    owner_account = w3.eth.account.from_key(OWNER_PRIVATE_KEY)
    print(f"[*] Owner Address: {owner_account.address}")

    # Load GLUE token contract
    glue_contract = w3.eth.contract(address=GLUE_TOKEN_ADDRESS, abi=GLUE_ABI)

    # Check owner balance
    owner_balance = glue_contract.functions.balanceOf(owner_account.address).call()
    owner_balance_human = owner_balance / 10**6
    print(f"[*] Owner GLUE Balance: {owner_balance_human:,.6f} GLUE")
    print()

    # Calculate total needed
    total_needed = AGENT_AMOUNT * len(AGENT_WALLETS)
    total_needed_human = total_needed / 10**6

    print(f"[*] Distribution Plan:")
    for agent_name in AGENT_WALLETS.keys():
        amount_human = AGENT_AMOUNT / 10**6
        print(f"   {agent_name}: {amount_human:,.6f} GLUE")
    print(f"   Number of agents: {len(AGENT_WALLETS)}")
    print(f"   Total required: {total_needed_human:,.6f} GLUE")
    print()

    if owner_balance < total_needed:
        print(f"[X] Insufficient balance! Need {total_needed_human:,.6f} GLUE, have {owner_balance_human:,.6f} GLUE")
        return

    # Show current balances
    print("[*] Current Agent Balances:")
    for agent_name, wallet_address in AGENT_WALLETS.items():
        current_balance = glue_contract.functions.balanceOf(wallet_address).call()
        current_balance_human = current_balance / 10**6
        print(f"   {agent_name}: {current_balance_human:,.6f} GLUE")
        print(f"   Address: {wallet_address}")
    print()

    print("[*] Starting distribution...")
    print("-" * 60)

    # Distribute to each agent
    successful_transfers = 0
    # Get initial nonce and manage it manually to avoid conflicts
    base_nonce = w3.eth.get_transaction_count(owner_account.address)
    current_nonce = base_nonce

    for agent_name, wallet_address in AGENT_WALLETS.items():
        print(f"\n[*] Transferring {AGENT_AMOUNT / 10**6:,.6f} GLUE to {agent_name}...")
        print(f"   Address: {wallet_address}")

        try:
            # Build transaction with manual nonce management
            tx = glue_contract.functions.transfer(
                wallet_address,
                AGENT_AMOUNT
            ).build_transaction({
                'from': owner_account.address,
                'nonce': current_nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': CHAIN_ID
            })

            # Sign transaction
            signed_tx = w3.eth.account.sign_transaction(tx, OWNER_PRIVATE_KEY)

            # Send transaction (use rawTransaction for newer web3.py versions)
            raw_tx = signed_tx.rawTransaction if hasattr(signed_tx, 'rawTransaction') else signed_tx.raw_transaction
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            print(f"   TX Hash: {tx_hash.hex()}")

            # Increment nonce for next transaction
            current_nonce += 1

            # Wait for receipt
            print(f"   [*] Waiting for confirmation...")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"   [+] SUCCESS!")
                print(f"   [+] https://sepolia.basescan.org/tx/{tx_hash.hex()}")

                # Check new balance
                new_balance = glue_contract.functions.balanceOf(wallet_address).call()
                new_balance_human = new_balance / 10**6
                print(f"   [+] New balance: {new_balance_human:,.6f} GLUE")
                successful_transfers += 1
            else:
                print(f"   [X] Transaction failed!")

        except Exception as e:
            print(f"   [X] Error: {e}")

    print()
    print("=" * 60)
    print(f"[+] Distribution Complete! ({successful_transfers}/{len(AGENT_WALLETS)} successful)")
    print("=" * 60)

    # Final balances
    print("\n[*] Final Balances:")
    for agent_name, wallet_address in AGENT_WALLETS.items():
        balance = glue_contract.functions.balanceOf(wallet_address).call()
        balance_human = balance / 10**6
        print(f"   {agent_name}: {balance_human:,.6f} GLUE")

    owner_final = glue_contract.functions.balanceOf(owner_account.address).call()
    owner_final_human = owner_final / 10**6
    print(f"   Owner (remaining): {owner_final_human:,.6f} GLUE")

if __name__ == "__main__":
    distribute_tokens()
