"""
Karma Kadabra V2 — Phase 8: Coordinator Service (Enhanced)

The coordinator agent's heartbeat action. On each wake cycle:

  1. Read all agent states from kk_swarm_state
  2. Identify idle, stale, and busy agents
  3. Browse EM for unassigned tasks
  4. Match tasks to idle agents via **6-factor enhanced matching**:
     - 30% skill keywords, 20% reliability, 15% category experience,
       10% chain experience, 10% budget fit, 15% unified reputation
  5. Assign via kk_task_claims + kk_notifications
  6. Generate health summary with lifecycle + reputation data

The coordinator does NOT execute tasks itself — it routes and monitors.

Usage:
  python coordinator_service.py                # Full coordination cycle
  python coordinator_service.py --dry-run      # Preview assignments
  python coordinator_service.py --summary      # Health summary only
  python coordinator_service.py --legacy       # Use old skill-only matching
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from em_client import AgentContext, EMClient, load_agent_context
from lib.performance_tracker import (
    AgentPerformance,
    compute_enhanced_match_score,
    extract_performance_from_json,
    extract_performance_from_notes,
    rank_agents_for_task,
    save_performance,
)
from lib.reputation_bridge import (
    UnifiedReputation,
    compute_swarm_reputation,
    load_latest_snapshot,
    reputation_boost_for_matching,
    save_reputation_snapshot,
)
from lib.swarm_state import (
    claim_task,
    get_agent_states,
    get_stale_agents,
    get_swarm_summary,
    send_notification,
)
from lib.autojob_bridge import AutoJobBridge, BridgeResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.coordinator")


# Default path to AutoJob repo (same machine local mode)
AUTOJOB_DEFAULT_PATH = str(Path(__file__).parent.parent.parent / "autojob")


# ---------------------------------------------------------------------------
# Skill loading
# ---------------------------------------------------------------------------


def load_agent_skills(workspaces_dir: Path, agent_name: str) -> set[str]:
    """Load an agent's skills from their workspace SOUL.md or skills data."""
    ws_dir = workspaces_dir / agent_name
    if not ws_dir.exists():
        ws_dir = workspaces_dir / f"kk-{agent_name}"
    if not ws_dir.exists():
        return set()

    # Try structured skills JSON first
    skills_file = ws_dir / "data" / "profile.json"
    if skills_file.exists():
        try:
            profile = json.loads(skills_file.read_text(encoding="utf-8"))
            return {s.get("skill", "").lower() for s in profile.get("top_skills", [])}
        except Exception:
            pass

    # Fallback: parse SOUL.md for skill lines
    soul_file = ws_dir / "SOUL.md"
    if soul_file.exists():
        try:
            text = soul_file.read_text(encoding="utf-8")
            skills = set()
            in_skills = False
            for line in text.splitlines():
                if "## Skills" in line:
                    in_skills = True
                    continue
                if in_skills and line.startswith("##"):
                    break
                if in_skills and line.startswith("- **"):
                    # Extract skill name from "- **SkillName** (Category)"
                    name = line.split("**")[1] if "**" in line else ""
                    if name:
                        skills.add(name.lower())
            return skills
        except Exception:
            pass

    return set()


def compute_skill_match(agent_skills: set[str], task_title: str, task_desc: str) -> float:
    """Legacy skill-only match (kept for --legacy mode).

    Returns 0.0-1.0 score.
    """
    if not agent_skills:
        return 0.1  # Minimal score for agents without skills data

    text = (task_title + " " + task_desc).lower()
    matches = sum(1 for skill in agent_skills if skill in text)

    if matches == 0:
        # Check for KK-tagged tasks (any agent can take these)
        if "[kk" in text:
            return 0.3
        return 0.0

    return min(1.0, matches / max(len(agent_skills), 1))


# ---------------------------------------------------------------------------
# Performance data loading
# ---------------------------------------------------------------------------


