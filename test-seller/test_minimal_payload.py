#!/usr/bin/env python3
"""
Test with absolute minimal payload to isolate the issue
"""
import json
import requests
import time

# Test 1: EXACTLY like the fake payload that worked
payload_past = {
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

# Test 2: Change ONLY validBefore to NOW
now = int(time.time())
payload_now = json.loads(json.dumps(payload_past))
payload_now["paymentPayload"]["payload"]["authorization"]["validBefore"] = str(now)

# Test 3: Change ONLY validBefore to NOW + 1
payload_now_plus_1 = json.loads(json.dumps(payload_past))
payload_now_plus_1["paymentPayload"]["payload"]["authorization"]["validBefore"] = str(now + 1)

# Test 4: Change BOTH validAfter and validBefore to NOW - 10 and NOW
payload_both_recent = json.loads(json.dumps(payload_past))
payload_both_recent["paymentPayload"]["payload"]["authorization"]["validAfter"] = str(now - 10)
payload_both_recent["paymentPayload"]["payload"]["authorization"]["validBefore"] = str(now)

def test(name, payload):
    response = requests.post(
        "https://facilitator.ultravioletadao.xyz/settle",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )

    va = payload["paymentPayload"]["payload"]["authorization"]["validAfter"]
    vb = payload["paymentPayload"]["payload"]["authorization"]["validBefore"]

    status = "OK" if response.status_code == 200 else f"FAIL ({response.status_code})"
    print(f"{status:15s} | {name:30s} | vA={va} vB={vb}")

    return response.status_code == 200

print(f"Current time: {now}")
print("="*100)
test("1. Original (past timestamps)", payload_past)
test("2. validBefore = NOW", payload_now)
test("3. validBefore = NOW + 1", payload_now_plus_1)
test("4. Both recent (NOW-10 to NOW)", payload_both_recent)
print("="*100)
