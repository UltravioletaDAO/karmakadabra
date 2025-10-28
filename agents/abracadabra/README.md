# Abracadabra Seller Agent

Stream transcription seller via x402 protocol with A2A discovery.

## Overview

The **Abracadabra Seller Agent** sells stream transcriptions through the Karmacadabra marketplace. It supports both local file testing and SQLite production data.

**Key Features:**
- FastAPI server with x402 payment protocol
- A2A protocol discovery (`.well-known/agent-card`)
- Local file fallback for testing
- SQLite integration for production
- Multi-tier pricing based on transcript length
- ERC-8004 on-chain registration

## Quick Start

### 1. Installation

```bash
cd abracadabra-agent
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
- `USE_LOCAL_FILES=false` - Use SQLite (production)

### 3. Run Server

```bash
python main.py
```

The seller will start on `http://0.0.0.0:8003`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               Abracadabra Seller Agent                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FastAPI Server                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Endpoints:                                            │ │
│  │  • GET  /                    - Health check           │ │
│  │  • GET  /health              - Detailed health        │ │
│  │  • GET  /.well-known/agent-card - A2A discovery       │ │
│  │  • POST /get_transcription   - Get transcript (x402)  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Data Sources (configurable):                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Testing: ../data/abracadabra/transcription_*.json    │ │
│  │  Production: SQLite (analytics.db)                    │ │
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
  "service": "Abracadabra Seller",
  "status": "healthy",
  "agent_id": "2",
  "address": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648",
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
  "agent_id": "2",
  "name": "Abracadabra Seller",
  "description": "Stream transcription seller - provides AI-transcribed audio from streams",
  "domain": "abracadabra.ultravioletadao.xyz",
  "wallet_address": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648",
  "skills": [
    {
      "name": "get_transcription",
      "description": "Get AI transcription for a specific stream or date",
      "pricing": {
        "currency": "GLUE",
        "base_price": "0.02",
        "price_per_segment": "0.001",
        "max_price": "300.0"
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

### Get Transcription

```bash
POST /get_transcription
Content-Type: application/json

{
  "stream_id": "stream_20251023_001",
  "date": "2025-10-23",
  "include_summary": true,
  "include_topics": true,
  "language": "en"
}
```

**Response:**
```json
{
  "stream_id": "stream_20251023_001",
  "duration_seconds": 7200,
  "language": "en",
  "transcript": [
    {
      "start": 0,
      "end": 15,
      "speaker": "host",
      "text": "Welcome everyone to today's stream! We're going to build trustless AI agents..."
    }
  ],
  "summary": "Stream covering the architecture and implementation of Karmacadabra...",
  "key_topics": ["Avalanche blockchain", "ERC-8004 Extended", "Gasless micropayments"],
  "metadata": {
    "source": "local_file",
    "filename": "transcription_20251023.json",
    "seller": "0x940DDDf6fB28E611b132FbBedbc4854CC7C22648",
    "timestamp": "2025-10-23T15:30:00Z"
  }
}
```

**Response Headers:**
```
X-Price: 0.035
X-Currency: GLUE
X-Segment-Count: 15
X-Duration: 7200
```

## Pricing

**Pricing Formula:**
```
price = BASE_PRICE + (PRICE_PER_SEGMENT × segment_count)
price = min(price, MAX_PRICE)
```

**Default Configuration:**
- Base price: 0.02 GLUE
- Per segment: 0.001 GLUE
- Max price: 300.0 GLUE

**Examples:**
- 10 segments: 0.02 + (0.001 × 10) = 0.03 GLUE
- 100 segments: 0.02 + (0.001 × 100) = 0.12 GLUE
- 1,000 segments: 0.02 + (0.001 × 1,000) = 1.02 GLUE

## Data Sources

### Local Files (Testing)

Located in `../data/abracadabra/`:

```
transcription_YYYYMMDD.json
{
  "stream_id": "stream_20251023_001",
  "duration_seconds": 7200,
  "language": "en",
  "transcript": [
    {
      "start": 0,
      "end": 15,
      "speaker": "host",
      "text": "Welcome everyone to today's stream! We're going to build trustless AI agents..."
    }
  ],
  "summary": "Stream covering the architecture and implementation of Karmacadabra...",
  "key_topics": ["Avalanche blockchain", "ERC-8004 Extended", "Gasless micropayments"],
  "metadata": {
    "transcription_method": "whisper_large_v3",
    "confidence_avg": 0.94
  }
}
```

### SQLite (Production)

**Database:** `analytics.db` (from `z:\ultravioleta\ai\cursor\abracadabra\`)

**Tables:**
- `transcriptions` - Complete transcriptions with metadata
- `segments` - Individual transcript segments
- `topics` - Extracted topics
- `analytics` - Engagement metrics

## Wallet Information

**Seller Wallet:** `0x940DDDf6fB28E611b132FbBedbc4854CC7C22648`
- **Balance:** 55,000 GLUE
- **Purpose:** Receive payments from buyers

## Integration Example

### Python Client

```python
import httpx

async def buy_transcription():
    async with httpx.AsyncClient() as client:
        # Discover seller
        agent_card = await client.get(
            "http://abracadabra.ultravioletadao.xyz/.well-known/agent-card"
        )
        print(f"Found seller: {agent_card.json()['name']}")

        # Get transcription
        response = await client.post(
            "http://abracadabra.ultravioletadao.xyz/get_transcription",
            json={
                "date": "2025-10-23",
                "include_summary": True,
                "include_topics": True
            }
        )

        transcription = response.json()
        price = response.headers.get("X-Price")

        print(f"Received {len(transcription['transcript'])} segments")
        print(f"Duration: {transcription['duration_seconds']} seconds")
        print(f"Price: {price} GLUE")

        return transcription
```

## Testing

### Quick Test (Mock Mode)

```bash
# Just run the server
python main.py

# In another terminal, test endpoints
curl http://localhost:8003/
curl http://localhost:8003/.well-known/agent-card
```

### Integration Test

```bash
# Test with sample data
curl -X POST http://localhost:8003/get_transcription \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-10-23",
    "include_summary": true
  }'
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIVATE_KEY` | Seller wallet private key | (from AWS Secrets) |
| `AGENT_DOMAIN` | Agent domain name | abracadabra.ultravioletadao.xyz |
| `RPC_URL_FUJI` | Avalanche Fuji RPC | publicnode.com |
| `CHAIN_ID` | Chain ID | 43113 (Fuji) |
| `GLUE_TOKEN_ADDRESS` | GLUE token address | 0x3D19A... |
| `IDENTITY_REGISTRY` | Identity Registry | 0xB0a405... |
| `FACILITATOR_URL` | x402 facilitator | facilitator.ultravioletadao.xyz |
| `USE_LOCAL_FILES` | Use local files vs SQLite | true |
| `LOCAL_DATA_PATH` | Path to local data files | ../data/abracadabra |
| `SQLITE_DB_PATH` | SQLite database path | analytics.db |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8003 |
| `BASE_PRICE` | Base price in GLUE | 0.02 |
| `PRICE_PER_SEGMENT` | Price per segment | 0.001 |
| `MAX_PRICE` | Maximum price | 300.0 |

## Troubleshooting

### "Agent not registered"
- Run registration: `python scripts/register_seller.py`
- Or manually register via ERC-8004 Identity Registry

### "No transcriptions found"
- Check `LOCAL_DATA_PATH` points to correct directory
- Verify sample data files exist in `../data/abracadabra/`
- Try specifying a specific date: `{"date": "2025-10-23"}`

### "SQLite connection failed"
- Check `SQLITE_DB_PATH` is correct
- Ensure SQLite database exists
- For testing, use `USE_LOCAL_FILES=true` instead

### "Insufficient balance"
- Seller wallet needs GLUE for operations
- Check balance: `curl http://localhost:8003/health`
- Fund wallet from GLUE token contract

## Roadmap

- [ ] x402 payment middleware integration
- [ ] Validation request before data delivery
- [ ] Multi-tier service offerings (summary, topics, clips)
- [ ] Rate limiting
- [ ] API key authentication
- [ ] Webhook notifications for purchases

## License

MIT

---

**Built with ❤️ by Ultravioleta DAO**
