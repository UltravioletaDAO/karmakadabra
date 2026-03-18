"""
Tests for KarmaKadabra V2 Swarm Module

Tests cover:
- ReputationBridge: composite scoring, confidence, evidence weight, tier
- LifecycleManager: state transitions, budget enforcement, health checks
- SwarmOrchestrator: agent registration, task assignment, economics
"""

import pytest
from datetime import datetime, timezone, timedelta

from lib.swarm.reputation_bridge import (
    ReputationBridge,
    BridgedReputation,
    ReputationSource,
)
from lib.swarm.lifecycle_manager import (
    LifecycleManager,
    AgentState,
    AgentStatus,
    ResourceBudget,
)
from lib.swarm.swarm_orchestrator import (
    SwarmOrchestrator,
    AssignmentStrategy,
)


# ══════════════════════════════════════════════
# ReputationBridge Tests
# ══════════════════════════════════════════════


class TestReputationBridge:
    """Tests for the reputation bridge."""

    def setup_method(self):
        self.bridge = ReputationBridge(dry_run=True)

    def test_composite_em_only(self):
        """When only EM data exists, composite = EM bayesian score."""
        rep = BridgedReputation(
            wallet="0x1234",
            em_bayesian_score=75.0,
            em_total_tasks=10,
            sources=[ReputationSource.EM_INTERNAL.value],
        )
        score = self.bridge._calculate_composite(rep)
        assert score == 75.0

    def test_composite_chain_only(self):
        """When only chain data exists, composite = chain score."""
        rep = BridgedReputation(
            wallet="0x1234",
            chain_score=80.0,
            chain_total_ratings=15,
            sources=[ReputationSource.ERC8004_ONCHAIN.value],
        )
        score = self.bridge._calculate_composite(rep)
        assert score == 80.0

    def test_composite_both_sources(self):
        """When both sources exist, composite is weighted average."""
        rep = BridgedReputation(
            wallet="0x1234",
            em_bayesian_score=70.0,
            em_total_tasks=20,
            chain_score=80.0,
            chain_total_ratings=10,
            sources=[
                ReputationSource.EM_INTERNAL.value,
                ReputationSource.ERC8004_ONCHAIN.value,
            ],
        )
        score = self.bridge._calculate_composite(rep)
        # EM weight = 0.6, chain weight = 0.4 (10 ratings >= 5 min)
        expected = 0.6 * 70.0 + 0.4 * 80.0
        assert abs(score - expected) < 0.1

    def test_composite_few_chain_ratings(self):
        """Chain weight is reduced when few ratings."""
        rep = BridgedReputation(
            wallet="0x1234",
            em_bayesian_score=70.0,
            em_total_tasks=20,
            chain_score=80.0,
            chain_total_ratings=2,  # Only 2 ratings (< 5 min)
            sources=[
                ReputationSource.EM_INTERNAL.value,
                ReputationSource.ERC8004_ONCHAIN.value,
            ],
        )
        score = self.bridge._calculate_composite(rep)
        # Chain weight = 0.4 * (2/5) = 0.16
        chain_w = 0.4 * (2 / 5)
        em_w = 1.0 - chain_w
        expected = em_w * 70.0 + chain_w * 80.0
        assert abs(score - expected) < 0.1

    def test_composite_no_data(self):
        """Default to 50 when no data."""
        rep = BridgedReputation(wallet="0x1234")
        score = self.bridge._calculate_composite(rep)
        assert score == 50.0

    def test_confidence_no_data(self):
        """Zero confidence with no data."""
        rep = BridgedReputation(wallet="0x1234")
        conf = self.bridge._calculate_confidence(rep)
        assert conf == 0.0

    def test_confidence_many_tasks(self):
        """High confidence with many tasks."""
        rep = BridgedReputation(
            wallet="0x1234",
            em_total_tasks=50,
            chain_total_ratings=20,
            sources=[
                ReputationSource.EM_INTERNAL.value,
                ReputationSource.ERC8004_ONCHAIN.value,
            ],
        )
        conf = self.bridge._calculate_confidence(rep)
        assert conf >= 0.9

    def test_confidence_single_source_bonus(self):
        """Multi-source gives confidence bonus."""
        rep_single = BridgedReputation(
            wallet="0x1234",
            em_total_tasks=10,
            sources=[ReputationSource.EM_INTERNAL.value],
        )
        rep_multi = BridgedReputation(
            wallet="0x1234",
            em_total_tasks=10,
            chain_total_ratings=5,
            sources=[
                ReputationSource.EM_INTERNAL.value,
                ReputationSource.ERC8004_ONCHAIN.value,
            ],
        )
        conf_single = self.bridge._calculate_confidence(rep_single)
        conf_multi = self.bridge._calculate_confidence(rep_multi)
        assert conf_multi > conf_single

    def test_evidence_weight_self_reported(self):
        """Self-reported has lowest evidence weight."""
        rep = BridgedReputation(wallet="0x1234")
        ew = self.bridge._calculate_evidence_weight(rep)
        assert ew == 0.3

    def test_evidence_weight_em_tasks(self):
        """EM tasks increase evidence weight."""
        rep = BridgedReputation(
            wallet="0x1234",
            em_total_tasks=10,
            em_successful_tasks=9,
        )
        ew = self.bridge._calculate_evidence_weight(rep)
        assert ew >= 0.7  # 0.6 base + 0.1 for 10+ tasks

    def test_evidence_weight_with_chain(self):
        """On-chain reputation gives highest evidence weight."""
        rep = BridgedReputation(
            wallet="0x1234",
            em_total_tasks=50,
            em_successful_tasks=48,
            chain_total_ratings=30,
        )
        ew = self.bridge._calculate_evidence_weight(rep)
        assert ew >= 0.85

    def test_evidence_weight_cap(self):
        """Evidence weight caps at 0.98."""
        rep = BridgedReputation(
            wallet="0x1234",
            em_total_tasks=1000,
            em_successful_tasks=999,
            chain_total_ratings=500,
        )
        ew = self.bridge._calculate_evidence_weight(rep)
        assert ew <= 0.98

    def test_tier_elite(self):
        """Elite requires high score AND high confidence."""
        tier = self.bridge._determine_tier(95.0, 0.9)
        assert tier == "elite"

    def test_tier_high_score_low_confidence(self):
        """High score with low confidence can't be elite."""
        tier = self.bridge._determine_tier(95.0, 0.3)
        assert tier != "elite"

    def test_tier_at_risk(self):
        """Low score = at_risk."""
        tier = self.bridge._determine_tier(30.0, 0.5)
        assert tier == "at_risk"

    def test_bayesian_adjust(self):
        """Bayesian adjustment pulls extreme scores toward mean."""
        # With few tasks, score is pulled toward 50
        adjusted = self.bridge._bayesian_adjust(100.0, 1)
        assert adjusted < 100.0
        assert adjusted > 50.0

        # With many tasks, score stays near raw
        adjusted_many = self.bridge._bayesian_adjust(100.0, 100)
        assert adjusted_many > adjusted  # Closer to 100 with more tasks


