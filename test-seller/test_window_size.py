#!/usr/bin/env python3
"""
Test if the facilitator has a maximum window size limit
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

def test(name, va, vb):
    payload = json.loads(json.dumps(base_payload))
    payload["paymentPayload"]["payload"]["authorization"]["validAfter"] = str(va)
    payload["paymentPayload"]["payload"]["authorization"]["validBefore"] = str(vb)

    response = requests.post(
        "https://facilitator.ultravioletadao.xyz/settle",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )

    window = vb - va
    status = "OK" if response.status_code == 200 else f"FAIL ({response.status_code})"
    print(f"{status:15s} | {name:40s} | window={window:6d}s ({window/60:6.1f}min)")

    return response.status_code == 200

now = int(time.time())

print(f"Current time: {now}")
print("="*100)

# Test different window sizes, all centered around NOW
test("Window: 60s (NOW-30 to NOW+30)", now - 30, now + 30)
test("Window: 120s (NOW-60 to NOW+60)", now - 60, now + 60)
test("Window: 600s / 10min (NOW-300 to NOW+300)", now - 300, now + 300)
test("Window: 1200s / 20min (NOW-600 to NOW+600)", now - 600, now + 600)
test("Window: 3600s / 1hr (NOW-1800 to NOW+1800)", now - 1800, now + 1800)
test("Window: 7200s / 2hr (NOW-3600 to NOW+3600)", now - 3600, now + 3600)
test("Window: 86400s / 24hr (NOW-43200 to NOW+43200)", now - 43200, now + 43200)

print()
print("Now test with validAfter far in the past:")
print("="*100)

# Test with validAfter in the past (like the failing test)
test("Window: 3hr (3hr ago to NOW)", now - 10800, now)
test("Window: 3hr (3hr ago to NOW+10)", now - 10800, now + 10)
test("Window: 3hr (3hr ago to NOW+60)", now - 10800, now + 60)
test("Window: 3hr (3hr ago to NOW+600)", now - 10800, now + 600)

print("="*100)
