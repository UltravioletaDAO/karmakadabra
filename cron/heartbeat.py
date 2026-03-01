"""
Karma Kadabra V2 — Phase 7: Heartbeat Runner

Mission Control-style continuous heartbeat for KK agents.
Each agent wakes every 15 minutes and follows this cycle:

  1. Read WORKING.md (state from last heartbeat)
  2. Decide action:
     a. Has active task? Resume it.
     b. No task? Check for coordinator assignments.
     c. No assignment? Browse EM for matching tasks.
     d. Nothing available? Check IRC @mentions.
     e. Still nothing? Log HEARTBEAT_OK and sleep.
  3. Execute action via EM API
  4. Write state to WORKING.md
  5. Append to daily notes
  6. Sleep until next heartbeat

Stagger Schedule (prevents API thundering herd):
  :00  kk-coordinator
  :02  kk-karma-hello
  :04  kk-abracadabra
  :06  kk-skill-extractor
  :08  kk-voice-extractor
  :09  kk-soul-extractor
  :10  kk-validator
  :10  community agents 1-10 (2s apart)
  :12  community agents 11-20
  :14  community agents 21-34

Usage:
  python heartbeat.py                          # All agents, 1 heartbeat cycle
  python heartbeat.py --daemon                 # Continuous 15-min loop
  python heartbeat.py --agent kk-juanjumagalp  # Single agent
  python heartbeat.py --agents 5               # First 5 agents
  python heartbeat.py --dry-run                # Preview actions
  python heartbeat.py --interval 900           # Custom interval (seconds)
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

from lib.memory import append_daily_note, get_daily_summary, init_memory_stack
from lib.swarm_state import poll_notifications, report_heartbeat
from lib.working_state import (
    WorkingState,
    clear_active_task,
    parse_working_md,
    set_active_task,
    update_heartbeat,
    write_working_md,
)
from services.em_client import AgentContext, EMClient, load_agent_context
from services.abracadabra_service import (
    discover_offerings as ab_discover,
    buy_offerings as ab_buy,
    generate_content as ab_generate,
    sell_content as ab_sell,
)
from services.karma_hello_service import run_service as run_karma_hello_service
from services.karma_hello_service import seller_flow as karma_hello_seller_flow
from services.skill_extractor_service import (
    discover_data_offerings as sk_discover,
    buy_data as sk_buy,
    process_skills as sk_process,
    publish_enriched_profiles as sk_publish,
    seller_flow as sk_seller_flow,
)
from services.voice_extractor_service import (
    discover_data_offerings as ve_discover,
    buy_data as ve_buy,
    process_voices as ve_process,
    publish_personality_profiles as ve_publish,
    seller_flow as ve_seller_flow,
)
from services.soul_extractor_service import (
    discover_data_offerings as so_discover,
    buy_data as so_buy,
    process_souls as so_process,
    publish_soul_profiles as so_publish,
    publish_profile_updates as so_publish_updates,
    seller_flow as so_seller_flow,
)
from services.coordinator_service import coordination_cycle as run_coordinator_cycle
from services.data_retrieval import check_and_retrieve_all
from services.irc_integration import check_irc_and_respond
from lib.vault_sync import VaultSync

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.heartbeat")

# Heartbeat config
DEFAULT_INTERVAL = 900  # 15 minutes
SYSTEM_AGENT_OFFSETS = {
    "kk-coordinator": 0,
    "kk-karma-hello": 2,
    "kk-abracadabra": 4,
    "kk-skill-extractor": 6,
    "kk-voice-extractor": 8,
    "kk-soul-extractor": 9,
    "kk-validator": 10,
    "kk-juanjumagalp": 12,
}
COMMUNITY_BASE_OFFSET = 10  # seconds after the minute


# ---------------------------------------------------------------------------
# Heartbeat actions
# ---------------------------------------------------------------------------


async def action_resume_task(
    client: EMClient,
    state: WorkingState,
    dry_run: bool,
) -> str:
    """Resume an active task based on its current status."""
    task = state.active_task
    task_id = task.task_id

    logger.info(f"  Resuming task {task_id} (status={task.status})")

    if task.status == "applied":
        # Check if we've been assigned
        try:
            task_data = await client.get_task(task_id)
            em_status = task_data.get("status", "")
            executor_id = task_data.get("executor_id", "")

            if em_status == "in_progress" and executor_id:
                task.status = "working"
                task.next_step = "Submit evidence"
                return f"assigned — now working on {task_id}"
            elif em_status in ("cancelled", "expired", "completed"):
                clear_active_task(state)
                return f"task {task_id} is {em_status} — cleared"
            else:
                return f"still waiting for assignment on {task_id}"
        except Exception as e:
            return f"check failed: {e}"

    elif task.status == "working":
        # Placeholder: in production, agent would execute the task here
        # For now, mark as ready to submit
        if dry_run:
            return f"[DRY RUN] would submit evidence for {task_id}"

        task.status = "submitting"
        task.next_step = "Submit evidence on next heartbeat"
        return f"task {task_id} ready for submission"

    elif task.status == "submitting":
        if dry_run:
            return f"[DRY RUN] would submit evidence for {task_id}"

        if client.agent.executor_id:
            try:
                await client.submit_evidence(
                    task_id=task_id,
                    executor_id=client.agent.executor_id,
                    evidence={
                        "type": "text",
                        "notes": f"Completed by KK agent {client.agent.name}",
                    },
                )
                task.status = "submitted"
                task.next_step = "Wait for review"
                return f"evidence submitted for {task_id}"
            except Exception as e:
                return f"submit failed: {e}"
        else:
            return "no executor_id — cannot submit"

    elif task.status == "submitted":
        # Check if task has been reviewed
        try:
            task_data = await client.get_task(task_id)
            em_status = task_data.get("status", "")
            if em_status == "completed":
                clear_active_task(state)
                return f"task {task_id} completed and paid"
            elif em_status in ("cancelled", "expired"):
                clear_active_task(state)
                return f"task {task_id} is {em_status}"
            else:
                return f"task {task_id} still under review"
        except Exception as e:
            return f"check failed: {e}"

    elif task.status == "reviewing":
        # Agent is reviewing submissions on a task they published
        try:
            submissions = await client.get_submissions(task_id)
            for sub in submissions:
                evidence = sub.get("evidence_url", "") or sub.get("evidence", {})
                if evidence and not dry_run:
                    await client.approve_submission(sub["id"], rating_score=80)
                    clear_active_task(state)
                    return f"approved submission on {task_id}"
            return f"no actionable submissions on {task_id}"
        except Exception as e:
            return f"review failed: {e}"

    return f"unknown task status: {task.status}"


async def action_browse_and_apply(
    client: EMClient,
    state: WorkingState,
    skills: dict,
    dry_run: bool,
) -> str:
    """Browse EM for tasks matching agent skills, apply to best match."""
    agent = client.agent

    agent_skills = set()
    for s in skills.get("top_skills", []):
        agent_skills.add(s.get("skill", "").lower())

    try:
        tasks = await client.browse_tasks(status="published", limit=20)
    except Exception as e:
        return f"browse failed: {e}"

    for task in tasks:
        title = task.get("title", "").lower()
        description = task.get("instructions", task.get("description", "")).lower()
        task_id = task.get("id", "")
        bounty = task.get("bounty_usd", 0)

        # Skip own tasks
        if task.get("agent_wallet", "") == agent.wallet_address:
            continue

        # Skill matching
        match = any(s in title or s in description for s in agent_skills)
        if not match and "[kk" not in title:
            continue

        # Budget check
        if bounty > state.can_spend:
            continue

        if dry_run:
            return f"[DRY RUN] would apply to: {task.get('title', '?')} (${bounty})"

        if not agent.executor_id:
            return "no executor_id — register on EM first"

        try:
            await client.apply_to_task(
                task_id=task_id,
                executor_id=agent.executor_id,
                message=f"KK agent {agent.name} — skills: {', '.join(list(agent_skills)[:3])}",
            )
            set_active_task(
                state,
                task_id=task_id,
                title=task.get("title", "?"),
                status="applied",
                next_step="Wait for assignment",
            )
            return f"applied to: {task.get('title', '?')} (${bounty})"
        except Exception as e:
            return f"apply failed: {e}"

    return "no matching tasks found"


async def action_check_own_tasks(
    client: EMClient,
    state: WorkingState,
    dry_run: bool,
) -> str:
    """Check if agent's published tasks have submissions to review."""
    agent = client.agent

    try:
        my_tasks = await client.list_tasks(
            agent_wallet=agent.wallet_address,
            status="submitted",
        )
    except Exception as e:
        return f"list tasks failed: {e}"

    if not my_tasks:
        return "no submissions to review"

    task = my_tasks[0]
    task_id = task.get("id", "")

    set_active_task(
        state,
        task_id=task_id,
        title=task.get("title", "?"),
        status="reviewing",
        next_step="Review submissions",
    )
    return f"found submission to review on: {task.get('title', '?')}"


