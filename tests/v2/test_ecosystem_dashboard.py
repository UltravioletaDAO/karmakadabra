"""
Tests for SwarmHealthDashboard
"""

import json
import time
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from monitoring.ecosystem_dashboard import (
    SwarmHealthDashboard,
    HealthReport,
    HealthStatus,
    ComponentCheck,
    MarketplaceState,
    ChainState,
    SwarmComponentStatus,
    _http_get,
)


class TestComponentCheck(unittest.TestCase):
    """Tests for ComponentCheck data model."""

    def test_healthy_check(self):
        c = ComponentCheck(name="Test", status=HealthStatus.HEALTHY, latency_ms=42.5)
        self.assertTrue(c.is_healthy)
        self.assertIn("✅", str(c))
        self.assertIn("42ms", str(c))

    def test_down_check(self):
        c = ComponentCheck(name="Test", status=HealthStatus.DOWN, error="Connection refused")
        self.assertFalse(c.is_healthy)
        self.assertIn("❌", str(c))
        self.assertIn("Connection refused", str(c))

    def test_degraded_check(self):
        c = ComponentCheck(name="Test", status=HealthStatus.DEGRADED)
        self.assertFalse(c.is_healthy)
        self.assertIn("⚠️", str(c))

    def test_unknown_check(self):
        c = ComponentCheck(name="Test")
        self.assertFalse(c.is_healthy)
        self.assertEqual(c.status, HealthStatus.UNKNOWN)

    def test_with_details(self):
        c = ComponentCheck(name="Test", status=HealthStatus.HEALTHY, details={"key": "value"})
        self.assertEqual(c.details["key"], "value")


class TestMarketplaceState(unittest.TestCase):
    """Tests for MarketplaceState."""

    def test_defaults(self):
        m = MarketplaceState()
        self.assertEqual(m.published_tasks, 0)
        self.assertEqual(m.completed_tasks, 0)
        self.assertEqual(m.total_bounty_published, 0.0)
        self.assertIsInstance(m.networks_active, list)

    def test_populated(self):
        m = MarketplaceState(
            published_tasks=5,
            completed_tasks=189,
            total_bounty_published=2.50,
            total_bounty_completed=47.00,
            networks_active=["base", "polygon"],
            avg_bounty_published=0.50,
            avg_bounty_completed=0.25,
        )
        self.assertEqual(m.published_tasks, 5)
        self.assertEqual(m.completed_tasks, 189)
        self.assertAlmostEqual(m.total_bounty_published, 2.50)


class TestChainState(unittest.TestCase):
    """Tests for ChainState."""

    def test_defaults(self):
        c = ChainState()
        self.assertEqual(c.total_identities, 0)
        self.assertEqual(c.system_agents_found, 0)
        self.assertIsInstance(c.system_agents_missing, list)

    def test_fully_healthy(self):
        c = ChainState(
            total_identities=24,
            system_agents_found=5,
            system_agents_missing=[],
            block_number=42_000_000,
        )
        self.assertEqual(c.system_agents_found, 5)
        self.assertEqual(len(c.system_agents_missing), 0)


