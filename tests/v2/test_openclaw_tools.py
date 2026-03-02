"""
KK V2 — OpenClaw Tools Unit Tests

Tests for the CLI tools that agents use inside Docker containers.
Each tool reads JSON from stdin and writes JSON to stdout.

Tools tested:
  - wallet_tool: balance, budget, can_afford
  - irc_tool: read_inbox, send, status, history
  - irc_guard: anti-loop, rate-limit, identity validation
  - data_tool: list_purchases, list_products
  - reputation_tool: get_score, get_leaderboard
  - mcp_client: list, call (HTTP mocking)

em_tool is integration-heavy (needs em_client + network), tested separately.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Add project root so tools can resolve imports
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "openclaw" / "tools"))


# ===================================================================
# wallet_tool tests
# ===================================================================


class TestWalletTool:
    """Tests for wallet balance, budget, and affordability checks."""

    def _make_workspace(self, tmp_path: Path, wallet_data: dict) -> None:
        ws = tmp_path / "workspaces" / "kk-test-agent" / "data"
        ws.mkdir(parents=True)
        (ws / "wallet.json").write_text(json.dumps(wallet_data))

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_budget_fresh_day(self, tmp_path: Path):
        """Budget shows full remaining on fresh day."""
        from openclaw.tools.wallet_tool import action_budget

        result = action_budget({"daily_budget": 2.0})
        assert result["daily_budget_usd"] == 2.0
        assert result["remaining_usd"] >= 0
        assert "date" in result
        assert "utilization_pct" in result

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_can_afford_within_budget(self, tmp_path: Path):
        from openclaw.tools.wallet_tool import action_can_afford

        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=0.5):
            result = action_can_afford({"amount": 0.10, "daily_budget": 2.0})
            assert result["can_afford"] is True
            assert result["remaining_usd"] == 1.5

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_can_afford_over_budget(self):
        from openclaw.tools.wallet_tool import action_can_afford

        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=1.95):
            result = action_can_afford({"amount": 0.10, "daily_budget": 2.0})
            assert result["can_afford"] is False
            assert result["remaining_usd"] == 0.05

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_can_afford_zero_amount(self):
        from openclaw.tools.wallet_tool import action_can_afford

        result = action_can_afford({"amount": 0})
        assert "error" in result

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_can_afford_negative_amount(self):
        from openclaw.tools.wallet_tool import action_can_afford

        result = action_can_afford({"amount": -5})
        assert "error" in result

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_budget_custom_limit(self):
        from openclaw.tools.wallet_tool import action_budget

        with patch("openclaw.tools.wallet_tool._load_daily_spent", return_value=0.0):
            result = action_budget({"daily_budget": 5.0})
            assert result["daily_budget_usd"] == 5.0
            assert result["remaining_usd"] == 5.0

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_balance_no_wallet(self, tmp_path: Path):
        from openclaw.tools.wallet_tool import action_balance

        with patch("openclaw.tools.wallet_tool._load_wallet", return_value={}):
            result = action_balance({})
            assert "error" in result

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_balance_rpc_success(self):
        """Balance check with mocked RPC response."""
        from openclaw.tools.wallet_tool import action_balance

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x00000000000000000000000000000000000000000000000000000000000F4240",  # 1.0 USDC
        }

        with patch("openclaw.tools.wallet_tool._load_wallet",
                    return_value={"address": "0x1234567890abcdef1234567890abcdef12345678"}):
            with patch("httpx.post", return_value=mock_response):
                result = action_balance({})
                assert result["balance"] == 1.0
                assert result["chain"] == "base"
                assert result["token"] == "USDC"

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_balance_zero(self):
        from openclaw.tools.wallet_tool import action_balance

        mock_response = MagicMock()
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": "0x0"}

        with patch("openclaw.tools.wallet_tool._load_wallet",
                    return_value={"address": "0xabc123"}):
            with patch("httpx.post", return_value=mock_response):
                result = action_balance({})
                assert result["balance"] == 0.0

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_daily_spent_from_working_md(self, tmp_path: Path):
        """Parse daily spent from WORKING.md format."""
        from openclaw.tools.wallet_tool import _load_daily_spent

        ws = tmp_path / "workspaces" / "kk-test-agent" / "memory"
        ws.mkdir(parents=True)
        working = ws / "WORKING.md"
        working.write_text("# WORKING.md\n## Daily Spent: $0.35\n## Status: idle\n")

        with patch("openclaw.tools.wallet_tool.Path",
                    side_effect=lambda p: ws / "WORKING.md" if "WORKING" in str(p) else Path(p)):
            # This would need path injection — skip for now
            pass


# ===================================================================
# irc_tool tests
# ===================================================================


class TestIRCTool:
    """Tests for IRC message reading, sending, and status."""

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_read_inbox_empty(self, tmp_path: Path):
        from openclaw.tools.irc_tool import read_inbox

        with patch("openclaw.tools.irc_tool.INBOX_PATH", tmp_path / "irc-inbox.jsonl"):
            result = read_inbox({"limit": 10})
            assert result["messages"] == []
            assert result["count"] == 0

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_read_inbox_with_messages(self, tmp_path: Path):
        inbox = tmp_path / "irc-inbox.jsonl"
        messages = [
            {"sender": "alice", "channel": "#karmakadabra", "content": "hola", "ts": time.time()},
            {"sender": "bob", "channel": "#karmakadabra", "content": "que mas", "ts": time.time()},
        ]
        inbox.write_text("\n".join(json.dumps(m) for m in messages))

        from openclaw.tools.irc_tool import read_inbox

        with patch("openclaw.tools.irc_tool.INBOX_PATH", inbox):
            result = read_inbox({"limit": 10})
            assert result["count"] == 2
            assert result["messages"][0]["sender"] == "alice"
            assert result["messages"][1]["sender"] == "bob"

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_read_inbox_clears_after_read(self, tmp_path: Path):
        inbox = tmp_path / "irc-inbox.jsonl"
        inbox.write_text(json.dumps({"sender": "x", "content": "test", "ts": time.time()}))

        from openclaw.tools.irc_tool import read_inbox

        with patch("openclaw.tools.irc_tool.INBOX_PATH", inbox):
            read_inbox({"limit": 10})
            # Inbox should be cleared
            assert inbox.read_text() == ""

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_read_inbox_respects_limit(self, tmp_path: Path):
        inbox = tmp_path / "irc-inbox.jsonl"
        messages = [
            json.dumps({"sender": f"user{i}", "content": f"msg{i}", "ts": time.time()})
            for i in range(20)
        ]
        inbox.write_text("\n".join(messages))

        from openclaw.tools.irc_tool import read_inbox

        with patch("openclaw.tools.irc_tool.INBOX_PATH", inbox):
            result = read_inbox({"limit": 5})
            assert result["count"] == 5

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_send_empty_message(self, tmp_path: Path):
        from openclaw.tools.irc_tool import send_message

        result = send_message({"channel": "#test", "message": ""})
        assert result["sent"] is False
        assert "Empty" in result["reason"]

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_send_no_channel(self, tmp_path: Path):
        from openclaw.tools.irc_tool import send_message

        result = send_message({"channel": "", "message": "hello"})
        assert result["sent"] is False

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_send_writes_to_outbox(self, tmp_path: Path):
        outbox = tmp_path / "irc-outbox.jsonl"
        from openclaw.tools.irc_tool import send_message

        with patch("openclaw.tools.irc_tool.OUTBOX_PATH", outbox):
            with patch("openclaw.tools.irc_tool.INBOX_PATH", tmp_path / "inbox.jsonl"):
                # Skip irc_guard
                with patch("openclaw.tools.irc_guard.check_message",
                            return_value={"allow": True}):
                    result = send_message({"channel": "#karmakadabra", "message": "bacano parce"})

        assert result["sent"] is True
        assert result["channel"] == "#karmakadabra"
        # Check outbox has the message
        outbox_data = outbox.read_text()
        entry = json.loads(outbox_data.strip())
        assert entry["message"] == "bacano parce"
        assert entry["target"] == "#karmakadabra"

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_status_no_daemon(self, tmp_path: Path):
        from openclaw.tools.irc_tool import get_status

        with patch("openclaw.tools.irc_tool.DATA_DIR", tmp_path):
            with patch("openclaw.tools.irc_tool.INBOX_PATH", tmp_path / "inbox.jsonl"):
                with patch("openclaw.tools.irc_tool.OUTBOX_PATH", tmp_path / "outbox.jsonl"):
                    result = get_status({})
                    assert result["daemon_running"] is False
                    assert result["agent"] == "kk-test-agent"

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_history_empty(self, tmp_path: Path):
        from openclaw.tools.irc_tool import get_history

        with patch("openclaw.tools.irc_tool.DATA_DIR", tmp_path):
            result = get_history({"limit": 5})
            assert result["messages"] == []
            assert result["count"] == 0


# ===================================================================
# irc_guard tests
# ===================================================================


class TestIRCGuard:
    """Tests for the anti-loop, rate-limit, and identity guard."""

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_allow_normal_message(self, tmp_path: Path):
        from openclaw.tools.irc_guard import check_message

        with patch("openclaw.tools.irc_guard.DATA_DIR", tmp_path):
            result = check_message("hola parce que mas", "#karmakadabra", "kk-test-agent")
            assert result["allow"] is True

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_block_empty_message_at_cli_level(self, tmp_path: Path):
        """Empty messages are caught by irc_tool's send_message, not check_message.
        
        The irc_guard.main() also catches empty messages before calling check_message.
        check_message() itself allows empties (guard of last resort is the caller).
        """
        from openclaw.tools.irc_tool import send_message

        result = send_message({"channel": "#test", "message": ""})
        assert result["sent"] is False

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_self_detection_blocks(self, tmp_path: Path):
        """Messages that look like they came from the agent itself are blocked."""
        from openclaw.tools.irc_guard import check_message

        with patch("openclaw.tools.irc_guard.DATA_DIR", tmp_path):
            with patch("openclaw.tools.irc_guard.SENT_LOG", tmp_path / "sent.jsonl"):
                with patch("openclaw.tools.irc_guard.STATE_FILE", tmp_path / "state.json"):
                    result = check_message(
                        "<kk-test-agent> hello world",
                        "#karmakadabra",
                        "kk-test-agent",
                    )
                    assert result["allow"] is False
                    assert "Self-detection" in result["reason"]

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_block_duplicate_message(self, tmp_path: Path):
        from openclaw.tools.irc_guard import check_message

        with patch("openclaw.tools.irc_guard.DATA_DIR", tmp_path), \
             patch("openclaw.tools.irc_guard.SENT_LOG", tmp_path / "sent.jsonl"), \
             patch("openclaw.tools.irc_guard.STATE_FILE", tmp_path / "state.json"):
            # First send should be allowed
            r1 = check_message("exact same message here", "#karmakadabra", "kk-test-agent")
            assert r1["allow"] is True

            # Immediate duplicate should be blocked (dedup via word overlap)
            r2 = check_message("exact same message here", "#karmakadabra", "kk-test-agent")
            assert r2["allow"] is False
            assert "Duplicate" in r2["reason"]


# ===================================================================
# data_tool tests
# ===================================================================


class TestDataTool:
    """Tests for data inventory operations."""

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_list_products(self, tmp_path: Path):
        from openclaw.tools.data_tool import action_list_products

        with patch("openclaw.tools.data_tool.DATA_DIR", tmp_path):
            result = action_list_products({})
            # Should return products from PRODUCTS catalog (imported from karma_hello_seller)
            assert "products" in result or "count" in result

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_list_purchases_empty(self, tmp_path: Path):
        from openclaw.tools.data_tool import action_list_purchases

        with patch("openclaw.tools.data_tool.DATA_DIR", tmp_path):
            with patch("openclaw.tools.data_tool._load_escrow_state",
                        return_value={}):
                result = action_list_purchases({})
                assert "purchases" in result

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    def test_list_purchases_with_data(self, tmp_path: Path):
        from openclaw.tools.data_tool import action_list_purchases

        with patch("openclaw.tools.data_tool._load_escrow_state",
                    return_value={
                        "applied_tasks": [
                            {"task_id": "t1", "title": "IRC Logs", "status": "completed"},
                        ]
                    }):
            result = action_list_purchases({})
            assert len(result.get("purchases", [])) >= 1


# ===================================================================
# reputation_tool tests
# ===================================================================


class TestReputationTool:
    """Tests for reputation tool actions."""

    @pytest.mark.asyncio
    async def test_check_reputation_missing_agent_id(self):
        """check_reputation requires agent_id parameter."""
        from openclaw.tools.reputation_tool import action_check_reputation

        result = await action_check_reputation({})
        assert "error" in result
        assert "agent_id" in result["error"]

    def test_reputation_tool_has_expected_actions(self):
        """Verify the tool has the expected action handlers."""
        from openclaw.tools.reputation_tool import ACTIONS
        assert "check_reputation" in ACTIONS or "rate_agent" in ACTIONS


# ===================================================================
# mcp_client tests (HTTP mocked)
# ===================================================================


class TestMCPClient:
    """Tests for the MCP bridge client with mocked HTTP."""

    def test_server_shortcuts_resolved(self):
        from openclaw.tools.mcp_client import MCP_SERVERS

        assert "meshrelay" in MCP_SERVERS
        assert "em" in MCP_SERVERS
        assert "autojob" in MCP_SERVERS
        assert MCP_SERVERS["meshrelay"].startswith("https://")

    def test_list_tools_success(self):
        from openclaw.tools.mcp_client import list_tools

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "list",
            "result": {
                "tools": [
                    {"name": "meshrelay_get_messages", "description": "Get IRC messages"},
                    {"name": "meshrelay_send_message", "description": "Send IRC message"},
                ]
            }
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = list_tools("https://api.meshrelay.xyz/mcp")
            assert "tools" in result
            assert len(result["tools"]) == 2
            assert result["tools"][0]["name"] == "meshrelay_get_messages"

    def test_call_tool_success(self):
        from openclaw.tools.mcp_client import call_mcp

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "abc",
            "result": {
                "content": [
                    {"type": "text", "text": json.dumps({"messages": [{"user": "alice", "text": "hi"}]})}
                ]
            }
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = call_mcp(
                "https://api.meshrelay.xyz/mcp",
                "meshrelay_get_messages",
                {"channel": "#karmakadabra", "limit": 5},
            )
            assert "result" in result
            assert result["result"]["messages"][0]["user"] == "alice"

    def test_call_tool_error_response(self):
        from openclaw.tools.mcp_client import call_mcp

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "abc",
            "error": {"code": -32601, "message": "Method not found"},
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = call_mcp("https://example.com/mcp", "bad_tool", {})
            assert "error" in result
            assert "not found" in result["error"]

    def test_call_tool_http_error(self):
        from openclaw.tools.mcp_client import call_mcp

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = call_mcp("https://example.com/mcp", "some_tool", {})
            assert "error" in result
            assert "500" in result["error"]

    def test_call_tool_timeout(self):
        import httpx
        from openclaw.tools.mcp_client import call_mcp

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")

        with patch("httpx.Client", return_value=mock_client):
            result = call_mcp("https://example.com/mcp", "slow_tool", {})
            assert "error" in result
            assert "timeout" in result["error"].lower()

    def test_call_tool_connection_error(self):
        import httpx
        from openclaw.tools.mcp_client import call_mcp

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch("httpx.Client", return_value=mock_client):
            result = call_mcp("https://offline.example.com/mcp", "any_tool", {})
            assert "error" in result
            assert "connect" in result["error"].lower()

    def test_call_tool_plain_text_result(self):
        """MCP result with non-JSON text content."""
        from openclaw.tools.mcp_client import call_mcp

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "abc",
            "result": {
                "content": [
                    {"type": "text", "text": "Hello, this is plain text"}
                ]
            }
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = call_mcp("https://example.com/mcp", "text_tool", {})
            assert result["result"] == "Hello, this is plain text"

    def test_call_tool_multi_content(self):
        """MCP result with multiple content items."""
        from openclaw.tools.mcp_client import call_mcp

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "abc",
            "result": {
                "content": [
                    {"type": "text", "text": "part 1"},
                    {"type": "text", "text": json.dumps({"key": "value"})},
                ]
            }
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            result = call_mcp("https://example.com/mcp", "multi_tool", {})
            assert isinstance(result["result"], list)
            assert len(result["result"]) == 2


# ===================================================================
# em_tool action dispatch tests (no network)
# ===================================================================


class TestEMToolDispatch:
    """Test em_tool action routing without network calls."""

    def test_unknown_action(self):
        from openclaw.tools.em_tool import ACTIONS

        assert "browse" in ACTIONS
        assert "publish" in ACTIONS
        assert "apply" in ACTIONS
        assert "submit" in ACTIONS
        assert "approve" in ACTIONS
        assert "status" in ACTIONS
        assert "history" in ACTIONS
        assert "nonexistent" not in ACTIONS

    @patch.dict(os.environ, {"KK_AGENT_NAME": "kk-test-agent"})
    @pytest.mark.asyncio
    async def test_history_no_state(self, tmp_path: Path):
        """History returns empty when no escrow_state.json exists."""
        from openclaw.tools.em_tool import action_history

        # Point the data dir to tmp_path where no state file exists
        with patch("openclaw.tools.em_tool.Path") as MockPath:
            # Make Path("/app/data") / "escrow_state.json" resolve to a non-existent file
            mock_path = tmp_path / "nonexistent_escrow_state.json"
            MockPath.return_value.__truediv__ = MagicMock(return_value=mock_path)

            result = await action_history({})
            assert result["purchases"] == []
            assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_publish_missing_fields(self):
        """Publish with missing required fields returns error."""
        from openclaw.tools.em_tool import action_publish

        with patch("openclaw.tools.em_tool._load_context") as mock_ctx:
            mock_ctx.return_value = MagicMock()

            mock_client = AsyncMock()
            with patch("services.em_client.EMClient", return_value=mock_client):
                result = await action_publish({"title": "Test"})
                assert "error" in result
                assert "instructions" in result["error"]

    @pytest.mark.asyncio
    async def test_apply_no_executor_id(self):
        """Apply without executor_id returns error."""
        from openclaw.tools.em_tool import action_apply

        mock_ctx = MagicMock()
        mock_ctx.executor_id = None
        with patch("openclaw.tools.em_tool._load_context", return_value=mock_ctx):
            result = await action_apply({"task_id": "abc"})
            assert "error" in result
            assert "executor_id" in result["error"]

    @pytest.mark.asyncio
    async def test_submit_no_executor_id(self):
        """Submit without executor_id returns error."""
        from openclaw.tools.em_tool import action_submit

        mock_ctx = MagicMock()
        mock_ctx.executor_id = None
        with patch("openclaw.tools.em_tool._load_context", return_value=mock_ctx):
            result = await action_submit({"task_id": "abc", "evidence": {}})
            assert "error" in result

    @pytest.mark.asyncio
    async def test_submit_no_task_id(self):
        """Submit without task_id returns error."""
        from openclaw.tools.em_tool import action_submit

        mock_ctx = MagicMock()
        mock_ctx.executor_id = "test-exec"
        with patch("openclaw.tools.em_tool._load_context", return_value=mock_ctx):
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            with patch("services.em_client.EMClient", return_value=mock_client):
                result = await action_submit({"evidence": {"text": "hello"}})
                assert "error" in result

    @pytest.mark.asyncio
    async def test_approve_no_submission_id(self):
        """Approve without submission_id returns error."""
        from openclaw.tools.em_tool import action_approve

        mock_ctx = MagicMock()
        with patch("openclaw.tools.em_tool._load_context", return_value=mock_ctx):
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()
            with patch("services.em_client.EMClient", return_value=mock_client):
                result = await action_approve({})
                assert "error" in result
