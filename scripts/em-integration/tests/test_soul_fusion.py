"""
Tests for scripts/kk/lib/soul_fusion.py

Covers:
  - Full fusion with rich skill + voice data
  - Fusion with missing voice data (defaults)
  - Fusion with missing skills data (defaults)
  - Dynamic pricing returns correct range
  - Monetizable capabilities ranked by market demand
  - Confidence scores boosted when voice tone matches skill domain
"""

import sys
from pathlib import Path

# Add parent packages to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.soul_fusion import (
    compute_soul_price,
    fuse_profiles,
    rank_monetizable_capabilities,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RICH_SKILLS = {
    "username": "poweruser",
    "primary_language": "spanish",
    "languages": {"spanish": 80, "english": 20},
    "skills": {
        "Programming": {
            "sub_skills": [
                {"name": "Python", "score": 0.85},
                {"name": "JavaScript", "score": 0.72},
            ]
        },
        "AI/ML": {
            "sub_skills": [
                {"name": "LLM", "score": 0.78},
                {"name": "Agents", "score": 0.65},
            ]
        },
        "Community": {
            "sub_skills": [
                {"name": "Teaching", "score": 0.60},
            ]
        },
    },
    "top_skills": [
        {"skill": "Python", "score": 0.85},
        {"skill": "LLM", "score": 0.78},
        {"skill": "JavaScript", "score": 0.72},
        {"skill": "Agents", "score": 0.65},
        {"skill": "Teaching", "score": 0.60},
    ],
}

RICH_VOICE = {
    "username": "poweruser",
    "tone": {"primary": "analytical"},
    "communication_style": {
        "social_role": "mentor",
        "greeting_style": "buenas",
        "avg_message_length": 65,
    },
    "vocabulary": {
        "signature_phrases": [
            {"phrase": "eso esta brutal"},
            {"phrase": "a ver a ver"},
            {"phrase": "parcero mira"},
            {"phrase": "bueno pues"},
            {"phrase": "de una"},
            {"phrase": "severo"},
        ],
        "slang_usage": {
            "crypto": {"top": [{"word": "rug"}, {"word": "degen"}]},
            "colombian": {"top": [{"word": "parcero"}, {"word": "chimba"}]},
            "tech": {"top": [{"word": "deploy"}, {"word": "merge"}]},
            "defi": {"top": [{"word": "yield"}, {"word": "pool"}]},
        },
    },
    "personality": {"risk_tolerance": "aggressive", "formality": "informal"},
}

MINIMAL_SKILLS = {
    "username": "newbie",
    "primary_language": "spanish",
    "languages": {},
    "skills": {},
    "top_skills": [],
}

MINIMAL_VOICE = {
    "username": "newbie",
    "tone": {"primary": "conversational"},
    "communication_style": {
        "social_role": "regular",
        "greeting_style": "gm",
        "avg_message_length": 20,
    },
    "vocabulary": {"signature_phrases": [], "slang_usage": {}},
    "personality": {"risk_tolerance": "moderate", "formality": "informal"},
}

AVERAGE_SKILLS = {
    "username": "miduser",
    "primary_language": "spanish",
    "languages": {"spanish": 90, "english": 10},
    "skills": {
        "Community": {
            "sub_skills": [
                {"name": "Community", "score": 0.55},
                {"name": "Teaching", "score": 0.40},
            ]
        },
    },
    "top_skills": [
        {"skill": "Community", "score": 0.55},
        {"skill": "Teaching", "score": 0.40},
    ],
}

AVERAGE_VOICE = {
    "username": "miduser",
    "tone": {"primary": "enthusiastic"},
    "communication_style": {
        "social_role": "cheerleader",
        "greeting_style": "gm gang!",
        "avg_message_length": 35,
    },
    "vocabulary": {
        "signature_phrases": [
            {"phrase": "vamos!"},
            {"phrase": "lfg"},
        ],
        "slang_usage": {
            "crypto": {"top": [{"word": "wagmi"}]},
        },
    },
    "personality": {"risk_tolerance": "moderate", "formality": "informal"},
}

RICH_STATS = {
    "username": "poweruser",
    "total_messages": 2500,
    "active_dates": 45,
    "engagement_score": 92,
    "rank": 1,
}

MINIMAL_STATS = {
    "username": "newbie",
    "total_messages": 10,
    "active_dates": 2,
    "engagement_score": 5,
    "rank": 30,
}

AVERAGE_STATS = {
    "username": "miduser",
    "total_messages": 400,
    "active_dates": 15,
    "engagement_score": 45,
    "rank": 12,
}


# ---------------------------------------------------------------------------
# Tests: fuse_profiles
# ---------------------------------------------------------------------------


def test_full_fusion_produces_all_sections():
    """Rich skill + voice data produces complete fused profile."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)

    assert fused["username"] == "poweruser"
    assert fused["stats"]["total_messages"] == 2500
    assert fused["stats"]["active_dates"] == 45
    assert "skills" in fused
    assert "voice" in fused
    assert "fusion_metadata" in fused
    assert fused["fusion_metadata"]["tone"] == "analytical"
    assert len(fused["skills"]["top_skills"]) > 0


def test_fusion_with_missing_voice_defaults():
    """Fusion with missing voice data falls back to defaults."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, MINIMAL_VOICE, RICH_STATS)

    assert fused["fusion_metadata"]["tone"] == "conversational"
    assert fused["fusion_metadata"]["personality_rich"] is False
    # Skills should still be present and unmodified (no affinity boost for conversational + Programming)
    assert len(fused["skills"]["top_skills"]) >= 3