# ---------------------------------------------------------------------------
# Single heartbeat cycle
# ---------------------------------------------------------------------------


async def heartbeat_once(
    workspace_dir: Path,
    data_dir: Path,
    dry_run: bool,
) -> dict:
    """Execute one heartbeat cycle for a single agent.

    Returns:
        Dict with agent name, action taken, and result.
    """
    name = workspace_dir.name

    # Ensure memory stack exists
    memory_dir = workspace_dir / "memory"
    if not memory_dir.exists():
        init_memory_stack(workspace_dir)

    working_path = memory_dir / "WORKING.md"

    # 1. Read state
    state = parse_working_md(working_path)

    # Load agent context and skills
    agent = load_agent_context(workspace_dir)
    skills_file = data_dir / "skills" / f"{name.removeprefix('kk-')}.json"
    skills = {}
    if skills_file.exists():
        skills = json.loads(skills_file.read_text(encoding="utf-8"))

    client = EMClient(agent)
    action = "idle"
    result = "no action needed"

    try:
        # 1b. Check for coordinator notifications (non-fatal)
        try:
            notifications = await poll_notifications(name)
            for notif in notifications:
                content = notif.get("content", "")
                # Parse JSON notifications from coordinator
                try:
                    data = json.loads(content)
                    if data.get("type") == "task_assignment" and data.get("task_id"):
                        set_active_task(
                            state,
                            task_id=data["task_id"],
                            title=data.get("title", "coordinator assignment"),
                            status="applied",
                            next_step="Wait for assignment confirmation",
                        )
                        logger.info(f"  [{name}] Coordinator assigned: {data.get('title', '?')}")
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception as e:
            logger.debug(f"  [{name}] Notification poll failed (non-fatal): {e}")

        # 2. Decide and execute action
        # -- Special heartbeat for kk-karma-hello: run service cycles
        if name == "kk-karma-hello":
            action = "karma_hello_service"
            try:
                svc_result = await run_karma_hello_service(
                    data_dir=data_dir,
                    workspace_dir=workspace_dir,
                    run_collect=True,
                    run_publish=True,
                    run_fulfill=True,
                    run_seller=True,
                    dry_run=dry_run,
                )
                cycles = ", ".join(svc_result.get("cycles_run", []))
                parts = []
                if "collect" in svc_result:
                    parts.append(f"{svc_result['collect']['new_messages']} new msgs")
                if "publish" in svc_result:
                    parts.append(f"{svc_result['publish']['published']} published")
                if "fulfill" in svc_result:
                    parts.append(f"{svc_result['fulfill']['approved']} approved")
                if "seller" in svc_result:
                    sr = svc_result["seller"]
                    parts.append(
                        f"seller: {sr.get('bounties_found', 0)} found, "
                        f"{sr.get('applied', 0)} applied, "
                        f"{sr.get('submitted', 0)} submitted"
                    )
                result = f"cycles=[{cycles}] {'; '.join(parts)}"
            except Exception as e:
                result = f"karma_hello_service error: {e}"

        # -- Special heartbeat for kk-abracadabra: content intelligence cycle
        elif name == "kk-abracadabra":
            action = "abracadabra_service"
            try:
                parts = []
                # Phase 1+2: Discover and buy data from Karma Hello
                offerings = await ab_discover(client)
                parts.append(f"{len(offerings)} offerings found")

                purchased = []
                if offerings:
                    purchased = await ab_buy(client, offerings, dry_run=dry_run)
                    parts.append(f"{len(purchased)} purchased")

                # Phase 3: Generate content products from local data
                generated = await ab_generate(data_dir, dry_run=dry_run)
                parts.append(f"{len(generated)} generated")

                # Phase 4: Publish content products on EM
                published = []
                if generated:
                    published = await ab_sell(client, generated, dry_run=dry_run)
                    parts.append(f"{len(published)} published")

                result = "; ".join(parts)
            except Exception as e:
                result = f"abracadabra_service error: {e}"

        # -- Special heartbeat for kk-skill-extractor: seller flow (escrow)
        elif name == "kk-skill-extractor":
            action = "skill_extractor_seller"
            try:
                parts = []

                # Seller flow: discover [KK Request] bounties, apply, fulfill
                seller_result = await sk_seller_flow(client, data_dir, dry_run=dry_run)
                sr = seller_result
                parts.append(
                    f"seller: {sr.get('bounties_found', 0)} found, "
                    f"{sr.get('applied', 0)} applied, "
                    f"{sr.get('submitted', 0)} submitted"
                )

                # Also process local data if available (enriches evidence quality)
                try:
                    stats = await sk_process(data_dir)
                    if stats:
                        parts.append(f"{stats['total_profiles']} profiles processed")
                except Exception as e:
                    logger.debug(f"  [{name}] Process (non-fatal): {e}")

                # Retrieve purchased data (non-fatal)
                try:
                    retrieved = await check_and_retrieve_all(client, data_dir, agent.wallet_address)
                    if retrieved:
                        parts.append(f"{len(retrieved)} files retrieved")
                except Exception as e:
                    logger.debug(f"  [{name}] Retrieval (non-fatal): {e}")

                result = "; ".join(parts)
            except Exception as e:
                result = f"skill_extractor_service error: {e}"

        # -- Special heartbeat for kk-voice-extractor: seller flow (escrow)
        elif name == "kk-voice-extractor":
            action = "voice_extractor_seller"
            try:
                parts = []

                # Seller flow: discover [KK Request] bounties, apply, fulfill
                seller_result = await ve_seller_flow(client, data_dir, dry_run=dry_run)
                sr = seller_result
                parts.append(
                    f"seller: {sr.get('bounties_found', 0)} found, "
                    f"{sr.get('applied', 0)} applied, "
                    f"{sr.get('submitted', 0)} submitted"
                )

                # Also process local data if available
                try:
                    stats = await ve_process(data_dir)
                    if stats:
                        parts.append(f"{stats['total_profiles']} profiles processed")
                except Exception as e:
                    logger.debug(f"  [{name}] Process (non-fatal): {e}")

                # Retrieve purchased data (non-fatal)
                try:
                    retrieved = await check_and_retrieve_all(client, data_dir, agent.wallet_address)
                    if retrieved:
                        parts.append(f"{len(retrieved)} files retrieved")
                except Exception as e:
                    logger.debug(f"  [{name}] Retrieval (non-fatal): {e}")

                result = "; ".join(parts)
            except Exception as e:
                result = f"voice_extractor_service error: {e}"

        # -- Special heartbeat for kk-soul-extractor: seller flow (escrow)
        elif name == "kk-soul-extractor":
            action = "soul_extractor_seller"
            try:
                parts = []

                # Seller flow: discover [KK Request] bounties, apply, fulfill
                seller_result = await so_seller_flow(client, data_dir, dry_run=dry_run)
                sr = seller_result
                parts.append(
                    f"seller: {sr.get('bounties_found', 0)} found, "
                    f"{sr.get('applied', 0)} applied, "
                    f"{sr.get('submitted', 0)} submitted"
                )

                # Also process local data if available (merges skill+voice into SOUL.md)
                try:
                    stats = await so_process(data_dir)
                    if stats:
                        parts.append(f"{stats.get('total_profiles', 0)} souls merged")
                except Exception as e:
                    logger.debug(f"  [{name}] Process (non-fatal): {e}")

                # Retrieve purchased data (non-fatal)
                try:
                    retrieved = await check_and_retrieve_all(client, data_dir, agent.wallet_address)
                    if retrieved:
                        parts.append(f"{len(retrieved)} files retrieved")
                except Exception as e:
                    logger.debug(f"  [{name}] Retrieval (non-fatal): {e}")

                result = "; ".join(parts)
            except Exception as e:
                result = f"soul_extractor_service error: {e}"

        # -- Special heartbeat for kk-coordinator: orchestration cycle
        elif name == "kk-coordinator":
            action = "coordinator_service"
            try:
                workspaces_dir = workspace_dir.parent
                cycle_result = await run_coordinator_cycle(
                    workspaces_dir=workspaces_dir,
                    client=client,
                    dry_run=dry_run,
                )
                assignments = cycle_result.get("assignments", [])
                summary = cycle_result.get("summary", {})
                result = (
                    f"{len(assignments)} assignments; "
                    f"{summary.get('total_agents', 0)} agents monitored"
                )
            except Exception as e:
                result = f"coordinator_service error: {e}"

        # -- Special heartbeat for kk-validator: browse and validate submissions
        elif name == "kk-validator":
            action = "validator_service"
            try:
                parts = []
                # Check own published tasks for submissions to review
                own_result = await action_check_own_tasks(client, state, dry_run)
                parts.append(own_result)

                # If no own tasks to review, browse for validation tasks
                if not state.has_active_task and own_result == "no submissions to review":
                    browse_result = await action_browse_and_apply(client, state, skills, dry_run)
                    parts.append(browse_result)

                result = "; ".join(parts)
            except Exception as e:
                result = f"validator_service error: {e}"

        # -- Community buyer agents (kk-juanjumagalp, etc.)
        elif name.startswith("kk-") and name.replace("kk-", "") not in (
            "coordinator", "karma-hello", "abracadabra",
            "skill-extractor", "voice-extractor", "soul-extractor", "validator",
        ):
            action = "community_buyer"
            try:
                from services.community_buyer_service import run_cycle as run_buyer_cycle
                buyer_result = await run_buyer_cycle(
                    data_dir=data_dir,
                    workspace_dir=workspace_dir,
                    dry_run=dry_run,
                )
                step = buyer_result.get("step", "?")
                published = buyer_result.get("published", 0)
                assigned = buyer_result.get("assigned", 0)
                approved = buyer_result.get("approved", 0)
                completed = buyer_result.get("completed", 0)
                cycle_count = buyer_result.get("cycle_count", 0)

                # Retrieve purchased data (non-fatal)
                retrieved_count = 0
                try:
                    retrieved = await check_and_retrieve_all(client, data_dir, agent.wallet_address)
                    retrieved_count = len(retrieved)
                except Exception as e:
                    logger.debug(f"  [{name}] Retrieval (non-fatal): {e}")

                result = (
                    f"step={step}, cycle#{cycle_count}, "
                    f"published={published}, assigned={assigned}, "
                    f"approved={approved}, completed={completed}"
                    + (f", retrieved={retrieved_count}" if retrieved_count else "")
                )
            except ImportError:
                # Fallback to generic browse+apply if community_buyer_service not available
                action = "browse"
                result = await action_browse_and_apply(client, state, skills, dry_run)
            except Exception as e:
                result = f"community_buyer error: {e}"

        elif state.has_active_task:
            action = f"resume:{state.active_task.status}"
            result = await action_resume_task(client, state, dry_run)

        elif state.can_spend > 0:
            # First check own tasks for submissions
            action = "check_own_tasks"
            result = await action_check_own_tasks(client, state, dry_run)

            if not state.has_active_task and result == "no submissions to review":
                # Then browse for new tasks
                action = "browse"
                result = await action_browse_and_apply(client, state, skills, dry_run)

        else:
            action = "budget_exhausted"
            result = f"daily budget spent (${state.daily_spent:.2f}/${state.daily_budget:.2f})"

    except Exception as e:
        action = "error"
        result = str(e)
        logger.error(f"  [{name}] Heartbeat error: {e}")

    finally:
        await client.close()

    # 3. Update state
    update_heartbeat(state, action, result)

    # 4. Write state
    if not dry_run:
        write_working_md(working_path, state)

    # 5. Append daily note
    if not dry_run:
        append_daily_note(memory_dir, action, result)

    # 6. Report to shared swarm state (non-fatal)
    if not dry_run:
        try:
            swarm_status = "busy" if state.has_active_task else "idle"
            await report_heartbeat(
                agent_name=name,
                status=swarm_status,
                task_id=state.active_task.task_id if state.has_active_task else None,
                daily_spent=state.daily_spent,
            )
        except Exception as e:
            logger.debug(f"  [{name}] Swarm state report failed (non-fatal): {e}")

    # 7. IRC: announce heartbeat results and respond to mentions
    irc_summary = ""
    if not dry_run:
        try:
            irc_summary = await check_irc_and_respond(
                data_dir=data_dir,
                agent_name=name,
                action=action,
                action_result=result,
            )
        except Exception as e:
            logger.debug(f"  [{name}] IRC (non-fatal): {e}")

    logger.info(f"  [{name}] {action} -> {result}")
    if irc_summary:
        logger.info(f"  [{name}] IRC: {irc_summary}")

    # 8. Vault: update Obsidian vault state (non-fatal)
    if not dry_run:
        try:
            vault_dir = data_dir.parent / "vault"
            if vault_dir.exists():
                vault = VaultSync(str(vault_dir), name)
                vault.pull()
                vault.write_state(
                    {
                        "status": "active" if action != "error" else "error",
                        "current_task": action,
                        "tasks_completed": state.tasks_completed if hasattr(state, "tasks_completed") else 0,
                        "daily_spent_usdc": state.daily_spent,
                        "errors_last_24h": 1 if action == "error" else 0,
                    },
                    body=f"## Last Heartbeat\n{action} -> {result}",
                )
                vault.append_log(f"{action} -> {result}")
                vault.commit_and_push(f"{action}: {result[:60]}")
        except Exception as e:
            logger.debug(f"  [{name}] Vault sync (non-fatal): {e}")

    return {"agent": name, "action": action, "result": result}


