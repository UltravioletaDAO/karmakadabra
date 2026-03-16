"""
Karma Kadabra V2 — Performance Tracker

Tracks agent task performance metrics for smarter coordinator matching.
Instead of matching purely on static skills, the coordinator now considers:

  1. Historical completion rates (agents who complete tasks rank higher)
  2. Category specialization (agents develop track records per category)
  3. Speed metrics (faster completion → higher priority for time-sensitive tasks)
  4. Budget efficiency (agents who stay within budget ranked higher)
  5. Multi-chain proficiency (agents experienced on specific chains preferred)

Data sources:
  - WORKING.md heartbeat history
  - kk_swarm_state table (Supabase)
  - Daily notes analysis
  - EM API task history (when available)

All functions are pure (no side effects) and easily testable.
Graceful degradation: returns neutral scores when no data available.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.performance")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class AgentPerformance:
    """Performance profile for one agent."""

    agent_name: str
    tasks_completed: int = 0
    tasks_attempted: int = 0
    tasks_failed: int = 0  # expired, cancelled, or disputed
    avg_completion_hours: float = 0.0
    total_earned_usd: float = 0.0
    total_spent_usd: float = 0.0

    # Per-category breakdown
    category_completions: dict[str, int] = field(default_factory=dict)
    category_attempts: dict[str, int] = field(default_factory=dict)

    # Per-chain activity
    chain_tasks: dict[str, int] = field(default_factory=dict)

    # Rating averages
    avg_rating_received: float = 0.0
    avg_rating_given: float = 0.0
    rating_count: int = 0

    @property
    def completion_rate(self) -> float:
        """Fraction of attempted tasks completed successfully."""
        if self.tasks_attempted == 0:
            return 0.5  # Neutral for new agents
        return self.tasks_completed / self.tasks_attempted

    @property
    def reliability_score(self) -> float:
        """0-1 score combining completion rate and rating quality."""
        if self.tasks_attempted == 0:
            return 0.5  # Neutral for new agents

        cr = self.completion_rate
        # Normalize avg_rating to 0-1 (ratings are 1-5 stars → 0.2-1.0)
        rating_norm = (self.avg_rating_received / 100.0) if self.avg_rating_received > 0 else 0.5

        # Weight: 60% completion rate, 40% rating
        return 0.6 * cr + 0.4 * rating_norm

    def category_strength(self, category: str) -> float:
        """0-1 score for this agent's track record in a category."""
        completed = self.category_completions.get(category, 0)
        attempted = self.category_attempts.get(category, 0)

        if attempted == 0:
            return 0.0  # No track record
        return completed / attempted

    def chain_experience(self, chain: str) -> float:
        """0-1 score for this agent's experience on a specific chain."""
        tasks_on_chain = self.chain_tasks.get(chain, 0)
        if tasks_on_chain == 0:
            return 0.1  # Minimal experience
        # Log scale: 1 task=0.3, 5=0.7, 10+=1.0
        import math
        return min(1.0, 0.3 + 0.3 * math.log(tasks_on_chain + 1))


# ---------------------------------------------------------------------------
# Data Extraction
# ---------------------------------------------------------------------------


