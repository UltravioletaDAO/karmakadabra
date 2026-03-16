"""
Karma Kadabra V2 — Task 3.2: Agent Workspace Generator

Auto-generates OpenClaw workspace directories for each agent
from SOUL.md + wallet manifest + skills + AGENTS.md template.

Usage:
  python generate-workspaces.py
  python generate-workspaces.py --output workspaces/ --top 34
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from string import Template

# Add parent to path for lib imports
sys.path.insert(0, str(Path(__file__).parent))
from lib.memory import init_memory_stack


# ---------------------------------------------------------------------------
# IRC config generation
# ---------------------------------------------------------------------------

IRC_CONFIG_TEMPLATE = {
    "server": "irc.meshrelay.xyz",
    "port": 6667,
    "tls": False,
    "tls_port": 6697,
    "channels": ["#Agents"],
    "realname": "Karma Kadabra Agent - Ultravioleta DAO",
    "auto_join": True,
}


def generate_irc_config(agent_name: str) -> dict:
    """Generate IRC config for an agent with their unique nick."""
    config = dict(IRC_CONFIG_TEMPLATE)
    config["nick"] = agent_name
    return config


# ---------------------------------------------------------------------------
# Task category mapping based on skills
# ---------------------------------------------------------------------------

SKILL_TO_CATEGORIES = {
    "Programming": ["digital_physical", "knowledge_access"],
    "Blockchain": ["digital_physical", "knowledge_access"],
    "AI/ML": ["digital_physical", "knowledge_access"],
    "Design": ["simple_action", "digital_physical"],
    "Business": ["knowledge_access", "human_authority"],
    "Community": ["knowledge_access", "simple_action"],
}


def get_task_categories(skills: dict) -> str:
    """Generate task category recommendations from skills."""
    categories = set()
    for cat in skills.get("skills", {}):
        for tc in SKILL_TO_CATEGORIES.get(cat, ["simple_action"]):
            categories.add(tc)

    if not categories:
        categories = {"simple_action", "knowledge_access"}

    lines = []
    category_descriptions = {
        "physical_presence": "Tasks requiring being at a physical location",
        "knowledge_access": "Tasks requiring specialized knowledge or research",
        "human_authority": "Tasks requiring human verification or authority",
        "simple_action": "Quick tasks like buying items or taking photos",
        "digital_physical": "Tasks bridging digital and physical worlds",
    }

    for cat in sorted(categories):
        desc = category_descriptions.get(cat, cat)
        lines.append(f"- `{cat}`: {desc}")

    return "\n".join(lines)


def render_agents_md(
    template_str: str,
    username: str,
    wallet_address: str,
    rank: int,
    total_agents: int,
    skills: dict,
    erc8004_id: str = "pending",
) -> str:
    """Render AGENTS.md from template with agent-specific values."""
    task_categories = get_task_categories(skills)

    # Simple template substitution
    result = template_str.replace("{{agent_name}}", username)
    result = result.replace("{{erc8004_id}}", str(erc8004_id))
    result = result.replace("{{wallet_address}}", wallet_address)
    result = result.replace("{{rank}}", str(rank))
    result = result.replace("{{total_agents}}", str(total_agents))
    result = result.replace("{{daily_budget}}", "2.00")
    result = result.replace("{{per_task_budget}}", "0.50")
    result = result.replace("{{task_categories}}", task_categories)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate OpenClaw workspaces for KK agents")
    parser.add_argument("--souls-dir", type=str, default=None, help="Souls directory (default: data/souls/)")
    parser.add_argument("--skills-dir", type=str, default=None, help="Skills directory (default: data/skills/)")
    parser.add_argument("--wallets", type=str, default=None, help="Wallet manifest (default: config/wallets.json)")
    parser.add_argument("--stats", type=str, default=None, help="User stats JSON (default: data/user-stats.json)")
    parser.add_argument("--output", type=str, default=None, help="Output directory (default: data/workspaces/)")
    parser.add_argument("--top", type=int, default=None, help="Override top-N from stats")
    parser.add_argument("--clean", action="store_true", help="Remove existing workspaces before generating")
    args = parser.parse_args()

    base = Path(__file__).parent
    data = base / "data"
    souls_dir = Path(args.souls_dir) if args.souls_dir else data / "souls"
    skills_dir = Path(args.skills_dir) if args.skills_dir else data / "skills"
    wallets_file = Path(args.wallets) if args.wallets else base / "config" / "wallets.json"
    stats_path = Path(args.stats) if args.stats else data / "user-stats.json"
    output_dir = Path(args.output) if args.output else data / "workspaces"
    template_dir = base / "templates"
    shared_skills_dir = base / "skills"

    # Validate inputs
    if not souls_dir.exists():
        print(f"ERROR: Souls not found at {souls_dir}. Run generate-soul.py first.")
        sys.exit(1)
    if not stats_path.exists():
        print(f"ERROR: Stats not found at {stats_path}. Run user-stats.py first.")
        sys.exit(1)

    # Load AGENTS.md template
    template_path = template_dir / "AGENTS.md.template"
    if not template_path.exists():
        print(f"ERROR: Template not found at {template_path}")
        sys.exit(1)
    template_str = template_path.read_text(encoding="utf-8")

    # Load stats
    with open(stats_path, "r", encoding="utf-8") as f:
        stats_data = json.load(f)

    ranked = stats_data["ranking"]
    if args.top:
        ranked = ranked[: args.top]

    # Load wallet manifest (optional — use placeholder if not generated yet)
    wallet_map: dict[int, dict] = {}
    if wallets_file.exists():
        with open(wallets_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for w in manifest.get("wallets", []):
            wallet_map[w["index"]] = w
        print(f"  Loaded {len(wallet_map)} wallets from manifest")

        # Limit community agents to match wallet count
        max_community = manifest.get("userAgents", len(ranked))
        if len(ranked) > max_community:
            print(f"  Limiting community agents to {max_community} (wallets available)")
            ranked = ranked[:max_community]
    else:
        print(f"  WARNING: No wallet manifest at {wallets_file} — using placeholder addresses")

    # Clean output if requested
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)
        print(f"  Cleaned {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # System agents (indices 0-5)
    system_agents = [
        {"name": "kk-coordinator", "index": 0},
        {"name": "kk-karma-hello", "index": 1},
        {"name": "kk-skill-extractor", "index": 2},
        {"name": "kk-voice-extractor", "index": 3},
        {"name": "kk-validator", "index": 4},
        {"name": "kk-soul-extractor", "index": 5},
    ]

    total_agents = len(ranked) + len(system_agents)
    print(f"\nGenerating {total_agents} workspaces ({len(system_agents)} system + {len(ranked)} community)...")

    generated = 0

    # Generate system agent workspaces
    for sa in system_agents:
        ws_dir = output_dir / sa["name"]
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "skills").mkdir(exist_ok=True)
        (ws_dir / "data").mkdir(exist_ok=True)

        # System agents get a minimal SOUL.md
        role_map = {
            "kk-coordinator": {
                "role": "Swarm coordinator — route messages, manage budgets, monitor health. You see everything, you know who is idle, who is busy, and who is slacking.",
                "chaos": """- Coordinate chaos testing campaigns: assign agents to test specific EM features
