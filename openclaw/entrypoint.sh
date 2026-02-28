#!/bin/bash
set -e

AGENT_NAME="${KK_AGENT_NAME:-unknown}"
WORKSPACES_ROOT="/app/workspaces"
WORKSPACE="$WORKSPACES_ROOT/$AGENT_NAME"
SKILLS_DIR="/app/skills"

echo "[entrypoint] Setting up agent: $AGENT_NAME"

# Create workspace structure (heartbeat expects workspaces_root/agent_name/)
mkdir -p "$WORKSPACE/memory"
mkdir -p "$SKILLS_DIR"

# Copy agent identity files to workspace
cp /app/openclaw/agents/$AGENT_NAME/SOUL.md "$WORKSPACE/" 2>/dev/null || true
cp /app/openclaw/agents/$AGENT_NAME/HEARTBEAT.md "$WORKSPACE/" 2>/dev/null || true

# Copy skills
cp -r /app/openclaw/skills/* "$SKILLS_DIR/" 2>/dev/null || true

# Initialize WORKING.md if not exists
if [ ! -f "$WORKSPACE/memory/WORKING.md" ]; then
    cat > "$WORKSPACE/memory/WORKING.md" << 'EOF'
# WORKING.md
## Status: idle
## Last Heartbeat: never
## Active Task: none
## Daily Spent: $0.00
## Daily Budget: $2.00
EOF
fi

echo "[entrypoint] Agent $AGENT_NAME ready"

# Create wallet.json for EMClient auth (EIP-8128 signing)
mkdir -p "$WORKSPACE/data"
WALLET_ADDRESS="${KK_WALLET_ADDRESS:-}"
CHAIN_ID="${KK_CHAIN_ID:-8453}"

# Parse private key from JSON secret if needed
# AWS Secrets Manager stores as {"private_key": "0x..."} not raw string
if echo "$KK_PRIVATE_KEY" | python3 -c "import sys,json; json.loads(sys.stdin.read())" 2>/dev/null; then
  KK_PRIVATE_KEY=$(echo "$KK_PRIVATE_KEY" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('private_key',''))")
fi

# Get executor_id from identities.json
EXECUTOR_ID=""
if [ -f /app/config/identities.json ]; then
  EXECUTOR_ID=$(python3 -c "
import json
data = json.load(open('/app/config/identities.json'))
for a in data.get('agents', []):
    if a.get('name') == '${AGENT_NAME}':
        print(a.get('executor_id', ''))
        break
")
fi

cat > "$WORKSPACE/data/wallet.json" <<WALLETEOF
{
  "address": "${WALLET_ADDRESS}",
  "private_key": "${KK_PRIVATE_KEY}",
  "chain_id": ${CHAIN_ID},
  "executor_id": "${EXECUTOR_ID}"
}
WALLETEOF

echo "[INIT] wallet.json created for ${AGENT_NAME} (executor: ${EXECUTOR_ID})"

# Start IRC daemon in background (connects to MeshRelay)
echo "[entrypoint] Starting IRC daemon for $AGENT_NAME"
python3 /app/scripts/kk/irc_daemon.py \
    --agent "$AGENT_NAME" \
    --channel "#karmakadabra" \
    --extra-channels "#Execution-Market" \
    --data-dir /app/data &
IRC_PID=$!
echo "[entrypoint] IRC daemon started (PID: $IRC_PID)"

# Cleanup IRC daemon on exit
trap "kill $IRC_PID 2>/dev/null; wait $IRC_PID 2>/dev/null" EXIT

# Start OpenClaw gateway (if installed) or run heartbeat loop
if command -v openclaw &> /dev/null; then
    exec openclaw --config /app/openclaw/agents/$AGENT_NAME/openclaw.json
else
    echo "[entrypoint] OpenClaw not found, running heartbeat loop"
    while true; do
        python3 /app/cron/heartbeat.py --agent "$AGENT_NAME" --workspaces "$WORKSPACES_ROOT" --data-dir /app/data || {
            echo "[entrypoint] Heartbeat exited with code $? — restarting after cooldown"
            sleep 60
        }
        sleep 1800
    done
fi
