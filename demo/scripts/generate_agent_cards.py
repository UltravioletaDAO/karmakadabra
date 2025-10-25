"""
Agent Card Auto-Generator
Converts user profiles into A2A protocol Agent Cards

Sprint 3, Task 2: Agent Card auto-generator
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from decimal import Decimal

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


def generate_services_from_profile(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate service offerings based on user profile

    Maps skills/interests to specific sellable services with pricing
    """

    services = []

    # Extract top skills and interests
    skills = profile.get("skills", [])
    interests = profile.get("interests", [])

    # Skill-based services
    for skill in skills[:3]:  # Top 3 skills
        skill_name = skill.get("skill", "")
        skill_score = skill.get("score", 0)

        if not skill_name:
            continue

        # Map skills to service offerings
        service_map = {
            "Python": {
                "name": "Python Development",
                "description": "Python coding assistance, script writing, automation tasks",
                "base_price": "0.05",
                "expertise_multiplier": 1.5
            },
            "JavaScript": {
                "name": "JavaScript Development",
                "description": "JavaScript/TypeScript coding, web development, API integration",
                "base_price": "0.05",
                "expertise_multiplier": 1.5
            },
            "Solidity": {
                "name": "Smart Contract Development",
                "description": "Solidity smart contract development, auditing, and consultation",
                "base_price": "0.15",
                "expertise_multiplier": 2.0
            },
            "Rust": {
                "name": "Rust Development",
                "description": "Rust programming, system-level development, performance optimization",
                "base_price": "0.10",
                "expertise_multiplier": 2.0
            },
            "Data Analysis": {
                "name": "Data Analysis",
                "description": "Data analysis, visualization, SQL queries, statistical insights",
                "base_price": "0.08",
                "expertise_multiplier": 1.5
            },
            "DevOps": {
                "name": "DevOps Services",
                "description": "Infrastructure setup, CI/CD pipelines, cloud deployment",
                "base_price": "0.10",
                "expertise_multiplier": 1.8
            },
            "Content Creation": {
                "name": "Content Creation",
                "description": "Video editing, streaming setup, content strategy",
                "base_price": "0.06",
                "expertise_multiplier": 1.3
            }
        }

        if skill_name in service_map:
            service_config = service_map[skill_name]
            base_price = float(service_config["base_price"])

            # Adjust price based on skill score (higher score = higher price)
            adjusted_price = base_price * (1 + skill_score * service_config["expertise_multiplier"])
            adjusted_price = round(adjusted_price, 2)

            services.append({
                "id": f"{skill_name.lower().replace(' ', '_')}_service",
                "name": service_config["name"],
                "description": service_config["description"],
                "pricing": {
                    "amount": str(adjusted_price),
                    "currency": "GLUE",
                    "unit": "per task"
                },
                "capabilities": [skill_name],
                "confidence": round(skill_score, 2)
            })

    # Interest-based consulting services
    for interest in interests[:2]:  # Top 2 interests
        domain = interest.get("domain", "")
        score = interest.get("score", 0)

        if not domain or score < 0.05:  # Only if significant interest
            continue

        # Map interests to consulting services
        consulting_map = {
            "Blockchain": {
                "name": "Blockchain Consultation",
                "description": "Web3 strategy, blockchain architecture, crypto economics advice",
                "base_price": "0.10"
            },
            "AI/ML": {
                "name": "AI/ML Consultation",
                "description": "Machine learning strategy, model selection, AI implementation advice",
                "base_price": "0.12"
            },
            "Design": {
                "name": "Design Consultation",
                "description": "UI/UX feedback, design reviews, visual strategy",
                "base_price": "0.08"
            },
            "Gaming": {
                "name": "Gaming Consultation",
                "description": "Game design feedback, gaming trends, player engagement strategies",
                "base_price": "0.06"
            },
            "Business": {
                "name": "Business Consultation",
                "description": "Startup advice, market analysis, business strategy",
                "base_price": "0.10"
            }
        }

        if domain in consulting_map:
            consulting_config = consulting_map[domain]
            base_price = float(consulting_config["base_price"])

            # Adjust based on interest score
            adjusted_price = base_price * (1 + score)
            adjusted_price = round(adjusted_price, 2)

            services.append({
                "id": f"{domain.lower().replace('/', '_').replace(' ', '_')}_consulting",
                "name": consulting_config["name"],
                "description": consulting_config["description"],
                "pricing": {
                    "amount": str(adjusted_price),
                    "currency": "GLUE",
                    "unit": "per hour"
                },
                "capabilities": [domain],
                "confidence": round(score, 2)
            })

    # If no services, add a generic "Community Insights" service
    if not services:
        services.append({
            "id": "community_insights",
            "name": "Community Insights",
            "description": "Share experiences and insights from community participation",
            "pricing": {
                "amount": "0.02",
                "currency": "GLUE",
                "unit": "per query"
            },
            "capabilities": ["Community Engagement"],
            "confidence": 0.5
        })

    return services


