#!/usr/bin/env python3
"""
Analyze facilitator logs for Solana settlement attempts
"""
import json
import subprocess
import re
from datetime import datetime, timedelta

# Calculate timestamp for 1 hour ago (in milliseconds)
one_hour_ago = int((datetime.utcnow() - timedelta(hours=1)).timestamp() * 1000)

print("Fetching logs from AWS CloudWatch...")
print(f"Time range: Last 1 hour (since {datetime.fromtimestamp(one_hour_ago/1000)})")
print()

# Query logs
cmd = [
    "aws", "logs", "filter-log-events",
    "--log-group-name", "/ecs/facilitator-production",
    "--region", "us-east-2",
    "--start-time", str(one_hour_ago),
    "--filter-pattern", "settle",
    "--max-items", "100"
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    events = data.get("events", [])

    print(f"Found {len(events)} settlement-related log entries\n")
    print("=" * 80)

    # Strip ANSI codes and analyze
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    for event in events:
        timestamp_ms = event["timestamp"]
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
        message = ansi_escape.sub('', event["message"])

        # Check for important keywords
        is_error = "ERROR" in message or "error" in message
        is_settlement = "SETTLE" in message.upper()
        is_transaction = "transaction" in message.lower()
        is_signature = "signature" in message.lower()

        # Color code based on content
        if is_error:
            print(f"\n[{timestamp}] ❌ ERROR")
        elif is_transaction or is_signature:
            print(f"\n[{timestamp}] 🔄 TRANSACTION")
        elif is_settlement:
            print(f"\n[{timestamp}] 📋 SETTLEMENT")
        else:
            print(f"\n[{timestamp}]")

        # Print the message (truncated if too long)
        if len(message) > 500:
            print(message[:500] + "...")
        else:
            print(message)

    print("\n" + "=" * 80)
    print("\n✅ Log analysis complete")

    # Summary
    error_count = sum(1 for e in events if "ERROR" in ansi_escape.sub('', e["message"]))
    settlement_count = sum(1 for e in events if "SETTLE" in ansi_escape.sub('', e["message"]).upper())

    print(f"\nSummary:")
    print(f"  Total events: {len(events)}")
    print(f"  Errors: {error_count}")
    print(f"  Settlement attempts: {settlement_count}")

except subprocess.CalledProcessError as e:
    print(f"Error querying logs: {e}")
    print(f"Stdout: {e.stdout}")
    print(f"Stderr: {e.stderr}")
except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")
    print(f"Raw output: {result.stdout[:1000]}")
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()
