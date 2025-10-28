# Karma-Hello Seller Agent

Twitch chat log seller via x402 protocol with A2A discovery.

## Overview

The **Karma-Hello Seller Agent** sells Twitch stream chat logs through the Karmacadabra marketplace. It supports both local file testing and MongoDB production data.

**Key Features:**
- FastAPI server with x402 payment protocol
- A2A protocol discovery (`.well-known/agent-card`)
- Local file fallback for testing
- MongoDB integration for production
- Multi-tier pricing based on data volume
- ERC-8004 on-chain registration

## Quick Start

### 1. Installation

```bash
cd karma-hello-agent
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required configuration:**
- `PRIVATE_KEY` - Seller wallet private key (or leave empty for AWS Secrets)
- `AGENT_DOMAIN` - Your agent's domain name
- Contract addresses (already configured for Fuji testnet)

**Optional configuration:**
- `USE_LOCAL_FILES=true` - Use sample data files (default for testing)
- `USE_LOCAL_FILES=false` - Use MongoDB (production)

### 3. Run Server

```bash
python main.py
```

The seller will start on `http://0.0.0.0:8002`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Karma-Hello Seller Agent                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FastAPI Server                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Endpoints:                                            │ │
│  │  • GET  /                    - Health check           │ │
│  │  • GET  /health              - Detailed health        │ │
│  │  • GET  /.well-known/agent-card - A2A discovery       │ │
│  │  • POST /get_chat_logs       - Get logs (x402)        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Data Sources (configurable):                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Testing: ../data/karma-hello/chat_logs_*.json        │ │
│  │  Production: MongoDB (karma_hello.chat_logs)          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Payment: x402 + EIP-3009 (gasless)                         │
│  Blockchain: Avalanche Fuji (Chain ID: 43113)               │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Health Check

```bash
GET /
GET /health
```

**Response:**
```json
{
  "service": "Karma-Hello Seller",
  "status": "healthy",
  "agent_id": "1",
  "address": "0x2C3e071df446B25B821F59425152838ae4931E75",
  "balance": "55000.0 GLUE",
  "data_source": "local_files"
}
```

### Agent Card (A2A Discovery)

```bash
GET /.well-known/agent-card
```

**Response:**
```json
{
  "schema_version": "1.0.0",
  "agent_id": "1",
  "name": "Karma-Hello Seller",
  "description": "Twitch chat log seller - provides historical chat data from streams",
  "domain": "karma-hello.ultravioletadao.xyz",
  "wallet_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
  "skills": [
    {
      "name": "get_chat_logs",
      "description": "Get Twitch chat logs for a specific stream or date range",
      "pricing": {
        "currency": "GLUE",
        "base_price": "0.01",
        "price_per_message": "0.0001",
        "max_price": "200.0"
      }
    }
  ],
  "payment_methods": [
    {
      "protocol": "x402",
      "token": {
        "symbol": "GLUE",
        "address": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"
      }
    }
  ]
}
```

### Get Chat Logs

```bash
POST /get_chat_logs
Content-Type: application/json

{
  "stream_id": "stream_20251023_001",
  "date": "2025-10-23",
  "users": ["alice_crypto", "bob_dev"],
  "limit": 1000,
  "include_stats": true
}
```

**Response:**
```json
{
  "stream_id": "stream_20251023_001",
  "stream_date": "2025-10-23",
  "total_messages": 156,
  "unique_users": 23,
  "messages": [
    {
      "timestamp": "2025-10-23T14:00:00Z",
      "user": "alice_crypto",
      "message": "Hello everyone! Excited for today's stream!",
      "user_badges": ["subscriber"]
    }
  ],
  "statistics": {
    "messages_per_minute": 1.3,
    "most_active_users": ["alice_crypto", "bob_dev", "eve_researcher"]
  },
  "metadata": {
    "source": "local_file",
    "filename": "chat_logs_20251023.json",
    "seller": "0x2C3e071df446B25B821F59425152838ae4931E75",
    "timestamp": "2025-10-23T15:30:00Z"
  }
}
```

**Response Headers:**
```
X-Price: 0.0156
X-Currency: GLUE
X-Message-Count: 156
```

## Pricing

**Pricing Formula:**
```
price = BASE_PRICE + (PRICE_PER_MESSAGE × message_count)
price = min(price, MAX_PRICE)
```

**Default Configuration:**
- Base price: 0.01 GLUE
- Per message: 0.0001 GLUE
- Max price: 200.0 GLUE

**Examples:**
- 100 messages: 0.01 + (0.0001 × 100) = 0.02 GLUE
- 1000 messages: 0.01 + (0.0001 × 1000) = 0.11 GLUE
- 10,000 messages: 0.01 + (0.0001 × 10,000) = 1.01 GLUE

## Data Sources

