"""
Tests for services/task_pipeline.py — End-to-End Task Pipeline

Tests the full pipeline:
    - PipelineConfig loading
    - TaskCandidate creation and scoring
    - PipelineResult tracking
    - Pipeline stages: discover → evaluate → apply → execute → submit
    - Full run_once cycle
    - Multi-agent SwarmPipelineRunner
    - Budget enforcement
    - Error handling
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from lib.llm_provider import MockProvider
from services.em_client import AgentContext
from services.task_executor import ExecutionStrategy
from services.task_pipeline import (
    PipelineConfig,
    PipelineResult,
    SwarmPipelineRunner,
    TaskCandidate,
    TaskPipeline,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary agent workspace."""
    ws = tmp_path / "test-agent"
    ws.mkdir()
    (ws / "SOUL.md").write_text("# Test Agent\nA test agent for pipeline testing.")
    (ws / "WORKING.md").write_text("# Working State\n\n## Status: idle\n")
    return ws


@pytest.fixture
def agent_context(tmp_workspace):
    return AgentContext(
        name="test-agent",
        wallet_address="0x1234567890abcdef1234567890abcdef12345678",
        workspace_dir=tmp_workspace,
        api_key="test-key",
    )


@pytest.fixture
def mock_em_client():
    client = AsyncMock()
    client.list_tasks = AsyncMock(return_value=[])
    client.apply_to_task = AsyncMock(return_value={"status": "applied"})
    client.submit_evidence = AsyncMock(return_value={"status": "submitted"})
    return client


@pytest.fixture
def mock_llm():
    return MockProvider(
        default_response="Based on analysis: the current trend shows positive momentum.",
        latency_ms=0,
    )


@pytest.fixture
def sample_tasks():
    return [
        {
            "id": "task-001",
            "title": "Analyze DeFi yield trends Q1 2026",
            "instructions": "Research and summarize the top DeFi yield strategies for Q1 2026.",
            "category": "research",
            "bounty_usd": 0.25,
            "evidence_required": ["text_response"],
            "status": "published",
        },
        {
            "id": "task-002",
            "title": "Review smart contract security",
            "instructions": "Audit this Solidity contract for vulnerabilities.",
            "category": "code_review",
            "bounty_usd": 0.50,
            "evidence_required": ["text_response", "document"],
            "status": "published",
        },
        {
            "id": "task-003",
            "title": "Deliver package to warehouse",
            "instructions": "Physically deliver the package to the downtown warehouse.",
            "category": "physical_presence",
            "bounty_usd": 5.00,
            "evidence_required": ["photo_geo"],
            "status": "published",
        },
        {
            "id": "task-004",
            "title": "Translate document to Spanish",
            "instructions": "Translate the attached English document to Spanish.",
            "category": "translation",
            "bounty_usd": 0.15,
            "evidence_required": ["text_response"],
            "status": "published",
        },
        {
            "id": "task-005",
            "title": "Take a photo of the store sign",
            "instructions": "Go to the store and take a photo of the front sign.",
            "category": "data_collection",
            "bounty_usd": 0.30,
            "evidence_required": ["photo"],
            "status": "published",
        },
    ]


# ═══════════════════════════════════════════════════════════════════
# PipelineConfig
# ═══════════════════════════════════════════════════════════════════


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig()
        assert config.per_task_budget_usd == 0.50
        assert config.daily_budget_usd == 5.00
        assert config.min_bounty_usd == 0.05
        assert config.max_tasks_per_cycle == 3
        assert config.continuous_interval_seconds == 300

    def test_from_env(self):
        env = {
            "KK_PER_TASK_BUDGET": "1.00",
            "KK_DAILY_BUDGET": "10.00",
            "KK_MIN_BOUNTY": "0.10",
            "KK_MAX_TASKS_PER_CYCLE": "5",
            "KK_LLM_BACKEND": "openai",
            "KK_DRY_RUN": "1",
        }
        with patch.dict(os.environ, env):
            config = PipelineConfig.from_env()
            assert config.per_task_budget_usd == 1.00
            assert config.daily_budget_usd == 10.00
            assert config.min_bounty_usd == 0.10
            assert config.max_tasks_per_cycle == 5
            assert config.llm_backend == "openai"
            assert config.dry_run is True

    def test_from_file(self, tmp_path):
        config_file = tmp_path / "pipeline_config.json"
        config_file.write_text(json.dumps({
            "per_task_budget_usd": 2.0,
            "daily_budget_usd": 20.0,
            "adaptive_llm": False,
        }))
        config = PipelineConfig.from_file(config_file)
        assert config.per_task_budget_usd == 2.0
        assert config.daily_budget_usd == 20.0
        assert config.adaptive_llm is False

    def test_from_file_missing(self, tmp_path):
        config = PipelineConfig.from_file(tmp_path / "nonexistent.json")
        assert config.per_task_budget_usd == 0.50  # defaults


