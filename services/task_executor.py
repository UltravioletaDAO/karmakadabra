"""
Karma Kadabra V2 — Task Executor Service

The engine that makes agents actually DO assigned tasks. This is the missing
piece between the Coordinator (which assigns) and the Evidence Pipeline
(which verifies).

Flow:
    Coordinator assigns task → Notification → Executor picks up
    → Analyze instructions → Choose strategy → Execute → Submit evidence

Execution Strategies:
    1. LLM_DIRECT — Knowledge tasks: answer questions, analyze data, translate
    2. LLM_WITH_TOOLS — Research + code tasks: enriched prompts with tool hints
    3. HUMAN_ROUTE — Physical tasks: self-aware "I can't do this" routing
    4. COMPOSITE — Multi-step tasks: break down, execute parts, assemble

Self-Aware Routing:
    Agents know their limits. Physical presence, photo verification, notarized
    docs — these get routed to human workers instead of hallucinated.

Usage:
    # As a service (called by agent heartbeat)
    executor = TaskExecutor(agent_context, em_client)
    result = await executor.execute_task(task_data)

    # CLI
    python task_executor.py --workspace /path/to/agent --task-id UUID
    python task_executor.py --workspace /path/to/agent --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from lib.working_state import (
    WorkingState,
    clear_active_task,
    parse_working_md,
    set_active_task,
    update_heartbeat,
    write_working_md,
)

logger = logging.getLogger("kk.executor")


# ═══════════════════════════════════════════════════════════════════
# Execution Strategy
# ═══════════════════════════════════════════════════════════════════


class ExecutionStrategy(str, Enum):
    """How a task should be executed."""

    LLM_DIRECT = "llm_direct"  # Pure LLM completion
    LLM_WITH_TOOLS = "llm_with_tools"  # LLM + enriched context
    HUMAN_ROUTE = "human_route"  # Route to human worker
    COMPOSITE = "composite"  # Multi-step breakdown
    SKIP = "skip"  # Not executable (no match)


@dataclass
class ExecutionPlan:
    """Plan for executing a task."""

    strategy: ExecutionStrategy
    reason: str
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    steps: list[str] = field(default_factory=list)
    requires_human: bool = False
    confidence: float = 0.0  # 0-1, how confident we are in the plan


@dataclass
class ExecutionResult:
    """Result of executing a task."""

    success: bool
    strategy_used: ExecutionStrategy
    output: str = ""
    evidence_type: str = "text_response"
    evidence_data: dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str = ""
    routed_to_human: bool = False


# ═══════════════════════════════════════════════════════════════════
# Category → Strategy Mapping
# ═══════════════════════════════════════════════════════════════════

# Tasks that REQUIRE physical presence or human authority
_HUMAN_ONLY_CATEGORIES = {
    "physical_presence",
    "human_authority",
}

# Evidence types that AI cannot produce
_HUMAN_ONLY_EVIDENCE = {
    "photo",
    "photo_geo",
    "video",
    "signature",
    "notarized",
    "receipt",
    "measurement",
}

# Category → default strategy for AI-capable tasks
_CATEGORY_STRATEGY_MAP: dict[str, ExecutionStrategy] = {
    "knowledge_access": ExecutionStrategy.LLM_DIRECT,
    "simple_action": ExecutionStrategy.LLM_WITH_TOOLS,
    "digital_physical": ExecutionStrategy.COMPOSITE,
    "data_collection": ExecutionStrategy.LLM_WITH_TOOLS,
    "content_creation": ExecutionStrategy.LLM_DIRECT,
    "code_review": ExecutionStrategy.LLM_WITH_TOOLS,
    "research": ExecutionStrategy.LLM_WITH_TOOLS,
    "translation": ExecutionStrategy.LLM_DIRECT,
    "analysis": ExecutionStrategy.LLM_DIRECT,
}

# Category-specific prompt enrichment
_CATEGORY_CONTEXT: dict[str, str] = {
    "knowledge_access": (
        "You are a knowledgeable research agent. Provide accurate, well-sourced "
        "information. Cite specific data points when possible. If uncertain, "
        "clearly state your confidence level."
    ),
    "code_review": (
        "You are an expert code reviewer. Check for: security vulnerabilities, "
        "performance issues, code style, error handling, and edge cases. "
        "Provide specific line-level feedback."
    ),
    "content_creation": (
        "You are a skilled content creator. Match the requested tone and style. "
        "Be original — do not copy or closely paraphrase existing content. "
        "Structure your output clearly with sections if appropriate."
    ),
    "research": (
        "You are a thorough research agent. Gather information from multiple "
        "angles. Present findings in a structured format with key takeaways. "
        "Note any conflicting information or gaps."
    ),
    "data_collection": (
        "You are a data collection agent. Extract and structure data precisely. "
        "Use consistent formatting. Flag any data quality issues. "
        "Return structured JSON when appropriate."
    ),
    "analysis": (
        "You are an analytical agent. Break down complex topics into clear "
        "components. Use data-driven reasoning. Present both quantitative "
        "and qualitative insights."
    ),
    "translation": (
        "You are a professional translator. Preserve meaning, tone, and "
        "cultural context. Flag any idioms or concepts that don't translate "
        "directly. Provide translator's notes if needed."
    ),
}


# ═══════════════════════════════════════════════════════════════════
# LLM Provider Protocol
# ═══════════════════════════════════════════════════════════════════


class LLMProvider(Protocol):
    """Protocol for LLM completion providers.

    Any callable matching this signature works:
        async def complete(prompt: str, max_tokens: int) -> str
    """

    async def __call__(self, prompt: str, max_tokens: int = 4096) -> str: ...


async def _mock_llm_provider(prompt: str, max_tokens: int = 4096) -> str:
    """Mock LLM provider for testing."""
    return f"[Mock LLM Response]\n\nBased on the task instructions, here is my analysis:\n\n{prompt[:200]}...\n\n[End of mock response]"


# ═══════════════════════════════════════════════════════════════════
# Task Executor
# ═══════════════════════════════════════════════════════════════════


class TaskExecutor:
    """Execute assigned tasks using appropriate strategies.

    The executor is the brain of each agent — it reads task instructions,
    decides HOW to execute, does the work, and packages evidence.

    Args:
        agent_name: Name of this agent (e.g., "kk-agent-3").
        workspace_dir: Agent's workspace directory.
        llm_provider: Async callable for LLM completions.
        max_output_tokens: Maximum tokens for LLM output.
        budget_limit_usd: Max cost per task execution.
    """

    def __init__(
        self,
        agent_name: str,
        workspace_dir: Path | None = None,
        llm_provider: LLMProvider | None = None,
        max_output_tokens: int = 4096,
        budget_limit_usd: float = 0.50,
    ):
        self.agent_name = agent_name
        self.workspace_dir = workspace_dir or Path(f"/tmp/kk-{agent_name}")
        self.llm = llm_provider or _mock_llm_provider
        self.max_output_tokens = max_output_tokens
        self.budget_limit_usd = budget_limit_usd

        # Execution log for audit trail
        self._execution_log: list[dict[str, Any]] = []

    # ──────────────────────────────────────────────────────────────
    # Planning
    # ──────────────────────────────────────────────────────────────

    def plan_execution(self, task: dict[str, Any]) -> ExecutionPlan:
        """Analyze a task and create an execution plan.

        This is the self-aware routing logic — the agent evaluates whether
        it CAN do the task before attempting it.
        """
        category = task.get("category", "").lower()
        title = task.get("title", "")
        instructions = task.get("instructions", task.get("description", ""))
        evidence_required = task.get("evidence_required", [])
        bounty = task.get("bounty_usd", 0)

        # Check 1: Human-only categories
        if category in _HUMAN_ONLY_CATEGORIES:
            return ExecutionPlan(
                strategy=ExecutionStrategy.HUMAN_ROUTE,
                reason=f"Category '{category}' requires physical human presence",
                requires_human=True,
                confidence=0.95,
                steps=["Route to human worker pool"],
            )

        # Check 2: Human-only evidence types
        human_evidence = set(evidence_required) & _HUMAN_ONLY_EVIDENCE
        if human_evidence:
            return ExecutionPlan(
                strategy=ExecutionStrategy.HUMAN_ROUTE,
                reason=f"Required evidence types need human: {', '.join(human_evidence)}",
                requires_human=True,
                confidence=0.90,
                steps=["Route to human worker pool"],
            )

        # Check 3: Budget check
        estimated_cost = self._estimate_cost(instructions, category)
        if estimated_cost > self.budget_limit_usd:
            return ExecutionPlan(
                strategy=ExecutionStrategy.SKIP,
                reason=f"Estimated cost ${estimated_cost:.2f} exceeds budget ${self.budget_limit_usd:.2f}",
                estimated_cost_usd=estimated_cost,
                confidence=0.80,
            )

        if bounty > 0 and estimated_cost > bounty:
            return ExecutionPlan(
                strategy=ExecutionStrategy.SKIP,
                reason=f"Estimated cost ${estimated_cost:.2f} exceeds bounty ${bounty:.2f} — unprofitable",
                estimated_cost_usd=estimated_cost,
                confidence=0.70,
            )

        # Check 4: Instruction analysis for physical keywords
        physical_keywords = {
            "go to", "visit", "physically", "in person", "take a photo",
            "photograph", "record video", "sign the", "notarize",
            "deliver", "pick up", "bring", "meet at",
        }
        instructions_lower = instructions.lower()
        found_physical = [kw for kw in physical_keywords if kw in instructions_lower]
        if found_physical:
            return ExecutionPlan(
                strategy=ExecutionStrategy.HUMAN_ROUTE,
                reason=f"Instructions contain physical requirements: {', '.join(found_physical[:3])}",
                requires_human=True,
                confidence=0.85,
                steps=["Route to human worker pool"],
            )

        # Check 5: Composite tasks (multiple distinct steps)
        steps = self._detect_steps(instructions)
        if len(steps) >= 3:
            return ExecutionPlan(
                strategy=ExecutionStrategy.COMPOSITE,
                reason=f"Multi-step task detected ({len(steps)} steps)",
                estimated_tokens=self._estimate_tokens(instructions) * len(steps),
                estimated_cost_usd=estimated_cost * len(steps) * 0.6,  # overlap discount
                steps=steps,
                confidence=0.75,
            )

        # Check 6: Category-based strategy
        strategy = _CATEGORY_STRATEGY_MAP.get(category, ExecutionStrategy.LLM_DIRECT)
        estimated_tokens = self._estimate_tokens(instructions)

        return ExecutionPlan(
            strategy=strategy,
            reason=f"Category '{category}' → {strategy.value}",
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost,
            steps=[f"Execute via {strategy.value}"],
            confidence=0.80,
        )

    # ──────────────────────────────────────────────────────────────
    # Execution
    # ──────────────────────────────────────────────────────────────

    async def execute_task(self, task: dict[str, Any]) -> ExecutionResult:
        """Execute a task end-to-end.

        1. Plan the execution
        2. Execute according to strategy
        3. Package evidence
        4. Return result

        This is the main entry point for task execution.
        """
        task_id = task.get("id", "unknown")
        title = task.get("title", "")
        start_time = time.monotonic()

        logger.info(f"[{self.agent_name}] Executing task: {title} ({task_id})")

        # Plan
        plan = self.plan_execution(task)
        logger.info(
            f"[{self.agent_name}] Strategy: {plan.strategy.value} "
            f"(confidence={plan.confidence:.0%}, reason={plan.reason})"
        )

        self._log_event("plan", {
            "task_id": task_id,
            "strategy": plan.strategy.value,
            "reason": plan.reason,
            "confidence": plan.confidence,
        })

        # Route based on strategy
        try:
            if plan.strategy == ExecutionStrategy.HUMAN_ROUTE:
                result = self._route_to_human(task, plan)
            elif plan.strategy == ExecutionStrategy.SKIP:
                result = ExecutionResult(
                    success=False,
                    strategy_used=ExecutionStrategy.SKIP,
                    error=plan.reason,
                )
            elif plan.strategy == ExecutionStrategy.LLM_DIRECT:
                result = await self._execute_llm_direct(task, plan)
            elif plan.strategy == ExecutionStrategy.LLM_WITH_TOOLS:
                result = await self._execute_llm_with_tools(task, plan)
            elif plan.strategy == ExecutionStrategy.COMPOSITE:
                result = await self._execute_composite(task, plan)
            else:
                result = ExecutionResult(
                    success=False,
                    strategy_used=plan.strategy,
                    error=f"Unknown strategy: {plan.strategy}",
                )
        except Exception as e:
            logger.error(f"[{self.agent_name}] Execution failed: {e}")
            result = ExecutionResult(
                success=False,
                strategy_used=plan.strategy,
                error=str(e),
            )

        result.duration_ms = int((time.monotonic() - start_time) * 1000)

        self._log_event("complete", {
            "task_id": task_id,
            "success": result.success,
            "strategy": result.strategy_used.value,
            "duration_ms": result.duration_ms,
            "tokens_used": result.tokens_used,
            "error": result.error,
        })

        return result

    async def _execute_llm_direct(
        self, task: dict[str, Any], plan: ExecutionPlan
    ) -> ExecutionResult:
        """Execute via direct LLM completion."""
        category = task.get("category", "")
        instructions = task.get("instructions", task.get("description", ""))
        title = task.get("title", "")

        # Build prompt
        system_context = _CATEGORY_CONTEXT.get(category, "")
        prompt = self._build_prompt(title, instructions, system_context)

        # Call LLM
        output = await self.llm(prompt, self.max_output_tokens)

        # Estimate tokens (rough)
        tokens_used = len(prompt.split()) + len(output.split())

        return ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.LLM_DIRECT,
            output=output,
            evidence_type=self._infer_evidence_type(task),
            evidence_data={
                "content": output,
                "type": self._infer_evidence_type(task),
                "agent": self.agent_name,
                "strategy": "llm_direct",
                "model": "anthropic/claude-sonnet-4-20250514",
            },
            tokens_used=tokens_used,
            cost_usd=tokens_used * 0.000003,  # ~$3/M input tokens estimate
        )

    async def _execute_llm_with_tools(
        self, task: dict[str, Any], plan: ExecutionPlan
    ) -> ExecutionResult:
        """Execute via LLM with enriched context and tool hints."""
        category = task.get("category", "")
        instructions = task.get("instructions", task.get("description", ""))
        title = task.get("title", "")

        # Build enriched prompt with tool context
        system_context = _CATEGORY_CONTEXT.get(category, "")
        tool_hints = self._get_tool_hints(category, instructions)

        prompt = self._build_prompt(
            title, instructions, system_context,
            extra_context=f"\n\nAvailable capabilities:\n{tool_hints}"
        )

        # Call LLM
        output = await self.llm(prompt, self.max_output_tokens)
        tokens_used = len(prompt.split()) + len(output.split())

        return ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.LLM_WITH_TOOLS,
            output=output,
            evidence_type=self._infer_evidence_type(task),
            evidence_data={
                "content": output,
                "type": self._infer_evidence_type(task),
                "agent": self.agent_name,
                "strategy": "llm_with_tools",
                "tools_available": tool_hints[:200],
            },
            tokens_used=tokens_used,
            cost_usd=tokens_used * 0.000003,
        )

    async def _execute_composite(
        self, task: dict[str, Any], plan: ExecutionPlan
    ) -> ExecutionResult:
        """Execute a multi-step task by breaking it down."""
        instructions = task.get("instructions", task.get("description", ""))
        title = task.get("title", "")

        # Step 1: Decompose
        steps = plan.steps if plan.steps else self._detect_steps(instructions)
        results: list[str] = []
        total_tokens = 0

        for i, step in enumerate(steps):
            logger.info(f"[{self.agent_name}] Step {i + 1}/{len(steps)}: {step[:50]}")

            step_prompt = self._build_prompt(
                f"{title} — Step {i + 1}/{len(steps)}",
                f"Complete this step of the larger task:\n\n{step}\n\n"
                f"Full task context: {instructions[:500]}",
                "Complete this step thoroughly. This is part of a multi-step task.",
            )

            step_output = await self.llm(step_prompt, self.max_output_tokens // len(steps))
            results.append(f"## Step {i + 1}: {step}\n\n{step_output}")
            total_tokens += len(step_prompt.split()) + len(step_output.split())

        # Assemble
        full_output = "\n\n---\n\n".join(results)

        return ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.COMPOSITE,
            output=full_output,
            evidence_type=self._infer_evidence_type(task),
            evidence_data={
                "content": full_output,
                "type": self._infer_evidence_type(task),
                "agent": self.agent_name,
                "strategy": "composite",
                "steps_completed": len(steps),
            },
            tokens_used=total_tokens,
            cost_usd=total_tokens * 0.000003,
        )

    def _route_to_human(
        self, task: dict[str, Any], plan: ExecutionPlan
    ) -> ExecutionResult:
        """Self-aware routing: agent acknowledges it can't do this task."""
        logger.info(
            f"[{self.agent_name}] Routing to human: {plan.reason}"
        )
        return ExecutionResult(
            success=False,
            strategy_used=ExecutionStrategy.HUMAN_ROUTE,
            output=f"Task requires human execution: {plan.reason}",
            routed_to_human=True,
            error="requires_human_worker",
        )

    # ──────────────────────────────────────────────────────────────
    # Prompt Building
    # ──────────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        title: str,
        instructions: str,
        system_context: str = "",
        extra_context: str = "",
    ) -> str:
        """Build an execution prompt for the LLM."""
        parts = []

        if system_context:
            parts.append(f"ROLE: {system_context}")

        parts.append(f"TASK: {title}")
        parts.append(f"\nINSTRUCTIONS:\n{instructions}")

        if extra_context:
            parts.append(extra_context)

        parts.append(
            "\nOUTPUT REQUIREMENTS:\n"
            "- Be thorough and accurate\n"
            "- Structure your response clearly\n"
            "- If you're uncertain about anything, state your confidence level\n"
            "- Provide actionable, specific information\n"
        )

        return "\n\n".join(parts)

    def _get_tool_hints(self, category: str, instructions: str) -> str:
        """Generate tool hints based on category and instructions."""
        hints = []

        # Universal capabilities
        hints.append("- Text analysis and generation")
        hints.append("- Structured data extraction (JSON, CSV)")
        hints.append("- Multi-language translation")

        # Category-specific
        if category in ("code_review", "simple_action"):
            hints.append("- Code analysis and review")
            hints.append("- Security vulnerability detection")
            hints.append("- Best practice recommendations")

        if category in ("research", "data_collection"):
            hints.append("- Information synthesis from multiple sources")
            hints.append("- Data validation and cross-referencing")
            hints.append("- Statistical analysis")

        if "market" in instructions.lower() or "price" in instructions.lower():
            hints.append("- Market data analysis")
            hints.append("- Price trend identification")

        if "blockchain" in instructions.lower() or "on-chain" in instructions.lower():
            hints.append("- Blockchain data interpretation")
            hints.append("- Smart contract analysis")
            hints.append("- On-chain transaction parsing")

        return "\n".join(hints)

    # ──────────────────────────────────────────────────────────────
    # Estimation Helpers
    # ──────────────────────────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate (words * 1.3)."""
        return int(len(text.split()) * 1.3)

    def _estimate_cost(self, instructions: str, category: str) -> float:
        """Estimate execution cost in USD."""
        input_tokens = self._estimate_tokens(instructions)
        output_tokens = min(self.max_output_tokens, input_tokens * 2)
        total_tokens = input_tokens + output_tokens

        # Sonnet pricing: $3/M input, $15/M output (rough blended ~$6/M)
        return total_tokens * 0.000006

    def _infer_evidence_type(self, task: dict[str, Any]) -> str:
        """Infer the best evidence type for a task's output."""
        evidence_required = task.get("evidence_required", [])

        # If task specifies evidence types, use the first AI-compatible one
        ai_compatible = {
            "text_response", "json_response", "api_response",
            "code_output", "structured_data", "text_report",
            "screenshot", "url_reference", "file_artifact",
            "document",
        }

        for ev_type in evidence_required:
            if ev_type in ai_compatible:
                return ev_type

        # Default based on category
        category = task.get("category", "")
        if category in ("data_collection", "research"):
            return "json_response"
        return "text_response"

    def _detect_steps(self, instructions: str) -> list[str]:
        """Detect distinct steps in task instructions."""
        lines = instructions.strip().splitlines()
        steps: list[str] = []
        current_step: list[str] = []

        for line in lines:
            stripped = line.strip()
            # Detect numbered steps or bullet points indicating new steps
            if (
                stripped
                and (
                    stripped[0].isdigit() and (stripped[1:2] in (".", ")", ":"))
                    or stripped.startswith("- Step")
                    or stripped.startswith("## ")
                )
            ):
                if current_step:
                    steps.append(" ".join(current_step))
                current_step = [stripped.lstrip("0123456789.)-: #")]
            elif stripped:
                current_step.append(stripped)

        if current_step:
            steps.append(" ".join(current_step))

        return steps

    # ──────────────────────────────────────────────────────────────
    # Audit Log
    # ──────────────────────────────────────────────────────────────

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Record an event in the execution log."""
        self._execution_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_name,
            "event": event_type,
            **data,
        })

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Get the full execution log."""
        return list(self._execution_log)

    def save_execution_log(self, path: Path | None = None) -> Path:
        """Save execution log to file."""
        if path is None:
            log_dir = self.workspace_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = log_dir / f"execution_{ts}.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._execution_log, indent=2),
            encoding="utf-8",
        )
        return path


