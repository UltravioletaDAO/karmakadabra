"""
Tests for Abracadabra Content Intelligence Service (Phase 10)

Covers:
  - Skills registry: all 5 skills have required fields
  - Discover phase finds KK Data offerings
  - Buy phase respects budget limits
  - Generate phase creates content summaries
  - Sell phase creates correct EM task payloads
  - IRC command parsing (trending, predict, blog, clips, help)
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent / "irc"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.abracadabra_skills import (
    REQUIRED_FIELDS,
    SKILLS,
    format_skill_title,
    get_skill,
    get_skill_bounty,
    list_skills,
    validate_skills,
)
from services.em_client import AgentContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent(**kwargs) -> AgentContext:
    defaults = {
        "name": "kk-abracadabra",
        "wallet_address": "0xTEST",
        "workspace_dir": Path("/tmp/kk-abracadabra"),
        "daily_budget_usd": 2.0,
    }
    defaults.update(kwargs)
    return AgentContext(**defaults)


def _make_mock_client(agent: AgentContext | None = None) -> MagicMock:
    """Create a mock EMClient."""
    client = MagicMock()
    client.agent = agent or _make_agent(executor_id="exec-123")
    client.browse_tasks = AsyncMock(return_value=[])
    client.apply_to_task = AsyncMock(return_value={"id": "apply-1"})
    client.publish_task = AsyncMock(return_value={"task": {"id": "task-pub-1"}})
    client.close = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Tests: Skills Registry
# ---------------------------------------------------------------------------


def test_skills_registry_has_five_skills():
    """Registry contains exactly 5 skills."""
    assert len(SKILLS) == 5


def test_all_skills_have_required_fields():
    """Every skill has title, description, category, bounty, evidence_type."""
    for name, skill in SKILLS.items():
        missing = REQUIRED_FIELDS - set(skill.keys())
        assert not missing, f"Skill '{name}' missing fields: {missing}"


def test_all_skills_have_positive_bounty():
    """Every skill has a bounty > 0."""
    for name, skill in SKILLS.items():
        assert skill["bounty"] > 0, f"Skill '{name}' has zero/negative bounty"


def test_all_skills_category_is_knowledge_access():
    """All Abracadabra skills are knowledge_access category."""
    for name, skill in SKILLS.items():
        assert skill["category"] == "knowledge_access", f"Skill '{name}' wrong category"


def test_get_skill_returns_correct_skill():
    """get_skill returns the correct skill definition."""
    skill = get_skill("generate_blog")
    assert skill is not None
    assert skill["bounty"] == 0.10
    assert "Blog Post" in skill["title"]


def test_get_skill_returns_none_for_unknown():
    """get_skill returns None for unknown skill name."""
    assert get_skill("nonexistent_skill") is None


def test_list_skills_returns_all_names():
    """list_skills returns all 5 skill names."""
    names = list_skills()
    assert len(names) == 5
    assert "analyze_stream" in names
    assert "predict_trending" in names
    assert "generate_blog" in names
    assert "suggest_clips" in names
    assert "knowledge_graph" in names


def test_format_skill_title_with_params():
    """format_skill_title fills in template parameters."""
    title = format_skill_title("analyze_stream", stream_id="2026-02-19")
    assert "2026-02-19" in title
    assert "[KK Content]" in title


def test_format_skill_title_unknown_skill():
    """format_skill_title returns empty string for unknown skill."""
    assert format_skill_title("nonexistent") == ""


def test_get_skill_bounty():
    """get_skill_bounty returns correct bounty."""
    assert get_skill_bounty("generate_blog") == 0.10
    assert get_skill_bounty("knowledge_graph") == 0.02
    assert get_skill_bounty("nonexistent") == 0.0


def test_validate_skills_no_errors():
    """validate_skills returns no errors for valid registry."""
    errors = validate_skills()
    assert errors == []


# ---------------------------------------------------------------------------
# Tests: Discover Phase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_finds_kk_data_offerings():
    """Discover phase filters for [KK Data] offerings within budget."""
    from services.abracadabra_service import discover_offerings

    client = _make_mock_client()
    client.browse_tasks = AsyncMock(
        return_value=[
            {"id": "1", "title": "[KK Data] Raw Logs", "bounty_usdc": 0.01},
            {"id": "2", "title": "[KK Data] Stats", "bounty_usdc": 0.03},
            {"id": "3", "title": "Unrelated Task", "bounty_usdc": 0.10},
            {"id": "4", "title": "[KK Data] Expensive", "bounty_usdc": 0.50},
        ]
    )

    offerings = await discover_offerings(client)
    # Should find 2 offerings: raw logs ($0.01) and stats ($0.03), not unrelated or expensive
    assert len(offerings) == 2
    titles = [o["title"] for o in offerings]
    assert "[KK Data] Raw Logs" in titles
    assert "[KK Data] Stats" in titles


@pytest.mark.asyncio
async def test_discover_handles_api_error():
    """Discover phase returns empty list on API error."""
    from services.abracadabra_service import discover_offerings

    client = _make_mock_client()
    client.browse_tasks = AsyncMock(side_effect=Exception("API down"))

    offerings = await discover_offerings(client)
    assert offerings == []


# ---------------------------------------------------------------------------
# Tests: Buy Phase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buy_respects_budget_limit():
    """Buy phase stops when agent daily budget is exhausted."""
    from services.abracadabra_service import buy_offerings

    agent = _make_agent(executor_id="exec-123")
    agent.daily_spent_usd = 1.98  # Only $0.02 left
    client = _make_mock_client(agent)

    offerings = [
        {"id": "1", "title": "[KK Data] Logs", "bounty_usdc": 0.01},
        {"id": "2", "title": "[KK Data] Stats", "bounty_usdc": 0.03},  # Would exceed budget
    ]

    purchased = await buy_offerings(client, offerings)
    # Should only buy first (0.01) since second would exceed budget
    assert len(purchased) == 1


@pytest.mark.asyncio
async def test_buy_skips_expensive_items():
    """Buy phase skips items above MAX_BUY_PER_ITEM."""
    from services.abracadabra_service import MAX_BUY_PER_ITEM, buy_offerings

    client = _make_mock_client()
    offerings = [
        {"id": "1", "title": "[KK Data] Cheap", "bounty_usdc": 0.01},
        {"id": "2", "title": "[KK Data] Expensive", "bounty_usdc": MAX_BUY_PER_ITEM + 0.01},
    ]

    purchased = await buy_offerings(client, offerings)
    assert len(purchased) == 1
    assert purchased[0]["title"] == "[KK Data] Cheap"


@pytest.mark.asyncio
async def test_buy_requires_executor_id():
    """Buy phase returns empty when executor_id is not set."""
    from services.abracadabra_service import buy_offerings

    agent = _make_agent()
    agent.executor_id = None
    client = _make_mock_client(agent)

    offerings = [{"id": "1", "title": "[KK Data] Logs", "bounty_usdc": 0.01}]
    purchased = await buy_offerings(client, offerings)
    assert purchased == []


@pytest.mark.asyncio
async def test_buy_dry_run_does_not_call_api():
    """Buy dry-run does not call apply_to_task."""
    from services.abracadabra_service import buy_offerings

    client = _make_mock_client()
    offerings = [{"id": "1", "title": "[KK Data] Logs", "bounty_usdc": 0.01}]

    purchased = await buy_offerings(client, offerings, dry_run=True)
    assert len(purchased) == 1
    client.apply_to_task.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Generate Phase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_creates_all_content_types(tmp_path):
    """Generate phase creates one product per skill type."""
    from services.abracadabra_service import generate_content

    # Create a minimal aggregated.json
    agg = {"messages": [{"message": "blockchain is cool"}, {"message": "python defi"}], "stats": {}, "topics": {}}
    (tmp_path / "aggregated.json").write_text(json.dumps(agg), encoding="utf-8")

    generated = await generate_content(tmp_path)
    assert len(generated) == 5

    skill_names = [g["skill"] for g in generated]
    assert "analyze_stream" in skill_names
    assert "predict_trending" in skill_names
    assert "generate_blog" in skill_names
    assert "suggest_clips" in skill_names
    assert "knowledge_graph" in skill_names


@pytest.mark.asyncio
async def test_generate_caches_to_disk(tmp_path):
    """Generate phase writes JSON files to content_cache directory."""
    from services.abracadabra_service import generate_content

    (tmp_path / "aggregated.json").write_text('{"messages": [], "stats": {}}', encoding="utf-8")

    await generate_content(tmp_path)
    cache_dir = tmp_path / "content_cache"
    assert cache_dir.exists()
    cached_files = list(cache_dir.glob("*.json"))
    assert len(cached_files) == 5


@pytest.mark.asyncio
async def test_generate_works_without_data(tmp_path):
    """Generate phase produces content even with no raw data."""
    from services.abracadabra_service import generate_content

    # No aggregated.json
    generated = await generate_content(tmp_path)
    assert len(generated) == 5


@pytest.mark.asyncio
async def test_generate_dry_run_no_files(tmp_path):
    """Generate dry-run does not write files to disk."""
    from services.abracadabra_service import generate_content

    generated = await generate_content(tmp_path, dry_run=True)
    assert len(generated) == 5
    cache_dir = tmp_path / "content_cache"
    # Cache dir may or may not be created, but no JSON files
    if cache_dir.exists():
        assert len(list(cache_dir.glob("*.json"))) == 0


# ---------------------------------------------------------------------------
# Tests: Sell Phase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sell_creates_correct_task_payloads():
    """Sell phase publishes tasks with correct skill metadata."""
    from services.abracadabra_service import sell_content

    client = _make_mock_client()
    generated = [
        {"skill": "generate_blog", "param": "ai-trends"},
        {"skill": "knowledge_graph", "param": "defi-ecosystem"},
    ]

    published = await sell_content(client, generated)
    assert len(published) == 2
    assert client.publish_task.call_count == 2

    # Verify first call args
    first_call = client.publish_task.call_args_list[0]
    assert "Blog Post" in first_call.kwargs.get("title", first_call[1].get("title", ""))


@pytest.mark.asyncio
async def test_sell_respects_budget():
    """Sell phase stops when budget is exhausted."""
    from services.abracadabra_service import sell_content

    agent = _make_agent()
    agent.daily_spent_usd = 1.95  # Only $0.05 left
    client = _make_mock_client(agent)

    # generate_blog costs $0.10 — should exceed budget
    generated = [
        {"skill": "knowledge_graph", "param": "test"},  # $0.02
        {"skill": "suggest_clips", "param": "stream1"},  # $0.03
        {"skill": "generate_blog", "param": "topic"},  # $0.10 — would exceed
    ]

    published = await sell_content(client, generated)
    # Should publish first two ($0.02 + $0.03 = $0.05) but not the blog ($0.10)
    assert len(published) == 2


@pytest.mark.asyncio
async def test_sell_empty_content():
    """Sell phase returns empty when no content provided."""
    from services.abracadabra_service import sell_content

    client = _make_mock_client()
    published = await sell_content(client, [])
    assert published == []
    client.publish_task.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: IRC Command Parsing
# ---------------------------------------------------------------------------


def test_parse_command_abracadabra_prefix():
    """!abracadabra prefix is recognized."""
    from irc.abracadabra_irc import parse_command

    cmd, arg = parse_command("!abracadabra trending")
    assert cmd == "trending"
    assert arg == ""


def test_parse_command_ab_prefix():
    """!ab prefix is recognized."""
    from irc.abracadabra_irc import parse_command

    cmd, arg = parse_command("!ab predict blockchain")
    assert cmd == "predict"
    assert arg == "blockchain"


def test_parse_command_with_argument():
    """Command argument is extracted correctly."""
    from irc.abracadabra_irc import parse_command

    cmd, arg = parse_command("!ab blog defi trends 2026")
    assert cmd == "blog"
    assert arg == "defi trends 2026"


def test_parse_command_no_command():
    """Bare !ab returns help command."""
    from irc.abracadabra_irc import parse_command

    cmd, arg = parse_command("!ab")
    assert cmd == "help"


def test_parse_command_ignores_non_commands():
    """Non-command messages return empty."""
    from irc.abracadabra_irc import parse_command

    cmd, arg = parse_command("hello everyone")
    assert cmd == ""
    assert arg == ""


def test_dispatch_trending():
    """Trending command returns response string."""
    from irc.abracadabra_irc import dispatch_command

    response = dispatch_command("trending", "")
    assert isinstance(response, str)
    assert len(response) > 0


def test_dispatch_help():
    """Help command lists all available commands."""
    from irc.abracadabra_irc import dispatch_command

    response = dispatch_command("help", "")
    assert "trending" in response
    assert "predict" in response
    assert "blog" in response
    assert "clips" in response


def test_dispatch_unknown_command():
    """Unknown command returns error message."""
    from irc.abracadabra_irc import dispatch_command

    response = dispatch_command("nonexistent", "")
    assert "Unknown command" in response


def test_dispatch_response_within_irc_limit():
    """All responses are within IRC message length limit."""
    from irc.abracadabra_irc import MAX_MSG_LEN, dispatch_command

    for cmd in ["trending", "help"]:
        response = dispatch_command(cmd, "")
        assert len(response) <= MAX_MSG_LEN

    for cmd in ["predict", "blog", "clips"]:
        response = dispatch_command(cmd, "test-topic")
        assert len(response) <= MAX_MSG_LEN
