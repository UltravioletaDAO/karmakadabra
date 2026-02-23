#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Karma Kadabra V2 -- Swarm Coordinator Simulation Test

Simulates a 24-agent swarm (6 system + 18 community) competing for 6 tasks.
Tests coordinator logic: task creation, application, assignment, completion,
and bidirectional reputation rating.

This is a SIMULATION test -- it uses mock data, NOT real API calls.
Tests the coordinator LOGIC, not the API.

Usage:
    python scripts/kk/tests/test_swarm_coordinator.py
    python scripts/kk/tests/test_swarm_coordinator.py --verbose
    pytest scripts/kk/tests/test_swarm_coordinator.py -v
"""

import argparse
import asyncio
import random
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Load dotenv (best-effort -- not required for simulation)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    _project_root = Path(__file__).parent.parent.parent.parent
    load_dotenv(_project_root / ".env.local")
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Agent model
# ---------------------------------------------------------------------------
@dataclass
class Agent:
    """Represents an agent in the swarm."""

    name: str
    wallet: str
    role: str  # "system" or "community"
    skills: List[str] = field(default_factory=list)
    reputation_score: float = 50.0
    tasks_created: int = 0
    tasks_completed: int = 0
    tasks_applied: int = 0
    ratings_given: int = 0
    ratings_received: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "wallet": self.wallet,
            "role": self.role,
            "reputation_score": round(self.reputation_score, 2),
            "tasks_created": self.tasks_created,
            "tasks_completed": self.tasks_completed,
            "tasks_applied": self.tasks_applied,
            "ratings_given": self.ratings_given,
            "ratings_received": self.ratings_received,
        }


@dataclass
class Task:
    """Represents a task in the simulation."""

    id: str
    title: str
    creator: str  # agent name
    category: str
    bounty_usd: float
    required_skills: List[str] = field(default_factory=list)
    status: str = "published"
    applicants: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    submission_id: Optional[str] = None


@dataclass
class Rating:
    """Represents a bidirectional reputation rating."""

    from_agent: str
    to_agent: str
    score: int  # 1-5
    role: str  # "agent_rates_worker" or "worker_rates_agent"


@dataclass
class SimulationResults:
    """Collects simulation outcomes."""

    tasks_created: int = 0
    applications_received: int = 0
    assignments_made: int = 0
    tasks_completed: int = 0
    ratings_submitted: int = 0
    rejected_applications: int = 0
    reputation_changes: Dict[str, Dict[str, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

SYSTEM_AGENTS = [
    Agent(
        name="kk-coordinator",
        wallet="0x0001000000000000000000000000000000000001",
        role="system",
        skills=["coordination", "task_routing", "monitoring"],
    ),
    Agent(
        name="kk-auditor",
        wallet="0x0002000000000000000000000000000000000002",
        role="system",
        skills=["auditing", "compliance", "verification"],
    ),
    Agent(
        name="kk-treasurer",
        wallet="0x0003000000000000000000000000000000000003",
        role="system",
        skills=["accounting", "payments", "treasury"],
    ),
    Agent(
        name="kk-recruiter",
        wallet="0x0004000000000000000000000000000000000004",
        role="system",
        skills=["recruiting", "onboarding", "community"],
    ),
    Agent(
        name="kk-trainer",
        wallet="0x0005000000000000000000000000000000000005",
        role="system",
        skills=["training", "documentation", "tutorials"],
    ),
    Agent(
        name="kk-archivist",
        wallet="0x0006000000000000000000000000000000000006",
        role="system",
        skills=["archiving", "indexing", "search"],
    ),
]

# 18 community agents with diverse skills
COMMUNITY_AGENTS = [
    Agent(
        name="alpha-dev",
        wallet="0x1001000000000000000000000000000000001001",
        role="community",
        skills=["python", "solidity", "testing"],
    ),
    Agent(
        name="beta-designer",
        wallet="0x1002000000000000000000000000000000001002",
        role="community",
        skills=["design", "ui", "branding"],
    ),
    Agent(
        name="gamma-writer",
        wallet="0x1003000000000000000000000000000000001003",
        role="community",
        skills=["writing", "documentation", "translation"],
    ),
    Agent(
        name="delta-trader",
        wallet="0x1004000000000000000000000000000000001004",
        role="community",
        skills=["trading", "defi", "analytics"],
    ),
    Agent(
        name="epsilon-security",
        wallet="0x1005000000000000000000000000000000001005",
        role="community",
        skills=["security", "auditing", "penetration_testing"],
    ),
    Agent(
        name="zeta-infra",
        wallet="0x1006000000000000000000000000000000001006",
        role="community",
        skills=["devops", "terraform", "monitoring"],
    ),
    Agent(
        name="eta-researcher",
        wallet="0x1007000000000000000000000000000000001007",
        role="community",
        skills=["research", "analytics", "data_science"],
    ),
    Agent(
        name="theta-marketer",
        wallet="0x1008000000000000000000000000000000001008",
        role="community",
        skills=["marketing", "community", "social_media"],
    ),
    Agent(
        name="iota-translator",
        wallet="0x1009000000000000000000000000000000001009",
        role="community",
        skills=["translation", "writing", "localization"],
    ),
    Agent(
        name="kappa-tester",
        wallet="0x100a000000000000000000000000000000000100a",
        role="community",
        skills=["testing", "qa", "automation"],
    ),
    Agent(
        name="lambda-artist",
        wallet="0x100b000000000000000000000000000000000100b",
        role="community",
        skills=["design", "nft", "creative"],
    ),
    Agent(
        name="mu-educator",
        wallet="0x100c000000000000000000000000000000000100c",
        role="community",
        skills=["training", "tutorials", "mentoring"],
    ),
    Agent(
        name="nu-analyst",
        wallet="0x100d000000000000000000000000000000000100d",
        role="community",
        skills=["analytics", "reporting", "data_science"],
    ),
    Agent(
        name="xi-builder",
        wallet="0x100e000000000000000000000000000000000100e",
        role="community",
        skills=["solidity", "defi", "smart_contracts"],
    ),
    Agent(
        name="omicron-ops",
        wallet="0x100f000000000000000000000000000000000100f",
        role="community",
        skills=["devops", "monitoring", "incident_response"],
    ),
    Agent(
        name="pi-modeler",
        wallet="0x1010000000000000000000000000000000001010",
        role="community",
        skills=["ai", "machine_learning", "python"],
    ),
    Agent(
        name="rho-legal",
        wallet="0x1011000000000000000000000000000000001011",
        role="community",
        skills=["compliance", "legal", "documentation"],
    ),
    Agent(
        name="sigma-growth",
        wallet="0x1012000000000000000000000000000000001012",
        role="community",
        skills=["marketing", "growth", "partnerships"],
    ),
]

# 6 tasks -- one created by each system agent
TASK_DEFINITIONS = [
    {
        "creator": "kk-coordinator",
        "title": "[KK] Audit swarm heartbeat logs for anomalies",
        "category": "simple_action",
        "bounty_usd": 0.10,
        "required_skills": ["monitoring", "analytics"],
    },
    {
        "creator": "kk-auditor",
        "title": "[KK] Verify on-chain fee distribution accuracy",
        "category": "knowledge_access",
        "bounty_usd": 0.15,
        "required_skills": ["auditing", "defi"],
    },
    {
        "creator": "kk-treasurer",
        "title": "[KK] Generate monthly treasury report",
        "category": "digital_physical",
        "bounty_usd": 0.12,
        "required_skills": ["accounting", "reporting"],
    },
    {
        "creator": "kk-recruiter",
        "title": "[KK] Write onboarding guide for new agents",
        "category": "knowledge_access",
        "bounty_usd": 0.10,
        "required_skills": ["writing", "documentation"],
    },
    {
        "creator": "kk-trainer",
        "title": "[KK] Create tutorial for soul fusion setup",
        "category": "digital_physical",
        "bounty_usd": 0.10,
        "required_skills": ["tutorials", "training"],
    },
    {
        "creator": "kk-archivist",
        "title": "[KK] Index and tag last week IRC transcripts",
        "category": "simple_action",
        "bounty_usd": 0.10,
        "required_skills": ["indexing", "search"],
    },
]


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------


def _compute_skill_match(agent: Agent, required_skills: List[str]) -> float:
    """Compute skill match score between agent and task requirements."""
    if not required_skills:
        return 0.1

    matches = sum(1 for skill in required_skills if skill in agent.skills)
    if matches == 0:
        # Any KK community agent gets a baseline score for KK tasks
        return 0.15
    return min(1.0, matches / len(required_skills))


def _apply_reputation_change(agent: Agent, rating: int) -> float:
    """Apply a reputation change from a 1-5 rating. Returns delta."""
    # Simple model: rating maps to delta (-5 to +5)
    # 1 star = -5, 2 = -2, 3 = 0, 4 = +2, 5 = +5
    delta_map = {1: -5.0, 2: -2.0, 3: 0.0, 4: 2.0, 5: 5.0}
    delta = delta_map.get(rating, 0.0)
    old_score = agent.reputation_score
    agent.reputation_score = max(0.0, min(100.0, agent.reputation_score + delta))
    return agent.reputation_score - old_score


async def simulate_swarm(verbose: bool = False) -> SimulationResults:
    """Run the full swarm simulation.

    Steps:
      1. Create 6 tasks (one per system agent)
      2. 18 community agents compete to apply (3 per task)
      3. 6 get assigned (first applicant wins), 12 don't
      4. All 6 assigned agents complete their tasks
      5. All pairs rate each other (agent->worker + worker->agent)
      6. Compute reputation leaderboard changes
    """
    results = SimulationResults()

    # Index agents by name
    all_agents: Dict[str, Agent] = {}
    for a in SYSTEM_AGENTS + COMMUNITY_AGENTS:
        all_agents[a.name] = a

    # Record initial reputation
    for name, agent in all_agents.items():
        results.reputation_changes[name] = {"before": agent.reputation_score}

    # -----------------------------------------------------------------------
    # Step 1: Create 6 tasks
    # -----------------------------------------------------------------------
    tasks: List[Task] = []
    for tdef in TASK_DEFINITIONS:
        task = Task(
            id=str(uuid.uuid4()),
            title=tdef["title"],
            creator=tdef["creator"],
            category=tdef["category"],
            bounty_usd=tdef["bounty_usd"],
            required_skills=tdef["required_skills"],
        )
        tasks.append(task)
        all_agents[task.creator].tasks_created += 1
        results.tasks_created += 1

        if verbose:
            print(
                f"  [CREATE] {task.creator} -> '{task.title}' (${task.bounty_usd:.2f})"
            )

    # -----------------------------------------------------------------------
    # Step 2: 18 community agents apply (3 per task, skill-matched)
    # -----------------------------------------------------------------------
    # Sort community agents by skill match for each task, pick top 3
    community = list(COMMUNITY_AGENTS)

    for task in tasks:
        # Score all community agents
        scored = []
        for agent in community:
            score = _compute_skill_match(agent, task.required_skills)
            scored.append((agent, score))

        # Sort by score descending, take top 3
        scored.sort(key=lambda x: (-x[1], x[0].name))
        applicants = scored[:3]

        for agent, score in applicants:
            task.applicants.append(agent.name)
            agent.tasks_applied += 1
            results.applications_received += 1

            if verbose:
                print(
                    f"  [APPLY]  {agent.name} -> '{task.title[:40]}' "
                    f"(score={score:.2f})"
                )

    # -----------------------------------------------------------------------
    # Step 3: Assign first applicant (highest skill match) to each task
    #         with deduplication — same agent cannot be assigned to multiple tasks
    # -----------------------------------------------------------------------
    assigned_agents: List[str] = []

    for task in tasks:
        if not task.applicants:
            if verbose:
                print(f"  [SKIP]   No applicants for '{task.title}'")
            continue

        # Pick highest-ranked applicant not already assigned to another task
        winner = None
        for applicant in task.applicants:
            if applicant not in assigned_agents:
                winner = applicant
                break
        if winner is None:
            # Fallback: all applicants already assigned elsewhere
            winner = task.applicants[0]

        task.assigned_to = winner
        task.status = "accepted"
        assigned_agents.append(winner)
        results.assignments_made += 1

        # The other applicants are rejected
        for rejected in task.applicants:
            if rejected != winner:
                results.rejected_applications += 1

        if verbose:
            others = [a for a in task.applicants if a != winner]
            print(f"  [ASSIGN] {winner} <- '{task.title[:40]}' (rejected: {others})")

    # Invariant: all assigned agents are unique
    assert len(set(assigned_agents)) == len(assigned_agents), (
        f"Deduplication failed: duplicate assignments in {assigned_agents}"
    )

    # -----------------------------------------------------------------------
    # Step 4: All 6 assigned agents complete their tasks
    # -----------------------------------------------------------------------
    for task in tasks:
        if not task.assigned_to:
            continue

        # Simulate submission + completion
        task.submission_id = str(uuid.uuid4())
        task.status = "completed"
        all_agents[task.assigned_to].tasks_completed += 1
        results.tasks_completed += 1

        if verbose:
            print(
                f"  [SUBMIT] {task.assigned_to} completed '{task.title[:40]}' "
                f"(sub={task.submission_id[:8]})"
            )

    # -----------------------------------------------------------------------
    # Step 5: Bidirectional ratings (agent rates worker + worker rates agent)
    # -----------------------------------------------------------------------
    ratings: List[Rating] = []

    for task in tasks:
        if task.status != "completed" or not task.assigned_to:
            continue

        creator = task.creator
        worker = task.assigned_to

        # Agent rates worker (4-5 stars for completed tasks)
        agent_rating = random.randint(4, 5)
        ratings.append(
            Rating(
                from_agent=creator,
                to_agent=worker,
                score=agent_rating,
                role="agent_rates_worker",
            )
        )
        delta = _apply_reputation_change(all_agents[worker], agent_rating)
        all_agents[creator].ratings_given += 1
        all_agents[worker].ratings_received += 1
        results.ratings_submitted += 1

        if verbose:
            print(
                f"  [RATE]   {creator} -> {worker}: "
                f"{agent_rating}/5 (rep delta={delta:+.1f})"
            )

        # Worker rates agent (3-5 stars, workers sometimes rate lower)
        worker_rating = random.randint(3, 5)
        ratings.append(
            Rating(
                from_agent=worker,
                to_agent=creator,
                score=worker_rating,
                role="worker_rates_agent",
            )
        )
        delta = _apply_reputation_change(all_agents[creator], worker_rating)
        all_agents[worker].ratings_given += 1
        all_agents[creator].ratings_received += 1
        results.ratings_submitted += 1

        if verbose:
            print(
                f"  [RATE]   {worker} -> {creator}: "
                f"{worker_rating}/5 (rep delta={delta:+.1f})"
            )

    # -----------------------------------------------------------------------
    # Step 6: Record final reputation
    # -----------------------------------------------------------------------
    for name, agent in all_agents.items():
        results.reputation_changes[name]["after"] = agent.reputation_score
        results.reputation_changes[name]["delta"] = round(
            agent.reputation_score - results.reputation_changes[name]["before"], 2
        )

    return results


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(results: SimulationResults, verbose: bool = False) -> None:
    """Print simulation summary."""
    print()
    print("=" * 64)
    print("  SWARM COORDINATOR SIMULATION SUMMARY")
    print("=" * 64)
    print()
    print(f"  Tasks created:          {results.tasks_created}")
    print(f"  Applications received:  {results.applications_received}")
    print(f"  Assignments made:       {results.assignments_made}")
    print(f"  Rejected applications:  {results.rejected_applications}")
    print(f"  Tasks completed:        {results.tasks_completed}")
    print(f"  Ratings submitted:      {results.ratings_submitted}")

    # Reputation changes
    print()
    print("-" * 64)
    print("  REPUTATION CHANGES")
    print("-" * 64)
    print(f"  {'Agent':<22s} {'Before':>8s} {'After':>8s} {'Delta':>8s}")
    print(f"  {'-' * 22} {'-' * 8} {'-' * 8} {'-' * 8}")

    # Sort by delta descending
    sorted_agents = sorted(
        results.reputation_changes.items(),
        key=lambda x: x[1].get("delta", 0),
        reverse=True,
    )

    for name, scores in sorted_agents:
        before = scores.get("before", 50.0)
        after = scores.get("after", 50.0)
        delta = scores.get("delta", 0.0)
        if delta != 0.0 or verbose:
            marker = ""
            if delta > 0:
                marker = " (+)"
            elif delta < 0:
                marker = " (-)"
            print(f"  {name:<22s} {before:>8.2f} {after:>8.2f} {delta:>+8.2f}{marker}")

    # Top 5 leaderboard
    print()
    print("-" * 64)
    print("  TOP 5 AGENTS BY REPUTATION")
    print("-" * 64)
    top5 = sorted_agents[:5]
    for rank, (name, scores) in enumerate(top5, 1):
        after = scores.get("after", 50.0)
        print(f"  #{rank}  {name:<22s}  {after:.2f}")

    print()
    print("=" * 64)
    print("  SIMULATION COMPLETE")
    print("=" * 64)


# ---------------------------------------------------------------------------
# Assertions (for pytest)
# ---------------------------------------------------------------------------


def validate_results(results: SimulationResults) -> List[str]:
    """Validate simulation invariants. Returns list of errors."""
    errors = []

    if results.tasks_created != 6:
        errors.append(f"Expected 6 tasks created, got {results.tasks_created}")

    if results.applications_received != 18:
        errors.append(f"Expected 18 applications, got {results.applications_received}")

    if results.assignments_made != 6:
        errors.append(f"Expected 6 assignments, got {results.assignments_made}")

    if results.rejected_applications != 12:
        errors.append(f"Expected 12 rejections, got {results.rejected_applications}")

    if results.tasks_completed != 6:
        errors.append(f"Expected 6 completions, got {results.tasks_completed}")

    if results.ratings_submitted != 12:
        errors.append(
            f"Expected 12 ratings (6 pairs x 2), got {results.ratings_submitted}"
        )

    # Verify that only agents who were rated have reputation changes
    agents_with_delta = [
        name
        for name, scores in results.reputation_changes.items()
        if scores.get("delta", 0.0) != 0.0
    ]
    if len(agents_with_delta) == 0:
        errors.append("No agents had reputation changes -- simulation may have failed")

    # Verify all reputation scores are within bounds
    for name, scores in results.reputation_changes.items():
        after = scores.get("after", 50.0)
        if after < 0 or after > 100:
            errors.append(f"Agent {name} has out-of-bounds reputation: {after}")

    return errors


# ---------------------------------------------------------------------------
# Pytest entrypoints
# ---------------------------------------------------------------------------


def test_swarm_simulation():
    """Pytest: run full swarm simulation and validate invariants."""
    # Use a fixed seed for reproducibility in tests
    random.seed(42)
    results = asyncio.run(simulate_swarm(verbose=False))
    errors = validate_results(results)
    assert not errors, f"Simulation invariants violated:\n" + "\n".join(
        f"  - {e}" for e in errors
    )


def test_tasks_created_by_system_agents():
    """Pytest: verify exactly 6 system agents create tasks."""
    random.seed(42)
    results = asyncio.run(simulate_swarm(verbose=False))
    assert results.tasks_created == 6


def test_three_applicants_per_task():
    """Pytest: verify 3 community agents apply per task (18 total)."""
    random.seed(42)
    results = asyncio.run(simulate_swarm(verbose=False))
    assert results.applications_received == 18


def test_one_assignment_per_task():
    """Pytest: verify exactly 1 agent assigned per task (6 total)."""
    random.seed(42)
    results = asyncio.run(simulate_swarm(verbose=False))
    assert results.assignments_made == 6


def test_bidirectional_ratings():
    """Pytest: verify 12 ratings (6 pairs x 2 directions)."""
    random.seed(42)
    results = asyncio.run(simulate_swarm(verbose=False))
    assert results.ratings_submitted == 12


def test_reputation_stays_in_bounds():
    """Pytest: verify all reputation scores stay within [0, 100]."""
    random.seed(42)
    results = asyncio.run(simulate_swarm(verbose=False))
    for name, scores in results.reputation_changes.items():
        after = scores.get("after", 50.0)
        assert 0.0 <= after <= 100.0, f"{name} has reputation {after} out of bounds"


def test_rejected_applications_count():
    """Pytest: 18 applications - 6 assignments = 12 rejections."""
    random.seed(42)
    results = asyncio.run(simulate_swarm(verbose=False))
    assert results.rejected_applications == 12


def test_no_system_agent_self_assignment():
    """Pytest: system agents should not be assigned their own tasks."""
    random.seed(42)
    # The simulation only uses community agents as applicants
    results = asyncio.run(simulate_swarm(verbose=False))
    # System agents should have 0 tasks_applied
    for agent in SYSTEM_AGENTS:
        assert agent.tasks_applied == 0, (
            f"System agent {agent.name} should not apply to tasks"
        )


# ---------------------------------------------------------------------------
# Main (standalone execution)
# ---------------------------------------------------------------------------


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="KK Swarm Coordinator Simulation Test (24 agents, 6 tasks)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show step-by-step details"
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print()
    print("=" * 64)
    print("  KARMA KADABRA V2 -- SWARM COORDINATOR SIMULATION")
    print("=" * 64)
    print(f"  Time:              {now}")
    print(f"  System agents:     {len(SYSTEM_AGENTS)}")
    print(f"  Community agents:  {len(COMMUNITY_AGENTS)}")
    print(f"  Total agents:      {len(SYSTEM_AGENTS) + len(COMMUNITY_AGENTS)}")
    print(f"  Tasks to create:   {len(TASK_DEFINITIONS)}")
    print(f"  Applicants/task:   3")
    print(f"  Mode:              simulation (no API calls)")
    print()

    # Use random seed based on current minute for varied but reproducible runs
    seed = int(datetime.now(timezone.utc).strftime("%Y%m%d%H%M"))
    random.seed(seed)

    results = await simulate_swarm(verbose=args.verbose)

    print_summary(results, verbose=args.verbose)

    # Validate
    errors = validate_results(results)
    if errors:
        print("\n  VALIDATION ERRORS:")
        for err in errors:
            print(f"    - {err}")
        return 1

    print(f"\n  All invariants validated -- simulation PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
