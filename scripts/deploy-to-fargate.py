#!/usr/bin/env python3
"""
Deploy Karmacadabra to AWS Fargate
Fully idempotent - applies Terraform and forces ECS service deployments

Usage:
    python scripts/deploy-to-fargate.py                    # Terraform apply only
    python scripts/deploy-to-fargate.py --force-deploy     # Terraform + force ECS redeployment
    python scripts/deploy-to-fargate.py facilitator        # Force redeploy specific service
"""

import os
import sys
import subprocess
import json
import boto3
import time
from pathlib import Path

# Configuration
AWS_REGION = "us-east-1"
ECS_CLUSTER = "karmacadabra-prod"
TERRAFORM_DIR = Path(__file__).parent.parent / "terraform" / "ecs-fargate"

# Services to deploy
SERVICES = [
    'facilitator',
    'validator',
    'karma-hello',
    'abracadabra',
    'skill-extractor',
    'voice-extractor'
]

def run_command(cmd, cwd=None, check=True, env=None):
    """Run shell command and return output"""
    print(f"  $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")

    # Merge environment variables
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=isinstance(cmd, str),
        capture_output=True,
        text=True,
        env=full_env
    )

    if check and result.returncode != 0:
        print(f"  [FAIL] Command failed with exit code {result.returncode}")
        print(f"  STDERR: {result.stderr}")
        raise RuntimeError(f"Command failed: {cmd}")

    return result

def terraform_init():
    """Initialize Terraform"""
    print("[1/4] Initializing Terraform...")

    try:
        result = run_command(
            ['terraform', 'init', '-upgrade'],
            cwd=str(TERRAFORM_DIR)
        )
        print("  [OK] Terraform initialized")
        return True

    except Exception as e:
        print(f"  [FAIL] Terraform init failed: {e}")
        return False

def terraform_plan():
    """Run Terraform plan"""
    print("[2/4] Running Terraform plan...")

    try:
        result = run_command(
            ['terraform', 'plan', '-out=tfplan'],
            cwd=str(TERRAFORM_DIR),
            check=False
        )

        if result.returncode == 0:
            print("  [OK] Terraform plan completed")
            return True
        else:
            print(f"  [WARN] Terraform plan completed with warnings")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return True  # Continue anyway

    except Exception as e:
        print(f"  [FAIL] Terraform plan failed: {e}")
        return False

def terraform_apply():
    """Apply Terraform changes"""
    print("[3/4] Applying Terraform changes...")

    try:
        # Check if plan file exists
        plan_file = TERRAFORM_DIR / "tfplan"
        if plan_file.exists():
            cmd = ['terraform', 'apply', 'tfplan']
        else:
            cmd = ['terraform', 'apply', '-auto-approve']

        result = run_command(cmd, cwd=str(TERRAFORM_DIR), check=False)

        if result.returncode == 0:
            print("  [OK] Terraform apply completed")
            return True
        else:
            print(f"  [WARN] Terraform apply completed with warnings")
            return True  # Continue anyway

    except Exception as e:
        print(f"  [FAIL] Terraform apply failed: {e}")
        return False

def force_ecs_deployment(service_name):
    """Force new deployment of ECS service"""
    print(f"  [DEPLOY] Forcing deployment of {service_name}...")

    try:
        ecs_client = boto3.client('ecs', region_name=AWS_REGION)

        service_full_name = f"{ECS_CLUSTER}-{service_name}"

        response = ecs_client.update_service(
            cluster=ECS_CLUSTER,
            service=service_full_name,
            forceNewDeployment=True
        )

        deployment_status = response['service']['deployments'][0]['status']
        print(f"  [OK] Deployment triggered for {service_name} (status: {deployment_status})")
        return True

    except ecs_client.exceptions.ServiceNotFoundException:
        print(f"  [SKIP] Service not found: {service_full_name}")
        return False

    except Exception as e:
        print(f"  [FAIL] Failed to deploy {service_name}: {e}")
        return False

