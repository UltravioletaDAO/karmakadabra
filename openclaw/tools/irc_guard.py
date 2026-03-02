#!/usr/bin/env python3
"""
OpenClaw Tool: IRC Anti-Loop Guard

Middleware called before sending IRC messages to prevent
feedback loops, spam, and runaway message floods.
Reads JSON from stdin, outputs JSON to stdout.

Input:  {"message": "text", "channel": "#karmakadabra", "agent_name": "kk-karma-hello"}
Output: {"allow": true/false, "reason": "..."}

Logic:
  - Dedup: reject if similar message sent in last 10 min (word overlap > 0.8)
  - Rate limit: max 5 msgs per 5-minute window
  - Self-detection: reject if message looks like it came from this agent
  - Circuit breaker: if >10 msgs in 2 min, silence for 5 min
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
logger = logging.getLogger("kk.tool.irc_guard")

DATA_DIR = Path("/app/data")
SENT_LOG = DATA_DIR / "irc_sent_log.jsonl"
STATE_FILE = DATA_DIR / "irc_guard_state.json"

# Thresholds
DEDUP_WINDOW_SEC = 600       # 10 minutes
DEDUP_SIMILARITY = 0.8       # Word overlap threshold
RATE_LIMIT_MSGS = 5          # Max messages per window
RATE_LIMIT_WINDOW_SEC = 300  # 5 minutes
CIRCUIT_BREAKER_MSGS = 10    # Trigger threshold
CIRCUIT_BREAKER_WINDOW = 120 # 2 minutes
CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minutes silence


def _word_set(text: str) -> set:
    """Extract lowercase word set from text."""
    return set(text.lower().split())


def _similarity(a: str, b: str) -> float:
    """Compute word overlap similarity between two strings (Jaccard)."""
    words_a = _word_set(a)
    words_b = _word_set(b)
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _load_sent_log(since_ts: float) -> list[dict]:
    """Load recent entries from the sent log."""
    if not SENT_LOG.exists():
        return []

    entries = []
    try:
        for line in SENT_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("ts", 0) >= since_ts:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return entries


def _load_state() -> dict:
    """Load circuit breaker state."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    """Persist circuit breaker state."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def _record_sent(message: str, channel: str, agent_name: str) -> None:
    """Append a sent message to the log."""
    try:
        SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "message": message,
            "channel": channel,
            "agent": agent_name,
        }
        with open(SENT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def check_message(message: str, channel: str, agent_name: str) -> dict:
    """Run all guard checks. Returns {"allow": bool, "reason": str}."""
    now = time.time()
    state = _load_state()

    # --- Circuit breaker: check if in cooldown ---
    cb_until = state.get("circuit_breaker_until", 0)
    if now < cb_until:
        remaining = int(cb_until - now)
        return {
            "allow": False,
            "reason": f"Circuit breaker active. Silence for {remaining}s more.",
        }

    # --- Self-detection: reject if message contains own agent name as author ---
    # Patterns like "<kk-karma-hello>" or "kk-karma-hello:" at start
    lower_msg = message.lower().strip()
    lower_name = agent_name.lower()
    if lower_msg.startswith(f"<{lower_name}>") or lower_msg.startswith(f"{lower_name}:"):
        return {
            "allow": False,
            "reason": "Self-detection: message appears to be from this agent.",
        }

    # --- Load recent sent messages ---
    recent_all = _load_sent_log(now - RATE_LIMIT_WINDOW_SEC)
    recent_dedup = [e for e in recent_all if e.get("ts", 0) >= now - DEDUP_WINDOW_SEC]

    # --- Circuit breaker: check burst rate ---
    recent_burst = [e for e in recent_all if e.get("ts", 0) >= now - CIRCUIT_BREAKER_WINDOW]
    if len(recent_burst) >= CIRCUIT_BREAKER_MSGS:
        state["circuit_breaker_until"] = now + CIRCUIT_BREAKER_COOLDOWN
        _save_state(state)
        return {
            "allow": False,
            "reason": f"Circuit breaker triggered: {len(recent_burst)} msgs in {CIRCUIT_BREAKER_WINDOW}s. Silenced for {CIRCUIT_BREAKER_COOLDOWN}s.",
        }

    # --- Rate limit: max N msgs per window ---
    if len(recent_all) >= RATE_LIMIT_MSGS:
        return {
            "allow": False,
            "reason": f"Rate limit: {len(recent_all)}/{RATE_LIMIT_MSGS} messages in {RATE_LIMIT_WINDOW_SEC}s window.",
        }

    # --- Dedup: check similarity against recent messages ---
    for entry in recent_dedup:
        prev_msg = entry.get("message", "")
        sim = _similarity(message, prev_msg)
        if sim >= DEDUP_SIMILARITY:
            return {
                "allow": False,
                "reason": f"Duplicate detected: {sim:.0%} similarity with message sent {int(now - entry.get('ts', 0))}s ago.",
            }

    # All checks passed — record and allow
    _record_sent(message, channel, agent_name)

    # Clear circuit breaker state if we are past cooldown
    if "circuit_breaker_until" in state:
        del state["circuit_breaker_until"]
        _save_state(state)

    return {"allow": True, "reason": "OK"}


def main():
    try:
        raw = sys.stdin.read()
        request = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"allow": False, "reason": f"Invalid JSON input: {e}"}))
        return

    message = request.get("message", "")
    channel = request.get("channel", "#karmakadabra")
    agent_name = request.get("agent_name", os.environ.get("KK_AGENT_NAME", "unknown"))

    if not message:
        print(json.dumps({"allow": False, "reason": "Empty message"}))
        return

    try:
        result = check_message(message, channel, agent_name)
        print(json.dumps(result))
    except Exception as e:
        logger.exception("irc_guard check failed")
        print(json.dumps({"allow": False, "reason": f"Guard error: {e}"}))


if __name__ == "__main__":
    main()
