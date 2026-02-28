"""
Karma Kadabra V2 — Task 5.5: Soul Extractor Service

The Soul Extractor agent is a higher-order data refinery that combines
skill profiles + voice profiles + engagement stats into complete
OpenClaw-compatible SOUL.md agent profiles.

Supply chain position:
  Karma Hello (raw logs $0.01)
    -> Skill Extractor (skill profiles $0.05)
    -> Voice Extractor (personality profiles $0.04)
    -> Soul Extractor (buys both, produces complete SOUL.md profiles $0.08)

Unlike generate-soul.py (batch, run once), this service:
  1. Discovers enriched skill + voice offerings on EM (from sibling extractors)
  2. Buys enriched data packages ($0.05 + $0.04)
  3. Merges skill + voice + stats into complete SOUL.md profiles
  4. Publishes SOUL.md bundles as premium EM offerings ($0.08)
  5. Monitors for new data and updates profiles periodically

Data products:
  - Complete SOUL.md profiles (identity, personality, skills, pricing, trust)
  - Profile update diffs (delta changes since last extraction)

Usage:
  python soul_extractor_service.py                 # Full cycle
  python soul_extractor_service.py --discover      # Only discover offerings
  python soul_extractor_service.py --process       # Only merge local data
  python soul_extractor_service.py --sell           # Only publish products
  python soul_extractor_service.py --dry-run       # Preview all actions
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure services package is importable
sys.path.insert(0, str(Path(__file__).parent))

from em_client import AgentContext, EMClient, load_agent_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.soul-extractor")


# ---------------------------------------------------------------------------
# SOUL.md generation (adapted from generate-soul.py for live service use)
# ---------------------------------------------------------------------------

TASK_CATEGORY_MAP = {
    "Programming": ["digital_physical", "knowledge_access"],
    "Blockchain": ["digital_physical", "knowledge_access"],
    "AI/ML": ["digital_physical", "knowledge_access"],
    "Design": ["simple_action", "digital_physical"],
    "Business": ["knowledge_access", "human_authority"],
    "Community": ["knowledge_access", "simple_action"],
}

RISK_DESCRIPTIONS = {
    "aggressive": "Takes bold positions, willing to go all-in on high-conviction plays",
    "moderate": "Balanced approach, diversifies across opportunities",
    "conservative": "Careful with capital, prefers stable and proven strategies",
    "unknown": "Adapts spending to opportunity quality",
}

TONE_DESCRIPTIONS = {
    "inquisitive": "always asking questions, eager to learn and understand",
    "enthusiastic": "high energy, uses exclamations, hypes up the community",
    "analytical": "detailed and thoughtful, provides in-depth analysis",
    "reactive": "quick responses, memes and reactions, keeps the chat lively",
    "conversational": "natural flow, mixes opinions with questions",
}

TONE_GUIDELINES = {
    "inquisitive": "Ask lots of questions -- you're naturally curious",
    "enthusiastic": "Use exclamations and hype -- you're energetic!",
    "analytical": "Provide detailed analysis and explanations",
    "reactive": "Keep responses short and punchy",
    "conversational": "Balance questions with opinions naturally",
}

SKILL_TO_SERVICE = {
    "Python": {"capability": "Python Development", "service": "Build automation scripts, APIs, and data processing tools"},
    "JavaScript": {"capability": "Web Development", "service": "Create web apps, bots, and integrations"},
    "Solidity": {"capability": "Smart Contract Dev", "service": "Write, audit, and deploy smart contracts"},
    "DeFi": {"capability": "DeFi Strategy", "service": "Analyze yield opportunities and protocol mechanics"},
    "Trading": {"capability": "Trading Analysis", "service": "Technical analysis, market signals, and trade ideas"},
    "NFTs": {"capability": "NFT Curation", "service": "Discover, analyze, and recommend NFT collections"},
    "LLM": {"capability": "AI Integration", "service": "Build LLM-powered tools and agent workflows"},
    "Agents": {"capability": "Agent Development", "service": "Design and deploy autonomous AI agents"},
    "UI/UX": {"capability": "Design Services", "service": "Create interfaces and user experiences"},
    "Marketing": {"capability": "Content Strategy", "service": "Growth hacking, content creation, and community building"},
    "Teaching": {"capability": "Education", "service": "Tutorials, mentoring, and knowledge sharing"},
    "General": {"capability": "Development", "service": "General software development and problem solving"},
}


def generate_soul_md(username: str, stats: dict, skills: dict, voice: dict) -> str:
    """Generate an OpenClaw-compatible SOUL.md for a single agent.

    This is the live-service version of generate-soul.py's generate_soul_md(),
    adapted to work with dynamically purchased data rather than local files.
    """
    # --- Identity ---
    primary_lang = skills.get("primary_language", "spanish")
    lang_str = "Spanish (primary)" if primary_lang == "spanish" else f"{primary_lang.title()} (primary)"
    lang_map = skills.get("languages", {})
    if len(lang_map) > 1:
        secondary = [lang for lang in lang_map if lang != primary_lang]
        if secondary:
            lang_str += f", {secondary[0].title()} (secondary)"

    # --- Personality from voice ---
    tone = voice.get("tone", {}).get("primary", "conversational")
    social_role = voice.get("communication_style", {}).get("social_role", "regular")
    risk = voice.get("personality", {}).get("risk_tolerance", "moderate")
    greeting = voice.get("communication_style", {}).get("greeting_style", "gm")
    formality = voice.get("personality", {}).get("formality", "informal")
    avg_msg_len = voice.get("communication_style", {}).get("avg_message_length", 40)

    # Signature phrases
    phrases = voice.get("vocabulary", {}).get("signature_phrases", [])
    phrase_list = [f'"{p["phrase"]}"' for p in phrases[:5]]

    # Slang
    slang = voice.get("vocabulary", {}).get("slang_usage", {})
    slang_words = []
    for _cat, data in slang.items():
        for item in data.get("top", [])[:3]:
            slang_words.append(item["word"])

    # --- Skills ---
    skill_lines = []
    for cat, data in skills.get("skills", {}).items():
        for sub in data.get("sub_skills", [])[:3]:
            score = sub["score"]
            if score >= 0.7:
                confidence = "high"
            elif score >= 0.4:
                confidence = "medium"
            else:
                confidence = "low"
            skill_lines.append(f"- **{sub['name']}** ({cat}) -- confidence: {confidence}")

    if not skill_lines:
        skill_lines = ["- Community participation -- confidence: medium"]

    top_skills = skills.get("top_skills", [])
    specialization = top_skills[0]["skill"] if top_skills else "Community Member"

    # --- Task categories ---
    task_types = []
    skill_categories = list(skills.get("skills", {}).keys())
    if "Programming" in skill_categories or "AI/ML" in skill_categories:
        task_types.append("digital_physical")
    if "Design" in skill_categories:
        task_types.append("simple_action")
    if "Business" in skill_categories or "Community" in skill_categories:
        task_types.append("knowledge_access")
    if not task_types:
        task_types = ["simple_action", "knowledge_access"]

    # --- Monetizable capabilities ---
    monetizable_lines = []
    for ts in top_skills[:3]:
        service = SKILL_TO_SERVICE.get(ts["skill"])
        if service:
            monetizable_lines.append(f"- **{service['capability']}**: {service['service']}")
    if not monetizable_lines:
        monetizable_lines.append(
            "- **Community Insight**: Share knowledge about Ultravioleta DAO community dynamics and trends"
        )

    # --- Trusted agents list ---
    # Derived from the KK swarm — system agents are always trusted
    trusted_agents = [
        "kk-coordinator",
        "kk-karma-hello",
        "kk-skill-extractor",
        "kk-voice-extractor",
        "kk-soul-extractor",
        "kk-validator",
    ]

    # --- Communication style description ---
    style_desc = TONE_DESCRIPTIONS.get(tone, "authentic and engaged")
    tone_guideline = TONE_GUIDELINES.get(tone, "Communicate authentically and naturally")

    # --- Pricing preferences ---
    if risk == "aggressive":
        max_spend = "0.50"
        negotiation = "Firm -- knows value and holds price"
    elif risk == "conservative":
        max_spend = "0.20"
        negotiation = "Generous -- prioritizes relationships over margins"
    else:
        max_spend = "0.30"
        negotiation = "Flexible -- willing to negotiate for good deals"

    # --- Build SOUL.md ---
    soul = f"""# Soul of {username}

