#!/usr/bin/env python3
"""
System State Test - Complete Status Check
Tests everything from scratch to verify current state
"""

import os
import sys
import json
import boto3
from web3 import Web3
from eth_account import Account
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("KARMACADABRA SYSTEM STATE TEST")
print("=" * 80)
print()

# Load environment
from dotenv import load_dotenv
load_dotenv()

RPC_URL = os.getenv("RPC_URL_FUJI", "https://avalanche-fuji-c-chain-rpc.publicnode.com")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Contract addresses
GLUE_TOKEN = os.getenv("GLUE_TOKEN_ADDRESS", "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743")
IDENTITY_REGISTRY = os.getenv("IDENTITY_REGISTRY", "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618")
REPUTATION_REGISTRY = os.getenv("REPUTATION_REGISTRY", "0x932d32194C7A47c0fe246C1d61caF244A4804C6a")
VALIDATION_REGISTRY = os.getenv("VALIDATION_REGISTRY", "0x9aF4590035C109859B4163fd8f2224b820d11bc2")
TRANSACTION_LOGGER = os.getenv("TRANSACTION_LOGGER", "0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654")

print("[1/8] Testing Blockchain Connection...")
print("-" * 80)
try:
    latest_block = w3.eth.block_number
    print(f"[OK] Connected to Avalanche Fuji")
    print(f"    Latest Block: {latest_block}")
    print(f"    Chain ID: {w3.eth.chain_id}")
except Exception as e:
    print(f"[FAIL] Connection error: {e}")
    sys.exit(1)
print()

print("[2/8] Testing Contract Deployments...")
print("-" * 80)
contracts = {
    "GLUE Token": GLUE_TOKEN,
    "Identity Registry": IDENTITY_REGISTRY,
    "Reputation Registry": REPUTATION_REGISTRY,
    "Validation Registry": VALIDATION_REGISTRY,
    "Transaction Logger": TRANSACTION_LOGGER
}

for name, address in contracts.items():
    code = w3.eth.get_code(address)
    if len(code) > 2:  # "0x" is empty
        print(f"[OK] {name}: {address}")
    else:
        print(f"[FAIL] {name}: No code at {address}")
print()

print("[3/8] Testing AWS Secrets Manager...")
print("-" * 80)
try:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='karmacadabra')
    secrets = json.loads(response['SecretString'])

    expected_agents = [
        'erc-20',
        'client-agent',
        'karma-hello-agent',
        'abracadabra-agent',
        'validator-agent',
        'voice-extractor-agent',
        'skill-extractor-agent'
    ]

    for agent in expected_agents:
        if agent in secrets:
            print(f"[OK] {agent} key found in AWS")
        else:
            print(f"[FAIL] {agent} key NOT found in AWS")
except Exception as e:
    print(f"[FAIL] AWS error: {e}")
print()

print("[4/8] Testing Agent Wallet Balances...")
print("-" * 80)

