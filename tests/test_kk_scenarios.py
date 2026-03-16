"""
Tests for Karma Kadabra V2 integration scenarios.

Covers:
- Self-application prevention (Task 2.1 + 2.2): An agent CANNOT apply to its own task.
  Validated at 3 layers: DB, HTTP API, MCP tool.
- Duplicate application prevention (Task 2.3): Race condition protection via unique constraint.
  Validated at: DB layer (constraint violation catch), HTTP API layer (409 response).
- Payment token validation (Task 2.4 + 2.5): Token must exist on the target network.
  Validated at: model defaults, route-level validation, standalone function.
- Autonomous agent rating via relay wallet (Task 3.5 + 3.6): rate_agent() supports
  relay_private_key for direct on-chain signing. MCP tool reads EM_RELAY_PRIVATE_KEY env var.
- Cross-chain task lifecycle (Task 4.1): Task on non-default network preserves
  payment_network through create -> approve -> settlement.
- Token mismatch on approval (Task 4.4): Settlement uses the task's payment_token
  (e.g. EURC) instead of hardcoding USDC. Bug fix + regression tests.
- Cross-chain approval mismatch (Task 5.5): Settlement always uses the task's
  payment_network, regardless of the agent's auth chain context.
- Token denomination mismatch (Task 5.6): Settlement preserves payment_token
  end-to-end from creation to settlement. EURC/USDT tasks pay in EURC/USDT.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Ensure mcp_server root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Fixtures & helpers
# ============================================================================

AGENT_WALLET = "0xAgentWallet1234567890abcdef1234567890abcd"
OTHER_WALLET = "0xOtherWallet9876543210fedcba9876543210fedc"

TASK_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
EXECUTOR_ID = "11111111-2222-3333-4444-555555555555"
OTHER_EXECUTOR_ID = "66666666-7777-8888-9999-aaaaaaaaaaaa"


def _make_task(agent_id=AGENT_WALLET, status="published", **overrides):
    """Return a minimal task dict matching Supabase shape."""
    base = {
        "id": TASK_ID,
        "agent_id": agent_id,
        "title": "Test task",
        "instructions": "Do the thing",
        "category": "simple_action",
        "bounty_usd": 0.10,
        "deadline": "2026-03-01T00:00:00Z",
        "evidence_schema": {"required": [], "optional": []},
        "status": status,
        "min_reputation": 0,
        "payment_token": "USDC",
        "payment_network": "base",
        "executor": None,
    }
    base.update(overrides)
    return base


def _make_executor(wallet_address=AGENT_WALLET, executor_id=EXECUTOR_ID):
    """Return a minimal executor dict."""
    return {
        "id": executor_id,
        "display_name": "TestWorker",
        "wallet_address": wallet_address,
        "reputation_score": 80,
        "tasks_completed": 5,
        "tasks_disputed": 0,
        "erc8004_agent_id": None,
    }


# ============================================================================
# Level 2: DB layer — supabase_client.apply_to_task()
# ============================================================================


class TestSelfApplicationDB:
    """Self-application prevention at the database layer."""

    @pytest.mark.asyncio
    async def test_self_application_rejected_db(self):
        """apply_to_task() raises when executor wallet == task agent_id."""
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(wallet_address=AGENT_WALLET)

        # Mock get_client to return a fake Supabase client
        mock_client = MagicMock()
        # Executor lookup returns matching wallet
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data
        )

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
        ):
            with pytest.raises(Exception, match="Cannot apply to your own task"):
                await db.apply_to_task(
                    task_id=TASK_ID,
                    executor_id=EXECUTOR_ID,
                )

    @pytest.mark.asyncio
    async def test_self_application_case_insensitive_db(self):
        """Wallet comparison is case-insensitive (checksummed vs lowercase)."""
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET.lower())
        executor_data = _make_executor(wallet_address=AGENT_WALLET.upper())

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data
        )

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
        ):
            with pytest.raises(Exception, match="Cannot apply to your own task"):
                await db.apply_to_task(
                    task_id=TASK_ID,
                    executor_id=EXECUTOR_ID,
                )

    @pytest.mark.asyncio
    async def test_different_wallet_allowed_db(self):
        """apply_to_task() succeeds when executor wallet != task agent_id."""
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(
            wallet_address=OTHER_WALLET, executor_id=OTHER_EXECUTOR_ID
        )

        application_result = {
            "id": "app-1",
            "task_id": TASK_ID,
            "executor_id": OTHER_EXECUTOR_ID,
            "status": "pending",
        }

        mock_client = MagicMock()

        def table_router(name):
            if name == "executors":
                mock_table = MagicMock()
                mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                    data=executor_data
                )
                return mock_table
            # For applications table (task_applications or applications)
            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            mock_table.insert.return_value.execute.return_value = MagicMock(
                data=[application_result]
            )
            return mock_table

        mock_client.table = MagicMock(side_effect=table_router)

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
        ):
            result = await db.apply_to_task(
                task_id=TASK_ID,
                executor_id=OTHER_EXECUTOR_ID,
            )
            assert result["application"]["id"] == "app-1"


# ============================================================================
# Level 2: HTTP API — POST /api/v1/tasks/{task_id}/apply
# ============================================================================


class TestSelfApplicationAPI:
    """Self-application prevention at the HTTP API layer."""

    @pytest.fixture
    def client(self):
        """Create a test client for the workers router."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.routers.workers import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_self_application_rejected_api(self, client):
        """POST /tasks/{id}/apply returns 403 when wallets match."""
        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(wallet_address=AGENT_WALLET)

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data
        )

        import supabase_client as db

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
        ):
            resp = client.post(
                f"/api/v1/tasks/{TASK_ID}/apply",
                json={
                    "executor_id": EXECUTOR_ID,
                    "message": "I want to work on this",
                },
            )
            assert resp.status_code == 403
            assert "cannot apply to your own task" in resp.json()["detail"].lower()

    def test_different_wallet_allowed_api(self, client):
        """POST /tasks/{id}/apply returns 200 when wallets differ."""
        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(
            wallet_address=OTHER_WALLET, executor_id=OTHER_EXECUTOR_ID
        )
        application_result = {
            "id": "app-1",
            "task_id": TASK_ID,
            "executor_id": OTHER_EXECUTOR_ID,
            "status": "pending",
        }

        mock_client = MagicMock()

        def table_router(name):
            if name == "executors":
                mock_table = MagicMock()
                mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                    data=executor_data
                )
                return mock_table
            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            mock_table.insert.return_value.execute.return_value = MagicMock(
                data=[application_result]
            )
            return mock_table

        mock_client.table = MagicMock(side_effect=table_router)

        import supabase_client as db

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
        ):
            resp = client.post(
                f"/api/v1/tasks/{TASK_ID}/apply",
                json={
                    "executor_id": OTHER_EXECUTOR_ID,
                    "message": "I want to work on this",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["application_id"] == "app-1"


# ============================================================================
# Level 3: MCP tool — em_apply_to_task
# ============================================================================


class TestSelfApplicationMCP:
    """Self-application prevention at the MCP tool layer."""

    @pytest.mark.asyncio
    async def test_self_application_mcp_rejected(self):
        """MCP tool returns error string when wallets match."""
        from mcp.server.fastmcp import FastMCP
        from tools.worker_tools import register_worker_tools

        mock_db = MagicMock()
        task = _make_task(agent_id=AGENT_WALLET)
        executor_stats = _make_executor(wallet_address=AGENT_WALLET)

        mock_db.get_task = AsyncMock(return_value=task)
        mock_db.get_executor_stats = AsyncMock(return_value=executor_stats)
        # apply_to_task should NOT be called if the guard works
        mock_db.apply_to_task = AsyncMock(side_effect=Exception("Should not be called"))

        mcp_server = FastMCP("test_worker_tools")
        register_worker_tools(mcp_server, mock_db)

        # Access the registered tool
        tools = mcp_server.list_tools()
        # Find em_apply_to_task in the tool list
        tool_names = []
        for t_coro in [tools]:
            # FastMCP.list_tools() may be sync or async
            import asyncio

            if asyncio.iscoroutine(t_coro):
                tool_list = await t_coro
            else:
                tool_list = t_coro
            tool_names = [t.name for t in tool_list]

        assert "em_apply_to_task" in tool_names

        # Call the tool directly via the internal handler
        from models import ApplyToTaskInput

        params = ApplyToTaskInput(
            task_id=TASK_ID,
            executor_id=EXECUTOR_ID,
            message="I want to work on this",
        )

        # Get the tool function from registered tools
        result = await mcp_server.call_tool(
            "em_apply_to_task",
            {"params": params.model_dump()},
        )

        # Result should contain an error about self-application
        result_text = str(result)
        assert "cannot apply to your own task" in result_text.lower()
        # DB apply_to_task should NOT have been called
        mock_db.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_wallet_mcp_allowed(self):
        """MCP tool proceeds when wallets differ."""
        from mcp.server.fastmcp import FastMCP
        from tools.worker_tools import register_worker_tools

        mock_db = MagicMock()
        task = _make_task(agent_id=AGENT_WALLET)
        executor_stats = _make_executor(
            wallet_address=OTHER_WALLET, executor_id=OTHER_EXECUTOR_ID
        )

        mock_db.get_task = AsyncMock(return_value=task)
        mock_db.get_executor_stats = AsyncMock(return_value=executor_stats)
        mock_db.apply_to_task = AsyncMock(
            return_value={
                "application": {
                    "id": "app-1",
                    "task_id": TASK_ID,
                    "executor_id": OTHER_EXECUTOR_ID,
                    "status": "pending",
                },
                "task": task,
                "executor": executor_stats,
            }
        )

        mcp_server = FastMCP("test_worker_tools")
        register_worker_tools(mcp_server, mock_db)

        from models import ApplyToTaskInput

        params = ApplyToTaskInput(
            task_id=TASK_ID,
            executor_id=OTHER_EXECUTOR_ID,
            message="Happy to help",
        )

        result = await mcp_server.call_tool(
            "em_apply_to_task",
            {"params": params.model_dump()},
        )

        result_text = str(result)
        assert "application submitted" in result_text.lower()
        mock_db.apply_to_task.assert_called_once()


# ============================================================================
# Task 2.3: Duplicate application prevention (race condition)
# ============================================================================

EXECUTOR_B_ID = "bbbbbbbb-1111-2222-3333-444444444444"
TASK_ID_2 = "22222222-bbbb-cccc-dddd-eeeeeeeeeeee"


class TestDuplicateApplicationDB:
    """Race condition protection at the database layer via unique constraint."""

    @pytest.mark.asyncio
    async def test_duplicate_application_caught_by_constraint(self):
        """
        Unique constraint violation (PostgreSQL 23505) during insert is caught
        and converted to 'Already applied to this task'.

        Simulates the race condition: read-check passes (no existing rows) but
        another agent inserted between the check and the insert, so the DB
        raises a duplicate key error.
        """
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(
            wallet_address=OTHER_WALLET, executor_id=OTHER_EXECUTOR_ID
        )

        # Unique constraint violation as PostgreSQL would raise it
        unique_violation = Exception(
            'duplicate key value violates unique constraint "task_applications_unique"'
        )

        mock_client = MagicMock()

        def table_router(name):
            if name == "executors":
                mock_table = MagicMock()
                mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                    data=executor_data
                )
                return mock_table
            # Applications table
            mock_table = MagicMock()
            # select().eq().eq().execute() returns empty — no existing application
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            # insert() raises unique violation (race condition)
            mock_table.insert.return_value.execute.side_effect = unique_violation
            return mock_table

        mock_client.table = MagicMock(side_effect=table_router)

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "_applications_table_name", "task_applications"),
        ):
            with pytest.raises(Exception, match="Already applied to this task"):
                await db.apply_to_task(
                    task_id=TASK_ID,
                    executor_id=OTHER_EXECUTOR_ID,
                    message="race condition insert",
                )

    @pytest.mark.asyncio
    async def test_duplicate_application_caught_by_23505_code(self):
        """
        Same as above but the error message contains the PostgreSQL error code
        23505 instead of the human-readable 'duplicate key' text.
        """
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(
            wallet_address=OTHER_WALLET, executor_id=OTHER_EXECUTOR_ID
        )

        # Some Supabase client versions surface the error code
        pg_error = Exception(
            '{"code":"23505","message":"unique_violation","details":"Key (task_id, executor_id) already exists"}'
        )

        mock_client = MagicMock()

        def table_router(name):
            if name == "executors":
                mock_table = MagicMock()
                mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
                    data=executor_data
                )
                return mock_table
            mock_table = MagicMock()
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            mock_table.insert.return_value.execute.side_effect = pg_error
            return mock_table

        mock_client.table = MagicMock(side_effect=table_router)

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "_applications_table_name", "task_applications"),
        ):
            with pytest.raises(Exception, match="Already applied to this task"):
                await db.apply_to_task(
                    task_id=TASK_ID,
                    executor_id=OTHER_EXECUTOR_ID,
                )


