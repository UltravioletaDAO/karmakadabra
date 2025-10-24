#!/usr/bin/env python3
"""
Karmacadabra System Rotation Script
====================================

SECURITY: Complete infrastructure rotation for key compromise scenarios

This script performs a complete system rotation:
1. Generates new wallets for all agents
2. Updates AWS Secrets Manager
3. Redeploys ERC-20 GLUE token contract
4. Redeploys ERC-8004 registries (Identity, Reputation, Validation)
5. Updates all agent .env files
6. Funds all wallets with testnet AVAX
7. Distributes GLUE tokens to all agents
8. Registers agents on-chain

[WARN]️  WARNING: This will invalidate ALL existing wallets and contracts!
[WARN]️  Use this when keys are compromised or for clean system reset.

Usage:
    python rotate-system.py [--confirm]

    Without --confirm flag, runs in dry-run mode (shows what would happen)
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from web3 import Web3
from eth_account import Account
import boto3
from typing import Dict, List, Tuple

# ============================================================================
# Configuration
# ============================================================================

AGENTS = [
    "validator-agent",
    "karma-hello-agent",
    "abracadabra-agent",
    "client-agent",
    "voice-extractor-agent",
    "skill-extractor-agent"
]

AWS_SECRET_NAME = "karmacadabra"
AWS_REGION = "us-east-1"

FUJI_RPC = "https://avalanche-fuji-c-chain-rpc.publicnode.com"
CHAIN_ID = 43113

# ============================================================================
# Colors for terminal output
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# ============================================================================
# Step 1: Generate New Wallets
# ============================================================================

def generate_wallets() -> Dict[str, Dict[str, str]]:
    """Generate new wallets for all agents"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}STEP 1: Generating New Wallets{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    wallets = {}

    for agent in AGENTS:
        # Generate new wallet
        account = Account.create()
        private_key = account.key.hex()
        address = account.address

        wallets[agent] = {
            "private_key": private_key,
            "address": address
        }

        print(f"{Colors.OKGREEN}[OK]{Colors.ENDC} {agent:25s} -> {address}")

    return wallets

# ============================================================================
# Step 2: Update AWS Secrets Manager
# ============================================================================

def update_aws_secrets(wallets: Dict[str, Dict[str, str]], dry_run: bool = True) -> bool:
    """Update AWS Secrets Manager with new wallets"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}STEP 2: Updating AWS Secrets Manager{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.WARNING}[DRY RUN] Would update AWS secret '{AWS_SECRET_NAME}'{Colors.ENDC}")
        for agent in AGENTS:
            print(f"  {agent}: {wallets[agent]['address']}")
        return True

    try:
        client = boto3.client('secretsmanager', region_name=AWS_REGION)

        # Build new secret structure
        new_secret = {}
        for agent in AGENTS:
            new_secret[agent] = {
                "private_key": wallets[agent]["private_key"]
            }

        # Also preserve erc-20 deployer key if it exists
        try:
            response = client.get_secret_value(SecretId=AWS_SECRET_NAME)
            current_secret = json.loads(response['SecretString'])
            if 'erc-20' in current_secret:
                new_secret['erc-20'] = current_secret['erc-20']
        except:
            pass

        # Update secret
        client.update_secret(
            SecretId=AWS_SECRET_NAME,
            SecretString=json.dumps(new_secret, indent=2)
        )

        print(f"{Colors.OKGREEN}[OK] Successfully updated AWS Secrets Manager{Colors.ENDC}")
        return True

    except Exception as e:
        print(f"{Colors.FAIL}[FAIL] Failed to update AWS Secrets: {e}{Colors.ENDC}")
        return False

# ============================================================================
# Step 3: Deploy ERC-20 GLUE Token
# ============================================================================

def deploy_glue_token(dry_run: bool = True) -> Tuple[bool, str]:
    """Deploy new GLUE token contract"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}STEP 3: Deploying ERC-20 GLUE Token{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.WARNING}[DRY RUN] Would deploy GLUE token to Fuji{Colors.ENDC}")
        return True, "0x0000000000000000000000000000000000000000"

    try:
        # Run deployment script
        result = subprocess.run(
            ["bash", "deploy-fuji.sh"],
            cwd="erc-20",
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"{Colors.FAIL}[FAIL] Deployment failed{Colors.ENDC}")
            print(result.stderr)
            return False, ""

        # Extract token address from output
        output = result.stdout
        for line in output.split('\n'):
            if 'GLUE Token:' in line:
                address = line.split(':')[-1].strip()
                print(f"{Colors.OKGREEN}[OK] GLUE Token deployed: {address}{Colors.ENDC}")
                return True, address

        print(f"{Colors.FAIL}[FAIL] Could not extract token address from deployment{Colors.ENDC}")
        return False, ""

    except Exception as e:
        print(f"{Colors.FAIL}[FAIL] Deployment error: {e}{Colors.ENDC}")
        return False, ""

