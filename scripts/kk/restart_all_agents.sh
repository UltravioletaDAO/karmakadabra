#!/bin/bash
# Restart all KK agents on EC2 with the latest Docker image
# Usage: bash scripts/kk/restart_all_agents.sh

set -e

ECR_IMAGE="518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest"
KEY="$HOME/.ssh/kk-openclaw.pem"
REGION="us-east-1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Agent IPs — dynamically resolved from AWS EC2 tags
# Falls back to hardcoded IPs if AWS CLI is unavailable
declare -A AGENTS

echo "Resolving agent IPs from AWS..."
RESOLVED=0
while IFS=$'\t' read -r ip name; do
  if [ -n "$name" ] && [ -n "$ip" ] && [ "$name" != "None" ] && [ "$ip" != "None" ]; then
    AGENTS["$name"]="$ip"
    RESOLVED=$((RESOLVED + 1))
    echo "  $name -> $ip"
  fi
done < <(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=tag:Project,Values=karmacadabra" "Name=tag:Component,Values=openclaw" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].{Name: Tags[?Key==`Agent`].Value | [0], IP: PublicIpAddress}' \
  --output text 2>/dev/null | tr -d '\r')

if [ "$RESOLVED" -eq 0 ]; then
  echo "WARN: AWS lookup failed, using hardcoded IPs"
  AGENTS[kk-coordinator]="44.211.242.65"
  AGENTS[kk-karma-hello]="13.218.119.234"
  AGENTS[kk-skill-extractor]="100.53.60.94"
  AGENTS[kk-voice-extractor]="100.52.188.43"
  AGENTS[kk-validator]="44.203.23.11"
  AGENTS[kk-soul-extractor]="3.234.249.61"
  AGENTS[kk-juanjumagalp]="3.235.151.197"
  AGENTS[kk-0xjokker]="13.218.189.187"
  AGENTS[kk-0xyuls]="3.237.200.195"
else
  echo "Resolved $RESOLVED agents from AWS"
fi

# Discover vLLM GPU inference server IP (from spot fleet tags)
echo "Discovering GPU inference server..."
INFERENCE_IP=""
INFERENCE_IP=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Component,Values=inference" "Name=tag:Project,Values=karmacadabra" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].PrivateIpAddress' --output text 2>/dev/null | tr -d '\r' | head -1) || true
INFERENCE_URL=""
VLLM_API_KEY=""
if [ -n "$INFERENCE_IP" ]; then
  INFERENCE_URL="http://$INFERENCE_IP:8000/v1"
  echo "  GPU found: $INFERENCE_URL"
  # Get vLLM API key from terraform state (stored in random_password)
  VLLM_API_KEY=$(cd "$(dirname "$0")/../../terraform/openclaw" && terraform output -raw vllm_api_key 2>/dev/null) || true
  if [ -z "$VLLM_API_KEY" ]; then
    echo "  WARN: Could not get vLLM API key from terraform state"
  fi
else
  echo "  No GPU inference server found"
fi

# LLM provider (default: auto)
LLM_PROVIDER="${KK_LLM_PROVIDER:-auto}"
echo "LLM provider: $LLM_PROVIDER"

# Create the restart script that runs on each EC2
cat > /tmp/restart_agent_remote.sh << 'REMOTESCRIPT'
#!/bin/bash
# Do NOT use set -e here — individual failures must be handled gracefully

AGENT_NAME="$(echo "$1" | tr -d '\r')"
ECR_IMAGE="$(echo "$2" | tr -d '\r')"
REGION="$(echo "$3" | tr -d '\r')"
INFERENCE_URL="$(echo "$4" | tr -d '\r')"
VLLM_API_KEY="$(echo "$5" | tr -d '\r')"
LLM_PROVIDER="$(echo "$6" | tr -d '\r')"

if [ -z "$AGENT_NAME" ] || [ "$AGENT_NAME" = "unknown" ]; then
    echo "FATAL: AGENT_NAME is empty or unknown. Skipping."
    exit 1
fi

echo "=== Restarting $AGENT_NAME ==="

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin 518898403364.dkr.ecr.$REGION.amazonaws.com 2>/dev/null

# Pull latest image
echo "Pulling latest image..."
docker pull $ECR_IMAGE 2>/dev/null

# Get private key from Secrets Manager (may not exist for new agents)
PRIVATE_KEY=""
PRIVATE_KEY=$(aws secretsmanager get-secret-value \
  --secret-id "kk/$AGENT_NAME" \
  --region "$REGION" \
  --query SecretString \
  --output text 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('private_key',''))" 2>/dev/null) || true

# Get Anthropic key from Secrets Manager
ANTHROPIC_KEY=""
ANTHROPIC_RAW=$(aws secretsmanager get-secret-value \
  --secret-id kk/anthropic \
  --region "$REGION" \
  --query SecretString \
  --output text 2>/dev/null) || true
if [ -n "$ANTHROPIC_RAW" ]; then
    ANTHROPIC_KEY=$(python3 -c "
import sys, json
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw)
    for k in ('ANTHROPIC_API_KEY', 'anthropic_api_key', 'api_key', 'key'):
        if k in data:
            print(data[k])
            break
    else:
        print(raw)
except:
    print(raw)
" <<< "$ANTHROPIC_RAW" 2>/dev/null) || true
fi

# Get LLM keys from Secrets Manager (multi-provider: OpenRouter, OpenAI, Anthropic)
OPENROUTER_KEY=""
OPENAI_KEY=""
LLM_RAW=$(aws secretsmanager get-secret-value \
  --secret-id kk/llm-keys \
  --region "$REGION" \
  --query SecretString \
  --output text 2>/dev/null) || true
if [ -n "$LLM_RAW" ]; then
    eval "$(python3 -c "
import sys, json
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw)
    if data.get('OPENROUTER_API_KEY'):
        print('OPENROUTER_KEY=\"' + data['OPENROUTER_API_KEY'] + '\"')
    if data.get('OPENAI_API_KEY'):
        print('OPENAI_KEY=\"' + data['OPENAI_API_KEY'] + '\"')
