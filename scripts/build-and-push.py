#!/usr/bin/env python3
"""
Build and Push Docker Images to ECR
Fully idempotent - checks if images exist, rebuilds if needed, pushes to ECR

Usage:
    python scripts/build-and-push.py                    # Build all agents
    python scripts/build-and-push.py facilitator       # Build specific agent
    python scripts/build-and-push.py --force           # Force rebuild all
"""

import os
import sys
import subprocess
import json
import boto3
from pathlib import Path

# Configuration
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "518898403364"
ECR_REGISTRY = f"{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com"
PROJECT_ROOT = Path(__file__).parent.parent

# Agent configurations
AGENTS = {
    'facilitator': {
        'context': 'x402-rs',
        'dockerfile': 'Dockerfile',
        'use_prebuilt': True,  # Use ukstv/x402-facilitator:latest
        'prebuilt_image': 'ukstv/x402-facilitator:latest',
        'platform': 'linux/amd64'
    },
    'validator': {
        'context': '.',
        'dockerfile': 'validator/Dockerfile',
        'platform': 'linux/amd64'
    },
    'karma-hello': {
        'context': '.',
        'dockerfile': 'karma-hello-agent/Dockerfile',
        'platform': 'linux/amd64'
    },
    'abracadabra': {
        'context': '.',
        'dockerfile': 'abracadabra-agent/Dockerfile',
        'platform': 'linux/amd64'
    },
    'skill-extractor': {
        'context': '.',
        'dockerfile': 'skill-extractor-agent/Dockerfile',
        'platform': 'linux/amd64'
    },
    'voice-extractor': {
        'context': '.',
        'dockerfile': 'voice-extractor-agent/Dockerfile',
        'platform': 'linux/amd64'
    }
}

def run_command(cmd, cwd=None, check=True):
    """Run shell command and return output"""
    print(f"  $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=isinstance(cmd, str),
        capture_output=True,
        text=True
    )

    if check and result.returncode != 0:
        print(f"  [FAIL] Command failed with exit code {result.returncode}")
        print(f"  STDERR: {result.stderr}")
        raise RuntimeError(f"Command failed: {cmd}")

    return result

def ecr_login():
    """Login to ECR"""
    print("[1/5] Logging into ECR...")
    try:
        # Get ECR login password
        ecr_client = boto3.client('ecr', region_name=AWS_REGION)
        response = ecr_client.get_authorization_token()
        token = response['authorizationData'][0]['authorizationToken']

        # Decode token (format: AWS:password)
        import base64
        username, password = base64.b64decode(token).decode('utf-8').split(':')

        # Docker login
        cmd = f'echo {password} | docker login --username {username} --password-stdin {ECR_REGISTRY}'
        result = run_command(cmd, check=False)

        if result.returncode == 0:
            print(f"  [OK] Logged into ECR: {ECR_REGISTRY}")
            return True
        else:
            print(f"  [FAIL] ECR login failed")
            return False

    except Exception as e:
        print(f"  [FAIL] ECR login error: {e}")
        return False

def ensure_ecr_repository(agent_name):
    """Ensure ECR repository exists for agent"""
    repo_name = f"karmacadabra/{agent_name}"

    try:
        ecr_client = boto3.client('ecr', region_name=AWS_REGION)

        # Try to describe repository
        try:
            ecr_client.describe_repositories(repositoryNames=[repo_name])
            print(f"  [OK] ECR repository exists: {repo_name}")
            return True

        except ecr_client.exceptions.RepositoryNotFoundException:
            # Create repository
            print(f"  [CREATE] Creating ECR repository: {repo_name}")
            ecr_client.create_repository(
                repositoryName=repo_name,
                imageScanningConfiguration={'scanOnPush': True},
                encryptionConfiguration={'encryptionType': 'AES256'}
            )
            print(f"  [OK] Created ECR repository: {repo_name}")
            return True

    except Exception as e:
        print(f"  [FAIL] ECR repository error: {e}")
        return False

