#!/usr/bin/env python3
"""
Test /verify endpoint only (no settlement) to diagnose timeout
"""
import json
import requests
from load_test_solana_v4 import *

FACILITATOR_URL = "https://facilitator.ultravioletadao.xyz"
SELLER = "Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB"

print("Loading buyer...")
buyer = load_buyer_keypair_from_aws()

print("Creating tester...")
tester = SolanaLoadTestV4(seller_pubkey=SELLER, buyer_keypair=buyer)

print("Creating transaction...")
transaction_b64 = tester.create_transfer_transaction()

payload = {
    "x402Version": 1,
    "paymentPayload": {
        "x402Version": 1,
        "scheme": "exact",
        "network": "solana",
        "payload": {
            "transaction": transaction_b64
        }
    },
    "paymentRequirements": {
        "scheme": "exact",
        "network": "solana",
        "maxAmountRequired": "10000",
        "resource": "https://test.example.com/test",
        "description": "Test",
        "mimeType": "application/json",
        "payTo": SELLER,
        "maxTimeoutSeconds": 60,
        "asset": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "extra": {
            "name": "USD Coin",
            "decimals": 6
        }
    }
}

print(f"\nCalling /verify (validation only, no blockchain submission)...")
try:
    response = requests.post(
        f"{FACILITATOR_URL}/verify",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )

    print(f"\nStatus: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        if data.get("isValid"):
            print(f"\nSUCCESS! Transaction is valid")
            print(f"Payer: {data.get('payer')}")
        else:
            print(f"\nValidation failed: {data.get('invalidReason')}")
    else:
        print(f"\nFailed with HTTP {response.status_code}")

except requests.exceptions.Timeout:
    print(f"\nTIMEOUT - even /verify hung (should be instant)")
except Exception as e:
    print(f"\nERROR: {e}")
