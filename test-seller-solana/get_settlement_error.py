#!/usr/bin/env python3
"""
Get the exact error from the most recent Solana settlement attempt
"""
import json
import subprocess
import re
from datetime import datetime, timedelta

# Calculate timestamp for 2 minutes ago
two_min_ago = int((datetime.utcnow() - timedelta(minutes=2)).timestamp() * 1000)

print("Querying facilitator logs for last 2 minutes...")
print(f"Start time: {datetime.fromtimestamp(two_min_ago/1000)} UTC")
print()

# Query AWS logs
cmd = [
    "aws", "logs", "filter-log-events",
    "--log-group-name", "/ecs/facilitator-production",
    "--region", "us-east-2",
    "--start-time", str(two_min_ago),
    "--max-items", "100",
    "--output", "json"
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    events = data.get("events", [])

    print(f"Retrieved {len(events)} log events")
    print("=" * 80)

    # Filter for our test time (15:22:)
    test_events = []
    for event in events:
        msg = event.get("message", "")
        if "15:22:" in msg and ("settle" in msg.lower() or "error" in msg.lower()):
            test_events.append(event)

    print(f"\nFound {len(test_events)} events from 15:22 timeframe")
    print("=" * 80)
    print()

    # Strip ANSI codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\\[[0-?]*[ -/]*[@-~])')

    for event in sorted(test_events, key=lambda x: x["timestamp"]):
        ts = datetime.fromtimestamp(event["timestamp"] / 1000).strftime("%H:%M:%S.%f")[:-3]
        msg = ansi_escape.sub('', event["message"])

        print(f"[{ts}]")
        print(msg[:1000])  # First 1000 chars
        print()

except subprocess.CalledProcessError as e:
    print(f"Error querying logs: {e}")
    print(f"Stderr: {e.stderr}")
except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")
    print(f"Output (first 1000 chars): {result.stdout[:1000]}")
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()
