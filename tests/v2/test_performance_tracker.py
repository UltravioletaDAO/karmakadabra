#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 — Tests for performance_tracker.py

Tests for performance-aware agent matching:
  - Performance data extraction from notes and JSON
  - Enhanced match scoring (skills + performance)
  - Agent ranking for task assignment
  - Data persistence (save/load)

Usage:
    pytest scripts/kk/tests/test_performance_tracker.py -v
"""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.performance_tracker import (
    AgentPerformance,
    compute_enhanced_match_score,
    extract_performance_from_json,
    extract_performance_from_notes,
    rank_agents_for_task,
    save_performance,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def workspace_with_structured_notes(tmp_dir):
    """Workspace with structured [TAG] log entries."""
    ws = tmp_dir / "workspaces"

    # Experienced agent: alpha
    alpha_notes = ws / "kk-alpha" / "memory" / "notes"
    alpha_notes.mkdir(parents=True)
    (alpha_notes / "2026-02-19.md").write_text(
        "- [COMPLETED] task-1 category:simple_action chain:base bounty:$0.10\n"
        "- [RATED] 4/5 by kk-coordinator\n"
        "- [EARNED] $0.10 from task-1\n"
    )
    (alpha_notes / "2026-02-20.md").write_text(
        "- [COMPLETED] task-2 category:knowledge_access chain:polygon bounty:$0.15\n"
        "- [RATED] 5/5 by kk-auditor\n"
        "- [EARNED] $0.15 from task-2\n"
        "- [APPLIED] task-3 category:digital_physical\n"
    )
    (alpha_notes / "2026-02-21.md").write_text(
        "- [COMPLETED] task-4 category:simple_action chain:base\n"
        "- [RATED] 4/5 by kk-treasurer\n"
        "- [EARNED] $0.10 from task-4\n"
    )

    # Newer agent: beta (fewer tasks, lower ratings)
    beta_notes = ws / "kk-beta" / "memory" / "notes"
    beta_notes.mkdir(parents=True)
    (beta_notes / "2026-02-21.md").write_text(
        "- [COMPLETED] task-5 category:simple_action chain:base bounty:$0.10\n"
        "- [RATED] 3/5 by kk-coordinator\n"
        "- [EARNED] $0.10 from task-5\n"
        "- applied to task-6 category:knowledge_access\n"
        "- task expired for task-6\n"
    )

    # Agent with no activity: gamma
    gamma_dir = ws / "kk-gamma"
    gamma_dir.mkdir(parents=True)

    return ws


@pytest.fixture
def workspace_with_json_profiles(tmp_dir):
    """Workspace with data/performance.json files."""
    ws = tmp_dir / "workspaces"

    # Alpha: experienced
    alpha_data = ws / "kk-alpha" / "data"
    alpha_data.mkdir(parents=True)
    (alpha_data / "performance.json").write_text(json.dumps({
        "agent_name": "kk-alpha",
        "tasks_completed": 15,
        "tasks_attempted": 18,
        "tasks_failed": 3,
        "avg_completion_hours": 2.5,
        "total_earned_usd": 2.50,
        "total_spent_usd": 0.30,
        "avg_rating_received": 85.0,
        "rating_count": 12,
        "category_completions": {"simple_action": 8, "knowledge_access": 5, "digital_physical": 2},
        "category_attempts": {"simple_action": 9, "knowledge_access": 6, "digital_physical": 3},
        "chain_tasks": {"base": 10, "polygon": 5, "arbitrum": 3},
    }))

    # Beta: less experienced
    beta_data = ws / "kk-beta" / "data"
    beta_data.mkdir(parents=True)
    (beta_data / "performance.json").write_text(json.dumps({
        "agent_name": "kk-beta",
        "tasks_completed": 3,
        "tasks_attempted": 5,
        "tasks_failed": 2,
        "avg_completion_hours": 5.0,
        "total_earned_usd": 0.30,
        "total_spent_usd": 0.10,
        "avg_rating_received": 60.0,
        "rating_count": 3,
        "category_completions": {"simple_action": 2, "knowledge_access": 1},
        "category_attempts": {"simple_action": 3, "knowledge_access": 2},
        "chain_tasks": {"base": 5},
    }))

    return ws


# ---------------------------------------------------------------------------
# AgentPerformance Model Tests
# ---------------------------------------------------------------------------


class TestAgentPerformance:
    """Tests for AgentPerformance dataclass."""

    def test_completion_rate_with_data(self):
        perf = AgentPerformance("test", tasks_completed=8, tasks_attempted=10)
        assert perf.completion_rate == 0.8

    def test_completion_rate_no_data(self):
        perf = AgentPerformance("test")
        assert perf.completion_rate == 0.5  # Neutral for new agents

    def test_completion_rate_perfect(self):
        perf = AgentPerformance("test", tasks_completed=10, tasks_attempted=10)
        assert perf.completion_rate == 1.0

    def test_reliability_score_good_agent(self):
        perf = AgentPerformance(
            "test",
            tasks_completed=9,
            tasks_attempted=10,
            avg_rating_received=90.0,
        )
        score = perf.reliability_score
        assert score > 0.7

    def test_reliability_score_new_agent(self):
        perf = AgentPerformance("test")
        assert perf.reliability_score == 0.5

    def test_category_strength_experienced(self):
        perf = AgentPerformance("test")
        perf.category_completions = {"simple_action": 8}
        perf.category_attempts = {"simple_action": 10}
        assert perf.category_strength("simple_action") == 0.8

    def test_category_strength_no_experience(self):
        perf = AgentPerformance("test")
        assert perf.category_strength("unknown") == 0.0

    def test_chain_experience_experienced(self):
        perf = AgentPerformance("test")
        perf.chain_tasks = {"base": 10}
        assert perf.chain_experience("base") > 0.5

    def test_chain_experience_no_experience(self):
        perf = AgentPerformance("test")
        assert perf.chain_experience("base") == 0.1


# ---------------------------------------------------------------------------
# Notes Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractPerformanceFromNotes:
    """Tests for extract_performance_from_notes()."""

    def test_extracts_completions(self, workspace_with_structured_notes):
        profiles = extract_performance_from_notes(workspace_with_structured_notes)
        alpha = profiles["kk-alpha"]
        assert alpha.tasks_completed == 3

    def test_extracts_failures(self, workspace_with_structured_notes):
        profiles = extract_performance_from_notes(workspace_with_structured_notes)
        beta = profiles["kk-beta"]
        assert beta.tasks_failed >= 1

    def test_extracts_earnings(self, workspace_with_structured_notes):
        profiles = extract_performance_from_notes(workspace_with_structured_notes)
        alpha = profiles["kk-alpha"]
        assert abs(alpha.total_earned_usd - 0.35) < 0.01  # $0.10 + $0.15 + $0.10

    def test_extracts_categories(self, workspace_with_structured_notes):
        profiles = extract_performance_from_notes(workspace_with_structured_notes)
        alpha = profiles["kk-alpha"]
        assert "simple_action" in alpha.category_completions
        assert alpha.category_completions["simple_action"] == 2

    def test_extracts_chains(self, workspace_with_structured_notes):
        profiles = extract_performance_from_notes(workspace_with_structured_notes)
        alpha = profiles["kk-alpha"]
        assert "base" in alpha.chain_tasks
        assert alpha.chain_tasks["base"] == 2
        assert "polygon" in alpha.chain_tasks

    def test_extracts_ratings(self, workspace_with_structured_notes):
        profiles = extract_performance_from_notes(workspace_with_structured_notes)
        alpha = profiles["kk-alpha"]
        assert alpha.rating_count == 3
        assert alpha.avg_rating_received > 0

    def test_empty_agent_has_default(self, workspace_with_structured_notes):
        profiles = extract_performance_from_notes(workspace_with_structured_notes)
        gamma = profiles["kk-gamma"]
        assert gamma.tasks_completed == 0
        assert gamma.completion_rate == 0.5

    def test_nonexistent_dir(self, tmp_dir):
        profiles = extract_performance_from_notes(tmp_dir / "nope")
        assert profiles == {}


# ---------------------------------------------------------------------------
# JSON Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractPerformanceFromJson:
    """Tests for extract_performance_from_json()."""

    def test_loads_structured_data(self, workspace_with_json_profiles):
        profiles = extract_performance_from_json(workspace_with_json_profiles)
        alpha = profiles["kk-alpha"]
        assert alpha.tasks_completed == 15
        assert alpha.tasks_attempted == 18
        assert alpha.avg_rating_received == 85.0

    def test_loads_categories(self, workspace_with_json_profiles):
        profiles = extract_performance_from_json(workspace_with_json_profiles)
        alpha = profiles["kk-alpha"]
        assert alpha.category_completions["simple_action"] == 8

    def test_loads_chain_data(self, workspace_with_json_profiles):
        profiles = extract_performance_from_json(workspace_with_json_profiles)
        alpha = profiles["kk-alpha"]
        assert alpha.chain_tasks["base"] == 10


# ---------------------------------------------------------------------------
# Enhanced Matching Tests
# ---------------------------------------------------------------------------


class TestComputeEnhancedMatchScore:
    """Tests for compute_enhanced_match_score()."""

    def test_experienced_agent_scores_higher(self):
        """Agent with good track record scores higher than one without."""
        experienced = AgentPerformance(
            "exp",
            tasks_completed=10,
            tasks_attempted=12,
            avg_rating_received=90,
            rating_count=8,
            category_completions={"simple_action": 8},
            category_attempts={"simple_action": 10},
            chain_tasks={"base": 10},
            total_earned_usd=2.0,
        )
        newbie = AgentPerformance("new")

        skills = {"monitoring", "analytics"}
        exp_score = compute_enhanced_match_score(
            experienced, skills,
            "[KK] Audit heartbeat logs", "Check for anomalies",
            task_category="simple_action", task_chain="base",
        )
        new_score = compute_enhanced_match_score(
            newbie, skills,
            "[KK] Audit heartbeat logs", "Check for anomalies",
            task_category="simple_action", task_chain="base",
        )
        assert exp_score > new_score

    def test_skill_match_contributes(self):
        """Skills matching boosts score."""
        perf = AgentPerformance("test")
        with_skills = compute_enhanced_match_score(
            perf, {"auditing", "analytics"},
            "Audit on-chain distribution", "Check auditing results",
        )
        without_skills = compute_enhanced_match_score(
            perf, {"cooking", "farming"},
            "Audit on-chain distribution", "Check auditing results",
        )
        assert with_skills > without_skills

    def test_kk_tagged_tasks_get_baseline(self):
        """KK-tagged tasks give baseline score even without skill match."""
        perf = AgentPerformance("test")
        score = compute_enhanced_match_score(
            perf, {"random_skill"},
            "[KK] Community task for everyone", "Anyone can do this",
        )
        assert score > 0

    def test_score_bounded_0_1(self):
        """Score never exceeds 1.0 or goes below 0.0."""
        perf = AgentPerformance(
            "max",
            tasks_completed=100,
            tasks_attempted=100,
            avg_rating_received=100,
            total_earned_usd=50,
        )
        score = compute_enhanced_match_score(
            perf, {"everything"},
            "everything match", "perfect match everything",
            task_category="simple_action",
        )
        assert 0 <= score <= 1.0

    def test_category_experience_matters(self):
        """Agent experienced in task category scores higher."""
        cat_expert = AgentPerformance(
            "expert",
            tasks_completed=5,
            tasks_attempted=5,
            category_completions={"knowledge_access": 5},
            category_attempts={"knowledge_access": 5},
        )
        cat_newbie = AgentPerformance(
            "newbie",
            tasks_completed=5,
            tasks_attempted=5,
            # No category track record
        )

        expert_score = compute_enhanced_match_score(
            cat_expert, set(),
            "Research task", "Investigate this topic",
            task_category="knowledge_access",
        )
        newbie_score = compute_enhanced_match_score(
            cat_newbie, set(),
            "Research task", "Investigate this topic",
            task_category="knowledge_access",
        )
        assert expert_score > newbie_score

    def test_chain_experience_matters(self):
        """Agent experienced on task's chain scores higher."""
        chain_expert = AgentPerformance("expert")
        chain_expert.chain_tasks = {"polygon": 20}

        chain_newbie = AgentPerformance("newbie")

        expert_score = compute_enhanced_match_score(
            chain_expert, {"testing"},
            "Test polygon task", "Verify on polygon",
            task_chain="polygon",
        )
        newbie_score = compute_enhanced_match_score(
            chain_newbie, {"testing"},
            "Test polygon task", "Verify on polygon",
            task_chain="polygon",
        )
        assert expert_score > newbie_score

    def test_no_skills_minimal_score(self):
        """Agent with no skills gets minimal score."""
        perf = AgentPerformance("test")
        score = compute_enhanced_match_score(
            perf, set(),
            "Any task", "Some description",
        )
        assert score > 0  # Should still get reliability + baseline scores


