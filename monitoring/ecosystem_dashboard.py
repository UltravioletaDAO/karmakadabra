"""
Swarm Health Dashboard — Real-Time Ecosystem Status
=====================================================

A unified health check that queries all systems in the Ultravioleta
ecosystem and produces a comprehensive status report:

1. EM API health (all 5 components)
2. Live marketplace state (published/completed tasks, bounty totals)
3. ERC-8004 identity status (24 agents on Base)
4. AutoJob integration readiness
5. Swarm component status (all 7 links)

Usage:
    from monitoring.ecosystem_dashboard import SwarmHealthDashboard
    
    dashboard = SwarmHealthDashboard()
    report = dashboard.generate_report()
    print(report.summary())
    
    # Or check individual systems:
    em_health = dashboard.check_em_api()
    chain_health = dashboard.check_erc8004()
    swarm_health = dashboard.check_swarm_components()

CLI:
    python -m monitoring.ecosystem_dashboard
"""

import json
import logging
import math
import ssl
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════

EM_API_BASE = "https://api.execution.market"
BASE_RPC_ENDPOINTS = [
    "https://base.llamarpc.com",
    "https://1rpc.io/base",
    "https://base-rpc.publicnode.com",
    "https://mainnet.base.org",
]
BASE_RPC = BASE_RPC_ENDPOINTS[0]

# ERC-8004 contracts (CREATE2 — same on every chain)
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

# Payment contracts on Base
PAYMENT_OPERATOR = "0x271f9fa7f8907aCf178CCFB470076D9129D8F0Eb"
AUTH_CAPTURE_ESCROW = "0xb9488351E48b23D798f24e8174514F28B741Eb4f"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Known KK V2 system agents (ERC-8004 IDs on Base)
KK_SYSTEM_AGENTS = {
    18775: "coordinator",
    18776: "karma-hello",
    18777: "skill-extractor",
    18778: "voice-extractor",
    18779: "validator",
}

# Expected enabled networks
EXPECTED_NETWORKS = {"base", "ethereum", "polygon", "arbitrum", "celo", "monad", "avalanche", "optimism"}


# ══════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════


