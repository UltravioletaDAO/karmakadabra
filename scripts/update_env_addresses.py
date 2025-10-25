#!/usr/bin/env python3
"""
Update all .env files with public addresses from AWS Secrets Manager

SECURITY NOTE:
- Public addresses are NOT secret and can be stored in .env files
- Private keys should NEVER be in .env - they stay in AWS Secrets Manager only
- This makes it easier to reference addresses without AWS lookups
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import json
import boto3
from eth_account import Account

print("=" * 80)
print("UPDATE .env FILES WITH PUBLIC ADDRESSES")
print("=" * 80)
print()

# Agent mapping: folder name -> AWS secret key
SERVICE_AGENTS = {
    'agents/karma-hello': 'karma-hello-agent',
    'agents/skill-extractor': 'skill-extractor-agent',
    'agents/voice-extractor': 'voice-extractor-agent',
    'agents/abracadabra': 'abracadabra-agent',
    'agents/validator': 'validator-agent',
    'validator': 'validator-agent',  # Also update root validator
}

# Load addresses from AWS
print("[1/2] Loading addresses from AWS Secrets Manager...")
try:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='karmacadabra')
    secrets = json.loads(response['SecretString'])
    print("  [OK] Loaded secrets from AWS")
except Exception as e:
    print(f"  [FAIL] Could not load from AWS: {e}")
    sys.exit(1)

# Derive addresses
agent_addresses = {}
for folder, secret_key in SERVICE_AGENTS.items():
    if secret_key in secrets:
        pk = secrets[secret_key]['private_key']
        account = Account.from_key(pk)
        agent_addresses[folder] = account.address
        print(f"  {folder:30} -> {account.address}")
    else:
        print(f"  [SKIP] {folder:30} -> Key '{secret_key}' not in AWS")

print()

# Update .env files
print("[2/2] Updating .env files...")

project_root = Path(__file__).parent.parent

for folder, address in agent_addresses.items():
    env_path = project_root / folder / ".env"

    if not env_path.exists():
        print(f"  [SKIP] {folder} - .env not found")
        continue

    # Read existing .env
    with open(env_path, 'r') as f:
        lines = f.readlines()

    # Check if AGENT_ADDRESS already exists
    has_agent_address = any(line.startswith('AGENT_ADDRESS=') for line in lines)

    if has_agent_address:
        # Update existing AGENT_ADDRESS
        new_lines = []
        for line in lines:
            if line.startswith('AGENT_ADDRESS='):
                new_lines.append(f'AGENT_ADDRESS={address}\n')
            else:
                new_lines.append(line)
    else:
        # Add AGENT_ADDRESS after PRIVATE_KEY line
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if line.startswith('PRIVATE_KEY='):
                new_lines.append(f'AGENT_ADDRESS={address}\n')

    # Write updated .env
    with open(env_path, 'w') as f:
        f.writelines(new_lines)

    print(f"  [OK] {folder}")

print()
print("=" * 80)
print("COMPLETE")
print("=" * 80)
print()
print("Updated .env files with public addresses.")
print()
print("SECURITY REMINDER:")
print("  ✅ Public addresses in .env = SAFE (not secret)")
print("  ❌ Private keys in .env = NEVER (use AWS Secrets Manager)")
print()
print("Next: Update .env.example files to document this pattern")
print("  Run: python scripts/update_env_examples.py")
print()