class TestHealthReport(unittest.TestCase):
    """Tests for HealthReport."""

    def test_default_report(self):
        r = HealthReport()
        self.assertEqual(r.overall_status, HealthStatus.UNKNOWN)
        self.assertIsNotNone(r.timestamp)
        self.assertIsInstance(r.swarm_components, list)

    def test_summary_output(self):
        r = HealthReport(
            overall_status=HealthStatus.HEALTHY,
            healthy_count=5,
            total_checks=5,
            total_latency_ms=123.4,
            em_api=ComponentCheck(name="EM API", status=HealthStatus.HEALTHY, latency_ms=30),
            em_auth=ComponentCheck(name="EM Auth", status=HealthStatus.HEALTHY, latency_ms=25),
            em_tasks=ComponentCheck(name="EM Tasks", status=HealthStatus.HEALTHY, latency_ms=45),
            base_rpc=ComponentCheck(name="Base RPC", status=HealthStatus.HEALTHY, latency_ms=15),
            erc8004=ComponentCheck(name="ERC-8004", status=HealthStatus.HEALTHY, latency_ms=8),
            marketplace=MarketplaceState(
                published_tasks=5,
                completed_tasks=189,
                total_bounty_published=2.50,
                total_bounty_completed=47.00,
                networks_active=["base", "polygon"],
                categories_seen=["simple_action"],
                avg_bounty_published=0.50,
                avg_bounty_completed=0.25,
            ),
            chain=ChainState(
                total_identities=24,
                system_agents_found=5,
                block_number=42_000_000,
            ),
        )
        
        summary = r.summary()
        self.assertIn("SWARM HEALTH DASHBOARD", summary)
        self.assertIn("HEALTHY", summary)
        self.assertIn("5/5", summary)
        self.assertIn("189", summary)
        self.assertIn("42,000,000", summary)
        self.assertIn("base", summary)

    def test_degraded_summary(self):
        r = HealthReport(
            overall_status=HealthStatus.DEGRADED,
            healthy_count=3,
            total_checks=5,
        )
        summary = r.summary()
        self.assertIn("DEGRADED", summary)
        self.assertIn("3/5", summary)

    def test_summary_with_missing_agents(self):
        r = HealthReport(
            chain=ChainState(
                system_agents_found=3,
                system_agents_missing=["coordinator", "validator"],
            ),
        )
        summary = r.summary()
        self.assertIn("coordinator", summary)
        self.assertIn("validator", summary)

    def test_summary_with_components(self):
        r = HealthReport(
            swarm_components=[
                SwarmComponentStatus(
                    component="Evidence Parser",
                    exists=True,
                    line_count=680,
                    description="AutoJob Bridge",
                ),
                SwarmComponentStatus(
                    component="Missing Module",
                    exists=False,
                    description="Not implemented",
                ),
            ],
        )
        summary = r.summary()
        self.assertIn("Evidence Parser", summary)
        self.assertIn("680 lines", summary)
        self.assertIn("❌", summary)


