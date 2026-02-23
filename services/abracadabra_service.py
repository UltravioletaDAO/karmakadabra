"""
Karma Kadabra V2 — Phase 10: Abracadabra Content Intelligence Service

Abracadabra is a content intelligence agent that:
  1. Discovers chat log data offerings from Karma Hello on EM
  2. Buys raw/enriched datasets ($0.01-$0.05)
  3. Generates content products (trending topics, blog posts, clip suggestions,
     predictions, knowledge graphs)
  4. Sells generated content on Execution Market

Supply chain position:
  Karma Hello (raw logs $0.01)
    -> Abracadabra (buys logs, produces content products $0.02-$0.10)

Usage:
  python abracadabra_service.py                  # Full 4-phase cycle
  python abracadabra_service.py --discover       # Only discover offerings
  python abracadabra_service.py --buy            # Only buy data
  python abracadabra_service.py --generate       # Only generate content
  python abracadabra_service.py --sell           # Only publish products
  python abracadabra_service.py --all            # Explicit full cycle
  python abracadabra_service.py --dry-run        # Preview all actions
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure services package is importable
sys.path.insert(0, str(Path(__file__).parent))

from abracadabra_skills import SKILLS, format_skill_title, get_skill, list_skills
from em_client import AgentContext, EMClient, load_agent_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("kk.abracadabra")

# Budget limits
MAX_BUY_PER_ITEM = 0.05
MAX_DAILY_BUY_BUDGET = 0.50

# Cache directory for generated content
CONTENT_CACHE_DIR = "content_cache"


# ---------------------------------------------------------------------------
# Phase 1: Discover — Browse EM for [KK Data] offerings from Karma Hello
# ---------------------------------------------------------------------------


async def discover_offerings(client: EMClient) -> list[dict[str, Any]]:
    """Search EM for data offerings from Karma Hello."""
    logger.info("Phase 1: Discover data offerings")

    try:
        tasks = await client.browse_tasks(
            status="published",
            category="knowledge_access",
        )
    except Exception as e:
        logger.error(f"  Failed to browse tasks: {e}")
        return []

    # Filter for KK Data offerings (from Karma Hello or sibling extractors)
    offerings = [
        t
        for t in tasks
        if "[KK Data]" in t.get("title", "")
        and t.get("bounty_usdc", t.get("bounty_usd", 0)) <= MAX_BUY_PER_ITEM
    ]

    logger.info(f"  Found {len(offerings)} data offerings within budget")
    for t in offerings:
        bounty = t.get("bounty_usdc", t.get("bounty_usd", 0))
        logger.info(f"    {t.get('title', '?')} (${bounty})")

    return offerings


# ---------------------------------------------------------------------------
# Phase 2: Buy — Purchase chat log datasets if within budget
# ---------------------------------------------------------------------------


async def buy_offerings(
    client: EMClient,
    offerings: list[dict[str, Any]],
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Buy data offerings from the marketplace.

    Respects daily budget and per-item limits.
    Returns list of purchased task metadata.
    """
    logger.info("Phase 2: Buy data offerings")

    if not offerings:
        logger.info("  No offerings to buy")
        return []

    if not client.agent.executor_id:
        logger.error("  Cannot buy: executor_id not set (register on EM first)")
        return []

    purchased = []
    buy_spent = 0.0

    for task in offerings:
        task_id = task.get("id", "")
        title = task.get("title", "?")
        bounty = task.get("bounty_usdc", task.get("bounty_usd", 0))

        # Budget checks
        if bounty > MAX_BUY_PER_ITEM:
            logger.info(f"  SKIP (too expensive): {title} (${bounty})")
            continue

        if buy_spent + bounty > MAX_DAILY_BUY_BUDGET:
            logger.info(f"  SKIP (daily buy budget reached): {title}")
            break

        if not client.agent.can_spend(bounty):
            logger.warning(f"  SKIP (agent budget limit): ${client.agent.daily_spent_usd:.2f} spent")
            break

        if dry_run:
            logger.info(f"  [DRY RUN] Would buy: {title} (${bounty})")
            purchased.append(task)
            continue

        logger.info(f"  Buying: {title} (${bounty})")
        try:
            result = await client.apply_to_task(
                task_id=task_id,
                executor_id=client.agent.executor_id,
                message="Abracadabra agent -- buying data for content intelligence generation",
            )
            client.agent.record_spend(bounty)
            buy_spent += bounty
            purchased.append({**task, "apply_result": result})
            logger.info(f"    Applied to task {task_id}")
        except Exception as e:
            logger.error(f"    Failed to apply to {task_id}: {e}")

    logger.info(f"  Purchased {len(purchased)} offerings (${buy_spent:.2f})")
    return purchased


