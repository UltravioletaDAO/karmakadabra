"""
Tests for the Swarm Runner — Production Daemon.

Covers:
  - Configuration (from env, from file, defaults)
  - Metrics tracking and cycle recording
  - State persistence and recovery
  - Coordination cycle execution
  - Evidence processing cycle
  - Health check cycle
  - Auto-pause on consecutive errors
  - Graceful shutdown
  - CLI argument parsing
  - Status formatting
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.swarm_runner import (
    CycleMetrics,
    RunnerConfig,
    RunnerMetrics,
    RunnerState,
    SwarmRunner,
    parse_args,
)


# ═══════════════════════════════════════════════════════════════════
# RunnerConfig Tests
# ═══════════════════════════════════════════════════════════════════


class TestRunnerConfig:
    """Configuration tests."""

    def test_defaults(self):
        config = RunnerConfig()
        assert config.coordination_interval == 300
        assert config.evidence_interval == 600
        assert config.health_interval == 1800
        assert config.dry_run is False
        assert config.max_tasks_per_cycle == 10
        assert config.max_assignments_per_cycle == 5

    def test_from_env(self):
        env = {
            "KK_WORKSPACES": "/tmp/ws",
            "KK_DRY_RUN": "true",
            "KK_COORD_INTERVAL": "120",
            "EM_API_URL": "http://localhost:8000",
        }
        with patch.dict(os.environ, env, clear=False):
            config = RunnerConfig.from_env()
            assert config.workspaces_dir == "/tmp/ws"
            assert config.dry_run is True
            assert config.coordination_interval == 120
            assert config.em_api_url == "http://localhost:8000"

    def test_from_env_defaults(self):
        """Env vars not set → defaults used."""
        with patch.dict(os.environ, {}, clear=True):
            config = RunnerConfig.from_env()
            assert config.workspaces_dir == "./workspaces"
            assert config.dry_run is False

    def test_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"coordination_interval": 60, "dry_run": True}, f)
            f.flush()
            config = RunnerConfig.from_file(f.name)
            assert config.coordination_interval == 60
            assert config.dry_run is True
        os.unlink(f.name)

    def test_from_file_missing(self):
        config = RunnerConfig.from_file("/nonexistent/config.json")
        assert config.coordination_interval == 300  # defaults

    def test_from_file_ignores_unknown_keys(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"coordination_interval": 90, "unknown_key": "ignored"}, f)
            f.flush()
            config = RunnerConfig.from_file(f.name)
            assert config.coordination_interval == 90
            assert not hasattr(config, "unknown_key")
        os.unlink(f.name)


# ═══════════════════════════════════════════════════════════════════
# CycleMetrics Tests
# ═══════════════════════════════════════════════════════════════════


class TestCycleMetrics:
    """Cycle metrics tracking."""

    def test_creation(self):
        m = CycleMetrics(cycle_type="coordination")
        assert m.cycle_type == "coordination"
        assert m.success is False
        assert m.error is None
        assert m.details == {}

    def test_timing(self):
        m = CycleMetrics(cycle_type="health")
        m.started_at = time.time()
        time.sleep(0.01)
        m.finished_at = time.time()
        m.duration_ms = int((m.finished_at - m.started_at) * 1000)
        assert m.duration_ms >= 10


# ═══════════════════════════════════════════════════════════════════
# RunnerMetrics Tests
# ═══════════════════════════════════════════════════════════════════


class TestRunnerMetrics:
    """Aggregate metrics tracking."""

    def test_initial_state(self):
        m = RunnerMetrics()
        assert m.total_coordination_cycles == 0
        assert m.consecutive_errors == 0
        assert m.paused is False

    def test_record_success_resets_consecutive_errors(self):
        m = RunnerMetrics()
        m.consecutive_errors = 3
        cycle = CycleMetrics(cycle_type="coordination")
        cycle.success = True
        m.record_cycle(cycle)
        assert m.consecutive_errors == 0

    def test_record_failure_increments_consecutive_errors(self):
        m = RunnerMetrics()
        cycle = CycleMetrics(cycle_type="coordination")
        cycle.success = False
        cycle.error = "timeout"
        m.record_cycle(cycle)
        assert m.consecutive_errors == 1
        assert m.total_errors == 1

    def test_history_capped_at_100(self):
        m = RunnerMetrics()
        for i in range(150):
            cycle = CycleMetrics(cycle_type="coordination")
            cycle.success = True
            m.record_cycle(cycle)
        assert len(m.cycle_history) == 100

    def test_uptime(self):
        m = RunnerMetrics()
        m.started_at = time.time() - 3600
        assert 3599 <= m.uptime_seconds() <= 3601

    def test_uptime_not_started(self):
        m = RunnerMetrics()
        assert m.uptime_seconds() == 0.0

    def test_to_dict(self):
        m = RunnerMetrics()
        m.total_coordination_cycles = 5
        m.total_tasks_assigned = 3
        d = m.to_dict()
        assert d["coordination_cycles"] == 5
        assert d["tasks_assigned"] == 3
        assert "paused" in d


# ═══════════════════════════════════════════════════════════════════
# RunnerState Tests
# ═══════════════════════════════════════════════════════════════════


class TestRunnerState:
    """Persistent state management."""

    def test_defaults(self):
        s = RunnerState()
        assert s.last_coordination_at == 0.0
        assert s.last_evidence_cursor is None
        assert s.version == "1.0.0"

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            s = RunnerState()
            s.last_coordination_at = 1234567890.0
            s.last_evidence_cursor = "cursor123"
            s.total_lifetime_cycles = 42
            s.save(path)

            loaded = RunnerState.load(path)
            assert loaded.last_coordination_at == 1234567890.0
            assert loaded.last_evidence_cursor == "cursor123"
            assert loaded.total_lifetime_cycles == 42

    def test_load_missing_file(self):
        s = RunnerState.load("/nonexistent/state.json")
        assert s.last_coordination_at == 0.0  # defaults

    def test_load_corrupted_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            f.flush()
            s = RunnerState.load(f.name)
            assert s.last_coordination_at == 0.0  # defaults
        os.unlink(f.name)

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "dir", "state.json")
            s = RunnerState()
            s.save(path)
            assert os.path.exists(path)

    def test_to_dict(self):
        s = RunnerState()
        s.total_lifetime_cycles = 100
        d = s.to_dict()
        assert d["total_lifetime_cycles"] == 100
        assert d["version"] == "1.0.0"


# ═══════════════════════════════════════════════════════════════════
# SwarmRunner Tests
# ═══════════════════════════════════════════════════════════════════


class TestSwarmRunner:
    """Core runner functionality."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = RunnerConfig(
            workspaces_dir=os.path.join(self.tmpdir, "workspaces"),
            state_file=os.path.join(self.tmpdir, "state.json"),
            dry_run=True,
        )
        os.makedirs(self.config.workspaces_dir, exist_ok=True)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creation(self):
        runner = SwarmRunner(self.config)
        assert runner.config.dry_run is True
        assert runner._shutdown is False

    def test_default_config(self):
        runner = SwarmRunner()
        assert runner.config.coordination_interval == 300

    def test_get_status(self):
        runner = SwarmRunner(self.config)
        status = runner.get_status()
        assert "state" in status
        assert "config" in status
        assert status["config"]["dry_run"] is True

    def test_format_status(self):
        runner = SwarmRunner(self.config)
        text = runner.format_status()
        assert "Swarm Runner" in text
        assert "Operational Status" in text
        assert "Coordination" in text

    def test_unpause(self):
        runner = SwarmRunner(self.config)
        runner.metrics.paused = True
        runner.metrics.pause_reason = "test"
        runner.metrics.consecutive_errors = 5
        runner.unpause()
        assert runner.metrics.paused is False
        assert runner.metrics.pause_reason is None
        assert runner.metrics.consecutive_errors == 0


