# KK V2 Swarm Architecture — Complete System Map

> **Date:** February 23, 2026  
> **Status:** Implementation Complete, Pending Deployment  
> **Tests:** 963 passing (0 failures)

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    KK V2 SWARM ORCHESTRATOR                             │
│                    services/swarm_orchestrator.py                        │
│                                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ STARTUP     │  │ MAIN LOOP    │  │ SHUTDOWN     │                  │
│  │ plan_startup│→ │ coord_cycle  │→ │ drain_tasks  │                  │
│  │ order       │  │ health_check │  │ save_state   │                  │
│  └─────────────┘  └──────────────┘  └──────────────┘                  │
└──────┬──────────────────┬────────────────────┬──────────────────────────┘
       │                  │                    │
       ▼                  ▼                    ▼
┌──────────────┐  ┌───────────────┐  ┌─────────────────┐
│ LIFECYCLE    │  │ COORDINATOR   │  │ OBSERVABILITY   │
│ agent_       │  │ coordinator_  │  │ observability.py│
│ lifecycle.py │  │ service.py    │  │                 │
│              │  │               │  │ • Health scores │
│ • State FSM  │  │ • 6-factor    │  │ • Swarm metrics │
│ • Circuit    │  │   matching    │  │ • Task funnel   │
│   breaker    │  │ • Reputation  │  │ • Trend detect  │
│ • Heartbeat  │  │   boost       │  │ • Reports       │
│ • Recovery   │  │ • Assignment  │  │                 │
│ • Balance    │  │ • Notifs      │  │                 │
└──────┬───────┘  └───────┬───────┘  └────────┬────────┘
       │                  │                    │
       │         ┌────────┴──────────┐         │
       │         ▼                   ▼         │
       │  ┌──────────────┐  ┌──────────────┐   │
       │  │ PERFORMANCE  │  │ REPUTATION   │   │
       │  │ performance_ │  │ reputation_  │   │
       │  │ tracker.py   │  │ bridge.py    │◄──┘
       │  │              │  │              │
       │  │ • Completion │  │ • On-chain   │
       │  │ • Categories │  │   (seals)    │
       │  │ • Chains     │  │ • Off-chain  │
       │  │ • Ratings    │  │   (perf)     │
       │  │ • Budget fit │  │ • Transaction│
       │  │              │  │   (EM API)   │
       │  └──────┬───────┘  │ • Unified    │
       │         │          │   composite  │
       │         └──────────┤ • Tiers      │
       │                    │ • Leaderboard│
       │                    └──────────────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│              AGENT INFRASTRUCTURE                 │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ MEMORY   │  │ SWARM    │  │ RELATIONSHIP │   │
