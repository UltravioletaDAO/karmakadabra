"""
Tests for voice_extractor_service.py — Personality Refinery Service

Covers:
  - discover_data_offerings (EM browse + raw data filtering)
  - buy_data (budget, dry run, dedup, no executor)
  - process_voices (message parsing, voice profile generation, stats)
  - _extract_voices_from_messages (tone, formality, greeting, social role, slang, risk)
  - publish_personality_profiles (deduped EM publishing)
  - seller_flow (discover → apply → fulfill)
  - Edge cases: empty data, few messages, all languages, all tones
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))

from services.voice_extractor_service import (
    _extract_voices_from_messages,
    buy_data,
    discover_data_offerings,
    process_voices,
    publish_personality_profiles,
    seller_flow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data(tmp_path):
    """Create a temp data directory with subdirs."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "voices").mkdir()
    (data / "purchases").mkdir()
    return data


@pytest.fixture
def mock_em_client():
    """Mock EMClient for testing."""
    client = MagicMock()
    client.agent = MagicMock()
    client.agent.name = "kk-voice-extractor"
    client.agent.wallet_address = "0xVOICEEXTRACTOR"
    client.agent.executor_id = "exec-voice-001"
    client.agent.can_spend = MagicMock(return_value=True)
    client.agent.record_spend = MagicMock()
    client.agent.daily_spent_usd = 0.0
    client.agent.daily_budget_usd = 1.0
    client.close = AsyncMock()
    client.browse_tasks = AsyncMock(return_value=[])
    client.apply_to_task = AsyncMock(return_value={"status": "applied"})
    return client


@pytest.fixture
def spanish_chat_messages():
    """Spanish chat messages for voice analysis."""
    return [
        {"user": "carlos", "message": "hola buenas a todos!"},
        {"user": "carlos", "message": "¿alguien sabe cómo funciona este token?"},
        {"user": "carlos", "message": "parce eso está chimba!"},
        {"user": "carlos", "message": "vamos con todo wagmi!"},
        {"user": "carlos", "message": "jaja que loco esto"},
        {"user": "carlos", "message": "buenas noches parce"},
        {"user": "carlos", "message": "esto está muy interesante"},
        {"user": "carlos", "message": "¿cómo va el precio?"},
        {"user": "carlos", "message": "gm gm"},
        {"user": "carlos", "message": "hola!"},
    ]


@pytest.fixture
def english_chat_messages():
    """English chat messages."""
    return [
        {"user": "bob", "message": "Hello everyone, how is the market today?"},
        {"user": "bob", "message": "I think this is a great opportunity to research more"},
        {"user": "bob", "message": "The DeFi protocol looks solid, please be careful though"},
        {"user": "bob", "message": "Thank you for the analysis, that was very helpful"},
        {"user": "bob", "message": "We should DYOR before investing, risk management is key"},
        {"user": "bob", "message": "The technical documentation is comprehensive"},
        {"user": "bob", "message": "I've been following this project with interest and have some thoughts"},
        {"user": "bob", "message": "The token economics look well designed with good fundamentals"},
    ]


@pytest.fixture
def enthusiastic_messages():
    """Messages with enthusiastic tone."""
    return [
        {"user": "hype", "message": "OMG this is AMAZING!!!!"},
        {"user": "hype", "message": "Let's GO! Moon time!!!"},
        {"user": "hype", "message": "INCREDIBLE launch!!! 🚀🚀🚀"},
        {"user": "hype", "message": "ALL IN! Send it! YOLO!"},
        {"user": "hype", "message": "This is the BEST thing ever!!!"},
    ]


@pytest.fixture
def inquisitive_messages():
    """Messages with lots of questions."""
    return [
        {"user": "curious", "message": "What is this protocol about?"},
        {"user": "curious", "message": "How does the staking mechanism work?"},
        {"user": "curious", "message": "Why did the price change?"},
        {"user": "curious", "message": "Can someone explain the tokenomics?"},
        {"user": "curious", "message": "What are the fees like?"},
        {"user": "curious", "message": "Is there a docs page?"},
        {"user": "curious", "message": "Who is behind this project?"},
    ]


