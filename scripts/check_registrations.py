#!/usr/bin/env python3
"""
Check actual agent registrations on-chain for all user agents
"""

import os
import sys
from pathlib import Path
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web3 import Web3
from dotenv import load_dotenv
import boto3

load_dotenv(project_root / ".env")

RPC_URL = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
IDENTITY_REGISTRY = os.getenv("IDENTITY_REGISTRY", "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Get all user agent directories
CLIENT_AGENTS_DIR = project_root / "client-agents"
USER_AGENTS = sorted([d.name for d in CLIENT_AGENTS_DIR.iterdir() if d.is_dir() and d.name != "template"])

print("=" * 100)
print("CHECKING ACTUAL AGENT REGISTRATIONS ON-CHAIN")
print("=" * 100)
print("")

# Get wallets from AWS
def get_wallets_from_aws():
    """Fetch all user agent wallets from AWS Secrets Manager"""
    try:
        session = boto3.session.Session()
        client = session.client('secretsmanager', region_name='us-east-1')

        response = client.get_secret_value(SecretId='karmacadabra')
        secret = json.loads(response['SecretString'])

        return secret.get('user-agents', {})
    except Exception as e:
        print(f"Error fetching from AWS: {e}")
        return {}

print("Fetching wallets from AWS Secrets Manager...")
all_wallets = get_wallets_from_aws()
print(f"   Found {len(all_wallets)} wallets")
print("")

# Check registration for each agent
# resolveByAddress returns AgentInfo struct: (agentId, agentDomain, agentAddress)
abi = [{
    "inputs": [{"name": "agentAddress", "type": "address"}],
    "name": "resolveByAddress",
    "outputs": [{
        "components": [
            {"name": "agentId", "type": "uint256"},
            {"name": "agentDomain", "type": "string"},
            {"name": "agentAddress", "type": "address"}
        ],
        "name": "agentInfo",
        "type": "tuple"
    }],
    "stateMutability": "view",
    "type": "function"
}]
contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=abi)

print(f"{'#':<4} {'Username':<25} {'Wallet Address':<45} {'Agent ID'}")
print("-" * 100)

agent_ids = {}
for i, username in enumerate(USER_AGENTS, 1):
    if username not in all_wallets:
        print(f"{i:<4} {username:<25} {'NO WALLET IN AWS':<45} N/A")
        continue

    wallet = all_wallets[username]
    address = wallet['address']

    try:
        agent_info = contract.functions.resolveByAddress(address).call()
        agent_id = agent_info[0]  # Extract agentId from tuple
        agent_ids[username] = agent_id

        if agent_id > 0:
            print(f"{i:<4} {username:<25} {address:<45} {agent_id}")
        else:
            print(f"{i:<4} {username:<25} {address:<45} NOT REGISTERED")
    except Exception as e:
        # Agent not found errors are expected for unregistered agents
        if "AgentNotFound" in str(e) or "execution reverted" in str(e):
            print(f"{i:<4} {username:<25} {address:<45} NOT REGISTERED")
            agent_ids[username] = 0
        else:
            print(f"{i:<4} {username:<25} {address:<45} ERROR: {e}")

print("-" * 100)
print("")

# Analyze results
registered_count = len([aid for aid in agent_ids.values() if aid > 0])
unique_ids = set([aid for aid in agent_ids.values() if aid > 0])

print("SUMMARY")
print("-" * 100)
print(f"Total agents:       {len(USER_AGENTS)}")
print(f"Registered:         {registered_count}")
print(f"Unique Agent IDs:   {len(unique_ids)}")
print(f"Agent ID range:     {min(unique_ids) if unique_ids else 'N/A'} - {max(unique_ids) if unique_ids else 'N/A'}")
print("")

if len(unique_ids) < registered_count:
    print("WARNING: Multiple agents share the same Agent ID!")
    print("This means they are using the same wallet address.")
    print("")

    # Find duplicates
    id_counts = {}
    for username, agent_id in agent_ids.items():
        if agent_id > 0:
            if agent_id not in id_counts:
                id_counts[agent_id] = []
            id_counts[agent_id].append(username)

    for agent_id, usernames in id_counts.items():
        if len(usernames) > 1:
            print(f"   Agent ID {agent_id} is shared by {len(usernames)} agents: {', '.join(usernames)}")
else:
    print("SUCCESS: All registered agents have unique Agent IDs")

print("")