### Local Files (Testing)

Located in `../data/karma-hello/`:

```
chat_logs_YYYYMMDD.json
{
  "stream_id": "stream_20251023_001",
  "stream_date": "2025-10-23",
  "stream_title": "Building Trustless AI Agents on Avalanche",
  "total_messages": 156,
  "unique_users": 23,
  "messages": [
    {
      "timestamp": "2025-10-23T14:00:00Z",
      "user": "alice_crypto",
      "message": "Hello everyone! Excited for today's stream!",
      "user_badges": ["subscriber"]
    }
  ],
  "statistics": {
    "messages_per_minute": 1.3,
    "most_active_users": ["alice_crypto", "bob_dev", "eve_researcher"]
  }
}
```

### MongoDB (Production)

**Database:** `karma_hello`
**Collection:** `chat_logs`

**Document Schema:**
```json
{
  "stream_id": "string",
  "stream_date": "YYYY-MM-DD",
  "stream_title": "string",
  "total_messages": "number",
  "unique_users": "number",
  "messages": [
    {
      "timestamp": "ISO 8601",
      "user": "string",
      "message": "string",
      "user_badges": ["array"],
      "color": "hex string"
    }
  ],
  "statistics": {}
}
```

## Wallet Information

**Seller Wallet:** `0x2C3e071df446B25B821F59425152838ae4931E75`
- **Balance:** 55,000 GLUE
- **Purpose:** Receive payments from buyers

## Integration Example

### Python Client

```python
import httpx

async def buy_chat_logs():
    async with httpx.AsyncClient() as client:
        # Discover seller
        agent_card = await client.get(
            "http://karma-hello.ultravioletadao.xyz/.well-known/agent-card"
        )
        print(f"Found seller: {agent_card.json()['name']}")

        # Get chat logs
        response = await client.post(
            "http://karma-hello.ultravioletadao.xyz/get_chat_logs",
            json={
                "date": "2025-10-23",
                "limit": 1000
            }
        )

        logs = response.json()
        price = response.headers.get("X-Price")

        print(f"Received {logs['total_messages']} messages")
        print(f"Price: {price} GLUE")

        return logs
```

## Testing

### Quick Test (Mock Mode)

```bash
# Just run the server
python main.py

# In another terminal, test endpoints
curl http://localhost:8002/
curl http://localhost:8002/.well-known/agent-card
```

### Integration Test

```bash
# Test with sample data
curl -X POST http://localhost:8002/get_chat_logs \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-10-23",
    "limit": 100
  }'
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIVATE_KEY` | Seller wallet private key | (from AWS Secrets) |
| `AGENT_DOMAIN` | Agent domain name | karma-hello.ultravioletadao.xyz |
| `RPC_URL_FUJI` | Avalanche Fuji RPC | publicnode.com |
| `CHAIN_ID` | Chain ID | 43113 (Fuji) |
| `GLUE_TOKEN_ADDRESS` | GLUE token address | 0x3D19A... |
| `IDENTITY_REGISTRY` | Identity Registry | 0xB0a405... |
| `FACILITATOR_URL` | x402 facilitator | facilitator.ultravioletadao.xyz |
| `USE_LOCAL_FILES` | Use local files vs MongoDB | true |
| `LOCAL_DATA_PATH` | Path to local data files | ../data/karma-hello |
| `MONGO_URI` | MongoDB connection string | mongodb://localhost:27017 |
| `MONGO_DB` | MongoDB database name | karma_hello |
| `MONGO_COLLECTION` | MongoDB collection name | chat_logs |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8002 |
| `BASE_PRICE` | Base price in GLUE | 0.01 |
| `PRICE_PER_MESSAGE` | Price per message | 0.0001 |
| `MAX_PRICE` | Maximum price | 200.0 |

## Troubleshooting

### "Agent not registered"
- Run registration: `python scripts/register_seller.py`
- Or manually register via ERC-8004 Identity Registry

### "No chat logs found"
- Check `LOCAL_DATA_PATH` points to correct directory
- Verify sample data files exist in `../data/karma-hello/`
- Try specifying a specific date: `{"date": "2025-10-23"}`

### "MongoDB connection failed"
- Check `MONGO_URI` is correct
- Ensure MongoDB is running
- For testing, use `USE_LOCAL_FILES=true` instead

### "Insufficient balance"
- Seller wallet needs GLUE for operations
- Check balance: `curl http://localhost:8002/health`
- Fund wallet from GLUE token contract

## Roadmap

- [ ] x402 payment middleware integration
- [ ] Validation request before data delivery
- [ ] Multi-tier service offerings
- [ ] Rate limiting
- [ ] API key authentication
- [ ] Webhook notifications for purchases

## License

MIT

---

**Built with ❤️ by Ultravioleta DAO**