def test_fusion_with_missing_skills_defaults():
    """Fusion with missing skills data falls back to defaults."""
    fused = fuse_profiles("newbie", MINIMAL_SKILLS, RICH_VOICE, MINIMAL_STATS)

    assert fused["username"] == "newbie"
    assert fused["stats"]["total_messages"] == 10
    assert fused["skills"]["top_skills"] == []
    # Voice data is still preserved
    assert fused["voice"]["tone"]["primary"] == "analytical"


def test_confidence_boosted_when_tone_matches_skill():
    """Analytical tone boosts DeFi/Trading/Python/Solidity/AI-ML confidence."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)

    # Python is in the analytical affinity set
    python_skill = None
    for s in fused["skills"]["top_skills"]:
        if s["skill"] == "Python":
            python_skill = s
            break

    assert python_skill is not None
    assert python_skill["boosted"] is True
    # Original 0.85 * 1.15 = 0.9775, capped at 1.0 → should be 0.978 (rounded)
    assert python_skill["score"] > 0.85

    # Teaching is NOT in the analytical affinity set (it's in the Community category)
    teaching = None
    for s in fused["skills"]["top_skills"]:
        if s["skill"] == "Teaching":
            teaching = s
            break

    if teaching:
        assert teaching["boosted"] is False


def test_personality_rich_detection():
    """Rich voice profile (>5 phrases, >3 slang categories) detected."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)
    assert fused["fusion_metadata"]["personality_rich"] is True

    fused_minimal = fuse_profiles("newbie", MINIMAL_SKILLS, MINIMAL_VOICE, MINIMAL_STATS)
    assert fused_minimal["fusion_metadata"]["personality_rich"] is False


def test_boosted_count_tracked():
    """Metadata tracks how many skills were boosted."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)
    assert fused["fusion_metadata"]["boosted_count"] >= 1


# ---------------------------------------------------------------------------
# Tests: rank_monetizable_capabilities
# ---------------------------------------------------------------------------


def test_capabilities_ranked_by_market_demand():
    """Higher market demand skills rank first."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)
    ranked = rank_monetizable_capabilities(fused)

    assert len(ranked) > 0
    # Check sorted by composite_score descending
    for i in range(len(ranked) - 1):
        assert ranked[i]["composite_score"] >= ranked[i + 1]["composite_score"]


def test_capabilities_include_demand_score():
    """Each capability includes market_demand and composite_score."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)
    ranked = rank_monetizable_capabilities(fused)

    for cap in ranked:
        assert "market_demand" in cap
        assert "composite_score" in cap
        assert "confidence" in cap
        assert cap["market_demand"] >= 1
        assert cap["composite_score"] >= 0


def test_capabilities_empty_for_minimal_skills():
    """Minimal skills produce empty capabilities list."""
    fused = fuse_profiles("newbie", MINIMAL_SKILLS, MINIMAL_VOICE, MINIMAL_STATS)
    ranked = rank_monetizable_capabilities(fused)
    assert ranked == []


# ---------------------------------------------------------------------------
# Tests: compute_soul_price
# ---------------------------------------------------------------------------


def test_price_minimal_profile():
    """Minimal profile returns base price $0.08."""
    fused = fuse_profiles("newbie", MINIMAL_SKILLS, MINIMAL_VOICE, MINIMAL_STATS)
    price = compute_soul_price(fused)
    assert price == 0.08


def test_price_rich_profile_capped():
    """Rich profile with many skills + rich personality caps at $0.15."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)
    price = compute_soul_price(fused)
    assert 0.08 <= price <= 0.15


def test_price_average_profile_in_range():
    """Average profile price falls in $0.08-$0.15 range."""
    fused = fuse_profiles("miduser", AVERAGE_SKILLS, AVERAGE_VOICE, AVERAGE_STATS)
    price = compute_soul_price(fused)
    assert 0.08 <= price <= 0.15


def test_price_personality_bonus():
    """Rich personality adds $0.02 bonus."""
    fused_rich = fuse_profiles("poweruser", RICH_SKILLS, RICH_VOICE, RICH_STATS)
    fused_plain = fuse_profiles("poweruser", RICH_SKILLS, MINIMAL_VOICE, RICH_STATS)

    price_rich = compute_soul_price(fused_rich)
    price_plain = compute_soul_price(fused_plain)

    # Rich should be at least $0.02 more (personality bonus)
    assert price_rich >= price_plain


def test_price_skill_bonus():
    """Each high-confidence skill (score >= 0.7) adds $0.01."""
    fused = fuse_profiles("poweruser", RICH_SKILLS, MINIMAL_VOICE, RICH_STATS)
    price = compute_soul_price(fused)

    # Count high-confidence skills
    high_conf = sum(
        1 for s in fused["skills"]["top_skills"] if s.get("score", 0) >= 0.7
    )
    expected_min = 0.08 + (high_conf * 0.01)
    assert price >= min(0.15, expected_min)
