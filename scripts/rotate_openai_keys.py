#!/usr/bin/env python3
"""
Rotate OpenAI API keys in AWS Secrets Manager
Reads keys from .unused/keys.txt and updates the karmacadabra secret
"""

import json
import boto3
from pathlib import Path

print("=" * 80)
print("ROTATE OPENAI API KEYS IN AWS SECRETS MANAGER")
print("=" * 80)
print()

# Read keys from file
keys_file = Path(__file__).parent.parent / ".unused" / "keys.txt"
print(f"[1/4] Reading keys from {keys_file}...")

openai_keys = {}
with open(keys_file, 'r') as f:
    lines = f.readlines()

# Parse the file (format: agent-name\nsk-proj-...\n)
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line and not line.startswith('sk-proj-'):
        # This is an agent name
        agent_name = line.replace('-2025', '')  # Remove the -2025 suffix
        if i + 1 < len(lines):
            key_line = lines[i + 1].strip()
            if key_line.startswith('sk-proj-'):
                openai_keys[agent_name] = key_line
                print(f"  ✓ Found key for {agent_name}")
    i += 1

print(f"[OK] Loaded {len(openai_keys)} keys")
print()

# Connect to AWS Secrets Manager
print("[2/4] Connecting to AWS Secrets Manager...")
try:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    print("[OK] Connected to AWS Secrets Manager")
except Exception as e:
    print(f"[FAIL] AWS connection error: {e}")
    exit(1)

print()

# Get existing secret
print("[3/4] Reading existing 'karmacadabra' secret...")
try:
    response = client.get_secret_value(SecretId='karmacadabra')
    secrets = json.loads(response['SecretString'])
    print("[OK] Existing secret loaded")
    print(f"     Current agents in secret: {list(secrets.keys())}")
except Exception as e:
    print(f"[FAIL] Error reading secret: {e}")
    exit(1)

print()

# Update openai_api_key for each agent
print("[4/4] Updating OPENAI_API_KEY for each agent...")
updated_count = 0

for agent_key, openai_key in openai_keys.items():
    if agent_key in secrets:
        old_key = secrets[agent_key].get('openai_api_key', 'NONE')
        secrets[agent_key]['openai_api_key'] = openai_key
        print(f"  ✓ Updated {agent_key}")
        print(f"    Old: {old_key[:20]}...")
        print(f"    New: {openai_key[:20]}...")
        updated_count += 1
    else:
        print(f"  ⚠ {agent_key} not found in secret (skipping)")

print()
print(f"[OK] Updated {updated_count} agents")
print()

# Update secret in AWS
print("Writing updated secret to AWS...")
try:
    client.put_secret_value(
        SecretId='karmacadabra',
        SecretString=json.dumps(secrets, indent=2)
    )
    print("[OK] Secret updated successfully!")
except Exception as e:
    print(f"[FAIL] Error updating secret: {e}")
    exit(1)

print()
print("=" * 80)
print("OPENAI API KEYS ROTATED IN AWS SECRETS MANAGER")
print("=" * 80)
print()

print("Summary:")
for agent_key in openai_keys.keys():
    print(f"  ✅ {agent_key}")

print()
print("Next steps:")
print("  1. Force redeploy ECS Fargate services to pick up new keys")
print("  2. Verify agents start successfully")
print("  3. Revoke old keys on OpenAI platform")
print()