## Identity
You are **{username}**'s digital twin in the Ultravioleta DAO. You represent their personality,
knowledge, and communication style in the agent economy. You transact on Execution Market,
buy and sell data, and interact with other agents on IRC.

- **Origin**: Extracted from Twitch chat logs (Ultravioleta DAO streams)
- **Language**: {lang_str}
- **Messages analyzed**: {stats.get('total_messages', 0)} across {stats.get('active_dates', 0)} sessions
- **Specialization**: {specialization}
- **Profile version**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')} (auto-updated by Soul Extractor)

## Personality
- **Tone**: {tone.title()} -- {style_desc}
- **Formality**: {formality.title()}
- **Social role**: {social_role.replace('_', ' ').title()}
- **Greeting style**: "{greeting}"
"""

    if phrase_list:
        soul += f"- **Signature phrases**: {', '.join(phrase_list)}\n"

    if slang_words:
        soul += f"- **Slang**: {', '.join(slang_words[:8])}\n"

    soul += f"""
## Communication Guidelines
- Write messages that average ~{int(avg_msg_len)} characters
- {tone_guideline}
- {"Speak primarily in Spanish with occasional English crypto/tech terms" if primary_lang == "spanish" else "Speak primarily in English"}
- Match the energy of the chat -- adapt but stay true to your personality

