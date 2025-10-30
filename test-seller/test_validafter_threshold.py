#!/usr/bin/env python3
"""
Test validAfter threshold - how far in the past must it be?
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

def test(va_offset, vb_offset):
    now = int(time.time())
    va = now + va_offset
    vb = now + vb_offset

    payload = json.loads(json.dumps(base_payload))
    payload["paymentPayload"]["payload"]["authorization"]["validAfter"] = str(va)
    payload["paymentPayload"]["payload"]["authorization"]["validBefore"] = str(vb)

    response = requests.post(
        "https://facilitator.ultravioletadao.xyz/settle",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )

    return response.status_code == 200

now = int(time.time())

print("Testing validAfter threshold (with validBefore = NOW + 600)...")
print("="*70)

# Keep validBefore constant at NOW + 600, vary validAfter
vb_offset = 600

tests = [
    -3600,  # 1 hour ago
    -1800,  # 30 min ago
    -600,   # 10 min ago
    -300,   # 5 min ago
    -120,   # 2 min ago
    -60,    # 1 min ago
    -30,    # 30 sec ago
    -10,    # 10 sec ago
    -5,     # 5 sec ago
    0,      # NOW
    5,      # 5 sec future
]

for va_offset in tests:
    result = test(va_offset, vb_offset)
    status = "OK" if result else "FAIL"
    print(f"{status:6s} | validAfter = NOW {va_offset:+5d}s | validBefore = NOW +600s")

print("="*70)
