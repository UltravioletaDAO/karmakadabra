#!/usr/bin/env python3
"""
Example: Integrating IRC Control into a Karmacadabra Agent

This file demonstrates how to add IRC control capabilities to any agent
that inherits from ERC8004BaseAgent. The integration is non-invasive and
backward-compatible (agents work without Redis/IRC).

Three integration patterns:

1. MIXIN PATTERN (Recommended)
   - Add IRCControlMixin to your agent class
   - Start IRC worker in background
   - Register custom command handlers

2. COMPOSITION PATTERN
   - Create separate IRC controller
   - Pass agent instance for actions
   - Useful for complex agents

3. DECORATOR PATTERN
   - Use @irc_handler decorator
   - Automatic handler registration
   - Cleanest syntax

Usage:
    # See examples below, then adapt to your agent
    python -m shared.irc_integration_example
"""

import os
import asyncio
import logging
from typing import Dict, Any

# Import base agent (adjust path as needed)
from shared.base_agent import ERC8004BaseAgent

# Import IRC control components
from shared.irc_control import (
    IRCControlMixin,
    IRCControlConfig,
    irc_handler,
    register_irc_handlers,
)
from shared.irc_protocol import (
    Task,
    TaskResult,
    TaskStatus,
    CommandType,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# PATTERN 1: Mixin Pattern (Recommended)
# =============================================================================

class KarmaHelloWithIRC(ERC8004BaseAgent, IRCControlMixin):
    """
    Example: karma-hello agent with IRC control capabilities

    This agent:
    - Sells chat logs (existing functionality)
    - Responds to IRC commands (new functionality)
    - Custom handlers for agent-specific actions
    """

    def __init__(self, config: Dict[str, Any]):
        # Initialize base agent
        super().__init__(
            agent_name="karma-hello-agent",
            agent_domain=config.get("domain", "karma-hello.karmacadabra.ultravioletadao.xyz"),
            rpc_url=config.get("rpc_url"),
            chain_id=config.get("chain_id", 84532),
            identity_registry_address=config.get("identity_registry"),
            reputation_registry_address=config.get("reputation_registry"),
        )

        # Initialize IRC control
        if os.getenv("IRC_ENABLED", "true").lower() == "true":
            self.init_irc_control(
                agent_id="karma-hello",
                roles=["seller", "logs"],
                groups=["extractors"],
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            )

            # Register custom handlers
            self.register_irc_handler("summarize", self.handle_summarize)
            self.register_irc_handler("ingest", self.handle_ingest)
            self.register_irc_handler("list_streams", self.handle_list_streams)

    async def handle_summarize(self, task: Task) -> TaskResult:
        """
        Handle summarize command from IRC

        Example IRC command:
            !dispatch karma-hello summarize {"stream_id":"2026-01-08","max":20} |sig=xxx
        """
        stream_id = task.payload.get("stream_id", "latest")
        max_entries = task.payload.get("max", 10)

        # Your summarization logic here
        # For now, return stub
        summary = {
            "stream_id": stream_id,
            "total_messages": 1234,
            "unique_users": 45,
            "top_topics": ["gaming", "music", "chat"],
            "sentiment": "positive",
        }

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output=summary,
        )

    async def handle_ingest(self, task: Task) -> TaskResult:
        """
        Handle ingest command - trigger log ingestion

        Example IRC command:
            !dispatch karma-hello ingest {"source":"twitch","channel":"ultravioleta"} |sig=xxx
        """
        source = task.payload.get("source", "twitch")
        channel = task.payload.get("channel")

        if not channel:
            return TaskResult(
                task_id=task.task_id,
                agent_id=self._irc_agent_id,
                status=TaskStatus.FAILED,
                error="Missing required parameter: channel",
            )

        # Trigger ingestion (implement your logic)
        # ...

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output={
                "ingestion_started": True,
                "source": source,
                "channel": channel,
            },
        )

    async def handle_list_streams(self, task: Task) -> TaskResult:
        """
        List available streams

        Example IRC command:
            !dispatch karma-hello list_streams {} |sig=xxx
        """
        # Your logic to list available streams
        streams = [
            {"id": "2026-01-08", "date": "2026-01-08", "messages": 5000},
            {"id": "2026-01-07", "date": "2026-01-07", "messages": 4200},
            {"id": "2026-01-06", "date": "2026-01-06", "messages": 3800},
        ]

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output={"streams": streams, "total": len(streams)},
        )

    def get_agent_status(self) -> Dict[str, Any]:
        """
        Override to provide custom status info for !status command
        """
        return {
            "logs_count": 15000,  # Replace with actual count
            "streams_available": 42,
            "last_ingest": "2026-01-08T10:30:00Z",
        }

    async def run(self):
        """
        Main run loop - starts HTTP server and IRC worker
        """
        # Start IRC worker in background (non-blocking)
        if hasattr(self, '_irc_enabled') and self._irc_enabled:
            asyncio.create_task(self.start_irc_worker())
            logger.info("IRC control worker started in background")

        # Start your HTTP server
        # await self.start_http_server()
        logger.info("Agent running (HTTP server would start here)")

        # Keep running
        while True:
            await asyncio.sleep(60)


# =============================================================================
# PATTERN 2: Decorator Pattern (Cleanest Syntax)
# =============================================================================

