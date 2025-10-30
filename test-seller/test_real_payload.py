#!/usr/bin/env python3
"""
Test the ACTUAL payload from load_test.py against the facilitator
"""
import json
import requests

# This is what load_test.py sends wrapped in x402Payment
# test-seller extracts payment = body.get("x402Payment") and sends THAT
payment = {
    "x402Version": 1,
    "paymentPayload": {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base",
        "payload": {
            "signature": "0x7e571923b0d83257d4862a2f49077bb8f8e1e9fb14747eecf7cfbd142d7c0ccf6620191d112cc11e849a02a033e98fbfb8fc809bd4ec50a5ac737a487389699c",
            "authorization": {
                "from": "0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011",
                "to": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
                "value": "10000",
                "validAfter": "1761848677",
                "validBefore": "1761849337",
                "nonce": "0xc45aa97ff9cf7d269f35ae3b99cc255ddc90eba0390b78d14366cec3add8c93d"
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

print("Testing REAL payload from load_test.py...")
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
