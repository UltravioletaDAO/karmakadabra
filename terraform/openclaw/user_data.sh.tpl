#!/bin/bash
set -e

# OpenClaw Agent Bootstrap Script
# Agent: ${agent_name} (wallet index: ${wallet_index})

# Ensure /usr/bin is in PATH (cloud-init uses a minimal PATH where crontab may not be found)
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

# Install Docker + cronie (cron scheduler)
yum update -y
yum install -y docker cronie
systemctl enable docker crond
systemctl start docker crond

# Login to ECR
aws ecr get-login-password --region ${region} \
  | docker login --username AWS --password-stdin ${account_id}.dkr.ecr.${region}.amazonaws.com

# Pull agent image
docker pull ${ecr_repo}:latest

# Get agent private key from Secrets Manager
PRIVATE_KEY=$(aws secretsmanager get-secret-value \
  --secret-id kk/${agent_name} \
  --region ${region} \
  --query SecretString \
  --output text | python3 -c "import sys,json; print(json.load(sys.stdin).get('private_key',''))")

# Get Anthropic API key from Secrets Manager (may be JSON or raw string)
ANTHROPIC_RAW=$(aws secretsmanager get-secret-value \
  --secret-id kk/anthropic \
  --region ${region} \
  --query SecretString \
  --output text)
ANTHROPIC_KEY=$(echo "$ANTHROPIC_RAW" | python3 -c '
import sys, json
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw)
    for k in ("ANTHROPIC_API_KEY", "anthropic_api_key", "api_key", "key"):
        if k in data:
            print(data[k])
            break
    else:
        print(raw)
except (json.JSONDecodeError, TypeError):
    print(raw)
')

# Get LLM keys from Secrets Manager (multi-provider: OpenRouter, OpenAI)
OPENROUTER_KEY=""
OPENAI_KEY=""
LLM_RAW=$(aws secretsmanager get-secret-value \
  --secret-id kk/llm-keys \
  --region ${region} \
  --query SecretString \
  --output text 2>/dev/null) || true
if [ -n "$LLM_RAW" ]; then
    eval "$(echo "$LLM_RAW" | python3 -c '
import sys, json
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw)
    if data.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_KEY=\"" + data["OPENROUTER_API_KEY"] + "\"")
    if data.get("OPENAI_API_KEY"):
        print("OPENAI_KEY=\"" + data["OPENAI_API_KEY"] + "\"")
except:
    pass
')" || true
fi

# Create persistent data directory
mkdir -p /data/${agent_name}

# Download agent-specific data from S3 (if exists)
aws s3 sync s3://karmacadabra-agent-data/${agent_name}/ /data/${agent_name}/ \
  --region ${region} || echo "No S3 data for ${agent_name}"

# Clean stale IRC state to prevent feedback loops on fresh start
rm -f /data/${agent_name}/irc-inbox.jsonl 2>/dev/null || true
rm -f /data/${agent_name}/irc-outbox.jsonl 2>/dev/null || true
rm -f /data/${agent_name}/.irc-state.json 2>/dev/null || true
rm -f /data/${agent_name}/.irc-introduced 2>/dev/null || true

# Run agent container
docker run -d \
  --name ${agent_name} \
  --restart unless-stopped \
  -e KK_AGENT_NAME=${agent_name} \
  -e KK_WALLET_INDEX=${wallet_index} \
  -e KK_WALLET_ADDRESS=${wallet_address} \
  -e KK_PRIVATE_KEY="$PRIVATE_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_KEY" \
  -e OPENROUTER_API_KEY="$OPENROUTER_KEY" \
  -e OPENAI_API_KEY="$OPENAI_KEY" \
  -p 18790:18790 \
  -v /data/${agent_name}:/app/data \
  ${ecr_repo}:latest

# Install all cron jobs at once (avoids set -e issues with crontab -l on empty crontab)
cat <<CRONTAB | crontab -
*/15 * * * * aws s3 sync s3://karmacadabra-agent-data/${agent_name}/ /data/${agent_name}/ --region ${region} >> /var/log/s3-sync.log 2>&1
7,22,37,52 * * * * aws s3 sync /data/${agent_name}/ s3://karmacadabra-agent-data/${agent_name}/state/ --region ${region} --exclude '*' --include 'purchase_history.json' --include 'memory/*' --include 'irc_guard_state.json' --include 'escrow_state.json' >> /var/log/s3-upload.log 2>&1
0 */12 * * * docker restart ${agent_name}
0 4 * * * docker image prune -af --filter 'until=24h' >> /var/log/docker-prune.log 2>&1
CRONTAB
