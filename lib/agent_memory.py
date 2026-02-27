"""
Karma Kadabra V2 — Agent Memory

Maintains a persistent memory of other agents seen in IRC and on
Execution Market. Each agent stores info about peers it has interacted
with, enabling social awareness in the swarm.

Memory file: workspace/memory/agents.json

Structure:
    {
        "kk-skill-extractor": {
            "first_seen": "2026-02-27T19:00:00Z",
            "last_seen": "2026-02-27T20:30:00Z",
            "role": "Analyst - skill extraction",
            "sells": "skill profiles ($0.05)",
            "buys": "chat logs ($0.01)",
            "message_count": 12,
            "interactions": [
                {"type": "purchase", "date": "2026-02-27", "amount": 0.01},
            ],
            "notes": []
        }
    }

Usage:
    from lib.agent_memory import AgentMemory

    mem = AgentMemory(workspace_dir)
    mem.record_seen("kk-skill-extractor", channel="#karmakadabra")
    mem.record_interaction("kk-skill-extractor", "purchase", amount=0.01)
    info = mem.get_agent("kk-skill-extractor")
    all_agents = mem.list_agents()
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("kk.agent-memory")

# Known agent roles (fallback if not learned via IRC)
KNOWN_ROLES = {
    "kk-coordinator": {
        "role": "Orchestrator",
        "sells": "task assignments",
        "buys": "agent status reports",
    },
    "kk-karma-hello": {
        "role": "Data Collector",
        "sells": "raw chat logs ($0.01), user stats ($0.03)",
        "buys": "transcriptions ($0.02)",
    },
    "kk-skill-extractor": {
        "role": "Skill Analyst",
        "sells": "skill profiles ($0.05)",
        "buys": "chat logs ($0.01)",
    },
    "kk-voice-extractor": {
        "role": "Personality Analyst",
        "sells": "personality profiles ($0.04)",
        "buys": "chat logs ($0.01)",
    },
    "kk-soul-extractor": {
        "role": "SOUL Synthesizer",
        "sells": "SOUL.md profiles ($0.08)",
        "buys": "skill + voice data ($0.09)",
    },
    "kk-validator": {
        "role": "Quality Verifier",
        "sells": "validation reports ($0.001)",
        "buys": "data for verification",
    },
}


class AgentMemory:
    """Persistent memory of peer agents."""

    def __init__(self, workspace_dir: Path):
        self.memory_dir = workspace_dir / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.agents_file = self.memory_dir / "agents.json"
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.agents_file.exists():
            try:
                return json.loads(self.agents_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self) -> None:
        try:
            self.agents_file.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"Failed to save agent memory: {e}")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_agent(self, name: str) -> dict:
        """Ensure agent entry exists with defaults."""
        if name not in self._data:
            defaults = KNOWN_ROLES.get(name, {})
            self._data[name] = {
                "first_seen": self._now(),
                "last_seen": self._now(),
                "role": defaults.get("role", "unknown"),
                "sells": defaults.get("sells", ""),
                "buys": defaults.get("buys", ""),
                "message_count": 0,
                "interactions": [],
                "notes": [],
            }
        return self._data[name]

    def record_seen(self, name: str, channel: str = "") -> None:
        """Record that we saw an agent (in IRC or EM)."""
        agent = self._ensure_agent(name)
        agent["last_seen"] = self._now()
        agent["message_count"] = agent.get("message_count", 0) + 1
        self._save()

    def record_interaction(
        self,
        name: str,
        interaction_type: str,
        amount: float = 0.0,
        note: str = "",
    ) -> None:
        """Record an interaction with an agent (purchase, sale, etc.)."""
        agent = self._ensure_agent(name)
        agent["last_seen"] = self._now()

        interaction = {
            "type": interaction_type,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "amount": amount,
        }
        if note:
            interaction["note"] = note

        agent.setdefault("interactions", []).append(interaction)

        # Keep last 50 interactions
        if len(agent["interactions"]) > 50:
            agent["interactions"] = agent["interactions"][-50:]

        self._save()

    def add_note(self, name: str, note: str) -> None:
        """Add a free-text note about an agent."""
        agent = self._ensure_agent(name)
        agent.setdefault("notes", []).append(note)
        # Keep last 20 notes
        if len(agent["notes"]) > 20:
            agent["notes"] = agent["notes"][-20:]
        self._save()

    def update_role(self, name: str, role: str = "", sells: str = "", buys: str = "") -> None:
        """Update learned role info about an agent."""
        agent = self._ensure_agent(name)
        if role:
            agent["role"] = role
        if sells:
            agent["sells"] = sells
        if buys:
            agent["buys"] = buys
        self._save()

    def get_agent(self, name: str) -> dict | None:
        """Get info about a specific agent."""
        return self._data.get(name)

    def list_agents(self) -> list[str]:
        """List all known agent names."""
        return sorted(self._data.keys())

    def get_summary(self) -> str:
        """Get a short summary of all known agents."""
        if not self._data:
            return "No agents known yet."

        lines = []
        for name in sorted(self._data):
            info = self._data[name]
            role = info.get("role", "?")
            count = info.get("message_count", 0)
            interactions = len(info.get("interactions", []))
            lines.append(f"  {name}: {role} ({count} msgs, {interactions} interactions)")

        return f"Known agents ({len(self._data)}):\n" + "\n".join(lines)
