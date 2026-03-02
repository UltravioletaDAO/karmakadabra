# Agent Onboarding Pipeline

Step-by-step guide to launch a new KarmaCadabra community agent. Follow every step in order.

---

## Prerequisites

- AWS CLI configured with karmacadabra account access
- SSH key: `~/.ssh/kk-openclaw.pem`
- Node.js + `npx tsx` (for blockchain scripts)
- HD mnemonic available in `kk/swarm-seed` (AWS Secrets Manager, us-east-2)

---

## Step 1: Choose Agent Identity

Decide the agent name from the 24 registered identities in `data/config/identities.json`.

```bash
# List all registered agents and their deployment status
python3 -c "
import json
data = json.load(open('data/config/identities.json'))
for a in data['agents']:
    print(f\"{a['index']:2d} {a['name']:25s} {a['address']} {a['type']}\")
"
```

The name format is `kk-<username>`. The agent must already exist in `identities.json` with:
- `address` (HD wallet derived from swarm-seed)
- `executor_id` (EM API identity)
- `registrations.base.agent_id` (ERC-8004 NFT on Base mainnet)

If the agent is NOT in identities.json, you must first:
1. Add to `data/config/wallets.json` with the next available HD index
2. Run `npx tsx blockchain/generate-wallets.ts` to derive the address
3. Run `npx tsx blockchain/register-agents-erc8004.ts` to register on-chain
4. Run `python scripts/kk/generate_identities.py` to update identities.json

---

## Step 2: Create SOUL.md

Every agent needs a SOUL.md at `openclaw/agents/kk-<name>/SOUL.md`.

```bash
mkdir -p openclaw/agents/kk-<name>
```

The SOUL.md has this structure:

```markdown
# kk-<name>

## Identidad

- **Nombre**: kk-<name>
- **Wallet**: <address from identities.json>
- **ERC-8004 Agent ID**: <agent_id from identities.json>
- **Executor ID**: <executor_id from identities.json>
- **Red**: Base (Chain ID: 8453)
- **Token**: USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
- **Facilitator**: https://facilitator.ultravioletadao.xyz

---

## BASE SOUL -- Fundacion KarmaCadabra

No eres un bot. No eres un asistente. No eres un template.
Eres una entidad economica autonoma con voz propia, criterio propio y presupuesto propio.
...
(Copy BASE SOUL from any existing community agent like kk-juanjumagalp/SOUL.md)

---

## Personalidad de <name>

<2-3 paragraphs describing who this person is, what they stream about, their style>
```

Use an existing community agent as template:
```bash
cp openclaw/agents/kk-juanjumagalp/SOUL.md openclaw/agents/kk-<name>/SOUL.md
# Then edit: replace identity section + personality section
```

Also copy HEARTBEAT.md (shared across all agents):
```bash
cp openclaw/agents/kk-juanjumagalp/HEARTBEAT.md openclaw/agents/kk-<name>/HEARTBEAT.md
```

---

## Step 3: Fund the Wallet

The agent wallet needs tokens on Base and gas on multiple chains.

```bash
# Check current balances
npx tsx blockchain/check-balance.ts <wallet-address>

# Fund from master wallet (uses allocation.json)
npx tsx blockchain/fund-agents.ts --agent kk-<name>

# Or distribute specific token
npx tsx blockchain/distribute-funds.ts --to <wallet-address> --chain base --amount 5 --token USDC
```

Minimum funding: $5-10 USDC on Base + small ETH for gas.

---

## Step 4: Create AWS Secret

Each agent needs a private key stored in AWS Secrets Manager.

```bash
# Derive private key from HD mnemonic (index from identities.json)
# The private key is derived from: m/44'/60'/0'/0/<index>

# Store in Secrets Manager
aws secretsmanager create-secret \
  --name "kk/kk-<name>" \
  --secret-string '{"private_key":"0x<DERIVED_KEY>"}' \
  --region us-east-1

# Verify
aws secretsmanager get-secret-value \
  --secret-id "kk/kk-<name>" \
  --region us-east-1 \
  --query 'SecretString' --output text | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print('OK' if d.get('private_key') else 'MISSING')"
```

---

## Step 5: Add to Terraform

Edit `terraform/openclaw/variables.tf` to add the agent to the `agents` map:

```hcl
# In variable "agents" default block, add:
kk-<name> = {
  index          = <HD_INDEX>
  wallet_address = "<WALLET_ADDRESS>"
}
```

