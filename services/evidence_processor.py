"""
Karma Kadabra V2 — Evidence Processor Service

Processes completed task evidence and feeds results back into the
performance tracking and reputation systems. This closes the loop:

    Task Assigned → Executed → Evidence Submitted → **Processed** → Performance Updated

The Evidence Processor:
  1. Monitors EM for completed tasks assigned to KK agents
  2. Extracts performance signals from evidence quality + approval/rejection
  3. Updates agent performance profiles (skills, success rates, speed)
  4. Feeds the reputation bridge with new data points
  5. Detects patterns (agent strengths, weaknesses, category trends)

This is the "learning loop" — agents get better at task selection over time
because their performance data improves the coordinator's matching.

Usage:
    processor = EvidenceProcessor(workspaces_dir)
    summary = await processor.process_recent_completions(em_client)
    summary = processor.process_evidence_batch(evidence_list)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("kk.evidence_processor")


# ═══════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════


@dataclass
class CompletionRecord:
    """A completed task with its evidence and outcome."""

    task_id: str
    agent_name: str
    title: str = ""
    category: str = ""
    bounty_usd: float = 0.0
    evidence_type: str = ""
    approved: bool = False
    rejected: bool = False
    rating_score: int = 0  # 0-100 from task creator
    rejection_reason: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    execution_strategy: str = ""
    completed_at: str = ""
    payment_network: str = "base"


@dataclass
class AgentPerformanceUpdate:
    """Performance delta for one agent from processing evidence."""

    agent_name: str
    tasks_completed: int = 0
    tasks_approved: int = 0
    tasks_rejected: int = 0
    total_earned_usd: float = 0.0
    total_cost_usd: float = 0.0
    avg_rating: float = 0.0
    avg_duration_ms: float = 0.0
    categories_worked: dict[str, int] = field(default_factory=dict)
    chains_worked: dict[str, int] = field(default_factory=dict)
    skills_demonstrated: set[str] = field(default_factory=set)
    quality_trend: str = "stable"  # improving, stable, declining


@dataclass
class ProcessingSummary:
    """Summary of an evidence processing batch."""

    records_processed: int = 0
    agents_updated: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    total_earned_usd: float = 0.0
    total_cost_usd: float = 0.0
    net_profit_usd: float = 0.0
    agent_updates: dict[str, AgentPerformanceUpdate] = field(default_factory=dict)
    processing_time_ms: int = 0
    errors: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# Skill Extraction
# ═══════════════════════════════════════════════════════════════════

# Keywords that indicate demonstrated skills
_SKILL_KEYWORDS: dict[str, list[str]] = {
    "defi_analysis": ["defi", "lending", "yield", "liquidity", "tvl", "apy"],
    "smart_contract_review": ["solidity", "contract", "reentrancy", "erc-20", "erc-721"],
    "market_analysis": ["market", "price", "trend", "trading", "volume", "chart"],
    "blockchain_data": ["on-chain", "blockchain", "transaction", "block", "hash"],
    "content_writing": ["article", "blog", "copy", "content", "writing"],
    "data_analysis": ["data", "analysis", "statistics", "correlation", "pattern"],
    "translation": ["translate", "translation", "language", "localize"],
    "code_review": ["code", "review", "bug", "vulnerability", "security"],
    "research": ["research", "investigate", "study", "survey", "literature"],
}


def extract_skills_from_task(
    title: str, instructions: str, category: str
) -> set[str]:
    """Extract demonstrated skills from task metadata."""
    text = f"{title} {instructions} {category}".lower()
    skills: set[str] = set()

    for skill_name, keywords in _SKILL_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            skills.add(skill_name)

    # Category itself is a skill
    if category:
        skills.add(category)

    return skills


def compute_quality_trend(
    recent_ratings: list[int], window: int = 5
) -> str:
    """Compute quality trend from recent ratings.

    Returns "improving", "stable", or "declining".
    """
    if len(recent_ratings) < 3:
        return "stable"

    # Use last N ratings
    recent = recent_ratings[-window:]

    if len(recent) < 3:
        return "stable"

    # Compare first half vs second half
    mid = len(recent) // 2
    first_half_avg = sum(recent[:mid]) / mid
    second_half_avg = sum(recent[mid:]) / (len(recent) - mid)

    diff = second_half_avg - first_half_avg

    if diff > 5:
        return "improving"
    elif diff < -5:
        return "declining"
    return "stable"


# ═══════════════════════════════════════════════════════════════════
# Evidence Processor
# ═══════════════════════════════════════════════════════════════════


class EvidenceProcessor:
    """Process task evidence and update agent performance profiles.

    The processor maintains a cursor of last-processed task ID to avoid
    reprocessing. State is persisted to disk between runs.

    Args:
        workspaces_dir: Base directory containing agent workspaces.
        data_dir: Directory for processor state and reports.
    """

    def __init__(
        self,
        workspaces_dir: Path,
        data_dir: Path | None = None,
    ):
        self.workspaces_dir = workspaces_dir
        self.data_dir = data_dir or workspaces_dir.parent / "data" / "evidence"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # State
        self._cursor_file = self.data_dir / "processor_cursor.json"
        self._last_processed_id: str = ""
        self._last_processed_at: str = ""
        self._load_cursor()

        # Recent ratings per agent (for trend analysis)
        self._rating_history: dict[str, list[int]] = {}
        self._load_rating_history()

    def _load_cursor(self) -> None:
        """Load last processed cursor from disk."""
        if self._cursor_file.exists():
            try:
                data = json.loads(self._cursor_file.read_text(encoding="utf-8"))
                self._last_processed_id = data.get("last_id", "")
                self._last_processed_at = data.get("last_at", "")
            except (json.JSONDecodeError, OSError):
                pass

    def _save_cursor(self) -> None:
        """Save cursor to disk."""
        self._cursor_file.write_text(
            json.dumps({
                "last_id": self._last_processed_id,
                "last_at": self._last_processed_at,
                "updated": datetime.now(timezone.utc).isoformat(),
            }),
            encoding="utf-8",
        )

    def _load_rating_history(self) -> None:
        """Load rating history from disk."""
        path = self.data_dir / "rating_history.json"
        if path.exists():
            try:
                self._rating_history = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    def _save_rating_history(self) -> None:
        """Save rating history to disk."""
        path = self.data_dir / "rating_history.json"
        path.write_text(
            json.dumps(self._rating_history, indent=2),
            encoding="utf-8",
        )

    # ──────────────────────────────────────────────────────────────
    # Processing
    # ──────────────────────────────────────────────────────────────

    def process_completion(self, record: CompletionRecord) -> AgentPerformanceUpdate:
        """Process a single completion record.

        Returns the performance update for the agent.
        """
        update = AgentPerformanceUpdate(agent_name=record.agent_name)

        update.tasks_completed = 1

        if record.approved:
            update.tasks_approved = 1
            update.total_earned_usd = record.bounty_usd
        elif record.rejected:
            update.tasks_rejected = 1

        update.total_cost_usd = record.cost_usd
        update.avg_rating = float(record.rating_score)
        update.avg_duration_ms = float(record.duration_ms)

        if record.category:
            update.categories_worked[record.category] = 1
        if record.payment_network:
            update.chains_worked[record.payment_network] = 1

        # Extract skills
        update.skills_demonstrated = extract_skills_from_task(
            record.title, "", record.category
        )

        # Track rating history
        if record.rating_score > 0:
            if record.agent_name not in self._rating_history:
                self._rating_history[record.agent_name] = []
            self._rating_history[record.agent_name].append(record.rating_score)
            # Keep last 50 ratings
            self._rating_history[record.agent_name] = \
                self._rating_history[record.agent_name][-50:]

        # Compute quality trend
        ratings = self._rating_history.get(record.agent_name, [])
        update.quality_trend = compute_quality_trend(ratings)

        return update

    def process_batch(
        self, records: list[CompletionRecord]
    ) -> ProcessingSummary:
        """Process a batch of completion records.

        Aggregates per-agent updates and computes summary stats.
        """
        start = time.monotonic()
        summary = ProcessingSummary()

        agent_updates: dict[str, AgentPerformanceUpdate] = {}

        for record in records:
            try:
                update = self.process_completion(record)
                summary.records_processed += 1

                if record.approved:
                    summary.total_approved += 1
                elif record.rejected:
                    summary.total_rejected += 1

                summary.total_earned_usd += update.total_earned_usd
                summary.total_cost_usd += update.total_cost_usd

                # Merge into per-agent aggregation
                if record.agent_name in agent_updates:
                    existing = agent_updates[record.agent_name]
                    existing.tasks_completed += update.tasks_completed
                    existing.tasks_approved += update.tasks_approved
                    existing.tasks_rejected += update.tasks_rejected
                    existing.total_earned_usd += update.total_earned_usd
                    existing.total_cost_usd += update.total_cost_usd
                    for cat, count in update.categories_worked.items():
                        existing.categories_worked[cat] = \
                            existing.categories_worked.get(cat, 0) + count
                    for chain, count in update.chains_worked.items():
                        existing.chains_worked[chain] = \
                            existing.chains_worked.get(chain, 0) + count
                    existing.skills_demonstrated |= update.skills_demonstrated
                    existing.quality_trend = update.quality_trend
                else:
                    agent_updates[record.agent_name] = update

            except Exception as e:
                summary.errors.append(f"Record {record.task_id}: {e}")
                logger.warning(f"Failed to process {record.task_id}: {e}")

        # Compute averages for agents with multiple completions
        for agent_name, update in agent_updates.items():
            if update.tasks_completed > 0:
                ratings = self._rating_history.get(agent_name, [])
                if ratings:
                    recent = ratings[-update.tasks_completed:]
                    update.avg_rating = sum(recent) / len(recent)

        summary.agent_updates = agent_updates
        summary.agents_updated = len(agent_updates)
        summary.net_profit_usd = summary.total_earned_usd - summary.total_cost_usd
        summary.processing_time_ms = int((time.monotonic() - start) * 1000)

        # Save state
        if records:
            self._last_processed_id = records[-1].task_id
            self._last_processed_at = datetime.now(timezone.utc).isoformat()
            self._save_cursor()
            self._save_rating_history()

        return summary

    # ──────────────────────────────────────────────────────────────
    # Performance Profile Persistence
    # ──────────────────────────────────────────────────────────────

    def update_performance_profiles(
        self, summary: ProcessingSummary
    ) -> int:
        """Write performance updates to agent workspace profile.json files.

        Returns count of profiles updated.
        """
        updated = 0

        for agent_name, update in summary.agent_updates.items():
            profile_path = self.workspaces_dir / agent_name / "data" / "profile.json"

            # Load existing profile
            profile: dict[str, Any] = {}
            if profile_path.exists():
                try:
                    profile = json.loads(profile_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass

            # Update stats
            stats = profile.setdefault("performance", {})
            stats["tasks_completed"] = stats.get("tasks_completed", 0) + update.tasks_completed
            stats["tasks_approved"] = stats.get("tasks_approved", 0) + update.tasks_approved
            stats["tasks_rejected"] = stats.get("tasks_rejected", 0) + update.tasks_rejected
            stats["total_earned_usd"] = round(
                stats.get("total_earned_usd", 0) + update.total_earned_usd, 6
            )
            stats["total_cost_usd"] = round(
                stats.get("total_cost_usd", 0) + update.total_cost_usd, 6
            )
            stats["quality_trend"] = update.quality_trend
            stats["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Success rate
            total = stats["tasks_completed"]
            if total > 0:
                stats["success_rate"] = round(stats["tasks_approved"] / total, 3)

            # Update category experience
            categories = profile.setdefault("category_experience", {})
            for cat, count in update.categories_worked.items():
                categories[cat] = categories.get(cat, 0) + count

            # Update chain experience
            chains = profile.setdefault("chain_experience", {})
            for chain, count in update.chains_worked.items():
                chains[chain] = chains.get(chain, 0) + count

            # Update skills
            existing_skills = set(profile.get("demonstrated_skills", []))
            existing_skills |= update.skills_demonstrated
            profile["demonstrated_skills"] = sorted(existing_skills)

            # Write back
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(
                json.dumps(profile, indent=2, default=str),
                encoding="utf-8",
            )
            updated += 1

        return updated

    # ──────────────────────────────────────────────────────────────
    # EM API Integration
    # ──────────────────────────────────────────────────────────────

    async def process_recent_completions(
        self,
        em_client: Any,
        agent_names: list[str] | None = None,
        limit: int = 50,
    ) -> ProcessingSummary:
        """Fetch recent completed tasks from EM and process them.

        Args:
            em_client: EMClient instance.
            agent_names: Optional filter — only process these agents.
            limit: Max tasks to fetch.

        Returns:
            ProcessingSummary with all updates.
        """
        records: list[CompletionRecord] = []

        try:
            # Fetch completed tasks
            tasks = await em_client.list_tasks(status="completed", limit=limit)

            for task in tasks:
                task_id = task.get("id", "")

                # Skip already processed
                if task_id == self._last_processed_id:
                    break

                # Determine which KK agent completed this
                agent_name = self._identify_kk_agent(task, agent_names)
                if not agent_name:
                    continue

                # Get submissions for approval status
                try:
                    submissions = await em_client.get_submissions(task_id)
                except Exception:
                    submissions = []

                # Find the relevant submission
                approved = False
                rejected = False
                rating_score = 0
                rejection_reason = ""

                for sub in submissions:
                    if sub.get("status") == "approved":
                        approved = True
                        rating_score = sub.get("rating_score", 0)
                    elif sub.get("status") == "rejected":
                        rejected = True
                        rejection_reason = sub.get("notes", "")

                # Extract execution metadata from evidence
                evidence = task.get("evidence", {})
                metadata = evidence.get("metadata", {}) if isinstance(evidence, dict) else {}

                record = CompletionRecord(
                    task_id=task_id,
                    agent_name=agent_name,
                    title=task.get("title", ""),
                    category=task.get("category", ""),
                    bounty_usd=task.get("bounty_usd", 0),
                    evidence_type=metadata.get("type", ""),
                    approved=approved,
                    rejected=rejected,
                    rating_score=rating_score,
                    rejection_reason=rejection_reason,
                    tokens_used=metadata.get("tokens_used", 0),
                    cost_usd=metadata.get("cost_usd", 0),
                    duration_ms=metadata.get("duration_ms", 0),
                    execution_strategy=metadata.get("strategy", ""),
                    completed_at=task.get("completed_at", ""),
                    payment_network=task.get("payment_network", "base"),
                )
                records.append(record)

        except Exception as e:
            logger.error(f"Failed to fetch completions: {e}")
            return ProcessingSummary(errors=[f"Fetch failed: {e}"])

        # Process the batch
        summary = self.process_batch(records)

        # Update performance profiles
        if summary.agents_updated > 0:
            profiles_updated = self.update_performance_profiles(summary)
            logger.info(
                f"Processed {summary.records_processed} completions, "
                f"updated {profiles_updated} profiles"
            )

        return summary

    def _identify_kk_agent(
        self,
        task: dict[str, Any],
        allowed_agents: list[str] | None = None,
    ) -> str | None:
        """Identify which KK agent completed a task.

        Checks executor wallet, agent metadata, and task claims.
        """
        # Check executor identity
        executor_wallet = task.get("executor_wallet", "")

        # Check evidence metadata
        evidence = task.get("evidence", {})
        if isinstance(evidence, dict):
            agent = evidence.get("metadata", {}).get("agent", "")
            if agent and agent.startswith("kk-"):
                if allowed_agents is None or agent in allowed_agents:
                    return agent

        # Check submissions for agent name
        for sub in task.get("submissions", []):
            agent = sub.get("agent_name", "")
            if agent and agent.startswith("kk-"):
                if allowed_agents is None or agent in allowed_agents:
                    return agent

        return None

    # ──────────────────────────────────────────────────────────────
    # Reports
    # ──────────────────────────────────────────────────────────────

    def generate_report(self, summary: ProcessingSummary) -> str:
        """Generate a human-readable processing report."""
        lines = [
            "# Evidence Processing Report",
            f"Processed: {summary.records_processed} records",
            f"Agents updated: {summary.agents_updated}",
            f"Approved: {summary.total_approved} | Rejected: {summary.total_rejected}",
            f"Earned: ${summary.total_earned_usd:.4f} | Cost: ${summary.total_cost_usd:.4f}",
            f"Net P&L: ${summary.net_profit_usd:.4f}",
            f"Processing time: {summary.processing_time_ms}ms",
            "",
        ]

        if summary.agent_updates:
            lines.append("## Per-Agent Performance")
            for agent_name, update in sorted(summary.agent_updates.items()):
                trend_icon = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(
                    update.quality_trend, "❓"
                )
                lines.append(
                    f"- **{agent_name}**: {update.tasks_completed} tasks "
                    f"({update.tasks_approved}✅ {update.tasks_rejected}❌) "
                    f"${update.total_earned_usd:.4f} earned "
                    f"{trend_icon} {update.quality_trend}"
                )
                if update.skills_demonstrated:
                    lines.append(f"  Skills: {', '.join(sorted(update.skills_demonstrated))}")

        if summary.errors:
            lines.extend(["", "## Errors"])
            for err in summary.errors:
                lines.append(f"- {err}")

        return "\n".join(lines)

    def save_report(self, summary: ProcessingSummary) -> Path:
        """Save processing report to disk."""
        report_dir = self.data_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = report_dir / f"processing_{ts}.md"
        path.write_text(self.generate_report(summary), encoding="utf-8")

        # Also save raw JSON
        json_path = report_dir / f"processing_{ts}.json"
        json_path.write_text(
            json.dumps({
                "records_processed": summary.records_processed,
                "agents_updated": summary.agents_updated,
                "total_approved": summary.total_approved,
                "total_rejected": summary.total_rejected,
                "total_earned_usd": summary.total_earned_usd,
                "total_cost_usd": summary.total_cost_usd,
                "net_profit_usd": summary.net_profit_usd,
                "processing_time_ms": summary.processing_time_ms,
                "errors": summary.errors,
                "agent_updates": {
                    name: {
                        "tasks_completed": u.tasks_completed,
                        "tasks_approved": u.tasks_approved,
                        "tasks_rejected": u.tasks_rejected,
                        "total_earned_usd": u.total_earned_usd,
                        "quality_trend": u.quality_trend,
                        "skills": sorted(u.skills_demonstrated),
                    }
                    for name, u in summary.agent_updates.items()
                },
            }, indent=2),
            encoding="utf-8",
        )

        return path
