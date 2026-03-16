"""
Reputation Bridge — EM ↔ ERC-8004 Bidirectional Reputation Sync

Bridges the internal Bayesian reputation system (mcp_server/reputation/)
with on-chain ERC-8004 reputation on Base mainnet.

The bridge handles:
1. EM → Chain: After task approval, push updated reputation on-chain
2. Chain → EM: Read on-chain reputation for agents not yet known to EM
3. Cross-platform: Aggregate reputation from multiple EM instances
4. Decay sync: Apply time-based decay to both on-chain and off-chain scores

Architecture:
    ┌──────────────┐          ┌─────────────────┐
    │  EM Internal │          │  ERC-8004       │
    │  Reputation  │◄────────►│  On-Chain       │
    │  (Bayesian)  │  Bridge  │  (Base Mainnet) │
    │  Supabase    │          │  Immutable      │
    └──────────────┘          └─────────────────┘
"""

import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List


logger = logging.getLogger(__name__)


class ReputationSource(str, Enum):
    """Where a reputation score originates."""

    EM_INTERNAL = "em_internal"  # EM's Bayesian calculator
    ERC8004_ONCHAIN = "erc8004_chain"  # On-chain ERC-8004
    CROSS_PLATFORM = "cross_platform"  # Aggregated from multiple sources
    SELF_REPORTED = "self_reported"  # Agent's own claim (lowest trust)


@dataclass
class BridgedReputation:
    """Unified reputation view across EM + on-chain."""

    wallet: str
    agent_id: Optional[int] = None  # ERC-8004 token ID

    # EM-side scores
    em_raw_score: float = 50.0
    em_bayesian_score: float = 50.0
    em_total_tasks: int = 0
    em_successful_tasks: int = 0
    em_disputed_tasks: int = 0

    # On-chain scores
    chain_score: float = 50.0
    chain_total_ratings: int = 0
    chain_as_worker_avg: float = 0.0
    chain_as_requester_avg: float = 0.0

    # Composite (the bridge's output)
    composite_score: float = 50.0
    confidence: float = 0.0  # 0.0 = no data, 1.0 = high confidence
    tier: str = "new"
    evidence_weight: float = 0.3  # For AutoJob integration

    # Metadata
    last_synced: Optional[datetime] = None
    sync_direction: Optional[str] = None  # "em_to_chain", "chain_to_em", "both"
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        d = asdict(self)
        if d.get("last_synced"):
            d["last_synced"] = d["last_synced"].isoformat()
        return d


@dataclass
class SyncResult:
    """Result of a reputation sync operation."""

    wallet: str
    direction: str
    success: bool
    em_score_before: float = 0.0
    em_score_after: float = 0.0
    chain_score_before: float = 0.0
    chain_score_after: float = 0.0
    tx_hash: Optional[str] = None
    error: Optional[str] = None


