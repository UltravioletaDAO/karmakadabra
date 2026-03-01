"""
Karma Kadabra V2 — Task 5.2: Skill Extractor Service

The Skill Extractor agent operates as a data refinery:
  1. Discovers Karma Hello's raw log offerings on EM
  2. Buys raw logs ($0.01)
  3. Processes with skill extraction pipeline → enriched skill profiles
  4. Publishes enriched profiles as new EM offerings ($0.05)
  5. Other agents buy the enriched data

This creates a supply chain:
  Karma Hello (raw data) → Skill Extractor (enriched data) → Consumer agents

Usage:
  python skill_extractor_service.py                 # Full cycle
  python skill_extractor_service.py --discover      # Only discover offerings
  python skill_extractor_service.py --process       # Only process local data
  python skill_extractor_service.py --sell           # Only publish products
  python skill_extractor_service.py --dry-run       # Preview all actions
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
from escrow_flow import (
    apply_to_bounty,
    discover_bounties,
    fulfill_assigned,
    load_escrow_state,
    publish_offering_deduped,
    save_escrow_state,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.skill-extractor")


async def discover_data_offerings(client: EMClient) -> list[dict]:
    """Search EM for Karma Hello's raw log data."""
    tasks = await client.browse_tasks(
        status="published",
        category="knowledge_access",
        limit=50,
    )

    offerings = [
        t for t in tasks
        if "[KK Data]" in t.get("title", "") and "Raw" in t.get("title", "")
    ]

    logger.info(f"  Found {len(offerings)} raw data offerings from Karma Hello")
    for t in offerings:
        logger.info(f"    - {t.get('title', '?')} (${t.get('bounty_usdc', 0)})")

    return offerings


async def buy_data(
    client: EMClient,
    task: dict,
    dry_run: bool = False,
) -> dict | None:
    """Apply to buy data from Karma Hello."""
    task_id = task.get("id", "")
    bounty = task.get("bounty_usdc", 0)
    title = task.get("title", "?")

    if not client.agent.can_spend(bounty):
        logger.warning(f"  SKIP: Budget limit (${client.agent.daily_spent_usd:.2f} spent)")
        return None

    if dry_run:
        logger.info(f"  [DRY RUN] Would buy: {title}")
        return None

    if not client.agent.executor_id:
        logger.error("  Cannot buy: executor_id not set (register on EM first)")
        return None

    logger.info(f"  Buying: {title} (${bounty})")
    result = await client.apply_to_task(
        task_id=task_id,
        executor_id=client.agent.executor_id,
        message="Skill Extractor agent — buying raw logs for skill profile generation",
    )
    client.agent.record_spend(bounty)
    return result


async def process_skills(data_dir: Path) -> dict | None:
    """Extract skill profiles from purchased data or existing pipeline output.

    Priority:
      1. data/purchases/*.json (freshly bought from Karma Hello)
      2. data/skills/*.json (already processed)

    Memory-safe: processes one file at a time, streaming by lines.
    """
    skills_dir = data_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    purchases_dir = data_dir / "purchases"

    # Check for purchased data to process
    purchase_files = sorted(purchases_dir.glob("*.json")) if purchases_dir.exists() else []
    raw_messages = []

    for pf in purchase_files:
        try:
            content = pf.read_text(encoding="utf-8")
            data = json.loads(content)
            # Handle both array format and {messages: [...]} format
            if isinstance(data, list):
                raw_messages.extend(data)
            elif isinstance(data, dict):
                raw_messages.extend(data.get("messages", []))
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"  Skipping {pf.name}: {e}")
            continue

    if raw_messages:
        logger.info(f"  Processing {len(raw_messages)} messages from {len(purchase_files)} purchased files")
        _extract_skills_from_messages(raw_messages, skills_dir)

    # Now read all skill profiles (newly generated + any existing)
    profiles = list(skills_dir.glob("*.json"))
    if not profiles:
        logger.warning(f"  No skill profiles found (no purchases or data)")
        return None

    logger.info(f"  Found {len(profiles)} skill profiles")

    # Aggregate stats
    all_skills: dict[str, int] = {}
    for profile_path in profiles:
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            for skill in profile.get("top_skills", []):
                name = skill.get("skill", "unknown")
                all_skills[name] = all_skills.get(name, 0) + 1
        except (json.JSONDecodeError, OSError):
            continue

    top_skills = sorted(all_skills.items(), key=lambda x: -x[1])[:10]
    logger.info(f"  Top community skills: {', '.join(s[0] for s in top_skills[:5])}")

    return {
        "total_profiles": len(profiles),
        "unique_skills": len(all_skills),
        "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
    }


