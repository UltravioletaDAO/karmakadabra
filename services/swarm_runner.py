"""
Karma Kadabra V2 — Swarm Runner (Production Daemon)

The operational entry point that ties the entire swarm into a running system.
This is what you deploy — it orchestrates all the pieces:

    Coordinator (assigns) → Task Executor (executes) → Evidence Processor (learns)
         ↓                                                      ↓
    Health Monitor                                      Performance Profiles
         ↓                                                      ↓
    Alerts + Dashboard                              Better Matching (flywheel)

Modes:
    daemon    — Run continuously with configurable cycle intervals
    cycle     — Run one coordination cycle and exit
    health    — Run ecosystem health check and exit
    evidence  — Process pending evidence and exit
    status    — Show swarm operational status and exit

Features:
    - Configurable cycle intervals (default: 5 min coordination, 10 min evidence)
    - Graceful shutdown on SIGINT/SIGTERM
    - State persistence between restarts
    - Health check integration with alerting
    - Operational metrics tracking
    - Dry-run mode for all operations

Usage:
    # Production daemon
    python swarm_runner.py daemon --workspaces ./workspaces

    # Single coordination cycle
    python swarm_runner.py cycle --workspaces ./workspaces --dry-run

    # Health check
    python swarm_runner.py health --json

    # Process evidence
    python swarm_runner.py evidence --workspaces ./workspaces

    # Operational status
    python swarm_runner.py status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from em_client import AgentContext, EMClient, load_agent_context

logger = logging.getLogger("kk.runner")


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════


@dataclass
class RunnerConfig:
    """Swarm Runner configuration."""

    # Paths
    workspaces_dir: str = "./workspaces"
    state_file: str = "./runner_state.json"
    log_file: Optional[str] = None

    # Cycle intervals (seconds)
    coordination_interval: int = 300      # 5 minutes
    evidence_interval: int = 600          # 10 minutes
    health_interval: int = 1800           # 30 minutes
    metrics_interval: int = 60            # 1 minute (lightweight)

    # Behavior
    dry_run: bool = False
    max_tasks_per_cycle: int = 10
    max_assignments_per_cycle: int = 5
    health_alert_threshold: float = 0.5   # Alert if <50% healthy
    auto_pause_on_errors: int = 3         # Pause after N consecutive errors

    # API
    em_api_url: str = "https://api.execution.market"
    em_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "RunnerConfig":
        """Load config from environment variables."""
        return cls(
            workspaces_dir=os.getenv("KK_WORKSPACES", "./workspaces"),
            state_file=os.getenv("KK_STATE_FILE", "./runner_state.json"),
            log_file=os.getenv("KK_LOG_FILE"),
            coordination_interval=int(os.getenv("KK_COORD_INTERVAL", "300")),
            evidence_interval=int(os.getenv("KK_EVIDENCE_INTERVAL", "600")),
            health_interval=int(os.getenv("KK_HEALTH_INTERVAL", "1800")),
            dry_run=os.getenv("KK_DRY_RUN", "").lower() in ("1", "true", "yes"),
            max_tasks_per_cycle=int(os.getenv("KK_MAX_TASKS", "10")),
            max_assignments_per_cycle=int(os.getenv("KK_MAX_ASSIGN", "5")),
            em_api_url=os.getenv("EM_API_URL", "https://api.execution.market"),
            em_api_key=os.getenv("EM_API_KEY"),
        )

    @classmethod
    def from_file(cls, path: str) -> "RunnerConfig":
        """Load config from JSON file."""
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text())
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════════
# Operational Metrics
# ═══════════════════════════════════════════════════════════════════


@dataclass
class CycleMetrics:
    """Metrics for a single cycle."""

    cycle_type: str  # "coordination", "evidence", "health"
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: int = 0
    success: bool = False
    error: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class RunnerMetrics:
    """Aggregate operational metrics."""

    started_at: float = 0.0
    total_coordination_cycles: int = 0
    total_evidence_cycles: int = 0
    total_health_checks: int = 0
    total_tasks_assigned: int = 0
    total_tasks_executed: int = 0
    total_evidence_processed: int = 0
    total_errors: int = 0
    consecutive_errors: int = 0
    paused: bool = False
    pause_reason: Optional[str] = None
    last_coordination: float = 0.0
    last_evidence: float = 0.0
    last_health: float = 0.0
    cycle_history: list = field(default_factory=list)

    def record_cycle(self, metrics: CycleMetrics) -> None:
        """Record a cycle's metrics."""
        if metrics.success:
            self.consecutive_errors = 0
        else:
            self.consecutive_errors += 1
            self.total_errors += 1

        self.cycle_history.append({
            "type": metrics.cycle_type,
            "started": metrics.started_at,
            "duration_ms": metrics.duration_ms,
            "success": metrics.success,
            "error": metrics.error,
            "details": metrics.details,
        })

        # Keep last 100 cycles
        if len(self.cycle_history) > 100:
            self.cycle_history = self.cycle_history[-100:]

    def uptime_seconds(self) -> float:
        """How long the runner has been running."""
        if self.started_at == 0:
            return 0.0
        return time.time() - self.started_at

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "started_at": self.started_at,
            "uptime_s": round(self.uptime_seconds()),
            "coordination_cycles": self.total_coordination_cycles,
            "evidence_cycles": self.total_evidence_cycles,
            "health_checks": self.total_health_checks,
            "tasks_assigned": self.total_tasks_assigned,
            "tasks_executed": self.total_tasks_executed,
            "evidence_processed": self.total_evidence_processed,
            "total_errors": self.total_errors,
            "consecutive_errors": self.consecutive_errors,
            "paused": self.paused,
            "pause_reason": self.pause_reason,
            "last_coordination": self.last_coordination,
            "last_evidence": self.last_evidence,
            "last_health": self.last_health,
        }


