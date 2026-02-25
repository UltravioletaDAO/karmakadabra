#!/usr/bin/env python3
"""Send a message to MeshRelay IRC and disconnect.

Usage:
    python irc_send.py --agent kk-karma-hello --channel "#kk-data-market" --message "HAVE: chat logs | $0.01"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from irc.agent_irc_client import IRCAgent


async def run(args):
    agent = IRCAgent(nick=args.agent, channels=[args.channel])
    try:
        await agent.connect()
        await asyncio.sleep(2)
        await agent.send_message(args.channel, args.message)
        await asyncio.sleep(1)
        print(json.dumps({"sent": True, "channel": args.channel, "agent": args.agent}))
    finally:
        await agent.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Send IRC message")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--channel", default="#kk-data-market", help="IRC channel")
    parser.add_argument("--message", required=True, help="Message to send")
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