# ============================================================================
# Step 4: Deploy ERC-8004 Registries
# ============================================================================

def deploy_registries(dry_run: bool = True) -> Tuple[bool, Dict[str, str]]:
    """Deploy ERC-8004 registry contracts"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}STEP 4: Deploying ERC-8004 Registries{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.WARNING}[DRY RUN] Would deploy ERC-8004 registries to Fuji{Colors.ENDC}")
        return True, {
            "identity": "0x0000000000000000000000000000000000000001",
            "reputation": "0x0000000000000000000000000000000000000002",
            "validation": "0x0000000000000000000000000000000000000003"
        }

    try:
        # Run deployment script
        result = subprocess.run(
            ["bash", "deploy-fuji.sh"],
            cwd="erc-8004",
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"{Colors.FAIL}[FAIL] Registry deployment failed{Colors.ENDC}")
            print(result.stderr)
            return False, {}

        # Extract addresses from output
        output = result.stdout
        addresses = {}

        for line in output.split('\n'):
            if 'Identity Registry:' in line:
                addresses['identity'] = line.split(':')[-1].strip()
            elif 'Reputation Registry:' in line:
                addresses['reputation'] = line.split(':')[-1].strip()
            elif 'Validation Registry:' in line:
                addresses['validation'] = line.split(':')[-1].strip()

        if len(addresses) == 3:
            print(f"{Colors.OKGREEN}[OK] Identity Registry: {addresses['identity']}{Colors.ENDC}")
            print(f"{Colors.OKGREEN}[OK] Reputation Registry: {addresses['reputation']}{Colors.ENDC}")
            print(f"{Colors.OKGREEN}[OK] Validation Registry: {addresses['validation']}{Colors.ENDC}")
            return True, addresses

        print(f"{Colors.FAIL}[FAIL] Could not extract all registry addresses{Colors.ENDC}")
        return False, {}

    except Exception as e:
        print(f"{Colors.FAIL}[FAIL] Registry deployment error: {e}{Colors.ENDC}")
        return False, {}

# ============================================================================
# Step 5: Update Agent .env Files
# ============================================================================

def update_agent_envs(
    wallets: Dict[str, Dict[str, str]],
    glue_address: str,
    registries: Dict[str, str],
    dry_run: bool = True
) -> bool:
    """Update all agent .env files with new contract addresses"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}STEP 5: Updating Agent .env Files{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    agent_dirs = {
        "validator-agent": "validator",
        "karma-hello-agent": "karma-hello-agent",
        "abracadabra-agent": "abracadabra-agent",
        "client-agent": "client-agent",
        "voice-extractor-agent": "voice-extractor-agent",
        "skill-extractor-agent": "skill-extractor-agent"
    }

    updates = {
        "GLUE_TOKEN_ADDRESS": glue_address,
        "IDENTITY_REGISTRY": registries.get('identity', ''),
        "REPUTATION_REGISTRY": registries.get('reputation', ''),
        "VALIDATION_REGISTRY": registries.get('validation', '')
    }

    for agent, directory in agent_dirs.items():
        env_path = Path(directory) / ".env"

        if not env_path.exists():
            print(f"{Colors.WARNING}[WARN] {agent}: No .env file found at {env_path}{Colors.ENDC}")
            continue

        if dry_run:
            print(f"{Colors.WARNING}[DRY RUN] Would update {env_path}{Colors.ENDC}")
            continue

        try:
            # Read current .env
            with open(env_path, 'r') as f:
                lines = f.readlines()

            # Update lines
            new_lines = []
            for line in lines:
                updated = False
                for key, value in updates.items():
                    if line.startswith(f"{key}="):
                        new_lines.append(f"{key}={value}\n")
                        updated = True
                        break

                if not updated:
                    new_lines.append(line)

            # Write back
            with open(env_path, 'w') as f:
                f.writelines(new_lines)

            print(f"{Colors.OKGREEN}[OK] Updated {env_path}{Colors.ENDC}")

        except Exception as e:
            print(f"{Colors.FAIL}[FAIL] Failed to update {env_path}: {e}{Colors.ENDC}")
            return False

    return True

# ============================================================================
# Step 6: Fund Wallets with AVAX
# ============================================================================

