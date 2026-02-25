#!/usr/bin/env python3
"""
Multi-Chain Contract Configuration
Centralized configuration for all supported networks (testnet + mainnet)

Networks:
- Testnets: Avalanche Fuji, Base Sepolia
- Mainnets: Base, Ethereum, Polygon, Arbitrum, Celo, Avalanche, Optimism, Monad

Usage:
    from shared.contracts_config import get_network_config, NETWORKS

    # Get config for specific network
    config = get_network_config("base")
    print(config["payment_token"]["address"])

    # Get payment token info
    token = get_payment_token("base")
    print(f"{token['symbol']} at {token['address']}")

    # List all networks
    print(NETWORKS.keys())
"""

from typing import Dict, Any, Optional


# =============================================================================
# Testnet Configurations (v1 - GLUE token)
# =============================================================================

FUJI_CONFIG = {
    "name": "Avalanche Fuji",
    "chain_id": 43113,
    "rpc_url": "https://avalanche-fuji-c-chain-rpc.publicnode.com",
    "currency": "AVAX",
    "explorer_url": "https://testnet.snowtrace.io",
    "is_testnet": True,

    # Contract Addresses
    "glue_token": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
    "identity_registry": "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618",
    "reputation_registry": "0x932d32194C7A47c0fe246C1d61caF244A4804C6a",
    "validation_registry": "0x9aF4590035C109859B4163fd8f2224b820d11bc2",
    "transaction_logger": "0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654",

    # Payment Token
    "payment_token": {
        "symbol": "GLUE",
        "address": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
        "decimals": 18,
        "eip712_name": "Gasless Ultravioleta DAO Extended Token",
        "eip712_version": "1",
    },

    # GLUE Token EIP-712 Metadata (for x402 facilitator)
    "glue_eip712_name": "Gasless Ultravioleta DAO Extended Token",
    "glue_eip712_version": "1",

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.005",  # AVAX
    "block_time": 2,  # seconds
}

BASE_SEPOLIA_CONFIG = {
    "name": "Base Sepolia",
    "chain_id": 84532,
    "rpc_url": "https://sepolia.base.org",
    "currency": "ETH",
    "explorer_url": "https://sepolia.basescan.org",
    "is_testnet": True,

    # Contract Addresses (deployed November 3, 2025)
    "glue_token": "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425",
    "identity_registry": "0x8a20f665c02a33562a0462a0908a64716Ed7463d",
    "reputation_registry": "0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F",
    "validation_registry": "0x3C545DBeD1F587293fA929385442A459c2d316c4",
    "transaction_logger": None,  # Not deployed yet

    # Payment Token
    "payment_token": {
        "symbol": "GLUE",
        "address": "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425",
        "decimals": 18,
        "eip712_name": "Gasless Ultravioleta DAO Extended Token",
        "eip712_version": "1",
    },

    # GLUE Token EIP-712 Metadata (for x402 facilitator)
    "glue_eip712_name": "Gasless Ultravioleta DAO Extended Token",
    "glue_eip712_version": "1",

    # x402 Facilitator (same as Fuji - multi-chain support)
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.005",  # ETH
    "block_time": 2,  # seconds
}

# =============================================================================
# Mainnet Configurations (v2 - USDC)
# =============================================================================

# ERC-8004 registries deployed via CREATE2 at same address on all chains
_ERC8004_IDENTITY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
_ERC8004_REPUTATION = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

