"""
Karma Kadabra V2 — Task Pipeline Service

End-to-end task lifecycle management: the single source of truth for
where every task is in its journey from discovery to completion.

Pipeline stages:
  1. DISCOVERED  — Task found on EM marketplace
  2. EVALUATED   — Scored by matching engine, ranked agents identified
  3. OFFERED     — Assignment offered to top-ranked agent
  4. ACCEPTED    — Agent accepted the assignment
  5. IN_PROGRESS — Agent actively working (heartbeat confirmed)
  6. SUBMITTED   — Agent submitted evidence for review
  7. UNDER_REVIEW — Evidence being validated (manual or automated)
  8. APPROVED    — Work approved, payment pending
  9. PAID        — Payment released (on-chain TX confirmed)
  10. RATED      — Bidirectional reputation recorded
  11. COMPLETED  — Final state, all side-effects done
  12. FAILED     — Terminal failure (with reason)
  13. EXPIRED    — TTL exceeded without completion
  14. DISPUTED   — Under dispute resolution

This pipeline replaces ad-hoc task tracking scattered across coordinator,
dispatch, and lifecycle services. It provides:

  - Single state machine for task lifecycle
  - Automated stage transitions with guard conditions
  - SLA tracking (time-in-stage alerts)
  - Event log for audit trail
  - Rollback/retry mechanics for recoverable failures
  - Integration hooks for IRC notifications, reputation, analytics

Usage:
  pipeline = TaskPipeline()
  pipeline.discover(task_data)
  pipeline.evaluate(task_id, rankings)
  pipeline.offer(task_id, agent_name)
  pipeline.accept(task_id)
  pipeline.submit(task_id, evidence)
  pipeline.approve(task_id)
  pipeline.pay(task_id, tx_hash)
  pipeline.rate(task_id, rating)
  pipeline.complete(task_id)

Architecture:
  TaskPipeline (this) orchestrates:
    → CoordinatorService (matching)
    → SwarmDispatch (assignment)
    → AgentLifecycle (state tracking)
    → ReputationBridge (scoring)
    → AutoJobBridge (intelligence)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("kk.pipeline")


# ---------------------------------------------------------------------------
# Pipeline Stage Enum
# ---------------------------------------------------------------------------

class PipelineStage(Enum):
    """Task pipeline stages in order."""
    DISCOVERED = "discovered"
    EVALUATED = "evaluated"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PAID = "paid"
    RATED = "rated"
    COMPLETED = "completed"
    # Terminal states
    FAILED = "failed"
    EXPIRED = "expired"
    DISPUTED = "disputed"


# Valid transitions: from_stage -> set of valid next stages
VALID_TRANSITIONS: dict[PipelineStage, set[PipelineStage]] = {
    PipelineStage.DISCOVERED: {PipelineStage.EVALUATED, PipelineStage.EXPIRED, PipelineStage.FAILED},
    PipelineStage.EVALUATED: {PipelineStage.OFFERED, PipelineStage.FAILED, PipelineStage.EXPIRED},
    PipelineStage.OFFERED: {PipelineStage.ACCEPTED, PipelineStage.EVALUATED, PipelineStage.EXPIRED, PipelineStage.FAILED},
    PipelineStage.ACCEPTED: {PipelineStage.IN_PROGRESS, PipelineStage.FAILED, PipelineStage.EXPIRED},
    PipelineStage.IN_PROGRESS: {PipelineStage.SUBMITTED, PipelineStage.FAILED, PipelineStage.EXPIRED, PipelineStage.DISPUTED},
    PipelineStage.SUBMITTED: {PipelineStage.UNDER_REVIEW, PipelineStage.FAILED},
    PipelineStage.UNDER_REVIEW: {PipelineStage.APPROVED, PipelineStage.FAILED, PipelineStage.DISPUTED},
    PipelineStage.APPROVED: {PipelineStage.PAID, PipelineStage.FAILED},
    PipelineStage.PAID: {PipelineStage.RATED, PipelineStage.COMPLETED},
    PipelineStage.RATED: {PipelineStage.COMPLETED},
    PipelineStage.COMPLETED: set(),  # Terminal
    PipelineStage.FAILED: {PipelineStage.DISCOVERED},  # Can retry from start
    PipelineStage.EXPIRED: {PipelineStage.DISCOVERED},  # Can retry from start
    PipelineStage.DISPUTED: {PipelineStage.APPROVED, PipelineStage.FAILED},
}

# Stage SLA defaults (max time in stage before alert)
DEFAULT_SLAS: dict[PipelineStage, timedelta] = {
    PipelineStage.DISCOVERED: timedelta(minutes=15),
    PipelineStage.EVALUATED: timedelta(minutes=5),
    PipelineStage.OFFERED: timedelta(minutes=10),
    PipelineStage.ACCEPTED: timedelta(minutes=5),
    PipelineStage.IN_PROGRESS: timedelta(hours=4),
    PipelineStage.SUBMITTED: timedelta(minutes=30),
    PipelineStage.UNDER_REVIEW: timedelta(hours=1),
    PipelineStage.APPROVED: timedelta(minutes=15),
    PipelineStage.PAID: timedelta(minutes=10),
    PipelineStage.RATED: timedelta(hours=24),
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class PipelineEvent:
    """An event in the task pipeline audit trail."""
    event_id: str
    task_id: str
    timestamp: str  # ISO 8601
    from_stage: Optional[str]
    to_stage: str
    actor: str  # Who/what triggered the transition
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentRanking:
    """A ranked agent for task matching."""
    agent_name: str
    score: float
    match_mode: str = "enhanced"
    factors: dict = field(default_factory=dict)


@dataclass
class TaskEvidence:
    """Evidence submitted by an agent for task completion."""
    evidence_type: str  # photo, text_response, document, etc.
    content_url: Optional[str] = None
    content_text: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    submitted_at: Optional[str] = None


@dataclass
class PipelineTask:
    """A task moving through the pipeline."""
    task_id: str
    stage: PipelineStage = PipelineStage.DISCOVERED
    title: str = ""
    description: str = ""
    category: str = ""
    bounty_usd: float = 0.0
    payment_network: str = "base"
    creator_wallet: str = ""

    # Assignment
    assigned_agent: Optional[str] = None
    rankings: list[AgentRanking] = field(default_factory=list)
    offer_attempts: int = 0
    max_offer_attempts: int = 3

    # Execution
    started_at: Optional[str] = None
    last_heartbeat: Optional[str] = None
    evidence: list[TaskEvidence] = field(default_factory=list)

    # Completion
    approved_at: Optional[str] = None
    payment_tx: Optional[str] = None
    paid_at: Optional[str] = None
    agent_rating: Optional[float] = None  # Rating given to agent (0-100)
    creator_rating: Optional[float] = None  # Rating given to creator (0-100)

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    stage_entered_at: str = ""  # When current stage was entered
    retry_count: int = 0
    failure_reason: Optional[str] = None
    dispute_reason: Optional[str] = None

    # Event log
    events: list[PipelineEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for persistence."""
        d = {
            "task_id": self.task_id,
            "stage": self.stage.value,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "bounty_usd": self.bounty_usd,
            "payment_network": self.payment_network,
            "creator_wallet": self.creator_wallet,
            "assigned_agent": self.assigned_agent,
            "rankings": [asdict(r) for r in self.rankings],
            "offer_attempts": self.offer_attempts,
            "max_offer_attempts": self.max_offer_attempts,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "evidence": [asdict(e) for e in self.evidence],
            "approved_at": self.approved_at,
            "payment_tx": self.payment_tx,
            "paid_at": self.paid_at,
            "agent_rating": self.agent_rating,
            "creator_rating": self.creator_rating,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stage_entered_at": self.stage_entered_at,
            "retry_count": self.retry_count,
            "failure_reason": self.failure_reason,
            "dispute_reason": self.dispute_reason,
            "events": [e.to_dict() for e in self.events[-100:]],  # Keep last 100 events
        }
        return d


