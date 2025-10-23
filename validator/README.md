# Validator Agent

Independent data quality verification service using CrewAI multi-agent validation.

## Overview

The Validator Agent provides trustless validation for data transactions in the Karmacadabra ecosystem. It analyzes data quality, detects fraud, and reviews pricing fairness using three specialized CrewAI crews.

**Key Features:**
- ✅ Quality validation using AI multi-agent crews
- ✅ Fraud detection and authenticity verification
- ✅ Price fairness review
- ✅ On-chain validation score submission (validator pays gas)
- ✅ FastAPI REST API
- ✅ A2A protocol compatible

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Validator Agent (FastAPI Server)                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Quality   │  │   Fraud    │  │   Price    │            │
│  │   Crew     │  │   Crew     │  │   Crew     │            │
│  │            │  │            │  │            │            │
│  │ • Analyst  │  │ • Detector │  │ • Analyst  │            │
│  │ • Checker  │  │ • Pattern  │  │ • Assessor │            │
│  │ • Validator│  │ • Verifier │  │ • Comparar │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└──────────────────────┬──────────────────────────────────────┘
                       │ Submit validation score
                       ▼
          ┌────────────────────────┐
          │  ValidationRegistry    │
          │  (Avalanche Fuji)      │
          │  Validator pays gas!   │
          └────────────────────────┘
```

## Quick Start

### 1. Installation

```bash
cd validator
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Edit .env with your configuration:
# - PRIVATE_KEY (validator wallet) or leave empty for AWS Secrets
# - OPENAI_API_KEY (for CrewAI)
# - Contract addresses (already configured for Fuji)
```

### 3. Run Validator

```bash
python main.py
```

The validator will start on `http://0.0.0.0:8001`

## API Endpoints

### Health Check

```bash
GET /
GET /health
```

Returns validator status and configuration.

### Agent Card (A2A Protocol)

```bash
GET /.well-known/agent-card
```

Returns A2A AgentCard with validator capabilities.

### Validate Data

```bash
POST /validate
Content-Type: application/json

{
  "data_type": "chat_logs",
  "data_content": {
    "messages": [...],
    "metadata": {...}
  },
  "seller_address": "0x...",
  "buyer_address": "0x...",
  "price_glue": "0.01",
  "metadata": {}
}
```

**Response:**

```json
{
  "validation_id": "val_1698765432_0x1219eF",
  "quality_score": 0.85,
  "fraud_score": 0.1,
  "price_score": 0.8,
  "overall_score": 0.78,
  "recommendation": "approve",
  "reasoning": "Quality: High-quality data with complete records | Fraud Check: No suspicious patterns | Price Review: Fair pricing | Overall Score: 0.78/1.0",
  "timestamp": "2025-10-23T10:30:00Z",
  "tx_hash": "0xabc123..."
}
```

## Validation Process

### 1. Quality Analysis

Three agents analyze data quality:
- **Quality Analyst**: Evaluates accuracy, consistency, format
- **Completeness Checker**: Identifies missing fields and gaps
- **Format Validator**: Checks schema compliance and structure

**Score**: 0.0 (poor) to 1.0 (excellent)

### 2. Fraud Detection

Three agents detect potential fraud:
- **Fraud Analyst**: Identifies scams, fake data, malicious content
- **Pattern Analyzer**: Detects statistical anomalies
- **Authenticity Checker**: Verifies genuine vs. AI-generated content

**Score**: 0.0 (no fraud) to 1.0 (definite fraud)

### 3. Price Review

Three agents review pricing fairness:
- **Price Analyst**: Evaluates pricing reasonableness
- **Value Assessor**: Assesses true data value
- **Market Comparator**: Compares against market benchmarks

**Score**: 0.0 (unfair) to 1.0 (very fair)

### 4. Overall Recommendation

Weighted average of all scores:
- Quality: 50% weight (most important)
- Fraud: 30% weight (inverse - lower is better)
- Price: 20% weight

**Recommendations:**
- `approve`: Overall score ≥ 0.8 AND fraud < 0.2
- `reject`: Overall score < 0.5 OR fraud > 0.7
- `review`: Everything in between

### 5. On-Chain Submission