# ═══════════════════════════════════════════════════════════════════
# Runner State (persistent across restarts)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class RunnerState:
    """Persistent state that survives restarts."""

    last_coordination_at: float = 0.0
    last_evidence_at: float = 0.0
    last_health_at: float = 0.0
    last_evidence_cursor: Optional[str] = None
    total_lifetime_cycles: int = 0
    total_lifetime_assignments: int = 0
    total_lifetime_executions: int = 0
    errors_since_clean_restart: int = 0
    version: str = "1.0.0"

    @classmethod
    def load(cls, path: str) -> "RunnerState":
        """Load state from disk."""
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupted state file, starting fresh")
            return cls()

    def save(self, path: str) -> None:
        """Persist state to disk."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {k: getattr(self, k) for k in self.__dataclass_fields__}
        p.write_text(json.dumps(data, indent=2) + "\n")

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# ═══════════════════════════════════════════════════════════════════
# Swarm Runner
# ═══════════════════════════════════════════════════════════════════


class SwarmRunner:
    """
    The production daemon that operates the KK V2 swarm.

    Orchestrates:
      - Coordination cycles (assign tasks to agents)
      - Evidence processing (learn from completions)
      - Health monitoring (alert on problems)
      - Metrics tracking (operational visibility)
    """

    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig()
        self.metrics = RunnerMetrics()
        self.state = RunnerState.load(self.config.state_file)
        self._shutdown = False
        self._em_client: Optional[EMClient] = None

    # ─── Lifecycle ───────────────────────────────────────────────

    def setup_signals(self) -> None:
        """Register signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle shutdown signal."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self._shutdown = True

    def _get_em_client(self) -> EMClient:
        """Get or create the EM API client."""
        if self._em_client is None:
            ctx = AgentContext(
                agent_name="coordinator",
                api_key=self.config.em_api_key or "",
                api_url=self.config.em_api_url,
            )
            self._em_client = EMClient(ctx)
        return self._em_client

    # ─── Coordination Cycle ──────────────────────────────────────

    async def run_coordination_cycle(self) -> CycleMetrics:
        """
        Run one coordination cycle:
        1. Fetch available tasks from EM
        2. Load agent states
        3. Match tasks to agents
        4. Assign tasks
        5. Update state
        """
        metrics = CycleMetrics(cycle_type="coordination", started_at=time.time())

        try:
            # Import coordinator components
            from coordinator_service import (
                CoordinatorService,
                load_coordinator_config,
            )

            workspaces = Path(self.config.workspaces_dir)
            if not workspaces.exists():
                raise FileNotFoundError(f"Workspaces directory not found: {workspaces}")

            # Initialize coordinator
            coordinator = CoordinatorService(
                workspaces_dir=str(workspaces),
                em_client=self._get_em_client(),
                dry_run=self.config.dry_run,
                max_assignments=self.config.max_assignments_per_cycle,
            )

            # Run coordination
            result = await coordinator.run_cycle()

            # Extract results
            tasks_found = result.get("tasks_found", 0)
            tasks_assigned = result.get("tasks_assigned", 0)
            agents_active = result.get("agents_active", 0)
            agents_idle = result.get("agents_idle", 0)

            metrics.details = {
                "tasks_found": tasks_found,
                "tasks_assigned": tasks_assigned,
                "agents_active": agents_active,
                "agents_idle": agents_idle,
            }
            metrics.success = True

            self.metrics.total_coordination_cycles += 1
            self.metrics.total_tasks_assigned += tasks_assigned
            self.metrics.last_coordination = time.time()
            self.state.last_coordination_at = time.time()
            self.state.total_lifetime_cycles += 1
            self.state.total_lifetime_assignments += tasks_assigned

            if tasks_assigned > 0:
                logger.info(
                    f"Coordination: {tasks_assigned}/{tasks_found} tasks assigned "
                    f"to {agents_idle} idle agents"
                )
            else:
                logger.debug(f"Coordination: no assignments ({tasks_found} tasks, {agents_idle} idle)")

        except ImportError:
            # CoordinatorService not fully wired — use standalone coordination
            metrics = await self._standalone_coordination(metrics)
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            logger.error(f"Coordination error: {e}")

        metrics.finished_at = time.time()
        metrics.duration_ms = int((metrics.finished_at - metrics.started_at) * 1000)
        self.metrics.record_cycle(metrics)
        return metrics

    async def _standalone_coordination(self, metrics: CycleMetrics) -> CycleMetrics:
        """
        Standalone coordination when CoordinatorService isn't available.
        Uses the swarm_state and em_client directly.
        """
        try:
            from lib.swarm_state import get_agent_states, get_swarm_summary

            workspaces = Path(self.config.workspaces_dir)
            if not workspaces.exists():
                metrics.details = {"status": "no_workspaces"}
                metrics.success = True
                return metrics

            # Get agent states
            states = get_agent_states(str(workspaces))
            idle = [s for s in states if s.get("status") == "idle"]
            busy = [s for s in states if s.get("status") == "busy"]

            # Fetch tasks from EM
            client = self._get_em_client()
            tasks_resp = await client.list_tasks(status="published", limit=self.config.max_tasks_per_cycle)
            tasks = tasks_resp if isinstance(tasks_resp, list) else tasks_resp.get("tasks", [])

            metrics.details = {
                "tasks_found": len(tasks),
                "tasks_assigned": 0,  # Standalone doesn't assign
                "agents_total": len(states),
                "agents_idle": len(idle),
                "agents_busy": len(busy),
                "mode": "standalone",
            }
            metrics.success = True

            self.metrics.total_coordination_cycles += 1
            self.metrics.last_coordination = time.time()
            self.state.last_coordination_at = time.time()

        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            logger.error(f"Standalone coordination error: {e}")

        return metrics

    # ─── Evidence Processing Cycle ───────────────────────────────

    async def run_evidence_cycle(self) -> CycleMetrics:
        """
        Process evidence from completed tasks:
        1. Fetch recent completions from EM
        2. Match to KK agents
        3. Extract performance signals
        4. Update agent profiles
        """
        metrics = CycleMetrics(cycle_type="evidence", started_at=time.time())

        try:
            from evidence_processor import EvidenceProcessor

            workspaces = Path(self.config.workspaces_dir)
            processor = EvidenceProcessor(str(workspaces))

            # Process recent completions
            client = self._get_em_client()
            summary = await processor.process_recent_completions(
                client,
                cursor=self.state.last_evidence_cursor,
            )

            processed = summary.get("processed", 0)
            approved = summary.get("approved", 0)
            rejected = summary.get("rejected", 0)
            new_cursor = summary.get("cursor")

            if new_cursor:
                self.state.last_evidence_cursor = new_cursor

            metrics.details = {
                "processed": processed,
                "approved": approved,
                "rejected": rejected,
                "cursor_advanced": new_cursor is not None,
            }
            metrics.success = True

            self.metrics.total_evidence_cycles += 1
            self.metrics.total_evidence_processed += processed
            self.metrics.last_evidence = time.time()
            self.state.last_evidence_at = time.time()

            if processed > 0:
                logger.info(
                    f"Evidence: processed {processed} completions "
                    f"({approved} approved, {rejected} rejected)"
                )
            else:
                logger.debug("Evidence: no new completions to process")

        except ImportError:
            metrics.details = {"status": "evidence_processor_not_available"}
            metrics.success = True  # Not a failure, just not wired yet
            self.metrics.total_evidence_cycles += 1
            self.metrics.last_evidence = time.time()
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            logger.error(f"Evidence processing error: {e}")

        metrics.finished_at = time.time()
        metrics.duration_ms = int((metrics.finished_at - metrics.started_at) * 1000)
        self.metrics.record_cycle(metrics)
        return metrics

    # ─── Health Check Cycle ──────────────────────────────────────

    async def run_health_check(self) -> CycleMetrics:
        """
        Run ecosystem health check:
        1. EM API health
        2. Agent wallet balances
        3. Swarm component status
        4. Alert on issues
        """
        metrics = CycleMetrics(cycle_type="health", started_at=time.time())

        try:
            from monitoring.ecosystem_dashboard import SwarmHealthDashboard

            dashboard = SwarmHealthDashboard()
            report = dashboard.generate_report()

            overall = report.get("overall_status", "unknown")
            components = report.get("components", {})
            healthy_count = sum(
                1 for c in components.values()
                if isinstance(c, dict) and c.get("status") == "healthy"
            )
            total_count = len(components) if components else 1

            health_ratio = healthy_count / total_count if total_count > 0 else 0.0

            metrics.details = {
                "overall": overall,
                "healthy_components": healthy_count,
                "total_components": total_count,
                "health_ratio": round(health_ratio, 2),
            }
            metrics.success = True

            # Alert if health is below threshold
            if health_ratio < self.config.health_alert_threshold:
                logger.warning(
                    f"⚠️ Health degraded: {healthy_count}/{total_count} components healthy "
                    f"(threshold: {self.config.health_alert_threshold})"
                )

            self.metrics.total_health_checks += 1
            self.metrics.last_health = time.time()
            self.state.last_health_at = time.time()

        except ImportError:
            # Health dashboard not available — do basic EM check
            metrics = await self._basic_health_check(metrics)
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            logger.error(f"Health check error: {e}")

        metrics.finished_at = time.time()
        metrics.duration_ms = int((metrics.finished_at - metrics.started_at) * 1000)
        self.metrics.record_cycle(metrics)
        return metrics

    async def _basic_health_check(self, metrics: CycleMetrics) -> CycleMetrics:
        """Basic health check when full dashboard isn't available."""
        try:
            import urllib.request

            url = f"{self.config.em_api_url}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                status = data.get("status", "unknown")

            metrics.details = {
                "em_api": status,
                "mode": "basic",
            }
            metrics.success = status in ("healthy", "ok")

            self.metrics.total_health_checks += 1
            self.metrics.last_health = time.time()
            self.state.last_health_at = time.time()

        except Exception as e:
            metrics.success = False
            metrics.error = f"EM API unreachable: {e}"
            logger.error(f"Basic health check failed: {e}")

        return metrics

    # ─── Daemon Mode ─────────────────────────────────────────────

    async def run_daemon(self) -> None:
        """
        Run the swarm continuously until shutdown signal.

        Interleaves coordination, evidence, and health cycles based on
        their configured intervals.
        """
        self.setup_signals()
        self.metrics.started_at = time.time()

        logger.info("=" * 60)
        logger.info("🐝 KK V2 Swarm Runner starting...")
        logger.info(f"  Workspaces:  {self.config.workspaces_dir}")
        logger.info(f"  Coordination: every {self.config.coordination_interval}s")
        logger.info(f"  Evidence:     every {self.config.evidence_interval}s")
        logger.info(f"  Health:       every {self.config.health_interval}s")
        logger.info(f"  Dry run:      {self.config.dry_run}")
        logger.info(f"  State file:   {self.config.state_file}")
        logger.info("=" * 60)

        # Run initial health check
        health = await self.run_health_check()
        if health.success:
            logger.info(f"✅ Initial health: {health.details.get('overall', 'ok')}")
        else:
            logger.warning(f"⚠️ Initial health check failed: {health.error}")

        while not self._shutdown:
            now = time.time()

            # Check auto-pause
            if self.metrics.consecutive_errors >= self.config.auto_pause_on_errors:
                if not self.metrics.paused:
                    self.metrics.paused = True
                    self.metrics.pause_reason = (
                        f"Auto-paused after {self.metrics.consecutive_errors} "
                        f"consecutive errors"
                    )
                    logger.error(f"🛑 {self.metrics.pause_reason}")
                    # Save state before pausing
                    self.state.save(self.config.state_file)

                # Wait but check for shutdown
                await asyncio.sleep(min(60, self.config.coordination_interval))
                continue

            # Run coordination if interval elapsed
            time_since_coord = now - self.metrics.last_coordination
            if time_since_coord >= self.config.coordination_interval:
                await self.run_coordination_cycle()

            # Run evidence processing if interval elapsed
            time_since_evidence = now - self.metrics.last_evidence
            if time_since_evidence >= self.config.evidence_interval:
                await self.run_evidence_cycle()

            # Run health check if interval elapsed
            time_since_health = now - self.metrics.last_health
            if time_since_health >= self.config.health_interval:
                await self.run_health_check()

            # Save state periodically
            if int(now) % 300 == 0:  # Every ~5 minutes
                self.state.save(self.config.state_file)

            # Sleep until next action needed
            next_coord = self.config.coordination_interval - (now - self.metrics.last_coordination)
            next_evidence = self.config.evidence_interval - (now - self.metrics.last_evidence)
            next_health = self.config.health_interval - (now - self.metrics.last_health)
            sleep_time = max(1, min(next_coord, next_evidence, next_health, 30))

            await asyncio.sleep(sleep_time)

        # Graceful shutdown
        logger.info("Shutting down...")
        self.state.save(self.config.state_file)
        logger.info(
            f"🐝 Runner stopped. Ran {self.metrics.total_coordination_cycles} coordination "
            f"+ {self.metrics.total_evidence_cycles} evidence cycles. "
            f"{self.metrics.total_tasks_assigned} tasks assigned."
        )

    # ─── Single-Shot Modes ───────────────────────────────────────

    async def run_single_cycle(self) -> dict:
        """Run one coordination cycle and return results."""
        result = await self.run_coordination_cycle()
        self.state.save(self.config.state_file)
        return {
            "success": result.success,
            "duration_ms": result.duration_ms,
            **result.details,
        }

    async def run_single_evidence(self) -> dict:
        """Process evidence once and return results."""
        result = await self.run_evidence_cycle()
        self.state.save(self.config.state_file)
        return {
            "success": result.success,
            "duration_ms": result.duration_ms,
            **result.details,
        }

    async def run_single_health(self) -> dict:
        """Run health check once and return results."""
        result = await self.run_health_check()
        return {
            "success": result.success,
            "duration_ms": result.duration_ms,
            **result.details,
        }

    # ─── Status & Reporting ──────────────────────────────────────

    def get_status(self) -> dict:
        """Get comprehensive operational status."""
        state = RunnerState.load(self.config.state_file)

        # Format timestamps
        def fmt_time(ts: float) -> str:
            if ts == 0:
                return "never"
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        def ago(ts: float) -> str:
            if ts == 0:
                return ""
            delta = time.time() - ts
            if delta < 60:
                return f" ({int(delta)}s ago)"
            elif delta < 3600:
                return f" ({int(delta/60)}m ago)"
            elif delta < 86400:
                return f" ({int(delta/3600)}h ago)"
            else:
                return f" ({int(delta/86400)}d ago)"

        return {
            "state": {
                "last_coordination": fmt_time(state.last_coordination_at) + ago(state.last_coordination_at),
                "last_evidence": fmt_time(state.last_evidence_at) + ago(state.last_evidence_at),
                "last_health": fmt_time(state.last_health_at) + ago(state.last_health_at),
                "evidence_cursor": state.last_evidence_cursor,
                "lifetime_cycles": state.total_lifetime_cycles,
                "lifetime_assignments": state.total_lifetime_assignments,
                "lifetime_executions": state.total_lifetime_executions,
            },
            "config": {
                "workspaces": self.config.workspaces_dir,
                "coordination_interval_s": self.config.coordination_interval,
                "evidence_interval_s": self.config.evidence_interval,
                "health_interval_s": self.config.health_interval,
                "dry_run": self.config.dry_run,
                "em_api": self.config.em_api_url,
            },
        }

    def format_status(self) -> str:
        """Format status as human-readable text."""
        status = self.get_status()
        state = status["state"]
        config = status["config"]

        lines = [
            "═══════════════════════════════════════════════════",
            "  🐝  KK V2 Swarm Runner — Operational Status",
            "═══════════════════════════════════════════════════",
            "",
            "  State:",
            f"    Last Coordination: {state['last_coordination']}",
            f"    Last Evidence:     {state['last_evidence']}",
            f"    Last Health:       {state['last_health']}",
            f"    Evidence Cursor:   {state['evidence_cursor'] or 'none'}",
            "",
            "  Lifetime:",
            f"    Cycles:      {state['lifetime_cycles']}",
            f"    Assignments: {state['lifetime_assignments']}",
            f"    Executions:  {state['lifetime_executions']}",
            "",
            "  Config:",
            f"    Workspaces:  {config['workspaces']}",
            f"    Coord:       every {config['coordination_interval_s']}s",
            f"    Evidence:    every {config['evidence_interval_s']}s",
            f"    Health:      every {config['health_interval_s']}s",
            f"    Dry Run:     {config['dry_run']}",
            f"    EM API:      {config['em_api']}",
            "",
            "═══════════════════════════════════════════════════",
        ]
        return "\n".join(lines)

    def unpause(self) -> None:
        """Resume after auto-pause."""
        self.metrics.paused = False
        self.metrics.pause_reason = None
        self.metrics.consecutive_errors = 0
        logger.info("▶️ Runner unpaused, consecutive errors reset")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="KK V2 Swarm Runner — Production Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s daemon --workspaces ./workspaces
  %(prog)s cycle --dry-run
  %(prog)s health --json
  %(prog)s evidence
  %(prog)s status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Operation mode")

    # Daemon
    daemon_p = subparsers.add_parser("daemon", help="Run continuously")
    daemon_p.add_argument("--workspaces", default="./workspaces")
    daemon_p.add_argument("--coord-interval", type=int, default=300)
    daemon_p.add_argument("--evidence-interval", type=int, default=600)
    daemon_p.add_argument("--health-interval", type=int, default=1800)
    daemon_p.add_argument("--dry-run", action="store_true")
    daemon_p.add_argument("--state-file", default="./runner_state.json")

    # Single cycle
    cycle_p = subparsers.add_parser("cycle", help="Run one coordination cycle")
    cycle_p.add_argument("--workspaces", default="./workspaces")
    cycle_p.add_argument("--dry-run", action="store_true")
    cycle_p.add_argument("--json", action="store_true")

    # Evidence
    evidence_p = subparsers.add_parser("evidence", help="Process pending evidence")
    evidence_p.add_argument("--workspaces", default="./workspaces")
    evidence_p.add_argument("--json", action="store_true")

    # Health
    health_p = subparsers.add_parser("health", help="Run health check")
    health_p.add_argument("--json", action="store_true")

    # Status
    status_p = subparsers.add_parser("status", help="Show operational status")
    status_p.add_argument("--json", action="store_true")

    # Unpause
    unpause_p = subparsers.add_parser("unpause", help="Resume after auto-pause")

    return parser.parse_args(argv)


