#!/usr/bin/env python3
"""
Community Agent Template — Heartbeat-based v2 agent.

Community agents follow the heartbeat model:
  1. Wake up on schedule (cron/heartbeat interval)
  2. Check for assigned tasks
  3. Execute task if available
  4. Report results
  5. Go back to sleep

Customize by editing SOUL.md and implementing execute_task().

Usage:
    AGENT_NAME=kk-juanita python main.py
    AGENT_NAME=kk-juanita NETWORK=base python main.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from lib.agent_lifecycle import AgentType
from lib.v2_base_agent import V2BaseAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("kk.community")


class CommunityAgent(V2BaseAgent):
    """
    Template community agent. Override execute_task() for custom behavior.
    """

    def __init__(self, agent_name: str, network: str = "base-sepolia"):
        domain = f"{agent_name}.karmacadabra.ultravioletadao.xyz"
        super().__init__(
            agent_name=agent_name,
            agent_domain=domain,
            network=network,
            agent_type=AgentType.USER,
        )
        self._workspace = Path(f"data/workspaces/{agent_name}")

    async def execute_task(self, task: dict) -> dict:
        """
        Execute an assigned task. Override in subclasses.

        Args:
            task: Task dict with id, title, description, bounty, etc.

        Returns:
            Result dict with output data.
        """
        logger.info(f"[{self.agent_name}] Executing task: {task.get('title', 'unknown')}")
        # Default: acknowledge task
        return {
            "status": "completed",
            "agent": self.agent_name,
            "task_id": task.get("id"),
            "output": "Task acknowledged by community agent template",
        }

    async def heartbeat_cycle(self):
        """One heartbeat cycle: check for work, execute, report."""
        status = await self.heartbeat()
        logger.info(f"[{self.agent_name}] Heartbeat: {status['state']}")

        # In production, this would check coordinator for assigned tasks
        # For now, just heartbeat
        return status


async def main():
    agent_name = os.getenv("AGENT_NAME", "kk-community-template")
    network = os.getenv("NETWORK", "base-sepolia")

    logger.info(f"Starting community agent: {agent_name} on {network}")

    agent = CommunityAgent(agent_name=agent_name, network=network)
    await agent.start()

    # Heartbeat loop
    interval = int(os.getenv("HEARTBEAT_INTERVAL", "300"))  # 5 min default
    try:
        while True:
            await agent.heartbeat_cycle()
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        logger.info(f"[{agent_name}] Shutting down...")
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
