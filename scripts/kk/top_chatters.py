#!/usr/bin/env python3
"""
Top Chatters — Rank Twitch chat users by message count.

Usage:
    python scripts/kk/top_chatters.py 18
    python scripts/kk/top_chatters.py 50
    python scripts/kk/top_chatters.py          # default: top 18
"""

import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_TOP = 18
LOG_FILE = Path(r"z:\ultravioleta\ai\cursor\karma-hello\logs\chat\full.txt")

# [date time] username: message
LINE_PATTERN = re.compile(r"^\[.*?\]\s+(.+?):\s")

# Bots and system accounts to exclude
BOTS = {
    "nightbot",
    "streamelements",
    "streamlabs",
    "moobot",
    "fossabot",
    "soundalerts",
    "commanderroot",
    "anotherttvviewer",
    "streamelementsbot",
}


def count_messages(log_path: Path) -> Counter:
    counts = Counter()
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_PATTERN.match(line)
            if m:
                username = m.group(1).strip().lower()
                if username not in BOTS:
                    counts[username] += 1
    return counts


def main():
    top_n = DEFAULT_TOP
    if len(sys.argv) > 1:
        try:
            top_n = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [N]  (e.g. 18, 50)")
            sys.exit(1)

    if not LOG_FILE.exists():
        print(f"Log file not found: {LOG_FILE}")
        sys.exit(1)

    counts = count_messages(LOG_FILE)
    total_messages = sum(counts.values())
    total_users = len(counts)
    ranking = counts.most_common(top_n)

    print(f"\n{'=' * 60}")
    print(f"  TOP {top_n} CHATTERS — KarmaHello Twitch Logs")
    print(f"  Total: {total_messages:,} messages from {total_users:,} users")
    print(f"{'=' * 60}\n")
    print(f"  {'#':>4}  {'Username':<25} {'Messages':>10}  {'% Total':>8}")
    print(f"  {'----'}  {'-' * 25} {'-' * 10}  {'-' * 8}")

    for i, (user, count) in enumerate(ranking, 1):
        pct = (count / total_messages) * 100
        print(f"  {i:>4}  {user:<25} {count:>10,}  {pct:>7.2f}%")

    top_total = sum(c for _, c in ranking)
    top_pct = (top_total / total_messages) * 100
    print(f"\n  {'----'}  {'-' * 25} {'-' * 10}  {'-' * 8}")
    print(f"        {'Top ' + str(top_n) + ' total':<25} {top_total:>10,}  {top_pct:>7.2f}%")
    print()


if __name__ == "__main__":
    main()
