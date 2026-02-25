#!/usr/bin/env python3
"""Announce an agent's offering on IRC (MeshRelay).

Sovereign version: instead of writing to a shared catalog.json,
publishes a HAVE: message on #kk-data-market via IRC.

Usage:
    python update_catalog.py --agent kk-karma-hello --product "chat-logs" \
        --price 0.01 --description "Raw Twitch chat logs"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from irc.agent_irc_client import IRCAgent

IRC_CHANNEL = "#kk-data-market"


async def announce(agent: str, product: str, price: float, description: str):
    """Connect to IRC, send HAVE: message, disconnect."""
    irc = IRCAgent(
        nick=agent,
        channels=[IRC_CHANNEL],
    )
    await irc.connect()

    msg = f"HAVE: {product} | ${price:.2f} USDC | {description}"
    await irc.send_message(IRC_CHANNEL, msg)

    # Brief pause to ensure message is sent before disconnect
    await asyncio.sleep(1)
    await irc.disconnect()

    return {
        "success": True,
        "agent": agent,
        "product": product,
        "price_usdc": price,
        "channel": IRC_CHANNEL,
        "message": msg,
    }


def main():
    parser = argparse.ArgumentParser(description="Announce offering on IRC")
    parser.add_argument("--agent", required=True, help="Agent name (IRC nick)")
    parser.add_argument("--product", required=True, help="Product identifier")
    parser.add_argument("--price", type=float, required=True, help="Price in USDC")
    parser.add_argument("--description", required=True, help="Product description")
    args = parser.parse_args()

    try:
        result = asyncio.run(
            announce(args.agent, args.product, args.price, args.description)
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
