"""
Karma Kadabra V2 — Task 2.4: Voice Extractor Pipeline

Analyzes communication patterns to build personality/voice profiles.
Pure pattern matching — no LLM needed.

Usage:
  python extract-voice.py
  python extract-voice.py --input data/user-stats.json --output data/voices/
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

# Greeting patterns (detect greeting style)
# Order matters: longer/more-specific patterns first to avoid shadowing
GREETING_PATTERNS = [
    (r"\bgm gm\b", "gm gm"),
    (r"\bbuenas tardes\b", "buenas tardes"),
    (r"\bque mas\b", "que mas"),
    (r"\bgm\b", "gm"),
    (r"\bbuenas?\b", "buenas"),
    (r"\bhola\b", "hola"),
    (r"\boe\b", "oe"),
    (r"\beoeo\b", "eoeo"),
    (r"\boeoe\b", "oeoe"),
    (r"\bhey\b", "hey"),
    (r"\byo\b", "yo"),
]

# Slang/informal markers (colombian + latam)
SLANG_MARKERS = {
    "colombian": ["parce", "parcero", "chimba", "gonorrea", "marica", "ome", "juepucha", "hijueputa", "berraco", "verraco", "severo", "bacano", "chimbada", "parcerito"],
    "latam_general": ["bro", "broder", "wey", "pana", "chamo", "vale", "man", "men", "loco"],
    "crypto_slang": ["moon", "rug", "fomo", "hodl", "wagmi", "ngmi", "gm", "gn", "lfg", "dyor", "nfa"],
    "internet": ["xd", "lol", "jaja", "jajaja", "lmao", "kek", "pog", "gg", "f", "rip"],
}

# Emoji/emoticon patterns
# Unicode emoji blocks (standard ranges — avoids matching normal punctuation)
EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]+"
)
EMOTICON_PATTERN = re.compile(r"[:;]-?[)(DPp/\\|]|<3|xd|XD|\^\^|>_<|:v|:3")

# Question patterns
QUESTION_PATTERN = re.compile(r"\?|como\s|que\s+(es|son|significa)|por\s*que|donde|cuando|quien|cuanto|alguien\s+(sabe|puede)")

# Exclamation/enthusiasm
EXCITEMENT_PATTERN = re.compile(r"!{2,}|[A-Z]{4,}|LFG|WAGMI|MOON|PUMP")


def extract_voice(username: str, messages: list[str], stats: dict) -> dict:
    """Extract communication patterns and personality profile."""
    if not messages:
        return {"username": username, "error": "no messages"}

    all_text = " ".join(messages)
    all_lower = all_text.lower()
    words = all_lower.split()
    total_words = len(words)

    # --- Message length distribution ---
    lengths = [len(m) for m in messages]
    avg_len = sum(lengths) / len(lengths)
    short_msgs = sum(1 for l in lengths if l < 20)  # Short reactions
    medium_msgs = sum(1 for l in lengths if 20 <= l < 100)
    long_msgs = sum(1 for l in lengths if l >= 100)  # Detailed messages

    # --- Tone analysis ---
    questions = sum(1 for m in messages if QUESTION_PATTERN.search(m.lower()))
    exclamations = sum(1 for m in messages if EXCITEMENT_PATTERN.search(m))
    emoji_count = sum(len(EMOJI_PATTERN.findall(m)) for m in messages)
    emoticon_count = sum(len(EMOTICON_PATTERN.findall(m.lower())) for m in messages)

    # Determine primary tone
    question_ratio = questions / len(messages)
    exclamation_ratio = exclamations / len(messages)

    if question_ratio > 0.3:
        primary_tone = "inquisitive"
    elif exclamation_ratio > 0.3:
        primary_tone = "enthusiastic"
    elif avg_len > 80:
        primary_tone = "analytical"
    elif avg_len < 25:
        primary_tone = "reactive"
    else:
        primary_tone = "conversational"

    # --- Greeting style ---
    greeting_counter = Counter()
    for pattern, label in GREETING_PATTERNS:
        for m in messages[:20]:  # Check first messages per day more likely to have greetings
            if re.search(pattern, m.lower()):
                greeting_counter[label] += 1

    greeting_style = greeting_counter.most_common(1)[0][0] if greeting_counter else "none"

    # --- Slang profile ---
    slang_usage = {}
    for category, markers in SLANG_MARKERS.items():
        count = sum(all_lower.count(m) for m in markers)
        if count > 0:
            top_used = sorted(
                [(m, all_lower.count(m)) for m in markers if all_lower.count(m) > 0],
                key=lambda x: x[1],
                reverse=True,
            )[:5]
            slang_usage[category] = {
                "count": count,
                "top": [{"word": w, "count": c} for w, c in top_used],
            }

    # --- Signature phrases ---
    # Find repeated 2-4 word sequences
    phrase_counter = Counter()
    for m in messages:
        words_in_msg = m.lower().split()
        for n in range(2, 5):
            for i in range(len(words_in_msg) - n + 1):
                phrase = " ".join(words_in_msg[i : i + n])
                if len(phrase) > 5:  # Ignore very short phrases
                    phrase_counter[phrase] += 1

    # Filter to phrases used 3+ times and remove subphrases
    repeated_phrases = {p: c for p, c in phrase_counter.items() if c >= 3}
    signature_phrases = sorted(repeated_phrases.items(), key=lambda x: x[1], reverse=True)[:10]

    # --- Risk tolerance ---
    risk_keywords = {
        "aggressive": ["all in", "yolo", "leverage", "apalancamiento", "x100", "x50", "moon", "pump", "ape"],
        "moderate": ["invertir", "invest", "strategy", "estrategia", "portfolio", "diversificar"],
        "conservative": ["ahorro", "save", "seguro", "safe", "stable", "estable", "largo plazo"],
    }

    risk_scores = {}
    for level, keywords in risk_keywords.items():
        count = sum(all_lower.count(kw) for kw in keywords)
        risk_scores[level] = count

    risk_total = sum(risk_scores.values())
    if risk_total == 0:
        risk_tolerance = "unknown"
    elif risk_scores["aggressive"] > risk_scores["moderate"] + risk_scores["conservative"]:
        risk_tolerance = "aggressive"
    elif risk_scores["conservative"] > risk_scores["aggressive"]:
        risk_tolerance = "conservative"
    else:
        risk_tolerance = "moderate"

    # --- Social role ---
    if question_ratio > 0.4:
        social_role = "learner"
    elif long_msgs > len(messages) * 0.3:
        social_role = "educator"
    elif exclamation_ratio > 0.3 and avg_len < 30:
        social_role = "hype_man"
    elif len(messages) > 50:
        social_role = "regular"
    else:
        social_role = "lurker"

    return {
        "username": username,
        "message_count": len(messages),
        "tone": {
            "primary": primary_tone,
            "question_ratio": round(question_ratio, 3),
            "excitement_ratio": round(exclamation_ratio, 3),
            "emoji_usage": emoji_count,
            "emoticon_usage": emoticon_count,
        },
        "communication_style": {
            "avg_message_length": round(avg_len, 1),
            "short_messages_pct": round(short_msgs / len(messages) * 100, 1),
            "medium_messages_pct": round(medium_msgs / len(messages) * 100, 1),
            "long_messages_pct": round(long_msgs / len(messages) * 100, 1),
            "greeting_style": greeting_style,
            "social_role": social_role,
        },
        "vocabulary": {
            "slang_usage": slang_usage,
            "signature_phrases": [{"phrase": p, "count": c} for p, c in signature_phrases],
        },
        "personality": {
            "risk_tolerance": risk_tolerance,
            "risk_scores": risk_scores,
            "formality": "informal" if sum(s.get("count", 0) for s in slang_usage.values()) > 5 else "mixed",
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Extract voice/personality profiles from chat messages")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input user-stats.json (default: data/user-stats.json)",
    )
    parser.add_argument(
        "--aggregated",
        type=str,
        default=None,
        help="Aggregated logs JSON (default: data/aggregated.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for voice JSONs (default: data/voices/)",
    )
    args = parser.parse_args()

    stats_path = Path(args.input) if args.input else Path(__file__).parent / "data" / "user-stats.json"
    agg_path = Path(args.aggregated) if args.aggregated else Path(__file__).parent / "data" / "aggregated.json"
    output_dir = Path(args.output) if args.output else Path(__file__).parent / "data" / "voices"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not stats_path.exists():
        print(f"ERROR: Stats file not found: {stats_path}")
        sys.exit(1)
    if not agg_path.exists():
        print(f"ERROR: Aggregated logs not found: {agg_path}")
        sys.exit(1)

    # Load data
    with open(stats_path, "r", encoding="utf-8") as f:
        stats_data = json.load(f)
    with open(agg_path, "r", encoding="utf-8") as f:
        agg_data = json.load(f)

    # Index messages by username
    user_messages: dict[str, list[str]] = defaultdict(list)
    for msg in agg_data["messages"]:
        user_messages[msg["username"]].append(msg["message"])

    ranked = stats_data["ranking"]
    print(f"\nExtracting voice profiles for {len(ranked)} users...")

    results = []
    for user in ranked:
        username = user["username"]
        messages = user_messages.get(username, [])

        if not messages:
            continue

        voice = extract_voice(username, messages, user)

        out_file = output_dir / f"{username}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(voice, f, ensure_ascii=False, indent=2)

        results.append(voice)
        tone = voice["tone"]["primary"]
        role = voice["communication_style"]["social_role"]
        risk = voice["personality"]["risk_tolerance"]
        greeting = voice["communication_style"]["greeting_style"]
        print(f"  [{user['rank']:>3}] {username:<22} tone={tone:<14} role={role:<10} risk={risk:<12} hi={greeting}")

    # Save summary
    summary_path = output_dir / "_summary.json"
    summary = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "users_processed": len(results),
        "users": [
            {
                "username": r["username"],
                "tone": r["tone"]["primary"],
                "social_role": r["communication_style"]["social_role"],
                "risk_tolerance": r["personality"]["risk_tolerance"],
                "greeting_style": r["communication_style"]["greeting_style"],
            }
            for r in results
        ],
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(results)} voice profiles saved to {output_dir}/")


if __name__ == "__main__":
    main()
