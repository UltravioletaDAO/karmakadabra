"""
Tests for lib/context_bridge.py — Acontext Context Server Bridge

Covers:
  - AcontextBridge construction
  - ingest_task_result (success, non-200, connection error)
  - retrieve_worker_context (success, empty, error)
  - retrieve_similar_tasks (success, empty, error)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from lib.context_bridge import AcontextBridge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bridge():
    return AcontextBridge(acontext_url="http://localhost:8000")


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_default_url(self):
        bridge = AcontextBridge()
        assert bridge.url == "http://localhost:8000"

    def test_custom_url(self):
        bridge = AcontextBridge(acontext_url="http://custom:9000")
        assert bridge.url == "http://custom:9000"

    def test_headers(self, bridge):
        assert bridge.headers == {"Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# ingest_task_result
# ---------------------------------------------------------------------------


class TestIngestTaskResult:
    @patch("lib.context_bridge.requests.post")
    def test_success(self, mock_post, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "ctx-1"}
        mock_post.return_value = mock_resp

        result = bridge.ingest_task_result("t1", "0xABC", {"score": 85}, "Good work")
        assert result == {"id": "ctx-1"}
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["type"] == "task_result"
        assert payload["task_id"] == "t1"
        assert payload["worker_wallet"] == "0xABC"

    @patch("lib.context_bridge.requests.post")
    def test_201_success(self, mock_post, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "ctx-2"}
        mock_post.return_value = mock_resp

        result = bridge.ingest_task_result("t2", "0xDEF", {}, "")
        assert result == {"id": "ctx-2"}

    @patch("lib.context_bridge.requests.post")
    def test_non_200_returns_none(self, mock_post, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        result = bridge.ingest_task_result("t3", "0x", {}, "")
        assert result is None

    @patch("lib.context_bridge.requests.post")
    def test_connection_error(self, mock_post, bridge):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")
        result = bridge.ingest_task_result("t4", "0x", {}, "")
        assert result is None

    @patch("lib.context_bridge.requests.post")
    def test_timeout_error(self, mock_post, bridge):
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("timeout")
        result = bridge.ingest_task_result("t5", "0x", {}, "")
        assert result is None


# ---------------------------------------------------------------------------
# retrieve_worker_context
# ---------------------------------------------------------------------------


class TestRetrieveWorkerContext:
    @patch("lib.context_bridge.requests.get")
    def test_success(self, mock_get, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"task": "t1", "quality": 4.5}]}
        mock_get.return_value = mock_resp

        results = bridge.retrieve_worker_context("0xABC")
        assert len(results) == 1
        assert results[0]["task"] == "t1"

    @patch("lib.context_bridge.requests.get")
    def test_empty_results(self, mock_get, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_get.return_value = mock_resp

        results = bridge.retrieve_worker_context("0xUNKNOWN")
        assert results == []

    @patch("lib.context_bridge.requests.get")
    def test_non_200(self, mock_get, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        results = bridge.retrieve_worker_context("0x")
        assert results == []

    @patch("lib.context_bridge.requests.get")
    def test_connection_error(self, mock_get, bridge):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        results = bridge.retrieve_worker_context("0x")
        assert results == []


# ---------------------------------------------------------------------------
# retrieve_similar_tasks
# ---------------------------------------------------------------------------


class TestRetrieveSimilarTasks:
    @patch("lib.context_bridge.requests.post")
    def test_success(self, mock_post, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"matches": [
            {"task_id": "t1", "score": 0.95},
            {"task_id": "t2", "score": 0.80},
        ]}
        mock_post.return_value = mock_resp

        matches = bridge.retrieve_similar_tasks("Build a Python API")
        assert len(matches) == 2
        assert matches[0]["score"] == 0.95

    @patch("lib.context_bridge.requests.post")
    def test_no_matches(self, mock_post, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"matches": []}
        mock_post.return_value = mock_resp

        matches = bridge.retrieve_similar_tasks("Very unique task")
        assert matches == []

    @patch("lib.context_bridge.requests.post")
    def test_non_200(self, mock_post, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        matches = bridge.retrieve_similar_tasks("test")
        assert matches == []

    @patch("lib.context_bridge.requests.post")
    def test_connection_error(self, mock_post, bridge):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        matches = bridge.retrieve_similar_tasks("test")
        assert matches == []

    @patch("lib.context_bridge.requests.post")
    def test_payload_format(self, mock_post, bridge):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"matches": []}
        mock_post.return_value = mock_resp

        bridge.retrieve_similar_tasks("Analyze data")
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["query"] == "Analyze data"
        assert payload["type"] == "task_result"
