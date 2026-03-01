"""
Karma Kadabra V2 — Task Pipeline

The end-to-end execution pipeline that makes agents actually DO tasks.
This is the missing production bridge between "assign a task" and "task completed."

Pipeline Stages:
    1. DISCOVER — Poll EM marketplace for available tasks
    2. EVALUATE — Intelligence Synthesizer scores task-agent fit
    3. APPLY — Agent applies to best-fit task via EM API
    4. EXECUTE — Task Executor runs the task using LLM
    5. SUBMIT — Package and submit evidence to EM API
    6. LEARN — Evidence Processor updates performance profiles

The pipeline can run:
    - Single-shot: Process one task and exit
    - Continuous: Loop with configurable interval
    - Batch: Process N tasks in sequence

Key Design Decisions:
    - Each agent runs its own pipeline instance (no shared state)
    - Pipeline is stateless between runs (state lives in WORKING.md + EM API)
    - LLM provider is injected (supports Anthropic, OpenAI, mock)
    - Budget enforcement at every stage
    - Full audit trail via execution logs

Usage:
    # Single agent pipeline
    pipeline = TaskPipeline.from_workspace("/path/to/agent")
    result = await pipeline.run_once()

    # Continuous mode
    await pipeline.run_continuous(interval_seconds=300)

    # CLI
    python task_pipeline.py --workspace /path/to/agent --once
    python task_pipeline.py --workspace /path/to/agent --continuous --interval 300
    python task_pipeline.py --workspace /path/to/agent --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from em_client import AgentContext, EMClient, load_agent_context
from lib.llm_provider import (
    AdaptiveProvider,
    Backend,
    MockProvider,
    ProviderStats,
    create_provider,
)
from lib.working_state import (
    WorkingState,
    clear_active_task,
    parse_working_md,
    set_active_task,
    update_heartbeat,
    write_working_md,
)
from task_executor import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStrategy,
    TaskExecutor,
    package_evidence,
)

logger = logging.getLogger("kk.pipeline")


# ═══════════════════════════════════════════════════════════════════
# Pipeline Configuration
# ═══════════════════════════════════════════════════════════════════


@dataclass
class PipelineConfig:
    """Configuration for the task pipeline."""

    # Budget limits
    per_task_budget_usd: float = 0.50
    daily_budget_usd: float = 5.00
    min_bounty_usd: float = 0.05  # Don't even look at tasks below this

    # Task selection
    max_tasks_per_cycle: int = 3
    preferred_categories: list[str] = field(default_factory=list)
    excluded_categories: list[str] = field(
        default_factory=lambda: ["physical_presence", "human_authority"]
    )

    # LLM provider
    llm_backend: str = "auto"  # auto, anthropic, openai, mock
    llm_model: str | None = None  # None = use provider default
    adaptive_llm: bool = True  # Auto-select model by task complexity

    # Execution
    max_output_tokens: int = 4096
    max_retries: int = 2

    # Pipeline behavior
    continuous_interval_seconds: int = 300  # 5 minutes between cycles
    dry_run: bool = False  # Plan but don't execute/submit

    @classmethod
    def from_env(cls) -> PipelineConfig:
        """Load config from environment variables."""
        return cls(
            per_task_budget_usd=float(os.environ.get("KK_PER_TASK_BUDGET", "0.50")),
            daily_budget_usd=float(os.environ.get("KK_DAILY_BUDGET", "5.00")),
            min_bounty_usd=float(os.environ.get("KK_MIN_BOUNTY", "0.05")),
            max_tasks_per_cycle=int(os.environ.get("KK_MAX_TASKS_PER_CYCLE", "3")),
            llm_backend=os.environ.get("KK_LLM_BACKEND", "auto"),
            llm_model=os.environ.get("KK_LLM_MODEL"),
            adaptive_llm=os.environ.get("KK_ADAPTIVE_LLM", "1") == "1",
            continuous_interval_seconds=int(os.environ.get("KK_CYCLE_INTERVAL", "300")),
            dry_run=os.environ.get("KK_DRY_RUN", "0") == "1",
        )

    @classmethod
    def from_file(cls, path: Path) -> PipelineConfig:
        """Load config from JSON file."""
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════════
# Pipeline Stage Results
# ═══════════════════════════════════════════════════════════════════


@dataclass
class TaskCandidate:
    """A task that passed evaluation for this agent."""
    task_id: str
    title: str
    category: str
    bounty_usd: float
    plan: ExecutionPlan
    match_score: float = 0.0
    raw_task: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of a complete pipeline cycle."""
    cycle_id: str
    agent_name: str
    started_at: str
    completed_at: str = ""
    duration_ms: int = 0

    # Stage results
    tasks_discovered: int = 0
    tasks_evaluated: int = 0
    tasks_applied: int = 0
    tasks_executed: int = 0
    tasks_submitted: int = 0
    tasks_failed: int = 0

    # Costs
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_bounty_usd: float = 0.0

    # Details
    execution_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "agent_name": self.agent_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "tasks_discovered": self.tasks_discovered,
            "tasks_evaluated": self.tasks_evaluated,
            "tasks_applied": self.tasks_applied,
            "tasks_executed": self.tasks_executed,
            "tasks_submitted": self.tasks_submitted,
            "tasks_failed": self.tasks_failed,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "total_bounty_usd": round(self.total_bounty_usd, 4),
            "errors": self.errors,
        }


