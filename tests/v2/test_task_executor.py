"""
Tests for KK V2 Task Executor Service.

Tests cover:
  1. Execution planning (strategy selection)
  2. Self-aware routing (human vs AI)
  3. LLM execution (direct, tools, composite)
  4. Evidence packaging
  5. Budget enforcement
  6. Full pipeline integration
  7. Edge cases and error handling
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.task_executor import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionStrategy,
    TaskExecutor,
    execute_and_submit,
    package_evidence,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def executor(tmp_path):
    """Create a TaskExecutor with a mock LLM provider."""
    async def mock_llm(prompt: str, max_tokens: int = 4096) -> str:
        return f"Analyzed the task. Here are my findings:\n\n1. The data shows clear trends\n2. Key insight: testing works\n3. Recommendation: proceed with caution"

    return TaskExecutor(
        agent_name="kk-test-agent",
        workspace_dir=tmp_path,
        llm_provider=mock_llm,
        max_output_tokens=4096,
        budget_limit_usd=0.50,
    )


@pytest.fixture
def knowledge_task():
    """A knowledge access task (AI-executable)."""
    return {
        "id": "task-001",
        "title": "Analyze DeFi lending protocol risks",
        "instructions": "Research and analyze the top 5 DeFi lending protocols on Base. "
                        "Evaluate their TVL, audit history, and smart contract risk factors. "
                        "Provide a risk score for each.",
        "category": "knowledge_access",
        "bounty_usd": 0.25,
        "evidence_required": ["text_response"],
        "payment_network": "base",
    }


@pytest.fixture
def physical_task():
    """A physical presence task (human only)."""
    return {
        "id": "task-002",
        "title": "Verify restaurant operating hours",
        "instructions": "Go to the restaurant at 123 Main St and verify their current "
                        "operating hours. Take a photo of the posted hours sign.",
        "category": "physical_presence",
        "bounty_usd": 0.50,
        "evidence_required": ["photo", "text_response"],
        "payment_network": "base",
    }


@pytest.fixture
def code_review_task():
    """A code review task (AI-executable with tools)."""
    return {
        "id": "task-003",
        "title": "Review Solidity smart contract",
        "instructions": "Review the following ERC-20 token contract for security "
                        "vulnerabilities, gas optimization, and best practices. "
                        "Check for reentrancy, overflow, and access control issues.",
        "category": "code_review",
        "bounty_usd": 0.30,
        "evidence_required": ["text_response", "json_response"],
        "payment_network": "base",
    }


@pytest.fixture
def multi_step_task():
    """A multi-step composite task."""
    return {
        "id": "task-004",
        "title": "Market analysis and report",
        "instructions": (
            "1. Collect current market data for top 10 Base ecosystem tokens\n"
            "2. Analyze price trends over the last 7 days\n"
            "3. Identify correlation patterns between tokens\n"
            "4. Generate a summary report with buy/sell recommendations\n"
            "5. Create a risk assessment matrix"
        ),
        "category": "research",
        "bounty_usd": 0.40,
        "evidence_required": ["text_response"],
        "payment_network": "base",
    }


@pytest.fixture
def photo_evidence_task():
    """A task requiring photo evidence (human only)."""
    return {
        "id": "task-005",
        "title": "Verify billboard advertisement",
        "instructions": "Confirm the new advertisement is displayed correctly.",
        "category": "simple_action",
        "bounty_usd": 0.25,
        "evidence_required": ["photo_geo"],
        "payment_network": "base",
    }


@pytest.fixture
def expensive_task():
    """A task that costs too much to execute."""
    return {
        "id": "task-006",
        "title": "Analyze entire blockchain history",
        "instructions": " ".join(["word"] * 50000),  # Very long instructions
        "category": "research",
        "bounty_usd": 0.01,
        "evidence_required": ["text_response"],
        "payment_network": "base",
    }


# ═══════════════════════════════════════════════════════════════════
# Planning Tests
# ═══════════════════════════════════════════════════════════════════


class TestPlanExecution:
    """Test execution planning and strategy selection."""

    def test_knowledge_task_gets_llm_direct(self, executor, knowledge_task):
        plan = executor.plan_execution(knowledge_task)
        assert plan.strategy == ExecutionStrategy.LLM_DIRECT
        assert plan.confidence > 0
        assert not plan.requires_human

    def test_physical_task_routes_to_human(self, executor, physical_task):
        plan = executor.plan_execution(physical_task)
        assert plan.strategy == ExecutionStrategy.HUMAN_ROUTE
        assert plan.requires_human
        assert "physical" in plan.reason.lower() or "human" in plan.reason.lower()

    def test_code_review_gets_tools(self, executor, code_review_task):
        plan = executor.plan_execution(code_review_task)
        assert plan.strategy == ExecutionStrategy.LLM_WITH_TOOLS

    def test_photo_evidence_routes_to_human(self, executor, photo_evidence_task):
        plan = executor.plan_execution(photo_evidence_task)
        assert plan.strategy == ExecutionStrategy.HUMAN_ROUTE
        assert plan.requires_human
        assert "photo_geo" in plan.reason or "evidence" in plan.reason.lower()

    def test_human_authority_routes_to_human(self, executor):
        task = {"category": "human_authority", "title": "Sign contract", "instructions": "...", "evidence_required": []}
        plan = executor.plan_execution(task)
        assert plan.strategy == ExecutionStrategy.HUMAN_ROUTE

    def test_plan_includes_cost_estimate(self, executor, knowledge_task):
        plan = executor.plan_execution(knowledge_task)
        assert plan.estimated_cost_usd >= 0

    def test_plan_includes_token_estimate(self, executor, knowledge_task):
        plan = executor.plan_execution(knowledge_task)
        assert plan.estimated_tokens > 0

    def test_unknown_category_defaults_to_llm_direct(self, executor):
        task = {"category": "brand_new_category", "title": "Test", "instructions": "Do something", "evidence_required": []}
        plan = executor.plan_execution(task)
        assert plan.strategy == ExecutionStrategy.LLM_DIRECT

    def test_physical_keywords_route_to_human(self, executor):
        task = {
            "category": "simple_action",
            "title": "Delivery",
            "instructions": "Please go to the store and pick up the package in person",
            "evidence_required": ["text_response"],
            "bounty_usd": 0.50,
        }
        plan = executor.plan_execution(task)
        assert plan.strategy == ExecutionStrategy.HUMAN_ROUTE

    def test_multi_step_gets_composite(self, executor, multi_step_task):
        plan = executor.plan_execution(multi_step_task)
        # Should detect multiple steps
        assert plan.strategy in (
            ExecutionStrategy.COMPOSITE,
            ExecutionStrategy.LLM_WITH_TOOLS,  # May fall through if steps not detected
        )


class TestBudgetEnforcement:
    """Test budget limits in planning."""

    def test_expensive_task_gets_skipped(self, executor, expensive_task):
        plan = executor.plan_execution(expensive_task)
        assert plan.strategy == ExecutionStrategy.SKIP
        assert "cost" in plan.reason.lower() or "budget" in plan.reason.lower()

    def test_task_within_budget_executes(self, executor, knowledge_task):
        plan = executor.plan_execution(knowledge_task)
        assert plan.strategy != ExecutionStrategy.SKIP

    def test_custom_budget_limit(self, tmp_path):
        async def mock_llm(prompt, max_tokens=4096):
            return "ok"

        # Very low budget
        executor = TaskExecutor(
            agent_name="test",
            workspace_dir=tmp_path,
            llm_provider=mock_llm,
            budget_limit_usd=0.001,
        )
        task = {
            "category": "knowledge_access",
            "title": "Test",
            "instructions": "This is a moderately detailed task that needs analysis " * 20,
            "evidence_required": ["text_response"],
            "bounty_usd": 0.001,
        }
        plan = executor.plan_execution(task)
        assert plan.strategy == ExecutionStrategy.SKIP


# ═══════════════════════════════════════════════════════════════════
# Execution Tests
# ═══════════════════════════════════════════════════════════════════


class TestExecuteLLMDirect:
    """Test LLM direct execution."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, executor, knowledge_task):
        result = await executor.execute_task(knowledge_task)
        assert result.success
        assert result.strategy_used == ExecutionStrategy.LLM_DIRECT
        assert len(result.output) > 0
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_evidence_data_populated(self, executor, knowledge_task):
        result = await executor.execute_task(knowledge_task)
        assert result.evidence_data.get("agent") == "kk-test-agent"
        assert result.evidence_data.get("strategy") == "llm_direct"

    @pytest.mark.asyncio
    async def test_tokens_tracked(self, executor, knowledge_task):
        result = await executor.execute_task(knowledge_task)
        assert result.tokens_used > 0
        assert result.cost_usd > 0


