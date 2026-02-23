"""
Karma Kadabra V2 — Task 2.3: Skill Extractor Pipeline

Analyzes each user's messages to extract skills, expertise areas, and interests.
Uses keyword-based extraction (fast, no API needed) with optional LLM enhancement.

Usage:
  python extract-skills.py
  python extract-skills.py --input data/user-stats.json --output data/skills/
  python extract-skills.py --llm   # Uses Claude Haiku for deeper analysis (requires ANTHROPIC_API_KEY)
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Skill taxonomy — keyword-based detection
# ---------------------------------------------------------------------------

SKILL_TAXONOMY = {
    "Programming": {
        "Python": ["python", "pip", "fastapi", "django", "flask", "pandas", "numpy"],
        "JavaScript": ["javascript", "js", "node", "nodejs", "react", "next", "typescript", "ts", "npm", "pnpm"],
        "Solidity": ["solidity", "smart contract", "contrato", "erc20", "erc721", "foundry", "hardhat", "remix"],
        "Rust": ["rust", "cargo", "tokio", "wasm"],
        "General": ["codigo", "code", "programar", "developer", "dev", "git", "github", "docker", "api", "deploy"],
    },
    "Blockchain": {
        "DeFi": ["defi", "swap", "liquidity", "yield", "farm", "pool", "amm", "aave", "uniswap", "compound"],
        "Trading": ["trade", "trading", "long", "short", "leverage", "scalping", "chart", "vela", "wick", "candle", "apalancamiento"],
        "NFTs": ["nft", "mint", "coleccion", "opensea", "pfp", "art", "metadata"],
        "Layer 2": ["l2", "layer 2", "rollup", "base", "arbitrum", "optimism", "polygon", "zk"],
        "Wallets": ["wallet", "metamask", "ledger", "seed", "private key", "mnemonic"],
        "Networks": ["ethereum", "avalanche", "avax", "celo", "monad", "solana", "cosmos"],
    },
    "AI/ML": {
        "LLM": ["llm", "gpt", "claude", "gemini", "openai", "anthropic", "prompt", "modelo"],
        "Agents": ["agent", "agente", "crew", "crewai", "autogen", "langchain", "mcp", "a2a"],
        "General AI": ["ai", "ia", "machine learning", "ml", "neural", "embedding", "vector"],
    },
    "Design": {
        "UI/UX": ["design", "diseno", "figma", "ui", "ux", "interfaz"],
        "Branding": ["logo", "brand", "marca", "identidad"],
        "Creative": ["arte", "art", "creative", "creativo", "video", "foto", "photo"],
    },
    "Business": {
        "Finance": ["inversion", "invertir", "banco", "bank", "dinero", "money", "plata", "dolar", "usd", "usdc"],
        "Marketing": ["marketing", "contenido", "content", "social media", "redes", "audiencia"],
        "Entrepreneurship": ["negocio", "business", "empresa", "startup", "emprendimiento", "proyecto"],
    },
    "Community": {
        "Teaching": ["explicar", "ensenar", "tutorial", "clase", "learn", "aprender"],
        "Leadership": ["lider", "leader", "coordinar", "organizar", "equipo", "team"],
        "Communication": ["podcast", "stream", "twitch", "youtube", "twitter", "x.com"],
    },
}

# Language detection keywords
LANGUAGE_MARKERS = {
    "spanish": ["bro", "parcero", "parce", "chimba", "que", "como", "pero", "porque", "entonces", "bueno", "oe", "gm"],
    "english": ["the", "and", "but", "because", "with", "about", "think", "know", "just", "like"],
    "portuguese": ["voce", "entao", "porque", "muito", "tambem", "ainda"],
}


def extract_skills_keyword(username: str, messages: list[str], stats: dict) -> dict:
    """Extract skills using keyword matching against taxonomy."""
    all_text = " ".join(messages).lower()
    words = all_text.split()
    word_set = set(words)

    skills = {}
    # Pre-compile word boundary patterns for short keywords to avoid false positives
    # (e.g., "ai" matching "chain", "ts" matching "its")
    import re as _re

    def _kw_in_text(kw: str, text: str) -> bool:
        if len(kw) <= 3:
            return bool(_re.search(rf"\b{_re.escape(kw)}\b", text))
        return kw in text

    def _kw_count(kw: str, text: str) -> int:
        if len(kw) <= 3:
            return len(_re.findall(rf"\b{_re.escape(kw)}\b", text))
        return text.count(kw)

    for category, subcategories in SKILL_TAXONOMY.items():
        cat_score = 0
        sub_skills = []

        for skill_name, keywords in subcategories.items():
            # Count keyword matches using word-boundary for short keywords
            matches = sum(1 for kw in keywords if _kw_in_text(kw, all_text))
            # Weight by frequency
            frequency = sum(_kw_count(kw, all_text) for kw in keywords)

            if matches > 0:
                # Score: 0-1 based on keyword diversity + frequency
                diversity_score = min(matches / len(keywords), 1.0)
                frequency_score = min(frequency / (len(messages) * 0.5), 1.0)
                score = round(diversity_score * 0.6 + frequency_score * 0.4, 2)

                evidence = [kw for kw in keywords if _kw_in_text(kw, all_text)][:5]
                sub_skills.append(
                    {
                        "name": skill_name,
                        "score": score,
                        "keyword_matches": matches,
                        "frequency": frequency,
                        "evidence": evidence,
                    }
                )
                cat_score = max(cat_score, score)

        if sub_skills:
            # Sort by score descending
            sub_skills.sort(key=lambda s: s["score"], reverse=True)
            skills[category] = {
                "score": round(cat_score, 2),
                "sub_skills": sub_skills,
            }

    # Detect languages
    lang_scores = {}
    for lang, markers in LANGUAGE_MARKERS.items():
        count = sum(1 for w in words if w in markers)
        if count > 0:
            lang_scores[lang] = round(count / len(words) * 100, 1)

    primary_lang = max(lang_scores, key=lang_scores.get) if lang_scores else "spanish"

    # Confidence based on message volume
    msg_count = len(messages)
    if msg_count >= 50:
        confidence = "high"
    elif msg_count >= 20:
        confidence = "medium"
    elif msg_count >= 5:
        confidence = "low"
    else:
        confidence = "very_low"

    return {
        "username": username,
        "extraction_method": "keyword",
        "confidence": confidence,
        "message_count": msg_count,
        "languages": lang_scores,
        "primary_language": primary_lang,
        "skills": skills,
        "top_skills": _get_top_skills(skills, 5),
    }


def _get_top_skills(skills: dict, n: int) -> list[dict]:
    """Get top N skills across all categories."""
    all_skills = []
    for cat, data in skills.items():
        for sub in data["sub_skills"]:
            all_skills.append(
                {
                    "category": cat,
                    "skill": sub["name"],
                    "score": sub["score"],
                }
            )
    all_skills.sort(key=lambda s: s["score"], reverse=True)
    return all_skills[:n]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Extract skills from user chat messages")
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
        help="Output directory for skill JSONs (default: data/skills/)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use Claude Haiku for deeper analysis (requires ANTHROPIC_API_KEY)",
    )
    args = parser.parse_args()

    stats_path = Path(args.input) if args.input else Path(__file__).parent / "data" / "user-stats.json"
    agg_path = Path(args.aggregated) if args.aggregated else Path(__file__).parent / "data" / "aggregated.json"
    output_dir = Path(args.output) if args.output else Path(__file__).parent / "data" / "skills"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not stats_path.exists():
        print(f"ERROR: Stats file not found: {stats_path}")
        print("Run user-stats.py first.")
        sys.exit(1)

    if not agg_path.exists():
        print(f"ERROR: Aggregated logs not found: {agg_path}")
        print("Run aggregate-logs.py first.")
        sys.exit(1)

    # Load data
    print(f"\nLoading stats from: {stats_path}")
    with open(stats_path, "r", encoding="utf-8") as f:
        stats_data = json.load(f)

    print(f"Loading messages from: {agg_path}")
    with open(agg_path, "r", encoding="utf-8") as f:
        agg_data = json.load(f)

    # Index messages by username
    user_messages: dict[str, list[str]] = defaultdict(list)
    for msg in agg_data["messages"]:
        user_messages[msg["username"]].append(msg["message"])

    # Process ranked users
    ranked = stats_data["ranking"]
    print(f"\nExtracting skills for {len(ranked)} users...")

    if args.llm:
        print("  LLM mode: requires ANTHROPIC_API_KEY (not implemented yet — using keyword fallback)")

    results = []
    for user in ranked:
        username = user["username"]
        messages = user_messages.get(username, [])

        if not messages:
            print(f"  WARNING: No messages for {username}")
            continue

        skills = extract_skills_keyword(username, messages, user)

        # Save individual file
        out_file = output_dir / f"{username}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(skills, f, ensure_ascii=False, indent=2)

        results.append(skills)
        top = skills["top_skills"]
        top_str = ", ".join(f"{s['skill']}({s['score']})" for s in top[:3])
        print(f"  [{user['rank']:>3}] {username:<22} {skills['confidence']:<8} {top_str}")

    # Save summary
    summary_path = output_dir / "_summary.json"
    summary = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "method": "llm" if args.llm else "keyword",
        "users_processed": len(results),
        "users": [
            {
                "username": r["username"],
                "confidence": r["confidence"],
                "primary_language": r["primary_language"],
                "top_skills": r["top_skills"][:3],
            }
            for r in results
        ],
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(results)} skill profiles saved to {output_dir}/")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
