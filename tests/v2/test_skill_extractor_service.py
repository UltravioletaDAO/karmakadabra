"""
Tests for skill_extractor_service.py — Data Refinery Service

Covers:
  - Skill keyword extraction pipeline
  - discover_data_offerings (EM browse + filtering)
  - buy_data (budget, apply, dry run)
  - process_skills (message parsing, profile generation, stats)
  - publish_enriched_profiles
  - seller_flow (discover → apply → fulfill)
  - Edge cases: empty messages, non-English text, budget limits
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from services.skill_extractor_service import (
    SKILL_KEYWORDS,
    _extract_skills_from_messages,
    buy_data,
    discover_data_offerings,
    process_skills,
    publish_enriched_profiles,
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
    (data / "purchases").mkdir()
    return data


@pytest.fixture
def mock_em_client():
    """Mock EMClient for testing."""
    client = MagicMock()
    client.agent = MagicMock()
    client.agent.name = "kk-skill-extractor"
    client.agent.wallet_address = "0xSKILLEXTRACTOR"
    client.agent.executor_id = "exec-001"
    client.agent.can_spend = MagicMock(return_value=True)
    client.agent.record_spend = MagicMock()
    client.agent.daily_spent_usd = 0.0
    client.agent.daily_budget_usd = 1.0
    client.close = AsyncMock()
    client.browse_tasks = AsyncMock(return_value=[])
    client.apply_to_task = AsyncMock(return_value={"status": "applied"})
    return client


@pytest.fixture
def sample_messages():
    """Sample chat messages for skill extraction."""
    return [
        {"user": "alice", "message": "I've been working with Python and Django a lot lately"},
        {"user": "alice", "message": "Setting up a FastAPI service with pandas for data analysis"},
        {"user": "alice", "message": "Also deployed it on AWS with docker and kubernetes"},
        {"user": "bob", "message": "Wrote a smart contract in Solidity using Hardhat"},
        {"user": "bob", "message": "Testing on the EVM testnet now"},
        {"user": "bob", "message": "The DeFi yield farming protocol is looking good, APY is high"},
        {"user": "bob", "message": "AMM liquidity pool swap mechanism is working"},
        {"user": "carol", "message": "hola buenas, estoy aprendiendo sobre blockchain y web3"},
        {"user": "carol", "message": "los tokens y wallets en la mainnet son interesantes"},
        {"user": "carol", "message": "quiero crear una DAO con governance y proposals"},
        {"user": "dave", "message": "hi"},
        {"user": "dave", "message": "ok"},
        # dave has too few messages to be processed
    ]


# ---------------------------------------------------------------------------
# Skill Keywords Tests
# ---------------------------------------------------------------------------


class TestSkillKeywords:
    def test_all_categories_have_keywords(self):
        for category, keywords in SKILL_KEYWORDS.items():
            assert len(keywords) > 0, f"Category '{category}' has no keywords"
            assert all(isinstance(kw, str) for kw in keywords)

    def test_keywords_are_lowercase(self):
        for category, keywords in SKILL_KEYWORDS.items():
            for kw in keywords:
                assert kw == kw.lower(), f"Keyword '{kw}' in '{category}' is not lowercase"

    def test_no_duplicate_categories(self):
        categories = list(SKILL_KEYWORDS.keys())
        assert len(categories) == len(set(categories))

    def test_expected_categories_exist(self):
        expected = {"Python", "JavaScript", "Solidity", "DeFi", "AI/ML", "DevOps", "Blockchain"}
        for cat in expected:
            assert cat in SKILL_KEYWORDS


# ---------------------------------------------------------------------------
# Skill Extraction Pipeline Tests
# ---------------------------------------------------------------------------


class TestExtractSkillsFromMessages:
    def test_basic_extraction(self, tmp_path, sample_messages):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _extract_skills_from_messages(sample_messages, skills_dir)

        # Alice should have Python and DevOps skills
        alice_profile = skills_dir / "alice.json"
        assert alice_profile.exists()
        profile = json.loads(alice_profile.read_text())
        skill_names = [s["skill"] for s in profile["top_skills"]]
        assert "Python" in skill_names
        assert "DevOps" in skill_names

    def test_solidity_defi_detection(self, tmp_path, sample_messages):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _extract_skills_from_messages(sample_messages, skills_dir)

        bob_profile = skills_dir / "bob.json"
        assert bob_profile.exists()
        profile = json.loads(bob_profile.read_text())
        skill_names = [s["skill"] for s in profile["top_skills"]]
        assert "Solidity" in skill_names or "DeFi" in skill_names

    def test_spanish_language_detection(self, tmp_path, sample_messages):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _extract_skills_from_messages(sample_messages, skills_dir)

        carol_profile = skills_dir / "carol.json"
        assert carol_profile.exists()
        profile = json.loads(carol_profile.read_text())
        assert profile["primary_language"] == "spanish"

    def test_english_language_detection(self, tmp_path, sample_messages):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _extract_skills_from_messages(sample_messages, skills_dir)

        alice_profile = skills_dir / "alice.json"
        profile = json.loads(alice_profile.read_text())
        assert profile["primary_language"] == "english"

    def test_skips_users_with_few_messages(self, tmp_path, sample_messages):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _extract_skills_from_messages(sample_messages, skills_dir)

        # dave has only 2 messages → should be skipped
        dave_profile = skills_dir / "dave.json"
        assert not dave_profile.exists()

    def test_empty_messages(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _extract_skills_from_messages([], skills_dir)
        assert len(list(skills_dir.glob("*.json"))) == 0

    def test_messages_without_user_field(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        messages = [
            {"text": "hello world"},
            {"user": "", "message": "no user"},
        ]
        _extract_skills_from_messages(messages, skills_dir)
        assert len(list(skills_dir.glob("*.json"))) == 0

    def test_skill_scores_bounded(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        # User with many keyword hits
        messages = [
            {"user": "pro", "message": f"python django flask fastapi pip pandas numpy {i}"}
            for i in range(10)
        ]
        _extract_skills_from_messages(messages, skills_dir)
        profile = json.loads((skills_dir / "pro.json").read_text())
        for skill in profile["top_skills"]:
            assert 0 <= skill["score"] <= 1.0

    def test_profile_has_required_fields(self, tmp_path, sample_messages):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _extract_skills_from_messages(sample_messages, skills_dir)

        for profile_path in skills_dir.glob("*.json"):
            profile = json.loads(profile_path.read_text())
            assert "username" in profile
            assert "total_messages" in profile
            assert "primary_language" in profile
            assert "top_skills" in profile
            assert "extracted_at" in profile

    def test_sender_field_alias(self, tmp_path):
        """Messages with 'sender' instead of 'user' are handled."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        messages = [
            {"sender": "eve", "text": "python is great for AI and machine learning"},
            {"sender": "eve", "text": "training a model with tensorflow"},
            {"sender": "eve", "text": "gpt and claude are amazing LLMs"},
        ]
        _extract_skills_from_messages(messages, skills_dir)
        assert (skills_dir / "eve.json").exists()


