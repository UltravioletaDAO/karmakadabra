"""
Karma Kadabra V2 — Acontext Integration Client

Shared wrapper for the Acontext SDK that provides KK-specific abstractions:
  - Per-agent session management (create, store, retrieve with compression)
  - Workspace disk management (artifacts, search)
  - Skill registry access (mount EM skills)
  - Observability helpers (session summary, health check)

Requires:
  pip install acontext  (v0.1.13+)

Configuration via environment variables:
  ACONTEXT_API_URL  — Default: http://localhost:8029/api/v1
  ACONTEXT_API_KEY  — Root API key from `acontext server up`

Usage:
  from lib.acontext_client import KKAcontextClient

  ac = KKAcontextClient()
  session = ac.create_agent_session("kk-coordinator", agent_id=18775)
  ac.store_interaction(session.id, role="user", content="Browse EM for tasks")
  messages = ac.get_compressed_context(session.id, max_tokens=50000)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("kk.acontext")

# Lazy-load SDK to avoid import errors when not installed
_client = None


def _get_client():
    """Lazy-initialize Acontext client."""
    global _client
    if _client is not None:
        return _client

    try:
        from acontext import AcontextClient
    except ImportError:
        logger.warning("acontext SDK not installed — context features disabled")
        return None

    api_url = os.environ.get("ACONTEXT_API_URL", "http://localhost:8029/api/v1")
    api_key = os.environ.get("ACONTEXT_API_KEY", "")

    if not api_key:
        logger.warning("ACONTEXT_API_KEY not set — context features disabled")
        return None

    try:
        _client = AcontextClient(base_url=api_url, api_key=api_key)
        logger.info(f"Acontext client initialized: {api_url}")
        return _client
    except Exception as e:
        logger.warning(f"Failed to initialize Acontext client: {e}")
        return None


class KKAcontextClient:
    """KK-specific Acontext operations.

    Designed to be non-blocking and gracefully degrade when Acontext
    is unavailable (returns None, logs warning, agents continue working).
    """

    def __init__(self):
        self._client = _get_client()
        self._agent_sessions: dict[str, str] = {}  # agent_name -> session_id
        self._agent_disks: dict[str, str] = {}  # agent_name -> disk_id

    @property
    def available(self) -> bool:
        """Check if Acontext is available."""
        return self._client is not None

    # ── Session Management ────────────────────────────────────────

    def create_agent_session(
        self,
        agent_name: str,
        agent_id: int | None = None,
        archetype: str = "unknown",
        cycle_id: str | None = None,
    ) -> Any | None:
        """Create a new Acontext session for an agent's work cycle.

        Returns the session object or None if unavailable.
        """
        if not self._client:
            return None

        try:
            metadata = {
                "agent_name": agent_name,
                "archetype": archetype,
                "cycle": cycle_id or datetime.now(timezone.utc).isoformat(),
                "platform": "execution-market",
            }
            if agent_id:
                metadata["erc8004_agent_id"] = agent_id

            session = self._client.sessions.create(metadata=metadata)
            self._agent_sessions[agent_name] = session.id
            logger.info(f"Created Acontext session for {agent_name}: {session.id}")
            return session
        except Exception as e:
            logger.warning(f"Failed to create session for {agent_name}: {e}")
            return None

    def store_interaction(
        self,
        session_id: str,
        role: str,
        content: str,
        format: str = "anthropic",
        metadata: dict | None = None,
    ) -> bool:
        """Store a message in an agent's session.

        Returns True on success, False on failure.
        """
        if not self._client:
            return False

        try:
            blob = {"role": role, "content": content}
            if metadata:
                blob["metadata"] = metadata

            self._client.sessions.store_message(
                session_id=session_id,
                blob=blob,
                format=format,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to store message in session {session_id}: {e}")
            return False

    def get_compressed_context(
        self,
        session_id: str,
        max_tokens: int = 50000,
        keep_recent_tools: int = 5,
        format: str = "anthropic",
    ) -> list[dict] | None:
        """Retrieve compressed context for an agent session.

        Uses Acontext's edit strategies to keep context within token limits.
        Returns list of messages or None if unavailable.
        """
        if not self._client:
            return None

        try:
            result = self._client.sessions.get_messages(
                session_id=session_id,
                format=format,
                edit_strategies=[
                    {
                        "type": "remove_tool_result",
                        "params": {"keep_recent_n_tool_results": keep_recent_tools},
                    },
                    {
                        "type": "token_limit",
                        "params": {"limit_tokens": max_tokens},
                    },
                ],
            )
            return result
        except Exception as e:
            logger.warning(f"Failed to get context for session {session_id}: {e}")
            return None

    def get_session_summary(self, session_id: str) -> str | None:
        """Get an AI-generated summary of an agent's session.

        Useful for coordinator oversight and cross-agent awareness.
        """
        if not self._client:
            return None

        try:
            summary = self._client.sessions.get_session_summary(session_id=session_id)
            return summary
        except Exception as e:
            logger.warning(f"Failed to get summary for session {session_id}: {e}")
            return None

    # ── Disk (Workspace) Management ───────────────────────────────

    def create_agent_disk(
        self,
        agent_name: str,
        metadata: dict | None = None,
    ) -> Any | None:
        """Create a persistent disk for an agent's workspace."""
        if not self._client:
            return None

        try:
            disk = self._client.disks.create(
                name=f"kk-{agent_name}-workspace",
                metadata=metadata or {},
            )
            self._agent_disks[agent_name] = disk.id
            logger.info(f"Created disk for {agent_name}: {disk.id}")
            return disk
        except Exception as e:
            logger.warning(f"Failed to create disk for {agent_name}: {e}")
            return None

    def store_artifact(
        self,
        disk_id: str,
        path: str,
        filename: str,
        content: str | bytes,
    ) -> bool:
        """Store a file in an agent's disk."""
        if not self._client:
            return False

        try:
            self._client.artifacts.upsert(
                disk_id=disk_id,
                path=path,
                filename=filename,
                content=content,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to store artifact {path}/{filename}: {e}")
            return False

    def search_artifacts(
        self,
        disk_id: str,
        pattern: str,
    ) -> list | None:
        """Search artifact content with regex."""
        if not self._client:
            return None

        try:
            results = self._client.artifacts.search_content(
                disk_id=disk_id,
                pattern=pattern,
            )
            return results
        except Exception as e:
            logger.warning(f"Failed to search artifacts: {e}")
            return None

    # ── Convenience Methods ───────────────────────────────────────

    def get_agent_session_id(self, agent_name: str) -> str | None:
        """Get the current session ID for an agent."""
        return self._agent_sessions.get(agent_name)

    def get_agent_disk_id(self, agent_name: str) -> str | None:
        """Get the disk ID for an agent."""
        return self._agent_disks.get(agent_name)

    def store_coordinator_event(
        self,
        session_id: str,
        event_type: str,
        details: dict,
    ) -> bool:
        """Store a coordination event (task assignment, health check, etc.)."""
        content = f"[{event_type.upper()}] {details}"
        return self.store_interaction(
            session_id=session_id,
            role="assistant",
            content=content,
            metadata={"event_type": event_type, **details},
        )

    def health_check(self) -> dict:
        """Check Acontext server health."""
        if not self._client:
            return {"status": "unavailable", "reason": "client not initialized"}

        try:
            result = self._client.ping()
            return {"status": "healthy", "response": str(result)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton for easy import
_kk_client: KKAcontextClient | None = None


def get_acontext() -> KKAcontextClient:
    """Get the shared KK Acontext client (singleton)."""
    global _kk_client
    if _kk_client is None:
        _kk_client = KKAcontextClient()
    return _kk_client
