#!/usr/bin/env python3
"""
Create USDC Associated Token Account for test-seller-solana
This must be done once before the seller can receive USDC payments
"""
import json
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from spl.token.instructions import get_associated_token_address, create_associated_token_account
from solana.transaction import Transaction
import boto3

# USDC mint on Solana mainnet
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

# Solana mainnet RPC
RPC_URL = "https://api.mainnet-beta.solana.com"


def load_seller_keypair():
    """Load seller keypair from AWS Secrets Manager"""
    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    response = secrets_client.get_secret_value(SecretId='karmacadabra-test-seller-solana')
    config = json.loads(response['SecretString'])

    keypair_data = config.get('keypair')
    if not keypair_data:
        raise ValueError("No 'keypair' field found in AWS secret")

    return Keypair.from_bytes(bytes(keypair_data))


def main():
    # Load seller keypair
    print("Loading seller keypair from AWS Secrets Manager...")
    seller = load_seller_keypair()
    print(f"Seller pubkey: {seller.pubkey()}")

    # Calculate ATA address
    ata_address = get_associated_token_address(seller.pubkey(), USDC_MINT)
    print(f"USDC ATA address: {ata_address}")

    # Connect to Solana
    client = Client(RPC_URL)

    # Check if ATA already exists
    response = client.get_account_info(ata_address)
    if response.value is not None:
        print(f"✓ ATA already exists!")
        print(f"  Address: {ata_address}")
        return

    print(f"ATA does not exist. Creating it...")

    # Create ATA instruction
    # Note: The payer (seller) will pay for the ATA creation (~0.002 SOL)
    ix = create_associated_token_account(
        payer=seller.pubkey(),
        owner=seller.pubkey(),
        mint=USDC_MINT
    )

    # Get recent blockhash
    recent_blockhash = client.get_latest_blockhash().value.blockhash

    # Create transaction
    tx = Transaction()
    tx.add(ix)
    tx.recent_blockhash = recent_blockhash
    tx.fee_payer = seller.pubkey()

    # Sign transaction
    tx.sign(seller)

    # Send transaction
    print(f"Sending transaction...")
    result = client.send_raw_transaction(tx.serialize())
    print(f"Transaction signature: {result.value}")

    print(f"\n✓ Successfully created USDC ATA!")
    print(f"  Address: {ata_address}")
    print(f"  Owner: {seller.pubkey()}")
    print(f"  View on Solscan: https://solscan.io/account/{ata_address}")


if __name__ == "__main__":
    main()
