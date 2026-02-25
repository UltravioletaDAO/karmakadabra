#!/usr/bin/env python3
"""Connect to MeshRelay IRC and listen for messages.

Usage:
    python irc_connect.py --agent kk-karma-hello [--channel "#kk-data-market"] [--duration 60]
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
        msg = {
            "time": time.strftime("%H:%M:%S"),
            "sender": sender,
            "channel": channel,
            "message": message,
        }
        messages.append(msg)
        print(json.dumps(msg), flush=True)
        await original_handle(sender, channel, message)

    agent.handle_message = capture_message

    try:
        await agent.connect()
        await asyncio.sleep(2)
        for ch in channels:
            await agent.introduce(ch)

        if args.duration > 0:
            try:
                await asyncio.wait_for(agent.listen(), timeout=args.duration)
            except asyncio.TimeoutError:
                pass
        else:
            await agent.listen()
    finally:
        await agent.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Connect to MeshRelay IRC")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--channel", default=None, help="IRC channel")
    parser.add_argument("--duration", type=int, default=60, help="Listen duration in seconds")
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
