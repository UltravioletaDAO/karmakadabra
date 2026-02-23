"""
Karma Kadabra V2 — Phase 7: Memory Stack Manager

Manages the 3-level memory system for each agent:
  1. WORKING.md — handled by working_state.py (every heartbeat)
  2. MEMORY.md — long-term mutable preferences (updated periodically)
  3. Daily notes — memory/notes/{date}.md (append per heartbeat)

MEMORY.md stores:
  - Trusted agents (agents that paid on time, good quality)
  - Preferred task categories
  - Pricing history (what bounties are worth taking)
  - Learned patterns (what tasks succeed vs. fail)
  - IRC contacts and relationships

Daily notes store:
  - Timestamped log of every heartbeat action
  - Used by coordinator for standup reports
  - Useful for debugging agent behavior
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# MEMORY.md
# ---------------------------------------------------------------------------

MEMORY_MD_TEMPLATE = """\
# Agent Memory

## Trusted Agents
<!-- Agents that consistently deliver quality work or pay on time -->

## Preferred Categories
<!-- Task categories this agent performs well in -->

## Pricing Notes
<!-- What bounties are worth taking, minimum viable bounty -->
- Minimum bounty: $0.02
- Sweet spot: $0.03-$0.10

## Learned Patterns
<!-- What works and what doesn't -->

## IRC Contacts
<!-- Known agents and their specialties -->

## Updated
- Last updated: {now}
"""


def create_initial_memory_md(path: Path) -> None:
    """Create a fresh MEMORY.md template."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    content = MEMORY_MD_TEMPLATE.format(now=now)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_memory_md(path: Path) -> str:
    """Read MEMORY.md contents."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def append_to_memory(path: Path, section: str, entry: str) -> None:
    """Append an entry to a specific section in MEMORY.md.

    Args:
        path: Path to MEMORY.md.
        section: Section header (e.g., "Trusted Agents").
        entry: Line to append (without leading "- ").
    """
    if not path.exists():
        create_initial_memory_md(path)

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the section and its content range
    section_header = f"## {section}"
    insert_idx = None

    for i, line in enumerate(lines):
        if line.strip() == section_header:
            # Find the next non-comment, non-empty line after the header
            j = i + 1
            while j < len(lines):
                if lines[j].strip().startswith("##"):
                    break
                j += 1
            insert_idx = j
            break

    if insert_idx is not None:
        lines.insert(insert_idx, f"- {entry}")
        # Update timestamp
        for i, line in enumerate(lines):
            if line.startswith("- Last updated:"):
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                lines[i] = f"- Last updated: {now}"
                break
        path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Daily Notes (memory/notes/{date}.md)
# ---------------------------------------------------------------------------


def get_daily_notes_path(memory_dir: Path) -> Path:
    """Get path to today's daily notes file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return memory_dir / "notes" / f"{today}.md"


def append_daily_note(memory_dir: Path, action: str, result: str = "") -> None:
    """Append a timestamped entry to today's daily notes.

    Args:
        memory_dir: Path to agent's memory/ directory.
        action: What the agent did.
        result: Outcome (optional).
    """
    notes_dir = memory_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    notes_path = notes_dir / f"{today}.md"

    now = datetime.now(timezone.utc).strftime("%H:%M:%S")

    if not notes_path.exists():
        header = f"# Daily Activity — {today}\n\n"
        notes_path.write_text(header, encoding="utf-8")

    entry = f"- `{now}` {action}"
    if result:
        entry += f" -> {result}"
    entry += "\n"

    with open(notes_path, "a", encoding="utf-8") as f:
        f.write(entry)


def get_daily_summary(memory_dir: Path) -> dict:
    """Read today's daily notes and produce a summary dict.

    Returns:
        Dict with: date, total_entries, entries list.
    """
    notes_path = get_daily_notes_path(memory_dir)

    if not notes_path.exists():
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {"date": today, "total_entries": 0, "entries": []}

    text = notes_path.read_text(encoding="utf-8")
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- `"):
            # Parse: - `HH:MM:SS` action -> result
            entries.append(line[2:])  # Remove "- "

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "date": today,
        "total_entries": len(entries),
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Memory directory initialization
# ---------------------------------------------------------------------------


def init_memory_stack(workspace_dir: Path, daily_budget: float = 2.0) -> None:
    """Initialize the full memory stack for an agent workspace.

    Creates:
        workspace_dir/memory/WORKING.md
        workspace_dir/memory/MEMORY.md
        workspace_dir/memory/notes/     (empty dir)
    """
    from .working_state import create_initial_working_md

    memory_dir = workspace_dir / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "notes").mkdir(exist_ok=True)

    working_path = memory_dir / "WORKING.md"
    if not working_path.exists():
        create_initial_working_md(working_path, daily_budget)

    memory_path = memory_dir / "MEMORY.md"
    if not memory_path.exists():
        create_initial_memory_md(memory_path)
