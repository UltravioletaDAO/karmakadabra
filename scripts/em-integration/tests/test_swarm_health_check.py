"""
Tests for the swarm health check tool.

Tests the health check logic with mocked HTTP calls.
The live integration tests (marked with @live) actually hit the EM API.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.swarm_health_check import (
    CheckResult,
    check_coordinator_matching,
    check_em_api_health,
    check_em_auth_nonce,
    check_lifecycle_state,
    check_module_imports,
    check_reputation_data,
    check_task_availability,
    check_completed_tasks,
    check_test_count,
    format_report,
    run_health_check,
)


# ---------------------------------------------------------------------------
# CheckResult
# ---------------------------------------------------------------------------


class TestCheckResult:
    def test_passing_result(self):
        r = CheckResult("test", True, "ok")
        assert r.passed
        assert "✅" in str(r)

    def test_failing_result(self):
        r = CheckResult("test", False, "bad")
        assert not r.passed
        assert "❌" in str(r)

    def test_fixable_result(self):
        r = CheckResult("test", False, "fixable", fixable=True)
        assert not r.passed
        assert "🔧" in str(r)

    def test_to_dict(self):
        r = CheckResult("test", True, "ok", details={"x": 1})
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["passed"] is True
        assert d["details"]["x"] == 1


# ---------------------------------------------------------------------------
# Mocked API checks
# ---------------------------------------------------------------------------


class TestEMAPIHealth:
    @patch("services.swarm_health_check._http_get")
    def test_healthy(self, mock_get):
        mock_get.return_value = {
            "status": "healthy",
            "uptime_seconds": 3600,
            "components": {
                "database": {"status": "healthy"},
                "redis": {"status": "healthy"},
            },
        }
        result = check_em_api_health()
        assert result.passed
        assert "Healthy" in result.message

    @patch("services.swarm_health_check._http_get")
    def test_degraded(self, mock_get):
        mock_get.return_value = {
            "status": "degraded",
            "uptime_seconds": 100,
            "components": {
                "database": {"status": "unhealthy"},
                "redis": {"status": "healthy"},
            },
        }
        result = check_em_api_health()
        assert not result.passed
        assert "Degraded" in result.message

    @patch("services.swarm_health_check._http_get")
    def test_unreachable(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        result = check_em_api_health()
        assert not result.passed
        assert "Unreachable" in result.message


class TestAuthNonce:
    @patch("services.swarm_health_check._http_get")
    def test_valid_nonce(self, mock_get):
        mock_get.return_value = {"nonce": "abc123def456xyz789"}
        result = check_em_auth_nonce()
        assert result.passed

    @patch("services.swarm_health_check._http_get")
    def test_empty_nonce(self, mock_get):
        mock_get.return_value = {"nonce": ""}
        result = check_em_auth_nonce()
        assert not result.passed

    @patch("services.swarm_health_check._http_get")
    def test_error(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        result = check_em_auth_nonce()
        assert not result.passed


class TestTaskAvailability:
    @patch("services.swarm_health_check._http_get")
    def test_tasks_available(self, mock_get):
        mock_get.return_value = {
            "tasks": [{"title": "Task 1"}, {"title": "Task 2"}],
            "total": 2,
        }
        result = check_task_availability()
        assert result.passed
        assert "2 published" in result.message

    @patch("services.swarm_health_check._http_get")
    def test_no_tasks(self, mock_get):
        mock_get.return_value = {"tasks": [], "total": 0}
        result = check_task_availability()
        assert result.passed  # Zero tasks is still valid
        assert "poll for new" in result.message

    @patch("services.swarm_health_check._http_get")
    def test_endpoint_error(self, mock_get):
        mock_get.side_effect = Exception("500")
        result = check_task_availability()
        assert not result.passed


class TestCompletedTasks:
    @patch("services.swarm_health_check._http_get")
    def test_has_history(self, mock_get):
        mock_get.return_value = {"tasks": [], "total": 189}
        result = check_completed_tasks()
        assert result.passed
        assert "189" in result.message

    @patch("services.swarm_health_check._http_get")
    def test_no_history(self, mock_get):
        mock_get.return_value = {"tasks": [], "total": 0}
        result = check_completed_tasks()
        assert not result.passed


# ---------------------------------------------------------------------------
# Local checks
# ---------------------------------------------------------------------------


class TestModuleImports:
    def test_modules_import(self):
        result = check_module_imports()
        # Should pass because all KK modules are available
        assert result.passed
        assert "14" in result.message


class TestCoordinatorMatching:
    def test_matching_works(self):
        result = check_coordinator_matching()
        assert result.passed
        assert "sample score" in result.message


class TestLifecycleState:
    def test_reports_state(self):
        result = check_lifecycle_state()
        # Either "exists with N agents" or "will be created"
        assert result.passed


class TestReputationData:
    def test_reports_status(self):
        result = check_reputation_data()
        assert result.passed


class TestTestCount:
    def test_enough_tests(self):
        result = check_test_count()
        assert result.passed
        assert "29" in result.message or "test files" in result.message


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_all_pass(self):
        results = [
            CheckResult("A", True, "ok"),
            CheckResult("B", True, "good"),
        ]
        report = format_report(results)
        assert "ALL CHECKS PASSED" in report
        assert "2 passed" in report

    def test_some_fail(self):
        results = [
            CheckResult("A", True, "ok"),
            CheckResult("B", False, "bad"),
        ]
        report = format_report(results)
        assert "1 failed" in report
        assert "critical" in report

    def test_fixable_fail(self):
        results = [
            CheckResult("A", True, "ok"),
            CheckResult("B", False, "fixable", fixable=True),
        ]
        report = format_report(results)
        assert "auto-fixable" in report


# ---------------------------------------------------------------------------
# Live integration tests (hit actual EM API)
# ---------------------------------------------------------------------------

live = pytest.mark.skipif(
    not __import__("os").environ.get("KK_LIVE_TESTS"),
    reason="Set KK_LIVE_TESTS=1 to run live API tests",
)


@live
class TestLiveHealthCheck:
    def test_full_health_check(self):
        """Run full health check against live API."""
        results = run_health_check(quick=False)
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        # At minimum, API should be reachable
        assert passed >= 4, f"Only {passed}/{total} passed"

    def test_quick_health_check(self):
        """Run quick health check (API only)."""
        results = run_health_check(quick=True)
        assert len(results) == 4  # 4 API checks
        assert all(r.passed for r in results)