# ---------------------------------------------------------------------------
# Pipeline State
# ---------------------------------------------------------------------------

@dataclass
class PipelineState:
    """Global pipeline state with all tracked tasks."""
    tasks: dict[str, PipelineTask] = field(default_factory=dict)
    total_discovered: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_expired: int = 0
    total_paid_usd: float = 0.0
    last_cycle_at: Optional[str] = None

    def active_tasks(self) -> list[PipelineTask]:
        """Tasks not in terminal states."""
        terminal = {PipelineStage.COMPLETED, PipelineStage.FAILED, PipelineStage.EXPIRED}
        return [t for t in self.tasks.values() if t.stage not in terminal]

    def tasks_in_stage(self, stage: PipelineStage) -> list[PipelineTask]:
        """Get all tasks currently in a specific stage."""
        return [t for t in self.tasks.values() if t.stage == stage]

    def agent_active_tasks(self, agent_name: str) -> list[PipelineTask]:
        """Get active tasks assigned to a specific agent."""
        return [
            t for t in self.active_tasks()
            if t.assigned_agent == agent_name
        ]

    def to_dict(self) -> dict:
        return {
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "total_discovered": self.total_discovered,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_expired": self.total_expired,
            "total_paid_usd": self.total_paid_usd,
            "last_cycle_at": self.last_cycle_at,
        }


