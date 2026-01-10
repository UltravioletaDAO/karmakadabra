#!/usr/bin/env python3
"""
IRC Control Mixin for Karmacadabra Agents

Adds IRC control plane capabilities to any agent that inherits from ERC8004BaseAgent.
Enables remote command execution, status reporting, and inter-agent communication
via Redis Streams with IRC as the human interface.

Usage:
    class MyAgent(ERC8004BaseAgent, IRCControlMixin):
        def __init__(self, ...):
            super().__init__(...)
            self.init_irc_control(
                agent_id="my-agent",
                roles=["seller", "extractor"],
                redis_url="redis://localhost:6379/0"
            )

        async def handle_custom_action(self, task: Task) -> TaskResult:
            # Handle agent-specific commands
            ...

Then in your agent's run loop:
    await self.start_irc_worker()  # Starts background task processing
"""

import os
import json
import time
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from functools import wraps

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .irc_protocol import (
    Task,
    TaskResult,
    TaskStatus,
    CommandType,
    TargetMatcher,
    RateLimiter,
    STREAM_TASKS,
    STREAM_RESULTS,
    STREAM_EVENTS,
    CONSUMER_GROUP,
    HEARTBEAT_PREFIX,
    HEARTBEAT_TTL_SEC,
    now_ts,
    make_task_id,
)


logger = logging.getLogger(__name__)


@dataclass
class IRCControlConfig:
    """Configuration for IRC control plane"""
    redis_url: str = "redis://localhost:6379/0"
    heartbeat_interval_sec: int = 30
    task_batch_size: int = 5
    task_block_ms: int = 2000
    max_concurrent_tasks: int = 3
    enabled: bool = True


