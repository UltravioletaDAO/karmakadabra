"""
Tests for Task 4.3: On-Chain Agent Profile Registration

Tests the pipeline: SOUL.md + skills + voice → agent-card.json
"""

import json
import sys
from pathlib import Path

import pytest

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from register_agent_profile import (
    extract_languages,
    extract_services,
    extract_skills_list,
    generate_agent_card,
    load_skills,
    load_voice,
)


# --- Fixtures ---


@pytest.fixture
def sample_skills():
    return {
        "username": "testuser",
        "primary_language": "spanish",
        "languages": {"spanish": 120, "english": 30},
        "skills": {
            "Programming": {
                "score": 0.6,
                "sub_skills": [
                    {"name": "Python", "score": 0.8},
                    {"name": "JavaScript", "score": 0.5},
                ],
            },
            "AI/ML": {
                "score": 0.4,
                "sub_skills": [
                    {"name": "LLM", "score": 0.6},
                    {"name": "General AI", "score": 0.3},
                ],
            },
        },
        "top_skills": [
            {"skill": "Python", "category": "Programming", "score": 0.8},
            {"skill": "LLM", "category": "AI/ML", "score": 0.6},
        ],
    }


@pytest.fixture
def sample_voice():
    return {
        "username": "testuser",
        "tone": {"primary": "analytical"},
        "communication_style": {
            "social_role": "regular",
            "greeting_style": "gm",
            "avg_message_length": 55,
        },
        "vocabulary": {"signature_phrases": [], "slang_usage": {}},
        "personality": {"risk_tolerance": "moderate", "formality": "informal"},
    }


@pytest.fixture
def empty_skills():
    return {
        "username": "empty",
        "skills": {},
        "top_skills": [],
        "primary_language": "spanish",
        "languages": {},
    }


@pytest.fixture
def empty_voice():
    return {
        "username": "empty",
        "tone": {},
        "personality": {},
    }


# --- Tests: extract_skills_list ---


class TestExtractSkillsList:
    def test_extracts_skills_above_threshold(self, sample_skills):
        result = extract_skills_list(sample_skills)
        assert len(result) >= 2
        names = [s["name"] for s in result]
        assert "Python" in names
        assert "JavaScript" in names

    def test_assigns_correct_levels(self, sample_skills):
        result = extract_skills_list(sample_skills)
        by_name = {s["name"]: s for s in result}
        assert by_name["Python"]["level"] == "expert"
        assert by_name["JavaScript"]["level"] == "intermediate"

    def test_empty_skills_returns_empty(self, empty_skills):
        result = extract_skills_list(empty_skills)
        assert result == []

    def test_filters_below_threshold(self):
        skills = {
            "skills": {
                "Programming": {
                    "sub_skills": [{"name": "Rust", "score": 0.1}]
                }
            }
        }
        result = extract_skills_list(skills)
        assert result == []


# --- Tests: extract_services ---


class TestExtractServices:
    def test_maps_skills_to_services(self, sample_skills):
        result = extract_services(sample_skills)
        assert len(result) >= 1
        names = [s["name"] for s in result]
        assert "Python Development" in names

    def test_default_service_when_no_skills(self, empty_skills):
        result = extract_services(empty_skills)
        assert len(result) == 1
        assert result[0]["name"] == "Community Insight"

    def test_max_three_services(self):
        skills = {
            "top_skills": [
                {"skill": "Python", "category": "Programming"},
                {"skill": "JavaScript", "category": "Programming"},
                {"skill": "Solidity", "category": "Blockchain"},
                {"skill": "LLM", "category": "AI/ML"},
            ]
        }
        result = extract_services(skills)
        assert len(result) <= 3


# --- Tests: extract_languages ---


class TestExtractLanguages:
    def test_primary_language(self, sample_skills):
        result = extract_languages(sample_skills)
        assert result[0] == "spanish"

    def test_includes_secondary(self, sample_skills):
        result = extract_languages(sample_skills)
        assert "english" in result

    def test_default_spanish(self, empty_skills):
        result = extract_languages(empty_skills)
        assert result == ["spanish"]


