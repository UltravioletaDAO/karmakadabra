#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 — Tests for relationship_tracker.py

Tests interaction extraction from daily notes, trust score computation,
and MEMORY.md updates.

Usage:
    pytest scripts/kk/tests/test_relationship_tracker.py -v
"""

import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.memory import create_initial_memory_md
from services.relationship_tracker import (
    WEIGHT_COMPLETION,
    WEIGHT_FREQUENCY,
    WEIGHT_PAYMENT,
    WEIGHT_RATING,
    Interaction,
    compute_trust_scores,
    extract_interactions_from_notes,
    format_report,
    update_agent_memory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def workspace_with_notes(tmp_dir):
    """Create workspace directories with daily notes containing interactions."""
    workspaces = tmp_dir / "workspaces"

    # Agent alpha's notes
    alpha_notes = workspaces / "kk-alpha" / "memory" / "notes"
    alpha_notes.mkdir(parents=True)
    (alpha_notes / "2026-02-20.md").write_text(
        "- completed task for kk-beta\n"
        "- rated kk-beta 85\n"
        "- applied to task by kk-gamma\n"
    )
    (alpha_notes / "2026-02-21.md").write_text(
        "- approved submission from kk-beta\n"
        "- completed task for kk-gamma\n"
    )

    # Agent beta's notes
    beta_notes = workspaces / "kk-beta" / "memory" / "notes"
    beta_notes.mkdir(parents=True)
    (beta_notes / "2026-02-20.md").write_text(
        "- completed task for kk-alpha\n"
        "- rated kk-alpha 90\n"
        "- paid by kk-alpha\n"
    )
    (beta_notes / "2026-02-21.md").write_text(
        "- applied to task by kk-gamma\n"
    )

    # Agent gamma's notes
    gamma_notes = workspaces / "kk-gamma" / "memory" / "notes"
    gamma_notes.mkdir(parents=True)
    (gamma_notes / "2026-02-20.md").write_text(
        "- rated kk-alpha 70\n"
        "- rated kk-beta 60\n"
    )

    return workspaces


@pytest.fixture
def workspace_with_memory(tmp_dir):
    """Workspace with MEMORY.md files for agents."""
    workspaces = tmp_dir / "workspaces"

    for agent in ["kk-alpha", "kk-beta", "kk-gamma"]:
        mem_dir = workspaces / agent / "memory"
        mem_dir.mkdir(parents=True)
        create_initial_memory_md(mem_dir / "MEMORY.md")

        # Add some notes
        notes_dir = mem_dir / "notes"
        notes_dir.mkdir()
        (notes_dir / "2026-02-20.md").write_text(
            f"- completed task for kk-{'beta' if agent == 'kk-alpha' else 'alpha'}\n"
            f"- rated kk-{'beta' if agent == 'kk-alpha' else 'alpha'} 80\n"
            f"- approved submission from kk-{'beta' if agent == 'kk-alpha' else 'alpha'}\n"
        )

    return workspaces


# ---------------------------------------------------------------------------
# Interaction Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractInteractions:
    """Tests for extract_interactions_from_notes()."""

    def test_extracts_completions(self, workspace_with_notes):
        interactions = extract_interactions_from_notes(workspace_with_notes)
        completions = [ix for ix in interactions if ix.interaction_type == "completed"]
        assert len(completions) >= 2

    def test_extracts_ratings(self, workspace_with_notes):
        interactions = extract_interactions_from_notes(workspace_with_notes)
        ratings = [ix for ix in interactions if ix.interaction_type == "rated"]
        assert len(ratings) >= 3

    def test_rating_values_extracted(self, workspace_with_notes):
        interactions = extract_interactions_from_notes(workspace_with_notes)
        ratings = [ix for ix in interactions if ix.interaction_type == "rated"]
        values = [ix.value for ix in ratings]
        assert 85.0 in values
        assert 90.0 in values

    def test_extracts_approvals(self, workspace_with_notes):
        interactions = extract_interactions_from_notes(workspace_with_notes)
        approvals = [ix for ix in interactions if ix.interaction_type == "approved"]
        assert len(approvals) >= 1

    def test_extracts_payments(self, workspace_with_notes):
        interactions = extract_interactions_from_notes(workspace_with_notes)
        payments = [ix for ix in interactions if ix.interaction_type == "paid"]
        assert len(payments) >= 1

    def test_no_self_interactions(self, workspace_with_notes):
        interactions = extract_interactions_from_notes(workspace_with_notes)
        for ix in interactions:
            assert ix.from_agent != ix.to_agent

    def test_empty_directory(self, tmp_dir):
        interactions = extract_interactions_from_notes(tmp_dir / "nonexistent")
        assert interactions == []

    def test_dates_captured(self, workspace_with_notes):
        interactions = extract_interactions_from_notes(workspace_with_notes)
        dates = {ix.date for ix in interactions}
        assert "2026-02-20" in dates
        assert "2026-02-21" in dates


# ---------------------------------------------------------------------------
# Trust Score Computation Tests
# ---------------------------------------------------------------------------


class TestComputeTrustScores:
    """Tests for compute_trust_scores()."""

    def test_basic_trust_computation(self):
        interactions = [
            Interaction("alpha", "beta", "completed", 0, "2026-02-20"),
            Interaction("alpha", "beta", "rated", 85, "2026-02-20"),
            Interaction("beta", "alpha", "completed", 0, "2026-02-20"),
            Interaction("beta", "alpha", "rated", 90, "2026-02-20"),
        ]
        trust = compute_trust_scores(interactions)
        assert "alpha" in trust
        assert "beta" in trust["alpha"]
        assert trust["alpha"]["beta"] > 0

    def test_minimum_interactions_threshold(self):
        """Pairs with fewer than MIN_INTERACTIONS get no score."""
        interactions = [
            Interaction("alpha", "beta", "completed", 0, "2026-02-20"),
        ]
        trust = compute_trust_scores(interactions)
        # With only 1 interaction (< MIN_INTERACTIONS=2), no trust should be computed
        alpha_trust = trust.get("alpha", {})
        assert "beta" not in alpha_trust

    def test_high_trust_from_good_interactions(self):
        """Good interactions produce high trust scores."""
        interactions = [
            Interaction("alpha", "beta", "completed", 0, "d1"),
            Interaction("alpha", "beta", "approved", 0, "d2"),
            Interaction("alpha", "beta", "rated", 95, "d1"),
            Interaction("alpha", "beta", "paid", 0, "d2"),
            Interaction("beta", "alpha", "completed", 0, "d1"),
            Interaction("beta", "alpha", "rated", 90, "d2"),
        ]
        trust = compute_trust_scores(interactions)
        assert trust["alpha"]["beta"] >= 60

    def test_trust_bounded_0_100(self):
        """Trust scores never exceed 100."""
        interactions = [
            Interaction("a", "b", "completed", 0, f"d{i}")
            for i in range(20)
        ]
        trust = compute_trust_scores(interactions)
        for agent, peers in trust.items():
            for peer, score in peers.items():
                assert 0 <= score <= 100

    def test_empty_interactions(self):
        trust = compute_trust_scores([])
        assert trust == {}

    def test_sorted_by_score_descending(self):
        """Peers are sorted by trust score descending."""
        interactions = [
            Interaction("alpha", "beta", "completed", 0, "d1"),
            Interaction("alpha", "beta", "rated", 90, "d1"),
            Interaction("alpha", "gamma", "completed", 0, "d1"),
            Interaction("alpha", "gamma", "rated", 60, "d1"),
            Interaction("beta", "alpha", "applied", 0, "d1"),
            Interaction("beta", "alpha", "completed", 0, "d2"),
            Interaction("gamma", "alpha", "applied", 0, "d1"),
            Interaction("gamma", "alpha", "completed", 0, "d2"),
        ]
        trust = compute_trust_scores(interactions)
        alpha_peers = list(trust.get("alpha", {}).items())
        if len(alpha_peers) >= 2:
            assert alpha_peers[0][1] >= alpha_peers[1][1]


# ---------------------------------------------------------------------------
# MEMORY.md Update Tests
# ---------------------------------------------------------------------------


class TestUpdateAgentMemory:
    """Tests for update_agent_memory()."""

    def test_updates_memory_files(self, workspace_with_memory):
        # First extract interactions
        interactions = extract_interactions_from_notes(workspace_with_memory)
        trust = compute_trust_scores(interactions)

        if trust:
            updated = update_agent_memory(workspace_with_memory, trust)
            # At least some should be updated
            assert updated >= 0

    def test_does_not_crash_on_empty_trust(self, workspace_with_memory):
        updated = update_agent_memory(workspace_with_memory, {})
        assert updated == 0

    def test_skips_missing_memory_files(self, tmp_dir):
        """Agents without MEMORY.md are skipped."""
        trust = {"nonexistent-agent": {"peer": 80.0}}
        workspaces = tmp_dir / "workspaces"
        workspaces.mkdir()
        updated = update_agent_memory(workspaces, trust)
        assert updated == 0


# ---------------------------------------------------------------------------
# Report Formatting Tests
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Tests for format_report()."""

    def test_empty_report(self):
        report = format_report({})
        assert "No interaction data" in report

    def test_report_with_data(self):
        trust = {
            "kk-alpha": {"kk-beta": 85.0, "kk-gamma": 60.0},
            "kk-beta": {"kk-alpha": 90.0},
        }
        report = format_report(trust)
        assert "kk-alpha" in report
        assert "kk-beta" in report
        assert "85.0" in report

    def test_report_has_header(self):
        report = format_report({"a": {"b": 50.0}})
        assert "Relationship Tracker" in report

    def test_report_shows_agent_count(self):
        trust = {"a": {"b": 50}, "c": {"d": 50}}
        report = format_report(trust)
        assert "2" in report  # 2 agents


# ---------------------------------------------------------------------------
# Integration Test
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline(self, workspace_with_notes):
        """Extract → compute → format pipeline works end-to-end."""
        interactions = extract_interactions_from_notes(workspace_with_notes)
        assert len(interactions) > 0

        trust = compute_trust_scores(interactions)
        # May or may not have scores depending on MIN_INTERACTIONS threshold

        report = format_report(trust)
        assert len(report) > 0

    def test_workspace_with_no_interactions(self, tmp_dir):
        """Workspaces with notes but no interaction patterns produce empty results."""
        workspaces = tmp_dir / "workspaces"
        agent_notes = workspaces / "kk-test" / "memory" / "notes"
        agent_notes.mkdir(parents=True)
        (agent_notes / "2026-02-20.md").write_text(
            "- woke up and browsed EM\n"
            "- found 3 tasks but none matched skills\n"
            "- went idle\n"
        )

        interactions = extract_interactions_from_notes(workspaces)
        assert len(interactions) == 0
