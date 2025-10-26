#!/usr/bin/env python3
"""
Fund all Karmacadabra wallets with AVAX for gas fees
Uses ERC-20 deployer wallet from AWS Secrets Manager (under 'erc-20' key)

This script is fully idempotent - it checks balances first and only funds wallets below threshold.
"""

import os
import sys
import json
import boto3
from web3 import Web3
from eth_account import Account

print("=" * 80)
print("FUND KARMACADABRA WALLETS WITH AVAX")
print("=" * 80)
print()

# Load environment
from dotenv import load_dotenv
load_dotenv()

RPC_URL = os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Minimum balance threshold - only fund if below this
MIN_AVAX_THRESHOLD = 0.05

# All wallets to fund (addresses from AWS Secrets Manager or known deployments)
# Amount is how much to top up to when below threshold
WALLETS_TO_FUND = {
    'facilitator': {
        'secret_key': 'karmacadabra-facilitator',
        'amount': 1.0,  # Facilitator needs more for settling many transactions
        'description': 'x402 payment facilitator hot wallet'
    },
    'validator-agent': {
        'secret_key': 'karmacadabra-validator',
        'amount': 0.10,
        'description': 'Validator agent for data quality verification'
    },
    'karma-hello-agent': {
        'secret_key': 'karmacadabra-karma-hello',
        'amount': 0.10,
        'description': 'Karma-Hello seller/buyer agent'
    },
    'abracadabra-agent': {
        'secret_key': 'karmacadabra-abracadabra',
        'amount': 0.10,
        'description': 'Abracadabra seller/buyer agent'
    },
    'skill-extractor-agent': {
        'secret_key': 'karmacadabra-skill-extractor',
        'amount': 0.10,
        'description': 'Skill-Extractor seller/buyer agent'
    },
    'voice-extractor-agent': {
        'secret_key': 'karmacadabra-voice-extractor',
        'amount': 0.10,
        'description': 'Voice-Extractor seller/buyer agent'
    },
    'client-agent': {
        'secret_key': 'karmacadabra-client',
        'amount': 0.10,
        'description': 'Demo client agent for testing'
    }
}

# Get ERC-20 deployer wallet from AWS
print("[1/4] Fetching ERC-20 deployer wallet from AWS Secrets Manager...")
try:
    client = boto3.client('secretsmanager', region_name='us-east-1')

    # Get deployer wallet from main karmacadabra secret (under erc-20 key)
    response = client.get_secret_value(SecretId='karmacadabra')
    secrets = json.loads(response['SecretString'])

    if 'erc-20' not in secrets:
        print("[FAIL] ERC-20 deployer wallet not found in AWS Secrets Manager")
        print("       Secret 'karmacadabra' should have 'erc-20' key with private_key")
        sys.exit(1)

    deployer_pk = secrets['erc-20']['private_key']
    deployer_account = Account.from_key(deployer_pk)
    deployer_address = deployer_account.address

    deployer_balance = w3.eth.get_balance(deployer_address)
    deployer_avax = w3.from_wei(deployer_balance, 'ether')

    print(f"[OK] ERC-20 Deployer: {deployer_address}")
    print(f"     Balance: {deployer_avax:.4f} AVAX")
    print()

except Exception as e:
    print(f"[FAIL] AWS error: {e}")
    sys.exit(1)

# Get wallet addresses from AWS Secrets Manager
print("[2/4] Fetching wallet addresses from AWS Secrets Manager...")
wallet_addresses = {}

for wallet_name, info in WALLETS_TO_FUND.items():
    try:
        response = client.get_secret_value(SecretId=info['secret_key'])
        wallet_secret = json.loads(response['SecretString'])

        # Get address from secret (either stored directly or derive from private_key)
        if 'address' in wallet_secret:
            address = wallet_secret['address']
        elif 'private_key' in wallet_secret:
            account = Account.from_key(wallet_secret['private_key'])
            address = account.address
        else:
            print(f"  [WARN] {wallet_name}: No address or private_key found in secret")
            continue

        wallet_addresses[wallet_name] = {
            'address': address,
            'amount': info['amount'],
            'description': info['description']
        }
        print(f"  [OK] {wallet_name:25} {address}")

    except client.exceptions.ResourceNotFoundException:
        print(f"  [SKIP] {wallet_name:25} Secret not found: {info['secret_key']}")
    except Exception as e:
        print(f"  [WARN] {wallet_name:25} Error: {e}")

print()

if not wallet_addresses:
    print("[FAIL] No wallets found to fund!")
    sys.exit(1)

# Check balances and determine which wallets need funding
print("[3/4] Checking wallet balances...")

wallets_needing_funding = {}
wallets_already_funded = {}

