"""
V2BaseAgent — Composes v1 ERC8004BaseAgent with v2 AgentLifecycle.

100% backward compatible: v1 agents keep using ERC8004BaseAgent directly.
New agents and upgrades use V2BaseAgent for lifecycle management.

Usage:
    from lib.v2_base_agent import V2BaseAgent

    class MyAgent(V2BaseAgent):
        async def execute_task(self, task):
            ...

    agent = MyAgent(
        agent_name="my-agent",
        agent_domain="my-agent.karmacadabra.ultravioletadao.xyz",
        network="base",  # mainnet USDC
    )
    await agent.start()
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from shared.base_agent import ERC8004BaseAgent
from shared.contracts_config import get_network_config, get_payment_token
from lib.agent_lifecycle import (
    AgentLifecycle,
    AgentState,
    AgentType,
    LifecycleConfig,
    TransitionReason,
    transition,
)

logger = logging.getLogger("kk.v2_base")


class V2BaseAgent(ERC8004BaseAgent):
    """
    V2 agent: v1 blockchain registration + v2 lifecycle management.

    Extends ERC8004BaseAgent with:
    - State machine (OFFLINE -> IDLE -> WORKING -> IDLE)
    - Circuit breaker for consecutive failures
    - Heartbeat tracking
    - Multi-chain support via network parameter
    """

    def __init__(
        self,
        agent_name: str,
        agent_domain: str,
        network: Optional[str] = None,
        agent_type: AgentType = AgentType.USER,
        lifecycle_config: Optional[LifecycleConfig] = None,
        **kwargs,
    ):
        """
        Initialize V2BaseAgent.

        Args:
            agent_name: Agent name for secrets lookup and registration.
            agent_domain: Agent's public domain.
            network: Network name (e.g., "base", "fuji"). Uses default if None.
            agent_type: SYSTEM, CORE, or USER (affects startup ordering).
            lifecycle_config: Custom lifecycle config. Uses defaults if None.
            **kwargs: Additional args passed to ERC8004BaseAgent.
        """
        # Resolve network config for v1 parent
        net_config = get_network_config(network)
        rpc_url = kwargs.pop("rpc_url", None) or net_config["rpc_url"]
        chain_id = kwargs.pop("chain_id", None) or net_config["chain_id"]

        super().__init__(
            agent_name=agent_name,
            agent_domain=agent_domain,
            rpc_url=rpc_url,
            chain_id=chain_id,
            identity_registry_address=kwargs.pop(
                "identity_registry_address",
                net_config.get("identity_registry"),
            ),
            reputation_registry_address=kwargs.pop(
                "reputation_registry_address",
                net_config.get("reputation_registry"),
            ),
            **kwargs,
        )

        # V2 lifecycle
        config = lifecycle_config or LifecycleConfig()
        self.lifecycle = AgentLifecycle(
            agent_name=agent_name,
            agent_type=agent_type,
        )
        self._lifecycle_config = config
        self._network = network or "base-sepolia"
        self._payment_token = get_payment_token(self._network)

        logger.info(
            f"[{agent_name}] V2BaseAgent initialized on {net_config['name']} "
            f"(payment: {self._payment_token['symbol']})"
        )

    @property
    def network_name(self) -> str:
        return self._network

    @property
    def payment_token(self) -> Dict[str, Any]:
        return self._payment_token

    @property
    def state(self) -> AgentState:
        return self.lifecycle.state

    # ------------------------------------------------------------------
    # Lifecycle methods
    # ------------------------------------------------------------------

    async def start(self):
        """Transition agent from OFFLINE to IDLE."""
        event = transition(
            self.lifecycle,
            TransitionReason.STARTUP,
            self._lifecycle_config,
        )
        if event and self.lifecycle.state == AgentState.STARTING:
            # Complete startup
            event = transition(
                self.lifecycle,
                TransitionReason.STARTUP,
                self._lifecycle_config,
            )
        logger.info(f"[{self.agent_name}] Started -> {self.lifecycle.state.value}")

    async def heartbeat(self) -> Dict[str, Any]:
        """
        Record heartbeat and return agent status.
        Call this periodically (default: every 5 minutes).
        """
        now = datetime.now(timezone.utc).isoformat()
        self.lifecycle.last_heartbeat = now

        return {
            "agent": self.agent_name,
            "state": self.lifecycle.state.value,
            "network": self._network,
            "last_heartbeat": now,
            "consecutive_failures": self.lifecycle.consecutive_failures,
        }

    async def start_task(self, task_id: str, details: Optional[Dict] = None):
        """Transition to WORKING state for a task."""
        event = transition(
            self.lifecycle,
            TransitionReason.TASK_ASSIGNED,
            self._lifecycle_config,
            details={"task_id": task_id},
        )
        if event:
            logger.info(f"[{self.agent_name}] Started task {task_id}")
        return event

    async def complete_task(self, task_id: str, result: Optional[Any] = None):
        """Mark current task as completed, transition back to IDLE."""
        event = transition(
            self.lifecycle,
            TransitionReason.TASK_COMPLETED,
            self._lifecycle_config,
        )
        if event:
            logger.info(f"[{self.agent_name}] Completed task {task_id}")
        return event

    async def fail_task(self, task_id: str, error: Optional[str] = None):
        """Mark current task as failed. May trigger circuit breaker."""
        event = transition(
            self.lifecycle,
            TransitionReason.TASK_FAILED,
            self._lifecycle_config,
        )
        if event:
            logger.info(f"[{self.agent_name}] Failed task {task_id}: {error}")

            # Check if circuit breaker should trip
            if (
                self.lifecycle.consecutive_failures
                >= self._lifecycle_config.circuit_breaker_threshold
            ):
                transition(
                    self.lifecycle,
                    TransitionReason.CIRCUIT_BREAKER,
                    self._lifecycle_config,
                )
                logger.warning(
                    f"[{self.agent_name}] Circuit breaker tripped after "
                    f"{self.lifecycle.consecutive_failures} failures"
                )

        return event

    async def stop(self):
        """Gracefully stop agent."""
        if self.lifecycle.state == AgentState.WORKING:
            transition(
                self.lifecycle,
                TransitionReason.MANUAL_STOP,
                self._lifecycle_config,
            )
            # Wait for drain
            logger.info(f"[{self.agent_name}] Draining current task...")
        else:
            transition(
                self.lifecycle,
                TransitionReason.MANUAL_STOP,
                self._lifecycle_config,
            )
        logger.info(f"[{self.agent_name}] Stopped -> {self.lifecycle.state.value}")

    def get_status(self) -> Dict[str, Any]:
        """Get full agent status dict."""
        status = self.lifecycle.to_dict()
        status["network"] = self._network
        status["payment_token"] = self._payment_token["symbol"]
        status["address"] = self.address
        return status
