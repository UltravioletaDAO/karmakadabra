"""
Karma Kadabra V2 — Task 4.3: On-Chain Agent Profile Registration

Reads SOUL.md + skills + voice data for KK agents and generates
ERC-8004 compatible agent-card.json files, uploads them to IPFS
via Pinata, and stores the manifest for on-chain URI updates.

Pipeline:
  SOUL.md + skills/{user}.json + voice/{user}.json
    -> agent-card.json (ERC-8004 compatible)
    -> IPFS upload via Pinata
    -> Manifest with agent_id -> IPFS URI mapping

Usage:
  python register_agent_profile.py                          # Generate all
  python register_agent_profile.py --agent kk-juanjumagalp  # Single agent
  python register_agent_profile.py --upload                 # Generate + upload
  python register_agent_profile.py --dry-run                # Preview only
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.register-profile")

# Paths
DATA_DIR = Path(__file__).parent / "data"
WALLETS_FILE = Path(__file__).parent / "config" / "wallets.json"
OUTPUT_DIR = DATA_DIR / "agent-cards"

# ERC-8004 constants
ERC8004_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
ERC8004_REPUTATION = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

# Known ERC-8004 agent IDs for KK agents (registered on Base)
# Format: wallet_address_lower -> agent_id
KK_AGENT_IDS: dict[str, int] = {}


def load_wallets() -> dict[str, dict[str, Any]]:
    """Load wallet mappings from config. Returns {name: wallet_data}."""
    if not WALLETS_FILE.exists():
        logger.error("Wallets file not found: %s", WALLETS_FILE)
        return {}
    data = json.loads(WALLETS_FILE.read_text(encoding="utf-8"))
    return {w["name"]: w for w in data.get("wallets", [])}


def load_soul(username: str) -> str | None:
    """Load SOUL.md content for a username."""
    soul_file = DATA_DIR / "souls" / f"{username}.md"
    if soul_file.exists():
        return soul_file.read_text(encoding="utf-8")
    return None


def load_skills(username: str) -> dict[str, Any]:
    """Load skills JSON for a username."""
    skills_file = DATA_DIR / "skills" / f"{username}.json"
    if skills_file.exists():
        return json.loads(skills_file.read_text(encoding="utf-8"))
    return {"username": username, "skills": {}, "top_skills": []}


def load_voice(username: str) -> dict[str, Any]:
    """Load voice/personality JSON for a username."""
    voice_file = DATA_DIR / "voices" / f"{username}.json"
    if voice_file.exists():
        return json.loads(voice_file.read_text(encoding="utf-8"))
    return {"username": username, "tone": {}, "personality": {}}


def extract_skills_list(skills_data: dict) -> list[dict[str, str]]:
    """Extract structured skill list from skills JSON."""
    result = []
    for cat, data in skills_data.get("skills", {}).items():
        for sub in data.get("sub_skills", [])[:3]:
            score = sub.get("score", 0)
            if score >= 0.3:
                level = "expert" if score >= 0.7 else "intermediate" if score >= 0.4 else "beginner"
                result.append({
                    "name": sub["name"],
                    "category": cat,
                    "level": level,
                })
    return result


def extract_services(skills_data: dict) -> list[dict[str, Any]]:
    """Generate service offerings from top skills."""
    service_map = {
        "Python": {"name": "Python Development", "price": "0.10 USDC", "desc": "Scripts, APIs, data processing"},
        "JavaScript": {"name": "Web Development", "price": "0.10 USDC", "desc": "Web apps, bots, integrations"},
        "Solidity": {"name": "Smart Contract Dev", "price": "0.20 USDC", "desc": "Write, audit, deploy contracts"},
        "DeFi": {"name": "DeFi Strategy", "price": "0.10 USDC", "desc": "Yield analysis, protocol mechanics"},
        "Trading": {"name": "Trading Analysis", "price": "0.10 USDC", "desc": "Technical analysis, market signals"},
        "NFTs": {"name": "NFT Curation", "price": "0.05 USDC", "desc": "NFT discovery and analysis"},
        "LLM": {"name": "AI Integration", "price": "0.15 USDC", "desc": "LLM tools and agent workflows"},
        "Agents": {"name": "Agent Development", "price": "0.15 USDC", "desc": "Autonomous AI agent design"},
        "UI/UX": {"name": "Design Services", "price": "0.10 USDC", "desc": "Interface and UX creation"},
        "Marketing": {"name": "Content Strategy", "price": "0.05 USDC", "desc": "Growth and community building"},
        "Teaching": {"name": "Education", "price": "0.05 USDC", "desc": "Tutorials and mentoring"},
    }
    services = []
    for ts in skills_data.get("top_skills", [])[:3]:
        svc = service_map.get(ts.get("skill", ""))
        if svc:
            services.append({
                "name": svc["name"],
                "description": svc["desc"],
                "price": svc["price"],
                "category": ts.get("category", "General"),
            })
    if not services:
        services.append({
            "name": "Community Insight",
            "description": "Knowledge about Ultravioleta DAO community",
            "price": "0.05 USDC",
            "category": "Community",
        })
    return services


def extract_languages(skills_data: dict) -> list[str]:
    """Extract language list from skills data."""
    lang_map = skills_data.get("languages", {})
    primary = skills_data.get("primary_language", "spanish")
    languages = [primary]
    for lang in lang_map:
        if lang != primary and lang not in languages:
            languages.append(lang)
    if not languages:
        languages = ["spanish"]
    return languages


def generate_agent_card(
    agent_name: str,
    username: str,
    wallet_address: str,
    agent_id: int | None,
    skills_data: dict,
    voice_data: dict,
    agent_type: str = "user",
) -> dict[str, Any]:
    """Generate an ERC-8004 compatible agent-card.json."""
    tone = voice_data.get("tone", {}).get("primary", "conversational")
    risk = voice_data.get("personality", {}).get("risk_tolerance", "moderate")

    # Build structured skills
    skills_list = extract_skills_list(skills_data)
    services = extract_services(skills_data)
    languages = extract_languages(skills_data)

    # Determine specialization
    top_skills = skills_data.get("top_skills", [])
    specialization = top_skills[0]["skill"] if top_skills else "Community"

    # System agent descriptions
    system_descriptions = {
        "kk-coordinator": "Swarm coordinator: routes agents to matching tasks, manages budget allocation, monitors health",
        "kk-karma-hello": "Data seller: publishes raw Twitch chat logs as structured datasets on Execution Market",
        "kk-skill-extractor": "Data refinery: buys raw logs, extracts skill profiles, publishes enriched data",
        "kk-voice-extractor": "Personality profiler: buys raw logs, extracts communication patterns and personality",
        "kk-validator": "Quality validator: verifies data integrity and task evidence quality",
        "kk-soul-extractor": "Profile merger: combines skills + voice into complete SOUL.md personality profiles",
    }

    description = system_descriptions.get(
        agent_name,
        f"Digital twin of {username} in the Ultravioleta DAO agent economy. "
        f"Specializes in {specialization}. Tone: {tone}. "
        f"Transacts on Execution Market, buys and sells data, "
        f"and collaborates with other agents via IRC.",
    )

    card: dict[str, Any] = {
        "name": agent_name,
        "description": description,
        "image": f"https://execution.market/agents/{agent_name}.png",
        "external_url": "https://execution.market",
        "agent_type": "system_agent" if agent_type == "system" else "community_agent",
        "category": "karma_kadabra_swarm",
        "ecosystem": "ultravioletadao",
        "capabilities": _build_capabilities(agent_name, skills_data, agent_type),
        "protocols": {
            "irc": f"irc://irc.meshrelay.xyz/#Agents ({agent_name})",
            "execution_market": "https://api.execution.market/api/v1",
        },
        "identity": {
            "standard": "ERC-8004",
            "network": "base",
            "registry": ERC8004_REGISTRY,
            "reputation_registry": ERC8004_REPUTATION,
            "wallet": wallet_address,
        },
        "personality": {
            "tone": tone,
            "risk_tolerance": risk,
            "origin": "Extracted from Twitch chat logs (Ultravioleta DAO)",
            "specialization": specialization,
        },
        "skills": skills_list,
        "services": services,
        "languages": languages,
        "payment": {
            "networks": ["base"],
            "tokens": ["USDC"],
            "protocol": "x402",
            "gasless": True,
            "daily_budget_usd": 2.0,
            "per_task_max_usd": 0.50,
        },
        "swarm": {
            "name": "karma_kadabra_v2",
            "role": agent_type,
            "parent_agent_id": 2106,
            "coordination_channel": "#Agents",
        },
        "version": "1.0.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if agent_id is not None:
        card["identity"]["agent_id"] = agent_id

    return card


def _build_capabilities(
    agent_name: str,
    skills_data: dict,
    agent_type: str,
) -> list[str]:
    """Build capabilities list based on agent role and skills."""
    base_caps = [
        "task_discovery",
        "task_execution",
        "evidence_submission",
        "reputation_tracking",
        "irc_communication",
        "x402_payments",
    ]

    if agent_type == "system":
        system_caps = {
            "kk-coordinator": ["swarm_coordination", "task_routing", "budget_management", "health_monitoring"],
            "kk-karma-hello": ["data_publication", "log_aggregation", "dataset_curation"],
            "kk-skill-extractor": ["skill_extraction", "data_enrichment", "profile_generation"],
            "kk-voice-extractor": ["personality_analysis", "voice_extraction", "behavior_profiling"],
            "kk-validator": ["evidence_verification", "quality_assurance", "fraud_detection"],
            "kk-soul-extractor": ["profile_merging", "soul_generation", "identity_synthesis"],
        }
        return base_caps + system_caps.get(agent_name, [])

    # User agents: add capabilities based on skills
    skill_caps = []
    for cat in skills_data.get("skills", {}):
        cap_map = {
            "Programming": "software_development",
            "Blockchain": "blockchain_expertise",
            "AI/ML": "ai_integration",
            "Design": "design_services",
            "Business": "business_strategy",
            "Community": "community_engagement",
        }
        if cat in cap_map:
            skill_caps.append(cap_map[cat])
    return base_caps + skill_caps


def upload_to_pinata(metadata: dict, name: str) -> str | None:
    """Upload metadata JSON to IPFS via Pinata. Returns IPFS URI or None."""
    api_key = os.environ.get("PINATA_API_KEY", "")
    secret_key = os.environ.get("PINATA_SECRET_KEY", "")

    if not api_key or not secret_key:
        logger.warning("PINATA_API_KEY/PINATA_SECRET_KEY not set — skipping upload")
        return None

    try:
        import httpx

        resp = httpx.post(
            "https://api.pinata.cloud/pinning/pinJSONToIPFS",
            headers={
                "Content-Type": "application/json",
                "pinata_api_key": api_key,
                "pinata_secret_api_key": secret_key,
            },
            json={
                "pinataContent": metadata,
                "pinataMetadata": {"name": f"kk-agent-{name}.json"},
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        ipfs_hash = resp.json()["IpfsHash"]
        return f"ipfs://{ipfs_hash}"
    except Exception as e:
        logger.error("Pinata upload failed for %s: %s", name, e)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ERC-8004 agent-card.json profiles")
    parser.add_argument("--agent", type=str, default=None, help="Single agent name (e.g., kk-juanjumagalp)")
    parser.add_argument("--upload", action="store_true", help="Upload to IPFS via Pinata")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no file writes")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load wallets
    wallets = load_wallets()
    if not wallets:
        logger.error("No wallets found. Run generate-relay-wallets.py first.")
        sys.exit(1)

    # Filter to single agent if specified
    if args.agent:
        name = args.agent
        if name not in wallets:
            logger.error("Agent '%s' not found in wallets.json", name)
            sys.exit(1)
        agent_list = [(name, wallets[name])]
    else:
        agent_list = list(wallets.items())

    logger.info("Generating agent-card.json for %d agents...", len(agent_list))

    manifest: list[dict[str, Any]] = []

    for agent_name, wallet_data in agent_list:
        address = wallet_data.get("address", "")
        agent_type = wallet_data.get("type", "user")
        agent_id = KK_AGENT_IDS.get(address.lower())

        # Username is agent name without kk- prefix
        username = agent_name.removeprefix("kk-")

        # Load data sources
        skills = load_skills(username)
        voice = load_voice(username)

        # Generate card
        card = generate_agent_card(
            agent_name=agent_name,
            username=username,
            wallet_address=address,
            agent_id=agent_id,
            skills_data=skills,
            voice_data=voice,
            agent_type=agent_type,
        )

        # Preview or write
        if args.dry_run:
            logger.info("[DRY-RUN] %s: %d skills, %d services", agent_name, len(card["skills"]), len(card["services"]))
            continue

        card_path = output_dir / f"{agent_name}.json"
        card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")

        entry: dict[str, Any] = {
            "agent_name": agent_name,
            "wallet": address,
            "type": agent_type,
            "card_file": str(card_path.relative_to(Path(__file__).parent)),
            "skills_count": len(card["skills"]),
            "services_count": len(card["services"]),
        }

        # IPFS upload
        if args.upload:
            ipfs_uri = upload_to_pinata(card, agent_name)
            if ipfs_uri:
                entry["ipfs_uri"] = ipfs_uri
                logger.info("  %s -> %s", agent_name, ipfs_uri)
            else:
                logger.warning("  %s: upload failed", agent_name)
        else:
            logger.info("  %s: card generated (%d skills, %d services)", agent_name, len(card["skills"]), len(card["services"]))

        if agent_id is not None:
            entry["agent_id"] = agent_id

        manifest.append(entry)

    if not args.dry_run:
        # Write manifest
        manifest_data = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agent_count": len(manifest),
            "agents": manifest,
        }
        manifest_path = output_dir / "_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("\nDone! %d agent cards in %s", len(manifest), output_dir)
        logger.info("Manifest: %s", manifest_path)

        uploaded = sum(1 for a in manifest if "ipfs_uri" in a)
        if uploaded > 0:
            logger.info("Uploaded to IPFS: %d/%d", uploaded, len(manifest))


if __name__ == "__main__":
    main()
