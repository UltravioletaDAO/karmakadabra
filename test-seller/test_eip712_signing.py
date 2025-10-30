#!/usr/bin/env python3
"""
Test EIP-712 signing to ensure signature format is correct
"""
import time
import os
from eth_account import Account
from eth_account.messages import encode_typed_data
import sys
sys.path.insert(0, '/z/ultravioleta/dao/karmacadabra')

from shared.secrets_manager import get_private_key

# Load test-buyer credentials
private_key = get_private_key('test-buyer')
account = Account.from_key(private_key)

SELLER_ADDRESS = '0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19'
USDC_ADDRESS = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'

# Create timestamp
now = int(time.time())
valid_after = now + 1
valid_before = now + 600
nonce = '0x' + os.urandom(32).hex()

print(f'Buyer address: {account.address}')
print(f'Now: {now}')
print(f'validAfter: {valid_after} (NOW + 1)')
print(f'validBefore: {valid_before} (NOW + 600)')
print(f'Nonce: {nonce}')

# Create EIP-712 domain
domain = {
    'name': 'USD Coin',
    'version': '2',
    'chainId': 8453,  # Base mainnet
    'verifyingContract': USDC_ADDRESS
}

# Create message
message = {
    'from': account.address,
    'to': SELLER_ADDRESS,
    'value': 10000,
    'validAfter': valid_after,
    'validBefore': valid_before,
    'nonce': bytes.fromhex(nonce[2:])
}

# Create typed data
typed_data = {
    'types': {
        'EIP712Domain': [
            {'name': 'name', 'type': 'string'},
            {'name': 'version', 'type': 'string'},
            {'name': 'chainId', 'type': 'uint256'},
            {'name': 'verifyingContract', 'type': 'address'}
        ],
        'TransferWithAuthorization': [
            {'name': 'from', 'type': 'address'},
            {'name': 'to', 'type': 'address'},
            {'name': 'value', 'type': 'uint256'},
            {'name': 'validAfter', 'type': 'uint256'},
            {'name': 'validBefore', 'type': 'uint256'},
            {'name': 'nonce', 'type': 'bytes32'}
        ]
    },
    'primaryType': 'TransferWithAuthorization',
    'domain': domain,
    'message': message
}

print(f'\nDomain: {domain}')
print(f'Message: {message}')

# Sign
signable_message = encode_typed_data(full_message=typed_data)
signed = account.sign_message(signable_message)
signature = '0x' + signed.signature.hex()

print(f'\nSignature: {signature}')
print(f'Signature length: {len(signature)} chars (including 0x) = {(len(signature)-2)//2} bytes')

# Now send this to facilitator
import requests
import json

payload = {
    "x402Version": 1,
    "paymentPayload": {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base",
        "payload": {
            "signature": signature,
            "authorization": {
                "from": account.address,
                "to": SELLER_ADDRESS,
                "value": "10000",
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce
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
        "payTo": SELLER_ADDRESS,
        "maxTimeoutSeconds": 60,
        "asset": USDC_ADDRESS,
        "extra": {
            "name": "USD Coin",
            "version": "2"
        }
    }
}

print(f'\nSending to facilitator...')
response = requests.post(
    "https://facilitator.ultravioletadao.xyz/settle",
    json=payload,
    headers={'Content-Type': 'application/json'},
    timeout=10
)

print(f'Response Status: {response.status_code}')
print(f'Response Body: {response.text}')

if response.status_code == 200:
    data = response.json()
    print(f'\nParsed response:')
    print(json.dumps(data, indent=2))
