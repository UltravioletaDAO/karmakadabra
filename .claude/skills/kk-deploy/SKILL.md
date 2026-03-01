---
name: kk-deploy
description: Build and deploy KarmaCadabra OpenClaw agents to EC2. Use this skill whenever the user says "deploy", "build and push", "push to ECR", "restart agents", "update agents", "redeploy", "rebuild Docker", or wants to get new code running on the 7 EC2 agent instances. Also use when discussing Docker builds, ECR pushes, or SSH operations to the KK swarm. Proactively use this after committing code changes that affect agent behavior (heartbeat.py, services/, lib/, cron/, openclaw/).
---

# KK Deploy — Build + Push + Deploy to EC2 Swarm

This skill handles the complete deployment pipeline for KarmaCadabra's 7 OpenClaw agents running on EC2.

## Architecture

- **Docker image**: Built from `Dockerfile.openclaw` at repo root
- **ECR repo**: `518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest`
- **Region**: us-east-1
- **SSH key**: `~/.ssh/kk-openclaw.pem`
- **7 agents on EC2 t3.small instances**

## Agent IPs

| Agent | IP |
|-------|-----|
| kk-coordinator | 44.211.242.65 |
| kk-karma-hello | 13.218.119.234 |
| kk-skill-extractor | 100.53.60.94 |
| kk-voice-extractor | 100.52.188.43 |
| kk-validator | 44.203.23.11 |
| kk-soul-extractor | 3.234.249.61 |
| kk-juanjumagalp | 3.235.151.197 |

## Full Deploy Pipeline (3 steps)

### Step 1: Build Docker Image

Always use `--no-cache` when code has changed. The Dockerfile.openclaw copies Python code at build time, so cached layers will serve stale code.

```bash
cd Z:\ultravioleta\dao\karmakadabra

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com

# Build with --no-cache for code changes
docker build --no-cache --platform linux/amd64 -f Dockerfile.openclaw -t openclaw-agent:latest .
```

If only config changes (SOUL.md, vault/), a cached build is fine — drop `--no-cache`.

### Step 2: Tag + Push to ECR

```bash
docker tag openclaw-agent:latest 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
```

### Step 3: Deploy to All 7 Agents

Use the existing script for parallel deploy:

```bash
bash scripts/kk/restart_all_agents.sh
```

Or for a single agent:

```bash
# SCP the update script and run it
KEY="$HOME/.ssh/kk-openclaw.pem"
AGENT="kk-karma-hello"
IP="13.218.119.234"

scp -o StrictHostKeyChecking=no -i "$KEY" scripts/kk/update_agent.sh ec2-user@$IP:/tmp/
ssh -o StrictHostKeyChecking=no -i "$KEY" ec2-user@$IP "bash /tmp/update_agent.sh $AGENT"
```

## Post-Deploy Verification

After deploy, verify agents are healthy:

```bash
# Check one agent's logs
KEY="$HOME/.ssh/kk-openclaw.pem"
ssh -o StrictHostKeyChecking=no -i "$KEY" ec2-user@13.218.119.234 "docker logs kk-karma-hello --tail 30 2>&1"
```

Look for:
- `Heartbeat #N` — confirms heartbeat loop running
- `IRC daemon started` — IRC integration active
- `vault swarm summary` — vault sync working (coordinator only)
- No `OOM`, `Killed`, or crash tracebacks

### Quick Health Check (All 7)

```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
for IP in 44.211.242.65 13.218.119.234 100.53.60.94 100.52.188.43 44.203.23.11 3.234.249.61 3.235.151.197; do
  echo "=== $IP ==="
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$KEY" ec2-user@$IP \
    "docker ps --format '{{.Names}} {{.Status}}' && docker logs \$(docker ps -q --filter 'name=kk-') --tail 5 2>&1 | tail -3" 2>/dev/null
  echo ""
done
```

## Common Issues

### Docker build fails with CRLF errors
Windows line endings in entrypoint.sh. The Dockerfile already has `RUN sed -i 's/\r$//' /app/openclaw/entrypoint.sh` to fix this.

### Agent shows as "unknown" in logs
Missing `KK_AGENT_NAME` env var. The restart script sets this from the agent name. Check the Docker run command.

### ECR push fails with "no basic auth credentials"
Re-run the ECR login command (tokens expire after 12 hours):
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com
```

### Agent crash-loops (OOM on t3.small)
t3.small has 2GB RAM. If the agent uses too much memory (loading large files), it gets killed. Check `docker logs` for "Killed" messages. Fix: process data in streaming fashion, don't load entire files into RAM.

### Old code still running after deploy
Docker cache served stale image. Always use `--no-cache` for code changes. Verify with:
```bash
# Check image creation time
ssh -i "$KEY" ec2-user@$IP "docker inspect --format='{{.Created}}' kk-karma-hello"
```

## Parallel Deploy Pattern

When deploying to all 7 agents from Claude Code, run SSH commands in parallel using `&`:

```bash
KEY="$HOME/.ssh/kk-openclaw.pem"
ECR="518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest"

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
  (
    scp -o StrictHostKeyChecking=no -i "$KEY" scripts/kk/restart_agent_remote.sh ec2-user@$IP:/tmp/restart_agent.sh 2>/dev/null
    ssh -o StrictHostKeyChecking=no -i "$KEY" ec2-user@$IP "bash /tmp/restart_agent.sh $AGENT $ECR us-east-1" 2>&1 | tail -5
    echo "--- $AGENT DONE ---"
  ) &
done
wait
echo "=== ALL DEPLOYED ==="
```

## When to Deploy

- After modifying `cron/heartbeat.py`, `services/*.py`, `lib/*.py` — code runs inside Docker
- After modifying `openclaw/agents/*/SOUL.md` — identity files are baked into image
- After modifying `openclaw/entrypoint.sh` — startup script changes
- After modifying `vault/` — vault structure changes
- NOT needed for: `scripts/kk/*.py` (local scripts), `terraform/` (infra), docs
