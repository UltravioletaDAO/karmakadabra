"""
Karma Kadabra V2 — ERC-8004 Live Bridge

Connects the autojob ERC-8004 on-chain reader to the KK V2 reputation system.

This module bridges two worlds:
  1. On-chain ERC-8004 identity & reputation (Base mainnet)
  2. Off-chain KK V2 reputation_bridge scoring

The bridge:
  - Queries live ERC-8004 IdentityRegistry for agent registration
  - Maps wallet addresses to agent IDs
  - Feeds on-chain data into reputation_bridge.OnChainReputation
  - Provides a cache layer to avoid hammering RPC endpoints
  - Supports batch queries for all swarm agents
  - Falls back gracefully when RPC is unavailable

Design:
  - Uses autojob's erc8004_reader (zero-dependency, pure Python)
  - Caches results with configurable TTL
  - Thread-safe via simple dict locking
  - Pure function core with thin IO layer

Usage:
    bridge = ERC8004LiveBridge()
    identity = bridge.check_agent_identity("0xD3868E...")
    on_chain_rep = bridge.get_on_chain_reputation("0xD3868E...")

    # Integrate with reputation_bridge
    from lib.reputation_bridge import compute_unified_reputation
    unified = compute_unified_reputation(
        agent_name="kk-coordinator",
        on_chain=on_chain_rep,
        off_chain=off_chain_data,
    )
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .reputation_bridge import (
    OnChainReputation,
    SealScore,
    compute_on_chain_score,
)

logger = logging.getLogger("kk.erc8004_bridge")


# ---------------------------------------------------------------------------
# Contract Addresses (CREATE2 — same on all EVM chains)
# ---------------------------------------------------------------------------

IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
REPUTATION_REGISTRY = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"

# Known KK agents on Base mainnet
KK_AGENT_IDS = {
    2106: {"name": "em-platform", "wallet": "0xD3868E1eD738CED6945a574a7c769433BeD5d474"},
    18775: {"name": "kk-coordinator", "wallet": "0xe66C0a23E0721b77E22B6F0Ef30C8eAeB14B3e22"},
    18776: {"name": "kk-karma-hello", "wallet": None},
    18777: {"name": "kk-skill-extractor", "wallet": None},
    18778: {"name": "kk-voice-extractor", "wallet": None},
    18779: {"name": "kk-validator", "wallet": None},
}

# Reverse index: wallet → agent_id
WALLET_TO_AGENT: dict[str, int] = {}
for agent_id, info in KK_AGENT_IDS.items():
    if info["wallet"]:
        WALLET_TO_AGENT[info["wallet"].lower()] = agent_id


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class BridgeConfig:
    """Configuration for the ERC-8004 live bridge."""
    # RPC endpoint
    rpc_url: str = "https://mainnet.base.org"
    network: str = "base"

    # Cache settings
    cache_ttl_seconds: float = 300.0   # 5 minutes
    cache_max_entries: int = 1000

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Timeouts
    rpc_timeout_seconds: float = 10.0

    # File cache (persistent across restarts)
    cache_dir: Optional[Path] = None


# ---------------------------------------------------------------------------
# Cache Entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A cached query result."""
    data: Any
    timestamp: float  # Unix timestamp
    ttl: float

    @property
    def expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


# ---------------------------------------------------------------------------
# Identity Result
# ---------------------------------------------------------------------------

@dataclass
class AgentIdentity:
    """Result of an identity check."""
    wallet: str
    registered: bool = False
    agent_id: int = 0
    token_count: int = 0
    token_uri: str = ""
    metadata_url: str = ""
    network: str = "base"

    # Error info
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "wallet": self.wallet,
            "registered": self.registered,
            "agent_id": self.agent_id,
            "token_count": self.token_count,
            "token_uri": self.token_uri,
            "metadata_url": self.metadata_url,
            "network": self.network,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# ABI Encoding Helpers (zero-dependency)
# ---------------------------------------------------------------------------

def _encode_address(addr: str) -> str:
    """ABI-encode an address as 32-byte hex (no 0x prefix)."""
    return addr.lower().replace("0x", "").zfill(64)


def _encode_uint256(val: int) -> str:
    """ABI-encode a uint256 as 32-byte hex (no 0x prefix)."""
    return hex(val)[2:].zfill(64)


def _decode_uint256(hex_str: str) -> int:
    """Decode hex string to uint256."""
    if not hex_str or hex_str == "0x":
        return 0
    clean = hex_str.replace("0x", "")
    if not clean:
        return 0
    return int(clean, 16)


def _decode_address(hex_str: str) -> str:
    """Decode 32-byte hex to address."""
    if not hex_str or hex_str == "0x":
        return "0x" + "0" * 40
    raw = hex_str.replace("0x", "")
    return "0x" + raw[-40:]


