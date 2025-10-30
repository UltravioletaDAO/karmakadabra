#!/usr/bin/env python3
"""
Test if the issue is validBefore < validAfter ordering
"""
import json
import requests

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

def test(desc, va, vb):
    payload = json.loads(json.dumps(base_payload))
    payload["paymentPayload"]["payload"]["authorization"]["validAfter"] = va
    payload["paymentPayload"]["payload"]["authorization"]["validBefore"] = vb

    response = requests.post(
        "https://facilitator.ultravioletadao.xyz/settle",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )

    print(f"{desc}:")
    print(f"  validAfter:  {va}")
    print(f"  validBefore: {vb}")
    print(f"  Status: {response.status_code}")
    if response.status_code != 200:
        print(f"  Error: {response.text}")
    print()

# Test 1: Original working values (validAfter < validBefore)
test("Original (working)", "1761839000", "1761840000")

# Test 2: Real failing validBefore with original validAfter
test("Real validBefore with original validAfter", "1761839000", "1761849337")

# Test 3: Real values from load_test (both changed)
test("Both real values", "1761848677", "1761849337")

# Test 4: Reversed (validBefore < validAfter) - should fail validation
test("Reversed (invalid)", "1761840000", "1761839000")

# Test 5: Same value
test("Same value", "1761840000", "1761840000")
