# Client Agent

Generic data buyer for the Karmacadabra marketplace.

## Overview

The Client Agent is a reference implementation showing how buyers interact with the data marketplace. It demonstrates:

- **Seller Discovery** via A2A protocol
- **Data Purchase** using x402 payments
- **Validation Requests** from validator agents
- **Data Storage** and organization
- **Seller Rating** via ERC-8004

**Wallet**: `0xCf30021812F27132d36dc791E0eC17f34B4eE8BA`  
**Balance**: 55,000 GLUE  
**Purpose**: Generic buyer (no selling, only buying)

## Quick Start

### 1. Install Dependencies

```bash
cd client-agent
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required:**
- `PRIVATE_KEY` - Client wallet private key (or leave empty for AWS Secrets)

**Optional (already configured):**
- Contract addresses
- Validator URL
- Max price limits

### 3. Run Demo

```bash
python main.py
```

## Usage

### Discover Sellers

```python
from main import ClientAgent, CONFIG

client = ClientAgent(CONFIG)

# Discover seller via A2A
agent_card = await client.discover_seller("https://seller.example.com")
print(f"Found: {agent_card.name}")
print(f"Skills: {[s.name for s in agent_card.skills]}")
```

### Request Validation

```python
# After purchasing data
validation = await client.request_validation(
    data=purchased_data,
    data_type="chat_logs",
    seller_address="0x...",
    price_glue="0.01"
)

if validation:
    print(f"Score: {validation['overall_score']}")
    print(f"Recommendation: {validation['recommendation']}")
```

### Save Purchased Data

```python
# Automatically saves to ./purchased_data/
client.save_data(
    seller_url="https://seller.example.com",
    data={"messages": [...]}
)
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRIVATE_KEY` | Client wallet private key | (AWS Secrets) |
| `MAX_PRICE_GLUE` | Maximum price willing to pay | 1.0 GLUE |
| `REQUEST_VALIDATION` | Auto-request validation | true |
| `MIN_VALIDATION_SCORE` | Minimum acceptable score | 0.7 |
| `DATA_DIR` | Where to save purchased data | ./purchased_data |
| `VALIDATOR_URL` | Validator agent URL | localhost:8001 |

### Known Sellers

Configure seller URLs in `.env`:
- `KARMA_HELLO_URL` - Twitch chat log seller
- `ABRACADABRA_URL` - Stream transcript seller

## Features

### 1. A2A Discovery

Automatically discovers seller capabilities:

```
GET https://seller.example.com/.well-known/agent-card

Response:
{
  "agentId": "seller-0x...",
  "name": "Karma-Hello Seller",
  "skills": [
    {
      "name": "get_chat_logs",
      "pricing": {"amount": "0.01", "currency": "GLUE"}
    }
  ]
}
```

### 2. x402 Payments

Gasless payments using EIP-712 signatures:
1. Client signs payment authorization off-chain
2. Sends to seller with X-Payment header
3. Facilitator verifies and executes on-chain
4. Client pays 0 gas!

### 3. Optional Validation

Request independent validation:
- Quality check
- Fraud detection
- Price review
- Overall recommendation

### 4. Data Management

Organized storage:
```
purchased_data/
├── karma-hello_20251023_120000.json
├── abracadabra_20251023_120130.json
└── ...
```

Each file contains:
- Seller info
- Purchase timestamp
- Data content

## Purchase Flow

```
1. Discover Seller
   └─> GET /.well-known/agent-card
   
2. Check Price
   └─> Verify <= MAX_PRICE_GLUE
   
3. Purchase Data
   └─> POST /api/endpoint + X-Payment header
   
4. Validate (Optional)
   └─> POST validator/validate
   
5. Save Data
   └─> Write to purchased_data/
   
6. Rate Seller (Optional)
   └─> Submit rating on-chain
```

## Examples

### Example 1: Buy Chat Logs

```python
# Discover Karma-Hello
card = await client.discover_seller("https://karma-hello.ultravioletadao.xyz")

# Find chat logs skill
skill = [s for s in card.skills if s.name == "get_chat_logs"][0]
price = skill.pricing.amount

# Purchase
# (Actual x402 integration coming in next sprint)
```

### Example 2: Buy with Validation

```python
# Buy data
data = await client.buy_data(
    seller_url="https://seller.example.com",
    seller_address="0x...",
    endpoint="/api/data",
    price_glue="0.01"
)

# Validate
validation = await client.request_validation(
    data=data,
    data_type="chat_logs",
    seller_address="0x...",
    price_glue="0.01"
)

# Check score
if validation['overall_score'] >= 0.7:
    print("Good quality data!")
else:
    print("Quality issues detected")
```

## Wallet Information

**Address**: `0xCf30021812F27132d36dc791E0eC17f34B4eE8BA`  
**Balance**: 55,000 GLUE  
**Network**: Avalanche Fuji (Chain ID: 43113)

Get testnet AVAX: https://faucet.avax.network/

## Troubleshooting

### "Seller not responding"
- Check seller URL is correct
- Verify seller service is running
- Check network connectivity

### "Price too high"
- Adjust MAX_PRICE_GLUE in .env
- Or negotiate with seller

### "Validation failed"
- Check VALIDATOR_URL is correct
- Verify validator is running
- Increase timeout if needed

## Roadmap

- [ ] Full x402 payment integration
- [ ] Automatic seller rating
- [ ] Data caching/deduplication
- [ ] Purchase history tracking
- [ ] Multi-seller comparison
- [ ] Batch purchases
- [ ] CLI interface

## License

MIT

---

**Built with ❤️ by Ultravioleta DAO**