BASE_CONFIG = {
    "name": "Base",
    "chain_id": 8453,
    "rpc_url": "https://mainnet.base.org",
    "currency": "ETH",
    "explorer_url": "https://basescan.org",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token
    "payment_token": {
        "symbol": "USDC",
        "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.0001",  # ETH
    "block_time": 2,
}

ETHEREUM_CONFIG = {
    "name": "Ethereum",
    "chain_id": 1,
    "rpc_url": "https://ethereum-rpc.publicnode.com",
    "currency": "ETH",
    "explorer_url": "https://etherscan.io",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token
    "payment_token": {
        "symbol": "USDC",
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.0005",  # ETH
    "block_time": 12,
}

POLYGON_CONFIG = {
    "name": "Polygon",
    "chain_id": 137,
    "rpc_url": "https://polygon-bor-rpc.publicnode.com",
    "currency": "POL",
    "explorer_url": "https://polygonscan.com",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token
    "payment_token": {
        "symbol": "USDC",
        "address": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.01",  # POL
    "block_time": 2,
}

ARBITRUM_CONFIG = {
    "name": "Arbitrum",
    "chain_id": 42161,
    "rpc_url": "https://arbitrum-one-rpc.publicnode.com",
    "currency": "ETH",
    "explorer_url": "https://arbiscan.io",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token
    "payment_token": {
        "symbol": "USDC",
        "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.0001",  # ETH
    "block_time": 0.25,
}

CELO_CONFIG = {
    "name": "Celo",
    "chain_id": 42220,
    "rpc_url": "https://forno.celo.org",
    "currency": "CELO",
    "explorer_url": "https://celoscan.io",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token
    "payment_token": {
        "symbol": "USDC",
        "address": "0xcebA9300f2b948710d2653dD7B07f33A8B32118C",
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.01",  # CELO
    "block_time": 5,
}

AVALANCHE_CONFIG = {
    "name": "Avalanche",
    "chain_id": 43114,
    "rpc_url": "https://avalanche-c-chain-rpc.publicnode.com",
    "currency": "AVAX",
    "explorer_url": "https://snowtrace.io",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token
    "payment_token": {
        "symbol": "USDC",
        "address": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.01",  # AVAX
    "block_time": 2,
}

OPTIMISM_CONFIG = {
    "name": "Optimism",
    "chain_id": 10,
    "rpc_url": "https://mainnet.optimism.io",
    "currency": "ETH",
    "explorer_url": "https://optimistic.etherscan.io",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token
    "payment_token": {
        "symbol": "USDC",
        "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.0001",  # ETH
    "block_time": 2,
}

MONAD_CONFIG = {
    "name": "Monad",
    "chain_id": 143,
    "rpc_url": "https://rpc.monad.xyz",
    "currency": "MON",
    "explorer_url": "https://explorer.monad.xyz",
    "is_testnet": False,

    # Contract Addresses
    "identity_registry": _ERC8004_IDENTITY,
    "reputation_registry": _ERC8004_REPUTATION,

    # Payment Token (TBD - USDC not yet deployed on Monad)
    "payment_token": {
        "symbol": "USDC",
        "address": None,  # TBD
        "decimals": 6,
        "eip712_name": "USD Coin",
        "eip712_version": "2",
    },

    # x402 Facilitator
    "facilitator_url": "https://facilitator.ultravioletadao.xyz",

    # Network Features
    "supports_eip3009": True,
    "registration_fee": "0.01",  # MON
    "block_time": 1,
}


# =============================================================================
# Network Registry
# =============================================================================

NETWORKS: Dict[str, Dict[str, Any]] = {
    # Testnets (v1)
    "fuji": FUJI_CONFIG,
    "base-sepolia": BASE_SEPOLIA_CONFIG,
    # Mainnets (v2)
    "base": BASE_CONFIG,
    "ethereum": ETHEREUM_CONFIG,
    "polygon": POLYGON_CONFIG,
    "arbitrum": ARBITRUM_CONFIG,
    "celo": CELO_CONFIG,
    "avalanche": AVALANCHE_CONFIG,
    "optimism": OPTIMISM_CONFIG,
    "monad": MONAD_CONFIG,
}

# Default network - Base mainnet (switched from base-sepolia for OpenClaw launch)
DEFAULT_NETWORK = "base"

# Mainnet networks list (for batch operations)
MAINNET_NETWORKS = ["base", "ethereum", "polygon", "arbitrum", "celo", "avalanche", "optimism", "monad"]
TESTNET_NETWORKS = ["fuji", "base-sepolia"]


# =============================================================================
# Helper Functions
# =============================================================================

def get_network_config(network: Optional[str] = None) -> Dict[str, Any]:
    """
    Get configuration for a specific network.

    Args:
        network: Network name (e.g., "base", "fuji", "polygon").
                 If None, uses DEFAULT_NETWORK.

    Returns:
        Dictionary with network configuration.

    Raises:
        ValueError: If network is not supported.
    """
    if network is None:
        network = DEFAULT_NETWORK

    network = network.lower()

    if network not in NETWORKS:
        supported = ", ".join(NETWORKS.keys())
        raise ValueError(f"Unsupported network: {network}. Supported: {supported}")

    return NETWORKS[network].copy()


def get_payment_token(network: Optional[str] = None) -> Dict[str, Any]:
    """
    Get payment token info for a network.

    Returns dict with: symbol, address, decimals, eip712_name, eip712_version

    Args:
        network: Network name. If None, uses DEFAULT_NETWORK.

    Example:
        >>> token = get_payment_token("base")
        >>> print(f"{token['symbol']} at {token['address']}")
        USDC at 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
    """
    config = get_network_config(network)
    return config["payment_token"].copy()


def is_mainnet(network: Optional[str] = None) -> bool:
    """Check if a network is mainnet (not testnet)."""
    config = get_network_config(network)
    return not config.get("is_testnet", False)


def list_networks(mainnet_only: bool = False, testnet_only: bool = False) -> list:
    """
    Get list of supported network names.

    Args:
        mainnet_only: If True, return only mainnet networks.
        testnet_only: If True, return only testnet networks.
    """
    if mainnet_only:
        return MAINNET_NETWORKS.copy()
    if testnet_only:
        return TESTNET_NETWORKS.copy()
    return list(NETWORKS.keys())


def get_contract_address(contract_name: str, network: Optional[str] = None) -> str:
    """
    Get address for a specific contract on a network.

    Args:
        contract_name: Contract name (e.g., "identity_registry", "payment_token")
        network: Network name (default: DEFAULT_NETWORK)

    Returns:
        Contract address string.

    Raises:
        ValueError: If contract not found or not deployed.
    """
    config = get_network_config(network)

    if contract_name == "payment_token":
        addr = config["payment_token"]["address"]
        if addr is None:
            raise ValueError(f"Payment token not deployed on {config['name']}")
        return addr

    if contract_name not in config:
        available = [k for k in config.keys() if not k.startswith("_")]
        raise ValueError(f"Contract {contract_name} not found. Available: {available}")

    address = config[contract_name]

    if address is None:
        raise ValueError(f"Contract {contract_name} not deployed on {config['name']}")

    return address


def get_explorer_link(address: str, network: Optional[str] = None, type: str = "address") -> str:
    """
    Get block explorer link for an address or transaction.

    Args:
        address: Address or transaction hash
        network: Network name
        type: "address" or "tx"
    """
    config = get_network_config(network)
    return f"{config['explorer_url']}/{type}/{address}"


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Multi-Chain Contract Configuration")
    print("=" * 70)
    print()

    print(f"Default Network: {DEFAULT_NETWORK}")
    print(f"All Networks: {', '.join(list_networks())}")
    print(f"Mainnets: {', '.join(list_networks(mainnet_only=True))}")
    print(f"Testnets: {', '.join(list_networks(testnet_only=True))}")
    print()

    for network_name in list_networks():
        config = get_network_config(network_name)
        token = get_payment_token(network_name)

        env = "TESTNET" if config.get("is_testnet") else "MAINNET"
        print(f"  [{env}] {config['name']} (chain {config['chain_id']})")
        token_addr = token['address'] or 'TBD'
        print(f"    Payment: {token['symbol']} @ {token_addr}")
        print(f"    Identity: {config.get('identity_registry', 'N/A')}")
        print()

    print("=" * 70)
    print("Configuration loaded successfully!")
    print("=" * 70)
