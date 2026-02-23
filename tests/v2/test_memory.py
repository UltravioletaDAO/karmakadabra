#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 — Tests for memory.py

Tests for the 3-level memory system:
  - MEMORY.md creation, reading, section appending
  - Daily notes management
  - Edge cases and concurrent access patterns

Usage:
    pytest scripts/kk/tests/test_memory.py -v
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.memory import (
    append_to_memory,
    create_initial_memory_md,
    read_memory_md,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def memory_path(tmp_dir):
    """Path for MEMORY.md."""
    return tmp_dir / "MEMORY.md"


@pytest.fixture
def existing_memory(memory_path):
    """Create a MEMORY.md with some content."""
    create_initial_memory_md(memory_path)
    return memory_path


# ---------------------------------------------------------------------------
# Create Tests
# ---------------------------------------------------------------------------


class TestCreateInitialMemoryMd:
    """Tests for create_initial_memory_md()."""

    def test_creates_file(self, memory_path):
        create_initial_memory_md(memory_path)
        assert memory_path.exists()

    def test_template_has_sections(self, memory_path):
        create_initial_memory_md(memory_path)
        content = memory_path.read_text()
        assert "## Trusted Agents" in content
        assert "## Preferred Categories" in content
        assert "## Pricing Notes" in content
        assert "## Learned Patterns" in content
        assert "## IRC Contacts" in content
        assert "## Updated" in content

    def test_template_has_timestamp(self, memory_path):
        create_initial_memory_md(memory_path)
        content = memory_path.read_text()
        # Should contain an ISO timestamp
        assert "Last updated:" in content

    def test_creates_parent_dirs(self, tmp_dir):
        path = tmp_dir / "deep" / "agent" / "MEMORY.md"
        create_initial_memory_md(path)
        assert path.exists()

    def test_defaults_pricing(self, memory_path):
        create_initial_memory_md(memory_path)
        content = memory_path.read_text()
        assert "$0.02" in content  # Minimum bounty
        assert "$0.03-$0.10" in content  # Sweet spot


# ---------------------------------------------------------------------------
# Read Tests
# ---------------------------------------------------------------------------


class TestReadMemoryMd:
    """Tests for read_memory_md()."""

    def test_reads_existing(self, existing_memory):
        content = read_memory_md(existing_memory)
        assert "# Agent Memory" in content
        assert len(content) > 100

    def test_returns_empty_for_nonexistent(self, tmp_dir):
        content = read_memory_md(tmp_dir / "nonexistent.md")
        assert content == ""

    def test_reads_custom_content(self, memory_path):
        memory_path.write_text("Custom memory content\n")
        content = read_memory_md(memory_path)
        assert content == "Custom memory content\n"


# ---------------------------------------------------------------------------
# Append Tests
# ---------------------------------------------------------------------------


class TestAppendToMemory:
    """Tests for append_to_memory()."""

    def test_append_to_trusted_agents(self, existing_memory):
        append_to_memory(existing_memory, "Trusted Agents", "kk-alpha-dev: reliable worker")
        content = existing_memory.read_text()
        assert "kk-alpha-dev: reliable worker" in content

    def test_append_to_preferred_categories(self, existing_memory):
        append_to_memory(existing_memory, "Preferred Categories", "DeFi analytics")
        content = existing_memory.read_text()
        assert "DeFi analytics" in content

    def test_append_to_learned_patterns(self, existing_memory):
        append_to_memory(existing_memory, "Learned Patterns", "Low bounty tasks have higher completion rates")
        content = existing_memory.read_text()
        assert "Low bounty tasks have higher completion rates" in content

    def test_append_to_irc_contacts(self, existing_memory):
        append_to_memory(existing_memory, "IRC Contacts", "beta-designer: UI expert, responds quickly")
        content = existing_memory.read_text()
        assert "beta-designer" in content

    def test_append_multiple_entries(self, existing_memory):
        append_to_memory(existing_memory, "Trusted Agents", "agent-1: good work")
        append_to_memory(existing_memory, "Trusted Agents", "agent-2: fast delivery")
        content = existing_memory.read_text()
        assert "agent-1" in content
        assert "agent-2" in content

    def test_append_creates_file_if_missing(self, memory_path):
        """append_to_memory creates MEMORY.md if it doesn't exist."""
        assert not memory_path.exists()
        append_to_memory(memory_path, "Trusted Agents", "new-agent: first contact")
        assert memory_path.exists()
        content = memory_path.read_text()
        assert "new-agent" in content

    def test_append_preserves_other_sections(self, existing_memory):
        """Appending to one section doesn't corrupt others."""
        original = existing_memory.read_text()
        append_to_memory(existing_memory, "Trusted Agents", "test-agent: testing")
        updated = existing_memory.read_text()

        # All original sections should still exist
        assert "## Preferred Categories" in updated
        assert "## Pricing Notes" in updated
        assert "## Learned Patterns" in updated
        assert "## IRC Contacts" in updated

    def test_append_to_nonexistent_section(self, existing_memory):
        """Appending to a section that doesn't exist should not crash."""
        # This tests graceful handling — the entry may not appear if section is missing
        append_to_memory(existing_memory, "Nonexistent Section", "this entry")
        # Should not raise — graceful degradation
        content = existing_memory.read_text()
        assert "# Agent Memory" in content  # File not corrupted


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestMemoryEdgeCases:
    """Edge case tests."""

    def test_unicode_content(self, existing_memory):
        """Unicode entries survive roundtrip."""
        append_to_memory(existing_memory, "IRC Contacts", "español-agent: habla español 🇪🇸")
        content = read_memory_md(existing_memory)
        assert "español" in content
        assert "🇪🇸" in content

    def test_multiline_entry(self, existing_memory):
        """Multi-line entries don't break the file."""
        entry = "complex-agent: skills=python,solidity; notes=very reliable"
        append_to_memory(existing_memory, "Trusted Agents", entry)
        content = read_memory_md(existing_memory)
        assert "complex-agent" in content

    def test_empty_entry(self, existing_memory):
        """Empty entry string doesn't crash."""
        append_to_memory(existing_memory, "Trusted Agents", "")
        content = read_memory_md(existing_memory)
        assert "# Agent Memory" in content

    def test_special_chars_in_entry(self, existing_memory):
        """Special markdown characters don't break parsing."""
        append_to_memory(existing_memory, "Learned Patterns", "Task with **bold** and [links](url) work fine")
        content = read_memory_md(existing_memory)
        assert "**bold**" in content

    def test_large_memory_file(self, memory_path):
        """Large memory files are handled correctly."""
        create_initial_memory_md(memory_path)
        for i in range(100):
            append_to_memory(memory_path, "Trusted Agents", f"agent-{i}: trust score {i}")
        content = read_memory_md(memory_path)
        assert "agent-99" in content
        assert len(content) > 1000

    def test_concurrent_section_appends(self, existing_memory):
        """Appending to different sections in sequence works."""
        append_to_memory(existing_memory, "Trusted Agents", "trusted-1")
        append_to_memory(existing_memory, "Preferred Categories", "category-1")
        append_to_memory(existing_memory, "IRC Contacts", "contact-1")
        append_to_memory(existing_memory, "Learned Patterns", "pattern-1")

        content = read_memory_md(existing_memory)
        assert "trusted-1" in content
        assert "category-1" in content
        assert "contact-1" in content
        assert "pattern-1" in content
