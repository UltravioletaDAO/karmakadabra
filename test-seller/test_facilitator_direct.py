#!/usr/bin/env python3
"""
Direct test of facilitator /settle endpoint to debug the "Invalid request" error
"""
import json
import requests

# Sample payment payload matching the exact structure from load_test.py
payment = {
    "x402Version": 1,
    "paymentPayload": {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base",
        "payload": {
            "signature": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef11",
            "authorization": {
                "from": "0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011",
                "to": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
                "value": "10000",
                "validAfter": "1761839000",
                "validBefore": "1761840000",
                "nonce": "0xa0c6b1edb9fed5b5cd99626dadf0e60b56013f94839d4fdcfa0117cce1f74485"
            }
        }
    },
    "paymentRequirements": {
        "scheme": "exact",
        "network": "base",
        "maxAmountRequired": "10000",
        "resource": "https://test-seller.karmacadabra.ultravioletadao.xyz/hello",
        "description": "Hello World message",
        "mimeType": "application/json",
        "payTo": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
        "maxTimeoutSeconds": 60,
        "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "extra": {
            "name": "USD Coin",
            "version": "2"
        }
    }
}

print("Testing facilitator /settle endpoint...")
print(f"Payload structure: {list(payment.keys())}")
print(f"x402Version: {payment['x402Version']}")
print(f"paymentPayload keys: {list(payment['paymentPayload'].keys())}")
print(f"paymentPayload.network: {payment['paymentPayload']['network']}")
print(f"\nFull JSON:")
print(json.dumps(payment, indent=2))

print(f"\n\nCalling POST https://facilitator.ultravioletadao.xyz/settle...")
response = requests.post(
    "https://facilitator.ultravioletadao.xyz/settle",
    json=payment,
    headers={'Content-Type': 'application/json'},
    timeout=10
)

print(f"\nResponse status: {response.status_code}")
print(f"Response body: {response.text}")

if response.status_code == 200:
    data = response.json()
    print(f"\nParsed response:")
    print(json.dumps(data, indent=2))
else:
    print(f"\nERROR: Expected 200, got {response.status_code}")
