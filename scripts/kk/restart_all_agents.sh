#!/bin/bash
# Restart all KK agents on EC2 with the latest Docker image
# Usage: bash scripts/kk/restart_all_agents.sh

set -e

ECR_IMAGE="518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest"
KEY="$HOME/.ssh/kk-openclaw.pem"
REGION="us-east-1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Agent IPs
declare -A AGENTS
AGENTS[kk-coordinator]="44.211.242.65"
AGENTS[kk-karma-hello]="13.218.119.234"
AGENTS[kk-skill-extractor]="100.53.60.94"
AGENTS[kk-voice-extractor]="100.52.188.43"
AGENTS[kk-validator]="44.203.23.11"
AGENTS[kk-soul-extractor]="3.234.249.61"
AGENTS[kk-juanjumagalp]="3.235.151.197"

# Create the restart script that runs on each EC2
cat > /tmp/restart_agent_remote.sh << 'REMOTESCRIPT'
#!/bin/bash
set -e

AGENT_NAME="$1"
ECR_IMAGE="$2"
REGION="$3"

echo "=== Restarting $AGENT_NAME ==="

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin 518898403364.dkr.ecr.$REGION.amazonaws.com 2>/dev/null

# Pull latest image
echo "Pulling latest image..."
docker pull $ECR_IMAGE 2>/dev/null

# Get secrets
PRIVATE_KEY=$(aws secretsmanager get-secret-value \
  --secret-id kk/$AGENT_NAME \
  --region $REGION \
  --query SecretString \
  --output text | python3 -c "import sys,json; print(json.load(sys.stdin).get('private_key',''))")

ANTHROPIC_RAW=$(aws secretsmanager get-secret-value \
  --secret-id kk/anthropic \
  --region $REGION \
  --query SecretString \
  --output text)
ANTHROPIC_KEY=$(python3 -c "
import sys, json
raw = '''$ANTHROPIC_RAW'''
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

# Get wallet address from image config
WALLET_ADDRESS=$(docker run --rm --entrypoint python3 $ECR_IMAGE -c "
import json
data = json.load(open('/app/config/identities.json'))
for a in data.get('agents', []):
    if a.get('name') == '$AGENT_NAME':
        print(a.get('address', ''))
        break
" 2>/dev/null)

echo "Wallet: $WALLET_ADDRESS"
echo "Private key: $([ -n "$PRIVATE_KEY" ] && echo SET || echo MISSING)"
echo "Anthropic key: $([ -n "$ANTHROPIC_KEY" ] && echo SET || echo MISSING)"

# Stop and remove old container
docker stop $AGENT_NAME 2>/dev/null || true
docker rm $AGENT_NAME 2>/dev/null || true

# Start new container
docker run -d \
  --name $AGENT_NAME \
  --restart unless-stopped \
  -e KK_AGENT_NAME=$AGENT_NAME \
  -e KK_WALLET_ADDRESS="$WALLET_ADDRESS" \
  -e KK_PRIVATE_KEY="$PRIVATE_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_KEY" \
  -p 18790:18790 \
  -v /data/$AGENT_NAME:/app/data \
  $ECR_IMAGE

echo "Container started. Waiting 5s for startup..."
sleep 5
docker logs $AGENT_NAME --tail 10
echo "=== $AGENT_NAME DONE ==="
REMOTESCRIPT

chmod +x /tmp/restart_agent_remote.sh

echo "=== Deploying to all 7 agents ==="
echo ""

for AGENT in "${!AGENTS[@]}"; do
  IP="${AGENTS[$AGENT]}"
  echo "--- $AGENT ($IP) ---"

  # SCP the script
  scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$KEY" \
    /tmp/restart_agent_remote.sh ec2-user@$IP:/tmp/restart_agent.sh 2>/dev/null

  # Execute it
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 -i "$KEY" ec2-user@$IP \
    "bash /tmp/restart_agent.sh $AGENT $ECR_IMAGE $REGION" 2>&1

  echo ""
done

echo "=== ALL AGENTS DEPLOYED ==="
