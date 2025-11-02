#!/usr/bin/env python3
"""
Update facilitator domain in documentation files
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
OLD_DOMAIN = "facilitator.ultravioletadao.xyz"
NEW_DOMAIN = "facilitator.dev.ultravioletadao.xyz"

files_to_update = [
    'README.md',
    'README.es.md',
    'docs/ARCHITECTURE.md',
    'docs/FACILITATOR_TESTING.md',
    'docs/guides/GUIA_PRUEBAS_PRODUCCION.md',
    'docs/guides/TEST_CLIENT_AGENT.md',
    'docs/guides/TEST_USER_AGENT_CYBERPAISA.md',
    'x402-rs/DEPLOYMENT.md',
    'x402-rs/LANDING_PAGE.md',
    'x402-rs/Caddyfile',
    'x402-rs/static/index.html',
    'x402-rs/static/SETUP.md'
]

updated = 0
for file_rel in files_to_update:
    file_path = ROOT / file_rel
    if not file_path.exists():
        print(f"[SKIP] {file_rel} (not found)")
        continue

    try:
        content = file_path.read_text(encoding='utf-8')
        if OLD_DOMAIN not in content:
            print(f"[SKIP] {file_rel} (no changes needed)")
            continue

        new_content = content.replace(OLD_DOMAIN, NEW_DOMAIN)
        count = content.count(OLD_DOMAIN)
        file_path.write_text(new_content, encoding='utf-8')
        print(f"[OK] {file_rel} ({count} replacements)")
        updated += 1
    except Exception as e:
        print(f"[ERROR] {file_rel}: {e}")

print(f"\nUpdated {updated} documentation files")