# ═══════════════════════════════════════════════════════════════════
# PipelineResult
# ═══════════════════════════════════════════════════════════════════


class TestPipelineResult:
    def test_defaults(self):
        r = PipelineResult(
            cycle_id="test-1",
            agent_name="agent-1",
            started_at="2026-02-28T00:00:00Z",
        )
        assert r.tasks_discovered == 0
        assert r.total_cost_usd == 0.0
        assert r.errors == []

    def test_to_dict(self):
        r = PipelineResult(
            cycle_id="test-1",
            agent_name="agent-1",
            started_at="2026-02-28T00:00:00Z",
            completed_at="2026-02-28T00:00:05Z",
            duration_ms=5000,
            tasks_discovered=10,
            tasks_submitted=3,
            total_cost_usd=0.015,
            total_bounty_usd=0.75,
        )
        d = r.to_dict()
        assert d["cycle_id"] == "test-1"
        assert d["tasks_discovered"] == 10
        assert d["tasks_submitted"] == 3
        assert d["total_cost_usd"] == 0.015


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Discovery
# ═══════════════════════════════════════════════════════════════════


class TestPipelineDiscover:
    @pytest.mark.asyncio
    async def test_discover_returns_tasks(self, agent_context, mock_em_client, mock_llm, sample_tasks):
        mock_em_client.list_tasks.return_value = sample_tasks
        config = PipelineConfig(min_bounty_usd=0.05)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)

        tasks = await pipeline.discover_tasks()
        # Should filter out task-003 (physical_presence category excluded)
        assert len(tasks) == 4

    @pytest.mark.asyncio
    async def test_discover_empty_marketplace(self, agent_context, mock_em_client, mock_llm):
        mock_em_client.list_tasks.return_value = []
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)

        tasks = await pipeline.discover_tasks()
        assert tasks == []

    @pytest.mark.asyncio
    async def test_discover_api_error(self, agent_context, mock_em_client, mock_llm):
        mock_em_client.list_tasks.side_effect = ConnectionError("API down")
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)

        tasks = await pipeline.discover_tasks()
        assert tasks == []

    @pytest.mark.asyncio
    async def test_discover_filters_low_bounty(self, agent_context, mock_em_client, mock_llm):
        tasks = [
            {"id": "t1", "title": "Cheap task", "bounty_usd": 0.01, "category": "research", "status": "published"},
            {"id": "t2", "title": "Good task", "bounty_usd": 0.50, "category": "research", "status": "published"},
        ]
        mock_em_client.list_tasks.return_value = tasks
        config = PipelineConfig(min_bounty_usd=0.05)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)

        result = await pipeline.discover_tasks()
        assert len(result) == 1
        assert result[0]["id"] == "t2"


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Evaluation
# ═══════════════════════════════════════════════════════════════════


class TestPipelineEvaluate:
    def test_evaluate_filters_human_tasks(self, agent_context, mock_em_client, mock_llm, sample_tasks):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        candidates = pipeline.evaluate_tasks(sample_tasks)

        # Physical tasks should be filtered
        task_ids = [c.task_id for c in candidates]
        assert "task-003" not in task_ids  # physical_presence
        assert "task-005" not in task_ids  # photo evidence required

    def test_evaluate_sorts_by_score(self, agent_context, mock_em_client, mock_llm, sample_tasks):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        candidates = pipeline.evaluate_tasks(sample_tasks)

        if len(candidates) >= 2:
            scores = [c.match_score for c in candidates]
            assert scores == sorted(scores, reverse=True)

    def test_evaluate_respects_max_per_cycle(self, agent_context, mock_em_client, mock_llm):
        tasks = [
            {
                "id": f"task-{i}",
                "title": f"Task {i}",
                "instructions": f"Do thing {i}",
                "category": "analysis",
                "bounty_usd": 0.25,
                "evidence_required": ["text_response"],
            }
            for i in range(10)
        ]
        config = PipelineConfig(max_tasks_per_cycle=2)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)

        candidates = pipeline.evaluate_tasks(tasks)
        assert len(candidates) <= 2

    def test_evaluate_respects_daily_budget(self, agent_context, mock_em_client, mock_llm):
        tasks = [
            {
                "id": "task-1",
                "title": "Task 1",
                "instructions": "Do thing",
                "category": "analysis",
                "bounty_usd": 0.25,
            }
        ]
        config = PipelineConfig(daily_budget_usd=0.001)  # Nearly exhausted
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)
        pipeline._daily_spent = 0.001  # Almost at budget

        candidates = pipeline.evaluate_tasks(tasks)
        # Should skip because daily budget is exhausted
        assert len(candidates) == 0

    def test_match_score_range(self, agent_context, mock_em_client, mock_llm, sample_tasks):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        candidates = pipeline.evaluate_tasks(sample_tasks)

        for c in candidates:
            assert 0 <= c.match_score <= 1.0

    def test_candidates_have_plans(self, agent_context, mock_em_client, mock_llm, sample_tasks):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        candidates = pipeline.evaluate_tasks(sample_tasks)

        for c in candidates:
            assert c.plan is not None
            assert c.plan.strategy != ExecutionStrategy.HUMAN_ROUTE
            assert c.plan.strategy != ExecutionStrategy.SKIP


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Apply
# ═══════════════════════════════════════════════════════════════════


