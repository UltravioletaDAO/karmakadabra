"""
Karma Kadabra V2 — Escrow Flow Helpers

Reusable buyer/seller patterns for the correct Execution Market escrow flow.

Correct EM flow:
  1. BUYER publishes task with bounty      -> status: published
  2. SELLER discovers and applies          -> status: published (has applications)
  3. BUYER assigns seller                  -> status: accepted
  4. SELLER submits evidence               -> status: submitted
  5. BUYER approves                        -> status: completed (87% seller, 13% fee)

BUYER API:
  publish_bounty()    — Post a bounty task requesting data/service
  manage_bounties()   — Assign applicants + approve submissions

SELLER API:
  discover_bounties() — Browse EM for matching bounty tasks
  apply_to_bounty()   — Apply to fulfill a bounty
  fulfill_assigned()  — Submit evidence for assigned tasks
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import sys

sys.path.insert(0, str(Path(__file__).parent))

from em_client import EMClient

logger = logging.getLogger("kk.escrow")


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def load_escrow_state(data_dir: Path) -> dict:
    """Load escrow state from disk."""
    state_path = data_dir / "escrow_state.json"
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"published": {}, "applied": {}}


def save_escrow_state(data_dir: Path, state: dict) -> None:
    """Persist escrow state to disk."""
    data_dir.mkdir(parents=True, exist_ok=True)
    state_path = data_dir / "escrow_state.json"
    try:
        state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.error(f"Failed to save escrow state: {e}")


# ---------------------------------------------------------------------------
# BUYER SIDE — publish bounties, assign sellers, approve submissions
# ---------------------------------------------------------------------------


async def publish_bounty(
    client: EMClient,
    title: str,
    instructions: str,
    bounty_usd: float,
    category_key: str,
    state: dict,
    dry_run: bool = False,
) -> str | None:
    """Publish a bounty task requesting data/service.

    Deduplicates: skips if an active bounty for the same category_key exists.

    Returns task_id if published, None if skipped.
    """
    # Check for active bounty in same category
    for tid, info in state.get("published", {}).items():
        if (
            info.get("category") == category_key
            and info.get("status") not in ("completed", "cancelled", "expired")
        ):
            logger.info(f"Bounty active for {category_key}: {tid[:8]} — skipping")
            return None

    if not client.agent.can_spend(bounty_usd):
        logger.warning(f"Budget limit — cannot publish bounty for {category_key}")
        return None

    if dry_run:
        logger.info(f"[DRY RUN] Would publish bounty: {title} (${bounty_usd})")
        return None

    try:
        resp = await client.publish_task(
            title=title,
            instructions=instructions,
            category="knowledge_access",
            bounty_usd=bounty_usd,
            deadline_hours=24,
            evidence_required=["json_response"],
        )
        task_id = resp.get("task", {}).get("id") or resp.get("id", "")

        state.setdefault("published", {})[task_id] = {
            "title": title,
            "category": category_key,
            "status": "published",
            "bounty": bounty_usd,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        client.agent.record_spend(bounty_usd)
        logger.info(f"Published bounty: {title} (${bounty_usd}) -> {task_id[:8]}")
        return task_id
    except Exception as e:
        logger.error(f"Failed to publish bounty for {category_key}: {e}")
        return None


async def manage_bounties(
    client: EMClient,
    state: dict,
    dry_run: bool = False,
) -> dict[str, int]:
    """Check published bounties: assign applicants + approve submissions.

    Returns {assigned, approved, completed, errors} counts.
    """
    stats = {"assigned": 0, "approved": 0, "completed": 0, "errors": 0}
    published = state.get("published", {})

    for task_id, info in list(published.items()):
        status = info.get("status", "")

        if status in ("completed", "cancelled", "expired"):
            continue

        try:
            task_data = await client.get_task(task_id)
        except Exception as e:
            logger.debug(f"Check bounty {task_id[:8]} failed: {e}")
            stats["errors"] += 1
            continue

        em_status = task_data.get("status", "")

        # Sync terminal states
        if em_status in ("completed", "cancelled", "expired"):
            info["status"] = em_status
            if em_status == "completed":
                stats["completed"] += 1
            continue

        # Phase A: ASSIGN first applicant
        if em_status == "published":
            try:
                applications = await client.get_applications(task_id)
            except Exception as e:
                logger.debug(f"Get applications for {task_id[:8]} failed: {e}")
                applications = []

            if applications:
                applicant = applications[0]
                executor_id = applicant.get("executor_id", "")
                if executor_id and not dry_run:
                    try:
                        await client.assign_task(task_id, executor_id)
                        info["status"] = "accepted"
                        info["executor_id"] = executor_id
                        stats["assigned"] += 1
                        logger.info(
                            f"Assigned {executor_id[:8]} to: {info.get('title', '?')}"
                        )
                    except Exception as e:
                        if "409" not in str(e):
                            logger.error(f"Assign failed: {e}")
                            stats["errors"] += 1

        # Phase B: APPROVE submissions
        if em_status in ("submitted", "accepted", "in_progress"):
            try:
                submissions = await client.get_submissions(task_id)
            except Exception:
                continue

            for sub in submissions:
                sub_id = sub.get("id", "")
                sub_status = sub.get("status", "")
                if not sub_id or sub_status in ("approved", "rejected"):
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would approve submission {sub_id[:8]}")
                    stats["approved"] += 1
                    continue

                try:
                    await client.approve_submission(
                        sub_id,
                        rating_score=85,
                        notes="Auto-approved by KK buyer agent",
                    )
                    info["status"] = "completed"
                    stats["approved"] += 1
                    stats["completed"] += 1
                    logger.info(
                        f"Approved submission {sub_id[:8]} for: {info.get('title', '?')}"
                    )
                    break
                except Exception as e:
                    logger.error(f"Approve failed: {e}")
                    stats["errors"] += 1

        # Small delay between task checks to avoid 429
        await asyncio.sleep(0.5)

    return stats


# ---------------------------------------------------------------------------
# SELLER SIDE — discover bounties, apply, fulfill
# ---------------------------------------------------------------------------


async def discover_bounties(
    client: EMClient,
    keywords: list[str],
    exclude_wallet: str = "",
    state: dict | None = None,
) -> list[dict]:
    """Browse EM for bounty tasks matching ANY of the keywords.

    Args:
        keywords: Title keywords to match (case-insensitive).
        exclude_wallet: Skip tasks from this wallet (own tasks).
        state: If provided, skip already-applied tasks.

    Returns:
        List of matching task dicts, sorted by bounty ascending.
    """
    try:
        tasks = await client.browse_tasks(
            status="published",
            category="knowledge_access",
            limit=50,
        )
    except Exception as e:
        logger.error(f"Browse failed: {e}")
        return []

    applied_ids = set()
    if state:
        applied_ids = set(state.get("applied", {}).keys())

    matches = []
    for task in tasks:
        task_id = task.get("id", "")
        title = task.get("title", "")

        # Skip own tasks (EM API uses agent_id or agent_wallet for poster identity)
        if exclude_wallet:
            task_wallet = (
                task.get("agent_wallet", "")
                or task.get("agent_id", "")
                or ""
            )
            if task_wallet.lower() == exclude_wallet.lower():
                continue

        # Skip already applied
        if task_id in applied_ids:
            continue

        # Keyword match (case-insensitive)
        title_lower = title.lower()
        if any(kw.lower() in title_lower for kw in keywords):
            matches.append(task)

    # Sort by bounty ascending (cheapest first)
    matches.sort(key=lambda t: t.get("bounty_usd", t.get("bounty_usdc", 0)))

    logger.info(f"Found {len(matches)} matching bounties (keywords: {keywords})")
    return matches


async def apply_to_bounty(
    client: EMClient,
    task: dict,
    state: dict,
    message: str = "",
    dry_run: bool = False,
) -> bool:
    """Apply to fulfill a bounty task.

    Returns True if application succeeded.
    """
    task_id = task.get("id", "")
    title = task.get("title", "?")

    if not client.agent.executor_id:
        logger.error("Cannot apply: no executor_id")
        return False

    if dry_run:
        logger.info(f"[DRY RUN] Would apply to: {title}")
        return False

    try:
        await client.apply_to_task(
            task_id=task_id,
            executor_id=client.agent.executor_id,
            message=message or f"KK agent {client.agent.name} — ready to deliver",
        )

        state.setdefault("applied", {})[task_id] = {
            "title": title,
            "status": "applied",
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Applied to bounty: {title}")
        return True
    except Exception as e:
        err_str = str(e)
        if "409" in err_str:
            logger.info(f"Already applied to: {title}")
            # Track it anyway so we don't retry
            state.setdefault("applied", {})[task_id] = {
                "title": title,
                "status": "applied",
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
            return False
        if "403" in err_str:
            logger.info(f"Cannot apply to own task: {title}")
            # Track to avoid retrying
            state.setdefault("applied", {})[task_id] = {
                "title": title,
                "status": "forbidden",
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
            return False
        logger.error(f"Apply failed: {e}")
        return False


async def fulfill_assigned(
    client: EMClient,
    state: dict,
    evidence: dict[str, Any] | None = None,
    evidence_fn: Callable[[str, dict], dict] | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Check applied tasks — if assigned, submit evidence.

    Args:
        evidence: Static evidence dict to submit for all tasks.
        evidence_fn: Callable(task_id, task_info) -> evidence_dict.
                     Takes precedence over static evidence.
        dry_run: Preview mode.

    Returns {submitted, completed, errors} counts.
    """
    stats = {"submitted": 0, "completed": 0, "errors": 0}
    applied = state.get("applied", {})

    for task_id, info in list(applied.items()):
        status = info.get("status", "")

        # Check completed tasks
        if status in ("submitted", "completed"):
            try:
                task_data = await client.get_task(task_id)
                em_status = task_data.get("status", "")
                if em_status == "completed":
                    info["status"] = "completed"
                    stats["completed"] += 1
            except Exception:
                pass
            continue

        if status != "applied":
            continue

        # Check if assigned
        try:
            task_data = await client.get_task(task_id)
        except Exception as e:
            logger.debug(f"Check task failed: {e}")
            continue

        em_status = task_data.get("status", "")

        if em_status in ("cancelled", "expired"):
            info["status"] = em_status
            continue

        if em_status in ("accepted", "in_progress"):
            # We're assigned! Submit evidence
            if not client.agent.executor_id:
                continue

            ev = {"type": "json_response", "notes": f"Delivered by {client.agent.name}"}
            if evidence_fn:
                try:
                    ev = evidence_fn(task_id, info)
                except Exception as e:
                    logger.error(f"Evidence generation failed: {e}")
                    continue
            elif evidence:
                ev = evidence

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would submit evidence for: {info.get('title', '?')}"
                )
                stats["submitted"] += 1
                continue

            try:
                await client.submit_evidence(
                    task_id=task_id,
                    executor_id=client.agent.executor_id,
                    evidence=ev,
                )
                info["status"] = "submitted"
                stats["submitted"] += 1
                logger.info(f"Submitted evidence for: {info.get('title', '?')}")
            except Exception as e:
                logger.error(f"Submit evidence failed: {e}")
                stats["errors"] += 1

        await asyncio.sleep(0.5)

    return stats
