"""
Karma Kadabra V2 — Phase 8: Soul Fusion Library

Pure function library that merges skill + voice + stats data into unified
profile dicts suitable for generate_soul_md().

No EM dependencies — fully unit-testable data transformations.

Functions:
  fuse_profiles()               — Merge skill + voice + stats into unified dict
  rank_monetizable_capabilities() — Rank services by market demand
  compute_soul_price()          — Dynamic pricing: $0.08-$0.15 based on richness
"""

from __future__ import annotations


# Market demand ranking (higher = more demand in the KK economy)
MARKET_DEMAND = {
    "DeFi": 10,
    "Trading": 9,
    "Solidity": 9,
    "Agents": 8,
    "LLM": 8,
    "Python": 7,
    "JavaScript": 7,
    "Blockchain": 7,
    "AI/ML": 7,
    "Marketing": 6,
    "UI/UX": 5,
    "Design": 5,
    "Business": 4,
    "Teaching": 4,
    "Community": 3,
    "General": 2,
}

# Tone-skill affinity boost: if voice tone matches skill domain, boost confidence
TONE_SKILL_AFFINITY = {
    "analytical": {"DeFi", "Trading", "Python", "Solidity", "AI/ML"},
    "enthusiastic": {"Marketing", "Community", "Teaching", "NFTs"},
    "inquisitive": {"Agents", "LLM", "JavaScript", "General"},
    "reactive": {"Trading", "NFTs", "Community"},
    "conversational": {"Business", "Teaching", "Marketing"},
}


def fuse_profiles(
    username: str,
    skills_json: dict,
    voice_json: dict,
    user_stats: dict,
) -> dict:
    """Merge skill + voice + stats into a unified profile dict.

    The fused profile contains all data needed by generate_soul_md() plus
    composite confidence scores that factor in voice-skill affinity.

    Args:
        username: Agent username.
        skills_json: Skill profile from kk-skill-extractor.
        voice_json: Voice profile from kk-voice-extractor.
        user_stats: Engagement stats from user-stats.json ranking entry.

    Returns:
        Fused profile dict with boosted confidence scores and metadata.
    """
    tone = voice_json.get("tone", {}).get("primary", "conversational")
    affinity_skills = TONE_SKILL_AFFINITY.get(tone, set())

    # Boost skill confidence when voice tone shows affinity
    boosted_skills = {}
    for category, data in skills_json.get("skills", {}).items():
        boosted_subs = []
        for sub in data.get("sub_skills", []):
            score = sub.get("score", 0.0)
            # 15% boost if tone matches skill domain
            if category in affinity_skills or sub.get("name", "") in affinity_skills:
                score = min(1.0, score * 1.15)
            boosted_subs.append({**sub, "score": round(score, 3), "boosted": score != sub.get("score", 0.0)})
        boosted_skills[category] = {**data, "sub_skills": boosted_subs}

    # Recompute top_skills with boosted scores
    all_subs = []
    for category, data in boosted_skills.items():
        for sub in data.get("sub_skills", []):
            all_subs.append({
                "skill": sub.get("name", category),
                "category": category,
                "score": sub["score"],
                "boosted": sub.get("boosted", False),
            })
    all_subs.sort(key=lambda x: x["score"], reverse=True)
    top_skills = all_subs[:5]

    # Profile richness indicators
    signature_phrases = voice_json.get("vocabulary", {}).get("signature_phrases", [])
    slang_categories = voice_json.get("vocabulary", {}).get("slang_usage", {})
    personality_rich = len(signature_phrases) > 5 and len(slang_categories) > 3

    return {
        "username": username,
        "stats": {
            "total_messages": user_stats.get("total_messages", 0),
            "active_dates": user_stats.get("active_dates", 0),
            "engagement_score": user_stats.get("engagement_score", 0),
        },
        "skills": {
            **skills_json,
            "skills": boosted_skills,
            "top_skills": top_skills,
        },
        "voice": voice_json,
        "fusion_metadata": {
            "tone": tone,
            "affinity_skills": sorted(affinity_skills),
            "personality_rich": personality_rich,
            "total_skills": len(all_subs),
            "boosted_count": sum(1 for s in all_subs if s.get("boosted")),
        },
    }


def rank_monetizable_capabilities(fused: dict) -> list[dict]:
    """Rank services by market demand in the KK economy.

    Args:
        fused: Output of fuse_profiles().

    Returns:
        Sorted list of capabilities with demand scores.
    """
    capabilities = []
    seen = set()

    for skill in fused.get("skills", {}).get("top_skills", []):
        name = skill.get("skill", "General")
        category = skill.get("category", "General")

        # Use category for demand lookup, fall back to skill name
        demand = MARKET_DEMAND.get(name, MARKET_DEMAND.get(category, 2))

        if name not in seen:
            seen.add(name)
            capabilities.append({
                "skill": name,
                "category": category,
                "confidence": skill.get("score", 0.0),
                "market_demand": demand,
                "composite_score": round(skill.get("score", 0.0) * (demand / 10), 3),
            })

    capabilities.sort(key=lambda x: x["composite_score"], reverse=True)
    return capabilities


def compute_soul_price(fused: dict) -> float:
    """Compute dynamic pricing for a SOUL.md profile.

    Pricing formula:
      base = $0.08
      + $0.01 per high-confidence skill (score >= 0.7)
      + $0.02 if personality is rich (>5 phrases, >3 slang categories)
      cap = $0.15

    Args:
        fused: Output of fuse_profiles().

    Returns:
        Price in USD, between 0.08 and 0.15.
    """
    base = 0.08

    # Count high-confidence skills
    high_conf_skills = sum(
        1
        for s in fused.get("skills", {}).get("top_skills", [])
        if s.get("score", 0) >= 0.7
    )
    skill_bonus = high_conf_skills * 0.01

    # Personality richness bonus
    personality_bonus = 0.02 if fused.get("fusion_metadata", {}).get("personality_rich", False) else 0.0

    price = base + skill_bonus + personality_bonus
    return min(0.15, round(price, 2))