def generate_agent_card(profile: Dict[str, Any], username: str) -> Dict[str, Any]:
    """
    Generate A2A protocol Agent Card from user profile

    Agent Card format follows A2A spec at /.well-known/agent-card
    """

    user_id = profile.get("user_id", f"@{username}")
    interaction_style = profile.get("interaction_style", {})
    data_coverage = profile.get("data_coverage", {})

    # Generate services
    services = generate_services_from_profile(profile)

    # Build agent card
    agent_card = {
        "version": "1.0",
        "agent": {
            "id": user_id,
            "name": f"{username.title()} Agent",
            "description": profile.get("agent_potential_summary", f"Community member offering {len(services)} services"),
            "avatar_url": f"https://karmacadabra.ultravioletadao.xyz/avatars/{username}.png",  # Placeholder
            "owner": user_id
        },
        "services": services,
        "capabilities": {
            "protocols": ["a2a", "x402"],
            "payment_methods": ["GLUE"],
            "communication": ["http", "websocket"]
        },
        "metadata": {
            "engagement_level": interaction_style.get("engagement_level", "medium"),
            "message_count": data_coverage.get("message_count", 0),
            "confidence_level": data_coverage.get("confidence_level", 0.5),
            "created_from_profile": True,
            "profile_level": profile.get("profile_level", "complete")
        },
        "discovery": {
            "tags": [
                interest.get("domain", "").lower()
                for interest in profile.get("interests", [])
            ] + [
                skill.get("skill", "").lower()
                for skill in profile.get("skills", [])
            ],
            "categories": list(set([
                interest.get("domain", "")
                for interest in profile.get("interests", [])
                if interest.get("domain")
            ])),
            "searchable": True
        },
        "contact": {
            "endpoint": f"https://{username}.karmacadabra.ultravioletadao.xyz",
            "health_check": f"https://{username}.karmacadabra.ultravioletadao.xyz/health",
            "agent_card": f"https://{username}.karmacadabra.ultravioletadao.xyz/.well-known/agent-card"
        }
    }

    return agent_card


def main():
    """Main generation function"""

    print("=" * 80)
    print("Karmacadabra - Sprint 3: Agent Card Auto-Generator")
    print("=" * 80)
    print()

    # Setup paths
    base_dir = Path(__file__).parent.parent
    profiles_dir = base_dir / "user-profiles"
    output_dir = base_dir / "agent-cards"
    output_dir.mkdir(exist_ok=True)

    # Get all profile files
    profile_files = list(profiles_dir.glob("*.json"))

    print(f"📋 Found {len(profile_files)} profiles to process")
    print(f"📂 Output directory: {output_dir}")
    print()

    # Process each profile
    successful = 0
    failed = 0

    for i, profile_file in enumerate(profile_files, 1):
        username = profile_file.stem
        print(f"[{i}/{len(profile_files)}] Generating Agent Card for {username}...", end=" ")

        try:
            # Load profile
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile = json.load(f)

            # Generate agent card
            agent_card = generate_agent_card(profile, username)

            # Save agent card
            card_file = output_dir / f"{username}.json"
            with open(card_file, 'w', encoding='utf-8') as f:
                json.dump(agent_card, f, indent=2, ensure_ascii=False)

            services_count = len(agent_card["services"])
            print(f"✅ ({services_count} services)")
            successful += 1

        except Exception as e:
            print(f"❌ {e}")
            failed += 1

    print()
    print("=" * 80)
    print(f"📊 Agent Card Generation Summary")
    print("=" * 80)
    print(f"Total profiles: {len(profile_files)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📂 Output directory: {output_dir}")
    print()

    if failed == 0:
        print("🎉 All Agent Cards generated successfully!")
        return 0
    else:
        print(f"⚠️  {failed} Agent Cards failed to generate")
        return 1


if __name__ == "__main__":
    sys.exit(main())