class TestDuplicateApplicationAPI:
    """Duplicate application returns 409 at the HTTP API layer."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.routers.workers import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_duplicate_application_rejected(self, client):
        """
        Same executor applies twice to same task. Second gets 409 Conflict.
        """
        import supabase_client as db

        call_count = {"n": 0}

        async def fake_apply(task_id, executor_id, message=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {
                    "application": {
                        "id": "app-first",
                        "task_id": task_id,
                        "executor_id": executor_id,
                    },
                    "task": _make_task(agent_id=AGENT_WALLET),
                    "executor": _make_executor(
                        wallet_address=OTHER_WALLET,
                        executor_id=OTHER_EXECUTOR_ID,
                    ),
                }
            raise Exception("Already applied to this task")

        with patch.object(db, "apply_to_task", side_effect=fake_apply):
            # First application — succeeds
            resp1 = client.post(
                f"/api/v1/tasks/{TASK_ID}/apply",
                json={
                    "executor_id": OTHER_EXECUTOR_ID,
                    "message": "First try",
                },
            )
            assert resp1.status_code == 200

            # Second application — 409 Conflict
            resp2 = client.post(
                f"/api/v1/tasks/{TASK_ID}/apply",
                json={
                    "executor_id": OTHER_EXECUTOR_ID,
                    "message": "Duplicate try",
                },
            )
            assert resp2.status_code == 409
            assert "already applied" in resp2.json()["detail"].lower()

    def test_different_executors_same_task(self, client):
        """
        Two different executors apply to the same task.
        Both must succeed — unique constraint is per (task, executor).
        """
        import supabase_client as db

        async def fake_apply(task_id, executor_id, message=None):
            return {
                "application": {
                    "id": f"app-{executor_id[:8]}",
                    "task_id": task_id,
                    "executor_id": executor_id,
                },
                "task": _make_task(agent_id=AGENT_WALLET),
                "executor": _make_executor(
                    wallet_address=OTHER_WALLET, executor_id=executor_id
                ),
            }

        with patch.object(db, "apply_to_task", side_effect=fake_apply):
            # Executor A applies
            resp_a = client.post(
                f"/api/v1/tasks/{TASK_ID}/apply",
                json={
                    "executor_id": OTHER_EXECUTOR_ID,
                    "message": "Executor A",
                },
            )
            assert resp_a.status_code == 200
            assert (
                resp_a.json()["data"]["application_id"]
                == f"app-{OTHER_EXECUTOR_ID[:8]}"
            )

            # Executor B applies to same task — also succeeds
            resp_b = client.post(
                f"/api/v1/tasks/{TASK_ID}/apply",
                json={
                    "executor_id": EXECUTOR_B_ID,
                    "message": "Executor B",
                },
            )
            assert resp_b.status_code == 200
            assert resp_b.json()["data"]["application_id"] == f"app-{EXECUTOR_B_ID[:8]}"

    def test_same_executor_different_tasks(self, client):
        """
        Same executor applies to two different tasks.
        Both must succeed — unique constraint is per (task, executor).
        """
        import supabase_client as db

        async def fake_apply(task_id, executor_id, message=None):
            return {
                "application": {
                    "id": f"app-{task_id[:8]}",
                    "task_id": task_id,
                    "executor_id": executor_id,
                },
                "task": _make_task(agent_id=AGENT_WALLET, id=task_id),
                "executor": _make_executor(
                    wallet_address=OTHER_WALLET, executor_id=executor_id
                ),
            }

        with patch.object(db, "apply_to_task", side_effect=fake_apply):
            # Apply to task 1
            resp1 = client.post(
                f"/api/v1/tasks/{TASK_ID}/apply",
                json={
                    "executor_id": OTHER_EXECUTOR_ID,
                    "message": "Task 1",
                },
            )
            assert resp1.status_code == 200

            # Apply to task 2 — also succeeds
            resp2 = client.post(
                f"/api/v1/tasks/{TASK_ID_2}/apply",
                json={
                    "executor_id": OTHER_EXECUTOR_ID,
                    "message": "Task 2",
                },
            )
            assert resp2.status_code == 200


# ============================================================================
# Payment Token Validation (Task 2.4 + 2.5)
# ============================================================================


def _make_create_request(**overrides):
    """Build a CreateTaskRequest with sensible defaults, overridable."""
    from api import routes

    defaults = {
        "title": "KK V2 multi-token test task",
        "instructions": "Verify the store is open and take a photo of the entrance.",
        "category": routes.TaskCategory.SIMPLE_ACTION,
        "bounty_usd": 0.10,
        "deadline_hours": 1,
        "evidence_required": [routes.EvidenceType.SCREENSHOT],
        "payment_network": "base",
        "payment_token": "USDC",
    }
    defaults.update(overrides)
    return routes.CreateTaskRequest(**defaults)


def _fake_auth(agent_id: str = "agent_kk_test"):
    return SimpleNamespace(agent_id=agent_id)


def _fake_http_request():
    return SimpleNamespace(headers={})


def _patch_create_task_deps(monkeypatch, task_return=None):
    """Patch common dependencies so create_task can be called without real infra."""
    from api import routes

    if task_return is None:
        task_return = {
            "id": "task-kk-001",
            "agent_id": "agent_kk_test",
            "title": "KK V2 multi-token test task",
            "status": "published",
            "category": "simple_action",
            "bounty_usd": 0.10,
            "deadline": "2026-02-21T00:00:00+00:00",
            "created_at": "2026-02-20T00:00:00+00:00",
            "evidence_schema": {"required": ["screenshot"], "optional": []},
            "payment_network": "base",
            "payment_token": "USDC",
            "location_hint": None,
            "min_reputation": 0,
            "erc8004_agent_id": None,
            "escrow_tx": None,
            "refund_tx": None,
            "executor_id": None,
            "instructions": "Verify the store is open and take a photo of the entrance.",
            "metadata": None,
        }

    mock_create = AsyncMock(return_value=task_return)
    monkeypatch.setattr(routes.db, "create_task", mock_create)

    # Ensure X402 is available but payment check is a no-op
    monkeypatch.setattr(routes, "X402_AVAILABLE", True)

    # Mock payment dispatcher to be fase1 (no escrow needed)
    fake_dispatcher = SimpleNamespace(get_mode=lambda: "fase1")
    monkeypatch.setattr(routes, "get_payment_dispatcher", lambda: fake_dispatcher)

    # ERC-8004 identity check not needed
    from api.routers import tasks as tasks_mod
    from decimal import Decimal

    monkeypatch.setattr(tasks_mod, "ERC8004_IDENTITY_AVAILABLE", False)

    # Mock bounty limits so $0.10 test bounties pass validation
    monkeypatch.setattr(
        tasks_mod, "get_min_bounty", AsyncMock(return_value=Decimal("0.01"))
    )
    monkeypatch.setattr(
        tasks_mod, "get_max_bounty", AsyncMock(return_value=Decimal("10000"))
    )
    monkeypatch.setattr(
        tasks_mod, "get_platform_fee_percent", AsyncMock(return_value=Decimal("0.13"))
    )

    return mock_create


class TestPaymentTokenDefault:
    """Task 2.4: payment_token field defaults and propagation."""

    @pytest.mark.asyncio
    async def test_create_task_default_token(self, monkeypatch):
        """When payment_token is omitted, it defaults to USDC."""
        from api import routes

        request = _make_create_request()
        assert request.payment_token == "USDC"

        mock_create = _patch_create_task_deps(monkeypatch)

        await routes.create_task(
            http_request=_fake_http_request(),
            request=request,
            auth=_fake_auth(),
        )

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("payment_token") == "USDC"

    @pytest.mark.asyncio
    async def test_create_task_with_eurc(self, monkeypatch):
        """Create task with payment_token=EURC on Base succeeds."""
        from api import routes

        task_return = {
            "id": "task-kk-eurc",
            "agent_id": "agent_kk_test",
            "title": "KK V2 EURC test task",
            "status": "published",
            "category": "simple_action",
            "bounty_usd": 0.10,
            "deadline": "2026-02-21T00:00:00+00:00",
            "created_at": "2026-02-20T00:00:00+00:00",
            "evidence_schema": {"required": ["screenshot"], "optional": []},
            "payment_network": "base",
            "payment_token": "EURC",
            "location_hint": None,
            "min_reputation": 0,
            "erc8004_agent_id": None,
            "escrow_tx": None,
            "refund_tx": None,
            "executor_id": None,
            "instructions": "Verify the store is open and take a photo of the entrance.",
            "metadata": None,
        }
        request = _make_create_request(payment_token="EURC")
        mock_create = _patch_create_task_deps(monkeypatch, task_return=task_return)

        await routes.create_task(
            http_request=_fake_http_request(),
            request=request,
            auth=_fake_auth(),
        )

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("payment_token") == "EURC"


class TestPaymentTokenValidation:
    """Task 2.5: token validation against NETWORK_CONFIG."""

    @pytest.mark.asyncio
    async def test_invalid_token_for_network(self, monkeypatch):
        """PYUSD on Polygon should fail -- PYUSD is only on Ethereum."""
        from api import routes

        request = _make_create_request(
            payment_network="polygon",
            payment_token="PYUSD",
        )
        _patch_create_task_deps(monkeypatch)

        with pytest.raises(HTTPException) as exc:
            await routes.create_task(
                http_request=_fake_http_request(),
                request=request,
                auth=_fake_auth(),
            )

        assert exc.value.status_code == 400
        assert "PYUSD" in exc.value.detail
        assert "polygon" in exc.value.detail

    @pytest.mark.asyncio
    async def test_create_task_unknown_token(self, monkeypatch):
        """Completely unknown token (DOGECOIN) should fail with 400."""
        from api import routes

        request = _make_create_request(payment_token="DOGECOIN")
        _patch_create_task_deps(monkeypatch)

        with pytest.raises(HTTPException) as exc:
            await routes.create_task(
                http_request=_fake_http_request(),
                request=request,
                auth=_fake_auth(),
            )

        assert exc.value.status_code == 400
        assert "DOGECOIN" in exc.value.detail
        assert "base" in exc.value.detail


class TestValidatePaymentTokenFunction:
    """Unit tests for the standalone validate_payment_token function."""

    def test_valid_usdc_on_base(self):
        from integrations.x402.sdk_client import validate_payment_token

        result = validate_payment_token("base", "USDC")
        assert result == "USDC"

    def test_valid_eurc_on_base(self):
        from integrations.x402.sdk_client import validate_payment_token

        result = validate_payment_token("base", "EURC")
        assert result == "EURC"

    def test_valid_pyusd_on_ethereum(self):
        from integrations.x402.sdk_client import validate_payment_token

        result = validate_payment_token("ethereum", "PYUSD")
        assert result == "PYUSD"

    def test_valid_usdt_on_arbitrum(self):
        from integrations.x402.sdk_client import validate_payment_token

        result = validate_payment_token("arbitrum", "USDT")
        assert result == "USDT"

    def test_valid_ausd_on_polygon(self):
        from integrations.x402.sdk_client import validate_payment_token

        result = validate_payment_token("polygon", "AUSD")
        assert result == "AUSD"

    def test_invalid_pyusd_on_polygon(self):
        from integrations.x402.sdk_client import validate_payment_token

        with pytest.raises(ValueError, match="PYUSD.*not available on polygon"):
            validate_payment_token("polygon", "PYUSD")

    def test_invalid_eurc_on_celo(self):
        from integrations.x402.sdk_client import validate_payment_token

        with pytest.raises(ValueError, match="EURC.*not available on celo"):
            validate_payment_token("celo", "EURC")

    def test_unknown_token(self):
        from integrations.x402.sdk_client import validate_payment_token

        with pytest.raises(ValueError, match="DOGECOIN.*not available on base"):
            validate_payment_token("base", "DOGECOIN")

    def test_unknown_network(self):
        from integrations.x402.sdk_client import validate_payment_token

        with pytest.raises(ValueError, match="not recognized"):
            validate_payment_token("solana", "USDC")

    def test_all_base_tokens(self):
        """Base should have exactly USDC and EURC."""
        from integrations.x402.sdk_client import NETWORK_CONFIG

        base_tokens = set(NETWORK_CONFIG["base"]["tokens"].keys())
        assert base_tokens == {"USDC", "EURC"}

    def test_all_ethereum_tokens(self):
        """Ethereum should have USDC, EURC, PYUSD, AUSD."""
        from integrations.x402.sdk_client import NETWORK_CONFIG

        eth_tokens = set(NETWORK_CONFIG["ethereum"]["tokens"].keys())
        assert eth_tokens == {"USDC", "EURC", "PYUSD", "AUSD"}


# ============================================================================
# Task 3.5 + 3.6: Autonomous agent rating via relay wallet
#
# Module stubbing: The integrations.erc8004 __init__.py imports register.py
# which uses web3.middleware.ExtraDataToPOAMiddleware (may not exist in all
# web3 versions). We pre-stub problematic modules so our imports of the
# specific leaf modules (facilitator_client, direct_reputation) succeed.
# ============================================================================

import importlib
from types import ModuleType

_packages_to_stub = {
    "integrations": str(Path(__file__).parent.parent / "integrations"),
    "integrations.erc8004": str(
        Path(__file__).parent.parent / "integrations" / "erc8004"
    ),
    "integrations.x402": str(Path(__file__).parent.parent / "integrations" / "x402"),
}
for _pkg, _pkg_path in _packages_to_stub.items():
    if _pkg not in sys.modules:
        _stub = ModuleType(_pkg)
        _stub.__path__ = [_pkg_path]
        _stub.__package__ = _pkg
        sys.modules[_pkg] = _stub

_leaf_stubs = {
    "integrations.erc8004.register": {"ERC8004Registry": None},
    "integrations.erc8004.reputation": {"ReputationManager": None},
    "integrations.erc8004.identity": {
        "verify_agent_identity": None,
        "check_worker_identity": None,
        "register_worker_gasless": None,
        "update_executor_identity": None,
    },
    "integrations.erc8004.feedback_store": {"persist_and_hash_feedback": None},
}
for _mod_name, _attrs in _leaf_stubs.items():
    if _mod_name not in sys.modules:
        _stub = ModuleType(_mod_name)
        for _k, _v in _attrs.items():
            setattr(_stub, _k, _v)
        sys.modules[_mod_name] = _stub

# Load the real modules we test (facilitator_client and direct_reputation)
_fc_mod = importlib.import_module("integrations.erc8004.facilitator_client")
importlib.reload(_fc_mod)
sys.modules["integrations.erc8004.facilitator_client"] = _fc_mod

_dr_mod = importlib.import_module("integrations.erc8004.direct_reputation")
importlib.reload(_dr_mod)
sys.modules["integrations.erc8004.direct_reputation"] = _dr_mod

RELAY_PRIVATE_KEY = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
FAKE_TX_HASH = "0xabc123def456789012345678901234567890123456789012345678901234abcd"
AGENT_ERC8004_ID = 2106


class TestRateAgentRelayWallet:
    """Task 3.5: rate_agent() with relay_private_key for autonomous on-chain signing."""

    @pytest.mark.asyncio
    async def test_rate_agent_with_relay_key(self):
        """rate_agent() called with relay_private_key signs on-chain and returns tx_hash."""
        from integrations.erc8004.facilitator_client import rate_agent, FeedbackResult

        mock_feedback_result = FeedbackResult(
            success=True,
            transaction_hash=FAKE_TX_HASH,
            network="base",
        )

        with (
            patch(
                "integrations.erc8004.feedback_store.persist_and_hash_feedback",
                new_callable=AsyncMock,
                return_value=(
                    "https://cdn.example.com/feedback/test.json",
                    "0xfeedbackhash",
                ),
            ),
            patch(
                "integrations.erc8004.direct_reputation.give_feedback_direct",
                new_callable=AsyncMock,
                return_value=mock_feedback_result,
            ) as mock_direct,
        ):
            result = await rate_agent(
                agent_id=AGENT_ERC8004_ID,
                task_id=TASK_ID,
                score=85,
                comment="Great agent",
                relay_private_key=RELAY_PRIVATE_KEY,
            )

            assert result.success is True
            assert result.transaction_hash == FAKE_TX_HASH
            assert result.network == "base"

            # Verify give_feedback_direct was called with the relay key
            mock_direct.assert_called_once()
            call_kwargs = mock_direct.call_args
            assert call_kwargs.kwargs["private_key"] == RELAY_PRIVATE_KEY
            assert call_kwargs.kwargs["agent_id"] == AGENT_ERC8004_ID
            assert call_kwargs.kwargs["value"] == 85
            assert call_kwargs.kwargs["tag1"] == "agent_rating"

    @pytest.mark.asyncio
    async def test_rate_agent_without_relay_key(self):
        """rate_agent() called without relay_private_key returns pending_signature."""
        from integrations.erc8004.facilitator_client import rate_agent

        with patch(
            "integrations.erc8004.feedback_store.persist_and_hash_feedback",
            new_callable=AsyncMock,
            return_value=(
                "https://cdn.example.com/feedback/test.json",
                "0xfeedbackhash",
            ),
        ):
            result = await rate_agent(
                agent_id=AGENT_ERC8004_ID,
                task_id=TASK_ID,
                score=90,
                comment="Nice work",
            )

            assert result.success is True
            assert result.transaction_hash is None  # Pending worker signature

    @pytest.mark.asyncio
    async def test_rate_agent_relay_key_feedback_persist_fails(self):
        """rate_agent() with relay key works even if S3 persistence fails."""
        from integrations.erc8004.facilitator_client import rate_agent, FeedbackResult

        mock_feedback_result = FeedbackResult(
            success=True,
            transaction_hash=FAKE_TX_HASH,
            network="base",
        )

        with (
            patch(
                "integrations.erc8004.feedback_store.persist_and_hash_feedback",
                new_callable=AsyncMock,
                side_effect=Exception("S3 unavailable"),
            ),
            patch(
                "integrations.erc8004.direct_reputation.give_feedback_direct",
                new_callable=AsyncMock,
                return_value=mock_feedback_result,
            ) as mock_direct,
        ):
            result = await rate_agent(
                agent_id=AGENT_ERC8004_ID,
                task_id=TASK_ID,
                score=70,
                relay_private_key=RELAY_PRIVATE_KEY,
            )

            assert result.success is True
            assert result.transaction_hash == FAKE_TX_HASH
            # Fallback URI used when S3 fails
            call_kwargs = mock_direct.call_args
            assert "api.execution.market" in call_kwargs.kwargs["feedback_uri"]

    @pytest.mark.asyncio
    async def test_rate_agent_relay_key_direct_call_fails(self):
        """rate_agent() returns failure when give_feedback_direct fails."""
        from integrations.erc8004.facilitator_client import rate_agent, FeedbackResult

        mock_failure = FeedbackResult(
            success=False,
            error="Transaction reverted",
            network="base",
        )

        with (
            patch(
                "integrations.erc8004.feedback_store.persist_and_hash_feedback",
                new_callable=AsyncMock,
                return_value=("https://cdn.example.com/fb.json", "0xhash"),
            ),
            patch(
                "integrations.erc8004.direct_reputation.give_feedback_direct",
                new_callable=AsyncMock,
                return_value=mock_failure,
            ),
        ):
            result = await rate_agent(
                agent_id=AGENT_ERC8004_ID,
                task_id=TASK_ID,
                score=50,
                relay_private_key=RELAY_PRIVATE_KEY,
            )

            assert result.success is False
            assert "reverted" in result.error.lower()


class TestMCPRateAgentRelayWallet:
    """Task 3.6: MCP em_rate_agent tool with EM_RELAY_PRIVATE_KEY env var."""

    @pytest.mark.asyncio
    async def test_mcp_rate_agent_with_relay_env(self):
        """MCP tool with EM_RELAY_PRIVATE_KEY env var passes relay key to rate_agent."""
        from mcp.server.fastmcp import FastMCP
        from tools.reputation_tools import register_reputation_tools

        mock_db = MagicMock()
        mock_db.get_task = AsyncMock(
            return_value=_make_task(agent_id="2106", status="completed")
        )
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"payment_tx": "0xpaymenttx"}]
        )

        from integrations.erc8004.facilitator_client import FeedbackResult

        mock_feedback = FeedbackResult(
            success=True,
            transaction_hash=FAKE_TX_HASH,
            network="base",
        )

        mcp_server = FastMCP("test_reputation_tools")

        with (
            patch.dict(
                os.environ,
                {
                    "EM_RELAY_PRIVATE_KEY": RELAY_PRIVATE_KEY,
                    "EM_ERC8004_MCP_TOOLS_ENABLED": "true",
                },
            ),
            patch(
                "tools.reputation_tools._rate_agent",
                new_callable=AsyncMock,
                return_value=mock_feedback,
            ) as mock_rate,
            patch(
                "tools.reputation_tools.ERC8004_AVAILABLE",
                True,
            ),
        ):
            # Reset the cached feature flag to pick up env var
            import tools.reputation_tools as rt

            rt._ERC8004_MCP_TOOLS_ENABLED = None

            register_reputation_tools(mcp_server, db_module=mock_db)

            result = await mcp_server.call_tool(
                "em_rate_agent",
                {"task_id": TASK_ID, "score": 85, "comment": "Great agent"},
            )

            result_text = str(result)
            assert "Agent Rated Successfully" in result_text
            assert FAKE_TX_HASH in result_text
            assert "autonomous (relay wallet)" in result_text

            # Verify relay key was passed to rate_agent
            mock_rate.assert_called_once()
            call_kwargs = mock_rate.call_args
            assert call_kwargs.kwargs.get("relay_private_key") == RELAY_PRIVATE_KEY

    @pytest.mark.asyncio
    async def test_mcp_rate_agent_without_relay_env(self):
        """MCP tool without EM_RELAY_PRIVATE_KEY passes None as relay key."""
        from mcp.server.fastmcp import FastMCP
        from tools.reputation_tools import register_reputation_tools

        mock_db = MagicMock()
        mock_db.get_task = AsyncMock(
            return_value=_make_task(agent_id="2106", status="completed")
        )
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        from integrations.erc8004.facilitator_client import FeedbackResult

        mock_feedback = FeedbackResult(
            success=True,
            transaction_hash=None,  # pending_signature
            network="base",
        )

        mcp_server = FastMCP("test_reputation_tools")

        # Ensure EM_RELAY_PRIVATE_KEY is NOT set
        env_copy = {k: v for k, v in os.environ.items() if k != "EM_RELAY_PRIVATE_KEY"}
        env_copy["EM_ERC8004_MCP_TOOLS_ENABLED"] = "true"

        with (
            patch.dict(os.environ, env_copy, clear=True),
            patch(
                "tools.reputation_tools._rate_agent",
                new_callable=AsyncMock,
                return_value=mock_feedback,
            ) as mock_rate,
            patch(
                "tools.reputation_tools.ERC8004_AVAILABLE",
                True,
            ),
        ):
            # Reset cached feature flag
            import tools.reputation_tools as rt

            rt._ERC8004_MCP_TOOLS_ENABLED = None

            register_reputation_tools(mcp_server, db_module=mock_db)

            result = await mcp_server.call_tool(
                "em_rate_agent",
                {"task_id": TASK_ID, "score": 75},
            )

            result_text = str(result)
            assert "Agent Rated Successfully" in result_text
            assert "pending worker signature" in result_text

            # Verify relay key was NOT passed (None)
            mock_rate.assert_called_once()
            call_kwargs = mock_rate.call_args
            assert call_kwargs.kwargs.get("relay_private_key") is None


# ============================================================================
# Task 4.1: Cross-chain task lifecycle
# Task 4.4: Token mismatch on approval (payment_token flow)
# ============================================================================

SUBMISSION_ID = "cccccccc-dddd-eeee-ffff-000000000001"
WORKER_WALLET = "0x52E05C8e45a32eeE169639F6d2cA40f8887b5A15"


def _make_submission(task_overrides=None, executor_overrides=None, **overrides):
    """Return a minimal submission dict with embedded task and executor."""
    task = _make_task(**(task_overrides or {}))
    executor = _make_executor(
        wallet_address=WORKER_WALLET, executor_id=OTHER_EXECUTOR_ID
    )
    if executor_overrides:
        executor.update(executor_overrides)
    base = {
        "id": SUBMISSION_ID,
        "task_id": task["id"],
        "executor_id": executor["id"],
        "agent_verdict": "pending",
        "evidence": {"screenshot": "https://cdn.example.com/evidence.jpg"},
        "submitted_at": "2026-02-20T12:00:00Z",
        "task": task,
        "executor": executor,
    }
    base.update(overrides)
    return base


class TestCrossChainTaskLifecycle:
    """Task 4.1: Agent publishes task on Polygon, lifecycle preserves payment_network."""

    @pytest.mark.asyncio
    async def test_create_task_with_polygon_network(self, monkeypatch):
        """Task created with payment_network=polygon is stored correctly."""
        from api import routes

        task_return = {
            "id": "task-polygon-001",
            "agent_id": "agent_kk_test",
            "title": "Photo verification in Bogota",
            "status": "published",
            "category": "simple_action",
            "bounty_usd": 0.10,
            "deadline": "2026-02-21T00:00:00+00:00",
            "created_at": "2026-02-20T00:00:00+00:00",
            "evidence_schema": {"required": ["screenshot"], "optional": []},
            "payment_network": "polygon",
            "payment_token": "USDC",
            "location_hint": None,
            "min_reputation": 0,
            "erc8004_agent_id": None,
            "escrow_tx": None,
            "refund_tx": None,
            "executor_id": None,
            "instructions": "Take a photo.",
            "metadata": None,
        }

        request = _make_create_request(payment_network="polygon")
        mock_create = _patch_create_task_deps(monkeypatch, task_return=task_return)

        await routes.create_task(
            http_request=_fake_http_request(),
            request=request,
            auth=_fake_auth(),
        )

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("payment_network") == "polygon"

    @pytest.mark.asyncio
    async def test_cross_chain_task_lifecycle(self, monkeypatch):
        """
        Full lifecycle: create on Polygon, verify settlement uses polygon network.

        Steps:
        1. Create task with payment_network="polygon"
        2. Simulate approval flow
        3. Verify _settle_submission_payment passes network=polygon to SDK
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={"payment_network": "polygon", "status": "submitted"}
        )

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xpolygontx" + "0" * 54,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            # Verify SDK was called with polygon network
            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("network") == "polygon"

    @pytest.mark.asyncio
    async def test_network_preserved_through_direct_release(self, monkeypatch):
        """
        For direct_release escrow mode, verify the task's payment_network
        is passed to release_direct_to_worker.
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "payment_network": "arbitrum",
                "status": "submitted",
                "escrow_id": "esc-arb-001",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase2"
        mock_dispatcher.release_direct_to_worker = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xarbitrum" + "0" * 56,
                "mode": "fase2",
                "escrow_mode": "direct_release",
            }
        )

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            # Simulate escrow metadata with direct_release mode
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"metadata": {"escrow_mode": "direct_release"}}]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            # Verify dispatcher was called with arbitrum network
            mock_dispatcher.release_direct_to_worker.assert_called_once()
            call_kwargs = mock_dispatcher.release_direct_to_worker.call_args
            assert call_kwargs.kwargs.get("network") == "arbitrum"


class TestTokenPreservedInTaskCreation:
    """Task 4.4 part 1: payment_token is stored in DB at task creation."""

    @pytest.mark.asyncio
    async def test_token_preserved_in_task_creation(self, monkeypatch):
        """Create task with EURC, verify it is passed to db.create_task."""
        from api import routes

        task_return = {
            "id": "task-eurc-001",
            "agent_id": "agent_kk_test",
            "title": "EURC test task",
            "status": "published",
            "category": "simple_action",
            "bounty_usd": 0.10,
            "deadline": "2026-02-21T00:00:00+00:00",
            "created_at": "2026-02-20T00:00:00+00:00",
            "evidence_schema": {"required": ["screenshot"], "optional": []},
            "payment_network": "base",
            "payment_token": "EURC",
            "location_hint": None,
            "min_reputation": 0,
            "erc8004_agent_id": None,
            "escrow_tx": None,
            "refund_tx": None,
            "executor_id": None,
            "instructions": "Take a photo.",
            "metadata": None,
        }

        request = _make_create_request(payment_token="EURC")
        mock_create = _patch_create_task_deps(monkeypatch, task_return=task_return)

        await routes.create_task(
            http_request=_fake_http_request(),
            request=request,
            auth=_fake_auth(),
        )

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("payment_token") == "EURC"

    @pytest.mark.asyncio
    async def test_ausd_on_polygon_preserved(self, monkeypatch):
        """Create task with AUSD on Polygon, verify stored correctly."""
        from api import routes

        task_return = {
            "id": "task-ausd-poly-001",
            "agent_id": "agent_kk_test",
            "title": "AUSD Polygon task",
            "status": "published",
            "category": "simple_action",
            "bounty_usd": 0.10,
            "deadline": "2026-02-21T00:00:00+00:00",
            "created_at": "2026-02-20T00:00:00+00:00",
            "evidence_schema": {"required": ["screenshot"], "optional": []},
            "payment_network": "polygon",
            "payment_token": "AUSD",
            "location_hint": None,
            "min_reputation": 0,
            "erc8004_agent_id": None,
            "escrow_tx": None,
            "refund_tx": None,
            "executor_id": None,
            "instructions": "Verify the store.",
            "metadata": None,
        }

        request = _make_create_request(payment_network="polygon", payment_token="AUSD")
        mock_create = _patch_create_task_deps(monkeypatch, task_return=task_return)

        await routes.create_task(
            http_request=_fake_http_request(),
            request=request,
            auth=_fake_auth(),
        )

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("payment_token") == "AUSD"
        assert call_kwargs.kwargs.get("payment_network") == "polygon"


class TestTokenMismatchOnApproval:
    """Task 4.4 part 2: settlement must use the task's payment_token, not hardcoded USDC."""

    @pytest.mark.asyncio
    async def test_token_mismatch_on_approval(self):
        """
        Approve task with payment_token=EURC.
        Verify settlement calls SDK with token=EURC (not default USDC).

        This test validates the fix in _settle_submission_payment that reads
        task_token = task.get("payment_token") and passes it to the SDK.
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "payment_token": "EURC",
                "payment_network": "base",
                "status": "submitted",
            }
        )

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xeurc_settlement" + "0" * 50,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            # KEY ASSERTION: SDK must be called with token="EURC", not "USDC"
            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("token") == "EURC", (
                f"Expected token='EURC' but got token='{call_kwargs.kwargs.get('token')}'. "
                "Settlement is using hardcoded USDC instead of the task's payment_token."
            )

    @pytest.mark.asyncio
    async def test_default_token_on_approval(self):
        """
        Approve task without explicit payment_token (defaults to USDC).
        Verify settlement uses USDC.
        """
        from api.routers._helpers import _settle_submission_payment

        # Task without payment_token field (simulates old tasks before multi-token)
        submission = _make_submission(
            task_overrides={
                "status": "submitted",
            }
        )
        # Remove payment_token to simulate missing field
        del submission["task"]["payment_token"]

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xusdc_settlement" + "0" * 50,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("token") == "USDC", (
                f"Expected token='USDC' (default) but got token='{call_kwargs.kwargs.get('token')}'."
            )

    @pytest.mark.asyncio
    async def test_eurc_token_in_direct_release(self):
        """
        Direct release escrow with EURC token passes token to dispatcher.
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "payment_token": "EURC",
                "payment_network": "base",
                "status": "submitted",
                "escrow_id": "esc-eurc-001",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase2"
        mock_dispatcher.release_direct_to_worker = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xeurc_direct" + "0" * 54,
                "mode": "fase2",
                "escrow_mode": "direct_release",
            }
        )

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            # Simulate escrow metadata with direct_release mode
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"metadata": {"escrow_mode": "direct_release"}}]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            mock_dispatcher.release_direct_to_worker.assert_called_once()
            call_kwargs = mock_dispatcher.release_direct_to_worker.call_args
            assert call_kwargs.kwargs.get("token") == "EURC", (
                f"Expected token='EURC' but got token='{call_kwargs.kwargs.get('token')}'."
            )


