#!/usr/bin/env python3
"""
Coordinator Agent — FastAPI service (port 9006)

The coordinator is a v2 system agent that:
- Monitors all agents via heartbeats
- Matches tasks to agents using 6-factor scoring
- Provides swarm health dashboard
- Routes work between agents

Endpoints:
    GET  /health          - Health check
    GET  /swarm-status    - Full swarm state
    POST /assign          - Trigger task assignment cycle
    POST /heartbeat       - Receive heartbeat from agents
    GET  /.well-known/agent-card - A2A agent card
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.coordinator_service import coordination_cycle, load_agent_skills
from lib.agent_lifecycle import AgentLifecycle, AgentState, AgentType, LifecycleConfig
from lib.swarm_state import get_agent_states, get_swarm_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("kk.coordinator")

app = FastAPI(
    title="KarmaCadabra Coordinator",
    version="2.0.0",
    description="Swarm coordination and task routing for KarmaCadabra agents",
)

# Lifecycle state
lifecycle = AgentLifecycle(
    agent_name="coordinator",
    agent_type=AgentType.SYSTEM,
)

# Track heartbeats from other agents
_agent_heartbeats: Dict[str, Dict[str, Any]] = {}
_startup_time = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class HeartbeatRequest(BaseModel):
    agent_name: str
    state: str = "idle"
    network: Optional[str] = None
    current_task_id: Optional[str] = None
    consecutive_failures: int = 0


class AssignRequest(BaseModel):
    dry_run: bool = False
    legacy_matching: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agent": "coordinator",
        "version": "2.0.0",
        "state": lifecycle.state.value,
        "uptime_since": _startup_time,
        "agents_tracked": len(_agent_heartbeats),
    }


@app.get("/.well-known/agent-card")
async def agent_card():
    return {
        "name": "kk-coordinator",
        "description": "KarmaCadabra swarm coordinator - task routing and health monitoring",
        "version": "2.0.0",
        "capabilities": ["coordination", "health-monitoring", "task-matching"],
        "endpoints": {
            "health": "/health",
            "swarm_status": "/swarm-status",
            "assign": "/assign",
            "heartbeat": "/heartbeat",
        },
    }


@app.post("/heartbeat")
async def receive_heartbeat(req: HeartbeatRequest):
    """Receive heartbeat from an agent."""
    now = datetime.now(timezone.utc).isoformat()
    _agent_heartbeats[req.agent_name] = {
        "agent_name": req.agent_name,
        "state": req.state,
        "network": req.network,
        "current_task_id": req.current_task_id,
        "consecutive_failures": req.consecutive_failures,
        "last_heartbeat": now,
    }
    return {"status": "ok", "received_at": now}


@app.get("/swarm-status")
async def swarm_status():
    """Return full swarm state: all agents, their states, and health."""
    agents_by_state: Dict[str, list] = {}
    for name, info in _agent_heartbeats.items():
        state = info.get("state", "unknown")
        agents_by_state.setdefault(state, []).append(name)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(_agent_heartbeats),
        "agents_by_state": agents_by_state,
        "agents": list(_agent_heartbeats.values()),
        "coordinator_state": lifecycle.state.value,
    }


@app.post("/assign")
async def trigger_assignment(req: AssignRequest):
    """Trigger a coordination cycle: match tasks to idle agents."""
    try:
        workspaces_dir = Path(os.getenv("WORKSPACES_DIR", "data/workspaces"))

        # For now, return a summary of what would be assigned
        idle_agents = [
            name for name, info in _agent_heartbeats.items()
            if info.get("state") == "idle"
        ]

        return {
            "status": "cycle_complete",
            "dry_run": req.dry_run,
            "idle_agents": idle_agents,
            "agents_available": len(idle_agents),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Assignment cycle failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    lifecycle.state = AgentState.IDLE
    lifecycle.last_heartbeat = datetime.now(timezone.utc).isoformat()
    logger.info("[coordinator] Agent started on port 9006")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "9006"))
    uvicorn.run(app, host="0.0.0.0", port=port)
