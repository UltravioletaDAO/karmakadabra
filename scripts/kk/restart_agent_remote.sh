#!/bin/bash
# Runs ON the EC2 instance to restart a single agent container
# Usage: bash restart_agent_remote.sh <agent-name> <ecr-image> <region>
set -e

AGENT_NAME="$1"
ECR_IMAGE="$2"
REGION="${3:-us-east-1}"

echo "=== Restarting $AGENT_NAME ==="

# Login to ECR
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "518898403364.dkr.ecr.${REGION}.amazonaws.com" 2>/dev/null

# Pull latest image
echo "Pulling latest image..."
docker pull "$ECR_IMAGE" >/dev/null

# Get private key from Secrets Manager
PRIVATE_KEY=$(aws secretsmanager get-secret-value \
  --secret-id "kk/$AGENT_NAME" \
  --region "$REGION" \
  --query SecretString \
  --output text | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('private_key',''))")

# Get Anthropic key from Secrets Manager (may be JSON or raw string)
ANTHROPIC_KEY=$(aws secretsmanager get-secret-value \
  --secret-id kk/anthropic \
  --region "$REGION" \
  --query SecretString \
  --output text | python3 -c "
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
")

# Get wallet address from Docker image config
WALLET_ADDRESS=$(docker run --rm "$ECR_IMAGE" python3 -c "
import json
data = json.load(open('/app/config/identities.json'))
for a in data.get('agents', []):
    if a.get('name') == '${AGENT_NAME}':
        print(a.get('address', ''))
        break
" 2>/dev/null)

echo "Wallet: $WALLET_ADDRESS"
echo "Private key: $([ -n "$PRIVATE_KEY" ] && echo SET || echo MISSING)"
echo "Anthropic key: $([ -n "$ANTHROPIC_KEY" ] && echo SET || echo MISSING)"

# Stop and remove old container
docker stop "$AGENT_NAME" 2>/dev/null || true
docker rm "$AGENT_NAME" 2>/dev/null || true

# Start new container
docker run -d \
  --name "$AGENT_NAME" \
  --restart unless-stopped \
  -e KK_AGENT_NAME="$AGENT_NAME" \
  -e KK_WALLET_ADDRESS="$WALLET_ADDRESS" \
  -e KK_PRIVATE_KEY="$PRIVATE_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_KEY" \
  -p 18790:18790 \
  -v "/data/${AGENT_NAME}:/app/data" \
  "$ECR_IMAGE"

echo "Container started. Waiting 8s for startup..."
sleep 8
echo "--- Startup logs ---"
docker logs "$AGENT_NAME" --tail 15
echo "=== $AGENT_NAME DONE ==="
