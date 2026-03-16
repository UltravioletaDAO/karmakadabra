"""
Karma Kadabra V2 — Task 5.6: Daily Activity Cron

Scheduled activity for each agent to maintain economic activity.
Agents run on a staggered schedule to avoid rate limiting.

Schedule (UTC, staggered by agent index * 2 minutes):
  06:00 — Browse EM for tasks matching skills, apply to matches
  08:00 — Review own published tasks, check submissions, approve/reject
  10:00 — Post in IRC #kk-data-market, announce offerings
  14:00 — Publish new tasks based on knowledge gaps
  18:00 — Rate completed interactions (ERC-8004 reputation)
  22:00 — Summarize daily activity, reset budgets

Usage:
  python daily_routine.py                          # Full daily cycle (all agents)
  python daily_routine.py --phase browse           # Only browse phase
  python daily_routine.py --phase review           # Only review phase
  python daily_routine.py --phase publish          # Only publish phase
  python daily_routine.py --phase announce         # Only IRC announce phase
  python daily_routine.py --agents 5               # First 5 agents
  python daily_routine.py --agent kk-juanjumagalp  # Single agent
  python daily_routine.py --dry-run                # Preview all actions
  python daily_routine.py --daemon                 # Run as daemon (continuous)

Daemon mode:
  Runs continuously, executing each phase at the scheduled UTC hour.
  Stagger offset: agent N starts N*2 minutes after the hour.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.em_client import AgentContext, EMClient, load_agent_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.daily-routine")


# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

PHASES = {
    "browse": {"hour": 6, "description": "Browse EM for tasks, apply to matches"},
    "review": {"hour": 8, "description": "Review submissions on own tasks"},
    "announce": {"hour": 10, "description": "Post offerings on IRC"},
    "publish": {"hour": 14, "description": "Publish new tasks"},
    "rate": {"hour": 18, "description": "Rate completed interactions"},
    "summary": {"hour": 22, "description": "Summarize daily activity"},
}


# ---------------------------------------------------------------------------
# Phase implementations
# ---------------------------------------------------------------------------

async def phase_browse(client: EMClient, skills: dict, dry_run: bool) -> dict:
    """Browse EM for tasks matching agent skills, apply to matches."""
    agent = client.agent
    applied = []

    agent_skills = set()
    for s in skills.get("top_skills", []):
        agent_skills.add(s.get("skill", "").lower())

    tasks = await client.browse_tasks(status="published", limit=20)

    for task in tasks:
        title = task.get("title", "").lower()
        description = task.get("description", "").lower()
        task_id = task.get("id", "")
        bounty = task.get("bounty_usdc", 0)

        if task.get("agent_wallet", "") == agent.wallet_address:
            continue

        match = any(s in title or s in description for s in agent_skills)
        if not match and "[kk data]" not in title:
            continue

        if not agent.can_spend(bounty):
            continue

        if len(applied) >= 3:
            break

        if dry_run:
            applied.append(task_id)
            continue

        if agent.executor_id:
            try:
                await client.apply_to_task(task_id, agent.executor_id)
                applied.append(task_id)
            except Exception as e:
                logger.warning(f"    Apply failed: {e}")

    return {"applied": len(applied)}


async def phase_review(client: EMClient, dry_run: bool) -> dict:
    """Review submissions on agent's published tasks."""
    agent = client.agent
    reviewed = 0

    my_tasks = await client.list_tasks(
        agent_wallet=agent.wallet_address,
        status="submitted",
    )

    for task in my_tasks:
        task_id = task.get("id", "")
        submissions = await client.get_submissions(task_id)

        for sub in submissions:
            sub_id = sub.get("id", "")
            evidence = sub.get("evidence_url", "")

            if dry_run:
                reviewed += 1
                continue

            if evidence:
                try:
                    await client.approve_submission(sub_id, rating_score=80)
                    reviewed += 1
                except Exception as e:
                    logger.warning(f"    Approve failed: {e}")

    return {"reviewed": reviewed}