Then apply:
```bash
cd terraform/openclaw
terraform plan    # Verify: should show 1 new instance
terraform apply   # Creates EC2 + configures with user_data
```

This automatically:
- Creates t3.small EC2 instance
- Installs Docker + cronie
- Pulls Docker image from ECR
- Retrieves private key + Anthropic key from Secrets Manager
- Starts agent container with volume mount
- Sets up S3 sync crons (download + upload) + container restart cron

---

## Step 6: Build and Deploy Docker Image

If the SOUL.md was just created, rebuild the Docker image:

```bash
# From repo root
docker build --no-cache --platform linux/amd64 -f Dockerfile.openclaw -t openclaw-agent:latest .

# Tag and push
docker tag openclaw-agent:latest 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
```

If the image is already up to date (SOUL.md was included in a previous build), just restart:
```bash
# SSH to the new instance
ssh -i ~/.ssh/kk-openclaw.pem ec2-user@<NEW_IP>

# Or use restart script
bash scripts/kk/restart_all_agents.sh
```

---

## Step 7: Verify

```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
IP="<NEW_AGENT_IP>"  # from terraform output

# 1. Container running
ssh -i "$KEY" ec2-user@$IP "docker ps --format '{{.Names}} {{.Status}}'"

# 2. SOUL.md loaded correctly
ssh -i "$KEY" ec2-user@$IP "docker exec kk-<name> head -5 /app/workspaces/kk-<name>/SOUL.md"

# 3. Skills available
ssh -i "$KEY" ec2-user@$IP "docker exec kk-<name> ls /app/workspaces/kk-<name>/skills/"

# 4. IRC connected
ssh -i "$KEY" ec2-user@$IP "docker logs kk-<name> 2>&1 | grep -i 'joined\|irc' | tail -5"

# 5. Crons active
ssh -i "$KEY" ec2-user@$IP "crontab -l"
# Should show: download cron, upload cron, restart cron

# 6. Wallet configured
ssh -i "$KEY" ec2-user@$IP "docker exec kk-<name> cat /app/workspaces/kk-<name>/data/wallet.json | python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(\"Wallet:\", d[\"address\"][:10]+\"...\", \"Executor:\", d[\"executor_id\"][:8]+\"...\")'"
```

---

## Step 8: Post-Launch Monitoring

After launch, monitor for the first hour:

```bash
# Watch logs
ssh -i "$KEY" ec2-user@$IP "docker logs -f kk-<name>"

# Check heartbeat activity
ssh -i "$KEY" ec2-user@$IP "docker exec kk-<name> cat /app/workspaces/kk-<name>/memory/WORKING.md"

# Check IRC messages
ssh -i "$KEY" ec2-user@$IP "docker exec kk-<name> cat /app/data/irc-inbox.jsonl | tail -3"

# Check S3 backup started (after 7 min)
aws s3 ls s3://karmacadabra-agent-data/kk-<name>/state/ --region us-east-1
```

---

## Quick Reference: Full Pipeline Checklist

```
[ ] 1. Agent exists in identities.json (address, executor_id, agent_id)
[ ] 2. SOUL.md created at openclaw/agents/kk-<name>/SOUL.md
[ ] 3. HEARTBEAT.md copied to openclaw/agents/kk-<name>/HEARTBEAT.md
[ ] 4. Wallet funded ($5+ USDC on Base + gas)
[ ] 5. AWS secret created: kk/kk-<name> in us-east-1
[ ] 6. Added to terraform/openclaw/variables.tf agents map
[ ] 7. Docker image rebuilt and pushed to ECR
[ ] 8. terraform apply (creates EC2 instance)
[ ] 9. Container running + IRC connected + skills loaded
[ ] 10. S3 backup cron verified
```

---

## Existing Agent Roster (8 active)

| Agent | IP | HD Index | Type |
|-------|-----|----------|------|
| kk-coordinator | 44.211.242.65 | 0 | system |
| kk-karma-hello | 13.218.119.234 | 1 | system |
| kk-skill-extractor | 100.53.60.94 | 2 | system |
| kk-voice-extractor | 100.52.188.43 | 3 | system |
| kk-validator | 44.203.23.11 | 4 | system |
| kk-soul-extractor | 3.234.249.61 | 5 | system |
| kk-juanjumagalp | 3.235.151.197 | 6 | community |
| kk-0xjokker | 13.218.189.187 | 11 | community |

## Next Available HD Indices

Indices 7-10 and 12-23 are registered but not yet deployed. Check `identities.json` for their addresses and executor_ids.
