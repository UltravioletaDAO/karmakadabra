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
    },
}

SUPPLY_CHAIN_STEPS = ["raw_logs", "skill_profiles", "voice_profiles", "soul_profiles"]


# ---------------------------------------------------------------------------
# run_cycle() — callable from heartbeat.py
# ---------------------------------------------------------------------------


async def run_cycle(
    data_dir: Path,
    workspace_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Execute one heartbeat of the buyer escrow flow.

    Each heartbeat:
      1. Publish bounty for current step (if not active)
      2. Manage ALL bounties (assign + approve)
      3. Advance step if current bounty completed
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

    stats: dict = {
        "step": current_step,
        "cycle_count": state.get("cycle_count", 0),
        "published": 0,
        "assigned": 0,
        "approved": 0,
        "completed": 0,
        "errors": [],
    }

    try:
        logger.info(
            f"Buyer flow step: {current_step} "
            f"(cycle #{state.get('cycle_count', 0)})"
        )

        # Phase 1: Publish bounty for current step
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
            )
            if task_id:
                stats["published"] = 1

        # Phase 2: Manage ALL active bounties (assign + approve)
        mgmt = await manage_bounties(client, state, dry_run=dry_run)
        stats["assigned"] = mgmt["assigned"]
        stats["approved"] = mgmt["approved"]
        stats["completed"] = mgmt["completed"]

        # Phase 3: Advance step if current bounty completed
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
                    # Full cycle complete!
                    state["cycle_count"] = state.get("cycle_count", 0) + 1
                    state["current_step"] = "raw_logs"
                    # Clear completed bounties for fresh cycle
                    state["published"] = {
                        k: v
                        for k, v in state.get("published", {}).items()
                        if v.get("status") not in ("completed", "cancelled", "expired")
                    }
                    logger.info(
                        f"Supply chain cycle #{state['cycle_count']} COMPLETE! "
                        f"Resetting to raw_logs."
                    )
                break

        logger.info(
            f"Buyer flow: step={stats['step']}, "
            f"published={stats['published']}, assigned={stats['assigned']}, "
            f"approved={stats['approved']}, completed={stats['completed']}"
        )

    except Exception as e:
        stats["errors"].append(str(e))
        logger.error(f"Buyer flow error: {e}")
    finally:
        if not dry_run:
            save_escrow_state(data_dir, state)
        await client.close()

    return stats


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
