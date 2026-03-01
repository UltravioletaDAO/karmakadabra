"""
Karma Kadabra V2 — Community Buyer Service (Correct Escrow Flow)

juanjumagalp operates as a BUYER in the EM escrow system:
  1. PUBLISH bounty tasks requesting data from the supply chain
  2. ASSIGN sellers that apply to fulfill
  3. APPROVE submissions -> payment released (87% seller, 13% fee)

Supply chain (buy side, sequential):
  Step 1: Request raw chat logs      -> karma-hello fulfills    ($0.01)
  Step 2: Request skill profiles     -> skill-extractor fulfills ($0.05)
  Step 3: Request voice profiles     -> voice-extractor fulfills ($0.04)
  Step 4: Request SOUL.md profiles   -> soul-extractor fulfills  ($0.08)
  Total per full cycle: $0.18

Each heartbeat:
  - Publishes bounty for current step (if not already active)
  - Manages ALL active bounties (assign applicants, approve submissions)
  - Advances to next step when current bounty completes

Usage:
  python community_buyer_service.py                 # Full cycle
  python community_buyer_service.py --discover      # Check active bounties
  python community_buyer_service.py --dry-run       # Preview all actions
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from em_client import AgentContext, EMClient, load_agent_context
from escrow_flow import (
    discover_bounties,
    load_escrow_state,
    manage_bounties,
    publish_bounty,
    save_escrow_state,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.community-buyer")


# ---------------------------------------------------------------------------
# Bounty definitions — what juanjumagalp wants to buy
# ---------------------------------------------------------------------------

BOUNTIES = {
    "raw_logs": {
        "title": "[KK Request] Raw Twitch Chat Logs - Ultravioleta DAO",
        "instructions": (
            "Looking for raw chat logs from Ultravioleta DAO Twitch streams.\n\n"
            "Requirements:\n"
            "- JSON format: array of {timestamp, user, message}\n"
            "- Minimum 1000 messages\n"
            "- Include date range and stream count\n\n"
            "Delivery: provide presigned S3 URL or inline JSON data.\n"
            "Payment: $0.01 USDC on Base via EM escrow."
        ),
        "bounty_usd": 0.01,
        "priority": 1,
        "target_executor": "agent",
        "skills_required": ["data_collection", "chat_logs"],
    },
    "skill_profiles": {
        "title": "[KK Request] Enriched Skill Profiles - Community Members",
        "instructions": (
            "Looking for machine-extracted skill profiles of Ultravioleta DAO members.\n\n"
            "Requirements:\n"
            "- Per profile: username, top_skills (ranked with confidence), languages\n"
            "- Extracted from chat behavior (not self-reported)\n"
            "- Minimum 50 profiles\n\n"
            "Delivery: JSON array of profile objects.\n"
            "Payment: $0.05 USDC on Base via EM escrow."
        ),
        "bounty_usd": 0.05,
        "priority": 2,
        "target_executor": "agent",
        "skills_required": ["nlp", "skill_extraction", "data_analysis"],
    },
    "voice_profiles": {
        "title": "[KK Request] Voice & Personality Profiles - Community Members",
        "instructions": (
            "Looking for communication pattern analysis of community members.\n\n"
            "Requirements:\n"
            "- Per profile: tone, formality, greeting_style, slang_profile, social_role\n"
            "- Based on message analysis (not surveys)\n"
            "- Minimum 50 profiles\n\n"
            "Delivery: JSON array of profile objects.\n"
            "Payment: $0.04 USDC on Base via EM escrow."
        ),
        "bounty_usd": 0.04,
        "priority": 3,
        "target_executor": "agent",
        "skills_required": ["nlp", "personality_analysis", "linguistics"],
    },
    "soul_profiles": {
        "title": "[KK Request] SOUL.md Complete Profiles - Community Members",
        "instructions": (
            "Looking for complete personality profiles merging skills + voice analysis.\n\n"
            "Requirements:\n"
            "- SOUL.md format with structured sections\n"
            "- Combines skill data + personality data\n"
            "- Minimum 30 complete profiles\n\n"
            "Delivery: JSON array or ZIP of markdown files.\n"
            "Payment: $0.08 USDC on Base via EM escrow."
        ),
        "bounty_usd": 0.08,
        "priority": 4,
        "target_executor": "agent",
        "skills_required": ["data_synthesis", "profile_generation"],
    },
}

SUPPLY_CHAIN_STEPS = ["raw_logs", "skill_profiles", "voice_profiles", "soul_profiles"]

# ---------------------------------------------------------------------------
# Phase 3: Entrepreneurial bounties — tasks for HUMANS (agent-to-human flow)
# Published after completing autodiscovery (cycle >= 1)
# ---------------------------------------------------------------------------

ENTREPRENEUR_BOUNTIES = [
    {
        "title": "[KK Agent] Research: Top DeFi Yield Opportunities This Week",
        "instructions": (
            "Research the top 5 DeFi yield farming opportunities available this week.\n\n"
            "Requirements:\n"
            "- Include protocol name, chain, APY, TVL, and risk level\n"
            "- Only include opportunities with >$1M TVL\n"
            "- Mention any recent security audits or incidents\n\n"
            "Delivery: JSON or markdown report.\n"
            "This task is posted by an AI agent and can be fulfilled by a human."
        ),
        "bounty_usd": 0.02,
        "category": "entrepreneur_research",
        "target_executor": "human",
        "skills_required": ["defi", "research", "risk_assessment"],
    },
    {
        "title": "[KK Agent] Data: Active AI Agents on Base Chain",
        "instructions": (
            "Compile a list of AI agents actively operating on Base chain.\n\n"
            "Requirements:\n"
            "- Agent name, wallet address, what they do\n"
            "- Check for .well-known/agent-card endpoints\n"
            "- Include any ERC-8004 registrations\n"
            "- Minimum 10 agents\n\n"
            "Delivery: JSON array of agent profiles.\n"
            "This task is posted by an AI agent and can be fulfilled by a human."
        ),
        "bounty_usd": 0.04,
        "category": "entrepreneur_data",
        "target_executor": "human",
        "skills_required": ["blockchain", "web3", "data_compilation"],
    },
    {
        "title": "[KK Agent] Research: DAO Governance Activity Report",
        "instructions": (
            "Analyze governance activity across top 10 DAOs by treasury size.\n\n"
            "Requirements:\n"
            "- Proposals submitted/passed in last 30 days\n"
            "- Voter participation rates\n"
            "- Notable proposals or controversies\n\n"
            "Delivery: Structured JSON or markdown report.\n"
            "This task is posted by an AI agent and can be fulfilled by a human."
        ),
        "bounty_usd": 0.03,
        "category": "entrepreneur_research",
        "target_executor": "human",
        "skills_required": ["governance", "analytics", "research"],
    },
    {
        "title": "[KK Agent] Verify: Smart Contract Security Quick Check",
        "instructions": (
            "Quick security review of 3 specified smart contracts.\n\n"
            "Requirements:\n"
            "- Check for common vulnerabilities (reentrancy, overflow, access control)\n"
            "- Verify if contracts are verified on block explorer\n"
            "- Check for recent audit reports\n"
            "- Contracts: [will be specified in comments]\n\n"
            "Delivery: Security assessment per contract.\n"
            "This task is posted by an AI agent and can be fulfilled by a human."
        ),
        "bounty_usd": 0.05,
        "category": "entrepreneur_verify",
        "target_executor": "human",
        "skills_required": ["solidity", "security_audit", "smart_contracts"],
    },
    {
        "title": "[KK Agent] Content: Explain Agent Economy in a Twitter Thread",
        "instructions": (
            "Write a Twitter thread (8-12 tweets) explaining how autonomous AI agents\n"
            "buy and sell data using blockchain micropayments.\n\n"
            "Requirements:\n"
            "- Use the KarmaCadabra supply chain as example\n"
            "- Explain: agent discovery, x402 payments, ERC-8004 identity\n"
            "- Make it accessible to non-technical audience\n"
            "- Include suggested images/diagrams descriptions\n\n"
            "Delivery: Thread text ready to post.\n"
            "This task is posted by an AI agent and can be fulfilled by a human."
        ),
        "bounty_usd": 0.05,
        "category": "entrepreneur_content",
        "target_executor": "human",
        "skills_required": ["writing", "crypto_content", "marketing"],
    },
]


# ---------------------------------------------------------------------------
# run_cycle() — callable from heartbeat.py
# ---------------------------------------------------------------------------


async def run_cycle(
    data_dir: Path,
    workspace_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Execute one heartbeat of the buyer escrow flow.

    Cycle 0: Autodiscovery — buy raw_logs > skills > voice > soul
    Cycle 1+: Entrepreneurial — publish tasks for humans + browse opportunities
    """
    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-juanjumagalp",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    client = EMClient(agent)
    state = load_escrow_state(data_dir)

    # Initialize step tracking
    if "current_step" not in state:
        state["current_step"] = "raw_logs"
    if "cycle_count" not in state:
        state["cycle_count"] = 0

    current_step = state["current_step"]
    cycle_count = state.get("cycle_count", 0)

    stats: dict = {
        "step": current_step,
        "cycle_count": cycle_count,
        "published": 0,
        "assigned": 0,
        "approved": 0,
        "completed": 0,
        "entrepreneur_published": 0,
        "errors": [],
    }

    try:
        # Route to correct mode based on cycle count
        if cycle_count >= 1:
            # Post-autodiscovery: entrepreneurial mode
            stats["step"] = "entrepreneur"
            state["current_step"] = "entrepreneur"
            await _run_entrepreneur_cycle(client, state, stats, dry_run)
        else:
            # Autodiscovery mode: buy supply chain data
            await _run_autodiscovery_cycle(
                client, state, stats, current_step, dry_run,
            )

        logger.info(
            f"Buyer flow: step={stats['step']}, "
            f"published={stats['published']}, assigned={stats['assigned']}, "
            f"approved={stats['approved']}, completed={stats['completed']}"
            + (f", entrepreneur={stats['entrepreneur_published']}" if stats["entrepreneur_published"] else "")
        )

    except Exception as e:
        stats["errors"].append(str(e))
        logger.error(f"Buyer flow error: {e}")
    finally:
        if not dry_run:
            save_escrow_state(data_dir, state)
        await client.close()

    return stats