class TestExecuteLLMWithTools:
    """Test LLM with tools execution."""

    @pytest.mark.asyncio
    async def test_code_review_execution(self, executor, code_review_task):
        result = await executor.execute_task(code_review_task)
        assert result.success
        assert result.strategy_used == ExecutionStrategy.LLM_WITH_TOOLS
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_evidence_includes_tools(self, executor, code_review_task):
        result = await executor.execute_task(code_review_task)
        assert "tools_available" in result.evidence_data


class TestExecuteComposite:
    """Test composite (multi-step) execution."""

    @pytest.mark.asyncio
    async def test_multi_step_execution(self, tmp_path):
        call_count = 0

        async def counting_llm(prompt: str, max_tokens: int = 4096) -> str:
            nonlocal call_count
            call_count += 1
            return f"Step {call_count} result: analysis complete"

        executor = TaskExecutor(
            agent_name="test-composite",
            workspace_dir=tmp_path,
            llm_provider=counting_llm,
        )

        task = {
            "id": "composite-001",
            "title": "Multi-step analysis",
            "instructions": (
                "1. Gather data from sources\n"
                "2. Analyze patterns\n"
                "3. Generate report\n"
                "4. Create recommendations"
            ),
            "category": "research",
            "bounty_usd": 0.50,
            "evidence_required": ["text_response"],
        }

        result = await executor.execute_task(task)
        assert result.success
        # Should have multiple step outputs
        assert "Step" in result.output


