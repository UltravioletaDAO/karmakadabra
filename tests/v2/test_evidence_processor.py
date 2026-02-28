"""
Tests for KK V2 Evidence Processor Service.

Tests cover:
  1. Single completion processing
  2. Batch processing and aggregation
  3. Skill extraction from tasks
  4. Quality trend computation
  5. Performance profile persistence
  6. Report generation
  7. Cursor management (idempotency)
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.evidence_processor import (
    CompletionRecord,
    EvidenceProcessor,
    ProcessingSummary,
    compute_quality_trend,
    extract_skills_from_task,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def processor(tmp_path):
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    return EvidenceProcessor(workspaces_dir=workspaces, data_dir=tmp_path / "data")


@pytest.fixture
def approved_record():
    return CompletionRecord(
        task_id="task-001",
        agent_name="kk-agent-3",
        title="Analyze DeFi protocol risks",
        category="knowledge_access",
        bounty_usd=0.25,
        evidence_type="text_response",
        approved=True,
        rating_score=85,
        tokens_used=1500,
        cost_usd=0.009,
        duration_ms=3200,
        execution_strategy="llm_direct",
        payment_network="base",
    )


@pytest.fixture
def rejected_record():
    return CompletionRecord(
        task_id="task-002",
        agent_name="kk-agent-5",
        title="Market analysis report",
        category="research",
        bounty_usd=0.30,
        evidence_type="text_response",
        approved=False,
        rejected=True,
        rating_score=0,
        rejection_reason="Insufficient detail",
        tokens_used=800,
        cost_usd=0.005,
        duration_ms=2100,
        execution_strategy="llm_with_tools",
        payment_network="base",
    )


@pytest.fixture
def batch_records():
    return [
        CompletionRecord(
            task_id=f"task-{i:03d}",
            agent_name=f"kk-agent-{(i % 3) + 3}",
            title=f"Task {i}",
            category=["knowledge_access", "research", "code_review"][i % 3],
            bounty_usd=0.20 + (i * 0.05),
            approved=(i % 4 != 0),
            rejected=(i % 4 == 0),
            rating_score=70 + (i * 3) if (i % 4 != 0) else 0,
            tokens_used=1000 + (i * 100),
            cost_usd=0.006 + (i * 0.001),
            duration_ms=2000 + (i * 200),
            execution_strategy="llm_direct",
            payment_network="base",
        )
        for i in range(10)
    ]


# ═══════════════════════════════════════════════════════════════════
# Skill Extraction Tests
# ═══════════════════════════════════════════════════════════════════


class TestSkillExtraction:
    """Test skill extraction from task metadata."""

    def test_defi_task_extracts_defi_skill(self):
        skills = extract_skills_from_task(
            "Analyze DeFi lending protocols",
            "Research TVL and yield rates",
            "knowledge_access",
        )
        assert "defi_analysis" in skills

    def test_solidity_task_extracts_contract_skill(self):
        skills = extract_skills_from_task(
            "Review Solidity contract",
            "Check for reentrancy bugs",
            "code_review",
        )
        assert "smart_contract_review" in skills

    def test_market_task_extracts_market_skill(self):
        skills = extract_skills_from_task(
            "Market price analysis",
            "Analyze trading volume",
            "research",
        )
        assert "market_analysis" in skills

    def test_category_always_included(self):
        skills = extract_skills_from_task("Test", "Instructions", "knowledge_access")
        assert "knowledge_access" in skills

    def test_multiple_skills_extracted(self):
        skills = extract_skills_from_task(
            "DeFi market analysis on blockchain",
            "Analyze on-chain trading data for DeFi protocols",
            "research",
        )
        assert len(skills) >= 3  # defi, market, blockchain, research

    def test_empty_inputs(self):
        skills = extract_skills_from_task("", "", "")
        assert len(skills) == 0 or skills == {""}


# ═══════════════════════════════════════════════════════════════════
# Quality Trend Tests
# ═══════════════════════════════════════════════════════════════════


class TestQualityTrend:
    """Test quality trend computation."""

    def test_improving_trend(self):
        ratings = [60, 65, 70, 75, 80, 85, 90]
        assert compute_quality_trend(ratings) == "improving"

    def test_declining_trend(self):
        ratings = [90, 85, 80, 75, 70, 65, 60]
        assert compute_quality_trend(ratings) == "declining"

    def test_stable_trend(self):
        ratings = [80, 82, 79, 81, 80, 78, 81]
        assert compute_quality_trend(ratings) == "stable"

    def test_too_few_ratings(self):
        assert compute_quality_trend([80]) == "stable"
        assert compute_quality_trend([80, 85]) == "stable"

    def test_empty_ratings(self):
        assert compute_quality_trend([]) == "stable"


# ═══════════════════════════════════════════════════════════════════
# Single Completion Tests
# ═══════════════════════════════════════════════════════════════════


class TestProcessCompletion:
    """Test single completion record processing."""

    def test_approved_completion(self, processor, approved_record):
        update = processor.process_completion(approved_record)
        assert update.agent_name == "kk-agent-3"
        assert update.tasks_completed == 1
        assert update.tasks_approved == 1
        assert update.tasks_rejected == 0
        assert update.total_earned_usd == 0.25
        assert update.total_cost_usd == 0.009

    def test_rejected_completion(self, processor, rejected_record):
        update = processor.process_completion(rejected_record)
        assert update.tasks_rejected == 1
        assert update.tasks_approved == 0
        assert update.total_earned_usd == 0.0

    def test_skills_extracted(self, processor, approved_record):
        update = processor.process_completion(approved_record)
        assert len(update.skills_demonstrated) > 0
        assert "knowledge_access" in update.skills_demonstrated

    def test_category_tracked(self, processor, approved_record):
        update = processor.process_completion(approved_record)
        assert "knowledge_access" in update.categories_worked

    def test_chain_tracked(self, processor, approved_record):
        update = processor.process_completion(approved_record)
        assert "base" in update.chains_worked

    def test_rating_history_updated(self, processor, approved_record):
        processor.process_completion(approved_record)
        assert "kk-agent-3" in processor._rating_history
        assert 85 in processor._rating_history["kk-agent-3"]


# ═══════════════════════════════════════════════════════════════════
# Batch Processing Tests
# ═══════════════════════════════════════════════════════════════════


class TestBatchProcessing:
    """Test batch processing of multiple completions."""

    def test_batch_processes_all(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        assert summary.records_processed == 10

    def test_batch_aggregates_per_agent(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        assert summary.agents_updated > 0
        # 10 records across 3 agents (agent-3, agent-4, agent-5)
        assert len(summary.agent_updates) == 3

    def test_batch_counts_approvals(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        # Every 4th record is rejected (i%4==0: indices 0,4,8 → 3 rejected)
        assert summary.total_rejected == 3
        assert summary.total_approved == 7

    def test_batch_computes_economics(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        assert summary.total_earned_usd > 0
        assert summary.total_cost_usd > 0
        assert summary.net_profit_usd == pytest.approx(
            summary.total_earned_usd - summary.total_cost_usd
        )

    def test_batch_timing(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        assert summary.processing_time_ms >= 0

    def test_empty_batch(self, processor):
        summary = processor.process_batch([])
        assert summary.records_processed == 0
        assert summary.agents_updated == 0

    def test_batch_saves_cursor(self, processor, batch_records):
        processor.process_batch(batch_records)
        assert processor._last_processed_id == "task-009"
        # Verify cursor persisted to disk
        cursor = json.loads(processor._cursor_file.read_text())
        assert cursor["last_id"] == "task-009"


# ═══════════════════════════════════════════════════════════════════
# Performance Profile Persistence Tests
# ═══════════════════════════════════════════════════════════════════


class TestProfilePersistence:
    """Test writing performance updates to workspace profiles."""

    def test_creates_profile(self, processor, batch_records, tmp_path):
        workspaces = tmp_path / "workspaces"
        processor.workspaces_dir = workspaces

        summary = processor.process_batch(batch_records)
        updated = processor.update_performance_profiles(summary)
        assert updated > 0

        # Check a profile was created
        for agent_name in summary.agent_updates:
            profile_path = workspaces / agent_name / "data" / "profile.json"
            assert profile_path.exists()
            profile = json.loads(profile_path.read_text())
            assert "performance" in profile
            assert "demonstrated_skills" in profile

    def test_profile_accumulates(self, processor, tmp_path):
        workspaces = tmp_path / "workspaces"
        processor.workspaces_dir = workspaces

        # First batch
        records1 = [
            CompletionRecord(
                task_id="t1", agent_name="kk-agent-3",
                category="research", bounty_usd=0.20,
                approved=True, rating_score=80,
            )
        ]
        summary1 = processor.process_batch(records1)
        processor.update_performance_profiles(summary1)

        # Second batch (same agent)
        records2 = [
            CompletionRecord(
                task_id="t2", agent_name="kk-agent-3",
                category="code_review", bounty_usd=0.30,
                approved=True, rating_score=90,
            )
        ]
        summary2 = processor.process_batch(records2)
        processor.update_performance_profiles(summary2)

        # Check accumulated
        profile = json.loads(
            (workspaces / "kk-agent-3" / "data" / "profile.json").read_text()
        )
        assert profile["performance"]["tasks_completed"] == 2
        assert profile["performance"]["tasks_approved"] == 2
        assert len(profile["category_experience"]) == 2

    def test_success_rate_computed(self, processor, tmp_path):
        workspaces = tmp_path / "workspaces"
        processor.workspaces_dir = workspaces

        records = [
            CompletionRecord(task_id="t1", agent_name="kk-agent-3", approved=True, rating_score=80),
            CompletionRecord(task_id="t2", agent_name="kk-agent-3", approved=True, rating_score=85),
            CompletionRecord(task_id="t3", agent_name="kk-agent-3", rejected=True),
        ]
        summary = processor.process_batch(records)
        processor.update_performance_profiles(summary)

        profile = json.loads(
            (workspaces / "kk-agent-3" / "data" / "profile.json").read_text()
        )
        assert profile["performance"]["success_rate"] == pytest.approx(2 / 3, abs=0.01)


# ═══════════════════════════════════════════════════════════════════
# Report Generation Tests
# ═══════════════════════════════════════════════════════════════════


class TestReportGeneration:
    """Test report generation and persistence."""

    def test_report_text(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        report = processor.generate_report(summary)
        assert "Evidence Processing Report" in report
        assert "records" in report.lower()
        assert "kk-agent" in report

    def test_report_includes_economics(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        report = processor.generate_report(summary)
        assert "$" in report  # Has dollar amounts
        assert "Earned" in report

    def test_report_saved_to_disk(self, processor, batch_records):
        summary = processor.process_batch(batch_records)
        path = processor.save_report(summary)
        assert path.exists()
        assert path.suffix == ".md"
        # JSON companion should also exist
        json_path = path.with_suffix(".json")
        assert json_path.exists()

    def test_empty_summary_report(self, processor):
        summary = ProcessingSummary()
        report = processor.generate_report(summary)
        assert "0 records" in report


# ═══════════════════════════════════════════════════════════════════
# Cursor Management Tests
# ═══════════════════════════════════════════════════════════════════


class TestCursorManagement:
    """Test cursor-based idempotency."""

    def test_cursor_persists_between_instances(self, tmp_path):
        workspaces = tmp_path / "workspaces"
        workspaces.mkdir()
        data_dir = tmp_path / "data"

        # First processor
        proc1 = EvidenceProcessor(workspaces_dir=workspaces, data_dir=data_dir)
        records = [CompletionRecord(task_id="cursor-test", agent_name="kk-agent-3")]
        proc1.process_batch(records)

        # Second processor (new instance)
        proc2 = EvidenceProcessor(workspaces_dir=workspaces, data_dir=data_dir)
        assert proc2._last_processed_id == "cursor-test"

    def test_rating_history_persists(self, tmp_path):
        workspaces = tmp_path / "workspaces"
        workspaces.mkdir()
        data_dir = tmp_path / "data"

        # First processor
        proc1 = EvidenceProcessor(workspaces_dir=workspaces, data_dir=data_dir)
        record = CompletionRecord(
            task_id="t1", agent_name="kk-agent-3",
            approved=True, rating_score=85,
        )
        proc1.process_batch([record])

        # Second processor
        proc2 = EvidenceProcessor(workspaces_dir=workspaces, data_dir=data_dir)
        assert "kk-agent-3" in proc2._rating_history
        assert 85 in proc2._rating_history["kk-agent-3"]


# ═══════════════════════════════════════════════════════════════════
# Agent Identification Tests
# ═══════════════════════════════════════════════════════════════════


class TestAgentIdentification:
    """Test identifying which KK agent completed a task."""

    def test_identify_from_evidence_metadata(self, processor):
        task = {
            "evidence": {
                "metadata": {"agent": "kk-agent-5"}
            }
        }
        assert processor._identify_kk_agent(task) == "kk-agent-5"

    def test_identify_from_submissions(self, processor):
        task = {
            "evidence": {},
            "submissions": [{"agent_name": "kk-agent-7"}],
        }
        assert processor._identify_kk_agent(task) == "kk-agent-7"

    def test_non_kk_agent_returns_none(self, processor):
        task = {
            "evidence": {
                "metadata": {"agent": "external-agent"}
            }
        }
        assert processor._identify_kk_agent(task) is None

    def test_filter_by_allowed_agents(self, processor):
        task = {
            "evidence": {
                "metadata": {"agent": "kk-agent-5"}
            }
        }
        assert processor._identify_kk_agent(task, allowed_agents=["kk-agent-5"]) == "kk-agent-5"
        assert processor._identify_kk_agent(task, allowed_agents=["kk-agent-3"]) is None

    def test_empty_task_returns_none(self, processor):
        assert processor._identify_kk_agent({}) is None
