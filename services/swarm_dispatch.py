"""
Karma Kadabra V2 — Swarm Dispatch Service

The operational bridge between coordinator intelligence and agent execution.
Handles the full lifecycle of task assignment within the swarm:

  1. Discovery: Poll EM for new/unassigned tasks
  2. Matching: Score agents via enhanced 6-factor + AutoJob bridge
  3. Dispatch: Assign tasks and notify agents via IRC + EM API
  4. Tracking: Monitor task progress and detect stalls
  5. Escalation: Reassign stalled tasks, report failures

This service is called by the coordinator on each heartbeat cycle.
It can also run standalone for testing/debugging.

Usage:
  python swarm_dispatch.py                     # Full dispatch cycle
  python swarm_dispatch.py --dry-run           # Preview without executing
  python swarm_dispatch.py --status            # Show dispatch queue status
  python swarm_dispatch.py --reassign          # Force reassign stalled tasks

Architecture:
  Coordinator (brain) -> Dispatch (muscles) -> Agents (workers)
  
  The coordinator decides WHAT to do.
  Dispatch handles HOW to do it:
    - IRC notification to agent
    - EM API task assignment
    - Progress tracking
    - Stall detection & reassignment
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.dispatch")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class DispatchRecord:
    """A record of a task dispatched to an agent."""

    task_id: str
    agent_name: str
    dispatched_at: str  # ISO 8601
    status: str = "dispatched"  # dispatched, acknowledged, in_progress, completed, stalled, failed, reassigned
    bounty_usd: float = 0.0
    title: str = ""
    category: str = ""
    match_score: float = 0.0
    match_mode: str = "enhanced"
    irc_notified: bool = False
    em_assigned: bool = False
    acknowledged_at: Optional[str] = None
    completed_at: Optional[str] = None
    stall_checks: int = 0
    reassigned_to: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DispatchQueue:
    """In-memory dispatch state with persistence."""

    active: list[DispatchRecord] = field(default_factory=list)
    completed: list[DispatchRecord] = field(default_factory=list)
    failed: list[DispatchRecord] = field(default_factory=list)
    total_dispatched: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_reassigned: int = 0
    last_cycle_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "active": [asdict(r) for r in self.active],
            "completed": [asdict(r) for r in self.completed[-50:]],  # Keep last 50
            "failed": [asdict(r) for r in self.failed[-20:]],  # Keep last 20
            "total_dispatched": self.total_dispatched,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_reassigned": self.total_reassigned,
            "last_cycle_at": self.last_cycle_at,
        }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def load_dispatch_queue(path: Path) -> DispatchQueue:
    """Load dispatch queue from JSON file."""
    if not path.exists():
        return DispatchQueue()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        queue = DispatchQueue()
        queue.active = [DispatchRecord(**r) for r in data.get("active", [])]
        queue.completed = [DispatchRecord(**r) for r in data.get("completed", [])]
        queue.failed = [DispatchRecord(**r) for r in data.get("failed", [])]
        queue.total_dispatched = data.get("total_dispatched", 0)
        queue.total_completed = data.get("total_completed", 0)
        queue.total_failed = data.get("total_failed", 0)
        queue.total_reassigned = data.get("total_reassigned", 0)
        queue.last_cycle_at = data.get("last_cycle_at")
        return queue
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to load dispatch queue: {e}")
        return DispatchQueue()


def save_dispatch_queue(queue: DispatchQueue, path: Path) -> None:
    """Save dispatch queue to JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(queue.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as e:
        logger.error(f"Failed to save dispatch queue: {e}")


# ---------------------------------------------------------------------------
# IRC Notification
# ---------------------------------------------------------------------------


def format_irc_assignment(record: DispatchRecord) -> str:
    """Format an IRC notification message for task assignment.
    
    Uses casual Colombian Spanish matching agent personality.
    """
    bounty = f"${record.bounty_usd:.2f}" if record.bounty_usd else "TBD"
    score_pct = f"{record.match_score * 100:.0f}%" if record.match_score else "?"

    # Vary the notification style
    templates = [
        f"Ey {record.agent_name}, te tengo un task: '{record.title}' ({bounty} USDC). Match: {score_pct}. Tomalo en EM.",
        f"Parce {record.agent_name}, hay bounty pa ti: '{record.title}' por {bounty}. Te lo asigné.",
        f"{record.agent_name}: task nuevo → '{record.title}' ({bounty}). Score {score_pct}. Dale.",
    ]

    # Rotate based on total dispatched count
    idx = record.stall_checks % len(templates)
    return templates[idx]


def format_irc_stall_warning(record: DispatchRecord, minutes_stalled: int) -> str:
    """Format a stall warning for IRC."""
    return (
        f"⚠️ {record.agent_name}, tu task '{record.title[:30]}...' lleva {minutes_stalled} min "
        f"sin progreso. ¿Todo bien parce?"
    )


def format_irc_reassignment(old_agent: str, new_agent: str, title: str) -> str:
    """Format a reassignment notice."""
    return (
        f"🔄 Task '{title[:30]}...' reasignado de {old_agent} → {new_agent}. "
        f"Se necesita movimiento."
    )


# ---------------------------------------------------------------------------
# Dispatch Logic
# ---------------------------------------------------------------------------


async def dispatch_task(
    record: DispatchRecord,
    queue: DispatchQueue,
    em_client: Any = None,
    irc_send_fn: Any = None,
    dry_run: bool = False,
) -> DispatchRecord:
    """Dispatch a single task: assign via EM API + notify via IRC.
    
    Args:
        record: The dispatch record to process.
        queue: The dispatch queue (for tracking).
        em_client: EM API client (optional, for API assignment).
        irc_send_fn: Callable to send IRC messages (optional).
        dry_run: If True, log but don't execute.
    
    Returns:
        Updated dispatch record.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    if dry_run:
        logger.info(f"[DRY RUN] Would dispatch '{record.title}' to {record.agent_name}")
        return record

    # Step 1: Assign via EM API (if client available)
    if em_client is not None:
        try:
            # Try to find executor_id for the agent
            # The coordinator maintains a mapping
            await em_client.assign_task(record.task_id, record.agent_name)
            record.em_assigned = True
            logger.info(f"EM assigned: {record.title} → {record.agent_name}")
        except Exception as e:
            err = str(e)
            # 409 = already assigned (not an error)
            if "409" in err or "already" in err.lower():
                record.em_assigned = True
            else:
                logger.warning(f"EM assign failed: {e}")
                record.error = f"EM assign: {e}"

    # Step 2: Notify via IRC
    if irc_send_fn is not None:
        try:
            msg = format_irc_assignment(record)
            await irc_send_fn("#karmakadabra", msg)
            record.irc_notified = True
            logger.info(f"IRC notified: {record.agent_name} about {record.title}")
        except Exception as e:
            logger.warning(f"IRC notify failed: {e}")

    record.status = "dispatched"
    record.dispatched_at = now_iso
    queue.active.append(record)
    queue.total_dispatched += 1

    return record


async def check_stalled_tasks(
    queue: DispatchQueue,
    stall_threshold_minutes: int = 30,
    max_stall_checks: int = 3,
    em_client: Any = None,
    irc_send_fn: Any = None,
) -> list[DispatchRecord]:
    """Check for stalled tasks and send warnings or reassign.
    
    A task is considered stalled if it's been dispatched/in_progress
    for longer than stall_threshold_minutes without completion.
    
    After max_stall_checks warnings, the task is marked as failed
    and can be reassigned.
    
    Returns list of stalled records.
    """
    now = datetime.now(timezone.utc)
    stalled = []
    threshold = timedelta(minutes=stall_threshold_minutes)

    for record in queue.active[:]:  # Copy to allow mutation
        if record.status in ("completed", "failed", "reassigned"):
            continue

        dispatched_at = datetime.fromisoformat(record.dispatched_at)
        elapsed = now - dispatched_at

        if elapsed < threshold:
            continue

        record.stall_checks += 1
        stalled.append(record)
        minutes_stalled = int(elapsed.total_seconds() / 60)

        if record.stall_checks >= max_stall_checks:
            # Mark as failed after too many stall checks
            record.status = "failed"
            record.error = f"Stalled after {minutes_stalled}min, {record.stall_checks} warnings"
            queue.active.remove(record)
            queue.failed.append(record)
            queue.total_failed += 1
            logger.warning(f"Task failed (stalled): {record.title} @ {record.agent_name}")
        else:
            # Send warning via IRC
            if irc_send_fn is not None:
                try:
                    msg = format_irc_stall_warning(record, minutes_stalled)
                    await irc_send_fn("#karmakadabra", msg)
                except Exception:
                    pass
            logger.info(
                f"Stall warning #{record.stall_checks}: {record.title} "
                f"@ {record.agent_name} ({minutes_stalled}min)"
            )

    return stalled


async def reassign_failed_task(
    record: DispatchRecord,
    new_agent: str,
    new_score: float,
    queue: DispatchQueue,
    em_client: Any = None,
    irc_send_fn: Any = None,
) -> DispatchRecord:
    """Reassign a failed/stalled task to a new agent.
    
    Creates a new dispatch record and updates the old one.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # Update old record
    record.status = "reassigned"
    record.reassigned_to = new_agent

    # Create new dispatch record
    new_record = DispatchRecord(
        task_id=record.task_id,
        agent_name=new_agent,
        dispatched_at=now_iso,
        bounty_usd=record.bounty_usd,
        title=record.title,
        category=record.category,
        match_score=new_score,
        match_mode=record.match_mode,
    )

    # Dispatch the new assignment
    result = await dispatch_task(
        new_record, queue, em_client=em_client, irc_send_fn=irc_send_fn
    )

    queue.total_reassigned += 1

    # Notify via IRC
    if irc_send_fn is not None:
        try:
            msg = format_irc_reassignment(record.agent_name, new_agent, record.title)
            await irc_send_fn("#karmakadabra", msg)
        except Exception:
            pass

    logger.info(f"Reassigned: {record.title} from {record.agent_name} → {new_agent}")
    return result


def mark_completed(
    queue: DispatchQueue,
    task_id: str,
    agent_name: str,
) -> Optional[DispatchRecord]:
    """Mark a dispatched task as completed.
    
    Called when the coordinator detects a task completion
    (via EM API polling or IRC notification).
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    for record in queue.active[:]:
        if record.task_id == task_id and record.agent_name == agent_name:
            record.status = "completed"
            record.completed_at = now_iso
            queue.active.remove(record)
            queue.completed.append(record)
            queue.total_completed += 1
            logger.info(f"Completed: {record.title} by {record.agent_name}")
            return record

    return None


def mark_acknowledged(
    queue: DispatchQueue,
    task_id: str,
    agent_name: str,
) -> Optional[DispatchRecord]:
    """Mark a dispatched task as acknowledged by the agent.
    
    Called when the agent confirms receipt (via IRC or heartbeat state).
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    for record in queue.active:
        if record.task_id == task_id and record.agent_name == agent_name:
            record.status = "acknowledged"
            record.acknowledged_at = now_iso
            return record

    return None


# ---------------------------------------------------------------------------
# Dispatch Cycle (full coordination)
# ---------------------------------------------------------------------------


async def dispatch_cycle(
    queue: DispatchQueue,
    available_tasks: list[dict],
    agent_rankings: dict[str, list[tuple[str, float]]],
    assigned_set: set[str],
    em_client: Any = None,
    irc_send_fn: Any = None,
    dry_run: bool = False,
    max_assignments_per_cycle: int = 5,
) -> dict:
    """Execute a full dispatch cycle.
    
    Args:
        queue: Current dispatch queue state.
        available_tasks: Tasks from EM API (status=published).
        agent_rankings: Dict of task_id -> [(agent_name, score), ...] from coordinator.
        assigned_set: Set of agent names already assigned this cycle.
        em_client: EM API client.
        irc_send_fn: IRC send function.
        dry_run: Preview mode.
        max_assignments_per_cycle: Limit assignments per cycle.
    
    Returns:
        Dict with cycle results.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    queue.last_cycle_at = now_iso

    results = {
        "dispatched": 0,
        "stalled": 0,
        "reassigned": 0,
        "completed_detected": 0,
        "errors": [],
    }

    # Skip already-active tasks
    active_task_ids = {r.task_id for r in queue.active}

    # Phase 1: Check for stalled tasks
    stalled = await check_stalled_tasks(
        queue, em_client=em_client, irc_send_fn=irc_send_fn
    )
    results["stalled"] = len(stalled)

    # Phase 2: Dispatch new tasks
    dispatched = 0
    for task in available_tasks:
        if dispatched >= max_assignments_per_cycle:
            break

        task_id = task.get("id", "")
        if task_id in active_task_ids:
            continue

        rankings = agent_rankings.get(task_id, [])
        if not rankings:
            continue

        # Find first available agent
        for agent_name, score in rankings:
            if agent_name in assigned_set:
                continue

            record = DispatchRecord(
                task_id=task_id,
                agent_name=agent_name,
                dispatched_at=now_iso,
                bounty_usd=task.get("bounty_usd", 0),
                title=task.get("title", ""),
                category=task.get("category", ""),
                match_score=score,
            )

            try:
                await dispatch_task(
                    record, queue,
                    em_client=em_client,
                    irc_send_fn=irc_send_fn,
                    dry_run=dry_run,
                )
                assigned_set.add(agent_name)
                dispatched += 1
                results["dispatched"] += 1
            except Exception as e:
                results["errors"].append(f"Dispatch {task_id}: {e}")

            break  # One agent per task

    return results


# ---------------------------------------------------------------------------
# Status Display
# ---------------------------------------------------------------------------


def display_queue_status(queue: DispatchQueue) -> None:
    """Display dispatch queue status."""
    print(f"\n{'=' * 60}")
    print(f"  🚀 KK Dispatch Queue Status")
    print(f"  Last cycle: {queue.last_cycle_at or 'never'}")
    print(f"{'=' * 60}")
    print(f"\n  📊 Totals:")
    print(f"    Dispatched: {queue.total_dispatched}")
    print(f"    Completed:  {queue.total_completed}")
    print(f"    Failed:     {queue.total_failed}")
    print(f"    Reassigned: {queue.total_reassigned}")

    if queue.active:
        print(f"\n  🔵 Active ({len(queue.active)}):")
        for r in queue.active:
            elapsed = ""
            try:
                dt = datetime.fromisoformat(r.dispatched_at)
                mins = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
                elapsed = f" ({mins}min ago)"
            except Exception:
                pass
            status_icon = {
                "dispatched": "📤",
                "acknowledged": "✅",
                "in_progress": "🔧",
            }.get(r.status, "❓")
            print(
                f"    {status_icon} {r.agent_name}: {r.title[:35]}... "
                f"(${r.bounty_usd:.2f}, score={r.match_score:.2f}){elapsed}"
            )

    if queue.completed:
        print(f"\n  ✅ Recent Completed ({len(queue.completed)}):")
        for r in queue.completed[-5:]:
            print(f"    {r.agent_name}: {r.title[:40]}... (${r.bounty_usd:.2f})")

    if queue.failed:
        print(f"\n  ❌ Recent Failed ({len(queue.failed)}):")
        for r in queue.failed[-5:]:
            print(f"    {r.agent_name}: {r.title[:40]}... — {r.error or 'unknown'}")

    print(f"\n{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="KK V2 Swarm Dispatch Service")
    parser.add_argument("--status", action="store_true", help="Show dispatch queue status")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--reassign", action="store_true", help="Force reassign stalled tasks")
    parser.add_argument("--data-dir", type=str, default=None)
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"
    queue_path = data_dir / "dispatch_queue.json"

    queue = load_dispatch_queue(queue_path)

    if args.status:
        display_queue_status(queue)
        return

    if args.reassign:
        stalled = [r for r in queue.active if r.stall_checks >= 2]
        if not stalled:
            print("No stalled tasks to reassign.")
            return
        print(f"Found {len(stalled)} stalled tasks — reassignment requires coordinator matching.")
        for r in stalled:
            print(f"  {r.agent_name}: {r.title} (stalls: {r.stall_checks})")
        return

    # Standalone mode: show status and run stall check
    print(f"\n  Running dispatch cycle (dry_run={args.dry_run})...")
    stalled = await check_stalled_tasks(queue)
    if stalled:
        print(f"  Found {len(stalled)} stalled tasks")
    else:
        print(f"  No stalled tasks")

    save_dispatch_queue(queue, queue_path)
    display_queue_status(queue)


if __name__ == "__main__":
    asyncio.run(main())
