# KarmaCadabra Shared Vault

Obsidian vault for monitoring and coordinating 24 KK agents.

## Quick Start

1. Open this folder (`vault/`) as an Obsidian vault
2. Install the **Dataview** community plugin
3. Open `dashboards/agent-status.md` to see all agents

## Structure

- `agents/` — Per-agent state (24 agents, each with state.md + memory.md)
- `shared/` — Coordination files (config, supply chain, ledger, tasks)
- `knowledge/` — Reference docs (contracts, APIs, protocols)
- `dashboards/` — Dataview query dashboards
- `projects/` — Cross-project links (AbraCadabra, KarmaGelou, EM)

## For Agents

Agents update their `state.md` via `lib/vault_sync.py` on each heartbeat.
Each agent writes ONLY to its own `agents/<name>/` directory.

## For Humans

Open in Obsidian to get:
- Graph view of agent relationships
- Dataview tables showing live status
- Backlink navigation between agents and knowledge
- Search across all agent states and logs
