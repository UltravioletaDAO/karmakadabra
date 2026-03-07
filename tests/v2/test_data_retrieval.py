"""
Tests for data_retrieval.py — Data Download Service

Covers:
  - Product classification (title → type + subdir)
  - Seller inference (title → agent name)
  - URL extraction from text
  - State persistence (load/save, dedup)
  - check_and_retrieve_all (all 3 strategies)
  - Edge cases: corrupted state, no completed tasks, failed strategies
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.data_retrieval import (
    PRODUCT_ROUTING,
    _classify_product,
    _extract_url,
    _infer_seller,
    _load_state,
    _save_state,
    check_and_retrieve_all,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "purchases").mkdir()
    return data


@pytest.fixture
def mock_em_client():
    client = MagicMock()
    client.agent = MagicMock()
    client.agent.wallet_address = "0xBUYER"
    client.close = AsyncMock()
    client.list_tasks = AsyncMock(return_value=[])
    client.get_submissions = AsyncMock(return_value=[])
    client.get_task = AsyncMock(return_value={})
    return client


# ---------------------------------------------------------------------------
# Product Classification Tests
# ---------------------------------------------------------------------------


class TestClassifyProduct:
    def test_raw_logs(self):
        result = _classify_product("[KK Data] Raw Chat Logs")
        assert result["type"] == "raw_logs"

    def test_skill_profiles(self):
        result = _classify_product("[KK Data] Enriched Skill Profiles")
        assert result["type"] == "skill_profiles"

    def test_voice_profiles(self):
        result = _classify_product("[KK Data] Voice and Personality Profiles")
        assert result["type"] == "voice_profiles"

    def test_soul_profiles(self):
        result = _classify_product("[KK Data] Complete Soul Profiles")
        assert result["type"] == "soul_profiles"

    def test_personality(self):
        result = _classify_product("Personality analysis")
        assert result["type"] == "voice_profiles"

    def test_unknown_title(self):
        result = _classify_product("Random unrelated task")
        assert result["type"] == "unknown"

    def test_case_insensitive(self):
        result = _classify_product("RAW CHAT LOG DATA")
        assert result["type"] == "raw_logs"

    def test_soul_before_skill(self):
        """Soul has higher priority than skill in routing."""
        result = _classify_product("Complete Profile (soul + skill)")
        assert result["type"] == "soul_profiles"


# ---------------------------------------------------------------------------
# Seller Inference Tests
# ---------------------------------------------------------------------------


class TestInferSeller:
    def test_raw_logs_seller(self):
        assert _infer_seller("Raw Chat Logs") == "kk-karma-hello"

    def test_skill_seller(self):
        assert _infer_seller("Enriched Skill Profiles") == "kk-skill-extractor"

    def test_voice_seller(self):
        assert _infer_seller("Voice Analysis") == "kk-voice-extractor"

    def test_personality_seller(self):
        assert _infer_seller("Personality Profiles") == "kk-voice-extractor"

    def test_soul_seller(self):
        assert _infer_seller("Complete Soul Profile") == "kk-soul-extractor"

    def test_unknown_seller(self):
        assert _infer_seller("Random task") == ""


# ---------------------------------------------------------------------------
# URL Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractUrl:
    def test_simple_url(self):
        assert _extract_url("Download from https://example.com/file.json") == "https://example.com/file.json"

    def test_url_with_trailing_period(self):
        url = _extract_url("Data available at https://s3.amazonaws.com/bucket/key.json.")
        assert url.endswith(".json")

    def test_url_with_quotes(self):
        url = _extract_url('"https://example.com/data"')
        assert url == "https://example.com/data"

    def test_no_url(self):
        assert _extract_url("No URL here, just text") is None

    def test_http_url(self):
        url = _extract_url("Available at http://localhost:8080/data")
        assert url == "http://localhost:8080/data"

    def test_multiple_urls_returns_first(self):
        url = _extract_url("https://first.com https://second.com")
        assert url == "https://first.com"


# ---------------------------------------------------------------------------
# State Persistence Tests
# ---------------------------------------------------------------------------


class TestStatePersistence:
    def test_load_empty_state(self, tmp_path):
        state = _load_state(tmp_path / "nonexistent.json")
        assert state == {"retrieved": {}}

    def test_save_and_load(self, tmp_path):
        state_file = tmp_path / ".retrieval_state.json"
        state = {
            "retrieved": {
                "task-001": {"title": "Test", "product_type": "raw_logs"},
            }
        }
        _save_state(state_file, state)
        loaded = _load_state(state_file)
        assert loaded["retrieved"]["task-001"]["title"] == "Test"

    def test_load_corrupted_file(self, tmp_path):
        state_file = tmp_path / ".retrieval_state.json"
        state_file.write_text("NOT JSON")
        state = _load_state(state_file)
        assert state == {"retrieved": {}}

    def test_save_creates_parent_dirs(self, tmp_path):
        state_file = tmp_path / "deep" / "nested" / "state.json"
        _save_state(state_file, {"retrieved": {}})
        assert state_file.exists()


# ---------------------------------------------------------------------------
# check_and_retrieve_all Tests
# ---------------------------------------------------------------------------


class TestCheckAndRetrieveAll:
    @pytest.mark.asyncio
    async def test_no_completed_tasks(self, mock_em_client, tmp_data):
        mock_em_client.list_tasks = AsyncMock(return_value=[])
        result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")
        assert result == []

    @pytest.mark.asyncio
    async def test_skip_already_retrieved(self, mock_em_client, tmp_data):
        """Tasks already in state are not re-downloaded."""
        # Pre-populate state
        state_file = tmp_data / ".retrieval_state.json"
        state_file.write_text(json.dumps({
            "retrieved": {
                "task-001": {"title": "Already got it"},
            }
        }))

        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-001", "title": "[KK Data] Raw Logs"},
        ])

        result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")
        assert result == []

    @pytest.mark.asyncio
    async def test_strategy2_submission_url(self, mock_em_client, tmp_data):
        """Strategy 2: parse delivery_url from submission evidence."""
        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-002", "title": "[KK Data] Raw Chat Logs"},
        ])
        mock_em_client.get_submissions = AsyncMock(return_value=[
            {
                "evidence": {
                    "json_response": {
                        "delivery_url": "https://s3.example.com/data.json",
                        "status": "delivered",
                    }
                }
            }
        ])

        test_data = [{"user": "test", "message": "hello"}]
        with patch("services.data_retrieval._download_from_s3", return_value=None), \
             patch("services.data_retrieval._fetch_presigned_url",
                    new_callable=AsyncMock, return_value=test_data):
            result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")

        assert len(result) == 1
        assert result[0]["product_type"] == "raw_logs"
        # File should exist
        output_file = Path(result[0]["file"])
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_strategy1_s3_direct(self, mock_em_client, tmp_data):
        """Strategy 1: S3 direct download succeeds."""
        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-003", "title": "[KK Data] Raw Chat Logs"},
        ])
        test_data = [{"user": "alice", "message": "hello world"}]

        with patch("services.data_retrieval._download_from_s3", return_value=test_data):
            result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")

        assert len(result) == 1
        assert result[0]["product_type"] == "raw_logs"

    @pytest.mark.asyncio
    async def test_strategy3_task_notes(self, mock_em_client, tmp_data):
        """Strategy 3: parse URL from task notes."""
        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-004", "title": "[KK Data] Skill Profiles"},
        ])
        mock_em_client.get_submissions = AsyncMock(return_value=[])
        mock_em_client.get_task = AsyncMock(return_value={
            "approval_notes": "Data at https://s3.example.com/skills.json approved."
        })
        test_data = {"profiles": [{"user": "alice", "skills": ["python"]}]}

        with patch("services.data_retrieval._download_from_s3", return_value=None), \
             patch("services.data_retrieval._fetch_presigned_url",
                    new_callable=AsyncMock, return_value=test_data):
            result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")

        assert len(result) == 1
        assert result[0]["product_type"] == "skill_profiles"

    @pytest.mark.asyncio
    async def test_all_strategies_fail(self, mock_em_client, tmp_data):
        """All strategies fail — task is logged but not in results."""
        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-005", "title": "[KK Data] Raw Chat Logs"},
        ])
        mock_em_client.get_submissions = AsyncMock(return_value=[])
        mock_em_client.get_task = AsyncMock(return_value={})

        with patch("services.data_retrieval._download_from_s3", return_value=None):
            result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")

        assert result == []

    @pytest.mark.asyncio
    async def test_state_saved_on_success(self, mock_em_client, tmp_data):
        """State is persisted after retrieval."""
        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-006", "title": "[KK Data] Raw Logs"},
        ])
        test_data = [{"user": "test", "message": "data"}]

        with patch("services.data_retrieval._download_from_s3", return_value=test_data):
            await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")

        state_file = tmp_data / ".retrieval_state.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert "task-006" in state["retrieved"]

    @pytest.mark.asyncio
    async def test_multiple_tasks_retrieved(self, mock_em_client, tmp_data):
        """Multiple completed tasks retrieved in one call."""
        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-007", "title": "[KK Data] Raw Chat Logs"},
            {"id": "task-008", "title": "[KK Data] Skill Profiles"},
        ])
        test_data = [{"data": "test"}]

        with patch("services.data_retrieval._download_from_s3", return_value=test_data):
            result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_creates_purchases_dir(self, tmp_path):
        """Purchases directory created if not exists."""
        data = tmp_path / "data"
        data.mkdir()
        client = MagicMock()
        client.list_tasks = AsyncMock(return_value=[
            {"id": "task-009", "title": "[KK Data] Raw Logs"},
        ])
        test_data = [{"test": True}]

        with patch("services.data_retrieval._download_from_s3", return_value=test_data):
            result = await check_and_retrieve_all(client, data, "0xBUYER")

        assert (data / "purchases").exists()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_s3_uri_in_submission(self, mock_em_client, tmp_data):
        """S3 URI in submission evidence triggers S3 key download."""
        mock_em_client.list_tasks = AsyncMock(return_value=[
            {"id": "task-010", "title": "[KK Data] Raw Chat Logs"},
        ])
        mock_em_client.get_submissions = AsyncMock(return_value=[
            {
                "evidence": {
                    "json_response": {
                        "s3_key": "kk-karma-hello/deliveries/batch-001.json",
                    }
                }
            }
        ])
        test_data = [{"user": "test", "message": "hello"}]

        with patch("services.data_retrieval._download_from_s3", return_value=None), \
             patch("services.data_retrieval._download_s3_key", return_value=test_data):
            result = await check_and_retrieve_all(mock_em_client, tmp_data, "0xBUYER")

        assert len(result) == 1


# ---------------------------------------------------------------------------
# PRODUCT_ROUTING consistency
# ---------------------------------------------------------------------------


class TestProductRouting:
    def test_routing_has_entries(self):
        assert len(PRODUCT_ROUTING) > 0

    def test_all_entries_have_type_and_subdir(self):
        for keywords, info in PRODUCT_ROUTING:
            assert "type" in info
            assert "subdir" in info
            assert len(keywords) > 0

    def test_routing_covers_supply_chain(self):
        types = [info["type"] for _, info in PRODUCT_ROUTING]
        assert "raw_logs" in types
        assert "skill_profiles" in types
        assert "voice_profiles" in types
        assert "soul_profiles" in types
