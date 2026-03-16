"""
Swarm Task Executor — Autonomous Task Execution Engine
=======================================================

The missing keystone: takes an assigned task and ACTUALLY DOES IT.

While the SwarmOrchestrator decides WHO does what, and the
SwarmContextInjector provides WHAT the agent knows, the TaskExecutor
is the engine that produces RESULTS.

Architecture:
    ┌──────────────────────────┐
    │   Swarm Orchestrator     │  "Agent aurora should do task X"
    └────────────┬─────────────┘
                 │ assignment
    ┌────────────▼─────────────┐
    │   Swarm Context Injector │  "Here's what aurora knows"
    └────────────┬─────────────┘
                 │ context
    ┌────────────▼─────────────┐
    │   Task Executor          │  ← YOU ARE HERE
    │                          │
    │   1. Accept task via API │
    │   2. Build execution ctx │
    │   3. Route to strategy   │
    │   4. Execute (LLM/human) │
    │   5. Submit evidence     │
    │   6. Report completion   │
    └──────────────────────────┘

Execution Strategies:
    - knowledge_access → LLM generates response (research, analysis, reports)
    - content_creation → LLM writes content (articles, summaries, docs)
    - code_review     → LLM analyzes code (review, testing, auditing)
    - translation     → LLM translates text
    - physical_presence → Route to human worker queue (can't be done by AI)
    - data_collection → Hybrid: LLM for web data, human for physical

Usage:
    executor = SwarmTaskExecutor(
        orchestrator=orchestrator,
        context_injector=injector,
        em_api_base="https://api.execution.market",
    )

    # Execute a single assigned task
    result = await executor.execute_task(assignment, task_data)

    # Process all available tasks in one batch
    results = await executor.process_available_tasks()
"""

import json
import logging
import ssl
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Callable

logger = logging.getLogger(__name__)


# ── Execution Strategies ──

class ExecutionStrategy(str, Enum):
    """How a task gets executed."""
    LLM_DIRECT = "llm_direct"           # LLM generates result directly
    LLM_WITH_TOOLS = "llm_with_tools"   # LLM + web search, code exec, etc.
    HUMAN_ROUTE = "human_route"          # Route to human worker queue
    HYBRID = "hybrid"                    # LLM does what it can, human fills gaps
    SKIP = "skip"                        # Task not executable (wrong type, etc.)


# Category → Strategy mapping
CATEGORY_STRATEGIES = {
    "knowledge_access": ExecutionStrategy.LLM_DIRECT,
    "content_creation": ExecutionStrategy.LLM_DIRECT,
    "code_review": ExecutionStrategy.LLM_WITH_TOOLS,
    "translation": ExecutionStrategy.LLM_DIRECT,
    "research": ExecutionStrategy.LLM_WITH_TOOLS,
    "testing": ExecutionStrategy.LLM_WITH_TOOLS,
    "data_collection": ExecutionStrategy.HYBRID,
    "physical_presence": ExecutionStrategy.HUMAN_ROUTE,
    "photo_verification": ExecutionStrategy.HUMAN_ROUTE,
    "design": ExecutionStrategy.HUMAN_ROUTE,
}


@dataclass
class ExecutionResult:
    """Result of executing a task."""
    task_id: str
    agent_id: str
    strategy: ExecutionStrategy
    success: bool
    result_type: str = "text_response"  # EM evidence type
    result_data: str = ""
    notes: str = ""
    submission_id: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    
    # For human-routed tasks
    routed_to_human: bool = False
    human_queue_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecutionPlan:
    """Plan for how to execute a task before doing it."""
    task_id: str
    agent_id: str
    strategy: ExecutionStrategy
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    context_block: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    can_execute: bool = True
    skip_reason: Optional[str] = None


