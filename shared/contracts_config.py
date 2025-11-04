#!/usr/bin/env python3
"""
Multi-Chain Contract Configuration
Centralized configuration for all supported networks

Networks:
- Avalanche Fuji (primary testnet)
- Base Sepolia (secondary testnet)

Usage:
    from shared.contracts_config import get_network_config, NETWORKS

    # Get config for specific network
    config = get_network_config("fuji")
    print(config["glue_token"])

    # List all networks
    print(NETWORKS.keys())
"""

from typing import Dict, Any, Literal

NetworkName = Literal["fuji", "base-sepolia"]

# =============================================================================
# Network Configurations
# =============================================================================

FUJI_CONFIG = {
    "name": "Avalanche Fuji",
    "chain_id": 43113,
    "rpc_url": "https://avalanche-fuji-c-chain-rpc.publicnode.com",
    "currency": "AVAX",
    "explorer_url": "https://testnet.snowtrace.io",

    # Contract Addresses
    "glue_token": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
    "identity_registry": "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618",
    "reputation_registry": "0x932d32194C7A47c0fe246C1d61caF244A4804C6a",
    "validation_registry": "0x9aF4590035C109859B4163fd8f2224b820d11bc2",
    "transaction_logger": "0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654",

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

    # Contract Addresses (deployed November 3, 2025)
    "glue_token": "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425",
    "identity_registry": "0x8a20f665c02a33562a0462a0908a64716Ed7463d",
    "reputation_registry": "0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F",
    "validation_registry": "0x3C545DBeD1F587293fA929385442A459c2d316c4",
    "transaction_logger": None,  # Not deployed yet

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

# All supported networks
NETWORKS: Dict[str, Dict[str, Any]] = {
    "fuji": FUJI_CONFIG,
    "base-sepolia": BASE_SEPOLIA_CONFIG,
}

# Default network (primary deployment)
DEFAULT_NETWORK: NetworkName = "fuji"


# =============================================================================
# Helper Functions
# =============================================================================

def get_network_config(network: str = None) -> Dict[str, Any]:
    """
    Get configuration for a specific network

    Args:
        network: Network name ("fuji" or "base-sepolia")
                 If None, uses DEFAULT_NETWORK

    Returns:
        Dictionary with network configuration

    Raises:
        ValueError: If network is not supported

    Example:
        >>> config = get_network_config("fuji")
        >>> print(config["glue_token"])
        0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
    """
    if network is None:
        network = DEFAULT_NETWORK

    network = network.lower()

    if network not in NETWORKS:
        supported = ", ".join(NETWORKS.keys())
        raise ValueError(f"Unsupported network: {network}. Supported: {supported}")

    return NETWORKS[network].copy()


def list_networks() -> list:
    """
    Get list of all supported networks

    Returns:
        List of network names

    Example:
        >>> networks = list_networks()
        >>> print(networks)
        ['fuji', 'base-sepolia']
    """
    return list(NETWORKS.keys())


def get_contract_address(contract_name: str, network: str = None) -> str:
    """
    Get address for a specific contract on a network

    Args:
        contract_name: Contract name (e.g., "glue_token", "identity_registry")
        network: Network name (default: fuji)

    Returns:
        Contract address

    Raises:
        ValueError: If contract not found or network not supported

    Example:
        >>> address = get_contract_address("glue_token", "base-sepolia")
        >>> print(address)
        0xfEe5CC33479E748f40F5F299Ff6494b23F88C425
    """
    config = get_network_config(network)

    if contract_name not in config:
        available = [k for k in config.keys() if not k.startswith("_")]
        raise ValueError(f"Contract {contract_name} not found. Available: {available}")

    address = config[contract_name]

    if address is None:
        raise ValueError(f"Contract {contract_name} not deployed on {config['name']}")

    return address


def get_explorer_link(address: str, network: str = None, type: str = "address") -> str:
    """
    Get block explorer link for an address or transaction

    Args:
        address: Address or transaction hash
        network: Network name
        type: "address" or "tx"

    Returns:
        Explorer URL

    Example:
        >>> link = get_explorer_link("0x123...", "fuji", "address")
        >>> print(link)
        https://testnet.snowtrace.io/address/0x123...
    """
    config = get_network_config(network)
    return f"{config['explorer_url']}/{type}/{address}"


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    import json

    print("=" * 70)
    print("Multi-Chain Contract Configuration")
    print("=" * 70)
    print()

    print(f"Default Network: {DEFAULT_NETWORK}")
    print(f"Supported Networks: {', '.join(list_networks())}")
    print()

    for network_name in list_networks():
        print("-" * 70)
        print(f"Network: {network_name.upper()}")
        print("-" * 70)

        config = get_network_config(network_name)

        print(f"\nNetwork Details:")
        print(f"  Name: {config['name']}")
        print(f"  Chain ID: {config['chain_id']}")
        print(f"  RPC: {config['rpc_url']}")
        print(f"  Currency: {config['currency']}")
        print(f"  Explorer: {config['explorer_url']}")

        print(f"\nContracts:")
        print(f"  GLUE Token: {config['glue_token']}")
        print(f"  Identity Registry: {config['identity_registry']}")
        print(f"  Reputation Registry: {config['reputation_registry']}")
        print(f"  Validation Registry: {config['validation_registry']}")
        if config['transaction_logger']:
            print(f"  Transaction Logger: {config['transaction_logger']}")

        print(f"\nFacilitator:")
        print(f"  URL: {config['facilitator_url']}")

        print(f"\nFeatures:")
        print(f"  EIP-3009 Support: {config['supports_eip3009']}")
        print(f"  Registration Fee: {config['registration_fee']} {config['currency']}")
        print(f"  Block Time: {config['block_time']}s")
        print()

    print("=" * 70)
    print("Configuration loaded successfully!")
    print("=" * 70)
