"""
Tests for services/abracadabra_skills.py — Abracadabra Skills Registry

Covers:
  - SKILLS catalog (all 5 skills defined, required fields, pricing)
  - REQUIRED_FIELDS constant
  - get_skill (existing, unknown)
  - list_skills (all names, count)
  - format_skill_title (with params, missing params, unknown skill)
  - get_skill_bounty (existing, unknown)
  - validate_skills (all valid, catches missing fields, bad bounty)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services"))

from services.abracadabra_skills import (
    REQUIRED_FIELDS,
    SKILLS,
    format_skill_title,
    get_skill,
    get_skill_bounty,
    list_skills,
    validate_skills,
)


# ---------------------------------------------------------------------------
# SKILLS catalog
# ---------------------------------------------------------------------------


class TestSkillsCatalog:
    def test_all_skills_defined(self):
        expected = {"analyze_stream", "predict_trending", "generate_blog", "suggest_clips", "knowledge_graph"}
        assert set(SKILLS.keys()) == expected

    def test_skill_count(self):
        assert len(SKILLS) == 5

    def test_all_skills_have_required_fields(self):
        for name, skill in SKILLS.items():
            for field in REQUIRED_FIELDS:
                assert field in skill, f"Skill '{name}' missing '{field}'"

    def test_all_categories_knowledge_access(self):
        for name, skill in SKILLS.items():
            assert skill["category"] == "knowledge_access", f"Skill '{name}' wrong category"

    def test_bounties_positive(self):
        for name, skill in SKILLS.items():
            assert skill["bounty"] > 0, f"Skill '{name}' has non-positive bounty"

    def test_specific_bounties(self):
        assert SKILLS["analyze_stream"]["bounty"] == 0.05
        assert SKILLS["predict_trending"]["bounty"] == 0.05
        assert SKILLS["generate_blog"]["bounty"] == 0.10
        assert SKILLS["suggest_clips"]["bounty"] == 0.03
        assert SKILLS["knowledge_graph"]["bounty"] == 0.02

    def test_titles_have_placeholders(self):
        assert "{stream_id}" in SKILLS["analyze_stream"]["title"]
        assert "{timeframe}" in SKILLS["predict_trending"]["title"]
        assert "{topic}" in SKILLS["generate_blog"]["title"]
        assert "{stream_id}" in SKILLS["suggest_clips"]["title"]
        assert "{topic}" in SKILLS["knowledge_graph"]["title"]

    def test_all_evidence_type_text(self):
        for name, skill in SKILLS.items():
            assert skill["evidence_type"] == "text"

    def test_descriptions_non_empty(self):
        for name, skill in SKILLS.items():
            assert len(skill["description"]) > 20, f"Skill '{name}' description too short"


# ---------------------------------------------------------------------------
# REQUIRED_FIELDS
# ---------------------------------------------------------------------------


class TestRequiredFields:
    def test_required_fields(self):
        assert REQUIRED_FIELDS == {"title", "description", "category", "bounty", "evidence_type"}


# ---------------------------------------------------------------------------
# get_skill
# ---------------------------------------------------------------------------


class TestGetSkill:
    def test_existing_skill(self):
        skill = get_skill("analyze_stream")
        assert skill is not None
        assert skill["bounty"] == 0.05

    def test_unknown_skill(self):
        assert get_skill("nonexistent") is None

    def test_each_skill(self):
        for name in list_skills():
            assert get_skill(name) is not None


# ---------------------------------------------------------------------------
# list_skills
# ---------------------------------------------------------------------------


class TestListSkills:
    def test_returns_all(self):
        skills = list_skills()
        assert len(skills) == 5

    def test_returns_list(self):
        skills = list_skills()
        assert isinstance(skills, list)

    def test_contains_expected(self):
        skills = list_skills()
        assert "analyze_stream" in skills
        assert "generate_blog" in skills


# ---------------------------------------------------------------------------
# format_skill_title
# ---------------------------------------------------------------------------


class TestFormatSkillTitle:
    def test_format_with_params(self):
        title = format_skill_title("analyze_stream", stream_id="2026-02-19")
        assert "2026-02-19" in title
        assert "[KK Content]" in title

    def test_format_predict_trending(self):
        title = format_skill_title("predict_trending", timeframe="7-day")
        assert "7-day" in title

    def test_format_generate_blog(self):
        title = format_skill_title("generate_blog", topic="DeFi Strategies")
        assert "DeFi Strategies" in title

    def test_format_suggest_clips(self):
        title = format_skill_title("suggest_clips", stream_id="stream-42")
        assert "stream-42" in title

    def test_format_knowledge_graph(self):
        title = format_skill_title("knowledge_graph", topic="Solidity")
        assert "Solidity" in title

    def test_format_missing_param(self):
        # Missing param → returns unformatted title (with {placeholder})
        title = format_skill_title("analyze_stream")
        assert "{stream_id}" in title

    def test_format_unknown_skill(self):
        title = format_skill_title("nonexistent", x="y")
        assert title == ""


# ---------------------------------------------------------------------------
# get_skill_bounty
# ---------------------------------------------------------------------------


class TestGetSkillBounty:
    def test_existing_skill(self):
        assert get_skill_bounty("generate_blog") == 0.10

    def test_unknown_skill(self):
        assert get_skill_bounty("nonexistent") == 0.0

    def test_each_bounty(self):
        bounties = {name: get_skill_bounty(name) for name in list_skills()}
        assert all(b > 0 for b in bounties.values())


# ---------------------------------------------------------------------------
# validate_skills
# ---------------------------------------------------------------------------


class TestValidateSkills:
    def test_all_valid(self):
        errors = validate_skills()
        assert errors == []

    def test_catches_missing_field(self):
        from unittest.mock import patch
        bad_skills = {
            "broken": {"title": "test", "description": "test"}
        }
        with patch("services.abracadabra_skills.SKILLS", bad_skills):
            errors = validate_skills()
            assert len(errors) >= 1
            assert "missing fields" in errors[0]

    def test_catches_zero_bounty(self):
        from unittest.mock import patch
        bad_skills = {
            "zero_bounty": {
                "title": "t", "description": "d", "category": "c",
                "bounty": 0, "evidence_type": "text",
            }
        }
        with patch("services.abracadabra_skills.SKILLS", bad_skills):
            errors = validate_skills()
            assert len(errors) == 1
            assert "invalid bounty" in errors[0]

    def test_catches_negative_bounty(self):
        from unittest.mock import patch
        bad_skills = {
            "neg": {
                "title": "t", "description": "d", "category": "c",
                "bounty": -0.01, "evidence_type": "text",
            }
        }
        with patch("services.abracadabra_skills.SKILLS", bad_skills):
            errors = validate_skills()
            assert len(errors) == 1
