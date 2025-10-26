#!/usr/bin/env python3
"""
Test Client Agent Flow
Tests the complete buyer+seller pattern with running agents
"""

import requests
import json
import sys
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def test_agent_health(name, port):
    """Test if agent is responding on its port"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        if response.status_code == 200:
            print(f"{GREEN}✓{RESET} {name} (port {port}): {response.json()}")
            return True
        else:
            print(f"{RED}✗{RESET} {name} (port {port}): HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"{RED}✗{RESET} {name} (port {port}): {str(e)}")
        return False

def test_agent_discovery(name, port):
    """Test if agent exposes A2A agent card"""
    try:
        response = requests.get(f"http://localhost:{port}/.well-known/agent-card", timeout=2)
        if response.status_code == 200:
            card = response.json()
            print(f"{GREEN}✓{RESET} {name} A2A card:")
            print(f"  Domain: {card.get('domain', 'N/A')}")
            print(f"  Skills: {len(card.get('skills', []))} available")
            if card.get('skills'):
                for skill in card['skills']:
                    print(f"    - {skill.get('name')}: {skill.get('pricing', {}).get('amount')} GLUE")
            return True
        else:
            print(f"{RED}✗{RESET} {name} A2A card: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"{RED}✗{RESET} {name} A2A card: {str(e)}")
        return False

def main():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}Testing Karmacadabra Agent Stack{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

    # Test 1: Health Checks
    print(f"{YELLOW}Test 1: Agent Health Checks{RESET}")
    print("-" * 70)

    agents = [
        ("Karma-Hello", 9002),
        ("Abracadabra", 9003),
        ("Skill-Extractor", 9004),
        ("Voice-Extractor", 9005),
        ("Validator", 9001),
    ]

    health_results = {}
    for name, port in agents:
        health_results[name] = test_agent_health(name, port)

    print()

    # Test 2: A2A Discovery
    print(f"{YELLOW}Test 2: A2A Protocol Discovery{RESET}")
    print("-" * 70)

    discovery_results = {}
    for name, port in agents:
        if health_results[name]:  # Only test discovery if health passed
            discovery_results[name] = test_agent_discovery(name, port)
        else:
            print(f"{RED}⊘{RESET} {name}: Skipped (not responding)")
            discovery_results[name] = False

    print()

    # Test 3: Summary
    print(f"{YELLOW}Test Summary{RESET}")
    print("-" * 70)

    total_agents = len(agents)
    healthy_agents = sum(health_results.values())
    discoverable_agents = sum(discovery_results.values())

    print(f"Agents responding: {healthy_agents}/{total_agents}")
    print(f"Agents discoverable: {discoverable_agents}/{total_agents}")

    print()

    if healthy_agents == total_agents and discoverable_agents == total_agents:
        print(f"{GREEN}✓ All agents ready!{RESET}")
        print(f"\n{BLUE}Next steps:{RESET}")
        print("  1. Run client agent:")
        print(f"     cd client-agents/template && python main.py")
        print()
        print("  2. Test agent-to-agent purchases:")
        print(f"     python main.py --buy-skills --user 0xultravioleta")
        print(f"     python main.py --buy-voice --user 0xultravioleta")
        return 0
    else:
        print(f"{RED}✗ Some agents not ready{RESET}")
        print(f"\n{BLUE}To start missing agents:{RESET}")

        for name, port in agents:
            if not health_results[name]:
                agent_dir = name.lower().replace("-", "_")
                if name == "Validator":
                    agent_dir = "validator"
                elif name == "Karma-Hello":
                    agent_dir = "karma-hello"
                elif name == "Abracadabra":
                    agent_dir = "abracadabra"
                elif name == "Skill-Extractor":
                    agent_dir = "skill-extractor"
                elif name == "Voice-Extractor":
                    agent_dir = "voice-extractor"

                print(f"  {name}:")
                print(f"    cd agents/{agent_dir}")
                print(f"    python main.py")
                print()

        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted{RESET}")
        sys.exit(130)
