#!/usr/bin/env python3
"""Generate initial Obsidian vault state files for all 24 KK agents."""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).parent.parent.parent
VAULT = REPO_ROOT / "vault"
IDENTITIES = REPO_ROOT / "data" / "config" / "identities.json"

# Agent roles
ROLES = {
    "kk-coordinator": {"role": "orchestrator", "sells": "Task routing, swarm health", "buys": "Nothing", "tags": ["system", "orchestrator"]},
    "kk-karma-hello": {"role": "seller", "sells": "Chat logs ($0.01), user stats ($0.03)", "buys": "Nothing (data producer)", "tags": ["system", "seller", "data-producer"]},
    "kk-skill-extractor": {"role": "buyer-seller", "sells": "Skill profiles ($0.05)", "buys": "Raw chat logs ($0.01)", "tags": ["system", "extractor", "buyer-seller"]},
    "kk-voice-extractor": {"role": "buyer-seller", "sells": "Voice/personality profiles ($0.04)", "buys": "Raw chat logs ($0.01)", "tags": ["system", "extractor", "buyer-seller"]},
    "kk-validator": {"role": "validator", "sells": "Validation reports ($0.001)", "buys": "Nothing", "tags": ["system", "validator"]},
    "kk-soul-extractor": {"role": "buyer-seller", "sells": "SOUL.md bundles ($0.08)", "buys": "Skill + voice profiles ($0.09)", "tags": ["system", "extractor", "aggregator"]},
}

# Supply chain links
SUPPLY_CHAIN = {
    "kk-karma-hello": {"sells_to": ["kk-skill-extractor", "kk-voice-extractor", "kk-juanjumagalp"], "buys_from": []},
    "kk-skill-extractor": {"sells_to": ["kk-soul-extractor", "kk-juanjumagalp"], "buys_from": ["kk-karma-hello"]},
    "kk-voice-extractor": {"sells_to": ["kk-soul-extractor", "kk-juanjumagalp"], "buys_from": ["kk-karma-hello"]},
    "kk-soul-extractor": {"sells_to": ["kk-juanjumagalp"], "buys_from": ["kk-skill-extractor", "kk-voice-extractor"]},
    "kk-coordinator": {"sells_to": [], "buys_from": []},
    "kk-validator": {"sells_to": [], "buys_from": []},
}


def generate_state_md(agent: dict) -> str:
    name = agent["name"]
    now = datetime.now(timezone.utc).isoformat()

    role_info = ROLES.get(name, {
        "role": "community-buyer",
        "sells": "Nothing (consumer)",
        "buys": "Chat logs, skill profiles, voice profiles, SOUL.md",
        "tags": ["community", "buyer"],
    })

    chain = SUPPLY_CHAIN.get(name, {"sells_to": [], "buys_from": ["kk-karma-hello", "kk-skill-extractor", "kk-voice-extractor", "kk-soul-extractor"]})

    erc8004_id = agent.get("registrations", {}).get("base", {}).get("agent_id", "")

    sells_to_links = ", ".join(f"[[{a}]]" for a in chain["sells_to"]) or "None"
    buys_from_links = ", ".join(f"[[{a}]]" for a in chain["buys_from"]) or "None"

    tags_yaml = "\n".join(f"  - {t}" for t in role_info["tags"] + [name.replace("kk-", "")])

    deployed = name in ["kk-coordinator", "kk-karma-hello", "kk-skill-extractor",
                        "kk-voice-extractor", "kk-validator", "kk-soul-extractor",
                        "kk-juanjumagalp"]
    status = "active" if deployed else "pending"

    return f"""---
agent_id: {name}
status: {status}
role: {role_info["role"]}
last_heartbeat: {now}
current_task: none
wallet: "{agent["address"]}"
executor_id: "{agent["executor_id"]}"
erc8004_id: {erc8004_id}
chain: base
daily_revenue_usdc: 0.00
daily_spent_usdc: 0.00
tasks_completed: 0
errors_last_24h: 0
irc_messages_sent: 0
tags:
{tags_yaml}
aliases:
  - "{name.replace("kk-", "")}"
---

## Current Activity
{"Running heartbeat loop every 5 minutes." if deployed else "Awaiting deployment."}

## Role
- **Sells**: {role_info["sells"]}
- **Buys**: {role_info["buys"]}

## Supply Chain
- Sells to: {sells_to_links}
- Buys from: {buys_from_links}

## Recent Actions
- {now[:10]} - State file initialized

## Links
- Identity: [[erc8004-registry]] (Agent #{erc8004_id})
- IRC: #karmakadabra, #Execution-Market
- EM API: [[execution-market]]
"""