# ══════════════════════════════════════════════
# LifecycleManager Tests
# ══════════════════════════════════════════════


class TestLifecycleManager:
    """Tests for the agent lifecycle manager."""

    def setup_method(self):
        self.lm = LifecycleManager(max_agents=5)

    def test_register_agent(self):
        """Can register a new agent."""
        state = self.lm.register_agent(
            agent_id="aurora",
            wallet="0x1234",
            personality="explorer",
        )
        assert state.agent_id == "aurora"
        assert state.wallet == "0x1234"
        assert state.status == AgentStatus.INACTIVE
        assert "aurora" in self.lm.agents

    def test_boot_from_inactive(self):
        """Can boot an inactive agent."""
        self.lm.register_agent("aurora", "0x1234")
        assert self.lm.boot_agent("aurora")
        assert self.lm.agents["aurora"].status == AgentStatus.BOOTING

    def test_activate_after_boot(self):
        """Can activate a booting agent."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        assert self.lm.activate_agent("aurora")
        assert self.lm.agents["aurora"].status == AgentStatus.ACTIVE

    def test_cannot_boot_active(self):
        """Cannot boot an already active agent."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")
        assert not self.lm.boot_agent("aurora")

    def test_sleep_active_agent(self):
        """Can put an active agent to sleep."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")
        assert self.lm.sleep_agent("aurora", reason="test")
        assert self.lm.agents["aurora"].status == AgentStatus.SLEEPING

    def test_wake_sleeping_agent(self):
        """Can wake a sleeping agent."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")
        self.lm.sleep_agent("aurora")
        assert self.lm.wake_agent("aurora")
        assert self.lm.agents["aurora"].status == AgentStatus.WAKING

    def test_capacity_limit(self):
        """Cannot boot more agents than max_agents."""
        for i in range(5):
            self.lm.register_agent(f"agent_{i}", f"0x{i}")
            self.lm.boot_agent(f"agent_{i}")
            self.lm.activate_agent(f"agent_{i}")

        self.lm.register_agent("agent_extra", "0xextra")
        assert not self.lm.boot_agent("agent_extra")

    def test_retire_agent(self):
        """Can retire any agent."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")
        assert self.lm.retire_agent("aurora", "manual")
        assert self.lm.agents["aurora"].status == AgentStatus.RETIRED

    def test_error_auto_retire(self):
        """Agent auto-retires after 10 consecutive failures."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")

        for i in range(10):
            # Reset to active for next error
            self.lm.agents["aurora"].status = AgentStatus.ACTIVE
            self.lm.error_agent("aurora", f"failure {i}")

        assert self.lm.agents["aurora"].status == AgentStatus.RETIRED

    def test_health_check(self):
        """Health check returns correct summary."""
        self.lm.register_agent("a1", "0x1")
        self.lm.register_agent("a2", "0x2")
        self.lm.boot_agent("a1")
        self.lm.activate_agent("a1")

        health = self.lm.health_check()
        assert health["total_agents"] == 2
        assert health["active"] == 1

    def test_heartbeat_continue(self):
        """Healthy agent with budget gets 'continue'."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")

        # Mock time to be within default active hours (6-22 UTC)
        from unittest.mock import patch
        from datetime import datetime as _dt, timezone as _tz

        mock_dt = _dt(2026, 2, 23, 12, 0, 0, tzinfo=_tz.utc)
        with patch("lib.swarm.lifecycle_manager.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.side_effect = lambda *a, **kw: _dt(*a, **kw)
            result = self.lm.heartbeat("aurora", {"tokens": 100})
        assert result["action"] == "continue"

    def test_heartbeat_budget_exceeded(self):
        """Agent exceeding budget gets 'sleep'."""
        self.lm.register_agent(
            "aurora",
            "0x1234",
            budget=ResourceBudget(max_tokens_per_day=1000),
        )
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")

        result = self.lm.heartbeat("aurora", {"tokens": 2000})
        assert result["action"] == "sleep"

    def test_budget_utilization(self):
        """Budget utilization reports correct percentages."""
        state = AgentState(
            agent_id="test",
            wallet="0x1234",
            budget=ResourceBudget(max_tokens_per_day=1000, max_usd_spend_per_day=1.0),
        )
        state.usage.tokens_today = 500
        state.usage.usd_spent_today = 0.5
        state.usage.last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        util = state.budget_utilization()
        assert util["tokens"] == 0.5
        assert util["usd"] == 0.5

    def test_active_agent_count(self):
        """Counts active, booting, and waking agents."""
        self.lm.register_agent("a1", "0x1")
        self.lm.register_agent("a2", "0x2")
        self.lm.register_agent("a3", "0x3")

        self.lm.boot_agent("a1")
        self.lm.activate_agent("a1")
        self.lm.boot_agent("a2")  # Still booting

        assert self.lm.active_agent_count() == 2  # 1 active + 1 booting

    def test_unregister_agent(self):
        """Can unregister an agent."""
        self.lm.register_agent("aurora", "0x1234")
        assert self.lm.unregister_agent("aurora")
        assert "aurora" not in self.lm.agents

    def test_auto_manage(self):
        """Auto-manage sleeps and recovers agents."""
        self.lm.register_agent("aurora", "0x1234")
        self.lm.boot_agent("aurora")
        self.lm.activate_agent("aurora")
        self.lm.error_agent("aurora", "test error")

        # Set error time to 6 minutes ago
        self.lm.agents["aurora"].status_since = datetime.now(timezone.utc) - timedelta(
            minutes=6
        )

        actions = self.lm.auto_manage()
        assert "aurora" in actions["recovered"]


# ══════════════════════════════════════════════
# SwarmOrchestrator Tests
# ══════════════════════════════════════════════


class TestSwarmOrchestrator:
    """Tests for the swarm orchestrator."""

    def setup_method(self):
        self.lifecycle = LifecycleManager(max_agents=10)
        self.bridge = ReputationBridge(dry_run=True)
        self.orch = SwarmOrchestrator(
            lifecycle=self.lifecycle,
            bridge=self.bridge,
        )

    def _setup_active_agent(self, agent_id, skills=None, specializations=None):
        """Helper: register and activate an agent."""
        profile = self.orch.register_agent(
            agent_id=agent_id,
            wallet=f"0x{agent_id}",
            personality="test",
            skills=skills or [],
            specializations=specializations or [],
        )
        self.lifecycle.boot_agent(agent_id)
        self.lifecycle.activate_agent(agent_id)
        return profile

    def test_register_agent(self):
        """Register agent in both lifecycle and orchestrator."""
        profile = self.orch.register_agent(
            agent_id="aurora",
            wallet="0x1234",
            personality="explorer",
            skills=["research", "documentation"],
        )
        assert profile.agent_id == "aurora"
        assert "aurora" in self.orch.profiles
        assert "aurora" in self.lifecycle.agents

    @pytest.mark.asyncio
    async def test_assign_task_basic(self):
        """Assign task to only available agent."""
        self._setup_active_agent("aurora", skills=["research", "documentation"])

        assignment = await self.orch.assign_task(
            task_id="task_1",
            category="data_collection",
        )

        assert assignment.assigned_agent == "aurora"
        assert assignment.score > 0
        assert "task_1" in self.orch.active_tasks

    @pytest.mark.asyncio
    async def test_assign_task_best_match(self):
        """Best skill match wins."""
        self._setup_active_agent(
            "aurora",
            skills=["research", "documentation"],
            specializations=["data_collection"],
        )
        self._setup_active_agent(
            "blaze",
            skills=["writing"],
        )

        assignment = await self.orch.assign_task(
            task_id="task_1",
            category="data_collection",
        )

        # Aurora should win (more matching skills + specialization)
        assert assignment.assigned_agent == "aurora"

    @pytest.mark.asyncio
    async def test_assign_no_eligible(self):
        """Returns unassigned when no agents available."""
        assignment = await self.orch.assign_task(task_id="task_1")
        assert assignment.assigned_agent is None
        assert assignment.unassigned_reason is not None

    @pytest.mark.asyncio
    async def test_prevent_duplicate_claims(self):
        """Cannot assign same task twice."""
        self._setup_active_agent("aurora", skills=["research"])

        await self.orch.assign_task(task_id="task_1", category="data_collection")
        assignment2 = await self.orch.assign_task(task_id="task_1")

        assert assignment2.assigned_agent is None
        assert "Already claimed" in assignment2.unassigned_reason

    @pytest.mark.asyncio
    async def test_complete_task(self):
        """Complete task updates metrics."""
        self._setup_active_agent("aurora", skills=["research"])
        await self.orch.assign_task(task_id="task_1", category="data_collection")

        result = await self.orch.complete_task(
            task_id="task_1",
            success=True,
            earnings_usd=0.50,
        )

        assert result["success"]
        assert result["earnings_usd"] == 0.50
        assert self.orch.total_tasks_completed == 1
        assert self.orch.total_usd_earned == 0.50
        assert "task_1" not in self.orch.active_tasks

    @pytest.mark.asyncio
    async def test_max_concurrent_tasks(self):
        """Agent can't exceed max concurrent tasks."""
        self._setup_active_agent("aurora", skills=["research"])
        self.orch.max_concurrent_tasks = 2

        await self.orch.assign_task(task_id="t1", category="data_collection")
        await self.orch.assign_task(task_id="t2", category="data_collection")
        assignment3 = await self.orch.assign_task(
            task_id="t3", category="data_collection"
        )

        # Third task should fail (aurora at capacity)
        assert assignment3.assigned_agent is None

    def test_economic_summary(self):
        """Economic summary aggregates correctly."""
        summary = self.orch.economic_summary()
        assert summary["total_assigned"] == 0
        assert summary["total_completed"] == 0
        assert summary["net_usd"] == 0.0

    def test_metrics(self):
        """Metrics return comprehensive data."""
        self._setup_active_agent("aurora")
        metrics = self.orch.metrics()

        assert "tasks" in metrics
        assert "agents" in metrics
        assert "economics" in metrics
        assert metrics["agents"]["total"] == 1
        assert metrics["agents"]["active"] == 1

    def test_model_cost(self):
        """Model cost returns correct values."""
        assert (
            self.orch._model_cost("anthropic/claude-haiku-4-5")
            < self.orch._model_cost("anthropic/claude-sonnet-4-20250514")
            < self.orch._model_cost("anthropic/claude-opus-4-6")
        )

    @pytest.mark.asyncio
    async def test_round_robin_strategy(self):
        """Round-robin distributes tasks evenly."""
        self._setup_active_agent("aurora", skills=["research"])
        self._setup_active_agent("blaze", skills=["research"])

        # Manually add history favoring aurora
        self.orch.task_history = [
            {
                "agent_id": "aurora",
                "success": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "agent_id": "aurora",
                "success": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        ]

        assignment = await self.orch.assign_task(
            task_id="task_rr",
            category="data_collection",
            strategy=AssignmentStrategy.ROUND_ROBIN,
        )

        # Blaze should be picked (fewer recent tasks)
        assert assignment.assigned_agent == "blaze"

    @pytest.mark.asyncio
    async def test_agent_profile_refresh(self):
        """Profile refresh updates availability and reputation."""
        self._setup_active_agent("aurora")
        profile = await self.orch.refresh_profile("aurora")
        assert profile is not None
        assert profile.availability_score > 0


# ══════════════════════════════════════════════
# Integration Tests
# ══════════════════════════════════════════════


class TestSwarmIntegration:
    """Integration tests across all swarm components."""

    def setup_method(self):
        self.lifecycle = LifecycleManager(max_agents=10)
        self.bridge = ReputationBridge(dry_run=True)
        self.orch = SwarmOrchestrator(
            lifecycle=self.lifecycle,
            bridge=self.bridge,
        )

    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self):
        """Full lifecycle: register → boot → assign → complete → sleep."""
        # Register and activate
        self.orch.register_agent(
            agent_id="aurora",
            wallet="0xAurora",
            skills=["research", "documentation"],
            specializations=["data_collection"],
        )
        self.lifecycle.boot_agent("aurora")
        self.lifecycle.activate_agent("aurora")

        # Assign task
        assignment = await self.orch.assign_task(
            task_id="task_001",
            category="data_collection",
            bounty_usd=0.25,
        )
        assert assignment.assigned_agent == "aurora"

        # Complete task
        result = await self.orch.complete_task(
            task_id="task_001",
            success=True,
            earnings_usd=0.25,
            rating=85.0,
        )
        assert result["success"]

        # Check metrics
        metrics = self.orch.metrics()
        assert metrics["tasks"]["total_completed"] == 1
        assert metrics["economics"]["total_earned_usd"] == 0.25

        # Sleep agent
        self.lifecycle.sleep_agent("aurora", reason="end_of_day")
        health = self.lifecycle.health_check()
        assert health["sleeping"] == 1

    @pytest.mark.asyncio
    async def test_multi_agent_competition(self):
        """Multiple agents compete for tasks based on skills."""
        # Researcher agent
        self.orch.register_agent(
            agent_id="researcher",
            wallet="0xR",
            skills=["research", "documentation", "analysis"],
            specializations=["data_collection", "research"],
        )
        self.lifecycle.boot_agent("researcher")
        self.lifecycle.activate_agent("researcher")

        # Writer agent
        self.orch.register_agent(
            agent_id="writer",
            wallet="0xW",
            skills=["writing", "creativity", "documentation"],
            specializations=["content_creation"],
        )
        self.lifecycle.boot_agent("writer")
        self.lifecycle.activate_agent("writer")

        # Coder agent
        self.orch.register_agent(
            agent_id="coder",
            wallet="0xC",
            skills=["code_review", "security", "testing"],
            specializations=["code_review"],
        )
        self.lifecycle.boot_agent("coder")
        self.lifecycle.activate_agent("coder")

        # Research task → researcher should win
        a1 = await self.orch.assign_task(task_id="t1", category="data_collection")
        assert a1.assigned_agent == "researcher"

        # Content task → writer should win
        a2 = await self.orch.assign_task(task_id="t2", category="content_creation")
        assert a2.assigned_agent == "writer"

        # Code review → coder should win
        a3 = await self.orch.assign_task(task_id="t3", category="code_review")
        assert a3.assigned_agent == "coder"

    def test_budget_enforcement_flow(self):
        """Budget enforcement prevents overspending."""
        from unittest.mock import patch
        from datetime import datetime as _dt, timezone as _tz

        self.orch.register_agent(
            agent_id="aurora",
            wallet="0x1234",
            budget=ResourceBudget(max_usd_spend_per_day=0.50),
        )
        self.lifecycle.boot_agent("aurora")
        self.lifecycle.activate_agent("aurora")

        # Use a consistent mock date for all heartbeats to avoid
        # time-dependent failures (reset_daily resets on date change)
        mock_dt = _dt(2026, 6, 15, 12, 0, 0, tzinfo=_tz.utc)
        mock_date_str = "2026-06-15"

        # Simulate spending up to limit
        agent = self.lifecycle.agents["aurora"]
        agent.usage.usd_spent_today = 0.48
        agent.usage.last_reset_date = mock_date_str

        with patch("lib.swarm.lifecycle_manager.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.side_effect = lambda *a, **kw: _dt(*a, **kw)

            # Heartbeat should still be ok (0.48 + 0.01 = 0.49 < 0.50)
            result = self.lifecycle.heartbeat("aurora", {"usd": 0.01})
            assert result["action"] == "continue"

            # Now exceed budget (0.49 + 0.05 = 0.54 > 0.50)
            result = self.lifecycle.heartbeat("aurora", {"usd": 0.05})
            assert result["action"] == "sleep"