except:
    pass
" <<< "$LLM_RAW" 2>/dev/null)" || true
fi

# Get wallet address from image config
WALLET_ADDRESS=$(docker run --rm --entrypoint python3 "$ECR_IMAGE" -c "
import json
data = json.load(open('/app/config/identities.json'))
for a in data.get('agents', []):
    if a.get('name') == '$AGENT_NAME':
        print(a.get('address', ''))
        break
" 2>/dev/null) || true

echo "Wallet: $WALLET_ADDRESS"
echo "Private key: $([ -n "$PRIVATE_KEY" ] && echo SET || echo MISSING)"
echo "Anthropic key: $([ -n "$ANTHROPIC_KEY" ] && echo SET || echo MISSING)"
echo "OpenRouter key: $([ -n "$OPENROUTER_KEY" ] && echo SET || echo MISSING)"
echo "OpenAI key: $([ -n "$OPENAI_KEY" ] && echo SET || echo MISSING)"

# Validate: must have private key to start
if [ -z "$PRIVATE_KEY" ]; then
    echo "SKIP: No private key for $AGENT_NAME (secret kk/$AGENT_NAME not found)"
    exit 0
fi

# Stop and remove old container
docker stop "$AGENT_NAME" 2>/dev/null || true
docker rm "$AGENT_NAME" 2>/dev/null || true

# Clean stale IRC state to prevent feedback loops on restart
rm -f "/data/$AGENT_NAME/irc-inbox.jsonl" 2>/dev/null || true
rm -f "/data/$AGENT_NAME/irc-outbox.jsonl" 2>/dev/null || true
rm -f "/data/$AGENT_NAME/.irc-state.json" 2>/dev/null || true
rm -f "/data/$AGENT_NAME/.irc-introduced" 2>/dev/null || true

# When vLLM inference is available, override OPENAI_API_KEY with vLLM key
EFFECTIVE_OPENAI_KEY="$OPENAI_KEY"
if [ -n "$INFERENCE_URL" ] && [ -n "$VLLM_API_KEY" ]; then
  EFFECTIVE_OPENAI_KEY="$VLLM_API_KEY"
fi

# Start new container
docker run -d \
  --name "$AGENT_NAME" \
  --restart unless-stopped \
  --memory 1800m \
  --memory-swap 2g \
  -e "KK_AGENT_NAME=$AGENT_NAME" \
  -e "KK_WALLET_ADDRESS=$WALLET_ADDRESS" \
  -e "KK_PRIVATE_KEY=$PRIVATE_KEY" \
  -e "ANTHROPIC_API_KEY=$ANTHROPIC_KEY" \
  -e "OPENAI_API_KEY=$EFFECTIVE_OPENAI_KEY" \
  -e "OPENROUTER_API_KEY=$OPENROUTER_KEY" \
  -e "OPENAI_BASE_URL=$INFERENCE_URL" \
  -e "KK_LLM_BASE_URL=$INFERENCE_URL" \
  -e "KK_LLM_API_KEY=$VLLM_API_KEY" \
  -e "KK_LLM_PROVIDER=$LLM_PROVIDER" \
  -p 18790:18790 \
  -v "/data/$AGENT_NAME:/app/data" \
  "$ECR_IMAGE"

echo "Container started. Waiting 5s for startup..."
sleep 5
docker logs "$AGENT_NAME" --tail 10
echo "=== $AGENT_NAME DONE ==="
REMOTESCRIPT

chmod +x /tmp/restart_agent_remote.sh

AGENT_COUNT=${#AGENTS[@]}
echo "=== Deploying to all $AGENT_COUNT agents ==="
echo ""

DEPLOYED=0
FAILED=0
for AGENT in "${!AGENTS[@]}"; do
  IP="${AGENTS[$AGENT]}"
  echo "--- $AGENT @ $IP ---"

  # SCP the script (tolerate failure)
  if ! scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$KEY" \
    /tmp/restart_agent_remote.sh "ec2-user@$IP:/tmp/restart_agent.sh" 2>/dev/null; then
    echo "WARN: SCP failed for $AGENT @ $IP — skipping"
    FAILED=$((FAILED + 1))
    echo ""
    continue
  fi

  # Execute it (tolerate failure per agent)
  if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 -i "$KEY" "ec2-user@$IP" \
    "bash /tmp/restart_agent.sh '$AGENT' '$ECR_IMAGE' '$REGION' '$INFERENCE_URL' '$VLLM_API_KEY' '$LLM_PROVIDER'" 2>&1; then
    DEPLOYED=$((DEPLOYED + 1))
  else
    echo "WARN: Deploy failed for $AGENT @ $IP"
    FAILED=$((FAILED + 1))
  fi

  echo "--- $AGENT @ $IP DONE ---"
  echo ""
done

echo "=== $DEPLOYED/$AGENT_COUNT DEPLOYED ($FAILED failed) ==="