async def _run_autodiscovery_cycle(
    client: EMClient,
    state: dict,
    stats: dict,
    current_step: str,
    dry_run: bool,
) -> None:
    """Cycle 0: Buy supply chain data (logs > skills > voice > soul)."""
    logger.info(
        f"Buyer flow step: {current_step} "
        f"(cycle #{state.get('cycle_count', 0)})"
    )

    # Publish bounty for current step
    bounty_def = BOUNTIES.get(current_step)
    if bounty_def:
        task_id = await publish_bounty(
            client=client,
            title=bounty_def["title"],
            instructions=bounty_def["instructions"],
            bounty_usd=bounty_def["bounty_usd"],
            category_key=current_step,
            state=state,
            dry_run=dry_run,
            target_executor=bounty_def.get("target_executor", "agent"),
            skills_required=bounty_def.get("skills_required"),
        )
        if task_id:
            stats["published"] = 1

    # Manage ALL active bounties (assign + approve)
    mgmt = await manage_bounties(client, state, dry_run=dry_run)
    stats["assigned"] = mgmt["assigned"]
    stats["approved"] = mgmt["approved"]
    stats["completed"] = mgmt["completed"]

    # Advance step if current bounty completed
    for tid, info in state.get("published", {}).items():
        if (
            info.get("category") == current_step
            and info.get("status") == "completed"
        ):
            idx = (
                SUPPLY_CHAIN_STEPS.index(current_step)
                if current_step in SUPPLY_CHAIN_STEPS
                else -1
            )
            if idx >= 0 and idx < len(SUPPLY_CHAIN_STEPS) - 1:
                next_step = SUPPLY_CHAIN_STEPS[idx + 1]
                state["current_step"] = next_step
                logger.info(f"Advanced to step: {next_step}")
            else:
                # Full cycle complete — enter entrepreneurial mode
                state["cycle_count"] = state.get("cycle_count", 0) + 1
                state["current_step"] = "raw_logs"
                state["published"] = {
                    k: v
                    for k, v in state.get("published", {}).items()
                    if v.get("status") not in ("completed", "cancelled", "expired")
                }
                logger.info(
                    f"Supply chain cycle #{state['cycle_count']} COMPLETE! "
                    f"Entering entrepreneurial mode."
                )
            break


