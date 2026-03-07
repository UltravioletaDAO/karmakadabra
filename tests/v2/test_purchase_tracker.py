"""
Tests for services/purchase_tracker.py — Duplicate Purchase Prevention

Covers:
  - PurchaseTracker construction (creates dirs, loads existing)
  - already_bought (check task_id)
  - record_purchase (idempotent, fields, persistence)
  - get_history (filters: product_type, seller, hours)
  - daily_spend (today's total)
  - needs_product (age-based check)
  - total_purchases
  - summary (by_type aggregation)
  - Edge cases: bad JSON, empty state, same task_id twice
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))

from services.purchase_tracker import PurchaseTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker(tmp_path):
    return PurchaseTracker(tmp_path / "data")


@pytest.fixture
def populated_tracker(tracker):
    tracker.record_purchase("t1", "seller-a", "raw_logs", 0.01, "Raw Logs Batch 1")
    tracker.record_purchase("t2", "seller-b", "skill_profiles", 0.05, "Skill Data")
    tracker.record_purchase("t3", "seller-a", "raw_logs", 0.01, "Raw Logs Batch 2")
    return tracker


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_creates_state_file(self, tracker):
        tracker.record_purchase("t1", "seller", "type", 0.01)
        assert tracker.state_file.exists()

    def test_starts_empty(self, tracker):
        assert tracker.total_purchases() == 0

    def test_loads_existing_state(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "purchase_history.json").write_text(json.dumps({
            "purchases": [
                {"task_id": "existing", "seller": "s", "product_type": "t", "price_usd": 0.01,
                 "timestamp": datetime.now(timezone.utc).isoformat()}
            ],
            "version": 1,
        }))
        tracker = PurchaseTracker(data_dir)
        assert tracker.total_purchases() == 1

    def test_handles_bad_json(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "purchase_history.json").write_text("not json")
        tracker = PurchaseTracker(data_dir)
        assert tracker.total_purchases() == 0


# ---------------------------------------------------------------------------
# already_bought
# ---------------------------------------------------------------------------


class TestAlreadyBought:
    def test_not_bought(self, tracker):
        assert tracker.already_bought("unknown-task") is False

    def test_already_bought(self, populated_tracker):
        assert populated_tracker.already_bought("t1") is True
        assert populated_tracker.already_bought("t2") is True

    def test_not_bought_after_different(self, populated_tracker):
        assert populated_tracker.already_bought("t999") is False


# ---------------------------------------------------------------------------
# record_purchase
# ---------------------------------------------------------------------------


class TestRecordPurchase:
    def test_basic_record(self, tracker):
        tracker.record_purchase("task-1", "alice", "raw_logs", 0.01, "Test Data")
        assert tracker.total_purchases() == 1
        history = tracker.get_history()
        assert history[0]["task_id"] == "task-1"
        assert history[0]["seller"] == "alice"
        assert history[0]["product_type"] == "raw_logs"
        assert history[0]["price_usd"] == 0.01
        assert history[0]["title"] == "Test Data"

    def test_idempotent(self, tracker):
        tracker.record_purchase("dup", "seller", "type", 0.01)
        tracker.record_purchase("dup", "seller", "type", 0.01)
        assert tracker.total_purchases() == 1

    def test_timestamp_added(self, tracker):
        tracker.record_purchase("ts", "seller", "type", 0.01)
        history = tracker.get_history()
        assert "timestamp" in history[0]

    def test_persists_to_disk(self, tracker):
        tracker.record_purchase("persist", "seller", "type", 0.01)
        data = json.loads(tracker.state_file.read_text())
        assert len(data["purchases"]) == 1


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    def test_all_history(self, populated_tracker):
        assert len(populated_tracker.get_history()) == 3

    def test_filter_by_product_type(self, populated_tracker):
        logs = populated_tracker.get_history(product_type="raw_logs")
        assert len(logs) == 2

    def test_filter_by_seller(self, populated_tracker):
        from_a = populated_tracker.get_history(seller="seller-a")
        assert len(from_a) == 2

    def test_filter_by_both(self, populated_tracker):
        result = populated_tracker.get_history(product_type="raw_logs", seller="seller-a")
        assert len(result) == 2

    def test_filter_no_results(self, populated_tracker):
        result = populated_tracker.get_history(product_type="nonexistent")
        assert len(result) == 0

    def test_filter_by_hours(self, populated_tracker):
        # All purchases are recent (just created), so hours=1 should include all
        result = populated_tracker.get_history(hours=1)
        assert len(result) == 3

    def test_empty_history(self, tracker):
        assert tracker.get_history() == []


# ---------------------------------------------------------------------------
# daily_spend
# ---------------------------------------------------------------------------


class TestDailySpend:
    def test_spend_today(self, populated_tracker):
        spend = populated_tracker.daily_spend()
        assert spend == pytest.approx(0.07, abs=0.001)  # 0.01 + 0.05 + 0.01

    def test_no_spend(self, tracker):
        assert tracker.daily_spend() == 0.0


# ---------------------------------------------------------------------------
# needs_product
# ---------------------------------------------------------------------------


class TestNeedsProduct:
    def test_needs_unknown_product(self, tracker):
        assert tracker.needs_product("soul_profiles") is True

    def test_doesnt_need_recent_product(self, populated_tracker):
        # raw_logs were just purchased, so within 2h window
        assert populated_tracker.needs_product("raw_logs") is False

    def test_needs_old_product(self, tracker):
        # No recent purchases → needs everything
        assert tracker.needs_product("raw_logs", max_age_hours=0.001) is True


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_counts(self, populated_tracker):
        summary = populated_tracker.summary()
        assert summary["total_purchases"] == 3
        assert summary["by_type"]["raw_logs"] == 2
        assert summary["by_type"]["skill_profiles"] == 1

    def test_summary_empty(self, tracker):
        summary = tracker.summary()
        assert summary["total_purchases"] == 0
        assert summary["by_type"] == {}

    def test_summary_daily_spend(self, populated_tracker):
        summary = populated_tracker.summary()
        assert summary["daily_spend_usd"] == pytest.approx(0.07, abs=0.001)
