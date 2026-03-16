"""
Karma Kadabra V2 — Soul Extractor Pipeline (Standalone)

Standalone script that merges skill + voice + stats into complete
OpenClaw-compatible SOUL.md profiles. This is the batch counterpart
to the live Soul Extractor Service (services/soul_extractor_service.py).

Unlike generate-soul.py (the original batch generator), this script:
  - Uses the same generation logic as the live service
  - Produces both .md and .json outputs per user
  - Tracks new vs updated profiles
  - Generates a manifest compatible with the EM data economy

Usage:
  python extract-soul.py
  python extract-soul.py --output data/souls/ --top 34
  python extract-soul.py --stats data/user-stats.json --skills-dir data/skills/ --voices-dir data/voices/
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add services to path for shared logic
sys.path.insert(0, str(Path(__file__).parent / "services"))

from soul_extractor_service import generate_soul_md


def main():
    parser = argparse.ArgumentParser(description="Extract complete SOUL.md profiles from skills + voice + stats")
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
            print("Run the previous pipeline steps first (extract-skills.py, extract-voice.py).")
            sys.exit(1)

    # Load stats
    with open(stats_path, "r", encoding="utf-8") as f:
        stats_data = json.load(f)

    ranked = stats_data["ranking"]
    if args.top:
        ranked = ranked[: args.top]

    print(f"\nExtracting SOUL.md profiles for {len(ranked)} agents...")
    print(f"  Skills: {skills_dir}")
    print(f"  Voices: {voices_dir}")
    print(f"  Output: {output_dir}")

    generated = 0
    updated = 0
    results = []

    for user in ranked:
        username = user["username"]

        # Load skills
        skills_file = skills_dir / f"{username}.json"
        if not skills_file.exists():
            print(f"  WARNING: No skills for {username}, using defaults")
            skills = {
                "username": username,
                "skills": {},
                "top_skills": [],
                "primary_language": "spanish",
                "languages": {},
            }
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
                "communication_style": {
                    "social_role": "regular",
                    "greeting_style": "gm",
                    "avg_message_length": 40,
                },
                "vocabulary": {"signature_phrases": [], "slang_usage": {}},
                "personality": {"risk_tolerance": "moderate", "formality": "informal"},
            }
        else:
            with open(voice_file, "r", encoding="utf-8") as f:
                voice = json.load(f)

        # Generate SOUL.md using the shared service logic
        soul_content = generate_soul_md(username, user, skills, voice)

        # Track new vs update
        soul_path = output_dir / f"{username}.md"
        is_update = soul_path.exists()

        # Write SOUL.md
        with open(soul_path, "w", encoding="utf-8") as f:
            f.write(soul_content)

        # Write structured JSON
        top_skill = skills["top_skills"][0]["skill"] if skills.get("top_skills") else "Community"
        tone = voice.get("tone", {}).get("primary", "?")
        risk = voice.get("personality", {}).get("risk_tolerance", "?")

        structured = {
            "username": username,
            "version": datetime.now().isoformat(),
            "specialization": top_skill,
            "tone": tone,
            "risk_tolerance": risk,
            "top_skills": skills.get("top_skills", [])[:5],
            "primary_language": skills.get("primary_language", "spanish"),
        }
        json_path = output_dir / f"{username}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)

        if is_update:
            updated += 1
            status = "UPD"
        else:
            generated += 1
            status = "NEW"

        results.append(structured)
        print(f"  [{user['rank']:>3}] {username:<22} [{status}] spec={top_skill:<18} tone={tone}")

    # Save manifest
    manifest = {
        "version": "2.0",
        "generator": "extract-soul.py (Soul Extractor pipeline)",
        "generated_at": datetime.now().isoformat(),
        "total_profiles": generated + updated,
        "new_profiles": generated,
        "updated_profiles": updated,
        "agents": [
            {
                "username": r["username"],
                "specialization": r["specialization"],
                "tone": r["tone"],
                "risk_tolerance": r["risk_tolerance"],
                "soul_file": f"{r['username']}.md",
                "json_file": f"{r['username']}.json",
            }
            for r in results
        ],
    }
    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {generated + updated} SOUL.md profiles in {output_dir}/")
    print(f"  New: {generated}")
    print(f"  Updated: {updated}")
    print(f"  Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