# ---------------------------------------------------------------------------
# Discover Data Offerings Tests
# ---------------------------------------------------------------------------


class TestDiscoverDataOfferings:
    @pytest.mark.asyncio
    async def test_filters_kk_data_tasks(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"id": "t1", "title": "[KK Data] Raw Chat Logs", "bounty_usdc": 0.01},
            {"id": "t2", "title": "Random task", "bounty_usdc": 0.50},
            {"id": "t3", "title": "[KK Data] Raw Twitch Data", "bounty_usdc": 0.01},
        ])

        offerings = await discover_data_offerings(mock_em_client)
        assert len(offerings) == 2
        assert all("[KK Data]" in o["title"] for o in offerings)

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[])
        offerings = await discover_data_offerings(mock_em_client)
        assert offerings == []

    @pytest.mark.asyncio
    async def test_no_matching_titles(self, mock_em_client):
        mock_em_client.browse_tasks = AsyncMock(return_value=[
            {"id": "t1", "title": "Unrelated task", "bounty_usdc": 1.00},
        ])
        offerings = await discover_data_offerings(mock_em_client)
        assert offerings == []


# ---------------------------------------------------------------------------
# Buy Data Tests
# ---------------------------------------------------------------------------


class TestBuyData:
    @pytest.mark.asyncio
    async def test_buy_success(self, mock_em_client):
        task = {"id": "t-001", "title": "[KK Data] Raw Logs", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task)
        assert result is not None
        mock_em_client.apply_to_task.assert_called_once()
        mock_em_client.agent.record_spend.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_budget_exceeded(self, mock_em_client):
        mock_em_client.agent.can_spend = MagicMock(return_value=False)
        task = {"id": "t-001", "title": "test", "bounty_usdc": 10.00}
        result = await buy_data(mock_em_client, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_buy_dry_run(self, mock_em_client):
        task = {"id": "t-001", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task, dry_run=True)
        assert result is None
        mock_em_client.apply_to_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_no_executor_id(self, mock_em_client):
        mock_em_client.agent.executor_id = ""
        task = {"id": "t-001", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_buy_already_applied(self, mock_em_client):
        mock_em_client.apply_to_task = AsyncMock(side_effect=Exception("409 conflict"))
        task = {"id": "t-001", "title": "test", "bounty_usdc": 0.01}
        result = await buy_data(mock_em_client, task)
        assert result is None  # Graceful handling


# ---------------------------------------------------------------------------
# Process Skills Tests
# ---------------------------------------------------------------------------


class TestProcessSkills:
    @pytest.mark.asyncio
    async def test_process_from_purchases(self, tmp_data, sample_messages):
        # Write purchase file
        purchase_file = tmp_data / "purchases" / "batch1.json"
        purchase_file.write_text(json.dumps(sample_messages))

        stats = await process_skills(tmp_data)
        assert stats is not None
        assert stats["total_profiles"] >= 2  # alice, bob, carol
        assert stats["unique_skills"] > 0
        assert len(stats["top_skills"]) > 0

    @pytest.mark.asyncio
    async def test_process_existing_profiles(self, tmp_data):
        # Pre-existing skill profiles
        for i, name in enumerate(["user1", "user2", "user3"]):
            (tmp_data / "skills" / f"{name}.json").write_text(json.dumps({
                "username": name,
                "top_skills": [{"skill": "Python", "score": 0.8}],
            }))

        stats = await process_skills(tmp_data)
        assert stats is not None
        assert stats["total_profiles"] == 3

    @pytest.mark.asyncio
    async def test_process_empty_data(self, tmp_data):
        stats = await process_skills(tmp_data)
        assert stats is None  # No profiles found

    @pytest.mark.asyncio
    async def test_process_handles_dict_format(self, tmp_data):
        """Handle {messages: [...]} format."""
        purchase = tmp_data / "purchases" / "wrapped.json"
        purchase.write_text(json.dumps({
            "messages": [
                {"user": "test", "message": "python django flask fastapi"},
                {"user": "test", "message": "docker kubernetes aws"},
                {"user": "test", "message": "terraform deploy ci/cd"},
            ]
        }))

        stats = await process_skills(tmp_data)
        assert stats is not None
        assert stats["total_profiles"] >= 1

    @pytest.mark.asyncio
    async def test_process_corrupted_file(self, tmp_data):
        """Corrupted purchase files are skipped gracefully."""
        (tmp_data / "purchases" / "bad.json").write_text("NOT JSON")
        (tmp_data / "purchases" / "good.json").write_text(json.dumps([
            {"user": "good", "message": "python django flask"},
            {"user": "good", "message": "aws docker kubernetes"},
            {"user": "good", "message": "terraform deployment pipeline"},
        ]))

        stats = await process_skills(tmp_data)
        assert stats is not None  # Good file still processed

    @pytest.mark.asyncio
    async def test_process_creates_skills_dir(self, tmp_path):
        """Skills dir created if not exists."""
        data = tmp_path / "data"
        data.mkdir()
        (data / "purchases").mkdir()
        (data / "purchases" / "msgs.json").write_text(json.dumps([
            {"user": "x", "message": "solidity smart contract hardhat"},
            {"user": "x", "message": "evm foundry remix"},
            {"user": "x", "message": "blockchain web3 crypto"},
        ]))

        stats = await process_skills(data)
        assert (data / "skills").exists()


# ---------------------------------------------------------------------------
# Publish Enriched Profiles Tests
# ---------------------------------------------------------------------------


class TestPublishEnrichedProfiles:
    @pytest.mark.asyncio
    async def test_publish_success(self, mock_em_client, tmp_data):
        with patch("services.skill_extractor_service.publish_offering_deduped",
                    new_callable=AsyncMock, return_value={"task_id": "pub-001"}):
            result = await publish_enriched_profiles(
                mock_em_client, tmp_data,
                {"total_profiles": 50, "unique_skills": 12},
            )
        assert result is not None

    @pytest.mark.asyncio
    async def test_publish_dry_run(self, mock_em_client, tmp_data):
        with patch("services.skill_extractor_service.publish_offering_deduped",
                    new_callable=AsyncMock, return_value=None) as mock_pub:
            await publish_enriched_profiles(
                mock_em_client, tmp_data,
                {"total_profiles": 50, "unique_skills": 12},
                dry_run=True,
            )
        mock_pub.assert_called_once()
        assert mock_pub.call_args.kwargs["dry_run"] is True


# ---------------------------------------------------------------------------
# Seller Flow Tests
# ---------------------------------------------------------------------------


class TestSellerFlow:
    @pytest.mark.asyncio
    async def test_seller_flow_no_bounties(self, mock_em_client, tmp_data):
        with patch("services.skill_extractor_service.discover_bounties",
                    new_callable=AsyncMock, return_value=[]), \
             patch("services.skill_extractor_service.apply_to_bounty",
                    new_callable=AsyncMock), \
             patch("services.skill_extractor_service.fulfill_assigned",
                    new_callable=AsyncMock, return_value={"submitted": 0, "completed": 0}), \
             patch("services.skill_extractor_service.save_escrow_state"), \
             patch("services.skill_extractor_service.load_escrow_state",
                    return_value={"published": {}, "applied": {}}):
            result = await seller_flow(mock_em_client, tmp_data)

        assert result["bounties_found"] == 0
        assert result["applied"] == 0

    @pytest.mark.asyncio
    async def test_seller_flow_with_matching_bounties(self, mock_em_client, tmp_data):
        bounties = [
            {"id": "b1", "title": "[KK Request] Skill Profiles", "bounty_usd": 0.05},
            {"id": "b2", "title": "[KK Request] Something Else", "bounty_usd": 0.03},
        ]
        with patch("services.skill_extractor_service.discover_bounties",
                    new_callable=AsyncMock, return_value=bounties), \
             patch("services.skill_extractor_service.apply_to_bounty",
                    new_callable=AsyncMock, return_value=True) as mock_apply, \
             patch("services.skill_extractor_service.fulfill_assigned",
                    new_callable=AsyncMock, return_value={"submitted": 0, "completed": 0}), \
             patch("services.skill_extractor_service.save_escrow_state"), \
             patch("services.skill_extractor_service.load_escrow_state",
                    return_value={"published": {}, "applied": {}}):
            result = await seller_flow(mock_em_client, tmp_data)

        assert result["bounties_found"] == 1  # Only "skill" bounty matches
        assert result["applied"] == 1

    @pytest.mark.asyncio
    async def test_seller_flow_error_handling(self, mock_em_client, tmp_data):
        with patch("services.skill_extractor_service.discover_bounties",
                    new_callable=AsyncMock, side_effect=Exception("Network error")), \
             patch("services.skill_extractor_service.save_escrow_state"), \
             patch("services.skill_extractor_service.load_escrow_state",
                    return_value={"published": {}, "applied": {}}):
            result = await seller_flow(mock_em_client, tmp_data)

        assert len(result["errors"]) > 0
        assert "Network error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_seller_flow_dry_run_no_save(self, mock_em_client, tmp_data):
        with patch("services.skill_extractor_service.discover_bounties",
                    new_callable=AsyncMock, return_value=[]), \
             patch("services.skill_extractor_service.fulfill_assigned",
                    new_callable=AsyncMock, return_value={"submitted": 0, "completed": 0}), \
             patch("services.skill_extractor_service.save_escrow_state") as mock_save, \
             patch("services.skill_extractor_service.load_escrow_state",
                    return_value={"published": {}, "applied": {}}):
            await seller_flow(mock_em_client, tmp_data, dry_run=True)

        mock_save.assert_not_called()