class HealthStatus:
    """Health status constants."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class ComponentCheck:
    """Result of a single health check."""
    name: str
    status: str = HealthStatus.UNKNOWN
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def __str__(self) -> str:
        icon = {"healthy": "✅", "degraded": "⚠️", "down": "❌", "unknown": "❓"}
        s = icon.get(self.status, "❓")
        latency = f" ({self.latency_ms:.0f}ms)" if self.latency_ms else ""
        err = f" — {self.error}" if self.error else ""
        return f"{s} {self.name}{latency}{err}"


@dataclass
class MarketplaceState:
    """Snapshot of the EM marketplace."""
    published_tasks: int = 0
    completed_tasks: int = 0
    total_bounty_published: float = 0.0
    total_bounty_completed: float = 0.0
    networks_active: List[str] = field(default_factory=list)
    categories_seen: List[str] = field(default_factory=list)
    avg_bounty_published: float = 0.0
    avg_bounty_completed: float = 0.0


@dataclass
class ChainState:
    """ERC-8004 on-chain state."""
    total_identities: int = 0
    system_agents_found: int = 0
    system_agents_missing: List[str] = field(default_factory=list)
    block_number: int = 0
    chain_id: int = 0


@dataclass
class SwarmComponentStatus:
    """Status of swarm integration chain components."""
    component: str
    exists: bool = False
    test_count: int = 0
    line_count: int = 0
    description: str = ""


@dataclass
class HealthReport:
    """Complete ecosystem health report."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Individual checks
    em_api: Optional[ComponentCheck] = None
    em_auth: Optional[ComponentCheck] = None
    em_tasks: Optional[ComponentCheck] = None
    base_rpc: Optional[ComponentCheck] = None
    erc8004: Optional[ComponentCheck] = None
    
    # Aggregated state
    marketplace: Optional[MarketplaceState] = None
    chain: Optional[ChainState] = None
    swarm_components: List[SwarmComponentStatus] = field(default_factory=list)
    
    # Summary
    overall_status: str = HealthStatus.UNKNOWN
    healthy_count: int = 0
    total_checks: int = 0
    total_latency_ms: float = 0.0

    def summary(self) -> str:
        """Human-readable summary of the full health report."""
        lines = []
        lines.append("=" * 60)
        lines.append("  SWARM HEALTH DASHBOARD")
        lines.append(f"  {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("=" * 60)
        lines.append("")
        
        # Overall
        icon = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(self.overall_status, "⚪")
        lines.append(f"{icon} Overall: {self.overall_status.upper()} ({self.healthy_count}/{self.total_checks} checks passing)")
        lines.append(f"   Total latency: {self.total_latency_ms:.0f}ms")
        lines.append("")
        
        # EM API
        lines.append("─── Execution Market API ───")
        for check in [self.em_api, self.em_auth, self.em_tasks]:
            if check:
                lines.append(f"  {check}")
        lines.append("")
        
        # Marketplace
        if self.marketplace:
            m = self.marketplace
            lines.append("─── Marketplace State ───")
            lines.append(f"  📋 Published tasks: {m.published_tasks} (${m.total_bounty_published:.2f} total)")
            lines.append(f"  ✅ Completed tasks: {m.completed_tasks} (${m.total_bounty_completed:.2f} total)")
            lines.append(f"  💰 Avg bounty: ${m.avg_bounty_published:.2f} (published) / ${m.avg_bounty_completed:.2f} (completed)")
            lines.append(f"  🌐 Networks: {', '.join(m.networks_active)}")
            lines.append(f"  📁 Categories: {', '.join(m.categories_seen[:5])}")
            lines.append("")
        
        # Chain
        lines.append("─── Base Mainnet (ERC-8004) ───")
        if self.base_rpc:
            lines.append(f"  {self.base_rpc}")
        if self.erc8004:
            lines.append(f"  {self.erc8004}")
        if self.chain:
            c = self.chain
            lines.append(f"  🔗 Block: {c.block_number:,}")
            id_str = str(c.total_identities) if c.total_identities >= 0 else "unknown"
            lines.append(f"  🤖 Identities (platform wallet): {id_str}")
            lines.append(f"  🎯 System agents: {c.system_agents_found}/5")
            if c.system_agents_missing:
                lines.append(f"  ⚠️ Missing: {', '.join(c.system_agents_missing)}")
        lines.append("")
        
        # Swarm components
        if self.swarm_components:
            lines.append("─── Swarm Integration Chain ───")
            for comp in self.swarm_components:
                icon = "✅" if comp.exists else "❌"
                lines.append(f"  {icon} {comp.component}: {comp.description}")
                if comp.line_count:
                    lines.append(f"      {comp.line_count} lines, {comp.test_count} tests")
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# ══════════════════════════════════════════════
# HTTP Helpers (stdlib only, no dependencies)
# ══════════════════════════════════════════════


def _http_get(url: str, timeout: int = 10) -> Tuple[dict, float]:
    """GET request, returns (parsed_json, latency_ms)."""
    ctx = ssl.create_default_context()
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SwarmHealthDashboard/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.loads(resp.read())
            latency = (time.monotonic() - start) * 1000
            return data, latency
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        raise


def _eth_call(to: str, data: str, rpc: str = BASE_RPC) -> str:
    """Make an eth_call to a contract."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }).encode()
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        rpc,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        result = json.loads(resp.read())
    
    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error']}")
    
    return result.get("result", "0x")


def _get_block_number(rpc: str = BASE_RPC) -> int:
    """Get current block number."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": [],
    }).encode()
    
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        rpc,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        result = json.loads(resp.read())
    
    return int(result.get("result", "0x0"), 16)


# ══════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════


