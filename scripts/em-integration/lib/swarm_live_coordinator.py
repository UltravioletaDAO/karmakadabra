#!/usr/bin/env python3
"""
Swarm Live Coordinator — Bridge Between KK V2 Swarm and Live EM API

Connects the swarm orchestrator to the real Execution Market API to:
1. Fetch published tasks from the live API
2. Match them against the agent roster using skill-based scoring
3. Track task lifecycle events through the performance tracker
4. Report swarm state and decisions

This is the integration glue between the in-memory swarm orchestrator
and the production EM infrastructure.

Usage:
    coordinator = SwarmLiveCoordinator()
    
    # Fetch and match available tasks
    matches = await coordinator.scan_and_match()
    
    # Get swarm health report
    health = await coordinator.health_report()
    
    # Run a single coordination cycle
    cycle = await coordinator.run_cycle()
    
    # Get performance report
    report = coordinator.performance_report()
"""

import asyncio
import json
import logging
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List

# Parent imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server.swarm import SwarmOrchestrator, LifecycleManager, ReputationBridge
from mcp_server.swarm.swarm_orchestrator import TASK_CATEGORY_SKILLS

logger = logging.getLogger("kk.live_coordinator")


# EM API configuration
EM_API_BASE = os.environ.get("EM_API_BASE", "https://api.execution.market")

# SSL context that allows self-signed certs (for dev)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = True
_SSL_CTX.verify_mode = ssl.CERT_REQUIRED


def _api_get(endpoint: str, params: Optional[Dict] = None) -> dict:
    """Make a GET request to the EM API."""
    url = f"{EM_API_BASE}{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{query}"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "KK-Swarm-Coordinator/1.0")
    req.add_header("Accept", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"EM API error: {endpoint} → {e}")
        return {}


class EMTaskView:
    """Parsed view of an EM task for swarm matching."""
    
    def __init__(self, raw: dict):
        self.raw = raw
        self.id = raw.get("id", "")
        self.title = raw.get("title", "")
        self.status = raw.get("status", "")
        self.category = raw.get("category", "simple_action")
        self.bounty_usd = float(raw.get("bounty_usd", 0))
        self.chain = raw.get("payment_network", "base")
        self.deadline = raw.get("deadline")
        self.instructions = raw.get("instructions", "")
        self.evidence_schema = raw.get("evidence_schema") or []
        self.location_hint = raw.get("location_hint", "")
        self.min_reputation = raw.get("min_reputation", 0)
        self.agent_id = raw.get("agent_id", "")
        self.erc8004_agent_id = raw.get("erc8004_agent_id", "")
        self.created_at = raw.get("created_at", "")
    
    @property
    def is_agent_capable(self) -> bool:
        """Can an AI agent complete this task?"""
        skills = TASK_CATEGORY_SKILLS.get(self.category, {})
        if not skills.get("agent_capable", True):
            return False
        # Physical tasks with location are probably not agent-capable
        if self.location_hint and self.category in (
            "physical_verification", "delivery", "mystery_shopping"
        ):
            return False
        return True
    
    @property 
    def required_skills(self) -> List[str]:
        """Skills required based on category."""
        skills = TASK_CATEGORY_SKILLS.get(self.category, {})
        return skills.get("required", [])
    
    def __repr__(self):
        return (
            f"EMTask(id={self.id[:8]}..., title={self.title!r}, "
            f"category={self.category}, bounty=${self.bounty_usd:.2f}, "
            f"chain={self.chain})"
        )


