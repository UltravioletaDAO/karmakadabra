#!/usr/bin/env python3
"""
Test the new timestamps from load_test.py
"""
import json
import requests

# Real payload from the test output above
payment = {
    "x402Version": 1,
    "paymentPayload": {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base",
        "payload": {
            "signature": "0x80ca1da4c7ba8561ae501422e1ef9e44d28f4c1cfce0c63d902e5a2d80d33f9b73d666101f13b59c1c363e5dee4ec13b275e94aca6195a7b55dc94362a0c7e381c",
            "authorization": {
                "from": "0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011",
                "to": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
                "value": "10000",
                "validAfter": "1761849263",
                "validBefore": "1761849378",
                "nonce": "0x65dc8e9023e0a638aa855dcb7980e42aa290812440b10448e7b5229678c25611"
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

print("Testing new timestamp format from load_test.py...")
print(f"validAfter: {payment['paymentPayload']['payload']['authorization']['validAfter']}")
print(f"validBefore: {payment['paymentPayload']['payload']['authorization']['validBefore']}")

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
