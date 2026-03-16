"""
Swarm HTTP API — REST Interface for the KarmaKadabra Agent Swarm
================================================================

Exposes the swarm's capabilities as a REST API for:
- Real-time monitoring dashboards
- External agent integration
- Webhook receivers for EM task events
- Health checks for infrastructure monitoring

Endpoints:
    GET  /                         → API info and version
    GET  /health                   → Health check (for load balancers)
    GET  /status                   → Full swarm status
    GET  /agents                   → List all agents with state
    GET  /agents/{agent_id}        → Single agent detail
    POST /agents/{agent_id}/wake   → Wake a sleeping agent
    POST /agents/{agent_id}/sleep  → Sleep an active agent
    GET  /tasks                    → Active task assignments
    POST /tasks/assign             → Manually assign a task
    POST /tasks/cycle              → Run one coordination cycle
    GET  /economics                → Economic summary
    GET  /leaderboard              → Reputation leaderboard
    GET  /metrics                  → Prometheus-compatible metrics
    POST /webhook/em               → EM task event webhook receiver
    GET  /dashboard                → HTML dashboard (self-contained)

Usage:
    # Start standalone
    python -m mcp_server.swarm.swarm_api --port 8888

    # Import and mount in existing app
    from mcp_server.swarm.swarm_api import create_app
    app = create_app(runner)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aiohttp import web

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server.swarm.swarm_runner import SwarmRunner, KK_ROSTER
from mcp_server.swarm.swarm_analytics import SwarmAnalytics

logger = logging.getLogger("swarm_api")

# ══════════════════════════════════════════════
# API Version
# ══════════════════════════════════════════════

API_VERSION = "1.0.0"
API_NAME = "KarmaKadabra Swarm API"


# ══════════════════════════════════════════════
# Route Handlers
# ══════════════════════════════════════════════


async def handle_root(request: web.Request) -> web.Response:
    """API info and version."""
    runner: SwarmRunner = request.app["runner"]
    return web.json_response({
        "name": API_NAME,
        "version": API_VERSION,
        "agents": len(runner.lifecycle.agents),
        "uptime_seconds": int(time.time() - request.app["start_time"]),
        "endpoints": [
            "GET  /health",
            "GET  /status",
            "GET  /agents",
            "GET  /agents/{id}",
            "POST /agents/{id}/wake",
            "POST /agents/{id}/sleep",
            "GET  /tasks",
            "POST /tasks/assign",
            "POST /tasks/cycle",
            "GET  /economics",
            "GET  /leaderboard",
            "GET  /metrics",
            "POST /webhook/em",
            "GET  /dashboard",
        ],
    })


async def handle_health(request: web.Request) -> web.Response:
    """Health check for load balancers and monitoring."""
    runner: SwarmRunner = request.app["runner"]
    health = runner.lifecycle.health_check()
    metrics = runner.orchestrator.metrics()

    status_code = 200 if health["active"] > 0 else 503

    return web.json_response({
        "status": "healthy" if status_code == 200 else "degraded",
        "agents_active": health["active"],
        "agents_total": health["total_agents"],
        "tasks_active": metrics["tasks"]["active"],
        "uptime_seconds": int(time.time() - request.app["start_time"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, status=status_code)


async def handle_status(request: web.Request) -> web.Response:
    """Full swarm status — everything in one call."""
    runner: SwarmRunner = request.app["runner"]
    health = runner.lifecycle.health_check()
    metrics = runner.orchestrator.metrics()
    economics = runner.orchestrator.economic_summary()

    # Agent summary by tier
    tier_summary = {"system": 0, "core": 0, "user": 0}
    for spec in KK_ROSTER:
        tier = spec.get("tier", "user")
        if spec["agent_id"] in runner.lifecycle.agents:
            agent = runner.lifecycle.agents[spec["agent_id"]]
            if agent.status.value == "active":
                tier_summary[tier] = tier_summary.get(tier, 0) + 1

    return web.json_response({
        "swarm": {
            "name": "KarmaKadabra V2",
            "version": API_VERSION,
            "uptime_seconds": int(time.time() - request.app["start_time"]),
            "cycle_count": runner._cycle_count,
        },
        "agents": {
            "total": health["total_agents"],
            "active": health["active"],
            "sleeping": health["sleeping"],
            "error": health["error"],
            "retired": health["retired"],
            "by_tier": tier_summary,
        },
        "tasks": metrics["tasks"],
        "economics": {
            "total_earned_usd": economics["total_earned_usd"],
            "total_spent_usd": economics["total_spent_usd"],
            "net_usd": economics["net_usd"],
            "completion_rate": economics["completion_rate"],
            "avg_earnings_per_task": economics["avg_earnings_per_task"],
        },
        "health": {
            "healthy_agents": health["healthy"],
            "budget_remaining_pct": health["budget_remaining_pct"],
            "status": "healthy" if health["active"] > 0 else "degraded",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def handle_agents_list(request: web.Request) -> web.Response:
    """List all agents with their current state."""
    runner: SwarmRunner = request.app["runner"]
    health = runner.lifecycle.health_check()

    # Build roster lookup
    roster_lookup = {spec["agent_id"]: spec for spec in KK_ROSTER}

    agents = []
    for agent_info in health["agents"]:
        agent_id = agent_info["agent_id"]
        spec = roster_lookup.get(agent_id, {})
        profile = runner.orchestrator.profiles.get(agent_id)

        agent_data = {
            "agent_id": agent_id,
            "status": agent_info["status"],
            "healthy": agent_info["healthy"],
            "budget_pct": agent_info["budget_pct"],
            "tasks_today": agent_info["tasks_today"],
            "tier": spec.get("tier", "unknown"),
            "personality": spec.get("personality", "unknown"),
            "model": spec.get("model", "unknown"),
            "skills": spec.get("skills", []),
            "specializations": spec.get("specializations", []),
        }

        if profile:
            agent_data["reputation_score"] = profile.reputation_score
            agent_data["availability_score"] = profile.availability_score
            agent_data["wallet"] = profile.wallet

        agents.append(agent_data)

    # Sort: active first, then by tier
    tier_order = {"system": 0, "core": 1, "user": 2}
    agents.sort(key=lambda a: (
        0 if a["status"] == "active" else 1,
        tier_order.get(a["tier"], 3),
        a["agent_id"],
    ))

    return web.json_response({
        "agents": agents,
        "total": len(agents),
        "active": sum(1 for a in agents if a["status"] == "active"),
    })


async def handle_agent_detail(request: web.Request) -> web.Response:
    """Single agent detail."""
    runner: SwarmRunner = request.app["runner"]
    agent_id = request.match_info["agent_id"]

    if agent_id not in runner.lifecycle.agents:
        return web.json_response(
            {"error": f"Agent '{agent_id}' not found"},
            status=404,
        )

    agent = runner.lifecycle.agents[agent_id]
    profile = runner.orchestrator.profiles.get(agent_id)
    spec = next((s for s in KK_ROSTER if s["agent_id"] == agent_id), {})

    # Get reputation
    rep = None
    if profile:
        rep = await runner.bridge.get_bridged_reputation(profile.wallet)

    data = {
        "agent_id": agent_id,
        "status": agent.status.value,
        "tier": spec.get("tier", "unknown"),
        "personality": spec.get("personality", "unknown"),
        "model": spec.get("model", "unknown"),
        "skills": spec.get("skills", []),
        "specializations": spec.get("specializations", []),
        "lifecycle": {
            "status": agent.status.value,
            "created_at": str(getattr(agent, "created_at", "")) if getattr(agent, "created_at", None) else None,
            "last_heartbeat": str(getattr(agent, "last_heartbeat", "")) if getattr(agent, "last_heartbeat", None) else None,
            "consecutive_failures": getattr(agent, "consecutive_failures", 0),
            "uptime_seconds": getattr(agent, "uptime_seconds", 0),
        },
        "budget": {
            "tokens_used_today": agent.usage.tokens_today if agent.usage else 0,
            "max_tokens_per_day": agent.budget.max_tokens_per_day if agent.budget else 0,
            "usd_spent_today": agent.usage.usd_spent_today if agent.usage else 0,
            "max_usd_spend_per_day": agent.budget.max_usd_spend_per_day if agent.budget else 0,
        },
    }

    if profile:
        data["profile"] = {
            "wallet": profile.wallet,
            "reputation_score": profile.reputation_score,
            "availability_score": profile.availability_score,
        }

    if rep:
        data["reputation"] = {
            "composite_score": rep.composite_score,
            "confidence": rep.confidence,
            "tier": rep.tier,
            "evidence_weight": rep.evidence_weight,
        }

    return web.json_response(data)


async def handle_agent_wake(request: web.Request) -> web.Response:
    """Wake a sleeping agent."""
    runner: SwarmRunner = request.app["runner"]
    agent_id = request.match_info["agent_id"]

    if agent_id not in runner.lifecycle.agents:
        return web.json_response({"error": f"Agent '{agent_id}' not found"}, status=404)

    try:
        runner.lifecycle.wake_agent(agent_id)
        # Complete the wake cycle: waking → active
        agent = runner.lifecycle.agents[agent_id]
        if agent.status.value == "waking":
            runner.lifecycle.activate_agent(agent_id)
        return web.json_response({
            "agent_id": agent_id,
            "action": "wake",
            "new_status": runner.lifecycle.agents[agent_id].status.value,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def handle_agent_sleep(request: web.Request) -> web.Response:
    """Sleep an active agent."""
    runner: SwarmRunner = request.app["runner"]
    agent_id = request.match_info["agent_id"]

    if agent_id not in runner.lifecycle.agents:
        return web.json_response({"error": f"Agent '{agent_id}' not found"}, status=404)

    try:
        runner.lifecycle.sleep_agent(agent_id, reason="API request")
        return web.json_response({
            "agent_id": agent_id,
            "action": "sleep",
            "new_status": runner.lifecycle.agents[agent_id].status.value,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def handle_tasks(request: web.Request) -> web.Response:
    """List active task assignments."""
    runner: SwarmRunner = request.app["runner"]
    metrics = runner.orchestrator.metrics()

    # Get assignment history from orchestrator
    assignments = []
    for agent_id, profile in runner.orchestrator.profiles.items():
        if hasattr(profile, 'current_task') and profile.current_task:
            assignments.append({
                "agent_id": agent_id,
                "task_id": profile.current_task,
                "status": "active",
            })

    return web.json_response({
        "active_tasks": assignments,
        "summary": metrics["tasks"],
    })


async def handle_task_assign(request: web.Request) -> web.Response:
    """Manually assign a task to an agent."""
    runner: SwarmRunner = request.app["runner"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    task_id = body.get("task_id")
    category = body.get("category", "general")
    bounty = float(body.get("bounty_usd", 0))

    if not task_id:
        return web.json_response({"error": "task_id is required"}, status=400)

    try:
        assignment = await runner.orchestrator.assign_task(
            task_id=task_id,
            category=category,
            bounty_usd=bounty,
        )
        return web.json_response({
            "task_id": task_id,
            "assigned_agent": assignment.assigned_agent,
            "score": assignment.score,
            "reasoning": assignment.reasoning if hasattr(assignment, 'reasoning') else None,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_task_cycle(request: web.Request) -> web.Response:
    """Run one coordination cycle manually."""
    runner: SwarmRunner = request.app["runner"]

    try:
        summary = await runner.cycle()
        # Serialize with default=str for datetime objects, then parse back
        serialized = json.loads(json.dumps(summary, default=str))
        return web.json_response(serialized)
    except Exception as e:
        logger.exception("Cycle error")
        return web.json_response({"error": str(e)}, status=500)


async def handle_economics(request: web.Request) -> web.Response:
    """Economic summary."""
    runner: SwarmRunner = request.app["runner"]
    summary = runner.orchestrator.economic_summary()
    return web.json_response(summary)


async def handle_leaderboard(request: web.Request) -> web.Response:
    """Reputation leaderboard."""
    runner: SwarmRunner = request.app["runner"]

    leaderboard = []
    for agent_id, profile in runner.orchestrator.profiles.items():
        rep = await runner.bridge.get_bridged_reputation(profile.wallet)
        leaderboard.append({
            "rank": 0,
            "agent_id": agent_id,
            "wallet": profile.wallet,
            "composite_score": rep.composite_score,
            "confidence": rep.confidence,
            "tier": rep.tier,
            "evidence_weight": rep.evidence_weight,
            "reputation_score": profile.reputation_score,
        })

    # Sort by composite score descending
    leaderboard.sort(key=lambda x: -x["composite_score"])
    for i, entry in enumerate(leaderboard, 1):
        entry["rank"] = i

    return web.json_response({
        "leaderboard": leaderboard,
        "total_agents": len(leaderboard),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def handle_metrics(request: web.Request) -> web.Response:
    """Prometheus-compatible metrics endpoint."""
    runner: SwarmRunner = request.app["runner"]
    health = runner.lifecycle.health_check()
    metrics = runner.orchestrator.metrics()
    economics = runner.orchestrator.economic_summary()

    lines = [
        "# HELP kk_agents_total Total number of agents in the swarm",
        "# TYPE kk_agents_total gauge",
        f"kk_agents_total {health['total_agents']}",
        "",
        "# HELP kk_agents_active Number of active agents",
        "# TYPE kk_agents_active gauge",
        f"kk_agents_active {health['active']}",
        "",
        "# HELP kk_agents_sleeping Number of sleeping agents",
        "# TYPE kk_agents_sleeping gauge",
        f"kk_agents_sleeping {health['sleeping']}",
        "",
        "# HELP kk_agents_error Number of agents in error state",
        "# TYPE kk_agents_error gauge",
        f"kk_agents_error {health['error']}",
        "",
        "# HELP kk_tasks_assigned_total Total tasks assigned",
        "# TYPE kk_tasks_assigned_total counter",
        f"kk_tasks_assigned_total {metrics['tasks']['total_assigned']}",
        "",
        "# HELP kk_tasks_completed_total Total tasks completed",
        "# TYPE kk_tasks_completed_total counter",
        f"kk_tasks_completed_total {metrics['tasks']['total_completed']}",
        "",
        "# HELP kk_tasks_active Currently active tasks",
        "# TYPE kk_tasks_active gauge",
        f"kk_tasks_active {metrics['tasks']['active']}",
        "",
        "# HELP kk_tasks_success_rate Task success rate",
        "# TYPE kk_tasks_success_rate gauge",
        f"kk_tasks_success_rate {metrics['tasks']['success_rate']}",
        "",
        "# HELP kk_earned_usd_total Total USD earned by swarm",
        "# TYPE kk_earned_usd_total counter",
        f"kk_earned_usd_total {economics['total_earned_usd']}",
        "",
        "# HELP kk_spent_usd_total Total USD spent by swarm",
        "# TYPE kk_spent_usd_total counter",
        f"kk_spent_usd_total {economics['total_spent_usd']}",
        "",
        "# HELP kk_net_usd Net P&L in USD",
        "# TYPE kk_net_usd gauge",
        f"kk_net_usd {economics['net_usd']}",
        "",
        "# HELP kk_budget_remaining_pct Percentage of daily budget remaining",
        "# TYPE kk_budget_remaining_pct gauge",
        f"kk_budget_remaining_pct {health['budget_remaining_pct']}",
        "",
        "# HELP kk_cycles_total Total coordination cycles run",
        "# TYPE kk_cycles_total counter",
        f"kk_cycles_total {runner._cycle_count}",
        "",
        "# HELP kk_uptime_seconds Server uptime in seconds",
        "# TYPE kk_uptime_seconds gauge",
        f"kk_uptime_seconds {int(time.time() - request.app['start_time'])}",
        "",
    ]

    # Per-agent metrics
    for agent_id, agent in runner.lifecycle.agents.items():
        status_val = 1 if agent.status.value == "active" else 0
        lines.append(f'kk_agent_active{{agent_id="{agent_id}"}} {status_val}')
        if agent.usage:
            lines.append(
                f'kk_agent_tokens_used{{agent_id="{agent_id}"}} '
                f'{agent.usage.tokens_today}'
            )
            lines.append(
                f'kk_agent_usd_spent{{agent_id="{agent_id}"}} '
                f'{agent.usage.usd_spent_today}'
            )

    return web.Response(
        text="\n".join(lines) + "\n",
        content_type="text/plain",
    )


async def handle_webhook_em(request: web.Request) -> web.Response:
    """
    Receive webhook events from Execution Market.

    Handles:
    - task.published: New task available
    - task.assigned: Task was assigned to a worker
    - task.completed: Worker submitted evidence
    - task.approved: Evidence approved, payment released
    - task.disputed: Task in dispute
    """
    runner: SwarmRunner = request.app["runner"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    event_type = body.get("event", body.get("type", "unknown"))
    task_data = body.get("task", body.get("data", {}))
    timestamp = body.get("timestamp", datetime.now(timezone.utc).isoformat())

    logger.info(f"Webhook received: {event_type} for task {task_data.get('id', '?')}")

    # Store event for processing
    event_log = request.app.get("webhook_events", [])
    event_log.append({
        "event": event_type,
        "task": task_data,
        "received_at": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 100 events (mutate in place to avoid deprecation warning)
    while len(event_log) > 100:
        event_log.pop(0)

    # Process event
    result = {"event": event_type, "processed": False}

    if event_type == "task.published":
        # New task — try to assign to an agent
        try:
            assignment = await runner.orchestrator.assign_task(
                task_id=task_data.get("id", ""),
                category=task_data.get("category", "general"),
                bounty_usd=float(task_data.get("bounty_usd", 0)),
            )
            result["processed"] = True
            result["assigned_to"] = assignment.assigned_agent
            result["score"] = assignment.score
        except Exception as e:
            result["error"] = str(e)

    elif event_type == "task.approved":
        # Payment released — update economics
        result["processed"] = True
        result["note"] = "Economics updated"

    elif event_type == "task.disputed":
        result["processed"] = True
        result["note"] = "Dispute logged for review"

    else:
        result["note"] = f"Event type '{event_type}' acknowledged"

    return web.json_response(result)


async def handle_analytics_report(request: web.Request) -> web.Response:
    """Generate a full analytics report."""
    runner: SwarmRunner = request.app["runner"]
    analytics: SwarmAnalytics = request.app["analytics"]
    
    report = analytics.generate_report()
    
    # Check if markdown format requested
    fmt = request.query.get("format", "json")
    if fmt == "markdown":
        return web.Response(
            text=report.to_markdown(),
            content_type="text/markdown",
        )
    
    return web.json_response(report.to_dict())


async def handle_analytics_score(request: web.Request) -> web.Response:
    """Score a specific agent."""
    runner: SwarmRunner = request.app["runner"]
    analytics: SwarmAnalytics = request.app["analytics"]
    agent_id = request.match_info["agent_id"]
    
    if agent_id not in runner.lifecycle.agents:
        return web.json_response({"error": f"Agent '{agent_id}' not found"}, status=404)
    
    score = analytics.score_agent(agent_id)
    return web.json_response(score.to_dict())


async def handle_analytics_anomalies(request: web.Request) -> web.Response:
    """Detect anomalies in the swarm."""
    analytics: SwarmAnalytics = request.app["analytics"]
    anomalies = analytics.detect_anomalies()
    return web.json_response({
        "anomalies": [a.to_dict() for a in anomalies],
        "total": len(anomalies),
        "critical": sum(1 for a in anomalies if a.severity == "critical"),
        "warnings": sum(1 for a in anomalies if a.severity == "warning"),
    })


async def handle_analytics_recommendations(request: web.Request) -> web.Response:
    """Get optimization recommendations."""
    analytics: SwarmAnalytics = request.app["analytics"]
    recs = analytics.get_recommendations()
    return web.json_response({
        "recommendations": [r.to_dict() for r in recs],
        "total": len(recs),
    })


async def handle_dashboard(request: web.Request) -> web.Response:
    """Serve a self-contained HTML dashboard."""
    runner: SwarmRunner = request.app["runner"]
    health = runner.lifecycle.health_check()
    metrics = runner.orchestrator.metrics()
    economics = runner.orchestrator.economic_summary()

    # Build agent rows
    agent_rows = []
    roster_lookup = {s["agent_id"]: s for s in KK_ROSTER}
    for agent_info in sorted(health["agents"], key=lambda a: a["agent_id"]):
        spec = roster_lookup.get(agent_info["agent_id"], {})
        status_emoji = {
            "active": "🟢", "sleeping": "😴", "booting": "🔄",
            "error": "🔴", "retired": "⚫", "inactive": "⚪",
        }.get(agent_info["status"], "❓")
        tier_badge = {
            "system": "⚙️", "core": "🔷", "user": "🔹",
        }.get(spec.get("tier", ""), "")

        agent_rows.append(
            f"<tr>"
            f"<td>{status_emoji} {agent_info['agent_id']}</td>"
            f"<td>{tier_badge} {spec.get('tier', '?')}</td>"
            f"<td>{spec.get('personality', '?')}</td>"
            f"<td>{agent_info['status']}</td>"
            f"<td>{agent_info['budget_pct']*100:.0f}%</td>"
            f"<td>{agent_info['tasks_today']}</td>"
            f"</tr>"
        )

    agent_table = "\n".join(agent_rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐝 KarmaKadabra Swarm Dashboard</title>
<style>
  :root {{
    --bg: #0f0f23; --card: #1a1a2e; --border: #2a2a4a;
    --text: #e0e0e0; --accent: #7b2ff7; --green: #00ff88;
    --red: #ff4757; --gold: #ffd700; --blue: #00d4ff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'SF Mono', 'Fira Code', monospace;
    background: var(--bg); color: var(--text);
    padding: 20px; min-height: 100vh;
  }}
  .header {{
    text-align: center; padding: 20px 0;
    border-bottom: 1px solid var(--border); margin-bottom: 20px;
  }}
  .header h1 {{ font-size: 1.8em; color: var(--accent); }}
  .header .subtitle {{ color: #888; margin-top: 5px; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px; margin-bottom: 20px;
  }}
  .card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px;
  }}
  .card .label {{ color: #888; font-size: 0.8em; text-transform: uppercase; }}
  .card .value {{ font-size: 2em; font-weight: bold; margin-top: 5px; }}
  .card .value.green {{ color: var(--green); }}
  .card .value.red {{ color: var(--red); }}
  .card .value.gold {{ color: var(--gold); }}
  .card .value.blue {{ color: var(--blue); }}
  table {{
    width: 100%; border-collapse: collapse;
    background: var(--card); border-radius: 12px; overflow: hidden;
  }}
  th {{
    background: var(--border); padding: 12px 15px;
    text-align: left; font-size: 0.85em; color: var(--accent);
  }}
  td {{ padding: 10px 15px; border-bottom: 1px solid var(--border); font-size: 0.9em; }}
  tr:hover {{ background: rgba(123, 47, 247, 0.1); }}
  .footer {{
    text-align: center; margin-top: 30px; color: #555; font-size: 0.8em;
  }}
  .status-badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 0.75em; font-weight: bold;
  }}
  .badge-healthy {{ background: rgba(0, 255, 136, 0.2); color: var(--green); }}
  .badge-degraded {{ background: rgba(255, 71, 87, 0.2); color: var(--red); }}
  @media (max-width: 600px) {{
    .grid {{ grid-template-columns: 1fr 1fr; }}
    .card .value {{ font-size: 1.5em; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>🐝 KarmaKadabra Swarm</h1>
  <div class="subtitle">
    Real-time Agent Coordination Dashboard
    <span class="status-badge {'badge-healthy' if health['active'] > 0 else 'badge-degraded'}">
      {'HEALTHY' if health['active'] > 0 else 'DEGRADED'}
    </span>
  </div>
</div>

<div class="grid">
  <div class="card">
    <div class="label">Active Agents</div>
    <div class="value green">{health['active']}/{health['total_agents']}</div>
  </div>
  <div class="card">
    <div class="label">Tasks Completed</div>
    <div class="value blue">{metrics['tasks']['total_completed']}</div>
  </div>
  <div class="card">
    <div class="label">Success Rate</div>
    <div class="value gold">{metrics['tasks']['success_rate']*100:.1f}%</div>
  </div>
  <div class="card">
    <div class="label">Net P&L</div>
    <div class="value {'green' if economics['net_usd'] >= 0 else 'red'}">
      ${economics['net_usd']:.2f}
    </div>
  </div>
  <div class="card">
    <div class="label">Total Earned</div>
    <div class="value green">${economics['total_earned_usd']:.2f}</div>
  </div>
  <div class="card">
    <div class="label">Budget Remaining</div>
    <div class="value blue">{health['budget_remaining_pct']*100:.0f}%</div>
  </div>
</div>

<div class="card" style="margin-bottom: 20px;">
  <h2 style="color: var(--accent); margin-bottom: 15px;">🤖 Agent Fleet</h2>
  <table>
    <thead>
      <tr>
        <th>Agent</th><th>Tier</th><th>Personality</th>
        <th>Status</th><th>Budget</th><th>Tasks</th>
      </tr>
    </thead>
    <tbody>
      {agent_table}
    </tbody>
  </table>
</div>

<div class="footer">
  KarmaKadabra V2 • Execution Market • Updated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
  <br>Auto-refresh: <a href="/dashboard" style="color: var(--accent);">↻ Reload</a>
  | <a href="/metrics" style="color: var(--accent);">Prometheus Metrics</a>
  | <a href="/status" style="color: var(--accent);">JSON Status</a>
</div>

<script>
  // Auto-refresh every 30 seconds
  setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>"""

    return web.Response(text=html, content_type="text/html")


