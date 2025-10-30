#!/usr/bin/env python3
"""
Web3 Helper Utility
Provides Web3 utilities for blockchain interactions.

Handles:
- Web3 connection to Avalanche Fuji
- Contract loading with ABIs
- Transaction waiting and verification
- Balance checking
- Gas estimation
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import TransactionNotFound
from dotenv import load_dotenv


# Contract addresses on Fuji (from main repo)
IDENTITY_REGISTRY_ADDRESS = "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618"
REPUTATION_REGISTRY_ADDRESS = "0x932d32194C7A47c0fe246C1d61caF244A4804C6a"
GLUE_TOKEN_ADDRESS = "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"

# Default RPC URL
DEFAULT_RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"


def get_w3(rpc_url: Optional[str] = None) -> Web3:
    """
    Get Web3 instance connected to Avalanche Fuji

    Args:
        rpc_url: RPC URL (defaults to publicnode.com)

    Returns:
        Web3 instance
    """
    if not rpc_url:
        # Try to load from main repo env
        main_repo = Path(__file__).parent.parent.parent.parent
        env_file = main_repo / "erc-8004" / ".env.fuji"
        if env_file.exists():
            load_dotenv(env_file)
            rpc_url = os.getenv("RPC_URL_FUJI", DEFAULT_RPC_URL)
        else:
            rpc_url = DEFAULT_RPC_URL

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to Fuji RPC: {rpc_url}")

    print(f"✅ Connected to Avalanche Fuji (block {w3.eth.block_number:,})")
    return w3


def get_contract(w3: Web3, contract_name: str, address: Optional[str] = None) -> Contract:
    """
    Get contract instance with ABI

    Args:
        w3: Web3 instance
        contract_name: "IdentityRegistry" or "GLUEToken"
        address: Contract address (optional, uses defaults)

    Returns:
        Contract instance
    """
    # Use provided address or defaults
    if contract_name == "IdentityRegistry":
        address = address or IDENTITY_REGISTRY_ADDRESS
        abi = get_identity_registry_abi()
    elif contract_name == "ReputationRegistry":
        address = address or REPUTATION_REGISTRY_ADDRESS
        abi = get_reputation_registry_abi()
    elif contract_name == "GLUEToken":
        address = address or GLUE_TOKEN_ADDRESS
        abi = get_glue_token_abi()
    else:
        raise ValueError(f"Unknown contract: {contract_name}")

    return w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)


def get_identity_registry_abi() -> list:
    """Get Identity Registry ABI (minimal, for agent queries)"""
    return [
        {
            "inputs": [{"name": "agentAddress", "type": "address"}],
            "name": "resolveByAddress",
            "outputs": [
                {
                    "components": [
                        {"name": "agentId", "type": "uint256"},
                        {"name": "agentDomain", "type": "string"},
                        {"name": "agentAddress", "type": "address"}
                    ],
                    "name": "",
                    "type": "tuple"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "agentId", "type": "uint256"}],
            "name": "resolve",
            "outputs": [
                {
                    "components": [
                        {"name": "agentId", "type": "uint256"},
                        {"name": "agentDomain", "type": "string"},
                        {"name": "agentAddress", "type": "address"}
                    ],
                    "name": "",
                    "type": "tuple"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        }
    ]


def get_reputation_registry_abi() -> list:
    """Get Reputation Registry ABI (for rating functions)"""
    return [
        {
            "inputs": [
                {"name": "agentClientId", "type": "uint256"},
                {"name": "rating", "type": "uint8"}
            ],
            "name": "rateClient",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "agentValidatorId", "type": "uint256"},
                {"name": "rating", "type": "uint8"}
            ],
            "name": "rateValidator",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]


def get_glue_token_abi() -> list:
    """Get GLUE Token ABI (minimal, for balance queries)"""
    return [
        {
            "inputs": [{"name": "account", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]


def wait_for_transaction(
    w3: Web3,
    tx_hash: str,
    timeout: int = 120,
    poll_interval: float = 2.0
) -> Dict[str, Any]:
    """
    Wait for transaction to be mined

    Args:
        w3: Web3 instance
        tx_hash: Transaction hash
        timeout: Max seconds to wait
        poll_interval: Seconds between checks

    Returns:
        Transaction receipt

    Raises:
        TimeoutError: If transaction not mined within timeout
    """
    print(f"⏳ Waiting for transaction: {tx_hash}")

    start_time = time.time()

    while True:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            elapsed = time.time() - start_time
            print(f"✅ Transaction mined in {elapsed:.1f}s (block {receipt['blockNumber']})")
            return receipt
        except TransactionNotFound:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Transaction not mined after {timeout}s: {tx_hash}")
            time.sleep(poll_interval)


def get_agent_info(w3: Web3, address: str) -> Optional[Dict]:
    """
    Get agent information from Identity Registry

    Args:
        w3: Web3 instance
        address: Agent wallet address

    Returns:
        Dictionary with agent_id, domain, address or None if not registered
    """
    contract = get_contract(w3, "IdentityRegistry")

    try:
        result = contract.functions.resolveByAddress(Web3.to_checksum_address(address)).call()

        # Result is tuple: (agent_id, domain, address)
        if result[0] == 0:  # Not registered
            return None

        return {
            "agent_id": result[0],
            "domain": result[1],
            "address": result[2]
        }
    except Exception as e:
        print(f"⚠️  Failed to query agent info for {address}: {e}")
        return None


def get_avax_balance(w3: Web3, address: str) -> float:
    """
    Get AVAX balance for address

    Args:
        w3: Web3 instance
        address: Wallet address

    Returns:
        AVAX balance as float
    """
    balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
    return float(w3.from_wei(balance_wei, 'ether'))


def get_glue_balance(w3: Web3, address: str) -> float:
    """
    Get GLUE token balance for address

    Args:
        w3: Web3 instance
        address: Wallet address

    Returns:
        GLUE balance as float
    """
    contract = get_contract(w3, "GLUEToken")

    try:
        balance = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
        decimals = contract.functions.decimals().call()
        return balance / (10 ** decimals)
    except Exception as e:
        print(f"⚠️  Failed to get GLUE balance for {address}: {e}")
        return 0.0


def format_address(address: str, length: int = 10) -> str:
    """
    Format address for display (truncate middle)

    Args:
        address: Full address
        length: Total characters to show (excluding 0x and ...)

    Returns:
        Formatted address like "0x2C3e071d..."
    """
    if not address or len(address) < length:
        return address

    return f"{address[:length]}..."


def get_snowtrace_url(tx_hash: str, testnet: bool = True) -> str:
    """
    Get Snowtrace URL for transaction

    Args:
        tx_hash: Transaction hash
        testnet: True for Fuji, False for mainnet

    Returns:
        Snowtrace URL
    """
    base_url = "https://testnet.snowtrace.io" if testnet else "https://snowtrace.io"
    return f"{base_url}/tx/{tx_hash}"


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Web3 Helper Utility")
    parser.add_argument("--test", action="store_true", help="Run connection test")
    parser.add_argument("--agent", help="Query agent info by address")
    parser.add_argument("--balance", help="Check AVAX and GLUE balance for address")
    parser.add_argument("--tx", help="Wait for transaction and show receipt")

    args = parser.parse_args()

    if args.test:
        print("Testing Web3 connection...\n")
        w3 = get_w3()
        print(f"Chain ID: {w3.eth.chain_id}")
        print(f"Latest block: {w3.eth.block_number:,}")
        print(f"Gas price: {w3.eth.gas_price / 1e9:.2f} gwei")
        print("\n✅ Connection test passed!")

    elif args.agent:
        w3 = get_w3()
        info = get_agent_info(w3, args.agent)
        if info:
            print(f"✅ Agent found:")
            print(f"   ID: {info['agent_id']}")
            print(f"   Domain: {info['domain']}")
            print(f"   Address: {info['address']}")
        else:
            print(f"❌ Agent not registered: {args.agent}")

    elif args.balance:
        w3 = get_w3()
        avax = get_avax_balance(w3, args.balance)
        glue = get_glue_balance(w3, args.balance)
        print(f"Address: {format_address(args.balance)}")
        print(f"AVAX: {avax:.4f}")
        print(f"GLUE: {glue:,.0f}")

    elif args.tx:
        w3 = get_w3()
        receipt = wait_for_transaction(w3, args.tx)
        print(f"\nReceipt:")
        print(f"  Block: {receipt['blockNumber']}")
        print(f"  Gas used: {receipt['gasUsed']:,}")
        print(f"  Status: {'✅ Success' if receipt['status'] == 1 else '❌ Failed'}")
        print(f"  Snowtrace: {get_snowtrace_url(args.tx)}")

    else:
        parser.print_help()