# ---------------------------------------------------------------------------
# Ranking Tests
# ---------------------------------------------------------------------------


class TestRankAgentsForTask:
    """Tests for rank_agents_for_task()."""

    def test_ranking_order(self):
        """Agents ranked by score descending."""
        profiles = {
            "alpha": AgentPerformance(
                "alpha", tasks_completed=10, tasks_attempted=10,
                avg_rating_received=90, rating_count=8,
            ),
            "beta": AgentPerformance(
                "beta", tasks_completed=2, tasks_attempted=5,
                avg_rating_received=50, rating_count=2,
            ),
            "gamma": AgentPerformance("gamma"),
        }
        skills_map = {
            "alpha": {"analytics"},
            "beta": {"analytics"},
            "gamma": set(),
        }

        rankings = rank_agents_for_task(
            profiles, skills_map,
            "[KK] Analytics task", "Run analytics monitoring",
        )
        assert len(rankings) >= 2
        # Alpha should rank first — same skills but much better track record
        assert rankings[0][0] == "alpha"
        assert rankings[0][1] >= rankings[1][1]

    def test_exclude_agents(self):
        """Excluded agents don't appear in rankings."""
        profiles = {
            "alpha": AgentPerformance("alpha"),
            "beta": AgentPerformance("beta"),
        }
        skills_map = {"alpha": set(), "beta": set()}

        rankings = rank_agents_for_task(
            profiles, skills_map,
            "Task", "Description",
            exclude_agents={"alpha"},
        )
        agent_names = [r[0] for r in rankings]
        assert "alpha" not in agent_names

    def test_min_score_threshold(self):
        """Only agents above min_score included."""
        profiles = {
            "alpha": AgentPerformance("alpha"),
            "beta": AgentPerformance("beta"),
        }
        skills_map = {"alpha": set(), "beta": set()}

        # Very high threshold should filter most agents
        rankings = rank_agents_for_task(
            profiles, skills_map,
            "Task", "Description",
            min_score=0.99,
        )
        assert len(rankings) == 0

    def test_empty_profiles(self):
        rankings = rank_agents_for_task({}, {}, "Task", "Desc")
        assert rankings == []