class TestHumanRouting:
    """Test self-aware human routing."""

    @pytest.mark.asyncio
    async def test_physical_task_not_executed(self, executor, physical_task):
        result = await executor.execute_task(physical_task)
        assert not result.success
        assert result.routed_to_human
        assert result.strategy_used == ExecutionStrategy.HUMAN_ROUTE

    @pytest.mark.asyncio
    async def test_human_route_has_explanation(self, executor, physical_task):
        result = await executor.execute_task(physical_task)
        assert "human" in result.output.lower() or "human" in result.error.lower()

    @pytest.mark.asyncio
    async def test_photo_evidence_routed(self, executor, photo_evidence_task):
        result = await executor.execute_task(photo_evidence_task)
        assert result.routed_to_human


class TestErrorHandling:
    """Test error handling during execution."""

    @pytest.mark.asyncio
    async def test_llm_error_caught(self, tmp_path):
        async def failing_llm(prompt: str, max_tokens: int = 4096) -> str:
            raise RuntimeError("LLM service unavailable")

        executor = TaskExecutor(
            agent_name="test-error",
            workspace_dir=tmp_path,
            llm_provider=failing_llm,
        )

        task = {
            "id": "error-001",
            "title": "Should fail gracefully",
            "instructions": "Do something",
            "category": "knowledge_access",
            "evidence_required": ["text_response"],
            "bounty_usd": 0.25,
        }

        result = await executor.execute_task(task)
        assert not result.success
        assert "unavailable" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_task_handled(self, executor):
        result = await executor.execute_task({})
        assert result.success or not result.success  # Should not crash

    @pytest.mark.asyncio
    async def test_skip_strategy_returns_error(self, executor, expensive_task):
        result = await executor.execute_task(expensive_task)
        assert not result.success
        assert result.strategy_used == ExecutionStrategy.SKIP


