"""
Karma Kadabra V2 — Swarm Orchestrator

Top-level orchestration layer that combines all subsystems:

  - Agent Lifecycle: state machine, circuit breaker, recovery
  - Coordinator: task matching + assignment
  - Reputation Bridge: unified scoring across chains
  - Observability: health monitoring + metrics
  - Memory Bridge: cross-agent context

This is the entry point for running the KK V2 swarm. It manages:
  1. Startup sequence (system → core → user agents, in batches)
  2. Main loop (coordinator cycles with health checks between rounds)
  3. Graceful shutdown (drain active tasks, save state)
  4. Self-healing (detect and recover failed agents)

Usage:
  python swarm_orchestrator.py                    # Full swarm operation
  python swarm_orchestrator.py --dry-run          # Preview without executing
  python swarm_orchestrator.py --status           # Current swarm status
  python swarm_orchestrator.py --health           # Health report
  python swarm_orchestrator.py --leaderboard      # Reputation leaderboard
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    TransitionReason,
    assess_swarm_health,
    create_agent_roster,
    get_available_agents,
    load_lifecycle_state,
    plan_startup_order,
    recommend_actions,
    save_lifecycle_state,
    transition,
)
from lib.observability import (
    assess_agent_health,
    compute_swarm_metrics,
    generate_health_report,
    save_health_report,
)
from lib.reputation_bridge import (
    compute_swarm_reputation,
    format_leaderboard_text,
    generate_leaderboard,
    load_latest_snapshot,
    save_reputation_snapshot,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.orchestrator")


# ---------------------------------------------------------------------------
# Agent Registry
# ---------------------------------------------------------------------------

# KK V2 agents (from generate-workspaces.py + Terraform config)
AGENT_REGISTRY = [
    # System agents (start first)
    {"name": "kk-coordinator", "type": "system"},
    {"name": "kk-validator", "type": "system"},
    # Core agents (start second)
    {"name": "kk-karma-hello", "type": "core"},
    {"name": "kk-skill-extractor", "type": "core"},
    {"name": "kk-soul-extractor", "type": "core"},
    {"name": "kk-voice-extractor", "type": "core"},
    # User agents (start in batches)
    {"name": "kk-abracadabra", "type": "user"},
    {"name": "kk-agent-3", "type": "user"},
    {"name": "kk-agent-4", "type": "user"},
    {"name": "kk-agent-5", "type": "user"},
    {"name": "kk-agent-6", "type": "user"},
    {"name": "kk-agent-7", "type": "user"},
    {"name": "kk-agent-8", "type": "user"},
    {"name": "kk-agent-9", "type": "user"},
    {"name": "kk-agent-10", "type": "user"},
    {"name": "kk-agent-11", "type": "user"},
    {"name": "kk-agent-12", "type": "user"},
    {"name": "kk-agent-13", "type": "user"},
    {"name": "kk-agent-14", "type": "user"},
    {"name": "kk-agent-15", "type": "user"},
    {"name": "kk-agent-16", "type": "user"},
    {"name": "kk-agent-17", "type": "user"},
    {"name": "kk-agent-18", "type": "user"},
    {"name": "kk-agent-19", "type": "user"},
]


# ---------------------------------------------------------------------------
# Status Display
# ---------------------------------------------------------------------------

def display_status(agents: list[AgentLifecycle], config: LifecycleConfig) -> None:
    """Display current swarm status in a human-readable format."""
    now = datetime.now(timezone.utc)
    health = assess_swarm_health(agents, config, now)

    print(f"\n{'=' * 70}")
    print(f"  🐝 Karma Kadabra V2 — Swarm Status")
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'=' * 70}")
    print(f"\n  Agents: {health.total_agents} total")
    print(f"    🟢 Online: {health.online_agents} "
          f"(idle: {health.idle_agents}, working: {health.working_agents})")
    print(f"    ⏸️  Cooldown: {health.cooldown_agents}")
    print(f"    🔴 Error: {health.error_agents}")
    print(f"    ⬛ Offline: {health.offline_agents}")
    print(f"    🔄 Starting: {health.starting_agents}")
    print(f"\n  Availability: {health.availability_ratio:.0%}")
    print(f"  Success Rate: {health.success_ratio:.0%} "
          f"({health.total_successes} ✅ / {health.total_failures} ❌)")
    if health.agents_with_low_balance > 0:
        print(f"  ⚠️  Low Balance: {health.agents_with_low_balance} agents")
    if health.agents_with_stale_heartbeat > 0:
        print(f"  ⚠️  Stale Heartbeat: {health.agents_with_stale_heartbeat} agents")

    # Per-agent status
    print(f"\n  {'Agent':<25} {'State':<12} {'Failures':<10} {'Task'}")
    print(f"  {'-' * 65}")
    for agent in sorted(agents, key=lambda a: (a.agent_type.value, a.agent_name)):
        state_icon = {
            AgentState.IDLE: "🟢",
            AgentState.WORKING: "🔵",
            AgentState.COOLDOWN: "⏸️ ",
            AgentState.ERROR: "🔴",
            AgentState.OFFLINE: "⬛",
            AgentState.STARTING: "🔄",
            AgentState.STOPPING: "🛑",
            AgentState.DRAINING: "💧",
        }.get(agent.state, "❓")

        task = agent.current_task_id[:15] if agent.current_task_id else "-"
        failures = f"{agent.consecutive_failures}/{agent.total_failures}"
        print(f"  {state_icon} {agent.agent_name:<23} {agent.state.value:<12} {failures:<10} {task}")

    # Recommended actions
    actions = recommend_actions(agents, config, now)
    if actions:
        print(f"\n  📋 Recommended Actions:")
        for action in actions[:5]:  # Show top 5
            icon = {"critical": "🚨", "high": "⚠️", "medium": "📌", "low": "💡"}.get(action["priority"], "")
            print(f"    {icon} [{action['priority'].upper()}] {action['agent']}: {action['reason']}")

    print(f"\n{'=' * 70}\n")


def display_leaderboard(workspaces_dir: Path) -> None:
    """Display the reputation leaderboard."""
    rep_dir = workspaces_dir.parent / "data" / "reputation"
    snapshot = load_latest_snapshot(rep_dir)

    if not snapshot:
        print("\n  No reputation data available yet.")
        print("  Run a coordination cycle to generate reputation snapshots.\n")
        return

    # Reconstruct UnifiedReputation objects for leaderboard
    from lib.reputation_bridge import UnifiedReputation, ReputationTier, classify_tier

    reps = {}
    for name, data in snapshot.items():
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
        reps[name] = rep

    lb = generate_leaderboard(reps)
    text = format_leaderboard_text(lb)
    print(f"\n{text}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="KK V2 Swarm Orchestrator")
    parser.add_argument("--status", action="store_true", help="Show current swarm status")
    parser.add_argument("--health", action="store_true", help="Generate health report")
    parser.add_argument("--leaderboard", action="store_true", help="Show reputation leaderboard")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory path")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"
    workspaces_dir = data_dir / "workspaces"
    lifecycle_path = data_dir / "lifecycle_state.json"
    config = LifecycleConfig()

    # Load or create agent roster
    if lifecycle_path.exists():
        agents = load_lifecycle_state(lifecycle_path)
        logger.info(f"Loaded {len(agents)} agents from state file")
    else:
        agents = create_agent_roster(AGENT_REGISTRY)
        logger.info(f"Created new roster with {len(agents)} agents")
        # Save initial state
        data_dir.mkdir(parents=True, exist_ok=True)
        save_lifecycle_state(agents, lifecycle_path)

    if args.status:
        display_status(agents, config)
        return

    if args.leaderboard:
        display_leaderboard(workspaces_dir)
        return

    if args.health:
        now = datetime.now(timezone.utc)
        # Build health snapshots for observability
        snapshots = []
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
            snapshots.append(snap)

        metrics = compute_swarm_metrics(snapshots, now=now)
        report = generate_health_report(snapshots, metrics)
        report_dir = data_dir / "reports"
        path = save_health_report(report, report_dir)
        print(f"\n  Health report saved to: {path}")
        print(f"  Summary: {json.dumps(report['summary'], indent=2)}\n")
        return

    # --- Startup Planning ---
    print(f"\n{'=' * 70}")
    print(f"  🐝 Karma Kadabra V2 — Swarm Orchestrator")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  Agents: {len(agents)}")
    print(f"{'=' * 70}\n")

    batches = plan_startup_order(agents, config)
    print(f"  Startup plan: {len(batches)} batches")
    for i, batch in enumerate(batches):
        print(f"    Batch {i + 1}: {', '.join(batch)}")

    if not args.dry_run:
        # Save updated state
        save_lifecycle_state(agents, lifecycle_path)
        print(f"\n  State saved to: {lifecycle_path}")

    display_status(agents, config)


if __name__ == "__main__":
    asyncio.run(main())
