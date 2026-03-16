"""
Karma Kadabra V2 — Phase 11: Agent-to-Agent Relationship Tracker

Tracks interaction quality between agents by analyzing daily notes
across all workspaces. Computes trust scores per agent pair based on:
  - Task completions (agent published, another executed)
  - Ratings given and received
  - Payment timeliness (approvals vs. disputes)

Trust score (0-100) is a weighted composite:
  - 40% task completion rate (did the agent finish tasks?)
  - 30% rating quality (average ratings given/received)
  - 20% payment reliability (on-time approvals vs. disputes)
  - 10% interaction frequency (more interactions = more data)

Usage:
  python relationship_tracker.py                            # Dry run
  python relationship_tracker.py --update-memory            # Write to MEMORY.md
  python relationship_tracker.py --workspaces-dir /path/to  # Custom path
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.memory import append_to_memory, read_memory_md

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.relationships")

# Trust score weights
WEIGHT_COMPLETION = 0.40
WEIGHT_RATING = 0.30
WEIGHT_PAYMENT = 0.20
WEIGHT_FREQUENCY = 0.10

# Minimum interactions before we compute trust
MIN_INTERACTIONS = 2
TOP_TRUSTED_COUNT = 5


# ---------------------------------------------------------------------------
# Interaction extraction
# ---------------------------------------------------------------------------


@dataclass
class Interaction:
    """A single interaction between two agents."""

    from_agent: str
    to_agent: str
    interaction_type: str  # completed, rated, paid, disputed
    value: float  # rating score, bounty amount, etc.
    date: str


def extract_interactions_from_notes(
    workspaces_dir: Path,
) -> list[Interaction]:
    """Scan all workspace daily notes for inter-agent interactions.

    Looks for patterns like:
      - `completed task for kk-agent-name`
      - `rated kk-agent-name 85`
      - `approved submission from kk-agent-name`
      - `applied to task by kk-agent-name`
    """
    interactions: list[Interaction] = []

    if not workspaces_dir.exists():
        return interactions

    # Patterns to match in daily notes
    patterns = [
        # Completed task for another agent
        (
            r"completed.*(?:task|for)\s+(kk-[\w-]+)",
            "completed",
        ),
        # Rated another agent
        (
            r"rated\s+(kk-[\w-]+)\s+(\d+)",
            "rated",
        ),
        # Approved submission from another agent
        (
            r"approved.*(?:from|submission)\s+(kk-[\w-]+)",
            "approved",
        ),
        # Applied to task by another agent
        (
            r"applied.*(?:task|by)\s+(kk-[\w-]+)",
            "applied",
        ),
        # Paid by another agent
        (
            r"paid.*(?:by|from)\s+(kk-[\w-]+)",
            "paid",
        ),
    ]

    for ws in sorted(workspaces_dir.iterdir()):
        if not ws.is_dir() or ws.name.startswith("_"):
            continue

        notes_dir = ws / "memory" / "notes"
        if not notes_dir.exists():
            continue

        from_agent = ws.name

        for notes_file in sorted(notes_dir.glob("*.md")):
            date_str = notes_file.stem  # e.g., "2026-02-19"

            try:
                text = notes_file.read_text(encoding="utf-8")
            except Exception:
                continue

            for line in text.splitlines():
                line_lower = line.lower().strip()

                for pattern, itype in patterns:
                    match = re.search(pattern, line_lower)
                    if match:
                        to_agent = match.group(1)
                        value = 0.0

                        if itype == "rated" and match.lastindex and match.lastindex >= 2:
                            try:
                                value = float(match.group(2))
                            except ValueError:
                                value = 0.0

                        if to_agent != from_agent:
                            interactions.append(Interaction(
                                from_agent=from_agent,
                                to_agent=to_agent,
                                interaction_type=itype,
                                value=value,
                                date=date_str,
                            ))
                        break  # Only match first pattern per line

    return interactions


# ---------------------------------------------------------------------------
# Trust score computation
# ---------------------------------------------------------------------------


def compute_trust_scores(
    interactions: list[Interaction],
) -> dict[str, dict[str, float]]:
    """Compute trust scores for each agent pair.

    Returns:
        Dict mapping agent_name -> {peer_name: trust_score}.
    """
    # Group interactions by (from, to) pair
    pair_data: dict[tuple[str, str], list[Interaction]] = defaultdict(list)
    for ix in interactions:
        pair_data[(ix.from_agent, ix.to_agent)].append(ix)

    # Compute trust per pair
    trust_matrix: dict[str, dict[str, float]] = defaultdict(dict)

    # Get all unique agents
    all_agents: set[str] = set()
    for ix in interactions:
        all_agents.add(ix.from_agent)
        all_agents.add(ix.to_agent)

    for agent in all_agents:
        peer_scores: dict[str, float] = {}

        for peer in all_agents:
            if peer == agent:
                continue

            # Collect all interactions in both directions
            outgoing = pair_data.get((agent, peer), [])
            incoming = pair_data.get((peer, agent), [])
            all_ix = outgoing + incoming

            if len(all_ix) < MIN_INTERACTIONS:
                continue

            # Completion rate
            completions = sum(1 for ix in all_ix if ix.interaction_type in ("completed", "approved"))
            total_tasks = sum(1 for ix in all_ix if ix.interaction_type in ("completed", "approved", "applied"))
            completion_score = (completions / max(total_tasks, 1)) * 100

            # Rating quality
            ratings = [ix.value for ix in all_ix if ix.interaction_type == "rated" and ix.value > 0]
            rating_score = sum(ratings) / len(ratings) if ratings else 50.0

            # Payment reliability
            paid = sum(1 for ix in all_ix if ix.interaction_type in ("paid", "approved"))
            disputed = sum(1 for ix in all_ix if ix.interaction_type == "disputed")
            payment_score = (paid / max(paid + disputed, 1)) * 100

            # Frequency bonus (log scale, capped at 100)
            freq_score = min(len(all_ix) * 10, 100)

            # Weighted composite
            trust = (
                WEIGHT_COMPLETION * completion_score
                + WEIGHT_RATING * rating_score
                + WEIGHT_PAYMENT * payment_score
                + WEIGHT_FREQUENCY * freq_score
            )

            peer_scores[peer] = round(min(trust, 100.0), 1)

        if peer_scores:
            trust_matrix[agent] = dict(
                sorted(peer_scores.items(), key=lambda x: x[1], reverse=True)
            )

    return dict(trust_matrix)


# ---------------------------------------------------------------------------
# MEMORY.md update
# ---------------------------------------------------------------------------


def update_agent_memory(
    workspaces_dir: Path,
    trust_matrix: dict[str, dict[str, float]],
) -> int:
    """Update MEMORY.md "Trusted Agents" section for each agent.

    Returns number of agents updated.
    """
    updated = 0

    for agent_name, peers in trust_matrix.items():
        ws_dir = workspaces_dir / agent_name
        memory_path = ws_dir / "memory" / "MEMORY.md"

        if not memory_path.exists():
            continue

        # Read current MEMORY.md
        text = read_memory_md(memory_path)
        lines = text.splitlines()

        # Find and replace "Trusted Agents" section
        section_start = None
        section_end = None
        for i, line in enumerate(lines):
            if line.strip() == "## Trusted Agents":
                section_start = i
            elif section_start is not None and line.strip().startswith("## "):
                section_end = i
                break

        if section_start is None:
            continue

        if section_end is None:
            section_end = len(lines)

        # Build new section
        top_peers = list(peers.items())[:TOP_TRUSTED_COUNT]
        new_section = ["## Trusted Agents"]
        if top_peers:
            for peer_name, score in top_peers:
                new_section.append(f"- {peer_name}: trust={score}")
        else:
            new_section.append("<!-- No trusted agents yet -->")

        # Replace section
        lines[section_start:section_end] = new_section
        memory_path.write_text("\n".join(lines), encoding="utf-8")
        updated += 1
        logger.info(f"  Updated {agent_name}: {len(top_peers)} trusted peers")

    return updated


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_report(trust_matrix: dict[str, dict[str, float]]) -> str:
    """Format trust matrix as a readable report."""
    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append("  Karma Kadabra -- Relationship Tracker")
    lines.append(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"  Agents with data: {len(trust_matrix)}")
    lines.append(f"{'=' * 60}")

    if not trust_matrix:
        lines.append("\n  No interaction data found.")
        lines.append("  Agents need to complete tasks and rate each other first.")
        lines.append("")
        return "\n".join(lines)

    for agent_name, peers in sorted(trust_matrix.items()):
        lines.append(f"\n  {agent_name}:")
        top = list(peers.items())[:TOP_TRUSTED_COUNT]
        for peer, score in top:
            bar = "#" * int(score / 5)
            lines.append(f"    {peer:<25} {score:>5.1f}  {bar}")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="KK Agent Relationship Tracker")
    parser.add_argument("--workspaces-dir", type=str, default=None)
    parser.add_argument(
        "--update-memory",
        action="store_true",
        help="Write trust scores to each agent's MEMORY.md",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show report without writing anything",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspaces_dir = (
        Path(args.workspaces_dir) if args.workspaces_dir else base / "data" / "workspaces"
    )

    # Extract interactions
    interactions = extract_interactions_from_notes(workspaces_dir)
    logger.info(f"Found {len(interactions)} interactions across workspaces")

    # Compute trust
    trust_matrix = compute_trust_scores(interactions)

    if args.json:
        print(json.dumps(trust_matrix, indent=2))
    else:
        print(format_report(trust_matrix))

    # Update MEMORY.md if requested
    if args.update_memory and not args.dry_run:
        updated = update_agent_memory(workspaces_dir, trust_matrix)
        print(f"\n  Updated {updated} agent MEMORY.md files.")
    elif args.update_memory and args.dry_run:
        print(f"\n  [DRY RUN] Would update {len(trust_matrix)} agent MEMORY.md files.")


if __name__ == "__main__":
    asyncio.run(main())
