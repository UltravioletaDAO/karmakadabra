"""
Tests for lib/irc_client.py — IRC Client for KK Agent Communication

Covers:
  - IRC message parsing (parse_irc_message)
  - Message splitting (_split_message)
  - IRCMessage dataclass properties
  - Client initialization and properties
  - Connection flow (mocked sockets)
  - Channel operations
  - Message sending
  - Message polling
  - Background receiver thread
  - Nick collision handling
  - PING/PONG handling
  - Error conditions
"""

import queue
import socket
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.irc_client import IRCClient, IRCMessage, parse_irc_message


# ═══════════════════════════════════════════════════════════════════
# TestParseIRCMessage — Protocol line parsing
# ═══════════════════════════════════════════════════════════════════


class TestParseIRCMessage:
    """IRC protocol message parsing."""

    def test_privmsg_channel(self):
        raw = ":nick!user@host PRIVMSG #channel :Hello world"
        msg = parse_irc_message(raw)
        assert msg.nick == "nick"
        assert msg.command == "PRIVMSG"
        assert msg.channel == "#channel"
        assert msg.text == "Hello world"
        assert msg.trailing == "Hello world"
        assert not msg.is_private

    def test_privmsg_dm(self):
        raw = ":alice!user@host PRIVMSG bob :Hey there"
        msg = parse_irc_message(raw)
        assert msg.nick == "alice"
        assert msg.channel == "bob"
        assert msg.text == "Hey there"
        assert msg.is_private

    def test_ping(self):
        raw = "PING :server.meshrelay.xyz"
        msg = parse_irc_message(raw)
        assert msg.command == "PING"
        assert msg.trailing == "server.meshrelay.xyz"
        assert msg.nick == ""

    def test_numeric_welcome(self):
        raw = ":server 001 kk-agent :Welcome to MeshRelay"
        msg = parse_irc_message(raw)
        assert msg.command == "001"
        assert msg.nick == "server"
        assert msg.trailing == "Welcome to MeshRelay"

    def test_nick_in_use(self):
        raw = ":server 433 * kk-agent :Nickname is already in use"
        msg = parse_irc_message(raw)
        assert msg.command == "433"

    def test_empty_line(self):
        msg = parse_irc_message("")
        assert msg.command == ""
        assert msg.raw == ""

    def test_whitespace_only(self):
        msg = parse_irc_message("   \r\n  ")
        assert msg.command == ""

    def test_prefix_without_user_host(self):
        raw = ":servername NOTICE * :Looking up your hostname"
        msg = parse_irc_message(raw)
        assert msg.nick == "servername"
        assert msg.prefix == "servername"
        assert msg.command == "NOTICE"

    def test_prefix_with_user_host(self):
        raw = ":nick!user@host.com PRIVMSG #test :msg"
        msg = parse_irc_message(raw)
        assert msg.nick == "nick"
        assert msg.prefix == "nick!user@host.com"

    def test_no_trailing(self):
        raw = ":nick!user@host JOIN #channel"
        msg = parse_irc_message(raw)
        assert msg.command == "JOIN"
        assert msg.params == ["#channel"]
        assert msg.trailing == ""

    def test_multiple_params(self):
        raw = ":server 353 kk-agent = #channel :user1 user2 user3"
        msg = parse_irc_message(raw)
        assert msg.command == "353"
        assert "=" in msg.params
        assert "#channel" in msg.params
        assert msg.trailing == "user1 user2 user3"

    def test_timestamp_set(self):
        before = time.time()
        msg = parse_irc_message(":nick PRIVMSG #test :hi")
        after = time.time()
        assert before <= msg.timestamp <= after

    def test_command_uppercased(self):
        raw = ":nick!user@host privmsg #test :hello"
        msg = parse_irc_message(raw)
        assert msg.command == "PRIVMSG"

    def test_raw_preserved(self):
        raw = ":nick!user@host PRIVMSG #test :some message"
        msg = parse_irc_message(raw)
        assert msg.raw == raw

    def test_trailing_with_colons(self):
        raw = ":nick PRIVMSG #test :time is 12:30:00 PM"
        msg = parse_irc_message(raw)
        assert msg.trailing == "time is 12:30:00 PM"

    def test_kk_protocol_hello(self):
        raw = ":kk-coordinator!user@host PRIVMSG #Agents :[HELLO] Coordinator online"
        msg = parse_irc_message(raw)
        assert msg.nick == "kk-coordinator"
        assert "[HELLO] Coordinator online" in msg.text

    def test_kk_protocol_proposal(self):
        raw = ":kk-agent-01!user@host PRIVMSG #Agents :[PROPOSAL] Task #42 assignment"
        msg = parse_irc_message(raw)
        assert "[PROPOSAL]" in msg.text


