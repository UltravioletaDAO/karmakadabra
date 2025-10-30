#!/usr/bin/env python3
"""
Find the EXACT future timestamp threshold with a fresh test
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

def test(seconds_from_now):
    now = int(time.time())
    vb = str(now + seconds_from_now)

    payload = json.loads(json.dumps(base_payload))
    payload["paymentPayload"]["payload"]["authorization"]["validBefore"] = vb

    response = requests.post(
        "https://facilitator.ultravioletadao.xyz/settle",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )

    return response.status_code == 200

# Test key values
tests = [0, 10, 30, 60, 90, 120, 180, 300, 600]

print("Testing validBefore timestamps...")
print("="*60)
for offset in tests:
    result = test(offset)
    status = "OK  " if result else "FAIL"
    print(f"{status} | +{offset:4d}s from now")

print("="*60)
