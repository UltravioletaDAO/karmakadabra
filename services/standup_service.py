"""
Karma Kadabra V2 — Phase 11: Daily Standup Report Generator

Generates a daily standup report by aggregating data from:
  1. kk_swarm_state (Supabase) — agent heartbeats, status, spend
  2. Workspace daily notes (memory/notes/{date}.md)
  3. WORKING.md state per agent

Output formats:
  - stdout: pretty-printed terminal report
  - file: full markdown report saved to disk
  - irc: shortened version for IRC messages (~400 chars)

Usage:
  python standup_service.py                            # Today, stdout
  python standup_service.py --date 2026-02-19          # Specific date
  python standup_service.py --output file              # Save markdown
  python standup_service.py --output irc               # IRC format
  python standup_service.py --dry-run                  # Preview without Supabase
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.memory import get_daily_summary
from lib.swarm_state import get_agent_states, get_stale_agents, get_swarm_summary
from lib.working_state import WorkingState, parse_working_md

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.standup")

EM_API_URL = "https://api.execution.market/api/v1"
DAILY_SWARM_BUDGET = 78.0  # USD


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


def read_workspace_notes(
    workspaces_dir: Path, date_str: str
) -> dict[str, list[str]]:
    """Read daily notes from all workspace memory directories.

    Returns:
        Dict mapping agent_name -> list of note entries for the date.
    """
    notes_by_agent: dict[str, list[str]] = {}

    if not workspaces_dir.exists():
        return notes_by_agent

    for ws in sorted(workspaces_dir.iterdir()):
        if not ws.is_dir() or ws.name.startswith("_"):
            continue

        notes_file = ws / "memory" / "notes" / f"{date_str}.md"
        if not notes_file.exists():
            continue

        entries = []
        try:
            text = notes_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("- `"):
                    entries.append(line[2:])  # Remove "- "
        except Exception:
            pass

        if entries:
            notes_by_agent[ws.name] = entries

    return notes_by_agent


def read_workspace_states(workspaces_dir: Path) -> dict[str, WorkingState]:
    """Read WORKING.md from all workspaces.

    Returns:
        Dict mapping agent_name -> WorkingState.
    """
    states: dict[str, WorkingState] = {}

    if not workspaces_dir.exists():
        return states

    for ws in sorted(workspaces_dir.iterdir()):
        if not ws.is_dir() or ws.name.startswith("_"):
            continue

        working_path = ws / "memory" / "WORKING.md"
        if working_path.exists():
            states[ws.name] = parse_working_md(working_path)

    return states


def categorize_agents(
    swarm_agents: list[dict[str, Any]],
    workspace_notes: dict[str, list[str]],
    workspace_states: dict[str, WorkingState],
    stale_agents: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Categorize agents into completed, in_progress, blocked, idle, offline.

    Returns dict with keys: completed, in_progress, blocked, idle, offline.
    """
    stale_names = {a["agent_name"] for a in stale_agents}

    categories: dict[str, list[dict[str, Any]]] = {
        "completed": [],
        "in_progress": [],
        "blocked": [],
        "idle": [],
        "offline": [],
    }

    seen_agents: set[str] = set()

    for agent in swarm_agents:
        name = agent.get("agent_name", "")
        seen_agents.add(name)
        status = agent.get("status", "idle")
        notes_text = agent.get("notes", "")
        task_id = agent.get("task_id", "")

        entry = {
            "name": name,
            "status": status,
            "task_id": task_id,
            "notes": notes_text,
            "daily_spent": float(agent.get("daily_spent_usd", 0)),
        }

        if name in stale_names:
            categories["offline"].append(entry)
        elif "blocked" in notes_text.lower() or "waiting" in notes_text.lower():
            categories["blocked"].append(entry)
        elif status == "busy":
            ws_state = workspace_states.get(name)
            if ws_state and ws_state.has_active_task:
                if ws_state.active_task.status in ("submitted", "completed"):
                    categories["completed"].append(entry)
                else:
                    categories["in_progress"].append(entry)
            else:
                categories["in_progress"].append(entry)
        elif status == "idle":
            categories["idle"].append(entry)
        else:
            categories["idle"].append(entry)

    # Count completed tasks from daily notes
    completed_count = 0
    for agent_name, entries in workspace_notes.items():
        for entry in entries:
            if "completed" in entry.lower() or "approved" in entry.lower():
                completed_count += 1

    return categories