def load_performance_profiles(
    workspaces_dir: Path,
) -> dict[str, AgentPerformance]:
    """Load performance profiles, preferring JSON over notes parsing.

    Merges both sources: JSON for structured data, notes for recent
    unrecorded completions.
    """
    # Try JSON first (faster, more reliable)
    json_profiles = extract_performance_from_json(workspaces_dir)

    # Also parse notes for anything not yet in JSON
    notes_profiles = extract_performance_from_notes(workspaces_dir)

    # Merge: JSON takes precedence, notes fill gaps
    merged: dict[str, AgentPerformance] = {}

    all_agents = set(json_profiles.keys()) | set(notes_profiles.keys())
    for agent_name in all_agents:
        json_perf = json_profiles.get(agent_name)
        notes_perf = notes_profiles.get(agent_name)

        if json_perf and json_perf.tasks_attempted > 0:
            # JSON has real data — use it
            merged[agent_name] = json_perf
        elif notes_perf and notes_perf.tasks_attempted > 0:
            # Notes have data that JSON doesn't — use notes
            merged[agent_name] = notes_perf
        else:
            # Neither has data — use whichever exists (or create default)
            merged[agent_name] = json_perf or notes_perf or AgentPerformance(agent_name=agent_name)

    return merged


# ---------------------------------------------------------------------------
# Coordination cycle
# ---------------------------------------------------------------------------


def _build_autojob_bridge(
    autojob_path: str = None,
    autojob_api: str = None,
    wallets_file: Path = None,
) -> tuple[AutoJobBridge | None, dict[str, str]]:
    """Initialize AutoJob bridge and build wallet→agent mapping.

    Returns (bridge, wallet_to_agent) or (None, {}) on failure.
    """
    wallet_to_agent: dict[str, str] = {}

    # Build wallet→agent mapping from wallets.json
    if wallets_file and wallets_file.exists():
        try:
            data = json.loads(wallets_file.read_text(encoding="utf-8"))
            for w in data.get("wallets", []):
                addr = w.get("address", "").lower()
                name = w.get("name", "")
                if addr and name:
                    wallet_to_agent[addr] = name
        except Exception as e:
            logger.warning("Failed to load wallets.json: %s", e)

    # Determine bridge mode
    if autojob_api:
        mode = "remote"
        path = None
    else:
        mode = "local"
        path = autojob_path or AUTOJOB_DEFAULT_PATH

    try:
        bridge = AutoJobBridge(
            mode=mode,
            autojob_path=path,
            api_base=autojob_api or "https://autojob.cc",
            wallet_to_agent=wallet_to_agent,
        )
        health = bridge.health()
        if health.get("status") == "healthy":
            logger.info(
                "AutoJob bridge initialized (%s mode, %d workers, %d wallet mappings)",
                mode,
                health.get("registered_workers", 0),
                len(wallet_to_agent),
            )
            return bridge, wallet_to_agent
        else:
            logger.warning("AutoJob bridge unhealthy: %s", health)
            return None, wallet_to_agent
    except Exception as e:
        logger.warning("AutoJob bridge init failed: %s", e)
        return None, wallet_to_agent


def _autojob_rank_to_coordinator(
    bridge_result: BridgeResult,
    idle_names: set[str],
    assigned_agents: set[str],
    system_agents: set[str],
) -> list[tuple[str, float]]:
    """Convert AutoJob BridgeResult into coordinator-compatible ranked list.

    Filters to only idle, non-system, non-assigned agents.
    Returns list of (agent_name, score) tuples, score normalized to 0-1.
    """
    ranked = []
    for r in bridge_result.rankings:
        name = r.agent_name
        if name in system_agents or name in assigned_agents:
            continue
        if name not in idle_names:
            continue
        # Normalize AutoJob's 0-100 score to 0-1 for coordinator compatibility
        score = r.final_score / 100.0
        ranked.append((name, score))
    return ranked