class SwarmLiveCoordinator:
    """
    Live coordinator that bridges the KK V2 Swarm with the EM API.
    
    Uses the SwarmOrchestrator for intelligent task-agent matching
    and tracks results via the AgentPerformanceTracker.
    """
    
    def __init__(
        self,
        orchestrator: Optional[SwarmOrchestrator] = None,
        dry_run: bool = True,
    ):
        """
        Args:
            orchestrator: Pre-configured SwarmOrchestrator (creates default if None)
            dry_run: If True, don't actually accept tasks on EM (just match)
        """
        self.orchestrator = orchestrator or self._default_orchestrator()
        self.dry_run = dry_run
        self._cycle_count = 0
        self._last_tasks_seen: Dict[str, EMTaskView] = {}
    
    def _default_orchestrator(self) -> SwarmOrchestrator:
        """Create a default orchestrator with the KK roster."""
        lifecycle = LifecycleManager(max_agents=48)
        bridge = ReputationBridge(dry_run=True)
        orch = SwarmOrchestrator(lifecycle=lifecycle, bridge=bridge)
        return orch
    
    # ── API Interaction ──
    
    def fetch_published_tasks(self, limit: int = 50) -> List[EMTaskView]:
        """Fetch currently published (available) tasks from EM API."""
        data = _api_get("/api/v1/tasks", {"status": "published", "limit": str(limit)})
        
        if not data:
            return []
        
        tasks = data if isinstance(data, list) else data.get("tasks", data.get("data", []))
        views = [EMTaskView(t) for t in tasks]
        
        logger.info(f"Fetched {len(views)} published tasks from EM API")
        return views
    
    def fetch_completed_tasks(self, limit: int = 100) -> List[EMTaskView]:
        """Fetch recently completed tasks (for performance tracking)."""
        data = _api_get("/api/v1/tasks", {"status": "completed", "limit": str(limit)})
        
        if not data:
            return []
        
        tasks = data if isinstance(data, list) else data.get("tasks", data.get("data", []))
        return [EMTaskView(t) for t in tasks]
    
    def fetch_api_health(self) -> dict:
        """Check EM API health."""
        return _api_get("/health")
    
    # ── Matching ──
    
    async def scan_and_match(self) -> List[dict]:
        """
        Fetch published tasks and match each against the agent roster.
        
        Returns a list of match results, each containing:
        - task: EMTaskView
        - assignment: TaskAssignment (best agent match)
        - agent_capable: whether any AI agent can do this
        """
        tasks = self.fetch_published_tasks()
        results = []
        
        for task in tasks:
            result = {
                "task_id": task.id,
                "title": task.title,
                "category": task.category,
                "bounty_usd": task.bounty_usd,
                "chain": task.chain,
                "agent_capable": task.is_agent_capable,
                "assignment": None,
            }
            
            if task.is_agent_capable and self.orchestrator.profiles:
                assignment = await self.orchestrator.assign_task(
                    task_id=task.id,
                    category=task.category,
                    bounty_usd=task.bounty_usd,
                )
                result["assignment"] = assignment.to_dict()
            elif not task.is_agent_capable:
                result["skip_reason"] = "Requires physical presence"
            else:
                result["skip_reason"] = "No agents registered"
            
            results.append(result)
        
        self._last_tasks_seen = {t.id: t for t in tasks}
        logger.info(
            f"Scanned {len(tasks)} tasks: "
            f"{sum(1 for r in results if r.get('assignment'))} matched, "
            f"{sum(1 for r in results if not r.get('agent_capable', True))} physical-only"
        )
        
        return results
    
    # ── Coordination Cycle ──
    
    async def run_cycle(self) -> dict:
        """
        Run a single coordination cycle:
        1. Check API health
        2. Fetch published tasks
        3. Match tasks to agents
        4. Report results
        
        In dry_run mode, this doesn't actually accept tasks.
        """
        self._cycle_count += 1
        cycle_start = time.time()
        
        # Step 1: Health check
        health = self.fetch_api_health()
        api_healthy = bool(health.get("status") == "healthy" or health.get("overall"))
        
        if not api_healthy:
            return {
                "cycle": self._cycle_count,
                "status": "api_unhealthy",
                "health": health,
                "duration_ms": int((time.time() - cycle_start) * 1000),
            }
        
        # Step 2: Fetch and match
        matches = await self.scan_and_match()
        
        # Step 3: Compute summary
        matched = [m for m in matches if m.get("assignment")]
        unmatched = [m for m in matches if not m.get("assignment")]
        physical = [m for m in matches if not m.get("agent_capable", True)]
        
        total_bounty = sum(m["bounty_usd"] for m in matched)
        
        result = {
            "cycle": self._cycle_count,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "api_healthy": api_healthy,
            "tasks_available": len(matches),
            "tasks_matched": len(matched),
            "tasks_physical_only": len(physical),
            "tasks_unmatched": len(unmatched) - len(physical),
            "total_bounty_matched_usd": round(total_bounty, 2),
            "dry_run": self.dry_run,
            "duration_ms": int((time.time() - cycle_start) * 1000),
            "matches": matched[:10],  # Top 10 for brevity
        }
        
        logger.info(
            f"Cycle {self._cycle_count}: {len(matches)} tasks, "
            f"{len(matched)} matched (${total_bounty:.2f}), "
            f"took {result['duration_ms']}ms"
        )
        
        return result
    
    # ── Health & Reports ──
    
    async def health_report(self) -> dict:
        """Comprehensive health report: API + Swarm + Agents."""
        api_health = self.fetch_api_health()
        
        # Count completed tasks for volume stats
        completed = self.fetch_completed_tasks(limit=50)
        
        # Swarm metrics
        swarm_metrics = self.orchestrator.metrics()
        economics = self.orchestrator.economic_summary()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "api": {
                "status": "healthy" if api_health else "unreachable",
                "health": api_health,
            },
            "em_stats": {
                "recent_completed_tasks": len(completed),
                "chains_active": list(set(t.chain for t in completed)),
                "categories_seen": list(set(t.category for t in completed)),
                "total_bounty_completed": round(
                    sum(t.bounty_usd for t in completed), 2
                ),
            },
            "swarm": {
                "agents_registered": len(self.orchestrator.profiles),
                "agents_active": swarm_metrics["agents"]["active"],
                "tasks_tracked": swarm_metrics["tasks"]["total_assigned"],
                "success_rate": swarm_metrics["tasks"]["success_rate"],
            },
            "economics": economics,
            "cycles_completed": self._cycle_count,
        }
    
    def task_category_analysis(self) -> dict:
        """Analyze task categories from completed tasks to guide agent skill development."""
        completed = self.fetch_completed_tasks(limit=200)
        
        category_stats: Dict[str, dict] = {}
        for task in completed:
            cat = task.category
            if cat not in category_stats:
                category_stats[cat] = {
                    "count": 0,
                    "total_bounty": 0.0,
                    "chains": set(),
                    "agent_capable": TASK_CATEGORY_SKILLS.get(cat, {}).get(
                        "agent_capable", True
                    ),
                }
            category_stats[cat]["count"] += 1
            category_stats[cat]["total_bounty"] += task.bounty_usd
            category_stats[cat]["chains"].add(task.chain)
        
        # Convert sets to lists for JSON
        for cat in category_stats:
            category_stats[cat]["chains"] = list(category_stats[cat]["chains"])
            category_stats[cat]["avg_bounty"] = round(
                category_stats[cat]["total_bounty"] / max(1, category_stats[cat]["count"]),
                2,
            )
            category_stats[cat]["total_bounty"] = round(
                category_stats[cat]["total_bounty"], 2
            )
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_analyzed": len(completed),
            "categories": category_stats,
            "recommendations": self._skill_recommendations(category_stats),
        }
    
    def _skill_recommendations(self, category_stats: dict) -> List[str]:
        """Generate skill development recommendations for the swarm."""
        recs = []
        
        # Find most common categories
        sorted_cats = sorted(
            category_stats.items(),
            key=lambda x: -x[1]["count"]
        )
        
        if sorted_cats:
            top = sorted_cats[0]
            recs.append(
                f"Most common task type: {top[0]} ({top[1]['count']} tasks). "
                f"Ensure agents have skills: {TASK_CATEGORY_SKILLS.get(top[0], {}).get('required', ['general'])}"
            )
        
        # Find highest-value categories
        sorted_by_value = sorted(
            category_stats.items(),
            key=lambda x: -x[1].get("avg_bounty", 0)
        )
        if sorted_by_value and sorted_by_value[0][1].get("avg_bounty", 0) > 0:
            top_val = sorted_by_value[0]
            recs.append(
                f"Highest-value category: {top_val[0]} "
                f"(avg ${top_val[1]['avg_bounty']:.2f}/task). "
                f"Prioritize agents with these skills."
            )
        
        # Check for agent-capable tasks that aren't being served
        agent_capable_unserved = [
            cat for cat, stats in category_stats.items()
            if stats.get("agent_capable", True) and stats["count"] > 5
        ]
        if agent_capable_unserved:
            recs.append(
                f"Agent-capable categories with volume: {', '.join(agent_capable_unserved)}. "
                f"These are opportunities for swarm automation."
            )
        
        return recs


