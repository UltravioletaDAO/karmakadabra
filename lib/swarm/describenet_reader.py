"""
describe-net Chain Reader — Read SealRegistry reputation from Base L2

Reads on-chain seal reputation from the describe-net SealRegistry contract
and converts it to the BridgedReputation format used by the reputation bridge.

This closes the evidence triangle:
    AutoJob (insights) ←→ EM (task history) ←→ describe-net (on-chain seals)

Architecture:
    ┌──────────────────────────┐
    │   describe-net Reader    │
    │   (this module)          │
    └────────────┬─────────────┘
                 │ eth_call (view functions)
    ┌────────────▼─────────────┐
    │   SealRegistry.sol       │
    │   (Base Mainnet)         │
    │   13 seal types × 4 quads│
    └──────────────────────────┘

Contract functions called:
    - compositeScore(address, bool, Quadrant) → (avg, active, total)
    - reputationByType(address, bytes32) → (avg, count)
    - timeWeightedScore(address, halfLife, bool, Quadrant) → (weighted, active)
    - totalSeals() → uint256
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional, Dict, List, Tuple


logger = logging.getLogger(__name__)


# ── Constants ──

# describe-net SealRegistry deployment
# Base Mainnet: Not yet deployed — set via DESCRIBENET_SEAL_REGISTRY env var when ready
# Base Sepolia (testnet): deployed via Monad testnet (see describe-net-contracts repo)
SEAL_REGISTRY_ADDRESS = os.environ.get(
    "DESCRIBENET_SEAL_REGISTRY",
    "0x0000000000000000000000000000000000000000",  # Placeholder until mainnet deploy
)

# Base RPC endpoints
BASE_MAINNET_RPC = "https://mainnet.base.org"
BASE_SEPOLIA_RPC = "https://sepolia.base.org"

# EVM function selectors (first 4 bytes of keccak256 of function signature)
# Verified via pycryptodome keccak256 computation (Feb 25, 2026)
SELECTORS = {
    # compositeScore(address,bool,uint8) → (uint256,uint256,uint256)
    "compositeScore": "128a1985",
    # reputationByType(address,bytes32) → (uint256,uint256)
    "reputationByType": "f51e4a82",
    # timeWeightedScore(address,uint256,bool,uint8) → (uint256,uint256)
    "timeWeightedScore": "673c5673",
    # totalSeals() → uint256
    "totalSeals": "d9ff054e",
    # getSubjectSeals(address) → uint256[]
    "getSubjectSeals": "cb8e44e1",
    # getSeal(uint256) → Seal
    "getSeal": "2c945c75",
}


class Quadrant(IntEnum):
    """SealRegistry quadrants (matches Solidity enum)."""

    H2H = 0  # Human to Human
    H2A = 1  # Human to Agent
    A2H = 2  # Agent to Human
    A2A = 3  # Agent to Agent


# Seal type hashes (keccak256 of type name)
def _keccak256(text: str) -> bytes:
    """Compute keccak256 hash (same as Solidity's keccak256)."""
    # Python's hashlib sha3_256 is the NIST SHA-3, not Ethereum's keccak256
    # For production, use pysha3 or web3.py. For now, we store precomputed values.
    # These are the actual keccak256 values from Solidity:
    raise NotImplementedError("Use SEAL_TYPE_HASHES instead")


# Pre-computed keccak256 hashes of seal type names
# Verified via pycryptodome keccak.new(digest_bits=256) on Feb 25, 2026
# These must match the Solidity contract's keccak256("SKILLFUL") etc.
SEAL_TYPE_HASHES = {
    "SKILLFUL": bytes.fromhex(
        "2b59625bf1c70ce0b0748af64d0663a0fbc490114b90652fd5cad97253a118c3"
    ),
    "RELIABLE": bytes.fromhex(
        "9977334e03f06fb00a398ef525cb94a37bebd15cb58d9c546a372b9b9bef277d"
    ),
    "THOROUGH": bytes.fromhex(
        "75b850ff1980c810bf47e3a7a5c14300b5f280d2c30dc33d679b8a22eb8a8f09"
    ),
    "ENGAGED": bytes.fromhex(
        "1c773b59cc2a31a7035eb6a5dde9f985e1767bf5af2663023e8eb6f4b1a50198"
    ),
    "HELPFUL": bytes.fromhex(
        "3f627fd8e1c60714e3c5a52c7ce1141560656c60dd8fe0bf6638bd52ee4d3dd0"
    ),
    "CURIOUS": bytes.fromhex(
        "24d11c4400d998406a337e977ad524cfbdd6759bb6a39ccf384205ba81c27e31"
    ),
    "FAIR": bytes.fromhex(
        "0053ea2dc4b7dbdadfce0e9ae827a7300872b8194f54ad6fa1bed272d8aea726"
    ),
    "ACCURATE": bytes.fromhex(
        "efa5454e441ab80ed3716aae139f48dc461ae5e8ff52ed8dbacb43a57aa81d8a"
    ),
    "RESPONSIVE": bytes.fromhex(
        "f0f4e083fe075a1104503f0e58bbba9c6146479f2d5f909112fd19d3e7120de8"
    ),
    "ETHICAL": bytes.fromhex(
        "ed4226489ecbaaf7a380d1cdadeac7e159062273f5f2f2cf0de1c3c4246c41e3"
    ),
    "CREATIVE": bytes.fromhex(
        "a5181ad8d41a4b9860ed1a7bf3aa6c5db2c06d4132ca94f900fc3340d8bd81bf"
    ),
    "PROFESSIONAL": bytes.fromhex(
        "87d60cd54fcc80ebf1c7463cbd8d67a09ac7cc464ce823e1058ee954208951b0"
    ),
    "FRIENDLY": bytes.fromhex(
        "b2a744d783fc58fdd58bd87840dc47a203ce2de0042b2a061a39340656cdce86"
    ),
}

# Quadrant groupings for analysis
QUADRANT_LABELS = {
    Quadrant.H2H: "Human→Human",
    Quadrant.H2A: "Human→Agent",
    Quadrant.A2H: "Agent→Human",
    Quadrant.A2A: "Agent→Agent",
}


@dataclass
class SealScore:
    """Score for a specific seal type."""

    seal_type: str
    average_score: float  # 0-100
    count: int
    quadrant: Optional[str] = None


@dataclass
class DescribeNetReputation:
    """Complete describe-net reputation profile for a wallet."""

    wallet: str

    # Composite scores
    overall_score: float = 0.0
    overall_active_seals: int = 0
    overall_total_seals: int = 0

    # Time-weighted score (more recent seals count more)
    time_weighted_score: float = 0.0

    # Per-quadrant breakdown
    h2h_score: float = 0.0  # How humans rate this human
    h2a_score: float = 0.0  # How humans rate this agent
    a2h_score: float = 0.0  # How agents rate this human
    a2a_score: float = 0.0  # How agents rate this agent

    h2h_count: int = 0
    h2a_count: int = 0
    a2h_count: int = 0
    a2a_count: int = 0

    # Per-type breakdown (top 5)
    top_seal_types: List[SealScore] = field(default_factory=list)

    # Metadata
    read_at: Optional[datetime] = None
    block_number: Optional[int] = None
    network: str = "base"

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("read_at"):
            d["read_at"] = d["read_at"].isoformat()
        return d

    @property
    def total_seals(self) -> int:
        return self.h2h_count + self.h2a_count + self.a2h_count + self.a2a_count

    @property
    def is_agent(self) -> bool:
        """Likely an agent if most seals are in H2A or A2A quadrants."""
        agent_seals = self.h2a_count + self.a2a_count
        human_seals = self.h2h_count + self.a2h_count
        return agent_seals > human_seals

    @property
    def trust_level(self) -> str:
        """Determine trust level from seal data."""
        if self.overall_active_seals >= 20 and self.overall_score >= 80:
            return "high"
        elif self.overall_active_seals >= 5 and self.overall_score >= 60:
            return "medium"
        elif self.overall_active_seals >= 1:
            return "low"
        else:
            return "none"


class DescribeNetReader:
    """
    Reads describe-net SealRegistry reputation from Base L2.

    Uses raw eth_call RPC (no web3.py dependency) for maximum portability.
    All calls are read-only view functions (no gas, no wallet needed).

    Usage:
        reader = DescribeNetReader(network="base")
        rep = await reader.get_reputation("0x1234...")
        print(f"Score: {rep.overall_score}, Seals: {rep.overall_active_seals}")
    """

    # Half-life for time-weighted scores: 90 days in seconds
    DEFAULT_HALF_LIFE = 90 * 24 * 3600  # 7,776,000 seconds

    def __init__(
        self,
        network: str = "base",
        rpc_url: Optional[str] = None,
        registry_address: Optional[str] = None,
    ):
        self.network = network
        self.rpc_url = rpc_url or (
            BASE_MAINNET_RPC if network == "base" else BASE_SEPOLIA_RPC
        )
        self.registry_address = registry_address or SEAL_REGISTRY_ADDRESS

        # Cache
        self._cache: Dict[str, DescribeNetReputation] = {}
        self._cache_ttl = 300  # 5 minutes

    async def get_reputation(
        self,
        wallet: str,
        include_breakdown: bool = True,
        half_life_seconds: int = None,
    ) -> DescribeNetReputation:
        """
        Get complete describe-net reputation for a wallet.

        Makes multiple eth_call requests:
        1. compositeScore (overall, no quadrant filter)
        2. compositeScore per quadrant (4 calls)
        3. timeWeightedScore (overall)
        4. Optionally: reputationByType for top seal types

        Args:
            wallet: Ethereum address
            include_breakdown: Include per-type breakdown
            half_life_seconds: Custom half-life for time weighting

        Returns:
            DescribeNetReputation with all scores
        """
        wallet = wallet.lower()
        half_life = half_life_seconds or self.DEFAULT_HALF_LIFE

        # Check cache
        if wallet in self._cache:
            cached = self._cache[wallet]
            if cached.read_at:
                age = (datetime.now(timezone.utc) - cached.read_at).total_seconds()
                if age < self._cache_ttl:
                    return cached

        rep = DescribeNetReputation(wallet=wallet, network=self.network)

        if self.registry_address == SEAL_REGISTRY_ADDRESS:
            # Contract not yet deployed — return empty reputation
            logger.debug(
                f"SealRegistry not deployed, returning empty reputation for {wallet}"
            )
            rep.read_at = datetime.now(timezone.utc)
            self._cache[wallet] = rep
            return rep

        try:
            # 1. Overall composite score
            overall = await self._call_composite_score(wallet, filter_quadrant=False)
            if overall:
                rep.overall_score = overall[0]
                rep.overall_active_seals = overall[1]
                rep.overall_total_seals = overall[2]

            # 2. Per-quadrant scores
            for quad in Quadrant:
                result = await self._call_composite_score(
                    wallet, filter_quadrant=True, quadrant=quad
                )
                if result:
                    score, count, _ = result
                    if quad == Quadrant.H2H:
                        rep.h2h_score, rep.h2h_count = score, count
                    elif quad == Quadrant.H2A:
                        rep.h2a_score, rep.h2a_count = score, count
                    elif quad == Quadrant.A2H:
                        rep.a2h_score, rep.a2h_count = score, count
                    elif quad == Quadrant.A2A:
                        rep.a2a_score, rep.a2a_count = score, count

            # 3. Time-weighted score
            tw = await self._call_time_weighted_score(wallet, half_life)
            if tw:
                rep.time_weighted_score = tw[0]

            # 4. Per-type breakdown (optional)
            if include_breakdown:
                type_scores = []
                for type_name, type_hash in SEAL_TYPE_HASHES.items():
                    result = await self._call_reputation_by_type(wallet, type_hash)
                    if result and result[1] > 0:  # count > 0
                        type_scores.append(
                            SealScore(
                                seal_type=type_name,
                                average_score=result[0],
                                count=result[1],
                            )
                        )
                # Sort by count (most seals first), take top 5
                type_scores.sort(key=lambda s: -s.count)
                rep.top_seal_types = type_scores[:5]

            rep.read_at = datetime.now(timezone.utc)
            self._cache[wallet] = rep

        except Exception as e:
            logger.error(f"Failed to read describe-net reputation for {wallet}: {e}")
            rep.read_at = datetime.now(timezone.utc)

        return rep

    def to_bridged_format(self, rep: DescribeNetReputation) -> dict:
        """
        Convert describe-net reputation to the format expected by ReputationBridge.

        Returns dict compatible with _read_chain_reputation() return value.
        """
        # The reputation bridge expects:
        # {
        #     "agent_id": optional int (ERC-8004 token ID),
        #     "score": float (0-100),
        #     "total_ratings": int,
        #     "as_worker_avg": float,
        #     "as_requester_avg": float,
        # }

        # Map quadrants to worker/requester roles:
        # Worker reputation = H2A (humans rating this agent) + A2A (agents rating this agent)
        # Requester reputation = A2H (this agent's ratings as requester)
        worker_count = rep.h2a_count + rep.a2a_count

        worker_avg = 0.0
        if worker_count > 0:
            # Weighted average of H2A and A2A scores
            total_weighted = (
                rep.h2a_score * rep.h2a_count + rep.a2a_score * rep.a2a_count
            )
            worker_avg = total_weighted / worker_count

        requester_avg = rep.a2h_score if rep.a2h_count > 0 else 0.0

        return {
            "score": rep.time_weighted_score or rep.overall_score,
            "total_ratings": rep.overall_active_seals,
            "as_worker_avg": worker_avg,
            "as_requester_avg": requester_avg,
            "source": "describe_net",
            "quadrant_breakdown": {
                "h2h": {"score": rep.h2h_score, "count": rep.h2h_count},
                "h2a": {"score": rep.h2a_score, "count": rep.h2a_count},
                "a2h": {"score": rep.a2h_score, "count": rep.a2h_count},
                "a2a": {"score": rep.a2a_score, "count": rep.a2a_count},
            },
            "top_seal_types": [
                {"type": s.seal_type, "score": s.average_score, "count": s.count}
                for s in rep.top_seal_types
            ],
        }

    def evidence_weight_from_seals(self, rep: DescribeNetReputation) -> float:
        """
        Calculate AutoJob evidence weight from describe-net seals.

        Evidence weight hierarchy:
        - 0 seals: 0.3 (self-reported)
        - 1-4 seals: 0.7 (some on-chain evidence)
        - 5-19 seals: 0.8 (established on-chain)
        - 20+ seals: 0.85 (strong on-chain)
        - 20+ seals + multi-quadrant: 0.90 (cross-validated)
        - 50+ seals + multi-quadrant: 0.95 (comprehensive)
        """
        n = rep.overall_active_seals

        if n == 0:
            return 0.3

        # Base weight from seal count
        if n >= 50:
            base = 0.90
        elif n >= 20:
            base = 0.85
        elif n >= 5:
            base = 0.80
        else:
            base = 0.70

        # Multi-quadrant bonus (cross-validation from different perspectives)
        quadrants_with_data = sum(
            1
            for c in [rep.h2h_count, rep.h2a_count, rep.a2h_count, rep.a2a_count]
            if c > 0
        )

        if quadrants_with_data >= 3:
            base += 0.05
        elif quadrants_with_data >= 2:
            base += 0.02

        return min(0.98, round(base, 3))

    # ── RPC Call Builders ──

    async def _call_composite_score(
        self,
        wallet: str,
        filter_quadrant: bool = False,
        quadrant: Quadrant = Quadrant.H2H,
    ) -> Optional[Tuple[float, int, int]]:
        """
        Call compositeScore(address, bool, uint8).

        Returns (averageScore, activeCount, totalCount) or None.
        """
        # ABI encode: address(32) + bool(32) + uint8(32)
        addr = wallet.lower().replace("0x", "").zfill(64)
        filt = "0" * 63 + ("1" if filter_quadrant else "0")
        quad = "0" * 63 + str(int(quadrant))

        # Function selector: compositeScore(address,bool,uint8)
        selector = self._selector("compositeScore(address,bool,uint8)")
        data = f"0x{selector}{addr}{filt}{quad}"

        result = await self._eth_call(data)
        if result and len(result) >= 194:  # "0x" + 3 * 64 hex chars
            hex_data = result[2:]
            avg_score = int(hex_data[0:64], 16)
            active_count = int(hex_data[64:128], 16)
            total_count = int(hex_data[128:192], 16)
            return (float(avg_score), active_count, total_count)
        return None

    async def _call_reputation_by_type(
        self,
        wallet: str,
        seal_type_hash: bytes,
    ) -> Optional[Tuple[float, int]]:
        """
        Call reputationByType(address, bytes32).

        Returns (averageScore, count) or None.
        """
        addr = wallet.lower().replace("0x", "").zfill(64)
        type_hex = seal_type_hash.hex().zfill(64)

        selector = self._selector("reputationByType(address,bytes32)")
        data = f"0x{selector}{addr}{type_hex}"

        result = await self._eth_call(data)
        if result and len(result) >= 130:  # "0x" + 2 * 64
            hex_data = result[2:]
            avg_score = int(hex_data[0:64], 16)
            count = int(hex_data[64:128], 16)
            return (float(avg_score), count)
        return None

    async def _call_time_weighted_score(
        self,
        wallet: str,
        half_life_seconds: int,
        filter_quadrant: bool = False,
        quadrant: Quadrant = Quadrant.H2H,
    ) -> Optional[Tuple[float, int]]:
        """
        Call timeWeightedScore(address, uint256, bool, uint8).

        Returns (weightedScore, activeCount) or None.
        """
        addr = wallet.lower().replace("0x", "").zfill(64)
        half_life = hex(half_life_seconds)[2:].zfill(64)
        filt = "0" * 63 + ("1" if filter_quadrant else "0")
        quad = "0" * 63 + str(int(quadrant))

        selector = self._selector("timeWeightedScore(address,uint256,bool,uint8)")
        data = f"0x{selector}{addr}{half_life}{filt}{quad}"

        result = await self._eth_call(data)
        if result and len(result) >= 130:
            hex_data = result[2:]
            weighted = int(hex_data[0:64], 16)
            active = int(hex_data[64:128], 16)
            return (float(weighted), active)
        return None

    async def _eth_call(self, data: str) -> Optional[str]:
        """
        Make an eth_call to the SealRegistry.

        Uses urllib (no dependencies) for the JSON-RPC call.
        """
        import urllib.request
        import urllib.error

        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {
                        "to": self.registry_address,
                        "data": data,
                    },
                    "latest",
                ],
                "id": 1,
            }
        ).encode()

        try:
            req = urllib.request.Request(
                self.rpc_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())

            if "result" in result and result["result"] != "0x":
                return result["result"]
            return None

        except Exception as e:
            logger.warning(f"eth_call failed: {e}")
            return None

    @staticmethod
    def _selector(signature: str) -> str:
        """
        Compute 4-byte function selector from signature.

        Uses a simple approach: take first 4 bytes of keccak256.
        Since Python's hashlib doesn't have keccak256, we use a
        lookup table for known selectors.
        """
        # Pre-computed keccak256 selectors — verified via pycryptodome (Feb 25, 2026)
        known_selectors = {
            "compositeScore(address,bool,uint8)": "128a1985",
            "reputationByType(address,bytes32)": "f51e4a82",
            "timeWeightedScore(address,uint256,bool,uint8)": "673c5673",
            "totalSeals()": "d9ff054e",
            "getSubjectSeals(address)": "cb8e44e1",
            "getSeal(uint256)": "2c945c75",
            "ownerOf(uint256)": "6352211e",
            "balanceOf(address)": "70a08231",
            "tokenURI(uint256)": "c87b56dd",
        }

        if signature in known_selectors:
            return known_selectors[signature]

        # Fallback: try pysha3 if available
        try:
            import sha3

            return sha3.keccak_256(signature.encode()).hexdigest()[:8]
        except ImportError:
            pass

        # Last resort: try pycryptodome
        try:
            from Crypto.Hash import keccak

            k = keccak.new(digest_bits=256)
            k.update(signature.encode())
            return k.hexdigest()[:8]
        except ImportError:
            pass

        raise RuntimeError(
            f"Cannot compute keccak256 for '{signature}'. "
            "Install pysha3 or pycryptodome, or add selector to known_selectors."
        )


# ── Integration with ReputationBridge ──


async def read_describenet_for_bridge(
    wallet: str,
    reader: Optional[DescribeNetReader] = None,
) -> Optional[dict]:
    """
    Convenience function: read describe-net reputation in bridge format.

    Used by reputation_bridge.py's _read_chain_reputation() method.

    Args:
        wallet: Ethereum address
        reader: Optional pre-configured reader

    Returns:
        Dict in bridge-compatible format, or None if no data
    """
    from config.platform_config import PlatformConfig

    if not await PlatformConfig.is_feature_enabled("describenet"):
        return None

    reader = reader or DescribeNetReader()
    rep = await reader.get_reputation(wallet)

    if rep.overall_active_seals == 0:
        return None

    return reader.to_bridged_format(rep)
