#!/usr/bin/env python3
"""Check reputation for a KK agent.

Usage:
    python check_reputation.py --agent kk-karma-hello
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.reputation_bridge import (
    classify_tier,
    load_latest_snapshot,
)


def main():
    parser = argparse.ArgumentParser(description="Check agent reputation")
    parser.add_argument("--agent", required=True, help="Agent name")
    args = parser.parse_args()

    try:
        root = Path(__file__).parent.parent.parent
        reputation_dir = root / "data" / "reputation"

        snapshot = load_latest_snapshot(reputation_dir)

        if args.agent in snapshot:
            agent_data = snapshot[args.agent]
            result = {
                "agent": args.agent,
                "composite_score": agent_data.get("composite_score", 50.0),
                "tier": agent_data.get("tier", "Unknown"),
                "confidence": agent_data.get("confidence", 0.0),
                "layers": agent_data.get("layers", {}),
                "sources_available": agent_data.get("sources_available", []),
            }
        else:
            # No reputation data — return neutral defaults
            score = 50.0
            tier = classify_tier(score)
            result = {
                "agent": args.agent,
                "composite_score": score,
                "tier": tier.value,
                "confidence": 0.0,
                "layers": {
                    "on_chain": {"score": 50.0, "confidence": 0.0, "available": False},
                    "off_chain": {"score": 50.0, "confidence": 0.0, "available": False},
                    "transactional": {"score": 50.0, "confidence": 0.0, "available": False},
                },
                "sources_available": [],
                "note": "No reputation data found. Agent starts at neutral (Plata tier).",
            }

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e), "agent": args.agent}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
