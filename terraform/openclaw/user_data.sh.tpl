#!/bin/bash
set -e

# OpenClaw Agent Bootstrap Script
# Agent: ${agent_name} (wallet index: ${wallet_index})

# Install Docker
yum update -y
yum install -y docker
systemctl enable docker
systemctl start docker

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

# Create persistent data directory
mkdir -p /data/${agent_name}

# Download agent-specific data from S3 (if exists)
aws s3 sync s3://karmacadabra-agent-data/${agent_name}/ /data/${agent_name}/ \
  --region ${region} || echo "No S3 data for ${agent_name}"

# Run agent container
docker run -d \
  --name ${agent_name} \
  --restart unless-stopped \
  -e KK_AGENT_NAME=${agent_name} \
  -e KK_WALLET_INDEX=${wallet_index} \
  -e KK_WALLET_ADDRESS=${wallet_address} \
  -e KK_PRIVATE_KEY="$PRIVATE_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_KEY" \
  -p 18790:18790 \
  -v /data/${agent_name}:/app/data \
  ${ecr_repo}:latest

# Cron: sync S3 data every 15 minutes
(crontab -l 2>/dev/null; echo "*/15 * * * * aws s3 sync s3://karmacadabra-agent-data/${agent_name}/ /data/${agent_name}/ --region ${region} >> /var/log/s3-sync.log 2>&1") | crontab -

# Cron: restart container every 12 hours (memory leak mitigation)
(crontab -l 2>/dev/null; echo "0 */12 * * * docker restart ${agent_name}") | crontab -
