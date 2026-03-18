"""
Tests for SwarmTaskExecutor — The Autonomous Execution Engine

Tests the full execution pipeline:
- Planning: strategy selection, prompt building, context injection
- Execution: LLM direct, LLM with tools, hybrid, human routing
- API integration: task acceptance, evidence submission
- Statistics: tracking, cost estimation, execution logging
- Pipeline E2E: fetch → assign → execute → submit → complete
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from lib.swarm.task_executor import (
    SwarmTaskExecutor,
    ExecutionResult,
    ExecutionPlan,
    ExecutionStats,
    ExecutionStrategy,
    CATEGORY_STRATEGIES,
)
from lib.swarm.lifecycle_manager import (
    LifecycleManager,
    AgentStatus,
    ResourceBudget,
)
from lib.swarm.reputation_bridge import ReputationBridge
from lib.swarm.swarm_orchestrator import SwarmOrchestrator


# ══════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════


def make_orchestrator(agent_count=5):
    """Create a test orchestrator with agents."""
    lifecycle = LifecycleManager(max_agents=24)
    bridge = ReputationBridge(dry_run=True)
    orch = SwarmOrchestrator(lifecycle=lifecycle, bridge=bridge)

    agents = [
        ("aurora", "explorer", ["research", "documentation", "analysis"]),
        ("blaze", "creator", ["writing", "creativity", "documentation"]),
        ("cipher", "auditor", ["code_review", "security", "testing"]),
        ("delta", "collector", ["research", "data_entry", "field_work"]),
        ("echo", "communicator", ["languages", "communication", "documentation"]),
    ]

    for agent_id, personality, skills in agents[:agent_count]:
        orch.register_agent(
            agent_id=agent_id,
            wallet=f"0x{agent_id}1234567890abcdef",
            personality=personality,
            skills=skills,
            specializations=[],
            model="anthropic/claude-haiku-4-5",
        )
        lifecycle.boot_agent(agent_id)
        lifecycle.activate_agent(agent_id)

    return orch


def make_task(
    task_id="task-001",
    title="Test task",
    category="knowledge_access",
    bounty=0.10,
    instructions="Complete the task",
    status="published",
):
    """Create a test task dict."""
    return {
        "id": task_id,
        "title": title,
        "status": status,
        "category": category,
        "bounty_usd": bounty,
        "instructions": instructions,
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "agent_id": "2106",
        "executor_id": None,
        "evidence_schema": None,
        "location_hint": None,
        "min_reputation": 0,
    }


async def mock_llm_provider(system_prompt, user_prompt, model="test"):
    """Mock LLM that returns structured responses."""
    return (
        "# Task Report\n\n"
        "## Summary\n"
        "This task has been completed successfully.\n\n"
        "## Details\n"
        "Comprehensive analysis performed as requested.\n"
        "All requirements addressed.\n\n"
        "## Conclusion\n"
        "Task fully completed with high confidence."
    )


async def mock_empty_llm(system_prompt, user_prompt, model="test"):
    """Mock LLM that returns empty response."""
    return ""


async def mock_error_llm(system_prompt, user_prompt, model="test"):
    """Mock LLM that raises an error."""
    raise RuntimeError("LLM service unavailable")


# ══════════════════════════════════════════════
# Strategy Selection Tests
# ══════════════════════════════════════════════


class TestStrategySelection:
    """Test that categories map to correct execution strategies."""

    def test_knowledge_access_is_llm_direct(self):
        assert CATEGORY_STRATEGIES["knowledge_access"] == ExecutionStrategy.LLM_DIRECT

    def test_content_creation_is_llm_direct(self):
        assert CATEGORY_STRATEGIES["content_creation"] == ExecutionStrategy.LLM_DIRECT

    def test_code_review_is_llm_with_tools(self):
        assert CATEGORY_STRATEGIES["code_review"] == ExecutionStrategy.LLM_WITH_TOOLS

    def test_research_is_llm_with_tools(self):
        assert CATEGORY_STRATEGIES["research"] == ExecutionStrategy.LLM_WITH_TOOLS

    def test_physical_presence_is_human_route(self):
        assert CATEGORY_STRATEGIES["physical_presence"] == ExecutionStrategy.HUMAN_ROUTE

    def test_photo_verification_is_human_route(self):
        assert CATEGORY_STRATEGIES["photo_verification"] == ExecutionStrategy.HUMAN_ROUTE

    def test_data_collection_is_hybrid(self):
        assert CATEGORY_STRATEGIES["data_collection"] == ExecutionStrategy.HYBRID

    def test_translation_is_llm_direct(self):
        assert CATEGORY_STRATEGIES["translation"] == ExecutionStrategy.LLM_DIRECT

    def test_unknown_category_defaults_to_llm_direct(self):
        """Unknown categories should default to LLM_DIRECT."""
        strat = CATEGORY_STRATEGIES.get("unknown_category", ExecutionStrategy.LLM_DIRECT)
        assert strat == ExecutionStrategy.LLM_DIRECT


# ══════════════════════════════════════════════
# Execution Plan Tests
# ══════════════════════════════════════════════


class TestExecutionPlanning:
    """Test execution plan building."""

    @pytest.mark.asyncio
    async def test_plan_knowledge_task(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(category="knowledge_access")
        plan = await executor._plan_execution(task, "aurora")

        assert plan.strategy == ExecutionStrategy.LLM_DIRECT
        assert plan.can_execute is True
        assert "Knowledge Access" in plan.system_prompt
        assert plan.agent_id == "aurora"

    @pytest.mark.asyncio
    async def test_plan_physical_task(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(category="physical_presence")
        plan = await executor._plan_execution(task, "terra")

        assert plan.strategy == ExecutionStrategy.HUMAN_ROUTE
        assert plan.can_execute is True

    @pytest.mark.asyncio
    async def test_plan_code_review_task(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(category="code_review", title="Review auth module")
        plan = await executor._plan_execution(task, "cipher")

        assert plan.strategy == ExecutionStrategy.LLM_WITH_TOOLS
        assert plan.can_execute is True

    @pytest.mark.asyncio
    async def test_plan_includes_task_details(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(
            title="Analyze market trends",
            instructions="Focus on DeFi protocols",
            bounty=0.50,
        )
        plan = await executor._plan_execution(task, "aurora")

        assert "Analyze market trends" in plan.user_prompt
        assert "Focus on DeFi protocols" in plan.user_prompt
        assert "$0.5" in plan.user_prompt

    @pytest.mark.asyncio
    async def test_plan_with_context_injector(self):
        mock_injector = AsyncMock()
        mock_injector.build_agent_context.return_value = "## Agent aurora: Explorer (Score: 85/100)"
        executor = SwarmTaskExecutor(
            context_injector=mock_injector,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )
        task = make_task()
        plan = await executor._plan_execution(task, "aurora")

        assert "Agent aurora" in plan.system_prompt or plan.context_block
        mock_injector.build_agent_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_handles_context_injector_failure(self):
        mock_injector = AsyncMock()
        mock_injector.build_agent_context.side_effect = Exception("Bridge down")
        executor = SwarmTaskExecutor(
            context_injector=mock_injector,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )
        task = make_task()
        plan = await executor._plan_execution(task, "aurora")

        # Should still work, just with degraded context
        assert plan.can_execute is True
        assert "Bridge down" in plan.context_block


# ══════════════════════════════════════════════
# Execution Tests
# ══════════════════════════════════════════════


class TestLLMDirectExecution:
    """Test LLM direct execution strategy."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(title="Research AI frameworks")
        result = await executor.execute_task(task, "aurora")

        assert result.success is True
        assert result.strategy == ExecutionStrategy.LLM_DIRECT
        assert result.result_type == "text_response"
        assert len(result.result_data) > 50
        assert result.agent_id == "aurora"
        assert result.duration_ms >= 0  # May be 0ms for fast mock execution

    @pytest.mark.asyncio
    async def test_empty_llm_response_fails(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_empty_llm)
        task = make_task()
        result = await executor.execute_task(task, "aurora")

        assert result.success is False
        assert "empty" in result.error.lower() or "trivial" in result.error.lower()

    @pytest.mark.asyncio
    async def test_llm_error_with_retry(self):
        call_count = 0

        async def flaky_llm(system_prompt, user_prompt, model="test"):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise RuntimeError("Temporary error")
            return "# Success\nCompleted after retry."

        executor = SwarmTaskExecutor(
            dry_run=True,
            llm_provider=flaky_llm,
            max_retries=2,
        )
        task = make_task()
        result = await executor.execute_task(task, "aurora")

        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_llm_error_exhausts_retries(self):
        executor = SwarmTaskExecutor(
            dry_run=True,
            llm_provider=mock_error_llm,
            max_retries=2,
        )
        task = make_task()
        result = await executor.execute_task(task, "aurora")

        assert result.success is False
        assert "attempts failed" in result.error.lower()


