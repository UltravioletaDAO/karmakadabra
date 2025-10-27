#!/usr/bin/env python3
"""
Setup User Agent - Quick setup script for testing user agents

This script:
1. Generates a new wallet for the user agent
2. Requests AVAX from faucet (manual step with instructions)
3. Distributes GLUE tokens from ERC-20 deployer
4. Updates .env file with wallet credentials
5. Verifies setup is complete

Usage:
    python scripts/setup_user_agent.py cyberpaisa
    python scripts/setup_user_agent.py --username cyberpaisa --glue 1000
"""

import argparse
import sys
from pathlib import Path
import os
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from eth_account import Account
from web3 import Web3
from dotenv import load_dotenv, set_key
import time


def generate_wallet():
    """Generate new Ethereum wallet"""
    print("🔑 Generating new wallet...")
    account = Account.create()
    print(f"   ✅ Address: {account.address}")
    print(f"   🔐 Private Key: {account.key.hex()}")
    return {
        "address": account.address,
        "private_key": account.key.hex()
    }


def update_env_file(env_path: Path, wallet: dict):
    """Update .env file with wallet credentials"""
    print(f"\n📝 Updating {env_path}...")

    if not env_path.exists():
        print(f"   ❌ ERROR: {env_path} not found")
        return False

    try:
        # Update PRIVATE_KEY
        set_key(str(env_path), "PRIVATE_KEY", wallet["private_key"])
        print(f"   ✅ Updated PRIVATE_KEY")

        # Add wallet address as comment for reference
        with open(env_path, 'a') as f:
            f.write(f"\n# Wallet Address: {wallet['address']}\n")

        return True

    except Exception as e:
        print(f"   ❌ ERROR: Failed to update .env: {e}")
        return False