# ═══════════════════════════════════════════════════════════════════
# Task Pipeline
# ═══════════════════════════════════════════════════════════════════


class TaskPipeline:
    """End-to-end task execution pipeline for a single KK agent.

    Connects:
        EM API (discover/apply/submit)
        → TaskExecutor (plan/execute)
        → LLM Provider (Anthropic/OpenAI)
        → Evidence packaging
    """

    def __init__(
        self,
        agent_context: AgentContext,
        em_client: EMClient,
        config: PipelineConfig | None = None,
        llm_provider: Any = None,
    ):
        self.agent = agent_context
        self.em = em_client
        self.config = config or PipelineConfig.from_env()
        self._daily_spent = 0.0
        self._cycle_count = 0
        self._running = False

        # Create LLM provider
        if llm_provider is not None:
            self._llm = llm_provider
        else:
            self._llm = create_provider(
                backend=self.config.llm_backend if self.config.llm_backend != "auto" else None,
                model=self.config.llm_model,
                adaptive=self.config.adaptive_llm,
            )

        # Create Task Executor
        self._executor = TaskExecutor(
            agent_name=self.agent.name,
            workspace_dir=self.agent.workspace_dir,
            llm_provider=self._llm,
            max_output_tokens=self.config.max_output_tokens,
            budget_limit_usd=self.config.per_task_budget_usd,
        )

        # Pipeline execution log
        self._log: list[dict[str, Any]] = []

    @classmethod
    def from_workspace(
        cls,
        workspace_path: str | Path,
        config: PipelineConfig | None = None,
        llm_provider: Any = None,
    ) -> TaskPipeline:
        """Create a pipeline from an agent workspace directory.

        Loads agent context from workspace/.env or workspace/config.json.
        """
        workspace = Path(workspace_path)
        agent_ctx = load_agent_context(workspace)
        em_client = EMClient(agent_ctx)
        return cls(agent_ctx, em_client, config, llm_provider)

    # ──────────────────────────────────────────────────────────────
    # Stage 1: DISCOVER
    # ──────────────────────────────────────────────────────────────

    async def discover_tasks(self) -> list[dict[str, Any]]:
        """Poll EM marketplace for available tasks.

        Filters out:
        - Tasks below minimum bounty
        - Tasks in excluded categories
        - Tasks the agent already applied to
        """
        try:
            tasks = await self.em.list_tasks(status="published")
        except Exception as e:
            logger.error(f"[{self.agent.name}] Failed to discover tasks: {e}")
            return []

        if not tasks:
            logger.info(f"[{self.agent.name}] No published tasks available")
            return []

        # Filter
        filtered = []
        for task in tasks:
            bounty = task.get("bounty_usd", 0) or 0
            category = task.get("category", "").lower()

            # Minimum bounty
            if bounty < self.config.min_bounty_usd:
                continue

            # Excluded categories
            if category in self.config.excluded_categories:
                continue

            # Already active (agent's own tasks don't need filtering here)
            task_id = task.get("id", "")
            if task_id in self.agent.active_tasks:
                continue

            filtered.append(task)

        logger.info(
            f"[{self.agent.name}] Discovered {len(filtered)}/{len(tasks)} eligible tasks"
        )
        return filtered

    # ──────────────────────────────────────────────────────────────
    # Stage 2: EVALUATE
    # ──────────────────────────────────────────────────────────────

    def evaluate_tasks(self, tasks: list[dict[str, Any]]) -> list[TaskCandidate]:
        """Evaluate tasks and create execution plans.

        Returns tasks sorted by fit score (best first).
        Only returns tasks the agent CAN execute.
        """
        candidates: list[TaskCandidate] = []

        for task in tasks:
            plan = self._executor.plan_execution(task)

            # Skip human-only and unexecutable tasks
            if plan.strategy in (ExecutionStrategy.HUMAN_ROUTE, ExecutionStrategy.SKIP):
                logger.debug(
                    f"[{self.agent.name}] Skip '{task.get('title', '')[:40]}': {plan.reason}"
                )
                continue

            # Budget check against daily limit
            if self._daily_spent + plan.estimated_cost_usd > self.config.daily_budget_usd:
                logger.debug(
                    f"[{self.agent.name}] Skip '{task.get('title', '')[:40]}': "
                    f"daily budget exhausted (${self._daily_spent:.2f}/${self.config.daily_budget_usd:.2f})"
                )
                continue

            # Calculate match score
            match_score = self._calculate_match_score(task, plan)

            candidates.append(TaskCandidate(
                task_id=task.get("id", ""),
                title=task.get("title", ""),
                category=task.get("category", ""),
                bounty_usd=task.get("bounty_usd", 0) or 0,
                plan=plan,
                match_score=match_score,
                raw_task=task,
            ))

        # Sort by match score (highest first)
        candidates.sort(key=lambda c: c.match_score, reverse=True)

        # Limit to max per cycle
        top = candidates[:self.config.max_tasks_per_cycle]

        logger.info(
            f"[{self.agent.name}] Evaluated {len(candidates)} executable tasks, "
            f"selected top {len(top)}"
        )
        return top

    def _calculate_match_score(self, task: dict[str, Any], plan: ExecutionPlan) -> float:
        """Calculate a match score for task-agent fit.

        Factors:
            - Plan confidence (30%)
            - Bounty vs cost ratio (25%)
            - Category preference (20%)
            - Task recency (15%)
            - Evidence type compatibility (10%)
        """
        score = 0.0

        # Confidence (30%)
        score += plan.confidence * 0.30

        # Profitability: bounty / estimated cost (25%)
        bounty = task.get("bounty_usd", 0) or 0
        cost = max(plan.estimated_cost_usd, 0.001)
        profit_ratio = min(bounty / cost, 10.0) / 10.0  # normalize to 0-1
        score += profit_ratio * 0.25

        # Category preference (20%)
        category = task.get("category", "").lower()
        if self.config.preferred_categories:
            if category in self.config.preferred_categories:
                score += 0.20
            else:
                score += 0.05  # still doable, just not preferred
        else:
            score += 0.10  # no preference = neutral

        # Recency (15%) — newer tasks score higher
        # (simple heuristic: all discovered tasks are "new enough")
        score += 0.12

        # Evidence compatibility (10%)
        evidence_required = task.get("evidence_required", [])
        ai_evidence = {"text_response", "document", "screenshot", "json_response"}
        if not evidence_required or set(evidence_required) & ai_evidence:
            score += 0.10
        else:
            score += 0.02

        return min(score, 1.0)

    # ──────────────────────────────────────────────────────────────
    # Stage 3: APPLY
    # ──────────────────────────────────────────────────────────────

    async def apply_to_task(self, candidate: TaskCandidate) -> bool:
        """Apply to a task on the EM marketplace.

        Returns True if application was successful.
        """
        if self.config.dry_run:
            logger.info(
                f"[{self.agent.name}] [DRY RUN] Would apply to: "
                f"'{candidate.title}' (${candidate.bounty_usd:.2f}, "
                f"score={candidate.match_score:.2f})"
            )
            return True

        try:
            result = await self.em.apply_to_task(
                task_id=candidate.task_id,
                message=(
                    f"KK agent {self.agent.name} applying. "
                    f"Strategy: {candidate.plan.strategy.value}, "
                    f"confidence: {candidate.plan.confidence:.0%}. "
                    f"Estimated cost: ${candidate.plan.estimated_cost_usd:.4f}."
                ),
            )
            logger.info(
                f"[{self.agent.name}] Applied to '{candidate.title}' "
                f"(id={candidate.task_id})"
            )
            return True
        except Exception as e:
            logger.error(
                f"[{self.agent.name}] Failed to apply to '{candidate.title}': {e}"
            )
            return False

    # ──────────────────────────────────────────────────────────────
    # Stage 4: EXECUTE
    # ──────────────────────────────────────────────────────────────

    async def execute_task(self, candidate: TaskCandidate) -> ExecutionResult:
        """Execute a task using the Task Executor.

        The executor handles strategy selection, prompt building, and LLM calls.
        """
        if self.config.dry_run:
            logger.info(
                f"[{self.agent.name}] [DRY RUN] Would execute: "
                f"'{candidate.title}' via {candidate.plan.strategy.value}"
            )
            return ExecutionResult(
                success=True,
                strategy_used=candidate.plan.strategy,
                output="[DRY RUN] Execution skipped.",
            )

        # Update workspace state
        workspace_path = self.agent.workspace_dir
        working_md = workspace_path / "WORKING.md"
        state = None
        if working_md.exists():
            state = parse_working_md(working_md)

        if state:
            set_active_task(
                state, candidate.task_id, candidate.title, status="executing"
            )
            write_working_md(working_md, state)

        # Execute via TaskExecutor
        result = await self._executor.execute_task(candidate.raw_task)

        # Update state
        if state:
            if result.success:
                set_active_task(
                    state, candidate.task_id, candidate.title,
                    status="executed", next_step="Submitting evidence"
                )
            else:
                set_active_task(
                    state, candidate.task_id, candidate.title,
                    status="failed", next_step=result.error[:100]
                )
            write_working_md(working_md, state)

        return result

    # ──────────────────────────────────────────────────────────────
    # Stage 5: SUBMIT
    # ──────────────────────────────────────────────────────────────

    async def submit_evidence(
        self, candidate: TaskCandidate, result: ExecutionResult
    ) -> bool:
        """Package and submit evidence to EM API.

        Returns True if submission was successful.
        """
        if not result.success:
            logger.warning(
                f"[{self.agent.name}] Cannot submit evidence for failed task: "
                f"'{candidate.title}'"
            )
            return False

        if self.config.dry_run:
            logger.info(
                f"[{self.agent.name}] [DRY RUN] Would submit evidence for: "
                f"'{candidate.title}' ({len(result.output)} chars)"
            )
            return True

        evidence = package_evidence(result, candidate.raw_task)
        if not evidence:
            logger.error(f"[{self.agent.name}] Evidence packaging failed")
            return False

        try:
            await self.em.submit_evidence(
                task_id=candidate.task_id,
                executor_id=self.agent.executor_id or self.agent.wallet_address,
                evidence=evidence,
            )
            logger.info(
                f"[{self.agent.name}] Evidence submitted for '{candidate.title}' "
                f"({result.tokens_used} tokens, ${result.cost_usd:.4f})"
            )
            return True
        except Exception as e:
            logger.error(
                f"[{self.agent.name}] Evidence submission failed: {e}"
            )
            return False

    # ──────────────────────────────────────────────────────────────
    # Full Pipeline
    # ──────────────────────────────────────────────────────────────

    async def run_once(self) -> PipelineResult:
        """Run one complete pipeline cycle.

        Discover → Evaluate → Apply → Execute → Submit for each task.
        """
        self._cycle_count += 1
        cycle_id = f"{self.agent.name}-cycle-{self._cycle_count}"
        start = time.monotonic()
        now = datetime.now(timezone.utc)

        result = PipelineResult(
            cycle_id=cycle_id,
            agent_name=self.agent.name,
            started_at=now.isoformat(),
        )

        logger.info(f"[{self.agent.name}] === Pipeline cycle {self._cycle_count} ===")

        # Stage 1: Discover
        tasks = await self.discover_tasks()
        result.tasks_discovered = len(tasks)

        if not tasks:
            result.completed_at = datetime.now(timezone.utc).isoformat()
            result.duration_ms = int((time.monotonic() - start) * 1000)
            self._log_result(result)
            return result

        # Stage 2: Evaluate
        candidates = self.evaluate_tasks(tasks)
        result.tasks_evaluated = len(candidates)

        if not candidates:
            logger.info(f"[{self.agent.name}] No executable tasks after evaluation")
            result.completed_at = datetime.now(timezone.utc).isoformat()
            result.duration_ms = int((time.monotonic() - start) * 1000)
            self._log_result(result)
            return result

        # Process each candidate through stages 3-5
        for candidate in candidates:
            task_start = time.monotonic()

            logger.info(
                f"[{self.agent.name}] Processing: '{candidate.title}' "
                f"(${candidate.bounty_usd:.2f}, score={candidate.match_score:.2f}, "
                f"strategy={candidate.plan.strategy.value})"
            )

            # Stage 3: Apply
            applied = await self.apply_to_task(candidate)
            if applied:
                result.tasks_applied += 1
            else:
                result.errors.append(f"Failed to apply: {candidate.title}")
                continue

            # Stage 4: Execute
            exec_result = await self.execute_task(candidate)
            if exec_result.success:
                result.tasks_executed += 1
                result.total_tokens += exec_result.tokens_used
                result.total_cost_usd += exec_result.cost_usd
                self._daily_spent += exec_result.cost_usd
            else:
                result.tasks_failed += 1
                result.errors.append(
                    f"Execution failed: {candidate.title} — {exec_result.error}"
                )
                continue

            # Stage 5: Submit
            submitted = await self.submit_evidence(candidate, exec_result)
            if submitted:
                result.tasks_submitted += 1
                result.total_bounty_usd += candidate.bounty_usd
            else:
                result.errors.append(f"Submission failed: {candidate.title}")

            # Record task details
            task_duration = int((time.monotonic() - task_start) * 1000)
            result.execution_results.append({
                "task_id": candidate.task_id,
                "title": candidate.title,
                "strategy": candidate.plan.strategy.value,
                "success": exec_result.success,
                "tokens": exec_result.tokens_used,
                "cost_usd": round(exec_result.cost_usd, 6),
                "bounty_usd": candidate.bounty_usd,
                "duration_ms": task_duration,
                "output_length": len(exec_result.output),
            })

        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.duration_ms = int((time.monotonic() - start) * 1000)
        self._log_result(result)

        logger.info(
            f"[{self.agent.name}] === Cycle complete: "
            f"{result.tasks_submitted}/{result.tasks_discovered} submitted, "
            f"${result.total_cost_usd:.4f} spent, "
            f"${result.total_bounty_usd:.2f} earned ==="
        )

        return result

    async def run_continuous(
        self,
        interval_seconds: int | None = None,
        max_cycles: int | None = None,
    ) -> list[PipelineResult]:
        """Run pipeline continuously with sleep between cycles.

        Args:
            interval_seconds: Sleep between cycles. Uses config default if None.
            max_cycles: Stop after N cycles. None = run forever.
        """
        interval = interval_seconds or self.config.continuous_interval_seconds
        self._running = True
        results: list[PipelineResult] = []

        logger.info(
            f"[{self.agent.name}] Starting continuous pipeline "
            f"(interval={interval}s, max_cycles={max_cycles})"
        )

        while self._running:
            result = await self.run_once()
            results.append(result)

            if max_cycles and len(results) >= max_cycles:
                logger.info(f"[{self.agent.name}] Reached max cycles ({max_cycles})")
                break

            logger.info(f"[{self.agent.name}] Sleeping {interval}s before next cycle...")
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info(f"[{self.agent.name}] Pipeline cancelled")
                break

        return results

    def stop(self):
        """Signal the continuous pipeline to stop after current cycle."""
        self._running = False
        logger.info(f"[{self.agent.name}] Stop requested")

    # ──────────────────────────────────────────────────────────────
    # Reporting
    # ──────────────────────────────────────────────────────────────

    def _log_result(self, result: PipelineResult) -> None:
        """Append result to internal log and optionally save to disk."""
        self._log.append(result.to_dict())

        # Save to workspace
        log_dir = self.agent.workspace_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"pipeline_{ts}.json"
        log_path.write_text(
            json.dumps(result.to_dict(), indent=2),
            encoding="utf-8",
        )

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate pipeline stats."""
        if not self._log:
            return {"cycles": 0, "agent": self.agent.name}

        total_discovered = sum(r.get("tasks_discovered", 0) for r in self._log)
        total_submitted = sum(r.get("tasks_submitted", 0) for r in self._log)
        total_cost = sum(r.get("total_cost_usd", 0) for r in self._log)
        total_bounty = sum(r.get("total_bounty_usd", 0) for r in self._log)

        # LLM provider stats
        llm_stats = {}
        if hasattr(self._llm, "stats"):
            llm_stats = self._llm.stats.to_dict()

        return {
            "agent": self.agent.name,
            "cycles": len(self._log),
            "daily_spent_usd": round(self._daily_spent, 6),
            "daily_budget_remaining_usd": round(
                self.config.daily_budget_usd - self._daily_spent, 4
            ),
            "total_tasks_discovered": total_discovered,
            "total_tasks_submitted": total_submitted,
            "total_cost_usd": round(total_cost, 6),
            "total_bounty_usd": round(total_bounty, 4),
            "roi": round(
                (total_bounty - total_cost) / max(total_cost, 0.001), 2
            ),
            "llm_stats": llm_stats,
        }

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Get all pipeline cycle results."""
        return list(self._log)


