"""
Karma Kadabra V2 -- Community Buyer Service

A community buyer agent (kk-juanjumagalp) that operates as a pure consumer
in the KK agent supply chain. It discovers and purchases data products from
the system agents:

  Supply chain (buy side):
    1. Raw chat logs from Karma Hello ($0.01)
    2. Skill profiles from Skill Extractor ($0.05)
    3. Voice/personality profiles from Voice Extractor ($0.04)
    4. SOUL.md profiles from Soul Extractor ($0.08)

  Total cost per full cycle: $0.18

Unlike system agents that buy inputs to produce outputs, community buyers
consume data for their own use (research, analysis, personalization).

Usage:
  python community_buyer_service.py                 # Full buy cycle
  python community_buyer_service.py --discover      # Only discover offerings
  python community_buyer_service.py --dry-run       # Preview all actions
  python community_buyer_service.py --workspace /path/to/workspace
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
logger = logging.getLogger("kk.community-buyer")


# ---------------------------------------------------------------------------
# Data category definitions
# ---------------------------------------------------------------------------

CATEGORIES = {
    "raw_logs": {
        "label": "Raw Chat Logs",
        "keywords": ["Raw", "Chat Log"],
        "max_price": 0.02,
        "priority": 1,
    },
    "skill_profiles": {
        "label": "Skill Profiles",
        "keywords": ["Skill"],
        "max_price": 0.06,
        "priority": 2,
    },
    "voice_profiles": {
        "label": "Voice/Personality Profiles",
        "keywords": ["Personality", "Voice"],
        "max_price": 0.05,
        "priority": 3,
    },
    "soul_profiles": {
        "label": "SOUL.md Profiles",
        "keywords": ["Soul", "SOUL"],
        "max_price": 0.10,
        "priority": 4,
    },
}


def categorize_offering(task: dict) -> str | None:
    """Classify a task into one of the known data categories.

    Returns the category key or None if the task does not match any category.
    Checks categories in priority order so that more specific matches
    (e.g. "Skill") are not accidentally captured by broader ones.
    """
    title = task.get("title", "")

    # Check in reverse priority so more specific categories match first.
    # "Soul" before "Skill" before "Voice" before "Raw" avoids false positives
    # since some titles might contain overlapping keywords.
    for cat_key in sorted(CATEGORIES, key=lambda k: -CATEGORIES[k]["priority"]):
        cat = CATEGORIES[cat_key]
        for keyword in cat["keywords"]:
            if keyword in title:
                return cat_key
    return None


# ---------------------------------------------------------------------------
# Phase 1: Discover available KK data offerings
# ---------------------------------------------------------------------------


async def discover_offerings(client: EMClient) -> dict[str, list[dict]]:
    """Browse EM for [KK Data] offerings and categorize them."""
    tasks = await client.browse_tasks(
        status="published",
        category="knowledge_access",
    )

    kk_tasks = [t for t in tasks if "[KK Data]" in t.get("title", "")]
    logger.info(f"  Found {len(kk_tasks)} [KK Data] offerings on EM")

    categorized: dict[str, list[dict]] = {key: [] for key in CATEGORIES}
    uncategorized: list[dict] = []

    for task in kk_tasks:
        cat = categorize_offering(task)
        if cat:
            categorized[cat].append(task)
        else:
            uncategorized.append(task)

    for cat_key, cat_info in CATEGORIES.items():
        offerings = categorized[cat_key]
        if offerings:
            # Sort by price ascending (cheapest first)
            offerings.sort(key=lambda t: t.get("bounty_usdc", 0))
            logger.info(
                f"  [{cat_info['label']}] {len(offerings)} offerings, "
                f"cheapest: ${offerings[0].get('bounty_usdc', 0)}"
            )
        else:
            logger.info(f"  [{cat_info['label']}] No offerings found")

    if uncategorized:
        logger.info(f"  [Uncategorized] {len(uncategorized)} offerings skipped")

    return categorized


# ---------------------------------------------------------------------------
# Phase 2: Buy one offering per category (cheapest first, budget permitting)
# ---------------------------------------------------------------------------


async def buy_offering(
    client: EMClient,
    task: dict,
    category_label: str,
    dry_run: bool = False,
) -> dict | None:
    """Apply to buy a single data offering."""
    task_id = task.get("id", "")
    bounty = task.get("bounty_usdc", 0)
    title = task.get("title", "?")

    if not client.agent.can_spend(bounty):
        logger.warning(
            f"  SKIP [{category_label}]: Budget limit "
            f"(${client.agent.daily_spent_usd:.2f} spent)"
        )
        return None

    if dry_run:
        logger.info(f"  [DRY RUN] Would buy [{category_label}]: {title} (${bounty})")
        return None

    if not client.agent.executor_id:
        logger.error("  Cannot buy: executor_id not set (register on EM first)")
        return None

    logger.info(f"  Buying [{category_label}]: {title} (${bounty})")
    result = await client.apply_to_task(
        task_id=task_id,
        executor_id=client.agent.executor_id,
        message=f"Community buyer agent -- purchasing {category_label.lower()} for research and analysis",
    )
    client.agent.record_spend(bounty)
    return result


async def buy_cycle(
    client: EMClient,
    categorized: dict[str, list[dict]],
    dry_run: bool = False,
) -> dict:
    """Buy one offering per category in priority order (cheapest first).

    Returns stats dict with purchase results.
    """
    purchased = 0
    spent = 0.0
    errors: list[str] = []

    # Process categories in priority order (lowest number = highest priority)
    for cat_key in sorted(CATEGORIES, key=lambda k: CATEGORIES[k]["priority"]):
        cat_info = CATEGORIES[cat_key]
        offerings = categorized.get(cat_key, [])

        if not offerings:
            continue

        # Already sorted by price in discover_offerings; take cheapest
        best = offerings[0]
        bounty = best.get("bounty_usdc", 0)

        # Reject offerings above the category max price
        if bounty > cat_info["max_price"]:
            logger.info(
                f"  SKIP [{cat_info['label']}]: ${bounty} exceeds max ${cat_info['max_price']}"
            )
            continue

        try:
            result = await buy_offering(client, best, cat_info["label"], dry_run=dry_run)
            if result is not None:
                purchased += 1
                spent += bounty
        except Exception as exc:
            msg = f"Error buying {cat_info['label']}: {exc}"
            logger.error(f"  {msg}")
            errors.append(msg)

    return {
        "purchased": purchased,
        "spent": spent,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Phase 3: Save purchased data references to workspace
# ---------------------------------------------------------------------------


def save_purchase_log(workspace_dir: Path, stats: dict) -> None:
    """Persist a log of purchases to the workspace for audit trail."""
    purchases_dir = workspace_dir / "data" / "purchases"
    purchases_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = purchases_dir / f"buy_cycle_{ts}.json"

    log_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"  Purchase log saved: {log_path.name}")


# ---------------------------------------------------------------------------
# Supply chain state machine — one step per heartbeat
# ---------------------------------------------------------------------------

SUPPLY_CHAIN_STEPS = ["raw_logs", "skill_profiles", "voice_profiles", "soul_profiles", "complete"]


def _load_supply_chain_state(data_dir: Path) -> dict:
    """Load persistent supply chain state."""
    state_path = data_dir / "purchases" / "supply_chain_state.json"
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "step": "raw_logs",
        "completed": [],
        "pending_delivery": {},
        "downloaded": {},
        "cycle_count": 0,
    }


def _save_supply_chain_state(data_dir: Path, state: dict) -> None:
    """Persist supply chain state."""
    purchases_dir = data_dir / "purchases"
    purchases_dir.mkdir(parents=True, exist_ok=True)
    state_path = purchases_dir / "supply_chain_state.json"
    try:
        state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _advance_step(state: dict) -> None:
    """Advance to the next step in the supply chain."""
    current = state["step"]
    if current in SUPPLY_CHAIN_STEPS:
        idx = SUPPLY_CHAIN_STEPS.index(current)
        if idx < len(SUPPLY_CHAIN_STEPS) - 1:
            state["completed"].append(current)
            state["step"] = SUPPLY_CHAIN_STEPS[idx + 1]

    # Reset when complete
    if state["step"] == "complete":
        state["cycle_count"] = state.get("cycle_count", 0) + 1
        logger.info(f"  Supply chain cycle #{state['cycle_count']} COMPLETE!")
        state["step"] = "raw_logs"
        state["completed"] = []
        state["pending_delivery"] = {}
        state["downloaded"] = {}


# ---------------------------------------------------------------------------
# run_cycle() — callable from heartbeat.py
# ---------------------------------------------------------------------------


async def run_cycle(
    data_dir: Path,
    workspace_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Execute one step of the sequential supply chain buy cycle.

    Each heartbeat advances ONE step:
      raw_logs -> skill_profiles -> voice_profiles -> soul_profiles -> complete -> reset

    With 5-min heartbeats, a full cycle completes in ~25 minutes.
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
    chain_state = _load_supply_chain_state(data_dir)
    current_step = chain_state["step"]

    stats: dict = {
        "discovered": 0,
        "purchased": 0,
        "spent": 0.0,
        "errors": [],
        "step": current_step,
        "cycle_count": chain_state.get("cycle_count", 0),
    }

    try:
        logger.info(f"  Supply chain step: {current_step} (cycle #{chain_state.get('cycle_count', 0)})")

        # Discover offerings
        categorized = await discover_offerings(client)
        total_offerings = sum(len(v) for v in categorized.values())
        stats["discovered"] = total_offerings

        # Map step to category
        step_to_category = {
            "raw_logs": "raw_logs",
            "skill_profiles": "skill_profiles",
            "voice_profiles": "voice_profiles",
            "soul_profiles": "soul_profiles",
        }

        target_category = step_to_category.get(current_step)
        if not target_category:
            # Already complete or unknown step -- reset
            _advance_step(chain_state)
            _save_supply_chain_state(data_dir, chain_state)
            return stats

        offerings = categorized.get(target_category, [])
        cat_info = CATEGORIES[target_category]

        if not offerings:
            logger.info(f"  No {cat_info['label']} offerings available -- waiting")
            stats["errors"].append(f"No {cat_info['label']} available")
            return stats

        # Buy the cheapest offering in the target category
        best = offerings[0]
        bounty = best.get("bounty_usdc", 0)

        if bounty > cat_info["max_price"]:
            logger.info(f"  {cat_info['label']} too expensive: ${bounty} > max ${cat_info['max_price']}")
            return stats

        try:
            result = await buy_offering(client, best, cat_info["label"], dry_run=dry_run)
            if result is not None:
                stats["purchased"] = 1
                stats["spent"] = bounty

                # Submit evidence immediately
                if client.agent.executor_id and not dry_run:
                    try:
                        await client.submit_evidence(
                            task_id=best.get("id", ""),
                            executor_id=client.agent.executor_id,
                            evidence={"type": "json_response", "notes": f"Ready for {cat_info['label']} delivery"},
                        )
                    except Exception:
                        pass

                # Advance to next step
                _advance_step(chain_state)
                logger.info(f"  Advanced to step: {chain_state['step']}")
        except Exception as exc:
            stats["errors"].append(str(exc))

        if not dry_run:
            save_purchase_log(workspace_dir, stats)

        logger.info(
            f"  Step {current_step}: {stats['purchased']} purchased, "
            f"${stats['spent']:.2f} spent"
        )
    finally:
        if not dry_run:
            _save_supply_chain_state(data_dir, chain_state)
        await client.close()

    return stats


# ---------------------------------------------------------------------------
# main() — standalone execution
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(
        description="Community Buyer -- Data Consumer Service"
    )
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--discover", action="store_true", help="Only discover offerings")
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
    print(f"  Community Buyer -- Data Consumer Service")
    print(f"  Agent: {agent.name}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    client = EMClient(agent)

    try:
        logger.info("Phase: Discover data offerings")
        categorized = await discover_offerings(client)

        if args.discover:
            logger.info("  Discovery only -- skipping purchases")
            logger.info(
                f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}"
            )
            return

        total_offerings = sum(len(v) for v in categorized.values())
        if total_offerings == 0:
            logger.info("  No [KK Data] offerings available -- nothing to buy")
            return

        logger.info("Phase: Buy data (one per category, cheapest first)")
        buy_stats = await buy_cycle(client, categorized, dry_run=args.dry_run)

        if not args.dry_run and buy_stats["purchased"] > 0:
            save_purchase_log(workspace_dir, buy_stats)

        logger.info(
            f"  Cycle complete: {buy_stats['purchased']} purchased, "
            f"${buy_stats['spent']:.2f} spent, {len(buy_stats['errors'])} errors"
        )
        logger.info(
            f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}"
        )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
