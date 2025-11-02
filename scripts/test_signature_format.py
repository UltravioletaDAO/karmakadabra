#!/usr/bin/env python3
"""
Phase 2: Signature Format Verification
Tests if Python's eth_account generates signatures with correct v-value normalization
"""

from eth_account import Account
from eth_account.messages import encode_structured_data
from eth_utils import keccak
import os

print("=" * 80)
print("SIGNATURE FORMAT VERIFICATION - Phase 2")
print("=" * 80)

# Use EXACT domain from network.rs (lines 133-145)
domain_data = {
    "name": "USD Coin",
    "version": "2",
    "chainId": 8453,  # Base mainnet
    "verifyingContract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
}

# Test message data
message_data = {
    "from": "0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011",  # Test buyer
    "to": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",    # Test seller
    "value": 10000,  # 0.01 USDC (6 decimals)
    "validAfter": 0,
    "validBefore": 2000000000,
    "nonce": "0x" + "00" * 32  # Deterministic nonce for testing
}

types = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"}
    ],
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"}
    ]
}

structured_data = {
    "types": types,
    "primaryType": "TransferWithAuthorization",
    "domain": domain_data,
    "message": message_data
}

# Test with deterministic private key (FOR TESTING ONLY)
test_private_key = "0x" + "01" * 32
account = Account.from_key(test_private_key)

print(f"\nTest Account Address: {account.address}")
print(f"Domain: {domain_data}")
print(f"Message: from={message_data['from']}, to={message_data['to']}, value={message_data['value']}")

# Generate signature
encoded = encode_structured_data(structured_data)
signature = account.sign_message(encoded)

print("\n" + "=" * 80)
print("SIGNATURE ANALYSIS")
print("=" * 80)

print(f"\nv: {signature.v} (should be 27 or 28 for Solidity)")
print(f"r: 0x{signature.r.to_bytes(32, 'big').hex()}")
print(f"s: 0x{signature.s.to_bytes(32, 'big').hex()}")
print(f"\nFull signature (hex): 0x{signature.signature.hex()}")
print(f"Signature length: {len(signature.signature)} bytes (should be 65)")

# Calculate domain separator for comparison
domain_separator = keccak(
    encode_structured_data({
        "types": {"EIP712Domain": types["EIP712Domain"]},
        "primaryType": "EIP712Domain",
        "domain": domain_data,
        "message": {}
    }).body
)
print(f"\nDomain Separator: 0x{domain_separator.hex()}")

# Check v value
print("\n" + "=" * 80)
print("V-VALUE DIAGNOSIS")
print("=" * 80)

if signature.v < 27:
    print(f"\n❌ ISSUE FOUND: v={signature.v}")
    print(f"   Solidity expects v=27 or v=28")
    print(f"   Needs normalization: v_normalized = {signature.v + 27}")
    print("\n   FIX REQUIRED: Add v normalization in load_test.py")

    # Show how to fix
    print("\n" + "=" * 80)
    print("RECOMMENDED FIX")
    print("=" * 80)
    print("""
In test-seller/load_test.py, change signature generation to:

    signature = buyer_account.sign_message(encoded_message)

    # FIX: Normalize v value for Solidity compatibility
    v = signature.v if signature.v >= 27 else signature.v + 27

    authorization = {
        "v": v,  # <-- Use normalized value
        "r": "0x" + signature.r.to_bytes(32, 'big').hex(),
        "s": "0x" + signature.s.to_bytes(32, 'big').hex(),
        # ...
    }
""")

elif signature.v in [27, 28]:
    print(f"\n✅ V-VALUE IS CORRECT: v={signature.v}")
    print("   Signature format matches Solidity expectations")
    print("\n   If payments still fail, the issue is NOT v-value normalization")
    print("   Check:")
    print("   1. Domain separator matches on-chain contract")
    print("   2. Message hash calculation")
    print("   3. Facilitator signature parsing logic")

else:
    print(f"\n⚠️ UNEXPECTED V-VALUE: v={signature.v}")
    print("   Expected v ∈ {{0, 1, 27, 28}}")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)

if signature.v < 27:
    print("\n1. Apply v normalization fix in load_test.py")
    print("2. Run: python test-seller/load_test.py --num-requests 1")
    print("3. Check facilitator logs for success")
else:
    print("\n1. Verify domain separator with on-chain contract:")
    print("   cast call 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \\")
    print("     'DOMAIN_SEPARATOR()(bytes32)' \\")
    print("     --rpc-url https://mainnet.base.org")
    print(f"\n   Expected: 0x{domain_separator.hex()}")
    print("\n2. If domain separator matches, issue is in facilitator parsing")

print("\n" + "=" * 80)