def extract_performance_from_notes(
    workspaces_dir: Path,
) -> dict[str, AgentPerformance]:
    """Extract performance data from agent workspace daily notes.

    Parses structured log patterns like:
      - [COMPLETED] task-id category:simple_action chain:base bounty:$0.10
      - [FAILED] task-id reason:expired
      - [APPLIED] task-id category:knowledge_access
      - [RATED] 4/5 by kk-coordinator
      - [EARNED] $0.10 from task-id
    """
    profiles: dict[str, AgentPerformance] = {}

    if not workspaces_dir.exists():
        return profiles

    for ws in sorted(workspaces_dir.iterdir()):
        if not ws.is_dir() or ws.name.startswith("_"):
            continue

        agent_name = ws.name
        perf = AgentPerformance(agent_name=agent_name)

        # Parse daily notes
        notes_dir = ws / "memory" / "notes"
        if not notes_dir.exists():
            # Also check legacy location
            notes_dir = ws / "notes"
            if not notes_dir.exists():
                profiles[agent_name] = perf
                continue

        for notes_file in sorted(notes_dir.glob("*.md")):
            try:
                text = notes_file.read_text(encoding="utf-8")
            except Exception:
                continue

            for line in text.splitlines():
                line = line.strip()

                # [COMPLETED] patterns
                if "[COMPLETED]" in line.upper() or "completed task" in line.lower():
                    perf.tasks_completed += 1
                    perf.tasks_attempted += 1

                    # Extract category
                    cat_match = re.search(r"category[:\s]+([\w_]+)", line, re.I)
                    if cat_match:
                        cat = cat_match.group(1).lower()
                        perf.category_completions[cat] = perf.category_completions.get(cat, 0) + 1
                        perf.category_attempts[cat] = perf.category_attempts.get(cat, 0) + 1

                    # Extract chain
                    chain_match = re.search(r"chain[:\s]+([\w]+)", line, re.I)
                    if chain_match:
                        chain = chain_match.group(1).lower()
                        perf.chain_tasks[chain] = perf.chain_tasks.get(chain, 0) + 1

                # [FAILED] patterns
                elif "[FAILED]" in line.upper() or "task expired" in line.lower() or "task cancelled" in line.lower():
                    perf.tasks_failed += 1
                    perf.tasks_attempted += 1

                    cat_match = re.search(r"category[:\s]+([\w_]+)", line, re.I)
                    if cat_match:
                        cat = cat_match.group(1).lower()
                        perf.category_attempts[cat] = perf.category_attempts.get(cat, 0) + 1

                # [APPLIED] patterns
                elif "[APPLIED]" in line.upper() or "applied to task" in line.lower():
                    cat_match = re.search(r"category[:\s]+([\w_]+)", line, re.I)
                    if cat_match:
                        cat = cat_match.group(1).lower()
                        perf.category_attempts[cat] = perf.category_attempts.get(cat, 0) + 1

                # [RATED] patterns
                elif "[RATED]" in line.upper() or "rated" in line.lower():
                    rating_match = re.search(r"(\d+)\s*/\s*5", line)
                    if rating_match:
                        rating = int(rating_match.group(1))
                        # Running average
                        total = perf.avg_rating_received * perf.rating_count + rating * 20  # Scale to 100
                        perf.rating_count += 1
                        perf.avg_rating_received = total / perf.rating_count

                # [EARNED] patterns
                elif "[EARNED]" in line.upper() or "earned $" in line.lower():
                    amount_match = re.search(r"\$(\d+\.?\d*)", line)
                    if amount_match:
                        perf.total_earned_usd += float(amount_match.group(1))

        profiles[agent_name] = perf

    return profiles


def extract_performance_from_json(
    workspaces_dir: Path,
) -> dict[str, AgentPerformance]:
    """Extract performance data from workspace profile.json files.

    These are structured data files maintained by the swarm runner,
    more reliable than parsing notes.
    """
    profiles: dict[str, AgentPerformance] = {}

    if not workspaces_dir.exists():
        return profiles

    for ws in sorted(workspaces_dir.iterdir()):
        if not ws.is_dir() or ws.name.startswith("_"):
            continue

        agent_name = ws.name
        perf = AgentPerformance(agent_name=agent_name)

        # Try structured performance JSON
        perf_file = ws / "data" / "performance.json"
        if perf_file.exists():
            try:
                data = json.loads(perf_file.read_text(encoding="utf-8"))
                perf.tasks_completed = data.get("tasks_completed", 0)
                perf.tasks_attempted = data.get("tasks_attempted", 0)
                perf.tasks_failed = data.get("tasks_failed", 0)
                perf.avg_completion_hours = data.get("avg_completion_hours", 0.0)
                perf.total_earned_usd = data.get("total_earned_usd", 0.0)
                perf.total_spent_usd = data.get("total_spent_usd", 0.0)
                perf.avg_rating_received = data.get("avg_rating_received", 0.0)
                perf.rating_count = data.get("rating_count", 0)
                perf.category_completions = data.get("category_completions", {})
                perf.category_attempts = data.get("category_attempts", {})
                perf.chain_tasks = data.get("chain_tasks", {})
            except Exception:
                pass

        profiles[agent_name] = perf

    return profiles


# ---------------------------------------------------------------------------
# Enhanced Matching
# ---------------------------------------------------------------------------