│  │ memory_  │  │ swarm_   │  │ relationship_│   │
│  │ bridge.py│  │ state.py │  │ tracker.py   │   │
│  │          │  │          │  │              │   │
│  │ • Local  │  │ • Agent  │  │ • Trust      │   │
│  │   first  │  │   states │  │   scoring    │   │
│  │ • Acontext│  │ • Claims │  │ • Inter-agent│   │
│  │   bridge │  │ • Notifs │  │   relations  │   │
│  │ • Token  │  │ • Summary│  │              │   │
│  │   aware  │  │          │  │              │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ WORKING  │  │ SOUL     │  │ IRC CLIENT   │   │
│  │ working_ │  │ soul_    │  │ irc_client.py│   │
│  │ state.py │  │ fusion.py│  │              │   │
│  │          │  │          │  │ • KK protocol│   │
│  │ • Parse  │  │ • Agent  │  │ • Swarm comms│   │
│  │ • Update │  │ personal │  │ • Nick mgmt  │   │
│  │ • Status │  │ • SOUL.md│  │              │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
└──────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│              EXTERNAL SERVICES                    │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ EM API   │  │ IRC      │  │ BLOCKCHAIN   │   │
│  │ em_client│  │ irc_     │  │              │   │
│  │ .py      │  │ service  │  │ • ERC-8004   │   │
│  │          │  │ .py      │  │ • ERC-8128   │   │
│  │ • Browse │  │          │  │ • Seals      │   │
│  │ • Submit │  │ • Connect│  │ • USDC       │   │
│  │ • Auth   │  │ • Listen │  │ • 8 chains   │   │
│  │ • Rate   │  │ • Route  │  │              │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
└──────────────────────────────────────────────────┘
```

## Module Inventory

### Lib Modules (Pure Functions, Testable)

| Module | LOC | Tests | Purpose |
|--------|-----|-------|---------|
| `reputation_bridge.py` | 705 | 78 | Unified 3-layer reputation scoring |
| `agent_lifecycle.py` | 694 | 84 | State machine, circuit breaker, recovery |
| `observability.py` | 537 | 57 | Health scores, metrics, trend detection |
| `memory_bridge.py` | 488 | 63 | Local-first + Acontext memory |
| `performance_tracker.py` | ~400 | 45 | 5-factor task matching data |
| `soul_fusion.py` | ~300 | 25+ | Agent personality system |
| `working_state.py` | ~250 | 25 | WORKING.md parse/write |
| `swarm_state.py` | ~200 | — | Supabase state management |
| `irc_client.py` | ~350 | 70 | IRC protocol + KK extensions |
| `eip8128_signer.py` | ~250 | 68 | Wallet-based HTTP auth |
| `acontext_client.py` | ~200 | 42 | Acontext API wrapper |
| `turnstile_client.py` | ~150 | 25+ | Cloudflare Turnstile bypass |
| `memory.py` | ~200 | 22 | MEMORY.md management |

### Service Modules (Async, Side-Effects)

| Module | Purpose |
|--------|---------|
| `coordinator_service.py` | Task matching + assignment (6-factor + reputation) |
| `swarm_orchestrator.py` | Top-level swarm runner |
| `karma_hello_service.py` | Automated task creation |
| `skill_extractor_service.py` | Agent skill discovery |
| `soul_extractor_service.py` | Personality generation |
| `voice_extractor_service.py` | Voice profile extraction |
| `abracadabra_service.py` | Cross-chain bridge integration |
| `irc_service.py` | IRC swarm communication |
| `relationship_tracker.py` | Inter-agent trust network |
| `standup_service.py` | Daily standup automation |

## Matching Pipeline (6-Factor + Reputation)

```
Task arrives from EM API
       │
       ▼
┌─────────────────────────────────────────┐
│ 1. SKILL MATCH (30%)                    │
│    Tokenized skill keywords vs task text │
│    Natural language + partial matching   │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 2. RELIABILITY (20%)                    │
│    60% completion rate + 40% ratings    │
│    Neutral 0.5 for new agents           │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 3. CATEGORY EXPERIENCE (15%)            │
│    Track record in this task category   │
│    simple_action, knowledge_access, etc │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 4. CHAIN EXPERIENCE (10%)              │
│    Has agent worked on this blockchain? │
│    Log-scale: 1 task=0.3, 10+=1.0      │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 5. BUDGET FIT (10%)                    │
│    Is bounty in agent's sweet spot?     │
│    Ratio of bounty to avg earned        │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 6. REPUTATION BOOST (15%)              │
│    Unified score across:                │
│    • On-chain seals (describe-net)      │
│    • Off-chain performance history      │
│    • EM API transactional ratings       │
│    Confidence-dampened for fairness     │
└─────────────────────────────────────────┘
       │
       ▼
  Ranked list of agents → Top agent assigned