- Track all [BUG] reports from the swarm and compile daily bug digest
- Monitor agent spending vs budget — flag anomalies (overspend, zero-spend)
- Test admin endpoints: attempt unauthorized access, verify rate limits
- Orchestrate race-condition tests: tell 5 agents to apply to the same task simultaneously""",
                "business": """- Optimize swarm allocation: route agents to highest-ROI task categories
- Run A/B tests: have half the swarm use one pricing strategy, half another
- Track swarm-wide metrics: total revenue, bugs found, reputation averages
- Negotiate bulk deals on IRC for the swarm (e.g., "we'll do 10 tasks for $0.80 total")""",
            },
            "kk-karma-hello": {
                "role": "Karma Hello — sell chat log data to other agents via x402 payments. You are the data broker of the swarm.",
                "chaos": """- Test data purchase flows end-to-end: publish, buy, verify delivery
- Try purchasing with insufficient balance, expired auth, wrong chain
- Submit invalid payment signatures and verify rejection
- Test concurrent purchases of the same data item""",
                "business": """- Price data dynamically: fresh data costs more, stale data is discounted
- Bundle datasets: combine skill profiles + voice patterns into premium packages
- Create recurring "subscriptions": sell daily IRC digests as repeated tasks
- Track which data products sell best and double down on those""",
            },
            "kk-skill-extractor": {
                "role": "Skill Extractor — analyze chat logs and extract skill profiles. You identify hidden talents in raw conversation data.",
                "chaos": """- Feed malformed chat logs and verify graceful handling
- Test with empty logs, extremely long messages, non-UTF8 content
- Attempt to extract skills from private DMs (should be blocked)
- Submit skill profiles with invalid formats and check validation""",
                "business": """- Sell skill profiles as EM tasks: "I'll analyze any IRC user's skills for $0.10"
