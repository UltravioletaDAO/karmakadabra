#!/bin/bash
# vault_sync_cron.sh — Sync agent vault state via git
# Run via cron every 60 seconds on each EC2 agent container
#
# Usage: vault_sync_cron.sh <vault_dir> <agent_name>

VAULT_DIR="${1:-/app/vault}"
AGENT_NAME="${2:-${KK_AGENT_NAME:-unknown}}"
LOCK_FILE="/tmp/vault-sync.lock"

# Prevent concurrent syncs
if [ -f "$LOCK_FILE" ]; then
    # Check if lock is stale (>2 min old)
    if [ "$(find "$LOCK_FILE" -mmin +2 2>/dev/null)" ]; then
        rm -f "$LOCK_FILE"
    else
        exit 0
    fi
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$VAULT_DIR" || exit 1

# Skip if not a git repo
if [ ! -d ".git" ]; then
    exit 0
fi

# Configure git identity if not set
git config user.name "$AGENT_NAME" 2>/dev/null
git config user.email "${AGENT_NAME}@karmacadabra.ultravioletadao.xyz" 2>/dev/null

# Pull remote changes (prefer theirs on shared/ conflicts to avoid blocking)
git fetch origin main --quiet 2>/dev/null
git merge origin/main --strategy-option=theirs --no-edit --quiet 2>/dev/null || true

# Stage agent's own files + shared
git add "agents/$AGENT_NAME/" "shared/" --quiet 2>/dev/null

# Commit if there are changes
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "sync: $AGENT_NAME $(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet 2>/dev/null
    git push origin main --quiet 2>/dev/null || true
fi
