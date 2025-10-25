#!/usr/bin/env python3
"""
AWS Secrets Manager Helper for Karmacadabra
Retrieves private keys from AWS Secrets Manager or .env files

Usage:
    from shared.secrets_manager import get_private_key

    # Automatically chooses source (env var or AWS)
    pk = get_private_key("validator-agent")
"""

import os
import json
import boto3
from typing import Optional, Dict
from functools import lru_cache

# AWS configuration
AWS_SECRET_NAME = "karmacadabra"
AWS_REGION = "us-east-1"

# Cache for AWS secret to avoid repeated API calls
_secret_cache: Optional[Dict] = None


@lru_cache(maxsize=1)
def _get_aws_secret() -> Dict:
    """
    Fetch the 'karmacadabra' secret from AWS Secrets Manager
    Cached to avoid repeated API calls
    """
    global _secret_cache

    if _secret_cache is not None:
        return _secret_cache

    try:
        client = boto3.client('secretsmanager', region_name=AWS_REGION)
        response = client.get_secret_value(SecretId=AWS_SECRET_NAME)

        secret_string = response['SecretString']
        _secret_cache = json.loads(secret_string)

        return _secret_cache

    except Exception as e:
        raise RuntimeError(
            f"Failed to retrieve secret '{AWS_SECRET_NAME}' from AWS Secrets Manager. "
            f"Ensure ~/.aws credentials are configured. Error: {e}"
        )


def get_private_key(agent_name: str, env_var: str = "PRIVATE_KEY") -> str:
    """
    Get private key for an agent

    Logic:
    1. Check if environment variable is set and non-empty → use it
    2. Otherwise, fetch from AWS Secrets Manager

    Args:
        agent_name: Name of the agent (e.g., "validator-agent", "karma-hello-agent")
        env_var: Name of environment variable to check (default: "PRIVATE_KEY")

    Returns:
        Private key as hex string (with 0x prefix)

    Raises:
        RuntimeError: If key not found in either source

    Example:
        >>> pk = get_private_key("validator-agent")
        >>> print(pk[:10])  # 0x1234567...
    """
    # 1. Try environment variable first
    env_value = os.getenv(env_var, "").strip()

    if env_value:
        # Normalize to 0x prefix
        if not env_value.startswith("0x"):
            env_value = "0x" + env_value

        print(f"[AWS Secrets] Using PRIVATE_KEY from environment variable")
        return env_value

    # 2. Fetch from AWS Secrets Manager
    print(f"[AWS Secrets] PRIVATE_KEY not in env, fetching from AWS Secrets Manager...")

    try:
        secrets = _get_aws_secret()

        if agent_name not in secrets:
            available = ", ".join(secrets.keys())
            raise RuntimeError(
                f"Agent '{agent_name}' not found in AWS secret '{AWS_SECRET_NAME}'. "
                f"Available agents: {available}"
            )

        agent_data = secrets[agent_name]
        private_key = agent_data.get("private_key")

        if not private_key:
            raise RuntimeError(
                f"No private_key found for '{agent_name}' in AWS secret"
            )

        print(f"[AWS Secrets] Retrieved key for '{agent_name}' from AWS")
        return private_key

    except Exception as e:
        raise RuntimeError(
            f"Failed to get private key for '{agent_name}': {e}\n"
            f"Ensure either:\n"
            f"  1. Set {env_var} in .env file, OR\n"
            f"  2. Run 'python scripts/setup-secrets.py' to create AWS secret, OR\n"
            f"  3. Configure ~/.aws credentials"
        )


def get_openai_api_key(agent_name: str, env_var: str = "OPENAI_API_KEY") -> str:
    """
    Get OpenAI API key for an agent

    Logic:
    1. Check if environment variable is set and non-empty → use it
    2. Otherwise, fetch from AWS Secrets Manager

    Args:
        agent_name: Name of the agent (e.g., "validator-agent", "karma-hello-agent")
        env_var: Name of environment variable to check (default: "OPENAI_API_KEY")

    Returns:
        OpenAI API key as string

    Raises:
        RuntimeError: If key not found in either source

    Example:
        >>> api_key = get_openai_api_key("validator-agent")
        >>> print(api_key[:10])  # sk-proj-Ab...
    """
    # 1. Try environment variable first
    env_value = os.getenv(env_var, "").strip()

    if env_value:
        print(f"[AWS Secrets] Using OPENAI_API_KEY from environment variable")
        return env_value

    # 2. Fetch from AWS Secrets Manager
    print(f"[AWS Secrets] OPENAI_API_KEY not in env, fetching from AWS Secrets Manager...")

    try:
        secrets = _get_aws_secret()

        if agent_name not in secrets:
            available = ", ".join(secrets.keys())
            raise RuntimeError(
                f"Agent '{agent_name}' not found in AWS secret '{AWS_SECRET_NAME}'. "
                f"Available agents: {available}"
            )

        agent_data = secrets[agent_name]
        openai_key = agent_data.get("openai_api_key")

        if not openai_key:
            raise RuntimeError(
                f"No openai_api_key found for '{agent_name}' in AWS secret"
            )

        print(f"[AWS Secrets] Retrieved OpenAI API key for '{agent_name}' from AWS")
        return openai_key

    except Exception as e:
        raise RuntimeError(
            f"Failed to get OpenAI API key for '{agent_name}': {e}\n"
            f"Ensure either:\n"
            f"  1. Set {env_var} in .env file, OR\n"
            f"  2. Run 'python scripts/add_openai_keys_to_aws.py' to add keys to AWS secret, OR\n"
            f"  3. Configure ~/.aws credentials"
        )


def get_agent_address(agent_name: str) -> Optional[str]:
    """
    Get wallet address for an agent from AWS Secrets Manager

    Args:
        agent_name: Name of the agent

    Returns:
        Wallet address (0x...) or None if not found
    """
    try:
        secrets = _get_aws_secret()
        agent_data = secrets.get(agent_name, {})
        return agent_data.get("address")
    except Exception:
        return None


def list_agents() -> list:
    """
    List all agents stored in AWS Secrets Manager

    Returns:
        List of agent names
    """
    try:
        secrets = _get_aws_secret()
        return list(secrets.keys())
    except Exception as e:
        print(f"[AWS Secrets] Failed to list agents: {e}")
        return []


def clear_cache():
    """Clear the AWS secret cache (useful for testing or after updating secrets)"""
    global _secret_cache
    _secret_cache = None
    _get_aws_secret.cache_clear()


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m shared.secrets_manager <agent-name>")
        print("\nAvailable agents:")
        for agent in list_agents():
            print(f"  - {agent}")
        sys.exit(1)

    agent_name = sys.argv[1]

    try:
        pk = get_private_key(agent_name)
        address = get_agent_address(agent_name)
        openai_key = get_openai_api_key(agent_name)

        print(f"\n[OK] Agent: {agent_name}")
        print(f"     Address: {address}")
        print(f"     Private Key: {pk[:10]}...{pk[-6:]}")
        print(f"     OpenAI API Key: {openai_key[:15]}...{openai_key[-6:]}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
