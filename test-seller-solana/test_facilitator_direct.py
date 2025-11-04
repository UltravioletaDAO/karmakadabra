#!/usr/bin/env python3
"""
Direct facilitator test - bypasses test-seller to debug faster
"""
import json
import requests
from load_test_solana_v2 import SolanaLoadTest, load_buyer_keypair_from_aws, SELLER_PUBKEY

# Configuration
FACILITATOR_URL = "https://facilitator.ultravioletadao.xyz"
SELLER = "Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PRICE_USDC = "10000"

print("Loading buyer keypair...")
buyer = load_buyer_keypair_from_aws()

print(f"Creating tester...")
tester = SolanaLoadTest(seller_pubkey=SELLER, buyer_keypair=buyer)

print(f"Creating transaction...")
transaction_b64 = tester.create_transfer_transaction()

print(f"\nTransaction created: {len(transaction_b64)} chars")
print(f"First 100 chars: {transaction_b64[:100]}")

# Build x402 payment payload
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
        "maxAmountRequired": PRICE_USDC,
        "resource": "https://test-seller-solana.karmacadabra.ultravioletadao.xyz/hello",
        "description": "Direct facilitator test",
        "mimeType": "application/json",
        "payTo": SELLER,
        "maxTimeoutSeconds": 60,
        "asset": USDC_MINT,
        "extra": {
            "name": "USD Coin",
            "decimals": 6
        }
    }
}

print(f"\nCalling facilitator /settle with 30s timeout...")
try:
    response = requests.post(
        f"{FACILITATOR_URL}/settle",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )

    print(f"\nStatus: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        print(f"\nSUCCESS!")
        print(f"Transaction: {data.get('transaction')}")
        print(f"Payer: {data.get('payer')}")
    else:
        print(f"\nFAILED")

except requests.exceptions.Timeout:
    print(f"\nTIMEOUT after 30s - facilitator hung")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