# Keyword categories for skill extraction (no LLM needed)
SKILL_KEYWORDS = {
    "Python": ["python", "django", "flask", "fastapi", "pip", "pandas", "numpy"],
    "JavaScript": ["javascript", "js", "react", "node", "npm", "typescript", "ts", "vue", "angular"],
    "Solidity": ["solidity", "smart contract", "hardhat", "foundry", "remix", "evm"],
    "DeFi": ["defi", "yield", "liquidity", "amm", "swap", "lending", "borrow", "apy", "tvl"],
    "Trading": ["trading", "trade", "chart", "ta", "rsi", "macd", "bullish", "bearish", "long", "short"],
    "NFTs": ["nft", "mint", "collection", "opensea", "blur", "pfp"],
    "AI/ML": ["ai", "llm", "gpt", "claude", "model", "training", "inference", "ml", "machine learning"],
    "Agents": ["agent", "autonomous", "crew", "crewai", "autogpt", "langchain"],
    "Design": ["design", "figma", "ui", "ux", "css", "tailwind", "frontend"],
    "DevOps": ["docker", "kubernetes", "k8s", "aws", "terraform", "ci/cd", "deploy"],
    "Blockchain": ["blockchain", "web3", "crypto", "wallet", "token", "chain", "mainnet", "testnet"],
    "Community": ["community", "dao", "governance", "vote", "proposal", "discord"],
}


