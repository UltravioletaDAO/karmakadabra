#!/bin/bash
# Update a running OpenClaw agent with the latest Docker image
# Usage: update_agent.sh <agent-name>  (run ON the EC2 instance)
set -e

NAME="${1:-}"
if [ -z "$NAME" ]; then
    echo "Usage: update_agent.sh <agent-name>"
    exit 1
fi

ECR="518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest"
REGION="us-east-1"

echo "Updating agent: $NAME"

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin 518898403364.dkr.ecr.$REGION.amazonaws.com 2>/dev/null

# Pull latest image
docker pull $ECR

# Stop and remove old container (try both possible names)
docker stop $NAME 2>/dev/null || true
docker rm $NAME 2>/dev/null || true
# Also stop any other kk- containers
for c in $(docker ps --format '{{.Names}}' | grep -v ecs-agent); do
    docker stop $c 2>/dev/null || true
    docker rm $c 2>/dev/null || true
done

# Read secrets
PRIVATE_KEY=$(aws secretsmanager get-secret-value --secret-id "kk/$NAME" --region $REGION --query SecretString --output text | python3 -c 'import sys,json; print(json.load(sys.stdin).get("private_key",""))')
ANTHROPIC_KEY=$(aws secretsmanager get-secret-value --secret-id "kk/anthropic" --region $REGION --query SecretString --output text)

# Get wallet address from image
WALLET_ADDR=$(docker run --rm $ECR python3 -c "
import json
data = json.load(open('/app/data/config/wallets.json'))
for w in data['wallets']:
    if w['name'] == '$NAME':
        print(w['address'])
        break
")

echo "Wallet: $WALLET_ADDR"

# Run new container
docker run -d \
  --name $NAME \
  --restart unless-stopped \
  -e KK_AGENT_NAME=$NAME \
  -e KK_WALLET_ADDRESS=$WALLET_ADDR \
  -e KK_PRIVATE_KEY="$PRIVATE_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_KEY" \
  -p 18790:18790 \
  -v /data/$NAME:/app/data \
  $ECR

sleep 3
echo "--- Container logs ---"
docker logs $NAME --tail 15 2>&1