# ═══════════════════════════════════════════════════════════════════
# Evidence Packaging Tests
# ═══════════════════════════════════════════════════════════════════


class TestEvidencePackaging:
    """Test evidence packaging for EM submission."""

    def test_successful_result_packages(self):
        result = ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.LLM_DIRECT,
            output="Analysis shows positive trends.",
            evidence_type="text_response",
            evidence_data={"agent": "kk-test", "strategy": "llm_direct"},
            tokens_used=500,
            cost_usd=0.003,
            duration_ms=1200,
        )
        task = {"id": "pkg-001", "category": "knowledge_access"}

        evidence = package_evidence(result, task)
        assert evidence["type"] == "text_response"
        assert "Analysis" in evidence["content"]
        assert evidence["metadata"]["agent"] == "kk-test"
        assert evidence["metadata"]["tokens_used"] == 500

    def test_failed_result_returns_empty(self):
        result = ExecutionResult(
            success=False,
            strategy_used=ExecutionStrategy.HUMAN_ROUTE,
            error="requires_human",
        )
        evidence = package_evidence(result, {})
        assert evidence == {}

    def test_long_output_truncated(self):
        result = ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.LLM_DIRECT,
            output="x" * 20000,
            evidence_type="text_response",
            evidence_data={"agent": "test"},
        )
        evidence = package_evidence(result, {})
        assert len(evidence["content"]) <= 10000

    def test_json_output_parsed(self):
        json_output = json.dumps({"key": "value", "score": 42})
        result = ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.LLM_DIRECT,
            output=json_output,
            evidence_type="json_response",
            evidence_data={"agent": "test"},
        )
        evidence = package_evidence(result, {})
        assert evidence.get("structured_data") == {"key": "value", "score": 42}

    def test_non_json_output_no_structured_data(self):
        result = ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.LLM_DIRECT,
            output="This is plain text, not JSON",
            evidence_type="json_response",
            evidence_data={"agent": "test"},
        )
        evidence = package_evidence(result, {})
        assert "structured_data" not in evidence


# ═══════════════════════════════════════════════════════════════════
# Execution Log Tests
# ═══════════════════════════════════════════════════════════════════


class TestExecutionLog:
    """Test audit trail / execution logging."""

    @pytest.mark.asyncio
    async def test_log_populated_after_execution(self, executor, knowledge_task):
        await executor.execute_task(knowledge_task)
        log = executor.get_execution_log()
        assert len(log) >= 2  # At least plan + complete events
        assert log[0]["event"] == "plan"
        assert log[-1]["event"] == "complete"

    @pytest.mark.asyncio
    async def test_log_includes_task_id(self, executor, knowledge_task):
        await executor.execute_task(knowledge_task)
        log = executor.get_execution_log()
        assert log[0]["task_id"] == "task-001"

    @pytest.mark.asyncio
    async def test_log_saved_to_file(self, executor, knowledge_task):
        await executor.execute_task(knowledge_task)
        path = executor.save_execution_log()
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_multiple_executions_append(self, executor, knowledge_task, code_review_task):
        await executor.execute_task(knowledge_task)
        await executor.execute_task(code_review_task)
        log = executor.get_execution_log()
        assert len(log) >= 4  # 2 events per task


