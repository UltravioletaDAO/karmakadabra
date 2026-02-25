#!/usr/bin/env python3
"""Derive a wallet address from HD mnemonic stored in AWS Secrets Manager.

Usage:
    python derive_wallet.py --index 1
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

HD_PATH_PREFIX = "m/44'/60'/0'/0"


def get_mnemonic() -> str:
    """Retrieve HD mnemonic from AWS Secrets Manager (kk/swarm-seed)."""
    import boto3

    client = boto3.client("secretsmanager", region_name="us-east-2")
    response = client.get_secret_value(SecretId="kk/swarm-seed")
    data = json.loads(response["SecretString"])
    mnemonic = data.get("mnemonic", "")
    if not mnemonic:
        raise ValueError("No 'mnemonic' key found in kk/swarm-seed secret")
    return mnemonic


def derive_address(mnemonic: str, index: int) -> str:
    """Derive an Ethereum address from mnemonic at given index."""
    from eth_account import Account
    Account.enable_unaudited_hdwallet_features()

    derivation_path = f"{HD_PATH_PREFIX}/{index}"
    acct = Account.from_mnemonic(mnemonic, account_path=derivation_path)
    return acct.address


def main():
    parser = argparse.ArgumentParser(description="Derive wallet from HD mnemonic")
    parser.add_argument("--index", type=int, required=True, help="HD derivation index")
    args = parser.parse_args()

    try:
        # Look up name from wallets.json
        root = Path(__file__).parent.parent.parent
        wallets_path = root / "data" / "config" / "wallets.json"
        name = f"index-{args.index}"
        if wallets_path.exists():
            data = json.loads(wallets_path.read_text(encoding="utf-8"))
            for w in data["wallets"]:
                if w["index"] == args.index:
                    name = w["name"]
                    break

        mnemonic = get_mnemonic()
        address = derive_address(mnemonic, args.index)

        result = {
            "index": args.index,
            "address": address,
            "name": name,
            "derivation_path": f"{HD_PATH_PREFIX}/{args.index}",
        }
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
