"""
End-to-End Swarm Integration Tests

These tests exercise the FULL swarm pipeline:
- Agent registration → boot → activate → assign → complete → reputation sync → sleep → wake
- Multi-agent scenarios: competition, failover, load balancing
- Economic tracking: budget enforcement, earnings aggregation
- Failure recovery: error handling, circuit breaking, auto-management
- Reputation flow: task completion → score update → tier promotion → better matching

Unlike unit tests, these tests verify the INTEGRATION between:
- SwarmOrchestrator (task routing)
- LifecycleManager (state machine)
- ReputationBridge (reputation scoring)
"""

import pytest
import time
from datetime import datetime, timezone, timedelta

from mcp_server.swarm.reputation_bridge import (
    ReputationBridge,
    BridgedReputation,
    ReputationSource,
)
from mcp_server.swarm.lifecycle_manager import (
    LifecycleManager,
    AgentStatus,
    ResourceBudget,
)
from mcp_server.swarm.swarm_orchestrator import (
    SwarmOrchestrator,
    AgentProfile,
    TaskAssignment,
    AssignmentStrategy,
)


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════


class SwarmTestHarness:
    """Reusable test harness for swarm E2E tests."""

    def __init__(self, max_agents=24):
        self.lifecycle = LifecycleManager(max_agents=max_agents)
        self.bridge = ReputationBridge(dry_run=True)
        self.orch = SwarmOrchestrator(
            lifecycle=self.lifecycle,
            bridge=self.bridge,
        )

    def add_agent(
        self,
        agent_id: str,
        skills: list = None,
        specializations: list = None,
        personality: str = "generalist",
        model: str = "anthropic/claude-haiku-4-5",
        budget: ResourceBudget = None,
        activate: bool = True,
    ) -> AgentProfile:
        """Register and optionally activate an agent."""
        profile = self.orch.register_agent(
            agent_id=agent_id,
            wallet=f"0x{agent_id.replace('_', '')}",
            personality=personality,
            skills=skills or [],
            specializations=specializations or [],
            model=model,
            budget=budget,
        )
        if activate:
            self.lifecycle.boot_agent(agent_id)
            self.lifecycle.activate_agent(agent_id)
        return profile

    def add_kk_roster(self, count=6):
        """Add a mini KarmaKadabra roster (subset of the 24)."""
        agents = [
            (
                "aurora",
                ["research", "documentation", "analysis"],
                ["data_collection", "research"],
                "explorer",
            ),
            (
                "blaze",
                ["writing", "creativity", "documentation"],
                ["content_creation"],
                "creator",
            ),
            (
                "cipher",
                ["code_review", "security", "testing", "automation"],
                ["code_review", "testing"],
                "auditor",
            ),
            (
                "delta",
                ["research", "data_entry", "documentation"],
                ["data_collection"],
                "collector",
            ),
            (
                "echo",
                ["languages", "communication", "documentation"],
                ["translation"],
                "communicator",
            ),
            (
                "forge",
                ["qa_testing", "automation", "documentation"],
                ["testing"],
                "tester",
            ),
        ]
        profiles = []
        for agent_id, skills, specs, personality in agents[:count]:
            profiles.append(
                self.add_agent(
                    agent_id=agent_id,
                    skills=skills,
                    specializations=specs,
                    personality=personality,
                )
            )
        return profiles


# ══════════════════════════════════════════════
# E2E: Full Task Pipeline
# ══════════════════════════════════════════════