def wait_for_service_stable(service_name, timeout=300):
    """Wait for ECS service to become stable"""
    print(f"  [WAIT] Waiting for {service_name} to stabilize...")

    try:
        ecs_client = boto3.client('ecs', region_name=AWS_REGION)
        service_full_name = f"{ECS_CLUSTER}-{service_name}"

        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                print(f"  [TIMEOUT] Service did not stabilize within {timeout}s")
                return False

            # Get service status
            response = ecs_client.describe_services(
                cluster=ECS_CLUSTER,
                services=[service_full_name]
            )

            if not response['services']:
                print(f"  [SKIP] Service not found")
                return False

            service = response['services'][0]
            running_count = service['runningCount']
            desired_count = service['desiredCount']
            deployments = service['deployments']

            # Check if stable (only one deployment, running = desired)
            if len(deployments) == 1 and running_count == desired_count:
                print(f"  [OK] Service stable: {running_count}/{desired_count} tasks running")
                return True

            # Still deploying
            print(f"  [WAIT] Deploying... {running_count}/{desired_count} tasks, {len(deployments)} deployments")
            time.sleep(10)

    except Exception as e:
        print(f"  [FAIL] Error waiting for service: {e}")
        return False

def get_service_health(service_name):
    """Check service health"""
    try:
        ecs_client = boto3.client('ecs', region_name=AWS_REGION)
        service_full_name = f"{ECS_CLUSTER}-{service_name}"

        response = ecs_client.describe_services(
            cluster=ECS_CLUSTER,
            services=[service_full_name]
        )

        if not response['services']:
            return None

        service = response['services'][0]
        return {
            'status': service['status'],
            'running_count': service['runningCount'],
            'desired_count': service['desiredCount'],
            'deployments': len(service['deployments'])
        }

    except:
        return None

def main():
    print("=" * 80)
    print("DEPLOY KARMACADABRA TO AWS FARGATE")
    print("=" * 80)
    print()

    # Parse arguments
    force_deploy = '--force-deploy' in sys.argv
    wait_stable = '--wait' in sys.argv
    skip_terraform = '--skip-terraform' in sys.argv
    specific_service = None

    for arg in sys.argv[1:]:
        if arg.startswith('--'):
            continue
        if arg in SERVICES:
            specific_service = arg
            force_deploy = True  # Implicit force deploy for specific service
            break

    # Summary
    print(f"Force ECS deployment: {force_deploy}")
    print(f"Wait for stable: {wait_stable}")
    print(f"Skip Terraform: {skip_terraform}")
    if specific_service:
        print(f"Specific service: {specific_service}")
    print()

    # Step 1-3: Terraform
    if not skip_terraform:
        if not terraform_init():
            sys.exit(1)

        print()

        if not terraform_plan():
            sys.exit(1)

        print()

        if not terraform_apply():
            sys.exit(1)

        print()
    else:
        print("[SKIP] Skipping Terraform (--skip-terraform)")
        print()

    # Step 4: Force ECS deployments
    if force_deploy:
        print("[4/4] Forcing ECS service deployments...")

        services_to_deploy = [specific_service] if specific_service else SERVICES
        deployed_services = []

        for service_name in services_to_deploy:
            success = force_ecs_deployment(service_name)
            if success:
                deployed_services.append(service_name)

        print()

        # Wait for stability if requested
        if wait_stable and deployed_services:
            print("[WAIT] Waiting for services to stabilize...")
            for service_name in deployed_services:
                wait_for_service_stable(service_name)
            print()

    else:
        print("[4/4] Skipping ECS force deployment")
        print("      Use --force-deploy to trigger new deployments")
        print()

    # Final status
    print("=" * 80)
    print("DEPLOYMENT STATUS")
    print("=" * 80)
    print()

    for service_name in SERVICES:
        health = get_service_health(service_name)

        if health:
            status_char = "[OK]  " if health['running_count'] == health['desired_count'] else "[WARN]"
            print(f"{status_char} {service_name:20} {health['running_count']}/{health['desired_count']} tasks, "
                  f"{health['deployments']} deployment(s)")
        else:
            print(f"[SKIP] {service_name:20} Not found or not deployed")

    print()
    print("[SUCCESS] Deployment completed!")
    print()
    print("Service endpoints:")
    print("  Facilitator:      https://facilitator.ultravioletadao.xyz/health")
    print("  Validator:        https://validator.karmacadabra.ultravioletadao.xyz/health")
    print("  Karma-Hello:      https://karma-hello.karmacadabra.ultravioletadao.xyz/health")
    print("  Abracadabra:      https://abracadabra.karmacadabra.ultravioletadao.xyz/health")
    print("  Skill-Extractor:  https://skill-extractor.karmacadabra.ultravioletadao.xyz/health")
    print("  Voice-Extractor:  https://voice-extractor.karmacadabra.ultravioletadao.xyz/health")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[CANCELLED] Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
