#!/usr/bin/env python3
"""Query another agent's state via EM API or IRC.

Sovereign version: instead of reading from a shared filesystem,
queries external sources (Execution Market API or IRC DM).

Usage:
    python read_agent_memory.py --agent kk-skill-extractor
    python read_agent_memory.py --agent kk-karma-hello --method em
    python read_agent_memory.py --agent kk-coordinator --method irc
    python read_agent_memory.py --agent kk-validator --section "active_tasks"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _load_wallet_address(agent_name: str) -> str:
    """Look up agent wallet address from wallets.json."""
    root = Path(__file__).parent.parent.parent
    wallets_path = root / "data" / "config" / "wallets.json"
    wallets = json.loads(wallets_path.read_text(encoding="utf-8"))
    for w in wallets["wallets"]:
        if w["name"] == agent_name:
            return w["address"]
    # Try with/without kk- prefix
    alt = f"kk-{agent_name}" if not agent_name.startswith("kk-") else agent_name.removeprefix("kk-")
    for w in wallets["wallets"]:
        if w["name"] == alt:
            return w["address"]
    raise ValueError(f"Agent '{agent_name}' not found in wallets.json")


def _load_executor_id(agent_name: str) -> str | None:
    """Look up agent executor_id from identities.json."""
    root = Path(__file__).parent.parent.parent
    ids_path = root / "data" / "config" / "identities.json"
    ids = json.loads(ids_path.read_text(encoding="utf-8"))
    for a in ids["agents"]:
        if a["name"] == agent_name:
            return a.get("executor_id")
    alt = f"kk-{agent_name}" if not agent_name.startswith("kk-") else agent_name.removeprefix("kk-")
    for a in ids["agents"]:
        if a["name"] == alt:
            return a.get("executor_id")
    return None


# ---------------------------------------------------------------------------
# EM method: query Execution Market API
# ---------------------------------------------------------------------------

async def _query_em(agent_name: str, section: str | None) -> dict:
    """Query EM API for the agent's published tasks and activity."""
    from services.em_client import AgentContext, EMClient

    wallet_address = _load_wallet_address(agent_name)
    root = Path(__file__).parent.parent.parent

    ctx = AgentContext(
        name=agent_name,
        wallet_address=wallet_address,
        workspace_dir=root / "data" / "workspaces" / agent_name,
    )
    client = EMClient(ctx)

    try:
        # Browse available tasks and filter by agent wallet
        all_tasks = await client.browse_tasks(limit=50)
        agent_tasks = [
            t for t in all_tasks
            if t.get("creator_wallet", "").lower() == wallet_address.lower()
            or t.get("agent_wallet", "").lower() == wallet_address.lower()
        ]

        result = {
            "agent": agent_name,
            "wallet": wallet_address,
            "method": "em",
            "active_tasks": [
                {
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "status": t.get("status"),
                    "bounty_usd": t.get("bounty_usd"),
                }
                for t in agent_tasks
            ],
            "total_offerings": len(agent_tasks),
        }

        if section and section in result:
            return {"agent": agent_name, "section": section, "content": result[section]}

        return result
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# IRC method: DM the agent and wait for response
# ---------------------------------------------------------------------------

async def _query_irc(agent_name: str, section: str | None) -> dict:
    """Send STATUS? DM via IRC, wait up to 10s for response."""
    from irc.agent_irc_client import IRCAgent

    # Use a temporary nick for the query
    query_nick = f"kk-query-{agent_name[-6:]}"
    irc = IRCAgent(nick=query_nick, channels=[])

    response_text = ""

    try:
        await irc.connect()

        # Send DM to agent
        question = f"STATUS?{f' section={section}' if section else ''}"
        await irc.send_message(agent_name, question)

        # Wait up to 10 seconds for a PRIVMSG response
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            line = await asyncio.wait_for(
                irc._recv(), timeout=max(remaining, 0.5)
            )
            if not line:
                continue
            if line.startswith("PING"):
                await irc._handle_ping(line)
                continue
            if "PRIVMSG" in line and agent_name in line:
                # Parse :sender!user@host PRIVMSG target :message
                _, _, rest = line.partition(" PRIVMSG ")
                _, _, msg = rest.partition(" :")
                response_text = msg
                break
    except (asyncio.TimeoutError, OSError):
        pass
    finally:
        await irc.disconnect()

    return {
        "agent": agent_name,
        "method": "irc",
        "query": f"STATUS?{f' section={section}' if section else ''}",
        "response": response_text if response_text else "(no response within 10s)",
    }


def main():
    parser = argparse.ArgumentParser(description="Query agent state")
    parser.add_argument("--agent", required=True, help="Agent name")
    parser.add_argument("--section", default=None, help="Specific data section")
    parser.add_argument(
        "--method",
        choices=["em", "irc"],
        default="em",
        help="Query method: em (Execution Market API) or irc (IRC DM)",
    )
    args = parser.parse_args()

    try:
        if args.method == "em":
            result = asyncio.run(_query_em(args.agent, args.section))
        else:
            result = asyncio.run(_query_irc(args.agent, args.section))
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e), "agent": args.agent}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
