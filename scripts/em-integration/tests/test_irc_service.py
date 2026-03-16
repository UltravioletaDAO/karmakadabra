"""
Tests for IRC Service — KK V2 Swarm IRC Communication

Covers:
  - IRCConfig: defaults, from_file, missing file
  - IRCService: initialization, connection lifecycle
  - Messaging: send, send_dm, default target
  - Heartbeat: formatted status messages
  - Message polling: poll, get_new, get_tail, get_mentions
  - Task negotiation: announce_task, announce_offer, announce_request
  - Channel management: create, leave
  - from_config: factory method
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.irc_service import IRCConfig, IRCService


# ═══════════════════════════════════════════════════════════════════
# IRCConfig Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCConfig:
    """Tests for IRC configuration."""

    def test_defaults(self):
        c = IRCConfig()
        assert c.server == "irc.meshrelay.xyz"
        assert c.port == 6667
        assert c.tls is False
        assert c.tls_port == 6697
        assert c.nick == "kk-agent"
        assert c.channels == ["#Agents"]
        assert c.auto_join is True

    def test_from_file(self):
        config_data = {
            "server": "irc.example.com",
            "port": 6668,
            "tls": True,
            "tls_port": 6698,
            "nick": "kk-aurora",
            "channels": ["#KK", "#test"],
            "realname": "Aurora Agent",
            "auto_join": False,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            path = f.name

        try:
            c = IRCConfig.from_file(path)
            assert c.server == "irc.example.com"
            assert c.port == 6668
            assert c.tls is True
            assert c.nick == "kk-aurora"
            assert c.channels == ["#KK", "#test"]
            assert c.auto_join is False
        finally:
            Path(path).unlink(missing_ok=True)

    def test_from_file_minimal(self):
        """Config with only some fields uses defaults for the rest."""
        config_data = {"nick": "kk-spark"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            path = f.name

        try:
            c = IRCConfig.from_file(path)
            assert c.nick == "kk-spark"
            assert c.server == "irc.meshrelay.xyz"
            assert c.port == 6667
        finally:
            Path(path).unlink(missing_ok=True)

    def test_from_file_missing(self):
        with pytest.raises(FileNotFoundError):
            IRCConfig.from_file("/nonexistent/config.json")

    def test_port_ssl_fallback(self):
        """Supports port_ssl as alternative to tls_port."""
        config_data = {"port_ssl": 6699}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            path = f.name

        try:
            c = IRCConfig.from_file(path)
            assert c.tls_port == 6699
        finally:
            Path(path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════
# IRCService Initialization Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCServiceInit:
    """Tests for IRCService initialization."""

    def test_basic_init(self):
        config = IRCConfig(nick="kk-test")
        with patch("services.irc_service.IRCClient"):
            svc = IRCService(config)
            assert svc.config.nick == "kk-test"
            assert svc._message_log == []
            assert svc._read_cursor == 0

    def test_from_config(self):
        config_data = {"nick": "kk-aurora", "channels": ["#test"]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            path = f.name

        try:
            with patch("services.irc_service.IRCClient"):
                svc = IRCService.from_config(path)
                assert svc.config.nick == "kk-aurora"
                assert svc.config.channels == ["#test"]
        finally:
            Path(path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════
# Connection Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCServiceConnection:
    """Tests for connect/disconnect."""

    def test_connect_success(self):
        config = IRCConfig(nick="kk-test", channels=["#ch1", "#ch2"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.connect.return_value = True
            svc = IRCService(config)

            result = svc.connect()
            assert result is True
            mock_client.connect.assert_called_once()
            # Should join both channels
            assert mock_client.join.call_count == 2

    def test_connect_failure(self):
        config = IRCConfig(nick="kk-test")
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.connect.return_value = False
            svc = IRCService(config)

            result = svc.connect()
            assert result is False
            mock_client.join.assert_not_called()

    def test_connect_no_auto_join(self):
        config = IRCConfig(nick="kk-test", auto_join=False, channels=["#ch1"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.connect.return_value = True
            svc = IRCService(config)

            result = svc.connect()
            assert result is True
            mock_client.join.assert_not_called()

    def test_disconnect(self):
        config = IRCConfig(nick="kk-test", channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.disconnect()
            mock_client.send_message.assert_called_once()
            mock_client.disconnect.assert_called_once()

    def test_connected_property(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.connected = True
            svc = IRCService(config)
            assert svc.connected is True


# ═══════════════════════════════════════════════════════════════════
# Messaging Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCServiceMessaging:
    """Tests for send/receive."""

    def test_send_to_default_channel(self):
        config = IRCConfig(channels=["#main", "#secondary"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.send("Hello world")
            mock_client.send_message.assert_called_with("#main", "Hello world")

    def test_send_to_specific_target(self):
        config = IRCConfig(channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.send("Hello", target="#other")
            mock_client.send_message.assert_called_with("#other", "Hello")

    def test_send_dm(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.send_dm("kk-spark", "Hey, got a task for you")
            mock_client.send_message.assert_called_with(
                "kk-spark", "Hey, got a task for you"
            )

    def test_send_empty_channels_defaults_to_agents(self):
        config = IRCConfig(channels=[])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.send("Hello")
            mock_client.send_message.assert_called_with("#Agents", "Hello")


# ═══════════════════════════════════════════════════════════════════
# Heartbeat Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCServiceHeartbeat:
    """Tests for heartbeat announcements."""

    def test_idle_heartbeat(self):
        config = IRCConfig(nick="kk-aurora", channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_heartbeat(
                status="idle",
                budget_remaining=1.50,
                budget_total=2.00,
                skills=["DeFi", "AI", "Data"],
            )
            sent_msg = mock_client.send_message.call_args[0][1]
            assert "[STATUS]" in sent_msg
            assert "kk-aurora" in sent_msg
            assert "idle" in sent_msg
            assert "$1.50/$2.00" in sent_msg
            assert "DeFi, AI, Data" in sent_msg

    def test_busy_heartbeat_with_task(self):
        config = IRCConfig(nick="kk-aurora", channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_heartbeat(
                status="busy",
                task_id="task_123456789abcdef",
            )
            sent_msg = mock_client.send_message.call_args[0][1]
            assert "busy" in sent_msg
            assert "task: task_123" in sent_msg

    def test_heartbeat_no_skills(self):
        config = IRCConfig(nick="kk-aurora", channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_heartbeat()
            sent_msg = mock_client.send_message.call_args[0][1]
            assert "general" in sent_msg

    def test_heartbeat_truncates_skills(self):
        config = IRCConfig(nick="kk-aurora", channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_heartbeat(
                skills=["A", "B", "C", "D", "E"],  # Only first 3
            )
            sent_msg = mock_client.send_message.call_args[0][1]
            assert "A, B, C" in sent_msg
            assert "D" not in sent_msg


# ═══════════════════════════════════════════════════════════════════
# Message Polling Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCServicePolling:
    """Tests for message polling and filtering."""

    def _make_message(self, nick="user", channel="#main", text="hello"):
        msg = MagicMock()
        msg.nick = nick
        msg.channel = channel
        msg.text = text
        msg.trailing = text
        return msg

    def test_poll_messages(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.poll_all.return_value = [
                self._make_message(text="msg1"),
                self._make_message(text="msg2"),
            ]
            svc = IRCService(config)
            msgs = svc.poll_messages()
            assert len(msgs) == 2
            assert len(svc._message_log) == 2

    def test_get_new_messages(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            # First poll
            mock_client.poll_all.return_value = [
                self._make_message(text="msg1"),
            ]
            svc = IRCService(config)
            
            unread1 = svc.get_new_messages()
            assert len(unread1) == 1
            
            # Second poll - no new messages
            mock_client.poll_all.return_value = []
            unread2 = svc.get_new_messages()
            assert len(unread2) == 0
            
            # Third poll - new message arrives
            mock_client.poll_all.return_value = [
                self._make_message(text="msg2"),
            ]
            unread3 = svc.get_new_messages()
            assert len(unread3) == 1

    def test_get_tail(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.poll_all.return_value = []
            svc = IRCService(config)
            # Pre-populate log
            for i in range(10):
                svc._message_log.append(self._make_message(text=f"msg{i}"))
            
            tail = svc.get_tail(3)
            assert len(tail) == 3

    def test_get_mentions(self):
        config = IRCConfig(nick="kk-aurora")
        with patch("services.irc_service.IRCClient") as MockClient:
            svc = IRCService(config)
            svc._message_log = [
                self._make_message(text="Hey kk-aurora, check this out"),
                self._make_message(text="General message"),
                self._make_message(text="@kk-aurora needs help"),
            ]
            mentions = svc.get_mentions()
            assert len(mentions) == 2

    def test_get_mentions_custom_nick(self):
        config = IRCConfig(nick="kk-aurora")
        with patch("services.irc_service.IRCClient") as MockClient:
            svc = IRCService(config)
            svc._message_log = [
                self._make_message(text="Hey coordinator!"),
                self._make_message(text="coordinator: ping"),
            ]
            mentions = svc.get_mentions("coordinator")
            assert len(mentions) == 2


# ═══════════════════════════════════════════════════════════════════
# Task Negotiation Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCServiceTaskNegotiation:
    """Tests for task announcement helpers."""

    def test_announce_task(self):
        config = IRCConfig(channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_task("Photo verification in NYC", 0.25, "physical_verification")
            sent = mock_client.send_message.call_args[0][1]
            assert "[TASK]" in sent
            assert "physical_verification" in sent
            assert "$0.25" in sent
            assert "Photo verification in NYC" in sent

    def test_announce_task_no_category(self):
        config = IRCConfig(channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_task("Simple task", 1.0)
            sent = mock_client.send_message.call_args[0][1]
            assert "[TASK]" in sent
            assert "[" not in sent.split("]", 1)[1].split("Simple")[0]

    def test_announce_offer(self):
        config = IRCConfig(channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_offer("Skill DNA extraction for 10 profiles", 0.50)
            sent = mock_client.send_message.call_args[0][1]
            assert "[OFFER]" in sent
            assert "$0.50" in sent

    def test_announce_request(self):
        config = IRCConfig(channels=["#main"])
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.announce_request("Need DeFi yield analysis", 2.0)
            sent = mock_client.send_message.call_args[0][1]
            assert "[REQUEST]" in sent
            assert "$2.00" in sent


# ═══════════════════════════════════════════════════════════════════
# Channel Management Tests
# ═══════════════════════════════════════════════════════════════════


class TestIRCServiceChannels:
    """Tests for channel management."""

    def test_create_channel(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.create_channel("kk-aurora-task")
            mock_client.join.assert_called_with("#kk-aurora-task")

    def test_create_channel_with_hash(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.create_channel("#already-prefixed")
            mock_client.join.assert_called_with("#already-prefixed")

    def test_leave_channel(self):
        config = IRCConfig()
        with patch("services.irc_service.IRCClient") as MockClient:
            mock_client = MockClient.return_value
            svc = IRCService(config)
            svc.leave_channel("#done-channel")
            mock_client.part.assert_called_with("#done-channel")