async def _run_entrepreneur_cycle(
    client: EMClient,
    state: dict,
    stats: dict,
    dry_run: bool,
) -> None:
    """Cycle 1+: Entrepreneurial mode — publish tasks for humans, browse opportunities."""
    import random

    cycle = state.get("cycle_count", 1)
    logger.info(f"Entrepreneur mode (cycle #{cycle})")

    # 1. Manage existing bounties first (assign + approve any pending)
    mgmt = await manage_bounties(client, state, dry_run=dry_run)
    stats["assigned"] = mgmt["assigned"]
    stats["approved"] = mgmt["approved"]
    stats["completed"] = mgmt["completed"]

    # 2. Publish ONE new entrepreneur bounty per heartbeat (if budget allows)
    # Track which ones we've already published
    published_categories = set()
    for info in state.get("published", {}).values():
        cat = info.get("category", "")
        if cat.startswith("entrepreneur_") and info.get("status") not in (
            "completed", "cancelled", "expired",
        ):
            published_categories.add(cat)

    # Find a bounty we haven't published yet
    available = [
        b for b in ENTREPRENEUR_BOUNTIES
        if b["category"] not in published_categories
    ]

    if available:
        bounty = random.choice(available)
        task_id = await publish_bounty(
            client=client,
            title=bounty["title"],
            instructions=bounty["instructions"],
            bounty_usd=bounty["bounty_usd"],
            category_key=bounty["category"],
            state=state,
            dry_run=dry_run,
            target_executor=bounty.get("target_executor", "human"),
            skills_required=bounty.get("skills_required"),
        )
        if task_id:
            stats["entrepreneur_published"] = 1
            stats["published"] = 1
            logger.info(f"Entrepreneur bounty published: {bounty['title']}")
    else:
        logger.info("All entrepreneur bounties already active")

    # 3. Browse EM for tasks we could apply to (opportunity seeking)
    try:
        tasks = await client.browse_tasks(status="published", limit=20)
        opportunities = []
        for t in tasks:
            title = t.get("title", "")
            # Skip our own and KK system tasks
            if "[KK Request]" in title or "[KK Data]" in title or "[KK Agent]" in title:
                continue
            bounty = t.get("bounty_amount", 0)
            if bounty and bounty > 0:
                opportunities.append(t)

        if opportunities:
            stats["opportunities_found"] = len(opportunities)
            logger.info(f"Found {len(opportunities)} external opportunities on EM")
    except Exception as e:
        logger.debug(f"Opportunity browse (non-fatal): {e}")


# ---------------------------------------------------------------------------
# main() — standalone execution
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(
        description="Community Buyer — Bounty Poster Service (Correct Escrow Flow)"
    )
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--discover", action="store_true", help="Show active bounties")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = (
        Path(args.workspace)
        if args.workspace
        else base / "data" / "workspaces" / "kk-juanjumagalp"
    )
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-juanjumagalp",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    print(f"\n{'=' * 60}")
    print(f"  Community Buyer — Bounty Poster (Correct Escrow Flow)")
    print(f"  Agent: {agent.name}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    if args.discover:
        state = load_escrow_state(data_dir)
        print(f"  Current step: {state.get('current_step', 'raw_logs')}")
        print(f"  Cycle count: {state.get('cycle_count', 0)}")
        print(f"  Active bounties:")
        for tid, info in state.get("published", {}).items():
            print(
                f"    - [{info.get('status', '?')}] {info.get('title', '?')} "
                f"(${info.get('bounty', 0)})"
            )
        return

    result = await run_cycle(
        data_dir=data_dir,
        workspace_dir=workspace_dir,
        dry_run=args.dry_run,
    )
    print(f"\n  Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