# ═══════════════════════════════════════════════════════════════════
# Multi-Agent Pipeline Runner
# ═══════════════════════════════════════════════════════════════════


class SwarmPipelineRunner:
    """Run pipelines for multiple agents concurrently.

    This is the production entry point for the full swarm.
    Each agent gets its own pipeline instance running in a separate task.
    """

    def __init__(
        self,
        workspaces_dir: str | Path,
        config: PipelineConfig | None = None,
    ):
        self.workspaces_dir = Path(workspaces_dir)
        self.config = config or PipelineConfig.from_env()
        self._pipelines: dict[str, TaskPipeline] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def discover_agents(self) -> list[Path]:
        """Find agent workspaces in the workspaces directory."""
        if not self.workspaces_dir.exists():
            logger.warning(f"Workspaces dir not found: {self.workspaces_dir}")
            return []

        agents = []
        for d in sorted(self.workspaces_dir.iterdir()):
            if d.is_dir() and (d / "SOUL.md").exists():
                agents.append(d)

        logger.info(f"Discovered {len(agents)} agent workspaces")
        return agents

    async def start(
        self,
        max_concurrent: int = 5,
        max_cycles: int | None = None,
    ) -> dict[str, list[PipelineResult]]:
        """Start pipelines for all discovered agents.

        Args:
            max_concurrent: Maximum agents running simultaneously.
            max_cycles: Cycles per agent before stopping.
        """
        agent_dirs = self.discover_agents()
        if not agent_dirs:
            logger.warning("No agent workspaces found")
            return {}

        # Create pipelines
        semaphore = asyncio.Semaphore(max_concurrent)
        all_results: dict[str, list[PipelineResult]] = {}

        async def run_agent(workspace: Path):
            async with semaphore:
                try:
                    pipeline = TaskPipeline.from_workspace(workspace, self.config)
                    self._pipelines[pipeline.agent.name] = pipeline
                    results = await pipeline.run_continuous(max_cycles=max_cycles)
                    all_results[pipeline.agent.name] = results
                except Exception as e:
                    logger.error(f"Agent {workspace.name} failed: {e}")
                    all_results[workspace.name] = []

        # Run all agents
        tasks = [asyncio.create_task(run_agent(d)) for d in agent_dirs]
        await asyncio.gather(*tasks, return_exceptions=True)

        return all_results

    def get_fleet_stats(self) -> dict[str, Any]:
        """Get aggregate stats across all pipelines."""
        fleet = {}
        for name, pipeline in self._pipelines.items():
            fleet[name] = pipeline.get_stats()
        return fleet


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════


