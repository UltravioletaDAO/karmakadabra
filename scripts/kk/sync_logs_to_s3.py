#!/usr/bin/env python3
"""Incremental sync of Twitch chat logs to S3.

Watches a local log directory (full.txt) and uploads new lines
to S3 every N minutes. Designed to run while the user is streaming.

Usage:
    python sync_logs_to_s3.py --watch
    python sync_logs_to_s3.py --watch --source "Z:\\ultravioleta\\ai\\cursor\\karma-hello\\logs\\chat"
    python sync_logs_to_s3.py --once   # Single sync pass
    python sync_logs_to_s3.py --once --dry-run
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

S3_BUCKET = "karmacadabra-agent-data"
S3_REGION = "us-east-1"
DEFAULT_AGENT = "kk-karma-hello"
SYNC_INTERVAL = 300  # 5 minutes

# Matches: [M/DD/YYYY HH:MM:SS AM/PM] username: message
LOG_LINE_RE = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M)\]\s+(\S+?):\s+(.*)$"
)

STATE_FILE = ".sync_state.json"


def load_state(source: Path) -> dict:
    """Load sync state (last byte offset per file)."""
    state_path = source / STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"offsets": {}, "last_sync": None}


def save_state(source: Path, state: dict) -> None:
    """Persist sync state."""
    state_path = source / STATE_FILE
    state["last_sync"] = datetime.utcnow().isoformat()
    state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def parse_lines_to_daily(lines: list[str]) -> dict[str, list[dict]]:
    """Parse raw log lines and bucket by date."""
    daily: dict[str, list[dict]] = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = LOG_LINE_RE.match(line)
        if not m:
            continue

        timestamp_raw, user, message = m.group(1), m.group(2), m.group(3)
        if user == "unknown" and "PRIVMSG" in message:
            continue

        try:
            ts = datetime.strptime(timestamp_raw.strip(), "%m/%d/%Y %I:%M:%S %p")
            date_key = ts.strftime("%Y%m%d")
            iso_ts = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

        daily.setdefault(date_key, []).append({
            "timestamp": iso_ts,
            "user": user,
            "message": message,
        })

    return daily


def read_new_lines(filepath: Path, offset: int) -> tuple[list[str], int]:
    """Read lines from filepath starting at byte offset.

    Returns (new_lines, new_offset).
    """
    size = filepath.stat().st_size
    if size <= offset:
        return [], offset

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        f.seek(offset)
        new_data = f.read()
        new_offset = f.tell()

    lines = new_data.splitlines()
    return lines, new_offset


def upload_daily_to_s3(agent: str, daily: dict[str, list[dict]], dry_run: bool) -> int:
    """Merge new messages into existing S3 objects. Returns count of updates."""
    if dry_run:
        for date_key, msgs in daily.items():
            print(f"  [DRY-RUN] Would upload {len(msgs)} new msgs for {date_key}")
        return len(daily)

    try:
        import boto3
    except ImportError:
        print("[ERROR] boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    s3 = boto3.client("s3", region_name=S3_REGION)
    uploaded = 0

    for date_key, new_msgs in daily.items():
        s3_key = f"{agent}/logs/chat_logs_{date_key}.json"

        # Try to load existing data from S3
        existing_data = None
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
            existing_data = json.loads(resp["Body"].read().decode("utf-8"))
        except s3.exceptions.NoSuchKey:
            pass
        except Exception:
            pass

        if existing_data:
            existing_msgs = existing_data.get("messages", [])
            existing_ts = {m.get("timestamp", "") for m in existing_msgs}
            added = [m for m in new_msgs if m.get("timestamp", "") not in existing_ts]
            if not added:
                continue
            all_msgs = existing_msgs + added
        else:
            all_msgs = new_msgs
            added = new_msgs

        # Build full document
        stream_date = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
        users = set(m["user"] for m in all_msgs)
        doc = {
            "stream_id": f"stream_{date_key}_001",
            "stream_date": stream_date,
            "stream_title": f"Stream {stream_date}",
            "total_messages": len(all_msgs),
            "unique_users": len(users),
            "messages": all_msgs,
            "metadata": {
                "collection_method": "twitch_irc",
                "format_version": "1.0",
                "last_updated": datetime.utcnow().isoformat(),
            },
        }

        body = json.dumps(doc, ensure_ascii=False, indent=2)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        print(f"  [UPLOADED] {date_key}: +{len(added)} msgs (total: {len(all_msgs)})")
        uploaded += 1

    return uploaded


def sync_once(source: Path, agent: str, dry_run: bool) -> dict:
    """Run one sync pass. Returns stats dict."""
    state = load_state(source)
    full_txt = source / "full.txt"

    stats = {"new_lines": 0, "dates_updated": 0, "errors": []}

    if not full_txt.exists():
        print(f"[WARN] {full_txt} not found")
        return stats

    offset = state["offsets"].get(str(full_txt), 0)
    new_lines, new_offset = read_new_lines(full_txt, offset)

    if not new_lines:
        print(f"  No new lines since last sync (offset: {offset})")
        return stats

    stats["new_lines"] = len(new_lines)
    print(f"  Found {len(new_lines)} new lines")

    daily = parse_lines_to_daily(new_lines)
    if not daily:
        print(f"  No parseable messages in new lines")
        state["offsets"][str(full_txt)] = new_offset
        if not dry_run:
            save_state(source, state)
        return stats

    print(f"  Parsed into {len(daily)} dates: {', '.join(sorted(daily.keys()))}")

    uploaded = upload_daily_to_s3(agent, daily, dry_run)
    stats["dates_updated"] = uploaded

    if not dry_run:
        state["offsets"][str(full_txt)] = new_offset
        save_state(source, state)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Incremental sync of Twitch logs to S3"
    )
    parser.add_argument(
        "--source",
        default=r"Z:\ultravioleta\ai\cursor\karma-hello\logs\chat",
        help="Source directory with full.txt",
    )
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="Agent name")
    parser.add_argument("--watch", action="store_true", help="Continuous watch mode")
    parser.add_argument("--once", action="store_true", help="Single sync pass")
    parser.add_argument("--interval", type=int, default=SYNC_INTERVAL, help="Sync interval in seconds")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists():
        print(f"[ERROR] Source not found: {source}")
        sys.exit(1)

    print(f"\n=== Sync Logs to S3 ===")
    print(f"Source:   {source}")
    print(f"Agent:    {args.agent}")
    print(f"Bucket:   s3://{S3_BUCKET}/{args.agent}/logs/")
    if args.watch:
        print(f"Mode:     watch (every {args.interval}s)")
    else:
        print(f"Mode:     single pass")
    if args.dry_run:
        print(f"Dry-run:  YES")
    print()

    if args.watch:
        print("[WATCH] Starting continuous sync...")
        while True:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{ts}] Syncing...")
            try:
                stats = sync_once(source, args.agent, args.dry_run)
                print(f"  Result: {stats['new_lines']} new lines, {stats['dates_updated']} dates updated")
            except Exception as e:
                print(f"  [ERROR] {e}")
            print(f"  Next sync in {args.interval}s...")
            time.sleep(args.interval)
    else:
        stats = sync_once(source, args.agent, args.dry_run)
        print(f"\n=== Done === {stats['new_lines']} lines, {stats['dates_updated']} dates")
        if args.dry_run:
            print("(Dry run -- nothing was uploaded)")


if __name__ == "__main__":
    main()