class TestPipelineApply:
    @pytest.mark.asyncio
    async def test_apply_success(self, agent_context, mock_em_client, mock_llm):
        from services.task_executor import ExecutionPlan
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        candidate = TaskCandidate(
            task_id="task-001",
            title="Test Task",
            category="research",
            bounty_usd=0.25,
            plan=ExecutionPlan(
                strategy=ExecutionStrategy.LLM_DIRECT,
                reason="test",
                confidence=0.8,
                estimated_cost_usd=0.01,
            ),
            match_score=0.8,
        )

        result = await pipeline.apply_to_task(candidate)
        assert result is True
        mock_em_client.apply_to_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_dry_run(self, agent_context, mock_em_client, mock_llm):
        config = PipelineConfig(dry_run=True)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)
        candidate = TaskCandidate(
            task_id="task-001",
            title="Test Task",
            category="research",
            bounty_usd=0.25,
            plan=MagicMock(),
        )

        result = await pipeline.apply_to_task(candidate)
        assert result is True
        mock_em_client.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_failure(self, agent_context, mock_em_client, mock_llm):
        mock_em_client.apply_to_task.side_effect = Exception("API error")
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        candidate = TaskCandidate(
            task_id="task-001",
            title="Test Task",
            category="research",
            bounty_usd=0.25,
            plan=MagicMock(),
        )

        result = await pipeline.apply_to_task(candidate)
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Execute
# ═══════════════════════════════════════════════════════════════════


class TestPipelineExecute:
    @pytest.mark.asyncio
    async def test_execute_task(self, agent_context, mock_em_client, mock_llm, tmp_workspace):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)

        from services.task_executor import ExecutionPlan
        candidate = TaskCandidate(
            task_id="task-001",
            title="Analyze market trends",
            category="analysis",
            bounty_usd=0.25,
            plan=ExecutionPlan(
                strategy=ExecutionStrategy.LLM_DIRECT,
                reason="Category analysis → llm_direct",
                confidence=0.8,
            ),
            raw_task={
                "id": "task-001",
                "title": "Analyze market trends",
                "instructions": "Summarize crypto market trends.",
                "category": "analysis",
                "bounty_usd": 0.25,
                "evidence_required": ["text_response"],
            },
        )

        result = await pipeline.execute_task(candidate)
        assert result.success
        assert result.output  # got some output
        assert mock_llm.stats.total_calls >= 1

    @pytest.mark.asyncio
    async def test_execute_dry_run(self, agent_context, mock_em_client, mock_llm):
        config = PipelineConfig(dry_run=True)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)

        from services.task_executor import ExecutionPlan
        candidate = TaskCandidate(
            task_id="task-001",
            title="Test",
            category="analysis",
            bounty_usd=0.25,
            plan=ExecutionPlan(
                strategy=ExecutionStrategy.LLM_DIRECT,
                reason="test",
                confidence=0.8,
            ),
            raw_task={"id": "task-001", "title": "Test", "category": "analysis"},
        )

        result = await pipeline.execute_task(candidate)
        assert result.success
        assert "DRY RUN" in result.output
        assert mock_llm.stats.total_calls == 0  # no LLM call in dry run


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Submit
# ═══════════════════════════════════════════════════════════════════