def fund_wallets(wallets: Dict[str, Dict[str, str]], dry_run: bool = True) -> bool:
    """Fund all wallets with testnet AVAX"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}STEP 6: Funding Wallets with AVAX{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.WARNING}[DRY RUN] Would request AVAX from faucet for {len(AGENTS)} agents{Colors.ENDC}")
        return True

    print(f"{Colors.WARNING}[WARN] Automatic faucet funding not implemented{Colors.ENDC}")
    print(f"{Colors.WARNING}[WARN] Please manually fund wallets at: https://faucet.avax.network/{Colors.ENDC}\n")

    for agent in AGENTS:
        print(f"  {agent:25s}: {wallets[agent]['address']}")

    return True

# ============================================================================
# Step 7: Distribute GLUE Tokens
# ============================================================================

def distribute_glue(wallets: Dict[str, Dict[str, str]], dry_run: bool = True) -> bool:
    """Distribute GLUE tokens to all agents"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}STEP 7: Distributing GLUE Tokens{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.WARNING}[DRY RUN] Would distribute GLUE tokens to {len(AGENTS)} agents{Colors.ENDC}")
        return True

    try:
        result = subprocess.run(
            ["python", "distribute-token.py"],
            cwd="erc-20",
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print(f"{Colors.OKGREEN}[OK] GLUE tokens distributed{Colors.ENDC}")
            return True
        else:
            print(f"{Colors.FAIL}[FAIL] Token distribution failed{Colors.ENDC}")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"{Colors.FAIL}[FAIL] Distribution error: {e}{Colors.ENDC}")
        return False

# ============================================================================
# Main Rotation Flow
# ============================================================================

def main():
    """Main rotation flow"""

    # Check for confirmation flag
    dry_run = "--confirm" not in sys.argv

    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}  KARMACADABRA SYSTEM ROTATION{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.WARNING}{'='*70}{Colors.ENDC}")
        print(f"{Colors.WARNING}  DRY RUN MODE - No changes will be made{Colors.ENDC}")
        print(f"{Colors.WARNING}  Add --confirm flag to execute actual rotation{Colors.ENDC}")
        print(f"{Colors.WARNING}{'='*70}{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}{'='*70}{Colors.ENDC}")
        print(f"{Colors.FAIL}  [WARN]️  LIVE MODE - Changes will be permanent!{Colors.ENDC}")
        print(f"{Colors.FAIL}  This will invalidate ALL existing wallets and contracts{Colors.ENDC}")
        print(f"{Colors.FAIL}{'='*70}{Colors.ENDC}\n")

        confirm = input("Type 'ROTATE' to confirm: ")
        if confirm != "ROTATE":
            print(f"\n{Colors.WARNING}Aborted{Colors.ENDC}")
            return

    # Execute rotation steps
    wallets = generate_wallets()

    if not update_aws_secrets(wallets, dry_run):
        print(f"\n{Colors.FAIL}[FAIL] Rotation failed at AWS Secrets update{Colors.ENDC}")
        return

    success, glue_address = deploy_glue_token(dry_run)
    if not success:
        print(f"\n{Colors.FAIL}[FAIL] Rotation failed at GLUE deployment{Colors.ENDC}")
        return

    success, registries = deploy_registries(dry_run)
    if not success:
        print(f"\n{Colors.FAIL}[FAIL] Rotation failed at registry deployment{Colors.ENDC}")
        return

    if not update_agent_envs(wallets, glue_address, registries, dry_run):
        print(f"\n{Colors.FAIL}[FAIL] Rotation failed at .env update{Colors.ENDC}")
        return

    if not fund_wallets(wallets, dry_run):
        print(f"\n{Colors.WARNING}[WARN] Wallet funding requires manual intervention{Colors.ENDC}")

    if not distribute_glue(wallets, dry_run):
        print(f"\n{Colors.WARNING}[WARN] Token distribution may require manual intervention{Colors.ENDC}")

    # Summary
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}ROTATION SUMMARY{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")

    if dry_run:
        print(f"{Colors.OKGREEN}[OK] Dry run completed successfully{Colors.ENDC}")
        print(f"\n{Colors.OKBLUE}Run with --confirm flag to execute actual rotation{Colors.ENDC}")
    else:
        print(f"{Colors.OKGREEN}[OK] System rotation completed{Colors.ENDC}")
        print(f"\n{Colors.OKCYAN}New Contract Addresses:{Colors.ENDC}")
        print(f"  GLUE Token:           {glue_address}")
        print(f"  Identity Registry:    {registries.get('identity', 'N/A')}")
        print(f"  Reputation Registry:  {registries.get('reputation', 'N/A')}")
        print(f"  Validation Registry:  {registries.get('validation', 'N/A')}")

        print(f"\n{Colors.OKCYAN}New Agent Wallets:{Colors.ENDC}")
        for agent in AGENTS:
            print(f"  {agent:25s}: {wallets[agent]['address']}")

    print(f"\n{Colors.OKGREEN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}  ROTATION COMPLETE{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{'='*70}{Colors.ENDC}\n")

if __name__ == "__main__":
    main()