class TestLLMWithToolsExecution:
    """Test LLM with tools execution strategy."""

    @pytest.mark.asyncio
    async def test_code_review_adds_guidelines(self):
        captured_prompts = {}

        async def capturing_llm(system_prompt, user_prompt, model="test"):
            captured_prompts["system"] = system_prompt
            return "# Code Review Report\nNo critical issues found."

        executor = SwarmTaskExecutor(dry_run=True, llm_provider=capturing_llm)
        task = make_task(category="code_review", title="Review auth module")
        result = await executor.execute_task(task, "cipher")

        assert result.success is True
        assert result.strategy == ExecutionStrategy.LLM_WITH_TOOLS
        assert "security vulnerabilities" in captured_prompts["system"].lower()

    @pytest.mark.asyncio
    async def test_research_adds_guidelines(self):
        captured_prompts = {}

        async def capturing_llm(system_prompt, user_prompt, model="test"):
            captured_prompts["system"] = system_prompt
            return "# Research Findings\nKey insight: ..."

        executor = SwarmTaskExecutor(dry_run=True, llm_provider=capturing_llm)
        task = make_task(category="research", title="DeFi protocol analysis")
        result = await executor.execute_task(task, "aurora")

        assert result.success is True
        assert "cite" in captured_prompts["system"].lower()


