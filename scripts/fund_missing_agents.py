#!/usr/bin/env python3
"""
Fund Voice-Extractor and Skill-Extractor with AVAX
Uses ERC-20 deployer wallet from AWS Secrets Manager
"""

import os
import sys
import json
import boto3
from web3 import Web3
from eth_account import Account

print("=" * 80)
print("FUND MISSING AGENTS WITH AVAX")
print("=" * 80)
print()

# Load environment
from dotenv import load_dotenv
load_dotenv()

RPC_URL = os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Get ERC-20 deployer wallet from AWS
print("[1/3] Fetching ERC-20 deployer wallet from AWS...")
try:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='karmacadabra')
    secrets = json.loads(response['SecretString'])

    deployer_pk = secrets['erc-20']['private_key']
    deployer_account = Account.from_key(deployer_pk)
    deployer_address = deployer_account.address

    deployer_balance = w3.eth.get_balance(deployer_address)
    deployer_avax = w3.from_wei(deployer_balance, 'ether')

    print(f"[OK] ERC-20 Deployer: {deployer_address}")
    print(f"     Balance: {deployer_avax:.4f} AVAX")

    if deployer_avax < 1.0:
        print(f"[FAIL] Insufficient balance! Need at least 1.0 AVAX to fund both agents")
        print(f"       Current balance: {deployer_avax:.4f} AVAX")
        print(f"       Get more AVAX from: https://faucet.avax.network/")
        sys.exit(1)
    print()

except Exception as e:
    print(f"[FAIL] AWS error: {e}")
    sys.exit(1)

# Agents to fund
agents_to_fund = {
    'voice-extractor': {
        'address': '0xDd63D5840090B98D9EB86f2c31974f9d6c270b17',
        'amount': 0.5
    },
    'skill-extractor': {
        'address': '0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9',
        'amount': 0.5
    }
}

print("[2/3] Checking agent balances...")
for agent_name, info in agents_to_fund.items():
    current_balance = w3.eth.get_balance(info['address'])
    current_avax = w3.from_wei(current_balance, 'ether')
    print(f"     {agent_name:20} {info['address']}")
    print(f"     Current: {current_avax:.4f} AVAX | Will fund: {info['amount']} AVAX")
print()

# Confirm
print("[3/3] Ready to fund agents...")
print(f"     Total AVAX to send: {sum(a['amount'] for a in agents_to_fund.values())} AVAX")
print(f"     Plus gas fees: ~0.001 AVAX per transaction")
print()

# Check for --confirm flag
if '--confirm' not in sys.argv:
    print("[DRY RUN] Use --confirm flag to execute")
    print("\nRun with: python fund_missing_agents.py --confirm")
    sys.exit(0)

print("[CONFIRMED] Proceeding with funding...")

print()
print("=" * 80)
print("FUNDING AGENTS")
print("=" * 80)
print()

# Fund each agent
for agent_name, info in agents_to_fund.items():
    print(f"Funding {agent_name}...")

    try:
        # Get nonce
        nonce = w3.eth.get_transaction_count(deployer_address)

        # Build transaction
        tx = {
            'nonce': nonce,
            'to': info['address'],
            'value': w3.to_wei(info['amount'], 'ether'),
            'gas': 21000,
            'gasPrice': w3.eth.gas_price,
            'chainId': 43113
        }

        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(tx, deployer_pk)

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"[OK] Transaction sent: {tx_hash.hex()}")
        print(f"     https://testnet.snowtrace.io/tx/{tx_hash.hex()}")

        # Wait for confirmation
        print(f"     Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            # Check new balance
            new_balance = w3.eth.get_balance(info['address'])
            new_avax = w3.from_wei(new_balance, 'ether')
            print(f"[OK] Confirmed! New balance: {new_avax:.4f} AVAX")
        else:
            print(f"[FAIL] Transaction failed!")

    except Exception as e:
        print(f"[FAIL] Error funding {agent_name}: {e}")

    print()

print("=" * 80)
print("FUNDING COMPLETE")
print("=" * 80)
print()

# Final balance check
print("Final agent balances:")
for agent_name, info in agents_to_fund.items():
    final_balance = w3.eth.get_balance(info['address'])
    final_avax = w3.from_wei(final_balance, 'ether')
    status = "[OK]" if final_avax > 0 else "[FAIL]"
    print(f"{status} {agent_name:20} {final_avax:.4f} AVAX")

print()
print("Next steps:")
print("1. Register these agents on-chain with correct domains")
print("2. Run system state test again: python test_system_state.py")
print()