async def coordination_cycle(
    workspaces_dir: Path,
    client: EMClient,
    dry_run: bool = False,
    use_legacy_matching: bool = False,
    use_autojob: bool = False,
    autojob_path: str = None,
    autojob_api: str = None,
) -> dict:
    """Execute one coordinator cycle.

    Args:
        workspaces_dir: Path to agent workspaces.
        client: EM API client for browsing tasks.
        dry_run: If True, preview assignments without executing.
        use_legacy_matching: If True, use simple skill-only matching instead
            of the enhanced 5-factor performance-aware matching.
        use_autojob: If True, use AutoJob's evidence-based matching engine.
            Falls back to enhanced matching if AutoJob is unavailable.
        autojob_path: Path to AutoJob repo (local mode). Defaults to
            sibling directory.
        autojob_api: AutoJob API base URL (remote mode). If set, overrides
            local mode.

    Returns dict with assignments, health summary, and performance stats.
    """
    logger.info("Starting coordination cycle")

    # 1. Read all agent states
    all_agents = await get_agent_states()
    idle_agents = [a for a in all_agents if a.get("status") == "idle"]
    stale_agents = await get_stale_agents(stale_minutes=30)

    logger.info(f"  Agents: {len(all_agents)} total, {len(idle_agents)} idle, {len(stale_agents)} stale")

    # 2. Load performance profiles + reputation data (enhanced matching)
    performance_profiles: dict[str, AgentPerformance] = {}
    reputation_data: dict[str, UnifiedReputation] = {}
    autojob_bridge: AutoJobBridge | None = None
    autojob_stats = {"used": False, "tasks_matched": 0, "fallbacks": 0}

    if use_autojob:
        wallets_file = workspaces_dir.parent / "data" / "config" / "wallets.json"
        autojob_bridge, wallet_to_agent = _build_autojob_bridge(
            autojob_path=autojob_path,
            autojob_api=autojob_api,
            wallets_file=wallets_file,
        )
        if autojob_bridge:
            autojob_stats["used"] = True

    if not use_legacy_matching:
        performance_profiles = load_performance_profiles(workspaces_dir)
        agents_with_data = sum(
            1 for p in performance_profiles.values() if p.tasks_attempted > 0
        )
        logger.info(
            f"  Performance data: {len(performance_profiles)} profiles, "
            f"{agents_with_data} with history"
        )

        # Load reputation snapshots (graceful — may not exist yet)
        rep_dir = workspaces_dir.parent / "data" / "reputation"
        rep_snapshot = load_latest_snapshot(rep_dir)
        if rep_snapshot:
            # Build UnifiedReputation objects from snapshot data
            for name, rep_data in rep_snapshot.items():
                reputation_data[name] = UnifiedReputation(
                    agent_name=name,
                    composite_score=rep_data.get("composite_score", 50.0),
                    effective_confidence=rep_data.get("confidence", 0.0),
                    sources_available=rep_data.get("sources_available", []),
                )
            logger.info(f"  Reputation data: {len(reputation_data)} agents from snapshot")

    # 3. Browse EM for unassigned tasks
    try:
        available_tasks = await client.browse_tasks(status="published", limit=30)
    except Exception as e:
        logger.error(f"  Browse tasks failed: {e}")
        available_tasks = []

    logger.info(f"  Available tasks: {len(available_tasks)}")

    # Build skills map for all idle agents
    idle_names = {a.get("agent_name", "") for a in idle_agents}
    system_agents = {"kk-coordinator", "kk-validator"}
    agent_skills_map: dict[str, set[str]] = {}
    for agent in idle_agents:
        agent_name = agent.get("agent_name", "")
        if agent_name not in system_agents:
            agent_skills_map[agent_name] = load_agent_skills(workspaces_dir, agent_name)

    # 4. Match and assign
    assignments = []
    assigned_agents: set[str] = set()

    for task in available_tasks:
        task_id = task.get("id", "")
        title = task.get("title", "")
        desc = task.get("instructions", task.get("description", ""))
        bounty = task.get("bounty_usd", 0)
        category = task.get("category", "")
        chain = task.get("payment_network", "base")

        # Skip own tasks (coordinator should not assign itself)
        if task.get("agent_wallet", "") == client.agent.wallet_address:
            continue

        matching_mode_used = "unknown"

        if use_legacy_matching:
            # --- Legacy mode: simple skill keyword matching ---
            matching_mode_used = "legacy"
            best_agent = None
            best_score = 0.0

            for agent in idle_agents:
                agent_name = agent.get("agent_name", "")
                if agent_name in system_agents or agent_name in assigned_agents:
                    continue
                agent_skills = agent_skills_map.get(agent_name, set())
                score = compute_skill_match(agent_skills, title, desc)
                if score > best_score:
                    best_score = score
                    best_agent = agent

            ranked = [(best_agent.get("agent_name", ""), best_score)] if best_agent and best_score > 0.0 else []

        elif autojob_bridge:
            # --- AutoJob mode: evidence-based matching via AutoJob bridge ---
            matching_mode_used = "autojob"
            try:
                bridge_result = autojob_bridge.rank_agents_for_task(
                    task=task,
                    limit=10,
                    min_score=1.0,  # AutoJob uses 0-100 scale
                )
                ranked = _autojob_rank_to_coordinator(
                    bridge_result,
                    idle_names=idle_names,
                    assigned_agents=assigned_agents,
                    system_agents=system_agents,
                )
                if ranked:
                    autojob_stats["tasks_matched"] += 1
                    logger.info(
                        f"  AutoJob matched '{title[:30]}': "
                        f"{len(ranked)} candidates (best={ranked[0][0]}, "
                        f"score={ranked[0][1]:.3f}, "
                        f"time={bridge_result.match_time_ms:.0f}ms)"
                    )
                else:
                    # AutoJob returned no matches — fall back to enhanced
                    logger.info(
                        f"  AutoJob: no matches for '{title[:30]}', "
                        f"falling back to enhanced matching"
                    )
                    autojob_stats["fallbacks"] += 1
                    matching_mode_used = "enhanced (autojob-fallback)"
                    # Fall through to enhanced matching below
                    ranked = None
            except Exception as e:
                logger.warning(f"  AutoJob error for '{title[:30]}': {e}")
                autojob_stats["fallbacks"] += 1
                matching_mode_used = "enhanced (autojob-error)"
                ranked = None

            # Fallback to enhanced matching if AutoJob returned nothing
            if ranked is None:
                eligible_profiles = {
                    name: performance_profiles.get(name, AgentPerformance(agent_name=name))
                    for name in agent_skills_map
                    if name not in assigned_agents
                }
                ranked = rank_agents_for_task(
                    profiles=eligible_profiles,
                    agent_skills_map=agent_skills_map,
                    task_title=title,
                    task_description=desc,
                    task_category=category,
                    task_chain=chain,
                    task_bounty=bounty,
                    exclude_agents=system_agents | assigned_agents,
                    min_score=0.01,
                )
                if reputation_data and ranked:
                    boosted_ranked = []
                    for agent_n, base_score in ranked:
                        rep = reputation_data.get(agent_n)
                        if rep and rep.effective_confidence > 0:
                            boosted = reputation_boost_for_matching(
                                rep, base_score, reputation_weight=0.15,
                            )
                            boosted_ranked.append((agent_n, boosted))
                        else:
                            boosted_ranked.append((agent_n, base_score))
                    boosted_ranked.sort(key=lambda x: x[1], reverse=True)
                    ranked = boosted_ranked

        else:
            # --- Enhanced mode: 5-factor performance-aware matching ---
            matching_mode_used = "enhanced"
            # Filter to only idle, non-system, non-assigned agents
            eligible_profiles = {
                name: performance_profiles.get(name, AgentPerformance(agent_name=name))
                for name in agent_skills_map
                if name not in assigned_agents
            }

            ranked = rank_agents_for_task(
                profiles=eligible_profiles,
                agent_skills_map=agent_skills_map,
                task_title=title,
                task_description=desc,
                task_category=category,
                task_chain=chain,
                task_bounty=bounty,
                exclude_agents=system_agents | assigned_agents,
                min_score=0.01,
            )

            # Apply reputation boost (6th factor) if reputation data available
            if reputation_data and ranked:
                boosted_ranked = []
                for agent_n, base_score in ranked:
                    rep = reputation_data.get(agent_n)
                    if rep and rep.effective_confidence > 0:
                        boosted = reputation_boost_for_matching(
                            rep, base_score, reputation_weight=0.15,
                        )
                        boosted_ranked.append((agent_n, boosted))
                    else:
                        boosted_ranked.append((agent_n, base_score))
                boosted_ranked.sort(key=lambda x: x[1], reverse=True)
                ranked = boosted_ranked

        if not ranked:
            continue

        # Take top-ranked agent
        agent_name, score = ranked[0]

        if dry_run:
            logger.info(
                f"  [DRY RUN] Would assign '{title}' to {agent_name} "
                f"(score={score:.3f}, mode={matching_mode_used})"
            )
            assignments.append({
                "task_id": task_id,
                "title": title,
                "agent": agent_name,
                "score": score,
                "dry_run": True,
                "matching_mode": matching_mode_used,
                "alternatives": len(ranked) - 1,
            })
        else:
            # Atomic claim
            claimed = await claim_task(task_id, agent_name)
            if claimed:
                # Notify agent
                notification = json.dumps({
                    "type": "task_assignment",
                    "task_id": task_id,
                    "title": title,
                    "bounty_usd": bounty,
                })
                await send_notification(agent_name, "kk-coordinator", notification)

                logger.info(f"  Assigned '{title}' to {agent_name} (score={score:.3f}, mode={matching_mode_used})")
                assignments.append({
                    "task_id": task_id,
                    "title": title,
                    "agent": agent_name,
                    "score": score,
                    "matching_mode": matching_mode_used,
                    "alternatives": len(ranked) - 1,
                })

                assigned_agents.add(agent_name)
            else:
                logger.info(f"  Task '{title}' already claimed — skipping")

    # 5. Save updated performance profiles (if enhanced mode)
    if not use_legacy_matching and performance_profiles and not dry_run:
        saved = save_performance(workspaces_dir, performance_profiles)
        logger.info(f"  Saved {saved} performance profiles")

    # 6. Health summary
    summary = await get_swarm_summary()

    # 7. Stale agent warnings
    if stale_agents:
        logger.warning(f"  Stale agents ({len(stale_agents)}):")
        for sa in stale_agents:
            logger.warning(f"    {sa['agent_name']}: {sa.get('minutes_stale', '?')} min since last heartbeat")

    # Determine overall matching mode label
    if use_legacy_matching:
        overall_mode = "legacy"
    elif use_autojob and autojob_stats["used"]:
        overall_mode = "autojob"
    else:
        overall_mode = "enhanced"

    return {
        "assignments": assignments,
        "summary": summary,
        "stale_agents": [s["agent_name"] for s in stale_agents],
        "matching_mode": overall_mode,
        "performance_profiles_loaded": len(performance_profiles),
        "autojob": autojob_stats if use_autojob else None,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Class-based interface (for swarm_runner.py daemon integration)
# ---------------------------------------------------------------------------


def load_coordinator_config(config: dict = None) -> dict:
    """Load coordinator configuration.

    Merges defaults with provided config dict or environment variables.
    Used by swarm_runner.py to configure the coordinator.

    Args:
        config: Optional dict with overrides

    Returns:
        Configuration dict with all coordinator settings
    """
    defaults = {
        "use_autojob": False,
        "autojob_path": None,
        "autojob_api": None,
        "use_legacy_matching": False,
        "dry_run": False,
    }
    # Environment variable overrides
    import os
    env_map = {
        "KK_USE_AUTOJOB": ("use_autojob", lambda v: v.lower() in ("1", "true", "yes")),
        "KK_AUTOJOB_PATH": ("autojob_path", str),
        "KK_AUTOJOB_API": ("autojob_api", str),
        "KK_DRY_RUN": ("dry_run", lambda v: v.lower() in ("1", "true", "yes")),
        "KK_LEGACY_MATCHING": ("use_legacy_matching", lambda v: v.lower() in ("1", "true", "yes")),
    }
    for env_key, (config_key, converter) in env_map.items():
        val = os.getenv(env_key)
        if val is not None:
            defaults[config_key] = converter(val)

    if config:
        defaults.update(config)

    return defaults


class CoordinatorService:
    """Class-based wrapper around coordination_cycle for daemon integration.

    This is the interface swarm_runner.py expects. It wraps the
    function-based coordination_cycle() with stateful configuration.

    Usage:
        coordinator = CoordinatorService(
            workspaces_dir="./workspaces",
            em_client=client,
            use_autojob=True,
        )
        result = await coordinator.run_cycle()
    """

    def __init__(
        self,
        workspaces_dir: str,
        em_client: EMClient,
        dry_run: bool = False,
        max_assignments: int = 5,
        use_autojob: bool = False,
        autojob_path: str = None,
        autojob_api: str = None,
        use_legacy_matching: bool = False,
    ):
        self.workspaces_dir = Path(workspaces_dir)
        self.em_client = em_client
        self.dry_run = dry_run
        self.max_assignments = max_assignments
        self.use_autojob = use_autojob
        self.autojob_path = autojob_path
        self.autojob_api = autojob_api
        self.use_legacy_matching = use_legacy_matching

    async def run_cycle(self) -> dict:
        """Run one coordination cycle and return results.

        Returns:
            Dict with standardized result keys:
            - tasks_found: number of available tasks
            - tasks_assigned: number of assignments made
            - agents_active: total agents
            - agents_idle: idle agents
            - assignments: list of assignment details
            - matching_mode: which matching engine was used
            - autojob: AutoJob bridge stats (if enabled)
        """
        result = await coordination_cycle(
            workspaces_dir=self.workspaces_dir,
            client=self.em_client,
            dry_run=self.dry_run,
            use_legacy_matching=self.use_legacy_matching,
            use_autojob=self.use_autojob,
            autojob_path=self.autojob_path,
            autojob_api=self.autojob_api,
        )

        # Normalize result keys for swarm_runner compatibility
        summary = result.get("summary", {})
        assignments = result.get("assignments", [])

        return {
            "tasks_found": summary.get("total_published_tasks", len(assignments)),
            "tasks_assigned": len([a for a in assignments if not a.get("dry_run")]),
            "agents_active": summary.get("total_agents", 0),
            "agents_idle": summary.get("idle_agents", 0),
            "assignments": assignments,
            "matching_mode": result.get("matching_mode", "unknown"),
            "autojob": result.get("autojob"),
            "stale_agents": result.get("stale_agents", []),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="KK Coordinator Service")
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--workspaces-dir", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary", action="store_true", help="Health summary only")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy skill-only matching instead of enhanced 5-factor matching",
    )
    parser.add_argument(
        "--autojob",
        action="store_true",
        help="Use AutoJob evidence-based matching engine (with fallback to enhanced)",
    )
    parser.add_argument(
        "--autojob-path",
        type=str,
        default=None,
        help="Path to AutoJob repo (local mode). Defaults to sibling directory.",
    )
    parser.add_argument(
        "--autojob-api",
        type=str,
        default=None,
        help="AutoJob API base URL (remote mode). Overrides local mode.",
    )
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = (
        Path(args.workspace)
        if args.workspace
        else base / "data" / "workspaces" / "kk-coordinator"
    )
    workspaces_dir = (
        Path(args.workspaces_dir)
        if args.workspaces_dir
        else base / "data" / "workspaces"
    )

    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-coordinator",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    if args.autojob:
        matching_mode = "autojob (evidence-based + decay-aware)"
    elif args.legacy:
        matching_mode = "legacy (skill-only)"
    else:
        matching_mode = "enhanced (6-factor + reputation)"
    print(f"\n{'=' * 60}")
    print(f"  Karma Kadabra — Coordinator")
    print(f"  Agent: {agent.name}")
    print(f"  Matching: {matching_mode}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    client = EMClient(agent)

    try:
        if args.summary:
            summary = await get_swarm_summary()
            print(json.dumps(summary, indent=2))
        else:
            result = await coordination_cycle(
                workspaces_dir,
                client,
                dry_run=args.dry_run,
                use_legacy_matching=args.legacy,
                use_autojob=args.autojob,
                autojob_path=args.autojob_path,
                autojob_api=args.autojob_api,
            )
            print(f"\n  Matching mode: {result.get('matching_mode', 'unknown')}")
            print(f"  Performance profiles: {result.get('performance_profiles_loaded', 0)}")
            if result.get("autojob"):
                aj = result["autojob"]
                print(
                    f"  AutoJob: active={aj['used']}, "
                    f"matched={aj['tasks_matched']}, "
                    f"fallbacks={aj['fallbacks']}"
                )
            print(f"  Assignments: {len(result['assignments'])}")
            for a in result["assignments"]:
                status = "[DRY RUN]" if a.get("dry_run") else "[ASSIGNED]"
                alt = f" ({a.get('alternatives', 0)} alternatives)" if a.get("alternatives") else ""
                mode_tag = f" [{a.get('matching_mode', '')}]" if a.get("matching_mode") else ""
                print(f"    {status} {a['title'][:40]} -> {a['agent']} (score={a['score']:.3f}){alt}{mode_tag}")
            if result["stale_agents"]:
                print(f"\n  Stale agents: {', '.join(result['stale_agents'])}")
            print(f"\n  Swarm summary: {json.dumps(result['summary'], indent=2)}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
