"""
Simple Batch Profile Extraction Script
Extracts basic skill profiles for 48 users from local chat logs

Sprint 3, Task 1: Automated profile extraction (simplified version)
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import re

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


def extract_profile_from_logs(username: str, logs_dir: Path) -> dict:
    """
    Extract skill profile from user's chat logs

    Simplified version - analyzes message content for:
    - Interests (topics discussed)
    - Skills (technical mentions)
    - Tools/platforms (software/services)
    - Interaction style
    - Monetization potential
    """

    # Find all log files for this user
    user_files = list(logs_dir.glob(f"202510*/{username}.txt"))

    if not user_files:
        raise ValueError(f"No log files found for {username}")

    # Read all messages
    all_messages = []
    all_text = ""

    for log_file in user_files:
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        # Parse message format: [MM/DD/YYYY HH:MM:SS AM/PM] username: message
                        match = re.match(r'\[(.*?)\] (.*?): (.*)', line)
                        if match:
                            timestamp, msg_username, message = match.groups()
                            if msg_username.lower() == username.lower():
                                all_messages.append({
                                    "timestamp": timestamp,
                                    "message": message
                                })
                                all_text += " " + message.lower()
        except Exception as e:
            print(f"   ⚠️  Error reading {log_file}: {e}")

    if not all_messages:
        raise ValueError(f"No messages found for {username}")

    # Analyze content
    profile = analyze_content(username, all_messages, all_text)

    return profile


def analyze_content(username: str, messages: list, all_text: str) -> dict:
    """
    Analyze chat content to extract profile
    """

    # Interest keywords
    interest_keywords = {
        "Blockchain": ["blockchain", "crypto", "ethereum", "solidity", "smart contract", "defi", "nft", "web3", "avax", "avalanche"],
        "AI/ML": ["ai", "machine learning", "ml", "neural", "gpt", "model", "training", "llm", "chatgpt", "claude"],
        "Development": ["code", "programming", "developer", "software", "api", "backend", "frontend", "database"],
        "Gaming": ["game", "gaming", "play", "ps5", "xbox", "steam", "twitch", "stream"],
        "Design": ["design", "ui", "ux", "figma", "adobe", "photoshop", "illustrator"],
        "Business": ["business", "startup", "entrepreneur", "marketing", "sales", "revenue"],
        "Community": ["community", "social", "discord", "twitter", "reddit", "engagement"]
    }

    # Skill keywords
    skill_keywords = {
        "Python": ["python", "django", "flask", "pandas", "numpy"],
        "JavaScript": ["javascript", "js", "node", "react", "vue", "angular", "typescript"],
        "Solidity": ["solidity", "smart contract", "ethereum", "hardhat", "truffle"],
        "Rust": ["rust", "cargo", "wasm"],
        "Data Analysis": ["data", "analytics", "sql", "database", "query"],
        "DevOps": ["docker", "kubernetes", "aws", "cloud", "ci/cd", "devops"],
        "Content Creation": ["video", "editing", "streaming", "content", "youtube"]
    }

    # Tool keywords
    tool_keywords = {
        "Git/GitHub": ["git", "github", "gitlab", "commit", "pull request"],
        "VS Code": ["vscode", "vs code", "visual studio"],
        "Docker": ["docker", "container", "dockerfile"],
        "AWS": ["aws", "amazon", "ec2", "s3", "lambda"],
        "Discord": ["discord", "bot", "server"],
        "Figma": ["figma", "design tool"],
        "Unity": ["unity", "unreal", "game engine"]
    }

    # Count occurrences
    interests = []
    for domain, keywords in interest_keywords.items():
        count = sum(all_text.count(kw) for kw in keywords)
        if count > 0:
            score = min(count / 100.0, 1.0)  # Normalize to 0-1
            interests.append({
                "domain": domain,
                "score": round(score, 2),
                "mention_count": count
            })

    skills = []
    for skill, keywords in skill_keywords.items():
        count = sum(all_text.count(kw) for kw in keywords)
        if count > 0:
            score = min(count / 50.0, 1.0)
            skills.append({
                "skill": skill,
                "score": round(score, 2),
                "mention_count": count
            })

    tools = []
    for tool, keywords in tool_keywords.items():
        count = sum(all_text.count(kw) for kw in keywords)
        if count > 0:
            tools.append({
                "tool": tool,
                "mention_count": count
            })

    # Sort by score/count
    interests.sort(key=lambda x: x["score"], reverse=True)
    skills.sort(key=lambda x: x["score"], reverse=True)
    tools.sort(key=lambda x: x["mention_count"], reverse=True)

    # Interaction style analysis
    avg_msg_length = sum(len(m["message"]) for m in messages) / len(messages) if messages else 0

    interaction_style = {
        "message_count": len(messages),
        "avg_message_length": round(avg_msg_length, 1),
        "engagement_level": "high" if len(messages) > 100 else ("medium" if len(messages) > 20 else "low"),
        "communication_style": "detailed" if avg_msg_length > 100 else ("moderate" if avg_msg_length > 30 else "brief")
    }

    # Monetization opportunities (based on top skills/interests)
    monetization = []
    if skills:
        top_skill = skills[0]["skill"]
        monetization.append({
            "opportunity": f"{top_skill} Development Services",
            "estimated_value": "0.05-0.15 GLUE per task",
            "confidence": "medium"
        })

    if interests and interests[0]["domain"] in ["Blockchain", "AI/ML"]:
        monetization.append({
            "opportunity": f"{interests[0]['domain']} Consulting",
            "estimated_value": "0.10-0.50 GLUE per hour",
            "confidence": "medium"
        })

    # Build profile
    profile = {
        "user_id": f"@{username}",
        "profile_level": "complete",
        "data_coverage": {
            "message_count": len(messages),
            "time_span": f"{messages[0]['timestamp']} to {messages[-1]['timestamp']}" if messages else "unknown",
            "data_quality": "high" if len(messages) > 50 else "medium",
            "confidence_level": 0.85 if len(messages) > 50 else 0.65
        },
        "interests": interests[:5],  # Top 5
        "skills": skills[:5],  # Top 5
        "tools_and_platforms": tools[:5],  # Top 5
        "interaction_style": interaction_style,
        "monetization_opportunities": monetization,
        "top_3_monetizable_strengths": [
            {"strength": s["skill"], "score": s["score"]}
            for s in skills[:3]
        ],
        "agent_potential_summary": generate_summary(username, interests, skills, len(messages))
    }

    return profile


def generate_summary(username: str, interests: list, skills: list, message_count: int) -> str:
    """Generate agent potential summary"""

    top_interest = interests[0]["domain"] if interests else "General Topics"
    top_skill = skills[0]["skill"] if skills else "Communication"

    engagement = "highly engaged" if message_count > 100 else ("active" if message_count > 20 else "casual")

    return (
        f"@{username} is a {engagement} community member with strong interest in {top_interest}. "
        f"Primary skill appears to be {top_skill}. "
        f"Good potential for marketplace agent offering {top_interest.lower()}-related services."
    )


def main():
    """Main extraction function"""

    print("=" * 80)
    print("Karmacadabra - Sprint 3: Automated Profile Extraction (Simple)")
    print("=" * 80)
    print()

    # Setup paths
    base_dir = Path(__file__).parent.parent
    logs_dir = base_dir / "karma-hello-agent" / "logs"
    output_dir = base_dir / "user-profiles"
    output_dir.mkdir(exist_ok=True)

    # Get list of users
    import subprocess
    result = subprocess.run(
        'find karma-hello-agent/logs/202510* -name "*.txt" -type f | sed "s|.*/||" | sed "s|\\.txt$||" | sort -u | head -48',
        shell=True,
        capture_output=True,
        text=True,
        cwd=base_dir
    )

    users = [u.strip() for u in result.stdout.strip().split('\n') if u.strip()]

    print(f"📋 Found {len(users)} users to process")
    print(f"📂 Output directory: {output_dir}")
    print()

    # Process each user
    successful = 0
    failed = 0

    for i, username in enumerate(users, 1):
        print(f"[{i}/{len(users)}] Processing {username}...", end=" ")

        try:
            profile = extract_profile_from_logs(username, logs_dir)

            # Save to JSON
            profile_file = output_dir / f"{username}.json"
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

            print(f"✅ ({profile['data_coverage']['message_count']} msgs, {len(profile['interests'])} interests)")
            successful += 1

        except Exception as e:
            print(f"❌ {e}")
            failed += 1

    print()
    print("=" * 80)
    print(f"📊 Profile Extraction Summary")
    print("=" * 80)
    print(f"Total users: {len(users)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📂 Output directory: {output_dir}")
    print()

    if failed == 0:
        print("🎉 All profiles extracted successfully!")
        return 0
    else:
        print(f"⚠️  {failed} profiles failed to extract")
        return 1


if __name__ == "__main__":
    sys.exit(main())
