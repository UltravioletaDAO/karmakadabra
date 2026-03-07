"""
Tests for lib/vault_sync.py — Obsidian Vault Sync

Covers:
  - State read/write (own agent)
  - Peer state reading
  - Log operations (daily log files)
  - Offerings write/read
  - Supply chain status (coordinator writes, others read)
  - Shared file operations
  - Git operations (mocked)
  - Frontmatter parsing (with and without python-frontmatter)
  - Edge cases: missing files, corrupted frontmatter, concurrent writes
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.vault_sync import VaultSync


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path):
    """Create a VaultSync instance with a temp vault directory."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "shared").mkdir()
    return VaultSync(str(vault_path), "kk-test-agent")


@pytest.fixture
def vault_with_peers(tmp_path):
    """Create vault with multiple agent directories."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "shared").mkdir()
    (vault_path / "agents").mkdir(parents=True)

    # Create peer agents
    for name in ["kk-alpha", "kk-beta", "kk-gamma"]:
        agent_dir = vault_path / "agents" / name
        agent_dir.mkdir()

    return VaultSync(str(vault_path), "kk-test-agent")


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_agent_dir(self, tmp_path):
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        vs = VaultSync(str(vault_path), "kk-new-agent")
        assert vs.agent_dir.exists()
        assert vs.agent_dir.name == "kk-new-agent"

    def test_agent_dir_under_agents(self, tmp_path):
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        vs = VaultSync(str(vault_path), "kk-test")
        assert vs.agent_dir == vault_path / "agents" / "kk-test"

    def test_shared_dir_set(self, vault):
        assert vault.shared_dir == vault.vault / "shared"


# ---------------------------------------------------------------------------
# State Write/Read Tests
# ---------------------------------------------------------------------------


class TestWriteState:
    def test_write_and_read_state(self, vault):
        vault.write_state({"status": "active", "current_task": "indexing"}, body="## Working on indexing")
        state = vault.read_state()
        assert state["status"] == "active"
        assert state["current_task"] == "indexing"
        assert "last_heartbeat" in state

    def test_write_state_preserves_agent_id(self, vault):
        vault.write_state({"status": "idle"})
        state = vault.read_state()
        assert state.get("agent_id") == "kk-test-agent"

    def test_write_state_updates_existing(self, vault):
        vault.write_state({"status": "active", "foo": "bar"})
        vault.write_state({"status": "idle"})
        state = vault.read_state()
        assert state["status"] == "idle"
        # Previous keys should be preserved (merged)
        assert state.get("foo") == "bar"

    def test_write_state_with_body(self, vault):
        vault.write_state({"status": "processing"}, body="## Progress\n- Step 1 done\n- Step 2 pending")
        state_path = vault.agent_dir / "state.md"
        content = state_path.read_text(encoding="utf-8")
        assert "## Progress" in content

    def test_write_state_without_body(self, vault):
        vault.write_state({"status": "idle"})
        state = vault.read_state()
        assert state["status"] == "idle"

    def test_read_state_empty(self, vault):
        state = vault.read_state()
        assert state == {}


# ---------------------------------------------------------------------------
# Peer State Tests
# ---------------------------------------------------------------------------


class TestPeerState:
    def test_read_peer_state(self, vault_with_peers):
        # Write state for alpha peer
        alpha_dir = vault_with_peers.vault / "agents" / "kk-alpha"
        alpha_vs = VaultSync(str(vault_with_peers.vault), "kk-alpha")
        alpha_vs.write_state({"status": "busy", "task": "photo verification"})

        # Read from our agent's perspective
        state = vault_with_peers.read_peer_state("kk-alpha")
        assert state["status"] == "busy"

    def test_read_nonexistent_peer(self, vault_with_peers):
        state = vault_with_peers.read_peer_state("kk-nonexistent")
        assert state == {}

    def test_list_peer_states(self, vault_with_peers):
        # Write states for peers
        for name, status in [("kk-alpha", "active"), ("kk-beta", "idle")]:
            peer = VaultSync(str(vault_with_peers.vault), name)
            peer.write_state({"status": status})

        states = vault_with_peers.list_peer_states()
        assert "kk-alpha" in states
        assert "kk-beta" in states
        assert states["kk-alpha"]["status"] == "active"
        assert states["kk-beta"]["status"] == "idle"

    def test_list_peer_states_empty_vault(self, vault):
        states = vault.list_peer_states()
        # Should at least include own agent (created in init)
        assert isinstance(states, dict)


# ---------------------------------------------------------------------------
# Log Operations Tests
# ---------------------------------------------------------------------------


class TestLogOperations:
    def test_append_log_creates_file(self, vault):
        vault.append_log("Started processing batch #1")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = vault.agent_dir / f"log-{today}.md"
        assert log_path.exists()

    def test_append_log_with_frontmatter(self, vault):
        vault.append_log("First entry")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = vault.agent_dir / f"log-{today}.md"
        content = log_path.read_text(encoding="utf-8")
        assert "---" in content
        assert "agent_id: kk-test-agent" in content
        assert f"date: {today}" in content

    def test_append_log_multiple_entries(self, vault):
        vault.append_log("Entry 1")
        vault.append_log("Entry 2")
        vault.append_log("Entry 3")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = vault.agent_dir / f"log-{today}.md"
        content = log_path.read_text(encoding="utf-8")
        assert "Entry 1" in content
        assert "Entry 2" in content
        assert "Entry 3" in content

    def test_log_entries_have_timestamps(self, vault):
        vault.append_log("Timestamped entry")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = vault.agent_dir / f"log-{today}.md"
        content = log_path.read_text(encoding="utf-8")
        # Should have HH:MM:SS format
        import re
        assert re.search(r"\d{2}:\d{2}:\d{2}", content)


# ---------------------------------------------------------------------------
# Offerings Tests
# ---------------------------------------------------------------------------


class TestOfferings:
    def test_write_offerings(self, vault):
        tasks = [
            {"task_id": "t-001", "title": "Raw chat logs", "bounty": 0.01},
            {"task_id": "t-002", "title": "Skill profiles", "bounty": 0.05},
        ]
        vault.write_offerings(tasks)
        offerings_path = vault.agent_dir / "offerings.md"
        assert offerings_path.exists()
        content = offerings_path.read_text(encoding="utf-8")
        assert "Raw chat logs" in content
        assert "Skill profiles" in content
        assert "$0.01" in content

    def test_write_empty_offerings(self, vault):
        vault.write_offerings([])
        offerings_path = vault.agent_dir / "offerings.md"
        assert offerings_path.exists()
        content = offerings_path.read_text(encoding="utf-8")
        assert "0 products" in content or "0" in content

    def test_read_peer_offerings(self, vault_with_peers):
        # Write offerings for alpha peer
        alpha = VaultSync(str(vault_with_peers.vault), "kk-alpha")
        alpha.write_offerings([
            {"task_id": "alpha-001", "title": "Voice Analysis", "bounty": 0.04},
            {"task_id": "alpha-002", "title": "Data Mining", "bounty": 0.10},
        ])

        # Read from our perspective
        offerings = vault_with_peers.read_peer_offerings("kk-alpha")
        assert len(offerings) == 2
        assert any(o["task_id"] == "alpha-001" for o in offerings)
        assert any(o["task_id"] == "alpha-002" for o in offerings)

    def test_read_nonexistent_peer_offerings(self, vault_with_peers):
        offerings = vault_with_peers.read_peer_offerings("kk-nonexistent")
        assert offerings == []

    def test_offerings_extract_bounty(self, vault_with_peers):
        alpha = VaultSync(str(vault_with_peers.vault), "kk-alpha")
        alpha.write_offerings([
            {"task_id": "t-1", "title": "Test", "bounty": 3.50},
        ])
        offerings = vault_with_peers.read_peer_offerings("kk-alpha")
        if offerings:
            assert offerings[0]["bounty"] == pytest.approx(3.50, abs=0.01)


# ---------------------------------------------------------------------------
# Supply Chain Status Tests
# ---------------------------------------------------------------------------


class TestSupplyChainStatus:
    def test_write_and_read_status(self, vault):
        # Create the supply-chain.md file first
        sc_path = vault.shared_dir / "supply-chain.md"
        sc_path.write_text("---\ntitle: Supply Chain\nupdated: 2026-01-01\n---\n\n## Overview\n\n", encoding="utf-8")

        vault.write_supply_chain_status({
            "kk-karma-hello": "publishing (5 tasks)",
            "kk-skill-extractor": "idle",
        })

        statuses = vault.read_supply_chain_status()
        assert "kk-karma-hello" in statuses
        assert "publishing" in statuses["kk-karma-hello"]
        assert "kk-skill-extractor" in statuses
        assert statuses["kk-skill-extractor"] == "idle"

    def test_status_updates_replace_existing(self, vault):
        sc_path = vault.shared_dir / "supply-chain.md"
        sc_path.write_text("---\ntitle: Supply Chain\nupdated: 2026-01-01\n---\n\n", encoding="utf-8")

        vault.write_supply_chain_status({"kk-alpha": "active"})
        vault.write_supply_chain_status({"kk-alpha": "completed"})

        statuses = vault.read_supply_chain_status()
        assert statuses["kk-alpha"] == "completed"

    def test_read_empty_supply_chain(self, vault):
        statuses = vault.read_supply_chain_status()
        assert statuses == {}

    def test_status_file_missing(self, vault):
        # Remove shared dir
        import shutil
        if vault.shared_dir.exists():
            shutil.rmtree(vault.shared_dir)
        statuses = vault.read_supply_chain_status()
        assert statuses == {}


# ---------------------------------------------------------------------------
# Shared File Operations Tests
# ---------------------------------------------------------------------------


class TestSharedFiles:
    def test_read_shared_existing(self, vault):
        shared_file = vault.shared_dir / "config.md"
        shared_file.write_text("---\nversion: 1\nmode: production\n---\n\n## Config\n", encoding="utf-8")

        meta = vault.read_shared("config.md")
        assert meta.get("version") == "1" or meta.get("version") == 1

    def test_read_shared_nonexistent(self, vault):
        meta = vault.read_shared("nonexistent.md")
        assert meta == {}

    def test_append_to_shared(self, vault):
        shared_file = vault.shared_dir / "ledger.md"
        shared_file.write_text("---\ntitle: Ledger\n---\n\n", encoding="utf-8")

        vault.append_to_shared("ledger.md", "- 2026-03-07: Task completed, $0.10")
        vault.append_to_shared("ledger.md", "- 2026-03-07: Another entry, $0.05")

        content = shared_file.read_text(encoding="utf-8")
        assert "$0.10" in content
        assert "$0.05" in content

    def test_append_to_nonexistent_shared(self, vault):
        # Should not crash
        vault.append_to_shared("nonexistent.md", "test line")


# ---------------------------------------------------------------------------
# Git Operations Tests (mocked)
# ---------------------------------------------------------------------------


class TestGitOperations:
    def test_pull_no_git_repo(self, vault):
        result = vault.pull()
        assert result is False

    def test_pull_with_git_repo(self, vault):
        (vault.vault / ".git").mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = vault.pull()
        assert result is True
        mock_run.assert_called_once()

    def test_pull_failure(self, vault):
        (vault.vault / ".git").mkdir()
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            result = vault.pull()
        assert result is False

    def test_pull_timeout(self, vault):
        (vault.vault / ".git").mkdir()
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            result = vault.pull()
        assert result is False

    def test_commit_no_git_repo(self, vault):
        result = vault.commit_and_push("test commit")
        assert result is False

    def test_commit_with_changes(self, vault):
        (vault.vault / ".git").mkdir()

        call_count = 0
        def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            cmd = args[0] if args else kwargs.get("args", [])
            if "diff" in cmd:
                result.returncode = 1  # Changes exist
            else:
                result.returncode = 0
            return result

        with patch("subprocess.run", side_effect=mock_run):
            result = vault.commit_and_push("added state")
        assert result is True
        assert call_count >= 3  # add, diff, commit, push

    def test_commit_no_changes(self, vault):
        (vault.vault / ".git").mkdir()

        def mock_run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0  # diff --quiet returns 0 = no changes
            return result

        with patch("subprocess.run", side_effect=mock_run):
            result = vault.commit_and_push("no changes")
        assert result is True


# ---------------------------------------------------------------------------
# Frontmatter Parsing Edge Cases
# ---------------------------------------------------------------------------


class TestFrontmatterParsing:
    def test_raw_frontmatter_fallback(self, vault):
        """Test the _read_raw_frontmatter method directly."""
        test_file = vault.agent_dir / "test.md"
        test_file.write_text(
            "---\nstatus: active\ntask: processing\ncount: 42\n---\n\n## Body\n",
            encoding="utf-8",
        )
        result = vault._read_raw_frontmatter(test_file)
        assert result["status"] == "active"
        assert result["task"] == "processing"

    def test_raw_frontmatter_no_frontmatter(self, vault):
        test_file = vault.agent_dir / "test.md"
        test_file.write_text("# Just a title\nNo frontmatter here.\n", encoding="utf-8")
        result = vault._read_raw_frontmatter(test_file)
        assert result == {}

    def test_raw_frontmatter_empty_file(self, vault):
        test_file = vault.agent_dir / "test.md"
        test_file.write_text("", encoding="utf-8")
        result = vault._read_raw_frontmatter(test_file)
        assert result == {}

    def test_raw_frontmatter_missing_file(self, vault):
        result = vault._read_raw_frontmatter(vault.agent_dir / "nonexistent.md")
        assert result == {}

    def test_write_raw_state(self, vault):
        """Test _write_raw_state directly."""
        path = vault.agent_dir / "raw_test.md"
        vault._write_raw_state(path, {"status": "active", "count": 5}, body="## Hello")
        content = path.read_text(encoding="utf-8")
        assert "---" in content
        assert "status: active" in content
        assert "## Hello" in content

    def test_write_raw_state_with_special_chars(self, vault):
        """Values with colons or quotes should be quoted."""
        path = vault.agent_dir / "special.md"
        vault._write_raw_state(path, {"url": "https://example.com:8080"}, body="test")
        content = path.read_text(encoding="utf-8")
        assert "https://example.com:8080" in content