def generate_shared_files():
    """Create shared coordination files."""

    # config.md
    (VAULT / "shared" / "config.md").write_text("""---
title: Shared Configuration
updated: """ + datetime.now(timezone.utc).isoformat() + """
tags:
  - config
  - shared
---

## Network
- **Chain**: Base (Chain ID: 8453)
- **Token**: USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
- **Facilitator**: https://facilitator.ultravioletadao.xyz
- **EM API**: https://api.execution.market

## ERC-8004 Registries
- **Identity**: 0x8004A169FB4a3325136EB29fA0ceB6D2e539a432
- **Reputation**: 0x8004BAa17C55a88189AE136b182e5fdA19dE9b63

## IRC
- **Server**: irc.meshrelay.xyz:6697 (SSL)
- **Channels**: #karmakadabra (general), #Execution-Market (trading)

## Agent Count
- **System**: 6 (coordinator, karma-hello, skill-extractor, voice-extractor, validator, soul-extractor)
- **Community**: 18 (juanjumagalp + 17 members)
- **Total**: 24

## Pricing
| Product | Price | Producer |
|---------|-------|----------|
| Raw chat logs | $0.01 | [[kk-karma-hello]] |
| User stats | $0.03 | [[kk-karma-hello]] |
| Skill profiles | $0.05 | [[kk-skill-extractor]] |
| Voice profiles | $0.04 | [[kk-voice-extractor]] |
| SOUL.md bundles | $0.08 | [[kk-soul-extractor]] |
| Validation | $0.001 | [[kk-validator]] |
""", encoding="utf-8")

    # supply-chain.md
    (VAULT / "shared" / "supply-chain.md").write_text("""---
title: Supply Chain Status
updated: """ + datetime.now(timezone.utc).isoformat() + """
tags:
  - supply-chain
  - shared
---

## Data Supply Chain

```
[[kk-karma-hello]] (Raw Logs $0.01)
    |
    +---> [[kk-skill-extractor]] (Skill Profiles $0.05)
    |         |
    |         +---> [[kk-soul-extractor]] (SOUL.md $0.08)
    |         |         |
    |         |         +---> [[kk-juanjumagalp]] (Consumer)
    |         |         +---> Community Buyers
    |         |
    |         +---> [[kk-juanjumagalp]]
    |         +---> Community Buyers
    |
    +---> [[kk-voice-extractor]] (Voice Profiles $0.04)
    |         |
    |         +---> [[kk-soul-extractor]]
    |         +---> [[kk-juanjumagalp]]
    |         +---> Community Buyers
    |
    +---> [[kk-juanjumagalp]] (Direct purchase)
    +---> Community Buyers (Direct purchase)
```

## Chain Status
- **Stage 1** (Raw Data): [[kk-karma-hello]] publishing actively
- **Stage 2** (Extraction): [[kk-skill-extractor]] + [[kk-voice-extractor]] buying and processing
- **Stage 3** (Synthesis): [[kk-soul-extractor]] merging skill+voice into SOUL.md
- **Stage 4** (Consumption): [[kk-juanjumagalp]] buying all products

## Flow Metrics
- Total products in chain: 5 types
- Full cycle cost: $0.18 (logs + skills + voice + SOUL.md)
- Full cycle time: ~25 minutes (5 min heartbeats x 5 steps)
""", encoding="utf-8")

    # announcements.md
    (VAULT / "shared" / "announcements.md").write_text("""---
title: Announcements
updated: """ + datetime.now(timezone.utc).isoformat() + """
tags:
  - announcements
  - shared
---

## 2026-03-01
- Obsidian Vault integration initialized for 24 agents
- IRC daemons active on all 7 deployed agents
- Supply chain running: karma-hello -> extractors -> soul-extractor -> juanjumagalp
""", encoding="utf-8")

    # ledger.md
    (VAULT / "shared" / "ledger.md").write_text("""---
title: Transaction Ledger
updated: """ + datetime.now(timezone.utc).isoformat() + """
tags:
  - ledger
  - transactions
  - shared
---

## Recent Transactions

| Date | Buyer | Seller | Product | Amount | Task ID |
|------|-------|--------|---------|--------|---------|
| 2026-02-28 | [[kk-juanjumagalp]] | [[kk-karma-hello]] | raw_logs | $0.01 | 0fde664c |
| 2026-02-28 | [[kk-skill-extractor]] | [[kk-karma-hello]] | raw_logs | $0.01 | - |
| 2026-02-28 | [[kk-voice-extractor]] | [[kk-karma-hello]] | raw_logs | $0.01 | - |

## Totals
- Total volume: $0.03
- Total transactions: 3
""", encoding="utf-8")

    # tasks.md
    (VAULT / "shared" / "tasks.md").write_text("""---
title: Task Board
updated: """ + datetime.now(timezone.utc).isoformat() + """
tags:
  - tasks
  - shared
---

## Backlog
- [ ] Deploy 17 community agents
- [ ] Implement skill extraction pipeline
- [ ] Implement voice extraction pipeline
- [ ] Add seller-side reputation rating fix

## In Progress
- [x] IRC daemon integration (all 7 agents)
- [x] Obsidian Vault setup

## Done
- [x] Golden flow: first end-to-end escrow cycle
- [x] 7 EC2 agents deployed
- [x] 24 wallets funded across 8 chains
- [x] 24 ERC-8004 NFTs registered on Base
""", encoding="utf-8")


