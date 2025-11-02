#!/usr/bin/env python3
"""
Extract USDC Contract Addresses from Facilitator Source Code
Compares configured addresses with on-chain reality
"""

import re
from pathlib import Path

print("=" * 80)
print("USDC CONTRACT ADDRESSES IN FACILITATOR CODE")
print("=" * 80)

# Read network.rs file
network_rs = Path("x402-rs/src/network.rs")

if not network_rs.exists():
    print(f"ERROR: {network_rs} not found!")
    exit(1)

content = network_rs.read_text()

# Extract USDC deployments
usdc_pattern = r'static\s+USDC_(\w+):\s+Lazy<USDCDeployment>\s+=\s+Lazy::new\(\|\|\s+\{[\s\S]*?address:\s+(?:address!\("([^"]+)"\)|MixedAddress::Solana\([^)]+Pubkey::from_str\("([^"]+)"\)[^)]*\))[\s\S]*?network:\s+Network::(\w+),[\s\S]*?decimals:\s+(\d+),[\s\S]*?eip712:\s+(Some\(TokenDeploymentEip712\s+\{[^}]+name:\s+"([^"]+)"[^}]+version:\s+"([^"]+)"[^}]+\}|None)'

matches = re.finditer(usdc_pattern, content)

usdc_deployments = {}

for match in matches:
    network_var = match.group(1)
    evm_address = match.group(2)
    solana_address = match.group(3)
    network_name = match.group(4)
    decimals = match.group(5)
    eip712_data = match.group(6)

    address = evm_address if evm_address else solana_address

    # Parse EIP712 if present
    if eip712_data and eip712_data != "None":
        name_match = re.search(r'name:\s+"([^"]+)"', eip712_data)
        version_match = re.search(r'version:\s+"([^"]+)"', eip712_data)
        eip712_name = name_match.group(1) if name_match else "N/A"
        eip712_version = version_match.group(1) if version_match else "N/A"
    else:
        eip712_name = "N/A (Solana)"
        eip712_version = "N/A"

    usdc_deployments[network_name] = {
        "address": address,
        "decimals": int(decimals),
        "eip712_name": eip712_name,
        "eip712_version": eip712_version,
        "variable": f"USDC_{network_var}"
    }

# Group by mainnet/testnet
mainnets = {}
testnets = {}

for network, data in sorted(usdc_deployments.items()):
    if any(x in network.lower() for x in ['sepolia', 'fuji', 'amoy', 'devnet', 'testnet']):
        testnets[network] = data
    else:
        mainnets[network] = data

# Print results
print("\n" + "=" * 80)
print("MAINNET USDC CONTRACTS")
print("=" * 80)

for network, data in sorted(mainnets.items()):
    print(f"\n{network}:")
    print(f"  Variable: {data['variable']}")
    print(f"  Address:  {data['address']}")
    print(f"  Decimals: {data['decimals']}")
    if data['eip712_name'] != "N/A (Solana)":
        print(f"  EIP-712 Name: {data['eip712_name']}")
        print(f"  EIP-712 Version: {data['eip712_version']}")

print("\n" + "=" * 80)
print("TESTNET USDC CONTRACTS")
print("=" * 80)

for network, data in sorted(testnets.items()):
    print(f"\n{network}:")
    print(f"  Variable: {data['variable']}")
    print(f"  Address:  {data['address']}")
    print(f"  Decimals: {data['decimals']}")
    if data['eip712_name'] != "N/A (Solana)":
        print(f"  EIP-712 Name: {data['eip712_name']}")
        print(f"  EIP-712 Version: {data['eip712_version']}")

# Export to JSON for comparison
import json

output_file = Path("scripts/usdc_contracts_facilitator.json")
output_data = {
    "mainnets": mainnets,
    "testnets": testnets,
    "extracted_at": "2025-10-31",
    "source_file": "x402-rs/src/network.rs"
}

output_file.write_text(json.dumps(output_data, indent=2))

print("\n" + "=" * 80)
print(f"SAVED TO: {output_file}")
print("=" * 80)