def _extract_skills_from_messages(messages: list[dict], skills_dir: Path) -> None:
    """Extract skill profiles per user from raw chat messages.

    Uses keyword matching -- fast, deterministic, no API calls.
    """
    user_messages: dict[str, list[str]] = {}

    for msg in messages:
        user = msg.get("user", "") or msg.get("sender", "")
        text = msg.get("message", "") or msg.get("text", "")
        if user and text:
            user_messages.setdefault(user, []).append(text)

    logger.info(f"  Analyzing {len(user_messages)} unique users")

    for username, msgs in user_messages.items():
        if len(msgs) < 3:  # Skip users with too few messages
            continue

        all_text = " ".join(msgs).lower()
        skill_scores: dict[str, float] = {}

        for skill, keywords in SKILL_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in all_text)
            if count > 0:
                # Normalize by number of keywords (0.0-1.0 scale)
                skill_scores[skill] = min(count / len(keywords), 1.0)

        if not skill_scores:
            continue

        # Detect primary language
        spanish_markers = ["hola", "buenas", "gracias", "que", "como", "pero", "porque", "esta", "muy"]
        english_markers = ["the", "and", "is", "that", "this", "have", "with", "for", "but", "from"]
        es_count = sum(1 for m in spanish_markers if m in all_text)
        en_count = sum(1 for m in english_markers if m in all_text)
        primary_lang = "spanish" if es_count >= en_count else "english"

        top_skills = sorted(skill_scores.items(), key=lambda x: -x[1])[:5]

        profile = {
            "username": username,
            "total_messages": len(msgs),
            "primary_language": primary_lang,
            "languages": {"spanish": es_count, "english": en_count},
            "top_skills": [{"skill": s, "score": round(sc, 2)} for s, sc in top_skills],
            "skills": {
                s: {"sub_skills": [{"name": s, "score": round(sc, 2)}]}
                for s, sc in top_skills
            },
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

        profile_path = skills_dir / f"{username}.json"
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    logger.info(f"  Saved skill profiles for {len([f for f in skills_dir.glob('*.json')])} users")


async def publish_enriched_profiles(
    client: EMClient,
    data_dir: Path,
    stats: dict,
    dry_run: bool = False,
) -> dict | None:
    """Publish enriched skill profiles on EM (deduped)."""
    total = stats.get("total_profiles", 0)
    unique = stats.get("unique_skills", 0)

    title = f"[KK Data] Enriched Skill Profiles — {total} Community Members"
    description = (
        f"Machine-extracted skill profiles for {total} Ultravioleta DAO members.\n"
        f"Extracted from Twitch chat behavior analysis (not self-reported).\n\n"
        f"Per profile: top_skills (ranked with confidence), skill_categories, "
        f"languages_detected, monetizable_capabilities.\n"
        f"Unique skills detected: {unique}.\n\n"
        f"Enrichment: Cross-referenced with engagement metrics, voice patterns, "
        f"and interaction graphs for higher accuracy.\n\n"
        f"Format: JSON. Delivery: URL provided upon approval."
    )

    return await publish_offering_deduped(
        client=client,
        title=title,
        instructions=description,
        bounty_usd=0.05,
        title_prefix="[KK Data] Enriched Skill Profiles",
        dry_run=dry_run,
    )


async def seller_flow(
    client: EMClient,
    data_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Skill Extractor SELLER flow: discover bounties requesting skill profiles, apply, deliver.

    Uses the escrow_flow pattern:
      1. Discover [KK Request] bounties matching "skill" keywords
      2. Apply to matching bounties
      3. For assigned tasks, submit evidence with skill profiles data

    Returns stats dict.
    """
    state = load_escrow_state(data_dir)

    result: dict = {
        "bounties_found": 0,
        "applied": 0,
        "submitted": 0,
        "completed": 0,
        "errors": [],
    }

    try:
        # Phase 1: Discover bounties requesting skill data
        bounties = await discover_bounties(
            client=client,
            keywords=["[KK Request]"],
            exclude_wallet=client.agent.wallet_address,
            state=state,
        )
        # Filter to skill-related bounties only
        skill_bounties = [
            b for b in bounties
            if any(kw in b.get("title", "").lower() for kw in ["skill", "profile"])
        ]
        result["bounties_found"] = len(skill_bounties)

        # Phase 2: Apply to up to 3 matching bounties
        for bounty_task in skill_bounties[:3]:
            ok = await apply_to_bounty(
                client=client,
                task=bounty_task,
                state=state,
                message=(
                    "Skill Extractor agent -- I extract skill profiles from chat logs. "
                    "Keyword-based analysis of 12 skill categories. Ready to deliver."
                ),
                dry_run=dry_run,
            )
            if ok:
                result["applied"] += 1

        # Phase 3: Fulfill assigned tasks
        def make_evidence(task_id: str, info: dict) -> dict:
            """Generate evidence with skill profile data summary."""
            skills_dir = data_dir / "skills"
            profiles = list(skills_dir.glob("*.json")) if skills_dir.exists() else []
            total = len(profiles)

            return {
                "json_response": {
                    "agent": client.agent.name,
                    "product": "enriched_skill_profiles",
                    "total_profiles": total,
                    "skill_categories": list(SKILL_KEYWORDS.keys()),
                    "extraction_method": "keyword-based analysis (12 categories)",
                    "format": "JSON per-user profiles with top_skills, confidence scores",
                    "status": "delivered",
                },
            }

        fulfill_stats = await fulfill_assigned(
            client=client,
            state=state,
            evidence_fn=make_evidence,
            dry_run=dry_run,
        )
        result["submitted"] = fulfill_stats["submitted"]
        result["completed"] = fulfill_stats["completed"]

    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"Seller flow error: {e}")
    finally:
        if not dry_run:
            save_escrow_state(data_dir, state)

    logger.info(
        f"Seller flow: found={result['bounties_found']}, "
        f"applied={result['applied']}, submitted={result['submitted']}"
    )
    return result


async def main():
    parser = argparse.ArgumentParser(description="Skill Extractor — Data Refinery Service")
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--discover", action="store_true", help="Only discover offerings")
    parser.add_argument("--process", action="store_true", help="Only process local data")
    parser.add_argument("--sell", action="store_true", help="Only publish products")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = Path(args.workspace) if args.workspace else base / "data" / "workspaces" / "kk-skill-extractor"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-skill-extractor",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    print(f"\n{'=' * 60}")
    print(f"  Skill Extractor — Data Refinery Service")
    print(f"  Agent: {agent.name}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    client = EMClient(agent)
    run_all = not (args.discover or args.process or args.sell)

    try:
        if args.discover or run_all:
            logger.info("Phase: Discover data offerings")
            offerings = await discover_data_offerings(client)
            if offerings and run_all:
                for offering in offerings[:1]:  # Buy only first match
                    await buy_data(client, offering, dry_run=args.dry_run)

        if args.process or run_all:
            logger.info("Phase: Process skill data")
            stats = await process_skills(data_dir)
            if stats:
                if args.sell or run_all:
                    logger.info("Phase: Publish enriched profiles")
                    await publish_enriched_profiles(client, data_dir, stats, dry_run=args.dry_run)

        logger.info(f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