def generate_knowledge_files():
    """Create knowledge base files."""

    (VAULT / "knowledge" / "contracts" / "erc8004-registry.md").write_text("""---
title: ERC-8004 Identity Registry
tags:
  - contract
  - erc8004
  - base
---

## ERC-8004 Identity Registry

- **Address**: 0x8004A169FB4a3325136EB29fA0ceB6D2e539a432
- **Chain**: Base (Chain ID: 8453)
- **Standard**: ERC-8004 (Agent Identity)
- **Total KK Agents**: 24

## Key Functions
- `resolveByAddress(address)` -> AgentInfo struct
- `newAgent(name, domain, metadata)` -> registers new agent
- `updateAgent(agentId, name, domain, metadata)` -> updates existing

## Related
- [[usdc-base]] - Payment token
- [[x402-payment]] - Payment protocol
- [[execution-market]] - Task marketplace
""", encoding="utf-8")

    (VAULT / "knowledge" / "contracts" / "usdc-base.md").write_text("""---
title: USDC on Base
tags:
  - contract
  - usdc
  - base
---

## USDC on Base

- **Address**: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
- **Chain**: Base (Chain ID: 8453)
- **Decimals**: 6
- **Standard**: ERC-20 + EIP-3009 (gasless transfers)

## EIP-3009 Functions
- `transferWithAuthorization(from, to, value, validAfter, validBefore, nonce, v, r, s)`
- Enables gasless payments - agents sign off-chain, facilitator executes on-chain

## Related
- [[erc8004-registry]] - Agent identities
- [[x402-payment]] - Payment protocol
- [[eip3009-gasless]] - Gasless transfer details
""", encoding="utf-8")

    (VAULT / "knowledge" / "apis" / "execution-market.md").write_text("""---
title: Execution Market API
tags:
  - api
  - execution-market
---

## Execution Market

- **URL**: https://api.execution.market
- **Auth**: `X-Agent-Wallet` header or EIP-8128 signed requests
- **Docs**: https://api.execution.market/docs

## Key Endpoints
- `POST /tasks` - Publish a task (buyer publishes bounty)
- `GET /tasks` - Browse available tasks
- `POST /tasks/{id}/apply` - Apply to a task (seller applies)
- `POST /tasks/{id}/assign` - Assign task to applicant
- `POST /tasks/{id}/submit` - Submit evidence
- `POST /tasks/{id}/approve` - Approve and release escrow

## Escrow Flow
1. Buyer publishes task with bounty amount
2. Seller applies
3. Buyer assigns (escrow locked on-chain)
4. Seller submits evidence
5. Buyer approves (escrow released: 87% seller, 13% fee)

## Related
- [[erc8004-registry]] - Agent identity verification
- [[x402-payment]] - Payment execution
- [[meshrelay-irc]] - Trading coordination
""", encoding="utf-8")

    (VAULT / "knowledge" / "apis" / "meshrelay-irc.md").write_text("""---
title: MeshRelay IRC
tags:
  - api
  - irc
  - meshrelay
---

## MeshRelay IRC Server

- **Server**: irc.meshrelay.xyz
- **Port SSL**: 6697
- **Port Plain**: 6667
- **Channels**: #karmakadabra, #Execution-Market

## Agent IRC Protocol
- `HAVE: {product} | ${price} on EM` - Announce available data
- `NEED: {product} | Budget: ${amount}` - Request data
- `DEAL: {buyer} <-> {seller} | {product} | ${price}` - Announce transaction
- `STATUS: {summary}` - Agent status update

## Integration
Each agent runs `irc_daemon.py` as background process, communicating via file-based inbox/outbox.

## Related
- [[execution-market]] - Where trades execute
- [[supply-chain]] - Data flow
""", encoding="utf-8")

    (VAULT / "knowledge" / "protocols" / "x402-payment.md").write_text("""---
title: x402 Payment Protocol
tags:
  - protocol
  - x402
  - payments
---

## x402 Payment Protocol

- **Facilitator**: https://facilitator.ultravioletadao.xyz
- **Standard**: HTTP 402 Payment Required
- **Execution**: Stateless, verifies EIP-712 signatures

## Flow
1. Buyer signs payment authorization off-chain (EIP-712)
2. Buyer sends HTTP request with payment header
3. Facilitator verifies signature
4. Facilitator executes `transferWithAuthorization()` on-chain
5. Response returned to buyer

## Related
- [[eip3009-gasless]] - Underlying transfer mechanism
- [[usdc-base]] - Payment token
- [[execution-market]] - Where x402 payments originate
""", encoding="utf-8")

    (VAULT / "knowledge" / "protocols" / "eip3009-gasless.md").write_text("""---
title: EIP-3009 Gasless Transfers
tags:
  - protocol
  - eip3009
  - gasless
---

## EIP-3009: Transfer With Authorization

Enables token transfers where the sender signs an off-chain authorization, and a third party (facilitator) submits the transaction and pays gas.

## Key Points
- Agents don't need ETH/AVAX for gas
- Nonces are random (not sequential) - prevents replay attacks
- Signatures use EIP-712 typed data
- `validAfter` and `validBefore` set time window (in SECONDS, not milliseconds)

## Related
- [[x402-payment]] - Protocol that uses EIP-3009
- [[usdc-base]] - Token that implements EIP-3009
""", encoding="utf-8")

    (VAULT / "knowledge" / "lessons-learned.md").write_text("""---
title: Lessons Learned
tags:
  - knowledge
  - lessons
---

## Deployment
- Docker volume mount `-v /data/$NAME:/app/data` HIDES built-in `/app/data/*` -- put config at `/app/config/`
- AWS Secrets Manager stores JSON -- must extract raw key from JSON wrapper
- SSH nested quoting corrupts private keys -- use SCP + local script execution
- Entrypoint uses `KK_AGENT_NAME` not `AGENT_NAME`
- AL2023 AMI requires EBS >= 30GB
- Windows CRLF in entrypoint.sh needs `sed -i 's/\\r$//'` in Dockerfile

## EM API
- `evidence_required` is MANDATORY (was missing, caused 422)
- Minimum bounty: $0.01
- 409 Conflict: agent already applied -- skip and try next
- 429 Too Many Requests: throttle with asyncio.sleep(0.5-1.0)
- Evidence format: dict keyed by type, NOT `{type: "json_response"}`

## Escrow Flow
- BUYER publishes task, SELLER applies (not the other way around)
- `[KK Request]` prefix for buyer bounty tasks
- Escrow: 87% seller / 13% fee
""", encoding="utf-8")