async def phase_announce(agent_name: str, skills: dict, dry_run: bool) -> dict:
    """Post offerings on IRC (placeholder — actual IRC posting done by agent_irc_client)."""
    top_skills = [s.get("skill", "") for s in skills.get("top_skills", [])[:3]]
    announcement = f"HAVE: {agent_name} available for tasks. Skills: {', '.join(top_skills)}"

    if dry_run:
        logger.info(f"    [DRY RUN] IRC: {announcement}")
    else:
        logger.info(f"    IRC announcement queued: {announcement}")
        # In production, this would connect to IRC or write to a queue
        # that the IRC agent client picks up

    return {"announced": 1}


async def phase_publish(client: EMClient, skills: dict, dry_run: bool) -> dict:
    """Publish new tasks based on knowledge gaps."""
    agent = client.agent
    published = 0

    # Simple: publish one knowledge request per cycle
    top_interest = skills.get("top_skills", [{}])[0].get("skill", "general knowledge") if skills.get("top_skills") else "community trends"

    title = f"[KK] Looking for: {top_interest} insights"
    description = (
        f"Agent {agent.name} is looking for recent insights about {top_interest}.\n"
        f"Submit a brief analysis (100+ words) with sources.\n\n"
        f"Delivery: Text URL or direct text submission."
    )
    bounty = 0.02

    if not agent.can_spend(bounty):
        return {"published": 0}

    if dry_run:
        logger.info(f"    [DRY RUN] Would publish: {title}")
        return {"published": 1}

    try:
        result = await client.publish_task(
            title=title,
            instructions=description,
            category="knowledge_access",
            bounty_usd=bounty,
            deadline_hours=12,
            evidence_required=["text"],
        )
        agent.record_spend(bounty)
        published = 1
    except Exception as e:
        logger.warning(f"    Publish failed: {e}")

    return {"published": published}


async def phase_rate(client: EMClient, dry_run: bool) -> dict:
    """Rate completed interactions."""
    # Check for completed tasks that haven't been rated
    completed = await client.list_tasks(
        agent_wallet=client.agent.wallet_address,
        status="completed",
    )

    rated = 0
    for task in completed[:5]:  # Rate up to 5 per cycle
        # Rating is handled during approve — this phase logs activity
        rated += 1

    return {"rated": rated}


async def phase_summary(agent: AgentContext, results: dict) -> dict:
    """Summarize daily activity and reset budgets."""
    summary = {
        "agent": agent.name,
        "date": datetime.now(timezone.utc).isoformat(),
        "daily_spent": agent.daily_spent_usd,
        "budget_remaining": agent.daily_budget_usd - agent.daily_spent_usd,
        "phases_run": results,
    }

    # Write summary to workspace
    summary_dir = agent.workspace_dir / "data" / "daily_summaries"
    summary_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary_file = summary_dir / f"{date_str}.json"
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Reset daily budget
    agent.reset_daily_budget()

    return summary


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_agent_daily(
    workspace_dir: Path,
    data_dir: Path,
    phase: str | None,
    dry_run: bool,
) -> dict:
    """Run daily routine for one agent."""
    agent = load_agent_context(workspace_dir)
    name = agent.name

    skills_file = data_dir / "skills" / f"{name.removeprefix('kk-')}.json"
    skills = {}
    if skills_file.exists():
        skills = json.loads(skills_file.read_text(encoding="utf-8"))

    client = EMClient(agent)
    results: dict = {}

    try:
        phases_to_run = [phase] if phase else list(PHASES.keys())

        for p in phases_to_run:
            logger.info(f"  [{name}] Phase: {p} — {PHASES[p]['description']}")

            if p == "browse":
                results[p] = await phase_browse(client, skills, dry_run)
            elif p == "review":
                results[p] = await phase_review(client, dry_run)
            elif p == "announce":
                results[p] = await phase_announce(name, skills, dry_run)
            elif p == "publish":
                results[p] = await phase_publish(client, skills, dry_run)
            elif p == "rate":
                results[p] = await phase_rate(client, dry_run)
            elif p == "summary":
                results[p] = await phase_summary(agent, results)

    except Exception as e:
        logger.error(f"  [{name}] Error: {e}")
    finally:
        await client.close()

    return results