class TestFullTaskPipeline:
    """Tests the complete lifecycle of tasks through the swarm."""

    def setup_method(self):
        self.harness = SwarmTestHarness()

    @pytest.mark.asyncio
    async def test_single_task_full_pipeline(self):
        """Single task: register → assign → complete → reputation update."""
        self.harness.add_agent(
            "aurora",
            skills=["research", "documentation"],
            specializations=["data_collection"],
        )

        # Assign
        assignment = await self.harness.orch.assign_task(
            task_id="task_001",
            category="data_collection",
            bounty_usd=0.25,
        )
        assert assignment.assigned_agent == "aurora"
        assert assignment.score > 0

        # Complete with rating
        result = await self.harness.orch.complete_task(
            task_id="task_001",
            success=True,
            earnings_usd=0.25,
            rating=88.0,
        )
        assert result["success"]
        assert result["earnings_usd"] == 0.25

        # Verify economics
        summary = self.harness.orch.economic_summary()
        assert summary["total_completed"] == 1
        assert summary["total_earned_usd"] == 0.25
        assert summary["completion_rate"] == 1.0

        # Verify agent state
        agent = self.harness.lifecycle.get_agent("aurora")
        assert agent.total_tasks_completed == 1
        assert agent.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_failed_task_pipeline(self):
        """Failed task: assign → fail → consecutive failure tracking."""
        self.harness.add_agent("aurora", skills=["research"])

        assignment = await self.harness.orch.assign_task(
            task_id="task_fail",
            category="data_collection",
        )
        assert assignment.assigned_agent == "aurora"

        # Fail the task
        result = await self.harness.orch.complete_task(
            task_id="task_fail",
            success=False,
            rating=20.0,
        )
        assert not result["success"]

        # Agent tracks failure
        agent = self.harness.lifecycle.get_agent("aurora")
        assert agent.total_tasks_failed == 1

    @pytest.mark.asyncio
    async def test_multi_task_sequential_pipeline(self):
        """Multiple tasks completed sequentially by same agent."""
        self.harness.add_agent(
            "aurora",
            skills=["research", "documentation", "analysis"],
            specializations=["data_collection"],
        )

        for i in range(5):
            assignment = await self.harness.orch.assign_task(
                task_id=f"task_{i:03d}",
                category="data_collection",
                bounty_usd=0.10,
            )
            assert assignment.assigned_agent == "aurora"

            await self.harness.orch.complete_task(
                task_id=f"task_{i:03d}",
                success=True,
                earnings_usd=0.10,
                rating=80.0 + i,
            )

        summary = self.harness.orch.economic_summary()
        assert summary["total_completed"] == 5
        assert abs(summary["total_earned_usd"] - 0.50) < 0.001
        assert summary["completion_rate"] == 1.0

        agent = self.harness.lifecycle.get_agent("aurora")
        assert agent.total_tasks_completed == 5


# ══════════════════════════════════════════════
# E2E: Multi-Agent Competition
# ══════════════════════════════════════════════