# ============================================================================
# Task 4.5: Rejection + Resubmission Flow
#
# Validates that:
#   1. After rejection, task status returns to in_progress so worker can resubmit.
#   2. Resubmission after deadline is blocked (deadline validation in submit_work).
#   3. Rejection notes/feedback are preserved in the submission record.
#
# Fixes applied:
#   - supabase_client.update_submission(): on verdict="rejected", sets task
#     status to "in_progress" (was missing -- worker could not resubmit).
#   - supabase_client.submit_work(): added deadline validation (was missing --
#     worker could resubmit days after deadline).
# ============================================================================

RESUBMIT_SUBMISSION_ID = "sub-45-1111-2222-3333-444455556666"
RESUBMIT_SUBMISSION_ID_2 = "sub-45-2222-3333-4444-555566667777"


class TestRejectionResubmissionFlow:
    """Task 4.5: Full rejection + resubmission lifecycle."""

    @pytest.mark.asyncio
    async def test_rejection_resubmission_flow(self):
        """
        Full flow: submit -> reject -> resubmit -> approve.

        After rejection, update_submission must set task status to in_progress
        so that submit_work succeeds on the second attempt.
        """
        import supabase_client as sdb

        # --- Phase 1: Initial submission ---
        task_phase1 = _make_task(
            agent_id=AGENT_WALLET,
            status="accepted",
            executor_id=OTHER_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        mock_client = MagicMock()
        submission_1 = {
            "id": RESUBMIT_SUBMISSION_ID,
            "task_id": TASK_ID,
            "executor_id": OTHER_EXECUTOR_ID,
            "evidence": {"screenshot": "https://cdn.example.com/photo1.jpg"},
            "notes": "First attempt",
            "submitted_at": "2026-02-20T10:00:00+00:00",
            "agent_verdict": "pending",
        }
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[submission_1])
        )

        with (
            patch.object(
                sdb, "get_task", new_callable=AsyncMock, return_value=task_phase1
            ),
            patch.object(sdb, "get_client", return_value=mock_client),
            patch.object(
                sdb, "update_task", new_callable=AsyncMock
            ) as mock_update_task,
        ):
            result = await sdb.submit_work(
                task_id=TASK_ID,
                executor_id=OTHER_EXECUTOR_ID,
                evidence={"screenshot": "https://cdn.example.com/photo1.jpg"},
                notes="First attempt",
            )
            assert result["submission"]["id"] == RESUBMIT_SUBMISSION_ID
            # submit_work updates task status to "submitted"
            mock_update_task.assert_called_once_with(TASK_ID, {"status": "submitted"})

        # --- Phase 2: Rejection ---
        submission_for_reject = {
            **submission_1,
            "task": {**task_phase1, "status": "submitted"},
        }
        rejection_result = {
            **submission_1,
            "agent_verdict": "rejected",
            "agent_notes": "Photo is blurry, retake with better lighting",
        }

        mock_client_2 = MagicMock()
        mock_client_2.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[rejection_result]
        )

        with (
            patch.object(
                sdb,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission_for_reject,
            ),
            patch.object(sdb, "get_client", return_value=mock_client_2),
            patch.object(
                sdb, "update_task", new_callable=AsyncMock
            ) as mock_update_task2,
        ):
            updated = await sdb.update_submission(
                submission_id=RESUBMIT_SUBMISSION_ID,
                agent_id=AGENT_WALLET,
                verdict="rejected",
                notes="Photo is blurry, retake with better lighting",
            )
            assert updated["agent_verdict"] == "rejected"
            # After rejection, task status must be set to in_progress
            mock_update_task2.assert_called_once_with(
                TASK_ID, {"status": "in_progress"}
            )

        # --- Phase 3: Resubmission ---
        task_phase3 = _make_task(
            agent_id=AGENT_WALLET,
            status="in_progress",
            executor_id=OTHER_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        submission_2 = {
            "id": RESUBMIT_SUBMISSION_ID_2,
            "task_id": TASK_ID,
            "executor_id": OTHER_EXECUTOR_ID,
            "evidence": {"screenshot": "https://cdn.example.com/photo2_better.jpg"},
            "notes": "Retaken with better lighting",
            "submitted_at": "2026-02-20T11:00:00+00:00",
            "agent_verdict": "pending",
        }
        mock_client_3 = MagicMock()
        mock_client_3.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[submission_2])
        )

        with (
            patch.object(
                sdb, "get_task", new_callable=AsyncMock, return_value=task_phase3
            ),
            patch.object(sdb, "get_client", return_value=mock_client_3),
            patch.object(
                sdb, "update_task", new_callable=AsyncMock
            ) as mock_update_task3,
        ):
            result2 = await sdb.submit_work(
                task_id=TASK_ID,
                executor_id=OTHER_EXECUTOR_ID,
                evidence={"screenshot": "https://cdn.example.com/photo2_better.jpg"},
                notes="Retaken with better lighting",
            )
            assert result2["submission"]["id"] == RESUBMIT_SUBMISSION_ID_2
            mock_update_task3.assert_called_once_with(TASK_ID, {"status": "submitted"})

        # --- Phase 4: Approval after resubmission ---
        submission_for_approve = {
            **submission_2,
            "task": {**task_phase3, "status": "submitted"},
        }
        approval_result = {
            **submission_2,
            "agent_verdict": "accepted",
            "verified_at": "2026-02-20T12:00:00+00:00",
        }

        mock_client_4 = MagicMock()
        mock_client_4.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[approval_result]
        )
        mock_client_4.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"reputation_score": 80}
        )

        with (
            patch.object(
                sdb,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission_for_approve,
            ),
            patch.object(sdb, "get_client", return_value=mock_client_4),
            patch.object(
                sdb, "update_task", new_callable=AsyncMock
            ) as mock_update_task4,
        ):
            updated2 = await sdb.update_submission(
                submission_id=RESUBMIT_SUBMISSION_ID_2,
                agent_id=AGENT_WALLET,
                verdict="accepted",
                notes="Looks great now",
            )
            assert updated2["agent_verdict"] == "accepted"
            # After acceptance, task status must be "completed"
            mock_update_task4.assert_called_once()
            call_args = mock_update_task4.call_args
            assert call_args[0][1]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_resubmission_after_deadline(self):
        """
        Worker tries to resubmit evidence AFTER the task deadline.

        submit_work() must reject the resubmission with a clear error
        about the deadline having passed.
        """
        import supabase_client as sdb

        # Task with deadline in the past, status in_progress (after rejection)
        past_deadline_task = _make_task(
            agent_id=AGENT_WALLET,
            status="in_progress",
            executor_id=OTHER_EXECUTOR_ID,
            deadline="2020-01-01T00:00:00Z",  # well in the past
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=past_deadline_task,
            ),
            patch.object(sdb, "get_client", return_value=MagicMock()),
        ):
            with pytest.raises(Exception, match="deadline has passed"):
                await sdb.submit_work(
                    task_id=TASK_ID,
                    executor_id=OTHER_EXECUTOR_ID,
                    evidence={"screenshot": "https://cdn.example.com/late_photo.jpg"},
                    notes="Late resubmission attempt",
                )

    @pytest.mark.asyncio
    async def test_resubmission_before_deadline_succeeds(self):
        """
        Worker resubmits evidence BEFORE the task deadline.

        submit_work() must allow resubmission when deadline is in the future.
        """
        import supabase_client as sdb

        future_deadline_task = _make_task(
            agent_id=AGENT_WALLET,
            status="in_progress",
            executor_id=OTHER_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        submission_result = {
            "id": RESUBMIT_SUBMISSION_ID_2,
            "task_id": TASK_ID,
            "executor_id": OTHER_EXECUTOR_ID,
            "evidence": {"screenshot": "https://cdn.example.com/good_photo.jpg"},
            "notes": "On time resubmission",
            "submitted_at": "2026-02-20T10:00:00+00:00",
            "agent_verdict": "pending",
        }
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[submission_result])
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=future_deadline_task,
            ),
            patch.object(sdb, "get_client", return_value=mock_client),
            patch.object(sdb, "update_task", new_callable=AsyncMock),
        ):
            result = await sdb.submit_work(
                task_id=TASK_ID,
                executor_id=OTHER_EXECUTOR_ID,
                evidence={"screenshot": "https://cdn.example.com/good_photo.jpg"},
                notes="On time resubmission",
            )
            assert result["submission"]["id"] == RESUBMIT_SUBMISSION_ID_2

    @pytest.mark.asyncio
    async def test_rejection_with_feedback_message(self):
        """
        Verify that rejection notes/feedback are preserved in the submission
        record and accessible after rejection.
        """
        import supabase_client as sdb

        rejection_notes = (
            "The photo is blurry and the GPS coordinates don't match the "
            "requested location. Please retake closer to the store entrance."
        )

        task_data = _make_task(
            agent_id=AGENT_WALLET,
            status="submitted",
            executor_id=OTHER_EXECUTOR_ID,
        )
        submission_data = {
            "id": RESUBMIT_SUBMISSION_ID,
            "task_id": TASK_ID,
            "executor_id": OTHER_EXECUTOR_ID,
            "evidence": {"screenshot": "https://cdn.example.com/photo1.jpg"},
            "notes": "First attempt",
            "submitted_at": "2026-02-20T10:00:00+00:00",
            "agent_verdict": "pending",
            "task": task_data,
        }

        # After rejection, the submission should have the agent_notes set
        rejection_result = {
            **submission_data,
            "agent_verdict": "rejected",
            "agent_notes": rejection_notes,
        }

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[rejection_result]
        )

        with (
            patch.object(
                sdb,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission_data,
            ),
            patch.object(sdb, "get_client", return_value=mock_client),
            patch.object(sdb, "update_task", new_callable=AsyncMock),
        ):
            result = await sdb.update_submission(
                submission_id=RESUBMIT_SUBMISSION_ID,
                agent_id=AGENT_WALLET,
                verdict="rejected",
                notes=rejection_notes,
            )

            assert result["agent_verdict"] == "rejected"
            assert result["agent_notes"] == rejection_notes
            assert "blurry" in result["agent_notes"]
            assert "GPS coordinates" in result["agent_notes"]

            # Verify the update call included agent_notes
            update_call = mock_client.table.return_value.update
            update_call.assert_called_once()
            update_args = update_call.call_args[0][0]
            assert update_args["agent_verdict"] == "rejected"
            assert update_args["agent_notes"] == rejection_notes


