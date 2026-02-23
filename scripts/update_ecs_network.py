#!/usr/bin/env python3
"""
Update ECS task definitions to use Base Sepolia network

This script adds NETWORK=base-sepolia environment variable to all agent task definitions.
The agents will then automatically load all Base Sepolia configuration from contracts_config.py.
"""

import json
import subprocess
import sys

AGENTS = ["validator", "karma-hello", "abracadabra", "skill-extractor", "voice-extractor"]
CLUSTER = "karmacadabra-prod"
REGION = "us-east-1"

def get_task_definition(agent):
    """Get current task definition for an agent"""
    cmd = [
        "aws", "ecs", "describe-task-definition",
        "--task-definition", f"karmacadabra-prod-{agent}",
        "--region", REGION
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] Failed to get task definition for {agent}")
        print(result.stderr)
        return None

    return json.loads(result.stdout)["taskDefinition"]

def update_task_definition(agent):
    """Add NETWORK=base-sepolia to task definition and register new revision"""
    print(f"\n[*] Updating {agent}...")

    # Get current task definition
    task_def = get_task_definition(agent)
    if not task_def:
        return False

    # Add or update NETWORK environment variable
    env_vars = task_def["containerDefinitions"][0]["environment"]

    # Remove existing NETWORK env var if present
    env_vars = [e for e in env_vars if e["name"] != "NETWORK"]

    # Add new NETWORK env var
    env_vars.append({"name": "NETWORK", "value": "base-sepolia"})

    task_def["containerDefinitions"][0]["environment"] = env_vars

    # Create new task definition with only required fields
    new_task_def = {
        "family": task_def["family"],
        "taskRoleArn": task_def["taskRoleArn"],
        "executionRoleArn": task_def["executionRoleArn"],
        "networkMode": task_def["networkMode"],
        "containerDefinitions": task_def["containerDefinitions"],
        "requiresCompatibilities": task_def["requiresCompatibilities"],
        "cpu": task_def["cpu"],
        "memory": task_def["memory"]
    }

    # Write to temp file
    temp_file = f"task-def-{agent}.json"
    with open(temp_file, "w") as f:
        json.dump(new_task_def, f, indent=2)

    # Register new task definition
    cmd = [
        "aws", "ecs", "register-task-definition",
        "--cli-input-json", f"file://{temp_file}",
        "--region", REGION
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] Failed to register task definition for {agent}")
        print(result.stderr)
        return False

    # Get new revision number
    new_revision = json.loads(result.stdout)["taskDefinition"]["revision"]
    print(f"[+] {agent} task definition updated to revision {new_revision}")

    return True

def deploy_service(agent):
    """Trigger ECS service to use new task definition"""
    print(f"[*] Deploying {agent} service...")

    cmd = [
        "aws", "ecs", "update-service",
        "--cluster", CLUSTER,
        "--service", f"karmacadabra-prod-{agent}",
        "--force-new-deployment",
        "--region", REGION
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] Failed to deploy {agent} service")
        print(result.stderr)
        return False

    print(f"[+] {agent} service deployment triggered")
    return True

def main():
    print("=" * 60)
    print("ECS Task Definition Update: Base Sepolia Migration")
    print("=" * 60)
    print("\nThis will add NETWORK=base-sepolia environment variable")
    print("to all agent task definitions and trigger new deployments.\n")

    input("Press Enter to continue or Ctrl+C to cancel...")

    # Update task definitions
    print("\n--- Updating Task Definitions ---")
    updated = []
    for agent in AGENTS:
        if update_task_definition(agent):
            updated.append(agent)

    if not updated:
        print("\n[!] No task definitions were updated. Exiting.")
        return 1

    # Deploy services
    print("\n--- Deploying Services ---")
    deployed = []
    for agent in updated:
        if deploy_service(agent):
            deployed.append(agent)

    # Summary
    print("\n" + "=" * 60)
    print("Deployment Summary")
    print("=" * 60)
    print(f"Task definitions updated: {len(updated)}/{len(AGENTS)}")
    print(f"Services deployed: {len(deployed)}/{len(updated)}")

    if deployed:
        print("\n[+] Successfully deployed:")
        for agent in deployed:
            print(f"    - {agent}")

    print("\nNext steps:")
    print("1. Monitor deployment: aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-validator --region us-east-1")
    print("2. Check agent card: curl https://validator.karmacadabra.ultravioletadao.xyz/.well-known/agent-card")
    print("3. Verify network shows 'base-sepolia' and chain_id shows 84532")

    return 0 if deployed else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[!] Cancelled by user")
        sys.exit(1)