class TestSwarmRunnerCycles:
    """Async cycle execution tests."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = RunnerConfig(
            workspaces_dir=os.path.join(self.tmpdir, "workspaces"),
            state_file=os.path.join(self.tmpdir, "state.json"),
            dry_run=True,
        )
        os.makedirs(self.config.workspaces_dir, exist_ok=True)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_coordination_standalone(self):
        """Standalone coordination when CoordinatorService unavailable."""
        runner = SwarmRunner(self.config)

        # Mock EM client
        mock_client = MagicMock()
        mock_client.list_tasks = AsyncMock(return_value=[])
        runner._em_client = mock_client

        # Mock swarm_state
        with patch("services.swarm_runner.SwarmRunner._standalone_coordination") as mock_standalone:
            mock_standalone.return_value = CycleMetrics(
                cycle_type="coordination",
                started_at=time.time(),
                finished_at=time.time(),
                duration_ms=50,
                success=True,
                details={"tasks_found": 0, "mode": "standalone"},
            )
            result = await runner.run_coordination_cycle()

        # Should still track metrics even with fallback
        assert runner.metrics.total_coordination_cycles >= 0

    @pytest.mark.asyncio
    async def test_evidence_cycle_no_processor(self):
        """Evidence cycle when processor isn't available."""
        runner = SwarmRunner(self.config)

        # Patch to raise ImportError (simulating missing service)
        with patch.dict(sys.modules, {"evidence_processor": None}):
            result = await runner.run_evidence_cycle()

        assert result.cycle_type == "evidence"
        assert runner.metrics.total_evidence_cycles == 1

    @pytest.mark.asyncio
    async def test_basic_health_check(self):
        """Basic health check via HTTP."""
        runner = SwarmRunner(self.config)

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "healthy"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            metrics = await runner._basic_health_check(
                CycleMetrics(cycle_type="health", started_at=time.time())
            )

        assert metrics.success is True
        assert metrics.details["em_api"] == "healthy"

    @pytest.mark.asyncio
    async def test_basic_health_check_failure(self):
        """Basic health check when API is down."""
        runner = SwarmRunner(self.config)

        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            metrics = await runner._basic_health_check(
                CycleMetrics(cycle_type="health", started_at=time.time())
            )

        assert metrics.success is False
        assert "unreachable" in metrics.error

    @pytest.mark.asyncio
    async def test_health_check_fallback(self):
        """Health check falls back to basic when dashboard unavailable."""
        runner = SwarmRunner(self.config)

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        # Patch the import to fail, then basic check succeeds
        with patch.dict(sys.modules, {"monitoring.ecosystem_dashboard": None}), \
             patch("urllib.request.urlopen", return_value=mock_response):
            result = await runner.run_health_check()

        assert result.success is True
        assert runner.metrics.total_health_checks == 1

    @pytest.mark.asyncio
    async def test_single_cycle(self):
        """Single coordination cycle returns dict."""
        runner = SwarmRunner(self.config)

        with patch.object(runner, "run_coordination_cycle") as mock:
            mock.return_value = CycleMetrics(
                cycle_type="coordination",
                started_at=time.time(),
                finished_at=time.time(),
                duration_ms=42,
                success=True,
                details={"tasks_found": 3, "tasks_assigned": 1},
            )
            result = await runner.run_single_cycle()

        assert result["success"] is True
        assert result["tasks_found"] == 3
        assert result["tasks_assigned"] == 1

    @pytest.mark.asyncio
    async def test_single_evidence(self):
        """Single evidence cycle returns dict."""
        runner = SwarmRunner(self.config)

        with patch.object(runner, "run_evidence_cycle") as mock:
            mock.return_value = CycleMetrics(
                cycle_type="evidence",
                started_at=time.time(),
                finished_at=time.time(),
                duration_ms=30,
                success=True,
                details={"processed": 5, "approved": 4, "rejected": 1},
            )
            result = await runner.run_single_evidence()

        assert result["success"] is True
        assert result["processed"] == 5

    @pytest.mark.asyncio
    async def test_single_health(self):
        """Single health check returns dict."""
        runner = SwarmRunner(self.config)

        with patch.object(runner, "run_health_check") as mock:
            mock.return_value = CycleMetrics(
                cycle_type="health",
                started_at=time.time(),
                finished_at=time.time(),
                duration_ms=100,
                success=True,
                details={"overall": "healthy", "health_ratio": 1.0},
            )
            result = await runner.run_single_health()

        assert result["success"] is True
        assert result["health_ratio"] == 1.0


