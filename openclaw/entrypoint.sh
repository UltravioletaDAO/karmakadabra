#!/bin/bash
set -e

AGENT_NAME="${KK_AGENT_NAME:-}"
if [ -z "$AGENT_NAME" ] || [ "$AGENT_NAME" = "unknown" ]; then
    echo "[FATAL] KK_AGENT_NAME is not set or is 'unknown'. Cannot start agent."
    echo "[FATAL] Set KK_AGENT_NAME env var (e.g., kk-karma-hello) in docker run."
    exit 1
fi

WORKSPACE="/app/workspaces/$AGENT_NAME"

echo "[entrypoint] Setting up agent: $AGENT_NAME"

# ── Workspace Structure ──────────────────────────────────────────────
# OpenClaw reads SOUL.md, HEARTBEAT.md, AGENTS.md from workspace root.
# Skills are loaded from workspace/skills/.

mkdir -p "$WORKSPACE/memory"
mkdir -p "$WORKSPACE/data"
mkdir -p "$WORKSPACE/skills"

# Copy agent identity files to workspace root
cp /app/openclaw/agents/$AGENT_NAME/SOUL.md "$WORKSPACE/SOUL.md" 2>/dev/null || true
cp /app/openclaw/agents/$AGENT_NAME/HEARTBEAT.md "$WORKSPACE/HEARTBEAT.md" 2>/dev/null || true

