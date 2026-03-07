"""
Tests for soul_extractor_service.py — Complete Agent Profile Service

Covers:
  - generate_soul_md (SOUL.md generation with various profiles)
  - discover_data_offerings (EM browse + skill/voice filtering)
  - buy_data (budget limits, dry run, dedup, no executor)
  - process_souls (merge skill+voice+stats into SOUL.md, partial profiles, defaults)
  - publish_soul_profiles & publish_profile_updates (deduped EM publishing)
  - seller_flow (discover → apply → fulfill with evidence)
  - _derive_task_categories, _default_skills, _default_voice helpers
  - Edge cases: empty data, missing dirs, no stats, partial data
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))

from services.soul_extractor_service import (
    RISK_DESCRIPTIONS,
    SKILL_TO_SERVICE,
    TASK_CATEGORY_MAP,
    TONE_DESCRIPTIONS,
    TONE_GUIDELINES,
    _default_skills,
    _default_voice,
    _derive_task_categories,
    buy_data,
    discover_data_offerings,
    generate_soul_md,
    process_souls,
    publish_profile_updates,
    publish_soul_profiles,
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
    (data / "skills").mkdir()
    (data / "voices").mkdir()
    (data / "souls").mkdir()
    return data


@pytest.fixture
def mock_em_client():
    """Mock EMClient for testing."""
    client = MagicMock()
    client.agent = MagicMock()
    client.agent.name = "kk-soul-extractor"
    client.agent.wallet_address = "0xSOULEXTRACTOR"
    client.agent.executor_id = "exec-soul-001"
    client.agent.can_spend = MagicMock(return_value=True)
    client.agent.record_spend = MagicMock()
    client.agent.daily_spent_usd = 0.0
    client.agent.daily_budget_usd = 2.0
    client.close = AsyncMock()
    client.browse_tasks = AsyncMock(return_value=[])
    client.apply_to_task = AsyncMock(return_value={"status": "applied"})
    return client


@pytest.fixture
def sample_skills():
    """Sample skill profile for a user."""
    return {
        "username": "alice",
        "skills": {
            "Programming": {
                "sub_skills": [
                    {"name": "Python", "score": 0.85},
                    {"name": "FastAPI", "score": 0.72},
                    {"name": "Docker", "score": 0.55},
                ]
            },
            "AI/ML": {
                "sub_skills": [
                    {"name": "LLM", "score": 0.65},
                    {"name": "NLP", "score": 0.40},
                ]
            },
        },
        "top_skills": [
            {"skill": "Python", "score": 0.85},
            {"skill": "LLM", "score": 0.65},
            {"skill": "Docker", "score": 0.55},
        ],
        "primary_language": "spanish",
        "languages": {"spanish": 0.8, "english": 0.2},
    }


@pytest.fixture
def sample_voice():
    """Sample voice profile for a user."""
    return {
        "username": "alice",
        "tone": {"primary": "enthusiastic", "question_ratio": 0.15, "excl_ratio": 0.35},
        "communication_style": {
            "avg_message_length": 45,
            "social_role": "active_participant",
            "greeting_style": "hola",
        },
        "vocabulary": {
            "signature_phrases": [
                {"phrase": "vamos con todo", "count": 8},
                {"phrase": "eso es chimba", "count": 5},
            ],
            "slang_usage": {
                "colombian": {"top": [{"word": "parce", "count": 12}]},
                "crypto": {"top": [{"word": "wagmi", "count": 7}]},
            },
        },
        "personality": {
            "formality": "informal",
            "risk_tolerance": "aggressive",
        },
    }


@pytest.fixture
def sample_stats():
    """Sample user stats."""
    return {
        "total_messages": 523,
        "active_dates": 42,
    }


# ---------------------------------------------------------------------------
# Constants / Maps
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify mapping constants are properly defined."""

    def test_task_category_map_has_keys(self):
        expected_keys = {"Programming", "Blockchain", "AI/ML", "Design", "Business", "Community"}
        assert expected_keys == set(TASK_CATEGORY_MAP.keys())

    def test_task_category_map_values_are_lists(self):
        for key, val in TASK_CATEGORY_MAP.items():
            assert isinstance(val, list), f"TASK_CATEGORY_MAP[{key}] should be list"
            for item in val:
                assert isinstance(item, str)

    def test_risk_descriptions_coverage(self):
        for risk in ["aggressive", "moderate", "conservative", "unknown"]:
            assert risk in RISK_DESCRIPTIONS

    def test_tone_descriptions_coverage(self):
        for tone in ["inquisitive", "enthusiastic", "analytical", "reactive", "conversational"]:
            assert tone in TONE_DESCRIPTIONS
            assert tone in TONE_GUIDELINES

    def test_skill_to_service_map(self):
        for skill_name, entry in SKILL_TO_SERVICE.items():
            assert "capability" in entry
            assert "service" in entry
            assert isinstance(entry["capability"], str)
            assert isinstance(entry["service"], str)


