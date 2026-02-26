#!/usr/bin/env python3
"""Upload Twitch chat logs to S3 for agent consumption.

Reads raw text logs (full.txt format) or JSON structured logs,
converts to the JSON format karma-hello expects, and uploads
to s3://karmacadabra-agent-data/<agent>/logs/.

Usage:
    python upload_logs_to_s3.py --source ~/twitch-logs/ --agent kk-karma-hello
    python upload_logs_to_s3.py --source ~/twitch-logs/ --agent kk-karma-hello --dry-run
    python upload_logs_to_s3.py --source agents/karma-hello/logs/ --agent kk-karma-hello --format text
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

S3_BUCKET = "karmacadabra-agent-data"
S3_REGION = "us-east-1"

# [MM/DD/YYYY HH:MM:SS AM/PM] username: message
LOG_LINE_RE = re.compile(
    r"^\[(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M)\]\s+(\S+?):\s+(.*)$"
)


def parse_text_log(text: str, date_str: str) -> dict:
    """Parse a full.txt log into structured JSON format."""
    messages = []
    users = Counter()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = LOG_LINE_RE.match(line)
        if not m:
            continue
        timestamp_raw, user, message = m.group(1), m.group(2), m.group(3)
        # Skip malformed IRC lines captured as 'unknown'
        if user == "unknown" and "PRIVMSG" in message:
            continue
        try:
            ts = datetime.strptime(timestamp_raw, "%m/%d/%Y %I:%M:%S %p")
            iso_ts = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            iso_ts = timestamp_raw
        messages.append({
            "timestamp": iso_ts,
            "user": user,
            "message": message,
        })
        users[user] += 1

    if not messages:
        return {}

    # Derive date from date_str (folder name like 20251015)
    try:
        stream_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        stream_date = date_str

    total = len(messages)
    unique = len(users)
    first_ts = messages[0]["timestamp"]
    last_ts = messages[-1]["timestamp"]

    # Calculate duration in minutes for messages_per_minute
    try:
        t0 = datetime.fromisoformat(first_ts.replace("Z", ""))
        t1 = datetime.fromisoformat(last_ts.replace("Z", ""))
        duration_min = max((t1 - t0).total_seconds() / 60, 1)
    except Exception:
        duration_min = max(total, 1)

    top_users = [{"user": u, "count": c} for u, c in users.most_common(10)]

    return {
        "stream_id": f"stream_{date_str}_001",
        "stream_date": stream_date,
        "stream_title": f"Stream {stream_date}",
        "total_messages": total,
        "unique_users": unique,
        "messages": messages,
        "statistics": {
            "messages_per_minute": round(total / duration_min, 2),
            "most_active_users": top_users,
        },
        "metadata": {
            "collection_method": "twitch_irc",
            "format_version": "1.0",
            "first_message": first_ts,
            "last_message": last_ts,
        },
    }


def find_text_logs(source: Path) -> list[tuple[str, Path]]:
    """Find all full.txt files organized by YYYYMMDD folders."""
    results = []
    for folder in sorted(source.iterdir()):
        if not folder.is_dir():
            continue
        # Folder name should be YYYYMMDD
        if not re.match(r"^\d{8}$", folder.name):
            continue
        full_txt = folder / "full.txt"
        if full_txt.exists():
            results.append((folder.name, full_txt))
    return results


def find_json_logs(source: Path) -> list[Path]:
    """Find all JSON log files."""
    return sorted(source.glob("chat_logs_*.json")) + sorted(source.glob("*.json"))


def process_source(source: Path, fmt: str) -> list[tuple[str, dict]]:
    """Process source directory, return list of (s3_key_suffix, data)."""
    output = []

    if fmt == "text":
        logs = find_text_logs(source)
        if not logs:
            print(f"[WARN] No YYYYMMDD/full.txt logs found in {source}")
            return output
        for date_str, log_path in logs:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            data = parse_text_log(text, date_str)
            if data:
                key = f"logs/chat_logs_{date_str}.json"
                output.append((key, data))
                print(f"  [OK] {date_str}: {data['total_messages']} msgs, {data['unique_users']} users")
            else:
                print(f"  [SKIP] {date_str}: no parseable messages")
    elif fmt == "json":
        json_files = find_json_logs(source)
        if not json_files:
            print(f"[WARN] No JSON log files found in {source}")
            return output
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                key = f"logs/{jf.name}"
                output.append((key, data))
                print(f"  [OK] {jf.name}: {data.get('total_messages', '?')} msgs")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  [SKIP] {jf.name}: {e}")
    else:
        # Auto-detect
        text_logs = find_text_logs(source)
        json_logs = find_json_logs(source)
        if text_logs:
            print(f"[AUTO] Found {len(text_logs)} text log folders")
            return process_source(source, "text")
        elif json_logs:
            print(f"[AUTO] Found {len(json_logs)} JSON log files")
            return process_source(source, "json")
        else:
            print(f"[ERROR] No logs found in {source}")

    return output


def upload_to_s3(agent: str, items: list[tuple[str, dict]], dry_run: bool) -> int:
    """Upload processed logs to S3. Returns count of uploaded files."""
    if dry_run:
        for key, data in items:
            print(f"  [DRY-RUN] s3://{S3_BUCKET}/{agent}/{key} ({data.get('total_messages', '?')} msgs)")
        return len(items)

    try:
        import boto3
    except ImportError:
        print("[ERROR] boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    s3 = boto3.client("s3", region_name=S3_REGION)
    uploaded = 0

    for key, data in items:
        s3_key = f"{agent}/{key}"
        body = json.dumps(data, ensure_ascii=False, indent=2)
        try:
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
            uploaded += 1
            print(f"  [UPLOADED] s3://{S3_BUCKET}/{s3_key}")
        except Exception as e:
            print(f"  [FAIL] {s3_key}: {e}")

    return uploaded


def main():
    parser = argparse.ArgumentParser(
        description="Upload Twitch chat logs to S3 for agent consumption"
    )
    parser.add_argument(
        "--source", required=True, help="Source directory with logs"
    )
    parser.add_argument(
        "--agent", default="kk-karma-hello", help="Agent name (default: kk-karma-hello)"
    )
    parser.add_argument(
        "--format", choices=["text", "json", "auto"], default="auto",
        help="Log format: text (full.txt), json (chat_logs_*.json), auto (detect)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be uploaded without uploading"
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists():
        print(f"[ERROR] Source directory not found: {source}")
        sys.exit(1)

    print(f"\n=== Upload Logs to S3 ===")
    print(f"Source:  {source}")
    print(f"Agent:   {args.agent}")
    print(f"Bucket:  s3://{S3_BUCKET}/{args.agent}/logs/")
    print(f"Format:  {args.format}")
    print(f"Dry-run: {args.dry_run}\n")

    print("[Phase 1] Processing logs...")
    items = process_source(source, args.format)

    if not items:
        print("\n[DONE] No logs to upload.")
        sys.exit(0)

    # Summary stats
    total_msgs = sum(d.get("total_messages", 0) for _, d in items)
    all_users = set()
    for _, d in items:
        for msg in d.get("messages", []):
            all_users.add(msg.get("user", ""))

    print(f"\n[Summary] {len(items)} streams, {total_msgs} messages, {len(all_users)} unique users\n")

    print("[Phase 2] Uploading to S3...")
    uploaded = upload_to_s3(args.agent, items, args.dry_run)

    print(f"\n=== Done === {uploaded}/{len(items)} files uploaded")
    if args.dry_run:
        print("(Dry run -- nothing was actually uploaded)")


if __name__ == "__main__":
    main()
