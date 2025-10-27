#!/usr/bin/env python3
"""
Update all .env.example files to include AGENT_ADDRESS field

This documents the best practice:
- PRIVATE_KEY= (empty - use AWS Secrets Manager)
- AGENT_ADDRESS=0x... (public address - safe to store)
"""

import os
import sys
from pathlib import Path

print("=" * 80)
print("UPDATE .env.example FILES")
print("=" * 80)
print()

project_root = Path(__file__).parent.parent

# Find all .env.example files in agent directories
env_example_files = []
env_example_files.extend(project_root.glob("agents/*/.env.example"))

print(f"Found {len(env_example_files)} .env.example files")
print()

for env_path in env_example_files:
    relative_path = env_path.relative_to(project_root)

    # Read existing .env.example
    with open(env_path, 'r') as f:
        lines = f.readlines()

    # Check if AGENT_ADDRESS already exists
    has_agent_address = any(line.startswith('AGENT_ADDRESS=') for line in lines)

    if has_agent_address:
        print(f"  [SKIP] {relative_path} - already has AGENT_ADDRESS")
        continue

    # Add AGENT_ADDRESS after PRIVATE_KEY line
    new_lines = []
    added = False

    for line in lines:
        new_lines.append(line)
        if line.startswith('PRIVATE_KEY=') and not added:
            # Add comment and AGENT_ADDRESS
            new_lines.append('AGENT_ADDRESS=  # Public address (derived from private key - safe to store)\n')
            added = True

    # Write updated .env.example
    with open(env_path, 'w') as f:
        f.writelines(new_lines)

    print(f"  [OK] {relative_path}")

print()
print("=" * 80)
print("COMPLETE")
print("=" * 80)
print()
print("Updated .env.example files to document AGENT_ADDRESS field.")
print()
print("Pattern documented:")
print("  PRIVATE_KEY=              # Empty - use AWS Secrets Manager")
print("  AGENT_ADDRESS=0x...       # Public address - safe to store")
print()
