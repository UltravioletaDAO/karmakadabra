#!/usr/bin/env python3
"""Create AWS Secrets Manager entries for all 24 OpenClaw agents.

Fetches the HD wallet mnemonic from kk/swarm-seed (us-east-2),
derives private keys for each agent wallet index, and creates
individual secrets in us-east-1 for EC2 consumption.

Also copies the Anthropic API key from em/anthropic (us-east-2)
to kk/anthropic (us-east-1).

Usage:
    python create_agent_secrets.py
    python create_agent_secrets.py --dry-run
    python create_agent_secrets.py --agents 6   # Only first 6 (Phase 1)
"""

import argparse
import json
import sys
from pathlib import Path

SEED_REGION = "us-east-2"
TARGET_REGION = "us-east-1"
SEED_SECRET = "kk/swarm-seed"
ANTHROPIC_SOURCE = "em/anthropic"
DERIVATION_PATH = "m/44'/60'/0'/0"


def get_secret(secret_id: str, region: str) -> str:
    import boto3
    client = boto3.client("secretsmanager", region_name=region)
    resp = client.get_secret_value(SecretId=secret_id)
    return resp["SecretString"]


def derive_private_key(mnemonic: str, index: int) -> str:
    from eth_account import Account
    Account.enable_unaudited_hdwallet_features()
    acct = Account.from_mnemonic(mnemonic, account_path=f"{DERIVATION_PATH}/{index}")
    return acct.key.hex()


def create_or_update_secret(name: str, value: str, region: str, dry_run: bool) -> str:
    if dry_run:
        return "dry-run"
    import boto3
    client = boto3.client("secretsmanager", region_name=region)
    try:
        client.create_secret(Name=name, SecretString=value)
        return "created"
    except client.exceptions.ResourceExistsException:
        client.put_secret_value(SecretId=name, SecretString=value)
        return "updated"


def main():
    parser = argparse.ArgumentParser(description="Create agent secrets in AWS")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    parser.add_argument("--agents", type=int, default=24, help="Number of agents (default: 24)")
    args = parser.parse_args()

    root = Path(__file__).parent.parent.parent
    wallets_file = root / "data" / "config" / "wallets.json"

    if not wallets_file.exists():
        print("[ERROR] wallets.json not found")
        sys.exit(1)

    wallets = json.loads(wallets_file.read_text(encoding="utf-8"))
    agent_wallets = wallets["wallets"][:args.agents]

    print(f"\n=== Create Agent Secrets ===")
    print(f"Agents:  {len(agent_wallets)}")
    print(f"Target:  {TARGET_REGION}")
    print(f"Dry-run: {args.dry_run}\n")

    # Step 1: Fetch mnemonic
    print("[Step 1] Fetching mnemonic from kk/swarm-seed...")
    if args.dry_run:
        print("  [DRY-RUN] Would fetch mnemonic")
        mnemonic = None
    else:
        raw = get_secret(SEED_SECRET, SEED_REGION)
        try:
            data = json.loads(raw)
            mnemonic = data.get("mnemonic", data.get("seed", raw))
        except json.JSONDecodeError:
            mnemonic = raw.strip()
        print("  [OK] Mnemonic retrieved (not displayed)")

    # Step 2: Derive keys and create secrets
    print(f"\n[Step 2] Creating {len(agent_wallets)} agent secrets...")
    created = 0
    for w in agent_wallets:
        name = w["name"]
        index = w["index"]
        secret_name = f"kk/{name}"

        if args.dry_run:
            print(f"  [DRY-RUN] {secret_name} (index {index})")
            created += 1
            continue

        pk = derive_private_key(mnemonic, index)
        secret_value = json.dumps({"private_key": pk})
        status = create_or_update_secret(secret_name, secret_value, TARGET_REGION, False)
        print(f"  [{status.upper()}] {secret_name}")
        created += 1
        # Clear from memory
        pk = None
        secret_value = None

    # Step 3: Copy Anthropic API key
    print(f"\n[Step 3] Copying Anthropic API key to kk/anthropic...")
    if args.dry_run:
        print(f"  [DRY-RUN] Would copy {ANTHROPIC_SOURCE} -> kk/anthropic")
    else:
        anthropic_key = get_secret(ANTHROPIC_SOURCE, SEED_REGION)
        status = create_or_update_secret("kk/anthropic", anthropic_key, TARGET_REGION, False)
        print(f"  [{status.upper()}] kk/anthropic")
        anthropic_key = None

    print(f"\n=== Done === {created} agent secrets + 1 anthropic key")
    if args.dry_run:
        print("(Dry run -- nothing was actually created)")


if __name__ == "__main__":
    main()
