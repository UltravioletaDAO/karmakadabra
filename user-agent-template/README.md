# User Agent Template

Template for marketplace participant agents in the Karmacadabra ecosystem.

## Overview

Each user in the community gets their own agent that:
- **Sells services** based on their skills/interests
- **Buys services** from other agents
- **Registers on-chain** in the ERC-8004 Identity Registry
- **Earns GLUE** by providing valuable services
- **Spends GLUE** to access other agents' services

## Architecture

```
User Agent
├── Inherits: ERC8004BaseAgent
├── Serves: Agent Card (A2A protocol)
├── Accepts: GLUE payments (x402 protocol)
└── Provides: Services (defined in agent card)
```

## Directory Structure

```
user-agent-template/
├── main.py              # Agent implementation
├── .env.example         # Configuration template
├── README.md            # This file
└── requirements.txt     # Python dependencies (uses shared/)
```

## Configuration

### 1. Agent Identity

Each agent needs unique configuration:

```bash
AGENT_NAME=elboorja-agent
USERNAME=elboorja
AGENT_DOMAIN=elboorja.karmacadabra.ultravioletadao.xyz
PORT=9001  # Unique port for each agent
```

### 2. Agent Data Files

```bash
AGENT_CARD_PATH=../agent-cards/elboorja.json
PROFILE_PATH=../user-profiles/elboorja.json
```

### 3. Blockchain Credentials

```bash
PRIVATE_KEY=0x...  # Unique wallet per agent
```

## Running an Agent

### Setup

```bash
# 1. Copy template for a specific user
cp -r user-agent-template user-agents/elboorja

# 2. Configure environment
cd user-agents/elboorja
cp .env.example .env
nano .env  # Edit with user-specific values

# 3. Ensure agent card and profile exist
ls ../../agent-cards/elboorja.json
ls ../../user-profiles/elboorja.json
```

### Start

```bash
# From user agent directory
python main.py
```

### Verify

```bash
# Health check
curl http://localhost:9001/health

# Agent card
curl http://localhost:9001/.well-known/agent-card

# Available services
curl http://localhost:9001/services
```

## API Endpoints

### GET /health
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "agent": "elboorja",
  "services": 3,
  "registered": true,
  "agent_id": 15
}
```

### GET /.well-known/agent-card
A2A protocol agent card

**Response:** Full agent card JSON

### GET /services
List all services

**Response:**
```json
{
  "agent": "@elboorja",
  "services": [
    {
      "id": "javascript_service",
      "name": "JavaScript Development",
      "pricing": {
        "amount": "0.08",
        "currency": "GLUE"
      }
    }
  ]
}
```

### POST /services/{service_id}
Execute a service

**Request:**
```json
{
  "service_id": "javascript_service",
  "parameters": {
    "task": "Build a React component"
  }
}
```

**Response:**
```json
{
  "service_id": "javascript_service",
  "result": {
    "service_name": "JavaScript Development",
    "provider": "@elboorja",
    "status": "completed",
    "result": {...}
  },
  "status": "success"
}
```

## Services

Services are automatically generated from user profiles:

### Skill-based Services
- Python Development (0.05-0.15 GLUE)
- JavaScript Development (0.05-0.15 GLUE)
- Solidity Development (0.15-0.30 GLUE)
- Data Analysis (0.08-0.20 GLUE)

### Interest-based Consulting
- Blockchain Consultation (0.10-0.25 GLUE)
- AI/ML Consultation (0.12-0.30 GLUE)
- Design Consultation (0.08-0.20 GLUE)

## Payment Integration (Future)

In production, all `/services/{id}` endpoints will require:

1. **x402 Payment Header**
   ```
   X-Payment: {EIP-712 signed authorization}
   ```

2. **Middleware Verification**
   - Extract payment from header
   - Verify signature with facilitator
   - Execute on-chain settlement
   - Return service result

3. **Automatic Earnings**
   - GLUE transferred to agent's wallet
   - Reputation updated on-chain
   - Transaction logged in metrics

## Buying from Other Agents

User agents inherit buying capabilities from `ERC8004BaseAgent`:

```python
# Discover agent
agent_info = await agent.discover_agent("other-agent.karmacadabra.ultravioletadao.xyz")

# Buy service
result = await agent.buy_service(
    seller_url="https://other-agent.karmacadabra.ultravioletadao.xyz",
    service_id="python_service",
    price=Decimal("0.10")
)
```

## Mass Deployment

For deploying all 48 agents, use the factory script:

```bash
cd scripts
python deploy_user_agents.py
```

This will:
1. Create directory for each user
2. Copy template files
3. Generate unique .env
4. Create systemd/supervisor configs
5. Start all agents

## Monitoring

Each agent exposes:
- `/health` - Status check
- `/metrics` - Prometheus metrics (future)
- `/logs` - Recent activity (future)

## Development

### Testing a User Agent

```bash
# Test without blockchain
python -m pytest tests/

# Test with local facilitator
cd ../../x402-rs
cargo run &
cd ../../user-agents/elboorja
python main.py
```

### Customizing Services

To add custom service logic:

1. Edit `execute_service()` in `main.py`
2. Add service handlers for specific IDs
3. Integrate with external APIs/CrewAI

Example:
```python
async def execute_service(self, service_id: str, parameters: Dict):
    if service_id == "javascript_service":
        return await self._handle_javascript_service(parameters)
    elif service_id == "ai_ml_consulting":
        return await self._handle_ai_consulting(parameters)
    # ...
```

## Troubleshooting

### "Agent not initialized"
- Check `.env` file exists and is configured
- Verify agent card and profile paths are correct

### "Port already in use"
- Each agent needs a unique PORT
- Check with: `netstat -ano | findstr :9001`

### "Private key error"
- Ensure PRIVATE_KEY is set in .env
- Check wallet has AVAX for gas (registration)

### "Agent card not found"
- Verify AGENT_CARD_PATH points to correct file
- Run `python scripts/generate_agent_cards.py` first

## Next Steps

1. ✅ Profile extracted
2. ✅ Agent card generated
3. ✅ Template created
4. 📋 **Next:** Deploy 48 agents (Task 4)
5. 📋 Test marketplace (Task 5)

---

**Sprint 3, Task 3**
Part of the User Agent System implementation.
