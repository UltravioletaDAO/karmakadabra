"""
Karma Kadabra V2 — Seal Issuer

EIP-712 signing and batch submission for describe-net SealRegistry.
This is the WRITE PATH for on-chain reputation — closing the flywheel loop.

Data flow:
  1. Agent completes EM task → receives evidence + rating
  2. SealIssuer maps task outcome to seal types + scores
  3. Signs seal data off-chain using EIP-712 (gasless for agents)
  4. Batches multiple seals into a single submission
  5. Relayer submits to SealRegistry on Base (pays gas)

This module bridges:
  - KK V2 task completion events  →  describe-net on-chain reputation
  - EM evidence types  →  seal types (SKILLFUL, RELIABLE, etc.)
  - Agent ratings  →  seal scores (0-100)
  - Batch operations  →  up to 20 seals per TX

The result: every task completion automatically builds on-chain reputation
that feeds back into the DecisionEngine's matching quality.

Design:
  - Pure functions for signing (no network I/O)
  - Separate submission layer (mockable, testable)
  - Category-to-seal mapping mirrors AutoJob's skill taxonomy
  - Graceful degradation (works without private key for dry runs)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("kk.seal_issuer")


# ══════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════

# describe-net seal types (from SealRegistry.sol)
SEAL_TYPES = {
    "SKILLFUL": "0x" + sha256(b"SKILLFUL").hexdigest()[:64],
    "RELIABLE": "0x" + sha256(b"RELIABLE").hexdigest()[:64],
    "THOROUGH": "0x" + sha256(b"THOROUGH").hexdigest()[:64],
    "ENGAGED": "0x" + sha256(b"ENGAGED").hexdigest()[:64],
    "HELPFUL": "0x" + sha256(b"HELPFUL").hexdigest()[:64],
    "CURIOUS": "0x" + sha256(b"CURIOUS").hexdigest()[:64],
    "FAIR": "0x" + sha256(b"FAIR").hexdigest()[:64],
    "ACCURATE": "0x" + sha256(b"ACCURATE").hexdigest()[:64],
    "RESPONSIVE": "0x" + sha256(b"RESPONSIVE").hexdigest()[:64],
    "ETHICAL": "0x" + sha256(b"ETHICAL").hexdigest()[:64],
    "CREATIVE": "0x" + sha256(b"CREATIVE").hexdigest()[:64],
    "PROFESSIONAL": "0x" + sha256(b"PROFESSIONAL").hexdigest()[:64],
    "FRIENDLY": "0x" + sha256(b"FRIENDLY").hexdigest()[:64],
}

# NOTE: Actual on-chain seal types use keccak256, not sha256.
# These are placeholders for off-chain logic. The submission layer
# will use proper keccak256 hashes when signing for the real contract.
# For now, we use these as semantic identifiers.


class Quadrant(Enum):
    """Evaluation quadrants from SealRegistry."""
    H2H = 0  # Human → Human
    H2A = 1  # Human → Agent
    A2H = 2  # Agent → Human
    A2A = 3  # Agent → Agent


# EIP-712 domain for SealRegistry
SEAL_REGISTRY_DOMAIN = {
    "name": "SealRegistry",
    "version": "2",
    # chainId and verifyingContract set at runtime
}

# EIP-712 type hash for meta-transaction seals
SEAL_TYPEHASH_FIELDS = [
    {"name": "subject", "type": "address"},
    {"name": "sealType", "type": "bytes32"},
    {"name": "quadrant", "type": "uint8"},
    {"name": "score", "type": "uint8"},
    {"name": "evidenceHash", "type": "bytes32"},
    {"name": "expiresAt", "type": "uint48"},
    {"name": "nonce", "type": "uint256"},
    {"name": "deadline", "type": "uint256"},
]


# ══════════════════════════════════════════════════════════════════
# EM Category → Seal Type Mapping
# ══════════════════════════════════════════════════════════════════

# Maps EM task categories to which seals should be issued
# When a task in this category is completed, these seals are issued
# to the worker (A2H quadrant — agent evaluating human worker)
CATEGORY_SEAL_MAP: dict[str, list[dict[str, Any]]] = {
    "physical_verification": [
        {"seal": "SKILLFUL", "weight": 0.3, "min_rating": 3},
        {"seal": "RELIABLE", "weight": 0.4, "min_rating": 2},
        {"seal": "THOROUGH", "weight": 0.3, "min_rating": 4},
    ],
    "data_collection": [
        {"seal": "THOROUGH", "weight": 0.4, "min_rating": 3},
        {"seal": "ACCURATE", "weight": 0.3, "min_rating": 3},
        {"seal": "RELIABLE", "weight": 0.3, "min_rating": 2},
    ],
    "content_creation": [
        {"seal": "CREATIVE", "weight": 0.4, "min_rating": 3},
        {"seal": "SKILLFUL", "weight": 0.3, "min_rating": 3},
        {"seal": "THOROUGH", "weight": 0.3, "min_rating": 4},
    ],
    "translation": [
        {"seal": "SKILLFUL", "weight": 0.4, "min_rating": 3},
        {"seal": "ACCURATE", "weight": 0.4, "min_rating": 3},
        {"seal": "PROFESSIONAL", "weight": 0.2, "min_rating": 4},
    ],
    "quality_assurance": [
        {"seal": "THOROUGH", "weight": 0.4, "min_rating": 3},
        {"seal": "ACCURATE", "weight": 0.3, "min_rating": 3},
        {"seal": "RELIABLE", "weight": 0.3, "min_rating": 2},
    ],
    "technical_task": [
        {"seal": "SKILLFUL", "weight": 0.5, "min_rating": 3},
        {"seal": "THOROUGH", "weight": 0.3, "min_rating": 3},
        {"seal": "RELIABLE", "weight": 0.2, "min_rating": 2},
    ],
    "survey": [
        {"seal": "ENGAGED", "weight": 0.4, "min_rating": 3},
        {"seal": "HELPFUL", "weight": 0.3, "min_rating": 3},
        {"seal": "RELIABLE", "weight": 0.3, "min_rating": 2},
    ],
    "delivery": [
        {"seal": "RELIABLE", "weight": 0.5, "min_rating": 2},
        {"seal": "PROFESSIONAL", "weight": 0.3, "min_rating": 3},
        {"seal": "ENGAGED", "weight": 0.2, "min_rating": 3},
    ],
    "mystery_shopping": [
        {"seal": "THOROUGH", "weight": 0.4, "min_rating": 3},
        {"seal": "CURIOUS", "weight": 0.3, "min_rating": 3},
        {"seal": "RELIABLE", "weight": 0.3, "min_rating": 2},
    ],
    "notarization": [
        {"seal": "PROFESSIONAL", "weight": 0.4, "min_rating": 4},
        {"seal": "ACCURATE", "weight": 0.3, "min_rating": 4},
        {"seal": "ETHICAL", "weight": 0.3, "min_rating": 4},
    ],
    "simple_action": [
        {"seal": "RELIABLE", "weight": 0.5, "min_rating": 2},
        {"seal": "RESPONSIVE", "weight": 0.3, "min_rating": 2},
        {"seal": "ENGAGED", "weight": 0.2, "min_rating": 2},
    ],
}


# ══════════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════════

@dataclass
class SealRequest:
    """A single seal to be issued."""
    subject: str            # Worker wallet address
    seal_type: str          # e.g., "SKILLFUL"
    quadrant: Quadrant      # Usually A2H for agent→worker
    score: int              # 0-100
    evidence_hash: str      # Hash of task evidence (0x-prefixed)
    expires_at: int = 0     # 0 = never expires
    
    def validate(self) -> list[str]:
        """Validate the seal request, return list of errors."""
        errors = []
        if not self.subject or len(self.subject) != 42:
            errors.append(f"Invalid subject address: {self.subject}")
        if self.seal_type not in SEAL_TYPES:
            errors.append(f"Invalid seal type: {self.seal_type}")
        if not 0 <= self.score <= 100:
            errors.append(f"Score out of range: {self.score}")
        if self.expires_at < 0:
            errors.append(f"Invalid expiry: {self.expires_at}")
        return errors


@dataclass
class SignedSeal:
    """A seal signed with EIP-712 for meta-transaction submission."""
    request: SealRequest
    evaluator: str          # Signer wallet address
    nonce: int
    deadline: int
    signature: str          # 0x-prefixed hex signature
    
    def to_contract_params(self) -> dict:
        """Convert to SealRegistry.MetaTxParams format."""
        return {
            "subject": self.request.subject,
            "sealType": _keccak256_seal_type(self.request.seal_type),
            "quadrant": self.request.quadrant.value,
            "score": self.request.score,
            "evidenceHash": self.request.evidence_hash,
            "expiresAt": self.request.expires_at,
            "nonce": self.nonce,
            "deadline": self.deadline,
        }


@dataclass
class SealBatch:
    """A batch of signed seals ready for submission."""
    seals: list[SignedSeal]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    submitted: bool = False
    tx_hash: Optional[str] = None
    
    @property
    def count(self) -> int:
        return len(self.seals)
    
    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "created_at": self.created_at,
            "submitted": self.submitted,
            "tx_hash": self.tx_hash,
            "seals": [
                {
                    "subject": s.request.subject,
                    "seal_type": s.request.seal_type,
                    "quadrant": s.request.quadrant.name,
                    "score": s.request.score,
                    "evaluator": s.evaluator,
                }
                for s in self.seals
            ],
        }


@dataclass
class IssuanceResult:
    """Result of processing a task completion into seals."""
    task_id: str
    worker_address: str
    seals_generated: int
    seals_signed: int
    errors: list[str] = field(default_factory=list)
    seal_requests: list[SealRequest] = field(default_factory=list)
    signed_seals: list[SignedSeal] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        return self.seals_signed > 0 and not self.errors


@dataclass
class SealIssuerConfig:
    """Configuration for the seal issuer."""
    # Contract addresses (set when describe-net deploys)
    seal_registry_address: str = ""
    identity_registry_address: str = ""
    
    # Chain config
    chain_id: int = 8453           # Base mainnet
    rpc_url: str = "https://mainnet.base.org"
    
    # Signing config
    private_key: str = ""          # Agent's private key for signing
    
    # Seal parameters
    default_expiry_days: int = 365  # Seals expire after 1 year
    min_rating_for_seal: int = 2   # Minimum EM rating to issue any seal
    max_seals_per_batch: int = 20  # SealRegistry limit
    
    # Score scaling
    rating_to_score_map: dict[int, int] = field(default_factory=lambda: {
        1: 20,   # 1 star → score 20 (minimum, still issued with low score)
        2: 40,   # 2 stars → score 40
        3: 60,   # 3 stars → score 60
        4: 80,   # 4 stars → score 80
        5: 95,   # 5 stars → score 95 (not 100 — perfect is rare)
    })
    
    # Evidence hash prefix (for traceability)
    evidence_prefix: str = "em-task-"
    
    # Dry run mode (signs but doesn't submit)
    dry_run: bool = True


# ══════════════════════════════════════════════════════════════════
# Core Logic
# ══════════════════════════════════════════════════════════════════

def _keccak256_seal_type(seal_name: str) -> bytes:
    """Compute keccak256 hash of a seal type name.
    
    Matches Solidity: keccak256(abi.encodePacked("SKILLFUL"))
    """
    try:
        from eth_utils import keccak
        return keccak(text=seal_name)
    except ImportError:
        # Fallback: use hashlib (not compatible with on-chain, but works for tests)
        import hashlib
        return bytes.fromhex(hashlib.sha256(seal_name.encode()).hexdigest())


def compute_evidence_hash(task_id: str, worker_address: str, rating: int) -> str:
    """Compute evidence hash from task completion data.
    
    The evidence hash links the on-chain seal to the off-chain EM task.
    Anyone can verify the seal by checking this hash against EM API data.
    """
    evidence_data = f"em:{task_id}:{worker_address.lower()}:{rating}"
    return "0x" + sha256(evidence_data.encode()).hexdigest()


def rating_to_score(rating: int, config: SealIssuerConfig) -> int:
    """Convert EM 1-5 star rating to 0-100 seal score."""
    return config.rating_to_score_map.get(rating, 0)


def map_task_to_seals(
    task_id: str,
    category: str,
    worker_address: str,
    rating: int,
    config: SealIssuerConfig,
) -> list[SealRequest]:
    """Map a completed EM task to seal requests.
    
    This is where the flywheel magic happens:
    - EM task category → seal types (from CATEGORY_SEAL_MAP)
    - EM rating → seal scores (via rating_to_score)
    - Task evidence → evidence hash (for on-chain traceability)
    
    Each seal represents a specific dimension of worker performance.
    Multiple seals per task gives granular reputation data.
    """
    if rating < config.min_rating_for_seal:
        logger.info(f"Task {task_id}: rating {rating} below minimum {config.min_rating_for_seal}, no seals")
        return []
    
    seal_mappings = CATEGORY_SEAL_MAP.get(category, [])
    if not seal_mappings:
        logger.warning(f"Task {task_id}: unknown category '{category}', using simple_action defaults")
        seal_mappings = CATEGORY_SEAL_MAP["simple_action"]
    
    base_score = rating_to_score(rating, config)
    evidence_hash = compute_evidence_hash(task_id, worker_address, rating)
    
    # Calculate expiry
    expires_at = 0
    if config.default_expiry_days > 0:
        expires_at = int(time.time()) + (config.default_expiry_days * 86400)
    
    seals = []
    for mapping in seal_mappings:
        # Only issue seals where rating meets the seal's minimum
        if rating < mapping.get("min_rating", 0):
            continue
        
        # Weight-adjusted score: base_score * weight gives category-specific emphasis
        # But we keep score in 0-100 range, so weight modulates the base
        weight = mapping.get("weight", 1.0)
        weighted_score = min(100, max(0, int(base_score * (0.7 + 0.3 * weight))))
        
        seal = SealRequest(
            subject=worker_address,
            seal_type=mapping["seal"],
            quadrant=Quadrant.A2H,  # Agent evaluating human worker
            score=weighted_score,
            evidence_hash=evidence_hash,
            expires_at=expires_at,
        )
        
        errors = seal.validate()
        if errors:
            logger.warning(f"Task {task_id}: invalid seal {mapping['seal']}: {errors}")
            continue
        
        seals.append(seal)
    
    logger.info(f"Task {task_id}: mapped to {len(seals)} seals for category '{category}'")
    return seals


def sign_seal(
    seal: SealRequest,
    evaluator_key: str,
    nonce: int,
    config: SealIssuerConfig,
    deadline_offset: int = 3600,  # 1 hour validity
) -> Optional[SignedSeal]:
    """Sign a seal request using EIP-712.
    
    This creates a meta-transaction that can be submitted by any relayer.
    The evaluator (agent) signs off-chain; the relayer pays gas on-chain.
    
    Args:
        seal: The seal to sign
        evaluator_key: Private key of the evaluating agent
        nonce: Current nonce from SealRegistry.nonces(evaluator)
        config: Issuer configuration
        deadline_offset: Seconds until signature expires
    
    Returns:
        SignedSeal or None if signing fails
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError:
        logger.error("eth_account required: pip install eth-account")
        return None
    
    account = Account.from_key(evaluator_key)
    deadline = int(time.time()) + deadline_offset
    
    # Build EIP-712 typed data matching SealRegistry.sol SEAL_TYPEHASH
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Seal": SEAL_TYPEHASH_FIELDS,
        },
        "primaryType": "Seal",
        "domain": {
            "name": SEAL_REGISTRY_DOMAIN["name"],
            "version": SEAL_REGISTRY_DOMAIN["version"],
            "chainId": config.chain_id,
            "verifyingContract": config.seal_registry_address,
        },
        "message": {
            "subject": seal.subject,
            "sealType": _keccak256_seal_type(seal.seal_type),
            "quadrant": seal.quadrant.value,
            "score": seal.score,
            "evidenceHash": bytes.fromhex(seal.evidence_hash[2:]) if seal.evidence_hash.startswith("0x") else bytes.fromhex(seal.evidence_hash),
            "expiresAt": seal.expires_at,
            "nonce": nonce,
            "deadline": deadline,
        },
    }
    
    try:
        signable = encode_typed_data(full_message=typed_data)
        signed = Account.sign_message(signable, private_key=evaluator_key)
        
        sig_hex = signed.signature.hex()
        if not sig_hex.startswith("0x"):
            sig_hex = "0x" + sig_hex
        
        return SignedSeal(
            request=seal,
            evaluator=account.address,
            nonce=nonce,
            deadline=deadline,
            signature=sig_hex,
        )
    except Exception as e:
        logger.error(f"Failed to sign seal {seal.seal_type} for {seal.subject}: {e}")
        return None


