#!/usr/bin/env python3
"""
Update facilitator domain from facilitator.dev.ultravioletadao.xyz to facilitator.dev.ultravioletadao.xyz
"""

import os
import re
from pathlib import Path

# Root directory
ROOT = Path(__file__).parent.parent

# Patterns to replace
OLD_DOMAIN = "facilitator.dev.ultravioletadao.xyz"
NEW_DOMAIN = "facilitator.dev.ultravioletadao.xyz"

# File patterns to include
INCLUDE_PATTERNS = [
    "**/*.py",
    "**/*.md",
    "**/*.yml",
    "**/*.yaml",
    "**/*.txt",
    "**/*.sh",
    "**/*.example",
    "**/*.env.example",
]

# Directories to exclude
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    "node_modules",
    ".pytest_cache",
    "logs",
    ".unused",
}

def should_process_file(file_path: Path) -> bool:
    """Check if file should be processed"""
    # Skip excluded directories
    for part in file_path.parts:
        if part in EXCLUDE_DIRS:
            return False

    # Only process text files
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)  # Try reading first 1KB
        return True
    except (UnicodeDecodeError, PermissionError):
        return False

def update_file(file_path: Path) -> tuple[bool, int]:
    """
    Update file with new domain
    Returns: (was_modified, num_replacements)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if OLD_DOMAIN not in content:
            return False, 0

        new_content = content.replace(OLD_DOMAIN, NEW_DOMAIN)
        count = content.count(OLD_DOMAIN)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True, count
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False, 0

def main():
    """Main function"""
    print(f"Updating facilitator domain in all files...")
    print(f"  Old: {OLD_DOMAIN}")
    print(f"  New: {NEW_DOMAIN}")
    print()

    total_files = 0
    total_replacements = 0
    modified_files = []

    # Process all files
    for pattern in INCLUDE_PATTERNS:
        for file_path in ROOT.rglob(pattern):
            if not file_path.is_file():
                continue

            if not should_process_file(file_path):
                continue

            modified, count = update_file(file_path)
            if modified:
                total_files += 1
                total_replacements += count
                rel_path = file_path.relative_to(ROOT)
                modified_files.append((rel_path, count))
                print(f"[OK] {rel_path} ({count} replacements)")

    print()
    print("=" * 60)
    print(f"Summary:")
    print(f"  Files modified: {total_files}")
    print(f"  Total replacements: {total_replacements}")
    print()

    if modified_files:
        print("Modified files:")
        for file_path, count in sorted(modified_files):
            print(f"  - {file_path} ({count}x)")

if __name__ == "__main__":
    main()