async def main():
    parser = argparse.ArgumentParser(
        description="KK Task Pipeline — End-to-End Task Execution"
    )
    parser.add_argument(
        "--workspace", type=str,
        help="Single agent workspace directory",
    )
    parser.add_argument(
        "--workspaces-dir", type=str,
        help="Directory containing multiple agent workspaces",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one cycle and exit",
    )
    parser.add_argument(
        "--continuous", action="store_true",
        help="Run continuously",
    )
    parser.add_argument(
        "--interval", type=int, default=300,
        help="Seconds between cycles (continuous mode)",
    )
    parser.add_argument(
        "--max-cycles", type=int,
        help="Maximum cycles before stopping",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Plan and evaluate but don't execute or submit",
    )
    parser.add_argument(
        "--backend", type=str, default="auto",
        choices=["auto", "anthropic", "openai", "mock"],
        help="LLM backend",
    )
    parser.add_argument(
        "--model", type=str,
        help="Specific LLM model to use",
    )
    parser.add_argument(
        "--budget", type=float, default=5.0,
        help="Daily budget in USD",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show pipeline stats and exit",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output in JSON format",
    )

    args = parser.parse_args()

    config = PipelineConfig(
        dry_run=args.dry_run,
        llm_backend=args.backend,
        llm_model=args.model,
        daily_budget_usd=args.budget,
        continuous_interval_seconds=args.interval,
    )

    if args.workspaces_dir:
        # Multi-agent mode
        runner = SwarmPipelineRunner(args.workspaces_dir, config)
        results = await runner.start(max_cycles=args.max_cycles)

        if args.json:
            print(json.dumps(runner.get_fleet_stats(), indent=2))
        else:
            for name, agent_results in results.items():
                print(f"\n{name}: {len(agent_results)} cycles")
                for r in agent_results:
                    print(
                        f"  {r.cycle_id}: {r.tasks_submitted}/{r.tasks_discovered} "
                        f"submitted, ${r.total_cost_usd:.4f} cost"
                    )

    elif args.workspace:
        # Single agent mode
        pipeline = TaskPipeline.from_workspace(args.workspace, config)

        if args.stats:
            print(json.dumps(pipeline.get_stats(), indent=2))
            return

        if args.continuous:
            results = await pipeline.run_continuous(max_cycles=args.max_cycles)
        else:
            result = await pipeline.run_once()
            results = [result]

        if args.json:
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            for r in results:
                print(f"\n{'=' * 60}")
                print(f"  Cycle: {r.cycle_id}")
                print(f"  Duration: {r.duration_ms}ms")
                print(f"  Tasks: {r.tasks_discovered} found → "
                      f"{r.tasks_evaluated} evaluated → "
                      f"{r.tasks_submitted} submitted")
                print(f"  Cost: ${r.total_cost_usd:.4f}")
                print(f"  Bounty: ${r.total_bounty_usd:.2f}")
                if r.errors:
                    print(f"  Errors:")
                    for e in r.errors:
                        print(f"    ⚠ {e}")
                print(f"{'=' * 60}")
    else:
        parser.error("Provide --workspace or --workspaces-dir")


if __name__ == "__main__":
    asyncio.run(main())