# ═══════════════════════════════════════════════════════════════════
# Evidence Packager
# ═══════════════════════════════════════════════════════════════════


def package_evidence(result: ExecutionResult, task: dict[str, Any]) -> dict[str, Any]:
    """Package an execution result into EM evidence format.

    This creates the evidence dict ready for em_client.submit_evidence().
    """
    if not result.success:
        return {}

    evidence = {
        "type": result.evidence_type,
        "content": result.output[:10000],  # EM has a 10K char limit
        "metadata": {
            "agent": result.evidence_data.get("agent", ""),
            "strategy": result.evidence_data.get("strategy", ""),
            "tokens_used": result.tokens_used,
            "cost_usd": round(result.cost_usd, 6),
            "duration_ms": result.duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Add structured data if present
    if result.evidence_type in ("json_response", "structured_data"):
        try:
            # Try to parse output as JSON
            parsed = json.loads(result.output)
            evidence["structured_data"] = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return evidence


# ═══════════════════════════════════════════════════════════════════
# Execution Pipeline (integrates with EM client and state)
# ═══════════════════════════════════════════════════════════════════


async def execute_and_submit(
    executor: TaskExecutor,
    em_client: Any,  # EMClient instance
    task: dict[str, Any],
    working_state: WorkingState | None = None,
    workspace_path: Path | None = None,
) -> ExecutionResult:
    """Full pipeline: plan → execute → submit evidence → update state.

    This is the convenience function that chains everything together.
    Used by agent heartbeat handlers.

    Args:
        executor: TaskExecutor instance.
        em_client: EMClient instance for EM API calls.
        task: Task dict from EM API.
        working_state: Optional WorkingState to update.
        workspace_path: Optional path for WORKING.md updates.

    Returns:
        ExecutionResult from the execution.
    """
    task_id = task.get("id", "unknown")
    title = task.get("title", "")

    # Update state: working
    if working_state and workspace_path:
        set_active_task(working_state, task_id, title, status="working")
        write_working_md(workspace_path / "WORKING.md", working_state)

    # Execute
    result = await executor.execute_task(task)

    if result.success:
        # Package evidence
        evidence = package_evidence(result, task)

        if evidence and em_client:
            # Update state: submitting
            if working_state and workspace_path:
                set_active_task(
                    working_state, task_id, title,
                    status="submitting", next_step="Uploading evidence",
                )
                write_working_md(workspace_path / "WORKING.md", working_state)

            try:
                executor_id = (
                    em_client.agent.executor_id
                    if hasattr(em_client, "agent") and em_client.agent
                    else ""
                )
                await em_client.submit_evidence(task_id, executor_id, evidence)
                logger.info(f"[{executor.agent_name}] Evidence submitted for {task_id}")
            except Exception as e:
                logger.error(f"[{executor.agent_name}] Evidence submission failed: {e}")
                result.error = f"Evidence submission failed: {e}"

    # Update state: done
    if working_state and workspace_path:
        status = "completed" if result.success else "failed"
        action = f"Task {task_id}: {status}"
        update_heartbeat(working_state, action, result.error or "ok")
        clear_active_task(working_state)
        write_working_md(workspace_path / "WORKING.md", working_state)

    return result


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════


async def main():
    parser = argparse.ArgumentParser(description="KK Task Executor")
    parser.add_argument("--workspace", type=str, required=True, help="Agent workspace dir")
    parser.add_argument("--task-id", type=str, help="Task ID to execute")
    parser.add_argument("--task-json", type=str, help="Task JSON file to execute")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, don't execute")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    agent_name = workspace.name

    executor = TaskExecutor(agent_name=agent_name, workspace_dir=workspace)

    if args.task_json:
        task = json.loads(Path(args.task_json).read_text(encoding="utf-8"))
    elif args.task_id:
        # Would need EM client to fetch — for now, require JSON
        print(f"Error: --task-json required (--task-id fetch not implemented in CLI)")
        sys.exit(1)
    else:
        print("Error: provide --task-id or --task-json")
        sys.exit(1)

    plan = executor.plan_execution(task)
    print(f"\n{'=' * 60}")
    print(f"  Task Executor — {agent_name}")
    print(f"{'=' * 60}")
    print(f"  Task: {task.get('title', 'unknown')}")
    print(f"  Strategy: {plan.strategy.value}")
    print(f"  Reason: {plan.reason}")
    print(f"  Confidence: {plan.confidence:.0%}")
    print(f"  Est. Cost: ${plan.estimated_cost_usd:.4f}")
    if plan.steps:
        print(f"  Steps: {len(plan.steps)}")
        for i, step in enumerate(plan.steps):
            print(f"    {i + 1}. {step[:60]}")

    if args.dry_run:
        print(f"\n  [DRY RUN] Would not execute.")
    else:
        print(f"\n  Executing...")
        result = await executor.execute_task(task)
        print(f"  Success: {result.success}")
        print(f"  Duration: {result.duration_ms}ms")
        print(f"  Tokens: {result.tokens_used}")
        if result.output:
            print(f"\n  Output ({len(result.output)} chars):")
            print(f"  {result.output[:500]}")
        if result.error:
            print(f"\n  Error: {result.error}")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