# ---------------------------------------------------------------------------
# generate_soul_md
# ---------------------------------------------------------------------------


class TestGenerateSoulMd:
    """Tests for SOUL.md generation."""

    def test_basic_generation(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "# Soul of alice" in soul
        assert "alice" in soul
        assert "523" in soul  # total messages
        assert "42" in soul  # active dates

    def test_identity_section(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Identity" in soul
        assert "Spanish (primary)" in soul
        assert "English (secondary)" in soul
        assert "Python" in soul  # specialization from top_skills

    def test_personality_section(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Personality" in soul
        assert "Enthusiastic" in soul
        assert "Informal" in soul
        assert "Active Participant" in soul
        assert '"hola"' in soul  # greeting style

    def test_signature_phrases_included(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "vamos con todo" in soul
        assert "eso es chimba" in soul

    def test_slang_included(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "parce" in soul
        assert "wagmi" in soul

    def test_skills_section(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Skills & Expertise" in soul
        assert "**Python**" in soul
        assert "confidence: high" in soul  # score 0.85

    def test_skill_confidence_levels(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        # Python 0.85 -> high, FastAPI 0.72 -> high, Docker 0.55 -> medium
        assert "confidence: high" in soul
        assert "confidence: medium" in soul

    def test_economic_section_aggressive(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Economic Behavior" in soul
        assert "Aggressive" in soul
        assert "$0.50" in soul  # max spend for aggressive
        assert "Firm" in soul  # negotiation style

    def test_economic_section_conservative(self, sample_skills, sample_voice, sample_stats):
        voice = dict(sample_voice)
        voice["personality"] = {"risk_tolerance": "conservative", "formality": "formal"}
        soul = generate_soul_md("alice", sample_stats, sample_skills, voice)
        assert "Conservative" in soul
        assert "$0.20" in soul
        assert "Generous" in soul

    def test_economic_section_moderate(self, sample_skills, sample_voice, sample_stats):
        voice = dict(sample_voice)
        voice["personality"] = {"risk_tolerance": "moderate", "formality": "informal"}
        soul = generate_soul_md("alice", sample_stats, sample_skills, voice)
        assert "Moderate" in soul
        assert "$0.30" in soul
        assert "Flexible" in soul

    def test_task_categories_from_programming(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "digital_physical" in soul

    def test_monetizable_capabilities(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Monetizable Capabilities" in soul
        # Python is top skill, should map to Python Development
        assert "Python Development" in soul

    def test_trusted_agents_list(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Trusted Agents" in soul
        assert "kk-coordinator" in soul
        assert "kk-soul-extractor" in soul

    def test_agent_rules(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Agent Rules" in soul
        assert "$2.00 USDC" in soul  # daily budget rule

    def test_communication_guidelines_spanish(self, sample_skills, sample_voice, sample_stats):
        soul = generate_soul_md("alice", sample_stats, sample_skills, sample_voice)
        assert "## Communication Guidelines" in soul
        assert "Spanish" in soul

    def test_communication_guidelines_english(self, sample_skills, sample_voice, sample_stats):
        skills = dict(sample_skills)
        skills["primary_language"] = "english"
        soul = generate_soul_md("alice", sample_stats, skills, sample_voice)
        assert "English" in soul

    def test_no_top_skills_fallback(self, sample_voice, sample_stats):
        skills = {
            "username": "newbie",
            "skills": {},
            "top_skills": [],
            "primary_language": "spanish",
            "languages": {"spanish": 1.0},
        }
        soul = generate_soul_md("newbie", sample_stats, skills, sample_voice)
        assert "Community Member" in soul  # fallback specialization
        assert "Community participation" in soul  # fallback skill line

    def test_no_signature_phrases(self, sample_skills, sample_stats):
        voice = {
            "username": "alice",
            "tone": {"primary": "analytical"},
            "communication_style": {"social_role": "regular", "greeting_style": "gm", "avg_message_length": 80},
            "vocabulary": {"signature_phrases": [], "slang_usage": {}},
            "personality": {"risk_tolerance": "moderate", "formality": "formal"},
        }
        soul = generate_soul_md("alice", sample_stats, sample_skills, voice)
        assert "Signature phrases" not in soul  # no phrases = no section

    def test_no_slang(self, sample_skills, sample_stats):
        voice = {
            "username": "alice",
            "tone": {"primary": "conversational"},
            "communication_style": {"social_role": "regular", "greeting_style": "hey", "avg_message_length": 30},
            "vocabulary": {"signature_phrases": [], "slang_usage": {}},
            "personality": {"risk_tolerance": "moderate", "formality": "informal"},
        }
        soul = generate_soul_md("alice", sample_stats, sample_skills, voice)
        assert "Slang" not in soul

    def test_empty_stats(self, sample_skills, sample_voice):
        soul = generate_soul_md("alice", {}, sample_skills, sample_voice)
        assert "0 across 0 sessions" in soul

    def test_single_language(self, sample_voice, sample_stats):
        skills = {
            "username": "mono",
            "skills": {},
            "top_skills": [],
            "primary_language": "english",
            "languages": {"english": 1.0},
        }
        soul = generate_soul_md("mono", sample_stats, skills, sample_voice)
        assert "English (primary)" in soul
        # Should not have secondary
        assert "secondary" not in soul

    def test_all_tones(self, sample_skills, sample_stats):
        for tone in ["inquisitive", "enthusiastic", "analytical", "reactive", "conversational"]:
            voice = {
                "username": "user",
                "tone": {"primary": tone},
                "communication_style": {"social_role": "regular", "greeting_style": "gm", "avg_message_length": 40},
                "vocabulary": {"signature_phrases": [], "slang_usage": {}},
                "personality": {"risk_tolerance": "moderate", "formality": "informal"},
            }
            soul = generate_soul_md("user", sample_stats, sample_skills, voice)
            assert tone.title() in soul

    def test_design_skill_category(self, sample_voice, sample_stats):
        skills = {
            "username": "designer",
            "skills": {"Design": {"sub_skills": [{"name": "UI/UX", "score": 0.80}]}},
            "top_skills": [{"skill": "UI/UX", "score": 0.80}],
            "primary_language": "english",
            "languages": {"english": 1.0},
        }
        soul = generate_soul_md("designer", sample_stats, skills, sample_voice)
        assert "simple_action" in soul
        assert "Design Services" in soul


# ---------------------------------------------------------------------------
# _derive_task_categories
# ---------------------------------------------------------------------------


class TestDeriveTaskCategories:
    def test_programming_category(self):
        skills = {"skills": {"Programming": {"sub_skills": []}}}
        result = _derive_task_categories(skills)
        assert "digital_physical" in result

    def test_business_category(self):
        skills = {"skills": {"Business": {"sub_skills": []}}}
        result = _derive_task_categories(skills)
        assert "knowledge_access" in result
        assert "human_authority" in result

    def test_empty_skills_fallback(self):
        result = _derive_task_categories({"skills": {}})
        assert "simple_action" in result
        assert "knowledge_access" in result

    def test_multiple_categories(self):
        skills = {"skills": {"Programming": {}, "Design": {}, "Community": {}}}
        result = _derive_task_categories(skills)
        assert "digital_physical" in result
        assert "simple_action" in result
        assert "knowledge_access" in result

    def test_returns_sorted(self):
        skills = {"skills": {"Programming": {}, "Business": {}, "Community": {}}}
        result = _derive_task_categories(skills)
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# _default_skills / _default_voice
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_skills(self):
        result = _default_skills("bob")
        assert result["username"] == "bob"
        assert result["skills"] == {}
        assert result["top_skills"] == []
        assert result["primary_language"] == "spanish"

    def test_default_voice(self):
        result = _default_voice("carol")
        assert result["username"] == "carol"
        assert result["tone"]["primary"] == "conversational"
        assert result["communication_style"]["social_role"] == "regular"
        assert result["personality"]["risk_tolerance"] == "moderate"
        assert result["personality"]["formality"] == "informal"


# ---------------------------------------------------------------------------
# discover_data_offerings
# ---------------------------------------------------------------------------


class TestDiscoverDataOfferings:
    @pytest.mark.asyncio
    async def test_finds_skill_and_voice_offerings(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"title": "[KK Data] Skill Profiles — 50 Users", "bounty_usdc": 0.05},
            {"title": "[KK Data] Personality & Voice — 50 Users", "bounty_usdc": 0.04},
            {"title": "Unrelated task", "bounty_usdc": 1.00},
        ])
        result = await discover_data_offerings(mock_em_client)
        assert len(result["skills"]) == 1
        assert len(result["voices"]) == 1

    @pytest.mark.asyncio
    async def test_no_offerings(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        result = await discover_data_offerings(mock_em_client)
        assert result["skills"] == []
        assert result["voices"] == []

    @pytest.mark.asyncio
    async def test_multiple_skill_offerings(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"title": "[KK Data] Skill Profiles v1", "bounty_usdc": 0.05},
            {"title": "[KK Data] Skill Update v2", "bounty_usdc": 0.03},
        ])
        result = await discover_data_offerings(mock_em_client)
        assert len(result["skills"]) == 2

    @pytest.mark.asyncio
    async def test_voice_keyword_matching(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"title": "[KK Data] Voice Analysis — 30 Users", "bounty_usdc": 0.04},
            {"title": "[KK Data] Personality Profiles", "bounty_usdc": 0.04},
        ])
        result = await discover_data_offerings(mock_em_client)
        # "Voice" and "Personality" both match voice_offerings filter
        assert len(result["voices"]) == 2


# ---------------------------------------------------------------------------
# buy_data
# ---------------------------------------------------------------------------


class TestBuyData:
    @pytest.mark.asyncio
    async def test_buy_success(self, mock_em_client):
        task = {"id": "task-1", "title": "[KK Data] Skills", "bounty_usdc": 0.05}
        result = await buy_data(mock_em_client, task, "skill")
        assert result == {"status": "applied"}
        mock_em_client.agent.record_spend.assert_called_with(0.05)

    @pytest.mark.asyncio
    async def test_buy_over_budget(self, mock_em_client):
        mock_em_client.agent.can_spend.return_value = False
        task = {"id": "task-1", "title": "[KK Data] Skills", "bounty_usdc": 5.00}
        result = await buy_data(mock_em_client, task, "skill")
        assert result is None
        mock_em_client.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_dry_run(self, mock_em_client):
        task = {"id": "task-1", "title": "[KK Data] Skills", "bounty_usdc": 0.05}
        result = await buy_data(mock_em_client, task, "skill", dry_run=True)
        assert result is None
        mock_em_client.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_no_executor_id(self, mock_em_client):
        mock_em_client.agent.executor_id = None
        task = {"id": "task-1", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task, "skill")
        assert result is None

    @pytest.mark.asyncio
    async def test_buy_duplicate_409(self, mock_em_client):
        mock_em_client.apply_to_task = AsyncMock(side_effect=Exception("409 Conflict: already applied"))
        task = {"id": "task-dup", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task, "skill")
        assert result is None  # handled gracefully

    @pytest.mark.asyncio
    async def test_buy_api_error(self, mock_em_client):
        mock_em_client.apply_to_task = AsyncMock(side_effect=Exception("500 server error"))
        task = {"id": "task-err", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task, "voice")
        assert result is None


# ---------------------------------------------------------------------------
# process_souls
# ---------------------------------------------------------------------------


class TestProcessSouls:
    @pytest.mark.asyncio
    async def test_process_complete_profiles(self, tmp_data, sample_skills, sample_voice):
        """Users with both skill + voice data get complete profiles."""
        (tmp_data / "skills" / "alice.json").write_text(json.dumps(sample_skills))
        (tmp_data / "voices" / "alice.json").write_text(json.dumps(sample_voice))
        (tmp_data / "user-stats.json").write_text(json.dumps({
            "ranking": [{"username": "alice", "total_messages": 500, "active_dates": 30}]
        }))

        result = await process_souls(tmp_data)
        assert result is not None
        assert result["complete_profiles"] == 1
        assert result["partial_profiles"] == 0
        assert result["new_profiles"] == 1

        # Check generated files
        soul_md = tmp_data / "souls" / "alice.md"
        soul_json = tmp_data / "souls" / "alice.json"
        assert soul_md.exists()
        assert soul_json.exists()
        assert "# Soul of alice" in soul_md.read_text()

    @pytest.mark.asyncio
    async def test_process_partial_skills_only(self, tmp_data, sample_skills):
        """Users with only skill data get partial profiles with default voice."""
        (tmp_data / "skills" / "bob.json").write_text(json.dumps({**sample_skills, "username": "bob"}))

        result = await process_souls(tmp_data)
        assert result is not None
        assert result["complete_profiles"] == 0
        assert result["partial_profiles"] == 1

        # Partial profile still generated
        assert (tmp_data / "souls" / "bob.md").exists()

    @pytest.mark.asyncio
    async def test_process_partial_voice_only(self, tmp_data, sample_voice):
        """Users with only voice data get partial profiles with default skills."""
        (tmp_data / "skills").mkdir(exist_ok=True)  # empty skills dir
        (tmp_data / "voices" / "carol.json").write_text(json.dumps({**sample_voice, "username": "carol"}))

        result = await process_souls(tmp_data)
        assert result is not None
        assert result["partial_profiles"] == 1

    @pytest.mark.asyncio
    async def test_process_no_stats_file(self, tmp_data, sample_skills, sample_voice):
        """Generates profiles even without user-stats.json."""
        (tmp_data / "skills" / "alice.json").write_text(json.dumps(sample_skills))
        (tmp_data / "voices" / "alice.json").write_text(json.dumps(sample_voice))

        result = await process_souls(tmp_data)
        assert result is not None
        assert result["total_profiles"] == 1

    @pytest.mark.asyncio
    async def test_process_update_tracking(self, tmp_data, sample_skills, sample_voice):
        """Second run counts as update, not new."""
        (tmp_data / "skills" / "alice.json").write_text(json.dumps(sample_skills))
        (tmp_data / "voices" / "alice.json").write_text(json.dumps(sample_voice))

        # First run
        result1 = await process_souls(tmp_data)
        assert result1["new_profiles"] == 1
        assert result1["updated_profiles"] == 0

        # Second run
        result2 = await process_souls(tmp_data)
        assert result2["new_profiles"] == 0
        assert result2["updated_profiles"] == 1

    @pytest.mark.asyncio
    async def test_process_no_skills_dir(self, tmp_path):
        """Returns None if no skills directory exists."""
        data = tmp_path / "empty"
        data.mkdir()
        (data / "voices").mkdir()
        result = await process_souls(data)
        assert result is None

    @pytest.mark.asyncio
    async def test_process_no_voices_dir(self, tmp_path):
        """Returns None if no voices directory exists."""
        data = tmp_path / "empty"
        data.mkdir()
        (data / "skills").mkdir()
        result = await process_souls(data)
        assert result is None

    @pytest.mark.asyncio
    async def test_process_skips_summary_files(self, tmp_data, sample_skills, sample_voice):
        """Files starting with _ are skipped."""
        (tmp_data / "skills" / "_summary.json").write_text(json.dumps({"aggregate": True}))
        (tmp_data / "skills" / "alice.json").write_text(json.dumps(sample_skills))
        (tmp_data / "voices" / "_summary.json").write_text(json.dumps({"aggregate": True}))
        (tmp_data / "voices" / "alice.json").write_text(json.dumps(sample_voice))

        result = await process_souls(tmp_data)
        assert result["total_profiles"] == 1  # only alice, not _summary

    @pytest.mark.asyncio
    async def test_process_structured_json_output(self, tmp_data, sample_skills, sample_voice):
        """Structured JSON output has correct schema."""
        (tmp_data / "skills" / "alice.json").write_text(json.dumps(sample_skills))
        (tmp_data / "voices" / "alice.json").write_text(json.dumps(sample_voice))

        result = await process_souls(tmp_data)
        assert len(result["profiles"]) == 1

        profile = result["profiles"][0]
        assert profile["username"] == "alice"
        assert "identity" in profile
        assert "personality" in profile
        assert "skills" in profile
        assert "task_categories" in profile
        assert "pricing" in profile
        assert profile["pricing"]["daily_budget_usd"] == 2.0

    @pytest.mark.asyncio
    async def test_process_multiple_users(self, tmp_data, sample_skills, sample_voice):
        """Multiple users all get profiles."""
        for name in ["alice", "bob", "carol"]:
            skills = {**sample_skills, "username": name}
            voice = {**sample_voice, "username": name}
            (tmp_data / "skills" / f"{name}.json").write_text(json.dumps(skills))
            (tmp_data / "voices" / f"{name}.json").write_text(json.dumps(voice))

        result = await process_souls(tmp_data)
        assert result["complete_profiles"] == 3
        assert result["total_profiles"] == 3

    @pytest.mark.asyncio
    async def test_process_creates_souls_dir(self, tmp_path, sample_skills, sample_voice):
        """souls/ directory is created if it doesn't exist."""
        data = tmp_path / "data"
        data.mkdir()
        (data / "skills").mkdir()
        (data / "voices").mkdir()
        # No souls/ dir
        (data / "skills" / "alice.json").write_text(json.dumps(sample_skills))
        (data / "voices" / "alice.json").write_text(json.dumps(sample_voice))

        result = await process_souls(data)
        assert result is not None
        assert (data / "souls").exists()


# ---------------------------------------------------------------------------
# publish_soul_profiles / publish_profile_updates
# ---------------------------------------------------------------------------


class TestPublishing:
    @pytest.mark.asyncio
    async def test_publish_soul_profiles(self, mock_em_client, tmp_data):
        stats = {"total_profiles": 10, "complete_profiles": 8, "new_profiles": 3, "updated_profiles": 7}
        with patch("services.soul_extractor_service.publish_offering_deduped", new_callable=AsyncMock) as mock_pub:
            mock_pub.return_value = {"id": "pub-1"}
            result = await publish_soul_profiles(mock_em_client, tmp_data, stats)
            assert result == {"id": "pub-1"}
            mock_pub.assert_called_once()
            call_kwargs = mock_pub.call_args[1]
            assert "10" in call_kwargs["title"]
            assert call_kwargs["bounty_usd"] == 0.08

    @pytest.mark.asyncio
    async def test_publish_profile_updates_with_changes(self, mock_em_client):
        stats = {"updated_profiles": 5}
        with patch("services.soul_extractor_service.publish_offering_deduped", new_callable=AsyncMock) as mock_pub:
            mock_pub.return_value = {"id": "pub-update"}
            result = await publish_profile_updates(mock_em_client, stats)
            assert result is not None
            call_kwargs = mock_pub.call_args[1]
            assert call_kwargs["bounty_usd"] == 0.04

    @pytest.mark.asyncio
    async def test_publish_profile_updates_no_changes(self, mock_em_client):
        stats = {"updated_profiles": 0}
        with patch("services.soul_extractor_service.publish_offering_deduped", new_callable=AsyncMock) as mock_pub:
            result = await publish_profile_updates(mock_em_client, stats)
            assert result is None
            mock_pub.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_dry_run(self, mock_em_client, tmp_data):
        stats = {"total_profiles": 5, "complete_profiles": 3, "new_profiles": 2, "updated_profiles": 3}
        with patch("services.soul_extractor_service.publish_offering_deduped", new_callable=AsyncMock) as mock_pub:
            mock_pub.return_value = None
            await publish_soul_profiles(mock_em_client, tmp_data, stats, dry_run=True)
            call_kwargs = mock_pub.call_args[1]
            assert call_kwargs["dry_run"] is True


# ---------------------------------------------------------------------------
# seller_flow
# ---------------------------------------------------------------------------


class TestSellerFlow:
    @pytest.mark.asyncio
    async def test_seller_flow_finds_soul_bounties(self, mock_em_client, tmp_data):
        with patch("services.soul_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = [
                {"id": "b1", "title": "[KK Request] Complete Soul Profiles", "bounty_usdc": 0.08},
                {"id": "b2", "title": "[KK Request] Voice Data", "bounty_usdc": 0.04},
            ]
            with patch("services.soul_extractor_service.apply_to_bounty", new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = True
                with patch("services.soul_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                    mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                    result = await seller_flow(mock_em_client, tmp_data)
                    assert result["bounties_found"] == 1  # only soul-related
                    assert result["applied"] == 1

    @pytest.mark.asyncio
    async def test_seller_flow_no_bounties(self, mock_em_client, tmp_data):
        with patch("services.soul_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = []
            with patch("services.soul_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                result = await seller_flow(mock_em_client, tmp_data)
                assert result["bounties_found"] == 0
                assert result["applied"] == 0

    @pytest.mark.asyncio
    async def test_seller_flow_error_handling(self, mock_em_client, tmp_data):
        with patch("services.soul_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_discover:
            mock_discover.side_effect = Exception("API down")
            with patch("services.soul_extractor_service.load_escrow_state") as mock_load:
                mock_load.return_value = {"published": {}, "applied": {}}
                with patch("services.soul_extractor_service.save_escrow_state"):
                    result = await seller_flow(mock_em_client, tmp_data)
                    assert len(result["errors"]) == 1
                    assert "API down" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_seller_flow_dry_run_skips_save(self, mock_em_client, tmp_data):
        with patch("services.soul_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = []
            with patch("services.soul_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                with patch("services.soul_extractor_service.save_escrow_state") as mock_save:
                    await seller_flow(mock_em_client, tmp_data, dry_run=True)
                    mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_seller_flow_max_3_applications(self, mock_em_client, tmp_data):
        bounties = [
            {"id": f"b{i}", "title": f"[KK Request] Soul Profiles {i}", "bounty_usdc": 0.08}
            for i in range(5)
        ]
        with patch("services.soul_extractor_service.discover_bounties", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = bounties
            with patch("services.soul_extractor_service.apply_to_bounty", new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = True
                with patch("services.soul_extractor_service.fulfill_assigned", new_callable=AsyncMock) as mock_fulfill:
                    mock_fulfill.return_value = {"submitted": 0, "completed": 0}
                    result = await seller_flow(mock_em_client, tmp_data)
                    # Should cap at 3 applications
                    assert mock_apply.call_count == 3
                    assert result["applied"] == 3
