#!/usr/bin/env python3
"""
Setup Test Wallet Helper

Quick script to configure and verify a test wallet for production testing.
"""

import sys
import os
from web3 import Web3
from eth_account import Account
import json

RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
GLUE_TOKEN = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"


def check_wallet(address: str):
    """Check wallet balances"""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    print(f"\n🔍 Checking wallet: {address}")
    print("=" * 70)

    # AVAX balance
    avax_balance = w3.eth.get_balance(address) / 1e18
    print(f"AVAX: {avax_balance:.4f}")

    if avax_balance < 0.05:
        print(f"  ⚠️  Low AVAX! Get more from: https://faucet.avax.network/")
    else:
        print(f"  ✅ Sufficient AVAX for gas")

    # GLUE balance
    glue_abi = json.loads('[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')
    glue_contract = w3.eth.contract(address=GLUE_TOKEN, abi=glue_abi)
    glue_balance = glue_contract.functions.balanceOf(address).call() / 1e18

    print(f"GLUE: {glue_balance:.4f}")

    if glue_balance < 0.1:
        print(f"  ⚠️  Low GLUE! Need 0.1 for testing")
        print(f"  Contact admin for GLUE testnet tokens")
    else:
        print(f"  ✅ Sufficient GLUE for testing")

    print("=" * 70)

    # Summary
    ready = avax_balance >= 0.05 and glue_balance >= 0.1

    if ready:
        print(f"\n✅ Wallet is READY for testing!")
        return True
    else:
        print(f"\n⚠️  Wallet needs more funds")
        return False


def main():
    print("\n" + "=" * 70)
    print("🔑 TEST WALLET SETUP HELPER")
    print("=" * 70)

    # Check if key is already configured
    test_key = os.getenv('TEST_BUYER_KEY') or os.getenv('TEST_BUYER_PRIVATE_KEY')

    if test_key:
        print(f"\n✅ Found TEST_BUYER_KEY in environment")

        try:
            account = Account.from_key(test_key)
            address = account.address
            print(f"Address: {address}")

            ready = check_wallet(address)

            if ready:
                print(f"\n🚀 You can now run:")
                print(f"   python scripts/test_complete_flow.py")
            else:
                print(f"\n📝 Next steps:")
                print(f"   1. Get AVAX: https://faucet.avax.network/")
                print(f"   2. Get GLUE: Contact admin")
                print(f"   3. Run this script again to verify")

            return 0 if ready else 1

        except Exception as e:
            print(f"\n❌ Invalid private key: {e}")
            return 1

    else:
        print(f"\n❌ TEST_BUYER_KEY not configured")
        print(f"\n📝 Setup instructions:")
        print(f"\n   Windows PowerShell:")
        print(f'   $env:TEST_BUYER_KEY = "0x..."')
        print(f"\n   Linux/Mac:")
        print(f'   export TEST_BUYER_KEY=0x...')
        print(f"\n   Then run this script again to verify.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
