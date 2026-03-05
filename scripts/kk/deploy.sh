#!/bin/bash
# scripts/kk/deploy.sh — Unified deploy script for KarmaCadabra swarm
# Usage:
#   bash scripts/kk/deploy.sh local              # Start local swarm
#   bash scripts/kk/deploy.sh local --build      # Rebuild + start
#   bash scripts/kk/deploy.sh local --down       # Stop
#   bash scripts/kk/deploy.sh local --logs       # Tail logs
#   bash scripts/kk/deploy.sh local --status     # Container status
#   bash scripts/kk/deploy.sh local --clean      # Stop + remove volumes
#   bash scripts/kk/deploy.sh remote             # Deploy to EC2 (existing)

set -euo pipefail

DEPLOY_TYPE="${1:-}"
SUBCOMMAND="${2:-}"

if [ -z "$DEPLOY_TYPE" ]; then
    echo "Usage: bash scripts/kk/deploy.sh <local|remote> [--build|--down|--logs|--status|--clean]"
    exit 1
fi

# ── Local Mode ──────────────────────────────────────────────────────
deploy_local() {
    local COMPOSE_CMD="docker compose -f docker-compose.local.yml"

    # Check env files exist
    if [ ! -f .env.local ]; then
        echo "[ERROR] .env.local not found. Copy from template:"
        echo "  cp .env.local.example .env.local"
        echo "  # Edit KK_LLM_BASE_URL with your Mac Mini IP"
        exit 1
    fi
    if [ ! -f .env.secrets ]; then
        echo "[ERROR] .env.secrets not found. Extract from AWS or fill manually:"
        echo "  bash scripts/kk/export_secrets_local.sh"
        echo "  # Or: cp .env.secrets.example .env.secrets && fill keys"
        exit 1
    fi

    COMPOSE_CMD="$COMPOSE_CMD --env-file .env.local --env-file .env.secrets"

    case "${SUBCOMMAND}" in
        --build)
            echo "[deploy] Building and starting 9 agents (local)..."
            $COMPOSE_CMD up -d --build
            echo "[deploy] Done. Check status: bash scripts/kk/deploy.sh local --status"
            ;;
        --down)
            echo "[deploy] Stopping local swarm..."
            $COMPOSE_CMD down
            echo "[deploy] Stopped."
            ;;
        --logs)
            $COMPOSE_CMD logs -f --tail 50
            ;;
        --status)
            $COMPOSE_CMD ps -a
            ;;
        --clean)
            echo "[deploy] Stopping and removing volumes..."
            $COMPOSE_CMD down -v
            echo "[deploy] Cleaned."
            ;;
        "")
            echo "[deploy] Starting 9 agents (local)..."
            $COMPOSE_CMD up -d
            echo "[deploy] Done. Check status: bash scripts/kk/deploy.sh local --status"
            ;;
        *)
            echo "[ERROR] Unknown subcommand: $SUBCOMMAND"
            echo "Valid: --build, --down, --logs, --status, --clean"
            exit 1
            ;;
    esac
}

# ── Remote Mode ─────────────────────────────────────────────────────
deploy_remote() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/restart_all_agents.sh" ]; then
        echo "[deploy] Delegating to restart_all_agents.sh..."
        bash "$SCRIPT_DIR/restart_all_agents.sh"
    else
        echo "[ERROR] restart_all_agents.sh not found in $SCRIPT_DIR"
        exit 1
    fi
}

# ── Dispatch ────────────────────────────────────────────────────────
case "$DEPLOY_TYPE" in
    local)
        deploy_local
        ;;
    remote)
        deploy_remote
        ;;
    *)
        echo "[ERROR] Unknown deploy type: $DEPLOY_TYPE (use 'local' or 'remote')"
        exit 1
        ;;
esac