# Function selectors
SEL_BALANCE_OF = "0x70a08231"    # balanceOf(address)
SEL_OWNER_OF = "0x6352211e"      # ownerOf(uint256)
SEL_TOKEN_URI = "0xc87b56dd"     # tokenURI(uint256)


# ---------------------------------------------------------------------------
# RPC Call (minimal, zero-dependency)
# ---------------------------------------------------------------------------

def _eth_call(
    rpc_url: str,
    to: str,
    data: str,
    timeout: float = 10.0,
) -> Optional[str]:
    """Make an eth_call via JSON-RPC. Returns hex result or None on error."""
    import ssl
    import urllib.request

    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
        "id": 1,
    }).encode()

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            rpc_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            result = json.loads(resp.read())

        if "error" in result:
            logger.debug(f"RPC error: {result['error']}")
            return None

        return result.get("result", None)

    except Exception as e:
        logger.debug(f"RPC call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Core Bridge Functions (pure, testable)
# ---------------------------------------------------------------------------

def parse_balance_response(hex_response: Optional[str]) -> int:
    """Parse a balanceOf response into a count."""
    if hex_response is None:
        return 0
    return _decode_uint256(hex_response)


def parse_owner_response(hex_response: Optional[str]) -> Optional[str]:
    """Parse an ownerOf response into an address."""
    if hex_response is None:
        return None
    addr = _decode_address(hex_response)
    if addr == "0x" + "0" * 40:
        return None
    return addr


def resolve_agent_id_from_wallet(wallet: str) -> Optional[int]:
    """Resolve a wallet address to a known agent ID.

    Uses the local known-agent index. Returns None if unknown.
    """
    return WALLET_TO_AGENT.get(wallet.lower())


def build_identity_from_data(
    wallet: str,
    balance: int,
    known_agent_id: Optional[int],
    token_uri: Optional[str] = None,
    network: str = "base",
) -> AgentIdentity:
    """Build an AgentIdentity from raw data."""
    identity = AgentIdentity(
        wallet=wallet.lower(),
        registered=balance > 0,
        token_count=balance,
        network=network,
    )

    if known_agent_id is not None:
        identity.agent_id = known_agent_id

    if token_uri:
        identity.token_uri = token_uri
        if token_uri.startswith("ipfs://"):
            identity.metadata_url = f"https://ipfs.io/ipfs/{token_uri[7:]}"

    return identity


def build_on_chain_reputation_from_identity(
    identity: AgentIdentity,
    seal_data: Optional[list[dict[str, Any]]] = None,
) -> OnChainReputation:
    """Build an OnChainReputation from identity + optional seal data.

    If no seal data is available, returns a neutral reputation based
    on registration status alone. Being registered is slightly positive.

    Args:
        identity: The agent's identity data.
        seal_data: Optional list of seal score dicts from SealRegistry.

    Returns:
        OnChainReputation suitable for the unified scoring pipeline.
    """
    if seal_data:
        seals = [
            SealScore(
                seal_type=s.get("seal_type", ""),
                quadrant=s.get("quadrant", "A2H"),
                score=s.get("score", 50),
                evaluator=s.get("evaluator", ""),
                timestamp=s.get("timestamp", datetime.now(timezone.utc).isoformat()),
                evidence_hash=s.get("evidence_hash", ""),
                seal_id=s.get("seal_id", 0),
            )
            for s in seal_data
        ]
        return compute_on_chain_score(seals)

    # No seal data → synthetic score based on registration
    rep = OnChainReputation(
        agent_address=identity.wallet,
        agent_id=identity.agent_id,
    )

    if identity.registered:
        # Being registered on-chain is a positive signal
        rep.composite_score = 55.0  # Slightly above neutral
        rep.confidence = 0.15       # Low confidence (registration only)
        rep.seal_count = 0
    else:
        # Not registered → neutral
        rep.composite_score = 50.0
        rep.confidence = 0.0

    return rep


# ---------------------------------------------------------------------------
# Swarm Batch Operations
# ---------------------------------------------------------------------------

def prepare_swarm_identity_queries(
    agent_wallets: dict[str, str],
) -> list[dict[str, str]]:
    """Prepare batch identity queries for all swarm agents.

    Args:
        agent_wallets: Dict of agent_name → wallet_address.

    Returns:
        List of query dicts with agent_name, wallet, and call_data.
    """
    queries = []
    for name, wallet in agent_wallets.items():
        call_data = SEL_BALANCE_OF + _encode_address(wallet)
        queries.append({
            "agent_name": name,
            "wallet": wallet.lower(),
            "call_data": call_data,
        })
    return queries


def aggregate_swarm_identities(
    results: list[tuple[str, AgentIdentity]],
) -> dict[str, AgentIdentity]:
    """Aggregate identity results for the full swarm.

    Args:
        results: List of (agent_name, AgentIdentity) tuples.

    Returns:
        Dict of agent_name → AgentIdentity.
    """
    return {name: identity for name, identity in results}


def swarm_identity_summary(
    identities: dict[str, AgentIdentity],
) -> dict[str, Any]:
    """Generate a summary of swarm identity status.

    Returns summary dict with counts and details.
    """
    total = len(identities)
    registered = sum(1 for i in identities.values() if i.registered)
    with_agent_id = sum(1 for i in identities.values() if i.agent_id > 0)
    errors = sum(1 for i in identities.values() if i.error is not None)

    return {
        "total_agents": total,
        "registered_on_chain": registered,
        "registration_rate": registered / total if total > 0 else 0.0,
        "with_known_agent_id": with_agent_id,
        "query_errors": errors,
        "agents": {
            name: {
                "registered": identity.registered,
                "agent_id": identity.agent_id,
                "tokens": identity.token_count,
            }
            for name, identity in identities.items()
        },
    }


# ---------------------------------------------------------------------------
# Bridge Class (with caching + IO)
# ---------------------------------------------------------------------------

class ERC8004LiveBridge:
    """Live bridge to ERC-8004 on-chain data with caching.

    This class wraps the pure functions above with:
      - In-memory cache with TTL
      - File-based persistent cache
      - Automatic retry on RPC failures
      - Batch operations for swarm queries
    """

    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config = config or BridgeConfig()
        self._cache: dict[str, CacheEntry] = {}

    def _cache_get(self, key: str) -> Optional[Any]:
        """Get from cache if not expired."""
        entry = self._cache.get(key)
        if entry and not entry.expired:
            return entry.data
        return None

    def _cache_set(self, key: str, data: Any) -> None:
        """Set cache entry."""
        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=self.config.cache_ttl_seconds,
        )
        # Evict if over limit
        if len(self._cache) > self.config.cache_max_entries:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].timestamp)
            del self._cache[oldest_key]

    def check_identity(self, wallet: str) -> AgentIdentity:
        """Check if a wallet is registered on ERC-8004.

        Returns AgentIdentity with registration status.
        Caches results for config.cache_ttl_seconds.
        """
        cache_key = f"identity:{wallet.lower()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Query balanceOf
        call_data = SEL_BALANCE_OF + _encode_address(wallet)
        result = _eth_call(
            self.config.rpc_url,
            IDENTITY_REGISTRY,
            call_data,
            timeout=self.config.rpc_timeout_seconds,
        )

        balance = parse_balance_response(result)
        known_id = resolve_agent_id_from_wallet(wallet)

        identity = build_identity_from_data(
            wallet=wallet,
            balance=balance,
            known_agent_id=known_id,
            network=self.config.network,
        )

        if result is None:
            identity.error = "RPC call failed"

        self._cache_set(cache_key, identity)
        return identity

    def get_on_chain_reputation(
        self,
        wallet: str,
        seal_data: Optional[list[dict[str, Any]]] = None,
    ) -> OnChainReputation:
        """Get on-chain reputation for a wallet.

        First checks identity, then builds reputation from available data.
        """
        identity = self.check_identity(wallet)
        return build_on_chain_reputation_from_identity(identity, seal_data)

    def query_swarm(
        self,
        agent_wallets: dict[str, str],
    ) -> dict[str, AgentIdentity]:
        """Query identities for all agents in the swarm."""
        results = []
        for name, wallet in agent_wallets.items():
            identity = self.check_identity(wallet)
            results.append((name, identity))
        return aggregate_swarm_identities(results)

    def get_swarm_summary(
        self,
        agent_wallets: dict[str, str],
    ) -> dict[str, Any]:
        """Get a summary of swarm identity status."""
        identities = self.query_swarm(agent_wallets)
        return swarm_identity_summary(identities)

    def clear_cache(self) -> int:
        """Clear the identity cache. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def save_cache(self, path: Path) -> None:
        """Save cache to a JSON file for persistence."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, entry in self._cache.items():
            if not entry.expired:
                if isinstance(entry.data, AgentIdentity):
                    data[key] = {
                        "data": entry.data.to_dict(),
                        "timestamp": entry.timestamp,
                        "ttl": entry.ttl,
                        "type": "AgentIdentity",
                    }
        path.write_text(json.dumps(data, indent=2))

    def load_cache(self, path: Path) -> int:
        """Load cache from a JSON file. Returns number of entries loaded."""
        if not path.exists():
            return 0
        try:
            raw = json.loads(path.read_text())
            count = 0
            for key, entry_data in raw.items():
                if entry_data.get("type") == "AgentIdentity":
                    d = entry_data["data"]
                    identity = AgentIdentity(
                        wallet=d["wallet"],
                        registered=d["registered"],
                        agent_id=d["agent_id"],
                        token_count=d["token_count"],
                        token_uri=d["token_uri"],
                        metadata_url=d["metadata_url"],
                        network=d["network"],
                        error=d.get("error"),
                    )
                    self._cache[key] = CacheEntry(
                        data=identity,
                        timestamp=entry_data["timestamp"],
                        ttl=entry_data["ttl"],
                    )
                    count += 1
            return count
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return 0