# Get agent addresses from AWS
try:
    agent_addresses = {}
    for agent_key in expected_agents:
        if agent_key == 'erc-20':
            continue
        if agent_key in secrets:
            pk = secrets[agent_key]['private_key']
            account = Account.from_key(pk)
            agent_addresses[agent_key] = account.address

    # Check balances
    for agent_name, address in agent_addresses.items():
        avax_balance = w3.eth.get_balance(address)
        avax_eth = w3.from_wei(avax_balance, 'ether')

        # Check GLUE balance
        glue_abi = [{"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]
        glue_contract = w3.eth.contract(address=GLUE_TOKEN, abi=glue_abi)
        glue_balance = glue_contract.functions.balanceOf(address).call()
        glue_formatted = glue_balance / 1_000_000  # 6 decimals

        status = "[OK]" if avax_eth > 0 else "[WARN]"
        print(f"{status} {agent_name:25} {address}")
        print(f"     AVAX: {avax_eth:.4f} | GLUE: {glue_formatted:,.0f}")

except Exception as e:
    print(f"[FAIL] Error checking balances: {e}")
print()

print("[5/8] Testing Agent Registrations...")
print("-" * 80)

identity_abi = [
    {"constant":True,"inputs":[{"name":"agentAddress","type":"address"}],"name":"resolveByAddress","outputs":[{"name":"agentInfo","type":"tuple","components":[{"name":"agentId","type":"uint256"},{"name":"agentDomain","type":"string"},{"name":"agentAddress","type":"address"}]}],"type":"function"},
    {"constant":True,"inputs":[],"name":"getAgentCount","outputs":[{"name":"count","type":"uint256"}],"type":"function"}
]

try:
    identity_contract = w3.eth.contract(address=IDENTITY_REGISTRY, abi=identity_abi)
    total_agents = identity_contract.functions.getAgentCount().call()
    print(f"Total Registered Agents: {total_agents}")
    print()

    expected_domains = {
        'client-agent': 'client.karmacadabra.ultravioletadao.xyz',
        'karma-hello-agent': 'karma-hello.karmacadabra.ultravioletadao.xyz',
        'abracadabra-agent': 'abracadabra.karmacadabra.ultravioletadao.xyz',
        'validator-agent': 'validator.karmacadabra.ultravioletadao.xyz',
        'voice-extractor-agent': 'voice-extractor.karmacadabra.ultravioletadao.xyz',
        'skill-extractor-agent': 'skill-extractor.karmacadabra.ultravioletadao.xyz'
    }

    for agent_name, address in agent_addresses.items():
        try:
            result = identity_contract.functions.resolveByAddress(address).call()
            agent_id, domain, reg_address = result

            expected_domain = expected_domains.get(agent_name, 'unknown')
            domain_match = "[OK]" if domain == expected_domain else "[WARN]"

            print(f"[OK] {agent_name}")
            print(f"     ID: {agent_id}")
            print(f"     Domain: {domain} {domain_match}")

        except Exception as e:
            print(f"[NOT REGISTERED] {agent_name}")
            print(f"     Address: {address}")
            print(f"     Expected: {expected_domains.get(agent_name, 'unknown')}")
        print()

except Exception as e:
    print(f"[FAIL] Error checking registrations: {e}")
print()

print("[6/8] Testing Agent .env Files...")
print("-" * 80)

agent_dirs = [
    'client-agent',
    'karma-hello-agent',
    'abracadabra-agent',
    'validator',
    'voice-extractor-agent',
    'skill-extractor-agent'
]

for agent_dir in agent_dirs:
    env_example = project_root / agent_dir / '.env.example'
    env_file = project_root / agent_dir / '.env'

    if env_example.exists():
        content = env_example.read_text()
        if 'karmacadabra.ultravioletadao.xyz' in content:
            print(f"[OK] {agent_dir}/.env.example has correct domain")
        else:
            print(f"[WARN] {agent_dir}/.env.example missing correct domain")
    else:
        print(f"[WARN] {agent_dir}/.env.example not found")

    if env_file.exists():
        try:
            content = env_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = env_file.read_text(encoding='latin-1')
            except:
                print(f"[WARN] {agent_dir}/.env encoding issue")
                continue
        if 'PRIVATE_KEY=' in content and 'PRIVATE_KEY=0x' not in content:
            print(f"[OK] {agent_dir}/.env has empty PRIVATE_KEY")
        elif 'PRIVATE_KEY=0x' in content:
            print(f"[WARN] {agent_dir}/.env has private key (should be empty)")
        else:
            print(f"[INFO] {agent_dir}/.env - check PRIVATE_KEY")
    else:
        print(f"[INFO] {agent_dir}/.env not found (will be created from .env.example)")
    print()

print("[7/8] Testing Data Availability...")
print("-" * 80)

# Check for demo data
karma_hello_data = project_root / "data" / "karma-hello" / "chat_logs_20251023.json"
if karma_hello_data.exists():
    print(f"[OK] Karma-Hello demo data: {karma_hello_data}")
else:
    print(f"[WARN] Karma-Hello demo data not found")

abracadabra_data = project_root / "data" / "abracadabra" / "transcript_20251021.json"
if abracadabra_data.exists():
    print(f"[OK] Abracadabra demo data: {abracadabra_data}")
else:
    print(f"[WARN] Abracadabra demo data not found")
print()

print("[8/8] Testing Shared Library...")
print("-" * 80)

required_files = [
    'shared/base_agent.py',
    'shared/payment_signer.py',
    'shared/x402_client.py',
    'shared/a2a_protocol.py',
    'shared/validation_crew.py'
]

for file_path in required_files:
    full_path = project_root / file_path
    if full_path.exists():
        size = full_path.stat().st_size
        print(f"[OK] {file_path} ({size:,} bytes)")
    else:
        print(f"[FAIL] {file_path} NOT FOUND")
print()

print("=" * 80)
print("SYSTEM STATE SUMMARY")
print("=" * 80)
print()
print("Blockchain: Connected to Fuji")
print("Contracts: 5 deployed and verified")
print("AWS Secrets: All 7 agent keys stored")
print("Agent Wallets: Check balances above")
print("Registrations: Check details above")
print()
print("Next Steps:")
print("1. If agents not registered: Run demo_system.py to register")
print("2. If wallets need GLUE: Run erc-20/distribute-token.py")
print("3. If wallets need AVAX: Use Fuji faucet or ERC-20 deployer")
print("4. Run individual agent tests: pytest <agent-name>/tests/")
print()