# ---------------------------------------------------------------------------
# Transition Engine
# ---------------------------------------------------------------------------

class TransitionError(Exception):
    """Invalid pipeline transition."""
    pass


def validate_transition(
    task: PipelineTask,
    target_stage: PipelineStage,
) -> bool:
    """Check if a transition from the task's current stage to target is valid."""
    allowed = VALID_TRANSITIONS.get(task.stage, set())
    return target_stage in allowed


def execute_transition(
    task: PipelineTask,
    target_stage: PipelineStage,
    actor: str = "system",
    details: Optional[dict] = None,
    now: Optional[datetime] = None,
) -> PipelineEvent:
    """Execute a stage transition with validation and event logging.

    Raises TransitionError if the transition is not valid.
    Returns the created PipelineEvent.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not validate_transition(task, target_stage):
        raise TransitionError(
            f"Invalid transition: {task.stage.value} → {target_stage.value} "
            f"for task {task.task_id}. "
            f"Allowed: {[s.value for s in VALID_TRANSITIONS.get(task.stage, set())]}"
        )

    event = PipelineEvent(
        event_id=str(uuid.uuid4())[:8],
        task_id=task.task_id,
        timestamp=now.isoformat(),
        from_stage=task.stage.value,
        to_stage=target_stage.value,
        actor=actor,
        details=details or {},
    )

    task.stage = target_stage
    task.updated_at = now.isoformat()
    task.stage_entered_at = now.isoformat()
    task.events.append(event)

    logger.info(
        f"Pipeline [{task.task_id[:8]}]: {event.from_stage} → {target_stage.value} "
        f"(actor={actor})"
    )

    return event


# ---------------------------------------------------------------------------
# SLA Monitoring
# ---------------------------------------------------------------------------

@dataclass
class SLAViolation:
    """A task that has exceeded its stage SLA."""
    task_id: str
    task_title: str
    stage: str
    assigned_agent: Optional[str]
    time_in_stage_minutes: float
    sla_limit_minutes: float
    severity: str  # "warning" (>50% SLA), "breach" (>100%), "critical" (>200%)


def check_sla_violations(
    state: PipelineState,
    slas: Optional[dict[PipelineStage, timedelta]] = None,
    now: Optional[datetime] = None,
) -> list[SLAViolation]:
    """Check all active tasks for SLA violations.

    Returns a list of violations sorted by severity (critical first).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if slas is None:
        slas = DEFAULT_SLAS

    violations = []

    for task in state.active_tasks():
        sla = slas.get(task.stage)
        if sla is None:
            continue

        if not task.stage_entered_at:
            continue

        entered = datetime.fromisoformat(task.stage_entered_at)
        elapsed = now - entered
        sla_seconds = sla.total_seconds()
        elapsed_seconds = elapsed.total_seconds()

        if elapsed_seconds <= sla_seconds * 0.5:
            continue  # Under 50% of SLA — no warning

        ratio = elapsed_seconds / sla_seconds
        if ratio >= 2.0:
            severity = "critical"
        elif ratio >= 1.0:
            severity = "breach"
        else:
            severity = "warning"

        violations.append(SLAViolation(
            task_id=task.task_id,
            task_title=task.title,
            stage=task.stage.value,
            assigned_agent=task.assigned_agent,
            time_in_stage_minutes=elapsed_seconds / 60,
            sla_limit_minutes=sla_seconds / 60,
            severity=severity,
        ))

    # Sort by severity
    severity_order = {"critical": 0, "breach": 1, "warning": 2}
    violations.sort(key=lambda v: (severity_order.get(v.severity, 3), -v.time_in_stage_minutes))

    return violations


# ---------------------------------------------------------------------------
# Pipeline Operations (High-Level API)
# ---------------------------------------------------------------------------