def create_batch(signed_seals: list[SignedSeal], max_per_batch: int = 20) -> list[SealBatch]:
    """Group signed seals into batches for submission.
    
    SealRegistry.batchSubmitSealsWithSignatures allows up to 20 per TX.
    This function splits larger sets into compliant batches.
    """
    batches = []
    for i in range(0, len(signed_seals), max_per_batch):
        chunk = signed_seals[i:i + max_per_batch]
        batches.append(SealBatch(seals=chunk))
    return batches


# ══════════════════════════════════════════════════════════════════
# Task Completion → Seal Issuance Pipeline
# ══════════════════════════════════════════════════════════════════

class SealIssuer:
    """Manages the full seal issuance pipeline.
    
    Lifecycle:
    1. on_task_completed(task) → generates seal requests from task data
    2. sign_pending() → signs all pending seals with the agent's key
    3. submit_batch() → sends signed seals to the blockchain (or dry-run logs)
    4. Repeat each orchestrator cycle
    
    The issuer maintains a queue of pending seals and batches them
    for efficient submission. Failed submissions are retried with
    exponential backoff.
    """
    
    def __init__(self, config: SealIssuerConfig):
        self.config = config
        self.pending_seals: list[SealRequest] = []
        self.signed_seals: list[SignedSeal] = []
        self.pending_batches: list[SealBatch] = []
        self.submitted_batches: list[SealBatch] = []
        self.total_seals_issued: int = 0
        self.total_tasks_processed: int = 0
        self.current_nonce: int = 0  # Fetched from chain on init
        self._history: list[IssuanceResult] = []
    
    def on_task_completed(
        self,
        task_id: str,
        category: str,
        worker_address: str,
        rating: int,
        evidence_data: Optional[dict] = None,
    ) -> IssuanceResult:
        """Process a task completion into seal requests.
        
        Called by the orchestrator when a task is approved on EM.
        Maps the task outcome to seal types and queues them for signing.
        
        Args:
            task_id: EM task ID
            category: EM task category (physical_verification, etc.)
            worker_address: Worker's wallet address
            rating: 1-5 star rating from task creator
            evidence_data: Optional additional evidence metadata
        
        Returns:
            IssuanceResult with generated seal requests
        """
        result = IssuanceResult(
            task_id=task_id,
            worker_address=worker_address,
            seals_generated=0,
            seals_signed=0,
        )
        
        # Generate seal requests from task data
        seals = map_task_to_seals(
            task_id=task_id,
            category=category,
            worker_address=worker_address,
            rating=rating,
            config=self.config,
        )
        
        result.seals_generated = len(seals)
        result.seal_requests = seals
        
        # Queue for signing
        self.pending_seals.extend(seals)
        self.total_tasks_processed += 1
        
        logger.info(
            f"Task {task_id} completed: {len(seals)} seals queued "
            f"(category={category}, rating={rating}, worker={worker_address[:10]}...)"
        )
        
        self._history.append(result)
        return result
    
    def sign_pending(self) -> int:
        """Sign all pending seal requests.
        
        Returns number of seals successfully signed.
        """
        if not self.pending_seals:
            return 0
        
        if not self.config.private_key:
            logger.warning("No private key configured — seals queued but not signed")
            return 0
        
        signed_count = 0
        remaining = []
        
        for seal in self.pending_seals:
            signed = sign_seal(
                seal=seal,
                evaluator_key=self.config.private_key,
                nonce=self.current_nonce,
                config=self.config,
            )
            
            if signed:
                self.signed_seals.append(signed)
                self.current_nonce += 1
                signed_count += 1
            else:
                remaining.append(seal)
        
        self.pending_seals = remaining
        
        if signed_count > 0:
            logger.info(f"Signed {signed_count} seals (nonce now {self.current_nonce})")
        
        return signed_count
    
    def prepare_batches(self) -> list[SealBatch]:
        """Prepare signed seals into submission batches."""
        if not self.signed_seals:
            return []
        
        batches = create_batch(
            self.signed_seals,
            max_per_batch=self.config.max_seals_per_batch,
        )
        
        self.pending_batches.extend(batches)
        self.signed_seals = []  # Clear signed queue
        
        logger.info(f"Prepared {len(batches)} batch(es) for submission")
        return batches
    
    def submit_batches(self) -> list[dict]:
        """Submit pending batches to the blockchain.
        
        In dry_run mode, logs the batches without submitting.
        In production, calls SealRegistry.batchSubmitSealsWithSignatures.
        
        Returns list of submission results.
        """
        results = []
        
        for batch in self.pending_batches:
            if self.config.dry_run:
                result = self._dry_run_submit(batch)
            else:
                result = self._chain_submit(batch)
            
            results.append(result)
            
            if result.get("success"):
                batch.submitted = True
                batch.tx_hash = result.get("tx_hash")
                self.submitted_batches.append(batch)
                self.total_seals_issued += batch.count
        
        # Remove submitted batches from pending
        self.pending_batches = [b for b in self.pending_batches if not b.submitted]
        
        return results
    
    def _dry_run_submit(self, batch: SealBatch) -> dict:
        """Simulate batch submission (no chain interaction)."""
        logger.info(
            f"[DRY RUN] Would submit batch of {batch.count} seals: "
            f"{[s.request.seal_type for s in batch.seals]}"
        )
        return {
            "success": True,
            "dry_run": True,
            "batch_size": batch.count,
            "seals": [
                {
                    "subject": s.request.subject,
                    "type": s.request.seal_type,
                    "score": s.request.score,
                    "quadrant": s.request.quadrant.name,
                }
                for s in batch.seals
            ],
        }
    
    def _chain_submit(self, batch: SealBatch) -> dict:
        """Submit batch to SealRegistry on-chain.
        
        TODO: Implement when describe-net deploys to Base mainnet.
        Will use web3.py to call batchSubmitSealsWithSignatures.
        """
        if not self.config.seal_registry_address:
            logger.error("SealRegistry address not configured")
            return {"success": False, "error": "No contract address"}
        
        logger.warning("Chain submission not yet implemented — use dry_run mode")
        return {"success": False, "error": "Chain submission pending deployment"}
    
    def process_cycle(self) -> dict:
        """Run a complete seal issuance cycle.
        
        Called by the swarm orchestrator each coordination cycle.
        Signs pending seals, batches them, and submits.
        
        Returns cycle summary.
        """
        signed = self.sign_pending()
        batches = self.prepare_batches()
        results = self.submit_batches() if batches else []
        
        return {
            "signed": signed,
            "batches_prepared": len(batches),
            "batches_submitted": sum(1 for r in results if r.get("success")),
            "total_issued": self.total_seals_issued,
            "pending_seals": len(self.pending_seals),
            "pending_batches": len(self.pending_batches),
        }
    
    def get_status(self) -> dict:
        """Get current issuer status."""
        return {
            "total_tasks_processed": self.total_tasks_processed,
            "total_seals_issued": self.total_seals_issued,
            "pending_seals": len(self.pending_seals),
            "signed_seals": len(self.signed_seals),
            "pending_batches": len(self.pending_batches),
            "submitted_batches": len(self.submitted_batches),
            "current_nonce": self.current_nonce,
            "dry_run": self.config.dry_run,
            "contract": self.config.seal_registry_address or "(not deployed)",
            "chain_id": self.config.chain_id,
        }
    
    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent issuance history."""
        return [
            {
                "task_id": r.task_id,
                "worker": r.worker_address,
                "seals_generated": r.seals_generated,
                "seals_signed": r.seals_signed,
                "success": r.success,
                "errors": r.errors,
            }
            for r in self._history[-limit:]
        ]


# ══════════════════════════════════════════════════════════════════
# Bidirectional Seal Issuance
# ══════════════════════════════════════════════════════════════════

def generate_worker_to_agent_seals(
    agent_address: str,
    agent_id: int,
    task_id: str,
    worker_rating_of_agent: int,
) -> list[dict]:
    """Generate seal data for worker evaluating agent (H2A quadrant).
    
    Workers can't sign EIP-712 on their own (they're humans with wallets).
    Instead, this generates the data needed for the EM dashboard to
    guide the worker through issuing H2A seals.
    
    The describe-net adapter handles H2A seals via the ERC8004ReputationAdapter,
    which accepts standard giveFeedback() calls.
    
    Returns list of seal data dicts for the dashboard.
    """
    if worker_rating_of_agent < 2:
        return []
    
    base_score = {1: 20, 2: 40, 3: 60, 4: 80, 5: 95}.get(worker_rating_of_agent, 0)
    evidence_hash = compute_evidence_hash(task_id, agent_address, worker_rating_of_agent)
    
    # Workers evaluate agents on H2A-specific seal types
    h2a_seals = [
        {"seal": "FAIR", "weight": 0.3},
        {"seal": "ACCURATE", "weight": 0.3},
        {"seal": "RESPONSIVE", "weight": 0.2},
        {"seal": "ETHICAL", "weight": 0.2},
    ]
    
    results = []
    for mapping in h2a_seals:
        score = min(100, max(0, int(base_score * (0.7 + 0.3 * mapping["weight"]))))
        results.append({
            "agent_id": agent_id,
            "seal_type": mapping["seal"],
            "quadrant": "H2A",
            "score": score,
            "evidence_hash": evidence_hash,
            "tag1": mapping["seal"],
            "tag2": "H2A",
        })
    
    return results


# ══════════════════════════════════════════════════════════════════
# Agent-to-Agent Seals (Swarm Coordination)
# ══════════════════════════════════════════════════════════════════

def generate_a2a_seals(
    evaluator_address: str,
    subject_agent_id: int,
    subject_address: str,
    collaboration_quality: int,  # 0-100 based on coordination metrics
    task_ids: list[str],
) -> list[SealRequest]:
    """Generate agent-to-agent seals for swarm coordination quality.
    
    When agents collaborate within the KK swarm, they evaluate each other
    on coordination effectiveness. This creates A2A reputation that's
    unique to multi-agent systems.
    
    Seal types for A2A:
    - RELIABLE: Consistently available and responsive
    - HELPFUL: Contributes to other agents' success
    - ENGAGED: Active participation in swarm coordination
    - SKILLFUL: Quality of task execution within the swarm
    """
    if collaboration_quality < 20:
        return []
    
    # Evidence hash covers all collaborative tasks
    evidence_data = f"a2a:{','.join(task_ids)}:{evaluator_address.lower()}:{subject_address.lower()}"
    evidence_hash = "0x" + sha256(evidence_data.encode()).hexdigest()
    
    a2a_mappings = [
        {"seal": "RELIABLE", "threshold": 30},
        {"seal": "HELPFUL", "threshold": 40},
        {"seal": "ENGAGED", "threshold": 20},
        {"seal": "SKILLFUL", "threshold": 50},
    ]
    
    seals = []
    for mapping in a2a_mappings:
        if collaboration_quality >= mapping["threshold"]:
            seals.append(SealRequest(
                subject=subject_address,
                seal_type=mapping["seal"],
                quadrant=Quadrant.A2A,
                score=min(100, collaboration_quality),
                evidence_hash=evidence_hash,
                expires_at=int(time.time()) + (180 * 86400),  # 6 months for A2A
            ))
    
    return seals


# ══════════════════════════════════════════════════════════════════
# Persistence
# ══════════════════════════════════════════════════════════════════

def save_issuance_state(issuer: SealIssuer, output_dir: Path) -> Path:
    """Save issuer state for continuity across restarts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    state_file = output_dir / "seal_issuer_state.json"
    
    state = {
        "status": issuer.get_status(),
        "history": issuer.get_history(limit=100),
        "pending_seals": [
            {
                "subject": s.subject,
                "seal_type": s.seal_type,
                "quadrant": s.quadrant.name,
                "score": s.score,
                "evidence_hash": s.evidence_hash,
            }
            for s in issuer.pending_seals
        ],
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    
    state_file.write_text(json.dumps(state, indent=2))
    logger.info(f"Saved seal issuer state to {state_file}")
    return state_file


def load_issuance_state(state_file: Path) -> dict:
    """Load previously saved issuer state."""
    if not state_file.exists():
        return {}
    
    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load issuer state: {e}")
        return {}
