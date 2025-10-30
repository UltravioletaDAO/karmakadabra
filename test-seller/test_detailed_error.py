#!/usr/bin/env python3
"""
Get detailed error message from facilitator
"""
import json
import requests
import time

base_payload = {
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
                "validAfter": "0",
                "validBefore": "0",
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

now = int(time.time())

# Test case that SHOULD work: validAfter in past, validBefore in future
payload = json.loads(json.dumps(base_payload))
payload["paymentPayload"]["payload"]["authorization"]["validAfter"] = str(now - 60)
payload["paymentPayload"]["payload"]["authorization"]["validBefore"] = str(now + 600)

print(f"Testing payment with:")
print(f"  validAfter:  {now - 60} (NOW - 60 = 60 seconds ago)")
print(f"  validBefore: {now + 600} (NOW + 600 = 600 seconds from now)")
print(f"  Current time: {now}")
print()

response = requests.post(
    "https://facilitator.ultravioletadao.xyz/settle",
    json=payload,
    headers={'Content-Type': 'application/json'},
    timeout=10
)

print(f"Response Status: {response.status_code}")
print(f"Response Headers: {dict(response.headers)}")
print(f"Response Body: {response.text}")

if response.status_code == 200:
    data = response.json()
    print(f"\nParsed JSON:")
    print(json.dumps(data, indent=2))