class TaskPipeline:
    """The main pipeline orchestrator.

    Provides a clean API for moving tasks through the pipeline
    with validation, event logging, and side-effect hooks.
    """

    def __init__(
        self,
        state: Optional[PipelineState] = None,
        slas: Optional[dict[PipelineStage, timedelta]] = None,
        on_transition: Optional[Callable[[PipelineTask, PipelineEvent], None]] = None,
    ):
        self.state = state or PipelineState()
        self.slas = slas or DEFAULT_SLAS
        self.on_transition = on_transition  # Hook for IRC notifications, etc.

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _fire_hook(self, task: PipelineTask, event: PipelineEvent) -> None:
        """Fire the transition hook if registered."""
        if self.on_transition:
            try:
                self.on_transition(task, event)
            except Exception as e:
                logger.warning(f"Transition hook failed: {e}")

    # --- Stage Operations ---

    def discover(
        self,
        task_id: str,
        title: str = "",
        description: str = "",
        category: str = "",
        bounty_usd: float = 0.0,
        payment_network: str = "base",
        creator_wallet: str = "",
        actor: str = "coordinator",
    ) -> PipelineTask:
        """Register a newly discovered task in the pipeline."""
        now = self._now()
        now_iso = now.isoformat()

        if task_id in self.state.tasks:
            existing = self.state.tasks[task_id]
            # Allow re-discovery of failed/expired tasks
            if existing.stage in (PipelineStage.FAILED, PipelineStage.EXPIRED):
                existing.retry_count += 1
                execute_transition(existing, PipelineStage.DISCOVERED, actor=actor,
                                   details={"retry": existing.retry_count}, now=now)
                self._fire_hook(existing, existing.events[-1])
                return existing
            return existing  # Already tracked

        task = PipelineTask(
            task_id=task_id,
            title=title,
            description=description,
            category=category,
            bounty_usd=bounty_usd,
            payment_network=payment_network,
            creator_wallet=creator_wallet,
            created_at=now_iso,
            updated_at=now_iso,
            stage_entered_at=now_iso,
        )

        # Create initial event
        event = PipelineEvent(
            event_id=str(uuid.uuid4())[:8],
            task_id=task_id,
            timestamp=now_iso,
            from_stage=None,
            to_stage=PipelineStage.DISCOVERED.value,
            actor=actor,
            details={"bounty_usd": bounty_usd, "category": category},
        )
        task.events.append(event)

        self.state.tasks[task_id] = task
        self.state.total_discovered += 1
        self._fire_hook(task, event)

        return task

    def evaluate(
        self,
        task_id: str,
        rankings: list[AgentRanking],
        actor: str = "coordinator",
    ) -> PipelineTask:
        """Record matching evaluation results and advance to EVALUATED."""
        task = self._get_task(task_id)
        task.rankings = rankings

        event = execute_transition(
            task, PipelineStage.EVALUATED, actor=actor,
            details={
                "top_agent": rankings[0].agent_name if rankings else None,
                "top_score": rankings[0].score if rankings else 0,
                "candidates": len(rankings),
            },
        )
        self._fire_hook(task, event)
        return task

    def offer(
        self,
        task_id: str,
        agent_name: Optional[str] = None,
        actor: str = "dispatcher",
    ) -> PipelineTask:
        """Offer the task to the top-ranked (or specified) agent."""
        task = self._get_task(task_id)

        if agent_name is None:
            # Use top-ranked agent that hasn't been offered before
            offered_agents = {
                e.details.get("agent")
                for e in task.events
                if e.to_stage == PipelineStage.OFFERED.value
            }
            for ranking in task.rankings:
                if ranking.agent_name not in offered_agents:
                    agent_name = ranking.agent_name
                    break

        if agent_name is None:
            raise TransitionError(
                f"No eligible agents to offer task {task_id}. "
                f"Rankings exhausted after {task.offer_attempts} attempts."
            )

        task.assigned_agent = agent_name
        task.offer_attempts += 1

        event = execute_transition(
            task, PipelineStage.OFFERED, actor=actor,
            details={
                "agent": agent_name,
                "attempt": task.offer_attempts,
                "score": next(
                    (r.score for r in task.rankings if r.agent_name == agent_name), 0
                ),
            },
        )
        self._fire_hook(task, event)
        return task

    def accept(
        self,
        task_id: str,
        actor: Optional[str] = None,
    ) -> PipelineTask:
        """Agent accepts the offered task."""
        task = self._get_task(task_id)
        if actor is None:
            actor = task.assigned_agent or "agent"

        event = execute_transition(
            task, PipelineStage.ACCEPTED, actor=actor,
            details={"agent": task.assigned_agent},
        )
        self._fire_hook(task, event)
        return task

    def start_work(
        self,
        task_id: str,
        actor: Optional[str] = None,
    ) -> PipelineTask:
        """Agent begins working on the task."""
        task = self._get_task(task_id)
        if actor is None:
            actor = task.assigned_agent or "agent"

        now = self._now()
        task.started_at = now.isoformat()
        task.last_heartbeat = now.isoformat()

        event = execute_transition(
            task, PipelineStage.IN_PROGRESS, actor=actor, now=now,
        )
        self._fire_hook(task, event)
        return task

    def heartbeat(self, task_id: str) -> PipelineTask:
        """Update the heartbeat timestamp for an in-progress task."""
        task = self._get_task(task_id)
        task.last_heartbeat = self._now().isoformat()
        task.updated_at = task.last_heartbeat
        return task

    def submit(
        self,
        task_id: str,
        evidence: list[TaskEvidence],
        actor: Optional[str] = None,
    ) -> PipelineTask:
        """Agent submits evidence for review."""
        task = self._get_task(task_id)
        if actor is None:
            actor = task.assigned_agent or "agent"

        now = self._now()
        for e in evidence:
            e.submitted_at = now.isoformat()
        task.evidence.extend(evidence)

        event = execute_transition(
            task, PipelineStage.SUBMITTED, actor=actor, now=now,
            details={
                "evidence_count": len(evidence),
                "evidence_types": [e.evidence_type for e in evidence],
            },
        )
        self._fire_hook(task, event)
        return task

    def review(
        self,
        task_id: str,
        actor: str = "validator",
    ) -> PipelineTask:
        """Move submitted task to under_review."""
        task = self._get_task(task_id)
        event = execute_transition(
            task, PipelineStage.UNDER_REVIEW, actor=actor,
        )
        self._fire_hook(task, event)
        return task

    def approve(
        self,
        task_id: str,
        actor: str = "creator",
    ) -> PipelineTask:
        """Approve the submitted work."""
        task = self._get_task(task_id)
        now = self._now()
        task.approved_at = now.isoformat()

        event = execute_transition(
            task, PipelineStage.APPROVED, actor=actor, now=now,
        )
        self._fire_hook(task, event)
        return task

    def pay(
        self,
        task_id: str,
        tx_hash: str,
        actor: str = "payment_service",
    ) -> PipelineTask:
        """Record payment release."""
        task = self._get_task(task_id)
        now = self._now()
        task.payment_tx = tx_hash
        task.paid_at = now.isoformat()

        event = execute_transition(
            task, PipelineStage.PAID, actor=actor, now=now,
            details={"tx_hash": tx_hash, "amount_usd": task.bounty_usd},
        )
        self.state.total_paid_usd += task.bounty_usd
        self._fire_hook(task, event)
        return task

    def rate(
        self,
        task_id: str,
        agent_rating: Optional[float] = None,
        creator_rating: Optional[float] = None,
        actor: str = "reputation_service",
    ) -> PipelineTask:
        """Record bidirectional reputation ratings."""
        task = self._get_task(task_id)
        if agent_rating is not None:
            task.agent_rating = agent_rating
        if creator_rating is not None:
            task.creator_rating = creator_rating

        event = execute_transition(
            task, PipelineStage.RATED, actor=actor,
            details={
                "agent_rating": agent_rating,
                "creator_rating": creator_rating,
            },
        )
        self._fire_hook(task, event)
        return task

    def complete(
        self,
        task_id: str,
        actor: str = "pipeline",
    ) -> PipelineTask:
        """Mark task as fully completed (terminal state)."""
        task = self._get_task(task_id)
        event = execute_transition(
            task, PipelineStage.COMPLETED, actor=actor,
        )
        self.state.total_completed += 1
        self._fire_hook(task, event)
        return task

    def fail(
        self,
        task_id: str,
        reason: str,
        actor: str = "system",
    ) -> PipelineTask:
        """Mark task as failed with reason."""
        task = self._get_task(task_id)
        task.failure_reason = reason

        event = execute_transition(
            task, PipelineStage.FAILED, actor=actor,
            details={"reason": reason},
        )
        self.state.total_failed += 1
        self._fire_hook(task, event)
        return task

    def expire(
        self,
        task_id: str,
        actor: str = "sla_monitor",
    ) -> PipelineTask:
        """Mark task as expired (TTL exceeded)."""
        task = self._get_task(task_id)

        event = execute_transition(
            task, PipelineStage.EXPIRED, actor=actor,
            details={"last_stage": task.stage.value},
        )
        self.state.total_expired += 1
        self._fire_hook(task, event)
        return task

    def dispute(
        self,
        task_id: str,
        reason: str,
        actor: str = "agent",
    ) -> PipelineTask:
        """Raise a dispute on an in-progress or under-review task."""
        task = self._get_task(task_id)
        task.dispute_reason = reason

        event = execute_transition(
            task, PipelineStage.DISPUTED, actor=actor,
            details={"reason": reason},
        )
        self._fire_hook(task, event)
        return task

    def reject_offer(
        self,
        task_id: str,
        actor: Optional[str] = None,
    ) -> PipelineTask:
        """Agent rejects the offer — return to EVALUATED for re-matching.

        If max_offer_attempts exceeded, the task fails.
        """
        task = self._get_task(task_id)
        if actor is None:
            actor = task.assigned_agent or "agent"

        if task.offer_attempts >= task.max_offer_attempts:
            return self.fail(task_id, reason="All offer attempts exhausted", actor="pipeline")

        # Clear assignment and go back to EVALUATED
        old_agent = task.assigned_agent
        task.assigned_agent = None

        event = execute_transition(
            task, PipelineStage.EVALUATED, actor=actor,
            details={"rejected_by": old_agent, "attempt": task.offer_attempts},
        )
        self._fire_hook(task, event)
        return task

    # --- Queries ---

    def get_task(self, task_id: str) -> Optional[PipelineTask]:
        """Get a task by ID, or None if not found."""
        return self.state.tasks.get(task_id)

    def _get_task(self, task_id: str) -> PipelineTask:
        """Get a task by ID, raising KeyError if not found."""
        task = self.state.tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found in pipeline")
        return task

    def check_slas(self, now: Optional[datetime] = None) -> list[SLAViolation]:
        """Check for SLA violations across all active tasks."""
        return check_sla_violations(self.state, self.slas, now)

    def pipeline_summary(self) -> dict:
        """Generate a summary of the pipeline state."""
        stage_counts: dict[str, int] = {}
        for task in self.state.tasks.values():
            stage_counts[task.stage.value] = stage_counts.get(task.stage.value, 0) + 1

        active = self.state.active_tasks()
        total_active_bounty = sum(t.bounty_usd for t in active)

        return {
            "total_tasks": len(self.state.tasks),
            "active_tasks": len(active),
            "stage_counts": stage_counts,
            "total_discovered": self.state.total_discovered,
            "total_completed": self.state.total_completed,
            "total_failed": self.state.total_failed,
            "total_expired": self.state.total_expired,
            "total_paid_usd": self.state.total_paid_usd,
            "active_bounty_usd": total_active_bounty,
            "completion_rate": (
                self.state.total_completed / max(self.state.total_discovered, 1)
            ),
            "last_cycle_at": self.state.last_cycle_at,
        }

    def agent_workload(self) -> dict[str, dict]:
        """Get workload summary per agent."""
        workloads: dict[str, dict] = {}
        for task in self.state.active_tasks():
            agent = task.assigned_agent
            if agent is None:
                continue
            if agent not in workloads:
                workloads[agent] = {"active": 0, "total_bounty": 0.0, "tasks": []}
            workloads[agent]["active"] += 1
            workloads[agent]["total_bounty"] += task.bounty_usd
            workloads[agent]["tasks"].append({
                "task_id": task.task_id,
                "title": task.title,
                "stage": task.stage.value,
            })
        return workloads

    # --- Funnel Analysis ---

    def funnel_analysis(self) -> dict:
        """Analyze the task funnel: how many tasks make it through each stage.

        Returns counts and conversion rates between stages.
        """
        # Count how many tasks have ever been in each stage (via events)
        stage_seen: dict[str, int] = {}
        for task in self.state.tasks.values():
            seen_stages = set()
            # Initial stage
            seen_stages.add(PipelineStage.DISCOVERED.value)
            for event in task.events:
                seen_stages.add(event.to_stage)
            for stage_name in seen_stages:
                stage_seen[stage_name] = stage_seen.get(stage_name, 0) + 1

        # Compute conversion rates between sequential stages
        stage_order = [
            "discovered", "evaluated", "offered", "accepted",
            "in_progress", "submitted", "under_review", "approved",
            "paid", "rated", "completed",
        ]

        conversions = []
        for i in range(len(stage_order) - 1):
            from_stage = stage_order[i]
            to_stage = stage_order[i + 1]
            from_count = stage_seen.get(from_stage, 0)
            to_count = stage_seen.get(to_stage, 0)
            rate = to_count / from_count if from_count > 0 else 0.0
            conversions.append({
                "from": from_stage,
                "to": to_stage,
                "from_count": from_count,
                "to_count": to_count,
                "rate": rate,
            })

        return {
            "stage_counts": stage_seen,
            "conversions": conversions,
            "terminal": {
                "completed": stage_seen.get("completed", 0),
                "failed": stage_seen.get("failed", 0),
                "expired": stage_seen.get("expired", 0),
                "disputed": stage_seen.get("disputed", 0),
            },
        }

    # --- Batch Operations ---

    def expire_stale_tasks(
        self,
        now: Optional[datetime] = None,
    ) -> list[str]:
        """Expire tasks that have exceeded critical SLA thresholds.

        Only expires tasks in DISCOVERED or OFFERED stages
        (in-progress tasks get stall warnings instead).
        Returns list of expired task IDs.
        """
        if now is None:
            now = self._now()

        expirable_stages = {PipelineStage.DISCOVERED, PipelineStage.EVALUATED, PipelineStage.OFFERED}
        expired_ids = []

        for task in self.state.active_tasks():
            if task.stage not in expirable_stages:
                continue

            sla = self.slas.get(task.stage)
            if sla is None:
                continue

            if not task.stage_entered_at:
                continue

            entered = datetime.fromisoformat(task.stage_entered_at)
            # Expire at 3x the SLA (generous threshold)
            if (now - entered) > sla * 3:
                try:
                    self.expire(task.task_id)
                    expired_ids.append(task.task_id)
                except TransitionError:
                    pass

        return expired_ids


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_pipeline_state(state: PipelineState, path: Path) -> None:
    """Save pipeline state to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(f"Pipeline state saved: {len(state.tasks)} tasks → {path}")


def load_pipeline_state(path: Path) -> PipelineState:
    """Load pipeline state from JSON."""
    if not path.exists():
        return PipelineState()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = PipelineState()
        state.total_discovered = data.get("total_discovered", 0)
        state.total_completed = data.get("total_completed", 0)
        state.total_failed = data.get("total_failed", 0)
        state.total_expired = data.get("total_expired", 0)
        state.total_paid_usd = data.get("total_paid_usd", 0.0)
        state.last_cycle_at = data.get("last_cycle_at")

        for tid, tdata in data.get("tasks", {}).items():
            task = PipelineTask(
                task_id=tdata["task_id"],
                stage=PipelineStage(tdata.get("stage", "discovered")),
                title=tdata.get("title", ""),
                description=tdata.get("description", ""),
                category=tdata.get("category", ""),
                bounty_usd=tdata.get("bounty_usd", 0.0),
                payment_network=tdata.get("payment_network", "base"),
                creator_wallet=tdata.get("creator_wallet", ""),
                assigned_agent=tdata.get("assigned_agent"),
                offer_attempts=tdata.get("offer_attempts", 0),
                max_offer_attempts=tdata.get("max_offer_attempts", 3),
                started_at=tdata.get("started_at"),
                last_heartbeat=tdata.get("last_heartbeat"),
                approved_at=tdata.get("approved_at"),
                payment_tx=tdata.get("payment_tx"),
                paid_at=tdata.get("paid_at"),
                agent_rating=tdata.get("agent_rating"),
                creator_rating=tdata.get("creator_rating"),
                created_at=tdata.get("created_at", ""),
                updated_at=tdata.get("updated_at", ""),
                stage_entered_at=tdata.get("stage_entered_at", ""),
                retry_count=tdata.get("retry_count", 0),
                failure_reason=tdata.get("failure_reason"),
                dispute_reason=tdata.get("dispute_reason"),
            )

            # Restore rankings
            for rdata in tdata.get("rankings", []):
                task.rankings.append(AgentRanking(
                    agent_name=rdata["agent_name"],
                    score=rdata["score"],
                    match_mode=rdata.get("match_mode", "enhanced"),
                    factors=rdata.get("factors", {}),
                ))

            # Restore evidence
            for edata in tdata.get("evidence", []):
                task.evidence.append(TaskEvidence(
                    evidence_type=edata["evidence_type"],
                    content_url=edata.get("content_url"),
                    content_text=edata.get("content_text"),
                    metadata=edata.get("metadata", {}),
                    submitted_at=edata.get("submitted_at"),
                ))

            # Restore events
            for evdata in tdata.get("events", []):
                task.events.append(PipelineEvent(
                    event_id=evdata["event_id"],
                    task_id=evdata["task_id"],
                    timestamp=evdata["timestamp"],
                    from_stage=evdata.get("from_stage"),
                    to_stage=evdata["to_stage"],
                    actor=evdata.get("actor", "system"),
                    details=evdata.get("details", {}),
                ))

            state.tasks[tid] = task

        logger.info(f"Pipeline state loaded: {len(state.tasks)} tasks from {path}")
        return state

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to load pipeline state: {e}")
        return PipelineState()


# ---------------------------------------------------------------------------
# IRC Notification Formatter
# ---------------------------------------------------------------------------

def format_pipeline_notification(task: PipelineTask, event: PipelineEvent) -> Optional[str]:
    """Format an IRC notification for a pipeline event.

    Returns None if the event doesn't warrant a notification.
    """
    stage = event.to_stage

    if stage == PipelineStage.OFFERED.value:
        agent = event.details.get("agent", "?")
        score = event.details.get("score", 0)
        return (
            f"📋 {agent}: nuevo task → '{task.title[:40]}' "
            f"(${task.bounty_usd:.2f}, match {score:.0%}). ¿Lo tomas?"
        )

    if stage == PipelineStage.ACCEPTED.value:
        return f"✅ {task.assigned_agent} aceptó '{task.title[:40]}'. A darle."

    if stage == PipelineStage.SUBMITTED.value:
        count = event.details.get("evidence_count", 0)
        return (
            f"📤 {task.assigned_agent} entregó evidencia para '{task.title[:40]}' "
            f"({count} archivos). Pendiente revisión."
        )

    if stage == PipelineStage.APPROVED.value:
        return f"👍 '{task.title[:40]}' aprobado. Procesando pago..."

    if stage == PipelineStage.PAID.value:
        tx = event.details.get("tx_hash", "")[:12]
        return (
            f"💰 Pago liberado para '{task.title[:40]}': "
            f"${task.bounty_usd:.2f} USDC → {task.assigned_agent} (tx: {tx}...)"
        )

    if stage == PipelineStage.COMPLETED.value:
        return f"🎉 Task completo: '{task.title[:40]}' por {task.assigned_agent}"

    if stage == PipelineStage.FAILED.value:
        reason = event.details.get("reason", "unknown")
        return f"❌ Task falló: '{task.title[:40]}' — {reason}"

    if stage == PipelineStage.DISPUTED.value:
        reason = event.details.get("reason", "unknown")
        return f"⚖️ Disputa en '{task.title[:40]}': {reason}"

    return None


# ---------------------------------------------------------------------------
# Pipeline Analytics
# ---------------------------------------------------------------------------

def compute_pipeline_metrics(state: PipelineState) -> dict:
    """Compute aggregate pipeline metrics."""
    tasks = list(state.tasks.values())
    if not tasks:
        return {"empty": True}

    # Timing analysis (for completed tasks)
    completed = [t for t in tasks if t.stage == PipelineStage.COMPLETED]
    durations = []
    for t in completed:
        if t.created_at and t.events:
            created = datetime.fromisoformat(t.created_at)
            last_event = datetime.fromisoformat(t.events[-1].timestamp)
            dur = (last_event - created).total_seconds() / 3600  # hours
            durations.append(dur)

    avg_duration_hours = sum(durations) / len(durations) if durations else 0

    # Agent efficiency
    agent_stats: dict[str, dict] = {}
    for t in tasks:
        if t.assigned_agent:
            if t.assigned_agent not in agent_stats:
                agent_stats[t.assigned_agent] = {"completed": 0, "failed": 0, "total_earned": 0.0}
            if t.stage == PipelineStage.COMPLETED:
                agent_stats[t.assigned_agent]["completed"] += 1
                agent_stats[t.assigned_agent]["total_earned"] += t.bounty_usd
            elif t.stage == PipelineStage.FAILED:
                agent_stats[t.assigned_agent]["failed"] += 1

    # Category distribution
    category_counts: dict[str, int] = {}
    for t in tasks:
        cat = t.category or "uncategorized"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Bounty distribution
    bounties = [t.bounty_usd for t in tasks if t.bounty_usd > 0]
    avg_bounty = sum(bounties) / len(bounties) if bounties else 0
    max_bounty = max(bounties) if bounties else 0

    return {
        "total_tasks": len(tasks),
        "active_tasks": len(state.active_tasks()),
        "completed": len(completed),
        "failed": state.total_failed,
        "expired": state.total_expired,
        "avg_duration_hours": round(avg_duration_hours, 2),
        "total_paid_usd": state.total_paid_usd,
        "avg_bounty_usd": round(avg_bounty, 2),
        "max_bounty_usd": round(max_bounty, 2),
        "agent_stats": agent_stats,
        "category_distribution": category_counts,
        "completion_rate": len(completed) / max(len(tasks), 1),
    }