# ---------------------------------------------------------------------------
# Phase 3: Generate — Process purchased data to create content products
# ---------------------------------------------------------------------------


def _generate_stream_analysis(raw_data: dict[str, Any], stream_id: str) -> dict[str, Any]:
    """Generate a stream analysis report from raw chat data."""
    messages = raw_data.get("messages", [])
    total = len(messages)

    # Placeholder analysis (actual AI generation is Phase 10+)
    topics: dict[str, int] = {}
    for msg in messages:
        text = msg.get("message", msg.get("text", "")).lower()
        for keyword in ["blockchain", "defi", "nft", "ai", "python", "solidity", "trading"]:
            if keyword in text:
                topics[keyword] = topics.get(keyword, 0) + 1

    top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "type": "stream_analysis",
        "stream_id": stream_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_messages": total,
        "topic_breakdown": [{"topic": t, "count": c} for t, c in top_topics],
        "engagement_summary": {
            "peak_messages_per_minute": 0,
            "avg_message_length": sum(len(m.get("message", "")) for m in messages) / max(total, 1),
        },
        "note": "Placeholder analysis -- full AI generation pending OpenAI API integration",
    }


def _generate_trending_predictions(raw_data: dict[str, Any], timeframe: str) -> dict[str, Any]:
    """Generate trending topic predictions from aggregated data."""
    topics = raw_data.get("topics", raw_data.get("topic_map", {}))

    # Placeholder predictions based on frequency
    predictions = []
    if isinstance(topics, dict):
        sorted_topics = sorted(topics.items(), key=lambda x: x[1] if isinstance(x[1], int) else 0, reverse=True)
        for i, (topic, count) in enumerate(sorted_topics[:10]):
            confidence = max(0.3, 0.9 - (i * 0.07))
            predictions.append({
                "topic": topic,
                "confidence": round(confidence, 2),
                "trend": "rising" if i < 3 else "stable",
                "mentions": count if isinstance(count, int) else 0,
            })

    return {
        "type": "trending_predictions",
        "timeframe": timeframe,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "predictions": predictions,
        "note": "Placeholder predictions -- full AI generation pending",
    }


def _generate_blog_post(raw_data: dict[str, Any], topic: str) -> dict[str, Any]:
    """Generate a blog post summary from chat data about a topic."""
    messages = raw_data.get("messages", [])
    relevant = [
        m for m in messages if topic.lower() in m.get("message", m.get("text", "")).lower()
    ]

    return {
        "type": "blog_post",
        "topic": topic,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": f"Community Insights: {topic.title()}",
        "word_count": 0,
        "relevant_messages": len(relevant),
        "summary": f"Blog post about '{topic}' based on {len(relevant)} community messages.",
        "content": f"# Community Insights: {topic.title()}\n\n"
        f"Based on analysis of {len(relevant)} messages from the Ultravioleta DAO community.\n\n"
        f"*Full AI-generated content pending OpenAI API integration.*\n",
        "note": "Placeholder content -- full AI generation pending",
    }


