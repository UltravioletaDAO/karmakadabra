"""
Karma Kadabra V2 — Task 5.4: Agent-to-Agent Task Trading (Swarm Runner)

Orchestrator that enables KK agents to discover and complete each other's
tasks on Execution Market.  Each agent:
  1. Browses EM for tasks matching their skills
  2. Applies to tasks they can complete
  3. Submits evidence/results
  4. Publishes tasks based on their knowledge gaps
  5. Reviews submissions and rates counterparties

The swarm runner manages agent lifecycles, enforces budgets, and
coordinates timing to avoid conflicts.

Usage:
  python swarm_runner.py                           # Run all agents (1 cycle)
  python swarm_runner.py --agents 5                # First 5 agents only
  python swarm_runner.py --agent kk-juanjumagalp   # Single agent
  python swarm_runner.py --mode browse             # Only browse phase
  python swarm_runner.py --mode publish             # Only publish phase
  python swarm_runner.py --dry-run                  # Preview actions
"""

import argparse
import asyncio
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure imports work regardless of CWD
sys.path.insert(0, str(Path(__file__).parent))

from services.em_client import AgentContext, EMClient, load_agent_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.swarm-runner")

# Max concurrent tasks per agent
MAX_CONCURRENT_TASKS = 3

# Delay between agent actions (avoid rate limiting)
INTER_AGENT_DELAY = 2.0
INTRA_AGENT_DELAY = 1.0


# ---------------------------------------------------------------------------
# Agent Behavior: Browse & Apply
# ---------------------------------------------------------------------------

async def agent_browse_and_apply(
    client: EMClient,
    skills: dict,
    dry_run: bool = False,
) -> list[str]:
    """Agent browses EM for tasks matching their skills, applies to best matches."""
    applied_to = []
    agent = client.agent

    if len(agent.active_tasks) >= MAX_CONCURRENT_TASKS:
        logger.info(f"  [{agent.name}] At max concurrent tasks ({MAX_CONCURRENT_TASKS})")
        return applied_to

    # Get skill categories for matching
    agent_skills = set()
    for skill in skills.get("top_skills", []):
        agent_skills.add(skill.get("skill", "").lower())
    for cat in skills.get("skills", {}):
        agent_skills.add(cat.lower())

    # Browse available tasks
    tasks = await client.browse_tasks(status="published", limit=20)

    for task in tasks:
        title = task.get("title", "").lower()
        description = task.get("description", "").lower()
        bounty = task.get("bounty_usdc", 0)
        task_id = task.get("id", "")

        # Skip own tasks
        if task.get("agent_wallet", "") == agent.wallet_address:
            continue

        # Skill matching: check if any agent skill appears in title/description
        match_score = sum(1 for s in agent_skills if s in title or s in description)
        if match_score == 0:
            # Also accept generic [KK Data] tasks (data economy)
            if "[kk data]" not in title:
                continue

        if not agent.can_spend(bounty):
            continue

        if len(applied_to) + len(agent.active_tasks) >= MAX_CONCURRENT_TASKS:
            break

        logger.info(f"  [{agent.name}] Match found: {task.get('title', '?')} (score={match_score})")

        if dry_run:
            logger.info(f"    [DRY RUN] Would apply to task {task_id}")
            applied_to.append(task_id)
            continue

        if not agent.executor_id:
            logger.warning(f"  [{agent.name}] No executor_id — register on EM first")
            break

        try:
            await client.apply_to_task(
                task_id=task_id,
                executor_id=agent.executor_id,
                message=f"KK agent {agent.name} — skills: {', '.join(list(agent_skills)[:3])}",
            )
            applied_to.append(task_id)
            agent.active_tasks.append(task_id)
            logger.info(f"    Applied to {task_id}")
        except Exception as e:
            logger.warning(f"    Apply failed: {e}")

        await asyncio.sleep(INTRA_AGENT_DELAY)

    return applied_to


# ---------------------------------------------------------------------------
# Agent Behavior: Publish Tasks
# ---------------------------------------------------------------------------

TASK_TEMPLATES = [
    {
        "title": "[KK] Research: {topic} — Analysis Needed",
        "description": (
            "Looking for analysis on {topic}.\n"
            "Submit a brief report (200+ words) covering key trends, "
            "tools, and community sentiment.\n\n"
            "Delivery: Text URL or markdown document."
        ),
        "category": "knowledge_access",
        "bounty": 0.03,
        "topics": ["DeFi yield strategies", "NFT market trends", "AI agent frameworks", "DAO governance models"],
    },
    {
        "title": "[KK] Data Request: Community Stats for {topic}",
        "description": (
            "Need community engagement data for {topic}.\n"
            "Looking for: member count, activity metrics, top contributors.\n\n"
            "Delivery: JSON or CSV file URL."
        ),
        "category": "knowledge_access",
        "bounty": 0.02,
        "topics": ["Telegram groups", "Discord servers", "IRC channels", "GitHub repos"],
    },
]


async def agent_publish_tasks(
    client: EMClient,
    skills: dict,
    dry_run: bool = False,
) -> list[str]:
    """Agent publishes tasks based on knowledge gaps and interests."""
    published = []
    agent = client.agent

    # Pick a template based on agent's interests
    template = random.choice(TASK_TEMPLATES)
    topic = random.choice(template["topics"])
    bounty = template["bounty"]

    if not agent.can_spend(bounty):
        logger.info(f"  [{agent.name}] Budget exhausted — skip publishing")
        return published

    title = template["title"].format(topic=topic)
    description = template["description"].format(topic=topic)

    if dry_run:
        logger.info(f"  [{agent.name}] [DRY RUN] Would publish: {title} (${bounty})")
        return [title]

    try:
        result = await client.publish_task(
            title=title,
            instructions=description,
            category=template["category"],
            bounty_usd=bounty,
            deadline_hours=12,
            evidence_required=["text"],
        )
        task_id = result.get("task", {}).get("id") or result.get("id", "unknown")
        logger.info(f"  [{agent.name}] Published: {title} → {task_id}")
        agent.record_spend(bounty)
        published.append(task_id)
    except Exception as e:
        logger.warning(f"  [{agent.name}] Publish failed: {e}")

    return published


