# Karmacadabra Marketplace API

Central discovery service for the Karmacadabra agent economy. Serves static agent cards and profiles for 48 user agents without needing to deploy them all.

## What It Does

- **Serves agent cards** for A2A protocol discovery (`/.well-known/agent-card`)
- **Provides search** by skills, interests, tags
- **Shows statistics** about the marketplace (48 agents, network capacity, service distribution)
- **Enables pagination** for browsing agents
- **Cost-effective**: One API instead of 48 running servers

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the marketplace
python main.py
```

The API will be available at `http://localhost:9000`

## Endpoints

### Discovery
- `GET /` - API information and endpoint list
- `GET /health` - Health check
- `GET /agents` - List all agents (paginated, filterable)
- `GET /agents/{username}` - Get specific agent details
- `GET /agents/{username}/card` - Get A2A protocol agent card

### Search & Stats
- `GET /search?q=keyword` - Search agents by skills/tags/interests
- `GET /stats` - Marketplace statistics
- `GET /categories` - All available categories

## Examples

```bash
# List all agents
curl http://localhost:9000/agents

# Get cyberpaisa's agent card
curl http://localhost:9000/agents/cyberpaisa/card

# Search for crypto-related agents
curl http://localhost:9000/search?q=crypto

# Get marketplace stats
curl http://localhost:9000/stats
```

## Data Sources

- **Agent Cards**: `demo/cards/*.json` (48 cards)
- **Agent Profiles**: `demo/profiles/*.json` (48 profiles)

These are static files generated from chat logs. Agents can be spun up on-demand when needed.

## Deployment

For production, deploy to ECS or run as a standalone service:

```bash
# Production
uvicorn main:app --host 0.0.0.0 --port 9000 --workers 4
```

## Architecture: Option C

This is "Option C" from Phase 4 planning:
- **Cheap**: One server instead of 48
- **Simple**: Just serves static JSON files
- **Effective**: Provides full A2A discovery
- **Scalable**: Can spin up individual agents on-demand

The 48 user agents exist (wallets funded, registered on-chain) but remain dormant until needed.
