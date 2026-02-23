"""
Karma Kadabra V2 — Task 2.2: User Statistics & Ranking

Analyzes aggregated chat logs and produces ranked user statistics.
Selects the top-N users (Fibonacci: 34, 55, 89) for agent creation.

Usage:
  python user-stats.py --top 34
  python user-stats.py --top 55 --input data/aggregated.json --output data/user-stats.json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------

# Topic keywords for interest detection
TOPIC_KEYWORDS = {
    "crypto": ["crypto", "bitcoin", "btc", "eth", "token", "coin", "mining", "blockchain", "ledger"],
    "defi": ["defi", "swap", "liquidity", "yield", "farm", "pool", "amm", "staking", "vault"],
    "nft": ["nft", "mint", "coleccion", "opensea", "pfp", "art"],
    "trading": ["trade", "trading", "long", "short", "leverage", "apalancamiento", "scalping", "chart", "vela"],
    "development": ["codigo", "code", "deploy", "contract", "smart contract", "solidity", "python", "javascript", "api", "docker", "github", "git"],
    "ai": ["ai", "ia", "llm", "gpt", "claude", "agent", "agente", "modelo", "machine learning", "ml"],
    "gaming": ["game", "juego", "play", "gamer", "steam", "fortnite", "minecraft", "esport"],
    "design": ["design", "diseno", "figma", "ui", "ux", "logo", "brand"],
    "finance": ["dinero", "money", "inversion", "invertir", "banco", "bank", "dolar", "usd", "plata"],
    "community": ["dao", "comunidad", "community", "discord", "telegram", "irc", "twitch"],
}


def compute_user_stats(messages: list[dict]) -> dict:
    """Compute statistics per user from aggregated messages."""
    user_data: dict[str, dict] = defaultdict(
        lambda: {
            "messages": [],
            "dates": set(),
            "hours": [],
            "word_counts": [],
            "topics": Counter(),
            "replies_to": Counter(),
            "replied_by": Counter(),
        }
    )

    # Build user data
    prev_user = None
    for msg in messages:
        username = msg["username"]
        text = msg["message"]
        date = msg["date"]
        hour = msg["hour"]

        ud = user_data[username]
        ud["messages"].append(text)
        ud["dates"].add(date)
        ud["hours"].append(hour)

        words = text.lower().split()
        ud["word_counts"].append(len(words))

        # Topic detection
        text_lower = text.lower()
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                ud["topics"][topic] += 1

        # Interaction tracking (simple sequential: if I speak after you, it's an interaction)
        if prev_user and prev_user != username:
            ud["replies_to"][prev_user] += 1
            user_data[prev_user]["replied_by"][username] += 1

        prev_user = username

    # Compute stats per user
    stats = {}
    for username, ud in user_data.items():
        if username in ("unknown",):
            continue

        n_messages = len(ud["messages"])
        n_dates = len(ud["dates"])
        all_words = [w for msg in ud["messages"] for w in msg.lower().split()]
        total_words = len(all_words)
        unique_words = len(set(all_words))

        # Average message length in chars
        avg_msg_len = sum(len(m) for m in ud["messages"]) / n_messages if n_messages else 0

        # Peak hours
        hour_counter = Counter(ud["hours"])
        peak_hours = [h for h, _ in hour_counter.most_common(3)]

        # Vocabulary richness (unique/total, higher = more diverse vocabulary)
        vocab_richness = unique_words / total_words if total_words > 0 else 0

        # Top topics
        top_topics = dict(ud["topics"].most_common(5))

        # Top interactions
        top_interactions = dict(ud["replies_to"].most_common(5))

        # Engagement score: weighted composite (all components capped 0-10)
        interaction_count = sum(ud["replies_to"].values()) + sum(ud["replied_by"].values())
        engagement_raw = (
            min(n_messages / 10, 10) * 0.4  # Cap messages at 100 → score 10
            + min(n_dates * 10 / 6, 10) * 0.3  # Cap at 6 dates → score 10
            + min(avg_msg_len / 50, 10) * 0.15  # Cap at 500 chars → score 10
            + min(interaction_count / 5, 10) * 0.15  # Cap at 50 interactions → score 10
        )

        stats[username] = {
            "username": username,
            "total_messages": n_messages,
            "active_dates": n_dates,
            "active_date_list": sorted(ud["dates"]),
            "avg_message_length": round(avg_msg_len, 1),
            "total_words": total_words,
            "unique_words": unique_words,
            "vocabulary_richness": round(vocab_richness, 3),
            "peak_hours": peak_hours,
            "topics": top_topics,
            "top_interactions": top_interactions,
            "interaction_count": interaction_count,
            "engagement_score": round(engagement_raw, 2),
        }

    return stats


def rank_users(stats: dict, top_n: int) -> list[dict]:
    """Rank users by engagement score and return top N."""
    ranked = sorted(stats.values(), key=lambda u: u["engagement_score"], reverse=True)

    # Add rank
    for i, user in enumerate(ranked):
        user["rank"] = i + 1

    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Compute user stats and ranking from aggregated logs")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input aggregated JSON (default: data/aggregated.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output stats JSON (default: data/user-stats.json)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=34,
        help="Top N users to select (Fibonacci: 34, 55, 89). Default: 34",
    )
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else Path(__file__).parent / "data" / "aggregated.json"
    output_path = Path(args.output) if args.output else Path(__file__).parent / "data" / "user-stats.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run aggregate-logs.py first.")
        sys.exit(1)

    print(f"\nLoading aggregated data from: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data["messages"]
    print(f"  {len(messages)} messages from {data['stats']['unique_users']} users")

    # Compute stats
    print("\nComputing user statistics...")
    stats = compute_user_stats(messages)
    print(f"  Processed {len(stats)} users (excluding 'unknown')")

    # Rank
    print(f"\nRanking top {args.top} users...")
    ranked = rank_users(stats, args.top)

    # Display top 20
    print(f"\n{'Rank':<6}{'Username':<22}{'Messages':<10}{'Days':<6}{'Avg Len':<9}{'Vocab':<7}{'Score':<8}")
    print("-" * 68)
    for u in ranked[:20]:
        print(
            f"{u['rank']:<6}{u['username']:<22}{u['total_messages']:<10}"
            f"{u['active_dates']:<6}{u['avg_message_length']:<9}"
            f"{u['vocabulary_richness']:<7}{u['engagement_score']:<8}"
        )
    if len(ranked) > 20:
        print(f"  ... and {len(ranked) - 20} more")

    # Output
    result = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "config": {
            "top_n": args.top,
            "total_users_analyzed": len(stats),
        },
        "ranking": ranked,
        "all_stats": stats,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {output_path}")
    print(f"  Top {len(ranked)} users selected for agent creation")
    print(f"  Min engagement score: {ranked[-1]['engagement_score'] if ranked else 'N/A'}")


if __name__ == "__main__":
    main()
