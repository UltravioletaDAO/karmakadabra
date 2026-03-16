#!/usr/bin/env python3
"""
Swarm Runner — Bootstrap and Operate the KarmaKadabra Agent Swarm

The runner is the CLI entry point that ties together:
- LifecycleManager (agent state machine)
- ReputationBridge (EM ↔ ERC-8004 reputation sync)
- SwarmOrchestrator (task routing and economics)

Usage:
    # Show swarm status
    python -m mcp_server.swarm.swarm_runner --status

    # Health check with details
    python -m mcp_server.swarm.swarm_runner --health

    # Show reputation leaderboard
    python -m mcp_server.swarm.swarm_runner --leaderboard

    # Bootstrap the 24-agent roster (dry run)
    python -m mcp_server.swarm.swarm_runner --bootstrap --dry-run

    # Run one coordination cycle (check tasks, assign, monitor)
    python -m mcp_server.swarm.swarm_runner --cycle

    # Full daemon mode (continuous coordination)
    python -m mcp_server.swarm.swarm_runner --daemon --interval 60

    # Economic summary
    python -m mcp_server.swarm.swarm_runner --economics

    # Export state to JSON
    python -m mcp_server.swarm.swarm_runner --export state.json
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server.swarm.lifecycle_manager import (
    LifecycleManager,
    ResourceBudget,
)
from mcp_server.swarm.reputation_bridge import ReputationBridge
from mcp_server.swarm.swarm_orchestrator import SwarmOrchestrator


logger = logging.getLogger("swarm_runner")


# ══════════════════════════════════════════════
# Agent Roster — The 24 KarmaKadabra Agents
# ══════════════════════════════════════════════

KK_ROSTER = [
    # ── System Agents (always on, minimal budget) ──
    {
        "agent_id": "coordinator",
        "wallet": "0xD3868E1eD738CED6945A574a7c769433BeD5d474",  # Platform wallet
        "personality": "orchestrator",
        "skills": ["coordination", "monitoring", "analysis"],
        "specializations": ["research"],
        "model": "anthropic/claude-sonnet-4-20250514",
        "budget": {"max_tokens_per_day": 1_000_000, "max_usd_spend_per_day": 2.00},
        "tier": "system",
    },
    {
        "agent_id": "sentinel",
        "wallet": "0x857fe6150401bFB4641Fe0D2B2621cc3B05543Cd",  # Treasury
        "personality": "guardian",
        "skills": ["monitoring", "security", "automation"],
        "specializations": ["testing"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "system",
    },
    # ── Core Agents (primary workers, moderate budget) ──
    {
        "agent_id": "aurora",
        "personality": "explorer",
        "skills": ["research", "documentation", "analysis", "data_entry"],
        "specializations": ["data_collection", "research"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 500_000, "max_usd_spend_per_day": 0.50},
        "tier": "core",
    },
    {
        "agent_id": "blaze",
        "personality": "creator",
        "skills": ["writing", "creativity", "documentation", "communication"],
        "specializations": ["content_creation"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 500_000, "max_usd_spend_per_day": 0.50},
        "tier": "core",
    },
    {
        "agent_id": "cipher",
        "personality": "auditor",
        "skills": ["code_review", "security", "testing", "automation"],
        "specializations": ["code_review", "testing"],
        "model": "anthropic/claude-sonnet-4-20250514",
        "budget": {"max_tokens_per_day": 500_000, "max_usd_spend_per_day": 0.75},
        "tier": "core",
    },
    {
        "agent_id": "delta",
        "personality": "collector",
        "skills": ["research", "data_entry", "documentation"],
        "specializations": ["data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 300_000, "max_usd_spend_per_day": 0.40},
        "tier": "core",
    },
    {
        "agent_id": "echo",
        "personality": "communicator",
        "skills": ["languages", "communication", "documentation", "writing"],
        "specializations": ["translation", "content_creation"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 400_000, "max_usd_spend_per_day": 0.50},
        "tier": "core",
    },
    {
        "agent_id": "forge",
        "personality": "tester",
        "skills": ["qa_testing", "automation", "documentation", "code_review"],
        "specializations": ["testing", "code_review"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 400_000, "max_usd_spend_per_day": 0.50},
        "tier": "core",
    },
    # ── User Agents (specialized, lower budget) ──
    {
        "agent_id": "glitch",
        "personality": "debugger",
        "skills": ["code_review", "testing", "automation", "security"],
        "specializations": ["code_review"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 300_000, "max_usd_spend_per_day": 0.30},
        "tier": "user",
    },
    {
        "agent_id": "horizon",
        "personality": "strategist",
        "skills": ["research", "analysis", "documentation"],
        "specializations": ["research"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 300_000, "max_usd_spend_per_day": 0.30},
        "tier": "user",
    },
    {
        "agent_id": "iris",
        "personality": "artist",
        "skills": ["design", "creativity", "visual_communication"],
        "specializations": ["design"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "jade",
        "personality": "negotiator",
        "skills": ["communication", "languages", "documentation"],
        "specializations": ["translation"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "kite",
        "personality": "scout",
        "skills": ["research", "data_entry", "field_work"],
        "specializations": ["data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "luna",
        "personality": "dreamer",
        "skills": ["writing", "creativity", "research"],
        "specializations": ["content_creation", "research"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "maven",
        "personality": "expert",
        "skills": ["research", "analysis", "documentation", "data_science"],
        "specializations": ["research", "data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "nexus",
        "personality": "connector",
        "skills": ["communication", "coordination", "documentation"],
        "specializations": ["data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "orbit",
        "personality": "observer",
        "skills": ["monitoring", "research", "analysis"],
        "specializations": ["research"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "pulse",
        "personality": "responder",
        "skills": ["communication", "documentation", "automation"],
        "specializations": ["data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "quartz",
        "personality": "analyst",
        "skills": ["analysis", "data_science", "research", "documentation"],
        "specializations": ["research", "data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "rune",
        "personality": "mystic",
        "skills": ["writing", "creativity", "languages"],
        "specializations": ["content_creation", "translation"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "spark",
        "personality": "inventor",
        "skills": ["automation", "code_review", "testing"],
        "specializations": ["testing"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "terra",
        "personality": "grounded",
        "skills": ["documentation", "field_work", "photography"],
        "specializations": ["data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "unity",
        "personality": "collaborator",
        "skills": ["coordination", "communication", "documentation"],
        "specializations": ["data_collection"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
    {
        "agent_id": "vortex",
        "personality": "chaotic",
        "skills": ["research", "testing", "automation", "creativity"],
        "specializations": ["testing", "research"],
        "model": "anthropic/claude-haiku-4-5",
        "budget": {"max_tokens_per_day": 200_000, "max_usd_spend_per_day": 0.25},
        "tier": "user",
    },
]


# ══════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════


class SwarmRunner:
    """
    CLI runner for the KarmaKadabra swarm.

    Handles:
    - Bootstrap: Initialize all 24 agents
    - Cycle: One coordination pass (check tasks, assign, monitor)
    - Daemon: Continuous operation with configurable interval
    - Status/Health/Leaderboard: Observability commands
    """

    DEFAULT_STATE_DIR = Path.home() / "clawd" / "data" / "swarm"
    EM_API_BASE = "https://api.execution.market"

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        dry_run: bool = False,
        em_api_key: Optional[str] = None,
    ):
        self.state_dir = state_dir or self.DEFAULT_STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.dry_run = dry_run
        self.em_api_key = em_api_key or os.environ.get("EM_API_KEY", "")

        # Core components
        self.lifecycle = LifecycleManager(
            max_agents=48,
            state_file=str(self.state_dir / "lifecycle.json"),
        )
        self.bridge = ReputationBridge(
            network="base",
            dry_run=dry_run,
        )
        self.orchestrator = SwarmOrchestrator(
            lifecycle=self.lifecycle,
            bridge=self.bridge,
        )

        self._running = False
        self._cycle_count = 0

    # ── Bootstrap ──

    def bootstrap(self, tiers: Optional[List[str]] = None) -> dict:
        """
        Bootstrap the agent roster from KK_ROSTER.

        Registers all agents and activates them in tier order:
        1. System agents (coordinator, sentinel)
        2. Core agents (aurora, blaze, cipher, etc.)
        3. User agents (glitch, horizon, etc.)

        Args:
            tiers: Which tiers to bootstrap (default: all)

        Returns:
            Summary of bootstrapped agents
        """
        tiers = tiers or ["system", "core", "user"]
        results = {"registered": [], "activated": [], "skipped": [], "errors": []}

        for tier in tiers:
            tier_agents = [a for a in KK_ROSTER if a.get("tier") == tier]
            logger.info(f"Bootstrapping {len(tier_agents)} {tier} agents...")

            for spec in tier_agents:
                agent_id = spec["agent_id"]

                # Skip already registered
                if agent_id in self.lifecycle.agents:
                    results["skipped"].append(agent_id)
                    continue

                try:
                    # Build budget
                    budget_spec = spec.get("budget", {})
                    budget = ResourceBudget(
                        max_tokens_per_day=budget_spec.get(
                            "max_tokens_per_day", 200_000
                        ),
                        max_usd_spend_per_day=budget_spec.get(
                            "max_usd_spend_per_day", 0.25
                        ),
                    )

                    # Wallet: use spec wallet or generate deterministic one
                    wallet = spec.get(
                        "wallet", f"0x{agent_id}_{hash(agent_id) % 10**8:08x}"
                    )

                    # Register in orchestrator (which registers in lifecycle too)
                    self.orchestrator.register_agent(
                        agent_id=agent_id,
                        wallet=wallet,
                        personality=spec.get("personality", "generalist"),
                        skills=spec.get("skills", []),
                        specializations=spec.get("specializations", []),
                        model=spec.get("model", "anthropic/claude-haiku-4-5"),
                        budget=budget,
                    )
                    results["registered"].append(agent_id)

                    # Activate
                    if not self.dry_run:
                        self.lifecycle.boot_agent(agent_id)
                        self.lifecycle.activate_agent(agent_id)
                        results["activated"].append(agent_id)

                except Exception as e:
                    logger.error(f"Failed to bootstrap {agent_id}: {e}")
                    results["errors"].append({"agent_id": agent_id, "error": str(e)})

        logger.info(
            f"Bootstrap complete: {len(results['registered'])} registered, "
            f"{len(results['activated'])} activated, "
            f"{len(results['skipped'])} skipped, "
            f"{len(results['errors'])} errors"
        )
        return results

    # ── Coordination Cycle ──

    async def cycle(self) -> dict:
        """
        Run one coordination cycle.

        Steps:
        1. Auto-manage lifecycle (wake/sleep/recover agents)
        2. Fetch available tasks from EM API
        3. Assign tasks to best-matching agents
        4. Check for completed tasks
        5. Update reputation scores
        6. Report metrics

        Returns:
            Cycle summary
        """
        self._cycle_count += 1
        cycle_start = time.time()
        summary = {
            "cycle": self._cycle_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lifecycle_actions": {},
            "tasks_fetched": 0,
            "tasks_assigned": 0,
            "errors": [],
        }

        try:
            # Step 1: Auto-manage lifecycle
            actions = self.lifecycle.auto_manage()
            summary["lifecycle_actions"] = actions

            # Step 2: Fetch available tasks
            tasks = await self._fetch_available_tasks()
            summary["tasks_fetched"] = len(tasks)

            # Step 3: Assign tasks
            for task in tasks:
                try:
                    assignment = await self.orchestrator.assign_task(
                        task_id=task.get("id", ""),
                        category=task.get("category", "general"),
                        bounty_usd=float(task.get("bounty", 0)),
                    )
                    if assignment.assigned_agent:
                        summary["tasks_assigned"] += 1
                        logger.info(
                            f"Assigned {task.get('id')} → {assignment.assigned_agent} "
                            f"(score: {assignment.score}%)"
                        )
                except Exception as e:
                    summary["errors"].append(f"Assignment error: {e}")

            # Step 4: Add metrics
            summary["metrics"] = self.orchestrator.metrics()
            summary["health"] = self.lifecycle.health_check()
            summary["cycle_duration_ms"] = int((time.time() - cycle_start) * 1000)

        except Exception as e:
            summary["errors"].append(f"Cycle error: {e}")
            logger.error(f"Cycle {self._cycle_count} failed: {e}")

        return summary

    async def daemon(self, interval_seconds: int = 60, max_cycles: int = 0):
        """
        Run continuous coordination daemon.

        Args:
            interval_seconds: Seconds between cycles
            max_cycles: Max cycles (0 = unlimited)
        """
        self._running = True
        logger.info(
            f"Starting swarm daemon (interval={interval_seconds}s, "
            f"max_cycles={'unlimited' if max_cycles == 0 else max_cycles})"
        )

        # Set up signal handlers
        def handle_signal(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        cycle_num = 0
        while self._running:
            cycle_num += 1
            if max_cycles > 0 and cycle_num > max_cycles:
                logger.info(f"Max cycles ({max_cycles}) reached, stopping")
                break

            try:
                summary = await self.cycle()
                self._print_cycle_summary(summary)
            except Exception as e:
                logger.error(f"Daemon cycle {cycle_num} error: {e}")

            if self._running:
                await asyncio.sleep(interval_seconds)

        logger.info("Swarm daemon stopped")

    # ── Observability Commands ──

    def show_status(self) -> str:
        """Show swarm status as formatted text."""
        health = self.lifecycle.health_check()
        metrics = self.orchestrator.metrics()

        lines = [
            "╔══════════════════════════════════════╗",
            "║     🐝 KarmaKadabra Swarm Status     ║",
            "╠══════════════════════════════════════╣",
            f"║  Agents: {health['total_agents']:>3} total                   ║",
            f"║    ✅ Active:   {health['active']:>3}                   ║",
            f"║    😴 Sleeping: {health['sleeping']:>3}                   ║",
            f"║    ❌ Error:    {health['error']:>3}                   ║",
            f"║    🪦 Retired:  {health['retired']:>3}                   ║",
            "╠══════════════════════════════════════╣",
            f"║  Tasks Assigned: {metrics['tasks']['total_assigned']:>6}             ║",
            f"║  Tasks Done:     {metrics['tasks']['total_completed']:>6}             ║",
            f"║  Active Tasks:   {metrics['tasks']['active']:>6}             ║",
            f"║  Success Rate:   {metrics['tasks']['success_rate'] * 100:>5.1f}%            ║",
            "╠══════════════════════════════════════╣",
            f"║  💰 Earned: ${metrics['economics']['total_earned_usd']:>8.2f}            ║",
            f"║  💸 Spent:  ${metrics['economics']['total_spent_usd']:>8.2f}            ║",
            f"║  📊 Net:    ${metrics['economics']['net_usd']:>8.2f}            ║",
            "╚══════════════════════════════════════╝",
        ]
        return "\n".join(lines)

    def show_health(self) -> str:
        """Show detailed agent health."""
        health = self.lifecycle.health_check()
        lines = [
            "🏥 Agent Health Report",
            f"   Total: {health['total_agents']} | "
            f"Active: {health['active']} | "
            f"Healthy: {health['healthy']} | "
            f"Budget: {health['budget_remaining_pct'] * 100:.0f}% remaining",
            "",
            "   Agent          Status     Healthy  Budget%  Tasks",
            "   " + "─" * 55,
        ]

        for agent in sorted(health["agents"], key=lambda a: a["status"]):
            status_emoji = {
                "active": "✅",
                "sleeping": "😴",
                "booting": "🔄",
                "waking": "🌅",
                "error": "❌",
                "retired": "🪦",
                "inactive": "⬜",
            }.get(agent["status"], "❓")

            lines.append(
                f"   {status_emoji} {agent['agent_id']:<12s} "
                f"{agent['status']:<10s} "
                f"{'yes' if agent['healthy'] else 'no':>7s} "
                f"{agent['budget_pct'] * 100:>6.1f}% "
                f"{agent['tasks_today']:>5d}"
            )

        return "\n".join(lines)

    async def show_leaderboard(self) -> str:
        """Show reputation leaderboard."""
        lines = [
            "🏆 Reputation Leaderboard",
            "",
            "   Rank  Agent          Score  Confidence  Tier        Evidence",
            "   " + "─" * 65,
        ]

        # Get bridged reputation for all agents
        reps = []
        for agent_id, profile in self.orchestrator.profiles.items():
            rep = await self.bridge.get_bridged_reputation(profile.wallet)
            reps.append((agent_id, rep))

        # Sort by composite score
        reps.sort(key=lambda x: -x[1].composite_score)

        tier_emoji = {
            "elite": "💎",
            "trusted": "🥇",
            "established": "🥈",
            "new": "🥉",
            "at_risk": "⚠️",
        }

        for rank, (agent_id, rep) in enumerate(reps, 1):
            emoji = tier_emoji.get(rep.tier, "❓")
            lines.append(
                f"   {rank:>3d}.  {agent_id:<12s} "
                f"{rep.composite_score:>5.1f}  "
                f"{rep.confidence:>10.3f}  "
                f"{emoji} {rep.tier:<10s} "
                f"{rep.evidence_weight:.2f}"
            )

        return "\n".join(lines)

    def show_economics(self) -> str:
        """Show economic summary."""
        summary = self.orchestrator.economic_summary()
        lines = [
            "💰 Swarm Economics",
            "",
            f"   Total Tasks Assigned:  {summary['total_assigned']}",
            f"   Total Tasks Completed: {summary['total_completed']}",
            f"   Completion Rate:       {summary['completion_rate'] * 100:.1f}%",
            f"   Avg Earnings/Task:     ${summary['avg_earnings_per_task']:.4f}",
            "",
            f"   Total Earned: ${summary['total_earned_usd']:.2f}",
            f"   Total Spent:  ${summary['total_spent_usd']:.2f}",
            f"   Net P&L:      ${summary['net_usd']:.2f}",
            "",
            "   Fleet: "
            f"{summary['fleet_health']['active']}/{summary['fleet_health']['total']} active, "
            f"{summary['fleet_health']['budget_remaining_pct'] * 100:.0f}% budget remaining",
        ]

        if summary["top_earners"]:
            lines.append("")
            lines.append("   🏆 Top Earners:")
            for i, earner in enumerate(summary["top_earners"], 1):
                lines.append(
                    f"      {i}. {earner['agent_id']}: ${earner['earned_usd']:.2f}"
                )

        return "\n".join(lines)

    def export_state(self, path: str):
        """Export complete swarm state to JSON."""
        state = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "2.0",
            "lifecycle": {},
            "profiles": {},
            "economics": self.orchestrator.economic_summary(),
            "metrics": self.orchestrator.metrics(),
        }

        for agent_id, agent in self.lifecycle.agents.items():
            state["lifecycle"][agent_id] = agent.to_dict()

        for agent_id, profile in self.orchestrator.profiles.items():
            state["profiles"][agent_id] = {
                "agent_id": profile.agent_id,
                "wallet": profile.wallet,
                "personality": profile.personality,
                "skills": profile.skills,
                "specializations": profile.specializations,
                "reputation_score": profile.reputation_score,
                "availability_score": profile.availability_score,
            }

        with open(path, "w") as f:
            json.dump(state, f, indent=2, default=str)

        logger.info(f"State exported to {path}")

    # ── Private ──

    async def _fetch_available_tasks(self) -> List[dict]:
        """
        Fetch available tasks from EM API.

        In dry_run mode, returns mock tasks.
        """
        if self.dry_run:
            return [
                {
                    "id": f"mock_task_{int(time.time())}",
                    "category": "data_collection",
                    "bounty": "0.10",
                    "title": "Mock data collection task",
                },
            ]

        try:
            import urllib.request
            import urllib.error

            url = f"{self.EM_API_BASE}/api/v1/tasks?status=published&limit=10"
            headers = {}
            if self.em_api_key:
                headers["Authorization"] = f"Bearer {self.em_api_key}"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            # Handle both list and dict responses
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("tasks", data.get("data", []))
            return []

        except Exception as e:
            logger.warning(f"Failed to fetch tasks from EM API: {e}")
            return []

    def _print_cycle_summary(self, summary: dict):
        """Print a one-line cycle summary."""
        health = summary.get("health", {})
        print(
            f"[Cycle {summary.get('cycle', 0)}] "
            f"Fetched: {summary.get('tasks_fetched', 0)} | "
            f"Assigned: {summary.get('tasks_assigned', 0)} | "
            f"Active: {health.get('active', 0)}/{health.get('total_agents', 0)} | "
            f"Duration: {summary.get('cycle_duration_ms', 0)}ms"
        )


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════


def parse_args():
    parser = argparse.ArgumentParser(
        description="KarmaKadabra Swarm Runner — Coordinate AI Agent Swarms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status                    Show swarm status
  %(prog)s --health                    Detailed agent health
  %(prog)s --bootstrap --dry-run       Bootstrap roster (dry run)
  %(prog)s --cycle                     Run one coordination cycle
  %(prog)s --daemon --interval 60      Continuous daemon mode
  %(prog)s --economics                 Economic summary
  %(prog)s --leaderboard               Reputation rankings
  %(prog)s --export state.json         Export state to file
        """,
    )

    # Commands
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Show swarm status")
    group.add_argument("--health", action="store_true", help="Show agent health")
    group.add_argument(
        "--bootstrap", action="store_true", help="Bootstrap agent roster"
    )
    group.add_argument(
        "--cycle", action="store_true", help="Run one coordination cycle"
    )
    group.add_argument("--daemon", action="store_true", help="Run continuous daemon")
    group.add_argument("--economics", action="store_true", help="Show economic summary")
    group.add_argument(
        "--leaderboard", action="store_true", help="Show reputation leaderboard"
    )
    group.add_argument("--export", metavar="FILE", help="Export state to JSON file")

    # Options
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't make real API calls"
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="Daemon cycle interval (seconds)"
    )
    parser.add_argument(
        "--max-cycles", type=int, default=0, help="Max daemon cycles (0=unlimited)"
    )
    parser.add_argument("--state-dir", type=str, help="State directory path")
    parser.add_argument(
        "--tiers",
        nargs="+",
        choices=["system", "core", "user"],
        help="Which agent tiers to bootstrap",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    return parser.parse_args()


async def main():
    args = parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Initialize runner
    state_dir = Path(args.state_dir) if args.state_dir else None
    runner = SwarmRunner(
        state_dir=state_dir,
        dry_run=args.dry_run,
    )

    # Always bootstrap if no agents loaded
    if not runner.lifecycle.agents:
        runner.bootstrap(tiers=args.tiers)

    # Execute command
    if args.status:
        print(runner.show_status())

    elif args.health:
        print(runner.show_health())

    elif args.bootstrap:
        result = runner.bootstrap(tiers=args.tiers)
        print(f"✅ Registered: {len(result['registered'])}")
        print(f"⚡ Activated:  {len(result['activated'])}")
        print(f"⏭️  Skipped:    {len(result['skipped'])}")
        if result["errors"]:
            print(f"❌ Errors:     {len(result['errors'])}")
            for err in result["errors"]:
                print(f"   - {err['agent_id']}: {err['error']}")

    elif args.cycle:
        summary = await runner.cycle()
        print(json.dumps(summary, indent=2, default=str))

    elif args.daemon:
        await runner.daemon(
            interval_seconds=args.interval,
            max_cycles=args.max_cycles,
        )

    elif args.economics:
        print(runner.show_economics())

    elif args.leaderboard:
        print(await runner.show_leaderboard())

    elif args.export:
        runner.export_state(args.export)
        print(f"✅ State exported to {args.export}")


if __name__ == "__main__":
    asyncio.run(main())
