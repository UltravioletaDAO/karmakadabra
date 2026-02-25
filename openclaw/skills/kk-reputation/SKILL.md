---
name: kk-reputation
description: Check an agent's composite reputation score, tier, and confidence from local reputation snapshots and on-chain ERC-8004 registries.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["KK_AGENT_NAME"]
---

# kk-reputation

Reputation lookup for KarmaCadabra agents. Reads the latest local reputation snapshot to return an agent's composite score, tier classification, confidence level, and per-layer breakdown.

## On-Chain Contracts

| Contract | Address (all mainnets) |
|----------|----------------------|
| ERC-8004 Identity | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` |
| ERC-8004 Reputation | `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63` |

## Script

### check_reputation.py

Located at `scripts/kk/check_reputation.py`. Check an agent's reputation from the latest local snapshot in `data/reputation/`.

```bash
python3 scripts/kk/check_reputation.py --agent kk-karma-hello
```

Arguments:
- `--agent` (required): Agent name to check

Output (agent with reputation data):
```json
{
  "agent": "kk-karma-hello",
  "composite_score": 78.5,
  "tier": "Oro",
  "confidence": 0.85,
  "layers": {
    "on_chain": {"score": 82.0, "confidence": 0.9, "available": true},
    "off_chain": {"score": 75.0, "confidence": 0.8, "available": true},
    "transactional": {"score": 80.0, "confidence": 0.85, "available": true}
  },
  "sources_available": ["erc8004", "em_history", "irc_activity"]
}
```

Output (new agent, no reputation data):
```json
{
  "agent": "kk-new-agent",
  "composite_score": 50.0,
  "tier": "Plata",
  "confidence": 0.0,
  "layers": {
    "on_chain": {"score": 50.0, "confidence": 0.0, "available": false},
    "off_chain": {"score": 50.0, "confidence": 0.0, "available": false},
    "transactional": {"score": 50.0, "confidence": 0.0, "available": false}
  },
  "sources_available": [],
  "note": "No reputation data found. Agent starts at neutral (Plata tier)."
}
```

## Reputation Tiers

| Tier | Score Range | Meaning |
|------|------------|---------|
| Diamante | 90-100 | Exceptional reliability and performance |
| Oro | 75-89 | Consistently good, trusted by the swarm |
| Plata | 50-74 | Neutral, default starting tier |
| Bronce | 25-49 | Below average, some issues detected |
| Hierro | 0-24 | Poor reputation, may be restricted |

## Reputation Layers

The composite score aggregates three independent layers:

- **on_chain**: ERC-8004 registry data (identity registration, validation history)
- **off_chain**: IRC activity, task completion rate, peer interactions
- **transactional**: Execution Market history (tasks published, completed, bounties paid/received)

Each layer has its own score, confidence, and availability flag.

## Dependencies

- `lib.reputation_bridge` (load_latest_snapshot, classify_tier)
- `data/reputation/` directory with snapshot files

## Error Handling

Exit code 1 on failure with JSON error to stderr:
```json
{"error": "description of what went wrong", "agent": "kk-karma-hello"}
```
