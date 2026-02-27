#!/bin/bash
# restart_agent.sh - Run ON the EC2 instance to restart agent container
# Usage: bash restart_agent.sh <agent-name> <wallet-address>
set -euo pipefail

NAME="${1:?Usage: restart_agent.sh <agent-name> <wallet-address>}"
WALLET="${2:?Usage: restart_agent.sh <agent-name> <wallet-address>}"
REGION="us-east-1"
ECR="518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest"

echo "=== Restarting agent: $NAME ==="
echo "Wallet: $WALLET"

# 1. Force remove ALL non-ecs containers (old + broken)
echo "[1/5] Stopping old containers..."
for c in $(docker ps -aq --format '{{.Names}}' | grep -v ecs-agent); do
    echo "  Removing container: $c"
    docker rm -f "$c" 2>/dev/null || true
done

# 2. Login to ECR and pull latest
echo "[2/5] Pulling latest image..."
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin \
    518898403364.dkr.ecr.$REGION.amazonaws.com 2>/dev/null
docker pull $ECR

# 3. Read secrets (no nested quoting - runs locally on the instance)
echo "[3/5] Reading secrets..."
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "kk/$NAME" \
    --region $REGION \
    --query SecretString \
    --output text)
PRIVATE_KEY=$(echo "$SECRET_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["private_key"])')

ANTHROPIC_RAW=$(aws secretsmanager get-secret-value \
    --secret-id "kk/anthropic" \
    --region $REGION \
    --query SecretString \
    --output text)
# Secret may be JSON {"ANTHROPIC_API_KEY":"sk-..."} or raw string
ANTHROPIC_KEY=$(echo "$ANTHROPIC_RAW" | python3 -c '
import sys, json
raw = sys.stdin.read().strip()
try:
    data = json.loads(raw)
    # Try common key names
    for k in ("ANTHROPIC_API_KEY", "anthropic_api_key", "api_key", "key"):
        if k in data:
            print(data[k])
            break
    else:
        print(raw)
except (json.JSONDecodeError, TypeError):
    print(raw)
')

# Verify we got the keys
if [ -z "$PRIVATE_KEY" ] || [ ${#PRIVATE_KEY} -lt 10 ]; then
    echo "ERROR: Failed to read private key for $NAME"
    exit 1
fi
echo "  Private key: ${PRIVATE_KEY:0:6}...${PRIVATE_KEY: -4} (${#PRIVATE_KEY} chars)"
echo "  Anthropic key: ${ANTHROPIC_KEY:0:10}... (${#ANTHROPIC_KEY} chars)"

# 4. Start new container
echo "[4/5] Starting container..."
docker run -d \
    --name "$NAME" \
    --restart unless-stopped \
    -e KK_AGENT_NAME="$NAME" \
    -e KK_WALLET_ADDRESS="$WALLET" \
    -e KK_PRIVATE_KEY="$PRIVATE_KEY" \
    -e ANTHROPIC_API_KEY="$ANTHROPIC_KEY" \
    -p 18790:18790 \
    -v "/data/$NAME:/app/data" \
    $ECR

# 5. Wait and show logs
echo "[5/5] Container started. Waiting for initialization..."
sleep 8
echo "--- Container logs ---"
docker logs "$NAME" --tail 20 2>&1
echo "=== Done: $NAME ==="