def generate_dashboard_files():
    """Create Dataview dashboard files."""

    (VAULT / "dashboards" / "agent-status.md").write_text("""---
title: Agent Status Dashboard
tags:
  - dashboard
---

## All Agents

```dataview
TABLE status, role, last_heartbeat, daily_revenue_usdc, tasks_completed, errors_last_24h
FROM "agents"
SORT status ASC, agent_id ASC
```

## Active Agents

```dataview
TABLE role, current_task, daily_revenue_usdc, irc_messages_sent
FROM "agents"
WHERE status = "active"
SORT last_heartbeat DESC
```

## Pending Deployment

```dataview
LIST
FROM "agents"
WHERE status = "pending"
SORT agent_id ASC
```
""", encoding="utf-8")

    (VAULT / "dashboards" / "supply-chain-flow.md").write_text("""---
title: Supply Chain Flow
tags:
  - dashboard
  - supply-chain
---

## Sellers (Data Producers)

```dataview
TABLE daily_revenue_usdc AS "Revenue", tasks_completed AS "Tasks"
FROM "agents"
WHERE role = "seller" OR role = "buyer-seller"
SORT daily_revenue_usdc DESC
```

## Buyers (Consumers)

```dataview
TABLE daily_spent_usdc AS "Spent", tasks_completed AS "Purchases"
FROM "agents"
WHERE role = "community-buyer" OR role = "buyer-seller"
SORT daily_spent_usdc DESC
```

## See Also
- [[supply-chain]] - Chain architecture
- [[ledger]] - Transaction history
""", encoding="utf-8")

    (VAULT / "dashboards" / "transactions.md").write_text("""---
title: Transaction Dashboard
tags:
  - dashboard
  - transactions
---

## Transaction Log
See [[ledger]] for full transaction history.

## Revenue by Agent

```dataview
TABLE daily_revenue_usdc AS "Revenue", daily_spent_usdc AS "Spent", (daily_revenue_usdc - daily_spent_usdc) AS "Net"
FROM "agents"
WHERE daily_revenue_usdc > 0 OR daily_spent_usdc > 0
SORT daily_revenue_usdc DESC
```
""", encoding="utf-8")

    (VAULT / "dashboards" / "irc-activity.md").write_text("""---
title: IRC Activity
tags:
  - dashboard
  - irc
---

## IRC Messages by Agent

```dataview
TABLE irc_messages_sent AS "Messages", status, last_heartbeat
FROM "agents"
WHERE irc_messages_sent > 0
SORT irc_messages_sent DESC
```

## See Also
- [[meshrelay-irc]] - IRC server details
- [[config]] - Channel configuration
""", encoding="utf-8")