```

## Agent State Machine

```
                    ┌─────────┐
              ┌────►│ OFFLINE │◄────────────────┐
              │     └────┬────┘                 │
              │          │ startup/manual_start  │ manual_stop
              │          ▼                       │
              │     ┌─────────┐                 │
              │     │STARTING │                 │
              │     └────┬────┘                 │
              │          │ startup (complete)    │
              │          ▼                       │
              │     ┌─────────┐  manual_stop   ┌┴────────┐
              │     │  IDLE   │───────────────►│STOPPING │
              │     └────┬────┘                └─────────┘
              │          │                          ▲
              │          │ task_assigned             │
              │          ▼                          │
              │     ┌─────────┐  manual_stop   ┌────┴────┐
              │     │WORKING  │───────────────►│DRAINING │
              │     └────┬────┘                └─────────┘
              │          │                          ▲
              │          │ task_completed/failed     │
              │          │                          │
              │          │   circuit_breaker         │ balance_low
              │          │   ┌──────────┐           │
              │          └──►│ COOLDOWN │           │
              │              └────┬─────┘           │
              │                   │ cooldown_expired │
              │                   └──►(back to IDLE) │
              │                                      │
              │     fatal_error / heartbeat_timeout   │
              │          ┌─────────┐                 │
              └──────────│  ERROR  │─────────────────┘
                recovery │         │
                         └─────────┘
```

## Reputation Layers

```
┌──────────────────────────────────────────────────────────────┐
│                 UNIFIED REPUTATION (0-100)                    │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │   ON-CHAIN     │  │   OFF-CHAIN    │  │  TRANSACTIONAL │ │
│  │   (30% base)   │  │   (40% base)   │  │   (30% base)  │ │
│  │                │  │                │  │                │ │
│  │ • SealRegistry │  │ • Completion   │  │ • EM ratings   │ │
│  │ • 13 seal types│  │   rate         │  │ • Bidirectional│ │
│  │ • 4 quadrants  │  │ • Categories   │  │ • Fresh data   │ │
│  │ • Time-weighted│  │ • Chain exp    │  │                │ │
│  │ • ERC-8004     │  │ • Budget fit   │  │                │ │
│  │                │  │ • Rating avg   │  │                │ │
│  │ Confidence:    │  │ Confidence:    │  │ Confidence:    │ │
│  │ log(seals)     │  │ log(tasks)     │  │ log(ratings)   │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
│                                                              │
│  Weights adjusted by confidence:                             │
│  high-confidence sources get proportionally more influence   │
│                                                              │
│  Tiers: 💎 Diamante (81-100) │ 🥇 Oro (61-80) │             │
│         🥈 Plata (31-60) │ 🥉 Bronce (0-30)                 │
└──────────────────────────────────────────────────────────────┘
```

## Deployment Blockers (as of Feb 23, 2026)

| # | Blocker | Impact | Owner |
|---|---------|--------|-------|
| 1 | **$3 swarm funding** | 24 agents need USDC + ETH for gas | Saúl |
| 2 | **ws:// gateway fix** | Sub-agent spawning blocked since Feb 19 | Saúl/OpenClaw |
| 3 | **feat/karmacadabra-swarm merge** | 538 files, 0 conflicts, ready | Clawd |
| 4 | **describe-net GitHub repo** | 98 tests + 5 commits local | Saúl |

## Test Coverage

```
Total: 963 tests, 0 failures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
reputation_bridge      78 tests  ✅
agent_lifecycle        84 tests  ✅
observability          57 tests  ✅
memory_bridge          63 tests  ✅
performance_tracker    45 tests  ✅
eip8128_signer         68 tests  ✅ (crypto roundtrips)
irc_client             70 tests  ✅
acontext_client        42 tests  ✅
em_client              33 tests  ✅
balance_monitor        32 tests  ✅
health_check           18 tests  ✅
coordinator_enhanced   27 tests  ✅
soul_fusion            25+ tests ✅
working_state          25 tests  ✅
memory                 22 tests  ✅
relationship_tracker   18 tests  ✅
integration/multichain 30+ tests ✅
chaos/stress           20+ tests ✅
+ services tests       ~100+     ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