def compute_budget_summary(
    swarm_agents: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute budget summary from swarm state."""
    total_spent = sum(
        float(a.get("daily_spent_usd", 0)) for a in swarm_agents
    )
    return {
        "total_spent": round(total_spent, 2),
        "daily_budget": DAILY_SWARM_BUDGET,
        "remaining": round(DAILY_SWARM_BUDGET - total_spent, 2),
    }


async def check_em_health() -> str:
    """Quick EM API health check."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{EM_API_URL}/health")
            if resp.status_code == 200:
                return "OK"
            return f"HTTP {resp.status_code}"
    except Exception as e:
        return f"FAIL ({e})"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


async def generate_standup(
    workspaces_dir: Path,
    date_str: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate a full standup report.

    Returns:
        Dict with all report sections.
    """
    # Collect data
    if dry_run:
        swarm_agents: list[dict[str, Any]] = []
        stale: list[dict[str, Any]] = []
        summary: dict[str, Any] = {
            "total_agents": 0,
            "by_status": {},
            "stale_agents": 0,
            "active_claims": 0,
            "total_daily_spent_usd": 0.0,
        }
    else:
        swarm_agents = await get_agent_states()
        stale = await get_stale_agents()
        summary = await get_swarm_summary()

    workspace_notes = read_workspace_notes(workspaces_dir, date_str)
    workspace_states = read_workspace_states(workspaces_dir)

    categories = categorize_agents(
        swarm_agents, workspace_notes, workspace_states, stale
    )
    budget = compute_budget_summary(swarm_agents)
    em_health = await check_em_health()

    total_agents = summary.get("total_agents", 0)
    active_count = total_agents - len(categories["offline"])

    return {
        "date": date_str,
        "categories": categories,
        "budget": budget,
        "health": {
            "total_agents": total_agents,
            "active_agents": active_count,
            "offline_agents": [a["name"] for a in categories["offline"]],
            "em_api": em_health,
        },
        "swarm_summary": summary,
        "workspace_notes": workspace_notes,
    }


def format_stdout(report: dict[str, Any]) -> str:
    """Format report for terminal output."""
    lines = []
    date = report["date"]
    cats = report["categories"]
    budget = report["budget"]
    health = report["health"]

    lines.append(f"\nDAILY STANDUP -- {date}")
    lines.append("=" * 50)

    # Completed
    completed = cats.get("completed", [])
    completed_notes = []
    for agent_name, entries in report.get("workspace_notes", {}).items():
        for e in entries:
            if "completed" in e.lower() or "approved" in e.lower():
                completed_notes.append(f"  - {agent_name}: {e}")
    total_completed = len(completed) + len(completed_notes)
    lines.append(f"\nCOMPLETED TODAY ({total_completed} tasks)")
    for a in completed:
        lines.append(f"  - {a['name']}: task {a['task_id'][:8]}...")
    for note in completed_notes[:10]:
        lines.append(note)
    if not completed and not completed_notes:
        lines.append("  (none)")

    # In progress
    in_progress = cats.get("in_progress", [])
    lines.append(f"\nIN PROGRESS ({len(in_progress)} tasks)")
    for a in in_progress:
        lines.append(f"  - {a['name']}: {a['notes'] or a['status']}")
    if not in_progress:
        lines.append("  (none)")

    # Blocked
    blocked = cats.get("blocked", [])
    lines.append(f"\nBLOCKED ({len(blocked)} tasks)")
    for a in blocked:
        lines.append(f"  - {a['name']}: {a['notes']}")
    if not blocked:
        lines.append("  (none)")

    # Budget
    lines.append(f"\nBUDGET SUMMARY")
    lines.append(f"  - Total spent: ${budget['total_spent']:.2f} / ${budget['daily_budget']:.2f} daily swarm budget")
    lines.append(f"  - Remaining: ${budget['remaining']:.2f}")

    # Health
    lines.append(f"\nHEALTH")
    total = health["total_agents"]
    active = health["active_agents"]
    offline = health["offline_agents"]
    lines.append(f"  - {active}/{total} agents active", )
    if offline:
        lines.append(f"  - Offline: {', '.join(offline[:5])}")
    lines.append(f"  - EM API: {health['em_api']}")

    lines.append("")
    return "\n".join(lines)


def format_markdown(report: dict[str, Any]) -> str:
    """Format report as a full markdown document."""
    lines = []
    date = report["date"]
    cats = report["categories"]
    budget = report["budget"]
    health = report["health"]

    lines.append(f"# Daily Standup -- {date}")
    lines.append("")

    # Completed
    completed = cats.get("completed", [])
    lines.append(f"## Completed Today ({len(completed)} tasks)")
    for a in completed:
        lines.append(f"- **{a['name']}**: task `{a['task_id'][:8]}...`")
    # Add completed from workspace notes
    for agent_name, entries in report.get("workspace_notes", {}).items():
        for e in entries:
            if "completed" in e.lower() or "approved" in e.lower():
                lines.append(f"- **{agent_name}**: {e}")
    if not completed:
        lines.append("- (none)")
    lines.append("")

    # In progress
    in_progress = cats.get("in_progress", [])
    lines.append(f"## In Progress ({len(in_progress)} tasks)")
    for a in in_progress:
        lines.append(f"- **{a['name']}**: {a['notes'] or a['status']}")
    if not in_progress:
        lines.append("- (none)")
    lines.append("")

    # Blocked
    blocked = cats.get("blocked", [])
    lines.append(f"## Blocked ({len(blocked)} tasks)")
    for a in blocked:
        lines.append(f"- **{a['name']}**: {a['notes']}")
    if not blocked:
        lines.append("- (none)")
    lines.append("")

    # Budget
    lines.append("## Budget Summary")
    lines.append(f"- Total spent: ${budget['total_spent']:.2f} / ${budget['daily_budget']:.2f} daily swarm budget")
    lines.append(f"- Remaining: ${budget['remaining']:.2f}")
    lines.append("")

    # Health
    total = health["total_agents"]
    active = health["active_agents"]
    offline = health["offline_agents"]
    lines.append("## Health")
    lines.append(f"- {active}/{total} agents active")
    if offline:
        lines.append(f"- Offline: {', '.join(offline)}")
    lines.append(f"- EM API: {health['em_api']}")
    lines.append("")

    return "\n".join(lines)


def format_irc(report: dict[str, Any]) -> str:
    """Format report as a short IRC message (under 500 chars)."""
    date = report["date"]
    cats = report["categories"]
    budget = report["budget"]
    health = report["health"]

    completed_count = len(cats.get("completed", []))
    in_progress_count = len(cats.get("in_progress", []))
    blocked_count = len(cats.get("blocked", []))
    active = health["active_agents"]
    total = health["total_agents"]

    msg = (
        f"[KK STANDUP {date}] "
        f"Done: {completed_count} | WIP: {in_progress_count} | "
        f"Blocked: {blocked_count} | "
        f"Spent: ${budget['total_spent']:.2f}/${budget['daily_budget']:.0f} | "
        f"Agents: {active}/{total} online | "
        f"API: {health['em_api']}"
    )

    # Truncate to 500 chars if needed
    if len(msg) > 500:
        msg = msg[:497] + "..."

    return msg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="KK Daily Standup Report Generator")
    parser.add_argument(
        "--output",
        choices=["stdout", "file", "irc"],
        default="stdout",
        help="Output format (default: stdout)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Report date YYYY-MM-DD (default: today)",
    )
    parser.add_argument("--workspaces-dir", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Skip Supabase calls")
    args = parser.parse_args()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = Path(__file__).parent.parent
    workspaces_dir = (
        Path(args.workspaces_dir) if args.workspaces_dir else base / "data" / "workspaces"
    )

    report = await generate_standup(workspaces_dir, date_str, dry_run=args.dry_run)

    if args.output == "stdout":
        print(format_stdout(report))
    elif args.output == "file":
        output_path = base / "data" / "reports" / f"standup_{date_str}.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(format_markdown(report), encoding="utf-8")
        print(f"Report saved to {output_path}")
    elif args.output == "irc":
        print(format_irc(report))


if __name__ == "__main__":
    asyncio.run(main())
