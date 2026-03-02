#!/usr/bin/env python3
"""
OpenClaw Tool: IRC Communication Bridge

Allows the LLM to read incoming IRC messages and send responses
through the Python IRC daemon (file-based bridge).

Input (JSON stdin):
  {"action": "read_inbox", "params": {"limit": 20}}
  {"action": "send", "params": {"channel": "#karmakadabra", "message": "Hola parce"}}
  {"action": "status", "params": {}}
  {"action": "history", "params": {"limit": 10}}

Output (JSON stdout):
  Depends on action — see each handler.

Architecture:
  LLM -> irc_tool.py -> irc-outbox.jsonl -> irc_daemon.py -> MeshRelay IRC
  MeshRelay IRC -> irc_daemon.py -> irc-inbox.jsonl -> irc_tool.py -> LLM
"""

import sys
sys.path.insert(0, "/app")

import json
import logging
import os
import time
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("kk.tool.irc")

DATA_DIR = Path(os.environ.get("KK_DATA_DIR", "/app/data"))
INBOX_PATH = DATA_DIR / "irc-inbox.jsonl"
OUTBOX_PATH = DATA_DIR / "irc-outbox.jsonl"
AGENT_NAME = os.environ.get("KK_AGENT_NAME", "unknown")


def read_inbox(params: dict) -> dict:
    """Read recent IRC messages from inbox.

    Returns messages and clears them from the inbox so they're
    only processed once.
    """
    limit = params.get("limit", 20)
    since_minutes = params.get("since_minutes", 30)

    if not INBOX_PATH.exists():
        return {"messages": [], "count": 0, "note": "No messages yet"}

    messages = []
    remaining = []
    cutoff = time.time() - (since_minutes * 60)

    try:
        lines = INBOX_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Parse ISO timestamp or unix ts
                ts = entry.get("ts", "")
                if isinstance(ts, str) and "T" in ts:
                    # Approximate: just keep recent ones
                    messages.append(entry)
                elif isinstance(ts, (int, float)) and ts >= cutoff:
                    messages.append(entry)
                else:
                    messages.append(entry)
            except json.JSONDecodeError:
                continue

        # Take the most recent N messages
        messages = messages[-limit:]

        # Clear inbox after reading (consumed)
        INBOX_PATH.write_text("", encoding="utf-8")

    except OSError as e:
        return {"error": f"Failed to read inbox: {e}", "messages": []}

    return {
        "messages": messages,
        "count": len(messages),
    }


def send_message(params: dict) -> dict:
    """Send a message to IRC via outbox.

    Runs irc_guard checks first to prevent loops/spam.
    """
    channel = params.get("channel", "#karmakadabra")
    message = params.get("message", "")

    if not message:
        return {"sent": False, "reason": "Empty message"}

    if not channel:
        return {"sent": False, "reason": "No channel specified"}

    # Run irc_guard check
    try:
        from openclaw.tools.irc_guard import check_message
        guard_result = check_message(message, channel, AGENT_NAME)
        if not guard_result.get("allow", False):
            return {
                "sent": False,
                "reason": f"Blocked by irc_guard: {guard_result.get('reason', 'unknown')}",
            }
    except ImportError:
        # irc_guard not available — allow but warn
        logger.warning("irc_guard not importable, skipping check")

    # Write to outbox for IRC daemon to pick up
    try:
        OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "target": channel,
            "message": message,
            "ts": time.time(),
            "agent": AGENT_NAME,
        }
        with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return {"sent": True, "channel": channel, "message_preview": message[:80]}

    except OSError as e:
        return {"sent": False, "reason": f"Failed to write outbox: {e}"}


def get_status(params: dict) -> dict:
    """Check IRC daemon status."""
    # Check if daemon is running by looking for PID file or process
    pid_file = DATA_DIR / "irc-daemon.pid"
    daemon_running = False

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            daemon_running = True
        except (ValueError, OSError):
            daemon_running = False

    inbox_lines = 0
    outbox_lines = 0

    if INBOX_PATH.exists():
        try:
            inbox_lines = sum(1 for _ in INBOX_PATH.read_text().splitlines() if _.strip())
        except OSError:
            pass

    if OUTBOX_PATH.exists():
        try:
            outbox_lines = sum(1 for _ in OUTBOX_PATH.read_text().splitlines() if _.strip())
        except OSError:
            pass

    return {
        "daemon_running": daemon_running,
        "inbox_pending": inbox_lines,
        "outbox_pending": outbox_lines,
        "agent": AGENT_NAME,
    }


def get_history(params: dict) -> dict:
    """Get recently sent message history from irc_guard log."""
    limit = params.get("limit", 10)
    sent_log = DATA_DIR / "irc_sent_log.jsonl"

    if not sent_log.exists():
        return {"messages": [], "count": 0}

    messages = []
    try:
        for line in sent_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    messages = messages[-limit:]
    return {"messages": messages, "count": len(messages)}


ACTIONS = {
    "read_inbox": read_inbox,
    "send": send_message,
    "status": get_status,
    "history": get_history,
}


def main():
    try:
        raw = sys.stdin.read()
        request = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        return

    action = request.get("action", "")
    params = request.get("params", {})

    handler = ACTIONS.get(action)
    if not handler:
        print(json.dumps({
            "error": f"Unknown action: {action}",
            "available_actions": list(ACTIONS.keys()),
        }))
        return

    try:
        result = handler(params)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        logger.exception(f"Action {action} failed")
        print(json.dumps({"error": f"{action} failed: {e}"}))


if __name__ == "__main__":
    main()