def generate_project_files():
    """Create cross-project link files."""

    (VAULT / "projects" / "karmacadabra.md").write_text("""---
title: KarmaCadabra
tags:
  - project
  - karmacadabra
---

## KarmaCadabra

Trustless agent economy with AI agents buying/selling data using blockchain payments.

- **Repo**: Z:\\ultravioleta\\dao\\karmakadabra
- **Agents**: 24 (6 system + 18 community)
- **Chain**: Base mainnet
- **Token**: USDC via EIP-3009 gasless

## Components
- [[erc8004-registry]] - Agent identity
- [[execution-market]] - Task marketplace
- [[x402-payment]] - Payment protocol
- [[meshrelay-irc]] - Agent communication
- [[supply-chain]] - Data pipeline

## Key Links
- [[agent-status]] - Live dashboard
- [[ledger]] - Transaction history
- [[config]] - Shared configuration
""", encoding="utf-8")

    (VAULT / "projects" / "abracadabra.md").write_text("""---
title: AbraCadabra
tags:
  - project
  - abracadabra
---

## AbraCadabra

AI-powered podcast transcription and knowledge extraction.

- **Repo**: Z:\\ultravioleta\\ai\\abracadabra
- **Integration**: Provides transcription data to [[kk-karma-hello]]
- **Format**: SQLite + Cognee knowledge graphs

## Data Flow
AbraCadabra transcripts -> [[kk-karma-hello]] (aggregation) -> Supply chain

## Related
- [[karmacadabra]] - Parent economy
- [[supply-chain]] - How transcripts feed the chain
""", encoding="utf-8")

    (VAULT / "projects" / "karmagelou.md").write_text("""---
title: KarmaGelou
tags:
  - project
  - karmagelou
---

## KarmaGelou

On-chain reputation and governance layer for Ultravioleta DAO.

- **Repo**: Z:\\ultravioleta\\dao\\karmagelou
- **Integration**: Provides reputation scores via [[erc8004-registry]]
- **Chain**: Base mainnet

## Data Flow
Agent actions -> [[erc8004-registry]] reputation -> KarmaGelou dashboard

## Related
- [[karmacadabra]] - Agent economy
- [[erc8004-registry]] - Identity contracts
""", encoding="utf-8")

    (VAULT / "projects" / "execution-market.md").write_text("""---
title: Execution Market
tags:
  - project
  - execution-market
---

## Execution Market

Decentralized task marketplace where agents post bounties and fulfill work.

- **API**: https://api.execution.market
- **Repo**: Z:\\ultravioleta\\dao\\execution-market
- **Integration**: All KK agents buy/sell via EM escrow

## Related
- [[karmacadabra]] - Primary customer
- [[x402-payment]] - Payment execution
- [[erc8004-registry]] - Agent verification
""", encoding="utf-8")


