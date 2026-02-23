"""
Karma Kadabra V2 — Task 2.5: SOUL.md Generator

Combines skills + voice + stats to generate OpenClaw-compatible SOUL.md
personality files for each agent in the swarm.

Usage:
  python generate-soul.py
  python generate-soul.py --output souls/ --top 34
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# SOUL.md template
# ---------------------------------------------------------------------------


def generate_soul_md(username: str, stats: dict, skills: dict, voice: dict) -> str:
    """Generate a SOUL.md file for an OpenClaw agent."""

    # --- Identity section ---
    primary_lang = skills.get("primary_language", "spanish")
    lang_str = "Spanish (primary)" if primary_lang == "spanish" else f"{primary_lang.title()} (primary)"
    lang_map = skills.get("languages", {})
    if len(lang_map) > 1:
        secondary = [l for l in lang_map if l != primary_lang]
        if secondary:
            lang_str += f", {secondary[0].title()} (secondary)"

    # --- Personality from voice ---
    tone = voice.get("tone", {}).get("primary", "conversational")
    social_role = voice.get("communication_style", {}).get("social_role", "regular")
    risk = voice.get("personality", {}).get("risk_tolerance", "moderate")
    greeting = voice.get("communication_style", {}).get("greeting_style", "gm")
    formality = voice.get("personality", {}).get("formality", "informal")
    avg_msg_len = voice.get("communication_style", {}).get("avg_message_length", 40)

    # Signature phrases
    phrases = voice.get("vocabulary", {}).get("signature_phrases", [])
    phrase_list = [f'"{p["phrase"]}"' for p in phrases[:5]]

    # Slang
    slang = voice.get("vocabulary", {}).get("slang_usage", {})
    slang_words = []
    for cat, data in slang.items():
        for item in data.get("top", [])[:3]:
            slang_words.append(item["word"])

    # --- Skills section ---
    skill_lines = []
    for cat, data in skills.get("skills", {}).items():
        for sub in data.get("sub_skills", [])[:3]:
            score = sub["score"]
            if score >= 0.7:
                confidence = "high"
            elif score >= 0.4:
                confidence = "medium"
            else:
                confidence = "low"
            skill_lines.append(f"- **{sub['name']}** ({cat}) — confidence: {confidence}")

    if not skill_lines:
        skill_lines = ["- Community participation — confidence: medium"]

    # Top skills for specialization
    top_skills = skills.get("top_skills", [])
    specialization = top_skills[0]["skill"] if top_skills else "Community Member"

    # --- Topics ---
    topics = stats.get("topics", {})
    topic_list = list(topics.keys())[:5]

    # --- Economic behavior ---
    risk_descriptions = {
        "aggressive": "Takes bold positions, willing to go all-in on high-conviction plays",
        "moderate": "Balanced approach, diversifies across opportunities",
        "conservative": "Careful with capital, prefers stable and proven strategies",
        "unknown": "Adapts spending to opportunity quality",
    }

    # Task type preferences based on skills
    task_types = []
    skill_categories = list(skills.get("skills", {}).keys())
    if "Programming" in skill_categories or "AI/ML" in skill_categories:
        task_types.append("digital_physical")
    if "Design" in skill_categories:
        task_types.append("simple_action")
    if "Business" in skill_categories or "Community" in skill_categories:
        task_types.append("knowledge_access")
    if not task_types:
        task_types = ["simple_action", "knowledge_access"]

    # Communication style description
    style_desc = _describe_communication_style(tone, social_role, formality, avg_msg_len)

    # --- Monetizable capabilities ---
    monetizable = []
    for ts in top_skills[:3]:
        service = _skill_to_service(ts["skill"], ts["category"])
        if service:
            monetizable.append(service)

    if not monetizable:
        monetizable.append({
            "capability": "Community Insight",
            "service": "Share knowledge about Ultravioleta DAO community dynamics and trends",
        })

    monetizable_lines = []
    for m in monetizable:
        monetizable_lines.append(f"- **{m['capability']}**: {m['service']}")

    # --- Build the SOUL.md ---
    soul = f"""# Soul of {username}

