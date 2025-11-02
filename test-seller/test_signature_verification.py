#!/usr/bin/env python3
"""
Verify EIP-712 Signature Generation for USDC transferWithAuthorization

This script tests if we're generating valid signatures by:
1. Creating an EIP-712 signature
2. Recovering the signer address from the signature
3. Verifying it matches the expected address
"""

import os
import time
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

# Test configuration
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
SELLER_ADDRESS = "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19"
PRICE_USDC = "10000"  # $0.01

# Generate test account
private_key = "0x" + "a" * 64  # Test key
account = Account.from_key(private_key)

print("="*60)
print("EIP-712 Signature Verification Test")
print("="*60)
print(f"Test Account: {account.address}")
print(f"USDC Contract: {USDC_BASE_ADDRESS}")
print(f"Seller: {SELLER_ADDRESS}")
print()

# Create EIP-712 domain
domain = {
    "name": "USD Coin",
    "version": "2",
    "chainId": 8453,  # Base mainnet
    "verifyingContract": USDC_BASE_ADDRESS,
}

# Create message
nonce = "0x" + os.urandom(32).hex()
valid_after = int(time.time()) - 300
valid_before = int(time.time()) + 3600

message = {
    "from": account.address,
    "to": SELLER_ADDRESS,
    "value": int(PRICE_USDC),
    "validAfter": valid_after,
    "validBefore": valid_before,
    "nonce": nonce,
}

print("Message:")
for key, val in message.items():
    print(f"  {key}: {val} (type: {type(val).__name__})")
print()

# Build structured data
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

# Sign the message
print("Signing message...")
encoded = encode_typed_data(full_message=structured_data)
signed = account.sign_message(encoded)

print(f"Signature: 0x{signed.signature.hex()}")
print(f"Signature length: {len(signed.signature)} bytes")
print(f"v: {signed.v}")
print(f"r: 0x{signed.r.to_bytes(32, 'big').hex()}")
print(f"s: 0x{signed.s.to_bytes(32, 'big').hex()}")
print()

# Verify signature by recovering signer
print("Verifying signature...")
try:
    recovered = Account.recover_message(encoded, signature=signed.signature)
    print(f"Recovered address: {recovered}")
    print(f"Expected address:  {account.address}")
    print(f"✓ Signature valid: {recovered.lower() == account.address.lower()}")
except Exception as e:
    print(f"✗ Signature verification failed: {e}")

print()
print("="*60)
print("Authorization Object (as sent to facilitator):")
print("="*60)
authorization = {
    "from": account.address,
    "to": SELLER_ADDRESS,
    "value": PRICE_USDC,  # STRING
    "validAfter": str(valid_after),  # STRING
    "validBefore": str(valid_before),  # STRING
    "nonce": nonce,
}

import json
print(json.dumps(authorization, indent=2))
print()
print("⚠️  NOTE: Authorization uses STRING types but signature was")
print("   generated using INTEGER types. This mismatch may cause")
print("   signature validation failures in the USDC contract!")