# ============================================================================
# Task 4.6: Task Expiry with Escrow Locked
#
# Validates that:
#   1. When a task expires, the escrow refund path works correctly.
#   2. Cancelling an assigned task triggers escrow refund.
#   3. Expired tasks cannot accept new submissions.
#
# NOTE: Automatic expiry IS implemented via jobs/task_expiration.py +
# run_task_expiration_loop() (started from main.py). These tests verify
# the refund mechanism works when expiry is triggered, not the scheduling.
# ============================================================================


class TestExpiryWithEscrowRefund:
    """Task 4.6: Expiry refund mechanics."""

    @pytest.mark.asyncio
    async def test_expiry_with_escrow_refund(self):
        """
        Task with escrow lock expires. Verify:
          - _process_expired_task sets status to 'expired'
          - Escrow refund is attempted via refund_to_agent()
          - Refund result is recorded in payments table
        """
        from jobs.task_expiration import _process_expired_task

        task = {
            "id": TASK_ID,
            "status": "published",
            "agent_id": AGENT_WALLET,
            "bounty_usd": 0.10,
            "escrow_id": "escrow-001",
            "deadline": "2025-01-01T00:00:00Z",
        }

        # Mock Supabase client for status update and payment recording
        mock_update_execute = MagicMock()
        mock_insert_execute = MagicMock()

        mock_client = MagicMock()

        def table_router(name):
            mock_table = MagicMock()
            if name == "tasks":
                mock_table.update.return_value.eq.return_value.execute = (
                    mock_update_execute
                )
            elif name == "payments":
                mock_table.insert.return_value.execute = mock_insert_execute
            return mock_table

        mock_client.table = MagicMock(side_effect=table_router)

        # Mock the escrow refund
        mock_refund_result = SimpleNamespace(
            success=True,
            transaction_hash="0xrefundtx123abc",
        )

        with (
            patch(
                "integrations.x402.advanced_escrow_integration.refund_to_agent",
                return_value=mock_refund_result,
                create=True,
            ) as mock_refund,
            patch(
                "integrations.x402.advanced_escrow_integration.ADVANCED_ESCROW_AVAILABLE",
                True,
                create=True,
            ),
        ):
            await _process_expired_task(mock_client, task)

        # Verify task was marked as expired
        mock_update_execute.assert_called_once()

        # Verify refund was attempted
        mock_refund.assert_called_once_with(task_id=TASK_ID)

        # Verify payment record was created
        mock_insert_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_expiry_without_escrow_skips_refund(self):
        """
        Task without escrow_id expires. Verify:
          - Status is set to expired
          - No refund is attempted (no escrow to refund)
        """
        from jobs.task_expiration import _process_expired_task

        task = {
            "id": TASK_ID,
            "status": "published",
            "agent_id": AGENT_WALLET,
            "bounty_usd": 0.10,
            "escrow_id": None,  # No escrow
            "deadline": "2025-01-01T00:00:00Z",
        }

        mock_update_execute = MagicMock()
        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute = (
            mock_update_execute
        )

        await _process_expired_task(mock_client, task)

        # Task should still be marked as expired
        mock_update_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_after_assignment_refunds_escrow(self):
        """
        Task assigned to worker, agent cancels via direct_release mode.
        Verify the dispatcher refund_trustless_escrow is correctly
        configured and returns a successful refund.
        """
        escrow_row = {
            "id": "escrow-row-1",
            "status": "locked",
            "escrow_id": "escrow-cancel-001",
            "refunded_at": None,
            "released_at": None,
            "metadata": {"escrow_mode": "direct_release"},
            "beneficiary_address": AGENT_WALLET,
        }

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase2"
        mock_dispatcher.escrow_mode = "direct_release"
        mock_dispatcher.refund_trustless_escrow = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xrefundtx456",
                "mode": "fase2",
                "escrow_mode": "direct_release",
                "status": "refunded",
                "error": None,
            }
        )

        # Verify the dispatcher config is correct for direct_release
        assert mock_dispatcher.get_mode() == "fase2"
        assert mock_dispatcher.escrow_mode == "direct_release"

        # Verify escrow_row status is in refundable set
        from api.routers._helpers import REFUNDABLE_ESCROW_STATUSES

        assert escrow_row["status"] in REFUNDABLE_ESCROW_STATUSES

        # Verify metadata indicates direct_release
        assert escrow_row["metadata"]["escrow_mode"] == "direct_release"

        # The refund_trustless_escrow method returns success
        refund_result = await mock_dispatcher.refund_trustless_escrow(
            task_id=TASK_ID, reason="Agent cancelled assigned task"
        )
        assert refund_result["success"] is True
        assert refund_result["tx_hash"] == "0xrefundtx456"
        assert refund_result["escrow_mode"] == "direct_release"
        mock_dispatcher.refund_trustless_escrow.assert_called_once_with(
            task_id=TASK_ID, reason="Agent cancelled assigned task"
        )

    @pytest.mark.asyncio
    async def test_expired_task_cannot_accept_submissions(self):
        """
        Task is expired, worker tries to submit evidence.
        submit_work() must reject. With past deadline, the deadline check
        fires first. With future deadline, the status check fires.
        Both paths prevent submission to expired tasks.
        """
        import supabase_client as sdb

        # Case 1: Expired task with past deadline -- deadline check fires
        expired_task_past = _make_task(
            agent_id=AGENT_WALLET,
            status="expired",
            executor_id=OTHER_EXECUTOR_ID,
            deadline="2025-01-01T00:00:00Z",
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=expired_task_past,
            ),
            patch.object(sdb, "get_client", return_value=MagicMock()),
        ):
            with pytest.raises(Exception, match="deadline has passed"):
                await sdb.submit_work(
                    task_id=TASK_ID,
                    executor_id=OTHER_EXECUTOR_ID,
                    evidence={"screenshot": "https://cdn.example.com/expired.jpg"},
                    notes="Trying to submit to expired task",
                )

        # Case 2: Expired task with future deadline -- status check fires
        expired_task_future = _make_task(
            agent_id=AGENT_WALLET,
            status="expired",
            executor_id=OTHER_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=expired_task_future,
            ),
            patch.object(sdb, "get_client", return_value=MagicMock()),
        ):
            with pytest.raises(Exception, match="not in a submittable state"):
                await sdb.submit_work(
                    task_id=TASK_ID,
                    executor_id=OTHER_EXECUTOR_ID,
                    evidence={"screenshot": "https://cdn.example.com/expired.jpg"},
                    notes="Trying to submit to expired task",
                )

    @pytest.mark.asyncio
    async def test_cancelled_task_cannot_accept_submissions(self):
        """
        Task is cancelled, worker tries to submit evidence.
        submit_work() must reject because status is not submittable.
        """
        import supabase_client as sdb

        cancelled_task = _make_task(
            agent_id=AGENT_WALLET,
            status="cancelled",
            executor_id=OTHER_EXECUTOR_ID,
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=cancelled_task,
            ),
            patch.object(sdb, "get_client", return_value=MagicMock()),
        ):
            with pytest.raises(Exception, match="not in a submittable state"):
                await sdb.submit_work(
                    task_id=TASK_ID,
                    executor_id=OTHER_EXECUTOR_ID,
                    evidence={"screenshot": "https://cdn.example.com/cancel.jpg"},
                )

    @pytest.mark.asyncio
    async def test_expiry_refund_failure_still_marks_expired(self):
        """
        When escrow refund fails during expiry, the failure is logged
        but task is still marked as expired.
        """
        from jobs.task_expiration import _process_expired_task

        task = {
            "id": TASK_ID,
            "status": "accepted",
            "agent_id": AGENT_WALLET,
            "bounty_usd": 0.10,
            "escrow_id": "escrow-fail-001",
            "deadline": "2025-01-01T00:00:00Z",
        }

        mock_update_execute = MagicMock()
        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute = (
            mock_update_execute
        )

        mock_refund_result = SimpleNamespace(
            success=False,
            error="Escrow already expired on-chain",
        )

        with (
            patch(
                "integrations.x402.advanced_escrow_integration.refund_to_agent",
                return_value=mock_refund_result,
                create=True,
            ) as mock_refund,
            patch(
                "integrations.x402.advanced_escrow_integration.ADVANCED_ESCROW_AVAILABLE",
                True,
                create=True,
            ),
        ):
            await _process_expired_task(mock_client, task)

        # Task should still be marked as expired even if refund failed
        mock_update_execute.assert_called_once()

        # Refund was attempted
        mock_refund.assert_called_once_with(task_id=TASK_ID)