# ---------------------------------------------------------------------------
# discover_data_offerings
# ---------------------------------------------------------------------------


class TestDiscoverDataOfferings:
    @pytest.mark.asyncio
    async def test_finds_raw_data(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"title": "[KK Data] Raw Chat Logs — 1000 messages", "bounty_usdc": 0.01},
            {"title": "[KK Data] Skill Profiles", "bounty_usdc": 0.05},
            {"title": "Random task", "bounty_usdc": 1.00},
        ])
        result = await discover_data_offerings(mock_em_client)
        assert len(result) == 1  # Only the Raw one
        assert "Raw" in result[0]["title"]

    @pytest.mark.asyncio
    async def test_no_raw_data(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"title": "[KK Data] Skill Profiles", "bounty_usdc": 0.05},
        ])
        result = await discover_data_offerings(mock_em_client)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_empty_marketplace(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        result = await discover_data_offerings(mock_em_client)
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_raw_offerings(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"title": "[KK Data] Raw Logs Batch 1", "bounty_usdc": 0.01},
            {"title": "[KK Data] Raw Logs Batch 2", "bounty_usdc": 0.01},
        ])
        result = await discover_data_offerings(mock_em_client)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# buy_data
# ---------------------------------------------------------------------------


class TestBuyData:
    @pytest.mark.asyncio
    async def test_buy_success(self, mock_em_client):
        task = {"id": "task-1", "title": "[KK Data] Raw Logs", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task)
        assert result == {"status": "applied"}
        mock_em_client.agent.record_spend.assert_called_with(0.01)

    @pytest.mark.asyncio
    async def test_buy_over_budget(self, mock_em_client):
        mock_em_client.agent.can_spend.return_value = False
        task = {"id": "task-1", "title": "test", "bounty_usdc": 5.00}
        result = await buy_data(mock_em_client, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_buy_dry_run(self, mock_em_client):
        task = {"id": "task-1", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task, dry_run=True)
        assert result is None
        mock_em_client.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_no_executor(self, mock_em_client):
        mock_em_client.agent.executor_id = None
        task = {"id": "task-1", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_buy_duplicate_409(self, mock_em_client):
        mock_em_client.apply_to_task = AsyncMock(side_effect=Exception("409 already applied"))
        task = {"id": "dup", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task)
        assert result is None  # graceful

    @pytest.mark.asyncio
    async def test_buy_server_error(self, mock_em_client):
        mock_em_client.apply_to_task = AsyncMock(side_effect=Exception("500 internal"))
        task = {"id": "err", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task)
        assert result is None


# ---------------------------------------------------------------------------
# _extract_voices_from_messages
# ---------------------------------------------------------------------------


class TestExtractVoices:
    def test_spanish_detection(self, tmp_path, spanish_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(spanish_chat_messages, voices_dir)
        profile_path = voices_dir / "carlos.json"
        assert profile_path.exists()
        profile = json.loads(profile_path.read_text())
        assert profile["vocabulary"]["primary_language"] == "spanish"

    def test_english_detection(self, tmp_path, english_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(english_chat_messages, voices_dir)
        profile_path = voices_dir / "bob.json"
        assert profile_path.exists()
        profile = json.loads(profile_path.read_text())
        assert profile["vocabulary"]["primary_language"] == "english"

    def test_enthusiastic_tone(self, tmp_path, enthusiastic_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(enthusiastic_messages, voices_dir)
        profile = json.loads((voices_dir / "hype.json").read_text())
        assert profile["tone"]["primary"] == "enthusiastic"

    def test_inquisitive_tone(self, tmp_path, inquisitive_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(inquisitive_messages, voices_dir)
        profile = json.loads((voices_dir / "curious.json").read_text())
        assert profile["tone"]["primary"] == "inquisitive"

    def test_analytical_tone_long_messages(self, tmp_path):
        """Long messages should be detected as analytical."""
        msgs = [
            {"user": "prof", "message": "The tokenomics of this protocol are actually quite interesting when you consider the mechanism design implications and game theory behind it all"},
            {"user": "prof", "message": "If we look at the historical data and analyze the trends over the past six months, we can see a clear pattern forming in the market dynamics"},
            {"user": "prof", "message": "I believe the fundamental analysis points to strong growth potential, particularly given the underlying technology architecture and team composition"},
            {"user": "prof", "message": "The correlation between on-chain metrics and price action suggests we are still early in the adoption curve for this particular protocol"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "prof.json").read_text())
        assert profile["tone"]["primary"] == "analytical"

    def test_reactive_tone_short_messages(self, tmp_path):
        """Very short messages → reactive."""
        msgs = [
            {"user": "fast", "message": "lol"},
            {"user": "fast", "message": "gg"},
            {"user": "fast", "message": "nice"},
            {"user": "fast", "message": "yep"},
            {"user": "fast", "message": "ok"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "fast.json").read_text())
        assert profile["tone"]["primary"] == "reactive"

    def test_informal_detection(self, tmp_path, spanish_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(spanish_chat_messages, voices_dir)
        profile = json.loads((voices_dir / "carlos.json").read_text())
        assert profile["personality"]["formality"] == "informal"

    def test_formal_detection(self, tmp_path):
        msgs = [
            {"user": "formal", "message": "Cordial saludo a todos, please let me share my regards"},
            {"user": "formal", "message": "Thank you for your attention, I appreciate your help"},
            {"user": "formal", "message": "Usted tiene razón, please consider this carefully"},
            {"user": "formal", "message": "Thank you for the thoughtful response, regards"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "formal.json").read_text())
        assert profile["personality"]["formality"] == "formal"

    def test_greeting_style_hola(self, tmp_path, spanish_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(spanish_chat_messages, voices_dir)
        profile = json.loads((voices_dir / "carlos.json").read_text())
        # hola appears 2x in the messages, should be detected
        assert profile["communication_style"]["greeting_style"] in ["hola", "gm", "buenas"]

    def test_social_role_hub(self, tmp_path):
        """50+ messages with questions → hub."""
        msgs = [{"user": "hubuser", "message": f"Question {i}?"} for i in range(55)]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "hubuser.json").read_text())
        assert profile["communication_style"]["social_role"] == "hub"

    def test_social_role_active(self, tmp_path):
        """30+ messages → active_participant."""
        msgs = [{"user": "active", "message": f"Message number {i}"} for i in range(35)]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "active.json").read_text())
        assert profile["communication_style"]["social_role"] == "active_participant"

    def test_social_role_regular(self, tmp_path):
        """10-30 messages → regular."""
        msgs = [{"user": "reg", "message": f"Message {i}"} for i in range(15)]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "reg.json").read_text())
        assert profile["communication_style"]["social_role"] == "regular"

    def test_social_role_observer(self, tmp_path):
        """< 10 messages → observer (but ≥ 3 to not be skipped)."""
        msgs = [{"user": "lurker", "message": f"Msg {i}"} for i in range(5)]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "lurker.json").read_text())
        assert profile["communication_style"]["social_role"] == "observer"

    def test_skip_users_with_few_messages(self, tmp_path):
        """Users with < 3 messages are skipped."""
        msgs = [
            {"user": "twomsgs", "message": "hello"},
            {"user": "twomsgs", "message": "bye"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        assert not (voices_dir / "twomsgs.json").exists()

    def test_colombian_slang_detection(self, tmp_path, spanish_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(spanish_chat_messages, voices_dir)
        profile = json.loads((voices_dir / "carlos.json").read_text())
        slang = profile["vocabulary"]["slang_usage"]
        assert "colombian" in slang
        parce_words = [w["word"] for w in slang["colombian"]["top"]]
        assert "parce" in parce_words

    def test_crypto_slang_detection(self, tmp_path, spanish_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(spanish_chat_messages, voices_dir)
        profile = json.loads((voices_dir / "carlos.json").read_text())
        slang = profile["vocabulary"]["slang_usage"]
        assert "crypto" in slang

    def test_aggressive_risk_tolerance(self, tmp_path, enthusiastic_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(enthusiastic_messages, voices_dir)
        profile = json.loads((voices_dir / "hype.json").read_text())
        assert profile["personality"]["risk_tolerance"] == "aggressive"

    def test_conservative_risk_tolerance(self, tmp_path):
        msgs = [
            {"user": "safe", "message": "we need to be careful with this investment"},
            {"user": "safe", "message": "the risk here is too high, let's wait"},
            {"user": "safe", "message": "DYOR and research before making moves"},
            {"user": "safe", "message": "be careful, this could be a scam"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "safe.json").read_text())
        assert profile["personality"]["risk_tolerance"] == "conservative"

    def test_signature_phrases(self, tmp_path):
        """Repeated short messages become signature phrases."""
        msgs = [
            {"user": "phrases", "message": "vamos con todo"},
            {"user": "phrases", "message": "vamos con todo"},
            {"user": "phrases", "message": "vamos con todo"},
            {"user": "phrases", "message": "eso es chimba"},
            {"user": "phrases", "message": "eso es chimba"},
            {"user": "phrases", "message": "unique message here"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        profile = json.loads((voices_dir / "phrases.json").read_text())
        sig = profile["vocabulary"]["signature_phrases"]
        assert len(sig) > 0
        phrase_texts = [p["phrase"] for p in sig]
        assert "vamos con todo" in phrase_texts

    def test_avg_message_length(self, tmp_path, english_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(english_chat_messages, voices_dir)
        profile = json.loads((voices_dir / "bob.json").read_text())
        avg = profile["communication_style"]["avg_message_length"]
        assert isinstance(avg, float)
        assert avg > 20  # English messages are reasonably long

    def test_multiple_users(self, tmp_path, spanish_chat_messages, english_chat_messages):
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        all_msgs = spanish_chat_messages + english_chat_messages
        _extract_voices_from_messages(all_msgs, voices_dir)
        assert (voices_dir / "carlos.json").exists()
        assert (voices_dir / "bob.json").exists()

    def test_handles_missing_user_field(self, tmp_path):
        """Messages without user field are skipped."""
        msgs = [
            {"message": "orphan message"},
            {"user": "good", "message": "msg1"},
            {"user": "good", "message": "msg2"},
            {"user": "good", "message": "msg3"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        assert (voices_dir / "good.json").exists()

    def test_handles_sender_field(self, tmp_path):
        """Supports 'sender' as alternative to 'user'."""
        msgs = [
            {"sender": "alt", "text": "message using text field"},
            {"sender": "alt", "text": "another text field message"},
            {"sender": "alt", "text": "third message via text"},
        ]
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        _extract_voices_from_messages(msgs, voices_dir)
        assert (voices_dir / "alt.json").exists()


# ---------------------------------------------------------------------------
# process_voices
# ---------------------------------------------------------------------------


class TestProcessVoices:
    @pytest.mark.asyncio
    async def test_process_existing_profiles(self, tmp_data):
        """Reads existing voice profiles and aggregates stats."""
        profile = {
            "username": "test",
            "tone": {"primary": "enthusiastic"},
            "communication_style": {"social_role": "active_participant"},
            "vocabulary": {"slang_usage": {"crypto": {"top": [{"word": "wagmi", "count": 5}]}}},
        }
        (tmp_data / "voices" / "test.json").write_text(json.dumps(profile))

        result = await process_voices(tmp_data)
        assert result is not None
        assert result["total_profiles"] == 1
        assert result["tone_distribution"]["enthusiastic"] == 1

    @pytest.mark.asyncio
    async def test_process_from_purchases(self, tmp_data):
        """Processes purchased raw data into voice profiles."""
        messages = [
            {"user": "buyer", "message": "Hello friends!"},
            {"user": "buyer", "message": "How is everyone?"},
            {"user": "buyer", "message": "Great to be here"},
        ]
        (tmp_data / "purchases" / "batch1.json").write_text(json.dumps(messages))

        result = await process_voices(tmp_data)
        assert result is not None
        assert (tmp_data / "voices" / "buyer.json").exists()

    @pytest.mark.asyncio
    async def test_process_purchases_dict_format(self, tmp_data):
        """Supports dict format with 'messages' key."""
        data = {"messages": [
            {"user": "dictfmt", "message": "msg1"},
            {"user": "dictfmt", "message": "msg2"},
            {"user": "dictfmt", "message": "msg3"},
        ]}
        (tmp_data / "purchases" / "batch.json").write_text(json.dumps(data))

        result = await process_voices(tmp_data)
        assert result is not None
        assert (tmp_data / "voices" / "dictfmt.json").exists()

    @pytest.mark.asyncio
    async def test_process_empty_voices(self, tmp_path):
        """Returns None if no profiles found."""
        data = tmp_path / "data"
        data.mkdir()
        (data / "voices").mkdir()
        result = await process_voices(data)
        assert result is None

    @pytest.mark.asyncio
    async def test_process_tone_distribution(self, tmp_data):
        """Multiple profiles show correct tone distribution."""
        for name, tone in [("a", "enthusiastic"), ("b", "analytical"), ("c", "enthusiastic")]:
            profile = {
                "username": name,
                "tone": {"primary": tone},
                "communication_style": {"social_role": "regular"},
                "vocabulary": {"slang_usage": {}},
            }
            (tmp_data / "voices" / f"{name}.json").write_text(json.dumps(profile))

        result = await process_voices(tmp_data)
        assert result["tone_distribution"]["enthusiastic"] == 2
        assert result["tone_distribution"]["analytical"] == 1

    @pytest.mark.asyncio
    async def test_process_role_distribution(self, tmp_data):
        for name, role in [("x", "hub"), ("y", "regular"), ("z", "hub")]:
            profile = {
                "username": name,
                "tone": {"primary": "conversational"},
                "communication_style": {"social_role": role},
                "vocabulary": {"slang_usage": {}},
            }
            (tmp_data / "voices" / f"{name}.json").write_text(json.dumps(profile))

        result = await process_voices(tmp_data)
        assert result["role_distribution"]["hub"] == 2
        assert result["role_distribution"]["regular"] == 1

    @pytest.mark.asyncio
    async def test_process_no_purchases_dir(self, tmp_data):
        """Works fine without purchases dir (just reads existing profiles)."""
        import shutil
        shutil.rmtree(tmp_data / "purchases")

        profile = {
            "username": "existing",
            "tone": {"primary": "conversational"},
            "communication_style": {"social_role": "regular"},
            "vocabulary": {"slang_usage": {}},
        }
        (tmp_data / "voices" / "existing.json").write_text(json.dumps(profile))

        result = await process_voices(tmp_data)
        assert result is not None
        assert result["total_profiles"] == 1

    @pytest.mark.asyncio
    async def test_process_bad_json_in_purchases(self, tmp_data):
        """Handles malformed JSON in purchases gracefully."""
        (tmp_data / "purchases" / "bad.json").write_text("not valid json {{{")
        profile = {
            "username": "ok",
            "tone": {"primary": "conversational"},
            "communication_style": {"social_role": "regular"},
            "vocabulary": {"slang_usage": {}},
        }
        (tmp_data / "voices" / "ok.json").write_text(json.dumps(profile))

        result = await process_voices(tmp_data)
        assert result is not None  # doesn't crash

    @pytest.mark.asyncio
    async def test_process_bad_json_in_profiles(self, tmp_data):
        """Handles malformed profile JSON gracefully."""
        (tmp_data / "voices" / "bad.json").write_text("broken {json}")
        profile = {
            "username": "good",
            "tone": {"primary": "conversational"},
            "communication_style": {"social_role": "regular"},
            "vocabulary": {"slang_usage": {}},
        }
        (tmp_data / "voices" / "good.json").write_text(json.dumps(profile))

        result = await process_voices(tmp_data)
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_avg_slang_variety(self, tmp_data):
        for name in ["a", "b"]:
            profile = {
                "username": name,
                "tone": {"primary": "conversational"},
                "communication_style": {"social_role": "regular"},
                "vocabulary": {"slang_usage": {"crypto": {}, "colombian": {}}},
            }
            (tmp_data / "voices" / f"{name}.json").write_text(json.dumps(profile))

        result = await process_voices(tmp_data)
        assert isinstance(result["avg_slang_variety"], float)


# ---------------------------------------------------------------------------
# publish_personality_profiles
# ---------------------------------------------------------------------------


class TestPublishing:
    @pytest.mark.asyncio
    async def test_publish_personality(self, mock_em_client):
        stats = {
            "total_profiles": 15,
            "tone_distribution": {"enthusiastic": 5, "analytical": 10},
        }
        with patch("services.voice_extractor_service.publish_offering_deduped", new_callable=AsyncMock) as mock_pub:
            mock_pub.return_value = {"id": "pub-1"}
            result = await publish_personality_profiles(mock_em_client, stats)
            assert result == {"id": "pub-1"}
            call_kwargs = mock_pub.call_args[1]
            assert "15" in call_kwargs["title"]
            assert call_kwargs["bounty_usd"] == 0.04

    @pytest.mark.asyncio
    async def test_publish_dry_run(self, mock_em_client):
        stats = {"total_profiles": 5, "tone_distribution": {}}
        with patch("services.voice_extractor_service.publish_offering_deduped", new_callable=AsyncMock) as mock_pub:
            await publish_personality_profiles(mock_em_client, stats, dry_run=True)
            call_kwargs = mock_pub.call_args[1]
            assert call_kwargs["dry_run"] is True


# ---------------------------------------------------------------------------
# seller_flow
# ---------------------------------------------------------------------------


class TestSellerFlow:
    @pytest.mark.asyncio
    async def test_seller_finds_voice_bounties(self, mock_em_client, tmp_data):
        with patch("services.voice_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_disc:
            mock_disc.return_value = [
                {"id": "b1", "title": "[KK Request] Voice/Personality Data", "bounty_usdc": 0.04},
                {"id": "b2", "title": "[KK Request] Skill Profiles", "bounty_usdc": 0.05},
            ]
            with patch("services.voice_extractor_service.apply_to_bounty", new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = True
                with patch("services.voice_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                    mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                    result = await seller_flow(mock_em_client, tmp_data)
                    assert result["bounties_found"] == 1  # only voice/personality
                    assert result["applied"] == 1

    @pytest.mark.asyncio
    async def test_seller_personality_keyword(self, mock_em_client, tmp_data):
        with patch("services.voice_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_disc:
            mock_disc.return_value = [
                {"id": "b1", "title": "[KK Request] personality profiles needed", "bounty_usdc": 0.04},
            ]
            with patch("services.voice_extractor_service.apply_to_bounty", new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = True
                with patch("services.voice_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                    mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                    result = await seller_flow(mock_em_client, tmp_data)
                    assert result["bounties_found"] == 1

    @pytest.mark.asyncio
    async def test_seller_no_bounties(self, mock_em_client, tmp_data):
        with patch("services.voice_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_disc:
            mock_disc.return_value = []
            with patch("services.voice_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                result = await seller_flow(mock_em_client, tmp_data)
                assert result["bounties_found"] == 0
                assert result["applied"] == 0

    @pytest.mark.asyncio
    async def test_seller_error_handling(self, mock_em_client, tmp_data):
        with patch("services.voice_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_disc:
            mock_disc.side_effect = Exception("connection refused")
            with patch("services.voice_extractor_service.load_escrow_state") as mock_load:
                mock_load.return_value = {"published": {}, "applied": {}}
                with patch("services.voice_extractor_service.save_escrow_state"):
                    result = await seller_flow(mock_em_client, tmp_data)
                    assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_seller_dry_run_no_save(self, mock_em_client, tmp_data):
        with patch("services.voice_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_disc:
            mock_disc.return_value = []
            with patch("services.voice_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                with patch("services.voice_extractor_service.save_escrow_state") as mock_save:
                    await seller_flow(mock_em_client, tmp_data, dry_run=True)
                    mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_seller_max_3_applications(self, mock_em_client, tmp_data):
        bounties = [
            {"id": f"b{i}", "title": f"[KK Request] voice data {i}", "bounty_usdc": 0.04}
            for i in range(6)
        ]
        with patch("services.voice_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_disc:
            mock_disc.return_value = bounties
            with patch("services.voice_extractor_service.apply_to_bounty", new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = True
                with patch("services.voice_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                    mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                    result = await seller_flow(mock_em_client, tmp_data)
                    assert mock_apply.call_count == 3
