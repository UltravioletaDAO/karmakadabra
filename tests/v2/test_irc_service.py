"""
Tests for irc_service.py — IRC Integration Service

Covers:
  - IRCConfig (from_file, defaults, custom fields)
  - IRCService construction (from config, from_config classmethod)
  - Connection lifecycle (connect, disconnect, auto-join)
  - Messaging (send, send_dm, default channel)
  - Heartbeat announcements (status, budget, skills, task_id)
  - Message polling (poll_messages, get_new_messages, get_tail, get_mentions)
  - Task negotiation (announce_task, announce_offer, announce_request)
  - Channel management (create_channel, leave_channel)
  - CLI functions (cli_connect, cli_send, cli_read, cli_heartbeat)
  - Edge cases: no channels, missing config, custom server
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from services.irc_service import IRCConfig, IRCService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_config(tmp_path):
    """Write a config file and return its path."""
    def _write(data=None):
        if data is None:
            data = {
                "server": "irc.meshrelay.xyz",
                "port": 6667,
                "tls": False,
                "nick": "kk-test-agent",
                "channels": ["#Agents", "#KarmaKadabra"],
                "realname": "Test Agent",
                "auto_join": True,
            }
        path = tmp_path / "irc-config.json"
        path.write_text(json.dumps(data))
        return path
    return _write


@pytest.fixture
def mock_irc_client():
    """Return a mocked IRCClient."""
    client = MagicMock()
    client.connected = True
    client.connect = MagicMock(return_value=True)
    client.disconnect = MagicMock()
    client.join = MagicMock()
    client.part = MagicMock()
    client.send_message = MagicMock()
    client.poll_all = MagicMock(return_value=[])
    client.nick = "kk-test-agent"
    return client


@pytest.fixture
def irc_service(mock_irc_client):
    """Create an IRCService with a mocked client."""
    config = IRCConfig(
        nick="kk-test-agent",
        channels=["#Agents", "#KarmaKadabra"],
    )
    svc = IRCService(config)
    svc.client = mock_irc_client
    return svc


def _make_msg(nick="alice", channel="#Agents", text="hello", trailing=None):
    """Create a mock IRCMessage."""
    msg = MagicMock()
    msg.nick = nick
    msg.channel = channel
    msg.text = text
    msg.trailing = trailing or text
    msg.timestamp = time.time()
    return msg


# ---------------------------------------------------------------------------
# IRCConfig
# ---------------------------------------------------------------------------


class TestIRCConfig:
    def test_defaults(self):
        config = IRCConfig()
        assert config.server == "irc.meshrelay.xyz"
        assert config.port == 6667
        assert config.tls is False
        assert config.tls_port == 6697
        assert config.nick == "kk-agent"
        assert config.channels == ["#Agents"]
        assert config.auto_join is True

    def test_from_file(self, tmp_config):
        path = tmp_config()
        config = IRCConfig.from_file(path)
        assert config.nick == "kk-test-agent"
        assert config.channels == ["#Agents", "#KarmaKadabra"]
        assert config.realname == "Test Agent"

    def test_from_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            IRCConfig.from_file(tmp_path / "nonexistent.json")

    def test_from_file_minimal(self, tmp_config):
        path = tmp_config({"nick": "minimal-bot"})
        config = IRCConfig.from_file(path)
        assert config.nick == "minimal-bot"
        assert config.server == "irc.meshrelay.xyz"  # default
        assert config.channels == ["#Agents"]  # default

    def test_from_file_custom_server(self, tmp_config):
        path = tmp_config({
            "server": "irc.custom.xyz",
            "port": 7777,
            "tls": True,
            "tls_port": 7778,
            "nick": "custom-bot",
            "channels": ["#custom"],
        })
        config = IRCConfig.from_file(path)
        assert config.server == "irc.custom.xyz"
        assert config.port == 7777
        assert config.tls is True
        assert config.tls_port == 7778

    def test_from_file_port_ssl_fallback(self, tmp_config):
        """Supports 'port_ssl' as alternative to 'tls_port'."""
        path = tmp_config({"port_ssl": 9999, "nick": "ssl-bot"})
        config = IRCConfig.from_file(path)
        assert config.tls_port == 9999

    def test_auto_join_false(self, tmp_config):
        path = tmp_config({"nick": "nojoin", "auto_join": False})
        config = IRCConfig.from_file(path)
        assert config.auto_join is False


# ---------------------------------------------------------------------------
# IRCService construction
# ---------------------------------------------------------------------------


class TestIRCServiceInit:
    def test_from_config_classmethod(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCClient") as MockClient:
            MockClient.return_value = MagicMock()
            svc = IRCService.from_config(path)
            assert svc.config.nick == "kk-test-agent"

    def test_message_log_starts_empty(self, irc_service):
        assert irc_service._message_log == []
        assert irc_service._read_cursor == 0


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestConnectionLifecycle:
    def test_connect_success(self, irc_service, mock_irc_client):
        ok = irc_service.connect()
        assert ok is True
        mock_irc_client.connect.assert_called_once()

    def test_connect_auto_joins(self, irc_service, mock_irc_client):
        irc_service.connect()
        assert mock_irc_client.join.call_count == 2  # #Agents + #KarmaKadabra

    def test_connect_no_auto_join(self, mock_irc_client):
        config = IRCConfig(nick="nojoin", auto_join=False)
        svc = IRCService(config)
        svc.client = mock_irc_client
        svc.connect()
        mock_irc_client.join.assert_not_called()

    def test_connect_failure(self, irc_service, mock_irc_client):
        mock_irc_client.connect.return_value = False
        ok = irc_service.connect()
        assert ok is False

    def test_disconnect(self, irc_service, mock_irc_client):
        irc_service.disconnect()
        mock_irc_client.send_message.assert_called_once()  # goodbye msg
        mock_irc_client.disconnect.assert_called_once()

    def test_disconnect_goodbye_message(self, irc_service, mock_irc_client):
        irc_service.disconnect()
        call_args = mock_irc_client.send_message.call_args
        assert call_args[0][0] == "#Agents"  # main channel
        assert "[BYE]" in call_args[0][1]

    def test_connected_property(self, irc_service, mock_irc_client):
        mock_irc_client.connected = True
        assert irc_service.connected is True
        mock_irc_client.connected = False
        assert irc_service.connected is False

    def test_disconnect_handles_send_error(self, mock_irc_client):
        config = IRCConfig(nick="err")
        svc = IRCService(config)
        svc.client = mock_irc_client
        mock_irc_client.send_message.side_effect = Exception("not connected")
        svc.disconnect()  # Should not raise
        mock_irc_client.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------


class TestMessaging:
    def test_send_default_channel(self, irc_service, mock_irc_client):
        irc_service.send("hello everyone")
        mock_irc_client.send_message.assert_called_with("#Agents", "hello everyone")

    def test_send_specific_channel(self, irc_service, mock_irc_client):
        irc_service.send("specialized msg", target="#KarmaKadabra")
        mock_irc_client.send_message.assert_called_with("#KarmaKadabra", "specialized msg")

    def test_send_to_user(self, irc_service, mock_irc_client):
        irc_service.send("private msg", target="alice")
        mock_irc_client.send_message.assert_called_with("alice", "private msg")

    def test_send_dm(self, irc_service, mock_irc_client):
        irc_service.send_dm("bob", "hey bob")
        mock_irc_client.send_message.assert_called_with("bob", "hey bob")

    def test_send_no_channels_fallback(self, mock_irc_client):
        config = IRCConfig(nick="lonely", channels=[])
        svc = IRCService(config)
        svc.client = mock_irc_client
        svc.send("fallback")
        mock_irc_client.send_message.assert_called_with("#Agents", "fallback")


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_basic_heartbeat(self, irc_service, mock_irc_client):
        irc_service.announce_heartbeat(status="idle")
        call_args = mock_irc_client.send_message.call_args
        msg = call_args[0][1]
        assert "[STATUS]" in msg
        assert "kk-test-agent" in msg
        assert "idle" in msg

    def test_heartbeat_with_skills(self, irc_service, mock_irc_client):
        irc_service.announce_heartbeat(status="busy", skills=["DeFi", "Python", "Solidity"])
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "DeFi" in msg
        assert "Python" in msg

    def test_heartbeat_budget(self, irc_service, mock_irc_client):
        irc_service.announce_heartbeat(budget_remaining=0.75, budget_total=2.0)
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "$0.75/$2.00" in msg

    def test_heartbeat_with_task_id(self, irc_service, mock_irc_client):
        irc_service.announce_heartbeat(task_id="abc12345-long-uuid")
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "task: abc12345" in msg  # truncated to 8 chars

    def test_heartbeat_no_skills(self, irc_service, mock_irc_client):
        irc_service.announce_heartbeat()
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "general" in msg

    def test_heartbeat_many_skills_truncated(self, irc_service, mock_irc_client):
        irc_service.announce_heartbeat(skills=["A", "B", "C", "D", "E"])
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "A" in msg
        assert "B" in msg
        assert "C" in msg
        # D and E should be truncated (only first 3)
        assert "D" not in msg


# ---------------------------------------------------------------------------
# Message polling
# ---------------------------------------------------------------------------


class TestMessagePolling:
    def test_poll_messages(self, irc_service, mock_irc_client):
        msg = _make_msg()
        mock_irc_client.poll_all.return_value = [msg]
        result = irc_service.poll_messages()
        assert len(result) == 1
        assert irc_service._message_log == [msg]

    def test_get_new_messages(self, irc_service, mock_irc_client):
        msg1 = _make_msg(text="first")
        msg2 = _make_msg(text="second")
        mock_irc_client.poll_all.return_value = [msg1, msg2]
        result = irc_service.get_new_messages()
        assert len(result) == 2
        assert irc_service._read_cursor == 2

        # Second call with no new msgs
        mock_irc_client.poll_all.return_value = []
        result2 = irc_service.get_new_messages()
        assert len(result2) == 0

    def test_get_new_messages_incremental(self, irc_service, mock_irc_client):
        msg1 = _make_msg(text="batch1")
        mock_irc_client.poll_all.return_value = [msg1]
        irc_service.get_new_messages()

        msg2 = _make_msg(text="batch2")
        mock_irc_client.poll_all.return_value = [msg2]
        result = irc_service.get_new_messages()
        assert len(result) == 1
        assert result[0].text == "batch2"

    def test_get_tail(self, irc_service, mock_irc_client):
        msgs = [_make_msg(text=f"msg{i}") for i in range(20)]
        mock_irc_client.poll_all.return_value = msgs
        result = irc_service.get_tail(5)
        assert len(result) == 5

    def test_get_tail_fewer_than_requested(self, irc_service, mock_irc_client):
        msgs = [_make_msg(text="only")]
        mock_irc_client.poll_all.return_value = msgs
        result = irc_service.get_tail(10)
        assert len(result) == 1

    def test_get_mentions(self, irc_service, mock_irc_client):
        msg1 = _make_msg(text="hey kk-test-agent what's up")
        msg2 = _make_msg(text="unrelated message")
        msg3 = _make_msg(text="", trailing="kk-test-agent help me")
        irc_service._message_log = [msg1, msg2, msg3]
        result = irc_service.get_mentions()
        assert len(result) == 2  # msg1 and msg3

    def test_get_mentions_custom_nick(self, irc_service):
        msg = _make_msg(text="alice please respond")
        irc_service._message_log = [msg]
        result = irc_service.get_mentions(nick="alice")
        assert len(result) == 1

    def test_get_mentions_case_insensitive(self, irc_service):
        msg = _make_msg(text="Hey KK-TEST-AGENT are you there?")
        irc_service._message_log = [msg]
        result = irc_service.get_mentions()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Task negotiation
# ---------------------------------------------------------------------------


class TestTaskNegotiation:
    def test_announce_task(self, irc_service, mock_irc_client):
        irc_service.announce_task("Build API endpoint", 0.50, "digital_physical")
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "[TASK]" in msg
        assert "[digital_physical]" in msg
        assert "Build API endpoint" in msg
        assert "$0.50" in msg

    def test_announce_task_no_category(self, irc_service, mock_irc_client):
        irc_service.announce_task("Simple task", 0.10)
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "[TASK]" in msg
        assert "Simple task" in msg
        # No category bracket
        assert msg.count("[") == 1  # only [TASK]

    def test_announce_offer(self, irc_service, mock_irc_client):
        irc_service.announce_offer("Python development services", 0.25)
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "[OFFER]" in msg
        assert "Python development" in msg
        assert "$0.25" in msg

    def test_announce_request(self, irc_service, mock_irc_client):
        irc_service.announce_request("Need data analysis done", 1.00)
        msg = mock_irc_client.send_message.call_args[0][1]
        assert "[REQUEST]" in msg
        assert "data analysis" in msg
        assert "budget: $1.00" in msg


# ---------------------------------------------------------------------------
# Channel management
# ---------------------------------------------------------------------------


class TestChannelManagement:
    def test_create_channel(self, irc_service, mock_irc_client):
        irc_service.create_channel("#NewChannel")
        mock_irc_client.join.assert_called_with("#NewChannel")

    def test_create_channel_adds_hash(self, irc_service, mock_irc_client):
        irc_service.create_channel("NoPrefixChannel")
        mock_irc_client.join.assert_called_with("#NoPrefixChannel")

    def test_leave_channel(self, irc_service, mock_irc_client):
        irc_service.leave_channel("#KarmaKadabra")
        mock_irc_client.part.assert_called_with("#KarmaKadabra")


# ---------------------------------------------------------------------------
# CLI helpers (integration-style, verifying they call the right methods)
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_send(self, tmp_config):
        """cli_send connects, sends, disconnects."""
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = True
            instance.connected = True
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(config=str(path), message="test msg", target=None)

            from services.irc_service import cli_send
            cli_send(args)

            instance.connect.assert_called_once()
            instance.send.assert_called_once_with("test msg", target=None)
            instance.disconnect.assert_called_once()

    def test_cli_send_with_target(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = True
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(config=str(path), message="dm", target="alice")

            from services.irc_service import cli_send
            cli_send(args)
            instance.send.assert_called_once_with("dm", target="alice")

    def test_cli_heartbeat(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = True
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(
                config=str(path), status="busy", budget=1.5, skills="DeFi,Python"
            )

            from services.irc_service import cli_heartbeat
            cli_heartbeat(args)
            instance.announce_heartbeat.assert_called_once_with(
                status="busy",
                budget_remaining=1.5,
                skills=["DeFi", "Python"],
            )

    def test_cli_heartbeat_no_skills(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = True
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(
                config=str(path), status="idle", budget=None, skills=""
            )

            from services.irc_service import cli_heartbeat
            cli_heartbeat(args)
            instance.announce_heartbeat.assert_called_once_with(
                status="idle",
                budget_remaining=2.0,
                skills=[],
            )

    def test_cli_read_new(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = True
            instance.get_new_messages.return_value = []
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(
                config=str(path), new=True, tail=None, wait=1
            )

            from services.irc_service import cli_read
            with patch("services.irc_service.time.sleep"):
                cli_read(args)
            instance.get_new_messages.assert_called_once()

    def test_cli_read_tail(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = True
            instance.get_tail.return_value = []
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(
                config=str(path), new=False, tail=5, wait=1
            )

            from services.irc_service import cli_read
            with patch("services.irc_service.time.sleep"):
                cli_read(args)
            instance.get_tail.assert_called_once_with(5)

    def test_cli_disconnect(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = True
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(config=str(path))

            from services.irc_service import cli_disconnect
            cli_disconnect(args)
            instance.disconnect.assert_called_once()

    def test_cli_send_connect_failure(self, tmp_config):
        path = tmp_config()
        with patch("services.irc_service.IRCService") as MockSvc:
            instance = MagicMock()
            instance.connect.return_value = False
            MockSvc.from_config.return_value = instance

            import argparse
            args = argparse.Namespace(config=str(path), message="test", target=None)

            from services.irc_service import cli_send
            with pytest.raises(SystemExit):
                cli_send(args)
