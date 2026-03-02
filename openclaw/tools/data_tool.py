#!/usr/bin/env python3
"""
OpenClaw Tool: Data Inventory & Purchase Tracking

Track purchased data, list products available to sell,
and check download/processing status.
Reads JSON from stdin, outputs JSON to stdout.

Actions:
  list_purchases   — what data I have bought
  list_products    — what I have to sell (scan /app/data/)
  download_status  — pending downloads
  process_status   — processing pipeline status
"""

import sys
sys.path.insert(0, "/app")

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("kk.tool.data")

DATA_DIR = Path("/app/data")

# File extensions considered publishable data products
PUBLISHABLE_EXTENSIONS = {
    ".json", ".jsonl", ".csv", ".txt", ".md",
    ".parquet", ".sqlite", ".db",
}


def _load_escrow_state() -> dict:
    state_file = DATA_DIR / "escrow_state.json"
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def action_list_purchases(params: dict) -> dict:
    """List data purchased via EM bounties (from escrow state)."""
    state = _load_escrow_state()
    applied = state.get("applied_tasks", [])

    # Filter to tasks where we submitted or completed
    purchases = []
    for task in applied:
        status = task.get("status", "")
        if status in ("submitted", "completed", "approved"):
            purchases.append({
                "task_id": task.get("task_id", ""),
                "title": task.get("title", ""),
                "status": status,
                "bounty_usd": task.get("bounty_usd", 0),
                "timestamp": task.get("timestamp", ""),
            })

    # Also check for downloaded data files
    downloads_dir = DATA_DIR / "downloads"
    downloaded_files = []
    if downloads_dir.exists():
        for f in sorted(downloads_dir.iterdir()):
            if f.is_file():
                downloaded_files.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        f.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                })

    return {
        "purchases": purchases,
        "purchase_count": len(purchases),
        "downloaded_files": downloaded_files,
        "download_count": len(downloaded_files),
    }


def action_list_products(params: dict) -> dict:
    """Scan /app/data/ for files that can be published as data products."""
    products = []

    # Scan known product directories
    scan_dirs = [
        DATA_DIR / "products",
        DATA_DIR / "exports",
        DATA_DIR / "output",
        DATA_DIR,
    ]

    seen_paths = set()
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for f in sorted(scan_dir.iterdir()):
            if not f.is_file():
                continue
            if f.suffix.lower() not in PUBLISHABLE_EXTENSIONS:
                continue
            if f.name.startswith(".") or f.name.startswith("_"):
                continue
            # Skip state/config files
            if f.name in (
                "escrow_state.json", "irc_guard_state.json",
                "irc-inbox.jsonl", "irc-outbox.jsonl",
                "irc_sent_log.jsonl",
            ):
                continue
            real_path = str(f.resolve())
            if real_path in seen_paths:
                continue
            seen_paths.add(real_path)

            products.append({
                "path": str(f),
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "extension": f.suffix,
                "modified": datetime.fromtimestamp(
                    f.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            })

    return {
        "products": products,
        "count": len(products),
    }


def action_download_status(params: dict) -> dict:
    """Check for pending downloads (tasks assigned but data not yet received)."""
    state = _load_escrow_state()
    applied = state.get("applied_tasks", [])

    pending = []
    for task in applied:
        status = task.get("status", "")
        if status in ("accepted", "assigned"):
            pending.append({
                "task_id": task.get("task_id", ""),
                "title": task.get("title", ""),
                "status": status,
                "timestamp": task.get("timestamp", ""),
            })

    return {
        "pending_downloads": pending,
        "count": len(pending),
    }


def action_process_status(params: dict) -> dict:
    """Check processing pipeline status from state files in /app/data/."""
    status = {
        "processing_queue": [],
        "completed": [],
        "errors": [],
    }

    # Check for processing state files
    for state_file in DATA_DIR.glob("*_state.json"):
        if state_file.name in ("escrow_state.json", "irc_guard_state.json"):
            continue
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            status["processing_queue"].append({
                "name": state_file.stem,
                "status": data.get("status", "unknown"),
                "updated": datetime.fromtimestamp(
                    state_file.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        except (json.JSONDecodeError, OSError):
            status["errors"].append(state_file.name)

    # Check for recent output
    output_dir = DATA_DIR / "output"
    if output_dir.exists():
        recent = sorted(output_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        for f in recent[:10]:
            if f.is_file():
                status["completed"].append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        f.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                })

    return status


ACTIONS = {
    "list_purchases": action_list_purchases,
    "list_products": action_list_products,
    "download_status": action_download_status,
    "process_status": action_process_status,
}


def main():
    try:
        raw = sys.stdin.read()
        request = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        return

    action = request.get("action", "")
    params = request.get("params", {})

    if action not in ACTIONS:
        print(json.dumps({
            "error": f"Unknown action: {action}",
            "available": list(ACTIONS.keys()),
        }))
        return

    try:
        result = ACTIONS[action](params)
        print(json.dumps(result, default=str))
    except Exception as e:
        logger.exception("data_tool action failed")
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))


if __name__ == "__main__":
    main()