class TestHybridExecution:
    """Test hybrid execution strategy."""

    @pytest.mark.asyncio
    async def test_web_data_task_uses_llm(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(
            category="data_collection",
            title="Compile DeFi TVL data",
            instructions="Gather total value locked across protocols",
        )
        result = await executor.execute_task(task, "delta")

        # No physical keywords + no location → should use LLM
        assert result.success is True
        assert not result.routed_to_human

    @pytest.mark.asyncio
    async def test_physical_data_task_routes_to_human(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(
            category="data_collection",
            title="Visit and photograph store prices",
            instructions="Check prices at local store",
        )
        task["location_hint"] = "123 Main St"
        result = await executor.execute_task(task, "delta")

        assert result.routed_to_human is True


class TestHumanRouting:
    """Test human routing strategy."""

    @pytest.mark.asyncio
    async def test_physical_task_routes_to_human(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(category="physical_presence", title="Verify store hours")
        result = await executor.execute_task(task, "terra")

        assert result.routed_to_human is True
        assert result.success is False  # Not failure, just not our job
        assert result.error is None
        assert "human" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_photo_verification_routes_to_human(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(category="photo_verification", title="Take photo of building")
        result = await executor.execute_task(task, "kite")

        assert result.routed_to_human is True


# ══════════════════════════════════════════════
# Orchestrator Integration Tests
# ══════════════════════════════════════════════


class TestOrchestratorIntegration:
    """Test executor with SwarmOrchestrator."""

    @pytest.mark.asyncio
    async def test_execute_reports_completion_to_orchestrator(self):
        orch = make_orchestrator()
        executor = SwarmTaskExecutor(
            orchestrator=orch,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )

        task = make_task(bounty=0.10)
        # Pre-assign the task in orchestrator
        assignment = await orch.assign_task("task-001", category="knowledge_access")
        agent_id = assignment.assigned_agent

        result = await executor.execute_task(task, agent_id)

        assert result.success is True
        # Orchestrator should record completion
        assert orch.total_tasks_completed == 1
        assert orch.total_usd_earned == 0.10

    @pytest.mark.asyncio
    async def test_failed_execution_reports_to_orchestrator(self):
        orch = make_orchestrator()
        executor = SwarmTaskExecutor(
            orchestrator=orch,
            dry_run=True,
            llm_provider=mock_empty_llm,
        )

        task = make_task()

        # Pre-track task in orchestrator so complete_task has something to find
        orch.active_tasks[task["id"]] = "aurora"

        result = await executor.execute_task(task, "aurora")

        assert result.success is False
        # Orchestrator records the attempt via complete_task (success=False, $0 earned)
        assert orch.total_tasks_completed == 1
        assert orch.total_usd_earned == 0.0


# ══════════════════════════════════════════════
# Statistics & Logging Tests
# ══════════════════════════════════════════════


class TestExecutionStats:
    """Test execution statistics tracking."""

    def test_empty_stats(self):
        stats = ExecutionStats()
        assert stats.total_executed == 0
        assert stats.success_rate == 0.0

    def test_record_success(self):
        stats = ExecutionStats()
        result = ExecutionResult(
            task_id="t1", agent_id="a1", strategy=ExecutionStrategy.LLM_DIRECT,
            success=True, tokens_used=1000, cost_usd=0.003, duration_ms=500,
        )
        stats.record(result, bounty_usd=0.10)

        assert stats.total_executed == 1
        assert stats.total_success == 1
        assert stats.total_earnings_usd == 0.10
        assert stats.total_tokens == 1000
        assert stats.success_rate == 1.0

    def test_record_failure(self):
        stats = ExecutionStats()
        result = ExecutionResult(
            task_id="t1", agent_id="a1", strategy=ExecutionStrategy.LLM_DIRECT,
            success=False, error="LLM failed", duration_ms=100,
        )
        stats.record(result)

        assert stats.total_failed == 1
        assert stats.total_earnings_usd == 0.0
        assert stats.success_rate == 0.0

    def test_record_human_routed(self):
        stats = ExecutionStats()
        result = ExecutionResult(
            task_id="t1", agent_id="a1", strategy=ExecutionStrategy.HUMAN_ROUTE,
            success=False, routed_to_human=True, duration_ms=10,
        )
        stats.record(result)

        assert stats.total_routed_to_human == 1
        # Human-routed shouldn't count against success rate
        assert stats.success_rate == 0.0  # No executable tasks

    def test_mixed_stats(self):
        stats = ExecutionStats()

        # 3 successes
        for i in range(3):
            stats.record(ExecutionResult(
                task_id=f"s{i}", agent_id="a1", strategy=ExecutionStrategy.LLM_DIRECT,
                success=True, tokens_used=500, cost_usd=0.001, duration_ms=300,
            ), bounty_usd=0.10)

        # 1 failure
        stats.record(ExecutionResult(
            task_id="f1", agent_id="a1", strategy=ExecutionStrategy.LLM_DIRECT,
            success=False, error="timeout", duration_ms=5000,
        ))

        # 1 human route
        stats.record(ExecutionResult(
            task_id="h1", agent_id="a1", strategy=ExecutionStrategy.HUMAN_ROUTE,
            success=False, routed_to_human=True, duration_ms=10,
        ))

        assert stats.total_executed == 5
        assert stats.total_success == 3
        assert stats.total_failed == 1
        assert stats.total_routed_to_human == 1
        assert stats.success_rate == 0.75  # 3 / (5 - 1 human) = 3/4
        assert abs(stats.total_earnings_usd - 0.30) < 0.001  # Float comparison
        assert stats.total_tokens == 1500

    def test_stats_to_dict(self):
        stats = ExecutionStats()
        d = stats.to_dict()
        assert "total_executed" in d
        assert "success_rate" in d
        assert "_durations" not in d  # Private field excluded

    @pytest.mark.asyncio
    async def test_executor_tracks_stats(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)

        for i in range(3):
            task = make_task(task_id=f"task-{i}", title=f"Research task {i}")
            await executor.execute_task(task, "aurora")

        stats = executor.get_stats()
        assert stats["total_executed"] == 3
        assert stats["total_success"] == 3

    @pytest.mark.asyncio
    async def test_executor_logs_executions(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(title="Important research")
        await executor.execute_task(task, "aurora")

        log = executor.get_execution_log()
        assert len(log) == 1
        assert log[0]["task_title"] == "Important research"
        assert log[0]["success"] is True
        assert "timestamp" in log[0]


# ══════════════════════════════════════════════
# Prompt Building Tests
# ══════════════════════════════════════════════


class TestPromptBuilding:
    """Test system and user prompt construction."""

    def test_system_prompt_includes_agent_id(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        prompt = executor._build_system_prompt("aurora", "knowledge_access")
        assert "aurora" in prompt

    def test_system_prompt_includes_category_guidance(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        prompt = executor._build_system_prompt("cipher", "code_review")
        assert "Code Review" in prompt

    def test_system_prompt_includes_context_block(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        prompt = executor._build_system_prompt("aurora", "research", "Custom context here")
        assert "Custom context here" in prompt

    def test_user_prompt_includes_title(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        prompt = executor._build_user_prompt("Analyze DeFi", "Study protocols", {})
        assert "Analyze DeFi" in prompt

    def test_user_prompt_includes_instructions(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        prompt = executor._build_user_prompt("Title", "Do specific thing", {})
        assert "Do specific thing" in prompt

    def test_user_prompt_includes_bounty(self):
        executor = SwarmTaskExecutor(dry_run=True, llm_provider=mock_llm_provider)
        task = make_task(bounty=1.50)
        prompt = executor._build_user_prompt(
            task["title"], task["instructions"], task
        )
        assert "1.5" in prompt


# ══════════════════════════════════════════════
# Cost Estimation Tests
# ══════════════════════════════════════════════


class TestCostEstimation:
    """Test cost estimation logic."""

    def test_haiku_cost(self):
        orch = make_orchestrator(1)
        executor = SwarmTaskExecutor(orchestrator=orch, dry_run=True)
        cost = executor._estimate_cost(1_000_000, "aurora")  # aurora uses haiku
        assert cost == 3.0  # $3 per million tokens

    def test_zero_tokens(self):
        executor = SwarmTaskExecutor(dry_run=True)
        cost = executor._estimate_cost(0, "any_agent")
        assert cost == 0.0

    def test_small_task_cost(self):
        executor = SwarmTaskExecutor(dry_run=True)
        cost = executor._estimate_cost(2000, "any_agent")
        assert cost < 0.01  # Very cheap for small tasks


# ══════════════════════════════════════════════
# Evidence Type Selection Tests
# ══════════════════════════════════════════════


class TestEvidenceTypeSelection:
    """Test evidence type selection based on task schema."""

    def test_default_is_text_response(self):
        executor = SwarmTaskExecutor(dry_run=True)
        task = make_task()
        assert executor._pick_evidence_type(task) == "text_response"

    def test_schema_with_text_response(self):
        executor = SwarmTaskExecutor(dry_run=True)
        task = make_task()
        task["evidence_schema"] = {"required_types": ["text_response", "document"]}
        assert executor._pick_evidence_type(task) == "text_response"

    def test_schema_with_document_only(self):
        executor = SwarmTaskExecutor(dry_run=True)
        task = make_task()
        task["evidence_schema"] = {"required_types": ["document"]}
        assert executor._pick_evidence_type(task) == "document"

    def test_schema_with_unknown_type(self):
        executor = SwarmTaskExecutor(dry_run=True)
        task = make_task()
        task["evidence_schema"] = {"required_types": ["custom_type"]}
        assert executor._pick_evidence_type(task) == "custom_type"


# ══════════════════════════════════════════════
# Full Pipeline E2E Tests
# ══════════════════════════════════════════════


class TestFullPipeline:
    """End-to-end pipeline tests with orchestrator + executor."""

    @pytest.mark.asyncio
    async def test_full_pipeline_dry_run(self):
        """Full pipeline: bootstrap → fetch → assign → execute → complete."""
        orch = make_orchestrator()
        executor = SwarmTaskExecutor(
            orchestrator=orch,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )

        # Process all available tasks (mock tasks in dry_run)
        results = await executor.process_available_tasks()

        # Should have processed some tasks (mock includes knowledge + content + physical)
        assert len(results) >= 1

        # At least one success (knowledge/content tasks)
        successes = [r for r in results if r.success]
        assert len(successes) >= 1

        # Stats should be updated
        stats = executor.get_stats()
        assert stats["total_executed"] > 0

    @pytest.mark.asyncio
    async def test_pipeline_skips_human_tasks(self):
        """Pipeline should skip tasks requiring human presence."""
        orch = make_orchestrator()
        executor = SwarmTaskExecutor(
            orchestrator=orch,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )

        results = await executor.process_available_tasks()

        # Mock tasks include physical_presence — should be skipped (not even attempted)
        task_ids = [r.task_id for r in results]
        assert "mock-task-003" not in task_ids  # Physical task skipped in process loop

    @pytest.mark.asyncio
    async def test_pipeline_with_category_filter(self):
        """Pipeline can filter by category."""
        orch = make_orchestrator()
        executor = SwarmTaskExecutor(
            orchestrator=orch,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )

        results = await executor.process_available_tasks(
            categories=["knowledge_access"]
        )

        # Should only process knowledge tasks
        for r in results:
            if r.success:
                assert r.strategy == ExecutionStrategy.LLM_DIRECT

    @pytest.mark.asyncio
    async def test_pipeline_multiple_agents(self):
        """Multiple tasks should be distributed across agents."""
        orch = make_orchestrator(5)
        executor = SwarmTaskExecutor(
            orchestrator=orch,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )

        # Execute multiple tasks
        tasks = [
            make_task(task_id=f"multi-{i}", title=f"Research task {i}")
            for i in range(5)
        ]

        results = []
        for task in tasks:
            assignment = await orch.assign_task(
                task_id=task["id"],
                category="knowledge_access",
            )
            if assignment.assigned_agent:
                r = await executor.execute_task(task, assignment.assigned_agent)
                results.append(r)

        assert len(results) == 5
        assert all(r.success for r in results)

        # Check that orchestrator tracked all completions
        assert orch.total_tasks_completed == 5

    @pytest.mark.asyncio
    async def test_pipeline_economics(self):
        """Pipeline should track economics through orchestrator."""
        orch = make_orchestrator()
        executor = SwarmTaskExecutor(
            orchestrator=orch,
            dry_run=True,
            llm_provider=mock_llm_provider,
        )

        # Execute 3 tasks with different bounties
        # Pre-track tasks so orchestrator.complete_task can find them
        bounties = [0.10, 0.25, 0.50]
        for i, bounty in enumerate(bounties):
            task_id = f"econ-{i}"
            orch.active_tasks[task_id] = "aurora"
            task = make_task(task_id=task_id, bounty=bounty)
            await executor.execute_task(task, "aurora")

        # Check economics
        summary = orch.economic_summary()
        assert summary["total_completed"] == 3
        assert abs(summary["total_earned_usd"] - 0.85) < 0.001

        # Executor stats should also reflect this
        stats = executor.get_stats()
        assert stats["total_success"] == 3


# ══════════════════════════════════════════════
# Default LLM Provider Tests
# ══════════════════════════════════════════════


class TestDefaultLLMProvider:
    """Test the built-in default LLM provider."""

    @pytest.mark.asyncio
    async def test_generates_structured_response(self):
        response = await SwarmTaskExecutor._default_llm_provider(
            system_prompt="You are an agent",
            user_prompt="# Task: Research AI frameworks\n## Instructions\nAnalyze top 5",
        )
        assert "Research AI frameworks" in response
        assert len(response) > 100

    @pytest.mark.asyncio
    async def test_research_content_detected(self):
        response = await SwarmTaskExecutor._default_llm_provider(
            system_prompt="You are an agent",
            user_prompt="# Task: Research DeFi\n## Instructions\nResearch the latest",
        )
        assert "findings" in response.lower() or "recommendations" in response.lower()

    @pytest.mark.asyncio
    async def test_code_review_content_detected(self):
        response = await SwarmTaskExecutor._default_llm_provider(
            system_prompt="You are an agent",
            user_prompt="# Task: Code Review\n## Instructions\nReview this code module",
        )
        assert "review" in response.lower()

    @pytest.mark.asyncio
    async def test_content_creation_detected(self):
        response = await SwarmTaskExecutor._default_llm_provider(
            system_prompt="You are an agent",
            user_prompt="# Task: Write Blog Post\n## Instructions\nWrite about ERC-8004",
        )
        assert "content" in response.lower() or "outline" in response.lower()


# ══════════════════════════════════════════════
# Mock Tasks Tests
# ══════════════════════════════════════════════


class TestMockTasks:
    """Test the dry_run mock task generation."""

    def test_mock_tasks_generated(self):
        executor = SwarmTaskExecutor(dry_run=True)
        tasks = executor._mock_tasks()

        assert len(tasks) == 3
        assert tasks[0]["category"] == "knowledge_access"
        assert tasks[1]["category"] == "content_creation"
        assert tasks[2]["category"] == "physical_presence"

    def test_mock_tasks_have_required_fields(self):
        executor = SwarmTaskExecutor(dry_run=True)
        tasks = executor._mock_tasks()

        for task in tasks:
            assert "id" in task
            assert "title" in task
            assert "status" in task
            assert "category" in task
            assert "bounty_usd" in task
            assert "instructions" in task


# ══════════════════════════════════════════════
# ExecutionResult Tests
# ══════════════════════════════════════════════


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_to_dict(self):
        result = ExecutionResult(
            task_id="t1",
            agent_id="aurora",
            strategy=ExecutionStrategy.LLM_DIRECT,
            success=True,
            result_data="Some data",
            duration_ms=500,
        )
        d = result.to_dict()
        assert d["task_id"] == "t1"
        assert d["success"] is True
        assert isinstance(d, dict)

    def test_default_values(self):
        result = ExecutionResult(
            task_id="t1",
            agent_id="a1",
            strategy=ExecutionStrategy.LLM_DIRECT,
            success=True,
        )
        assert result.result_type == "text_response"
        assert result.tokens_used == 0
        assert result.routed_to_human is False
        assert result.error is None
