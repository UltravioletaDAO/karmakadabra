"""
Karma Kadabra V2 — Memory Bridge

Unified memory abstraction for KK agents. Works local-first with files,
designed to seamlessly bridge to Acontext when available.

The memory bridge provides:
  1. Unified read/write for agent state (WORKING.md, MEMORY.md, daily notes)
  2. Cross-agent memory queries (coordinator can read any agent's state)
  3. Context compression (summarize old entries, manage token budgets)
  4. Event logging with structured tags (feeds into observability)
  5. Acontext session mapping (local operations → Acontext API when available)

Architecture:
  - LocalBackend: File-based (default, always available)
  - AcontextBackend: API-based (available when Docker + Acontext server running)
  - MemoryBridge: Routes to appropriate backend, handles fallbacks

Design principles:
  - Local-first: Always works without external services
  - Transparent fallback: If Acontext is down, silently falls back to local
  - Event-sourced: All state changes logged as events
  - Token-aware: Context compression for LLM context windows
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.memory_bridge")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class MemoryEntry:
    """A single memory entry (usable for MEMORY.md sections, daily notes, events)."""
    timestamp: str = ""
    agent_name: str = ""
    category: str = ""       # e.g., "trusted_agents", "pricing", "learned_patterns"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "local"    # "local" or "acontext"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "agent_name": self.agent_name,
            "category": self.category,
            "content": self.content,
            "metadata": self.metadata,
            "source": self.source,
        }


@dataclass
class AgentContext:
    """Assembled context for an agent, ready to inject into LLM prompts."""
    agent_name: str
    working_state: str = ""      # Current WORKING.md contents
    memory: str = ""             # Relevant MEMORY.md sections
    recent_notes: list[str] = field(default_factory=list)  # Last N daily note entries
    events: list[dict[str, Any]] = field(default_factory=list)  # Recent events
    token_estimate: int = 0      # Estimated token count

    def to_prompt(self, max_tokens: int = 4000) -> str:
        """Assemble into a prompt-ready string, respecting token budget."""
        sections: list[str] = []

        # Working state is always included (highest priority)
        if self.working_state:
            sections.append(f"## Current State\n{self.working_state}")

        # Memory (second priority)
        if self.memory:
            sections.append(f"## Agent Memory\n{self.memory}")

        # Recent notes (third priority, trimmed to fit)
        if self.recent_notes:
            notes = "\n".join(f"- {n}" for n in self.recent_notes[-10:])
            sections.append(f"## Recent Activity\n{notes}")

        result = "\n\n".join(sections)

        # Rough token estimate (4 chars ≈ 1 token)
        self.token_estimate = len(result) // 4

        # Trim if over budget
        if self.token_estimate > max_tokens:
            # Drop notes first, then memory
            result = sections[0] if sections else ""
            if len(sections) > 1:
                remaining = max_tokens * 4 - len(result)
                if remaining > 100:
                    result += "\n\n" + sections[1][:remaining]
            self.token_estimate = len(result) // 4

        return result


# ---------------------------------------------------------------------------
# Backend Interface
# ---------------------------------------------------------------------------


class MemoryBackend(ABC):
    """Abstract backend for memory operations."""

    @abstractmethod
    def read_working_state(self, agent_name: str) -> str:
        """Read the current WORKING.md for an agent."""

    @abstractmethod
    def write_working_state(self, agent_name: str, content: str) -> bool:
        """Write WORKING.md for an agent. Returns success."""

    @abstractmethod
    def read_memory(self, agent_name: str) -> str:
        """Read MEMORY.md for an agent."""

    @abstractmethod
    def append_memory(self, agent_name: str, section: str, entry: str) -> bool:
        """Append to a MEMORY.md section. Returns success."""

    @abstractmethod
    def append_note(self, agent_name: str, action: str, result: str = "") -> bool:
        """Append to daily notes. Returns success."""

    @abstractmethod
    def get_recent_notes(self, agent_name: str, limit: int = 20) -> list[str]:
        """Get recent daily note entries."""

    @abstractmethod
    def log_event(self, agent_name: str, event_type: str, details: dict[str, Any] | None = None) -> bool:
        """Log a structured event. Returns success."""

    @abstractmethod
    def query_events(self, agent_name: str | None = None, event_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Query logged events, optionally filtered."""

    @abstractmethod
    def get_all_agent_names(self) -> list[str]:
        """List all known agent names."""


