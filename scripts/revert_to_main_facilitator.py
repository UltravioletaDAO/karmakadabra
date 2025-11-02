#!/usr/bin/env python3
"""
Revert all facilitator.dev.ultravioletadao.xyz references to facilitator.ultravioletadao.xyz
This is the CORRECT main production endpoint (standalone deployment)
"""
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
OLD_DOMAIN = "facilitator.dev.ultravioletadao.xyz"
NEW_DOMAIN = "facilitator.ultravioletadao.xyz"

# Directories to skip
SKIP_DIRS = {'.git', '__pycache__', 'venv', 'node_modules', '.pytest_cache', 'logs', '.unused'}

# Files to skip
SKIP_FILES = {
    'revert_to_main_facilitator.py',
    'update_facilitator_domain.py',
    'update_docs_domain.py',
    'update_all_remaining_domains.py'
}

def should_skip(path: Path) -> bool:
    """Check if path should be skipped"""
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    if path.name in SKIP_FILES:
        return True
    if path.suffix not in ['.md', '.py', '.js', '.yml', '.yaml', '.txt', '.sh', '.rs', '.toml', '.json', '.html', '.mmd', '.example', ''] and not path.name.endswith('.env'):
        return True
    return False

def update_file(file_path: Path) -> tuple[bool, int]:
    """Update file with new domain"""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        if OLD_DOMAIN not in content:
            return False, 0
        new_content = content.replace(OLD_DOMAIN, NEW_DOMAIN)
        count = content.count(OLD_DOMAIN)
        file_path.write_text(new_content, encoding='utf-8')
        return True, count
    except Exception as e:
        print(f"[ERROR] {file_path.relative_to(ROOT)}: {e}", file=sys.stderr)
        return False, 0

def main():
    """Main function"""
    print(f"Reverting to main facilitator endpoint...")
    print(f"  Old (temp): {OLD_DOMAIN}")
    print(f"  New (main): {NEW_DOMAIN}")
    print()

    total_files = 0
    total_replacements = 0

    for file_path in ROOT.rglob('*'):
        if not file_path.is_file():
            continue
        if should_skip(file_path):
            continue

        modified, count = update_file(file_path)
        if modified:
            total_files += 1
            total_replacements += count
            rel_path = file_path.relative_to(ROOT)
            print(f"[OK] {rel_path} ({count}x)")

    print()
    print(f"=" * 60)
    print(f"Total files reverted: {total_files}")
    print(f"Total replacements: {total_replacements}")
    print()
    print("All references now point to: facilitator.ultravioletadao.xyz")

if __name__ == "__main__":
    main()
