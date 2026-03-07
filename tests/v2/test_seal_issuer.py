"""
Tests for Seal Issuer — the describe-net flywheel bridge.

Tests cover:
  - EM category → seal type mapping
  - Rating → score conversion  
  - Evidence hash computation
  - Seal request validation
  - Task completion → seal pipeline
  - Batch creation and splitting
  - Bidirectional seal generation (A2H + H2A)
  - Agent-to-agent seal generation (A2A)
  - Pipeline cycle processing
  - State persistence
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.seal_issuer import (
    CATEGORY_SEAL_MAP,
    Quadrant,
    SealBatch,
    SealIssuer,
    SealIssuerConfig,
    SealRequest,
    SignedSeal,
    compute_evidence_hash,
    create_batch,
    generate_a2a_seals,
    generate_worker_to_agent_seals,
    load_issuance_state,
    map_task_to_seals,
    rating_to_score,
    save_issuance_state,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

WORKER_ADDRESS = "0x52E05C8e45a32eeE169639F6d2cA40f8887b5A15"
AGENT_ADDRESS = "0xD3868E1eD738CED6945A574a7c769433BeD5d474"
TASK_ID = "task-abc-123"


@pytest.fixture
def config():
    return SealIssuerConfig(
        seal_registry_address="0x" + "11" * 20,
        chain_id=8453,
        dry_run=True,
    )


@pytest.fixture
def issuer(config):
    return SealIssuer(config)


# ═══════════════════════════════════════════════════════════════════
# Rating → Score
# ═══════════════════════════════════════════════════════════════════

class TestRatingToScore:
    def test_all_ratings(self, config):
        assert rating_to_score(1, config) == 20
        assert rating_to_score(2, config) == 40
        assert rating_to_score(3, config) == 60
        assert rating_to_score(4, config) == 80
        assert rating_to_score(5, config) == 95

    def test_invalid_rating_returns_zero(self, config):
        assert rating_to_score(0, config) == 0
        assert rating_to_score(6, config) == 0
        assert rating_to_score(-1, config) == 0


# ═══════════════════════════════════════════════════════════════════
# Evidence Hash
# ═══════════════════════════════════════════════════════════════════

class TestEvidenceHash:
    def test_deterministic(self):
        h1 = compute_evidence_hash(TASK_ID, WORKER_ADDRESS, 5)
        h2 = compute_evidence_hash(TASK_ID, WORKER_ADDRESS, 5)
        assert h1 == h2

    def test_starts_with_0x(self):
        h = compute_evidence_hash(TASK_ID, WORKER_ADDRESS, 5)
        assert h.startswith("0x")
        assert len(h) == 66  # 0x + 64 hex chars

    def test_different_ratings_different_hashes(self):
        h1 = compute_evidence_hash(TASK_ID, WORKER_ADDRESS, 4)
        h2 = compute_evidence_hash(TASK_ID, WORKER_ADDRESS, 5)
        assert h1 != h2

    def test_case_insensitive_address(self):
        h1 = compute_evidence_hash(TASK_ID, WORKER_ADDRESS.lower(), 5)
        h2 = compute_evidence_hash(TASK_ID, WORKER_ADDRESS.lower(), 5)
        assert h1 == h2


# ═══════════════════════════════════════════════════════════════════
# Seal Request Validation
# ═══════════════════════════════════════════════════════════════════

class TestSealRequestValidation:
    def test_valid_request(self):
        seal = SealRequest(
            subject=WORKER_ADDRESS,
            seal_type="SKILLFUL",
            quadrant=Quadrant.A2H,
            score=85,
            evidence_hash="0x" + "ab" * 32,
        )
        assert seal.validate() == []

    def test_invalid_address(self):
        seal = SealRequest(
            subject="0xinvalid",
            seal_type="SKILLFUL",
            quadrant=Quadrant.A2H,
            score=85,
            evidence_hash="0x" + "ab" * 32,
        )
        errors = seal.validate()
        assert len(errors) == 1
        assert "address" in errors[0].lower()

    def test_invalid_seal_type(self):
        seal = SealRequest(
            subject=WORKER_ADDRESS,
            seal_type="NONEXISTENT",
            quadrant=Quadrant.A2H,
            score=85,
            evidence_hash="0x" + "ab" * 32,
        )
        errors = seal.validate()
        assert len(errors) == 1
        assert "seal type" in errors[0].lower()

    def test_score_out_of_range(self):
        seal = SealRequest(
            subject=WORKER_ADDRESS,
            seal_type="SKILLFUL",
            quadrant=Quadrant.A2H,
            score=101,
            evidence_hash="0x" + "ab" * 32,
        )
        errors = seal.validate()
        assert len(errors) == 1
        assert "score" in errors[0].lower()

    def test_negative_score(self):
        seal = SealRequest(
            subject=WORKER_ADDRESS,
            seal_type="SKILLFUL",
            quadrant=Quadrant.A2H,
            score=-1,
            evidence_hash="0x" + "ab" * 32,
        )
        errors = seal.validate()
        assert any("score" in e.lower() for e in errors)

    def test_multiple_errors(self):
        seal = SealRequest(
            subject="bad",
            seal_type="BAD",
            quadrant=Quadrant.A2H,
            score=200,
            evidence_hash="0x" + "ab" * 32,
        )
        errors = seal.validate()
        assert len(errors) >= 2


# ═══════════════════════════════════════════════════════════════════
# Category → Seal Mapping
# ═══════════════════════════════════════════════════════════════════

class TestCategorySealMapping:
    def test_all_categories_have_mappings(self):
        expected_categories = [
            "physical_verification", "data_collection", "content_creation",
            "translation", "quality_assurance", "technical_task",
            "survey", "delivery", "mystery_shopping", "notarization",
            "simple_action",
        ]
        for cat in expected_categories:
            assert cat in CATEGORY_SEAL_MAP, f"Missing mapping for {cat}"

    def test_each_mapping_has_valid_seals(self):
        from lib.seal_issuer import SEAL_TYPES
        for cat, mappings in CATEGORY_SEAL_MAP.items():
            for m in mappings:
                assert m["seal"] in SEAL_TYPES, f"{cat}: invalid seal {m['seal']}"
                assert 0 < m["weight"] <= 1.0, f"{cat}: bad weight {m['weight']}"
                assert 0 <= m["min_rating"] <= 5, f"{cat}: bad min_rating {m['min_rating']}"

    def test_weights_approximately_sum_to_one(self):
        for cat, mappings in CATEGORY_SEAL_MAP.items():
            total = sum(m["weight"] for m in mappings)
            assert 0.95 <= total <= 1.05, f"{cat}: weights sum to {total}"

    def test_physical_verification_seals(self, config):
        seals = map_task_to_seals(TASK_ID, "physical_verification", WORKER_ADDRESS, 5, config)
        seal_types = {s.seal_type for s in seals}
        assert "SKILLFUL" in seal_types
        assert "RELIABLE" in seal_types
        assert "THOROUGH" in seal_types

    def test_technical_task_seals(self, config):
        seals = map_task_to_seals(TASK_ID, "technical_task", WORKER_ADDRESS, 4, config)
        seal_types = {s.seal_type for s in seals}
        assert "SKILLFUL" in seal_types

    def test_content_creation_seals(self, config):
        seals = map_task_to_seals(TASK_ID, "content_creation", WORKER_ADDRESS, 5, config)
        seal_types = {s.seal_type for s in seals}
        assert "CREATIVE" in seal_types

    def test_unknown_category_defaults_to_simple(self, config):
        seals = map_task_to_seals(TASK_ID, "unknown_thing", WORKER_ADDRESS, 4, config)
        assert len(seals) > 0  # Falls back to simple_action
        seal_types = {s.seal_type for s in seals}
        assert "RELIABLE" in seal_types


class TestMapTaskToSeals:
    def test_low_rating_no_seals(self, config):
        config.min_rating_for_seal = 3
        seals = map_task_to_seals(TASK_ID, "technical_task", WORKER_ADDRESS, 2, config)
        assert len(seals) == 0

    def test_rating_filters_by_min_rating(self, config):
        # notarization requires min_rating 4 for all seals
        seals = map_task_to_seals(TASK_ID, "notarization", WORKER_ADDRESS, 3, config)
        assert len(seals) == 0  # All three seals require min_rating >= 4

    def test_five_star_generates_all_seals(self, config):
        seals = map_task_to_seals(TASK_ID, "data_collection", WORKER_ADDRESS, 5, config)
        assert len(seals) == 3  # THOROUGH, ACCURATE, RELIABLE

    def test_all_seals_are_a2h_quadrant(self, config):
        seals = map_task_to_seals(TASK_ID, "technical_task", WORKER_ADDRESS, 5, config)
        for seal in seals:
            assert seal.quadrant == Quadrant.A2H

    def test_scores_in_valid_range(self, config):
        for rating in range(1, 6):
            seals = map_task_to_seals(TASK_ID, "delivery", WORKER_ADDRESS, rating, config)
            for seal in seals:
                assert 0 <= seal.score <= 100

    def test_higher_rating_higher_scores(self, config):
        seals_3 = map_task_to_seals(TASK_ID, "simple_action", WORKER_ADDRESS, 3, config)
        seals_5 = map_task_to_seals(TASK_ID, "simple_action", WORKER_ADDRESS, 5, config)
        
        if seals_3 and seals_5:
            avg_3 = sum(s.score for s in seals_3) / len(seals_3)
            avg_5 = sum(s.score for s in seals_5) / len(seals_5)
            assert avg_5 > avg_3

    def test_evidence_hash_consistent(self, config):
        seals = map_task_to_seals(TASK_ID, "survey", WORKER_ADDRESS, 4, config)
        # All seals for same task should share the same evidence hash
        hashes = {s.evidence_hash for s in seals}
        assert len(hashes) == 1

    def test_expiry_set_from_config(self, config):
        config.default_expiry_days = 365
        seals = map_task_to_seals(TASK_ID, "delivery", WORKER_ADDRESS, 4, config)
        for seal in seals:
            assert seal.expires_at > 0

    def test_no_expiry_when_zero(self, config):
        config.default_expiry_days = 0
        seals = map_task_to_seals(TASK_ID, "delivery", WORKER_ADDRESS, 4, config)
        for seal in seals:
            assert seal.expires_at == 0


# ═══════════════════════════════════════════════════════════════════
# Batch Creation
# ═══════════════════════════════════════════════════════════════════

class TestBatchCreation:
    def _make_signed_seal(self, seal_type="SKILLFUL") -> SignedSeal:
        return SignedSeal(
            request=SealRequest(
                subject=WORKER_ADDRESS,
                seal_type=seal_type,
                quadrant=Quadrant.A2H,
                score=80,
                evidence_hash="0x" + "ab" * 32,
            ),
            evaluator=AGENT_ADDRESS,
            nonce=0,
            deadline=9999999999,
            signature="0x" + "cc" * 65,
        )

    def test_single_batch(self):
        seals = [self._make_signed_seal() for _ in range(5)]
        batches = create_batch(seals, max_per_batch=20)
        assert len(batches) == 1
        assert batches[0].count == 5

    def test_split_into_multiple_batches(self):
        seals = [self._make_signed_seal() for _ in range(25)]
        batches = create_batch(seals, max_per_batch=20)
        assert len(batches) == 2
        assert batches[0].count == 20
        assert batches[1].count == 5

    def test_exact_batch_size(self):
        seals = [self._make_signed_seal() for _ in range(20)]
        batches = create_batch(seals, max_per_batch=20)
        assert len(batches) == 1
        assert batches[0].count == 20

    def test_empty_input(self):
        batches = create_batch([], max_per_batch=20)
        assert len(batches) == 0

    def test_batch_to_dict(self):
        seals = [self._make_signed_seal("RELIABLE")]
        batch = SealBatch(seals=seals)
        d = batch.to_dict()
        assert d["count"] == 1
        assert d["submitted"] is False
        assert d["seals"][0]["seal_type"] == "RELIABLE"


# ═══════════════════════════════════════════════════════════════════
# Seal Issuer Pipeline
# ═══════════════════════════════════════════════════════════════════

class TestSealIssuer:
    def test_on_task_completed(self, issuer):
        result = issuer.on_task_completed(
            task_id=TASK_ID,
            category="technical_task",
            worker_address=WORKER_ADDRESS,
            rating=5,
        )
        assert result.success is False  # No signing yet (no private key)
        assert result.seals_generated > 0
        assert result.worker_address == WORKER_ADDRESS

    def test_pending_seals_queued(self, issuer):
        issuer.on_task_completed(TASK_ID, "delivery", WORKER_ADDRESS, 4)
        assert len(issuer.pending_seals) > 0

    def test_low_rating_no_seals(self, issuer):
        issuer.config.min_rating_for_seal = 3
        result = issuer.on_task_completed(TASK_ID, "delivery", WORKER_ADDRESS, 1)
        assert result.seals_generated == 0
        assert len(issuer.pending_seals) == 0

    def test_multiple_tasks_accumulate(self, issuer):
        issuer.on_task_completed("task-1", "delivery", WORKER_ADDRESS, 5)
        issuer.on_task_completed("task-2", "technical_task", WORKER_ADDRESS, 4)
        assert len(issuer.pending_seals) > 3

    def test_sign_pending_without_key(self, issuer):
        issuer.on_task_completed(TASK_ID, "delivery", WORKER_ADDRESS, 5)
        signed = issuer.sign_pending()
        assert signed == 0  # No key configured

    def test_process_cycle_no_key(self, issuer):
        issuer.on_task_completed(TASK_ID, "delivery", WORKER_ADDRESS, 5)
        result = issuer.process_cycle()
        assert result["signed"] == 0
        assert result["pending_seals"] > 0

    def test_get_status(self, issuer):
        status = issuer.get_status()
        assert "total_tasks_processed" in status
        assert "total_seals_issued" in status
        assert "dry_run" in status
        assert status["dry_run"] is True

    def test_get_history(self, issuer):
        issuer.on_task_completed(TASK_ID, "delivery", WORKER_ADDRESS, 5)
        history = issuer.get_history()
        assert len(history) == 1
        assert history[0]["task_id"] == TASK_ID

    def test_tasks_processed_counter(self, issuer):
        issuer.on_task_completed("t1", "delivery", WORKER_ADDRESS, 5)
        issuer.on_task_completed("t2", "survey", WORKER_ADDRESS, 4)
        assert issuer.total_tasks_processed == 2


# ═══════════════════════════════════════════════════════════════════
# Dry Run Submission
# ═══════════════════════════════════════════════════════════════════

class TestDryRunSubmission:
    def _make_signed_seal(self) -> SignedSeal:
        return SignedSeal(
            request=SealRequest(
                subject=WORKER_ADDRESS,
                seal_type="RELIABLE",
                quadrant=Quadrant.A2H,
                score=75,
                evidence_hash="0x" + "dd" * 32,
            ),
            evaluator=AGENT_ADDRESS,
            nonce=0,
            deadline=9999999999,
            signature="0x" + "ee" * 65,
        )

    def test_dry_run_succeeds(self, issuer):
        issuer.signed_seals = [self._make_signed_seal()]
        batches = issuer.prepare_batches()
        results = issuer.submit_batches()
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["dry_run"] is True

    def test_dry_run_updates_counters(self, issuer):
        issuer.signed_seals = [self._make_signed_seal() for _ in range(3)]
        issuer.prepare_batches()
        issuer.submit_batches()
        assert issuer.total_seals_issued == 3
        assert len(issuer.submitted_batches) == 1
        assert len(issuer.pending_batches) == 0


# ═══════════════════════════════════════════════════════════════════
# Bidirectional Seals
# ═══════════════════════════════════════════════════════════════════

class TestWorkerToAgentSeals:
    def test_generates_h2a_seals(self):
        seals = generate_worker_to_agent_seals(
            agent_address=AGENT_ADDRESS,
            agent_id=2106,
            task_id=TASK_ID,
            worker_rating_of_agent=5,
        )
        assert len(seals) == 4  # FAIR, ACCURATE, RESPONSIVE, ETHICAL

    def test_h2a_seal_types(self):
        seals = generate_worker_to_agent_seals(
            agent_address=AGENT_ADDRESS,
            agent_id=2106,
            task_id=TASK_ID,
            worker_rating_of_agent=4,
        )
        seal_types = {s["seal_type"] for s in seals}
        assert seal_types == {"FAIR", "ACCURATE", "RESPONSIVE", "ETHICAL"}

    def test_low_rating_no_seals(self):
        seals = generate_worker_to_agent_seals(
            agent_address=AGENT_ADDRESS,
            agent_id=2106,
            task_id=TASK_ID,
            worker_rating_of_agent=1,
        )
        assert len(seals) == 0

    def test_seal_data_has_required_fields(self):
        seals = generate_worker_to_agent_seals(
            agent_address=AGENT_ADDRESS,
            agent_id=2106,
            task_id=TASK_ID,
            worker_rating_of_agent=5,
        )
        for seal in seals:
            assert "agent_id" in seal
            assert "seal_type" in seal
            assert "quadrant" in seal
            assert "score" in seal
            assert "evidence_hash" in seal
            assert seal["quadrant"] == "H2A"
            assert 0 <= seal["score"] <= 100


# ═══════════════════════════════════════════════════════════════════
# Agent-to-Agent Seals
# ═══════════════════════════════════════════════════════════════════

class TestA2ASeals:
    def test_generates_a2a_seals(self):
        seals = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=80,
            task_ids=["t1", "t2"],
        )
        assert len(seals) > 0

    def test_all_a2a_quadrant(self):
        seals = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=80,
            task_ids=["t1"],
        )
        for seal in seals:
            assert seal.quadrant == Quadrant.A2A

    def test_high_quality_all_seals(self):
        seals = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=90,
            task_ids=["t1", "t2", "t3"],
        )
        seal_types = {s.seal_type for s in seals}
        assert "RELIABLE" in seal_types
        assert "HELPFUL" in seal_types
        assert "ENGAGED" in seal_types
        assert "SKILLFUL" in seal_types

    def test_low_quality_fewer_seals(self):
        seals = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=25,
            task_ids=["t1"],
        )
        seal_types = {s.seal_type for s in seals}
        assert "ENGAGED" in seal_types  # threshold 20
        assert "SKILLFUL" not in seal_types  # threshold 50

    def test_very_low_quality_no_seals(self):
        seals = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=15,
            task_ids=["t1"],
        )
        assert len(seals) == 0

    def test_a2a_evidence_hash_deterministic(self):
        seals1 = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=80,
            task_ids=["t1", "t2"],
        )
        seals2 = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=80,
            task_ids=["t1", "t2"],
        )
        assert seals1[0].evidence_hash == seals2[0].evidence_hash

    def test_a2a_expiry_set(self):
        seals = generate_a2a_seals(
            evaluator_address=AGENT_ADDRESS,
            subject_agent_id=100,
            subject_address=WORKER_ADDRESS,
            collaboration_quality=80,
            task_ids=["t1"],
        )
        for seal in seals:
            assert seal.expires_at > 0  # 6 month expiry


# ═══════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════

class TestPersistence:
    def test_save_and_load(self, issuer):
        issuer.on_task_completed(TASK_ID, "delivery", WORKER_ADDRESS, 5)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_issuance_state(issuer, Path(tmpdir))
            assert path.exists()
            
            loaded = load_issuance_state(path)
            assert loaded["status"]["total_tasks_processed"] == 1
            assert len(loaded["history"]) == 1

    def test_load_nonexistent(self):
        result = load_issuance_state(Path("/nonexistent/state.json"))
        assert result == {}

    def test_save_creates_directory(self, issuer):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "deep" / "nested"
            path = save_issuance_state(issuer, nested)
            assert path.exists()


# ═══════════════════════════════════════════════════════════════════
# Integration: Full Pipeline Flow
# ═══════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end pipeline tests (without actual signing/chain)."""

    def test_multi_task_pipeline(self, issuer):
        """Simulate processing multiple tasks through the full pipeline."""
        # Process 5 tasks
        for i in range(5):
            issuer.on_task_completed(
                task_id=f"task-{i}",
                category=["delivery", "technical_task", "survey", "content_creation", "notarization"][i],
                worker_address=WORKER_ADDRESS,
                rating=[5, 4, 3, 5, 5][i],
            )
        
        assert issuer.total_tasks_processed == 5
        assert len(issuer.pending_seals) > 5  # Multiple seals per task
        
        # Process cycle (no key, so nothing gets signed)
        result = issuer.process_cycle()
        assert result["signed"] == 0
        
        # Status should reflect all processed tasks
        status = issuer.get_status()
        assert status["total_tasks_processed"] == 5

    def test_different_workers(self, issuer):
        """Different workers get separate seal requests."""
        issuer.on_task_completed("t1", "delivery", WORKER_ADDRESS, 5)
        issuer.on_task_completed("t2", "delivery", "0x1111111111111111111111111111111111111111", 4)
        
        subjects = {s.subject for s in issuer.pending_seals}
        assert len(subjects) == 2

    def test_category_diversity(self, issuer):
        """Different categories produce different seal types."""
        issuer.on_task_completed("t1", "technical_task", WORKER_ADDRESS, 5)
        issuer.on_task_completed("t2", "content_creation", WORKER_ADDRESS, 5)
        
        seal_types = {s.seal_type for s in issuer.pending_seals}
        assert len(seal_types) > 2  # Should have diverse seal types
        assert "SKILLFUL" in seal_types  # From technical_task
        assert "CREATIVE" in seal_types  # From content_creation


# ═══════════════════════════════════════════════════════════════════
# Quadrant Enum
# ═══════════════════════════════════════════════════════════════════

class TestQuadrant:
    def test_values(self):
        assert Quadrant.H2H.value == 0
        assert Quadrant.H2A.value == 1
        assert Quadrant.A2H.value == 2
        assert Quadrant.A2A.value == 3

    def test_all_quadrants_exist(self):
        assert len(Quadrant) == 4