async def run_all_agents(
    workspaces_dir: Path,
    data_dir: Path,
    phase: str | None,
    agent_name: str | None,
    max_agents: int | None,
    dry_run: bool,
) -> None:
    """Run daily routine for all agents."""
    if agent_name:
        ws = workspaces_dir / agent_name
        if not ws.exists():
            ws = workspaces_dir / f"kk-{agent_name}"
        agent_dirs = [ws] if ws.exists() else []
    else:
        manifest = workspaces_dir / "_manifest.json"
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            agent_dirs = [
                workspaces_dir / w["name"]
                for w in data.get("workspaces", [])
                if w.get("type") == "community"
            ]
        else:
            agent_dirs = sorted(
                d for d in workspaces_dir.iterdir()
                if d.is_dir() and d.name.startswith("kk-")
            )

    if max_agents:
        agent_dirs = agent_dirs[:max_agents]

    print(f"\n{'=' * 60}")
    print(f"  Karma Kadabra — Daily Routine")
    print(f"  Phase: {phase or 'all'}")
    print(f"  Agents: {len(agent_dirs)}")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    if dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    for i, ws_dir in enumerate(agent_dirs):
        if not ws_dir.exists():
            continue

        # Stagger: agent N waits N*2 seconds (simulates minute-level stagger)
        if i > 0 and not dry_run:
            stagger = min(i * 2, 60)
            logger.info(f"  Stagger: waiting {stagger}s before agent {ws_dir.name}")
            await asyncio.sleep(stagger)

        logger.info(f"[{i + 1}/{len(agent_dirs)}] {ws_dir.name}")
        results = await run_agent_daily(ws_dir, data_dir, phase, dry_run)

        # Log results
        for p, r in results.items():
            if isinstance(r, dict):
                stats = ", ".join(f"{k}={v}" for k, v in r.items() if k != "agent" and k != "date" and k != "phases_run")
                if stats:
                    logger.info(f"    {p}: {stats}")

    print(f"\n  Daily routine complete for {len(agent_dirs)} agents.\n")


async def daemon_loop(
    workspaces_dir: Path,
    data_dir: Path,
    max_agents: int | None,
    dry_run: bool,
) -> None:
    """Run as daemon — execute phases at their scheduled hours."""
    logger.info("Starting daemon mode...")
    last_run: dict[str, str] = {}  # phase -> date string of last run

    # Pre-populate already-passed phases for today to avoid firing all on startup
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    for phase_name, phase_config in PHASES.items():
        if now.hour > phase_config["hour"]:
            run_key = f"{phase_name}:{today}"
            last_run[run_key] = now.isoformat()
            logger.info(f"Daemon: skipping already-passed phase '{phase_name}' (hour {phase_config['hour']})")

    while True:
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        today = now.strftime("%Y-%m-%d")

        for phase_name, phase_config in PHASES.items():
            run_key = f"{phase_name}:{today}"
            if current_hour >= phase_config["hour"] and run_key not in last_run:
                logger.info(f"Daemon: triggering phase '{phase_name}' (scheduled at {phase_config['hour']}:00 UTC)")
                await run_all_agents(workspaces_dir, data_dir, phase_name, None, max_agents, dry_run)
                last_run[run_key] = now.isoformat()

        # Check every 5 minutes
        await asyncio.sleep(300)


async def main():
    parser = argparse.ArgumentParser(description="KK Daily Routine")
    parser.add_argument("--phase", choices=list(PHASES.keys()), help="Run specific phase")
    parser.add_argument("--agent", type=str, help="Single agent name")
    parser.add_argument("--agents", type=int, help="Limit to N agents")
    parser.add_argument("--workspaces", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspaces_dir = Path(args.workspaces) if args.workspaces else base / "data" / "workspaces"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if not workspaces_dir.exists():
        print(f"ERROR: Workspaces not found at {workspaces_dir}")
        return

    if args.daemon:
        await daemon_loop(workspaces_dir, data_dir, args.agents, args.dry_run)
    else:
        await run_all_agents(
            workspaces_dir, data_dir, args.phase, args.agent, args.agents, args.dry_run,
        )


if __name__ == "__main__":
    asyncio.run(main())