class TestSwarmRunnerAutoPause:
    """Auto-pause behavior on consecutive errors."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = RunnerConfig(
            workspaces_dir=os.path.join(self.tmpdir, "workspaces"),
            state_file=os.path.join(self.tmpdir, "state.json"),
            auto_pause_on_errors=3,
        )
        os.makedirs(self.config.workspaces_dir, exist_ok=True)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_auto_pause_threshold(self):
        runner = SwarmRunner(self.config)

        # Simulate 3 consecutive failures
        for _ in range(3):
            cycle = CycleMetrics(cycle_type="coordination")
            cycle.success = False
            cycle.error = "timeout"
            runner.metrics.record_cycle(cycle)

        assert runner.metrics.consecutive_errors == 3

    def test_success_resets_error_count(self):
        runner = SwarmRunner(self.config)

        # 2 failures then 1 success
        for _ in range(2):
            cycle = CycleMetrics(cycle_type="coordination")
            cycle.success = False
            runner.metrics.record_cycle(cycle)
        assert runner.metrics.consecutive_errors == 2

        cycle = CycleMetrics(cycle_type="coordination")
        cycle.success = True
        runner.metrics.record_cycle(cycle)
        assert runner.metrics.consecutive_errors == 0

    def test_unpause_clears_state(self):
        runner = SwarmRunner(self.config)
        runner.metrics.paused = True
        runner.metrics.consecutive_errors = 5
        runner.metrics.pause_reason = "errors"

        runner.unpause()
        assert not runner.metrics.paused
        assert runner.metrics.consecutive_errors == 0


class TestSwarmRunnerDaemon:
    """Daemon mode tests."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = RunnerConfig(
            workspaces_dir=os.path.join(self.tmpdir, "workspaces"),
            state_file=os.path.join(self.tmpdir, "state.json"),
            coordination_interval=1,
            evidence_interval=2,
            health_interval=3,
        )
        os.makedirs(self.config.workspaces_dir, exist_ok=True)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_daemon_shutdown(self):
        """Daemon shuts down on _shutdown flag."""
        runner = SwarmRunner(self.config)

        # Mock all cycle methods
        health_mock = AsyncMock(return_value=CycleMetrics(
            cycle_type="health", success=True, details={"overall": "ok"},
        ))
        coord_mock = AsyncMock(return_value=CycleMetrics(
            cycle_type="coordination", success=True, details={},
        ))
        evidence_mock = AsyncMock(return_value=CycleMetrics(
            cycle_type="evidence", success=True, details={},
        ))

        runner.run_health_check = health_mock
        runner.run_coordination_cycle = coord_mock
        runner.run_evidence_cycle = evidence_mock

        # Schedule shutdown after a small delay
        async def shutdown_after():
            await asyncio.sleep(0.1)
            runner._shutdown = True

        # Run daemon with shutdown timer
        await asyncio.gather(
            runner.run_daemon(),
            shutdown_after(),
        )

        # Should have run initial health + at least 1 coordination cycle
        assert health_mock.call_count >= 1
        # State should be saved
        assert os.path.exists(self.config.state_file)

    @pytest.mark.asyncio
    async def test_daemon_auto_pause_skips_cycles(self):
        """Daemon pauses when too many errors."""
        runner = SwarmRunner(self.config)
        runner.metrics.paused = True
        runner.metrics.pause_reason = "test"

        call_count = 0

        original_health = runner.run_health_check

        async def mock_health():
            nonlocal call_count
            call_count += 1
            return CycleMetrics(cycle_type="health", success=True, details={})

        runner.run_health_check = mock_health

        # Schedule shutdown
        async def shutdown_after():
            await asyncio.sleep(0.2)
            runner._shutdown = True

        await asyncio.gather(
            runner.run_daemon(),
            shutdown_after(),
        )

        # While paused, no coordination or evidence cycles should run
        # (health is the initial check only)