# ── CLI ──

async def main():
    """CLI for live coordinator testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="KK V2 Swarm Live Coordinator")
    parser.add_argument("--health", action="store_true", help="Show health report")
    parser.add_argument("--cycle", action="store_true", help="Run one coordination cycle")
    parser.add_argument("--scan", action="store_true", help="Scan and match tasks")
    parser.add_argument("--categories", action="store_true", help="Analyze task categories")
    parser.add_argument("--published", action="store_true", help="List published tasks")
    parser.add_argument("--completed", action="store_true", help="List recent completed tasks")
    parser.add_argument("--limit", type=int, default=20, help="Task limit")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    coord = SwarmLiveCoordinator(dry_run=True)
    
    if args.health:
        report = await coord.health_report()
        print(json.dumps(report, indent=2))
    
    elif args.cycle:
        result = await coord.run_cycle()
        print(json.dumps(result, indent=2, default=str))
    
    elif args.scan:
        matches = await coord.scan_and_match()
        for m in matches:
            print(json.dumps(m, indent=2, default=str))
    
    elif args.categories:
        analysis = coord.task_category_analysis()
        print(json.dumps(analysis, indent=2))
    
    elif args.published:
        tasks = coord.fetch_published_tasks(limit=args.limit)
        for t in tasks:
            print(f"  [{t.category}] {t.title} — ${t.bounty_usd:.2f} on {t.chain}")
    
    elif args.completed:
        tasks = coord.fetch_completed_tasks(limit=args.limit)
        for t in tasks:
            print(f"  [{t.category}] {t.title} — ${t.bounty_usd:.2f} on {t.chain}")
        print(f"\n  Total: {len(tasks)} completed tasks")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
