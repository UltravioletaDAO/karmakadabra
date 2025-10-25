#!/usr/bin/env python3
"""
Show Marketplace Overview
Displays what's deployed without starting any agents

Usage:
    python show_marketplace.py              # Show all agents
    python show_marketplace.py --top 10     # Show top 10 by engagement
    python show_marketplace.py --services   # Show all services
"""

import json
import sys
from pathlib import Path
from collections import Counter
import argparse

# Fix Windows encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


def load_profiles():
    """Load all user profiles"""
    base_dir = Path(__file__).parent.parent.parent  # demo/scripts/ -> demo/ -> root
    profiles_dir = base_dir / "demo/profiles"

    profiles = []
    for profile_file in profiles_dir.glob("*.json"):
        with open(profile_file, 'r', encoding='utf-8') as f:
            profile = json.load(f)
            profile['_username'] = profile_file.stem
            profiles.append(profile)

    return profiles


def load_agent_cards():
    """Load all agent cards"""
    base_dir = Path(__file__).parent.parent.parent  # demo/scripts/ -> demo/ -> root
    cards_dir = base_dir / "demo/cards"

    cards = []
    for card_file in cards_dir.glob("*.json"):
        with open(card_file, 'r', encoding='utf-8') as f:
            card = json.load(f)
            card['_username'] = card_file.stem
            cards.append(card)

    return cards


def show_overview():
    """Show marketplace overview"""
    print("=" * 80)
    print("Karmacadabra Marketplace - Overview")
    print("=" * 80)
    print()

    profiles = load_profiles()
    cards = load_agent_cards()

    print(f"📊 Total Agents: {len(profiles)}")
    print(f"🃏 Agent Cards: {len(cards)}")
    print()

    # Engagement distribution
    engagement_counts = Counter()
    for profile in profiles:
        level = profile.get("interaction_style", {}).get("engagement_level", "unknown")
        engagement_counts[level] += 1

    print("Engagement Levels:")
    for level, count in engagement_counts.most_common():
        print(f"  {level.title()}: {count} agents")
    print()

    # Service type distribution
    service_types = Counter()
    for card in cards:
        for service in card.get("services", []):
            service_name = service.get("name", "Unknown")
            service_types[service_name] += 1

    print("Top Services Offered:")
    for service, count in service_types.most_common(10):
        print(f"  {service}: {count} agents")
    print()

    # Network math
    n = len(profiles)
    potential_trades = n * (n - 1)
    print(f"🕸️  Network Capacity: {potential_trades:,} potential trades")
    print()


def show_top_agents(limit=10):
    """Show top agents by engagement"""
    print("=" * 80)
    print(f"Top {limit} Agents by Engagement")
    print("=" * 80)
    print()

    profiles = load_profiles()

    # Sort by message count
    sorted_profiles = sorted(
        profiles,
        key=lambda p: p.get("interaction_style", {}).get("message_count", 0),
        reverse=True
    )[:limit]

    print(f"{'Rank':<6} {'Username':<20} {'Messages':<10} {'Level':<12} {'Top Skill':<20}")
    print("-" * 80)

    for idx, profile in enumerate(sorted_profiles, 1):
        username = profile['_username']
        msg_count = profile.get("interaction_style", {}).get("message_count", 0)
        level = profile.get("interaction_style", {}).get("engagement_level", "unknown")

        skills = profile.get("skills", [])
        top_skill = skills[0]['skill'] if skills else "N/A"

        print(f"{idx:<6} @{username:<19} {msg_count:<10} {level.title():<12} {top_skill:<20}")

    print()


def show_all_services():
    """Show all available services"""
    print("=" * 80)
    print("All Available Services")
    print("=" * 80)
    print()

    cards = load_agent_cards()

    # Group services by agent
    for card in sorted(cards, key=lambda c: c['_username']):
        username = card['_username']
        services = card.get("services", [])

        if not services:
            continue

        print(f"\n@{username} ({len(services)} services):")
        print("-" * 60)

        for svc in services:
            pricing = svc.get("pricing", {})
            price = f"{pricing.get('amount', '?')} {pricing.get('currency', 'GLUE')}"
            confidence = svc.get("confidence", 0)

            print(f"  • {svc['name']}")
            print(f"    ID: {svc['id']}")
            print(f"    Price: {price} {pricing.get('unit', '')}")
            print(f"    Confidence: {confidence:.2f}")
            print(f"    Description: {svc.get('description', 'N/A')}")
            print()


def show_agent_detail(username):
    """Show detailed info for a specific agent"""
    base_dir = Path(__file__).parent.parent.parent  # demo/scripts/ -> demo/ -> root

    # Load profile
    profile_path = base_dir / "demo/profiles" / f"{username}.json"
    if not profile_path.exists():
        print(f"❌ Agent not found: {username}")
        return

    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)

    # Load card
    card_path = base_dir / "demo/cards" / f"{username}.json"
    with open(card_path, 'r', encoding='utf-8') as f:
        card = json.load(f)

    print("=" * 80)
    print(f"Agent Details: @{username}")
    print("=" * 80)
    print()

    # Profile info
    print("📊 Profile:")
    print(f"  User ID: {profile['user_id']}")
    print(f"  Messages: {profile['interaction_style']['message_count']}")
    print(f"  Engagement: {profile['interaction_style']['engagement_level']}")
    print(f"  Confidence: {profile['data_coverage']['confidence_level']:.2f}")
    print()

    # Interests
    print("🎯 Interests:")
    for interest in profile.get('interests', [])[:5]:
        print(f"  • {interest['domain']} (score: {interest['score']:.2f})")
    print()

    # Skills
    print("💪 Skills:")
    for skill in profile.get('skills', [])[:5]:
        print(f"  • {skill['skill']} (score: {skill['score']:.2f})")
    print()

    # Services
    print("🛒 Services Offered:")
    for svc in card.get('services', []):
        pricing = svc.get('pricing', {})
        price = f"{pricing.get('amount', '?')} {pricing.get('currency', 'GLUE')}"
        print(f"  • {svc['name']}: {price} {pricing.get('unit', '')}")
        print(f"    {svc.get('description', '')}")
    print()

    # Agent card
    print("🃏 Agent Card:")
    print(f"  Endpoint: {card['contact']['endpoint']}")
    print(f"  Health: {card['contact']['health_check']}")
    print(f"  Protocols: {', '.join(card['capabilities']['protocols'])}")
    print(f"  Payment: {', '.join(card['capabilities']['payment_methods'])}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Show Karmacadabra Marketplace")
    parser.add_argument("--top", type=int, help="Show top N agents by engagement")
    parser.add_argument("--services", action="store_true", help="Show all services")
    parser.add_argument("--agent", type=str, help="Show detail for specific agent")

    args = parser.parse_args()

    if args.agent:
        show_agent_detail(args.agent)
    elif args.top:
        show_top_agents(args.top)
    elif args.services:
        show_all_services()
    else:
        show_overview()


if __name__ == "__main__":
    main()