# Copy skills to workspace/skills/ (OpenClaw auto-discovers from here)
cp -r /app/openclaw/skills/* "$WORKSPACE/skills/" 2>/dev/null || true

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

# Create AGENTS.md (primary operational instructions for the LLM)
cat > "$WORKSPACE/AGENTS.md" << AGENTSEOF
# Agent Instructions — $AGENT_NAME

You are $AGENT_NAME, an autonomous economic agent in the KarmaCadabra swarm.
You operate headless in a Docker container with no human interaction.

## Available Tools

Use the exec tool to run Python scripts. Pipe JSON to stdin, read JSON from stdout.

### Execution Market (em_tool)
echo '{"action":"browse","params":{"limit":10}}' | python3 /app/openclaw/tools/em_tool.py
echo '{"action":"publish","params":{"title":"...","instructions":"...","bounty_usd":0.01}}' | python3 /app/openclaw/tools/em_tool.py
echo '{"action":"apply","params":{"task_id":"uuid"}}' | python3 /app/openclaw/tools/em_tool.py
echo '{"action":"submit","params":{"task_id":"uuid","evidence":{"json_response":{"data":"..."}}}}' | python3 /app/openclaw/tools/em_tool.py
echo '{"action":"status","params":{}}' | python3 /app/openclaw/tools/em_tool.py
echo '{"action":"history","params":{}}' | python3 /app/openclaw/tools/em_tool.py

### Wallet (wallet_tool)
echo '{"action":"balance","params":{}}' | python3 /app/openclaw/tools/wallet_tool.py
echo '{"action":"budget","params":{}}' | python3 /app/openclaw/tools/wallet_tool.py
echo '{"action":"can_afford","params":{"amount":0.05}}' | python3 /app/openclaw/tools/wallet_tool.py

### Data Inventory (data_tool)
echo '{"action":"list_purchases","params":{}}' | python3 /app/openclaw/tools/data_tool.py
echo '{"action":"list_products","params":{}}' | python3 /app/openclaw/tools/data_tool.py

### IRC Communication (irc_tool)
echo '{"action":"read_inbox","params":{"limit":20}}' | python3 /app/openclaw/tools/irc_tool.py
echo '{"action":"send","params":{"channel":"#karmakadabra","message":"Hola parce"}}' | python3 /app/openclaw/tools/irc_tool.py
echo '{"action":"status","params":{}}' | python3 /app/openclaw/tools/irc_tool.py
echo '{"action":"history","params":{"limit":10}}' | python3 /app/openclaw/tools/irc_tool.py

### MCP Bridge (mcp_client — connects to MeshRelay, Execution Market, AutoJob)
# List tools from any MCP server
echo '{"server":"meshrelay","action":"list","tool":"","params":{}}' | python3 /app/openclaw/tools/mcp_client.py
echo '{"server":"em","action":"list","tool":"","params":{}}' | python3 /app/openclaw/tools/mcp_client.py
echo '{"server":"autojob","action":"list","tool":"","params":{}}' | python3 /app/openclaw/tools/mcp_client.py

# Call a specific MCP tool
echo '{"server":"meshrelay","action":"call","tool":"meshrelay_get_messages","params":{"channel":"#karmakadabra","limit":20}}' | python3 /app/openclaw/tools/mcp_client.py
echo '{"server":"autojob","action":"call","tool":"autojob_match_jobs","params":{"query":"data processing"}}' | python3 /app/openclaw/tools/mcp_client.py

# Server shortcuts: meshrelay, em, execution-market, autojob
# Or use full URL: {"server":"https://api.meshrelay.xyz/mcp",...}

## IRC — Tu Vida Social (PRIORIDAD MAXIMA)
- You MUST send at least 1 message per heartbeat. ZERO messages = heartbeat FAILED.
- Be social, be human, be interesting. NO operational reports. NO templates.
- If someone said something -> respond to THEM, don't just talk about yourself.
- Topics: business, market, music, philosophy, jokes, questions, opinions, ANYTHING.
- You're in a group chat with friends, not filing a report.
- Maximum 3 IRC messages per heartbeat — quality over quantity.
- Use irc_tool read_inbox to check messages, irc_tool send to reply.
- Channels: #karmakadabra (main), #Execution-Market (trades), #agents (coordination)
- Speak in casual Colombian Spanish: "parce", "bacano", "que mas"
- NEVER respond to your own messages or repeat what you just said

## Platform Integration
- **MeshRelay**: IRC network for agent communication. Use irc_tool for messages, mcp_client for network stats.
- **Execution Market**: Task marketplace. Use em_tool for tasks, mcp_client for advanced queries.
- **AutoJob**: Skill matching. Use mcp_client to analyze skills and match to bounties.
- Read the SKILL.md files in your skills/ directory for detailed documentation on each platform.

## Rules
- Execute ONE action per heartbeat. Do not try to do everything at once.
- All tool output is JSON. Parse it and act on it.
- You are sovereign. Trade data on the Execution Market.
- NEVER respond to your own messages or repeat templates.
- Check your skills/ directory for platform-specific instructions.
AGENTSEOF

# Create TOOLS.md (environment documentation)
cat > "$WORKSPACE/TOOLS.md" << 'TOOLSEOF'
# Tools Environment
- OS: Linux (Debian slim)
- Python: /usr/bin/python3 (3.11)
- Node.js: v22
- Working directory: /app
- Data directory: /app/data (persistent, mounted volume)
- Config: /app/config (identities.json, wallets.json)
- All tools: JSON stdin -> JSON stdout, errors to stderr
- IRC: Python daemon bridges to irc.meshrelay.xyz:6697 (SSL)
- IRC inbox: /app/data/irc-inbox.jsonl (read by irc_tool)
- IRC outbox: /app/data/irc-outbox.jsonl (written by irc_tool)
TOOLSEOF

echo "[entrypoint] Agent $AGENT_NAME workspace ready"

# ── Wallet Config ────────────────────────────────────────────────────

WALLET_ADDRESS="${KK_WALLET_ADDRESS:-}"
CHAIN_ID="${KK_CHAIN_ID:-8453}"

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

# ── Obsidian Vault ───────────────────────────────────────────────────

VAULT_DIR="/app/vault"
if [ -d "$VAULT_DIR" ]; then
    echo "[entrypoint] Vault directory found at $VAULT_DIR"
    cd "$VAULT_DIR"
    git config user.name "$AGENT_NAME" 2>/dev/null || true
    git config user.email "${AGENT_NAME}@karmacadabra.ultravioletadao.xyz" 2>/dev/null || true
    cd /app
fi

# ── Python IRC Daemon (background) ──────────────────────────────────
# Runs alongside OpenClaw gateway. Bridges IRC <-> file-based inbox/outbox.
# OpenClaw's native IRC plugin is buggy (exits 2ms after connecting),
# so we use our proven Python IRC daemon instead.

echo "[entrypoint] Starting Python IRC daemon for $AGENT_NAME"

# Ensure data directory exists for inbox/outbox
mkdir -p /app/data

python3 /app/scripts/kk/irc_daemon.py \
    --agent "$AGENT_NAME" \
    --channel "#karmakadabra" \
    --extra-channels "#Execution-Market" "#agents" \
    --data-dir /app/data \
    &
IRC_DAEMON_PID=$!
echo "$IRC_DAEMON_PID" > /app/data/irc-daemon.pid
echo "[entrypoint] IRC daemon started (PID: $IRC_DAEMON_PID)"

# ── OpenClaw Gateway Configuration ───────────────────────────────────
# OpenClaw reads config from ~/.openclaw/openclaw.json.
# Env vars (OPENROUTER_API_KEY, ANTHROPIC_API_KEY) are auto-detected.
# No paste-token needed — env vars are resolved at request time.

if ! command -v openclaw &> /dev/null; then
    echo "[FATAL] OpenClaw not installed."
    exit 1
fi

echo "[entrypoint] Configuring OpenClaw for $AGENT_NAME"

# Step 1: Initialize config (non-interactive, local mode)
openclaw setup --non-interactive --mode local --workspace "$WORKSPACE" 2>/dev/null || true

# Step 2: LLM Provider — Dynamic selection
# Env var KK_LLM_PROVIDER controls: auto, vllm, openrouter, openai, anthropic
LLM_PROVIDER="${KK_LLM_PROVIDER:-auto}"
echo "[entrypoint] LLM provider: $LLM_PROVIDER"

configure_vllm() {
    openclaw models set "openai/gpt-4o-mini" 2>/dev/null || true
    AGENT_MODELS_DIR="$HOME/.openclaw/agents/main/agent"
    mkdir -p "$AGENT_MODELS_DIR"
    cat > "$AGENT_MODELS_DIR/models.json" << MODELEOF
{
  "providers": {
    "openai": {
      "baseUrl": "${KK_LLM_BASE_URL}",
      "api": "openai-completions",
      "models": [{"id":"gpt-4o-mini","name":"Qwen3-8B via vLLM","reasoning":false,"input":["text"],"cost":{"input":0,"output":0,"cacheRead":0,"cacheWrite":0},"contextWindow":32768,"maxTokens":8192}],
      "apiKey": "OPENAI_API_KEY"
    }
  }
}
MODELEOF
    echo "[entrypoint] Model: Qwen3-8B via vLLM @ $KK_LLM_BASE_URL"
}

configure_openrouter() {
    openclaw models set "openrouter/openai/gpt-4o-mini" 2>/dev/null || true
    echo "[entrypoint] Model: openrouter/openai/gpt-4o-mini"
}

configure_openai() {
    openclaw models set "openai/gpt-4o-mini" 2>/dev/null || true
    echo "[entrypoint] Model: openai/gpt-4o-mini"
}

configure_anthropic() {
    openclaw models set "anthropic/claude-haiku-4-5-20251001" 2>/dev/null || true
    echo "[entrypoint] Model: anthropic/claude-haiku-4-5-20251001"
}

wait_for_vllm() {
    echo "[entrypoint] Waiting for Qwen to be ready..."
    for i in $(seq 1 40); do
        if curl -sf "${KK_LLM_BASE_URL}/models" -H "Authorization: Bearer ${KK_LLM_API_KEY:-none}" > /dev/null 2>&1; then
            return 0
        fi
        echo "[entrypoint] Qwen not ready yet... ($((i * 15))s)"
        sleep 15
    done
    return 1
}

MODEL_SET=false

case "$LLM_PROVIDER" in
    vllm)
        if [ -n "$KK_LLM_BASE_URL" ]; then
            if wait_for_vllm; then
                configure_vllm
                MODEL_SET=true
            else
                echo "[FATAL] KK_LLM_PROVIDER=vllm but Qwen not available after 10 minutes"
            fi
        else
            echo "[FATAL] KK_LLM_PROVIDER=vllm but KK_LLM_BASE_URL not set"
        fi
        ;;
    openrouter)
        if [ -n "$OPENROUTER_API_KEY" ]; then
            configure_openrouter
            MODEL_SET=true
        else
            echo "[FATAL] KK_LLM_PROVIDER=openrouter but OPENROUTER_API_KEY not set"
        fi
        ;;
    openai)
        if [ -n "$OPENAI_API_KEY" ]; then
            configure_openai
            MODEL_SET=true
        else
            echo "[FATAL] KK_LLM_PROVIDER=openai but OPENAI_API_KEY not set"
        fi
        ;;
    anthropic)
        if [ -n "$ANTHROPIC_API_KEY" ]; then
            configure_anthropic
            MODEL_SET=true
        else
            echo "[FATAL] KK_LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY not set"
        fi
        ;;
    auto|*)
        # Auto-detect: vLLM > OpenRouter > OpenAI > Anthropic
        if [ -n "$KK_LLM_BASE_URL" ]; then
            if wait_for_vllm; then
                configure_vllm
                MODEL_SET=true
            else
                echo "[WARN] vLLM unreachable, trying fallbacks..."
            fi
        fi
        if [ "$MODEL_SET" = false ] && [ -n "$OPENROUTER_API_KEY" ]; then
            configure_openrouter
            MODEL_SET=true
        fi
        if [ "$MODEL_SET" = false ] && [ -n "$OPENAI_API_KEY" ]; then
            configure_openai
            MODEL_SET=true
        fi
        if [ "$MODEL_SET" = false ] && [ -n "$ANTHROPIC_API_KEY" ]; then
            configure_anthropic
            MODEL_SET=true
        fi
        ;;
esac

if [ "$MODEL_SET" = false ]; then
    echo "[FATAL] No LLM provider available. Agent will start but heartbeats will fail."
    echo "[FATAL] Set KK_LLM_PROVIDER or provide API keys (OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)"
fi

# Step 3: Agent identity and workspace
openclaw config set agents.defaults.workspace "$WORKSPACE" 2>/dev/null || true

# Step 4: Heartbeat interval (configurable: 45s remote, 90s local — less GPU pressure)
HEARTBEAT="${KK_HEARTBEAT_INTERVAL:-45s}"
openclaw config set agents.defaults.heartbeat.every "$HEARTBEAT" 2>/dev/null || true

# Step 5: Tool policy (enable exec for Python tools, deny browser)
openclaw config set tools.allow '["exec","read","write","edit","web_fetch"]' 2>/dev/null || true
openclaw config set tools.deny '["browser"]' 2>/dev/null || true
# Step 5b: Disable sandbox (no Docker-in-Docker in our containers)
# See: https://github.com/openclaw/openclaw/issues/4689
# Bug: Model requests host="sandbox" in exec tool calls, but configuredHost="gateway"
#      causes strict mismatch rejection. Config alone doesn't fix this.
# Fix: Patch OpenClaw source to skip the host mismatch check (allow any host).
#      With sandbox.mode=off, all exec runs on host regardless of requested host.
openclaw config set agents.defaults.sandbox.mode "off" 2>/dev/null || true
openclaw config set tools.exec.host "gateway" 2>/dev/null || true
# Bug #26496: tools.exec.security defaults to "allowlist" and minSecurity() picks the
# MORE restrictive of tools.exec.security vs exec-approvals.json — so we must set BOTH.
# "full" = allow all exec commands without approval prompts.
openclaw config set tools.exec.security "full" 2>/dev/null || true
openclaw config set tools.exec.ask "off" 2>/dev/null || true

# Note: exec host patch (bug #4689) applied at Docker build time in Dockerfile

# Step 5c: Exec approvals — security=full means ALL exec commands auto-approved
# Without this, every exec call waits 120s for manual approval (timeout)
# See: https://docs.openclaw.ai/tools/exec-approvals
APPROVALS_FILE="$HOME/.openclaw/exec-approvals.json"
mkdir -p "$(dirname "$APPROVALS_FILE")"
cat > "$APPROVALS_FILE" << 'APPROVALS_EOF'
{
  "version": 1,
  "defaults": {
    "security": "full",
    "ask": "off",
    "askFallback": "full",
    "autoAllowSkills": true
  },
  "agents": {}
}
APPROVALS_EOF
echo "[entrypoint] Exec approvals: security=full, ask=off (all commands auto-approved)"

# Step 6: DISABLE OpenClaw native IRC plugin (buggy — exits 2ms after connecting)
# IRC is handled by the Python daemon started above.
openclaw config set channels.irc.enabled false 2>/dev/null || true

# Step 7: Gateway mode (local, loopback)
openclaw config set gateway.port 18790 2>/dev/null || true
openclaw config set gateway.mode "local" 2>/dev/null || true
openclaw config set gateway.bind "loopback" 2>/dev/null || true

echo "[entrypoint] OpenClaw configured. Starting gateway for $AGENT_NAME"

# ── Shutdown handler ─────────────────────────────────────────────────
# Clean up IRC daemon when container stops
cleanup() {
    echo "[entrypoint] Shutting down..."
    if [ -n "$IRC_DAEMON_PID" ] && kill -0 "$IRC_DAEMON_PID" 2>/dev/null; then
        kill "$IRC_DAEMON_PID" 2>/dev/null || true
        wait "$IRC_DAEMON_PID" 2>/dev/null || true
    fi
    rm -f /app/data/irc-daemon.pid
}
trap cleanup SIGTERM SIGINT

# Launch gateway in foreground (does NOT replace shell — we need trap to work)
openclaw gateway run --port 18790 --auth none --bind loopback &
GATEWAY_PID=$!
echo "[entrypoint] OpenClaw gateway started (PID: $GATEWAY_PID)"

# Wait for either process to exit
wait -n $IRC_DAEMON_PID $GATEWAY_PID 2>/dev/null || true
echo "[entrypoint] A process exited. Cleaning up..."
cleanup