# ═══════════════════════════════════════════════════════════════════
# TestIRCMessageProperties — Dataclass convenience properties
# ═══════════════════════════════════════════════════════════════════


class TestIRCMessageProperties:
    """IRCMessage dataclass property methods."""

    def test_channel_from_params(self):
        msg = IRCMessage(raw="", params=["#test"], trailing="hello")
        assert msg.channel == "#test"

    def test_channel_empty_params(self):
        msg = IRCMessage(raw="", params=[], trailing="hello")
        assert msg.channel == ""

    def test_is_private_dm(self):
        msg = IRCMessage(raw="", params=["username"], trailing="hi")
        assert msg.is_private is True

    def test_is_private_channel(self):
        msg = IRCMessage(raw="", params=["#channel"], trailing="hi")
        assert msg.is_private is False

    def test_text_alias(self):
        msg = IRCMessage(raw="", trailing="the message text")
        assert msg.text == "the message text"


# ═══════════════════════════════════════════════════════════════════
# TestSplitMessage — IRC line length splitting
# ═══════════════════════════════════════════════════════════════════


class TestSplitMessage:
    """Message splitting for IRC line limits."""

    def test_short_message_single_chunk(self):
        chunks = IRCClient._split_message("hello", max_len=400)
        assert chunks == ["hello"]

    def test_exact_length(self):
        msg = "x" * 400
        chunks = IRCClient._split_message(msg, max_len=400)
        assert len(chunks) == 1
        assert chunks[0] == msg

    def test_long_message_split(self):
        msg = "x" * 800
        chunks = IRCClient._split_message(msg, max_len=400)
        assert len(chunks) == 2
        assert len(chunks[0]) == 400
        assert len(chunks[1]) == 400

    def test_very_long_message(self):
        msg = "x" * 1500
        chunks = IRCClient._split_message(msg, max_len=400)
        assert len(chunks) == 4
        assert "".join(chunks) == msg

    def test_empty_message(self):
        chunks = IRCClient._split_message("", max_len=400)
        assert chunks == [""]

    def test_custom_max_len(self):
        msg = "x" * 100
        chunks = IRCClient._split_message(msg, max_len=50)
        assert len(chunks) == 2


# ═══════════════════════════════════════════════════════════════════
# TestClientInit — IRCClient initialization
# ═══════════════════════════════════════════════════════════════════


class TestClientInit:
    """Client constructor and initial state."""

    def test_default_values(self):
        client = IRCClient()
        assert client.server == "irc.meshrelay.xyz"
        assert client.port == 6667
        assert client.nick == "kk-agent"
        assert not client.connected
        assert client.channels == set()

    def test_custom_server(self):
        client = IRCClient(server="irc.example.com", port=6668, nick="my-agent")
        assert client.server == "irc.example.com"
        assert client.port == 6668
        assert client.nick == "my-agent"

    def test_tls_uses_tls_port(self):
        client = IRCClient(use_tls=True)
        assert client.port == 6697

    def test_tls_custom_port(self):
        client = IRCClient(use_tls=True, tls_port=7000)
        assert client.port == 7000

    def test_initial_not_connected(self):
        client = IRCClient()
        assert client.connected is False
        assert client.channels == set()


# ═══════════════════════════════════════════════════════════════════
# TestClientConnection — Connect and disconnect flow
# ═══════════════════════════════════════════════════════════════════