# ---------------------------------------------------------------------------
# Stagger calculator
# ---------------------------------------------------------------------------


def get_stagger_offset(agent_name: str, agent_index: int) -> float:
    """Calculate stagger offset in seconds for an agent.

    System agents get fixed offsets (0-8s).
    Community agents get offset based on index (10s + index * 2s).
    """
    if agent_name in SYSTEM_AGENT_OFFSETS:
        return float(SYSTEM_AGENT_OFFSETS[agent_name])

    # Community agents: base offset + 2s per agent
    return COMMUNITY_BASE_OFFSET + (agent_index * 2)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run_all_heartbeats(
    workspaces_dir: Path,
    data_dir: Path,
    agent_name: str | None,
    max_agents: int | None,
    dry_run: bool,
    stagger: bool = True,
) -> list[dict]:
    """Run one heartbeat cycle for all agents (staggered)."""
    # Discover agents
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
            ]
        else:
            agent_dirs = sorted(
                d
                for d in workspaces_dir.iterdir()
                if d.is_dir() and d.name.startswith("kk-")
            )

    if max_agents:
        agent_dirs = agent_dirs[:max_agents]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'=' * 60}")
    print(f"  Karma Kadabra — Heartbeat")
    print(f"  Agents: {len(agent_dirs)}")
    print(f"  Time: {now}")
    if dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    results = []
    for i, ws_dir in enumerate(agent_dirs):
        if not ws_dir.exists():
            continue

        # Stagger
        if stagger and i > 0 and not dry_run:
            offset = get_stagger_offset(ws_dir.name, i)
            offset = min(offset, 120)  # Cap at 2 minutes
            if offset > 0:
                logger.info(f"  Stagger: {ws_dir.name} waits {offset:.0f}s")
                await asyncio.sleep(offset)

        result = await heartbeat_once(ws_dir, data_dir, dry_run)
        results.append(result)

    # Summary
    actions = {}
    for r in results:
        a = r["action"].split(":")[0]
        actions[a] = actions.get(a, 0) + 1

    print(f"\n  Heartbeat complete: {len(results)} agents")
    for a, count in sorted(actions.items()):
        print(f"    {a}: {count}")
    print()

    return results