class TestPipelineSubmit:
    @pytest.mark.asyncio
    async def test_submit_success(self, agent_context, mock_em_client, mock_llm):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)

        from services.task_executor import ExecutionResult
        candidate = TaskCandidate(
            task_id="task-001",
            title="Test",
            category="analysis",
            bounty_usd=0.25,
            plan=MagicMock(),
            raw_task={"id": "task-001", "category": "analysis"},
        )
        result = ExecutionResult(
            success=True,
            strategy_used=ExecutionStrategy.LLM_DIRECT,
            output="Here is the analysis...",
            evidence_type="text_response",
            evidence_data={"content": "analysis", "agent": "test", "strategy": "llm_direct"},
        )

        submitted = await pipeline.submit_evidence(candidate, result)
        assert submitted is True
        mock_em_client.submit_evidence.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_failed_result(self, agent_context, mock_em_client, mock_llm):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)

        from services.task_executor import ExecutionResult
        candidate = TaskCandidate(
            task_id="task-001",
            title="Test",
            category="analysis",
            bounty_usd=0.25,
            plan=MagicMock(),
            raw_task={},
        )
        result = ExecutionResult(
            success=False,
            strategy_used=ExecutionStrategy.LLM_DIRECT,
            error="LLM failed",
        )

        submitted = await pipeline.submit_evidence(candidate, result)
        assert submitted is False


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Full Cycle (run_once)
# ═══════════════════════════════════════════════════════════════════


class TestPipelineRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_no_tasks(self, agent_context, mock_em_client, mock_llm):
        mock_em_client.list_tasks.return_value = []
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)

        result = await pipeline.run_once()
        assert result.tasks_discovered == 0
        assert result.tasks_submitted == 0

    @pytest.mark.asyncio
    async def test_run_once_with_tasks(self, agent_context, mock_em_client, mock_llm):
        tasks = [
            {
                "id": "task-001",
                "title": "Research crypto trends",
                "instructions": "Provide analysis of current crypto market.",
                "category": "research",
                "bounty_usd": 0.25,
                "evidence_required": ["text_response"],
                "status": "published",
            },
        ]
        mock_em_client.list_tasks.return_value = tasks

        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        result = await pipeline.run_once()

        assert result.tasks_discovered == 1
        assert result.tasks_executed >= 1
        assert result.tasks_submitted >= 1
        assert result.total_bounty_usd == 0.25
        assert result.agent_name == "test-agent"
        assert result.cycle_id == "test-agent-cycle-1"

    @pytest.mark.asyncio
    async def test_run_once_dry_run(self, agent_context, mock_em_client, mock_llm):
        tasks = [
            {
                "id": "task-001",
                "title": "Test task",
                "instructions": "Do something.",
                "category": "analysis",
                "bounty_usd": 0.25,
                "evidence_required": ["text_response"],
            },
        ]
        mock_em_client.list_tasks.return_value = tasks

        config = PipelineConfig(dry_run=True)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)
        result = await pipeline.run_once()

        assert result.tasks_discovered == 1
        assert result.tasks_applied >= 1
        # Dry run should still "submit" (it just logs instead of calling API)
        mock_em_client.submit_evidence.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_once_multiple_tasks(self, agent_context, mock_em_client, mock_llm):
        tasks = [
            {
                "id": f"task-{i:03d}",
                "title": f"Task {i}",
                "instructions": f"Do analysis {i}.",
                "category": "analysis",
                "bounty_usd": 0.20,
                "evidence_required": ["text_response"],
            }
            for i in range(5)
        ]
        mock_em_client.list_tasks.return_value = tasks

        config = PipelineConfig(max_tasks_per_cycle=3)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)
        result = await pipeline.run_once()

        assert result.tasks_discovered == 5
        assert result.tasks_evaluated <= 3  # max per cycle
        assert len(result.execution_results) <= 3

    @pytest.mark.asyncio
    async def test_run_once_records_log(self, agent_context, mock_em_client, mock_llm, tmp_workspace):
        tasks = [
            {
                "id": "task-001",
                "title": "Test",
                "instructions": "Do test.",
                "category": "analysis",
                "bounty_usd": 0.25,
            },
        ]
        mock_em_client.list_tasks.return_value = tasks

        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        await pipeline.run_once()

        log = pipeline.get_execution_log()
        assert len(log) == 1

        # Check log file was saved
        log_dir = tmp_workspace / "logs"
        assert log_dir.exists()
        log_files = list(log_dir.glob("pipeline_*.json"))
        assert len(log_files) == 1


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Stats
# ═══════════════════════════════════════════════════════════════════


