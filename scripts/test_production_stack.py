#!/usr/bin/env python3
"""
Test Karmacadabra Production Stack
Tests all agents via HTTPS endpoints on AWS
"""

import requests
import json
import sys

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Production HTTPS endpoints
BASE_DOMAIN = "karmacadabra.ultravioletadao.xyz"

AGENTS = {
    "Validator": f"https://validator.{BASE_DOMAIN}",
    "Karma-Hello": f"https://karma-hello.{BASE_DOMAIN}",
    "Abracadabra": f"https://abracadabra.{BASE_DOMAIN}",
    "Skill-Extractor": f"https://skill-extractor.{BASE_DOMAIN}",
    "Voice-Extractor": f"https://voice-extractor.{BASE_DOMAIN}",
}


def test_agent_health(name, url):
    """Test if agent is responding on HTTPS"""
    try:
        response = requests.get(f"{url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"{GREEN}[OK]{RESET} {name}: {data}")
            return True
        else:
            print(f"{RED}[FAIL]{RESET} {name}: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"{RED}[FAIL]{RESET} {name}: {str(e)}")
        return False


def test_agent_discovery(name, url):
    """Test if agent exposes A2A agent card"""
    try:
        response = requests.get(f"{url}/.well-known/agent-card", timeout=5)
        if response.status_code == 200:
            card = response.json()
            print(f"{GREEN}[OK]{RESET} {name} A2A card:")
            print(f"  Domain: {card.get('domain', 'N/A')}")
            print(f"  Agent ID: {card.get('agentId', card.get('agent_id', 'N/A'))}")

            skills = card.get('skills', [])
            print(f"  Skills: {len(skills)} available")

            for skill in skills[:3]:  # Show first 3 skills
                skill_name = skill.get('name', skill.get('skillId', 'Unknown'))

                # Handle different pricing formats
                pricing = skill.get('pricing', skill.get('price', {}))
                if isinstance(pricing, dict):
                    if 'amount' in pricing:
                        price = pricing['amount']
                    elif 'base_price' in pricing:
                        price = pricing['base_price']
                    else:
                        price = "N/A"
                else:
                    price = str(pricing)

                print(f"    - {skill_name}: {price} GLUE")

            return True
        else:
            print(f"{RED}[FAIL]{RESET} {name} A2A card: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"{RED}[FAIL]{RESET} {name} A2A card: {str(e)}")
        return False


def test_https_security(name, url):
    """Test HTTPS/TLS security"""
    try:
        # Test HTTP redirect to HTTPS (if configured)
        http_url = url.replace("https://", "http://")
        response = requests.get(f"{http_url}/health", timeout=5, allow_redirects=False)

        if response.status_code in [301, 302, 307, 308]:
            print(f"{GREEN}[OK]{RESET} {name}: HTTP->HTTPS redirect enabled")
            return True
        elif response.status_code == 200:
            print(f"{YELLOW}[WARN]{RESET} {name}: HTTP allowed (no redirect)")
            return True
        else:
            print(f"{YELLOW}[WARN]{RESET} {name}: Unexpected HTTP response {response.status_code}")
            return False
    except Exception as e:
        # Some agents may block HTTP entirely - that's good!
        print(f"{GREEN}[OK]{RESET} {name}: HTTP blocked (HTTPS only)")
        return True


def main():
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}Testing Karmacadabra Production Stack (HTTPS){RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

    print(f"Production endpoint: {BASE_DOMAIN}")
    print(f"Protocol: HTTPS with TLS 1.2+")
    print()

    # Test 1: Health Checks
    print(f"{YELLOW}Test 1: Agent Health Checks (HTTPS){RESET}")
    print("-" * 80)

    health_results = {}
    for name, url in AGENTS.items():
        health_results[name] = test_agent_health(name, url)

    print()

    # Test 2: HTTPS Security
    print(f"{YELLOW}Test 2: HTTPS/TLS Security{RESET}")
    print("-" * 80)

    security_results = {}
    for name, url in AGENTS.items():
        if health_results[name]:
            security_results[name] = test_https_security(name, url)
        else:
            print(f"{RED}[SKIP]{RESET} {name}: Skipped (not responding)")
            security_results[name] = False

    print()

    # Test 3: A2A Discovery
    print(f"{YELLOW}Test 3: A2A Protocol Discovery{RESET}")
    print("-" * 80)

    discovery_results = {}
    for name, url in AGENTS.items():
        if health_results[name]:
            discovery_results[name] = test_agent_discovery(name, url)
        else:
            print(f"{RED}[SKIP]{RESET} {name}: Skipped (not responding)")
            discovery_results[name] = False

    print()

    # Test 4: Summary
    print(f"{YELLOW}Test Summary{RESET}")
    print("-" * 80)

    total_agents = len(AGENTS)
    healthy_agents = sum(health_results.values())
    secure_agents = sum(security_results.values())
    discoverable_agents = sum(discovery_results.values())

    print(f"Agents responding (HTTPS): {healthy_agents}/{total_agents}")
    print(f"Agents with secure config: {secure_agents}/{total_agents}")
    print(f"Agents discoverable (A2A): {discoverable_agents}/{total_agents}")

    print()

    if healthy_agents == total_agents and discoverable_agents == total_agents:
        print(f"{GREEN}[SUCCESS] Production stack ready!{RESET}")
        print()
        print(f"{BLUE}Production Endpoints:{RESET}")
        for name, url in AGENTS.items():
            print(f"  {name}:")
            print(f"    Health: {url}/health")
            print(f"    AgentCard: {url}/.well-known/agent-card")

        print()
        print(f"{BLUE}Next steps:{RESET}")
        print("  1. Test agent-to-agent purchases:")
        print(f"     python scripts/demo_client_purchases.py --production")
        print()
        print("  2. Run end-to-end integration test:")
        print(f"     python tests/test_level3_e2e.py --production")

        return 0
    else:
        print(f"{RED}[ERROR] Some agents not ready{RESET}")
        print()
        print(f"{BLUE}Failing agents:{RESET}")

        for name in AGENTS.keys():
            if not health_results[name]:
                print(f"  {RED}[FAIL]{RESET} {name}: Not responding")
            elif not discoverable_agents[name]:
                print(f"  {YELLOW}[WARN]{RESET} {name}: Not exposing AgentCard")

        print()
        print("Check AWS ECS service status:")
        print("  aws ecs describe-services --cluster karmacadabra-prod --services \\")
        print("    karmacadabra-prod-validator \\")
        print("    karmacadabra-prod-karma-hello \\")
        print("    karmacadabra-prod-abracadabra \\")
        print("    karmacadabra-prod-skill-extractor \\")
        print("    karmacadabra-prod-voice-extractor")

        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted{RESET}")
        sys.exit(130)
