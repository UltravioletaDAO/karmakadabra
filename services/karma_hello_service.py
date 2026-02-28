"""
Karma Kadabra V2 — Phase 9.2: Karma Hello Service

Enhanced Karma Hello service with three operational cycles integrated
into the heartbeat system:

  - Collect: Scan data/irc-logs/ for new daily logs, aggregate into
             data/aggregated.json for analysis pipeline.
  - Publish: Use PRODUCTS catalog from karma_hello_seller.py to publish
             data offerings on Execution Market.
  - Fulfill: Check for purchased tasks (submitted status) and auto-approve
             data deliveries.

Integrates with swarm_state.report_heartbeat() for coordinator visibility.

Usage:
  python karma_hello_service.py --collect               # Run collect cycle only
  python karma_hello_service.py --publish               # Run publish cycle only
  python karma_hello_service.py --fulfill               # Run fulfill cycle only
  python karma_hello_service.py --all                   # Run all three cycles
  python karma_hello_service.py --all --dry-run         # Preview without side effects
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure parent packages are importable
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from em_client import AgentContext, EMClient, load_agent_context
from karma_hello_seller import PRODUCTS, load_data_stats
from lib.swarm_state import report_heartbeat

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.karma-hello-service")

# Budget guard
MAX_DAILY_SPEND_USD = 0.50


# ---------------------------------------------------------------------------
# Collect cycle
# ---------------------------------------------------------------------------


def collect_all_logs(data_dir: Path, dry_run: bool = False) -> dict[str, Any]:
    """Scan irc-logs/ AND S3-synced logs/ for data and aggregate into aggregated.json.

    Memory-optimized: tracks processed files in .collect_state.json so that
    subsequent heartbeats skip re-reading the entire aggregated.json (~76 MB)
    when no new source files have appeared.  This prevents OOM kills on
    t3.small instances (1.8 GB RAM).

    Sources:
      1. data/irc-logs/*.json  — JSONL daily logs from live IRC collection
      2. data/logs/chat_logs_*.json — S3-synced Twitch logs (array format)

    Returns:
        Dict with files_found, new_messages, total_messages, dates.
    """
    irc_logs_dir = data_dir / "irc-logs"
    s3_logs_dir = data_dir / "logs"
    agg_file = data_dir / "aggregated.json"
    state_file = data_dir / ".collect_state.json"

    result: dict[str, Any] = {
        "files_found": 0,
        "new_messages": 0,
        "total_messages": 0,
        "dates": [],
        "sources": {"irc_logs": 0, "s3_logs": 0},
    }

    # Load collection state (lightweight — just file paths and counts)
    state: dict[str, Any] = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {}

    processed_files: set[str] = set(state.get("processed_files", []))

    # Discover all source files
    irc_files: list[Path] = []
    s3_files: list[Path] = []
    if irc_logs_dir.exists():
        irc_files = sorted(irc_logs_dir.glob("*.json"))
    if s3_logs_dir.exists():
        s3_files = sorted(s3_logs_dir.glob("chat_logs_*.json"))

    all_source_paths = {str(f) for f in irc_files} | {str(f) for f in s3_files}
    new_file_paths = all_source_paths - processed_files

    result["files_found"] = len(all_source_paths)
    result["sources"]["irc_logs"] = len(irc_files)
    result["sources"]["s3_logs"] = len(s3_files)

    # Fast path: no new files → return cached stats without touching aggregated.json
    if not new_file_paths:
        result["total_messages"] = state.get("total_messages", 0)
        result["dates"] = state.get("dates", [])
        logger.info(
            f"No new files to process ({len(all_source_paths)} already processed, "
            f"{result['total_messages']} messages cached)"
        )
        return result

    if not irc_logs_dir.exists() and not s3_logs_dir.exists():
        logger.info("No log directories found (irc-logs/ or logs/) — nothing to collect")
        return result

    # --- Slow path: new files detected — load existing data and merge ---
    logger.info(f"{len(new_file_paths)} new source files detected — running full collect")

    existing: dict[str, Any] = {"messages": [], "stats": {}}
    existing_keys: set[str] = set()
    if agg_file.exists():
        try:
            existing = json.loads(agg_file.read_text(encoding="utf-8"))
            for m in existing.get("messages", []):
                key = m.get("ts") or f"{m.get('timestamp', '')}|{m.get('user', '')}"
                if key:
                    existing_keys.add(key)
        except (json.JSONDecodeError, KeyError):
            pass

    all_messages: list[dict] = list(existing.get("messages", []))
    new_count = 0
    dates: set[str] = set()

    # --- Source 1: irc-logs/ (JSONL daily files) ---
    for log_file in irc_files:
        if str(log_file) in processed_files:
            dates.add(log_file.stem)
            continue
        date_str = log_file.stem
        dates.add(date_str)
        for line in log_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("ts", "")
                if ts and ts not in existing_keys:
                    all_messages.append(entry)
                    existing_keys.add(ts)
                    new_count += 1
            except json.JSONDecodeError:
                continue

    # --- Source 2: logs/ (S3-synced Twitch chat logs) ---
    for s3_file in s3_files:
        date_str = s3_file.stem.replace("chat_logs_", "")
        if len(date_str) == 8:
            date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        dates.add(date_str)
        if str(s3_file) in processed_files:
            continue
        try:
            data = json.loads(s3_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        messages = data.get("messages", [])
        for msg in messages:
            ts = msg.get("timestamp", "")
            user = msg.get("user", "")
            dedup_key = f"{ts}|{user}"
            if dedup_key in existing_keys:
                continue
            unified = {
                "ts": ts,
                "user": user,
                "message": msg.get("message", ""),
                "source": "s3_twitch",
                "date": date_str,
            }
            all_messages.append(unified)
            existing_keys.add(dedup_key)
            new_count += 1

    result["new_messages"] = new_count
    result["total_messages"] = len(all_messages)
    result["dates"] = sorted(dates)

    if new_count == 0:
        logger.info("No new messages to aggregate")
    else:
        logger.info(
            f"Collected {new_count} new messages from {len(new_file_paths)} new files "
            f"(irc: {result['sources']['irc_logs']}, s3: {result['sources']['s3_logs']})"
        )

    if not dry_run and new_count > 0:
        agg_data = {
            "messages": all_messages,
            "stats": {
                "total_messages": len(all_messages),
                "date_count": len(dates),
                "dates": sorted(dates),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
        }
        data_dir.mkdir(parents=True, exist_ok=True)
        agg_file.write_text(
            json.dumps(agg_data, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Aggregated {len(all_messages)} messages -> {agg_file}")

    # Persist collection state (always, even if no new messages)
    if not dry_run:
        new_state = {
            "processed_files": sorted(all_source_paths),
            "total_messages": len(all_messages) if all_messages else state.get("total_messages", 0),
            "dates": sorted(dates) if dates else state.get("dates", []),
            "sources": result["sources"],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        try:
            state_file.write_text(
                json.dumps(new_state, indent=2), encoding="utf-8",
            )
        except OSError:
            pass

    return result


# ---------------------------------------------------------------------------
# Publish cycle
# ---------------------------------------------------------------------------


async def publish_offerings(
    client: EMClient,
    data_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Publish data product offerings on EM using PRODUCTS catalog.

    Returns:
        Dict with published count and skipped reasons.
    """
    result: dict[str, Any] = {
        "published": 0,
        "skipped": 0,
        "errors": [],
    }

    stats = load_data_stats(data_dir)
    if stats["total_messages"] == 0:
        logger.info("No data to sell — aggregate first with --collect")
        result["skipped"] = len(PRODUCTS)
        return result

    # Check existing published tasks to avoid duplicates
    existing_titles: set[str] = set()
    try:
        existing = await client.browse_tasks(status="published", category="knowledge_access", limit=50)
        existing_titles = {t.get("title", "") for t in existing}
    except Exception:
        pass  # If listing fails, publish anyway

    for key, product in PRODUCTS.items():
        title = product["title"].format(**stats)
        description = product["description"].format(**stats)
        bounty = product["bounty"]

        # Skip if already published with same title
        if title in existing_titles:
            logger.info(f"Already published: {key} — skipping duplicate")
            result["skipped"] += 1
            continue

        # Budget check
        if not client.agent.can_spend(bounty):
            logger.warning(
                f"Budget exhausted — skipping {key} "
                f"(spent ${client.agent.daily_spent_usd:.2f})"
            )
            result["skipped"] += 1
            continue

        # Global safety cap
        if client.agent.daily_spent_usd + bounty > MAX_DAILY_SPEND_USD:
            logger.warning(
                f"Would exceed safety cap ${MAX_DAILY_SPEND_USD} — skipping {key}"
            )
            result["skipped"] += 1
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would publish: {title} (${bounty})")
            result["published"] += 1
            continue

        try:
            resp = await client.publish_task(
                title=title,
                instructions=description,
                category=product["category"],
                bounty_usd=bounty,
                deadline_hours=24,
                evidence_required=["json_response"],
            )
            task_id = resp.get("task", {}).get("id") or resp.get("id", "unknown")
            logger.info(f"Published {key}: task_id={task_id} (${bounty})")
            client.agent.record_spend(bounty)
            result["published"] += 1
        except Exception as e:
            logger.error(f"Failed to publish {key}: {e}")
            result["errors"].append(f"{key}: {e}")

    return result


# ---------------------------------------------------------------------------
# Fulfill cycle
# ---------------------------------------------------------------------------


async def fulfill_purchases(
    client: EMClient,
    dry_run: bool = False,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """Assign pending applicants and auto-approve submitted deliveries.

    Two-phase fulfillment:
      Phase A — Assign: fetch published tasks with pending applications,
                auto-assign the first applicant so they can start work.
      Phase B — Approve: fetch submitted tasks, review and approve
                completed submissions with data delivery URLs.

    Returns:
        Dict with assigned, approved, and error counts.
    """
    result: dict[str, Any] = {
        "assigned": 0,
        "reviewed": 0,
        "approved": 0,
        "skipped": 0,
        "errors": [],
    }

    # --- Phase A: Auto-assign pending applications ---
    # Throttle: max 5 task detail checks per cycle to avoid 429
    MAX_CHECKS_PER_CYCLE = 5

    try:
        published_tasks = await client.list_tasks(
            agent_wallet=client.agent.wallet_address,
            status="published",
        )
    except Exception as e:
        logger.warning(f"Failed to list published tasks: {e}")
        published_tasks = []

    kk_tasks = [t for t in published_tasks if t.get("title", "").startswith("[KK Data]")]
    checked = 0

    for task in kk_tasks:
        if checked >= MAX_CHECKS_PER_CYCLE:
            break
        task_id = task.get("id", "")
        title = task.get("title", "")

        # Throttle between requests
        if checked > 0:
            await asyncio.sleep(1.0)
        checked += 1

        # Get full task detail (includes applications)
        try:
            detail = await client.get_task(task_id)
        except Exception as e:
            logger.warning(f"Failed to get task detail {task_id}: {e}")
            continue

        applications = detail.get("applications", [])
        if not applications:
            continue

        # Auto-assign ALL applicants (not just first)
        for applicant in applications:
            executor_id = applicant.get("executor_id", "")
            if not executor_id:
                continue

            status = applicant.get("status", "")
            if status == "assigned":
                continue  # Already assigned

            applicant_name = applicant.get("display_name", executor_id[:8])
            if dry_run:
                logger.info(f"[DRY RUN] Would assign {applicant_name} to {title}")
                result["assigned"] += 1
                continue

            try:
                await client.assign_task(task_id, executor_id)
                logger.info(f"Assigned {applicant_name} to: {title}")
                result["assigned"] += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                err_str = str(e)
                if "409" in err_str or "already" in err_str.lower():
                    continue  # Already assigned, skip
                logger.error(f"Failed to assign {task_id}: {e}")
                result["errors"].append(f"assign({task_id}): {e}")

    # --- Phase B: Auto-approve submitted deliveries ---
    try:
        await asyncio.sleep(1.0)  # Throttle between phases
        my_tasks = await client.list_tasks(
            agent_wallet=client.agent.wallet_address,
            status="submitted",
        )
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        result["errors"].append(str(e))
        return result

    for task in my_tasks[:MAX_CHECKS_PER_CYCLE]:
        task_id = task.get("id", "")
        title = task.get("title", "")

        # Only auto-approve our own KK Data offerings
        if not title.startswith("[KK Data]"):
            continue

        result["reviewed"] += 1
        logger.info(f"Reviewing: {title}")

        try:
            await asyncio.sleep(0.5)
            submissions = await client.get_submissions(task_id)
        except Exception as e:
            logger.error(f"Failed to get submissions for {task_id}: {e}")
            result["errors"].append(f"get_submissions({task_id}): {e}")
            continue

        for sub in submissions:
            sub_id = sub.get("id", "")

            if dry_run:
                logger.info(f"[DRY RUN] Would approve submission {sub_id}")
                result["approved"] += 1
                continue

            # Generate presigned URL for data delivery
            delivery_url = None
            if data_dir:
                try:
                    from services.data_delivery import prepare_delivery_package
                    # Determine product key from title
                    product_key = "raw_logs"  # default
                    title_lower = title.lower()
                    if "stat" in title_lower:
                        product_key = "user_stats"
                    elif "topic" in title_lower:
                        product_key = "topic_map"
                    elif "skill" in title_lower:
                        product_key = "skill_profile"

                    delivery_url = await prepare_delivery_package(
                        "kk-karma-hello", product_key, data_dir,
                    )
                except ImportError:
                    logger.debug("data_delivery module not available")
                except Exception as e:
                    logger.warning(f"Delivery URL generation failed: {e}")

            try:
                notes = "KK data delivery auto-approved"
                if delivery_url:
                    notes = f"KK data delivery: {delivery_url}"

                await client.approve_submission(
                    sub_id,
                    rating_score=90,
                    notes=notes,
                )
                logger.info(f"Approved submission {sub_id}")
                result["approved"] += 1
            except Exception as e:
                logger.error(f"Failed to approve {sub_id}: {e}")
                result["errors"].append(f"approve({sub_id}): {e}")

    return result


# ---------------------------------------------------------------------------
# Combined service runner
# ---------------------------------------------------------------------------


async def run_service(
    data_dir: Path,
    workspace_dir: Path,
    run_collect: bool = False,
    run_publish: bool = False,
    run_fulfill: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run one or more Karma Hello service cycles.

    Returns:
        Combined results dict.
    """
    results: dict[str, Any] = {"cycles_run": []}

    # Load agent
    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-karma-hello",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    # Report heartbeat: starting
    if not dry_run:
        try:
            await report_heartbeat(
                agent_name="kk-karma-hello",
                status="busy",
                notes="service cycle starting",
                daily_spent=agent.daily_spent_usd,
            )
        except Exception:
            pass

    client = EMClient(agent)

    try:
        # Health check
        try:
            health = await client.health()
            logger.info(f"EM API: {health.get('status', 'unknown')}")
        except Exception as e:
            logger.warning(f"Health check failed (continuing anyway): {e}")

        # Collect cycle
        if run_collect:
            logger.info("--- Collect cycle ---")
            collect_result = collect_all_logs(data_dir, dry_run=dry_run)
            results["collect"] = collect_result
            results["cycles_run"].append("collect")

        # Publish cycle
        if run_publish:
            logger.info("--- Publish cycle ---")
            publish_result = await publish_offerings(client, data_dir, dry_run=dry_run)
            results["publish"] = publish_result
            results["cycles_run"].append("publish")

        # Fulfill cycle
        if run_fulfill:
            logger.info("--- Fulfill cycle ---")
            fulfill_result = await fulfill_purchases(client, dry_run=dry_run, data_dir=data_dir)
            results["fulfill"] = fulfill_result
            results["cycles_run"].append("fulfill")

    finally:
        await client.close()

    # Report heartbeat: done
    if not dry_run:
        try:
            await report_heartbeat(
                agent_name="kk-karma-hello",
                status="idle",
                notes=f"cycles: {', '.join(results['cycles_run'])}",
                daily_spent=agent.daily_spent_usd,
            )
        except Exception:
            pass

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Karma Hello Service (KK V2)")
    parser.add_argument("--collect", action="store_true", help="Run collect cycle")
    parser.add_argument("--publish", action="store_true", help="Run publish cycle")
    parser.add_argument("--fulfill", action="store_true", help="Run fulfill cycle")
    parser.add_argument("--all", action="store_true", help="Run all three cycles")
    parser.add_argument("--workspace", type=str, default=None, help="Workspace dir")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without side effects")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = (
        Path(args.workspace) if args.workspace
        else base / "data" / "workspaces" / "kk-karma-hello"
    )
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    run_collect = args.collect or args.all
    run_publish = args.publish or args.all
    run_fulfill = args.fulfill or args.all

    if not (run_collect or run_publish or run_fulfill):
        parser.print_help()
        print("\nSpecify at least one cycle: --collect, --publish, --fulfill, or --all")
        return

    print(f"\n{'=' * 60}")
    print(f"  Karma Hello Service")
    print(f"  Cycles: {', '.join(c for c, v in [('collect', run_collect), ('publish', run_publish), ('fulfill', run_fulfill)] if v)}")
    print(f"  Data dir: {data_dir}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    results = await run_service(
        data_dir=data_dir,
        workspace_dir=workspace_dir,
        run_collect=run_collect,
        run_publish=run_publish,
        run_fulfill=run_fulfill,
        dry_run=args.dry_run,
    )

    # Summary
    print(f"\n  Cycles completed: {', '.join(results['cycles_run'])}")
    if "collect" in results:
        c = results["collect"]
        print(f"  Collect: {c['new_messages']} new messages from {c['files_found']} files")
    if "publish" in results:
        p = results["publish"]
        print(f"  Publish: {p['published']} products, {p['skipped']} skipped")
    if "fulfill" in results:
        f = results["fulfill"]
        print(f"  Fulfill: {f.get('assigned', 0)} assigned, {f['approved']} approved, {f['reviewed']} reviewed")
    print()


if __name__ == "__main__":
    asyncio.run(main())