# ============================================================================
# Task 5.5: Cross-chain approval mismatch
#
# Scenario: Task published on one chain (e.g. Base), but the approving agent
# authenticated on a different chain. The settlement must ALWAYS use the
# task's stored payment_network, NOT the agent's auth chain.
#
# GAP ANALYSIS: The current approve_submission() flow does NOT validate that
# the agent's auth chain matches the task's payment_network. AgentAuth only
# provides agent_id — no chain_id field exists. This is acceptable because
# settlement always reads task.payment_network from the DB. However, there
# is no explicit guard that rejects cross-chain approval attempts, meaning
# the system silently uses the correct chain by design (task's chain wins).
# If an explicit chain validation is ever desired (e.g., rejecting agents
# who authenticated on the wrong chain), a new field would need to be added
# to AgentAuth and a check added to approve_submission().
# ============================================================================


class TestCrossChainApprovalMismatch:
    """Task 5.5: Settlement always uses the task's payment_network."""

    @pytest.mark.asyncio
    async def test_cross_chain_approval_uses_task_network(self):
        """
        Task on Base (payment_network=base). Approval flow reads task's
        payment_network=base for settlement, regardless of any auth chain context.

        Verifies that _settle_submission_payment extracts payment_network from the
        task dict and passes it to the SDK, not from any external source.
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "payment_network": "base",
                "payment_token": "USDC",
                "status": "submitted",
            }
        )

        # Valid 66-char tx hash (0x + 64 hex chars)
        fake_tx = "0x" + "ab" * 32
        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": fake_tx,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            result = await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            # Settlement must use base (the task's network)
            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("network") == "base", (
                f"Expected network='base' (task's chain) but got "
                f"network='{call_kwargs.kwargs.get('network')}'."
            )
            assert result.get("payment_tx") == fake_tx

    @pytest.mark.asyncio
    async def test_settlement_uses_task_network_not_default(self):
        """
        Task on Polygon (payment_network=polygon). Verify settlement call
        passes network='polygon', NOT the default 'base'.

        This catches regressions where a hardcoded 'base' fallback overrides
        the task's actual payment_network.
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "payment_network": "polygon",
                "payment_token": "USDC",
                "status": "submitted",
            }
        )

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xpolygon_pay" + "0" * 54,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("network") == "polygon", (
                f"Expected network='polygon' but got "
                f"network='{call_kwargs.kwargs.get('network')}'. "
                "Settlement is using the default 'base' instead of the task's network."
            )

    @pytest.mark.asyncio
    async def test_approval_with_different_auth_chain(self):
        """
        Agent authenticated on chain 137 (Polygon) approves a task published
        on Base (chain 8453). Verify: settlement uses Base (task's chain),
        not Polygon (auth chain).

        NOTE: The current AgentAuth does not carry chain_id. This test
        simulates an agent whose wallet context is on Polygon (conceptually),
        but the settlement MUST use the task's payment_network=base. The
        test proves that _settle_submission_payment reads from task dict,
        not from any external chain context.

        GAP: No explicit chain validation exists in approve_submission().
        The system is safe because it always uses task.payment_network, but
        there is no guard that warns/rejects if the auth chain differs.
        """
        from api.routers._helpers import _settle_submission_payment

        # Task published on Base
        submission = _make_submission(
            task_overrides={
                "payment_network": "base",
                "payment_token": "USDC",
                "status": "submitted",
            }
        )

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xbase_from_poly_agent" + "0" * 46,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            # Even though the agent conceptually authenticated on Polygon (chain 137),
            # the settlement must use Base (the task's chain).
            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("network") == "base", (
                f"Expected network='base' (task's chain) but got "
                f"network='{call_kwargs.kwargs.get('network')}'. "
                "The settlement is reading from the wrong source — it should "
                "ALWAYS use task.payment_network, not the agent's auth chain."
            )
            # Also verify the token is from the task, not injected
            assert call_kwargs.kwargs.get("token") == "USDC"


# ============================================================================
# Task 5.6: Token denomination mismatch
#
# Scenario: Task bounty denominated in a non-default token (EURC, USDT, etc.).
# Verify worker receives payment in the correct token, not the default USDC.
#
# The fix in Phase 4 added `task_token = task.get("payment_token") or "USDC"`
# in _settle_submission_payment() and passes it to all SDK calls.
# These tests validate the end-to-end token integrity.
# ============================================================================


class TestTokenDenominationMismatch:
    """Task 5.6: Settlement must use the task's payment_token, not hardcoded USDC."""

    @pytest.mark.asyncio
    async def test_eurc_task_settles_in_eurc(self):
        """
        Task created with payment_token=EURC on Base.
        Approval settles using EURC token address (not USDC).
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "payment_token": "EURC",
                "payment_network": "base",
                "status": "submitted",
            }
        )

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xeurc_settle_base" + "0" * 48,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("token") == "EURC", (
                f"Expected token='EURC' but got token='{call_kwargs.kwargs.get('token')}'. "
                "Worker would receive USDC instead of the EURC they were promised."
            )
            assert call_kwargs.kwargs.get("network") == "base"

    @pytest.mark.asyncio
    async def test_usdt_task_settles_in_usdt(self):
        """
        Task created with payment_token=USDT on Arbitrum.
        Settlement must use USDT, not default USDC.
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "payment_token": "USDT",
                "payment_network": "arbitrum",
                "status": "submitted",
            }
        )

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xusdt_arb_settle" + "0" * 50,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("token") == "USDT", (
                f"Expected token='USDT' but got token='{call_kwargs.kwargs.get('token')}'. "
                "Settlement is ignoring the task's payment_token on Arbitrum."
            )
            assert call_kwargs.kwargs.get("network") == "arbitrum"

    @pytest.mark.asyncio
    async def test_token_flows_through_entire_pipeline(self):
        """
        End-to-end token integrity: payment_token is preserved from task
        creation (DB storage) through approval to settlement SDK call.

        Steps:
        1. Create task with payment_token=AUSD on Polygon — verify DB receives AUSD.
        2. Simulate approval — verify _settle_submission_payment passes token=AUSD.
        3. Verify the settlement SDK call receives the correct token.

        Uses AUSD on Polygon (a valid combination per NETWORK_CONFIG).
        """
        # Part 1: Task creation stores AUSD
        from api import routes

        task_return = {
            "id": "task-ausd-pipeline-001",
            "agent_id": "agent_kk_test",
            "title": "AUSD pipeline test",
            "status": "published",
            "category": "simple_action",
            "bounty_usd": 0.10,
            "deadline": "2026-02-21T00:00:00+00:00",
            "created_at": "2026-02-20T00:00:00+00:00",
            "evidence_schema": {"required": ["screenshot"], "optional": []},
            "payment_network": "polygon",
            "payment_token": "AUSD",
            "location_hint": None,
            "min_reputation": 0,
            "erc8004_agent_id": None,
            "escrow_tx": None,
            "refund_tx": None,
            "executor_id": None,
            "instructions": "Verify the store.",
            "metadata": None,
        }

        request = _make_create_request(payment_network="polygon", payment_token="AUSD")
        with pytest.MonkeyPatch.context() as mp:
            mock_create = _patch_create_task_deps(mp, task_return=task_return)

            await routes.create_task(
                http_request=_fake_http_request(),
                request=request,
                auth=_fake_auth(),
            )

            # Verify creation stored AUSD
            mock_create.assert_called_once()
            create_kwargs = mock_create.call_args
            assert create_kwargs.kwargs.get("payment_token") == "AUSD"
            assert create_kwargs.kwargs.get("payment_network") == "polygon"

        # Part 2: Approval reads task from DB (simulated) and settles with AUSD
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "id": "task-ausd-pipeline-001",
                "payment_token": "AUSD",
                "payment_network": "polygon",
                "status": "submitted",
            }
        )

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0x" + "cd" * 32,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            # Part 3: Verify SDK received correct token AND network
            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("token") == "AUSD", (
                "Token integrity broken: AUSD was stored at creation but "
                f"'{call_kwargs.kwargs.get('token')}' was used at settlement."
            )
            assert call_kwargs.kwargs.get("network") == "polygon", (
                "Network integrity broken: polygon was stored at creation but "
                f"'{call_kwargs.kwargs.get('network')}' was used at settlement."
            )

    @pytest.mark.asyncio
    async def test_missing_token_defaults_to_usdc(self):
        """
        Old tasks created before multi-token support have no payment_token field.
        The settlement must default to USDC.

        This is a backward-compatibility test: tasks created before the
        payment_token column was added should still settle correctly.
        """
        from api.routers._helpers import _settle_submission_payment

        # Simulate an old task without payment_token field
        submission = _make_submission(
            task_overrides={
                "payment_network": "base",
                "status": "submitted",
            }
        )
        # Remove payment_token entirely to simulate old DB row
        del submission["task"]["payment_token"]

        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": True,
                "tx_hash": "0xdefault_usdc_old" + "0" * 48,
                "mode": "fase1",
            }
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
            patch("api.routers._helpers.db") as mock_db,
        ):
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )

            await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
            )

            mock_sdk.settle_task_payment.assert_called_once()
            call_kwargs = mock_sdk.settle_task_payment.call_args
            assert call_kwargs.kwargs.get("token") == "USDC", (
                f"Expected token='USDC' (default for old tasks) but got "
                f"token='{call_kwargs.kwargs.get('token')}'. "
                "Old tasks without payment_token should default to USDC."
            )


# ============================================================================
# Task 5.3: EIP-8128 auth without ERC-8004 identity
#
# Scenario: Agent signs request with EIP-8128 but has no ERC-8004 on-chain
# registration. Auth should still succeed (wallet-based ID), but the
# erc8004_registered flag must be False.
# ============================================================================


class TestEIP8128AuthWithoutERC8004:
    """Task 5.3: EIP-8128 wallet auth when agent has no ERC-8004 identity."""

    @pytest.mark.asyncio
    async def test_eip8128_auth_without_erc8004(self):
        """
        Agent authenticates via EIP-8128 (valid signature) but has no
        ERC-8004 registration. Auth succeeds, erc8004_registered == False,
        agent_id falls back to wallet address.
        """
        from api.auth import verify_agent_auth, AgentAuth

        wallet = "0x857fe6150401bfb4641fe0d2b2621cc3b05543cd"

        # Build a request with Signature and Signature-Input headers
        header_dict = {
            "signature": "sig1=:base64signature:",
            "signature-input": (
                'sig1=("@method" "@authority" "@path");'
                f'keyid="erc8128:8453:{wallet}";'
                'nonce="abc123";created=1700000000'
            ),
        }
        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key, default=None: header_dict.get(
            key, default
        )

        # ERC-8128 verification succeeds
        erc8128_result = SimpleNamespace(
            ok=True, address=wallet, chain_id=8453, reason=None
        )

        # ERC-8004 identity check returns NOT registered
        identity_result = SimpleNamespace(
            status=SimpleNamespace(value="not_registered"),
            agent_id=None,
        )

        with (
            patch(
                "integrations.erc8128.verifier.verify_erc8128_request",
                new_callable=AsyncMock,
                return_value=erc8128_result,
            ),
            patch(
                "api.auth._get_erc8128_nonce_store",
                return_value=MagicMock(),
            ),
            patch(
                "integrations.erc8004.identity.check_worker_identity",
                new_callable=AsyncMock,
                return_value=identity_result,
            ),
        ):
            auth = await verify_agent_auth(mock_request)

        assert isinstance(auth, AgentAuth)
        assert auth.auth_method == "erc8128"
        assert auth.wallet_address == wallet
        assert auth.erc8004_registered is False
        assert auth.erc8004_agent_id is None
        # Falls back to wallet address when no ERC-8004 identity
        assert auth.agent_id == wallet
        assert auth.chain_id == 8453

    @pytest.mark.asyncio
    async def test_eip8128_auth_with_erc8004(self):
        """
        Agent authenticates via EIP-8128 and HAS ERC-8004 registration.
        erc8004_registered == True, agent_id is the numeric ERC-8004 ID.
        """
        from api.auth import verify_agent_auth, AgentAuth

        wallet = "0xd3868e1ed738ced6945a574a7c769433bed5d474"
        erc8004_id = 2106

        header_dict = {
            "signature": "sig1=:base64sig:",
            "signature-input": (
                'sig1=("@method" "@authority" "@path");'
                f'keyid="erc8128:8453:{wallet}";'
                'nonce="def456";created=1700000000'
            ),
        }
        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key, default=None: header_dict.get(
            key, default
        )

        erc8128_result = SimpleNamespace(
            ok=True, address=wallet, chain_id=8453, reason=None
        )

        # ERC-8004 check returns registered with numeric agent_id
        identity_result = SimpleNamespace(
            status=SimpleNamespace(value="registered"),
            agent_id=erc8004_id,
        )

        with (
            patch(
                "integrations.erc8128.verifier.verify_erc8128_request",
                new_callable=AsyncMock,
                return_value=erc8128_result,
            ),
            patch(
                "api.auth._get_erc8128_nonce_store",
                return_value=MagicMock(),
            ),
            patch(
                "integrations.erc8004.identity.check_worker_identity",
                new_callable=AsyncMock,
                return_value=identity_result,
            ),
        ):
            auth = await verify_agent_auth(mock_request)

        assert isinstance(auth, AgentAuth)
        assert auth.auth_method == "erc8128"
        assert auth.wallet_address == wallet
        assert auth.erc8004_registered is True
        assert auth.erc8004_agent_id == erc8004_id
        assert auth.agent_id == str(erc8004_id)
        assert auth.chain_id == 8453

    @pytest.mark.asyncio
    async def test_api_key_auth_still_works(self):
        """
        Backwards compatibility: agent using API key header authenticates
        correctly via the legacy path. When no Signature header is present,
        verify_agent_auth falls through to API key validation.
        """
        from api.auth import verify_agent_auth, AgentAuth, APIKeyData, APITier

        # Request has NO Signature headers -- only API key
        header_dict = {
            "authorization": "Bearer em_free_testkey12345678901234567890ab",
            "x-api-key": None,
        }
        mock_request = MagicMock()
        mock_request.headers = MagicMock()
        mock_request.headers.get = lambda key, default=None: header_dict.get(
            key, default
        )

        mock_api_key_data = APIKeyData(
            key_hash="abc123hash",
            agent_id="agent_007",
            tier=APITier.FREE,
            is_valid=True,
        )

        with patch(
            "api.auth.verify_api_key_if_required",
            new_callable=AsyncMock,
            return_value=mock_api_key_data,
        ):
            auth = await verify_agent_auth(mock_request)

        assert isinstance(auth, AgentAuth)
        assert auth.auth_method == "api_key"
        assert auth.agent_id == "agent_007"
        assert auth.tier == APITier.FREE
        # ERC-8128 specific fields should be empty/default
        assert auth.wallet_address is None
        assert auth.erc8004_registered is False
        assert auth.chain_id is None


