#!/usr/bin/env python3
"""
IRC Control Protocol for Karmacadabra Agents

Defines message formats, commands, and security primitives for
agent-to-agent and human-to-agent communication via IRC.

Security Model:
- All commands MUST be signed with HMAC-SHA256
- Each agent has a unique identity (wallet address as nick suffix)
- Commands are rate-limited per sender
- Actions are whitelisted per agent role

Protocol:
- Commands: !dispatch, !agents, !halt, !resume, !status, !logs
- Events: Published to Redis Streams, forwarded to IRC channels
- Results: Task ID + status + output JSON
"""

import os
import json
import time
import hmac
import hashlib
import secrets
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from enum import Enum


class TaskStatus(str, Enum):
    """Task lifecycle states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    REJECTED = "rejected"


class CommandType(str, Enum):
    """Allowed command types"""
    # Query commands (read-only)
    PING = "ping"
    STATUS = "status"
    AGENTS = "agents"
    LOGS = "logs"
    BALANCE = "balance"
    HEALTH = "health"

    # Action commands (state-changing)
    DISPATCH = "dispatch"
    HALT = "halt"
    RESUME = "resume"
    SUMMARIZE = "summarize"
    INGEST = "ingest"
    VALIDATE = "validate"

    # Agent-specific
    BUY = "buy"
    SELL = "sell"
    RATE = "rate"


# Commands that require elevated permissions
PRIVILEGED_COMMANDS = {
    CommandType.HALT,
    CommandType.RESUME,
    CommandType.DISPATCH,
}

# Commands safe for any authenticated user
PUBLIC_COMMANDS = {
    CommandType.PING,
    CommandType.STATUS,
    CommandType.AGENTS,
    CommandType.HEALTH,
    CommandType.BALANCE,
}


def now_ts() -> int:
    """Return current Unix timestamp"""
    return int(time.time())


def make_task_id(prefix: str = "task") -> str:
    """Generate unique task ID without external dependencies"""
    rand = secrets.token_hex(4)
    return f"{prefix}-{now_ts()}-{rand}"


def make_nonce() -> str:
    """Generate random nonce for replay protection"""
    return secrets.token_hex(16)


@dataclass
class Task:
    """
    Task message for agent execution

    Attributes:
        task_id: Unique identifier
        target: Agent target (e.g., "karma-hello:all", "agent:validator")
        action: Command type from CommandType enum
        payload: JSON-serializable command parameters
        sender: IRC nick or wallet address of sender
        ttl_sec: Time-to-live in seconds (default 60)
        priority: 0=low, 1=normal, 2=high
        created_at: Unix timestamp
        nonce: Replay protection
    """
    task_id: str
    target: str
    action: str
    payload: Dict[str, Any]
    sender: str = ""
    ttl_sec: int = 60
    priority: int = 1
    created_at: int = field(default_factory=now_ts)
    nonce: str = field(default_factory=make_nonce)

    def is_expired(self) -> bool:
        """Check if task has exceeded TTL"""
        return now_ts() - self.created_at > self.ttl_sec

    def to_redis(self) -> Dict[str, str]:
        """Convert to Redis Streams format (all string values)"""
        return {
            "task_id": self.task_id,
            "target": self.target,
            "action": self.action,
            "payload": json.dumps(self.payload),
            "sender": self.sender,
            "ttl_sec": str(self.ttl_sec),
            "priority": str(self.priority),
            "created_at": str(self.created_at),
            "nonce": self.nonce,
        }

    @classmethod
    def from_redis(cls, fields: Dict[bytes, bytes]) -> "Task":
        """Parse from Redis Streams message"""
        return cls(
            task_id=fields[b"task_id"].decode(),
            target=fields[b"target"].decode(),
            action=fields[b"action"].decode(),
            payload=json.loads(fields[b"payload"].decode()),
            sender=fields.get(b"sender", b"").decode(),
            ttl_sec=int(fields[b"ttl_sec"].decode()),
            priority=int(fields.get(b"priority", b"1").decode()),
            created_at=int(fields[b"created_at"].decode()),
            nonce=fields.get(b"nonce", b"").decode(),
        )


@dataclass
class TaskResult:
    """
    Result of task execution

    Attributes:
        task_id: Reference to original task
        agent_id: Agent that processed the task
        status: Execution status
        output: Result data (JSON-serializable)
        error: Error message if failed
        execution_ms: Time taken in milliseconds
        ts: Completion timestamp
    """
    task_id: str
    agent_id: str
    status: TaskStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_ms: int = 0
    ts: int = field(default_factory=now_ts)

    def to_redis(self) -> Dict[str, str]:
        """Convert to Redis Streams format"""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "output": json.dumps(self.output),
            "error": self.error or "",
            "execution_ms": str(self.execution_ms),
            "ts": str(self.ts),
        }

    @classmethod
    def from_redis(cls, fields: Dict[bytes, bytes]) -> "TaskResult":
        """Parse from Redis Streams message"""
        return cls(
            task_id=fields[b"task_id"].decode(),
            agent_id=fields[b"agent_id"].decode(),
            status=TaskStatus(fields[b"status"].decode()),
            output=json.loads(fields.get(b"output", b"{}").decode()),
            error=fields.get(b"error", b"").decode() or None,
            execution_ms=int(fields.get(b"execution_ms", b"0").decode()),
            ts=int(fields.get(b"ts", b"0").decode()),
        )

    def to_irc(self, max_len: int = 400) -> str:
        """Format for IRC message (truncated if needed)"""
        status_emoji = {
            TaskStatus.COMPLETED: "[OK]",
            TaskStatus.FAILED: "[FAIL]",
            TaskStatus.EXPIRED: "[EXPIRED]",
            TaskStatus.REJECTED: "[REJECTED]",
        }.get(self.status, "[?]")

        output_str = json.dumps(self.output)
        if len(output_str) > 200:
            output_str = output_str[:197] + "..."

        msg = f"{status_emoji} {self.task_id} agent={self.agent_id} "
        if self.error:
            msg += f"error={self.error}"
        else:
            msg += f"output={output_str}"

        if self.execution_ms > 0:
            msg += f" ({self.execution_ms}ms)"

        return msg[:max_len]


# -------- Security Primitives --------

def sign_command(secret: str, raw: str) -> str:
    """
    Create HMAC-SHA256 signature for a command

    Args:
        secret: Shared secret (from AWS Secrets Manager)
        raw: Raw command text (before |sig=)

    Returns:
        Hexadecimal signature string
    """
    return hmac.new(
        secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def verify_command(secret: str, raw: str, sig: str) -> bool:
    """
    Verify HMAC signature in constant time

    Args:
        secret: Shared secret
        raw: Raw command text
        sig: Provided signature

    Returns:
        True if signature is valid
    """
    expected = sign_command(secret, raw)
    return hmac.compare_digest(expected, sig)


def parse_irc_command(msg: str) -> tuple[str, str]:
    """
    Parse IRC command into raw text and signature

    Format: !command args |sig=<hex>

    Returns:
        Tuple of (raw_command, signature)

    Raises:
        ValueError if signature not found
    """
    if "|sig=" not in msg:
        raise ValueError("Missing signature (|sig=)")

    raw, sig_part = msg.rsplit("|sig=", 1)
    return raw.strip(), sig_part.strip()


def format_signed_command(raw: str, secret: str) -> str:
    """
    Create a signed IRC command ready to send

    Args:
        raw: Command without signature (e.g., "!dispatch agent:all ping {}")
        secret: HMAC secret

    Returns:
        Full command with signature
    """
    sig = sign_command(secret, raw)
    return f"{raw} |sig={sig}"


# -------- Target Matching --------

class TargetMatcher:
    """
    Determines if an agent should process a task based on target pattern

    Patterns:
        - "agent:<id>" - Specific agent by ID
        - "agent:all" - All agents
        - "karma-cabra:all" - All Karmacadabra agents
        - "role:validator" - Agents with specific role
        - "group:extractors" - Agent groups
    """

    def __init__(self, agent_id: str, roles: List[str] = None, groups: List[str] = None):
        self.agent_id = agent_id
        self.roles = set(roles or [])
        self.groups = set(groups or [])

        # All Karmacadabra agents belong to this group
        self.groups.add("karma-cabra")

    def matches(self, target: str) -> bool:
        """Check if this agent should handle the target"""
        if not target:
            return False

        # Exact agent match
        if target == f"agent:{self.agent_id}":
            return True

        # Broadcast targets
        if target in ("agent:all", "karma-cabra:all", "*"):
            return True

        # Role-based targeting
        if target.startswith("role:"):
            role = target.split(":", 1)[1]
            return role in self.roles

        # Group-based targeting
        if target.startswith("group:"):
            group = target.split(":", 1)[1]
            return group in self.groups

        return False


# -------- Redis Stream Names --------

STREAM_TASKS = "uvd:tasks"
STREAM_RESULTS = "uvd:results"
STREAM_EVENTS = "uvd:events"
CONSUMER_GROUP = "uvd:workers"
HEARTBEAT_PREFIX = "uvd:agent:hb:"
HEARTBEAT_TTL_SEC = 120


# -------- IRC Channel Names --------

IRC_CHANNEL_COMMANDS = "#karma-cabra"
IRC_CHANNEL_ALERTS = "#karma-cabra-alerts"
IRC_CHANNEL_LOGS = "#karma-cabra-logs"


# -------- Rate Limiting --------

@dataclass
class RateLimiter:
    """Simple in-memory rate limiter"""
    max_requests: int = 10
    window_sec: int = 60
    _requests: Dict[str, List[int]] = field(default_factory=dict)

    def check(self, sender: str) -> bool:
        """Check if sender is within rate limit"""
        now = now_ts()
        window_start = now - self.window_sec

        # Clean old requests
        if sender in self._requests:
            self._requests[sender] = [
                ts for ts in self._requests[sender]
                if ts > window_start
            ]
        else:
            self._requests[sender] = []

        # Check limit
        if len(self._requests[sender]) >= self.max_requests:
            return False

        # Record request
        self._requests[sender].append(now)
        return True


# -------- Convenience Functions --------

def create_ping_task(target: str = "agent:all", sender: str = "system") -> Task:
    """Create a simple ping task"""
    return Task(
        task_id=make_task_id("ping"),
        target=target,
        action=CommandType.PING.value,
        payload={},
        sender=sender,
        ttl_sec=30,
    )


def create_status_task(target: str, sender: str = "system") -> Task:
    """Create a status query task"""
    return Task(
        task_id=make_task_id("status"),
        target=target,
        action=CommandType.STATUS.value,
        payload={},
        sender=sender,
        ttl_sec=30,
    )


def create_halt_task(target: str, sender: str, reason: str = "") -> Task:
    """Create a halt command task"""
    return Task(
        task_id=make_task_id("halt"),
        target=target,
        action=CommandType.HALT.value,
        payload={"reason": reason},
        sender=sender,
        ttl_sec=60,
        priority=2,  # High priority
    )