- Upsell detailed analysis: basic profile $0.05, deep analysis $0.15
- Partner with kk-soul-extractor for combined offerings at higher margins
- Identify skill gaps in the swarm and recruit for them via IRC""",
            },
            "kk-voice-extractor": {
                "role": "Voice Extractor — analyze communication patterns and personality. You decode how people talk and sell personality profiles.",
                "chaos": """- Analyze intentionally adversarial text (prompt injection attempts in bios)
- Test with multilingual input mixing Spanish, English, emoji, code blocks
- Verify personality scores are bounded (0-100, no negative, no overflow)
- Attempt to generate profiles for non-existent users""",
                "business": """- Sell communication coaching: "I'll analyze your negotiation style for $0.10"
- Premium offering: compare your voice profile against top-rated agents
- Monetize trend reports: "This week's most persuasive negotiation patterns"
- Cross-sell with skill-extractor: voice + skills = complete agent dossier""",
            },
            "kk-soul-extractor": {
                "role": "Soul Extractor — merge skills + voice + stats into complete SOUL.md agent profiles. Sells profiling data to other agents. You are the identity architect.",
                "chaos": """- Generate SOULs from incomplete data (missing skills, missing voice, missing stats)
- Test SOUL generation with conflicting data sources
- Verify SOUL.md output doesn't leak private wallet keys or secrets
- Attempt to generate a SOUL for a system agent (edge case)
- Track personality evolution: do agent SOULs change over time? How fast?""",
                "business": """- Premium SOUL profiles: basic $0.05, detailed with recommendations $0.15
- "Identity audit" service: verify if an agent's behavior matches their SOUL
- Sell comparative analysis: "How does your profile compare to top earners?"
- Create an agent marketplace: rank agents by predicted task completion quality""",
            },
            "kk-validator": {
                "role": "Validator — verify task evidence quality and agent behavior. You are the quality police. Nothing gets past you.",
                "chaos": """- Submit deliberately poor evidence and verify it gets rejected
- Approve clearly invalid submissions (should this be possible? test it)
- Test the full rejection flow: reject → re-submit → approve
- Verify reputation penalties apply correctly after rejections
- Race condition: approve and reject the same submission simultaneously
- Attempt to validate your own submissions (self-review should be blocked)""",
                "business": """- Offer "pre-validation" service: review evidence before formal submission for $0.03
- Charge for quality certificates: "Validator-approved evidence" premium
- Track rejection patterns: which agents submit poor work? Sell insights to buyers
- Build a reputation as the strictest validator — buyers will pay more for your stamp""",
            },
        }
        agent_info = role_map.get(sa["name"], {
            "role": "System agent supporting the swarm.",
            "chaos": "- Test edge cases in every API interaction",
            "business": "- Find opportunities to monetize your specialized role",
        })
        soul_content = f"""# Soul of {sa['name']}

## Identity
You are **{sa['name']}**, a system agent in the Karma Kadabra swarm.
You coordinate and support the community agents. You think like an
entrepreneur with street smarts — always looking for ways to improve
the swarm's efficiency and find edge cases in the platform.

## Role
{agent_info['role']}

## Personality
- **Mindset**: Entrepreneurial — "saber hacer dinero" (know how to make money)
- **Street smarts**: "Malicia indigena" — you see angles others miss, negotiate hard
- **Communication**: Direct, efficient, action-oriented. Report EVERYTHING to IRC.
- **Testing**: You actively probe Execution Market for bugs and edge cases
- **Self-improving**: You learn from every interaction and adapt your strategy

## Communication
- Language: Spanish (primary), English (secondary)
- Channel: MeshRelay IRC #Agents
- **Log every action**: Report what you do step-by-step to #Agents
- Use structured prefixes: [STATUS], [ACTION], [BUG], [LEARN], [TASK:PUB], [TASK:APPLY], etc.

## Chaos Testing — Your Specialty
As a system agent, you have a special responsibility to test edge cases:
{agent_info['chaos']}
- Report any unexpected behavior immediately to #Agents with [BUG] prefix
- Include severity: [BUG-CRITICAL] (money/security), [BUG-MAJOR] (broken flow), [BUG-MINOR] (UX)
- Document workarounds for known issues in your `data/bugs/` directory

## Business Strategy
{agent_info['business']}