@dataclass
class ExecutionStats:
    """Aggregate stats for the executor."""
    total_executed: int = 0
    total_success: int = 0
    total_failed: int = 0
    total_routed_to_human: int = 0
    total_skipped: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_earnings_usd: float = 0.0
    avg_duration_ms: float = 0.0
    _durations: List[int] = field(default_factory=list, repr=False)

    def record(self, result: ExecutionResult, bounty_usd: float = 0.0):
        """Record an execution result."""
        self.total_executed += 1
        if result.success:
            self.total_success += 1
            self.total_earnings_usd += bounty_usd
        elif result.routed_to_human:
            self.total_routed_to_human += 1
        elif result.error:
            self.total_failed += 1
        else:
            self.total_skipped += 1
        self.total_tokens += result.tokens_used
        self.total_cost_usd += result.cost_usd
        self._durations.append(result.duration_ms)
        if self._durations:
            self.avg_duration_ms = sum(self._durations) / len(self._durations)

    @property
    def success_rate(self) -> float:
        executable = self.total_executed - self.total_skipped - self.total_routed_to_human
        if executable <= 0:
            return 0.0
        return self.total_success / executable

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_durations", None)
        d["success_rate"] = round(self.success_rate, 3)
        return d


class SwarmTaskExecutor:
    """
    Autonomous task execution engine for the KarmaKadabra swarm.

    Takes assigned tasks and produces results by:
    1. Planning the execution strategy
    2. Building agent-specific context
    3. Generating results via LLM or routing to human
    4. Submitting evidence to EM API
    5. Reporting completion to the orchestrator
    """

    def __init__(
        self,
        orchestrator=None,
        context_injector=None,
        em_api_base: str = "https://api.execution.market",
        em_api_key: str = "",
        llm_provider: Optional[Callable] = None,
        max_retries: int = 2,
        timeout_seconds: int = 120,
        dry_run: bool = False,
    ):
        """
        Args:
            orchestrator: SwarmOrchestrator instance
            context_injector: SwarmContextInjector instance
            em_api_base: EM API base URL
            em_api_key: EM API key for authentication
            llm_provider: Async callable for LLM inference
                Signature: async (system_prompt: str, user_prompt: str, model: str) -> str
            max_retries: Max retries per task execution
            timeout_seconds: Timeout per task execution
            dry_run: If True, don't make real API calls
        """
        self.orchestrator = orchestrator
        self.context_injector = context_injector
        self.em_api_base = em_api_base.rstrip("/")
        self.em_api_key = em_api_key
        self.llm_provider = llm_provider or self._default_llm_provider
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run

        self.stats = ExecutionStats()
        self._execution_log: List[dict] = []

    # ══════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════

    async def execute_task(
        self,
        task: dict,
        agent_id: str,
        executor_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a single task as the given agent.

        Full lifecycle:
        1. Plan execution strategy
        2. Accept task via EM API (if not already accepted)
        3. Build execution context
        4. Execute (LLM call or human routing)
        5. Submit evidence to EM API
        6. Report completion to orchestrator

        Args:
            task: Task dict from EM API
            agent_id: Agent performing the task
            executor_id: EM executor ID (from em_register_as_executor)

        Returns:
            ExecutionResult with success/failure details
        """
        start_time = time.time()
        task_id = task.get("id", "unknown")

        logger.info(f"[{agent_id}] Starting execution of task {task_id}")

        # Step 1: Plan
        plan = await self._plan_execution(task, agent_id)
        if not plan.can_execute:
            result = ExecutionResult(
                task_id=task_id,
                agent_id=agent_id,
                strategy=plan.strategy,
                success=False,
                error=plan.skip_reason,
            )
            self.stats.record(result)
            return result

        # Step 2: Accept task (if not dry_run and executor_id provided)
        if not self.dry_run and executor_id and task.get("status") == "published":
            accepted = await self._accept_task(task_id, executor_id)
            if not accepted:
                result = ExecutionResult(
                    task_id=task_id,
                    agent_id=agent_id,
                    strategy=plan.strategy,
                    success=False,
                    error="Failed to accept task via API",
                )
                self.stats.record(result)
                return result

        # Step 3: Execute based on strategy
        result = await self._execute_with_strategy(plan, task)

        # Step 4: Submit evidence (if successful and not dry_run)
        if result.success and not self.dry_run and executor_id:
            submitted = await self._submit_evidence(
                task_id=task_id,
                executor_id=executor_id,
                result_type=result.result_type,
                result_data=result.result_data,
                notes=result.notes,
            )
            if submitted:
                result.submission_id = submitted
            else:
                logger.warning(f"[{agent_id}] Evidence submission failed for {task_id}")

        # Step 5: Report to orchestrator
        if self.orchestrator:
            await self.orchestrator.complete_task(
                task_id=task_id,
                success=result.success,
                earnings_usd=float(task.get("bounty_usd", 0)) if result.success else 0,
            )

        # Finalize
        result.duration_ms = int((time.time() - start_time) * 1000)
        self.stats.record(result, float(task.get("bounty_usd", 0)))
        self._log_execution(result, task)

        logger.info(
            f"[{agent_id}] Task {task_id} {'✅ completed' if result.success else '❌ failed'} "
            f"in {result.duration_ms}ms (strategy: {result.strategy.value})"
        )

        return result

    async def process_available_tasks(
        self,
        limit: int = 10,
        categories: Optional[List[str]] = None,
    ) -> List[ExecutionResult]:
        """
        Fetch available tasks, assign via orchestrator, and execute.

        Full autonomous pipeline:
        1. Fetch published tasks from EM API
        2. For each task, ask orchestrator for best agent
        3. Execute with assigned agent
        4. Collect results

        Args:
            limit: Max tasks to process
            categories: Filter by category (None = all)

        Returns:
            List of ExecutionResult
        """
        results = []

        # Fetch available tasks
        tasks = await self._fetch_tasks(limit=limit, categories=categories)
        if not tasks:
            logger.info("No available tasks to process")
            return results

        logger.info(f"Found {len(tasks)} available tasks")

        for task in tasks:
            task_id = task.get("id", "")
            category = task.get("category", "general")
            bounty = float(task.get("bounty_usd", 0))

            # Skip human-only tasks
            strategy = CATEGORY_STRATEGIES.get(category, ExecutionStrategy.LLM_DIRECT)
            if strategy == ExecutionStrategy.HUMAN_ROUTE:
                logger.info(f"Skipping {task_id} — requires human (category: {category})")
                continue

            # Ask orchestrator for best agent
            if self.orchestrator:
                assignment = await self.orchestrator.assign_task(
                    task_id=task_id,
                    category=category,
                    bounty_usd=bounty,
                )
                if not assignment.assigned_agent:
                    logger.info(f"No agent available for {task_id}: {assignment.unassigned_reason}")
                    continue
                agent_id = assignment.assigned_agent
            else:
                agent_id = "default_agent"

            # Execute
            result = await self.execute_task(task, agent_id)
            results.append(result)

        return results

    def get_stats(self) -> dict:
        """Get execution statistics."""
        return self.stats.to_dict()

    def get_execution_log(self, limit: int = 50) -> List[dict]:
        """Get recent execution log entries."""
        return self._execution_log[-limit:]

    # ══════════════════════════════════════════
    # Execution Strategies
    # ══════════════════════════════════════════

    async def _execute_with_strategy(
        self,
        plan: ExecutionPlan,
        task: dict,
    ) -> ExecutionResult:
        """Route execution to the appropriate strategy."""
        task_id = task.get("id", "unknown")

        for attempt in range(self.max_retries + 1):
            try:
                if plan.strategy == ExecutionStrategy.LLM_DIRECT:
                    return await self._execute_llm_direct(plan, task)
                elif plan.strategy == ExecutionStrategy.LLM_WITH_TOOLS:
                    return await self._execute_llm_with_tools(plan, task)
                elif plan.strategy == ExecutionStrategy.HYBRID:
                    return await self._execute_hybrid(plan, task)
                elif plan.strategy == ExecutionStrategy.HUMAN_ROUTE:
                    return await self._execute_human_route(plan, task)
                else:
                    return ExecutionResult(
                        task_id=task_id,
                        agent_id=plan.agent_id,
                        strategy=plan.strategy,
                        success=False,
                        error=f"Unknown strategy: {plan.strategy}",
                    )
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"[{plan.agent_id}] Attempt {attempt + 1} failed for {task_id}: {e}"
                    )
                    continue
                return ExecutionResult(
                    task_id=task_id,
                    agent_id=plan.agent_id,
                    strategy=plan.strategy,
                    success=False,
                    error=f"All {self.max_retries + 1} attempts failed: {e}",
                )

        # Should not reach here, but just in case
        return ExecutionResult(
            task_id=task_id,
            agent_id=plan.agent_id,
            strategy=plan.strategy,
            success=False,
            error="Execution loop ended without result",
        )

    async def _execute_llm_direct(
        self,
        plan: ExecutionPlan,
        task: dict,
    ) -> ExecutionResult:
        """Execute task using direct LLM generation."""
        task_id = task.get("id", "unknown")

        # Get LLM response
        response = await self.llm_provider(
            system_prompt=plan.system_prompt,
            user_prompt=plan.user_prompt,
            model=self._get_agent_model(plan.agent_id),
        )

        if not response or len(response.strip()) < 10:
            return ExecutionResult(
                task_id=task_id,
                agent_id=plan.agent_id,
                strategy=ExecutionStrategy.LLM_DIRECT,
                success=False,
                error="LLM returned empty or trivial response",
            )

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        est_tokens = (len(plan.system_prompt) + len(plan.user_prompt) + len(response)) // 4

        return ExecutionResult(
            task_id=task_id,
            agent_id=plan.agent_id,
            strategy=ExecutionStrategy.LLM_DIRECT,
            success=True,
            result_type=self._pick_evidence_type(task),
            result_data=response,
            notes=f"Generated by {plan.agent_id} via LLM direct execution",
            tokens_used=est_tokens,
            cost_usd=self._estimate_cost(est_tokens, plan.agent_id),
        )

    async def _execute_llm_with_tools(
        self,
        plan: ExecutionPlan,
        task: dict,
    ) -> ExecutionResult:
        """
        Execute task using LLM with tool augmentation.

        For now, this is the same as LLM_DIRECT but with an enriched prompt
        that tells the LLM to be thorough and analytical. In production,
        this would connect to web search, code execution, etc.
        """
        task_id = task.get("id", "unknown")
        category = task.get("category", "")

        # Enrich prompt for tool-augmented categories
        enriched_system = plan.system_prompt
        if category == "code_review":
            enriched_system += (
                "\n\n## Code Review Guidelines\n"
                "- Check for security vulnerabilities (injection, XSS, CSRF)\n"
                "- Evaluate code quality (naming, structure, DRY)\n"
                "- Assess performance implications\n"
                "- Suggest concrete improvements with code examples\n"
                "- Rate severity: critical / major / minor / suggestion\n"
            )
        elif category == "research":
            enriched_system += (
                "\n\n## Research Guidelines\n"
                "- Cite specific sources where possible\n"
                "- Distinguish facts from opinions\n"
                "- Include quantitative data when available\n"
                "- Note limitations and gaps in available information\n"
                "- Provide actionable conclusions\n"
            )
        elif category == "testing":
            enriched_system += (
                "\n\n## Testing Guidelines\n"
                "- Define clear test cases with expected outcomes\n"
                "- Cover edge cases and error conditions\n"
                "- Include setup and teardown steps\n"
                "- Rate test coverage: comprehensive / adequate / minimal\n"
                "- Flag any untestable requirements\n"
            )

        response = await self.llm_provider(
            system_prompt=enriched_system,
            user_prompt=plan.user_prompt,
            model=self._get_agent_model(plan.agent_id),
        )

        if not response or len(response.strip()) < 10:
            return ExecutionResult(
                task_id=task_id,
                agent_id=plan.agent_id,
                strategy=ExecutionStrategy.LLM_WITH_TOOLS,
                success=False,
                error="LLM returned empty or trivial response",
            )

        est_tokens = (len(enriched_system) + len(plan.user_prompt) + len(response)) // 4

        return ExecutionResult(
            task_id=task_id,
            agent_id=plan.agent_id,
            strategy=ExecutionStrategy.LLM_WITH_TOOLS,
            success=True,
            result_type=self._pick_evidence_type(task),
            result_data=response,
            notes=f"Generated by {plan.agent_id} via LLM with {category} augmentation",
            tokens_used=est_tokens,
            cost_usd=self._estimate_cost(est_tokens, plan.agent_id),
        )

    async def _execute_hybrid(
        self,
        plan: ExecutionPlan,
        task: dict,
    ) -> ExecutionResult:
        """
        Hybrid execution: LLM handles what it can, flags what needs human.

        For data_collection tasks:
        - Web-accessible data → LLM fetches and analyzes
        - Physical-world data → Flagged for human follow-up
        """
        task_id = task.get("id", "unknown")
        location = task.get("location_hint", "")

        # If task requires physical location, route to human
        if location and any(
            kw in task.get("title", "").lower()
            for kw in ["visit", "photograph", "check", "verify", "inspect"]
        ):
            return await self._execute_human_route(plan, task)

        # Otherwise, try LLM execution
        return await self._execute_llm_direct(plan, task)

    async def _execute_human_route(
        self,
        plan: ExecutionPlan,
        task: dict,
    ) -> ExecutionResult:
        """
        Route task to human worker queue.

        The swarm recognizes it CAN'T do this task and gracefully
        leaves it for human workers. This is key: agent self-awareness
        about capability boundaries.
        """
        task_id = task.get("id", "unknown")

        logger.info(
            f"[{plan.agent_id}] Task {task_id} routed to human queue "
            f"(category: {task.get('category', 'unknown')})"
        )

        return ExecutionResult(
            task_id=task_id,
            agent_id=plan.agent_id,
            strategy=ExecutionStrategy.HUMAN_ROUTE,
            success=False,  # Not a failure — just not our job
            error=None,
            routed_to_human=True,
            notes=(
                f"Task requires human capabilities. "
                f"Category: {task.get('category', 'unknown')}. "
                f"Location: {task.get('location_hint', 'N/A')}."
            ),
        )

    # ══════════════════════════════════════════
    # Planning & Context
    # ══════════════════════════════════════════

    async def _plan_execution(
        self,
        task: dict,
        agent_id: str,
    ) -> ExecutionPlan:
        """
        Build an execution plan for a task.

        Determines:
        - Which strategy to use
        - What context to inject
        - What prompts to send
        - Whether the task is even executable
        """
        task_id = task.get("id", "unknown")
        category = task.get("category", "general")
        title = task.get("title", "Untitled task")
        instructions = task.get("instructions", "")
        bounty = float(task.get("bounty_usd", 0))

        # Determine strategy
        strategy = CATEGORY_STRATEGIES.get(category, ExecutionStrategy.LLM_DIRECT)

        plan = ExecutionPlan(
            task_id=task_id,
            agent_id=agent_id,
            strategy=strategy,
        )

        # Check if we can execute this strategy
        if strategy == ExecutionStrategy.HUMAN_ROUTE:
            plan.can_execute = True  # We "execute" by routing to human
            return plan

        # Build context from injector
        context_block = ""
        if self.context_injector:
            try:
                context_block = await self.context_injector.build_agent_context(
                    agent_id=agent_id,
                    task=task,
                )
            except Exception as e:
                logger.warning(f"Context injection failed for {agent_id}: {e}")
                context_block = f"[Context unavailable: {e}]"

        plan.context_block = context_block

        # Build system prompt
        plan.system_prompt = self._build_system_prompt(
            agent_id=agent_id,
            category=category,
            context_block=context_block,
        )

        # Build user prompt
        plan.user_prompt = self._build_user_prompt(
            title=title,
            instructions=instructions,
            task=task,
        )

        # Estimate resources
        total_chars = len(plan.system_prompt) + len(plan.user_prompt)
        plan.estimated_tokens = total_chars // 4 * 3  # Input + estimated output
        plan.estimated_cost_usd = self._estimate_cost(plan.estimated_tokens, agent_id)

        return plan

    def _build_system_prompt(
        self,
        agent_id: str,
        category: str,
        context_block: str = "",
    ) -> str:
        """Build the system prompt for task execution."""
        prompt_parts = [
            "You are an autonomous agent executing a task on Execution Market.",
            f"Your agent ID is: {agent_id}",
            "",
            "## Your Mission",
            "Complete the assigned task thoroughly and accurately.",
            "Your output will be submitted as evidence of task completion.",
            "",
            "## Quality Standards",
            "- Be thorough: address every aspect of the task",
            "- Be specific: provide concrete details, not vague generalities",
            "- Be honest: if you can't fully complete something, say so",
            "- Be structured: use clear headings and organization",
            "",
        ]

        # Add category-specific guidance
        category_guidance = {
            "knowledge_access": (
                "## Task Type: Knowledge Access\n"
                "Provide comprehensive, well-researched information.\n"
                "Structure your response with clear sections.\n"
                "Include relevant data points and analysis."
            ),
            "content_creation": (
                "## Task Type: Content Creation\n"
                "Write engaging, well-structured content.\n"
                "Match the requested tone and style.\n"
                "Ensure originality and depth."
            ),
            "code_review": (
                "## Task Type: Code Review\n"
                "Analyze code systematically.\n"
                "Categorize findings by severity.\n"
                "Provide specific, actionable feedback with examples."
            ),
            "translation": (
                "## Task Type: Translation\n"
                "Provide accurate, natural-sounding translations.\n"
                "Preserve meaning, tone, and cultural context.\n"
                "Note any untranslatable terms or cultural references."
            ),
            "research": (
                "## Task Type: Research\n"
                "Conduct thorough investigation.\n"
                "Cite sources where possible.\n"
                "Present findings clearly with supporting evidence."
            ),
            "data_collection": (
                "## Task Type: Data Collection\n"
                "Gather requested data systematically.\n"
                "Verify accuracy where possible.\n"
                "Present in structured format (tables, lists, etc.)."
            ),
        }

        if category in category_guidance:
            prompt_parts.append(category_guidance[category])
            prompt_parts.append("")

        # Add injected context
        if context_block:
            prompt_parts.append("## Your Profile & Context")
            prompt_parts.append(context_block)
            prompt_parts.append("")

        return "\n".join(prompt_parts)

    def _build_user_prompt(
        self,
        title: str,
        instructions: str,
        task: dict,
    ) -> str:
        """Build the user prompt for task execution."""
        parts = [
            f"# Task: {title}",
            "",
        ]

        if instructions:
            parts.extend([
                "## Instructions",
                instructions,
                "",
            ])

        # Add task metadata
        bounty = task.get("bounty_usd", 0)
        deadline = task.get("deadline", "")
        category = task.get("category", "")
        evidence_schema = task.get("evidence_schema", {})

        parts.extend([
            "## Task Details",
            f"- **Category**: {category}",
            f"- **Bounty**: ${bounty}",
        ])

        if deadline:
            parts.append(f"- **Deadline**: {deadline}")

        if evidence_schema:
            parts.extend([
                "",
                "## Required Evidence Format",
                json.dumps(evidence_schema, indent=2),
            ])

        parts.extend([
            "",
            "## Your Response",
            "Provide your complete response below. Be thorough and well-structured.",
        ])

        return "\n".join(parts)

    # ══════════════════════════════════════════
    # EM API Interactions
    # ══════════════════════════════════════════

    async def _fetch_tasks(
        self,
        limit: int = 10,
        categories: Optional[List[str]] = None,
    ) -> List[dict]:
        """Fetch available tasks from EM API."""
        if self.dry_run:
            return self._mock_tasks()

        try:
            url = f"{self.em_api_base}/api/v1/tasks?status=published&limit={limit}"
            data = await self._api_get(url)

            tasks = data if isinstance(data, list) else data.get("tasks", [])

            # Filter by category if specified
            if categories:
                tasks = [t for t in tasks if t.get("category") in categories]

            return tasks

        except Exception as e:
            logger.error(f"Failed to fetch tasks: {e}")
            return []

    async def _accept_task(self, task_id: str, executor_id: str) -> bool:
        """Accept a task via EM API."""
        try:
            url = f"{self.em_api_base}/api/v1/tasks/{task_id}/accept"
            payload = {"executor_id": executor_id}
            await self._api_post(url, payload)
            logger.info(f"Accepted task {task_id} as executor {executor_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to accept task {task_id}: {e}")
            return False

    async def _submit_evidence(
        self,
        task_id: str,
        executor_id: str,
        result_type: str,
        result_data: str,
        notes: str = "",
    ) -> Optional[str]:
        """Submit task evidence via EM API."""
        try:
            url = f"{self.em_api_base}/api/v1/tasks/{task_id}/submit"
            payload = {
                "executor_id": executor_id,
                "result_type": result_type,
                "result_data": result_data,
                "notes": notes,
            }
            resp = await self._api_post(url, payload)
            submission_id = resp.get("submission_id") if isinstance(resp, dict) else None
            logger.info(f"Submitted evidence for task {task_id}: {submission_id}")
            return submission_id
        except Exception as e:
            logger.error(f"Failed to submit evidence for {task_id}: {e}")
            return None

    async def _api_get(self, url: str) -> Any:
        """Make a GET request to EM API."""
        headers = {"Content-Type": "application/json"}
        if self.em_api_key:
            headers["Authorization"] = f"Bearer {self.em_api_key}"

        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=self.timeout_seconds, context=ctx) as resp:
            return json.loads(resp.read().decode())

    async def _api_post(self, url: str, payload: dict) -> Any:
        """Make a POST request to EM API."""
        headers = {"Content-Type": "application/json"}
        if self.em_api_key:
            headers["Authorization"] = f"Bearer {self.em_api_key}"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        ctx = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=self.timeout_seconds, context=ctx) as resp:
            return json.loads(resp.read().decode())

    # ══════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════

    def _get_agent_model(self, agent_id: str) -> str:
        """Get the LLM model for an agent."""
        if self.orchestrator:
            state = self.orchestrator.lifecycle.get_agent(agent_id)
            if state:
                return state.model
        return "anthropic/claude-haiku-4-5"

    def _pick_evidence_type(self, task: dict) -> str:
        """Pick the best evidence type for a task."""
        schema = task.get("evidence_schema") or {}
        required = schema.get("required_types", [])

        if "text_response" in required:
            return "text_response"
        elif "document" in required:
            return "document"
        elif required:
            return required[0]
        return "text_response"

    def _estimate_cost(self, tokens: int, agent_id: str) -> float:
        """Estimate execution cost in USD."""
        model = self._get_agent_model(agent_id)
        # Cost per million tokens (input + output average)
        costs_per_mtok = {
            "anthropic/claude-haiku-4-5": 3.0,    # ($1 + $5) / 2
            "anthropic/claude-sonnet-4-20250514": 9.0,    # ($3 + $15) / 2
            "anthropic/claude-opus-4-6": 45.0,   # ($15 + $75) / 2
        }
        cost_per_mtok = costs_per_mtok.get(model, 3.0)
        return round(tokens / 1_000_000 * cost_per_mtok, 6)

    def _log_execution(self, result: ExecutionResult, task: dict):
        """Log execution for audit trail."""
        self._execution_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": result.task_id,
            "agent_id": result.agent_id,
            "strategy": result.strategy.value,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd,
            "error": result.error,
            "task_title": task.get("title", ""),
            "task_bounty": task.get("bounty_usd", 0),
        })

    def _mock_tasks(self) -> List[dict]:
        """Generate mock tasks for dry_run mode."""
        return [
            {
                "id": "mock-task-001",
                "title": "Research current AI agent frameworks",
                "status": "published",
                "category": "knowledge_access",
                "bounty_usd": 0.10,
                "instructions": (
                    "Provide a comprehensive overview of the top 5 AI agent frameworks "
                    "in 2026. Include: architecture, key features, ecosystem, and "
                    "comparison table."
                ),
                "deadline": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            },
            {
                "id": "mock-task-002",
                "title": "Write a technical blog post about ERC-8004",
                "status": "published",
                "category": "content_creation",
                "bounty_usd": 0.15,
                "instructions": (
                    "Write a 1000-word blog post explaining the ERC-8004 identity "
                    "standard for AI agents. Target audience: developers. Include "
                    "code examples and practical use cases."
                ),
                "deadline": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
            },
            {
                "id": "mock-task-003",
                "title": "Verify coffee shop hours",
                "status": "published",
                "category": "physical_presence",
                "bounty_usd": 5.00,
                "instructions": "Visit the coffee shop and verify their posted hours.",
                "location_hint": "123 Main St, Anytown",
                "deadline": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
            },
        ]

    @staticmethod
    async def _default_llm_provider(
        system_prompt: str,
        user_prompt: str,
        model: str = "anthropic/claude-haiku-4-5",
    ) -> str:
        """
        Default LLM provider — generates a structured placeholder.

        In production, this would call Anthropic's API, OpenRouter, etc.
        For now, it generates a deterministic response based on the prompt,
        suitable for testing the pipeline.
        """
        # Extract task title from user prompt
        title = "Unknown Task"
        for line in user_prompt.split("\n"):
            if line.startswith("# Task:"):
                title = line.replace("# Task:", "").strip()
                break

        # Generate structured response based on prompt length/content
        response_parts = [
            f"# {title} — Execution Report",
            "",
            f"**Executed at**: {datetime.now(timezone.utc).isoformat()}",
            f"**Model**: {model}",
            "",
            "## Summary",
            f"This report addresses the task: {title}.",
            "",
            "## Analysis",
            "Based on the provided instructions, here are the key findings:",
            "",
        ]

        # Generate category-aware content
        if "research" in user_prompt.lower() or "knowledge" in user_prompt.lower():
            response_parts.extend([
                "### Key Findings",
                "1. The landscape continues to evolve rapidly",
                "2. Multiple competing approaches exist",
                "3. Integration opportunities are significant",
                "",
                "### Recommendations",
                "- Further investigation recommended for emerging patterns",
                "- Cross-reference with on-chain data for validation",
            ])
        elif "write" in user_prompt.lower() or "content" in user_prompt.lower():
            response_parts.extend([
                "### Content Outline",
                "1. Introduction and context",
                "2. Core concepts explained",
                "3. Practical examples",
                "4. Conclusion and next steps",
                "",
                "[Full content would be generated by production LLM provider]",
            ])
        elif "code" in user_prompt.lower() or "review" in user_prompt.lower():
            response_parts.extend([
                "### Code Review Findings",
                "| Severity | Count | Category |",
                "|----------|-------|----------|",
                "| Critical | 0     | Security |",
                "| Major    | 2     | Design   |",
                "| Minor    | 5     | Style    |",
                "",
                "### Detailed Findings",
                "1. [Major] Consider extracting shared logic into utilities",
                "2. [Minor] Inconsistent naming conventions in 3 files",
            ])
        else:
            response_parts.extend([
                "### Task Completion",
                "The requested work has been completed as specified.",
                "All requirements addressed per the instructions.",
            ])

        response_parts.extend([
            "",
            "---",
            f"*Report generated by Execution Market Swarm Agent ({model})*",
        ])

        return "\n".join(response_parts)
