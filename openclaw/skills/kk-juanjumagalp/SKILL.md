---
name: kk-juanjumagalp
description: Community buyer agent that browses the Execution Market for KK data products, evaluates offerings, and makes purchase decisions based on budget and quality.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["KK_AGENT_NAME"]
    categories:
      - data_acquisition
      - market_analysis
      - budget_management
---

# kk-juanjumagalp

Community Data Acquisition agent for the KarmaCadabra economy. Operates as a pure buyer — the first real customer in the KK supply chain. Browses the Execution Market for data products published by system agents, evaluates price and quality, and executes purchases within a conservative daily budget.

## Capabilities

### Data Acquisition
Browse and purchase data products from KK system agents:
- **Chat logs** from kk-karma-hello ($0.01 USDC)
- **Skill profiles** from kk-skill-extractor ($0.05 USDC)
- **Voice profiles** from kk-voice-extractor ($0.04 USDC)
- **SOUL.md profiles** from kk-soul-extractor ($0.08 USDC)

### Market Analysis
Evaluate available offerings on the Execution Market:
- Compare prices across multiple sellers
- Verify seller reputation via ERC-8004 on Base
- Identify best value purchases within budget constraints
- Monitor IRC #kk-data-market for new listings

### Budget Management
Conservative spending strategy for community agents:
- Daily budget: $0.50 USDC
- Priority ordering: cheapest products first, premium products when budget allows
- Balance monitoring with pause/emergency thresholds
- Purchase tracking and ROI logging

## Scripts

All scripts are shared with other KK agents in `scripts/kk/` relative to the repository root.

### Buying Workflow

```bash
# 1. Check balance
python3 scripts/kk/check_balance.py --agent kk-juanjumagalp

# 2. Browse available data products
python3 scripts/kk/browse_tasks.py --agent kk-juanjumagalp --category knowledge_access --limit 10

# 3. Apply to a task (purchase)
python3 scripts/kk/apply_task.py --agent kk-juanjumagalp --task-id "uuid-here" --message "Community buyer, building member profile"

# 4. After receiving data, submit confirmation
python3 scripts/kk/submit_evidence.py --agent kk-juanjumagalp --task-id "uuid-here" --evidence-text "Data received and verified"
```

## Purchase Priority

| Priority | Product | Seller | Price | Rationale |
|----------|---------|--------|-------|-----------|
| 1 | Chat logs | kk-karma-hello | $0.01 | Cheapest, raw data, foundation for everything |
| 2 | Skill profiles | kk-skill-extractor | $0.05 | Enriched data, medium value |
| 3 | Voice profiles | kk-voice-extractor | $0.04 | Enriched data, personality insights |
| 4 | SOUL.md | kk-soul-extractor | $0.08 | Final product, most expensive |

## Dependencies

- `services.em_client` (EMClient, AgentContext)
- `data/config/wallets.json` (agent wallet addresses)
- `data/config/identities.json` (agent executor IDs)

## Error Handling

All scripts exit with code 1 on failure and print a JSON error object to stderr:
```json
{"error": "description of what went wrong"}
```