def check_balance(address: str, rpc_url: str, token_address: str) -> tuple:
    """Check AVAX and GLUE balances"""
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Check AVAX balance
        avax_balance = w3.eth.get_balance(address)
        avax_balance_ether = w3.from_wei(avax_balance, 'ether')

        # Check GLUE balance
        glue_abi = [
            {
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        glue_contract = w3.eth.contract(address=token_address, abi=glue_abi)
        glue_balance = glue_contract.functions.balanceOf(address).call()
        decimals = glue_contract.functions.decimals().call()
        glue_balance_decimal = Decimal(glue_balance) / Decimal(10 ** decimals)

        return float(avax_balance_ether), float(glue_balance_decimal)

    except Exception as e:
        print(f"   ⚠️  Could not check balance: {e}")
        return 0.0, 0.0


def distribute_glue(recipient: str, amount: int, deployer_key: str, rpc_url: str, token_address: str) -> bool:
    """Distribute GLUE tokens from deployer wallet"""
    print(f"\n💰 Distributing {amount} GLUE to {recipient[:10]}...{recipient[-8:]}...")

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Load deployer account
        deployer_account = Account.from_key(deployer_key)

        # GLUE token contract
        glue_abi = [
            {
                "inputs": [
                    {"name": "recipient", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        glue_contract = w3.eth.contract(address=token_address, abi=glue_abi)
        decimals = glue_contract.functions.decimals().call()

        # Build transfer transaction
        amount_wei = amount * (10 ** decimals)

        tx = glue_contract.functions.transfer(recipient, amount_wei).build_transaction({
            'from': deployer_account.address,
            'nonce': w3.eth.get_transaction_count(deployer_account.address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        # Sign and send
        signed_tx = deployer_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"   📤 Transaction sent: {tx_hash.hex()}")
        print(f"   ⏳ Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status == 1:
            print(f"   ✅ Transfer successful!")
            print(f"   🌐 View on Snowtrace: https://testnet.snowtrace.io/tx/{tx_hash.hex()}")
            return True
        else:
            print(f"   ❌ Transaction failed")
            return False

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Setup user agent for testing")
    parser.add_argument("username", help="Username of the agent (e.g., cyberpaisa)")
    parser.add_argument("--glue", type=int, default=1000, help="Amount of GLUE to distribute (default: 1000)")
    parser.add_argument("--skip-wallet", action="store_true", help="Skip wallet generation (use existing)")
    parser.add_argument("--skip-glue", action="store_true", help="Skip GLUE distribution")

    args = parser.parse_args()

    print("=" * 80)
    print(f"🚀 SETUP USER AGENT: {args.username}")
    print("=" * 80)

    # Locate user agent directory
    agent_dir = project_root / "client-agents" / args.username
    env_file = agent_dir / ".env"

    if not agent_dir.exists():
        print(f"❌ ERROR: Agent directory not found: {agent_dir}")
        print(f"   Available agents:")
        for d in (project_root / "client-agents").iterdir():
            if d.is_dir() and d.name != "template":
                print(f"      - {d.name}")
        return 1

    print(f"📁 Agent directory: {agent_dir}")

    # Step 1: Generate or use existing wallet
    if args.skip_wallet:
        print("\n⏭️  Skipping wallet generation (--skip-wallet)")
        load_dotenv(env_file)
        private_key = os.getenv("PRIVATE_KEY")
        if not private_key:
            print("   ❌ ERROR: No PRIVATE_KEY found in .env and --skip-wallet specified")
            return 1
        wallet = {
            "private_key": private_key,
            "address": Account.from_key(private_key).address
        }
        print(f"   ✅ Using existing wallet: {wallet['address']}")
    else:
        wallet = generate_wallet()
        update_env_file(env_file, wallet)

    # Step 2: Request AVAX from faucet (manual)
    print("\n⛽ Step 2: Get AVAX testnet tokens")
    print("-" * 80)
    print(f"   1. Visit: https://faucet.avax.network/")
    print(f"   2. Enter address: {wallet['address']}")
    print(f"   3. Complete captcha and request tokens")
    print(f"   4. Wait ~30 seconds for confirmation")

    input("\n   Press ENTER when you've completed the faucet request...")

    # Check AVAX balance
    load_dotenv(project_root / ".env")  # Load main .env for contract addresses
    rpc_url = os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
    token_address = os.getenv("GLUE_TOKEN_ADDRESS", "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743")

    print("\n📊 Checking balances...")
    avax_balance, glue_balance = check_balance(wallet['address'], rpc_url, token_address)

    print(f"   💎 AVAX: {avax_balance:.4f}")
    print(f"   💎 GLUE: {glue_balance:.6f}")

    if avax_balance < 0.1:
        print(f"   ⚠️  WARNING: Low AVAX balance. May not be enough for gas fees.")
        print(f"   Continuing anyway...")

    # Step 3: Distribute GLUE
    if args.skip_glue:
        print("\n⏭️  Skipping GLUE distribution (--skip-glue)")
    else:
        print(f"\n💰 Step 3: Distribute {args.glue} GLUE tokens")
        print("-" * 80)

        # Load ERC-20 deployer key
        erc20_env = project_root / "erc-20" / ".env"
        if not erc20_env.exists():
            print(f"   ❌ ERROR: ERC-20 .env not found: {erc20_env}")
            print(f"   Run manually: cd erc-20 && python distribute-token.py")
            return 1

        load_dotenv(erc20_env)
        deployer_key = os.getenv("PRIVATE_KEY")

        if not deployer_key:
            print(f"   ❌ ERROR: No PRIVATE_KEY in erc-20/.env")
            return 1

        success = distribute_glue(wallet['address'], args.glue, deployer_key, rpc_url, token_address)

        if not success:
            print(f"   ⚠️  GLUE distribution failed. Try manually:")
            print(f"   cd erc-20 && python distribute-token.py")

    # Step 4: Verify setup
    print("\n✅ Step 4: Verify Setup")
    print("-" * 80)

    time.sleep(3)  # Wait for potential transactions to confirm

    avax_balance, glue_balance = check_balance(wallet['address'], rpc_url, token_address)

    print(f"   📊 Final Balances:")
    print(f"      💎 AVAX: {avax_balance:.4f}")
    print(f"      💎 GLUE: {glue_balance:.6f}")

    success = True
    if avax_balance < 0.1:
        print(f"   ⚠️  Low AVAX - may not have enough for gas")
        success = False

    if glue_balance < 1.0:
        print(f"   ⚠️  Low GLUE - may not have enough for purchases")
        success = False

    if success:
        print("\n" + "=" * 80)
        print("✅ SETUP COMPLETE!")
        print("=" * 80)
        print(f"\n🎯 Next steps:")
        print(f"   1. Test the agent:")
        print(f"      python tests/test_cyberpaisa_client.py")
        print(f"")
        print(f"   2. Run the agent server:")
        print(f"      cd client-agents/{args.username}")
        print(f"      python main.py")
        print(f"")
        print(f"   3. Register on-chain:")
        print(f"      python scripts/register_missing_agents.py --agent {args.username}")
        print(f"")
        print(f"   4. View wallet on Snowtrace:")
        print(f"      https://testnet.snowtrace.io/address/{wallet['address']}")
    else:
        print("\n" + "=" * 80)
        print("⚠️  SETUP INCOMPLETE")
        print("=" * 80)
        print("\nPlease resolve the warnings above before testing.")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