# ---------------------------------------------------------------------------
# Save/Load Tests
# ---------------------------------------------------------------------------


class TestSavePerformance:
    """Tests for save_performance()."""

    def test_save_creates_json(self, tmp_dir):
        ws = tmp_dir / "workspaces" / "kk-alpha"
        ws.mkdir(parents=True)

        profiles = {
            "kk-alpha": AgentPerformance(
                "kk-alpha",
                tasks_completed=5,
                tasks_attempted=6,
                total_earned_usd=0.50,
            )
        }

        saved = save_performance(tmp_dir / "workspaces", profiles)
        assert saved == 1

        perf_file = ws / "data" / "performance.json"
        assert perf_file.exists()

        data = json.loads(perf_file.read_text())
        assert data["tasks_completed"] == 5
        assert data["total_earned_usd"] == 0.50
        assert "completion_rate" in data
        assert "reliability_score" in data

    def test_save_roundtrip(self, tmp_dir):
        """Save then load produces same data."""
        ws = tmp_dir / "workspaces" / "kk-alpha"
        ws.mkdir(parents=True)

        original = AgentPerformance(
            "kk-alpha",
            tasks_completed=10,
            tasks_attempted=12,
            avg_rating_received=85.0,
            rating_count=8,
            category_completions={"simple_action": 7},
            category_attempts={"simple_action": 8},
            chain_tasks={"base": 10, "polygon": 5},
        )

        save_performance(tmp_dir / "workspaces", {"kk-alpha": original})
        loaded = extract_performance_from_json(tmp_dir / "workspaces")

        assert "kk-alpha" in loaded
        loaded_alpha = loaded["kk-alpha"]
        assert loaded_alpha.tasks_completed == original.tasks_completed
        assert loaded_alpha.avg_rating_received == original.avg_rating_received
        assert loaded_alpha.chain_tasks == original.chain_tasks

    def test_save_skips_nonexistent_workspace(self, tmp_dir):
        profiles = {"nonexistent": AgentPerformance("nonexistent")}
        saved = save_performance(tmp_dir / "workspaces", profiles)
        assert saved == 0
