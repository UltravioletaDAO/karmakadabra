"""
Karma Kadabra V2 — Phase 8: Shared Swarm State Client

Python client for the kk_swarm_state, kk_task_claims, and kk_notifications
Supabase tables. Used by all KK agents and the coordinator.

All functions are async and use the project's existing Supabase connection.
Failures are non-fatal — agents should always fall back to local WORKING.md.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("kk.swarm_state")

# Lazy-loaded Supabase client (not all environments have supabase-py)
_supabase_client = None


def _get_supabase():
    """Lazy-load Supabase client."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    try:
        from supabase import create_client
    except ImportError:
        logger.warning("supabase-py not installed — swarm state disabled")
        return None

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

    if not url or not key:
        logger.warning("SUPABASE_URL or key not set — swarm state disabled")
        return None

    try:
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        logger.warning(f"Failed to create Supabase client: {e}")
        return None


# ---------------------------------------------------------------------------
# kk_swarm_state — Agent heartbeat reporting
# ---------------------------------------------------------------------------


async def report_heartbeat(
    agent_name: str,
    status: str = "idle",
    task_id: str | None = None,
    daily_spent: float = 0.0,
    current_chain: str = "base",
    notes: str = "",
) -> bool:
    """Upsert agent heartbeat to kk_swarm_state.

    Returns True on success, False on failure (non-fatal).
    """
    sb = _get_supabase()
    if sb is None:
        return False

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "agent_name": agent_name,
        "status": status,
        "task_id": task_id or "",
        "last_heartbeat": now,
        "daily_spent_usd": daily_spent,
        "current_chain": current_chain,
        "notes": notes,
        "updated_at": now,
    }

    try:
        sb.table("kk_swarm_state").upsert(row, on_conflict="agent_name").execute()
        return True
    except Exception as e:
        logger.warning(f"report_heartbeat failed: {e}")
        return False


async def get_agent_states(
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Read all agent states, optionally filtered by status.

    Returns empty list on failure (non-fatal).
    """
    sb = _get_supabase()
    if sb is None:
        return []

    try:
        query = sb.table("kk_swarm_state").select("*")
        if status:
            query = query.eq("status", status)
        result = query.order("agent_name").execute()
        return result.data or []
    except Exception as e:
        logger.warning(f"get_agent_states failed: {e}")
        return []


async def get_agent_state(agent_name: str) -> dict[str, Any] | None:
    """Read a single agent's state.

    Returns None if not found or on failure.
    """
    sb = _get_supabase()
    if sb is None:
        return None

    try:
        result = (
            sb.table("kk_swarm_state")
            .select("*")
            .eq("agent_name", agent_name)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"get_agent_state failed: {e}")
        return None


async def get_stale_agents(stale_minutes: int = 30) -> list[dict[str, Any]]:
    """Find agents whose last heartbeat is older than stale_minutes.

    Returns empty list on failure.
    """
    sb = _get_supabase()
    if sb is None:
        return []

    try:
        # Use RPC or manual filtering
        all_agents = await get_agent_states()
        now = datetime.now(timezone.utc)
        stale = []
        for agent in all_agents:
            hb = agent.get("last_heartbeat")
            if hb:
                last = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                diff = (now - last).total_seconds() / 60
                if diff > stale_minutes:
                    stale.append({**agent, "minutes_stale": round(diff, 1)})
        return stale
    except Exception as e:
        logger.warning(f"get_stale_agents failed: {e}")
        return []


# ---------------------------------------------------------------------------
# kk_task_claims — Atomic task claiming
# ---------------------------------------------------------------------------


async def claim_task(em_task_id: str, agent_name: str) -> bool:
    """Atomically claim a task. Returns False if already claimed.

    Uses UNIQUE constraint on em_task_id for atomicity.
    """
    sb = _get_supabase()
    if sb is None:
        return False

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "em_task_id": em_task_id,
        "claimed_by": agent_name,
        "claimed_at": now,
        "status": "claimed",
    }

    try:
        sb.table("kk_task_claims").insert(row).execute()
        return True
    except Exception as e:
        # UNIQUE violation = already claimed
        if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
            logger.info(f"Task {em_task_id} already claimed")
            return False
        logger.warning(f"claim_task failed: {e}")
        return False


async def release_claim(em_task_id: str) -> bool:
    """Release a task claim (mark as released)."""
    sb = _get_supabase()
    if sb is None:
        return False

    try:
        sb.table("kk_task_claims").update(
            {"status": "released"}
        ).eq("em_task_id", em_task_id).execute()
        return True
    except Exception as e:
        logger.warning(f"release_claim failed: {e}")
        return False


async def get_claimed_tasks(agent_name: str | None = None) -> list[dict[str, Any]]:
    """Get all active claims, optionally filtered by agent."""
    sb = _get_supabase()
    if sb is None:
        return []

    try:
        query = sb.table("kk_task_claims").select("*").eq("status", "claimed")
        if agent_name:
            query = query.eq("claimed_by", agent_name)
        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.warning(f"get_claimed_tasks failed: {e}")
        return []


# ---------------------------------------------------------------------------
# kk_notifications — Coordinator -> Agent messaging
# ---------------------------------------------------------------------------


async def send_notification(
    target_agent: str,
    from_agent: str,
    content: str,
) -> bool:
    """Send a notification to a target agent."""
    sb = _get_supabase()
    if sb is None:
        return False

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "target_agent": target_agent,
        "from_agent": from_agent,
        "content": content,
        "delivered": False,
        "created_at": now,
    }

    try:
        sb.table("kk_notifications").insert(row).execute()
        return True
    except Exception as e:
        logger.warning(f"send_notification failed: {e}")
        return False


async def poll_notifications(agent_name: str) -> list[dict[str, Any]]:
    """Poll for undelivered notifications and mark them as delivered.

    Returns list of notification dicts. Empty on failure.
    """
    sb = _get_supabase()
    if sb is None:
        return []

    try:
        # Fetch undelivered
        result = (
            sb.table("kk_notifications")
            .select("*")
            .eq("target_agent", agent_name)
            .eq("delivered", False)
            .order("created_at")
            .execute()
        )
        notifications = result.data or []

        # Mark as delivered
        if notifications:
            ids = [n["id"] for n in notifications]
            for nid in ids:
                sb.table("kk_notifications").update(
                    {"delivered": True}
                ).eq("id", nid).execute()

        return notifications
    except Exception as e:
        logger.warning(f"poll_notifications failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Health / summary
# ---------------------------------------------------------------------------


async def get_swarm_summary() -> dict[str, Any]:
    """Get a summary of the swarm state for standup reports."""
    all_agents = await get_agent_states()
    stale = await get_stale_agents()
    claims = await get_claimed_tasks()

    by_status: dict[str, int] = {}
    total_spent = 0.0
    for agent in all_agents:
        s = agent.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        total_spent += float(agent.get("daily_spent_usd", 0))

    return {
        "total_agents": len(all_agents),
        "by_status": by_status,
        "stale_agents": len(stale),
        "active_claims": len(claims),
        "total_daily_spent_usd": round(total_spent, 2),
    }
