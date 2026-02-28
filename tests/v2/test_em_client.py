"""
Tests for kk/services/em_client.py

Tests AgentContext, EMClient configuration, and load_agent_context
without requiring actual API calls. Network I/O is mocked.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.em_client import AgentContext, EMClient, load_agent_context


# ---------------------------------------------------------------------------
# Tests: AgentContext
# ---------------------------------------------------------------------------


class TestAgentContext:
    def test_create_basic(self):
        ctx = AgentContext(
            name="test-agent",
            wallet_address="0x1234",
            workspace_dir=Path("/tmp/ws"),
        )
        assert ctx.name == "test-agent"
        assert ctx.wallet_address == "0x1234"
        assert ctx.daily_spent_usd == 0.0

    def test_can_spend_under_budget(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
            daily_budget_usd=2.0,
        )
        assert ctx.can_spend(1.0) is True

    def test_can_spend_at_limit(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
            daily_budget_usd=2.0,
        )
        assert ctx.can_spend(2.0) is True

    def test_cannot_spend_over_budget(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
            daily_budget_usd=2.0,
        )
        ctx.daily_spent_usd = 1.5
        assert ctx.can_spend(1.0) is False

    def test_record_spend(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
        )
        ctx.record_spend(0.50)
        assert ctx.daily_spent_usd == 0.50
        ctx.record_spend(0.25)
        assert ctx.daily_spent_usd == 0.75

    def test_reset_daily_budget(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
        )
        ctx.record_spend(1.50)
        ctx.reset_daily_budget()
        assert ctx.daily_spent_usd == 0.0

    def test_active_tasks_starts_empty(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
        )
        assert ctx.active_tasks == []

    def test_default_chain_id(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
        )
        assert ctx.chain_id == 8453  # Base mainnet

    def test_default_budgets(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
        )
        assert ctx.daily_budget_usd == 2.0
        assert ctx.per_task_budget_usd == 0.50

    def test_custom_budget(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
            daily_budget_usd=10.0, per_task_budget_usd=2.0,
        )
        assert ctx.daily_budget_usd == 10.0
        assert ctx.per_task_budget_usd == 2.0

    def test_cumulative_spend_tracking(self):
        ctx = AgentContext(
            name="test", wallet_address="0x1", workspace_dir=Path("/tmp"),
            daily_budget_usd=1.0,
        )
        assert ctx.can_spend(0.30) is True
        ctx.record_spend(0.30)
        assert ctx.can_spend(0.30) is True
        ctx.record_spend(0.30)
        assert ctx.can_spend(0.30) is True
        ctx.record_spend(0.30)
        # Now at 0.90, can't spend another 0.30
        assert ctx.can_spend(0.30) is False
        # But can spend 0.10
        assert ctx.can_spend(0.10) is True


# ---------------------------------------------------------------------------
# Tests: load_agent_context
# ---------------------------------------------------------------------------


class TestLoadAgentContext:
    def test_loads_from_wallet_json(self, tmp_path):
        ws = tmp_path / "kk-alice"
        (ws / "data").mkdir(parents=True)
        (ws / "data" / "wallet.json").write_text(json.dumps({
            "address": "0xAlice1234",
            "private_key": "0xPRIVATE_KEY_HERE",
            "chain_id": 137,
        }))

        ctx = load_agent_context(ws)
        assert ctx.wallet_address == "0xAlice1234"
        assert ctx.private_key == "0xPRIVATE_KEY_HERE"
        assert ctx.chain_id == 137

    def test_strips_kk_prefix(self, tmp_path):
        ws = tmp_path / "kk-alice"
        (ws / "data").mkdir(parents=True)
        (ws / "data" / "wallet.json").write_text(json.dumps({"address": "0x1"}))

        ctx = load_agent_context(ws)
        assert ctx.name == "alice"

    def test_no_prefix_kept(self, tmp_path):
        ws = tmp_path / "coordinator"
        (ws / "data").mkdir(parents=True)
        (ws / "data" / "wallet.json").write_text(json.dumps({"address": "0x1"}))

        ctx = load_agent_context(ws)
        assert ctx.name == "coordinator"

    def test_missing_wallet_file(self, tmp_path):
        ws = tmp_path / "kk-test"
        ws.mkdir(parents=True)

        ctx = load_agent_context(ws)
        assert ctx.wallet_address == ""
        assert ctx.private_key == ""

    def test_missing_profile_file(self, tmp_path):
        ws = tmp_path / "kk-test"
        (ws / "data").mkdir(parents=True)
        (ws / "data" / "wallet.json").write_text(json.dumps({"address": "0x1"}))

        ctx = load_agent_context(ws)
        # Should not crash, just have defaults
        assert ctx.workspace_dir == ws

    def test_default_chain_id_when_missing(self, tmp_path):
        ws = tmp_path / "kk-test"
        (ws / "data").mkdir(parents=True)
        (ws / "data" / "wallet.json").write_text(json.dumps({"address": "0x1"}))

        ctx = load_agent_context(ws)
        assert ctx.chain_id == 8453


# ---------------------------------------------------------------------------
# Tests: EMClient construction
# ---------------------------------------------------------------------------


class TestEMClientConstruction:
    def test_creates_with_header_auth(self, tmp_path):
        """Client without private key uses header-based auth."""
        ctx = AgentContext(
            name="test", wallet_address="0xABC", workspace_dir=tmp_path,
        )
        client = EMClient(ctx)
        assert client.agent.name == "test"
        assert client._signer is None

    def test_sign_headers_empty_without_signer(self, tmp_path):
        ctx = AgentContext(
            name="test", wallet_address="0xABC", workspace_dir=tmp_path,
        )
        client = EMClient(ctx)
        headers = client._sign_headers("GET", "https://example.com")
        assert headers == {}

    @pytest.mark.asyncio
    async def test_close(self, tmp_path):
        ctx = AgentContext(
            name="test", wallet_address="0xABC", workspace_dir=tmp_path,
        )
        client = EMClient(ctx)
        # Should not raise
        await client.close()


# ---------------------------------------------------------------------------
# Tests: EMClient API methods (mocked)
# ---------------------------------------------------------------------------


class TestEMClientAPIMethods:
    @pytest.fixture
    def client(self, tmp_path):
        ctx = AgentContext(
            name="test", wallet_address="0xABC", workspace_dir=tmp_path,
        )
        return EMClient(ctx)

    @pytest.mark.asyncio
    async def test_health(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "healthy"}
        mock_resp.raise_for_status = MagicMock()

        client._client.get = AsyncMock(return_value=mock_resp)

        result = await client.health()
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_browse_tasks_returns_list(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tasks": [
                {"id": "task-1", "title": "Test Task", "status": "published"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        client._client.get = AsyncMock(return_value=mock_resp)

        tasks = await client.browse_tasks(status="published")
        assert len(tasks) == 1
        assert tasks[0]["id"] == "task-1"

    @pytest.mark.asyncio
    async def test_browse_tasks_handles_direct_list(self, client):
        """Some responses return a direct list instead of {tasks: []}."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"id": "task-1", "title": "Test"},
        ]
        mock_resp.raise_for_status = MagicMock()

        client._client.get = AsyncMock(return_value=mock_resp)

        tasks = await client.browse_tasks()
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_publish_task_sends_payload(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"task": {"id": "new-task-1"}}
        mock_resp.raise_for_status = MagicMock()

        client._client.post = AsyncMock(return_value=mock_resp)

        result = await client.publish_task(
            title="Test Task",
            instructions="Do something",
            category="simple_action",
            bounty_usd=0.10,
        )

        assert result["task"]["id"] == "new-task-1"
        # Verify the POST was called
        client._client.post.assert_called_once()
        call_args = client._client.post.call_args
        body = json.loads(call_args.kwargs.get("content", call_args[1].get("content", "")))
        assert body["title"] == "Test Task"
        assert body["bounty_usd"] == 0.10

    @pytest.mark.asyncio
    async def test_apply_to_task(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "applied"}
        mock_resp.raise_for_status = MagicMock()

        client._client.post = AsyncMock(return_value=mock_resp)

        result = await client.apply_to_task(
            task_id="task-1",
            executor_id="exec-1",
            message="I can do this",
        )

        assert result["status"] == "applied"

    @pytest.mark.asyncio
    async def test_get_task(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "task-1", "title": "Test", "status": "published"}
        mock_resp.raise_for_status = MagicMock()

        client._client.get = AsyncMock(return_value=mock_resp)

        task = await client.get_task("task-1")
        assert task["id"] == "task-1"

    @pytest.mark.asyncio
    async def test_submit_evidence(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "submitted"}
        mock_resp.raise_for_status = MagicMock()

        client._client.post = AsyncMock(return_value=mock_resp)

        result = await client.submit_evidence(
            task_id="task-1",
            executor_id="exec-1",
            evidence={"url": "https://example.com/proof", "type": "text"},
        )

        assert result["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_approve_submission(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "approved"}
        mock_resp.raise_for_status = MagicMock()

        client._client.post = AsyncMock(return_value=mock_resp)

        result = await client.approve_submission(
            submission_id="sub-1",
            rating_score=85,
            notes="Good work",
        )

        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_reject_submission(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "rejected"}
        mock_resp.raise_for_status = MagicMock()

        client._client.post = AsyncMock(return_value=mock_resp)

        result = await client.reject_submission(
            submission_id="sub-1",
            notes="Does not meet requirements at all",
            severity="major",
        )

        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_cancel_task(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "cancelled"}
        mock_resp.raise_for_status = MagicMock()

        client._client.post = AsyncMock(return_value=mock_resp)

        result = await client.cancel_task("task-1")
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_submissions(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "submissions": [
                {"id": "sub-1", "evidence_url": "https://example.com"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        client._client.get = AsyncMock(return_value=mock_resp)

        subs = await client.get_submissions("task-1")
        assert len(subs) == 1
        assert subs[0]["id"] == "sub-1"

    @pytest.mark.asyncio
    async def test_list_tasks_with_filters(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tasks": []}
        mock_resp.raise_for_status = MagicMock()

        client._client.get = AsyncMock(return_value=mock_resp)

        tasks = await client.list_tasks(agent_wallet="0xABC", status="submitted")
        assert tasks == []
        # Verify params were passed — note: agent_wallet is NOT sent
        # as a query param per EM API spec (server auto-filters by
        # authenticated wallet from ERC-8128 signature)
        call_args = client._client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert "agent_wallet" not in params  # intentionally omitted
        assert params.get("status") == "submitted"

    @pytest.mark.asyncio
    async def test_assign_task(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "assigned"}
        mock_resp.raise_for_status = MagicMock()

        client._client.post = AsyncMock(return_value=mock_resp)

        result = await client.assign_task("task-1", "exec-1")
        assert result["status"] == "assigned"
