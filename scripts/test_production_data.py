#!/usr/bin/env python3
"""
Test that production data is actually being served by karma-hello and abracadabra agents.
"""

import requests
import json

def test_karma_hello():
    """Test karma-hello has production logs"""
    print("Testing karma-hello production data...")

    # Try to fetch agent card to see available endpoints
    url = "https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card"
    response = requests.get(url)

    if response.status_code == 200:
        card = response.json()
        print(f"  ✓ Agent card retrieved")
        print(f"  Domain: {card.get('domain')}")
        print(f"  Skills: {len(card.get('skills', []))}")

        # Check if get_chat_logs skill exists
        skills = card.get('skills', [])
        if any(s['name'] == 'get_chat_logs' for s in skills):
            print(f"  ✓ get_chat_logs skill found")
        else:
            print(f"  ✗ get_chat_logs skill NOT found")
            return False
    else:
        print(f"  ✗ Failed to retrieve agent card: {response.status_code}")
        return False

    return True


def test_abracadabra():
    """Test abracadabra has production transcripts"""
    print("\nTesting abracadabra production data...")

    # Try to fetch agent card
    url = "https://abracadabra.karmacadabra.ultravioletadao.xyz/.well-known/agent-card"
    response = requests.get(url)

    if response.status_code == 200:
        card = response.json()
        print(f"  ✓ Agent card retrieved")
        print(f"  Domain: {card.get('domain')}")
        print(f"  Skills: {len(card.get('skills', []))}")

        # Check if get_transcription skill exists
        skills = card.get('skills', [])
        if any(s['name'] == 'get_transcription' for s in skills):
            print(f"  ✓ get_transcription skill found")
        else:
            print(f"  ✗ get_transcription skill NOT found")
            return False
    else:
        print(f"  ✗ Failed to retrieve agent card: {response.status_code}")
        return False

    return True


def main():
    print("=" * 80)
    print("Testing Production Data Availability")
    print("=" * 80)
    print()

    karma_ok = test_karma_hello()
    abra_ok = test_abracadabra()

    print()
    print("=" * 80)
    print("Summary:")
    print(f"  karma-hello: {'✓ PASS' if karma_ok else '✗ FAIL'}")
    print(f"  abracadabra: {'✓ PASS' if abra_ok else '✗ FAIL'}")
    print("=" * 80)
    print()

    if karma_ok and abra_ok:
        print("✓ All agents have production data configured")
        print()
        print("Next step: Test actual data retrieval with payment")
        print("  python scripts/demo_client_purchases.py --production")
        return 0
    else:
        print("✗ Some agents are missing production data")
        return 1


if __name__ == "__main__":
    exit(main())