def _generate_clip_suggestions(raw_data: dict[str, Any], stream_id: str) -> dict[str, Any]:
    """Generate clip suggestions from stream data."""
    messages = raw_data.get("messages", [])

    # Placeholder: find message clusters as potential clip moments
    suggestions = []
    if len(messages) > 10:
        # Sample 3 "high engagement" moments
        step = max(1, len(messages) // 4)
        for i in range(1, 4):
            idx = min(i * step, len(messages) - 1)
            msg = messages[idx]
            suggestions.append({
                "timestamp_index": idx,
                "topic": "community discussion",
                "suggested_title": f"Highlight moment #{i}",
                "estimated_virality": round(0.5 + (0.1 * (3 - i)), 2),
            })

    return {
        "type": "clip_suggestions",
        "stream_id": stream_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suggestions": suggestions,
        "note": "Placeholder suggestions -- full AI generation pending",
    }


def _generate_knowledge_graph(raw_data: dict[str, Any], topic: str) -> dict[str, Any]:
    """Generate a knowledge graph from chat data."""
    messages = raw_data.get("messages", [])

    # Placeholder: extract entity co-occurrences
    entities = set()
    for msg in messages:
        text = msg.get("message", msg.get("text", "")).lower()
        for keyword in ["blockchain", "defi", "nft", "ai", "python", "solidity", "ethereum", "base"]:
            if keyword in text:
                entities.add(keyword)

    nodes = [{"id": e, "label": e.title()} for e in sorted(entities)]
    edges = []
    entity_list = sorted(entities)
    for i in range(len(entity_list)):
        for j in range(i + 1, min(i + 3, len(entity_list))):
            edges.append({
                "source": entity_list[i],
                "target": entity_list[j],
                "weight": 1,
            })

    return {
        "type": "knowledge_graph",
        "topic": topic,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
        "note": "Placeholder graph -- full AI generation pending",
    }


GENERATORS = {
    "analyze_stream": _generate_stream_analysis,
    "predict_trending": _generate_trending_predictions,
    "generate_blog": _generate_blog_post,
    "suggest_clips": _generate_clip_suggestions,
    "knowledge_graph": _generate_knowledge_graph,
}


async def generate_content(
    data_dir: Path,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Process purchased data and generate content products.

    For now generates placeholder summaries. Actual AI generation
    will be wired in when OpenAI API is integrated (Phase 10+).
    """
    logger.info("Phase 3: Generate content products")

    cache_dir = data_dir / CONTENT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Load any available raw data
    raw_data: dict[str, Any] = {}
    agg_file = data_dir / "aggregated.json"
    if agg_file.exists():
        try:
            raw_data = json.loads(agg_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"  Failed to load aggregated data: {e}")

    if not raw_data:
        logger.info("  No raw data available -- generating from empty dataset")
        raw_data = {"messages": [], "stats": {}, "topics": {}}

    generated = []
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Generate one product per skill type
    generation_params = {
        "analyze_stream": ("stream_id", f"session-{now_str}"),
        "predict_trending": ("timeframe", f"7d-from-{now_str}"),
        "generate_blog": ("topic", "community-trends"),
        "suggest_clips": ("stream_id", f"session-{now_str}"),
        "knowledge_graph": ("topic", "ultravioleta-ecosystem"),
    }

    for skill_name, (param_name, param_value) in generation_params.items():
        generator = GENERATORS.get(skill_name)
        if not generator:
            continue

        if dry_run:
            logger.info(f"  [DRY RUN] Would generate: {skill_name} ({param_name}={param_value})")
            generated.append({"skill": skill_name, "param": param_value, "dry_run": True})
            continue

        logger.info(f"  Generating: {skill_name} ({param_name}={param_value})")
        try:
            content = generator(raw_data, param_value)
            # Cache to disk
            output_file = cache_dir / f"{skill_name}_{now_str}.json"
            output_file.write_text(
                json.dumps(content, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            generated.append({"skill": skill_name, "param": param_value, "content": content})
            logger.info(f"    Cached to {output_file.name}")
        except Exception as e:
            logger.error(f"    Failed to generate {skill_name}: {e}")

    logger.info(f"  Generated {len(generated)} content products")
    return generated


# ---------------------------------------------------------------------------
# Phase 4: Sell — Publish content products on EM using skills registry
# ---------------------------------------------------------------------------


async def sell_content(
    client: EMClient,
    generated_content: list[dict[str, Any]],
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Publish generated content products as tasks on EM."""
    logger.info("Phase 4: Sell content products")

    if not generated_content:
        logger.info("  No content to sell")
        return []

    published = []

    for item in generated_content:
        skill_name = item.get("skill", "")
        param_value = item.get("param", "")

        skill = get_skill(skill_name)
        if not skill:
            logger.warning(f"  Unknown skill: {skill_name}")
            continue

        bounty = skill["bounty"]

        # Determine template parameter name from skill title
        if "{stream_id}" in skill["title"]:
            title = format_skill_title(skill_name, stream_id=param_value)
        elif "{timeframe}" in skill["title"]:
            title = format_skill_title(skill_name, timeframe=param_value)
        elif "{topic}" in skill["title"]:
            title = format_skill_title(skill_name, topic=param_value)
        else:
            title = skill["title"]

        if not client.agent.can_spend(bounty):
            logger.warning(f"  SKIP (budget limit): {title}")
            break

        if dry_run:
            logger.info(f"  [DRY RUN] Would publish: {title} (${bounty})")
            published.append({"skill": skill_name, "title": title, "bounty": bounty, "dry_run": True})
            continue

        logger.info(f"  Publishing: {title} (${bounty})")
        try:
            result = await client.publish_task(
                title=title,
                instructions=skill["description"],
                category=skill["category"],
                bounty_usd=bounty,
                deadline_hours=24,
                evidence_required=[skill.get("evidence_type", "text")],
            )
            task_id = result.get("task", {}).get("id") or result.get("id", "unknown")
            client.agent.record_spend(bounty)
            published.append({"skill": skill_name, "title": title, "bounty": bounty, "task_id": task_id})
            logger.info(f"    Published: task_id={task_id}")
        except Exception as e:
            logger.error(f"    Failed to publish {skill_name}: {e}")

    logger.info(f"  Published {len(published)} content products")
    return published


# ---------------------------------------------------------------------------
# Swarm state integration
# ---------------------------------------------------------------------------


async def _report_heartbeat(agent_name: str, status: str, spent: float, notes: str = "") -> None:
    """Report heartbeat to swarm state (non-fatal)."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
        from swarm_state import report_heartbeat

        await report_heartbeat(
            agent_name=agent_name,
            status=status,
            daily_spent=spent,
            notes=notes,
        )
    except Exception as e:
        logger.debug(f"  Heartbeat failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="Abracadabra -- Content Intelligence Service")
    parser.add_argument("--workspace", type=str, default=None, help="Workspace directory")
    parser.add_argument("--data-dir", type=str, default=None, help="Pipeline data directory")
    parser.add_argument("--discover", action="store_true", help="Only discover offerings")
    parser.add_argument("--buy", action="store_true", help="Only buy data")
    parser.add_argument("--generate", action="store_true", help="Only generate content")
    parser.add_argument("--sell", action="store_true", help="Only publish products")
    parser.add_argument("--all", action="store_true", help="Run full 4-phase cycle")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    workspace_dir = Path(args.workspace) if args.workspace else base / "data" / "workspaces" / "kk-abracadabra"
    data_dir = Path(args.data_dir) if args.data_dir else base / "data"

    # Load agent context
    if workspace_dir.exists():
        agent = load_agent_context(workspace_dir)
    else:
        agent = AgentContext(
            name="kk-abracadabra",
            wallet_address="",
            workspace_dir=workspace_dir,
        )

    print(f"\n{'=' * 60}")
    print(f"  Abracadabra -- Content Intelligence Service")
    print(f"  Agent: {agent.name}")
    print(f"  Skills: {', '.join(list_skills())}")
    if args.dry_run:
        print(f"  ** DRY RUN **")
    print(f"{'=' * 60}\n")

    client = EMClient(agent)
    run_all = args.all or not (args.discover or args.buy or args.generate or args.sell)

    try:
        # Report starting heartbeat
        await _report_heartbeat(agent.name, "running", agent.daily_spent_usd, "Starting cycle")

        offerings = []
        purchased = []
        generated_content = []
        published = []

        # Phase 1: Discover
        if args.discover or run_all:
            offerings = await discover_offerings(client)

        # Phase 2: Buy
        if args.buy or run_all:
            if not offerings and run_all:
                # Already discovered above
                pass
            elif not offerings:
                offerings = await discover_offerings(client)
            purchased = await buy_offerings(client, offerings, dry_run=args.dry_run)

        # Phase 3: Generate
        if args.generate or run_all:
            generated_content = await generate_content(data_dir, dry_run=args.dry_run)

        # Phase 4: Sell
        if args.sell or run_all:
            if not generated_content and run_all:
                pass
            elif not generated_content:
                generated_content = await generate_content(data_dir, dry_run=args.dry_run)
            published = await sell_content(client, generated_content, dry_run=args.dry_run)

        # Summary
        print(f"\n{'=' * 60}")
        print(f"  Cycle Complete")
        print(f"  Offerings found: {len(offerings)}")
        print(f"  Data purchased:  {len(purchased)}")
        print(f"  Content generated: {len(generated_content)}")
        print(f"  Products published: {len(published)}")
        print(f"  Daily spent: ${agent.daily_spent_usd:.2f} / ${agent.daily_budget_usd:.2f}")
        print(f"{'=' * 60}\n")

        # Report completion heartbeat
        await _report_heartbeat(
            agent.name,
            "idle",
            agent.daily_spent_usd,
            f"Cycle done: {len(published)} published",
        )

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
