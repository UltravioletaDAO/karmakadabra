#!/usr/bin/env python3
"""
Add OpenAI API keys to AWS Secrets Manager
Stores keys in the existing 'karmacadabra' secret alongside private keys
"""

import json
import boto3
from pathlib import Path

print("=" * 80)
print("ADD OPENAI API KEYS TO AWS SECRETS MANAGER")
print("=" * 80)
print()

# OpenAI API keys - MUST be passed as command line arguments or environment variables
# NEVER hardcode API keys in this file
#
# Usage:
#   export KARMA_HELLO_KEY="REMOVED_FOR_SECURITY..."
#   export ABRACADABRA_KEY="REMOVED_FOR_SECURITY..."
#   python add_openai_keys_to_aws.py
#
# Or pass via command line (TODO: implement argparse)
import os

openai_keys = {
    'karma-hello-agent': os.getenv('KARMA_HELLO_KEY'),
    'abracadabra-agent': os.getenv('ABRACADABRA_KEY'),
    'validator-agent': os.getenv('VALIDATOR_KEY'),
    'voice-extractor-agent': os.getenv('VOICE_EXTRACTOR_KEY'),
    'skill-extractor-agent': os.getenv('SKILL_EXTRACTOR_KEY'),
    'client-agent': os.getenv('CLIENT_KEY')
}

# Validate that all keys are provided
missing_keys = [k for k, v in openai_keys.items() if not v]
if missing_keys:
    print(f"ERROR: Missing environment variables for: {', '.join(missing_keys)}")
    print("Please set environment variables before running this script:")
    for k in missing_keys:
        env_var = k.upper().replace('-AGENT', '_KEY').replace('-', '_')
        print(f"  export {env_var}=REMOVED_FOR_SECURITY...")
    exit(1)

print("OpenAI API keys to add:")
for agent_name in openai_keys.keys():
    print(f"  - {agent_name}")
print()

# Connect to AWS Secrets Manager
print("[1/3] Connecting to AWS Secrets Manager...")
try:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    print("[OK] Connected to AWS Secrets Manager")
except Exception as e:
    print(f"[FAIL] AWS connection error: {e}")
    exit(1)

print()

# Get existing secret
print("[2/3] Reading existing 'karmacadabra' secret...")
try:
    response = client.get_secret_value(SecretId='karmacadabra')
    secrets = json.loads(response['SecretString'])
    print("[OK] Existing secret loaded")
    print(f"     Current keys in secret: {list(secrets.keys())}")
except Exception as e:
    print(f"[FAIL] Error reading secret: {e}")
    exit(1)

print()

# Add openai_api_key to each agent's config
print("[3/3] Adding OPENAI_API_KEY to each agent...")
updated = False

for agent_key, openai_key in openai_keys.items():
    if agent_key in secrets:
        # Add openai_api_key to existing agent config
        secrets[agent_key]['openai_api_key'] = openai_key
        print(f"[OK] Added OpenAI key to {agent_key}")
        updated = True
    else:
        print(f"[SKIP] {agent_key} not found in secret (will create with openai_api_key only)")
        secrets[agent_key] = {'openai_api_key': openai_key}
        updated = True

if not updated:
    print("[SKIP] No changes needed")
    exit(0)

print()

# Update secret in AWS
print("Updating AWS secret with OpenAI keys...")
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
print("OPENAI API KEYS ADDED TO AWS SECRETS MANAGER")
print("=" * 80)
print()

print("Summary:")
for agent_key in openai_keys.keys():
    print(f"  ✅ {agent_key}")

print()
print("Next steps:")
print("  1. Update shared/base_agent.py to fetch OPENAI_API_KEY from AWS")
print("  2. Keep OPENAI_API_KEY= empty in .env files")
print("  3. If OPENAI_API_KEY is set in .env, it overrides AWS")
print()
