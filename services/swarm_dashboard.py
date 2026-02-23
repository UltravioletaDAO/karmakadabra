"""
Karma Kadabra V2 — Swarm Dashboard Generator

Generates comprehensive human-readable and machine-readable status reports
for the KK V2 agent swarm. Combines data from:
  - Agent lifecycle state
  - Reputation snapshots
  - Health reports
  - Performance metrics
  - Balance monitoring

Outputs:
  - Terminal dashboard (rich text)
  - JSON report (for APIs)
  - Markdown report (for Telegram/docs)

Usage:
  python swarm_dashboard.py                    # Terminal dashboard
  python swarm_dashboard.py --json             # JSON output
  python swarm_dashboard.py --markdown         # Markdown output
  python swarm_dashboard.py --telegram         # Send to Telegram (requires integration)
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    assess_swarm_health,
    load_lifecycle_state,
    recommend_actions,
)
from lib.observability import (
    assess_agent_health,
    compute_swarm_metrics,
)
from lib.reputation_bridge import (
    classify_tier,
    generate_leaderboard,
    load_latest_snapshot,
    UnifiedReputation,
)


# ---------------------------------------------------------------------------
# Dashboard Data Collection
# ---------------------------------------------------------------------------

def collect_dashboard_data(data_dir: Path) -> dict:
    """Collect all swarm data into a single dashboard payload."""
    now = datetime.now(timezone.utc)
    config = LifecycleConfig()

    # Load lifecycle state
    lifecycle_path = data_dir / "lifecycle_state.json"
    agents = []
    if lifecycle_path.exists():
        agents = load_lifecycle_state(lifecycle_path)

    # Assess swarm health
    health = assess_swarm_health(agents, config, now) if agents else None

    # Build per-agent health snapshots
    agent_snapshots = []
    for agent in agents:
        snap = assess_agent_health(
            agent_name=agent.agent_name,
            last_heartbeat=agent.last_heartbeat or None,
            active_task_id=agent.current_task_id or None,
            tasks_completed_24h=agent.total_successes,
            tasks_failed_24h=agent.total_failures,
            balance_usdc=agent.usdc_balance,
            balance_eth=agent.eth_balance,
            now=now,
        )
        agent_snapshots.append(snap)

    # Compute swarm metrics
    metrics = compute_swarm_metrics(agent_snapshots, now=now) if agent_snapshots else None

    # Load reputation data
    rep_dir = data_dir / "reputation"
    rep_snapshot = load_latest_snapshot(rep_dir) if rep_dir.exists() else None

    # Build reputation objects
    reputations = {}
    if rep_snapshot:
        for name, data in rep_snapshot.items():
            rep = UnifiedReputation(
                agent_name=name,
                composite_score=data.get("composite_score", 50.0),
                effective_confidence=data.get("confidence", 0.0),
                on_chain_score=data.get("layers", {}).get("on_chain", {}).get("score", 50.0),
                off_chain_score=data.get("layers", {}).get("off_chain", {}).get("score", 50.0),
                transactional_score=data.get("layers", {}).get("transactional", {}).get("score", 50.0),
                sources_available=data.get("sources_available", []),
            )
            rep.tier = classify_tier(rep.composite_score)
            reputations[name] = rep

    # Recommended actions
    actions = recommend_actions(agents, config, now) if agents else []

    return {
        "timestamp": now.isoformat(),
        "agents": agents,
        "health": health,
        "agent_snapshots": agent_snapshots,
        "metrics": metrics,
        "reputations": reputations,
        "actions": actions,
        "config": config,
    }


# ---------------------------------------------------------------------------
# Markdown Dashboard
# ---------------------------------------------------------------------------

def render_markdown(data: dict) -> str:
    """Render dashboard as Markdown (for Telegram, docs, etc.)."""
    lines = []
    now_str = data["timestamp"][:19].replace("T", " ") + " UTC"
    agents = data["agents"]
    health = data["health"]
    reputations = data["reputations"]
    actions = data["actions"]

    lines.append(f"🐝 **KK V2 Swarm Dashboard**")
    lines.append(f"*{now_str}*\n")

    if health:
        # Overview
        lines.append(f"**Fleet Status**")
        lines.append(f"• Total Agents: {health.total_agents}")
        lines.append(f"• 🟢 Online: {health.online_agents} (idle: {health.idle_agents}, working: {health.working_agents})")
        if health.cooldown_agents > 0:
            lines.append(f"• ⏸️ Cooldown: {health.cooldown_agents}")
        if health.error_agents > 0:
            lines.append(f"• 🔴 Error: {health.error_agents}")
        if health.offline_agents > 0:
            lines.append(f"• ⬛ Offline: {health.offline_agents}")
        lines.append(f"• Availability: {health.availability_ratio:.0%}")
        lines.append(f"• Success Rate: {health.success_ratio:.0%}")
        if health.agents_with_low_balance > 0:
            lines.append(f"• ⚠️ Low Balance: {health.agents_with_low_balance}")
        lines.append("")

    # Top agents by reputation
    if reputations:
        lines.append(f"**🏆 Top Agents (Reputation)**")
        sorted_reps = sorted(reputations.values(), key=lambda r: r.composite_score, reverse=True)
        for i, rep in enumerate(sorted_reps[:5]):
            tier_icon = {
                "platinum": "💎",
                "gold": "🥇",
                "silver": "🥈",
                "bronze": "🥉",
                "unranked": "⚪",
            }.get(rep.tier.value if hasattr(rep.tier, 'value') else str(rep.tier), "⚪")
            lines.append(f"  {i+1}. {tier_icon} {rep.agent_name}: {rep.composite_score:.1f}/100")
        lines.append("")

    # Agent status table
    if agents:
        lines.append(f"**Agent States**")
        state_counts = {}
        for agent in agents:
            state = agent.state.value
            state_counts[state] = state_counts.get(state, 0) + 1

        for state, count in sorted(state_counts.items()):
            icon = {
                "idle": "🟢", "working": "🔵", "cooldown": "⏸️",
                "error": "🔴", "offline": "⬛", "starting": "🔄",
                "stopping": "🛑", "draining": "💧",
            }.get(state, "❓")
            lines.append(f"  {icon} {state}: {count}")
        lines.append("")

    # Recommended actions
    if actions:
        lines.append(f"**📋 Actions Needed**")
        for action in actions[:3]:
            icon = {"critical": "🚨", "high": "⚠️", "medium": "📌", "low": "💡"}.get(action["priority"], "")
            lines.append(f"  {icon} {action['agent']}: {action['reason']}")
        lines.append("")

    # Metrics summary
    if data["metrics"]:
        m = data["metrics"]
        lines.append(f"**📊 Metrics**")
        if hasattr(m, 'total_tasks_24h'):
            lines.append(f"• Tasks (24h): {m.total_tasks_24h}")
        if hasattr(m, 'avg_response_time_ms'):
            lines.append(f"• Avg Response: {m.avg_response_time_ms:.0f}ms")
        if hasattr(m, 'total_usdc_balance'):
            lines.append(f"• Total USDC: ${m.total_usdc_balance:.2f}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON Dashboard
# ---------------------------------------------------------------------------

def render_json(data: dict) -> str:
    """Render dashboard as JSON (for APIs, storage)."""
    health = data["health"]
    agents = data["agents"]
    reputations = data["reputations"]
    actions = data["actions"]

    output = {
        "timestamp": data["timestamp"],
        "swarm": {
            "total_agents": health.total_agents if health else 0,
            "online": health.online_agents if health else 0,
            "working": health.working_agents if health else 0,
            "idle": health.idle_agents if health else 0,
            "error": health.error_agents if health else 0,
            "offline": health.offline_agents if health else 0,
            "cooldown": health.cooldown_agents if health else 0,
            "availability": health.availability_ratio if health else 0,
            "success_rate": health.success_ratio if health else 0,
            "low_balance_count": health.agents_with_low_balance if health else 0,
        },
        "agents": [
            {
                "name": a.agent_name,
                "type": a.agent_type.value,
                "state": a.state.value,
                "consecutive_failures": a.consecutive_failures,
                "total_successes": a.total_successes,
                "total_failures": a.total_failures,
                "current_task": a.current_task_id,
                "usdc_balance": a.usdc_balance,
                "eth_balance": a.eth_balance,
            }
            for a in agents
        ],
        "reputation": {
            name: {
                "score": rep.composite_score,
                "confidence": rep.effective_confidence,
                "tier": rep.tier.value if hasattr(rep.tier, 'value') else str(rep.tier),
            }
            for name, rep in reputations.items()
        },
        "actions": actions[:10],
    }

    return json.dumps(output, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Terminal Dashboard
# ---------------------------------------------------------------------------

def render_terminal(data: dict) -> str:
    """Render dashboard for terminal output."""
    lines = []
    now_str = data["timestamp"][:19].replace("T", " ") + " UTC"
    agents = data["agents"]
    health = data["health"]
    reputations = data["reputations"]
    actions = data["actions"]

    lines.append(f"\n{'=' * 72}")
    lines.append(f"  🐝 KARMA KADABRA V2 — SWARM DASHBOARD")
    lines.append(f"  {now_str}")
    lines.append(f"{'=' * 72}")

    if health:
        lines.append(f"\n  ┌─ FLEET STATUS ──────────────────────────────────────┐")
        lines.append(f"  │  Total Agents:   {health.total_agents:<8} Availability: {health.availability_ratio:.0%}       │")
        lines.append(f"  │  🟢 Online:      {health.online_agents:<8} Success Rate: {health.success_ratio:.0%}       │")
        lines.append(f"  │    └ Idle:       {health.idle_agents:<8} Tasks Done:   {health.total_successes:<12}│")
        lines.append(f"  │    └ Working:    {health.working_agents:<8} Tasks Failed: {health.total_failures:<12}│")
        if health.cooldown_agents > 0:
            lines.append(f"  │  ⏸️  Cooldown:   {health.cooldown_agents:<8}                              │")
        if health.error_agents > 0:
            lines.append(f"  │  🔴 Error:      {health.error_agents:<8}                              │")
        if health.offline_agents > 0:
            lines.append(f"  │  ⬛ Offline:    {health.offline_agents:<8}                              │")
        lines.append(f"  └──────────────────────────────────────────────────────┘")

    # Agent grid
    if agents:
        lines.append(f"\n  ┌─ AGENTS ─────────────────────────────────────────────┐")
        lines.append(f"  │  {'Name':<25} {'State':<12} {'F/Total':<10} {'Task':<14}│")
        lines.append(f"  │  {'─' * 53}│")

        for agent in sorted(agents, key=lambda a: (a.agent_type.value, a.agent_name)):
            state_icon = {
                AgentState.IDLE: "🟢",
                AgentState.WORKING: "🔵",
                AgentState.COOLDOWN: "⏸️",
                AgentState.ERROR: "🔴",
                AgentState.OFFLINE: "⬛",
                AgentState.STARTING: "🔄",
                AgentState.STOPPING: "🛑",
                AgentState.DRAINING: "💧",
            }.get(agent.state, "❓")
            task = (agent.current_task_id[:12] + "..") if agent.current_task_id and len(agent.current_task_id) > 12 else (agent.current_task_id or "-")
            fails = f"{agent.consecutive_failures}/{agent.total_failures}"
            lines.append(f"  │  {state_icon} {agent.agent_name:<23} {agent.state.value:<12} {fails:<10} {task:<12}│")

        lines.append(f"  └──────────────────────────────────────────────────────┘")

    # Reputation leaderboard
    if reputations:
        lines.append(f"\n  ┌─ REPUTATION LEADERBOARD ──────────────────────────────┐")
        sorted_reps = sorted(reputations.values(), key=lambda r: r.composite_score, reverse=True)
        for i, rep in enumerate(sorted_reps[:10]):
            tier_icon = {
                "platinum": "💎",
                "gold": "🥇",
                "silver": "🥈",
                "bronze": "🥉",
                "unranked": "⚪",
            }.get(rep.tier.value if hasattr(rep.tier, 'value') else str(rep.tier), "⚪")
            bar_len = int(rep.composite_score / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"  │  {i+1:>2}. {tier_icon} {rep.agent_name:<20} {rep.composite_score:>5.1f} [{bar}]│")
        lines.append(f"  └──────────────────────────────────────────────────────┘")

    # Actions
    if actions:
        lines.append(f"\n  ┌─ RECOMMENDED ACTIONS ──────────────────────────────────┐")
        for action in actions[:5]:
            icon = {"critical": "🚨", "high": "⚠️", "medium": "📌", "low": "💡"}.get(action["priority"], "")
            lines.append(f"  │  {icon} [{action['priority'].upper():<8}] {action['agent']:<16} {action['reason'][:30]}│")
        lines.append(f"  └──────────────────────────────────────────────────────┘")

    lines.append(f"\n{'=' * 72}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="KK V2 Swarm Dashboard")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--markdown", action="store_true", help="Output as Markdown")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory")
    parser.add_argument("--save", type=str, default=None, help="Save report to file")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    data = collect_dashboard_data(data_dir)

    if args.json:
        output = render_json(data)
    elif args.markdown:
        output = render_markdown(data)
    else:
        output = render_terminal(data)

    print(output)

    if args.save:
        Path(args.save).write_text(output, encoding="utf-8")
        print(f"  Saved to: {args.save}")


if __name__ == "__main__":
    main()
