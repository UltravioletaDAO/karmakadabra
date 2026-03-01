---
name: kk-swarm-monitor
description: Monitor and diagnose KarmaCadabra agent swarm health. Use this skill when the user asks to "check agents", "monitor swarm", "check logs", "are agents running", "agent health", "check heartbeats", "view agent status", "what are agents doing", "check IRC", "check balances", or any question about agent operational status. Also use proactively after deployments to verify agents are healthy, or when debugging agent behavior issues.
---

# KK Swarm Monitor — Agent Health & Diagnostics

Monitor 7 KK agents running on EC2 (OpenClaw architecture). Each agent runs in a Docker container with heartbeat loop, IRC integration, and vault sync.

## Quick Commands

### Full swarm status (local, no SSH needed)
```bash
cd Z:\ultravioleta\dao\karmakadabra
python scripts/kk/swarm_ops.py status
```

### System health (EM API, facilitator, Base RPC)
```bash
python scripts/kk/swarm_ops.py health
```

### Wallet balances (Base mainnet USDC + ETH)
```bash
python scripts/kk/swarm_ops.py balances
```

### IRC connectivity check
```bash
python scripts/kk/swarm_ops.py irc-check
```

### Pre-deploy checklist
```bash
python scripts/kk/swarm_ops.py deploy-checklist
```

### Generate markdown report
```bash
python scripts/kk/swarm_ops.py report -o docs/reports/swarm_status.md
```

## SSH Log Checks (Live Agent Status)

SSH key: `~/.ssh/kk-openclaw.pem`

### Check a single agent's recent logs
```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
ssh -o StrictHostKeyChecking=no -i "$KEY" ec2-user@13.218.119.234 \
  "docker logs kk-karma-hello --tail 50 2>&1"
```

### Check all 7 agents in parallel
```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
declare -A AGENTS=(
  [kk-coordinator]="44.211.242.65"
  [kk-karma-hello]="13.218.119.234"
  [kk-skill-extractor]="100.53.60.94"
  [kk-voice-extractor]="100.52.188.43"
  [kk-validator]="44.203.23.11"
  [kk-soul-extractor]="3.234.249.61"
  [kk-juanjumagalp]="3.235.151.197"
)

for AGENT in "${!AGENTS[@]}"; do
  IP="${AGENTS[$AGENT]}"
  echo "=== $AGENT ($IP) ==="
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$KEY" ec2-user@$IP \
    "docker logs $AGENT --tail 15 2>&1 | tail -10" 2>/dev/null
  echo ""
done
```

### Check container status on all EC2s
```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
for IP in 44.211.242.65 13.218.119.234 100.53.60.94 100.52.188.43 44.203.23.11 3.234.249.61 3.235.151.197; do
  echo -n "$IP: "
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$KEY" ec2-user@$IP \
    "docker ps --format '{{.Names}} | {{.Status}} | {{.Image}}'" 2>/dev/null || echo "UNREACHABLE"
done
```

## What to Look For

### Healthy Agent Signs
- `Heartbeat #N` with incrementing N — heartbeat loop active (every 5 min)
- `IRC daemon started` or `IRC: sent N messages` — IRC integration working
- `vault swarm summary` — vault sync active (coordinator)
- `Published X tasks` / `Applied to task` / `Assigned` — EM operations working
- No `ERROR`, `Traceback`, or `Killed` lines

### Red Flags
- `OOM` or `Killed` — Out of memory, t3.small has 2GB
- `Traceback` with `ConnectionError` — network issue or EM API down
- No recent `Heartbeat` — agent stuck or container stopped
- `429 Too Many Requests` — EM API rate limiting (already handled with 0.5s delay)
- `422 Unprocessable Entity` — bad API request format (check evidence format)
- `409 Conflict` — already applied to task (expected, handled gracefully)

### Agent Role Summary (for context when reading logs)

| Agent | Role | What to look for in logs |
|-------|------|--------------------------|
| kk-coordinator | Orchestrator | vault swarm summary, agent state reads, IRC health broadcasts |
| kk-karma-hello | Seller (raw logs) | collect_all_logs, Published tasks, fulfill_purchases, S3 URLs |
| kk-skill-extractor | Buyer+Seller | browse_and_apply, skills extracted, skill profiles published |
| kk-voice-extractor | Buyer+Seller | browse_and_apply, voices extracted, voice profiles published |
| kk-soul-extractor | Buyer+Seller | browse_and_apply, SOUL.md generated, soul bundles published |
| kk-validator | QA | validation tasks, VERIFIED results |
| kk-juanjumagalp | Buyer (consumer) | supply chain step=, bought, retrieved, cycle# |

## Agent IP Reference

Read from: `references/agent_ips.md`

## Checking IRC Activity

### From local machine (uses MeshRelay directly)
```bash
python scripts/kk/swarm_ops.py irc-check
```

### From an agent's perspective
```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
ssh -i "$KEY" ec2-user@44.211.242.65 \
  "docker exec kk-coordinator cat /app/data/irc_state.json 2>/dev/null || echo 'no IRC state file'"
```

## Checking Vault State

### Read an agent's vault state file
```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
ssh -i "$KEY" ec2-user@13.218.119.234 \
  "docker exec kk-karma-hello cat /app/vault/agents/kk-karma-hello/state.md 2>/dev/null || echo 'no vault state'"
```

### Check vault git log (sync history)
```bash
ssh -i "$KEY" ec2-user@13.218.119.234 \
  "docker exec kk-karma-hello bash -c 'cd /app/vault && git log --oneline -5' 2>/dev/null || echo 'no vault repo'"
```

## Checking Data Downloads (Buyers)

```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
# Check what data skill-extractor has downloaded
ssh -i "$KEY" ec2-user@100.53.60.94 \
  "ls -la /data/kk-skill-extractor/purchases/ 2>/dev/null && ls -la /data/kk-skill-extractor/skills/ 2>/dev/null || echo 'no data yet'"
```

## Facilitator Logs (AWS CloudWatch)

The x402-rs facilitator runs in us-east-2:

```bash
aws logs filter-log-events \
  --log-group-name /ecs/facilitator-production \
  --filter-pattern "[SETTLEMENT]" \
  --region us-east-2 \
  --limit 10
```

## Generating a Full Report

```bash
python scripts/kk/swarm_ops.py report -o /tmp/kk_status.md
```

This generates a markdown report with:
- All 24 agents listed with addresses and ERC-8004 IDs
- Wallet balances (Base USDC + ETH)
- Infrastructure health (EM API, facilitator, Base RPC)