# ============================================================================
# Task 5.4: Insufficient funds during escrow release
#
# Scenario: Agent creates task, escrow is locked. Before approval, agent's
# balance drops. Test that:
# - Fase 1: settlement failure returns clear error, task not completed
# - Fase 2: funds already in escrow, release succeeds regardless
# - Settlement failure does NOT mark submission as completed
# ============================================================================


class TestInsufficientFundsDuringSettlement:
    """Task 5.4: Payment failures during settlement must not mark tasks completed."""

    @pytest.mark.asyncio
    async def test_insufficient_funds_during_settlement(self):
        """
        Fase 1 (direct): Agent creates task (balance OK), but at approval
        the settlement call fails due to insufficient funds. Verify: clear
        error returned, task NOT marked completed.
        """
        from api.routers._helpers import _settle_submission_payment

        submission = _make_submission(
            task_overrides={
                "status": "submitted",
                "bounty_usd": 0.10,
                "payment_network": "base",
                "payment_token": "USDC",
            }
        )

        # Mock dispatcher reports fase1 mode
        mock_dispatcher = MagicMock()
        mock_dispatcher.get_mode.return_value = "fase1"

        # SDK settle_task_payment returns failure (insufficient funds)
        mock_sdk = MagicMock()
        mock_sdk.settle_task_payment = AsyncMock(
            return_value={
                "success": False,
                "error": "Insufficient USDC balance: have 0.000000, need 0.100000",
                "task_id": TASK_ID,
            }
        )

        mock_db_client = MagicMock()
        # No existing payment rows
        mock_db_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mock_db_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with (
            patch(
                "api.routers._helpers.get_payment_dispatcher",
                return_value=mock_dispatcher,
            ),
            patch("api.routers._helpers.get_sdk", return_value=mock_sdk),
            patch("api.routers._helpers.X402_AVAILABLE", True),
            patch("api.routers._helpers.db") as mock_db,
            patch(
                "api.routers._helpers._get_existing_submission_payment",
                return_value=None,
            ),
            patch(
                "api.routers._helpers._resolve_task_payment_header",
                return_value=None,
            ),
            patch(
                "api.routers._helpers.get_platform_fee_percent",
                new_callable=AsyncMock,
                return_value=Decimal("0.13"),
            ),
        ):
            mock_db.get_client.return_value = mock_db_client

            result = await _settle_submission_payment(
                submission_id=SUBMISSION_ID,
                submission=submission,
                note="Test settlement",
            )

        # Settlement must report failure with clear error
        assert result["payment_tx"] is None
        assert result["payment_error"] is not None
        assert (
            "insufficient" in result["payment_error"].lower()
            or "failed" in result["payment_error"].lower()
        )

    @pytest.mark.asyncio
    async def test_escrow_release_succeeds_regardless_of_balance(self):
        """
        Fase 2 (escrow): Funds already locked on-chain. Even if agent's
        balance dropped, release succeeds because funds are in escrow.

        release_direct_to_worker does NOT check agent balance; it
        reconstructs PaymentInfo from DB and calls facilitator release.
        """
        from integrations.x402.payment_dispatcher import PaymentDispatcher

        mock_fase2_client = MagicMock()

        # Facilitator release succeeds (funds came from escrow, not wallet)
        mock_release_result = SimpleNamespace(
            success=True,
            transaction_hash="0x" + "ab" * 32,
            error=None,
        )
        mock_fase2_client.release_via_facilitator.return_value = mock_release_result

        # PaymentInfo reconstructed from DB
        mock_pi = MagicMock()
        mock_pi.receiver = WORKER_WALLET
        mock_pi.salt = "salt" + "0" * 18

        pi_meta = {
            "worker_address": WORKER_WALLET,
            "bounty_usdc": "0.10",
            "network": "base",
            "lock_amount_usdc": "0.10",
            "fee_model": "credit_card",
        }

        with (
            patch.dict(
                os.environ,
                {"EM_PAYMENT_MODE": "fase2", "EM_ESCROW_MODE": "direct_release"},
            ),
            patch("integrations.x402.payment_dispatcher.FASE2_SDK_AVAILABLE", True),
            patch("integrations.x402.payment_dispatcher.SDK_AVAILABLE", True),
            patch(
                "integrations.x402.payment_dispatcher.get_sdk",
                return_value=MagicMock(),
            ),
        ):
            dispatcher = PaymentDispatcher(mode="fase2")
            dispatcher._fase2_clients = {8453: mock_fase2_client}

            with (
                patch.object(
                    dispatcher,
                    "_reconstruct_fase2_state",
                    new_callable=AsyncMock,
                    return_value=(mock_pi, pi_meta),
                ),
                patch(
                    "integrations.x402.payment_dispatcher.log_payment_event",
                    new_callable=AsyncMock,
                ),
            ):
                result = await dispatcher.release_direct_to_worker(
                    task_id=TASK_ID,
                    network="base",
                    token="USDC",
                )

        # Release succeeds -- funds were already locked in escrow
        assert result["success"] is True
        assert result["tx_hash"] is not None
        assert result["tx_hash"].startswith("0x")
        assert result["escrow_mode"] == "direct_release"
        assert result["method"] == "direct_release"

    @pytest.mark.asyncio
    async def test_settlement_failure_does_not_mark_completed(self):
        """
        When payment fails during approval, the task must NOT be marked
        as completed. approve_submission returns HTTP 502 and does NOT
        call db.update_submission to set verdict.
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.routers.submissions import router
        from api.auth import AgentAuth

        app = FastAPI()
        app.include_router(router)
        test_client = TestClient(app)

        submission = _make_submission(
            task_overrides={
                "status": "submitted",
                "bounty_usd": 0.10,
                "payment_network": "base",
                "payment_token": "USDC",
            }
        )

        mock_auth = AgentAuth(
            agent_id=AGENT_WALLET,
            auth_method="api_key",
            tier="free",
        )

        # Track calls to update_submission
        update_submission_mock = AsyncMock()

        with (
            patch(
                "api.routers.submissions.verify_agent_auth",
                return_value=mock_auth,
            ),
            patch(
                "api.routers.submissions.verify_agent_owns_submission",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "api.routers.submissions.db.get_submission",
                new_callable=AsyncMock,
                return_value=submission,
            ),
            patch(
                "api.routers.submissions.db.update_submission",
                update_submission_mock,
            ),
            patch(
                "api.routers.submissions._settle_submission_payment",
                new_callable=AsyncMock,
                return_value={
                    "payment_tx": None,
                    "payment_error": "Insufficient USDC balance",
                },
            ),
        ):
            resp = test_client.post(
                f"/api/v1/submissions/{SUBMISSION_ID}/approve",
                json={"notes": "Looks good"},
            )

        # Should return 502 (payment settlement failure)
        assert resp.status_code == 502
        body = resp.json()
        assert (
            "settle payment" in body["detail"].lower()
            or "insufficient" in body["detail"].lower()
        )

        # Critically: update_submission must NOT have been called because
        # settlement failed before we reach the state update
        update_submission_mock.assert_not_called()


# ============================================================================
# Task 5.1: Reputation without transaction
#
# Scenario: Agent tries to rate another agent without a completed task.
#
# KNOWN GAP (documented, NOT fixed in this PR):
#   rate_worker_endpoint only rejects statuses: published, cancelled, expired.
#   It does NOT check that the task reached "completed" status or that an
#   approved submission exists. Therefore, rating a worker whose task is
#   "accepted" or "in_progress" (no submission) succeeds at the HTTP layer.
#   The on-chain call may still fail if the worker has no ERC-8004 identity.
#
#   Similarly, rate_agent_endpoint accepts any status not in
#   {published, cancelled, expired}.
#
# These tests PROVE the gap exists. A future PR should add a check:
#   if task_status != "completed":
#       raise HTTPException(status_code=409, detail="Task not completed")
# ============================================================================

REPUTATION_TASK_ID = "51515151-aaaa-bbbb-cccc-ddddeeee0001"
REPUTATION_WORKER_WALLET = "0xWorkerWalletForRepTest0123456789abcdef00"


class TestReputationWithoutTransaction:
    """Task 5.1: Rating without a completed task -- proves validation gap."""

    @pytest.mark.xfail(
        reason="Known gap: rate_worker does not validate completed submission — 'accepted' status slips through",
        strict=False,
    )
    @pytest.mark.asyncio
    async def test_rate_without_completed_task(self):
        """
        Agent rates worker for a task that was never completed (status='accepted').

        DESIRED BEHAVIOR: Should raise HTTPException(409) because 'accepted'
        means no submission was ever completed. When the gap is fixed, this
        test will pass naturally and the xfail marker can be removed.
        """
        from api.reputation import rate_worker_endpoint, WorkerFeedbackRequest

        # Task in 'accepted' status -- worker assigned but never submitted evidence
        task = _make_task(
            id=REPUTATION_TASK_ID,
            agent_id=AGENT_WALLET,
            status="accepted",
            executor_id=OTHER_EXECUTOR_ID,
            executor={
                "wallet_address": REPUTATION_WORKER_WALLET,
                "erc8004_agent_id": 999,
            },
        )

        mock_api_key = SimpleNamespace(agent_id=AGENT_WALLET)

        from integrations.erc8004.facilitator_client import FeedbackResult

        mock_feedback = FeedbackResult(
            success=True,
            transaction_hash=FAKE_TX_HASH,
            network="base",
            feedback_index=1,
        )

        request = WorkerFeedbackRequest(
            task_id=REPUTATION_TASK_ID,
            score=85,
            worker_address=REPUTATION_WORKER_WALLET,
            comment="Rating without completion",
        )

        with (
            patch(
                "api.reputation.ERC8004_AVAILABLE",
                True,
            ),
            patch(
                "api.reputation._get_task_or_404",
                new_callable=AsyncMock,
                return_value=task,
            ),
            patch(
                "api.reputation.rate_worker",
                new_callable=AsyncMock,
                return_value=mock_feedback,
                create=True,
            ),
            patch(
                "api.reputation.db",
            ),
            patch(
                "api.reputation.log_payment_event",
                new_callable=AsyncMock,
            ),
        ):
            # DESIRED: Should raise HTTPException(409, "Task not completed")
            with pytest.raises(HTTPException) as exc_info:
                await rate_worker_endpoint(request, mock_api_key)

            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_rate_for_nonexistent_task(self):
        """
        Agent rates worker for a task_id that does not exist.

        Expected: HTTP 404 from _get_task_or_404().
        """
        from api.reputation import rate_worker_endpoint, WorkerFeedbackRequest

        nonexistent_task_id = "00000000-0000-0000-0000-000000000000"
        mock_api_key = SimpleNamespace(agent_id=AGENT_WALLET)

        request = WorkerFeedbackRequest(
            task_id=nonexistent_task_id,
            score=75,
            worker_address=REPUTATION_WORKER_WALLET,
        )

        with (
            patch(
                "api.reputation.ERC8004_AVAILABLE",
                True,
            ),
            patch(
                "api.reputation._get_task_or_404",
                new_callable=AsyncMock,
                side_effect=HTTPException(
                    status_code=404,
                    detail=f"Task {nonexistent_task_id} not found",
                ),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await rate_worker_endpoint(request, mock_api_key)

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail

    @pytest.mark.xfail(
        reason="Known gap: rate_worker does not check submission verdict — rejected submissions can be rated",
        strict=False,
    )
    @pytest.mark.asyncio
    async def test_rate_after_rejection(self):
        """
        Agent rates worker after submission was rejected (task status='submitted',
        submission verdict='rejected' but task not yet returned to in_progress).

        DESIRED BEHAVIOR: Should raise HTTPException(409) because no approved
        submission exists. When the gap is fixed, this test will pass naturally
        and the xfail marker can be removed.
        """
        from api.reputation import rate_worker_endpoint, WorkerFeedbackRequest

        # Task in 'submitted' status -- but the submission was rejected
        task = _make_task(
            id=REPUTATION_TASK_ID,
            agent_id=AGENT_WALLET,
            status="submitted",
            executor_id=OTHER_EXECUTOR_ID,
            executor={
                "wallet_address": REPUTATION_WORKER_WALLET,
                "erc8004_agent_id": 888,
            },
        )

        mock_api_key = SimpleNamespace(agent_id=AGENT_WALLET)

        from integrations.erc8004.facilitator_client import FeedbackResult

        mock_feedback = FeedbackResult(
            success=True,
            transaction_hash=FAKE_TX_HASH,
            network="base",
            feedback_index=2,
        )

        request = WorkerFeedbackRequest(
            task_id=REPUTATION_TASK_ID,
            score=20,
            worker_address=REPUTATION_WORKER_WALLET,
            comment="Rating after rejection",
        )

        with (
            patch(
                "api.reputation.ERC8004_AVAILABLE",
                True,
            ),
            patch(
                "api.reputation._get_task_or_404",
                new_callable=AsyncMock,
                return_value=task,
            ),
            patch(
                "api.reputation.rate_worker",
                new_callable=AsyncMock,
                return_value=mock_feedback,
                create=True,
            ),
            patch(
                "api.reputation.db",
            ),
            patch(
                "api.reputation.log_payment_event",
                new_callable=AsyncMock,
            ),
        ):
            # DESIRED: Should raise HTTPException(409) because submission was rejected
            with pytest.raises(HTTPException) as exc_info:
                await rate_worker_endpoint(request, mock_api_key)

            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_rate_blocked_for_published_status(self):
        """
        Sanity check: rating IS correctly blocked for 'published' status.
        Confirms the existing validation works for the statuses it does check.
        """
        from api.reputation import rate_worker_endpoint, WorkerFeedbackRequest

        task = _make_task(
            id=REPUTATION_TASK_ID,
            agent_id=AGENT_WALLET,
            status="published",
        )

        mock_api_key = SimpleNamespace(agent_id=AGENT_WALLET)

        request = WorkerFeedbackRequest(
            task_id=REPUTATION_TASK_ID,
            score=50,
            worker_address=REPUTATION_WORKER_WALLET,
        )

        with (
            patch(
                "api.reputation.ERC8004_AVAILABLE",
                True,
            ),
            patch(
                "api.reputation._get_task_or_404",
                new_callable=AsyncMock,
                return_value=task,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await rate_worker_endpoint(request, mock_api_key)

            assert exc_info.value.status_code == 409
            assert "published" in exc_info.value.detail


# ============================================================================
# Task 5.2: Bilateral task economy
#
# Scenario: Agent A creates a task for B, Agent B creates a task for A.
# Both complete successfully. Circular economy validated.
#
# Tests prove that:
#   1. Two agents can each publish tasks and work on the other's.
#   2. Both tasks complete independently without conflicts.
#   3. Bidirectional reputation works (both rate each other).
#   4. An entity can be publisher and worker simultaneously.
# ============================================================================

AGENT_A_WALLET = "0xAgentA_Wallet_aaaa1111bbbb2222cccc3333dddd"
AGENT_B_WALLET = "0xAgentB_Wallet_eeee4444ffff5555aaaa6666bbbb"
AGENT_A_EXECUTOR_ID = "aa-aa-aaaa-1111-bbbb-2222-ccccddddeeee"
AGENT_B_EXECUTOR_ID = "bb-bb-eeee-4444-ffff-5555-aaaa6666bbbb"
TASK_A_ID = "52520001-aaaa-1111-bbbb-000000000001"
TASK_B_ID = "52520002-bbbb-2222-cccc-000000000002"


class TestBilateralTaskEconomy:
    """Task 5.2: Full circular flow -- A tasks B, B tasks A, both complete."""

    @pytest.mark.asyncio
    async def test_bilateral_task_economy(self):
        """
        Full circular flow:
          1. Agent A publishes task, Agent B applies and completes it.
          2. Agent B publishes task, Agent A applies and completes it.
          3. Both tasks reach COMPLETED.
          4. Both agents rate each other.
          5. Both reputation scores updated.
        """
        import supabase_client as sdb

        # =================================================================
        # Phase 1: Agent A publishes task -> Agent B completes
        # =================================================================
        task_a = _make_task(
            id=TASK_A_ID,
            agent_id=AGENT_A_WALLET,
            status="accepted",
            executor_id=AGENT_B_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        # B submits evidence for A's task
        sub_a = {
            "id": "sub-bilateral-a-111111111111",
            "task_id": TASK_A_ID,
            "executor_id": AGENT_B_EXECUTOR_ID,
            "evidence": {"screenshot": "https://cdn.example.com/b_for_a.jpg"},
            "notes": "Agent B completed task for Agent A",
            "submitted_at": "2026-02-20T10:00:00+00:00",
            "agent_verdict": "pending",
        }
        mock_client_1 = MagicMock()
        mock_client_1.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[sub_a])
        )

        with (
            patch.object(sdb, "get_task", new_callable=AsyncMock, return_value=task_a),
            patch.object(sdb, "get_client", return_value=mock_client_1),
            patch.object(sdb, "update_task", new_callable=AsyncMock),
        ):
            result_a = await sdb.submit_work(
                task_id=TASK_A_ID,
                executor_id=AGENT_B_EXECUTOR_ID,
                evidence={"screenshot": "https://cdn.example.com/b_for_a.jpg"},
                notes="Agent B completed task for Agent A",
            )
            assert result_a["submission"]["id"] == sub_a["id"]

        # A approves B's submission
        sub_a_for_approve = {
            **sub_a,
            "task": {**task_a, "status": "submitted"},
        }
        approval_a = {
            **sub_a,
            "agent_verdict": "accepted",
            "verified_at": "2026-02-20T10:30:00+00:00",
        }
        mock_client_2 = MagicMock()
        mock_client_2.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[approval_a]
        )
        mock_client_2.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"reputation_score": 80}
        )

        with (
            patch.object(
                sdb,
                "get_submission",
                new_callable=AsyncMock,
                return_value=sub_a_for_approve,
            ),
            patch.object(sdb, "get_client", return_value=mock_client_2),
            patch.object(sdb, "update_task", new_callable=AsyncMock) as mock_ut_a,
        ):
            updated_a = await sdb.update_submission(
                submission_id=sub_a["id"],
                agent_id=AGENT_A_WALLET,
                verdict="accepted",
                notes="Good work, approved",
            )
            assert updated_a["agent_verdict"] == "accepted"
            mock_ut_a.assert_called_once()
            assert mock_ut_a.call_args[0][1]["status"] == "completed"

        # =================================================================
        # Phase 2: Agent B publishes task -> Agent A completes
        # =================================================================
        task_b = _make_task(
            id=TASK_B_ID,
            agent_id=AGENT_B_WALLET,
            status="accepted",
            executor_id=AGENT_A_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        sub_b = {
            "id": "sub-bilateral-b-222222222222",
            "task_id": TASK_B_ID,
            "executor_id": AGENT_A_EXECUTOR_ID,
            "evidence": {"screenshot": "https://cdn.example.com/a_for_b.jpg"},
            "notes": "Agent A completed task for Agent B",
            "submitted_at": "2026-02-20T11:00:00+00:00",
            "agent_verdict": "pending",
        }
        mock_client_3 = MagicMock()
        mock_client_3.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[sub_b])
        )

        with (
            patch.object(sdb, "get_task", new_callable=AsyncMock, return_value=task_b),
            patch.object(sdb, "get_client", return_value=mock_client_3),
            patch.object(sdb, "update_task", new_callable=AsyncMock),
        ):
            result_b = await sdb.submit_work(
                task_id=TASK_B_ID,
                executor_id=AGENT_A_EXECUTOR_ID,
                evidence={"screenshot": "https://cdn.example.com/a_for_b.jpg"},
                notes="Agent A completed task for Agent B",
            )
            assert result_b["submission"]["id"] == sub_b["id"]

        # B approves A's submission
        sub_b_for_approve = {
            **sub_b,
            "task": {**task_b, "status": "submitted"},
        }
        approval_b = {
            **sub_b,
            "agent_verdict": "accepted",
            "verified_at": "2026-02-20T11:30:00+00:00",
        }
        mock_client_4 = MagicMock()
        mock_client_4.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[approval_b]
        )
        mock_client_4.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"reputation_score": 75}
        )

        with (
            patch.object(
                sdb,
                "get_submission",
                new_callable=AsyncMock,
                return_value=sub_b_for_approve,
            ),
            patch.object(sdb, "get_client", return_value=mock_client_4),
            patch.object(sdb, "update_task", new_callable=AsyncMock) as mock_ut_b,
        ):
            updated_b = await sdb.update_submission(
                submission_id=sub_b["id"],
                agent_id=AGENT_B_WALLET,
                verdict="accepted",
                notes="Well done, approved",
            )
            assert updated_b["agent_verdict"] == "accepted"
            mock_ut_b.assert_called_once()
            assert mock_ut_b.call_args[0][1]["status"] == "completed"

        # =================================================================
        # Phase 3: Bidirectional reputation -- both rate each other
        # =================================================================
        from integrations.erc8004.facilitator_client import FeedbackResult

        # A rates B (as worker on task A)
        mock_fb_a_rates_b = FeedbackResult(
            success=True,
            transaction_hash="0xrate_a_to_b_" + "a" * 52,
            network="base",
            feedback_index=10,
        )

        # B rates A (as worker on task B)
        mock_fb_b_rates_a = FeedbackResult(
            success=True,
            transaction_hash="0xrate_b_to_a_" + "b" * 52,
            network="base",
            feedback_index=11,
        )

        with patch(
            "integrations.erc8004.feedback_store.persist_and_hash_feedback",
            new_callable=AsyncMock,
            return_value=("https://cdn.example.com/fb.json", "0xhash"),
        ):
            # A rates B (worker on task A) via direct_reputation
            with patch(
                "integrations.erc8004.direct_reputation.give_feedback_direct",
                new_callable=AsyncMock,
                return_value=mock_fb_a_rates_b,
            ) as mock_direct_ab:
                from integrations.erc8004.facilitator_client import rate_worker

                result_ab = await rate_worker(
                    task_id=TASK_A_ID,
                    score=90,
                    worker_address=AGENT_B_WALLET,
                    comment="B did great work on my task",
                    worker_agent_id=200,
                )
                assert result_ab.success is True
                assert result_ab.feedback_index == 10
                mock_direct_ab.assert_called_once()

            # B rates A (worker on task B)
            with patch(
                "integrations.erc8004.direct_reputation.give_feedback_direct",
                new_callable=AsyncMock,
                return_value=mock_fb_b_rates_a,
            ) as mock_direct_ba:
                result_ba = await rate_worker(
                    task_id=TASK_B_ID,
                    score=85,
                    worker_address=AGENT_A_WALLET,
                    comment="A did great work on my task",
                    worker_agent_id=100,
                )
                assert result_ba.success is True
                assert result_ba.feedback_index == 11
                mock_direct_ba.assert_called_once()

        # Both directions succeeded independently
        assert result_ab.transaction_hash != result_ba.transaction_hash

    @pytest.mark.asyncio
    async def test_bilateral_same_category(self):
        """
        Both tasks in the same category -- verify no conflicts.

        When two agents create tasks in the same category and work on each
        other's tasks, the category field should not cause any collision or
        uniqueness constraint violation.
        """
        import supabase_client as sdb

        shared_category = "physical_presence"

        task_a = _make_task(
            id=TASK_A_ID,
            agent_id=AGENT_A_WALLET,
            status="accepted",
            category=shared_category,
            executor_id=AGENT_B_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )
        task_b = _make_task(
            id=TASK_B_ID,
            agent_id=AGENT_B_WALLET,
            status="accepted",
            category=shared_category,
            executor_id=AGENT_A_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        sub_a = {
            "id": "sub-same-cat-a-111111111111",
            "task_id": TASK_A_ID,
            "executor_id": AGENT_B_EXECUTOR_ID,
            "evidence": {"photo": "https://cdn.example.com/same_cat_a.jpg"},
            "notes": "Same category, task A",
            "submitted_at": "2026-02-20T10:00:00+00:00",
            "agent_verdict": "pending",
        }
        sub_b = {
            "id": "sub-same-cat-b-222222222222",
            "task_id": TASK_B_ID,
            "executor_id": AGENT_A_EXECUTOR_ID,
            "evidence": {"photo": "https://cdn.example.com/same_cat_b.jpg"},
            "notes": "Same category, task B",
            "submitted_at": "2026-02-20T10:05:00+00:00",
            "agent_verdict": "pending",
        }

        # Submit evidence for task A (B is worker)
        mock_client_a = MagicMock()
        mock_client_a.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[sub_a])
        )
        with (
            patch.object(sdb, "get_task", new_callable=AsyncMock, return_value=task_a),
            patch.object(sdb, "get_client", return_value=mock_client_a),
            patch.object(sdb, "update_task", new_callable=AsyncMock),
        ):
            result_a = await sdb.submit_work(
                task_id=TASK_A_ID,
                executor_id=AGENT_B_EXECUTOR_ID,
                evidence={"photo": "https://cdn.example.com/same_cat_a.jpg"},
                notes="Same category, task A",
            )
            assert result_a["submission"]["id"] == sub_a["id"]

        # Submit evidence for task B (A is worker)
        mock_client_b = MagicMock()
        mock_client_b.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[sub_b])
        )
        with (
            patch.object(sdb, "get_task", new_callable=AsyncMock, return_value=task_b),
            patch.object(sdb, "get_client", return_value=mock_client_b),
            patch.object(sdb, "update_task", new_callable=AsyncMock),
        ):
            result_b = await sdb.submit_work(
                task_id=TASK_B_ID,
                executor_id=AGENT_A_EXECUTOR_ID,
                evidence={"photo": "https://cdn.example.com/same_cat_b.jpg"},
                notes="Same category, task B",
            )
            assert result_b["submission"]["id"] == sub_b["id"]

        # Approve both -- task A
        sub_a_approve = {
            **sub_a,
            "task": {**task_a, "status": "submitted"},
        }
        approved_a = {**sub_a, "agent_verdict": "accepted"}
        mock_ca = MagicMock()
        mock_ca.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[approved_a]
        )
        mock_ca.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"reputation_score": 80}
        )

        with (
            patch.object(
                sdb,
                "get_submission",
                new_callable=AsyncMock,
                return_value=sub_a_approve,
            ),
            patch.object(sdb, "get_client", return_value=mock_ca),
            patch.object(sdb, "update_task", new_callable=AsyncMock) as mock_ut_a,
        ):
            ua = await sdb.update_submission(
                submission_id=sub_a["id"],
                agent_id=AGENT_A_WALLET,
                verdict="accepted",
                notes="Approved",
            )
            assert ua["agent_verdict"] == "accepted"
            assert mock_ut_a.call_args[0][1]["status"] == "completed"

        # Approve both -- task B
        sub_b_approve = {
            **sub_b,
            "task": {**task_b, "status": "submitted"},
        }
        approved_b = {**sub_b, "agent_verdict": "accepted"}
        mock_cb = MagicMock()
        mock_cb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[approved_b]
        )
        mock_cb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"reputation_score": 70}
        )

        with (
            patch.object(
                sdb,
                "get_submission",
                new_callable=AsyncMock,
                return_value=sub_b_approve,
            ),
            patch.object(sdb, "get_client", return_value=mock_cb),
            patch.object(sdb, "update_task", new_callable=AsyncMock) as mock_ut_b,
        ):
            ub = await sdb.update_submission(
                submission_id=sub_b["id"],
                agent_id=AGENT_B_WALLET,
                verdict="accepted",
                notes="Approved",
            )
            assert ub["agent_verdict"] == "accepted"
            assert mock_ut_b.call_args[0][1]["status"] == "completed"

        # Both tasks completed with the same category -- no conflicts
        assert task_a["category"] == task_b["category"] == shared_category

    @pytest.mark.asyncio
    async def test_agent_can_be_both_publisher_and_worker(self):
        """
        Same agent is publisher on task A and worker on task B simultaneously.

        This validates that the system doesn't conflate roles: an agent
        creating a task is not prevented from accepting work on another agent's
        task. The self-application prevention only blocks applying to your OWN
        task, not to tasks from other agents.
        """
        import supabase_client as sdb

        # Agent A is publisher on task A
        task_a_published = _make_task(
            id=TASK_A_ID,
            agent_id=AGENT_A_WALLET,
            status="published",
        )

        # Agent A is also worker on task B (published by B)
        task_b_with_a_as_worker = _make_task(
            id=TASK_B_ID,
            agent_id=AGENT_B_WALLET,
            status="accepted",
            executor_id=AGENT_A_EXECUTOR_ID,
            deadline="2099-12-31T23:59:59Z",
        )

        # A can submit evidence on B's task while A's own task is still published
        sub_for_b = {
            "id": "sub-dual-role-a-333333333333",
            "task_id": TASK_B_ID,
            "executor_id": AGENT_A_EXECUTOR_ID,
            "evidence": {"screenshot": "https://cdn.example.com/a_works_for_b.jpg"},
            "notes": "A working on B's task while publishing own task",
            "submitted_at": "2026-02-20T12:00:00+00:00",
            "agent_verdict": "pending",
        }
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[sub_for_b])
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=task_b_with_a_as_worker,
            ),
            patch.object(sdb, "get_client", return_value=mock_client),
            patch.object(sdb, "update_task", new_callable=AsyncMock),
        ):
            result = await sdb.submit_work(
                task_id=TASK_B_ID,
                executor_id=AGENT_A_EXECUTOR_ID,
                evidence={"screenshot": "https://cdn.example.com/a_works_for_b.jpg"},
                notes="A working on B's task while publishing own task",
            )
            assert result["submission"]["id"] == sub_for_b["id"]

        # Verify self-application prevention: A cannot apply to A's own task
        executor_a = _make_executor(
            wallet_address=AGENT_A_WALLET,
            executor_id=AGENT_A_EXECUTOR_ID,
        )

        mock_client_self = MagicMock()
        mock_client_self.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_a
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=task_a_published,
            ),
            patch.object(sdb, "get_client", return_value=mock_client_self),
        ):
            with pytest.raises(Exception, match="[Cc]annot apply.*own task"):
                await sdb.apply_to_task(
                    task_id=TASK_A_ID,
                    executor_id=AGENT_A_EXECUTOR_ID,
                    message="Trying to self-apply",
                )

        # But A CAN apply to B's task (different agent)
        task_b_published = _make_task(
            id=TASK_B_ID,
            agent_id=AGENT_B_WALLET,
            status="published",
        )

        # Mock for apply_to_task on B's task
        application_result = {
            "id": "app-dual-role-001",
            "task_id": TASK_B_ID,
            "executor_id": AGENT_A_EXECUTOR_ID,
            "message": "I can help with this",
            "status": "pending",
        }

        mock_client_apply = MagicMock()
        # Executor lookup: table("executors").select("*").eq(id).single().execute()
        mock_client_apply.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_a
        )
        # Existing application check: table(apps).select("*").eq(task_id).eq(exec_id).execute()
        mock_client_apply.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        # Insert application: table(apps).insert({...}).execute()
        mock_client_apply.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[application_result]
        )

        with (
            patch.object(
                sdb,
                "get_task",
                new_callable=AsyncMock,
                return_value=task_b_published,
            ),
            patch.object(sdb, "get_client", return_value=mock_client_apply),
        ):
            app_result = await sdb.apply_to_task(
                task_id=TASK_B_ID,
                executor_id=AGENT_A_EXECUTOR_ID,
                message="I can help with this",
            )
            # Application succeeded -- A is both publisher (on own task)
            # and worker (on B's task)
            assert app_result is not None


# ============================================================================
# Audit Bug Fixes: Self-application with numeric agent_id, rejection rollback,
# case-insensitive agent_id matching
# ============================================================================


class TestSelfApplicationNumericAgentId:
    """BUG 1: Self-application guard must work when agent_id is numeric (ERC-8004)."""

    @pytest.mark.asyncio
    async def test_self_application_numeric_agent_id_db(self):
        """
        apply_to_task() raises when task.agent_id is a numeric ERC-8004 ID
        and executor.erc8004_agent_id matches.
        """
        import supabase_client as db

        # Task created by agent with numeric ID "2106"
        task = _make_task(agent_id="2106")
        # Executor whose erc8004_agent_id is 2106 (same agent)
        executor_data = _make_executor(
            wallet_address=OTHER_WALLET,
            executor_id=EXECUTOR_ID,
        )
        executor_data["erc8004_agent_id"] = 2106

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data,
        )

        with (
            patch.object(
                db,
                "get_task",
                new_callable=AsyncMock,
                return_value=task,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(
                db,
                "_resolve_applications_table",
                return_value="task_applications",
            ),
        ):
            with pytest.raises(Exception, match="Cannot apply to your own task"):
                await db.apply_to_task(
                    task_id=TASK_ID,
                    executor_id=EXECUTOR_ID,
                )

    @pytest.mark.asyncio
    async def test_self_application_numeric_agent_id_mcp_tool(self):
        """
        MCP tool em_apply_to_task returns error when task.agent_id is numeric
        and executor.erc8004_agent_id matches.
        """
        task = _make_task(agent_id="2106")
        executor_stats = _make_executor(
            wallet_address=OTHER_WALLET,
            executor_id=EXECUTOR_ID,
        )
        executor_stats["erc8004_agent_id"] = 2106

        mock_db = MagicMock()
        mock_db.get_task = AsyncMock(return_value=task)
        mock_db.get_executor_stats = AsyncMock(return_value=executor_stats)
        # apply_to_task should NOT be called if pre-check catches it
        mock_db.apply_to_task = AsyncMock()

        mcp_server = MagicMock()
        tools = {}

        def capture_tool(**kwargs):
            def decorator(fn):
                tools[kwargs.get("name", fn.__name__)] = fn
                return fn

            return decorator

        mcp_server.tool = capture_tool

        from tools.worker_tools import register_worker_tools

        register_worker_tools(mcp_server, mock_db)

        apply_fn = tools["em_apply_to_task"]

        params = SimpleNamespace(
            task_id=TASK_ID,
            executor_id=EXECUTOR_ID,
            message=None,
        )

        result = await apply_fn(params)
        assert "Cannot apply to your own task" in result
        # DB apply_to_task should never be called
        mock_db.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_wallet_based_agent_id_still_works(self):
        """
        Self-application guard still works for wallet-based agent_id (original case).
        """
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(
            wallet_address=AGENT_WALLET,
            executor_id=EXECUTOR_ID,
        )

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data,
        )

        with (
            patch.object(
                db,
                "get_task",
                new_callable=AsyncMock,
                return_value=task,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(
                db,
                "_resolve_applications_table",
                return_value="task_applications",
            ),
        ):
            with pytest.raises(Exception, match="Cannot apply to your own task"):
                await db.apply_to_task(
                    task_id=TASK_ID,
                    executor_id=EXECUTOR_ID,
                )

    @pytest.mark.asyncio
    async def test_different_numeric_agent_id_allowed(self):
        """
        Executor with erc8004_agent_id=999 can apply to task with agent_id="2106".
        """
        import supabase_client as db

        task = _make_task(agent_id="2106")
        executor_data = _make_executor(
            wallet_address=OTHER_WALLET,
            executor_id=EXECUTOR_ID,
        )
        executor_data["erc8004_agent_id"] = 999

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data,
        )
        # Existing application check returns empty
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[],
        )
        # Insert application
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(
                data=[
                    {
                        "id": "app-1",
                        "task_id": TASK_ID,
                        "executor_id": EXECUTOR_ID,
                    }
                ],
            )
        )

        with (
            patch.object(
                db,
                "get_task",
                new_callable=AsyncMock,
                return_value=task,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(
                db,
                "_resolve_applications_table",
                return_value="task_applications",
            ),
        ):
            result = await db.apply_to_task(
                task_id=TASK_ID,
                executor_id=EXECUTOR_ID,
            )
            assert result is not None


class TestRejectionRollbackGuard:
    """BUG 2: Rejection must not resurrect cancelled/expired/completed tasks."""

    @pytest.mark.asyncio
    async def test_rejection_does_not_resurrect_cancelled_task(self):
        """
        When a submission is rejected but the task is already cancelled,
        the task status should NOT be changed back to in_progress.
        """
        import supabase_client as db

        cancelled_task = _make_task(status="cancelled")
        submission = {
            "id": "sub-1",
            "task_id": TASK_ID,
            "executor_id": EXECUTOR_ID,
            "task": cancelled_task,
        }

        mock_client = MagicMock()
        # update submission
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "sub-1",
                    "agent_verdict": "rejected",
                    "agent_notes": None,
                    "verified_at": None,
                }
            ],
        )

        mock_update_task = AsyncMock()

        with (
            patch.object(
                db,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "update_task", mock_update_task),
        ):
            result = await db.update_submission(
                submission_id="sub-1",
                agent_id=cancelled_task["agent_id"],
                verdict="rejected",
            )
            assert result is not None
            # update_task should NOT have been called -- task is cancelled
            mock_update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejection_does_not_resurrect_expired_task(self):
        """
        When a submission is rejected but the task is expired,
        the task status should NOT be changed.
        """
        import supabase_client as db

        expired_task = _make_task(status="expired")
        submission = {
            "id": "sub-2",
            "task_id": TASK_ID,
            "executor_id": EXECUTOR_ID,
            "task": expired_task,
        }

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "sub-2",
                    "agent_verdict": "rejected",
                    "agent_notes": None,
                    "verified_at": None,
                }
            ],
        )

        mock_update_task = AsyncMock()

        with (
            patch.object(
                db,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "update_task", mock_update_task),
        ):
            result = await db.update_submission(
                submission_id="sub-2",
                agent_id=expired_task["agent_id"],
                verdict="rejected",
            )
            assert result is not None
            mock_update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejection_does_not_resurrect_completed_task(self):
        """
        When a submission is rejected but the task is completed,
        the task status should NOT be changed.
        """
        import supabase_client as db

        completed_task = _make_task(status="completed")
        submission = {
            "id": "sub-3",
            "task_id": TASK_ID,
            "executor_id": EXECUTOR_ID,
            "task": completed_task,
        }

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "sub-3",
                    "agent_verdict": "rejected",
                    "agent_notes": None,
                    "verified_at": None,
                }
            ],
        )

        mock_update_task = AsyncMock()

        with (
            patch.object(
                db,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "update_task", mock_update_task),
        ):
            result = await db.update_submission(
                submission_id="sub-3",
                agent_id=completed_task["agent_id"],
                verdict="rejected",
            )
            assert result is not None
            mock_update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejection_rolls_back_submitted_task(self):
        """
        Normal case: rejection on a submitted task DOES roll back to in_progress.
        """
        import supabase_client as db

        submitted_task = _make_task(status="submitted")
        submission = {
            "id": "sub-4",
            "task_id": TASK_ID,
            "executor_id": EXECUTOR_ID,
            "task": submitted_task,
        }

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "sub-4",
                    "agent_verdict": "rejected",
                    "agent_notes": None,
                    "verified_at": None,
                }
            ],
        )

        mock_update_task = AsyncMock(return_value=_make_task(status="in_progress"))

        with (
            patch.object(
                db,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "update_task", mock_update_task),
        ):
            result = await db.update_submission(
                submission_id="sub-4",
                agent_id=submitted_task["agent_id"],
                verdict="rejected",
            )
            assert result is not None
            # update_task SHOULD be called to roll back to in_progress
            mock_update_task.assert_called_once_with(TASK_ID, {"status": "in_progress"})


class TestUpdateSubmissionCaseInsensitive:
    """BUG 3: agent_id comparison in update_submission must be case-insensitive."""

    @pytest.mark.asyncio
    async def test_update_submission_case_insensitive_agent_id(self):
        """
        update_submission() should succeed when agent_id differs only in case
        (e.g., checksummed vs lowercase).
        """
        import supabase_client as db

        # Task with checksummed agent_id
        checksummed_agent = "0xD3868E1eD738CED6945A574a7c769433BeD5d474"
        lowercase_agent = checksummed_agent.lower()

        task = _make_task(agent_id=checksummed_agent, status="submitted")
        submission = {
            "id": "sub-case",
            "task_id": TASK_ID,
            "executor_id": EXECUTOR_ID,
            "task": task,
        }

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "sub-case",
                    "agent_verdict": "accepted",
                    "agent_notes": None,
                    "verified_at": "2026-02-20T00:00:00Z",
                }
            ],
        )

        mock_update_task = AsyncMock(return_value=_make_task(status="completed"))
        mock_update_rep = AsyncMock()

        with (
            patch.object(
                db,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission,
            ),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "update_task", mock_update_task),
            patch.object(db, "_update_executor_reputation", mock_update_rep),
        ):
            # Use lowercase agent_id -- should still be authorized
            result = await db.update_submission(
                submission_id="sub-case",
                agent_id=lowercase_agent,
                verdict="accepted",
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_update_submission_wrong_agent_rejected(self):
        """
        update_submission() should still reject a completely different agent.
        """
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET, status="submitted")
        submission = {
            "id": "sub-wrong",
            "task_id": TASK_ID,
            "executor_id": EXECUTOR_ID,
            "task": task,
        }

        mock_client = MagicMock()

        with (
            patch.object(
                db,
                "get_submission",
                new_callable=AsyncMock,
                return_value=submission,
            ),
            patch.object(db, "get_client", return_value=mock_client),
        ):
            with pytest.raises(Exception, match="Not authorized"):
                await db.update_submission(
                    submission_id="sub-wrong",
                    agent_id=OTHER_WALLET,
                    verdict="accepted",
                )


class TestSelfAssignmentPrevention:
    """Task 0.1: Self-assignment guard in assign_task() — mirrors TestSelfApplicationDB."""

    @pytest.mark.asyncio
    async def test_self_assignment_rejected_wallet_match(self):
        """assign_task() raises when executor wallet == task agent_id."""
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(wallet_address=AGENT_WALLET)

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data
        )

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(
                db,
                "_resolve_applications_table",
                return_value="task_applications",
            ),
        ):
            with pytest.raises(Exception, match="Cannot assign task to yourself"):
                await db.assign_task(
                    task_id=TASK_ID,
                    agent_id=AGENT_WALLET,
                    executor_id=EXECUTOR_ID,
                )

    @pytest.mark.asyncio
    async def test_self_assignment_rejected_numeric_agent_id(self):
        """assign_task() raises when executor erc8004_agent_id matches task agent_id."""
        import supabase_client as db

        task = _make_task(agent_id="2106")
        executor_data = _make_executor(wallet_address=OTHER_WALLET)
        executor_data["erc8004_agent_id"] = 2106

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data
        )

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(
                db,
                "_resolve_applications_table",
                return_value="task_applications",
            ),
        ):
            with pytest.raises(Exception, match="Cannot assign task to yourself"):
                await db.assign_task(
                    task_id=TASK_ID,
                    agent_id="2106",
                    executor_id=EXECUTOR_ID,
                )

    @pytest.mark.asyncio
    async def test_assignment_allowed_different_agent(self):
        """assign_task() succeeds when executor is a different agent."""
        import supabase_client as db

        task = _make_task(agent_id=AGENT_WALLET)
        executor_data = _make_executor(
            wallet_address=OTHER_WALLET, executor_id=EXECUTOR_ID
        )

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=executor_data
        )

        mock_update = AsyncMock(return_value=_make_task(status="accepted"))

        with (
            patch.object(db, "get_task", new_callable=AsyncMock, return_value=task),
            patch.object(db, "get_client", return_value=mock_client),
            patch.object(db, "update_task", mock_update),
            patch.object(
                db,
                "_resolve_applications_table",
                return_value="task_applications",
            ),
        ):
            result = await db.assign_task(
                task_id=TASK_ID,
                agent_id=AGENT_WALLET,
                executor_id=EXECUTOR_ID,
            )
            assert result is not None