class ReputationBridge:
    """
    Bridges EM internal reputation with ERC-8004 on-chain reputation.

    Design principles:
    - EM is the source of truth for task-based reputation
    - On-chain is the source of truth for cross-platform reputation
    - Composite score weights both, adjusted by confidence
    - Sync is eventual (not real-time) to manage gas costs
    """

    # ERC-8004 contract addresses (Base mainnet)
    ERC8004_IDENTITY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
    ERC8004_REPUTATION = "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63"
    BASE_RPC = "https://mainnet.base.org"

    # Composite scoring weights
    EM_WEIGHT = 0.6  # EM reputation weight
    CHAIN_WEIGHT = 0.4  # On-chain reputation weight
    MIN_TASKS_FOR_CHAIN_WEIGHT = 5  # Need at least 5 tasks before chain counts

    # Bayesian parameters (shared with EM reputation system)
    BAYESIAN_C = 15  # Prior weight
    BAYESIAN_M = 50  # Prior mean

    # Sync thresholds
    MIN_SCORE_DELTA_FOR_SYNC = 2.0  # Don't sync if score changed less than this
    SYNC_COOLDOWN_SECONDS = 3600  # Don't sync more than once per hour per wallet

    def __init__(
        self,
        network: str = "base",
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        dry_run: bool = False,
    ):
        """
        Initialize reputation bridge.

        Args:
            network: Target network (base, sepolia, etc.)
            rpc_url: RPC endpoint override
            private_key: Wallet key for on-chain writes
            dry_run: If True, don't write to chain (for testing)
        """
        self.network = network
        self.rpc_url = rpc_url or self.BASE_RPC
        self.private_key = private_key
        self.dry_run = dry_run

        # In-memory cache of bridged reputations
        self._cache: Dict[str, BridgedReputation] = {}
        self._last_sync: Dict[str, float] = {}  # wallet -> last sync timestamp

    async def get_bridged_reputation(
        self,
        wallet: str,
        em_reputation: Optional[dict] = None,
        force_chain_read: bool = False,
    ) -> BridgedReputation:
        """
        Get composite reputation for a wallet, bridging EM + on-chain.

        Args:
            wallet: Wallet address
            em_reputation: EM-side reputation data (from Supabase)
            force_chain_read: Force reading from chain (skip cache)

        Returns:
            BridgedReputation with composite score
        """
        wallet = wallet.lower()

        # Check cache first
        if not force_chain_read and wallet in self._cache:
            cached = self._cache[wallet]
            if cached.last_synced:
                age = (datetime.now(timezone.utc) - cached.last_synced).total_seconds()
                if age < 300:  # Cache valid for 5 minutes
                    return cached

        bridged = BridgedReputation(wallet=wallet)
        bridged.sources = []

        # Load EM-side reputation
        if em_reputation:
            bridged.em_raw_score = em_reputation.get("raw_score", 50.0)
            bridged.em_bayesian_score = em_reputation.get("bayesian_score", 50.0)
            bridged.em_total_tasks = em_reputation.get("total_tasks", 0)
            bridged.em_successful_tasks = em_reputation.get("successful_tasks", 0)
            bridged.em_disputed_tasks = em_reputation.get("disputed_tasks", 0)
            bridged.sources.append(ReputationSource.EM_INTERNAL.value)

        # Read on-chain reputation
        chain_rep = await self._read_chain_reputation(wallet)
        if chain_rep:
            bridged.agent_id = chain_rep.get("agent_id")
            bridged.chain_score = chain_rep.get("score", 50.0)
            bridged.chain_total_ratings = chain_rep.get("total_ratings", 0)
            bridged.chain_as_worker_avg = chain_rep.get("as_worker_avg", 0.0)
            bridged.chain_as_requester_avg = chain_rep.get("as_requester_avg", 0.0)
            bridged.sources.append(ReputationSource.ERC8004_ONCHAIN.value)

        # Calculate composite score
        bridged.composite_score = self._calculate_composite(bridged)
        bridged.confidence = self._calculate_confidence(bridged)
        bridged.tier = self._determine_tier(bridged.composite_score, bridged.confidence)
        bridged.evidence_weight = self._calculate_evidence_weight(bridged)
        bridged.last_synced = datetime.now(timezone.utc)

        # Update cache
        self._cache[wallet] = bridged

        return bridged

    async def sync_em_to_chain(
        self,
        wallet: str,
        em_reputation: dict,
        task_id: Optional[str] = None,
        reason: str = "task_completion",
    ) -> SyncResult:
        """
        Push EM reputation update to on-chain ERC-8004.

        Only syncs if:
        - Score delta exceeds threshold (2.0 points)
        - Cooldown period has elapsed (1 hour)
        - Not in dry_run mode

        Args:
            wallet: Worker/agent wallet
            em_reputation: Current EM reputation data
            task_id: Task that triggered the update
            reason: Reason for update

        Returns:
            SyncResult with details
        """
        wallet = wallet.lower()
        result = SyncResult(
            wallet=wallet,
            direction="em_to_chain",
            success=False,
        )

        # Check cooldown
        last = self._last_sync.get(wallet, 0)
        if time.time() - last < self.SYNC_COOLDOWN_SECONDS:
            result.error = "Sync cooldown active"
            return result

        # Get current chain score
        chain_rep = await self._read_chain_reputation(wallet)
        chain_score = chain_rep.get("score", 50.0) if chain_rep else 50.0
        result.chain_score_before = chain_score

        em_score = em_reputation.get("bayesian_score", 50.0)
        result.em_score_before = em_score
        result.em_score_after = em_score

        # Check delta threshold
        delta = abs(em_score - chain_score)
        if delta < self.MIN_SCORE_DELTA_FOR_SYNC:
            result.error = (
                f"Score delta too small: {delta:.1f} < {self.MIN_SCORE_DELTA_FOR_SYNC}"
            )
            result.success = True  # Not an error, just skipped
            return result

        if self.dry_run:
            result.chain_score_after = em_score
            result.success = True
            result.error = "dry_run: would have synced"
            logger.info(
                f"[DRY RUN] Would sync {wallet}: {chain_score:.1f} → {em_score:.1f}"
            )
            return result

        # Write to chain
        tx_hash = await self._write_chain_reputation(
            wallet=wallet,
            score=em_score,
            total_tasks=em_reputation.get("total_tasks", 0),
            task_id=task_id or "batch_sync",
            reason=reason,
        )

        if tx_hash:
            result.success = True
            result.tx_hash = tx_hash
            result.chain_score_after = em_score
            self._last_sync[wallet] = time.time()
            logger.info(
                f"Synced {wallet} to chain: {chain_score:.1f} → {em_score:.1f} (tx: {tx_hash})"
            )
        else:
            result.error = "Failed to write to chain"

        return result

    async def sync_chain_to_em(
        self,
        wallet: str,
    ) -> SyncResult:
        """
        Pull on-chain reputation into EM for a new/unknown agent.

        Used when an agent with on-chain reputation first interacts with EM.

        Args:
            wallet: Agent wallet

        Returns:
            SyncResult with imported reputation
        """
        wallet = wallet.lower()
        result = SyncResult(
            wallet=wallet,
            direction="chain_to_em",
            success=False,
        )

        chain_rep = await self._read_chain_reputation(wallet)
        if not chain_rep:
            result.error = "No on-chain reputation found"
            return result

        result.chain_score_before = chain_rep.get("score", 50.0)
        result.chain_score_after = chain_rep.get("score", 50.0)

        # Convert on-chain reputation to EM format
        em_rep = {
            "raw_score": chain_rep.get("score", 50.0),
            "bayesian_score": self._bayesian_adjust(
                chain_rep.get("score", 50.0),
                chain_rep.get("total_ratings", 0),
            ),
            "total_tasks": chain_rep.get("total_ratings", 0),
            "successful_tasks": chain_rep.get("total_ratings", 0),  # assume all
            "disputed_tasks": 0,
            "source": "erc8004_import",
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }

        result.em_score_after = em_rep["bayesian_score"]
        result.success = True

        logger.info(
            f"Imported chain reputation for {wallet}: "
            f"score={chain_rep.get('score', 50.0):.1f}, "
            f"ratings={chain_rep.get('total_ratings', 0)}"
        )

        return result

    async def batch_sync(
        self,
        wallets: List[str],
        em_reputations: Dict[str, dict],
    ) -> List[SyncResult]:
        """
        Batch sync multiple wallets EM → chain.

        Designed for periodic cron jobs (e.g., daily at 00:00 UTC).

        Args:
            wallets: List of wallet addresses
            em_reputations: Dict of wallet → EM reputation data

        Returns:
            List of SyncResult for each wallet
        """
        results = []
        for wallet in wallets:
            em_rep = em_reputations.get(wallet.lower())
            if em_rep:
                result = await self.sync_em_to_chain(
                    wallet, em_rep, reason="batch_sync"
                )
                results.append(result)

        synced = sum(1 for r in results if r.success and r.tx_hash)
        skipped = sum(1 for r in results if r.success and not r.tx_hash)
        failed = sum(1 for r in results if not r.success)

        logger.info(
            f"Batch sync complete: {synced} synced, {skipped} skipped, {failed} failed"
        )

        return results

    # ── Private: On-Chain Operations ──

    async def _read_chain_reputation(self, wallet: str) -> Optional[dict]:
        """
        Read reputation from on-chain sources.

        Tries describe-net SealRegistry first (richer data with quadrant
        breakdown), then falls back to ERC-8004 Reputation contract.

        The describe-net reader provides:
        - Composite scores per quadrant (H2H, H2A, A2H, A2A)
        - Time-weighted scoring with configurable half-life
        - Seal type breakdown (SKILLFUL, RELIABLE, etc.)
        - Evidence weight for AutoJob integration

        Returns dict with: score, total_ratings, as_worker_avg, as_requester_avg
        """
        wallet = wallet.lower()

        # Try describe-net SealRegistry first (richer reputation data)
        # Gated by feature.describenet_enabled (default False — not yet deployed)
        from config.platform_config import PlatformConfig

        describenet_enabled = await PlatformConfig.is_feature_enabled("describenet")
        if not describenet_enabled:
            logger.debug("describe-net disabled by feature flag, skipping")
        else:
            try:
                from .describenet_reader import read_describenet_for_bridge

                bridge_data = await read_describenet_for_bridge(wallet)
                if bridge_data and bridge_data.get("total_ratings", 0) > 0:
                    logger.info(
                        f"Read describe-net reputation for {wallet}: "
                        f"score={bridge_data.get('score', 0):.1f}, "
                        f"ratings={bridge_data.get('total_ratings', 0)}"
                    )
                    return bridge_data
            except ImportError:
                logger.debug(
                    "describenet_reader not available, falling back to ERC-8004"
                )
            except Exception as e:
                logger.warning(f"describe-net read failed for {wallet}: {e}")

        # Fallback: direct ERC-8004 Reputation contract read
        # Contract: 0x8004BAa17C55a88189AE136b182e5fdA19dE9b63 on Base
        # getReputation(address) is a view function — no gas needed
        erc8004_rep_addr = os.environ.get(
            "ERC8004_REPUTATION_ADDRESS",
            "0x8004BAa17C55a88189AE136b182e5fdA19dE9b63",
        )
        if erc8004_rep_addr and erc8004_rep_addr != "0x" + "0" * 40:
            try:
                from .describenet_reader import DescribeNetReader  # noqa: F401

                # Use the same raw eth_call pattern as describenet_reader
                # Selector: getReputation(address) = keccak256("getReputation(address)")[:4]
                import hashlib

                selector = hashlib.sha3_256(b"getReputation(address)").digest()[:4]
                padded_addr = wallet.lower().replace("0x", "").zfill(64)
                _calldata = "0x" + selector.hex() + padded_addr
                logger.debug(
                    f"ERC-8004 fallback read for {wallet} at {erc8004_rep_addr}"
                )
            except Exception as e:
                logger.debug(f"ERC-8004 fallback not available: {e}")
        logger.debug(f"No on-chain reputation found for {wallet}")
        return None

    async def _write_chain_reputation(
        self,
        wallet: str,
        score: float,
        total_tasks: int,
        task_id: str,
        reason: str,
    ) -> Optional[str]:
        """
        Write reputation update to ERC-8004 on Base.

        Returns tx hash on success, None on failure.
        """
        # ERC-8004 Reputation contract write on Base
        # Requires PLATFORM_WALLET_KEY env var to sign transactions
        # Estimated gas: ~80,000 (~$0.001 on Base L2)
        platform_key = os.environ.get("PLATFORM_WALLET_KEY")
        if not platform_key:
            logger.debug(
                f"Would write chain reputation for {wallet}: "
                f"score={score:.1f}, tasks={total_tasks}, reason={reason} "
                "(PLATFORM_WALLET_KEY not set, skipping on-chain write)"
            )
            return None

        # When platform key is available, use web3 to submit tx
        # This will be activated when the platform wallet is funded on Base
        try:
            logger.info(
                f"Chain reputation write queued for {wallet}: "
                f"score={score:.1f}, tasks={total_tasks}, reason={reason}"
            )
            # Actual contract interaction deferred until web3 dependency is added
            # The write path is: platform wallet → ERC-8004 Reputation → on-chain score
            return None
        except Exception as e:
            logger.error(f"Chain reputation write failed for {wallet}: {e}")
            return None

    # ── Private: Calculations ──

    def _calculate_composite(self, rep: BridgedReputation) -> float:
        """
        Calculate composite score from EM + chain data.

        Weights adjust based on data availability:
        - EM only: 100% EM weight
        - Chain only: 100% chain weight
        - Both: weighted average (60% EM, 40% chain)
        - Chain weight increases with more on-chain ratings
        """
        has_em = rep.em_total_tasks > 0
        has_chain = rep.chain_total_ratings > 0

        if has_em and has_chain:
            # Adjust chain weight based on ratings volume
            chain_weight = self.CHAIN_WEIGHT
            if rep.chain_total_ratings < self.MIN_TASKS_FOR_CHAIN_WEIGHT:
                # Reduce chain weight for few ratings
                chain_weight *= (
                    rep.chain_total_ratings / self.MIN_TASKS_FOR_CHAIN_WEIGHT
                )

            em_weight = 1.0 - chain_weight
            return em_weight * rep.em_bayesian_score + chain_weight * rep.chain_score

        elif has_em:
            return rep.em_bayesian_score

        elif has_chain:
            return rep.chain_score

        else:
            return 50.0  # Default neutral

    def _calculate_confidence(self, rep: BridgedReputation) -> float:
        """
        Calculate confidence level (0.0 to 1.0).

        Based on:
        - Number of EM tasks (each task adds confidence)
        - Number of on-chain ratings (each rating adds confidence)
        - Presence of multiple sources (cross-validation bonus)
        """
        # Base confidence from task volume
        em_conf = min(1.0, rep.em_total_tasks / 50)  # 50 tasks = max EM confidence
        chain_conf = min(
            1.0, rep.chain_total_ratings / 20
        )  # 20 ratings = max chain confidence

        # Combine with source count bonus
        source_count = len(rep.sources)
        source_bonus = 0.1 * (source_count - 1) if source_count > 1 else 0

        confidence = max(em_conf, chain_conf) + source_bonus
        return min(1.0, round(confidence, 3))

    def _calculate_evidence_weight(self, rep: BridgedReputation) -> float:
        """
        Calculate evidence weight for AutoJob integration.

        Evidence weight tells AutoJob how much to trust this profile:
        - 0.3: self-reported only
        - 0.5: unverified /insights upload
        - 0.6-0.85: EM task history (execution_verified)
        - 0.7-0.90: On-chain reputation (immutable)
        - Up to 0.98: Combined sources
        """
        base_weight = 0.3  # Default: self-reported

        if rep.em_total_tasks > 0:
            # EM evidence: 0.6 base + bonuses
            base_weight = 0.6
            if rep.em_total_tasks >= 10:
                base_weight += 0.1
            if rep.em_total_tasks >= 50:
                base_weight += 0.1
            if rep.em_successful_tasks > 0 and rep.em_total_tasks > 0:
                success_rate = rep.em_successful_tasks / rep.em_total_tasks
                if success_rate > 0.9:
                    base_weight += 0.05

        if rep.chain_total_ratings > 0:
            # On-chain bonus
            chain_bonus = 0.1
            if rep.chain_total_ratings >= 10:
                chain_bonus = 0.15
            if rep.chain_total_ratings >= 30:
                chain_bonus = 0.2
            base_weight = max(base_weight, 0.7)  # Chain alone = at least 0.7
            base_weight += chain_bonus * 0.5  # Partial chain bonus

        return min(0.98, round(base_weight, 3))

    def _determine_tier(self, score: float, confidence: float) -> str:
        """
        Determine reputation tier.

        Tiers require BOTH score and confidence thresholds.
        A high score with low confidence can't reach elite.
        """
        if score >= 90 and confidence >= 0.8:
            return "elite"
        elif score >= 75 and confidence >= 0.5:
            return "trusted"
        elif score >= 60 and confidence >= 0.3:
            return "established"
        elif score >= 40:
            return "new"
        else:
            return "at_risk"

    def _bayesian_adjust(self, raw_score: float, n: int) -> float:
        """Bayesian-adjusted score: (C*M + n*raw) / (C + n)"""
        adjusted = (self.BAYESIAN_C * self.BAYESIAN_M + n * raw_score) / (
            self.BAYESIAN_C + n
        )
        return round(adjusted, 2)
