#!/usr/bin/env python3
"""
Migrate all agents from Avalanche Fuji to Base Sepolia
Updates .env files with Base Sepolia contract addresses
"""

import os
import re
from pathlib import Path

# Base Sepolia Configuration
BASE_SEPOLIA_CONFIG = {
    "NETWORK": "base-sepolia",
    "CHAIN_ID": "84532",
    "RPC_URL": "https://sepolia.base.org",
    "GLUE_TOKEN_ADDRESS": "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425",
    "IDENTITY_REGISTRY": "0x8a20f665c02a33562a0462a0908a64716Ed7463d",
    "REPUTATION_REGISTRY": "0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F",
    "VALIDATION_REGISTRY": "0x3C545DBeD1F587293fA929385442A459c2d316c4",
    "FACILITATOR_URL": "https://facilitator.ultravioletadao.xyz",
}

# Agent directories
AGENT_DIRS = [
    "agents/validator",
    "agents/karma-hello",
    "agents/abracadabra",
    "agents/skill-extractor",
    "agents/voice-extractor",
]

def update_env_file(env_path: Path):
    """Update a single .env file with Base Sepolia config"""

    if not env_path.exists():
        print(f"  [-] File not found: {env_path}")
        return

    print(f"  [*] Updating: {env_path}")

    # Read current content
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Track changes
    changes = []

    # Update each config value
    for key, value in BASE_SEPOLIA_CONFIG.items():
        # Pattern: KEY=value (capture everything after = until newline)
        pattern = rf'^{key}=.*$'
        replacement = f'{key}={value}'

        if re.search(pattern, content, re.MULTILINE):
            new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            if new_content != content:
                changes.append(f"{key}={value}")
                content = new_content
        else:
            # Key doesn't exist, append it
            # Find a good place to add it (after related keys or at end)
            if key == "NETWORK":
                # Add at the top after comments
                lines = content.split('\n')
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.strip().startswith('#'):
                        insert_pos = i
                        break
                lines.insert(insert_pos, f"{key}={value}")
                content = '\n'.join(lines)
                changes.append(f"Added {key}={value}")

    # Write back
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(content)

    if changes:
        for change in changes:
            print(f"    [+] {change}")
    else:
        print(f"    [=] No changes needed")

    print()

def main():
    print("=" * 70)
    print("MIGRATION: Avalanche Fuji -> Base Sepolia")
    print("=" * 70)
    print()

    print("[*] Base Sepolia Configuration:")
    for key, value in BASE_SEPOLIA_CONFIG.items():
        print(f"  {key}: {value}")
    print()

    # Update root .env (already done manually, but verify)
    root_env = Path(".env")
    if root_env.exists():
        print("[1] Root .env:")
        update_env_file(root_env)

    # Update each agent's .env
    print(f"[2] Updating {len(AGENT_DIRS)} agent .env files:")
    print()

    for agent_dir in AGENT_DIRS:
        agent_path = Path(agent_dir)
        env_path = agent_path / ".env"

        print(f"[*] Agent: {agent_dir}")
        update_env_file(env_path)

    print("=" * 70)
    print("[SUCCESS] Migration complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Review updated .env files")
    print("  2. Update docker-compose.yml (if needed)")
    print("  3. Update ECS task definitions")
    print("  4. Redeploy agents with: docker-compose up --build")
    print()

if __name__ == "__main__":
    main()