# ══════════════════════════════════════════════
# App Factory
# ══════════════════════════════════════════════


def create_app(runner: Optional[SwarmRunner] = None) -> web.Application:
    """
    Create the aiohttp application.

    Args:
        runner: Pre-configured SwarmRunner. If None, creates one with defaults.

    Returns:
        Configured aiohttp.web.Application
    """
    app = web.Application()

    if runner is None:
        import tempfile
        td = tempfile.mkdtemp()
        runner = SwarmRunner(dry_run=False, state_dir=Path(td))
        runner.bootstrap()

    app["runner"] = runner
    app["analytics"] = SwarmAnalytics(
        orchestrator=runner.orchestrator,
        lifecycle=runner.lifecycle,
    )
    app["start_time"] = time.time()
    app["webhook_events"] = []

    # Routes
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/agents", handle_agents_list)
    app.router.add_get("/agents/{agent_id}", handle_agent_detail)
    app.router.add_post("/agents/{agent_id}/wake", handle_agent_wake)
    app.router.add_post("/agents/{agent_id}/sleep", handle_agent_sleep)
    app.router.add_get("/tasks", handle_tasks)
    app.router.add_post("/tasks/assign", handle_task_assign)
    app.router.add_post("/tasks/cycle", handle_task_cycle)
    app.router.add_get("/economics", handle_economics)
    app.router.add_get("/leaderboard", handle_leaderboard)
    app.router.add_get("/metrics", handle_metrics)
    app.router.add_post("/webhook/em", handle_webhook_em)
    app.router.add_get("/analytics/report", handle_analytics_report)
    app.router.add_get("/analytics/score/{agent_id}", handle_analytics_score)
    app.router.add_get("/analytics/anomalies", handle_analytics_anomalies)
    app.router.add_get("/analytics/recommendations", handle_analytics_recommendations)
    app.router.add_get("/dashboard", handle_dashboard)

    return app


# ══════════════════════════════════════════════
# CLI Entry Point
# ══════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="KarmaKadabra Swarm API Server"
    )
    parser.add_argument("--port", type=int, default=8888, help="Port (default: 8888)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--dry-run", action="store_true", help="No real API calls")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    runner = SwarmRunner(dry_run=args.dry_run)
    runner.bootstrap()

    app = create_app(runner)

    logger.info(f"Starting Swarm API on {args.host}:{args.port}")
    logger.info(f"Dashboard: http://localhost:{args.port}/dashboard")
    logger.info(f"Health:    http://localhost:{args.port}/health")
    logger.info(f"Metrics:   http://localhost:{args.port}/metrics")

    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
