#!/usr/bin/env python3
"""
Clear Private Keys from .env Files
After storing keys in AWS Secrets Manager, empty all PRIVATE_KEY values in .env files

Usage:
    python scripts/clear-env-keys.py
"""

import os
import re
from pathlib import Path


def clear_private_key_in_file(env_path: Path) -> bool:
    """
    Clear PRIVATE_KEY value in a .env file

    Args:
        env_path: Path to .env file

    Returns:
        True if file was modified, False otherwise
    """
    if not env_path.exists():
        print(f"[SKIP] {env_path} does not exist")
        return False

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if PRIVATE_KEY is present and has a value
        pk_match = re.search(r'PRIVATE_KEY=(0x[a-fA-F0-9]{64}|[a-fA-F0-9]{64})', content)

        if not pk_match:
            # Either no PRIVATE_KEY or already empty
            if 'PRIVATE_KEY=' in content:
                print(f"[OK] {env_path.name} - PRIVATE_KEY already empty")
            else:
                print(f"[SKIP] {env_path.name} - No PRIVATE_KEY found")
            return False

        # Replace with empty value
        new_content = re.sub(
            r'PRIVATE_KEY=(0x[a-fA-F0-9]{64}|[a-fA-F0-9]{64})',
            'PRIVATE_KEY=',
            content
        )

        # Write back
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"[CLEARED] {env_path.relative_to(env_path.parent.parent)} - Private key removed")
        return True

    except Exception as e:
        print(f"[ERROR] {env_path.name}: {e}")
        return False


def main():
    print("=" * 70)
    print("Clear Private Keys from .env Files")
    print("=" * 70)
    print()

    base_dir = Path(__file__).parent.parent

    # List of all .env files to process
    env_files = [
        base_dir / "validator-agent" / ".env",
        base_dir / "karma-hello-agent" / ".env",
        base_dir / "abracadabra-agent" / ".env",
        base_dir / "client-agent" / ".env",
        base_dir / "voice-extractor-agent" / ".env",
        base_dir / "skill-extractor-agent" / ".env",
        base_dir / "erc-20" / ".env",
    ]

    print("[SCAN] Checking .env files...")
    print()

    modified_count = 0
    for env_path in env_files:
        if clear_private_key_in_file(env_path):
            modified_count += 1

    print()
    print("=" * 70)
    print(f"[DONE] Cleared {modified_count} file(s)")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Verify all agents can read keys from AWS Secrets Manager")
    print("2. Test with: python -m shared.secrets_manager validator-agent")
    print("3. If needed, restore keys from AWS with setup-secrets.py")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
