"""
Tests for the KK V2 Decision Engine.

Covers:
  - Factor computation (reputation, efficiency, specialization, workload, recency, risk)
  - Agent scoring and disqualification
  - Single-task decisions
  - Batch decisions with workload balancing
  - Optimization modes (balanced, quality, cost, speed, exploration)
  - Edge cases (no agents, all disqualified, single agent)
  - Decision confidence and risk assessment
  - Explainability and formatting
"""

import pytest
from datetime import datetime, timezone, timedelta

from lib.decision_engine import (
    AgentProfile,
    Decision,
    DecisionConfig,
    DecisionContext,
    DecisionEngine,
    OptimizationMode,
    ScoredAgent,
    TaskProfile,
    apply_mode_adjustment,
    compute_efficiency_factor,
    compute_recency_factor,
    compute_reputation_factor,
    compute_risk_factor,
    compute_specialization_factor,
    compute_workload_factor,
    explain_ranking,
    format_decision_irc,
    quick_decide,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_agent(
    name: str = "agent-1",
    reputation: float = 70.0,
    efficiency: float = 60.0,
    reliability: float = 0.8,
    tasks_completed: int = 20,
    current_tasks: int = 0,
    consecutive_failures: int = 0,
    is_available: bool = True,
    category_strengths: dict | None = None,
    chain_experience: dict | None = None,
    reputation_confidence: float = 0.5,
    predicted_success: float = 0.0,
    avg_completion_hours: float = 8.0,
    earnings_per_hour: float = 2.0,
    last_task_completed_at: str = "",
) -> AgentProfile:
    return AgentProfile(
        agent_name=name,
        reputation_score=reputation,
        reputation_confidence=reputation_confidence,
        efficiency_score=efficiency,
        reliability=reliability,
        tasks_completed=tasks_completed,
        current_tasks=current_tasks,
        consecutive_failures=consecutive_failures,
        is_available=is_available,
        is_idle=current_tasks == 0,
        category_strengths=category_strengths or {},
        chain_experience=chain_experience or {},
        predicted_success=predicted_success,
        avg_completion_hours=avg_completion_hours,
        earnings_per_hour=earnings_per_hour,
        last_task_completed_at=last_task_completed_at,
    )


def make_task(
    task_id: str = "task-001",
    category: str = "simple_action",
    bounty: float = 1.0,
    complexity: str = "medium",
    required_chain: str = "",
    time_limit: float = 24.0,
    priority: str = "normal",
) -> TaskProfile:
    return TaskProfile(
        task_id=task_id,
        category=category,
        bounty_usd=bounty,
        complexity=complexity,
        required_chain=required_chain,
        time_limit_hours=time_limit,
        priority=priority,
    )


NOW = datetime(2026, 3, 2, 3, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Factor Tests
# ---------------------------------------------------------------------------

class TestReputationFactor:
    def test_high_reputation_scores_high(self):
        agent = make_agent(reputation=90.0, reputation_confidence=0.8)
        task = make_task()
        score, reasons = compute_reputation_factor(agent, task)
        assert score > 80

    def test_low_reputation_scores_low(self):
        agent = make_agent(reputation=20.0, reputation_confidence=0.8)
        task = make_task()
        score, reasons = compute_reputation_factor(agent, task)
        assert score < 30

    def test_low_confidence_dampens_score(self):
        agent = make_agent(reputation=90.0, reputation_confidence=0.1)
        task = make_task()
        score, reasons = compute_reputation_factor(agent, task)
        # Should be dampened toward 50
        assert score < 90
        assert any("dampened" in r.lower() for r in reasons)

    def test_neutral_confidence_no_dampening(self):
        agent = make_agent(reputation=70.0, reputation_confidence=0.5)
        task = make_task()
        score, reasons = compute_reputation_factor(agent, task)
        assert score == 70.0


class TestEfficiencyFactor:
    def test_fast_agent_gets_bonus(self):
        agent = make_agent(efficiency=60, avg_completion_hours=4.0)
        task = make_task(time_limit=24.0)
        score, reasons = compute_efficiency_factor(agent, task)
        assert score > 60  # Base + speed bonus

    def test_slow_agent_gets_penalty(self):
        agent = make_agent(efficiency=60, avg_completion_hours=20.0)
        task = make_task(time_limit=24.0)
        score, reasons = compute_efficiency_factor(agent, task)
        assert score <= 60

    def test_high_reliability_noted(self):
        agent = make_agent(efficiency=50, reliability=0.95)
        task = make_task()
        score, reasons = compute_efficiency_factor(agent, task)
        assert any("reliability" in r.lower() for r in reasons)

    def test_low_reliability_penalty(self):
        agent = make_agent(efficiency=70, reliability=0.3, avg_completion_hours=20.0)
        task = make_task(time_limit=24.0)
        score, reasons = compute_efficiency_factor(agent, task)
        assert score < 70


class TestSpecializationFactor:
    def test_category_match_boosts_score(self):
        agent = make_agent(category_strengths={"simple_action": 0.9})
        task = make_task(category="simple_action")
        score, reasons = compute_specialization_factor(agent, task)
        assert score > 60

    def test_no_category_experience_lowers_score(self):
        agent = make_agent(category_strengths={"research": 0.9})
        task = make_task(category="physical_verification")
        score, reasons = compute_specialization_factor(agent, task)
        assert score < 50

    def test_chain_experience_matters(self):
        agent = make_agent(chain_experience={"base": 0.8})
        task = make_task(required_chain="base")
        score, reasons = compute_specialization_factor(agent, task)
        assert any("base" in r.lower() for r in reasons)

    def test_no_chain_experience_penalized(self):
        agent = make_agent(chain_experience={"ethereum": 0.8})
        task = make_task(required_chain="polygon")
        score, reasons = compute_specialization_factor(agent, task)
        assert any("no experience" in r.lower() for r in reasons)

    def test_no_data_returns_neutral(self):
        agent = make_agent()
        task = make_task(category="")
        score, reasons = compute_specialization_factor(agent, task)
        assert 40 <= score <= 60


class TestWorkloadFactor:
    def test_idle_agent_scores_high(self):
        agent = make_agent(current_tasks=0)
        config = DecisionConfig()
        score, reasons = compute_workload_factor(agent, config)
        assert score >= 95  # 100 + idle bonus, capped

    def test_busy_agent_penalized(self):
        agent = make_agent(current_tasks=2)
        agent.is_idle = False
        config = DecisionConfig()
        score, reasons = compute_workload_factor(agent, config)
        assert score < 90

    def test_at_capacity_zeroed(self):
        agent = make_agent(current_tasks=3)
        agent.is_idle = False
        config = DecisionConfig(max_concurrent_tasks=3)
        score, reasons = compute_workload_factor(agent, config)
        assert score == 0

    def test_cooldown_zeroed(self):
        agent = make_agent()
        agent.in_cooldown = True
        config = DecisionConfig()
        score, reasons = compute_workload_factor(agent, config)
        assert score == 0

    def test_error_state_zeroed(self):
        agent = make_agent()
        agent.in_error = True
        config = DecisionConfig()
        score, reasons = compute_workload_factor(agent, config)
        assert score == 0


class TestRecencyFactor:
    def test_recently_active_scores_high(self):
        two_hours_ago = (NOW - timedelta(hours=2)).isoformat()
        agent = make_agent(last_task_completed_at=two_hours_ago)
        score, reasons = compute_recency_factor(agent, NOW)
        assert score >= 80

    def test_very_recent_slightly_lower(self):
        ten_min_ago = (NOW - timedelta(minutes=10)).isoformat()
        agent = make_agent(last_task_completed_at=ten_min_ago)
        score, reasons = compute_recency_factor(agent, NOW)
        assert 60 <= score <= 80  # Cooling period

    def test_inactive_agent_scores_low(self):
        five_days_ago = (NOW - timedelta(days=5)).isoformat()
        agent = make_agent(last_task_completed_at=five_days_ago)
        score, reasons = compute_recency_factor(agent, NOW)
        assert score <= 40

    def test_no_history_neutral(self):
        agent = make_agent(last_task_completed_at="")
        score, reasons = compute_recency_factor(agent, NOW)
        assert score == 50.0


class TestRiskFactor:
    def test_clean_agent_low_risk(self):
        agent = make_agent(consecutive_failures=0, tasks_completed=30)
        task = make_task(complexity="low")
        config = DecisionConfig()
        score, reasons = compute_risk_factor(agent, task, config)
        assert score >= 90

    def test_failing_agent_high_risk(self):
        agent = make_agent(consecutive_failures=2)
        task = make_task()
        config = DecisionConfig()
        score, reasons = compute_risk_factor(agent, task, config)
        assert score < 80

    def test_complex_task_inexperienced_agent(self):
        agent = make_agent(tasks_completed=3)
        task = make_task(complexity="high")
        config = DecisionConfig()
        score, reasons = compute_risk_factor(agent, task, config)
        assert score < 90

    def test_high_value_low_confidence(self):
        agent = make_agent(reputation_confidence=0.1)
        task = make_task(bounty=20.0)
        config = DecisionConfig()
        score, reasons = compute_risk_factor(agent, task, config)
        assert score < 90

    def test_autojob_high_success_boosts(self):
        agent = make_agent(predicted_success=0.9)
        task = make_task()
        config = DecisionConfig()
        score, reasons = compute_risk_factor(agent, task, config)
        assert any("high success" in r.lower() for r in reasons)

    def test_autojob_low_success_penalizes(self):
        agent = make_agent(predicted_success=0.2)
        task = make_task()
        config = DecisionConfig()
        score, reasons = compute_risk_factor(agent, task, config)
        assert score < 90


# ---------------------------------------------------------------------------
# Scoring Tests
# ---------------------------------------------------------------------------

class TestAgentScoring:
    def test_unavailable_agent_disqualified(self):
        engine = DecisionEngine()
        agent = make_agent(is_available=False)
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        assert scored.disqualified
        assert "not available" in scored.disqualify_reason.lower()

    def test_cooldown_agent_disqualified(self):
        engine = DecisionEngine()
        agent = make_agent()
        agent.in_cooldown = True
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        assert scored.disqualified

    def test_at_capacity_disqualified(self):
        engine = DecisionEngine(DecisionConfig(max_concurrent_tasks=2))
        agent = make_agent(current_tasks=2)
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        assert scored.disqualified

    def test_circuit_breaker_disqualified(self):
        engine = DecisionEngine(DecisionConfig(max_consecutive_failures=3))
        agent = make_agent(consecutive_failures=3)
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        assert scored.disqualified

    def test_low_reputation_disqualified(self):
        engine = DecisionEngine(DecisionConfig(min_reputation_score=30))
        agent = make_agent(reputation=10.0)
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        assert scored.disqualified

    def test_qualified_agent_gets_score(self):
        engine = DecisionEngine()
        agent = make_agent(reputation=80, efficiency=70, reliability=0.9)
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        assert not scored.disqualified
        assert scored.total_score > 0
        assert len(scored.reasons) > 0

    def test_cold_start_bonus_applied(self):
        config = DecisionConfig(cold_start_threshold=5, cold_start_bonus=10.0, min_confidence=0.1)
        engine = DecisionEngine(config)
        agent = make_agent(tasks_completed=2, reputation_confidence=0.05)
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        assert scored.cold_start_bonus > 0

    def test_score_to_dict_structure(self):
        engine = DecisionEngine()
        agent = make_agent()
        task = make_task()
        scored = engine.score_agent(agent, task, NOW)
        d = scored.to_dict()
        assert "agent" in d
        assert "total_score" in d
        assert "factors" in d
        assert "adjustments" in d


# ---------------------------------------------------------------------------
# Decision Tests
# ---------------------------------------------------------------------------

class TestDecisions:
    def test_empty_agents_no_assignment(self):
        engine = DecisionEngine()
        context = DecisionContext(task=make_task(), agents=[], timestamp=NOW)
        decision = engine.decide(context)
        assert decision.chosen_agent is None

    def test_single_agent_assigned(self):
        engine = DecisionEngine()
        context = DecisionContext(
            task=make_task(),
            agents=[make_agent("solo")],
            timestamp=NOW,
        )
        decision = engine.decide(context)
        assert decision.chosen_agent == "solo"

    def test_best_agent_wins(self):
        engine = DecisionEngine()
        agents = [
            make_agent("weak", reputation=30, efficiency=30, reliability=0.3),
            make_agent("strong", reputation=90, efficiency=85, reliability=0.95),
            make_agent("medium", reputation=60, efficiency=55, reliability=0.7),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        assert decision.chosen_agent == "strong"

    def test_alternatives_identified(self):
        engine = DecisionEngine(DecisionConfig(cascade_depth=2))
        agents = [
            make_agent("a1", reputation=90),
            make_agent("a2", reputation=80),
            make_agent("a3", reputation=70),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        assert len(decision.alternatives) >= 1

    def test_all_disqualified(self):
        engine = DecisionEngine(DecisionConfig(min_reputation_score=50))
        agents = [
            make_agent("a1", reputation=10),
            make_agent("a2", reputation=20),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        assert decision.chosen_agent is None
        assert decision.agents_disqualified == 2

    def test_decision_has_reasoning(self):
        engine = DecisionEngine()
        context = DecisionContext(
            task=make_task(),
            agents=[make_agent("test")],
            timestamp=NOW,
        )
        decision = engine.decide(context)
        assert len(decision.reasoning) > 0

    def test_decision_to_dict_structure(self):
        engine = DecisionEngine()
        context = DecisionContext(
            task=make_task(),
            agents=[make_agent()],
            timestamp=NOW,
        )
        decision = engine.decide(context)
        d = decision.to_dict()
        assert "task_id" in d
        assert "chosen_agent" in d
        assert "stats" in d
        assert "top_rankings" in d

    def test_explain_method(self):
        engine = DecisionEngine()
        context = DecisionContext(
            task=make_task(),
            agents=[make_agent()],
            timestamp=NOW,
        )
        decision = engine.decide(context)
        text = decision.explain()
        assert "Decision" in text
        assert decision.chosen_agent in text


# ---------------------------------------------------------------------------
# Batch Decision Tests
# ---------------------------------------------------------------------------

class TestBatchDecisions:
    def test_batch_distributes_work(self):
        engine = DecisionEngine()
        agents = [
            make_agent("a1", reputation=80, efficiency=75),
            make_agent("a2", reputation=78, efficiency=73),
            make_agent("a3", reputation=75, efficiency=70),
        ]
        tasks = [
            make_task("t1"),
            make_task("t2"),
            make_task("t3"),
        ]
        decisions = engine.batch_decide(tasks, agents, NOW)
        assert len(decisions) == 3

        # Should not all go to the same agent (workload penalty kicks in)
        chosen = [d.chosen_agent for d in decisions if d.chosen_agent]
        assert len(chosen) == 3
        # At least 2 different agents should be used
        assert len(set(chosen)) >= 2

    def test_batch_respects_priority(self):
        engine = DecisionEngine()
        agents = [make_agent("a1", reputation=80)]
        tasks = [
            make_task("low", priority="low"),
            make_task("critical", priority="critical"),
        ]
        decisions = engine.batch_decide(tasks, agents, NOW)
        # Critical should be processed first
        assert decisions[0].task_id == "critical"

    def test_batch_handles_capacity(self):
        config = DecisionConfig(max_concurrent_tasks=2)
        engine = DecisionEngine(config)
        agents = [make_agent("a1", reputation=80)]
        tasks = [make_task(f"t{i}") for i in range(4)]
        decisions = engine.batch_decide(tasks, agents, NOW)
        assigned = [d for d in decisions if d.chosen_agent]
        # Only 2 should be assigned (capacity limit)
        assert len(assigned) == 2


# ---------------------------------------------------------------------------
# Optimization Mode Tests
# ---------------------------------------------------------------------------

class TestOptimizationModes:
    def test_quality_mode_boosts_reputation(self):
        config = DecisionConfig(mode=OptimizationMode.QUALITY)
        engine = DecisionEngine(config)
        agents = [
            make_agent("high_rep", reputation=95, efficiency=50),
            make_agent("high_eff", reputation=60, efficiency=95),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        # Quality mode should prefer the high-reputation agent
        assert decision.chosen_agent == "high_rep"

    def test_speed_mode_prefers_efficient(self):
        config = DecisionConfig(mode=OptimizationMode.SPEED)
        engine = DecisionEngine(config)
        agents = [
            make_agent("fast", efficiency=95, avg_completion_hours=2.0, reputation=60),
            make_agent("slow", efficiency=40, avg_completion_hours=20.0, reputation=80),
        ]
        context = DecisionContext(
            task=make_task(time_limit=24.0),
            agents=agents,
            timestamp=NOW,
        )
        decision = engine.decide(context)
        assert decision.chosen_agent == "fast"

    def test_exploration_mode_favors_new_agents(self):
        config = DecisionConfig(mode=OptimizationMode.EXPLORATION, cold_start_threshold=10)
        engine = DecisionEngine(config)
        agents = [
            make_agent("veteran", reputation=75, tasks_completed=100),
            make_agent("newbie", reputation=55, tasks_completed=3),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        # Exploration should boost the newbie
        assert decision.chosen_agent == "newbie"

    def test_cost_mode_respects_quality_floor(self):
        config = DecisionConfig(mode=OptimizationMode.COST, quality_floor=50)
        engine = DecisionEngine(config)
        agents = [
            make_agent("cheap_bad", reputation=30, earnings_per_hour=0.5),
            make_agent("cheap_ok", reputation=60, earnings_per_hour=1.0),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        # cheap_bad should be disqualified by quality floor
        assert decision.chosen_agent == "cheap_ok"


# ---------------------------------------------------------------------------
# Confidence & Risk Tests
# ---------------------------------------------------------------------------

class TestConfidenceAndRisk:
    def test_clear_winner_high_confidence(self):
        engine = DecisionEngine()
        agents = [
            make_agent("star", reputation=95, efficiency=90, reliability=0.99,
                       reputation_confidence=0.9),
            make_agent("meh", reputation=30, efficiency=30, reliability=0.3),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        assert decision.confidence > 0.5
        assert decision.score_spread > 10

    def test_close_scores_low_confidence(self):
        engine = DecisionEngine()
        agents = [
            make_agent("a1", reputation=70, efficiency=65),
            make_agent("a2", reputation=69, efficiency=66),
        ]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        assert decision.confidence < 0.7

    def test_complex_task_with_failures_high_risk(self):
        engine = DecisionEngine()
        agents = [
            make_agent("risky", reputation=60, consecutive_failures=2,
                       reputation_confidence=0.1),
        ]
        task = make_task(complexity="high", bounty=15.0)
        context = DecisionContext(task=task, agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        assert decision.risk_level in ("medium", "high")


# ---------------------------------------------------------------------------
# Formatting Tests
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_explain_ranking(self):
        engine = DecisionEngine()
        agents = [make_agent("a1"), make_agent("a2")]
        context = DecisionContext(task=make_task(), agents=agents, timestamp=NOW)
        decision = engine.decide(context)
        text = explain_ranking(decision)
        assert "Full Ranking" in text
        assert "a1" in text or "a2" in text

    def test_format_decision_irc_with_agent(self):
        engine = DecisionEngine()
        context = DecisionContext(
            task=make_task("test-123"),
            agents=[make_agent("parcero")],
            timestamp=NOW,
        )
        decision = engine.decide(context)
        text = format_decision_irc(decision)
        assert "parcero" in text
        assert "test-123" in text

    def test_format_decision_irc_no_agent(self):
        decision = Decision(task_id="empty-task")
        text = format_decision_irc(decision)
        assert "No hay agentes" in text

    def test_quick_decide_shortcut(self):
        agents = [make_agent("quick")]
        decision = quick_decide(make_task(), agents)
        assert decision.chosen_agent == "quick"


# ---------------------------------------------------------------------------
# Complexity Scaling Tests
# ---------------------------------------------------------------------------

class TestComplexityScaling:
    def test_high_complexity_increases_reputation_weight(self):
        engine = DecisionEngine()
        agents = [
            make_agent("high_rep", reputation=95, efficiency=50),
            make_agent("high_eff", reputation=50, efficiency=95),
        ]
        # Low complexity — efficiency might win
        low_task = make_task(complexity="low")
        context_low = DecisionContext(task=low_task, agents=agents, timestamp=NOW)
        decision_low = engine.decide(context_low)

        # High complexity — reputation should win
        high_task = make_task(complexity="high")
        context_high = DecisionContext(task=high_task, agents=agents, timestamp=NOW)
        decision_high = engine.decide(context_high)

        # At minimum, the scores should differ
        assert decision_low.chosen_score != decision_high.chosen_score

    def test_task_profile_multiplier(self):
        assert TaskProfile(task_id="t", complexity="low").complexity_multiplier == 0.7
        assert TaskProfile(task_id="t", complexity="medium").complexity_multiplier == 1.0
        assert TaskProfile(task_id="t", complexity="high").complexity_multiplier == 1.3
        assert TaskProfile(task_id="t", complexity="critical").complexity_multiplier == 1.5
