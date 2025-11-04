#!/usr/bin/env python3
"""
Agent Configuration Helper
Loads all configuration from environment and AWS Secrets Manager

Usage in agent main.py:
    from shared.agent_config import load_agent_config

    config = load_agent_config("karma-hello-agent")

    # Now you can use:
    # config.private_key
    # config.openai_api_key
    # config.agent_address
    # config.rpc_url
    # etc.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

from .secrets_manager import get_private_key, get_openai_api_key
from .contracts_config import get_network_config, DEFAULT_NETWORK


@dataclass
class AgentConfig:
    """Configuration for an agent with all required credentials and endpoints"""

    # Identity
    agent_name: str
    agent_domain: str

    # Credentials (from AWS or .env)
    private_key: str
    openai_api_key: str
    agent_address: Optional[str] = None

    # Network Selection
    network: str = "fuji"  # "fuji" or "base-sepolia"

    # Blockchain
    rpc_url: str = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
    chain_id: int = 43113

    # Contracts
    glue_token_address: Optional[str] = None
    identity_registry: Optional[str] = None
    reputation_registry: Optional[str] = None
    validation_registry: Optional[str] = None

    # x402 Facilitator
    facilitator_url: str = "https://facilitator.ultravioletadao.xyz"

    # Server (for seller agents)
    host: str = "0.0.0.0"
    port: int = 8000

    # Pricing (in GLUE)
    base_price: float = 0.01
    max_price: float = 100.0


def load_agent_config(
    agent_name: str,
    agent_domain: Optional[str] = None,
    network: Optional[str] = None
) -> AgentConfig:
    """
    Load complete agent configuration from environment and AWS

    Priority:
    1. Environment variables (.env file) - if set and non-empty
    2. contracts_config.py - network defaults
    3. AWS Secrets Manager - fallback for credentials

    Args:
        agent_name: Agent name for AWS lookup (e.g., "karma-hello-agent")
        agent_domain: Optional domain override
        network: Network to use ("fuji" or "base-sepolia"). If None, uses NETWORK env var or default.

    Returns:
        AgentConfig with all settings loaded

    Example:
        >>> # Use default network (Fuji)
        >>> config = load_agent_config("validator-agent")

        >>> # Use Base Sepolia
        >>> config = load_agent_config("validator-agent", network="base-sepolia")

        >>> # Or set via environment
        >>> os.environ["NETWORK"] = "base-sepolia"
        >>> config = load_agent_config("validator-agent")
    """
    # Load .env file
    load_dotenv()

    # Get credentials (env overrides AWS)
    private_key = get_private_key(agent_name)
    openai_api_key = get_openai_api_key(agent_name)

    # Determine network to use
    selected_network = network or os.getenv("NETWORK", DEFAULT_NETWORK)

    # Load network-specific configuration
    network_config = get_network_config(selected_network)

    # Agent identity
    domain = agent_domain or os.getenv("AGENT_DOMAIN", f"{agent_name}.karmacadabra.ultravioletadao.xyz")

    # Blockchain config (env vars override network config)
    rpc_url = os.getenv("RPC_URL") or network_config["rpc_url"]
    chain_id = int(os.getenv("CHAIN_ID") or network_config["chain_id"])

    # Contract addresses (env vars override network config)
    glue_token = os.getenv("GLUE_TOKEN_ADDRESS") or network_config["glue_token"]
    identity_registry = os.getenv("IDENTITY_REGISTRY") or network_config["identity_registry"]
    reputation_registry = os.getenv("REPUTATION_REGISTRY") or network_config["reputation_registry"]
    validation_registry = os.getenv("VALIDATION_REGISTRY") or network_config["validation_registry"]

    # x402 (env var overrides network config)
    facilitator_url = os.getenv("FACILITATOR_URL") or network_config["facilitator_url"]

    # Server config
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    # Pricing
    base_price = float(os.getenv("BASE_PRICE", "0.01"))
    max_price = float(os.getenv("MAX_PRICE", "100.0"))

    # Public address (from .env if available)
    agent_address = os.getenv("AGENT_ADDRESS")

    return AgentConfig(
        agent_name=agent_name,
        agent_domain=domain,
        private_key=private_key,
        openai_api_key=openai_api_key,
        agent_address=agent_address,
        network=selected_network,
        rpc_url=rpc_url,
        chain_id=chain_id,
        glue_token_address=glue_token,
        identity_registry=identity_registry,
        reputation_registry=reputation_registry,
        validation_registry=validation_registry,
        facilitator_url=facilitator_url,
        host=host,
        port=port,
        base_price=base_price,
        max_price=max_price
    )


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m shared.agent_config <agent-name>")
        print("\nExample: python -m shared.agent_config validator-agent")
        sys.exit(1)

    agent_name = sys.argv[1]

    try:
        config = load_agent_config(agent_name)

        print(f"\n[+] Configuration loaded for: {config.agent_name}")
        print(f"\nNetwork:")
        print(f"  Selected: {config.network}")
        print(f"\nIdentity:")
        print(f"  Domain: {config.agent_domain}")
        print(f"  Address: {config.agent_address or 'Not set in .env'}")
        print(f"\nCredentials:")
        print(f"  Private Key: {config.private_key[:10]}...{config.private_key[-6:]}")
        print(f"  OpenAI Key: {config.openai_api_key[:15]}...{config.openai_api_key[-6:]}")
        print(f"\nBlockchain:")
        print(f"  RPC: {config.rpc_url}")
        print(f"  Chain ID: {config.chain_id}")
        print(f"\nContracts:")
        print(f"  GLUE: {config.glue_token_address}")
        print(f"  Identity Registry: {config.identity_registry}")
        print(f"  Reputation Registry: {config.reputation_registry}")
        print(f"  Validation Registry: {config.validation_registry}")
        print(f"\nx402 Facilitator:")
        print(f"  URL: {config.facilitator_url}")
        print(f"\nServer:")
        print(f"  {config.host}:{config.port}")
        print(f"\nPricing:")
        print(f"  Base: {config.base_price} GLUE")
        print(f"  Max: {config.max_price} GLUE")
        print()

    except Exception as e:
        print(f"\n[-] Error: {e}")
        sys.exit(1)
