#!/usr/bin/env python3
"""
Verify USDC EIP-712 Domain on Base Mainnet

Queries the USDC contract to get the correct name/version for EIP-712 domain
"""

from web3 import Web3

# Base mainnet RPC
w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))

# USDC contract address
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# EIP-2612 name() and version() function selectors
NAME_SELECTOR = "0x06fdde03"  # name()
VERSION_SELECTOR = "0x54fd4d50"  # version()
DOMAIN_SEPARATOR_SELECTOR = "0x3644e515"  # DOMAIN_SEPARATOR()

print("="*60)
print("USDC EIP-712 Domain Verification (Base Mainnet)")
print("="*60)
print(f"Contract: {USDC_ADDRESS}")
print()

try:
    # Get name
    name_result = w3.eth.call({
        "to": USDC_ADDRESS,
        "data": NAME_SELECTOR
    })
    # Decode string (ABI-encoded)
    name = w3.to_text(name_result[64:64+int(name_result[32:64].hex(), 16)])
    print(f"name(): {name}")

    # Get version
    version_result = w3.eth.call({
        "to": USDC_ADDRESS,
        "data": VERSION_SELECTOR
    })
    # Decode string
    version = w3.to_text(version_result[64:64+int(version_result[32:64].hex(), 16)])
    print(f"version(): {version}")

    # Get DOMAIN_SEPARATOR
    domain_sep_result = w3.eth.call({
        "to": USDC_ADDRESS,
        "data": DOMAIN_SEPARATOR_SELECTOR
    })
    domain_sep = w3.to_hex(domain_sep_result)
    print(f"DOMAIN_SEPARATOR(): {domain_sep}")

    print()
    print("Expected in load_test.py:")
    print(f'  "name": "{name}"')
    print(f'  "version": "{version}"')
    print(f'  "chainId": 8453  # Base mainnet')
    print(f'  "verifyingContract": "{USDC_ADDRESS}"')

except Exception as e:
    print(f"Error querying contract: {e}")
    print()
    print("Note: The contract may not support EIP-2612 name()/version()")
    print("      Trying alternative method...")

    # Try reading from contract storage
    try:
        # USDC uses FiatTokenV2_1 which has name() and symbol()
        abi = [
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "version", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        ]

        contract = w3.eth.contract(address=USDC_ADDRESS, abi=abi)
        name = contract.functions.name().call()

        print(f"name(): {name}")

        try:
            version = contract.functions.version().call()
            print(f"version(): {version}")
        except:
            print("version(): Not available (trying default '2')")
            version = "2"

        print()
        print("Expected in load_test.py:")
        print(f'  "name": "{name}"')
        print(f'  "version": "{version}"')
        print(f'  "chainId": 8453')
        print(f'  "verifyingContract": "{USDC_ADDRESS}"')

    except Exception as e2:
        print(f"Alternative method also failed: {e2}")

print()
print("="*60)
