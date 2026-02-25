#!/usr/bin/env python3
"""Check USDC balance for a KK agent on Base mainnet.

Usage:
    python check_balance.py --agent kk-karma-hello
"""

import argparse
import json
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.contracts_config import get_network_config

# Minimal ERC-20 balanceOf ABI
ERC20_BALANCE_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def load_wallet(agent_name: str) -> dict:
    wallets_path = Path(__file__).parent.parent.parent / "data" / "config" / "wallets.json"
    data = json.loads(wallets_path.read_text(encoding="utf-8"))
    for w in data["wallets"]:
        if w["name"] == agent_name:
            return w
    raise ValueError(f"Agent '{agent_name}' not found in wallets.json")


def main():
    parser = argparse.ArgumentParser(description="Check USDC balance for a KK agent")
    parser.add_argument("--agent", required=True, help="Agent name (e.g., kk-karma-hello)")
    args = parser.parse_args()

    try:
        from web3 import Web3

        wallet = load_wallet(args.agent)
        config = get_network_config("base")
        token = config["payment_token"]

        w3 = Web3(Web3.HTTPProvider(config["rpc_url"]))
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token["address"]),
            abi=ERC20_BALANCE_ABI,
        )

        raw_balance = contract.functions.balanceOf(
            Web3.to_checksum_address(wallet["address"])
        ).call()
        balance = raw_balance / (10 ** token["decimals"])

        result = {
            "agent": args.agent,
            "address": wallet["address"],
            "balance": f"{balance:.6f}",
            "token": token["symbol"],
            "network": "base",
        }
        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"error": str(e), "agent": args.agent}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