async def async_main(args: argparse.Namespace) -> int:
    """Async entry point."""
    config = RunnerConfig.from_env()

    # Override with CLI args
    if hasattr(args, "workspaces") and args.workspaces:
        config.workspaces_dir = args.workspaces
    if hasattr(args, "dry_run") and args.dry_run:
        config.dry_run = True
    if hasattr(args, "state_file") and args.state_file:
        config.state_file = args.state_file
    if hasattr(args, "coord_interval") and args.coord_interval:
        config.coordination_interval = args.coord_interval
    if hasattr(args, "evidence_interval") and args.evidence_interval:
        config.evidence_interval = args.evidence_interval
    if hasattr(args, "health_interval") and args.health_interval:
        config.health_interval = args.health_interval

    runner = SwarmRunner(config)

    if args.command == "daemon":
        await runner.run_daemon()
        return 0

    elif args.command == "cycle":
        result = await runner.run_single_cycle()
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            status = "✅" if result["success"] else "❌"
            print(f"{status} Coordination cycle: {result.get('duration_ms', 0)}ms")
            for k, v in result.items():
                if k not in ("success", "duration_ms"):
                    print(f"  {k}: {v}")
        return 0 if result["success"] else 1

    elif args.command == "evidence":
        result = await runner.run_single_evidence()
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            status = "✅" if result["success"] else "❌"
            print(f"{status} Evidence processing: {result.get('duration_ms', 0)}ms")
            for k, v in result.items():
                if k not in ("success", "duration_ms"):
                    print(f"  {k}: {v}")
        return 0 if result["success"] else 1

    elif args.command == "health":
        result = await runner.run_single_health()
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            status = "✅" if result["success"] else "❌"
            print(f"{status} Health check: {result.get('duration_ms', 0)}ms")
            for k, v in result.items():
                if k not in ("success", "duration_ms"):
                    print(f"  {k}: {v}")
        return 0 if result["success"] else 1

    elif args.command == "status":
        if getattr(args, "json", False):
            print(json.dumps(runner.get_status(), indent=2))
        else:
            print(runner.format_status())
        return 0

    elif args.command == "unpause":
        runner.unpause()
        runner.state.errors_since_clean_restart = 0
        runner.state.save(config.state_file)
        print("▶️ Runner unpaused")
        return 0

    else:
        print("Use: swarm_runner.py {daemon|cycle|health|evidence|status|unpause}")
        return 1


def main(argv: Optional[list] = None) -> int:
    """Synchronous entry point."""
    args = parse_args(argv)
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    sys.exit(main())