def build_image(agent_name, config, force=False):
    """Build Docker image for agent"""
    print(f"\n[BUILD] {agent_name}")

    # Check if using prebuilt image
    if config.get('use_prebuilt'):
        print(f"  [PREBUILT] Using prebuilt image: {config['prebuilt_image']}")

        # Pull prebuilt image
        cmd = ['docker', 'pull', config['prebuilt_image']]
        try:
            run_command(cmd)
            print(f"  [OK] Pulled prebuilt image")
            return config['prebuilt_image']
        except:
            print(f"  [FAIL] Failed to pull prebuilt image")
            return None

    # Build from source
    context_path = PROJECT_ROOT / config['context']
    dockerfile_path = PROJECT_ROOT / config['dockerfile']

    if not dockerfile_path.exists():
        print(f"  [SKIP] Dockerfile not found: {dockerfile_path}")
        return None

    # Build command
    image_tag = f"karmacadabra/{agent_name}:latest"
    cmd = [
        'docker', 'build',
        '--platform', config.get('platform', 'linux/amd64'),
        '-f', str(dockerfile_path),
        '-t', image_tag,
        str(context_path)
    ]

    if force:
        cmd.insert(2, '--no-cache')

    try:
        run_command(cmd, cwd=str(PROJECT_ROOT))
        print(f"  [OK] Built image: {image_tag}")
        return image_tag

    except Exception as e:
        print(f"  [FAIL] Build failed: {e}")
        return None

def push_image(agent_name, local_image):
    """Push image to ECR"""
    if not local_image:
        return False

    print(f"  [PUSH] Pushing to ECR...")

    # Tag for ECR
    ecr_image = f"{ECR_REGISTRY}/karmacadabra/{agent_name}:latest"

    # Tag image
    try:
        run_command(['docker', 'tag', local_image, ecr_image])
        print(f"  [OK] Tagged: {ecr_image}")
    except:
        print(f"  [FAIL] Failed to tag image")
        return False

    # Push to ECR
    try:
        run_command(['docker', 'push', ecr_image])
        print(f"  [OK] Pushed to ECR: {ecr_image}")
        return True
    except:
        print(f"  [FAIL] Failed to push to ECR")
        return False

def main():
    print("=" * 80)
    print("BUILD AND PUSH DOCKER IMAGES TO ECR")
    print("=" * 80)
    print()

    # Parse arguments
    force_rebuild = '--force' in sys.argv
    specific_agent = None

    for arg in sys.argv[1:]:
        if arg.startswith('--'):
            continue
        if arg in AGENTS:
            specific_agent = arg
            break

    # Filter agents to build
    agents_to_build = {specific_agent: AGENTS[specific_agent]} if specific_agent else AGENTS

    print(f"Agents to build: {', '.join(agents_to_build.keys())}")
    print(f"Force rebuild: {force_rebuild}")
    print()

    # Step 1: ECR Login
    if not ecr_login():
        print("[FAIL] ECR login failed. Cannot proceed.")
        sys.exit(1)

    print()

    # Step 2: Ensure ECR repositories exist
    print("[2/5] Ensuring ECR repositories exist...")
    for agent_name in agents_to_build.keys():
        ensure_ecr_repository(agent_name)

    print()

    # Step 3: Build images
    print("[3/5] Building Docker images...")
    built_images = {}

    for agent_name, config in agents_to_build.items():
        local_image = build_image(agent_name, config, force=force_rebuild)
        built_images[agent_name] = local_image

    print()

    # Step 4: Push images
    print("[4/5] Pushing images to ECR...")
    pushed_images = {}

    for agent_name, local_image in built_images.items():
        success = push_image(agent_name, local_image)
        pushed_images[agent_name] = success

    print()

    # Step 5: Summary
    print("[5/5] Summary")
    print("=" * 80)

    successful = [name for name, success in pushed_images.items() if success]
    failed = [name for name, success in pushed_images.items() if not success]

    print(f"\n[OK]   Successfully pushed: {len(successful)}/{len(agents_to_build)}")
    for name in successful:
        print(f"       - {name}")

    if failed:
        print(f"\n[FAIL] Failed: {len(failed)}/{len(agents_to_build)}")
        for name in failed:
            print(f"       - {name}")

    print()

    if failed:
        print("[WARN] Some images failed to build/push. Review errors above.")
        sys.exit(1)

    print("[SUCCESS] All images built and pushed successfully!")
    print()
    print("Next steps:")
    print("1. Deploy to Fargate: python scripts/deploy-to-fargate.py")
    print("2. Force ECS service update: python scripts/deploy-to-fargate.py --force-deploy")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[CANCELLED] Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