# ---------------------------------------------------------------------------
# Agent Behavior: Review Submissions
# ---------------------------------------------------------------------------

async def agent_review_submissions(
    client: EMClient,
    dry_run: bool = False,
) -> int:
    """Agent reviews submissions on their published tasks."""
    reviewed = 0
    agent = client.agent

    # Get agent's tasks that have submissions
    my_tasks = await client.list_tasks(
        agent_wallet=agent.wallet_address,
        status="submitted",
    )

    for task in my_tasks:
        task_id = task.get("id", "")
        submissions = await client.get_submissions(task_id)

        for sub in submissions:
            sub_id = sub.get("id", "")

            if dry_run:
                logger.info(f"  [{agent.name}] [DRY RUN] Would review submission {sub_id}")
                reviewed += 1
                continue

            # Simple auto-review: approve if evidence URL is present
            evidence_url = sub.get("evidence_url", "")
            if evidence_url:
                rating_score = random.randint(60, 95)
                try:
                    await client.approve_submission(
                        sub_id,
                        rating_score=rating_score,
                        notes=f"KK agent {agent.name} approved. Score: {rating_score}/100.",
                    )
                    logger.info(f"  [{agent.name}] Approved submission {sub_id} (score={rating_score})")
                    reviewed += 1
                except Exception as e:
                    logger.warning(f"  [{agent.name}] Approve failed: {e}")
            else:
                logger.info(f"  [{agent.name}] Submission {sub_id} has no evidence — skipping")

    return reviewed


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

async def run_agent_cycle(
    workspace_dir: Path,
    data_dir: Path,
    mode: str,
    dry_run: bool,
) -> dict:
    """Run one cycle for a single agent."""
    agent = load_agent_context(workspace_dir)
    name = agent.name

    # Load skills
    skills_file = data_dir / "skills" / f"{name.removeprefix('kk-')}.json"
    skills = {}
    if skills_file.exists():
        skills = json.loads(skills_file.read_text(encoding="utf-8"))

    client = EMClient(agent)
    results = {"name": name, "applied": [], "published": [], "reviewed": 0}

    try:
        if mode in ("all", "browse"):
            results["applied"] = await agent_browse_and_apply(client, skills, dry_run)

        if mode in ("all", "publish"):
            results["published"] = await agent_publish_tasks(client, skills, dry_run)

        if mode in ("all", "review"):
            results["reviewed"] = await agent_review_submissions(client, dry_run)

    except Exception as e:
        logger.error(f"  [{name}] Error: {e}")
    finally:
        await client.close()

    return results


async def main():
    parser = argparse.ArgumentParser(description="KK Swarm Runner — Agent-to-Agent Trading")
    parser.add_argument("--agents", type=int, default=None, help="Limit to first N agents")
    parser.add_argument("--agent", type=str, default=None, help="Run single agent by name")
    parser.add_argument("--mode", choices=["all", "browse", "publish", "review"], default="all")
    parser.add_argument("--workspaces", type=str, default=None, help="Workspaces directory")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(__file__).parent
    workspaces_dir = Path(args.workspaces) if args.workspaces else base / "data" / "workspaces"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if not workspaces_dir.exists():
        print(f"ERROR: Workspaces not found at {workspaces_dir}")
        print("  Run generate-workspaces.py first.")
        return

    # Discover agent workspaces
    if args.agent:
        agent_dirs = [workspaces_dir / args.agent]
        if not agent_dirs[0].exists():
            agent_dirs = [workspaces_dir / f"kk-{args.agent}"]
    else:
        manifest_file = workspaces_dir / "_manifest.json"
        if manifest_file.exists():
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            agent_dirs = [
                workspaces_dir / ws["name"]
                for ws in manifest.get("workspaces", [])
                if ws.get("type") == "community"  # Skip system agents for trading
            ]
        else:
            agent_dirs = sorted(
                d for d in workspaces_dir.iterdir()
                if d.is_dir() and d.name.startswith("kk-") and d.name != "kk-coordinator"
            )

    if args.agents:
        agent_dirs = agent_dirs[: args.agents]

    print(f"\n{'=' * 60}")
    print(f"  Karma Kadabra — Swarm Runner")
    print(f"  Mode: {args.mode}")
    print(f"  Agents: {len(agent_dirs)}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    total_applied = 0
    total_published = 0
    total_reviewed = 0

    for i, ws_dir in enumerate(agent_dirs):
        if not ws_dir.exists():
            logger.warning(f"  Workspace not found: {ws_dir}")
            continue

        logger.info(f"[{i + 1}/{len(agent_dirs)}] Running agent: {ws_dir.name}")
        result = await run_agent_cycle(ws_dir, data_dir, args.mode, args.dry_run)

        total_applied += len(result["applied"])
        total_published += len(result["published"])
        total_reviewed += result["reviewed"]

        # Stagger agents to avoid rate limiting
        if i < len(agent_dirs) - 1:
            await asyncio.sleep(INTER_AGENT_DELAY)

    print(f"\n{'=' * 60}")
    print(f"  Swarm Cycle Complete")
    print(f"    Applied to tasks:    {total_applied}")
    print(f"    Tasks published:     {total_published}")
    print(f"    Submissions reviewed: {total_reviewed}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