class ValidatorWithIRC(ERC8004BaseAgent, IRCControlMixin):
    """
    Example using @irc_handler decorator for cleaner syntax
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            agent_name="validator-agent",
            agent_domain="validator.karmacadabra.ultravioletadao.xyz",
            rpc_url=config.get("rpc_url"),
            chain_id=config.get("chain_id", 84532),
            identity_registry_address=config.get("identity_registry"),
            reputation_registry_address=config.get("reputation_registry"),
        )

        self.init_irc_control(
            agent_id="validator",
            roles=["validator", "quality"],
        )

        # Auto-register decorated handlers
        register_irc_handlers(self)

    @irc_handler("validate")
    async def handle_validate(self, task: Task) -> TaskResult:
        """
        Handle validation request via IRC

        Example:
            !dispatch validator validate {"data_type":"chat_log","content":"..."} |sig=xxx
        """
        data_type = task.payload.get("data_type")
        content = task.payload.get("content")

        # Your validation logic
        validation_result = {
            "quality_score": 85,
            "fraud_score": 5,
            "price_score": 90,
            "recommendation": "APPROVE",
        }

        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output=validation_result,
        )

    @irc_handler("queue_stats")
    async def handle_queue_stats(self, task: Task) -> TaskResult:
        """Get validation queue statistics"""
        return TaskResult(
            task_id=task.task_id,
            agent_id=self._irc_agent_id,
            status=TaskStatus.COMPLETED,
            output={
                "pending": 12,
                "completed_today": 145,
                "avg_processing_ms": 234,
            },
        )


# =============================================================================
# PATTERN 3: Minimal Integration (Existing Agent)
# =============================================================================

def add_irc_to_existing_agent(agent: ERC8004BaseAgent):
    """
    Add IRC control to an existing agent instance without modifying its class.

    Usage:
        agent = YourExistingAgent(config)
        add_irc_to_existing_agent(agent)
        # Now agent responds to IRC commands
    """
    # Dynamically add mixin methods
    IRCControlMixin.init_irc_control(
        agent,
        agent_id=agent.agent_name.replace("-agent", ""),
        roles=["seller"],
    )

    # The agent now has IRC capabilities
    # Start worker in your run loop:
    # asyncio.create_task(agent.start_irc_worker())


# =============================================================================
# CLI Tool: Sign Commands
# =============================================================================

def sign_irc_command():
    """
    CLI helper to sign IRC commands

    Usage:
        python -m shared.irc_integration_example sign "!dispatch agent:all ping {}"
    """
    import sys
    from shared.irc_protocol import format_signed_command

    if len(sys.argv) < 3:
        print("Usage: python -m shared.irc_integration_example sign '<command>'")
        print("Example: python -m shared.irc_integration_example sign '!dispatch agent:all ping {}'")
        sys.exit(1)

    raw_command = sys.argv[2]
    secret = os.getenv("IRC_HMAC_SECRET")

    if not secret:
        print("ERROR: IRC_HMAC_SECRET environment variable not set")
        print("Generate with: python -c \"import secrets; print(secrets.token_hex(32))\"")
        sys.exit(1)

    signed = format_signed_command(raw_command, secret)
    print(f"\nSigned command (copy to IRC):\n{signed}\n")


# =============================================================================
# Demo
# =============================================================================

async def demo():
    """
    Demonstrate IRC integration

    Run with:
        # Terminal 1: Start Redis
        docker run -d -p 6379:6379 redis:7-alpine

        # Terminal 2: Run demo
        export IRC_ENABLED=true
        export REDIS_URL=redis://localhost:6379/0
        python -m shared.irc_integration_example
    """
    print("=" * 60)
    print("IRC Control Integration Demo")
    print("=" * 60)

    # This would normally load from config/AWS
    demo_config = {
        "rpc_url": os.getenv("RPC_URL", "https://sepolia.base.org"),
        "chain_id": 84532,
        "identity_registry": os.getenv("IDENTITY_REGISTRY", "0x8a20f665c02a33562a0462a0908a64716Ed7463d"),
        "reputation_registry": os.getenv("REPUTATION_REGISTRY", "0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F"),
    }

    print("\n[1] Creating agent with IRC control...")

    # Skip actual blockchain init for demo
    class DemoAgent(IRCControlMixin):
        """Simplified demo agent without blockchain"""
        def __init__(self):
            self.agent_name = "demo-agent"

        def get_agent_status(self):
            return {"demo": True, "uptime": 123}

    agent = DemoAgent()
    agent.init_irc_control(
        agent_id="demo",
        roles=["demo"],
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    )

    print("[2] Registered handlers:")
    for action in agent._irc_action_handlers:
        print(f"    - {action}")

    print("\n[3] Starting IRC worker (background)...")
    print("    Listening for commands on Redis stream: uvd:tasks")

    # Run for a bit to show it's working
    try:
        await asyncio.wait_for(agent.start_irc_worker(), timeout=10)
    except asyncio.TimeoutError:
        print("\n[4] Demo timeout reached (normal)")

    print("\n[5] To test manually:")
    print("    # Send a ping command to Redis")
    print("    redis-cli XADD uvd:tasks '*' task_id ping-test-1 target agent:all action ping payload '{}' sender demo ttl_sec 30 created_at $(date +%s) nonce test123")
    print("\n    # Check results")
    print("    redis-cli XRANGE uvd:results - +")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sign":
        sign_irc_command()
    else:
        asyncio.run(demo())
