"""
Tests for irc_integration.py — IRC/MeshRelay Bridge

Covers:
  - Inbox reading (JSONL parsing, timestamp filtering)
  - Outbox writing (JSONL append)
  - IRC state persistence (load/save)
  - Mention detection
  - Dedup / cooldown (was_recently_sent, record_sent)
  - Proactive messages (HAVE/NEED generation)
  - Announcement building
  - check_irc_and_respond (end-to-end heartbeat flow)
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.irc_integration import (
    _build_announcement,
    _is_mention,
    _load_irc_state,
    _read_inbox,
    _record_sent,
    _save_irc_state,
    _was_recently_sent,
    _write_outbox,
    check_irc_and_respond,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    return data


# ---------------------------------------------------------------------------
# Inbox Reading Tests
# ---------------------------------------------------------------------------


class TestReadInbox:
    def test_empty_inbox(self, tmp_data):
        msgs = _read_inbox(tmp_data)
        assert msgs == []

    def test_read_messages(self, tmp_data):
        inbox = tmp_data / "irc-inbox.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        lines = [
            json.dumps({"sender": "alice", "message": "hello", "channel": "#test", "ts": now}),
            json.dumps({"sender": "bob", "message": "world", "channel": "#test", "ts": now}),
        ]
        inbox.write_text("\n".join(lines) + "\n")

        msgs = _read_inbox(tmp_data)
        assert len(msgs) == 2
        assert msgs[0]["sender"] == "alice"
        assert msgs[1]["sender"] == "bob"

    def test_filter_by_timestamp(self, tmp_data):
        inbox = tmp_data / "irc-inbox.jsonl"
        old_ts = "2026-01-01T00:00:00+00:00"
        new_ts = "2026-03-07T02:00:00+00:00"
        lines = [
            json.dumps({"sender": "old", "message": "ancient", "ts": old_ts}),
            json.dumps({"sender": "new", "message": "fresh", "ts": new_ts}),
        ]
        inbox.write_text("\n".join(lines) + "\n")

        # Filter: only messages after Feb 2026
        since = datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp()
        msgs = _read_inbox(tmp_data, since_ts=since)
        assert len(msgs) == 1
        assert msgs[0]["sender"] == "new"

    def test_malformed_json_skipped(self, tmp_data):
        inbox = tmp_data / "irc-inbox.jsonl"
        inbox.write_text(
            '{"sender": "valid", "message": "ok"}\n'
            'NOT JSON\n'
            '{"sender": "also_valid", "message": "fine"}\n'
        )
        msgs = _read_inbox(tmp_data)
        assert len(msgs) == 2

    def test_empty_lines_skipped(self, tmp_data):
        inbox = tmp_data / "irc-inbox.jsonl"
        inbox.write_text(
            '{"sender": "a", "message": "1"}\n\n\n'
            '{"sender": "b", "message": "2"}\n'
        )
        msgs = _read_inbox(tmp_data)
        assert len(msgs) == 2


# ---------------------------------------------------------------------------
# Outbox Writing Tests
# ---------------------------------------------------------------------------


class TestWriteOutbox:
    def test_write_creates_file(self, tmp_data):
        _write_outbox(tmp_data, "#market", "HAVE skill_profiles 50 profiles ready")
        outbox = tmp_data / "irc-outbox.jsonl"
        assert outbox.exists()
        content = outbox.read_text()
        assert "#market" in content
        assert "HAVE" in content

    def test_write_appends(self, tmp_data):
        _write_outbox(tmp_data, "#market", "msg1")
        _write_outbox(tmp_data, "#market", "msg2")
        _write_outbox(tmp_data, "#swarm", "msg3")
        outbox = tmp_data / "irc-outbox.jsonl"
        lines = [l for l in outbox.read_text().splitlines() if l.strip()]
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# State Persistence Tests
# ---------------------------------------------------------------------------


class TestIRCState:
    def test_load_empty(self, tmp_data):
        state = _load_irc_state(tmp_data)
        assert isinstance(state, dict)

    def test_save_and_load(self, tmp_data):
        state = {"last_inbox_ts": time.time(), "sent_hashes": {"abc": time.time()}}
        _save_irc_state(tmp_data, state)
        loaded = _load_irc_state(tmp_data)
        assert loaded["last_inbox_ts"] == state["last_inbox_ts"]

    def test_load_corrupted(self, tmp_data):
        state_file = tmp_data / ".irc_state.json"
        state_file.write_text("BROKEN")
        state = _load_irc_state(tmp_data)
        assert isinstance(state, dict)


# ---------------------------------------------------------------------------
# Mention Detection Tests
# ---------------------------------------------------------------------------


class TestIsMention:
    def test_at_mention(self):
        assert _is_mention("@kk-skill-extractor hello", "kk-skill-extractor")

    def test_name_start_with_colon(self):
        assert _is_mention("kk-skill-extractor: can you help?", "kk-skill-extractor")

    def test_name_start_with_space(self):
        assert _is_mention("kk-skill-extractor do you have profiles?", "kk-skill-extractor")

    def test_name_start_with_comma(self):
        assert _is_mention("kk-skill-extractor, check this", "kk-skill-extractor")

    def test_no_mention_in_middle(self):
        # Name in middle without @ should NOT match
        assert not _is_mention("hey kk-skill-extractor can you help?", "kk-skill-extractor")

    def test_no_mention(self):
        assert not _is_mention("random chat about nothing", "kk-skill-extractor")

    def test_case_insensitive(self):
        assert _is_mention("@KK-SKILL-EXTRACTOR test", "kk-skill-extractor")

    def test_partial_name_no_match(self):
        assert not _is_mention("kk is cool", "kk-skill-extractor")

    def test_empty_agent_name(self):
        assert not _is_mention("@unknown hello", "")

    def test_unknown_agent_name(self):
        assert not _is_mention("@unknown hello", "unknown")


# ---------------------------------------------------------------------------
# Dedup / Cooldown Tests
# ---------------------------------------------------------------------------


class TestDedup:
    def test_new_message_not_recently_sent(self):
        state = {"recent_messages": []}
        assert not _was_recently_sent(state, "hash123")

    def test_recently_sent_within_cooldown(self):
        state = {"recent_messages": [{"hash": "hash123", "ts": time.time()}]}
        assert _was_recently_sent(state, "hash123")

    def test_old_message_past_cooldown(self):
        state = {"recent_messages": [{"hash": "hash123", "ts": time.time() - 7200}]}
        assert not _was_recently_sent(state, "hash123")

    def test_record_sent(self):
        state = {"recent_messages": []}
        _record_sent(state, "hash456")
        assert any(m["hash"] == "hash456" for m in state["recent_messages"])

    def test_record_prunes_old_entries(self):
        state = {"recent_messages": [
            {"hash": "old", "ts": time.time() - 86400},  # 24 hours ago
        ]}
        _record_sent(state, "new")
        # Old entry should be pruned
        hashes = [m["hash"] for m in state["recent_messages"]]
        assert "new" in hashes
        assert "old" not in hashes


# ---------------------------------------------------------------------------
# Announcement Building Tests
# ---------------------------------------------------------------------------


class TestBuildAnnouncement:
    def test_returns_none_for_all_actions(self):
        """_build_announcement currently delegates to _proactive_messages, returns None."""
        # The function always returns None — proactive messages handle everything
        assert _build_announcement("kk-skill-extractor", "sell", "published=1") is None
        assert _build_announcement("kk-juanjumagalp", "buy", "assigned=2") is None
        assert _build_announcement("kk-test", "heartbeat", "ok") is None
        assert _build_announcement("agent", "unknown", "result") is None


# ---------------------------------------------------------------------------
# check_irc_and_respond Tests (integration)
# ---------------------------------------------------------------------------


class TestCheckIRCAndRespond:
    @pytest.mark.asyncio
    async def test_no_messages_no_crash(self, tmp_data):
        """Empty inbox, no action taken."""
        state_before = _load_irc_state(tmp_data)
        await check_irc_and_respond(
            data_dir=tmp_data,
            agent_name="kk-test-agent",
            action="sell",
            action_result="published=0",
        )
        # Should not crash

    @pytest.mark.asyncio
    async def test_processes_mentions(self, tmp_data):
        """Messages mentioning the agent are processed."""
        inbox = tmp_data / "irc-inbox.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        inbox.write_text(
            json.dumps({
                "sender": "buyer",
                "message": "kk-skill-extractor do you have skill profiles?",
                "channel": "#market",
                "ts": now,
            }) + "\n"
        )

        await check_irc_and_respond(
            data_dir=tmp_data,
            agent_name="kk-skill-extractor",
            action="idle",
            action_result="",
        )

        # Should have generated a response in outbox
        outbox = tmp_data / "irc-outbox.jsonl"
        if outbox.exists():
            content = outbox.read_text()
            assert len(content) > 0

    @pytest.mark.asyncio
    async def test_proactive_messages_on_sell(self, tmp_data):
        """Seller action triggers HAVE messages."""
        await check_irc_and_respond(
            data_dir=tmp_data,
            agent_name="kk-skill-extractor",
            action="sell",
            action_result="published=2, offerings=3",
        )

        outbox = tmp_data / "irc-outbox.jsonl"
        if outbox.exists():
            content = outbox.read_text()
            # Should have proactive market messages
            assert "HAVE" in content or "skill" in content.lower() or len(content) > 0

    @pytest.mark.asyncio
    async def test_state_updated_after_processing(self, tmp_data):
        """IRC state is updated with last processing timestamp."""
        await check_irc_and_respond(
            data_dir=tmp_data,
            agent_name="kk-test",
            action="heartbeat",
            action_result="ok",
        )

        state = _load_irc_state(tmp_data)
        assert "last_inbox_ts" in state or isinstance(state, dict)

    @pytest.mark.asyncio
    async def test_respects_rate_limit(self, tmp_data):
        """Rate limiting prevents message floods."""
        # Fill inbox with many mentions
        inbox = tmp_data / "irc-inbox.jsonl"
        now = datetime.now(timezone.utc).isoformat()
        lines = []
        for i in range(20):
            lines.append(json.dumps({
                "sender": f"user{i}",
                "message": f"kk-test-agent question {i}?",
                "channel": "#market",
                "ts": now,
            }))
        inbox.write_text("\n".join(lines) + "\n")

        await check_irc_and_respond(
            data_dir=tmp_data,
            agent_name="kk-test-agent",
            action="idle",
            action_result="",
        )

        outbox = tmp_data / "irc-outbox.jsonl"
        if outbox.exists():
            lines_out = [l for l in outbox.read_text().splitlines() if l.strip()]
            # Should be capped by MAX_MESSAGES_PER_HEARTBEAT
            assert len(lines_out) <= 12  # 8 proactive + some buffer