The validator submits the validation score to `ValidationRegistry` on Avalanche Fuji. **The validator pays gas for this transaction** (~0.01 AVAX per validation).

## Pricing

**Validation Fee**: 0.001 GLUE per validation

## Wallet Information

**Validator Wallet**: `0x1219eF9484BF7E40E6479141B32634623d37d507`
- **Balance**: 55,000 GLUE
- **Purpose**: Pay gas for on-chain validation submissions

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PRIVATE_KEY` | Validator wallet private key (or use AWS Secrets) | Yes |
| `OPENAI_API_KEY` | OpenAI API key for CrewAI | Yes |
| `OPENAI_MODEL` | Model to use (default: gpt-4o) | No |
| `RPC_URL_FUJI` | Avalanche Fuji RPC endpoint | Yes |
| `CHAIN_ID` | Chain ID (43113 for Fuji) | Yes |
| `IDENTITY_REGISTRY` | Identity Registry address | Yes |
| `REPUTATION_REGISTRY` | Reputation Registry address | Yes |
| `VALIDATION_REGISTRY` | Validation Registry address | Yes |
| `GLUE_TOKEN_ADDRESS` | GLUE Token address | Yes |
| `HOST` | Server host (default: 0.0.0.0) | No |
| `PORT` | Server port (default: 8001) | No |
| `VALIDATION_FEE_GLUE` | Validation fee (default: 0.001) | No |

## Example Usage

### Python Client

```python
import httpx

async def validate_data(data):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/validate",
            json={
                "data_type": "chat_logs",
                "data_content": data,
                "seller_address": "0xSeller...",
                "buyer_address": "0xBuyer...",
                "price_glue": "0.01"
            }
        )
        return response.json()

# Usage
result = await validate_data({"messages": [...]})
print(f"Recommendation: {result['recommendation']}")
print(f"Overall Score: {result['overall_score']}")
```

### cURL

```bash
curl -X POST http://localhost:8001/validate \
  -H "Content-Type: application/json" \
  -d '{
    "data_type": "chat_logs",
    "data_content": {"messages": []},
    "seller_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
    "buyer_address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
    "price_glue": "0.01"
  }'
```

## Development

### Run in Development Mode

```bash
# With auto-reload
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### Testing

```bash
# Unit tests for crews
pytest tests/

# Integration test with sample data
python test_validator.py
```

## Architecture Details

### CrewAI Integration

Each validation crew uses the CrewAI framework with:
- **Multiple specialized agents** with distinct roles
- **Sequential process** for coordinated analysis
- **GPT-4o** for advanced reasoning
- **Structured output** parsing for scores and reasoning

### On-Chain Integration

The validator uses `ERC8004BaseAgent` from `shared/` to:
- Register on-chain with a unique agent ID
- Submit validation scores to `ValidationRegistry`
- Pay gas fees from the validator wallet
- Maintain reputation through successful validations

### A2A Protocol Compliance

Exposes an AgentCard at `/.well-known/agent-card` with:
- Agent identity and description
- Available skills (validate_data)
- Pricing information
- Input/output schemas

## Security Considerations

1. **Private Key Management**: Use AWS Secrets Manager or secure environment variables
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **API Authentication**: Consider adding API key auth for production
4. **Gas Management**: Monitor AVAX balance to ensure validator can submit validations
5. **OpenAI API**: Secure your OpenAI key and monitor usage

## Troubleshooting

### Validator Not Starting

- Check OPENAI_API_KEY is valid
- Verify private key is correct
- Ensure all contract addresses are set
- Check RPC endpoint is accessible

### Validation Failing

- Verify validator has AVAX for gas
- Check ValidationRegistry contract is deployed
- Ensure validator is registered on-chain
- Review logs for CrewAI errors

### Low Validation Scores

- Review crew prompts in `crews/` directory
- Adjust scoring weights in `main.py`
- Consider fine-tuning GPT model
- Add more sophisticated parsing logic

## Roadmap

- [ ] Add validation caching for repeated data
- [ ] Implement rate limiting
- [ ] Add API key authentication
- [ ] Support batch validations
- [ ] Add validation history tracking
- [ ] Implement dynamic pricing based on data size
- [ ] Add webhook notifications for validation results

## License

MIT

---

**Built with ❤️ by Ultravioleta DAO**
