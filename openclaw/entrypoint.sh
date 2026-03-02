#!/bin/bash
set -e

AGENT_NAME="${KK_AGENT_NAME:-}"
if [ -z "$AGENT_NAME" ] || [ "$AGENT_NAME" = "unknown" ]; then
    echo "[FATAL] KK_AGENT_NAME is not set or is 'unknown'. Cannot start agent."
    echo "[FATAL] Set KK_AGENT_NAME env var (e.g., kk-karma-hello) in docker run."
    exit 1
fi

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

# Initialize Obsidian Vault (local copy, no git remote yet)
VAULT_DIR="/app/vault"
if [ -d "$VAULT_DIR" ]; then
    echo "[entrypoint] Vault directory found at $VAULT_DIR"
    cd "$VAULT_DIR"
    git config user.name "$AGENT_NAME" 2>/dev/null || true
    git config user.email "${AGENT_NAME}@karmacadabra.ultravioletadao.xyz" 2>/dev/null || true
    cd /app
fi

# Start OpenClaw gateway (Node.js LLM gateway with native IRC)
# OpenClaw handles: IRC connection, LLM reasoning, tool execution, heartbeat cycles
if command -v openclaw &> /dev/null; then
    echo "[entrypoint] Starting OpenClaw gateway for $AGENT_NAME"
    exec openclaw --config /app/openclaw/agents/$AGENT_NAME/openclaw.json
else
    echo "[FATAL] OpenClaw not installed. Ensure Node.js + openclaw are in the Docker image."
    echo "[FATAL] The heartbeat loop fallback has been removed — OpenClaw is required."
    exit 1
fi
