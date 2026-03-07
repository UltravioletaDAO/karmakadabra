"""
Tests for services/karma_hello_seller.py — EM Log Sales Service

Covers:
  - PRODUCTS catalog (all product definitions)
  - load_data_stats (aggregated.json, user-stats.json)
  - publish_product (success, budget limit, dry run)
  - Edge cases: missing data files, empty stats, template formatting
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))

from services.karma_hello_seller import (
    PRODUCTS,
    load_data_stats,
    publish_product,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def mock_em_client():
    client = MagicMock()
    client.agent = MagicMock()
    client.agent.name = "kk-karma-hello"
    client.agent.wallet_address = "0xKARMAHELLO"
    client.agent.can_spend = MagicMock(return_value=True)
    client.agent.record_spend = MagicMock()
    client.agent.daily_spent_usd = 0.0
    client.agent.daily_budget_usd = 2.0
    client.publish_task = AsyncMock(return_value={"task": {"id": "pub-1"}})
    client.close = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# PRODUCTS catalog
# ---------------------------------------------------------------------------


class TestProducts:
    def test_all_products_defined(self):
        expected = {"raw_logs", "user_stats", "topic_map", "skill_profile"}
        assert set(PRODUCTS.keys()) == expected

    def test_products_have_required_fields(self):
        for key, product in PRODUCTS.items():
            assert "title" in product, f"{key} missing title"
            assert "description" in product, f"{key} missing description"
            assert "category" in product, f"{key} missing category"
            assert "bounty" in product, f"{key} missing bounty"
            assert isinstance(product["bounty"], (int, float))

    def test_product_prices(self):
        assert PRODUCTS["raw_logs"]["bounty"] == 0.01
        assert PRODUCTS["user_stats"]["bounty"] == 0.03
        assert PRODUCTS["topic_map"]["bounty"] == 0.02
        assert PRODUCTS["skill_profile"]["bounty"] == 0.05

    def test_all_knowledge_access_category(self):
        for key, product in PRODUCTS.items():
            assert product["category"] == "knowledge_access"

    def test_title_templates_have_placeholders(self):
        assert "{date_range}" in PRODUCTS["raw_logs"]["title"]
        assert "{user_count}" in PRODUCTS["user_stats"]["title"]
        assert "{total_dates}" in PRODUCTS["topic_map"]["title"]
        assert "{user_count}" in PRODUCTS["skill_profile"]["title"]


# ---------------------------------------------------------------------------
# load_data_stats
# ---------------------------------------------------------------------------


class TestLoadDataStats:
    def test_empty_dir(self, tmp_data):
        stats = load_data_stats(tmp_data)
        assert stats["total_messages"] == 0
        assert stats["total_dates"] == 0
        assert stats["user_count"] == 0
        assert stats["date_range"] == "unknown"

    def test_with_aggregated(self, tmp_data):
        (tmp_data / "aggregated.json").write_text(json.dumps({
            "stats": {
                "total_messages": 1500,
                "date_count": 12,
                "dates": ["2026-02-01", "2026-02-12"],
            }
        }))
        stats = load_data_stats(tmp_data)
        assert stats["total_messages"] == 1500
        assert stats["total_dates"] == 12
        assert stats["date_range"] == "2026-02-01 to 2026-02-12"

    def test_with_user_stats(self, tmp_data):
        (tmp_data / "user-stats.json").write_text(json.dumps({
            "ranking": [{"username": "a"}, {"username": "b"}, {"username": "c"}]
        }))
        stats = load_data_stats(tmp_data)
        assert stats["user_count"] == 3

    def test_with_all_data(self, tmp_data):
        (tmp_data / "aggregated.json").write_text(json.dumps({
            "stats": {
                "total_messages": 5000,
                "date_count": 30,
                "dates": ["2026-01-01", "2026-01-30"],
            }
        }))
        (tmp_data / "user-stats.json").write_text(json.dumps({
            "ranking": [{"username": f"u{i}"} for i in range(50)]
        }))
        stats = load_data_stats(tmp_data)
        assert stats["total_messages"] == 5000
        assert stats["user_count"] == 50

    def test_no_dates_in_aggregated(self, tmp_data):
        (tmp_data / "aggregated.json").write_text(json.dumps({
            "stats": {"total_messages": 100, "date_count": 0, "dates": []}
        }))
        stats = load_data_stats(tmp_data)
        assert stats["date_range"] == "unknown"

    def test_single_date(self, tmp_data):
        (tmp_data / "aggregated.json").write_text(json.dumps({
            "stats": {"total_messages": 50, "date_count": 1, "dates": ["2026-03-01"]}
        }))
        stats = load_data_stats(tmp_data)
        assert stats["date_range"] == "2026-03-01 to 2026-03-01"


# ---------------------------------------------------------------------------
# publish_product
# ---------------------------------------------------------------------------


class TestPublishProduct:
    @pytest.mark.asyncio
    async def test_publish_success(self, mock_em_client):
        stats = {"total_messages": 1000, "total_dates": 10, "user_count": 50, "date_range": "2026-01-01 to 2026-01-10"}
        product = PRODUCTS["raw_logs"]
        result = await publish_product(mock_em_client, "raw_logs", product, stats)
        assert result is not None
        mock_em_client.publish_task.assert_called_once()
        mock_em_client.agent.record_spend.assert_called_with(0.01)

    @pytest.mark.asyncio
    async def test_publish_dry_run(self, mock_em_client):
        stats = {"total_messages": 100, "total_dates": 5, "user_count": 10, "date_range": "test"}
        product = PRODUCTS["user_stats"]
        result = await publish_product(mock_em_client, "user_stats", product, stats, dry_run=True)
        assert result is None
        mock_em_client.publish_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_over_budget(self, mock_em_client):
        mock_em_client.agent.can_spend.return_value = False
        stats = {"total_messages": 100, "total_dates": 5, "user_count": 10, "date_range": "test"}
        result = await publish_product(mock_em_client, "raw_logs", PRODUCTS["raw_logs"], stats)
        assert result is None
        mock_em_client.publish_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_title_formatting(self, mock_em_client):
        stats = {"total_messages": 500, "total_dates": 7, "user_count": 25, "date_range": "2026-02-01 to 2026-02-07"}
        await publish_product(mock_em_client, "raw_logs", PRODUCTS["raw_logs"], stats)
        call_kwargs = mock_em_client.publish_task.call_args[1]
        assert "2026-02-01 to 2026-02-07" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_each_product_type(self, mock_em_client):
        stats = {"total_messages": 500, "total_dates": 7, "user_count": 25, "date_range": "test range"}
        for key, product in PRODUCTS.items():
            mock_em_client.publish_task.reset_mock()
            result = await publish_product(mock_em_client, key, product, stats)
            assert result is not None, f"Failed to publish {key}"
