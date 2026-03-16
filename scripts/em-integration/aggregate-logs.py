"""
Karma Kadabra V2 — Task 2.1: Log Aggregation

Reads all Karma Hello chat logs across all dates,
parses the log format, and outputs a unified JSON dataset.

Usage:
  python aggregate-logs.py --logs-dir Z:/ultravioleta/dao/karmacadabra/agents/karma-hello/logs
  python aggregate-logs.py --logs-dir ../../../karmacadabra/agents/karma-hello/logs --output data/aggregated.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Log line parser
# ---------------------------------------------------------------------------

# Support both single and double-digit month/day (e.g., 1/2/2026 or 01/02/2026)
LOG_PATTERN = re.compile(
    r"\[(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M)\]\s+(\S+?):\s+(.*)"
)

# Filter out raw IRC protocol lines (PRIVMSG with full prefix)
IRC_RAW_PATTERN = re.compile(r"^\S+!\S+@\S+\.tmi\.twitch\.tv\s+PRIVMSG")


def parse_line(line: str) -> dict | None:
    """Parse a single log line into structured data."""
    line = line.strip()
    if not line:
        return None

    m = LOG_PATTERN.match(line)
    if not m:
        return None

    timestamp_str, username, message = m.groups()

    # Skip "unknown" entries that contain raw IRC protocol data
    if username == "unknown" and IRC_RAW_PATTERN.match(message):
        return None

    try:
        ts = datetime.strptime(timestamp_str, "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None

    return {
        "timestamp": ts.isoformat(),
        "username": username.lower(),
        "message": message.strip(),
        "date": ts.strftime("%Y%m%d"),
        "hour": ts.hour,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_logs(logs_dir: Path) -> dict:
    """Read all full.txt files and aggregate into unified dataset."""
    all_messages: list[dict] = []
    dates_found: list[str] = []
    users: set[str] = set()
    duplicates_removed = 0

    # Find all date directories
    date_dirs = sorted(
        [d for d in logs_dir.iterdir() if d.is_dir() and d.name.isdigit()],
        key=lambda d: d.name,
    )

    if not date_dirs:
        print(f"ERROR: No date directories found in {logs_dir}")
        sys.exit(1)

    for date_dir in date_dirs:
        full_txt = date_dir / "full.txt"
        if not full_txt.exists():
            print(f"  WARNING: No full.txt in {date_dir.name}")
            continue

        dates_found.append(date_dir.name)
        date_messages = []
        seen_in_date: set[str] = set()

        with open(full_txt, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parsed = parse_line(line)
                if parsed is None:
                    continue

                # Dedup within same date (same timestamp + username + message)
                dedup_key = f"{parsed['timestamp']}|{parsed['username']}|{parsed['message']}"
                if dedup_key in seen_in_date:
                    duplicates_removed += 1
                    continue
                seen_in_date.add(dedup_key)

                date_messages.append(parsed)
                users.add(parsed["username"])

        all_messages.extend(date_messages)
        print(f"  {date_dir.name}: {len(date_messages)} messages, {len(set(m['username'] for m in date_messages))} users")

    # Sort by timestamp
    all_messages.sort(key=lambda m: m["timestamp"])

    result = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "source": str(logs_dir),
        "stats": {
            "total_messages": len(all_messages),
            "unique_users": len(users),
            "dates": dates_found,
            "date_count": len(dates_found),
            "duplicates_removed": duplicates_removed,
        },
        "users": sorted(users),
        "messages": all_messages,
    }

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Aggregate Karma Hello chat logs")
    parser.add_argument(
        "--logs-dir",
        type=str,
        default=None,
        help="Path to karma-hello logs directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file (default: data/aggregated.json)",
    )
    args = parser.parse_args()

    # Default: look for karmacadabra sibling repo relative to execution-market
    if args.logs_dir:
        logs_dir = Path(args.logs_dir)
    else:
        logs_dir = Path(__file__).parent.parent.parent.parent / "karmacadabra" / "agents" / "karma-hello" / "logs"
    if not logs_dir.exists():
        print(f"ERROR: Logs directory not found: {logs_dir}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else Path(__file__).parent / "data" / "aggregated.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nAggregating logs from: {logs_dir}")
    print(f"Output: {output_path}\n")

    result = aggregate_logs(logs_dir)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nDone!")
    print(f"  Messages: {result['stats']['total_messages']}")
    print(f"  Users:    {result['stats']['unique_users']}")
    print(f"  Dates:    {result['stats']['date_count']}")
    print(f"  Dupes:    {result['stats']['duplicates_removed']} removed")
    print(f"  Output:   {output_path}")


if __name__ == "__main__":
    main()