def main():
    with open(IDENTITIES, "r") as f:
        data = json.load(f)

    agents = data["agents"]
    print(f"Generating vault for {len(agents)} agents...")

    # Generate state.md for each agent
    for agent in agents:
        name = agent["name"]
        agent_dir = VAULT / "agents" / name
        agent_dir.mkdir(parents=True, exist_ok=True)

        state_path = agent_dir / "state.md"
        state_path.write_text(generate_state_md(agent), encoding="utf-8")
        print(f"  {name}/state.md")

        # Create empty memory.md
        memory_path = agent_dir / "memory.md"
        memory_path.write_text(f"""---
agent_id: {name}
title: Memory
tags:
  - memory
  - {name.replace("kk-", "")}
---

## Long-term Memory

Notes and learnings accumulated over time.
""", encoding="utf-8")

    # Generate shared files
    print("\nGenerating shared files...")
    generate_shared_files()
    print("  shared/config.md, supply-chain.md, announcements.md, ledger.md, tasks.md")

    # Generate knowledge base
    print("\nGenerating knowledge base...")
    generate_knowledge_files()
    print("  knowledge/contracts/, knowledge/apis/, knowledge/protocols/, lessons-learned.md")

    # Generate dashboards
    print("\nGenerating dashboards...")
    generate_dashboard_files()
    print("  dashboards/agent-status.md, supply-chain-flow.md, transactions.md, irc-activity.md")

    # Generate project files
    print("\nGenerating project files...")
    generate_project_files()
    print("  projects/karmacadabra.md, abracadabra.md, karmagelou.md, execution-market.md")

    # Create .gitattributes
    gitattributes = VAULT / ".gitattributes"
    gitattributes.write_text("""# Append-only merge for log files (prevents conflicts)
agents/*/log-*.md merge=union
shared/announcements.md merge=union
shared/ledger.md merge=union
""", encoding="utf-8")
    print("\n.gitattributes created")

    total_files = sum(1 for _ in VAULT.rglob("*.md"))
    print(f"\nVault generated: {total_files} markdown files")


if __name__ == "__main__":
    main()
