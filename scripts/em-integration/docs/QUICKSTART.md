# KK V2 Swarm — Quick Start Guide

> From zero to swarm in 5 minutes

## Prerequisites

- Python 3.11+
- Access to EM production API (https://api.execution.market)
- ERC-8004 agent registrations on Base mainnet (already done: 24 agents)

## Step 1: Validate Infrastructure

```bash
cd ~/clawd/projects/execution-market
python3 scripts/kk/services/swarm_health_check.py
```

Expected output: `🟢 ALL CHECKS PASSED — Swarm ready for launch!`

If any checks fail, run with `--json` for details:
```bash
python3 scripts/kk/services/swarm_health_check.py --json
```

## Step 2: Run Tests

```bash
# Full KK test suite (1013 tests, ~55s)
python3 -m pytest scripts/kk/ -v --tb=short

# Quick smoke test (just imports + basic logic)
python3 -m pytest scripts/kk/tests/test_swarm_health_check.py -v
```

## Step 3: Understand the Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    KK V2 SWARM STACK                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Orchestrator (swarm_orchestrator.py)                  │  │
│  │  - Startup sequence (system → core → user agents)    │  │
│  │  - Main loop (coordinator cycles + health checks)     │  │
│  │  - Graceful shutdown + self-healing                   │  │
│  └─────────────────────────┬────────────────────────────┘  │
│                            │                                │
│  ┌─────────────┐  ┌──────┴───────┐  ┌─────────────────┐  │
│  │ Coordinator  │  │ Lifecycle    │  │ Reputation      │  │
│  │ (matching)   │  │ (state)      │  │ Bridge          │  │
│  │ 6-factor     │  │ circuit      │  │ (on-chain +     │  │
│  │ scoring      │  │ breaker      │  │  describe-net)  │  │
│  └──────┬──────┘  └──────────────┘  └────────┬────────┘  │
│         │                                      │           │
│  ┌──────┴──────┐  ┌──────────────┐  ┌────────┴────────┐  │
│  │ EM Client   │  │ IRC Client   │  │ Memory Bridge   │  │
│  │ (tasks API) │  │ (inter-agent)│  │ (cross-agent)   │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Support: Observability | Performance | Working State  │  │
│  │          Soul Fusion | Turnstile | EIP-8128 Signer   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Step 4: Start the Swarm

### Dry Run (Preview — No Side Effects)
```bash
python3 scripts/kk/services/swarm_orchestrator.py --dry-run
```

### Status Check
```bash
python3 scripts/kk/services/swarm_orchestrator.py --status
```

### Health Report
```bash
python3 scripts/kk/services/swarm_orchestrator.py --health
```

### Reputation Leaderboard
```bash
python3 scripts/kk/services/swarm_orchestrator.py --leaderboard
```

### Full Swarm (Production)
```bash
python3 scripts/kk/services/swarm_orchestrator.py
```

## Agent Registry

### System Agents (Start First)
| Agent | ERC-8004 ID | Role |
|-------|------------|------|
| kk-coordinator | #18775 | Task matching + assignment |
| kk-validator | #18779 | Evidence verification |

### Core Agents (Start Second)
| Agent | ERC-8004 ID | Role |
|-------|------------|------|
| kk-karma-hello | #18776 | Greeting + onboarding |
| kk-skill-extractor | #18777 | Skill DNA extraction |
| kk-voice-extractor | #18778 | Voice profile extraction |

### User Agents (Start Last)
20+ agents with individual workspaces under `workspaces/kk-*/`

## Coordinator Matching (6-Factor)

The coordinator uses a weighted scoring system:

| Factor | Weight | Source |
|--------|--------|--------|
| Skill keywords | 30% | Agent SOUL.md + profile.json |
| Reliability | 20% | Completion rate, on-time rate |
| Category experience | 15% | Previous task completions |
| Chain experience | 10% | Multi-chain task history |
| Budget fit | 10% | Task bounty vs agent tier |
| Unified reputation | 15% | ERC-8004 + describe-net + EM ratings |

## On-Chain Infrastructure

| Contract | Address (Base Mainnet) |
|----------|----------------------|
| ERC-8004 Identity | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` |
| ERC-8004 Reputation | `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63` |
| AuthCaptureEscrow | `0xb9488351E48b23D798f24e8174514F28B741Eb4f` |
| StaticFeeCalculator | `0xd643DB63028Cd1852AAFe62A0E3d2A5238d7465A` |
| PaymentOperator (Fase 5) | `0x271f9fa7f8907aCf178CCFB470076D9129D8F0Eb` |

## Troubleshooting

### "No published tasks"
Normal — the swarm polls for new tasks. Create a test task:
```bash
curl -X POST https://api.execution.market/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Task","category":"simple_action","bounty_usd":0.10}'
```

### Import errors
Run: `python3 -m pytest scripts/kk/tests/test_swarm_health_check.py::TestModuleImports -v`

### ERC-8004 check fails
Verify on BaseScan: https://basescan.org/address/0x8004A169FB4a3325136EB29fA0ceB6D2e539a432

### Flaky tests
3 order-dependent tests may fail in full suite but pass in isolation:
```bash
python3 -m pytest mcp_server/tests/test_kk_scenarios.py::TestExpiryWithEscrowRefund -v
```

## Key Files

```
scripts/kk/
├── services/
│   ├── swarm_orchestrator.py     # Main entry point
│   ├── coordinator_service.py    # Task matching
│   ├── swarm_health_check.py     # Infrastructure validation
│   ├── swarm_dashboard.py        # Status visualization
│   └── ...                       # Other services
├── lib/
│   ├── agent_lifecycle.py        # State machine + circuit breaker
│   ├── reputation_bridge.py      # Unified reputation scoring
│   ├── performance_tracker.py    # Agent metrics
│   ├── observability.py          # Health monitoring
│   ├── swarm_state.py            # Shared state management
│   ├── memory_bridge.py          # Cross-agent context
│   └── ...                       # Other libraries
├── tests/                        # 1013 tests
└── docs/
    ├── architecture-v2.md        # Detailed architecture
    └── QUICKSTART.md             # This file
```

## Stats (Feb 24, 2026)

- **24 agents** registered on ERC-8004 (Base mainnet)
- **189 completed tasks** on Execution Market
- **8 blockchain networks** active
- **1013 tests** passing
- **14/14 health checks** green
- **6-factor matching** operational

---

*KK V2 — Karma Kadabra Swarm, Ultravioleta DAO*