# --- Tests: generate_agent_card ---


class TestGenerateAgentCard:
    def test_basic_card_structure(self, sample_skills, sample_voice):
        card = generate_agent_card(
            agent_name="kk-testuser",
            username="testuser",
            wallet_address="0x1234",
            agent_id=18775,
            skills_data=sample_skills,
            voice_data=sample_voice,
            agent_type="user",
        )
        assert card["name"] == "kk-testuser"
        assert card["agent_type"] == "community_agent"
        assert card["identity"]["agent_id"] == 18775
        assert card["identity"]["wallet"] == "0x1234"
        assert card["identity"]["standard"] == "ERC-8004"
        assert card["identity"]["network"] == "base"
        assert card["category"] == "karma_kadabra_swarm"

    def test_system_agent_type(self, sample_skills, sample_voice):
        card = generate_agent_card(
            agent_name="kk-coordinator",
            username="coordinator",
            wallet_address="0x5678",
            agent_id=None,
            skills_data=sample_skills,
            voice_data=sample_voice,
            agent_type="system",
        )
        assert card["agent_type"] == "system_agent"
        assert "swarm_coordination" in card["capabilities"]
        assert "agent_id" not in card["identity"]

    def test_card_has_personality(self, sample_skills, sample_voice):
        card = generate_agent_card(
            agent_name="kk-testuser",
            username="testuser",
            wallet_address="0x1234",
            agent_id=None,
            skills_data=sample_skills,
            voice_data=sample_voice,
        )
        assert card["personality"]["tone"] == "analytical"
        assert card["personality"]["risk_tolerance"] == "moderate"
        assert card["personality"]["specialization"] == "Python"

    def test_card_has_payment_config(self, sample_skills, sample_voice):
        card = generate_agent_card(
            agent_name="kk-testuser",
            username="testuser",
            wallet_address="0x1234",
            agent_id=None,
            skills_data=sample_skills,
            voice_data=sample_voice,
        )
        assert card["payment"]["protocol"] == "x402"
        assert card["payment"]["gasless"] is True
        assert card["payment"]["daily_budget_usd"] == 2.0

    def test_card_has_swarm_info(self, sample_skills, sample_voice):
        card = generate_agent_card(
            agent_name="kk-testuser",
            username="testuser",
            wallet_address="0x1234",
            agent_id=None,
            skills_data=sample_skills,
            voice_data=sample_voice,
        )
        assert card["swarm"]["name"] == "karma_kadabra_v2"
        assert card["swarm"]["parent_agent_id"] == 2106

    def test_card_is_json_serializable(self, sample_skills, sample_voice):
        card = generate_agent_card(
            agent_name="kk-testuser",
            username="testuser",
            wallet_address="0x1234",
            agent_id=18775,
            skills_data=sample_skills,
            voice_data=sample_voice,
        )
        # Must not raise
        result = json.dumps(card, ensure_ascii=False)
        parsed = json.loads(result)
        assert parsed["name"] == "kk-testuser"

    def test_empty_data_still_generates(self, empty_skills, empty_voice):
        card = generate_agent_card(
            agent_name="kk-empty",
            username="empty",
            wallet_address="0x0000",
            agent_id=None,
            skills_data=empty_skills,
            voice_data=empty_voice,
        )
        assert card["name"] == "kk-empty"
        assert len(card["services"]) >= 1
        assert card["personality"]["specialization"] == "Community"

    def test_all_system_agents_have_descriptions(self, sample_skills, sample_voice):
        system_names = [
            "kk-coordinator",
            "kk-karma-hello",
            "kk-skill-extractor",
            "kk-voice-extractor",
            "kk-validator",
            "kk-soul-extractor",
        ]
        for name in system_names:
            card = generate_agent_card(
                agent_name=name,
                username=name.removeprefix("kk-"),
                wallet_address="0x1234",
                agent_id=None,
                skills_data=sample_skills,
                voice_data=sample_voice,
                agent_type="system",
            )
            assert "Swarm" in card["description"] or "sell" in card["description"] or "refin" in card["description"] or "profil" in card["description"] or "valid" in card["description"] or "merg" in card["description"]
