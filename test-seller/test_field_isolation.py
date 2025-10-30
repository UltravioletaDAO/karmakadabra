#!/usr/bin/env python3
"""
Systematically test each field to identify which one causes the 400 error
"""
import json
import requests

# Base payload that works (returns 200 OK with isValid: false)
working_payload = {
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

# Real values from failing payload
real_values = {
    "signature": "0x7e571923b0d83257d4862a2f49077bb8f8e1e9fb14747eecf7cfbd142d7c0ccf6620191d112cc11e849a02a033e98fbfb8fc809bd4ec50a5ac737a487389699c1b",
    "validAfter": "1761848677",
    "validBefore": "1761849337",
    "nonce": "0xc45aa97ff9cf7d269f35ae3b99cc255ddc90eba0390b78d14366cec3add8c93d"
}

def test_payload(description, payload):
    """Test a payload and return status code"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"{'='*60}")

    response = requests.post(
        "https://facilitator.ultravioletadao.xyz/settle",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {response.json()}")
        return True
    else:
        print(f"Error: {response.text}")
        return False

# Test 1: Baseline - working payload
print("\n" + "="*60)
print("BASELINE TEST - Working fake payload")
print("="*60)
test_payload("Baseline (fake signature)", working_payload)

# Test 2: Replace signature only
print("\n" + "="*60)
print("FIELD ISOLATION TESTS")
print("="*60)

test_payload_sig = json.loads(json.dumps(working_payload))
test_payload_sig["paymentPayload"]["payload"]["signature"] = real_values["signature"]
if not test_payload("Real signature only", test_payload_sig):
    print("[FAIL] FOUND IT! Real signature causes the 400 error")
    print(f"   Fake sig length: {len(working_payload['paymentPayload']['payload']['signature'])}")
    print(f"   Real sig length: {len(real_values['signature'])}")
    print(f"   Fake sig: {working_payload['paymentPayload']['payload']['signature']}")
    print(f"   Real sig: {real_values['signature']}")
else:
    print("[OK] Real signature works")

# Test 3: Replace validAfter only
test_payload_va = json.loads(json.dumps(working_payload))
test_payload_va["paymentPayload"]["payload"]["authorization"]["validAfter"] = real_values["validAfter"]
if not test_payload("Real validAfter only", test_payload_va):
    print("[FAIL] FOUND IT! Real validAfter causes the 400 error")
else:
    print("[OK] Real validAfter works")

# Test 4: Replace validBefore only
test_payload_vb = json.loads(json.dumps(working_payload))
test_payload_vb["paymentPayload"]["payload"]["authorization"]["validBefore"] = real_values["validBefore"]
if not test_payload("Real validBefore only", test_payload_vb):
    print("[FAIL] FOUND IT! Real validBefore causes the 400 error")
else:
    print("[OK] Real validBefore works")

# Test 5: Replace nonce only
test_payload_nonce = json.loads(json.dumps(working_payload))
test_payload_nonce["paymentPayload"]["payload"]["authorization"]["nonce"] = real_values["nonce"]
if not test_payload("Real nonce only", test_payload_nonce):
    print("[FAIL] FOUND IT! Real nonce causes the 400 error")
    print(f"   Fake nonce length: {len(working_payload['paymentPayload']['payload']['authorization']['nonce'])}")
    print(f"   Real nonce length: {len(real_values['nonce'])}")
    print(f"   Fake nonce: {working_payload['paymentPayload']['payload']['authorization']['nonce']}")
    print(f"   Real nonce: {real_values['nonce']}")
else:
    print("[OK] Real nonce works")

# Test 6: All real values combined
test_payload_all = json.loads(json.dumps(working_payload))
test_payload_all["paymentPayload"]["payload"]["signature"] = real_values["signature"]
test_payload_all["paymentPayload"]["payload"]["authorization"]["validAfter"] = real_values["validAfter"]
test_payload_all["paymentPayload"]["payload"]["authorization"]["validBefore"] = real_values["validBefore"]
test_payload_all["paymentPayload"]["payload"]["authorization"]["nonce"] = real_values["nonce"]
test_payload("All real values combined", test_payload_all)

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
