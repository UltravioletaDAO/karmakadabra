"""
KarmaKadabra V2 Swarm Module

Orchestrates autonomous AI agent swarms on Execution Market.

Components:
- reputation_bridge: Bridges EM reputation ↔ ERC-8004 on-chain reputation
- lifecycle_manager: Manages agent lifecycle (boot → active → sleep → wake)
- swarm_orchestrator: Coordinates multi-agent task distribution and economics
- task_executor: Autonomous task execution engine (the keystone)
- swarm_context_injector: Dynamic per-agent context from Skill DNA + reputation
- autojob_bridge: Routes tasks through AutoJob's matching intelligence
- describenet_reader: Reads describe-net SealRegistry reputation from chain
- swarm_runner: CLI entry point for swarm operations
- swarm_daemon: Production daemon with WAL, snapshots, and self-healing

Usage:
    >>> from mcp_server.swarm import SwarmOrchestrator, LifecycleManager, ReputationBridge
    >>> from mcp_server.swarm import SwarmTaskExecutor
    >>>
    >>> bridge = ReputationBridge(network="base")
    >>> lifecycle = LifecycleManager(max_agents=48)
    >>> orchestrator = SwarmOrchestrator(lifecycle=lifecycle, bridge=bridge)
    >>> executor = SwarmTaskExecutor(orchestrator=orchestrator, dry_run=True)
    >>>
    >>> # Register agents
    >>> orchestrator.register_agent("agent_aurora", wallet="0x...", personality="explorer")
    >>>
    >>> # Distribute a task to the best-matched agent
    >>> assignment = await orchestrator.assign_task(task_id="task_abc")
    >>>
    >>> # Execute autonomously
    >>> result = await executor.execute_task(task_data, assignment.assigned_agent)
"""

from .reputation_bridge import ReputationBridge, BridgedReputation
from .lifecycle_manager import LifecycleManager, AgentState, AgentStatus
from .swarm_orchestrator import SwarmOrchestrator, TaskAssignment, AgentProfile
from .task_executor import SwarmTaskExecutor, ExecutionResult, ExecutionStrategy
from .swarm_api import create_app as create_swarm_app
from .swarm_analytics import SwarmAnalytics, SwarmReport, AgentPerformanceScore
from .swarm_daemon import SwarmDaemon, WriteAheadLog, FleetBudgetManager

__all__ = [
    "ReputationBridge",
    "BridgedReputation",
    "LifecycleManager",
    "AgentState",
    "AgentStatus",
    "SwarmOrchestrator",
    "TaskAssignment",
    "AgentProfile",
    "SwarmTaskExecutor",
    "ExecutionResult",
    "ExecutionStrategy",
    "create_swarm_app",
    "SwarmAnalytics",
    "SwarmReport",
    "AgentPerformanceScore",
    "SwarmDaemon",
    "WriteAheadLog",
    "FleetBudgetManager",
]