class SwarmHealthDashboard:
    """Unified health checker for the Ultravioleta ecosystem."""

    def __init__(self, em_api_base: str = EM_API_BASE, rpc: str = BASE_RPC):
        self.em_api = em_api_base
        self.rpc = rpc

    def check_em_health(self) -> ComponentCheck:
        """Check EM API /health endpoint."""
        try:
            data, latency = _http_get(f"{self.em_api}/health")
            status = data.get("status", "unknown")
            components = data.get("components", {})
            
            all_healthy = all(
                c.get("status") == "healthy" 
                for c in components.values()
            )
            
            return ComponentCheck(
                name="EM API Health",
                status=HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED,
                latency_ms=latency,
                details=components,
            )
        except Exception as e:
            return ComponentCheck(
                name="EM API Health",
                status=HealthStatus.DOWN,
                error=str(e),
            )

    def check_em_auth(self) -> ComponentCheck:
        """Check EM auth nonce endpoint."""
        try:
            data, latency = _http_get(f"{self.em_api}/api/v1/auth/nonce")
            nonce = data.get("nonce", "")
            
            return ComponentCheck(
                name="EM Auth (Nonce)",
                status=HealthStatus.HEALTHY if nonce else HealthStatus.DEGRADED,
                latency_ms=latency,
                details={"nonce_length": len(nonce)},
            )
        except Exception as e:
            return ComponentCheck(
                name="EM Auth (Nonce)",
                status=HealthStatus.DOWN,
                error=str(e),
            )

    def check_em_tasks(self) -> Tuple[ComponentCheck, MarketplaceState]:
        """Check EM tasks and gather marketplace state."""
        marketplace = MarketplaceState()
        
        try:
            # Published tasks
            pub_data, lat1 = _http_get(
                f"{self.em_api}/api/v1/tasks?status=published&limit=50"
            )
            pub_tasks = pub_data.get("tasks", [])
            marketplace.published_tasks = pub_data.get("total", len(pub_tasks))
            
            # Completed tasks
            comp_data, lat2 = _http_get(
                f"{self.em_api}/api/v1/tasks?status=completed&limit=50"
            )
            comp_tasks = comp_data.get("tasks", [])
            marketplace.completed_tasks = comp_data.get("total", len(comp_tasks))
            
            # Analyze published tasks
            networks = set()
            categories = set()
            bounty_pub = 0.0
            for t in pub_tasks:
                bounty_pub += float(t.get("bounty_usd", 0))
                net = t.get("payment_network", "unknown")
                if net:
                    networks.add(net)
                cat = t.get("category", "unknown")
                if cat:
                    categories.add(cat)
            
            marketplace.total_bounty_published = bounty_pub
            marketplace.avg_bounty_published = bounty_pub / max(1, len(pub_tasks))
            
            # Analyze completed tasks
            bounty_comp = 0.0
            for t in comp_tasks:
                bounty_comp += float(t.get("bounty_usd", 0))
                net = t.get("payment_network", "unknown")
                if net:
                    networks.add(net)
                cat = t.get("category", "unknown")
                if cat:
                    categories.add(cat)
            
            marketplace.total_bounty_completed = bounty_comp
            marketplace.avg_bounty_completed = bounty_comp / max(1, len(comp_tasks))
            marketplace.networks_active = sorted(networks)
            marketplace.categories_seen = sorted(categories)
            
            total_latency = lat1 + lat2
            
            check = ComponentCheck(
                name="EM Tasks API",
                status=HealthStatus.HEALTHY,
                latency_ms=total_latency,
                details={
                    "published": marketplace.published_tasks,
                    "completed": marketplace.completed_tasks,
                },
            )
            return check, marketplace
            
        except Exception as e:
            check = ComponentCheck(
                name="EM Tasks API",
                status=HealthStatus.DOWN,
                error=str(e),
            )
            return check, marketplace

    def check_base_rpc(self) -> Tuple[ComponentCheck, int]:
        """Check Base RPC connectivity with fallback endpoints."""
        rpcs = [self.rpc] + [r for r in BASE_RPC_ENDPOINTS if r != self.rpc]
        
        for rpc_url in rpcs:
            try:
                start = time.monotonic()
                block = _get_block_number(rpc_url)
                latency = (time.monotonic() - start) * 1000
                
                # Update self.rpc if fallback worked
                self.rpc = rpc_url
                
                return ComponentCheck(
                    name=f"Base RPC ({rpc_url.split('//')[1].split('/')[0]})",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                    details={"block_number": block, "endpoint": rpc_url},
                ), block
            except Exception:
                continue
        
        return ComponentCheck(
            name="Base RPC",
            status=HealthStatus.DOWN,
            error="All RPC endpoints failed",
        ), 0

    def check_erc8004(self) -> Tuple[ComponentCheck, ChainState]:
        """Check ERC-8004 contract state on Base.
        
        Uses balanceOf(platformWallet) to verify contract is live,
        then checks each system agent via ownerOf(tokenId).
        Note: ERC-8004 may not implement totalSupply().
        """
        chain = ChainState()
        
        try:
            start = time.monotonic()
            
            # Check if contract is live by calling balanceOf on platform wallet
            # balanceOf(address) selector = 0x70a08231
            platform_wallet = "0xD3868E1eD738CED6945A574a7c769433BeD5d474"
            addr_padded = platform_wallet[2:].lower().zfill(64)
            try:
                result = _eth_call(
                    IDENTITY_REGISTRY,
                    f"0x70a08231{addr_padded}",
                    self.rpc,
                )
                platform_balance = int(result, 16) if result != "0x" else 0
                chain.total_identities = platform_balance  # At least this many
            except Exception:
                chain.total_identities = -1  # Unknown
            
            # Check system agents via ownerOf(tokenId)
            found = 0
            missing = []
            for agent_id, name in KK_SYSTEM_AGENTS.items():
                # ownerOf(tokenId) selector = 0x6352211e
                data = f"0x6352211e{agent_id:064x}"
                try:
                    owner = _eth_call(IDENTITY_REGISTRY, data, self.rpc)
                    if owner and owner != "0x" and int(owner, 16) != 0:
                        found += 1
                    else:
                        missing.append(name)
                except Exception:
                    missing.append(name)
            
            chain.system_agents_found = found
            chain.system_agents_missing = missing
            
            latency = (time.monotonic() - start) * 1000
            
            # Healthy if at least 3/5 system agents found
            if found >= 4:
                status = HealthStatus.HEALTHY
            elif found >= 2:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.DOWN
            
            check = ComponentCheck(
                name="ERC-8004 Registry",
                status=status,
                latency_ms=latency,
                details={
                    "platform_balance": chain.total_identities,
                    "system_agents": f"{found}/{len(KK_SYSTEM_AGENTS)}",
                },
            )
            return check, chain
            
        except Exception as e:
            check = ComponentCheck(
                name="ERC-8004 Registry",
                status=HealthStatus.DOWN,
                error=str(e),
            )
            return check, chain

    def check_swarm_components(self) -> List[SwarmComponentStatus]:
        """Check which swarm integration components exist."""
        import os
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        components = [
            ("Evidence Parser (AutoJob Bridge)", "autojob_bridge.py",
             "AutoJob Bridge — skill DNA routing"),
            ("Reputation Bridge", "reputation_bridge.py",
             "EM ↔ ERC-8004 bidirectional sync"),
            ("Lifecycle Manager", "lifecycle_manager.py",
             "Agent budget + state management"),
            ("Context Injector", "swarm_context_injector.py",
             "Skill DNA → agent prompt injection"),
            ("Task Executor", "task_executor.py",
             "Autonomous task execution engine"),
            ("Swarm Analytics", "swarm_analytics.py",
             "Performance intelligence + anomaly detection"),
            ("Swarm Daemon", "swarm_daemon.py",
             "Production runtime with WAL + snapshots"),
        ]
        
        results = []
        for name, path, desc in components:
            full_path = os.path.join(base_dir, path)
            exists = os.path.isfile(full_path)
            
            line_count = 0
            if exists:
                try:
                    with open(full_path) as f:
                        line_count = sum(1 for _ in f)
                except Exception:
                    pass
            
            results.append(SwarmComponentStatus(
                component=name,
                exists=exists,
                line_count=line_count,
                description=desc,
            ))
        
        return results

    def generate_report(self) -> HealthReport:
        """Run all checks and generate a comprehensive report."""
        report = HealthReport()
        checks = []
        
        # EM API health
        report.em_api = self.check_em_health()
        checks.append(report.em_api)
        
        # EM auth
        report.em_auth = self.check_em_auth()
        checks.append(report.em_auth)
        
        # EM tasks + marketplace state
        report.em_tasks, report.marketplace = self.check_em_tasks()
        checks.append(report.em_tasks)
        
        # Base RPC
        report.base_rpc, block = self.check_base_rpc()
        checks.append(report.base_rpc)
        
        # ERC-8004
        report.erc8004, report.chain = self.check_erc8004()
        if block:
            report.chain.block_number = block
        checks.append(report.erc8004)
        
        # Swarm components
        report.swarm_components = self.check_swarm_components()
        
        # Calculate overall
        report.total_checks = len(checks)
        report.healthy_count = sum(1 for c in checks if c.is_healthy)
        report.total_latency_ms = sum(c.latency_ms for c in checks)
        
        if report.healthy_count == report.total_checks:
            report.overall_status = HealthStatus.HEALTHY
        elif report.healthy_count >= report.total_checks * 0.6:
            report.overall_status = HealthStatus.DEGRADED
        else:
            report.overall_status = HealthStatus.DOWN
        
        return report


# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════

if __name__ == "__main__":
    dashboard = SwarmHealthDashboard()
    report = dashboard.generate_report()
    print(report.summary())
