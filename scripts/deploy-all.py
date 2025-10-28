#!/usr/bin/env python3
"""
Master Deployment Script for Karmacadabra
Orchestrates the complete deployment pipeline:
1. Fund wallets
2. Build and push Docker images
3. Deploy to Fargate
4. Verify health

Fully idempotent - safe to run multiple times

Usage:
    python scripts/deploy-all.py                    # Full deployment
    python scripts/deploy-all.py --skip-build       # Skip Docker build
    python scripts/deploy-all.py --skip-fund        # Skip wallet funding
    python scripts/deploy-all.py --force-rebuild    # Force Docker rebuild
"""

import os
import sys
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

def run_script(script_name, args=None, check=True):
    """Run a Python script"""
    args = args or []

    cmd = ['python', str(SCRIPTS_DIR / script_name)] + args

    print(f"\n{'=' * 80}")
    print(f"RUNNING: {script_name}")
    print(f"{'=' * 80}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if check and result.returncode != 0:
        print(f"\n[FAIL] {script_name} failed with exit code {result.returncode}")
        return False

    return True

def check_prerequisites():
    """Check if required tools are installed"""
    print("=" * 80)
    print("CHECKING PREREQUISITES")
    print("=" * 80)
    print()

    required_tools = {
        'python': ['python', '--version'],
        'docker': ['docker', '--version'],
        'aws': ['aws', '--version'],
        'terraform': ['terraform', '--version']
    }

    all_ok = True

    for tool, cmd in required_tools.items():
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                print(f"  [OK] {tool:12} {version}")
            else:
                print(f"  [FAIL] {tool:12} Not working")
                all_ok = False

        except FileNotFoundError:
            print(f"  [FAIL] {tool:12} Not installed")
            all_ok = False

    print()

    if not all_ok:
        print("[FAIL] Prerequisites check failed. Install missing tools.")
        return False

    print("[OK] All prerequisites satisfied")
    return True

def verify_health():
    """Verify all services are healthy"""
    print("\n" + "=" * 80)
    print("VERIFYING SERVICE HEALTH")
    print("=" * 80)
    print()

    import time
    import requests

    endpoints = {
        'Facilitator': 'https://facilitator.ultravioletadao.xyz/health',
        'Validator': 'https://validator.karmacadabra.ultravioletadao.xyz/health',
        'Karma-Hello': 'https://karma-hello.karmacadabra.ultravioletadao.xyz/health',
        'Abracadabra': 'https://abracadabra.karmacadabra.ultravioletadao.xyz/health',
        'Skill-Extractor': 'https://skill-extractor.karmacadabra.ultravioletadao.xyz/health',
        'Voice-Extractor': 'https://voice-extractor.karmacadabra.ultravioletadao.xyz/health'
    }

    print("Waiting 30 seconds for services to start...")
    time.sleep(30)
    print()

    all_healthy = True

    for service, url in endpoints.items():
        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                print(f"  [OK]   {service:20} {url}")
            else:
                print(f"  [WARN] {service:20} Status {response.status_code}")
                all_healthy = False

        except Exception as e:
            print(f"  [FAIL] {service:20} {str(e)[:50]}")
            all_healthy = False

    print()

    if all_healthy:
        print("[SUCCESS] All services are healthy!")
    else:
        print("[WARN] Some services are not responding. They may still be starting up.")
        print("       Check CloudWatch logs for details.")

    return all_healthy

def main():
    print("=" * 80)
    print("KARMACADABRA MASTER DEPLOYMENT")
    print("=" * 80)
    print()

    # Parse arguments
    skip_fund = '--skip-fund' in sys.argv
    skip_build = '--skip-build' in sys.argv
    force_rebuild = '--force-rebuild' in sys.argv
    skip_health = '--skip-health' in sys.argv

    print("Deployment options:")
    print(f"  Skip funding:        {skip_fund}")
    print(f"  Skip build:          {skip_build}")
    print(f"  Force rebuild:       {force_rebuild}")
    print(f"  Skip health check:   {skip_health}")
    print()

    # Step 0: Prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Step 1: Fund wallets
    if not skip_fund:
        print("\n" + "=" * 80)
        print("STEP 1: FUND WALLETS")
        print("=" * 80)

        if not run_script('fund-wallets.py', ['--confirm'], check=False):
            print("\n[WARN] Wallet funding had warnings. Continuing...")
    else:
        print("\n[SKIP] Skipping wallet funding (--skip-fund)")

    # Step 2: Build and push Docker images
    if not skip_build:
        print("\n" + "=" * 80)
        print("STEP 2: BUILD AND PUSH DOCKER IMAGES")
        print("=" * 80)

        build_args = []
        if force_rebuild:
            build_args.append('--force')

        if not run_script('build-and-push.py', build_args, check=False):
            print("\n[FAIL] Docker build failed. Continuing with deployment...")
            print("       Note: Deployment will use existing images in ECR")
    else:
        print("\n[SKIP] Skipping Docker build (--skip-build)")

    # Step 3: Deploy to Fargate
    print("\n" + "=" * 80)
    print("STEP 3: DEPLOY TO FARGATE")
    print("=" * 80)

    if not run_script('deploy-to-fargate.py', ['--force-deploy']):
        print("\n[FAIL] Deployment failed")
        sys.exit(1)

    # Step 4: Verify health
    if not skip_health:
        verify_health()
    else:
        print("\n[SKIP] Skipping health check (--skip-health)")

    # Summary
    print("\n" + "=" * 80)
    print("DEPLOYMENT COMPLETE")
    print("=" * 80)
    print()
    print("[SUCCESS] Karmacadabra deployed successfully!")
    print()
    print("Next steps:")
    print("1. Monitor CloudWatch logs: aws logs tail /ecs/karmacadabra-prod/facilitator --follow")
    print("2. Test facilitator: curl https://facilitator.ultravioletadao.xyz/supported")
    print("3. Run system tests: python scripts/test_production_stack.py")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