for wallet_name, info in wallet_addresses.items():
    current_balance = w3.eth.get_balance(info['address'])
    current_avax = w3.from_wei(current_balance, 'ether')

    if current_avax < MIN_AVAX_THRESHOLD:
        wallets_needing_funding[wallet_name] = info
        print(f"  [FUND] {wallet_name:25} {current_avax:.4f} AVAX - NEEDS FUNDING (top up to {info['amount']:.2f})")
    else:
        wallets_already_funded[wallet_name] = current_avax
        print(f"  [OK]   {wallet_name:25} {current_avax:.4f} AVAX - Already funded")

print()

# If no wallets need funding, exit
if not wallets_needing_funding:
    print("[OK] All wallets already have sufficient AVAX!")
    print(f"     Minimum threshold: {MIN_AVAX_THRESHOLD} AVAX")
    print()
    for wallet_name, balance in wallets_already_funded.items():
        print(f"     {wallet_name}: {balance:.4f} AVAX")
    print()
    print("[OK] Nothing to do. All wallets are funded!")
    sys.exit(0)

# Calculate total needed
total_to_send = sum(w['amount'] for w in wallets_needing_funding.values())
gas_buffer = len(wallets_needing_funding) * 0.001  # ~0.001 AVAX per tx
total_needed = total_to_send + gas_buffer

if deployer_avax < total_needed:
    print(f"[FAIL] Insufficient balance in deployer wallet!")
    print(f"       Need: {total_needed:.4f} AVAX")
    print(f"       Have: {deployer_avax:.4f} AVAX")
    print(f"       Short: {total_needed - deployer_avax:.4f} AVAX")
    print()
    print(f"       Get more AVAX from: https://faucet.avax.network/")
    print(f"       Send to deployer: {deployer_address}")
    sys.exit(1)

# Summary
print("[4/4] Ready to fund wallets...")
print(f"     Wallets to fund: {len(wallets_needing_funding)}")
print(f"     Total AVAX to send: {total_to_send:.2f} AVAX")
print(f"     Plus gas fees: ~{gas_buffer:.3f} AVAX")
print(f"     Total needed: {total_needed:.4f} AVAX")
print(f"     Deployer balance: {deployer_avax:.4f} AVAX")
print()

# Check for --confirm flag
if '--confirm' not in sys.argv:
    print("[DRY RUN] Use --confirm flag to execute")
    print("\nRun with: python scripts/fund-wallets.py --confirm")
    sys.exit(0)

print("[CONFIRMED] Proceeding with funding...")

print()
print("=" * 80)
print("FUNDING WALLETS")
print("=" * 80)
print()

# Fund each wallet
successful_transfers = []
failed_transfers = []

for wallet_name, info in wallets_needing_funding.items():
    print(f"Funding {wallet_name}...")
    print(f"  Address: {info['address']}")
    print(f"  Amount: {info['amount']:.2f} AVAX")

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

        print(f"  [TX] {tx_hash.hex()}")
        print(f"       https://testnet.snowtrace.io/tx/{tx_hash.hex()}")

        # Wait for confirmation
        print(f"  [WAIT] Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] == 1:
            # Check new balance
            new_balance = w3.eth.get_balance(info['address'])
            new_avax = w3.from_wei(new_balance, 'ether')
            print(f"  [OK] Confirmed! New balance: {new_avax:.4f} AVAX")
            successful_transfers.append(wallet_name)
        else:
            print(f"  [FAIL] Transaction failed!")
            failed_transfers.append(wallet_name)

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        failed_transfers.append(wallet_name)

    print()

print("=" * 80)
print("FUNDING COMPLETE")
print("=" * 80)
print()

# Summary
print("Summary:")
print(f"  [OK]   Successful: {len(successful_transfers)}/{len(wallets_needing_funding)}")
print(f"  [FAIL] Failed: {len(failed_transfers)}/{len(wallets_needing_funding)}")
print()

# Final balance check
print("Final wallet balances:")
for wallet_name, info in wallet_addresses.items():
    final_balance = w3.eth.get_balance(info['address'])
    final_avax = w3.from_wei(final_balance, 'ether')

    if final_avax >= MIN_AVAX_THRESHOLD:
        status = "[OK]  "
    else:
        status = "[FAIL]"

    print(f"  {status} {wallet_name:25} {final_avax:.4f} AVAX")

print()

# Final deployer balance
final_deployer = w3.eth.get_balance(deployer_address)
final_deployer_avax = w3.from_wei(final_deployer, 'ether')
print(f"Deployer balance after funding: {final_deployer_avax:.4f} AVAX")
print()

if failed_transfers:
    print("[WARN] Some transfers failed. Review errors above.")
    sys.exit(1)

print("[SUCCESS] All wallets funded successfully!")
print()
print("Next steps:")
print("1. Verify agents can make transactions")
print("2. Run system health check: python scripts/check_system_ready.py")
print()
