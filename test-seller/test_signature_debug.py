#!/usr/bin/env python3
"""
Debug script to test EIP-712 signature generation for USDC on Base
This will show us exactly what signature is being generated and whether it's valid
"""

import os
import time
import json
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_typed_data

# Base mainnet
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
RPC_URL = "https://mainnet.base.org"
SELLER_ADDRESS = "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19"  # test-seller
PRICE_USDC = "10000"  # 0.01 USDC

# Load test-buyer private key
def load_buyer_key():
    try:
        import boto3
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        response = secrets_client.get_secret_value(SecretId='karmacadabra-test-buyer')
        config = json.loads(response['SecretString'])
        return config['private_key']
    except Exception as e:
        print(f"[ERROR] Failed to load from AWS: {e}")
        return None

def create_eip712_domain():
    """Create EIP-712 domain for USDC on Base"""
    return {
        "name": "USD Coin",
        "version": "2",
        "chainId": 8453,  # Base mainnet
        "verifyingContract": USDC_BASE_ADDRESS,
    }

def sign_transfer_authorization(private_key):
    """Sign EIP-712 TransferWithAuthorization"""
    account = Account.from_key(private_key)

    # Generate random nonce
    nonce = "0x" + os.urandom(32).hex()

    # Timestamps (EIP-3009 spec)
    valid_after = int(time.time()) - 60  # 1 minute ago
    valid_before = int(time.time()) + 600  # 10 minutes from now

    domain = create_eip712_domain()

    message = {
        "from": account.address,
        "to": SELLER_ADDRESS,
        "value": int(PRICE_USDC),
        "validAfter": valid_after,
        "validBefore": valid_before,
        "nonce": nonce,
    }

    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": domain,
        "message": message,
    }

    print("\n=== EIP-712 STRUCTURED DATA ===")
    print(json.dumps(structured_data, indent=2))

    encoded = encode_typed_data(full_message=structured_data)
    signed = account.sign_message(encoded)

    print("\n=== SIGNATURE ===")
    print(f"  Full signature (hex): {signed.signature.hex()}")
    print(f"  v: {signed.v}")
    print(f"  r: {hex(signed.r)}")
    print(f"  s: {hex(signed.s)}")

    # Return authorization with timestamps as strings (as expected by facilitator)
    authorization = {
        "from": account.address,
        "to": SELLER_ADDRESS,
        "value": PRICE_USDC,
        "validAfter": str(valid_after),
        "validBefore": str(valid_before),
        "nonce": nonce,
    }

    return signed.signature.hex(), authorization

def main():
    print("=" * 70)
    print("EIP-712 SIGNATURE DEBUG FOR USDC ON BASE")
    print("=" * 70)

    # Load buyer
    key = load_buyer_key()
    if not key:
        print("[FAIL] No wallet found")
        return

    account = Account.from_key(key)
    print(f"\n[INFO] Buyer wallet: {account.address}")
    print(f"[INFO] Seller wallet: {SELLER_ADDRESS}")
    print(f"[INFO] Amount: {float(PRICE_USDC)/1000000:.2f} USDC")

    # Generate signature
    signature, authorization = sign_transfer_authorization(key)

    # Build full x402 payment payload
    payload = {
        "x402Version": 1,
        "paymentPayload": {
            "x402Version": 1,
            "scheme": "exact",
            "network": "base",
            "payload": {
                "signature": signature,
                "authorization": authorization,
            },
        },
        "paymentRequirements": {
            "scheme": "exact",
            "network": "base",
            "maxAmountRequired": PRICE_USDC,
            "resource": "https://test-seller.karmacadabra.ultravioletadao.xyz/hello",
            "description": "Hello World message",
            "mimeType": "application/json",
            "payTo": SELLER_ADDRESS,
            "maxTimeoutSeconds": 60,
            "asset": USDC_BASE_ADDRESS,
            "extra": {
                "name": "USD Coin",
                "version": "2"
            }
        }
    }

    print("\n=== FULL X402 PAYMENT PAYLOAD ===")
    print(json.dumps(payload, indent=2))

    # Save to file for reference
    with open("test-seller/debug_payment_payload.json", "w") as f:
        json.dump(payload, f, indent=2)

    print("\n[SUCCESS] Payload saved to test-seller/debug_payment_payload.json")
    print("\nYou can now test this payload by sending it to:")
    print("  POST https://facilitator.ultravioletadao.xyz/settle")
    print("=" * 70)

if __name__ == "__main__":
    main()