class TestSwarmHealthDashboard(unittest.TestCase):
    """Tests for the main dashboard class."""

    def setUp(self):
        self.dashboard = SwarmHealthDashboard()

    @patch("monitoring.ecosystem_dashboard._http_get")
    def test_check_em_health_healthy(self, mock_get):
        mock_get.return_value = (
            {
                "status": "healthy",
                "components": {
                    "database": {"status": "healthy"},
                    "blockchain": {"status": "healthy"},
                    "storage": {"status": "healthy"},
                    "facilitator": {"status": "healthy"},
                    "payment": {"status": "healthy"},
                },
            },
            45.0,
        )
        
        result = self.dashboard.check_em_health()
        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertAlmostEqual(result.latency_ms, 45.0)
        self.assertEqual(len(result.details), 5)

    @patch("monitoring.ecosystem_dashboard._http_get")
    def test_check_em_health_degraded(self, mock_get):
        mock_get.return_value = (
            {
                "status": "degraded",
                "components": {
                    "database": {"status": "healthy"},
                    "blockchain": {"status": "down"},
                },
            },
            50.0,
        )
        
        result = self.dashboard.check_em_health()
        self.assertEqual(result.status, HealthStatus.DEGRADED)

    @patch("monitoring.ecosystem_dashboard._http_get")
    def test_check_em_health_down(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        
        result = self.dashboard.check_em_health()
        self.assertEqual(result.status, HealthStatus.DOWN)
        self.assertIn("Connection refused", result.error)

    @patch("monitoring.ecosystem_dashboard._http_get")
    def test_check_em_auth(self, mock_get):
        mock_get.return_value = (
            {"nonce": "abc123def456", "expires_at": "2026-02-28T01:05:00Z"},
            20.0,
        )
        
        result = self.dashboard.check_em_auth()
        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertEqual(result.details["nonce_length"], 12)

    @patch("monitoring.ecosystem_dashboard._http_get")
    def test_check_em_auth_empty_nonce(self, mock_get):
        mock_get.return_value = ({"nonce": ""}, 20.0)
        
        result = self.dashboard.check_em_auth()
        self.assertEqual(result.status, HealthStatus.DEGRADED)

    @patch("monitoring.ecosystem_dashboard._http_get")
    def test_check_em_tasks(self, mock_get):
        # First call: published, second call: completed
        mock_get.side_effect = [
            (
                {
                    "tasks": [
                        {"bounty_usd": 0.50, "payment_network": "base", "category": "simple_action"},
                        {"bounty_usd": 0.30, "payment_network": "polygon", "category": "data_collection"},
                    ],
                    "total": 2,
                },
                30.0,
            ),
            (
                {
                    "tasks": [
                        {"bounty_usd": 0.10, "payment_network": "base", "category": "simple_action"},
                    ],
                    "total": 189,
                },
                25.0,
            ),
        ]
        
        check, marketplace = self.dashboard.check_em_tasks()
        self.assertEqual(check.status, HealthStatus.HEALTHY)
        self.assertEqual(marketplace.published_tasks, 2)
        self.assertEqual(marketplace.completed_tasks, 189)
        self.assertAlmostEqual(marketplace.total_bounty_published, 0.80)
        self.assertIn("base", marketplace.networks_active)
        self.assertIn("polygon", marketplace.networks_active)

    @patch("monitoring.ecosystem_dashboard._http_get")
    def test_check_em_tasks_down(self, mock_get):
        mock_get.side_effect = Exception("Timeout")
        
        check, marketplace = self.dashboard.check_em_tasks()
        self.assertEqual(check.status, HealthStatus.DOWN)
        self.assertEqual(marketplace.published_tasks, 0)

    @patch("monitoring.ecosystem_dashboard._get_block_number")
    def test_check_base_rpc(self, mock_block):
        mock_block.return_value = 42_693_170
        
        check, block = self.dashboard.check_base_rpc()
        self.assertEqual(check.status, HealthStatus.HEALTHY)
        self.assertEqual(block, 42_693_170)

    @patch("monitoring.ecosystem_dashboard._get_block_number")
    def test_check_base_rpc_down(self, mock_block):
        mock_block.side_effect = Exception("RPC timeout")
        
        check, block = self.dashboard.check_base_rpc()
        self.assertEqual(check.status, HealthStatus.DOWN)
        self.assertEqual(block, 0)

    @patch("monitoring.ecosystem_dashboard._eth_call")
    def test_check_erc8004_all_agents(self, mock_call):
        # First call: totalSupply, then 5 ownerOf calls
        mock_call.side_effect = [
            "0x0000000000000000000000000000000000000000000000000000000000000018",  # 24 total
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # coordinator
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # karma-hello
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # skill-extractor
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # voice-extractor
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # validator
        ]
        
        check, chain = self.dashboard.check_erc8004()
        self.assertEqual(check.status, HealthStatus.HEALTHY)
        self.assertEqual(chain.total_identities, 24)
        self.assertEqual(chain.system_agents_found, 5)
        self.assertEqual(len(chain.system_agents_missing), 0)

    @patch("monitoring.ecosystem_dashboard._eth_call")
    def test_check_erc8004_missing_agent(self, mock_call):
        mock_call.side_effect = [
            "0x0000000000000000000000000000000000000000000000000000000000000018",  # 24
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # ok
            "0x0000000000000000000000000000000000000000000000000000000000000000",  # missing!
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # ok
            "0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474",  # ok
            Exception("Revert"),  # error = missing
        ]
        
        check, chain = self.dashboard.check_erc8004()
        self.assertEqual(check.status, HealthStatus.DEGRADED)
        self.assertEqual(chain.system_agents_found, 3)
        self.assertEqual(len(chain.system_agents_missing), 2)

    @patch("monitoring.ecosystem_dashboard._eth_call")
    def test_check_erc8004_down(self, mock_call):
        mock_call.side_effect = Exception("RPC unavailable")
        
        check, chain = self.dashboard.check_erc8004()
        self.assertEqual(check.status, HealthStatus.DOWN)

    def test_check_swarm_components(self):
        """Swarm components should detect existing files."""
        components = self.dashboard.check_swarm_components()
        self.assertIsInstance(components, list)
        self.assertGreater(len(components), 0)
        
        # At least some components should exist (since we're in the right dir)
        names = [c.component for c in components]
        self.assertIn("Reputation Bridge", names)
        self.assertIn("Task Executor", names)

    @patch("monitoring.ecosystem_dashboard._http_get")
    @patch("monitoring.ecosystem_dashboard._get_block_number")
    @patch("monitoring.ecosystem_dashboard._eth_call")
    def test_generate_report_all_healthy(self, mock_eth, mock_block, mock_http):
        # Setup mocks for a fully healthy system
        mock_http.side_effect = [
            # EM health
            ({"status": "healthy", "components": {
                "db": {"status": "healthy"}, "chain": {"status": "healthy"},
            }}, 30.0),
            # EM auth
            ({"nonce": "abc123"}, 20.0),
            # Published tasks
            ({"tasks": [{"bounty_usd": 0.50, "payment_network": "base", "category": "test"}], "total": 1}, 25.0),
            # Completed tasks
            ({"tasks": [], "total": 0}, 20.0),
        ]
        mock_block.return_value = 42_000_000
        mock_eth.side_effect = [
            "0x0000000000000000000000000000000000000000000000000000000000000018",
            *["0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474"] * 5,
        ]
        
        report = self.dashboard.generate_report()
        self.assertEqual(report.overall_status, HealthStatus.HEALTHY)
        self.assertEqual(report.healthy_count, 5)
        self.assertEqual(report.total_checks, 5)
        self.assertGreater(report.total_latency_ms, 0)
        
        # Verify report components
        self.assertIsNotNone(report.em_api)
        self.assertIsNotNone(report.em_auth)
        self.assertIsNotNone(report.marketplace)
        self.assertIsNotNone(report.chain)
        self.assertEqual(report.chain.block_number, 42_000_000)

    @patch("monitoring.ecosystem_dashboard._http_get")
    @patch("monitoring.ecosystem_dashboard._get_block_number")
    @patch("monitoring.ecosystem_dashboard._eth_call")
    def test_generate_report_partial_failure(self, mock_eth, mock_block, mock_http):
        mock_http.side_effect = [
            ({"status": "healthy", "components": {"db": {"status": "healthy"}}}, 30.0),
            Exception("Auth service down"),
            Exception("Tasks service down"),
        ]
        mock_block.return_value = 42_000_000
        mock_eth.side_effect = [
            "0x0000000000000000000000000000000000000000000000000000000000000018",
            *["0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474"] * 5,
        ]
        
        report = self.dashboard.generate_report()
        self.assertEqual(report.overall_status, HealthStatus.DEGRADED)
        self.assertGreater(report.healthy_count, 0)
        self.assertLess(report.healthy_count, report.total_checks)

    @patch("monitoring.ecosystem_dashboard._http_get")
    @patch("monitoring.ecosystem_dashboard._get_block_number")
    @patch("monitoring.ecosystem_dashboard._eth_call")
    def test_generate_report_full_failure(self, mock_eth, mock_block, mock_http):
        mock_http.side_effect = Exception("Everything is down")
        mock_block.side_effect = Exception("RPC dead")
        mock_eth.side_effect = Exception("Chain dead")
        
        report = self.dashboard.generate_report()
        self.assertEqual(report.overall_status, HealthStatus.DOWN)
        self.assertEqual(report.healthy_count, 0)

    @patch("monitoring.ecosystem_dashboard._http_get")
    @patch("monitoring.ecosystem_dashboard._get_block_number")
    @patch("monitoring.ecosystem_dashboard._eth_call")
    def test_summary_is_string(self, mock_eth, mock_block, mock_http):
        mock_http.side_effect = [
            ({"status": "healthy", "components": {}}, 30.0),
            ({"nonce": "x"}, 20.0),
            ({"tasks": [], "total": 0}, 25.0),
            ({"tasks": [], "total": 0}, 20.0),
        ]
        mock_block.return_value = 1
        mock_eth.side_effect = [
            "0x01",
            *["0x000000000000000000000000d3868e1ed738ced6945a574a7c769433bed5d474"] * 5,
        ]
        
        report = self.dashboard.generate_report()
        summary = report.summary()
        self.assertIsInstance(summary, str)
        self.assertIn("SWARM HEALTH DASHBOARD", summary)


class TestSwarmComponentStatus(unittest.TestCase):
    """Tests for SwarmComponentStatus."""

    def test_existing_component(self):
        s = SwarmComponentStatus(
            component="Test Module",
            exists=True,
            line_count=500,
            test_count=42,
            description="A test module",
        )
        self.assertTrue(s.exists)
        self.assertEqual(s.line_count, 500)

    def test_missing_component(self):
        s = SwarmComponentStatus(
            component="Missing Module",
            exists=False,
            description="Not yet built",
        )
        self.assertFalse(s.exists)
        self.assertEqual(s.line_count, 0)


if __name__ == "__main__":
    unittest.main()