## Identity
You are **{username}**'s digital twin in the Ultravioleta DAO. You represent their personality,
knowledge, and communication style in the agent economy. You transact on Execution Market,
buy and sell data, and interact with other agents on IRC.

- **Origin**: Extracted from Twitch chat logs (Ultravioleta DAO streams)
- **Language**: {lang_str}
- **Messages analyzed**: {stats.get('total_messages', 0)} across {stats.get('active_dates', 0)} sessions
- **Specialization**: {specialization}

## Personality
- **Tone**: {tone.title()} — {style_desc}
- **Formality**: {formality.title()}
- **Social role**: {social_role.replace('_', ' ').title()}
- **Greeting style**: "{greeting}"
"""

    if phrase_list:
        soul += f"- **Signature phrases**: {', '.join(phrase_list)}\n"

    if slang_words:
        soul += f"- **Slang**: {', '.join(slang_words[:8])}\n"

    soul += f"""
## Communication Guidelines
- Write messages that average ~{int(avg_msg_len)} characters
- {{"inquisitive": "Ask lots of questions — you're naturally curious", "enthusiastic": "Use exclamations and hype — you're energetic!", "analytical": "Provide detailed analysis and explanations", "reactive": "Keep responses short and punchy", "conversational": "Balance questions with opinions naturally"}.get(tone, "Communicate authentically and naturally")}
- {"Speak primarily in Spanish with occasional English crypto/tech terms" if primary_lang == "spanish" else "Speak primarily in English"}
- Match the energy of the chat — adapt but stay true to your personality

## Skills & Expertise
{chr(10).join(skill_lines)}

## Interests
{chr(10).join(f"- {t.title()}" for t in topic_list) if topic_list else "- Web3 community and culture"}

## Economic Behavior
- **Risk tolerance**: {risk.title()} — {risk_descriptions.get(risk, risk_descriptions['unknown'])}
- **Preferred task types**: {', '.join(task_types)}
- **Max spend per transaction**: $0.50 USDC (start conservative, scale with reputation)
- **Negotiation style**: {"Firm — knows value and holds price" if risk == "aggressive" else "Flexible — willing to negotiate for good deals" if risk == "moderate" else "Generous — prioritizes relationships over margins"}

## Monetizable Capabilities
{chr(10).join(monetizable_lines)}