## Skills & Expertise
{chr(10).join(skill_lines)}

## Preferred Task Categories
{chr(10).join(f"- `{t}`" for t in task_types)}

## Economic Behavior
- **Risk tolerance**: {risk.title()} -- {RISK_DESCRIPTIONS.get(risk, RISK_DESCRIPTIONS['unknown'])}
- **Max spend per transaction**: ${max_spend} USDC
- **Daily budget**: $2.00 USDC
- **Negotiation style**: {negotiation}

## Pricing Preferences
- Accept tasks with bounty >= $0.01 USDC
- Prefer tasks matching top skills (higher confidence = lower minimum bounty)
- Data tasks: willing to pay $0.01-$0.05 for raw data, $0.05-$0.10 for enriched
- Service tasks: charge based on skill confidence (high=$0.10+, medium=$0.05+, low=$0.02+)

## Monetizable Capabilities
{chr(10).join(monetizable_lines)}

## Trusted Agents
{chr(10).join(f"- `{a}`" for a in trusted_agents)}

## Agent Rules
1. Never spend more than your daily budget ($2.00 USDC)
2. Always verify task requirements before accepting
3. Prioritize tasks that match your skill profile
4. Rate other agents honestly after interactions
5. Report suspicious tasks or scam attempts
6. Maintain your reputation score above 60 (Plata tier)
7. Participate in IRC channels relevant to your interests
8. Prefer trusted agents for high-value transactions
"""

    return soul.strip() + "\n"


# ---------------------------------------------------------------------------
# Phase 1: Discover enriched data offerings from sibling extractors
# ---------------------------------------------------------------------------


async def discover_data_offerings(client: EMClient) -> dict[str, list[dict]]:
    """Search EM for skill and voice enriched data from sibling extractors."""
    tasks = await client.browse_tasks(
        status="published",
        category="knowledge_access",
        limit=50,
    )

    skill_offerings = [
        t for t in tasks
        if "[KK Data]" in t.get("title", "") and "Skill" in t.get("title", "")
    ]
    voice_offerings = [
        t for t in tasks
        if "[KK Data]" in t.get("title", "") and ("Personality" in t.get("title", "") or "Voice" in t.get("title", ""))
    ]

    logger.info(f"  Found {len(skill_offerings)} skill data offerings")
    logger.info(f"  Found {len(voice_offerings)} voice/personality data offerings")

    for t in skill_offerings:
        logger.info(f"    [SKILL] {t.get('title', '?')} (${t.get('bounty_usdc', 0)})")
    for t in voice_offerings:
        logger.info(f"    [VOICE] {t.get('title', '?')} (${t.get('bounty_usdc', 0)})")

    return {
        "skills": skill_offerings,
        "voices": voice_offerings,
    }


async def buy_data(
    client: EMClient,
    task: dict,
    data_type: str,
    dry_run: bool = False,
) -> dict | None:
    """Apply to buy data from a sibling extractor."""
    task_id = task.get("id", "")
    bounty = task.get("bounty_usdc", 0)
    title = task.get("title", "?")

    if not client.agent.can_spend(bounty):
        logger.warning(f"  SKIP: Budget limit (${client.agent.daily_spent_usd:.2f} spent)")
        return None

    if dry_run:
        logger.info(f"  [DRY RUN] Would buy {data_type}: {title}")
        return None

    if not client.agent.executor_id:
        logger.error("  Cannot buy: executor_id not set (register on EM first)")
        return None

    logger.info(f"  Buying {data_type}: {title} (${bounty})")
    result = await client.apply_to_task(
        task_id=task_id,
        executor_id=client.agent.executor_id,
        message=f"Soul Extractor agent -- buying {data_type} data for complete SOUL.md profile generation",
    )
    client.agent.record_spend(bounty)
    return result


# ---------------------------------------------------------------------------
# Phase 2: Process — merge skills + voices + stats into SOUL.md profiles
# ---------------------------------------------------------------------------


async def process_souls(data_dir: Path) -> dict | None:
    """Merge skill profiles + voice profiles + stats into SOUL.md files.

    Reads from:
      data_dir/skills/*.json   (skill profiles from Skill Extractor)
      data_dir/voices/*.json   (voice profiles from Voice Extractor)
      data_dir/user-stats.json (engagement stats from pipeline)

    Writes to:
      data_dir/souls/*.md      (generated SOUL.md files)
      data_dir/souls/*.json    (structured profile data for API consumers)
    """
    skills_dir = data_dir / "skills"
    voices_dir = data_dir / "voices"
    stats_file = data_dir / "user-stats.json"
    souls_dir = data_dir / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)

    if not skills_dir.exists():
        logger.warning(f"  No skills directory at {skills_dir}")
        return None
    if not voices_dir.exists():
        logger.warning(f"  No voices directory at {voices_dir}")
        return None
    if not stats_file.exists():
        logger.info(f"  No user-stats.json found, generating basic stats from profiles")
        stats_data = {"ranking": []}
    else:
        stats_data = json.loads(stats_file.read_text(encoding="utf-8"))
    ranked = stats_data.get("ranking", [])
    stats_by_user = {u["username"]: u for u in ranked}

    skill_profiles = list(skills_dir.glob("*.json"))
    voice_profiles = list(voices_dir.glob("*.json"))

    # Index by username (exclude _summary.json)
    skill_map: dict[str, dict] = {}
    for path in skill_profiles:
        if path.stem.startswith("_"):
            continue
        profile = json.loads(path.read_text(encoding="utf-8"))
        skill_map[profile.get("username", path.stem)] = profile

    voice_map: dict[str, dict] = {}
    for path in voice_profiles:
        if path.stem.startswith("_"):
            continue
        profile = json.loads(path.read_text(encoding="utf-8"))
        voice_map[profile.get("username", path.stem)] = profile

    # Find users with BOTH skill + voice data (complete profiles only)
    complete_users = set(skill_map.keys()) & set(voice_map.keys())
    partial_users = (set(skill_map.keys()) | set(voice_map.keys())) - complete_users

    logger.info(f"  Skill profiles: {len(skill_map)}")
    logger.info(f"  Voice profiles: {len(voice_map)}")
    logger.info(f"  Complete (both): {len(complete_users)}")
    logger.info(f"  Partial (one only): {len(partial_users)}")

    generated = 0
    updated = 0
    profile_summaries = []

    for username in sorted(complete_users):
        skills = skill_map[username]
        voice = voice_map[username]
        stats = stats_by_user.get(username, {"total_messages": 0, "active_dates": 0})

        # Generate SOUL.md
        soul_content = generate_soul_md(username, stats, skills, voice)
        soul_path = souls_dir / f"{username}.md"

        # Check if profile changed (for update tracking)
        is_update = soul_path.exists()
        soul_path.write_text(soul_content, encoding="utf-8")

        # Also save structured JSON for API consumers
        structured = {
            "username": username,
            "version": datetime.now(timezone.utc).isoformat(),
            "identity": {
                "language": skills.get("primary_language", "spanish"),
                "specialization": skills["top_skills"][0]["skill"] if skills.get("top_skills") else "Community",
                "messages_analyzed": stats.get("total_messages", 0),
                "sessions_analyzed": stats.get("active_dates", 0),
            },
            "personality": {
                "tone": voice.get("tone", {}).get("primary", "conversational"),
                "social_role": voice.get("communication_style", {}).get("social_role", "regular"),
                "risk_tolerance": voice.get("personality", {}).get("risk_tolerance", "moderate"),
                "formality": voice.get("personality", {}).get("formality", "informal"),
                "greeting_style": voice.get("communication_style", {}).get("greeting_style", "gm"),
            },
            "skills": skills.get("top_skills", [])[:5],
            "task_categories": _derive_task_categories(skills),
            "pricing": {
                "daily_budget_usd": 2.0,
                "max_per_task_usd": 0.50,
                "min_accept_bounty_usd": 0.01,
            },
        }
        json_path = souls_dir / f"{username}.json"
        json_path.write_text(json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8")

        if is_update:
            updated += 1
        else:
            generated += 1

        profile_summaries.append(structured)

    # Also generate partial profiles (skill-only or voice-only) with defaults
    for username in sorted(partial_users):
        skills = skill_map.get(username, _default_skills(username))
        voice = voice_map.get(username, _default_voice(username))
        stats = stats_by_user.get(username, {"total_messages": 0, "active_dates": 0})

        soul_content = generate_soul_md(username, stats, skills, voice)
        soul_path = souls_dir / f"{username}.md"
        is_update = soul_path.exists()
        soul_path.write_text(soul_content, encoding="utf-8")

        if is_update:
            updated += 1
        else:
            generated += 1

    logger.info(f"  Generated {generated} new SOUL.md profiles")
    logger.info(f"  Updated {updated} existing profiles")

    return {
        "total_profiles": generated + updated,
        "new_profiles": generated,
        "updated_profiles": updated,
        "complete_profiles": len(complete_users),
        "partial_profiles": len(partial_users),
        "profiles": profile_summaries,
    }


def _derive_task_categories(skills: dict) -> list[str]:
    """Derive preferred EM task categories from skill profile."""
    categories = set()
    for cat in skills.get("skills", {}):
        for tc in TASK_CATEGORY_MAP.get(cat, ["simple_action"]):
            categories.add(tc)
    if not categories:
        categories = {"simple_action", "knowledge_access"}
    return sorted(categories)


def _default_skills(username: str) -> dict:
    """Default skill profile for users with voice but no skills data."""
    return {
        "username": username,
        "skills": {},
        "top_skills": [],
        "primary_language": "spanish",
        "languages": {},
    }


def _default_voice(username: str) -> dict:
    """Default voice profile for users with skills but no voice data."""
    return {
        "username": username,
        "tone": {"primary": "conversational"},
        "communication_style": {
            "social_role": "regular",
            "greeting_style": "gm",
            "avg_message_length": 40,
        },
        "vocabulary": {"signature_phrases": [], "slang_usage": {}},
        "personality": {"risk_tolerance": "moderate", "formality": "informal"},
    }


# ---------------------------------------------------------------------------
# Phase 3: Sell — publish SOUL.md bundles on Execution Market
# ---------------------------------------------------------------------------


async def publish_soul_profiles(
    client: EMClient,
    data_dir: Path,
    stats: dict,
    dry_run: bool = False,
) -> dict | None:
    """Publish complete SOUL.md profile bundles on EM."""
    total = stats.get("total_profiles", 0)
    complete = stats.get("complete_profiles", 0)
    new_count = stats.get("new_profiles", 0)
    updated_count = stats.get("updated_profiles", 0)

    title = f"[KK Data] Complete Agent Profiles (SOUL.md) -- {total} Community Members"
    description = (
        f"OpenClaw-compatible SOUL.md personality profiles for {total} "
        f"Ultravioleta DAO community members.\n\n"
        f"Each profile includes:\n"
        f"- Identity (origin, language, specialization)\n"
        f"- Personality (tone, social role, greeting style, signature phrases)\n"
        f"- Communication guidelines (message style, language mix)\n"
        f"- Skills & expertise (ranked with confidence scores)\n"
        f"- Preferred task categories for Execution Market\n"
        f"- Economic behavior (risk tolerance, pricing preferences)\n"
        f"- Monetizable capabilities\n"
        f"- Trusted agents list\n\n"
        f"Complete profiles (skill+voice): {complete}. "
        f"New: {new_count}. Updated: {updated_count}.\n\n"
        f"Format: Markdown (SOUL.md) + JSON (structured). "
        f"Delivery: URL provided upon approval."
    )
    bounty = 0.08

    if dry_run:
        logger.info(f"  [DRY RUN] Would publish: {title} (${bounty})")
        return None

    if not client.agent.can_spend(bounty):
        logger.warning(f"  SKIP: Budget limit")
        return None

    result = await client.publish_task(
        title=title,
        instructions=description,
        category="knowledge_access",
        bounty_usd=bounty,
        deadline_hours=24,
        evidence_required=["json_response"],
    )

    task_id = result.get("task", {}).get("id") or result.get("id", "unknown")
    logger.info(f"  Published soul profiles: task_id={task_id}")
    client.agent.record_spend(bounty)
    return result


async def publish_profile_updates(
    client: EMClient,
    stats: dict,
    dry_run: bool = False,
) -> dict | None:
    """Publish a delta update product if there are updated profiles."""
    updated_count = stats.get("updated_profiles", 0)
    if updated_count == 0:
        logger.info("  No profile updates to publish")
        return None

    title = f"[KK Data] Agent Profile Updates (Delta) -- {updated_count} Profiles"
    description = (
        f"Updated SOUL.md profiles for {updated_count} community members.\n"
        f"These are delta updates from the latest data refresh cycle.\n\n"
        f"Contains only profiles that changed since last extraction.\n"
        f"Use for keeping agent personality models current.\n\n"
        f"Format: Markdown (SOUL.md) + JSON (structured). "
        f"Delivery: URL provided upon approval."
    )
    bounty = 0.04

    if dry_run:
        logger.info(f"  [DRY RUN] Would publish update: {title} (${bounty})")
        return None

    if not client.agent.can_spend(bounty):
        logger.warning(f"  SKIP: Budget limit")
        return None

    result = await client.publish_task(
        title=title,
        instructions=description,
        category="knowledge_access",
        bounty_usd=bounty,
        deadline_hours=24,
        evidence_required=["json_response"],
    )

    task_id = result.get("task", {}).get("id") or result.get("id", "unknown")
    logger.info(f"  Published profile updates: task_id={task_id}")
    client.agent.record_spend(bounty)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="Soul Extractor -- Complete Agent Profile Service")
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--discover", action="store_true", help="Only discover offerings")
    parser.add_argument("--process", action="store_true", help="Only process local data")
    parser.add_argument("--sell", action="store_true", help="Only publish products")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = Path(args.workspace) if args.workspace else base / "data" / "workspaces" / "kk-soul-extractor"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-soul-extractor",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    print(f"\n{'=' * 60}")
    print(f"  Soul Extractor -- Complete Agent Profile Service")
    print(f"  Agent: {agent.name}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    client = EMClient(agent)
    run_all = not (args.discover or args.process or args.sell)

    try:
        if args.discover or run_all:
            logger.info("Phase: Discover enriched data offerings")
            offerings = await discover_data_offerings(client)

            if run_all:
                # Buy first matching skill offering
                for offering in offerings.get("skills", [])[:1]:
                    await buy_data(client, offering, "skill", dry_run=args.dry_run)
                # Buy first matching voice offering
                for offering in offerings.get("voices", [])[:1]:
                    await buy_data(client, offering, "voice", dry_run=args.dry_run)

        if args.process or run_all:
            logger.info("Phase: Process and merge profiles")
            stats = await process_souls(data_dir)
            if stats:
                if args.sell or run_all:
                    logger.info("Phase: Publish soul profiles")
                    await publish_soul_profiles(client, data_dir, stats, dry_run=args.dry_run)
                    await publish_profile_updates(client, stats, dry_run=args.dry_run)

        logger.info(f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