class IRCControlMixin:
    """
    Mixin that adds IRC control plane capabilities to an agent

    Features:
    - Heartbeat publishing (agent presence)
    - Task consumption from Redis Streams
    - Result publishing back to Redis
    - Built-in handlers for common commands (ping, status, halt, resume)
    - Extensible action handlers
    """

    def init_irc_control(
        self,
        agent_id: str,
        roles: List[str] = None,
        groups: List[str] = None,
        redis_url: str = None,
        config: IRCControlConfig = None,
    ):
        """
        Initialize IRC control capabilities

        Args:
            agent_id: Unique identifier for this agent (e.g., "karma-hello-1")
            roles: Agent roles for role-based targeting (e.g., ["seller", "extractor"])
            groups: Additional groups beyond "karma-cabra"
            redis_url: Redis connection URL
            config: Optional configuration override
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis not installed. IRC control disabled. pip install redis")
            self._irc_enabled = False
            return

        self._irc_config = config or IRCControlConfig()
        self._irc_config.redis_url = redis_url or os.getenv(
            "REDIS_URL",
            self._irc_config.redis_url
        )

        self._irc_agent_id = agent_id
        self._irc_target_matcher = TargetMatcher(
            agent_id=agent_id,
            roles=roles or [],
            groups=groups or [],
        )

        # State
        self._irc_enabled = self._irc_config.enabled
        self._irc_halted = False
        self._irc_redis: Optional[redis.Redis] = None
        self._irc_async_redis: Optional[aioredis.Redis] = None
        self._irc_action_handlers: Dict[str, Callable] = {}
        self._irc_rate_limiter = RateLimiter(max_requests=50, window_sec=60)

        # Register built-in handlers
        self._register_builtin_handlers()

        logger.info(
            f"[{agent_id}] IRC control initialized. "
            f"Redis: {self._irc_config.redis_url}, "
            f"Roles: {roles}, Groups: {groups}"
        )

    def _register_builtin_handlers(self):
        """Register built-in command handlers"""
        self.register_irc_handler(CommandType.PING.value, self._handle_ping)
        self.register_irc_handler(CommandType.STATUS.value, self._handle_status)
        self.register_irc_handler(CommandType.HEALTH.value, self._handle_health)
        self.register_irc_handler(CommandType.HALT.value, self._handle_halt)
        self.register_irc_handler(CommandType.RESUME.value, self._handle_resume)
        self.register_irc_handler(CommandType.BALANCE.value, self._handle_balance)

    def register_irc_handler(self, action: str, handler: Callable):
        """
        Register a custom action handler

        Args:
            action: Action name (e.g., "summarize", "ingest")
            handler: Async function(task: Task) -> TaskResult
        """
        self._irc_action_handlers[action] = handler
        logger.debug(f"[{self._irc_agent_id}] Registered handler for action: {action}")

    def _get_sync_redis(self) -> redis.Redis:
        """Get or create synchronous Redis connection"""
        if self._irc_redis is None:
            self._irc_redis = redis.Redis.from_url(
                self._irc_config.redis_url,
                decode_responses=False
            )
            # Ensure consumer group exists
            try:
                self._irc_redis.xgroup_create(
                    STREAM_TASKS,
                    CONSUMER_GROUP,
                    id="0",
                    mkstream=True
                )
            except redis.exceptions.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
        return self._irc_redis

    async def _get_async_redis(self) -> aioredis.Redis:
        """Get or create async Redis connection"""
        if self._irc_async_redis is None:
            self._irc_async_redis = aioredis.from_url(
                self._irc_config.redis_url,
                decode_responses=False
            )
            # Ensure consumer group exists
            try:
                await self._irc_async_redis.xgroup_create(
                    STREAM_TASKS,
                    CONSUMER_GROUP,
                    id="0",
                    mkstream=True
                )
            except aioredis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
        return self._irc_async_redis

    def heartbeat(self):
        """Send heartbeat (sync version for simple cases)"""
        if not self._irc_enabled:
            return
        try:
            rds = self._get_sync_redis()
            key = f"{HEARTBEAT_PREFIX}{self._irc_agent_id}"
            rds.set(key, str(now_ts()), ex=HEARTBEAT_TTL_SEC)
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")

    async def heartbeat_async(self):
        """Send heartbeat (async version)"""
        if not self._irc_enabled:
            return
        try:
            rds = await self._get_async_redis()
            key = f"{HEARTBEAT_PREFIX}{self._irc_agent_id}"
            await rds.set(key, str(now_ts()), ex=HEARTBEAT_TTL_SEC)
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")

    async def emit_result(self, result: TaskResult):
        """Publish task result to Redis Streams"""
        if not self._irc_enabled:
            return
        try:
            rds = await self._get_async_redis()
            await rds.xadd(STREAM_RESULTS, result.to_redis())
            logger.debug(f"[{self._irc_agent_id}] Emitted result: {result.task_id}")
        except Exception as e:
            logger.error(f"Failed to emit result: {e}")

    async def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Publish an event to the events stream"""
        if not self._irc_enabled:
            return
        try:
            rds = await self._get_async_redis()
            await rds.xadd(STREAM_EVENTS, {
                "agent_id": self._irc_agent_id,
                "event_type": event_type,
                "data": json.dumps(data),
                "ts": str(now_ts()),
            })
        except Exception as e:
            logger.warning(f"Failed to emit event: {e}")

    async def start_irc_worker(self):
        """
        Start the IRC control worker as a background task

        This should be called from your agent's main async function.
        It will run indefinitely, processing tasks from Redis Streams.
        """
        if not self._irc_enabled:
            logger.info(f"[{self._irc_agent_id}] IRC control disabled, worker not started")
            return

        logger.info(f"[{self._irc_agent_id}] Starting IRC control worker...")

        # Start heartbeat task
        asyncio.create_task(self._heartbeat_loop())

        # Start task processing loop
        await self._task_processing_loop()

    async def _heartbeat_loop(self):
        """Background heartbeat loop"""
        while self._irc_enabled:
            await self.heartbeat_async()
            await asyncio.sleep(self._irc_config.heartbeat_interval_sec)

    async def _task_processing_loop(self):
        """Main task processing loop"""
        rds = await self._get_async_redis()

        while self._irc_enabled:
            try:
                # Read tasks from stream
                messages = await rds.xreadgroup(
                    CONSUMER_GROUP,
                    self._irc_agent_id,
                    {STREAM_TASKS: ">"},
                    count=self._irc_config.task_batch_size,
                    block=self._irc_config.task_block_ms,
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        try:
                            await self._process_task(msg_id, fields, rds)
                        except Exception as e:
                            logger.error(f"Error processing task: {e}")
                            # Acknowledge to prevent reprocessing
                            await rds.xack(STREAM_TASKS, CONSUMER_GROUP, msg_id)

            except asyncio.CancelledError:
                logger.info(f"[{self._irc_agent_id}] Worker cancelled")
                break
            except Exception as e:
                logger.error(f"Task loop error: {e}")
                await asyncio.sleep(1)

    async def _process_task(
        self,
        msg_id: bytes,
        fields: Dict[bytes, bytes],
        rds: aioredis.Redis
    ):
        """Process a single task from the stream"""
        task = Task.from_redis(fields)
        start_time = time.time()

        # Check if task is for this agent
        if not self._irc_target_matcher.matches(task.target):
            # Not for us, acknowledge without processing
            await rds.xack(STREAM_TASKS, CONSUMER_GROUP, msg_id)
            return

        # Check TTL
        if task.is_expired():
            result = TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.EXPIRED,
                error="Task TTL exceeded",
            )
            await self.emit_result(result)
            await rds.xack(STREAM_TASKS, CONSUMER_GROUP, msg_id)
            return

        # Check if halted (except for resume command)
        if self._irc_halted and task.action != CommandType.RESUME.value:
            result = TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.REJECTED,
                error="Agent is halted",
            )
            await self.emit_result(result)
            await rds.xack(STREAM_TASKS, CONSUMER_GROUP, msg_id)
            return

        # Find handler
        handler = self._irc_action_handlers.get(task.action)
        if not handler:
            result = TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.REJECTED,
                error=f"Unknown action: {task.action}",
            )
            await self.emit_result(result)
            await rds.xack(STREAM_TASKS, CONSUMER_GROUP, msg_id)
            return

        # Execute handler
        try:
            logger.info(f"[{self._irc_agent_id}] Processing {task.action}: {task.task_id}")
            result = await handler(task)
            result.execution_ms = int((time.time() - start_time) * 1000)
        except Exception as e:
            logger.error(f"Handler error for {task.action}: {e}")
            result = TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.FAILED,
                error=str(e),
                execution_ms=int((time.time() - start_time) * 1000),
            )

        await self.emit_result(result)
        await rds.xack(STREAM_TASKS, CONSUMER_GROUP, msg_id)

    # -------- Built-in Handlers --------

    async def _handle_ping(self, task: Task) -> TaskResult:
        """Handle ping command"""
        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output={
                "pong": True,
                "agent_id": self._irc_agent_id,
                "ts": now_ts(),
            },
        )

    async def _handle_status(self, task: Task) -> TaskResult:
        """Handle status command - override in subclass for more detail"""
        status = {
            "agent_id": self._irc_agent_id,
            "halted": self._irc_halted,
            "uptime_sec": getattr(self, "_start_time", 0),
            "ts": now_ts(),
        }

        # Add agent-specific status if available
        if hasattr(self, "get_agent_status"):
            status.update(self.get_agent_status())

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output=status,
        )

    async def _handle_health(self, task: Task) -> TaskResult:
        """Handle health check command"""
        health = {
            "healthy": True,
            "agent_id": self._irc_agent_id,
            "halted": self._irc_halted,
        }

        # Check Web3 connection if available (from ERC8004BaseAgent)
        if hasattr(self, "w3"):
            try:
                health["web3_connected"] = self.w3.is_connected()
            except Exception:
                health["web3_connected"] = False
                health["healthy"] = False

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output=health,
        )

    async def _handle_halt(self, task: Task) -> TaskResult:
        """Handle halt command - pauses task processing"""
        reason = task.payload.get("reason", "No reason provided")
        self._irc_halted = True
        logger.warning(f"[{self._irc_agent_id}] HALTED by {task.sender}: {reason}")

        await self.emit_event("agent_halted", {
            "reason": reason,
            "sender": task.sender,
        })

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output={
                "halted": True,
                "reason": reason,
            },
        )

    async def _handle_resume(self, task: Task) -> TaskResult:
        """Handle resume command - resumes task processing"""
        was_halted = self._irc_halted
        self._irc_halted = False
        logger.info(f"[{self._irc_agent_id}] RESUMED by {task.sender}")

        await self.emit_event("agent_resumed", {
            "sender": task.sender,
            "was_halted": was_halted,
        })

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output={
                "resumed": True,
                "was_halted": was_halted,
            },
        )

    async def _handle_balance(self, task: Task) -> TaskResult:
        """Handle balance query - requires ERC8004BaseAgent"""
        if not hasattr(self, "get_balance"):
            return TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.FAILED,
                error="Balance not available (agent does not inherit from ERC8004BaseAgent)",
            )

        try:
            balance = self.get_balance()
            return TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.COMPLETED,
                output={
                    "balance_native": str(balance),
                    "address": getattr(self, "address", "unknown"),
                },
            )
        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.FAILED,
                error=str(e),
            )


# -------- Decorator for custom handlers --------

def irc_handler(action: str):
    """
    Decorator to register a method as an IRC action handler

    Usage:
        class MyAgent(ERC8004BaseAgent, IRCControlMixin):
            @irc_handler("summarize")
            async def handle_summarize(self, task: Task) -> TaskResult:
                # Process summarize command
                ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, task: Task) -> TaskResult:
            return await func(self, task)

        # Store action name for registration
        wrapper._irc_action = action
        return wrapper

    return decorator


def register_irc_handlers(agent):
    """
    Scan agent for @irc_handler decorated methods and register them

    Call this after init_irc_control():
        self.init_irc_control(...)
        register_irc_handlers(self)
    """
    for name in dir(agent):
        method = getattr(agent, name, None)
        if callable(method) and hasattr(method, "_irc_action"):
            agent.register_irc_handler(method._irc_action, method)