# ---------------------------------------------------------------------------
# Local File Backend
# ---------------------------------------------------------------------------


class LocalBackend(MemoryBackend):
    """File-based memory backend using agent workspace directories."""

    def __init__(self, workspaces_dir: Path):
        self.workspaces_dir = workspaces_dir
        self._events_dir = workspaces_dir / "_events"

    def _agent_dir(self, agent_name: str) -> Path:
        return self.workspaces_dir / agent_name

    def _memory_dir(self, agent_name: str) -> Path:
        return self._agent_dir(agent_name) / "memory"

    def read_working_state(self, agent_name: str) -> str:
        path = self._memory_dir(agent_name) / "WORKING.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_working_state(self, agent_name: str, content: str) -> bool:
        path = self._memory_dir(agent_name) / "WORKING.md"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.warning(f"Failed to write WORKING.md for {agent_name}: {e}")
            return False

    def read_memory(self, agent_name: str) -> str:
        path = self._memory_dir(agent_name) / "MEMORY.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def append_memory(self, agent_name: str, section: str, entry: str) -> bool:
        path = self._memory_dir(agent_name) / "MEMORY.md"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            if not path.exists():
                # Create with minimal template
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                path.write_text(
                    f"# Agent Memory\n\n## {section}\n- {entry}\n\n## Updated\n- Last updated: {now}\n",
                    encoding="utf-8",
                )
                return True

            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()

            section_header = f"## {section}"
            insert_idx = None

            for i, line in enumerate(lines):
                if line.strip() == section_header:
                    j = i + 1
                    while j < len(lines):
                        if lines[j].strip().startswith("##"):
                            break
                        j += 1
                    insert_idx = j
                    break

            if insert_idx is not None:
                lines.insert(insert_idx, f"- {entry}")
            else:
                # Section doesn't exist — append it
                lines.append(f"\n## {section}")
                lines.append(f"- {entry}")

            # Update timestamp
            for i, line in enumerate(lines):
                if line.startswith("- Last updated:"):
                    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    lines[i] = f"- Last updated: {now}"
                    break

            path.write_text("\n".join(lines), encoding="utf-8")
            return True
        except Exception as e:
            logger.warning(f"Failed to append memory for {agent_name}: {e}")
            return False

    def append_note(self, agent_name: str, action: str, result: str = "") -> bool:
        notes_dir = self._memory_dir(agent_name) / "notes"
        try:
            notes_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            notes_path = notes_dir / f"{today}.md"
            now_time = datetime.now(timezone.utc).strftime("%H:%M:%S")

            if not notes_path.exists():
                notes_path.write_text(f"# Daily Activity — {today}\n\n", encoding="utf-8")

            entry = f"- `{now_time}` {action}"
            if result:
                entry += f" -> {result}"
            entry += "\n"

            with open(notes_path, "a", encoding="utf-8") as f:
                f.write(entry)
            return True
        except Exception as e:
            logger.warning(f"Failed to append note for {agent_name}: {e}")
            return False

    def get_recent_notes(self, agent_name: str, limit: int = 20) -> list[str]:
        notes_dir = self._memory_dir(agent_name) / "notes"
        if not notes_dir.exists():
            return []

        # Get most recent notes file
        files = sorted(notes_dir.glob("*.md"), reverse=True)
        entries: list[str] = []

        for f in files[:3]:  # Check last 3 days
            try:
                text = f.read_text(encoding="utf-8")
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith("- `"):
                        entries.append(line[2:])  # Remove "- "
                    if len(entries) >= limit:
                        break
            except Exception:
                continue
            if len(entries) >= limit:
                break

        return entries[:limit]

    def log_event(self, agent_name: str, event_type: str, details: dict[str, Any] | None = None) -> bool:
        try:
            self._events_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            events_file = self._events_dir / f"events_{today}.jsonl"

            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent_name,
                "event": event_type,
                "details": details or {},
            }

            with open(events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
            return True
        except Exception as e:
            logger.warning(f"Failed to log event: {e}")
            return False

    def query_events(
        self,
        agent_name: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self._events_dir.exists():
            return []

        files = sorted(self._events_dir.glob("events_*.jsonl"), reverse=True)
        results: list[dict[str, Any]] = []

        for f in files[:7]:  # Check last 7 days
            try:
                lines = f.read_text(encoding="utf-8").strip().splitlines()
                for line in reversed(lines):  # Most recent first
                    if not line.strip():
                        continue
                    event = json.loads(line)

                    if agent_name and event.get("agent") != agent_name:
                        continue
                    if event_type and event.get("event") != event_type:
                        continue

                    results.append(event)
                    if len(results) >= limit:
                        return results
            except Exception:
                continue

        return results

    def get_all_agent_names(self) -> list[str]:
        if not self.workspaces_dir.exists():
            return []
        return sorted(
            d.name
            for d in self.workspaces_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        )


# ---------------------------------------------------------------------------
# Acontext Backend (stub — activates when Acontext server is running)
# ---------------------------------------------------------------------------


class AcontextBackend(MemoryBackend):
    """Acontext API-based memory backend.

    Delegates to Acontext sessions for rich context management.
    Falls back to None/empty on any error (graceful degradation).
    """

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self._client = None
        self._sessions: dict[str, str] = {}  # agent_name → session_id

    def _get_client(self) -> Any:
        """Lazy-initialize Acontext client."""
        if self._client is None:
            try:
                from acontext import AcontextClient
                self._client = AcontextClient(
                    base_url=self.api_url,
                    api_key=self.api_key,
                )
            except ImportError:
                logger.warning("Acontext SDK not available")
                return None
            except Exception as e:
                logger.warning(f"Failed to init Acontext client: {e}")
                return None
        return self._client

    def _ensure_session(self, agent_name: str) -> str | None:
        """Get or create an Acontext session for an agent."""
        if agent_name in self._sessions:
            return self._sessions[agent_name]

        client = self._get_client()
        if not client:
            return None

        try:
            session = client.sessions.create(
                metadata={
                    "agent_name": agent_name,
                    "type": "memory_bridge",
                    "created": datetime.now(timezone.utc).isoformat(),
                }
            )
            self._sessions[agent_name] = session.id
            return session.id
        except Exception as e:
            logger.warning(f"Failed to create Acontext session for {agent_name}: {e}")
            return None

    def read_working_state(self, agent_name: str) -> str:
        # Acontext stores this as a session artifact
        client = self._get_client()
        if not client:
            return ""
        try:
            session_id = self._ensure_session(agent_name)
            if not session_id:
                return ""
            summary = client.sessions.get_session_summary(session_id=session_id)
            return summary or ""
        except Exception:
            return ""

    def write_working_state(self, agent_name: str, content: str) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            session_id = self._ensure_session(agent_name)
            if not session_id:
                return False
            client.sessions.store_message(
                session_id=session_id,
                blob={"role": "system", "content": content, "type": "working_state"},
                format="anthropic",
            )
            return True
        except Exception:
            return False

    def read_memory(self, agent_name: str) -> str:
        # Memory stored as disk artifact
        return ""  # Stub — full implementation needs disk ID tracking

    def append_memory(self, agent_name: str, section: str, entry: str) -> bool:
        return self.log_event(agent_name, "memory_append", {"section": section, "entry": entry})

    def append_note(self, agent_name: str, action: str, result: str = "") -> bool:
        return self.log_event(agent_name, "daily_note", {"action": action, "result": result})

    def get_recent_notes(self, agent_name: str, limit: int = 20) -> list[str]:
        events = self.query_events(agent_name=agent_name, event_type="daily_note", limit=limit)
        return [
            f"`{e.get('timestamp', '?')[-8:]}` {e.get('details', {}).get('action', '?')}"
            for e in events
        ]

    def log_event(self, agent_name: str, event_type: str, details: dict[str, Any] | None = None) -> bool:
        client = self._get_client()
        if not client:
            return False
        try:
            session_id = self._ensure_session(agent_name)
            if not session_id:
                return False
            client.sessions.store_message(
                session_id=session_id,
                blob={
                    "role": "system",
                    "content": json.dumps({
                        "event": event_type,
                        "details": details or {},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }),
                    "type": "event",
                },
                format="anthropic",
            )
            return True
        except Exception:
            return False

    def query_events(
        self,
        agent_name: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        # Acontext session query — stub for now
        return []

    def get_all_agent_names(self) -> list[str]:
        return list(self._sessions.keys())


# ---------------------------------------------------------------------------
# Memory Bridge (Router)
# ---------------------------------------------------------------------------


class MemoryBridge:
    """Routes memory operations to the best available backend.

    Local backend is always primary. Acontext is used as a secondary
    store when available (write-through, read-fallback).
    """

    def __init__(
        self,
        workspaces_dir: Path,
        acontext_url: str | None = None,
        acontext_key: str | None = None,
    ):
        self.local = LocalBackend(workspaces_dir)
        self.acontext: AcontextBackend | None = None

        if acontext_url and acontext_key:
            self.acontext = AcontextBackend(acontext_url, acontext_key)

    @property
    def has_acontext(self) -> bool:
        return self.acontext is not None

    def read_working_state(self, agent_name: str) -> str:
        """Read working state. Local is source of truth."""
        return self.local.read_working_state(agent_name)

    def write_working_state(self, agent_name: str, content: str) -> bool:
        """Write working state to local. Also writes to Acontext if available."""
        success = self.local.write_working_state(agent_name, content)
        if success and self.acontext:
            # Best effort — don't fail if Acontext is down
            try:
                self.acontext.write_working_state(agent_name, content)
            except Exception:
                pass
        return success

    def read_memory(self, agent_name: str) -> str:
        return self.local.read_memory(agent_name)

    def append_memory(self, agent_name: str, section: str, entry: str) -> bool:
        success = self.local.append_memory(agent_name, section, entry)
        if success and self.acontext:
            try:
                self.acontext.append_memory(agent_name, section, entry)
            except Exception:
                pass
        return success

    def append_note(self, agent_name: str, action: str, result: str = "") -> bool:
        success = self.local.append_note(agent_name, action, result)
        if success and self.acontext:
            try:
                self.acontext.append_note(agent_name, action, result)
            except Exception:
                pass
        return success

    def get_recent_notes(self, agent_name: str, limit: int = 20) -> list[str]:
        return self.local.get_recent_notes(agent_name, limit)

    def log_event(self, agent_name: str, event_type: str, details: dict[str, Any] | None = None) -> bool:
        """Log event to both backends."""
        success = self.local.log_event(agent_name, event_type, details)
        if self.acontext:
            try:
                self.acontext.log_event(agent_name, event_type, details)
            except Exception:
                pass
        return success

    def query_events(
        self,
        agent_name: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query events from local backend (source of truth)."""
        return self.local.query_events(agent_name, event_type, limit)

    def get_all_agent_names(self) -> list[str]:
        return self.local.get_all_agent_names()

    def get_agent_context(
        self,
        agent_name: str,
        max_notes: int = 10,
        max_events: int = 5,
    ) -> AgentContext:
        """Assemble full context for an agent.

        Combines working state, memory, recent notes, and events
        into a single AgentContext ready for LLM injection.
        """
        ctx = AgentContext(agent_name=agent_name)
        ctx.working_state = self.read_working_state(agent_name)
        ctx.memory = self.read_memory(agent_name)
        ctx.recent_notes = self.get_recent_notes(agent_name, limit=max_notes)
        ctx.events = self.query_events(agent_name=agent_name, limit=max_events)
        return ctx

    def get_swarm_overview(self) -> dict[str, AgentContext]:
        """Get context for all agents (used by coordinator)."""
        overview: dict[str, AgentContext] = {}
        for name in self.get_all_agent_names():
            overview[name] = self.get_agent_context(name, max_notes=3, max_events=3)
        return overview