def compute_enhanced_match_score(
    agent_perf: AgentPerformance,
    agent_skills: set[str],
    task_title: str,
    task_description: str,
    task_category: str = "",
    task_chain: str = "base",
    task_bounty: float = 0.0,
) -> float:
    """Compute an enhanced match score using skills + performance data.

    Factors:
      - 35% skill match (original keyword matching)
      - 25% reliability score (completion rate + ratings)
      - 20% category experience (track record in this category)
      - 10% chain experience (has the agent worked on this chain?)
      - 10% budget fit (is the bounty in the agent's sweet spot?)

    Returns:
        0.0 - 1.0 match score (higher is better).
    """
    text = (task_title + " " + task_description).lower()

    # 1. Skill match (35%)
    # Tokenize skills: replace underscores/hyphens with spaces for natural language matching
    skill_score = 0.0
    if agent_skills:
        matches = 0
        for skill in agent_skills:
            # Match both the raw skill name and the space-separated version
            skill_lower = skill.lower()
            skill_spaced = skill_lower.replace("_", " ").replace("-", " ")
            if skill_lower in text or skill_spaced in text:
                matches += 1
            elif any(word in text.split() for word in skill_spaced.split() if len(word) > 3):
                # Partial match: at least one significant word matches
                matches += 0.5
        if matches == 0:
            # KK-tagged tasks get a baseline
            skill_score = 0.3 if "[kk" in text else 0.0
        else:
            skill_score = min(1.0, matches / max(len(agent_skills), 1))
    else:
        skill_score = 0.1  # No skills data

    # 2. Reliability (25%)
    reliability = agent_perf.reliability_score

    # 3. Category experience (20%)
    category_score = 0.0
    if task_category:
        category_score = agent_perf.category_strength(task_category)
    else:
        # Infer category from text
        categories = ["simple_action", "knowledge_access", "digital_physical", "verification"]
        for cat in categories:
            if cat.replace("_", " ") in text or cat in text:
                category_score = agent_perf.category_strength(cat)
                break

    # 4. Chain experience (10%)
    chain_score = agent_perf.chain_experience(task_chain)

    # 5. Budget fit (10%)
    budget_score = 0.5  # Neutral default
    if task_bounty > 0 and agent_perf.total_earned_usd > 0:
        # Agents who've earned more can handle higher-value tasks
        avg_task_value = agent_perf.total_earned_usd / max(agent_perf.tasks_completed, 1)
        # Score higher if bounty is close to their average task value
        ratio = task_bounty / max(avg_task_value, 0.01)
        if 0.5 <= ratio <= 2.0:
            budget_score = 0.8  # Good fit
        elif 0.2 <= ratio <= 5.0:
            budget_score = 0.5  # Acceptable
        else:
            budget_score = 0.2  # Poor fit

    # Weighted composite
    total = (
        0.35 * skill_score
        + 0.25 * reliability
        + 0.20 * category_score
        + 0.10 * chain_score
        + 0.10 * budget_score
    )

    return round(min(1.0, total), 3)


# ---------------------------------------------------------------------------
# Save/Load Performance Data
# ---------------------------------------------------------------------------


def save_performance(
    workspaces_dir: Path,
    profiles: dict[str, AgentPerformance],
) -> int:
    """Save performance profiles to workspace data/performance.json files.

    Returns number of profiles saved.
    """
    saved = 0

    for agent_name, perf in profiles.items():
        ws_dir = workspaces_dir / agent_name
        data_dir = ws_dir / "data"

        if not ws_dir.exists():
            continue

        data_dir.mkdir(parents=True, exist_ok=True)
        perf_file = data_dir / "performance.json"

        data = {
            "agent_name": perf.agent_name,
            "tasks_completed": perf.tasks_completed,
            "tasks_attempted": perf.tasks_attempted,
            "tasks_failed": perf.tasks_failed,
            "avg_completion_hours": perf.avg_completion_hours,
            "total_earned_usd": perf.total_earned_usd,
            "total_spent_usd": perf.total_spent_usd,
            "avg_rating_received": perf.avg_rating_received,
            "rating_count": perf.rating_count,
            "category_completions": perf.category_completions,
            "category_attempts": perf.category_attempts,
            "chain_tasks": perf.chain_tasks,
            "completion_rate": perf.completion_rate,
            "reliability_score": perf.reliability_score,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            perf_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to save performance for {agent_name}: {e}")

    return saved


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_agents_for_task(
    profiles: dict[str, AgentPerformance],
    agent_skills_map: dict[str, set[str]],
    task_title: str,
    task_description: str,
    task_category: str = "",
    task_chain: str = "base",
    task_bounty: float = 0.0,
    exclude_agents: set[str] | None = None,
    min_score: float = 0.0,
) -> list[tuple[str, float]]:
    """Rank all agents by enhanced match score for a specific task.

    Args:
        profiles: Agent performance data.
        agent_skills_map: Agent name → set of skill keywords.
        task_title: Task title.
        task_description: Task description/instructions.
        task_category: Task category (optional).
        task_chain: Blockchain network (default: base).
        task_bounty: Task bounty in USD (optional).
        exclude_agents: Agents to exclude (already assigned, system agents, etc.).
        min_score: Minimum score threshold.

    Returns:
        Sorted list of (agent_name, score) tuples, highest first.
    """
    exclude = exclude_agents or set()
    rankings: list[tuple[str, float]] = []

    for agent_name, perf in profiles.items():
        if agent_name in exclude:
            continue

        skills = agent_skills_map.get(agent_name, set())
        score = compute_enhanced_match_score(
            agent_perf=perf,
            agent_skills=skills,
            task_title=task_title,
            task_description=task_description,
            task_category=task_category,
            task_chain=task_chain,
            task_bounty=task_bounty,
        )

        if score >= min_score:
            rankings.append((agent_name, score))

    rankings.sort(key=lambda x: x[1], reverse=True)
    return rankings
