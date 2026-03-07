"""
Tests for KK V2 Escrow Flow — the money path through Execution Market.

Covers:
  - Buyer flow: publish bounty → manage → assign → approve → rate
  - Seller flow: discover bounties → apply → fulfill → rate agent
  - Deduplication (same-category bounty, same-title offering)
  - State persistence (save/load)
  - Executor wallet resolution
  - Edge cases: budget limits, 409 conflicts, empty applications, etc.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.escrow_flow import (
    apply_to_bounty,
    discover_bounties,
    fulfill_assigned,
    load_escrow_state,
    manage_bounties,
    publish_bounty,
    publish_offering_deduped,
    resolve_executor_wallet,
    save_escrow_state,
    _load_executor_map,
)
from services.em_client import AgentContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_agent(
    name: str = "test-agent",
    wallet: str = "0xTestWallet123",
    budget: float = 10.0,
    executor_id: str = "exec-001",
) -> AgentContext:
    """Create a test AgentContext."""
    return AgentContext(
        name=name,
        wallet_address=wallet,
        workspace_dir=Path("/tmp/kk-test"),
        daily_budget_usd=budget,
        per_task_budget_usd=2.0,
        executor_id=executor_id,
    )


def make_client(agent: AgentContext | None = None) -> MagicMock:
    """Create a mock EMClient."""
    if agent is None:
        agent = make_agent()
    client = MagicMock()
    client.agent = agent
    return client


def make_task(
    task_id: str = "task-001",
    title: str = "Test bounty",
    status: str = "published",
    bounty: float = 0.50,
    agent_wallet: str = "0xOtherAgent",
) -> dict:
    """Create a test task dict."""
    return {
        "id": task_id,
        "title": title,
        "status": status,
        "bounty_usd": bounty,
        "agent_wallet": agent_wallet,
        "agent_id": agent_wallet,
        "category": "knowledge_access",
    }


# ---------------------------------------------------------------------------
# State Persistence
# ---------------------------------------------------------------------------

class TestStatePersistence:
    """Test escrow state save/load."""

    def test_save_and_load(self, tmp_path):
        state = {
            "published": {"task-1": {"title": "Test", "status": "published"}},
            "applied": {"task-2": {"title": "Applied", "status": "applied"}},
        }
        save_escrow_state(tmp_path, state)
        loaded = load_escrow_state(tmp_path)
        assert loaded == state

    def test_load_empty_dir(self, tmp_path):
        loaded = load_escrow_state(tmp_path)
        assert loaded == {"published": {}, "applied": {}}

    def test_save_creates_dir(self, tmp_path):
        new_dir = tmp_path / "nested" / "state"
        state = {"published": {}, "applied": {}}
        save_escrow_state(new_dir, state)
        assert (new_dir / "escrow_state.json").exists()

    def test_save_with_prefix(self, tmp_path):
        state = {"published": {"t1": {}}, "applied": {}}
        save_escrow_state(tmp_path, state, prefix="buyer")
        assert (tmp_path / "buyer_escrow_state.json").exists()
        loaded = load_escrow_state(tmp_path, prefix="buyer")
        assert loaded == state

    def test_load_corrupt_file(self, tmp_path):
        (tmp_path / "escrow_state.json").write_text("NOT JSON")
        loaded = load_escrow_state(tmp_path)
        assert loaded == {"published": {}, "applied": {}}


# ---------------------------------------------------------------------------
# Buyer Flow: Publish Bounty
# ---------------------------------------------------------------------------

class TestPublishBounty:
    """Test buyer bounty publishing."""

    @pytest.mark.asyncio
    async def test_publish_success(self):
        client = make_client()
        client.publish_task = AsyncMock(return_value={"task": {"id": "new-task"}})
        state = {"published": {}, "applied": {}}

        result = await publish_bounty(
            client=client,
            title="Research DeFi protocols",
            instructions="Analyze top 5 DeFi protocols",
            bounty_usd=0.25,
            category_key="research",
            state=state,
        )

        assert result == "new-task"
        assert "new-task" in state["published"]
        assert state["published"]["new-task"]["status"] == "published"
        assert state["published"]["new-task"]["bounty"] == 0.25
        assert client.agent.daily_spent_usd == 0.25

    @pytest.mark.asyncio
    async def test_publish_dedup_existing_active(self):
        """Should skip if active bounty exists in same category."""
        client = make_client()
        state = {
            "published": {
                "existing-task": {
                    "category": "research",
                    "status": "published",
                }
            },
            "applied": {},
        }

        result = await publish_bounty(
            client=client,
            title="Research DeFi protocols v2",
            instructions="...",
            bounty_usd=0.25,
            category_key="research",
            state=state,
        )

        assert result is None  # Deduplicated
        assert client.agent.daily_spent_usd == 0.0

    @pytest.mark.asyncio
    async def test_publish_allows_different_category(self):
        """Should allow bounty in a different category."""
        client = make_client()
        client.publish_task = AsyncMock(return_value={"task": {"id": "new-task-2"}})
        state = {
            "published": {
                "existing": {"category": "research", "status": "published"}
            },
            "applied": {},
        }

        result = await publish_bounty(
            client=client,
            title="Code review",
            instructions="...",
            bounty_usd=0.30,
            category_key="code_review",  # Different category
            state=state,
        )

        assert result == "new-task-2"

    @pytest.mark.asyncio
    async def test_publish_allows_completed_category(self):
        """Should allow new bounty if previous one in same category is completed."""
        client = make_client()
        client.publish_task = AsyncMock(return_value={"task": {"id": "new-task-3"}})
        state = {
            "published": {
                "old": {"category": "research", "status": "completed"}
            },
            "applied": {},
        }

        result = await publish_bounty(
            client=client,
            title="Research v3",
            instructions="...",
            bounty_usd=0.25,
            category_key="research",
            state=state,
        )

        assert result == "new-task-3"

    @pytest.mark.asyncio
    async def test_publish_budget_exceeded(self):
        """Should reject when budget is exhausted."""
        agent = make_agent(budget=0.10)
        agent.daily_spent_usd = 0.08
        client = make_client(agent)
        state = {"published": {}, "applied": {}}

        result = await publish_bounty(
            client=client,
            title="Expensive task",
            instructions="...",
            bounty_usd=0.25,
            category_key="expensive",
            state=state,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_publish_dry_run(self):
        """Dry run should not call API or track state."""
        client = make_client()
        state = {"published": {}, "applied": {}}

        result = await publish_bounty(
            client=client,
            title="Test",
            instructions="...",
            bounty_usd=0.25,
            category_key="test",
            state=state,
            dry_run=True,
        )

        assert result is None
        assert len(state["published"]) == 0

    @pytest.mark.asyncio
    async def test_publish_api_failure(self):
        """API failure should be caught and return None."""
        client = make_client()
        client.publish_task = AsyncMock(side_effect=Exception("API timeout"))
        state = {"published": {}, "applied": {}}

        result = await publish_bounty(
            client=client,
            title="Will fail",
            instructions="...",
            bounty_usd=0.25,
            category_key="test",
            state=state,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_publish_with_skills_and_executor_type(self):
        """Should pass target_executor and skills_required."""
        client = make_client()
        client.publish_task = AsyncMock(return_value={"task": {"id": "skill-task"}})
        state = {"published": {}, "applied": {}}

        result = await publish_bounty(
            client=client,
            title="Skilled task",
            instructions="...",
            bounty_usd=0.50,
            category_key="skilled",
            state=state,
            target_executor="agent",
            skills_required=["defi", "research"],
        )

        assert result == "skill-task"
        call_kwargs = client.publish_task.call_args.kwargs
        assert call_kwargs.get("target_executor") == "agent"
        assert call_kwargs.get("skills_required") == ["defi", "research"]


# ---------------------------------------------------------------------------
# Buyer Flow: Manage Bounties
# ---------------------------------------------------------------------------

class TestManageBounties:
    """Test buyer bounty management: assign + approve."""

    @pytest.mark.asyncio
    async def test_assign_first_applicant(self):
        """Should assign the first applicant when task is published."""
        client = make_client()
        client.get_task = AsyncMock(return_value={"status": "published"})
        client.get_applications = AsyncMock(return_value=[
            {"executor_id": "worker-001", "wallet": "0xWorker1"}
        ])
        client.assign_task = AsyncMock(return_value={"status": "accepted"})

        state = {
            "published": {
                "task-1": {
                    "title": "Test bounty",
                    "category": "test",
                    "status": "published",
                    "bounty": 0.25,
                }
            },
            "applied": {},
        }

        stats = await manage_bounties(client, state)

        assert stats["assigned"] == 1
        assert state["published"]["task-1"]["status"] == "accepted"
        assert state["published"]["task-1"]["executor_id"] == "worker-001"
        assert state["published"]["task-1"]["worker_wallet"] == "0xWorker1"

    @pytest.mark.asyncio
    async def test_approve_submission(self):
        """Should approve pending submissions."""
        client = make_client()
        client.get_task = AsyncMock(return_value={"status": "submitted"})
        client.get_submissions = AsyncMock(return_value=[
            {"id": "sub-001", "status": "pending", "executor_id": "worker-001"}
        ])
        client.approve_submission = AsyncMock(return_value={"status": "approved"})
        client.rate_worker = AsyncMock(return_value={"status": "ok"})

        state = {
            "published": {
                "task-1": {
                    "title": "Submitted task",
                    "category": "test",
                    "status": "published",
                    "bounty": 0.25,
                    "worker_wallet": "0xWorker1",
                }
            },
            "applied": {},
        }

        stats = await manage_bounties(client, state)

        assert stats["approved"] == 1
        assert stats["completed"] == 1
        assert state["published"]["task-1"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_skip_completed_tasks(self):
        """Should skip tasks that are already completed."""
        client = make_client()
        state = {
            "published": {
                "done-task": {
                    "title": "Completed",
                    "status": "completed",
                }
            },
            "applied": {},
        }

        stats = await manage_bounties(client, state)
        assert stats["assigned"] == 0
        assert stats["approved"] == 0

    @pytest.mark.asyncio
    async def test_sync_terminal_states(self):
        """Should sync terminal states from EM API."""
        client = make_client()
        client.get_task = AsyncMock(return_value={"status": "expired"})

        state = {
            "published": {
                "expired-task": {
                    "title": "Old task",
                    "status": "published",
                }
            },
            "applied": {},
        }

        stats = await manage_bounties(client, state)
        assert state["published"]["expired-task"]["status"] == "expired"

    @pytest.mark.asyncio
    async def test_no_applications(self):
        """Published task with no applicants should be skipped."""
        client = make_client()
        client.get_task = AsyncMock(return_value={"status": "published"})
        client.get_applications = AsyncMock(return_value=[])

        state = {
            "published": {
                "no-apps": {
                    "title": "No applications",
                    "status": "published",
                }
            },
            "applied": {},
        }

        stats = await manage_bounties(client, state)
        assert stats["assigned"] == 0

    @pytest.mark.asyncio
    async def test_approve_dry_run(self):
        """Dry run should not call approve API."""
        client = make_client()
        client.get_task = AsyncMock(return_value={"status": "submitted"})
        client.get_submissions = AsyncMock(return_value=[
            {"id": "sub-1", "status": "pending"}
        ])

        state = {
            "published": {
                "task-dr": {"title": "Dry run", "status": "published"}
            },
            "applied": {},
        }

        stats = await manage_bounties(client, state, dry_run=True)
        assert stats["approved"] == 1
        # State should NOT be updated in dry run
        assert state["published"]["task-dr"]["status"] == "published"

    @pytest.mark.asyncio
    async def test_assign_409_conflict(self):
        """409 on assign should be handled gracefully."""
        client = make_client()
        client.get_task = AsyncMock(return_value={"status": "published"})
        client.get_applications = AsyncMock(return_value=[
            {"executor_id": "w1", "wallet": "0xW1"}
        ])
        client.assign_task = AsyncMock(side_effect=Exception("409 Conflict"))

        state = {
            "published": {
                "t1": {"title": "Conflict", "status": "published"}
            },
            "applied": {},
        }

        stats = await manage_bounties(client, state)
        # 409 is NOT counted as error (expected race condition)
        assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# Seller Flow: Discover Bounties
# ---------------------------------------------------------------------------

class TestDiscoverBounties:
    """Test seller bounty discovery."""

    @pytest.mark.asyncio
    async def test_discover_with_keyword_match(self):
        """Should return tasks matching keywords."""
        client = make_client()
        client.browse_tasks = AsyncMock(return_value=[
            make_task(task_id="t1", title="Research DeFi protocols"),
            make_task(task_id="t2", title="Buy groceries"),
            make_task(task_id="t3", title="DeFi analytics report"),
        ])

        results = await discover_bounties(
            client=client,
            keywords=["defi"],
        )

        assert len(results) == 2
        assert results[0]["id"] in ("t1", "t3")

    @pytest.mark.asyncio
    async def test_discover_excludes_own_tasks(self):
        """Should exclude tasks from the agent's own wallet."""
        client = make_client(make_agent(wallet="0xMyWallet"))
        client.browse_tasks = AsyncMock(return_value=[
            make_task(task_id="t1", title="DeFi research", agent_wallet="0xMyWallet"),
            make_task(task_id="t2", title="DeFi analysis", agent_wallet="0xOther"),
        ])

        results = await discover_bounties(
            client=client,
            keywords=["defi"],
            exclude_wallet="0xMyWallet",
        )

        assert len(results) == 1
        assert results[0]["id"] == "t2"

    @pytest.mark.asyncio
    async def test_discover_excludes_applied(self):
        """Should skip tasks already applied to."""
        client = make_client()
        client.browse_tasks = AsyncMock(return_value=[
            make_task(task_id="t1", title="DeFi research"),
            make_task(task_id="t2", title="DeFi analysis"),
        ])

        state = {"applied": {"t1": {"status": "applied"}}}

        results = await discover_bounties(
            client=client,
            keywords=["defi"],
            state=state,
        )

        assert len(results) == 1
        assert results[0]["id"] == "t2"

    @pytest.mark.asyncio
    async def test_discover_sorts_by_bounty(self):
        """Should sort results by bounty (cheapest first)."""
        client = make_client()
        client.browse_tasks = AsyncMock(return_value=[
            make_task(task_id="t1", title="DeFi expensive", bounty=1.00),
            make_task(task_id="t2", title="DeFi cheap", bounty=0.10),
            make_task(task_id="t3", title="DeFi medium", bounty=0.50),
        ])

        results = await discover_bounties(
            client=client,
            keywords=["defi"],
        )

        assert len(results) == 3
        bounties = [t["bounty_usd"] for t in results]
        assert bounties == sorted(bounties)

    @pytest.mark.asyncio
    async def test_discover_empty_marketplace(self):
        """Should handle empty marketplace gracefully."""
        client = make_client()
        client.browse_tasks = AsyncMock(return_value=[])

        results = await discover_bounties(
            client=client,
            keywords=["defi"],
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_discover_api_failure(self):
        """Should return empty list on API failure."""
        client = make_client()
        client.browse_tasks = AsyncMock(side_effect=Exception("Network error"))

        results = await discover_bounties(
            client=client,
            keywords=["defi"],
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_discover_case_insensitive(self):
        """Keyword matching should be case-insensitive."""
        client = make_client()
        client.browse_tasks = AsyncMock(return_value=[
            make_task(task_id="t1", title="DEFI Protocol Research"),
        ])

        results = await discover_bounties(
            client=client,
            keywords=["defi"],
        )

        assert len(results) == 1


# ---------------------------------------------------------------------------
# Seller Flow: Apply to Bounty
# ---------------------------------------------------------------------------

class TestApplyToBounty:
    """Test seller bounty application."""

    @pytest.mark.asyncio
    async def test_apply_success(self):
        """Should apply to task and track state."""
        agent = make_agent(executor_id="exec-123")
        client = make_client(agent)
        client.apply_to_task = AsyncMock(return_value={"status": "applied"})

        task = make_task(task_id="task-apply-1", title="Test apply")
        state = {"applied": {}}

        result = await apply_to_bounty(client, task, state)

        assert result is True
        assert "task-apply-1" in state["applied"]
        assert state["applied"]["task-apply-1"]["status"] == "applied"

    @pytest.mark.asyncio
    async def test_apply_no_executor_id(self):
        """Should reject if agent has no executor_id."""
        agent = make_agent(executor_id=None)
        client = make_client(agent)
        state = {"applied": {}}

        result = await apply_to_bounty(
            client, make_task(), state,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_dry_run(self):
        """Dry run should not call API."""
        client = make_client()
        state = {"applied": {}}

        result = await apply_to_bounty(
            client, make_task(), state, dry_run=True,
        )

        assert result is False
        assert len(state["applied"]) == 0

    @pytest.mark.asyncio
    async def test_apply_409_already_applied(self):
        """409 should track as applied but return False."""
        client = make_client()
        client.apply_to_task = AsyncMock(
            side_effect=Exception("409 Already applied")
        )
        state = {"applied": {}}

        result = await apply_to_bounty(
            client, make_task(task_id="dup-task"), state,
        )

        assert result is False
        assert "dup-task" in state["applied"]  # Tracked to avoid retry

    @pytest.mark.asyncio
    async def test_apply_403_own_task(self):
        """403 on own task should track and return False."""
        client = make_client()
        client.apply_to_task = AsyncMock(
            side_effect=Exception("403 Forbidden")
        )
        state = {"applied": {}}

        result = await apply_to_bounty(
            client, make_task(task_id="own-task"), state,
        )

        assert result is False
        assert "own-task" in state["applied"]
        assert state["applied"]["own-task"]["status"] == "forbidden"

    @pytest.mark.asyncio
    async def test_apply_with_message(self):
        """Should pass custom message to API."""
        client = make_client()
        client.apply_to_task = AsyncMock(return_value={"status": "applied"})
        state = {"applied": {}}

        await apply_to_bounty(
            client, make_task(), state,
            message="Expert in DeFi research",
        )

        call_kwargs = client.apply_to_task.call_args.kwargs
        assert call_kwargs.get("message") == "Expert in DeFi research"


# ---------------------------------------------------------------------------
# Seller Flow: Fulfill Assigned
# ---------------------------------------------------------------------------

class TestFulfillAssigned:
    """Test seller evidence submission flow."""

    @pytest.mark.asyncio
    async def test_fulfill_assigned_task(self):
        """Should submit evidence for assigned tasks."""
        agent = make_agent(executor_id="exec-001")
        client = make_client(agent)
        client.get_task = AsyncMock(return_value={
            "status": "accepted",
            "executor_id": "exec-001",
        })
        client.submit_evidence = AsyncMock(return_value={"status": "submitted"})

        state = {
            "applied": {
                "t1": {"title": "Test", "status": "applied"},
            }
        }

        stats = await fulfill_assigned(client, state)

        assert stats["submitted"] == 1
        assert state["applied"]["t1"]["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_fulfill_skip_not_our_assignment(self):
        """Should skip tasks assigned to another executor."""
        agent = make_agent(executor_id="exec-001")
        client = make_client(agent)
        client.get_task = AsyncMock(return_value={
            "status": "accepted",
            "executor_id": "exec-OTHER",
        })

        state = {
            "applied": {
                "t1": {"title": "Not ours", "status": "applied"},
            }
        }

        stats = await fulfill_assigned(client, state)
        assert stats["submitted"] == 0

    @pytest.mark.asyncio
    async def test_fulfill_with_evidence_fn(self):
        """Should use evidence_fn when provided."""
        agent = make_agent(executor_id="exec-001")
        client = make_client(agent)
        client.get_task = AsyncMock(return_value={
            "status": "accepted",
            "executor_id": "exec-001",
        })
        client.submit_evidence = AsyncMock(return_value={"status": "submitted"})

        def custom_evidence(task_id, info):
            return {"json_response": {"custom": True, "task": task_id}}

        state = {"applied": {"t1": {"title": "Custom", "status": "applied"}}}

        stats = await fulfill_assigned(
            client, state, evidence_fn=custom_evidence,
        )

        assert stats["submitted"] == 1
        # Verify custom evidence was passed
        call_kwargs = client.submit_evidence.call_args.kwargs
        assert call_kwargs["evidence"]["json_response"]["custom"] is True

    @pytest.mark.asyncio
    async def test_fulfill_detects_completion_and_rates(self):
        """Should detect completed tasks and rate the agent."""
        agent = make_agent(executor_id="exec-001")
        client = make_client(agent)
        client.get_task = AsyncMock(return_value={
            "status": "completed",
            "agent_id": "2106",
        })
        client.rate_agent = AsyncMock(return_value={"status": "ok"})

        state = {
            "applied": {
                "t1": {"title": "Completed", "status": "submitted"},
            }
        }

        stats = await fulfill_assigned(client, state)

        assert stats["completed"] == 1
        assert state["applied"]["t1"]["status"] == "completed"
        client.rate_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fulfill_sync_cancelled(self):
        """Should sync cancelled status."""
        agent = make_agent(executor_id="exec-001")
        client = make_client(agent)
        client.get_task = AsyncMock(return_value={"status": "cancelled"})

        state = {
            "applied": {
                "t1": {"title": "Cancelled", "status": "applied"},
            }
        }

        await fulfill_assigned(client, state)
        assert state["applied"]["t1"]["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_fulfill_dry_run(self):
        """Dry run should not submit evidence."""
        agent = make_agent(executor_id="exec-001")
        client = make_client(agent)
        client.get_task = AsyncMock(return_value={
            "status": "accepted",
            "executor_id": "exec-001",
        })

        state = {"applied": {"t1": {"title": "Dry", "status": "applied"}}}

        stats = await fulfill_assigned(client, state, dry_run=True)
        assert stats["submitted"] == 1
        # But status is NOT updated in dry run

    @pytest.mark.asyncio
    async def test_fulfill_skip_already_submitted(self):
        """Should not resubmit already submitted tasks."""
        agent = make_agent(executor_id="exec-001")
        client = make_client(agent)
        client.get_task = AsyncMock(return_value={"status": "submitted"})

        state = {
            "applied": {
                "t1": {"title": "Already submitted", "status": "submitted"},
            }
        }

        stats = await fulfill_assigned(client, state)
        assert stats["submitted"] == 0


# ---------------------------------------------------------------------------
# Offering Deduplication
# ---------------------------------------------------------------------------

class TestOfferingDeduplication:
    """Test deduplicated offering publication."""

    @pytest.mark.asyncio
    async def test_publish_new_offering(self):
        """Should publish when no duplicate exists."""
        agent = make_agent()
        client = make_client(agent)
        client.list_tasks = AsyncMock(return_value=[])
        client.publish_task = AsyncMock(return_value={"task": {"id": "new-off-1"}})

        result = await publish_offering_deduped(
            client=client,
            title="Data offering",
            instructions="Provide data",
            bounty_usd=0.10,
            title_prefix="[KK Data]",
        )

        assert result is not None
        assert result["task"]["id"] == "new-off-1"

    @pytest.mark.asyncio
    async def test_skip_existing_offering(self):
        """Should skip if active offering with same prefix exists."""
        agent = make_agent()
        client = make_client(agent)
        client.list_tasks = AsyncMock(return_value=[
            {"id": "existing-1", "title": "[KK Data] Old offering", "status": "published"}
        ])

        result = await publish_offering_deduped(
            client=client,
            title="Data offering v2",
            instructions="...",
            bounty_usd=0.10,
            title_prefix="[KK Data]",
        )

        assert result is None  # Deduplicated

    @pytest.mark.asyncio
    async def test_offering_budget_check(self):
        """Should check budget before publishing."""
        agent = make_agent(budget=0.05)
        agent.daily_spent_usd = 0.04
        client = make_client(agent)
        client.list_tasks = AsyncMock(return_value=[])

        result = await publish_offering_deduped(
            client=client,
            title="Too expensive",
            instructions="...",
            bounty_usd=0.10,
        )

        assert result is None


# ---------------------------------------------------------------------------
# Executor Wallet Resolution
# ---------------------------------------------------------------------------

class TestExecutorWalletResolution:
    """Test executor ID to wallet address resolution."""

    def test_resolve_unknown_executor(self):
        """Unknown executor should return empty string."""
        # Clear the cached map for this test
        import services.escrow_flow as ef
        ef._EXECUTOR_WALLET_MAP = {}
        result = resolve_executor_wallet("unknown-exec-id")
        assert result == ""

    def test_resolve_with_loaded_map(self):
        """Should return wallet when map is populated."""
        import services.escrow_flow as ef
        ef._EXECUTOR_WALLET_MAP = {"exec-001": "0xWallet001"}
        result = resolve_executor_wallet("exec-001")
        assert result == "0xWallet001"
        # Cleanup
        ef._EXECUTOR_WALLET_MAP = None


# ---------------------------------------------------------------------------
# Full Flow Integration
# ---------------------------------------------------------------------------

class TestFullBuyerSellerFlow:
    """Test the complete buyer → seller → completion flow."""

    @pytest.mark.asyncio
    async def test_buyer_seller_roundtrip(self):
        """Simulate a complete buyer-seller cycle."""
        # BUYER: publish bounty
        buyer_agent = make_agent(name="buyer", wallet="0xBuyer")
        buyer_client = make_client(buyer_agent)
        buyer_client.publish_task = AsyncMock(
            return_value={"task": {"id": "roundtrip-1"}}
        )
        buyer_state = {"published": {}, "applied": {}}

        task_id = await publish_bounty(
            buyer_client, "Research task", "Do research", 0.25,
            "research", buyer_state,
        )
        assert task_id == "roundtrip-1"

        # SELLER: discover bounty
        seller_agent = make_agent(
            name="seller", wallet="0xSeller", executor_id="seller-exec"
        )
        seller_client = make_client(seller_agent)
        seller_client.browse_tasks = AsyncMock(return_value=[
            make_task(
                task_id="roundtrip-1",
                title="Research task",
                agent_wallet="0xBuyer",
            )
        ])

        bounties = await discover_bounties(
            seller_client, keywords=["research"],
            exclude_wallet="0xSeller",
        )
        assert len(bounties) == 1

        # SELLER: apply
        seller_client.apply_to_task = AsyncMock(return_value={"status": "applied"})
        seller_state = {"applied": {}}
        applied = await apply_to_bounty(
            seller_client, bounties[0], seller_state,
        )
        assert applied is True

        # BUYER: manage (assign applicant)
        buyer_client.get_task = AsyncMock(return_value={"status": "published"})
        buyer_client.get_applications = AsyncMock(return_value=[
            {"executor_id": "seller-exec", "wallet": "0xSeller"}
        ])
        buyer_client.assign_task = AsyncMock(return_value={"status": "accepted"})

        stats = await manage_bounties(buyer_client, buyer_state)
        assert stats["assigned"] == 1

        # SELLER: fulfill
        seller_client.get_task = AsyncMock(return_value={
            "status": "accepted",
            "executor_id": "seller-exec",
        })
        seller_client.submit_evidence = AsyncMock(
            return_value={"status": "submitted"}
        )

        stats = await fulfill_assigned(seller_client, seller_state)
        assert stats["submitted"] == 1

        # BUYER: approve submission
        buyer_client.get_task = AsyncMock(return_value={"status": "submitted"})
        buyer_client.get_submissions = AsyncMock(return_value=[
            {"id": "sub-roundtrip", "status": "pending",
             "executor_id": "seller-exec", "worker_wallet": "0xSeller"}
        ])
        buyer_client.approve_submission = AsyncMock(
            return_value={"status": "approved"}
        )
        buyer_client.rate_worker = AsyncMock(return_value={"status": "ok"})

        stats = await manage_bounties(buyer_client, buyer_state)
        assert stats["approved"] == 1
        assert stats["completed"] == 1

        # Final state check
        assert buyer_state["published"]["roundtrip-1"]["status"] == "completed"
        assert seller_state["applied"]["roundtrip-1"]["status"] == "submitted"
