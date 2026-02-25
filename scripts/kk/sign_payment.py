#!/usr/bin/env python3
"""Sign an EIP-3009 transferWithAuthorization for USDC on Base.

Usage:
    python sign_payment.py --agent kk-karma-hello --to 0x... --amount 0.01
"""

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.contracts_config import get_network_config

# EIP-712 domain and types for USDC transferWithAuthorization
TRANSFER_WITH_AUTHORIZATION_TYPEHASH = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ]
}


def load_wallet_key(agent_name: str) -> tuple[str, str]:
    """Load agent address and private key. Key from env or AWS Secrets Manager."""
    root = Path(__file__).parent.parent.parent
    wallets = json.loads((root / "data" / "config" / "wallets.json").read_text(encoding="utf-8"))

    wallet = None
    for w in wallets["wallets"]:
        if w["name"] == agent_name:
            wallet = w
            break
    if not wallet:
        raise ValueError(f"Agent '{agent_name}' not found in wallets.json")

    # Try env var first, then AWS
    pk = os.environ.get("PRIVATE_KEY", "")
    if not pk:
        try:
            from shared.secrets_manager import get_private_key
            pk = get_private_key(agent_name)
        except Exception:
            raise ValueError(
                f"No private key available for {agent_name}. "
                "Set PRIVATE_KEY env var or configure AWS credentials."
            )

    return wallet["address"], pk


def main():
    parser = argparse.ArgumentParser(description="Sign EIP-3009 USDC payment")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--to", required=True, help="Recipient address")
    parser.add_argument("--amount", type=float, required=True, help="Amount in USDC")
    args = parser.parse_args()

    try:
        from eth_account import Account
        from eth_account.messages import encode_structured_data

        address, private_key = load_wallet_key(args.agent)
        config = get_network_config("base")
        token = config["payment_token"]

        value = int(args.amount * (10 ** token["decimals"]))
        nonce = "0x" + secrets.token_hex(32)
        valid_after = 0
        valid_before = int(time.time()) + 3600  # 1 hour validity

        # EIP-712 structured data
        domain = {
            "name": token["eip712_name"],
            "version": token["eip712_version"],
            "chainId": config["chain_id"],
            "verifyingContract": token["address"],
        }

        message = {
            "from": address,
            "to": args.to,
            "value": value,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": bytes.fromhex(nonce[2:]),
        }

        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                **TRANSFER_WITH_AUTHORIZATION_TYPEHASH,
            },
            "primaryType": "TransferWithAuthorization",
            "domain": domain,
            "message": message,
        }

        encoded = encode_structured_data(structured_data)
        signed = Account.sign_message(encoded, private_key=private_key)

        result = {
            "from": address,
            "to": args.to,
            "value": str(value),
            "amount_usdc": f"{args.amount:.6f}",
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
            "v": signed.v,
            "r": hex(signed.r),
            "s": hex(signed.s),
            "signature": signed.signature.hex(),
            "network": "base",
            "token": token["address"],
        }
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
