#!/bin/bash
set -e

AGENT_NAME="${KK_AGENT_NAME:-unknown}"
WORKSPACE="/app/workspace"
SKILLS_DIR="/app/skills"

echo "[entrypoint] Setting up agent: $AGENT_NAME"

# Create workspace structure
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

# Start OpenClaw gateway (if installed) or run heartbeat loop
if command -v openclaw &> /dev/null; then
    exec openclaw --config /app/openclaw/agents/$AGENT_NAME/openclaw.json
else
    echo "[entrypoint] OpenClaw not found, running heartbeat loop"
    while true; do
        python3 /app/cron/heartbeat.py --agent "$AGENT_NAME" --workspaces "$WORKSPACE/.." --data-dir /app/data
        sleep 1800
    done
fi
