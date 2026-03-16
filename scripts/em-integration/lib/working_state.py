"""
Karma Kadabra V2 — Phase 7: WORKING.md State Manager

Parse and write WORKING.md — the mutable state file each agent reads on wake
and writes before sleeping. This is the crash recovery checkpoint.

Format:
    # Current State

    ## Active Task
    - Task ID: <uuid>
    - Title: <string>
    - Status: <idle|browsing|applied|working|submitting|reviewing>
    - Started: <ISO timestamp>
    - Next step: <description>

    ## Pending
    - <action item 1>
    - <action item 2>

    ## Budget
    - Daily spent: $X.XX / $Y.YY
    - Active escrows: N ($Z.ZZ)

    ## Last Heartbeat
    - Time: <ISO timestamp>
    - Action: <what happened>
    - Result: <outcome>
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ActiveTask:
    """Currently active task being worked on."""

    task_id: str = ""
    title: str = ""
    status: str = "idle"
    started: str = ""
    next_step: str = ""


@dataclass
class WorkingState:
    """Parsed WORKING.md state for one agent."""

    active_task: ActiveTask = field(default_factory=ActiveTask)
    pending: list[str] = field(default_factory=list)
    daily_spent: float = 0.0
    daily_budget: float = 2.0
    active_escrows: int = 0
    escrow_total: float = 0.0
    last_heartbeat_time: str = ""
    last_heartbeat_action: str = ""
    last_heartbeat_result: str = ""

    @property
    def has_active_task(self) -> bool:
        return bool(self.active_task.task_id) and self.active_task.status not in (
            "idle",
            "",
        )

    @property
    def can_spend(self) -> float:
        return self.daily_budget - self.daily_spent


def parse_working_md(path: Path) -> WorkingState:
    """Parse WORKING.md into a WorkingState object."""
    state = WorkingState()

    if not path.exists():
        return state

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    section = ""
    for line in lines:
        stripped = line.strip()

        # Detect section headers
        if stripped.startswith("## "):
            section = stripped.lstrip("# ").lower()
            continue

        if not stripped.startswith("- "):
            continue

        content = stripped[2:].strip()

        if section == "active task":
            if content.startswith("Task ID:"):
                state.active_task.task_id = content.split(":", 1)[1].strip()
            elif content.startswith("Title:"):
                state.active_task.title = content.split(":", 1)[1].strip()
            elif content.startswith("Status:"):
                state.active_task.status = content.split(":", 1)[1].strip()
            elif content.startswith("Started:"):
                state.active_task.started = content.split(":", 1)[1].strip()
            elif content.startswith("Next step:"):
                state.active_task.next_step = content.split(":", 1)[1].strip()

        elif section == "pending":
            if content:
                state.pending.append(content)

        elif section == "budget":
            if content.startswith("Daily spent:"):
                match = re.search(r"\$(\d+\.?\d*)\s*/\s*\$(\d+\.?\d*)", content)
                if match:
                    state.daily_spent = float(match.group(1))
                    state.daily_budget = float(match.group(2))
            elif content.startswith("Active escrows:"):
                match = re.search(r"(\d+)\s*\(\$(\d+\.?\d*)\)", content)
                if match:
                    state.active_escrows = int(match.group(1))
                    state.escrow_total = float(match.group(2))

        elif section == "last heartbeat":
            if content.startswith("Time:"):
                state.last_heartbeat_time = content.split(":", 1)[1].strip()
            elif content.startswith("Action:"):
                state.last_heartbeat_action = content.split(":", 1)[1].strip()
            elif content.startswith("Result:"):
                state.last_heartbeat_result = content.split(":", 1)[1].strip()

    return state


def write_working_md(path: Path, state: WorkingState) -> None:
    """Write WorkingState to WORKING.md."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    lines = [
        "# Current State",
        "",
        "## Active Task",
    ]

    if state.has_active_task:
        t = state.active_task
        lines.extend(
            [
                f"- Task ID: {t.task_id}",
                f"- Title: {t.title}",
                f"- Status: {t.status}",
                f"- Started: {t.started}",
                f"- Next step: {t.next_step}",
            ]
        )
    else:
        lines.append("- Status: idle")

    lines.extend(
        [
            "",
            "## Pending",
        ]
    )
    if state.pending:
        for item in state.pending:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")

    lines.extend(
        [
            "",
            "## Budget",
            f"- Daily spent: ${state.daily_spent:.2f} / ${state.daily_budget:.2f}",
            f"- Active escrows: {state.active_escrows} (${state.escrow_total:.2f})",
            "",
            "## Last Heartbeat",
            f"- Time: {state.last_heartbeat_time or now}",
            f"- Action: {state.last_heartbeat_action or 'initialized'}",
            f"- Result: {state.last_heartbeat_result or 'ok'}",
            "",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def update_heartbeat(
    state: WorkingState,
    action: str,
    result: str,
) -> None:
    """Update the last heartbeat fields in state."""
    state.last_heartbeat_time = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    state.last_heartbeat_action = action
    state.last_heartbeat_result = result


def set_active_task(
    state: WorkingState,
    task_id: str,
    title: str,
    status: str = "applied",
    next_step: str = "",
) -> None:
    """Set the active task in state."""
    state.active_task = ActiveTask(
        task_id=task_id,
        title=title,
        status=status,
        started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        next_step=next_step,
    )


def clear_active_task(state: WorkingState) -> None:
    """Clear the active task (task completed or cancelled)."""
    state.active_task = ActiveTask()


WORKING_MD_TEMPLATE = """\
# Current State

## Active Task
- Status: idle

## Pending
- (none)

## Budget
- Daily spent: $0.00 / $2.00
- Active escrows: 0 ($0.00)

## Last Heartbeat
- Time: {now}
- Action: workspace initialized
- Result: ok
"""


def create_initial_working_md(path: Path, daily_budget: float = 2.0) -> None:
    """Create a fresh WORKING.md template."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    content = WORKING_MD_TEMPLATE.format(now=now).replace("$2.00", f"${daily_budget:.2f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
