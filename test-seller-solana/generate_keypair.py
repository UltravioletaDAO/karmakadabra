#!/usr/bin/env python3
"""
Generate a Solana keypair for testing
Outputs JSON format compatible with load_test_solana.py
"""
import json
from solders.keypair import Keypair  # type: ignore


def generate_keypair(output_file: str = "buyer_keypair.json"):
    """Generate a new Solana keypair and save to file"""
    keypair = Keypair()

    # Convert to JSON array format (compatible with Solana CLI)
    keypair_bytes = list(bytes(keypair))

    with open(output_file, 'w') as f:
        json.dump(keypair_bytes, f)

    print("=" * 70)
    print("Solana Keypair Generated!")
    print("=" * 70)
    print(f"Public Key:  {keypair.pubkey()}")
    print(f"Saved to:    {output_file}")
    print()
    print("IMPORTANT:")
    print("  1. Fund this address with SOL for transaction fees")
    print("  2. Fund this address with USDC for payments")
    print()
    print("Get SOL:")
    print(f"  Visit https://faucet.solana.com and enter: {keypair.pubkey()}")
    print()
    print("Get USDC (mainnet):")
    print("  Transfer USDC to the generated address from another wallet")
    print()
    print("Security Warning:")
    print("  ⚠️  This is a test keypair - DO NOT use for production!")
    print("  ⚠️  Store buyer_keypair.json securely - it contains your private key")
    print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Solana keypair for testing")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="buyer_keypair.json",
        help="Output file path (default: buyer_keypair.json)"
    )

    args = parser.parse_args()
    generate_keypair(args.output)