class TestPipelineStats:
    @pytest.mark.asyncio
    async def test_stats_empty(self, agent_context, mock_em_client, mock_llm):
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        stats = pipeline.get_stats()
        assert stats["cycles"] == 0
        assert stats["agent"] == "test-agent"

    @pytest.mark.asyncio
    async def test_stats_after_cycle(self, agent_context, mock_em_client, mock_llm):
        tasks = [
            {
                "id": "task-001",
                "title": "Test",
                "instructions": "Do test.",
                "category": "analysis",
                "bounty_usd": 0.25,
                "evidence_required": ["text_response"],
            },
        ]
        mock_em_client.list_tasks.return_value = tasks

        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)
        await pipeline.run_once()

        stats = pipeline.get_stats()
        assert stats["cycles"] == 1
        assert stats["total_tasks_discovered"] >= 1
        assert "daily_budget_remaining_usd" in stats
        assert "llm_stats" in stats


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Budget Enforcement
# ═══════════════════════════════════════════════════════════════════


class TestPipelineBudget:
    @pytest.mark.asyncio
    async def test_stops_at_daily_budget(self, agent_context, mock_em_client, mock_llm):
        config = PipelineConfig(daily_budget_usd=0.001, per_task_budget_usd=0.001)
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)
        pipeline._daily_spent = 0.001  # Already spent budget

        tasks = [
            {
                "id": "task-001",
                "title": "Expensive task",
                "instructions": "Do elaborate analysis with many steps.",
                "category": "analysis",
                "bounty_usd": 0.25,
            },
        ]
        mock_em_client.list_tasks.return_value = tasks

        result = await pipeline.run_once()
        # Should discover tasks but not execute (budget exhausted)
        assert result.tasks_discovered == 1
        assert result.tasks_evaluated == 0


# ═══════════════════════════════════════════════════════════════════
# TaskPipeline — Continuous Mode
# ═══════════════════════════════════════════════════════════════════


class TestPipelineContinuous:
    @pytest.mark.asyncio
    async def test_run_continuous_max_cycles(self, agent_context, mock_em_client, mock_llm):
        mock_em_client.list_tasks.return_value = []
        config = PipelineConfig(continuous_interval_seconds=0)  # no sleep
        pipeline = TaskPipeline(agent_context, mock_em_client, config, mock_llm)

        results = await pipeline.run_continuous(
            interval_seconds=0, max_cycles=3
        )
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_stop_signal(self, agent_context, mock_em_client, mock_llm):
        mock_em_client.list_tasks.return_value = []
        pipeline = TaskPipeline(agent_context, mock_em_client, llm_provider=mock_llm)

        # Pre-stop the pipeline (it checks _running at loop start)
        # Then run with max_cycles to ensure it terminates
        async def stop_soon():
            await asyncio.sleep(0.05)
            pipeline.stop()

        task = asyncio.ensure_future(stop_soon())
        results = await asyncio.wait_for(
            pipeline.run_continuous(interval_seconds=0),
            timeout=5.0,
        )
        await task
        # Should stop after signal (might have run 1+ cycles)
        assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════════
# SwarmPipelineRunner
# ═══════════════════════════════════════════════════════════════════


class TestSwarmPipelineRunner:
    def test_discover_agents(self, tmp_path):
        # Create agent workspaces
        for name in ["agent-1", "agent-2", "agent-3"]:
            ws = tmp_path / name
            ws.mkdir()
            (ws / "SOUL.md").write_text(f"# {name}\nA test agent.")

        # Create a non-agent directory (no SOUL.md)
        non_agent = tmp_path / "not-an-agent"
        non_agent.mkdir()

        runner = SwarmPipelineRunner(tmp_path)
        agents = runner.discover_agents()
        assert len(agents) == 3

    def test_discover_agents_empty(self, tmp_path):
        runner = SwarmPipelineRunner(tmp_path)
        agents = runner.discover_agents()
        assert agents == []

    def test_discover_agents_missing_dir(self, tmp_path):
        runner = SwarmPipelineRunner(tmp_path / "nonexistent")
        agents = runner.discover_agents()
        assert agents == []


# ═══════════════════════════════════════════════════════════════════
# TaskCandidate
# ═══════════════════════════════════════════════════════════════════


class TestTaskCandidate:
    def test_creation(self):
        from services.task_executor import ExecutionPlan
        candidate = TaskCandidate(
            task_id="t-1",
            title="Test",
            category="analysis",
            bounty_usd=0.25,
            plan=ExecutionPlan(
                strategy=ExecutionStrategy.LLM_DIRECT,
                reason="test",
                confidence=0.8,
            ),
            match_score=0.75,
        )
        assert candidate.task_id == "t-1"
        assert candidate.match_score == 0.75
        assert candidate.plan.strategy == ExecutionStrategy.LLM_DIRECT

    def test_raw_task_default(self):
        candidate = TaskCandidate(
            task_id="t-1",
            title="Test",
            category="analysis",
            bounty_usd=0.25,
            plan=MagicMock(),
        )
        assert candidate.raw_task == {}
