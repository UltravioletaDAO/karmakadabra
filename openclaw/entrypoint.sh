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

# ── OpenClaw Gateway Setup ──────────────────────────────────────────
# OpenClaw uses its own config system (~/.openclaw/openclaw.json).
# We configure it via CLI on each start, then launch the gateway.

if ! command -v openclaw &> /dev/null; then
    echo "[FATAL] OpenClaw not installed. Ensure Node.js + openclaw are in the Docker image."
    exit 1
fi

echo "[entrypoint] Configuring OpenClaw for $AGENT_NAME"

# Step 1: Initialize config (non-interactive, local mode)
openclaw setup --non-interactive --mode local --workspace "$WORKSPACE" 2>/dev/null || true

# Step 2: Set model (OpenRouter as primary)
if [ -n "$OPENROUTER_API_KEY" ]; then
    openclaw config set models.default "openrouter/openai/gpt-4o-mini" 2>/dev/null || true
    openclaw models auth paste-token --provider openrouter --token "$OPENROUTER_API_KEY" 2>/dev/null || true
    echo "[entrypoint] Model: openrouter/openai/gpt-4o-mini"
elif [ -n "$OPENAI_API_KEY" ]; then
    openclaw config set models.default "openai/gpt-4o-mini" 2>/dev/null || true
    openclaw models auth paste-token --provider openai --token "$OPENAI_API_KEY" 2>/dev/null || true
    echo "[entrypoint] Model: openai/gpt-4o-mini"
elif [ -n "$ANTHROPIC_API_KEY" ]; then
    openclaw config set models.default "anthropic/claude-haiku-4-5-20251001" 2>/dev/null || true
    openclaw models auth paste-token --provider anthropic --token "$ANTHROPIC_API_KEY" 2>/dev/null || true
    echo "[entrypoint] Model: anthropic/claude-haiku-4-5-20251001"
else
    echo "[WARN] No LLM API key set (OPENROUTER_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)"
fi

# Step 3: Configure agent identity
openclaw config set agents.defaults.name "$AGENT_NAME" 2>/dev/null || true
openclaw config set agents.defaults.workspace "$WORKSPACE" 2>/dev/null || true

# Step 4: Copy SOUL.md and HEARTBEAT.md to workspace (OpenClaw reads them from there)
cp /app/openclaw/agents/$AGENT_NAME/SOUL.md "$WORKSPACE/SOUL.md" 2>/dev/null || true
cp /app/openclaw/agents/$AGENT_NAME/HEARTBEAT.md "$WORKSPACE/HEARTBEAT.md" 2>/dev/null || true

# Step 5: Add IRC channel (MeshRelay)
openclaw channels add \
    --channel irc \
    --name "$AGENT_NAME" \
    2>/dev/null || true

# Step 6: Set gateway mode
openclaw config set gateway.mode "local" 2>/dev/null || true
openclaw config set gateway.bind "loopback" 2>/dev/null || true

echo "[entrypoint] OpenClaw configured. Starting gateway for $AGENT_NAME"

# Launch gateway in foreground (exec replaces shell)
exec openclaw gateway run --port 18790 --auth none --bind loopback
