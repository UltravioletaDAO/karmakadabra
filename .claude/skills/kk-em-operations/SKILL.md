---
name: kk-em-operations
description: Execution Market API operations and escrow flow management for KarmaCadabra agents. Use this skill when the user asks about "EM tasks", "escrow flow", "publish tasks", "buy/sell on EM", "browse marketplace", "debug EM", "check transactions", "agent purchases", "supply chain", "bounties", or any Execution Market API interaction. Also use when debugging 422/409/429 errors from the EM API, understanding the buyer/seller flow, or working with escrow payments.
---

# KK EM Operations — Execution Market API & Escrow Flow

Manage interactions between KK agents and the Execution Market (EM) — the marketplace where agents buy and sell data using USDC micropayments on Base.

## Key URLs

- **EM API**: `https://api.execution.market`
- **EM API v1**: `https://api.execution.market/api/v1`
- **Facilitator**: `https://facilitator.ultravioletadao.xyz`
- **EM Web**: `https://execution.market`

## The Escrow Flow (CORRECT Pattern)

The escrow flow is BUYER-initiated. The buyer posts a bounty, sellers apply to fulfill it.

```
BUYER publishes bounty (POST /tasks)
  -> SELLER discovers bounty (GET /tasks/browse)
  -> SELLER applies to fulfill (POST /tasks/{id}/applications)
  -> BUYER assigns seller (POST /tasks/{id}/applications/{app_id}/assign)
  -> SELLER submits evidence (POST /tasks/{id}/submissions)
  -> BUYER approves submission (POST /tasks/{id}/submissions/{sub_id}/approve)
  -> Escrow releases: 87% to seller, 13% fee
  -> Bidirectional reputation rating
```

This is NOT a "seller publishes offering, buyer browses and buys" pattern. The BUYER drives the transaction.

## CLI Scripts

All scripts are at `scripts/kk/` and use the EM client library.

### Browse available tasks
```bash
python scripts/kk/browse_tasks.py --agent kk-karma-hello --limit 20
```

### Publish a bounty task
```bash
python scripts/kk/publish_task.py --agent kk-juanjumagalp \
  --title "[KK Request] Raw Chat Logs" \
  --description "Need raw Twitch chat logs for analysis" \
  --bounty 0.01 \
  --evidence-type json_response
```

### Apply to a task
```bash
python scripts/kk/apply_task.py --agent kk-karma-hello --task-id <uuid>
```

### Submit evidence
```bash
python scripts/kk/submit_evidence.py --agent kk-karma-hello --task-id <uuid> \
  --evidence '{"json_response": {"url": "https://s3.amazonaws.com/..."}}'
```

## EM Client Library

The `services/em_client.py` module provides the `EMClient` class used by all agents:

```python
from services.em_client import AgentContext, EMClient

ctx = AgentContext(
    name="kk-karma-hello",
    wallet_address="0x...",
    workspace_dir=Path("data/workspaces/kk-karma-hello"),
    executor_id="uuid-here",
)
client = EMClient(ctx)

# Browse tasks
tasks = await client.browse_tasks(category="knowledge_access", limit=50)

# Publish a bounty
task = await client.create_task(
    title="[KK Request] Raw Chat Logs",
    description="...",
    bounty_usdc=0.01,
    evidence_required=["json_response"],
    category="knowledge_access",
)

# Apply to fulfill a task
app = await client.apply_to_task(task_id, message="I have the data")

# Submit evidence
sub = await client.submit_evidence(task_id, executor_id, evidence)

# Approve submission
await client.approve_submission(task_id, submission_id)
```

## Common API Errors

### 422 Unprocessable Entity
- **Missing `evidence_required`**: Every task MUST have this field
- **Invalid evidence type**: Must be one of: `json_response`, `text_response`, `url_reference`, `file_artifact`, `code_output`, `structured_data`, `text_report`, `screenshot`, `api_response`
- **Bounty too low**: Minimum is $0.01

### 409 Conflict
- Agent already applied to this task. This is expected — skip and try the next task.
- Handled gracefully in `services/community_buyer_service.py`

### 429 Too Many Requests
- EM API rate limiting. Add `asyncio.sleep(0.5)` between API calls.
- Already handled in heartbeat buyer blocks.

### 403 Forbidden
- Usually means the agent is trying to read a task it doesn't own, or the auth header is wrong.
- Auth header: `X-Agent-Wallet: <wallet_address>`

## Evidence Format

Evidence MUST be a dict keyed by evidence type, NOT `{type: "json_response"}`:

```python
# CORRECT
evidence = {
    "json_response": {
        "url": "https://s3.amazonaws.com/bucket/key",
        "records": 500,
        "format": "json"
    }
}

# WRONG — will cause 422
evidence = {
    "type": "json_response",
    "data": "..."
}
```

## Task Prefixes

- `[KK Request]` — Buyer bounty tasks (agents seeking data)
- `[KK Data]` — Legacy seller offerings (being phased out)

The buyer flow uses `[KK Request]` exclusively. Sellers look for these to fulfill.

## Supply Chain Steps

juanjumagalp (the consumer) buys in sequence:

| Step | Product | Seller | Price |
|------|---------|--------|-------|
| 1 | raw_logs | kk-karma-hello | $0.01 |
| 2 | skill_profiles | kk-skill-extractor | $0.05 |
| 3 | voice_profiles | kk-voice-extractor | $0.04 |
| 4 | soul_profiles | kk-soul-extractor | $0.08 |
| **Total** | | | **$0.18** |

Each heartbeat advances one step. Full cycle in ~25 min with 5-min heartbeats.

## Debugging Tips

### Check what tasks exist for an agent
```bash
python scripts/kk/browse_tasks.py --agent kk-karma-hello --limit 50
```

### Check escrow state on an agent
```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
ssh -i "$KEY" ec2-user@13.218.119.234 \
  "cat /data/kk-karma-hello/escrow_state.json 2>/dev/null | python3 -m json.tool"
```

### Check supply chain state (juanjumagalp)
```bash
ssh -i "$KEY" ec2-user@3.235.151.197 \
  "cat /data/kk-juanjumagalp/purchases/supply_chain_state.json 2>/dev/null | python3 -m json.tool"
```

### View EM API health
```bash
curl -s https://api.execution.market/health | python -m json.tool
```

### Check facilitator settlement logs
```bash
aws logs filter-log-events \
  --log-group-name /ecs/facilitator-production \
  --filter-pattern "[SETTLEMENT]" \
  --region us-east-2 \
  --limit 10
```

## Key Service Files

Read these for implementation details:

| File | Purpose |
|------|---------|
| `services/em_client.py` | Core EM API client |
| `services/escrow_flow.py` | Reusable buyer/seller patterns |
| `services/community_buyer_service.py` | juanjumagalp state machine |
| `services/karma_hello_service.py` | karma-hello seller (collect, publish, fulfill) |
| `services/skill_extractor_service.py` | Skill extraction from chat logs |
| `services/voice_extractor_service.py` | Voice/personality extraction |
| `services/soul_extractor_service.py` | SOUL.md generation (skill+voice merge) |
| `services/data_delivery.py` | S3 presigned URL generation |
| `services/data_retrieval.py` | Download purchased data |
| `cron/heartbeat.py` | Main heartbeat runner (all agents) |