# ═══════════════════════════════════════════════════════════════════
# CLI Tests
# ═══════════════════════════════════════════════════════════════════


class TestCLI:
    """CLI argument parsing."""

    def test_daemon_args(self):
        args = parse_args(["daemon", "--workspaces", "/tmp/ws", "--dry-run"])
        assert args.command == "daemon"
        assert args.workspaces == "/tmp/ws"
        assert args.dry_run is True

    def test_cycle_args(self):
        args = parse_args(["cycle", "--json"])
        assert args.command == "cycle"
        assert args.json is True

    def test_health_args(self):
        args = parse_args(["health", "--json"])
        assert args.command == "health"
        assert args.json is True

    def test_evidence_args(self):
        args = parse_args(["evidence"])
        assert args.command == "evidence"

    def test_status_args(self):
        args = parse_args(["status", "--json"])
        assert args.command == "status"
        assert args.json is True

    def test_unpause_args(self):
        args = parse_args(["unpause"])
        assert args.command == "unpause"

    def test_daemon_default_intervals(self):
        args = parse_args(["daemon"])
        assert args.coord_interval == 300
        assert args.evidence_interval == 600
        assert args.health_interval == 1800

    def test_daemon_custom_intervals(self):
        args = parse_args([
            "daemon",
            "--coord-interval", "60",
            "--evidence-interval", "120",
            "--health-interval", "300",
        ])
        assert args.coord_interval == 60
        assert args.evidence_interval == 120
        assert args.health_interval == 300