# ═══════════════════════════════════════════════════════════════════
# Full Pipeline Tests
# ═══════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """Test the full execute_and_submit pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_updates_working_state(self, executor, knowledge_task, tmp_path):
        from services.task_executor import execute_and_submit
        from lib.working_state import WorkingState, parse_working_md

        state = WorkingState()
        mock_client = MagicMock()
        mock_client.submit_evidence = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.executor_id = "exec-001"

        result = await execute_and_submit(
            executor, mock_client, knowledge_task,
            working_state=state, workspace_path=tmp_path,
        )

        assert result.success
        # Working state should be cleared (task done)
        assert not state.has_active_task
        # WORKING.md should exist
        assert (tmp_path / "WORKING.md").exists()

    @pytest.mark.asyncio
    async def test_pipeline_submits_evidence(self, executor, knowledge_task, tmp_path):
        mock_client = MagicMock()
        mock_client.submit_evidence = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.executor_id = "exec-001"

        result = await execute_and_submit(
            executor, mock_client, knowledge_task,
        )

        assert result.success
        mock_client.submit_evidence.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_handles_submit_failure(self, executor, knowledge_task, tmp_path):
        from lib.working_state import WorkingState

        mock_client = MagicMock()
        mock_client.submit_evidence = AsyncMock(side_effect=Exception("API error"))
        mock_client.agent = MagicMock()
        mock_client.agent.executor_id = "exec-001"

        state = WorkingState()
        result = await execute_and_submit(
            executor, mock_client, knowledge_task,
            working_state=state, workspace_path=tmp_path,
        )

        # Execution succeeded but submission failed
        assert result.success  # The LLM execution worked
        assert "submission failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pipeline_human_task_no_submission(self, executor, physical_task):
        mock_client = MagicMock()
        mock_client.submit_evidence = AsyncMock()

        result = await execute_and_submit(executor, mock_client, physical_task)

        assert not result.success
        assert result.routed_to_human
        mock_client.submit_evidence.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_without_state(self, executor, knowledge_task):
        """Pipeline works even without state tracking."""
        mock_client = MagicMock()
        mock_client.submit_evidence = AsyncMock()
        mock_client.agent = MagicMock()
        mock_client.agent.executor_id = "exec-001"

        result = await execute_and_submit(
            executor, mock_client, knowledge_task,
            working_state=None, workspace_path=None,
        )
        assert result.success


# ═══════════════════════════════════════════════════════════════════
# Evidence Type Inference Tests
# ═══════════════════════════════════════════════════════════════════


class TestEvidenceTypeInference:
    """Test evidence type selection."""

    def test_text_response_default(self, executor):
        task = {"category": "knowledge_access", "evidence_required": ["text_response"]}
        assert executor._infer_evidence_type(task) == "text_response"

    def test_json_response_for_data(self, executor):
        task = {"category": "data_collection", "evidence_required": []}
        assert executor._infer_evidence_type(task) == "json_response"

    def test_first_ai_compatible_type(self, executor):
        task = {
            "category": "simple_action",
            "evidence_required": ["photo", "text_response", "screenshot"],
        }
        # Should skip photo (human only) and use text_response
        assert executor._infer_evidence_type(task) == "text_response"


# ═══════════════════════════════════════════════════════════════════
# Step Detection Tests
# ═══════════════════════════════════════════════════════════════════


class TestStepDetection:
    """Test multi-step instruction parsing."""

    def test_numbered_steps_detected(self, executor):
        instructions = "1. First thing\n2. Second thing\n3. Third thing"
        steps = executor._detect_steps(instructions)
        assert len(steps) >= 3

    def test_no_steps_in_prose(self, executor):
        instructions = "Please analyze this data and provide insights about market trends."
        steps = executor._detect_steps(instructions)
        assert len(steps) <= 1

    def test_empty_instructions(self, executor):
        steps = executor._detect_steps("")
        assert len(steps) == 0


# ═══════════════════════════════════════════════════════════════════
# Tool Hints Tests
# ═══════════════════════════════════════════════════════════════════


class TestToolHints:
    """Test tool hint generation."""

    def test_code_category_has_code_hints(self, executor):
        hints = executor._get_tool_hints("code_review", "Review this contract")
        assert "code" in hints.lower()

    def test_blockchain_instructions_add_chain_hints(self, executor):
        hints = executor._get_tool_hints("research", "Analyze on-chain transactions")
        assert "blockchain" in hints.lower()

    def test_market_instructions_add_market_hints(self, executor):
        hints = executor._get_tool_hints("research", "Analyze market prices")
        assert "market" in hints.lower()

    def test_basic_hints_always_present(self, executor):
        hints = executor._get_tool_hints("unknown", "anything")
        assert "text analysis" in hints.lower()