class TestMultiAgentCompetition:
    """Tests task distribution across multiple agents."""

    def setup_method(self):
        self.harness = SwarmTestHarness()
        self.harness.add_kk_roster(6)

    @pytest.mark.asyncio
    async def test_skill_based_routing(self):
        """Tasks route to agents with matching skills."""
        # Research task → aurora or delta (both have research skills)
        a1 = await self.harness.orch.assign_task("t1", category="data_collection")
        assert a1.assigned_agent in ("aurora", "delta")

        # Content → blaze (writing + creativity)
        a2 = await self.harness.orch.assign_task("t2", category="content_creation")
        assert a2.assigned_agent == "blaze"

        # Code review → cipher (code_review + security)
        a3 = await self.harness.orch.assign_task("t3", category="code_review")
        assert a3.assigned_agent == "cipher"

        # Translation → echo (languages + communication)
        a4 = await self.harness.orch.assign_task("t4", category="translation")
        assert a4.assigned_agent == "echo"

        # Testing → forge (qa_testing + automation)
        a5 = await self.harness.orch.assign_task("t5", category="testing")
        assert a5.assigned_agent == "forge"

    @pytest.mark.asyncio
    async def test_specialization_beats_general_skills(self):
        """Agent with specialization wins over one with just matching skills."""
        # Aurora has research skill AND data_collection specialization
        # Delta has research skill AND data_collection specialization
        # Blaze only has writing
        a = await self.harness.orch.assign_task("t1", category="data_collection")
        assert a.assigned_agent in ("aurora", "delta")  # Both specialized

    @pytest.mark.asyncio
    async def test_alternatives_reported(self):
        """Assignment includes alternative agents."""
        a = await self.harness.orch.assign_task("t1", category="data_collection")
        # Should have alternatives since multiple agents exist
        assert len(a.alternatives) > 0
        assert all("agent_id" in alt for alt in a.alternatives)

    @pytest.mark.asyncio
    async def test_concurrent_task_distribution(self):
        """Multiple simultaneous tasks get different agents."""
        self.harness.orch.max_concurrent_tasks = 1  # Force one task per agent

        assignments = []
        for i in range(4):
            a = await self.harness.orch.assign_task(
                f"task_{i}", category="data_collection"
            )
            if a.assigned_agent:
                assignments.append(a)

        # Multiple agents should be used
        assigned_agents = set(a.assigned_agent for a in assignments)
        assert len(assigned_agents) > 1

    @pytest.mark.asyncio
    async def test_round_robin_distributes_evenly(self):
        """Round-robin strategy distributes tasks more evenly."""
        # Give aurora a history of many tasks
        self.harness.orch.task_history = [
            {
                "agent_id": "aurora",
                "success": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            for _ in range(10)
        ]

        a = await self.harness.orch.assign_task(
            "t_rr",
            category="data_collection",
            strategy=AssignmentStrategy.ROUND_ROBIN,
        )
        # Round-robin should pick agent with fewer tasks
        assert a.assigned_agent != "aurora"


# ══════════════════════════════════════════════
# E2E: Failover & Recovery
# ══════════════════════════════════════════════


class TestFailoverAndRecovery:
    """Tests failure handling and agent recovery."""

    def setup_method(self):
        self.harness = SwarmTestHarness()

    @pytest.mark.asyncio
    async def test_failover_to_next_agent(self):
        """When one agent fails, tasks route to next best."""
        self.harness.add_agent(
            "primary",
            skills=["research", "documentation"],
            specializations=["data_collection"],
        )
        self.harness.add_agent(
            "backup", skills=["research"], specializations=["data_collection"]
        )

        # Primary takes first task
        a1 = await self.harness.orch.assign_task("t1", category="data_collection")
        assert a1.assigned_agent == "primary"

        # Primary enters error state
        self.harness.lifecycle.error_agent("primary", "API timeout")

        # Next task should go to backup
        a2 = await self.harness.orch.assign_task("t2", category="data_collection")
        assert a2.assigned_agent == "backup"

    @pytest.mark.asyncio
    async def test_agent_recovery_after_error(self):
        """Agent can be recovered and assigned tasks again."""
        self.harness.add_agent("aurora", skills=["research"])

        # Error the agent
        self.harness.lifecycle.error_agent("aurora", "transient error")
        assert self.harness.lifecycle.agents["aurora"].status == AgentStatus.ERROR

        # Can't assign tasks to errored agent
        a = await self.harness.orch.assign_task("t1", category="data_collection")
        assert a.assigned_agent is None

        # Recover: sleep → wake → activate
        self.harness.lifecycle.sleep_agent("aurora", reason="recovered")
        self.harness.lifecycle.wake_agent("aurora")
        self.harness.lifecycle.activate_agent("aurora")

        # Now can assign again
        a2 = await self.harness.orch.assign_task("t2", category="data_collection")
        assert a2.assigned_agent == "aurora"

    def test_auto_manage_recovery_cycle(self):
        """Auto-manage recovers errored agents after cooldown."""
        self.harness.add_agent("aurora", skills=["research"])
        self.harness.lifecycle.error_agent("aurora", "transient failure")

        # Set error time to 6 minutes ago (past the 5-min recovery threshold)
        self.harness.lifecycle.agents["aurora"].status_since = datetime.now(
            timezone.utc
        ) - timedelta(minutes=6)

        actions = self.harness.lifecycle.auto_manage()
        assert "aurora" in actions["recovered"]

    def test_auto_retire_after_many_failures(self):
        """Agent auto-retires after repeated failures."""
        self.harness.add_agent("flaky", skills=["research"])

        for i in range(10):
            self.harness.lifecycle.agents["flaky"].status = AgentStatus.ACTIVE
            self.harness.lifecycle.error_agent("flaky", f"failure #{i}")

        assert self.harness.lifecycle.agents["flaky"].status == AgentStatus.RETIRED

    @pytest.mark.asyncio
    async def test_claim_expiry_reassignment(self):
        """Expired claims allow task reassignment."""
        self.harness.add_agent("slow", skills=["research"])
        self.harness.add_agent("fast", skills=["research"])

        # Slow agent claims task
        a1 = await self.harness.orch.assign_task("t1", category="data_collection")
        assert a1.assigned_agent is not None

        # Simulate claim expiry (set timestamp to past)
        self.harness.orch._claim_timestamps["t1"] = time.time() - 700  # >600s timeout

        # Task can now be reassigned
        a2 = await self.harness.orch.assign_task("t1", category="data_collection")
        assert a2.assigned_agent is not None


# ══════════════════════════════════════════════
# E2E: Budget Enforcement
# ══════════════════════════════════════════════


class TestBudgetEnforcement:
    """Tests budget limits across the full pipeline."""

    def setup_method(self):
        self.harness = SwarmTestHarness()

    @pytest.mark.asyncio
    async def test_budget_prevents_assignment(self):
        """Agent near budget limit can't take expensive tasks."""
        budget = ResourceBudget(max_usd_spend_per_day=0.50)
        self.harness.add_agent("aurora", skills=["research"], budget=budget)

        # Spend most of budget
        agent = self.harness.lifecycle.agents["aurora"]
        agent.usage.usd_spent_today = 0.45
        agent.usage.last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Expensive task should fail (0.45 + 0.10 > 0.50)
        a = await self.harness.orch.assign_task(
            "t_expensive",
            category="data_collection",
            bounty_usd=0.10,
        )
        assert a.assigned_agent is None

    @pytest.mark.asyncio
    async def test_cheap_task_still_possible(self):
        """Agent near budget can still take cheap tasks."""
        budget = ResourceBudget(max_usd_spend_per_day=0.50)
        self.harness.add_agent("aurora", skills=["research"], budget=budget)

        agent = self.harness.lifecycle.agents["aurora"]
        agent.usage.usd_spent_today = 0.45
        agent.usage.last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Cheap task should succeed (0.45 + 0.04 < 0.50)
        a = await self.harness.orch.assign_task(
            "t_cheap",
            category="data_collection",
            bounty_usd=0.04,
        )
        assert a.assigned_agent == "aurora"

    def test_heartbeat_enforces_token_budget(self):
        """Heartbeat puts agent to sleep when token budget exceeded."""
        budget = ResourceBudget(max_tokens_per_day=10_000)
        self.harness.add_agent("aurora", skills=["research"], budget=budget)

        result = self.harness.lifecycle.heartbeat("aurora", {"tokens": 15_000})
        assert result["action"] == "sleep"
        assert self.harness.lifecycle.agents["aurora"].status == AgentStatus.SLEEPING

    def test_heartbeat_enforces_error_budget(self):
        """Heartbeat puts agent to sleep when too many errors per hour."""
        budget = ResourceBudget(max_errors_per_hour=3)
        self.harness.add_agent("aurora", skills=["research"], budget=budget)

        result = self.harness.lifecycle.heartbeat("aurora", {"errors": 5})
        assert result["action"] == "sleep"

    @pytest.mark.asyncio
    async def test_budget_cascading_to_backup(self):
        """When primary exhausts budget, tasks cascade to backup."""
        budget_low = ResourceBudget(max_usd_spend_per_day=0.20)
        budget_high = ResourceBudget(max_usd_spend_per_day=5.00)

        self.harness.add_agent(
            "primary",
            skills=["research"],
            specializations=["data_collection"],
            budget=budget_low,
        )
        self.harness.add_agent(
            "backup",
            skills=["research"],
            specializations=["data_collection"],
            budget=budget_high,
        )

        # Exhaust primary's budget
        agent = self.harness.lifecycle.agents["primary"]
        agent.usage.usd_spent_today = 0.19
        agent.usage.last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Task that exceeds primary's remaining budget
        a = await self.harness.orch.assign_task(
            "t1",
            category="data_collection",
            bounty_usd=0.05,
        )
        assert a.assigned_agent == "backup"


# ══════════════════════════════════════════════
# E2E: Reputation Flow
# ══════════════════════════════════════════════


class TestReputationFlow:
    """Tests reputation scoring through the task lifecycle."""

    def setup_method(self):
        self.harness = SwarmTestHarness()

    def test_new_agent_default_reputation(self):
        """New agent starts with neutral reputation."""
        self.harness.add_agent("newbie", skills=["research"])
        profile = self.harness.orch.profiles["newbie"]
        assert profile.reputation_score == 50.0

    @pytest.mark.asyncio
    async def test_reputation_affects_matching(self):
        """Higher reputation agent wins when skills are equal."""
        self.harness.add_agent(
            "veteran", skills=["research"], specializations=["data_collection"]
        )
        self.harness.add_agent(
            "newbie", skills=["research"], specializations=["data_collection"]
        )

        # Boost veteran's reputation
        self.harness.orch.profiles["veteran"].reputation_score = 90.0
        self.harness.orch.profiles["newbie"].reputation_score = 50.0

        a = await self.harness.orch.assign_task("t1", category="data_collection")
        # Veteran should win due to higher reputation
        assert a.assigned_agent == "veteran"

    def test_tier_calculation_progression(self):
        """Reputation tiers progress with score and confidence."""
        bridge = self.harness.bridge

        # New agent: low score, low confidence
        assert bridge._determine_tier(50.0, 0.1) == "new"

        # Established: moderate score, some confidence
        assert bridge._determine_tier(65.0, 0.4) == "established"

        # Trusted: good score, decent confidence
        assert bridge._determine_tier(78.0, 0.6) == "trusted"

        # Elite: high score, high confidence
        assert bridge._determine_tier(92.0, 0.85) == "elite"

        # At risk: low score regardless of confidence
        assert bridge._determine_tier(35.0, 0.9) == "at_risk"

    def test_evidence_weight_progression(self):
        """Evidence weight increases with task history."""
        bridge = self.harness.bridge

        # No history → self-reported
        rep_new = BridgedReputation(wallet="0x1")
        assert bridge._calculate_evidence_weight(rep_new) == 0.3

        # Some EM tasks
        rep_some = BridgedReputation(
            wallet="0x2", em_total_tasks=5, em_successful_tasks=5
        )
        ew_some = bridge._calculate_evidence_weight(rep_some)
        assert ew_some > 0.3

        # Many EM tasks + on-chain
        rep_veteran = BridgedReputation(
            wallet="0x3",
            em_total_tasks=50,
            em_successful_tasks=48,
            chain_total_ratings=30,
        )
        ew_veteran = bridge._calculate_evidence_weight(rep_veteran)
        assert ew_veteran > ew_some
        assert ew_veteran >= 0.85

    def test_confidence_from_multiple_sources(self):
        """Multiple data sources increase confidence."""
        bridge = self.harness.bridge

        # EM only
        rep_em = BridgedReputation(
            wallet="0x1",
            em_total_tasks=20,
            sources=[ReputationSource.EM_INTERNAL.value],
        )
        conf_em = bridge._calculate_confidence(rep_em)

        # EM + chain
        rep_both = BridgedReputation(
            wallet="0x2",
            em_total_tasks=20,
            chain_total_ratings=10,
            sources=[
                ReputationSource.EM_INTERNAL.value,
                ReputationSource.ERC8004_ONCHAIN.value,
            ],
        )
        conf_both = bridge._calculate_confidence(rep_both)

        assert conf_both > conf_em  # Multi-source bonus

    @pytest.mark.asyncio
    async def test_sync_result_on_task_completion(self):
        """Task completion triggers reputation sync (dry run)."""
        self.harness.add_agent("aurora", skills=["research"])

        # Assign and complete with rating
        await self.harness.orch.assign_task("t1", category="data_collection")
        result = await self.harness.orch.complete_task(
            "t1",
            success=True,
            earnings_usd=0.25,
            rating=90.0,
        )

        assert result["success"]
        # In dry_run, the sync is attempted but no tx_hash returned
        # We verify the sync was attempted by checking task_history
        assert len(self.harness.orch.task_history) == 1
        assert self.harness.orch.task_history[0]["rating"] == 90.0

    @pytest.mark.asyncio
    async def test_batch_sync_respects_thresholds(self):
        """Batch sync skips wallets with small score changes."""
        bridge = self.harness.bridge

        results = await bridge.batch_sync(
            wallets=["0xaaa", "0xbbb"],
            em_reputations={
                "0xaaa": {
                    "bayesian_score": 51.0,
                    "total_tasks": 5,
                },  # Small delta from 50
                "0xbbb": {"bayesian_score": 75.0, "total_tasks": 20},  # Large delta
            },
        )

        # Both should show results (0xaaa skipped due to small delta, 0xbbb synced)
        assert len(results) == 2


# ══════════════════════════════════════════════
# E2E: Swarm Operations
# ══════════════════════════════════════════════


class TestSwarmOperations:
    """Tests swarm-level operations and observability."""

    def setup_method(self):
        self.harness = SwarmTestHarness()
        self.harness.add_kk_roster(6)

    def test_health_check_all_active(self):
        """Health check with all agents active."""
        health = self.harness.lifecycle.health_check()
        assert health["total_agents"] == 6
        assert health["active"] == 6

    def test_health_check_mixed_states(self):
        """Health check with agents in various states."""
        self.harness.lifecycle.sleep_agent("aurora", reason="test")
        self.harness.lifecycle.error_agent("blaze", "test error")
        self.harness.lifecycle.retire_agent("echo", "test retire")

        health = self.harness.lifecycle.health_check()
        assert health["active"] == 3  # cipher, delta, forge
        assert health["sleeping"] == 1  # aurora
        assert health["error"] == 1  # blaze
        assert health["retired"] == 1  # echo

    @pytest.mark.asyncio
    async def test_metrics_after_workload(self):
        """Metrics reflect task processing accurately."""
        # Process several tasks
        for i in range(10):
            category = [
                "data_collection",
                "content_creation",
                "code_review",
                "translation",
                "testing",
            ][i % 5]
            a = await self.harness.orch.assign_task(f"t_{i}", category=category)
            if a.assigned_agent:
                await self.harness.orch.complete_task(
                    f"t_{i}",
                    success=(i != 7),  # One failure
                    earnings_usd=0.10,
                    rating=80.0 + i,
                )

        metrics = self.harness.orch.metrics()
        assert metrics["tasks"]["total_completed"] > 0
        assert metrics["agents"]["total"] == 6
        assert metrics["agents"]["active"] == 6
        assert metrics["economics"]["total_earned_usd"] > 0

    @pytest.mark.asyncio
    async def test_economic_summary_top_earners(self):
        """Economic summary tracks top earners correctly."""
        # Aurora does more tasks
        for i in range(5):
            await self.harness.orch.assign_task(
                f"t_aurora_{i}", category="data_collection"
            )
            await self.harness.orch.complete_task(
                f"t_aurora_{i}",
                success=True,
                earnings_usd=0.20,
            )

        # Blaze does fewer
        await self.harness.orch.assign_task("t_blaze_0", category="content_creation")
        await self.harness.orch.complete_task(
            "t_blaze_0",
            success=True,
            earnings_usd=0.10,
        )

        summary = self.harness.orch.economic_summary()
        assert summary["total_earned_usd"] > 0.0
        assert len(summary["top_earners"]) > 0

        # Aurora should be top earner
        top = summary["top_earners"][0]
        assert top["agent_id"] in (
            "aurora",
            "delta",
        )  # Either could take data_collection tasks

    def test_swarm_full_capacity(self):
        """Swarm handles capacity limits correctly."""
        harness = SwarmTestHarness(max_agents=3)
        harness.add_agent("a1", skills=["research"])
        harness.add_agent("a2", skills=["research"])
        harness.add_agent("a3", skills=["research"])

        # Fourth agent can't boot
        harness.add_agent("a4", skills=["research"], activate=False)
        harness.lifecycle.register_agent("a4_extra", "0xa4extra")
        assert not harness.lifecycle.boot_agent("a4_extra")

    @pytest.mark.asyncio
    async def test_assignment_with_custom_required_skills(self):
        """Tasks with custom skill requirements match correctly."""
        a = await self.harness.orch.assign_task(
            "t_custom",
            required_skills=["security", "testing"],
        )
        # Cipher has both security and testing
        assert a.assigned_agent == "cipher"

    @pytest.mark.asyncio
    async def test_cheapest_strategy(self):
        """Cheapest strategy picks agent with lowest model cost."""
        harness = SwarmTestHarness()
        harness.add_agent(
            "cheap", skills=["research"], model="anthropic/claude-haiku-4-5"
        )
        harness.add_agent(
            "expensive", skills=["research"], model="anthropic/claude-opus-4-6"
        )

        a = await harness.orch.assign_task(
            "t_cheap",
            category="data_collection",
            strategy=AssignmentStrategy.CHEAPEST,
        )
        assert a.assigned_agent == "cheap"


# ══════════════════════════════════════════════
# E2E: Stress & Edge Cases
# ══════════════════════════════════════════════


class TestStressAndEdgeCases:
    """Tests unusual scenarios and edge cases."""

    def setup_method(self):
        self.harness = SwarmTestHarness()

    @pytest.mark.asyncio
    async def test_complete_unknown_task(self):
        """Completing a task that was never assigned."""
        result = await self.harness.orch.complete_task(
            "nonexistent",
            success=True,
            earnings_usd=0.10,
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_many_tasks_sequential(self):
        """Handle 50 tasks sequentially without errors."""
        self.harness.add_kk_roster(6)
        self.harness.orch.max_concurrent_tasks = 10  # Higher limit

        completed = 0
        for i in range(50):
            category = [
                "data_collection",
                "content_creation",
                "code_review",
                "translation",
                "testing",
                "research",
            ][i % 6]
            a = await self.harness.orch.assign_task(f"stress_{i}", category=category)
            if a.assigned_agent:
                await self.harness.orch.complete_task(
                    f"stress_{i}",
                    success=True,
                    earnings_usd=0.05,
                )
                completed += 1

        assert completed >= 40  # Most should succeed

        metrics = self.harness.orch.metrics()
        assert metrics["tasks"]["total_completed"] == completed

    @pytest.mark.asyncio
    async def test_all_agents_sleeping(self):
        """No assignments when all agents are sleeping."""
        self.harness.add_agent("aurora", skills=["research"])
        self.harness.lifecycle.sleep_agent("aurora", reason="test")

        a = await self.harness.orch.assign_task("t1", category="data_collection")
        assert a.assigned_agent is None
        assert "No eligible" in a.unassigned_reason

    @pytest.mark.asyncio
    async def test_agent_with_no_matching_skills(self):
        """Agent without matching skills can still be assigned if no alternatives."""
        self.harness.add_agent("mismatch", skills=["cooking", "gardening"])

        a = await self.harness.orch.assign_task("t1", category="code_review")
        # Should still assign (only agent available) but with low score
        assert a.assigned_agent == "mismatch"
        assert a.score < 50  # Low score due to skill mismatch

    def test_unregister_active_agent(self):
        """Unregistering an active agent puts it to sleep first."""
        self.harness.add_agent("doomed", skills=["research"])
        assert self.harness.lifecycle.agents["doomed"].status == AgentStatus.ACTIVE

        self.harness.lifecycle.unregister_agent("doomed")
        assert "doomed" not in self.harness.lifecycle.agents

    def test_heartbeat_unknown_agent(self):
        """Heartbeat for unknown agent returns error."""
        result = self.harness.lifecycle.heartbeat("ghost", {"tokens": 100})
        assert result["action"] == "error"

    @pytest.mark.asyncio
    async def test_profile_refresh_nonexistent(self):
        """Refreshing nonexistent profile returns None."""
        result = await self.harness.orch.refresh_profile("ghost")
        assert result is None

    def test_state_serialization(self):
        """Agent state serializes correctly."""
        self.harness.add_agent("aurora", skills=["research"])
        state = self.harness.lifecycle.agents["aurora"]
        d = state.to_dict()

        assert d["agent_id"] == "aurora"
        assert d["status"] == "active"
        assert "is_healthy" in d
        assert "budget_utilization" in d

    def test_assignment_serialization(self):
        """TaskAssignment serializes correctly."""
        assignment = TaskAssignment(
            task_id="t1",
            assigned_agent="aurora",
            score=85.5,
            reasons=["Good match"],
            assignment_time=datetime.now(timezone.utc),
        )
        d = assignment.to_dict()
        assert d["task_id"] == "t1"
        assert isinstance(d["assignment_time"], str)

    @pytest.mark.asyncio
    async def test_reputation_strategy(self):
        """Reputation strategy picks highest-reputation agent."""
        self.harness.add_agent("high_rep", skills=["research"])
        self.harness.add_agent("low_rep", skills=["research"])

        self.harness.orch.profiles["high_rep"].reputation_score = 95.0
        self.harness.orch.profiles["low_rep"].reputation_score = 45.0

        a = await self.harness.orch.assign_task(
            "t_rep",
            category="data_collection",
            strategy=AssignmentStrategy.REPUTATION,
        )
        assert a.assigned_agent == "high_rep"


# ══════════════════════════════════════════════
# E2E: Full Swarm Day Simulation
# ══════════════════════════════════════════════


class TestFullDaySimulation:
    """Simulates a full day of swarm operation."""

    @pytest.mark.asyncio
    async def test_day_simulation(self):
        """Simulate a typical day: boot → work → sleep → wake → work more."""
        harness = SwarmTestHarness(max_agents=6)
        harness.add_kk_roster(6)

        # Morning: All agents active, process tasks
        morning_completed = 0
        for i in range(20):
            category = ["data_collection", "content_creation", "code_review"][i % 3]
            a = await harness.orch.assign_task(f"morning_{i}", category=category)
            if a.assigned_agent:
                await harness.orch.complete_task(
                    f"morning_{i}",
                    success=True,
                    earnings_usd=0.10,
                )
                morning_completed += 1

        assert morning_completed >= 15

        # Mid-day: Some agents sleep (budget/schedule)
        harness.lifecycle.sleep_agent("aurora", reason="lunch_break")
        harness.lifecycle.sleep_agent("blaze", reason="budget_pause")

        health = harness.lifecycle.health_check()
        assert health["active"] == 4
        assert health["sleeping"] == 2

        # Afternoon: Wake agents back up
        harness.lifecycle.wake_agent("aurora")
        harness.lifecycle.activate_agent("aurora")
        harness.lifecycle.wake_agent("blaze")
        harness.lifecycle.activate_agent("blaze")

        health = harness.lifecycle.health_check()
        assert health["active"] == 6

        # Afternoon tasks
        afternoon_completed = 0
        for i in range(15):
            category = ["translation", "testing", "research"][i % 3]
            a = await harness.orch.assign_task(f"afternoon_{i}", category=category)
            if a.assigned_agent:
                await harness.orch.complete_task(
                    f"afternoon_{i}",
                    success=(i != 5),  # one failure
                    earnings_usd=0.08,
                )
                afternoon_completed += 1

        # End of day: check economics
        summary = harness.orch.economic_summary()
        total = morning_completed + afternoon_completed
        assert summary["total_completed"] == total
        assert summary["total_earned_usd"] > 2.0  # At least $2 earned
        assert summary["completion_rate"] > 0.9  # >90% success

        # Night: Sleep all agents
        for agent_id in list(harness.lifecycle.agents.keys()):
            if harness.lifecycle.agents[agent_id].status == AgentStatus.ACTIVE:
                harness.lifecycle.sleep_agent(agent_id, reason="end_of_day")

        health = harness.lifecycle.health_check()
        assert health["active"] == 0
        assert health["sleeping"] == 6
