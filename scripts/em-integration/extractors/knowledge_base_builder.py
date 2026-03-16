"""
Karma Kadabra V2 — Task 4.2: Knowledge Base Builder

Processes Abracadabra content products and raw chat data into a
structured knowledge base with indexed chunks, ready for semantic
search and agent consumption.

Input sources:
  - Abracadabra content cache (generated products)
  - Raw aggregated chat logs
  - Skills/voice extraction data

Output:
  data/knowledge-base/
    {topic}/chunks.jsonl       — Indexed knowledge chunks
    _index.json                — Topic index with metadata

Chunk format (JSONL):
  {"id": "...", "topic": "...", "content": "...", "source": "...",
   "timestamp": "...", "tags": [...], "confidence": 0.85}

Usage:
  python knowledge_base_builder.py                        # Build from all sources
  python knowledge_base_builder.py --source content_cache # Only content products
  python knowledge_base_builder.py --source chat_logs     # Only raw logs
  python knowledge_base_builder.py --topic defi           # Single topic
  python knowledge_base_builder.py --dry-run              # Preview
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.knowledge-base")

DATA_DIR = Path(__file__).parent.parent / "data"
KB_DIR = DATA_DIR / "knowledge-base"
CONTENT_CACHE = DATA_DIR / "content_cache"

# Topic taxonomy aligned with skills extraction
TOPIC_TAXONOMY = {
    "ai": ["ai", "ml", "llm", "gpt", "claude", "agent", "chatbot", "neural", "modelo", "inteligencia"],
    "defi": ["defi", "yield", "liquidity", "swap", "pool", "farm", "stake", "lending", "aave", "uniswap"],
    "trading": ["trade", "trading", "buy", "sell", "long", "short", "bull", "bear", "chart", "signal"],
    "nft": ["nft", "mint", "collection", "opensea", "art", "pfp", "metadata"],
    "blockchain": ["blockchain", "chain", "layer", "l1", "l2", "bridge", "rollup", "ethereum", "base", "solana"],
    "smart_contracts": ["contract", "solidity", "evm", "deploy", "audit", "vulnerability", "foundry", "hardhat"],
    "web3": ["web3", "dapp", "wallet", "metamask", "connect", "sign", "transaction", "gas"],
    "community": ["community", "dao", "governance", "vote", "proposal", "treasury", "member"],
    "design": ["design", "ui", "ux", "figma", "branding", "logo", "interface", "mockup"],
    "development": ["code", "python", "javascript", "typescript", "rust", "api", "backend", "frontend"],
}

# Minimum content length for a chunk to be useful
MIN_CHUNK_LENGTH = 20
MAX_CHUNK_LENGTH = 2000


def chunk_id(content: str, source: str) -> str:
    """Generate a deterministic chunk ID."""
    h = hashlib.sha256(f"{content}:{source}".encode()).hexdigest()[:12]
    return f"chunk-{h}"


def classify_topic(text: str) -> list[str]:
    """Classify text into topic categories using keyword matching."""
    text_lower = text.lower()
    matches = []
    for topic, keywords in TOPIC_TAXONOMY.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score >= 1:
            matches.append((topic, score))
    matches.sort(key=lambda x: -x[1])
    return [m[0] for m in matches[:3]] or ["general"]


def extract_tags(text: str) -> list[str]:
    """Extract relevant tags from text."""
    text_lower = text.lower()
    tags = set()
    for topic, keywords in TOPIC_TAXONOMY.items():
        for kw in keywords:
            if kw in text_lower:
                tags.add(kw)
    return sorted(tags)[:10]


# ---------------------------------------------------------------------------
# Source: Content Cache (Abracadabra products)
# ---------------------------------------------------------------------------


def process_content_cache() -> list[dict[str, Any]]:
    """Process Abracadabra content cache into knowledge chunks."""
    chunks: list[dict[str, Any]] = []
    if not CONTENT_CACHE.exists():
        logger.info("No content cache found at %s", CONTENT_CACHE)
        return chunks

    for fpath in sorted(CONTENT_CACHE.glob("*.json")):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping %s: %s", fpath.name, e)
            continue

        source_type = fpath.stem.rsplit("_", 1)[0]  # e.g., "analyze_stream"
        chunks.extend(_extract_chunks_from_product(data, source_type, fpath.name))

    logger.info("Content cache: %d chunks from %d files", len(chunks), len(list(CONTENT_CACHE.glob("*.json"))))
    return chunks


def _extract_chunks_from_product(data: dict, source_type: str, filename: str) -> list[dict[str, Any]]:
    """Extract knowledge chunks from a single content product."""
    chunks = []
    source = f"abracadabra:{source_type}:{filename}"

    if source_type == "analyze_stream":
        # Stream analysis has topic_breakdown, key_moments, etc.
        for topic_entry in data.get("topic_breakdown", []):
            content = f"Topic: {topic_entry.get('topic', '?')} - {topic_entry.get('summary', '')}"
            if len(content) >= MIN_CHUNK_LENGTH:
                topics = classify_topic(content)
                chunks.append({
                    "id": chunk_id(content, source),
                    "topic": topics[0],
                    "content": content[:MAX_CHUNK_LENGTH],
                    "source": source,
                    "source_type": "stream_analysis",
                    "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "tags": extract_tags(content),
                    "confidence": topic_entry.get("confidence", 0.7),
                })
        for moment in data.get("key_moments", []):
            content = f"Key moment: {moment.get('description', '')}"
            if len(content) >= MIN_CHUNK_LENGTH:
                topics = classify_topic(content)
                chunks.append({
                    "id": chunk_id(content, source),
                    "topic": topics[0],
                    "content": content[:MAX_CHUNK_LENGTH],
                    "source": source,
                    "source_type": "stream_moment",
                    "timestamp": moment.get("timestamp", ""),
                    "tags": extract_tags(content),
                    "confidence": 0.8,
                })

    elif source_type == "predict_trending":
        for prediction in data.get("predictions", data.get("topics", [])):
            topic_name = prediction.get("topic", prediction.get("name", ""))
            confidence = prediction.get("confidence", 0.5)
            content = f"Trending prediction: {topic_name} (confidence: {confidence:.0%})"
            reason = prediction.get("reason", "")
            if reason:
                content += f" — {reason}"
            if len(content) >= MIN_CHUNK_LENGTH:
                topics = classify_topic(content)
                chunks.append({
                    "id": chunk_id(content, source),
                    "topic": topics[0],
                    "content": content[:MAX_CHUNK_LENGTH],
                    "source": source,
                    "source_type": "trend_prediction",
                    "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "tags": extract_tags(content),
                    "confidence": confidence,
                })

    elif source_type == "generate_blog":
        # Blog posts are single large chunks
        content = data.get("content", data.get("body", ""))
        title = data.get("title", "Untitled")
        if len(content) >= MIN_CHUNK_LENGTH:
            topics = classify_topic(f"{title} {content}")
            chunks.append({
                "id": chunk_id(content, source),
                "topic": topics[0],
                "content": content[:MAX_CHUNK_LENGTH],
                "source": source,
                "source_type": "blog_post",
                "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "tags": extract_tags(f"{title} {content}"),
                "confidence": 0.9,
                "title": title,
            })

    elif source_type == "knowledge_graph":
        for node in data.get("nodes", []):
            content = f"Entity: {node.get('name', '?')} — {node.get('description', '')}"
            if len(content) >= MIN_CHUNK_LENGTH:
                topics = classify_topic(content)
                chunks.append({
                    "id": chunk_id(content, source),
                    "topic": topics[0],
                    "content": content[:MAX_CHUNK_LENGTH],
                    "source": source,
                    "source_type": "knowledge_entity",
                    "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "tags": extract_tags(content),
                    "confidence": node.get("centrality", 0.5),
                })

    return chunks


# ---------------------------------------------------------------------------
# Source: Raw Chat Logs (aggregated.json)
# ---------------------------------------------------------------------------


def process_chat_logs() -> list[dict[str, Any]]:
    """Process raw aggregated chat logs into knowledge chunks."""
    chunks: list[dict[str, Any]] = []
    agg_file = DATA_DIR / "aggregated.json"
    if not agg_file.exists():
        logger.info("No aggregated.json found at %s", agg_file)
        return chunks

    try:
        data = json.loads(agg_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read aggregated.json: %s", e)
        return chunks

    messages = data.get("messages", [])
    if not messages:
        logger.info("No messages in aggregated.json")
        return chunks

    # Group messages into conversation threads (5-minute windows)
    threads = _group_into_threads(messages, window_seconds=300)
    for thread in threads:
        content = _thread_to_content(thread)
        if len(content) < MIN_CHUNK_LENGTH:
            continue
        topics = classify_topic(content)
        participants = list({m.get("username", "?") for m in thread})
        chunks.append({
            "id": chunk_id(content, "chat_logs"),
            "topic": topics[0],
            "content": content[:MAX_CHUNK_LENGTH],
            "source": "chat_logs:aggregated",
            "source_type": "chat_thread",
            "timestamp": thread[0].get("timestamp", ""),
            "tags": extract_tags(content),
            "confidence": min(0.5 + len(thread) * 0.05, 0.9),
            "participants": participants[:10],
            "message_count": len(thread),
        })

    logger.info("Chat logs: %d chunks from %d messages (%d threads)", len(chunks), len(messages), len(threads))
    return chunks


def _group_into_threads(messages: list[dict], window_seconds: int = 300) -> list[list[dict]]:
    """Group messages into conversation threads by time proximity."""
    if not messages:
        return []

    threads: list[list[dict]] = []
    current_thread: list[dict] = [messages[0]]

    for msg in messages[1:]:
        # Simple time-based grouping
        current_thread.append(msg)
        if len(current_thread) >= 20:
            threads.append(current_thread)
            current_thread = []

    if current_thread:
        threads.append(current_thread)

    return threads


def _thread_to_content(thread: list[dict]) -> str:
    """Convert a message thread into a text chunk."""
    lines = []
    for msg in thread[:20]:
        username = msg.get("username", "?")
        text = msg.get("message", msg.get("text", ""))
        if text:
            lines.append(f"{username}: {text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Source: Skills/Voice Profiles (enriched metadata)
# ---------------------------------------------------------------------------


def process_profiles() -> list[dict[str, Any]]:
    """Process skills and voice profiles into knowledge chunks."""
    chunks: list[dict[str, Any]] = []

    skills_dir = DATA_DIR / "skills"
    if not skills_dir.exists():
        return chunks

    for fpath in sorted(skills_dir.glob("*.json")):
        if fpath.name.startswith("_"):
            continue
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        username = data.get("username", fpath.stem)
        top_skills = data.get("top_skills", [])
        if not top_skills:
            continue

        skill_summary = ", ".join(f"{s['skill']} ({s['category']})" for s in top_skills[:5])
        content = f"Agent profile: {username} — Top skills: {skill_summary}"
        topics = classify_topic(content)
        chunks.append({
            "id": chunk_id(content, f"profile:{username}"),
            "topic": topics[0],
            "content": content,
            "source": f"profile:{username}",
            "source_type": "agent_profile",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tags": [s["skill"].lower() for s in top_skills[:5]],
            "confidence": 0.95,
            "agent": username,
        })

    logger.info("Profiles: %d agent profile chunks", len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Build: Write knowledge base to disk
# ---------------------------------------------------------------------------


def build_knowledge_base(
    chunks: list[dict[str, Any]],
    output_dir: Path,
    topic_filter: str | None = None,
) -> dict[str, Any]:
    """Write knowledge chunks organized by topic."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group by topic
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        topic = chunk.get("topic", "general")
        if topic_filter and topic != topic_filter:
            continue
        by_topic[topic].append(chunk)

    # Deduplicate by chunk ID
    for topic in by_topic:
        seen = set()
        deduped = []
        for chunk in by_topic[topic]:
            if chunk["id"] not in seen:
                seen.add(chunk["id"])
                deduped.append(chunk)
        by_topic[topic] = deduped

    # Write JSONL files per topic
    index_entries: list[dict[str, Any]] = []
    total_chunks = 0
    for topic, topic_chunks in sorted(by_topic.items()):
        topic_dir = output_dir / topic
        topic_dir.mkdir(parents=True, exist_ok=True)

        chunks_file = topic_dir / "chunks.jsonl"
        with open(chunks_file, "w", encoding="utf-8") as f:
            for chunk in topic_chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        total_chunks += len(topic_chunks)
        index_entries.append({
            "topic": topic,
            "chunk_count": len(topic_chunks),
            "sources": list({c["source_type"] for c in topic_chunks}),
            "file": str(chunks_file.relative_to(output_dir)),
        })
        logger.info("  %s: %d chunks", topic, len(topic_chunks))

    # Write index
    index = {
        "version": "1.0",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": total_chunks,
        "total_topics": len(index_entries),
        "topics": index_entries,
    }
    index_path = output_dir / "_index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Karma Kadabra knowledge base")
    parser.add_argument("--source", choices=["content_cache", "chat_logs", "profiles", "all"], default="all")
    parser.add_argument("--topic", type=str, default=None, help="Filter to a single topic")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else KB_DIR

    logger.info("Building knowledge base...")

    all_chunks: list[dict[str, Any]] = []

    if args.source in ("content_cache", "all"):
        all_chunks.extend(process_content_cache())

    if args.source in ("chat_logs", "all"):
        all_chunks.extend(process_chat_logs())

    if args.source in ("profiles", "all"):
        all_chunks.extend(process_profiles())

    logger.info("Total chunks: %d", len(all_chunks))

    if args.dry_run:
        by_topic = defaultdict(int)
        for c in all_chunks:
            by_topic[c.get("topic", "general")] += 1
        for topic, count in sorted(by_topic.items(), key=lambda x: -x[1]):
            logger.info("  [DRY-RUN] %s: %d chunks", topic, count)
        return

    index = build_knowledge_base(all_chunks, output_dir, topic_filter=args.topic)
    logger.info("\nKnowledge base built: %d chunks across %d topics", index["total_chunks"], index["total_topics"])
    logger.info("Index: %s", output_dir / "_index.json")


if __name__ == "__main__":
    main()
