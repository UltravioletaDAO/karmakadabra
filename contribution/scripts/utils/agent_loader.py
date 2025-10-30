#!/usr/bin/env python3
"""
Agent Loader Utility
Load agent configurations from main repository for Week 2 simulation.

This utility handles loading all 54 agents (5 system + 1 client + 48 users)
with their addresses, domains, and configuration details.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Add lib to path for imports
LIB_PATH = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(LIB_PATH))

from agent_config import load_agent_config


class AgentInfo:
    """Agent configuration data"""

    def __init__(self, name: str, agent_type: str, config_path: Path):
        self.name = name
        self.type = agent_type  # "system", "client", or "user"
        self.config_path = config_path
        self.address = None
        self.domain = None
        self.agent_id = None
        self.env_data = {}

        # Load .env file
        self._load_env()

    def _load_env(self):
        """Load agent .env file"""
        env_file = self.config_path / ".env"
        if not env_file.exists():
            raise FileNotFoundError(f"No .env file found for {self.name} at {env_file}")

        # Load environment variables
        load_dotenv(env_file)

        # Extract key fields
        self.address = os.getenv("AGENT_ADDRESS")
        self.domain = os.getenv("AGENT_DOMAIN")

        # Store all env vars for reference
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    self.env_data[key] = value

    def __repr__(self):
        return f"AgentInfo(name={self.name}, type={self.type}, address={self.address})"


def get_main_repo_path() -> Path:
    """Get path to main Karmacadabra repository"""
    # contribution/scripts/utils/agent_loader.py -> contribution -> karmacadabra
    return Path(__file__).parent.parent.parent.parent


def load_system_agents() -> List[AgentInfo]:
    """
    Load 5 system agents: karma-hello, abracadabra, skill-extractor,
    voice-extractor, validator
    """
    main_repo = get_main_repo_path()
    agents_dir = main_repo / "agents"

    system_agent_names = [
        "karma-hello",
        "abracadabra",
        "skill-extractor",
        "voice-extractor",
        "validator"
    ]

    agents = []
    for name in system_agent_names:
        agent_path = agents_dir / name
        if agent_path.exists():
            try:
                agent = AgentInfo(name, "system", agent_path)
                agents.append(agent)
            except Exception as e:
                print(f"Warning: Failed to load system agent {name}: {e}")

    return agents


def load_client_agent() -> Optional[AgentInfo]:
    """Load client agent"""
    main_repo = get_main_repo_path()
    client_path = main_repo / "client-agents" / "template"

    if client_path.exists():
        try:
            return AgentInfo("client", "client", client_path)
        except Exception as e:
            print(f"Warning: Failed to load client agent: {e}")

    return None


def load_user_agents() -> List[AgentInfo]:
    """
    Load 48 user agents from client-agents/ directory
    """
    main_repo = get_main_repo_path()
    client_agents_dir = main_repo / "client-agents"

    agents = []

    # Iterate through all directories in client-agents/
    for agent_dir in sorted(client_agents_dir.iterdir()):
        if agent_dir.is_dir() and agent_dir.name != "template":
            try:
                agent = AgentInfo(agent_dir.name, "user", agent_dir)
                agents.append(agent)
            except Exception as e:
                print(f"Warning: Failed to load user agent {agent_dir.name}: {e}")

    return agents


def load_all_agents() -> List[AgentInfo]:
    """
    Load all 54 agents (5 system + 1 client + 48 users)

    Returns:
        List of AgentInfo objects
    """
    all_agents = []

    # Load system agents
    system = load_system_agents()
    all_agents.extend(system)
    print(f"Loaded {len(system)} system agents")

    # Load client agent
    client = load_client_agent()
    if client:
        all_agents.append(client)
        print(f"Loaded 1 client agent")

    # Load user agents
    users = load_user_agents()
    all_agents.extend(users)
    print(f"Loaded {len(users)} user agents")

    print(f"Total: {len(all_agents)} agents loaded")
    return all_agents


def load_agent_by_name(agent_name: str) -> Optional[AgentInfo]:
    """
    Load a specific agent by name

    Args:
        agent_name: Agent name (e.g., "karma-hello", "0xultravioleta")

    Returns:
        AgentInfo or None if not found
    """
    main_repo = get_main_repo_path()

    # Check system agents
    agent_path = main_repo / "agents" / agent_name
    if agent_path.exists():
        return AgentInfo(agent_name, "system", agent_path)

    # Check client agent
    if agent_name == "client":
        client_path = main_repo / "client-agents" / "template"
        if client_path.exists():
            return AgentInfo("client", "client", client_path)

    # Check user agents
    agent_path = main_repo / "client-agents" / agent_name
    if agent_path.exists():
        return AgentInfo(agent_name, "user", agent_path)

    return None


def get_agents_by_type(agent_type: str) -> List[AgentInfo]:
    """
    Get all agents of a specific type

    Args:
        agent_type: "system", "client", or "user"

    Returns:
        List of AgentInfo objects
    """
    all_agents = load_all_agents()
    return [a for a in all_agents if a.type == agent_type]


def filter_agents_with_address(agents: List[AgentInfo]) -> List[AgentInfo]:
    """
    Filter agents that have an address configured

    Args:
        agents: List of AgentInfo objects

    Returns:
        List of agents with non-empty addresses
    """
    return [a for a in agents if a.address and a.address.strip()]


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load Karmacadabra agent configurations")
    parser.add_argument("--agent", help="Load specific agent by name")
    parser.add_argument("--type", choices=["system", "client", "user"], help="Load agents of specific type")
    parser.add_argument("--all", action="store_true", help="Load all agents")
    parser.add_argument("--verbose", action="store_true", help="Show detailed info")

    args = parser.parse_args()

    if args.agent:
        agent = load_agent_by_name(args.agent)
        if agent:
            print(f"✅ Loaded: {agent.name}")
            print(f"   Type: {agent.type}")
            print(f"   Address: {agent.address}")
            print(f"   Domain: {agent.domain}")
            if args.verbose:
                print(f"   Config path: {agent.config_path}")
                print(f"   Env vars: {list(agent.env_data.keys())}")
        else:
            print(f"❌ Agent '{args.agent}' not found")

    elif args.type:
        agents = get_agents_by_type(args.type)
        print(f"Found {len(agents)} {args.type} agents:")
        for agent in agents:
            status = "✅" if agent.address else "⚠️"
            print(f"{status} {agent.name} - {agent.address or 'NO ADDRESS'}")

    elif args.all:
        agents = load_all_agents()
        print(f"\nAll agents ({len(agents)}):")

        # Group by type
        by_type = {
            "system": [a for a in agents if a.type == "system"],
            "client": [a for a in agents if a.type == "client"],
            "user": [a for a in agents if a.type == "user"]
        }

        for agent_type, type_agents in by_type.items():
            print(f"\n{agent_type.upper()} ({len(type_agents)}):")
            for agent in type_agents:
                status = "✅" if agent.address else "⚠️"
                addr = agent.address[:10] + "..." if agent.address else "NO ADDRESS"
                print(f"  {status} {agent.name:20} {addr}")

    else:
        parser.print_help()
