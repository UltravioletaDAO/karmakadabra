#!/usr/bin/env python3
"""
Wallet Generator Script
Generates new Ethereum-compatible wallets for agents

Usage:
    python generate-wallet.py [agent_name] [--auto-save]

Examples:
    python generate-wallet.py client-agent
    python generate-wallet.py client-agent-2
    python generate-wallet.py my-custom-agent
    python generate-wallet.py client-agent --auto-save

Options:
    --auto-save    Automatically save to .env file without prompting
"""

import sys
import os
from web3 import Web3
from eth_account import Account

def generate_wallet(agent_name=None, auto_save=False):
    """Generate a new wallet and display credentials"""

    print("=" * 70)
    print("WALLET GENERATOR - Avalanche Fuji Compatible")
    print("=" * 70)
    print()

    # Enable unaudited HD wallet features (needed for account creation)
    Account.enable_unaudited_hdwallet_features()

    # Generate a new account
    print("[*] Generating new wallet...")
    account = Account.create()

    print("[OK] Wallet generated successfully!")
    print()

    # Display wallet information
    print("=" * 70)
    print("WALLET INFORMATION")
    print("=" * 70)
    print()

    if agent_name:
        print(f"[AGENT NAME]: {agent_name}")
        print()

    print("[PRIVATE KEY]:")
    print(account.key.hex())
    print()

    print("[PUBLIC ADDRESS]:")
    print(account.address)
    print()

    # Display additional information
    print("=" * 70)
    print("IMPORTANT SECURITY NOTES")
    print("=" * 70)
    print()
    print("[!] NEVER share your private key with anyone")
    print("[!] NEVER commit your private key to git")
    print("[!] Store your private key securely (password manager, vault, etc.)")
    print("[!] This wallet works on ALL EVM chains (Ethereum, Avalanche, etc.)")
    print()

    # Network information
    print("=" * 70)
    print("NETWORK INFORMATION")
    print("=" * 70)
    print()
    print("[NETWORK]: Avalanche Fuji Testnet")
    print("[CHAIN ID]: 43113")
    print("[RPC URL]: https://avalanche-fuji-c-chain-rpc.publicnode.com")
    print("[EXPLORER]: https://testnet.snowtrace.io/")
    print()
    print(f"[VIEW WALLET]: https://testnet.snowtrace.io/address/{account.address}")
    print()

    # Funding information
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    print("[1] Get testnet AVAX from faucet:")
    print("    https://faucet.avax.network/")
    print()
    print("[2] Add private key to .env file:")
    if agent_name:
        print(f"    Edit: {agent_name}/.env")
    print(f"    PRIVATE_KEY={account.key.hex()}")
    print()
    print("[3] Fund wallet with tokens:")
    print("    cd erc-20")
    print("    python distribute-token.py")
    print()

    # Save to file option
    if agent_name:
        env_dir = agent_name
        env_file = os.path.join(env_dir, ".env")
        env_example = os.path.join(env_dir, ".env.example")

        if os.path.exists(env_example):
            print("=" * 70)
            print("SAVE TO .ENV FILE")
            print("=" * 70)
            print()

            # Check if auto-save is enabled
            if auto_save:
                # Auto-save mode - don't prompt
                if os.path.exists(env_file):
                    print(f"[SKIP] {env_file} already exists (auto-save mode)")
                    print()
                    return account
                else:
                    print(f"[AUTO] Creating {env_file} (auto-save mode)")
                    print()
            else:
                # Interactive mode - ask user
                try:
                    if os.path.exists(env_file):
                        response = input(f"[!] {env_file} already exists. Overwrite? (yes/no): ")
                        if response.lower() not in ['yes', 'y']:
                            print("[SKIP] Not overwriting existing .env file")
                            print()
                            return account
                    else:
                        response = input(f"[?] Create {env_file} with this wallet? (yes/no): ")
                        if response.lower() not in ['yes', 'y']:
                            print("[SKIP] Not creating .env file")
                            print()
                            return account
                except (EOFError, KeyboardInterrupt):
                    # Handle non-interactive environment
                    print()
                    print("[AUTO] Non-interactive environment detected, auto-creating .env")
                    if os.path.exists(env_file):
                        print(f"[SKIP] {env_file} already exists")
                        print()
                        return account

            # Copy .env.example and update PRIVATE_KEY
            try:
                with open(env_example, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Replace placeholder private key
                content = content.replace(
                    'PRIVATE_KEY=0x0000000000000000000000000000000000000000000000000000000000000000',
                    f'PRIVATE_KEY={account.key.hex()}'
                )

                # Add derived address comment
                content = content.replace(
                    '# AGENT_WALLET_ADDRESS=',
                    f'AGENT_WALLET_ADDRESS={account.address}'
                )

                with open(env_file, 'w', encoding='utf-8') as f:
                    f.write(content)

                print(f"[OK] Created {env_file} with wallet credentials")
                print()

            except Exception as e:
                print(f"[X] Error creating .env file: {e}")
                print()

    print("=" * 70)
    print("[COMPLETE] Wallet generation complete!")
    print("=" * 70)
    print()

    return account


def main():
    """Main entry point"""

    # Parse command line arguments
    agent_name = None
    auto_save = False

    for arg in sys.argv[1:]:
        if arg == '--auto-save':
            auto_save = True
        else:
            agent_name = arg

    # Generate wallet
    account = generate_wallet(agent_name, auto_save)

    # Summary
    print()
    print("[SUMMARY]")
    print(f"Private Key: {account.key.hex()}")
    print(f"Address: {account.address}")
    print()


if __name__ == "__main__":
    main()
