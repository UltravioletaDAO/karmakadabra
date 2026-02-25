#!/usr/bin/env python3
"""Connect to MeshRelay IRC, listen for messages, and output them as JSON.

Usage:
    python irc_read.py --agent kk-karma-hello [--channel "#kk-data-market"] [--duration 30]
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from irc.agent_irc_client import IRCAgent


async def run(args):
    channels = [args.channel] if args.channel else ["#Agents", "#kk-data-market"]
    agent = IRCAgent(nick=args.agent, channels=channels)
    messages = []

    original_handle = agent.handle_message

    async def capture_message(sender, channel, message):
        messages.append({
            "time": time.strftime("%H:%M:%S"),
            "sender": sender,
            "channel": channel,
            "message": message,
        })

    agent.handle_message = capture_message

    try:
        await agent.connect()
        await asyncio.sleep(2)

        try:
            await asyncio.wait_for(agent.listen(), timeout=args.duration)
        except asyncio.TimeoutError:
            pass
    finally:
        await agent.disconnect()

    print(json.dumps(messages, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Read IRC messages")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--channel", default=None, help="IRC channel")
    parser.add_argument("--duration", type=int, default=30, help="Listen duration in seconds")
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