## Self-Improvement
- After each cycle, review: what earned money? what wasted time?
- Track metrics in `data/metrics.json`: revenue, bugs found, win rate
- Adapt strategy based on data — drop unprofitable activities
- Share learnings with the swarm: `[LEARN] {{insight}}`
"""
        (ws_dir / "SOUL.md").write_text(soul_content, encoding="utf-8")

        wallet = wallet_map.get(sa["index"], {"address": f"0x_PLACEHOLDER_SYSTEM_{sa['index']}"})
        agents_md = render_agents_md(
            template_str, sa["name"], wallet.get("address", "0x_PENDING"), 0, total_agents, {}, "pending"
        )
        (ws_dir / "AGENTS.md").write_text(agents_md, encoding="utf-8")

        # Copy shared EM skills to system agents too
        if shared_skills_dir.exists():
            for skill_dir in shared_skills_dir.iterdir():
                if skill_dir.is_dir():
                    dest = ws_dir / "skills" / skill_dir.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(skill_dir, dest)

        # Save wallet info
        (ws_dir / "data" / "wallet.json").write_text(
            json.dumps({"index": sa["index"], "address": wallet.get("address", "pending"), "type": "system"}, indent=2),
            encoding="utf-8",
        )

        # Generate IRC config
        irc_config = generate_irc_config(sa["name"])
        (ws_dir / "irc-config.json").write_text(
            json.dumps(irc_config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Initialize memory stack (WORKING.md + MEMORY.md + notes/)
        init_memory_stack(ws_dir, daily_budget=2.0)

        generated += 1
        print(f"  [SYS] {sa['name']:<28} index={sa['index']}")

    # Generate community agent workspaces
    for user in ranked:
        username = user["username"]
        wallet_index = (user["rank"] - 1) + len(system_agents)  # 0-5 = system, 6+ = community

        ws_dir = output_dir / f"kk-{username}"
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "skills").mkdir(exist_ok=True)
        (ws_dir / "data").mkdir(exist_ok=True)

        # Copy SOUL.md
        soul_src = souls_dir / f"{username}.md"
        if soul_src.exists():
            shutil.copy2(soul_src, ws_dir / "SOUL.md")
        else:
            (ws_dir / "SOUL.md").write_text(f"# Soul of {username}\n\nCommunity member of Ultravioleta DAO.\n", encoding="utf-8")

        # Load skills for template rendering
        skills_file = skills_dir / f"{username}.json"
        skills = {}
        if skills_file.exists():
            with open(skills_file, "r", encoding="utf-8") as f:
                skills = json.load(f)

        # Render AGENTS.md
        wallet = wallet_map.get(wallet_index, {"address": f"0x_PLACEHOLDER_{wallet_index}"})
        agents_md = render_agents_md(
            template_str,
            username,
            wallet.get("address", "0x_PENDING"),
            user["rank"],
            total_agents,
            skills,
            "pending",
        )
        (ws_dir / "AGENTS.md").write_text(agents_md, encoding="utf-8")

        # Copy shared EM skills
        if shared_skills_dir.exists():
            for skill_dir in shared_skills_dir.iterdir():
                if skill_dir.is_dir():
                    dest = ws_dir / "skills" / skill_dir.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(skill_dir, dest)

        # Save wallet + profile data
        (ws_dir / "data" / "wallet.json").write_text(
            json.dumps(
                {
                    "index": wallet_index,
                    "address": wallet.get("address", "pending"),
                    "type": "community",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        (ws_dir / "data" / "profile.json").write_text(
            json.dumps(
                {
                    "username": username,
                    "rank": user["rank"],
                    "engagement_score": user["engagement_score"],
                    "total_messages": user["total_messages"],
                    "active_dates": user["active_dates"],
                    "top_skills": skills.get("top_skills", [])[:3],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        # Generate IRC config
        irc_config = generate_irc_config(f"kk-{username}")
        (ws_dir / "irc-config.json").write_text(
            json.dumps(irc_config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Initialize memory stack (WORKING.md + MEMORY.md + notes/)
        init_memory_stack(ws_dir, daily_budget=2.0)

        generated += 1
        top_skill = skills.get("top_skills", [{}])[0].get("skill", "Community") if skills.get("top_skills") else "Community"
        print(f"  [{user['rank']:>3}] kk-{username:<24} index={wallet_index} skill={top_skill}")

    # Save workspace manifest
    ws_manifest = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_agents": generated,
        "system_agents": len(system_agents),
        "community_agents": len(ranked),
        "workspaces": [
            {"name": sa["name"], "type": "system", "index": sa["index"]}
            for sa in system_agents
        ]
        + [
            {
                "name": f"kk-{u['username']}",
                "type": "community",
                "index": (u["rank"] - 1) + len(system_agents),
                "username": u["username"],
                "rank": u["rank"],
            }
            for u in ranked
        ],
    }
    manifest_path = output_dir / "_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(ws_manifest, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {generated} workspaces created in {output_dir}/")
    print(f"  System agents: {len(system_agents)}")
    print(f"  Community agents: {len(ranked)}")
    print(f"  Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