async def daemon_loop(
    workspaces_dir: Path,
    data_dir: Path,
    max_agents: int | None,
    dry_run: bool,
    interval: int,
) -> None:
    """Run heartbeats in a continuous loop."""
    logger.info(f"Starting heartbeat daemon (interval: {interval}s = {interval // 60}m)")

    while True:
        try:
            await run_all_heartbeats(
                workspaces_dir, data_dir, None, max_agents, dry_run
            )
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")

        logger.info(f"  Next heartbeat in {interval}s...")
        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="KK Heartbeat Runner")
    parser.add_argument("--agent", type=str, help="Single agent name")
    parser.add_argument("--agents", type=int, help="Limit to N agents")
    parser.add_argument("--workspaces", type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Heartbeat interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument("--no-stagger", action="store_true", help="Disable stagger")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspaces_dir = (
        Path(args.workspaces) if args.workspaces else base / "data" / "workspaces"
    )
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    if not workspaces_dir.exists():
        print(f"ERROR: Workspaces not found at {workspaces_dir}")
        print("  Run generate-workspaces.py first.")
        return

    if args.daemon:
        await daemon_loop(
            workspaces_dir, data_dir, args.agents, args.dry_run, args.interval
        )
    else:
        await run_all_heartbeats(
            workspaces_dir,
            data_dir,
            args.agent,
            args.agents,
            args.dry_run,
            stagger=not args.no_stagger,
        )


if __name__ == "__main__":
    asyncio.run(main())
