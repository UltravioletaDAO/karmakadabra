#!/usr/bin/env python3
"""
Find the exact threshold for future timestamps
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

def test(desc, seconds_from_now):
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

    status = "OK" if response.status_code == 200 else "FAIL"
    print(f"{status} | {desc:30s} | validBefore={vb} ({seconds_from_now:+6d}s from now)")

    return response.status_code == 200

print("Testing validBefore timestamps...")
print("="*80)

# Test various offsets
test("Past (-1 hour)", -3600)
test("Past (-10 min)", -600)
test("Now", 0)
test("Future (+10 sec)", 10)
test("Future (+30 sec)", 30)
test("Future (+1 min)", 60)
test("Future (+2 min)", 120)
test("Future (+3 min)", 180)
test("Future (+5 min)", 300)
test("Future (+10 min)", 600)
test("Future (+15 min)", 900)
test("Future (+20 min)", 1200)
test("Future (+30 min)", 1800)
test("Future (+1 hour)", 3600)
test("Future (+2 hours)", 7200)

print("="*80)

# Binary search to find exact threshold
print("\nBinary search for exact threshold...")
low = 60  # Known to work
high = 300  # Testing

while low < high - 1:
    mid = (low + high) // 2
    if test(f"Testing {mid}s", mid):
        low = mid
    else:
        high = mid

print(f"\nThreshold found: validBefore can be at most ~{low} seconds in the future")
