#!/usr/bin/env python3
"""
Convert karma-hello TXT logs to JSON format expected by the agent.

Reads logs from agents/karma-hello/logs/ directory structure:
  - logs/YYYYMMDD/full.txt
  - logs/YYYYMMDD/username.txt

Outputs JSON files in the format:
  - chat_logs_YYYYMMDD.json
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import sys

# Regex to parse log lines: [MM/DD/YYYY HH:MM:SS AM/PM] username: message
LOG_LINE_PATTERN = re.compile(
    r'\[(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM))\]\s+(\w+):\s+(.+)'
)


def parse_log_line(line: str) -> Dict[str, Any]:
    """Parse a single log line into a message dict"""
    match = LOG_LINE_PATTERN.match(line.strip())
    if not match:
        return None

    timestamp_str, user, message = match.groups()

    # Convert timestamp to ISO 8601
    dt = datetime.strptime(timestamp_str, "%m/%d/%Y %I:%M:%S %p")
    iso_timestamp = dt.isoformat() + "Z"

    return {
        "timestamp": iso_timestamp,
        "user": user,
        "message": message,
        "user_badges": []
    }


def convert_txt_to_json(txt_file: Path, output_dir: Path, date_str: str):
    """Convert a full.txt file to JSON format"""

    if not txt_file.exists():
        print(f"  [SKIP] {txt_file} not found")
        return

    print(f"  [CONVERT] {txt_file}")

    # Read all lines
    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Parse messages
    messages = []
    for line in lines:
        parsed = parse_log_line(line)
        if parsed:
            messages.append(parsed)

    # Count unique users
    unique_users = len(set(m["user"] for m in messages))

    # Create JSON structure
    json_data = {
        "stream_id": f"stream_{date_str}_001",
        "stream_date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
        "stream_title": "Twitch Stream",
        "streamer": "ultravioletadao",
        "duration_minutes": 180,
        "total_messages": len(messages),
        "unique_users": unique_users,
        "messages": messages,
        "statistics": {
            "avg_messages_per_user": len(messages) / unique_users if unique_users > 0 else 0,
            "most_active_users": []
        }
    }

    # Write JSON file
    output_file = output_dir / f"chat_logs_{date_str}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"    -> {output_file} ({len(messages)} messages, {unique_users} users)")


def main():
    """Convert all production logs to JSON"""

    # Paths (can be overridden by command line args)
    if len(sys.argv) > 1:
        logs_dir = Path(sys.argv[1])
    else:
        logs_dir = Path("/app/logs")  # Default for Docker

    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])
    else:
        output_dir = Path("/app/data/karma-hello")  # Default for Docker

    print(f"Converting TXT logs to JSON")
    print(f"  Input:  {logs_dir}")
    print(f"  Output: {output_dir}")
    print()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all date directories (YYYYMMDD format)
    date_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir() and d.name.isdigit()])

    if not date_dirs:
        print(f"[WARN] No date directories found in {logs_dir}")
        return

    # Convert each date
    for date_dir in date_dirs:
        date_str = date_dir.name  # YYYYMMDD
        full_txt = date_dir / "full.txt"

        convert_txt_to_json(full_txt, output_dir, date_str)

    print()
    print(f"[SUCCESS] Converted {len(date_dirs)} log files")


if __name__ == "__main__":
    main()
