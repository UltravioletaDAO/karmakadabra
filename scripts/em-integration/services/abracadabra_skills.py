"""
Karma Kadabra V2 — Phase 10: Abracadabra Skills Registry

Defines Abracadabra's sellable content intelligence capabilities.
Each skill maps to an Execution Market task template with title,
description, category, and bounty.

Skills:
  - analyze_stream:   Full analysis of a Twitch stream session
  - predict_trending: 7-day trending topic predictions
  - generate_blog:    AI-generated blog post on a topic
  - suggest_clips:    Best moments for short-form clips
  - knowledge_graph:  Related topics, entities, connections
"""

from typing import Any

SKILLS: dict[str, dict[str, Any]] = {
    "analyze_stream": {
        "title": "[KK Content] Stream Analysis -- {stream_id}",
        "description": (
            "Full analysis of Twitch stream session.\n"
            "Includes: topic breakdown, engagement peaks, key moments,\n"
            "sentiment timeline, audience participation metrics.\n\n"
            "Delivery: JSON report URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.05,
        "evidence_type": "text",
    },
    "predict_trending": {
        "title": "[KK Content] Trending Topic Predictions -- {timeframe}",
        "description": (
            "7-day topic predictions with confidence scores.\n"
            "Based on chat log frequency analysis, cross-stream patterns,\n"
            "and community engagement velocity.\n\n"
            "Includes: top 10 rising topics, confidence %, supporting data.\n\n"
            "Delivery: JSON report URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.05,
        "evidence_type": "text",
    },
    "generate_blog": {
        "title": "[KK Content] Blog Post -- {topic}",
        "description": (
            "AI-generated blog post based on community discussion analysis.\n"
            "Length: 500-1000 words. Includes topic context, community quotes,\n"
            "key insights, and actionable takeaways.\n\n"
            "Delivery: Markdown file URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.10,
        "evidence_type": "text",
    },
    "suggest_clips": {
        "title": "[KK Content] Clip Suggestions -- {stream_id}",
        "description": (
            "Best moments for short-form clips from stream session.\n"
            "Each suggestion includes: timestamp range, topic, engagement spike,\n"
            "suggested title, estimated virality score.\n\n"
            "Delivery: JSON list URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.03,
        "evidence_type": "text",
    },
    "knowledge_graph": {
        "title": "[KK Content] Knowledge Graph -- {topic}",
        "description": (
            "Related topics, entities, and connections extracted from\n"
            "community discussions.\n"
            "Includes: entity nodes, relationship edges, centrality scores,\n"
            "temporal evolution of topic clusters.\n\n"
            "Delivery: JSON graph URL provided upon approval."
        ),
        "category": "knowledge_access",
        "bounty": 0.02,
        "evidence_type": "text",
    },
}

# Required fields that every skill must contain
REQUIRED_FIELDS = {"title", "description", "category", "bounty", "evidence_type"}


def get_skill(name: str) -> dict[str, Any] | None:
    """Get a skill definition by name. Returns None if not found."""
    return SKILLS.get(name)


def list_skills() -> list[str]:
    """Return list of all available skill names."""
    return list(SKILLS.keys())


def format_skill_title(name: str, **params: str) -> str:
    """Format a skill title with dynamic parameters.

    Args:
        name: Skill name (e.g., "analyze_stream").
        **params: Template parameters (e.g., stream_id="2026-02-19").

    Returns:
        Formatted title string, or empty string if skill not found.
    """
    skill = SKILLS.get(name)
    if not skill:
        return ""
    try:
        return skill["title"].format(**params)
    except KeyError:
        return skill["title"]


def get_skill_bounty(name: str) -> float:
    """Get the bounty for a skill. Returns 0.0 if not found."""
    skill = SKILLS.get(name)
    return skill["bounty"] if skill else 0.0


def validate_skills() -> list[str]:
    """Validate that all skills have required fields.

    Returns list of error messages (empty if all valid).
    """
    errors = []
    for name, skill in SKILLS.items():
        missing = REQUIRED_FIELDS - set(skill.keys())
        if missing:
            errors.append(f"Skill '{name}' missing fields: {missing}")
        if skill.get("bounty", 0) <= 0:
            errors.append(f"Skill '{name}' has invalid bounty: {skill.get('bounty')}")
    return errors
