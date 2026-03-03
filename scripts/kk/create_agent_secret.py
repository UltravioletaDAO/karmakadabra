#!/usr/bin/env python3
"""Derive a private key from HD mnemonic and store in AWS Secrets Manager.

Usage:
    python scripts/kk/create_agent_secret.py --agent kk-elboorja --index 7

Security: Private key is NEVER printed to stdout. Goes directly to AWS.
"""

import argparse
import json
import sys

import boto3
from eth_account import Account

Account.enable_unaudited_hdwallet_features()


def main():
    parser = argparse.ArgumentParser(description="Create agent secret in AWS")
    parser.add_argument("--agent", required=True, help="Agent name (e.g. kk-elboorja)")
    parser.add_argument("--index", required=True, type=int, help="HD derivation index")
    parser.add_argument("--dry-run", action="store_true", help="Only verify, don't create secret")
    args = parser.parse_args()

    agent_name = args.agent
    hd_index = args.index

    # 1. Fetch mnemonic from AWS (us-east-2)
    print(f"[1/4] Fetching mnemonic from kk/swarm-seed (us-east-2)...")
    sm_seed = boto3.client("secretsmanager", region_name="us-east-2")
    try:
        resp = sm_seed.get_secret_value(SecretId="kk/swarm-seed")
        raw = resp["SecretString"]
        try:
            data = json.loads(raw)
            mnemonic = data.get("mnemonic", data.get("seed", raw))
        except json.JSONDecodeError:
            mnemonic = raw.strip()
    except Exception as e:
        print(f"FATAL: Cannot fetch mnemonic: {e}")
        sys.exit(1)

    # 2. Derive account
    print(f"[2/4] Deriving key for index {hd_index} (m/44'/60'/0'/0/{hd_index})...")
    path = f"m/44'/60'/0'/0/{hd_index}"
    acct = Account.from_mnemonic(mnemonic, account_path=path)
    address = acct.address
    private_key = acct.key.hex()
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    print(f"    Address: {address}")
    print(f"    Private key: [REDACTED - stored in AWS only]")

    if args.dry_run:
        print(f"\n[DRY RUN] Would create secret kk/{agent_name} in us-east-1")
        print(f"  Address matches identities.json? Check manually.")
        return

    # 3. Create secret in us-east-1
    secret_id = f"kk/{agent_name}"
    secret_value = json.dumps({"private_key": private_key})
    print(f"[3/4] Creating secret {secret_id} in us-east-1...")

    sm_agents = boto3.client("secretsmanager", region_name="us-east-1")
    try:
        sm_agents.create_secret(
            Name=secret_id,
            SecretString=secret_value,
            Description=f"Private key for {agent_name} (HD index {hd_index})",
        )
        print(f"[4/4] Secret created successfully!")
    except sm_agents.exceptions.ResourceExistsException:
        print(f"    Secret already exists. Updating...")
        sm_agents.put_secret_value(SecretId=secret_id, SecretString=secret_value)
        print(f"[4/4] Secret updated successfully!")
    except Exception as e:
        print(f"FATAL: Cannot create secret: {e}")
        sys.exit(1)

    # 4. Verify
    print(f"\nVerification:")
    print(f"  Agent: {agent_name}")
    print(f"  Index: {hd_index}")
    print(f"  Address: {address}")
    print(f"  Secret: {secret_id} (us-east-1)")
    print(f"  Status: OK")


if __name__ == "__main__":
    main()