class TestClientConnection:
    """Connection and disconnection with mocked sockets."""

    def test_connect_success(self):
        """Simulate a successful connection with RPL_WELCOME."""
        mock_sock = MagicMock()
        welcome = b":server 001 kk-agent :Welcome to MeshRelay\r\n"
        mock_sock.recv.side_effect = [welcome, socket.timeout()]

        with patch("lib.irc_client.socket.create_connection", return_value=mock_sock):
            client = IRCClient(nick="kk-agent")
            result = client.connect(timeout=5)
            assert result is True
            assert client.connected is True
            client.disconnect()

    def test_connect_nick_collision(self):
        """Simulate nick already in use → retry with timestamp suffix."""
        mock_sock = MagicMock()
        collision = b":server 433 * kk-agent :Nickname is already in use\r\n"
        welcome = b":server 001 kk-agent-1234 :Welcome\r\n"
        mock_sock.recv.side_effect = [collision, welcome, socket.timeout()]

        with patch("lib.irc_client.socket.create_connection", return_value=mock_sock):
            client = IRCClient(nick="kk-agent")
            result = client.connect(timeout=5)
            assert result is True
            assert "kk-agent-" in client.nick  # Modified nick
            client.disconnect()

    def test_connect_timeout(self):
        """Simulate no RPL_WELCOME within timeout."""
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = socket.timeout()

        with patch("lib.irc_client.socket.create_connection", return_value=mock_sock):
            client = IRCClient(nick="kk-agent")
            result = client.connect(timeout=0.1)
            assert result is False

    def test_connect_network_error(self):
        """Simulate connection refused."""
        with patch(
            "lib.irc_client.socket.create_connection",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            client = IRCClient()
            result = client.connect(timeout=1)
            assert result is False
            assert client.connected is False

    def test_disconnect_clears_state(self):
        mock_sock = MagicMock()
        welcome = b":server 001 kk-agent :Welcome\r\n"
        mock_sock.recv.side_effect = [welcome, socket.timeout()]

        with patch("lib.irc_client.socket.create_connection", return_value=mock_sock):
            client = IRCClient(nick="kk-agent")
            client.connect(timeout=5)
            client._channels.add("#test")
            client.disconnect()
            assert client.connected is False
            assert client.channels == set()

    def test_disconnect_sends_quit(self):
        mock_sock = MagicMock()
        welcome = b":server 001 kk-agent :Welcome\r\n"
        mock_sock.recv.side_effect = [welcome, socket.timeout()]

        with patch("lib.irc_client.socket.create_connection", return_value=mock_sock):
            client = IRCClient(nick="kk-agent")
            client.connect(timeout=5)
            client.disconnect()
            # Check QUIT was sent
            calls = mock_sock.sendall.call_args_list
            quit_calls = [c for c in calls if b"QUIT" in c[0][0]]
            assert len(quit_calls) > 0

    def test_ping_pong_during_connect(self):
        """Server sends PING during registration → client should PONG."""
        mock_sock = MagicMock()
        ping = b"PING :meshrelay\r\n"
        welcome = b":server 001 kk-agent :Welcome\r\n"
        mock_sock.recv.side_effect = [ping, welcome, socket.timeout()]

        with patch("lib.irc_client.socket.create_connection", return_value=mock_sock):
            client = IRCClient(nick="kk-agent")
            result = client.connect(timeout=5)
            assert result is True
            # Verify PONG was sent
            calls = mock_sock.sendall.call_args_list
            pong_calls = [c for c in calls if b"PONG" in c[0][0]]
            assert len(pong_calls) > 0
            client.disconnect()


# ═══════════════════════════════════════════════════════════════════
# TestChannelOps — Join and part
# ═══════════════════════════════════════════════════════════════════


class TestChannelOps:
    """Channel join/part operations."""

    def test_join_adds_channel(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client.join("#Agents")
        assert "#Agents" in client.channels

    def test_join_prefixes_hash(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client.join("Agents")
        assert "#Agents" in client.channels

    def test_join_sends_command(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client.join("#test")
        client._sock.sendall.assert_called()
        sent = client._sock.sendall.call_args[0][0]
        assert b"JOIN #test" in sent

    def test_part_removes_channel(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client._channels.add("#test")
        client.part("#test")
        assert "#test" not in client.channels

    def test_part_sends_command(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client._channels.add("#test")
        client.part("#test", "Goodbye")
        sent = client._sock.sendall.call_args[0][0]
        assert b"PART #test" in sent
        assert b"Goodbye" in sent


# ═══════════════════════════════════════════════════════════════════
# TestMessaging — Send messages and notices
# ═══════════════════════════════════════════════════════════════════


class TestMessaging:
    """Sending messages and notices."""

    def test_send_message(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client.send_message("#Agents", "[HELLO] Online!")
        sent = client._sock.sendall.call_args[0][0]
        assert b"PRIVMSG #Agents :[HELLO] Online!" in sent

    def test_send_notice(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client.send_notice("#Agents", "Notice text")
        sent = client._sock.sendall.call_args[0][0]
        assert b"NOTICE #Agents :Notice text" in sent

    def test_long_message_splits(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        long_msg = "x" * 800
        client.send_message("#test", long_msg)
        # Should have sent 2 PRIVMSG commands
        assert client._sock.sendall.call_count == 2

    def test_send_dm(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client.send_message("alice", "Hey!")
        sent = client._sock.sendall.call_args[0][0]
        assert b"PRIVMSG alice :Hey!" in sent

    def test_send_no_socket_graceful(self):
        client = IRCClient()
        client._sock = None
        # Should not raise
        client.send_message("#test", "hello")


# ═══════════════════════════════════════════════════════════════════
# TestPolling — Message queue polling
# ═══════════════════════════════════════════════════════════════════


class TestPolling:
    """Message polling from the inbox queue."""

    def test_poll_empty_queue(self):
        client = IRCClient()
        messages = client.poll_messages()
        assert messages == []

    def test_poll_returns_messages(self):
        client = IRCClient()
        msg = parse_irc_message(":nick PRIVMSG #test :hello")
        client._inbox.put(msg)
        messages = client.poll_messages()
        assert len(messages) == 1
        assert messages[0].text == "hello"

    def test_poll_max_count(self):
        client = IRCClient()
        for i in range(10):
            msg = parse_irc_message(f":nick PRIVMSG #test :msg{i}")
            client._inbox.put(msg)
        messages = client.poll_messages(max_count=3)
        assert len(messages) == 3

    def test_poll_all_drains_queue(self):
        client = IRCClient()
        for i in range(5):
            msg = parse_irc_message(f":nick PRIVMSG #test :msg{i}")
            client._inbox.put(msg)
        messages = client.poll_all()
        assert len(messages) == 5
        assert client._inbox.empty()

    def test_poll_nonblocking(self):
        """poll_messages should return immediately even with empty queue."""
        client = IRCClient()
        start = time.time()
        messages = client.poll_messages()
        elapsed = time.time() - start
        assert elapsed < 0.1
        assert messages == []


# ═══════════════════════════════════════════════════════════════════
# TestOnMessageCallback — Callback registration
# ═══════════════════════════════════════════════════════════════════


class TestOnMessageCallback:
    """on_message callback registration."""

    def test_register_callback(self):
        client = IRCClient()
        callback = MagicMock()
        client.on_message(callback)
        assert client._on_message == callback

    def test_callback_replaces_previous(self):
        client = IRCClient()
        cb1 = MagicMock()
        cb2 = MagicMock()
        client.on_message(cb1)
        client.on_message(cb2)
        assert client._on_message == cb2


# ═══════════════════════════════════════════════════════════════════
# TestRecvLines — Raw data receiving
# ═══════════════════════════════════════════════════════════════════


class TestRecvLines:
    """Internal _recv_lines data handling."""

    def test_complete_lines(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client._sock.recv.return_value = b":nick PRIVMSG #test :hello\r\n"
        lines = client._recv_lines()
        assert len(lines) == 1
        assert ":nick PRIVMSG #test :hello" in lines[0]

    def test_multiple_lines(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        data = b"PING :server\r\n:nick PRIVMSG #test :hi\r\n"
        client._sock.recv.return_value = data
        lines = client._recv_lines()
        assert len(lines) == 2

    def test_partial_line_buffered(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client._sock.recv.return_value = b":nick PRIVMSG #test :partial"
        lines = client._recv_lines()
        assert len(lines) == 0  # No complete line yet
        assert "partial" in client._recv_buffer

    def test_timeout_returns_empty(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client._sock.recv.side_effect = socket.timeout()
        lines = client._recv_lines()
        assert lines == []

    def test_no_socket_returns_empty(self):
        client = IRCClient()
        client._sock = None
        lines = client._recv_lines()
        assert lines == []

    def test_connection_lost(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client._sock.recv.return_value = b""  # EOF
        lines = client._recv_lines()
        assert client._connected is False


# ═══════════════════════════════════════════════════════════════════
# TestSendRaw — Internal _send method
# ═══════════════════════════════════════════════════════════════════


class TestSendRaw:
    """Internal _send method."""

    def test_appends_crlf(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._send("PING :test")
        sent = client._sock.sendall.call_args[0][0]
        assert sent == b"PING :test\r\n"

    def test_send_error_marks_disconnected(self):
        client = IRCClient()
        client._sock = MagicMock()
        client._connected = True
        client._sock.sendall.side_effect = BrokenPipeError("Broken pipe")
        client._send("test")
        assert client._connected is False


# ═══════════════════════════════════════════════════════════════════
# TestChannelsProperty — Thread-safe copy
# ═══════════════════════════════════════════════════════════════════


class TestChannelsProperty:
    """channels property returns a copy."""

    def test_channels_is_copy(self):
        client = IRCClient()
        client._channels.add("#test")
        channels = client.channels
        channels.add("#other")
        assert "#other" not in client._channels

    def test_channels_reflects_state(self):
        client = IRCClient()
        assert client.channels == set()
        client._channels.add("#a")
        client._channels.add("#b")
        assert client.channels == {"#a", "#b"}