## Agent Rules
1. Never spend more than your daily budget ($2.00 USDC)
2. Always verify task requirements before accepting
3. Prioritize tasks that match your skill profile
4. Rate other agents honestly after interactions
5. Report suspicious tasks or scam attempts
6. Maintain your reputation score above 60 (Plata tier)
7. Participate in IRC channels relevant to your interests
"""

    return soul.strip() + "\n"


def _describe_communication_style(tone: str, role: str, formality: str, avg_len: float) -> str:
    """Generate a natural description of communication style."""
    descriptions = {
        "inquisitive": "always asking questions, eager to learn and understand",
        "enthusiastic": "high energy, uses exclamations, hypes up the community",
        "analytical": "detailed and thoughtful, provides in-depth analysis",
        "reactive": "quick responses, memes and reactions, keeps the chat lively",
        "conversational": "natural flow, mixes opinions with questions",
    }
    return descriptions.get(tone, "authentic and engaged")


def _skill_to_service(skill: str, category: str) -> dict | None:
    """Map a skill to a potential service offering."""
    services = {
        "Python": {"capability": "Python Development", "service": "Build automation scripts, APIs, and data processing tools"},
        "JavaScript": {"capability": "Web Development", "service": "Create web apps, bots, and integrations"},
        "Solidity": {"capability": "Smart Contract Dev", "service": "Write, audit, and deploy smart contracts"},
        "DeFi": {"capability": "DeFi Strategy", "service": "Analyze yield opportunities and protocol mechanics"},
        "Trading": {"capability": "Trading Analysis", "service": "Technical analysis, market signals, and trade ideas"},
        "NFTs": {"capability": "NFT Curation", "service": "Discover, analyze, and recommend NFT collections"},
        "LLM": {"capability": "AI Integration", "service": "Build LLM-powered tools and agent workflows"},
        "Agents": {"capability": "Agent Development", "service": "Design and deploy autonomous AI agents"},
        "UI/UX": {"capability": "Design Services", "service": "Create interfaces and user experiences"},
        "Marketing": {"capability": "Content Strategy", "service": "Growth hacking, content creation, and community building"},
        "Teaching": {"capability": "Education", "service": "Tutorials, mentoring, and knowledge sharing"},
        "General": {"capability": "Development", "service": "General software development and problem solving"},
    }
    return services.get(skill)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate SOUL.md files for OpenClaw agents")
    parser.add_argument("--stats", type=str, default=None, help="User stats JSON (default: data/user-stats.json)")
    parser.add_argument("--skills-dir", type=str, default=None, help="Skills directory (default: data/skills/)")
    parser.add_argument("--voices-dir", type=str, default=None, help="Voices directory (default: data/voices/)")
    parser.add_argument("--output", type=str, default=None, help="Output directory for SOUL.md files (default: data/souls/)")
    parser.add_argument("--top", type=int, default=None, help="Override top-N from stats")
    args = parser.parse_args()

    base = Path(__file__).parent / "data"
    stats_path = Path(args.stats) if args.stats else base / "user-stats.json"
    skills_dir = Path(args.skills_dir) if args.skills_dir else base / "skills"
    voices_dir = Path(args.voices_dir) if args.voices_dir else base / "voices"
    output_dir = Path(args.output) if args.output else base / "souls"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate inputs
    for path, name in [(stats_path, "stats"), (skills_dir, "skills"), (voices_dir, "voices")]:
        if not path.exists():
            print(f"ERROR: {name} not found at {path}")
            print("Run the previous pipeline steps first.")
            sys.exit(1)

    # Load stats
    with open(stats_path, "r", encoding="utf-8") as f:
        stats_data = json.load(f)

    ranked = stats_data["ranking"]
    if args.top:
        ranked = ranked[: args.top]

    print(f"\nGenerating SOUL.md for {len(ranked)} agents...")

    generated = 0
    for user in ranked:
        username = user["username"]

        # Load skills
        skills_file = skills_dir / f"{username}.json"
        if not skills_file.exists():
            print(f"  WARNING: No skills for {username}, using defaults")
            skills = {"username": username, "skills": {}, "top_skills": [], "primary_language": "spanish", "languages": {}}
        else:
            with open(skills_file, "r", encoding="utf-8") as f:
                skills = json.load(f)

        # Load voice
        voice_file = voices_dir / f"{username}.json"
        if not voice_file.exists():
            print(f"  WARNING: No voice for {username}, using defaults")
            voice = {
                "username": username,
                "tone": {"primary": "conversational"},
                "communication_style": {"social_role": "regular", "greeting_style": "gm", "avg_message_length": 40},
                "vocabulary": {"signature_phrases": [], "slang_usage": {}},
                "personality": {"risk_tolerance": "moderate", "formality": "informal"},
            }
        else:
            with open(voice_file, "r", encoding="utf-8") as f:
                voice = json.load(f)

        # Generate SOUL.md
        soul_content = generate_soul_md(username, user, skills, voice)

        # Save
        soul_path = output_dir / f"{username}.md"
        with open(soul_path, "w", encoding="utf-8") as f:
            f.write(soul_content)

        generated += 1
        top_skill = skills["top_skills"][0]["skill"] if skills.get("top_skills") else "Community"
        tone = voice.get("tone", {}).get("primary", "?")
        print(f"  [{user['rank']:>3}] {username:<22} spec={top_skill:<18} tone={tone}")

    # Summary
    manifest = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "agent_count": generated,
        "agents": [
            {
                "username": u["username"],
                "rank": u["rank"],
                "engagement_score": u["engagement_score"],
                "soul_file": f"{u['username']}.md",
            }
            for u in ranked[:generated]
        ],
    }
    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {generated} SOUL.md files generated in {output_dir}/")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