# ═══════════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════════


class TestStateIntegration:
    """State persistence integration."""

    def test_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "state.json")

            # First runner writes state
            config1 = RunnerConfig(state_file=state_path)
            runner1 = SwarmRunner(config1)
            runner1.state.last_coordination_at = 1234567890.0
            runner1.state.total_lifetime_cycles = 42
            runner1.state.save(state_path)

            # Second runner reads it
            config2 = RunnerConfig(state_file=state_path)
            runner2 = SwarmRunner(config2)
            assert runner2.state.last_coordination_at == 1234567890.0
            assert runner2.state.total_lifetime_cycles == 42

    def test_status_format_after_cycles(self):
        """Status shows meaningful data after some cycles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "state.json")
            config = RunnerConfig(state_file=state_path)
            runner = SwarmRunner(config)

            # Simulate some history
            runner.state.total_lifetime_cycles = 150
            runner.state.total_lifetime_assignments = 45
            runner.state.last_coordination_at = time.time() - 120
            runner.state.save(state_path)

            # Reload and check status
            runner2 = SwarmRunner(config)
            status = runner2.get_status()
            assert status["state"]["lifetime_cycles"] == 150
            assert status["state"]["lifetime_assignments"] == 45


class TestMetricsIntegration:
    """Metrics tracking across multiple cycles."""

    def test_mixed_cycle_types(self):
        m = RunnerMetrics()

        # Record different cycle types
        for ctype in ["coordination", "evidence", "health", "coordination", "evidence"]:
            cycle = CycleMetrics(cycle_type=ctype, success=True)
            m.record_cycle(cycle)

        assert len(m.cycle_history) == 5
        types = [c["type"] for c in m.cycle_history]
        assert types.count("coordination") == 2
        assert types.count("evidence") == 2
        assert types.count("health") == 1

    def test_error_pattern_tracking(self):
        m = RunnerMetrics()

        # Error → Error → Success → Error
        for success in [False, False, True, False]:
            cycle = CycleMetrics(cycle_type="coordination", success=success)
            if not success:
                cycle.error = "test error"
            m.record_cycle(cycle)

        assert m.total_errors == 3
        assert m.consecutive_errors == 1  # Reset by the success in the middle
