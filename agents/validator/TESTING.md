# Testing the Validator Agent

Step-by-step guide to test the Validator Agent.

## Quick Test (No Setup Required)

Test the validator logic without needing OpenAI API or running the server:

```bash
cd validator
python test_validator.py --quick
```

This will show you a mock validation result to understand the output format.

## Full Test (Requires Setup)

### Step 1: Install Dependencies

```bash
cd validator
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env and add:
# - OPENAI_API_KEY=your_openai_key_here
# - PRIVATE_KEY=your_validator_private_key (or leave empty for AWS Secrets)
```

**Required for testing:**
- `OPENAI_API_KEY` - Get from https://platform.openai.com/api-keys
- `PRIVATE_KEY` - Validator wallet key (or leave empty if using AWS Secrets)

**Already configured (no changes needed):**
- Contract addresses (Fuji testnet)
- RPC URL
- Chain ID

### Step 3: Start the Validator

```bash
python main.py
```

You should see:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Validator agent initialized: 0x1219eF...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Step 4: Test with Sample Data

Open a new terminal and run:

```bash
python test_validator.py --live
```

This will run 4 test cases:
1. ✅ High-quality chat logs (should get ~0.8 score, "approve")
2. ✅ Stream transcript (should get ~0.7-0.9 score)
3. ⚠️ Suspicious/malicious data (should get high fraud score, "reject")
4. ⚠️ Overpriced data (should get low price score)

## Manual Testing with cURL

### Test 1: Health Check

```bash
curl http://localhost:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "validator_address": "0x1219eF9484BF7E40E6479141B32634623d37d507",
  "chain_id": 43113,
  "validation_fee": "0.001 GLUE"
}
```

### Test 2: Get Agent Card (A2A Protocol)

```bash
curl http://localhost:8001/.well-known/agent-card
```

Expected response: JSON with agent identity, skills, and pricing.

### Test 3: Validate Data

```bash
curl -X POST http://localhost:8001/validate \
  -H "Content-Type: application/json" \
  -d '{
    "data_type": "chat_logs",
    "data_content": {
      "messages": [
        {"user": "alice", "text": "Hello!"},
        {"user": "bob", "text": "Hi Alice!"}
      ]
    },
    "seller_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
    "buyer_address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
    "price_glue": "0.01"
  }'
```

Expected response:
```json
{
  "validation_id": "val_1698765432_0x2C3e07",
  "quality_score": 0.7,
  "fraud_score": 0.1,
  "price_score": 0.8,
  "overall_score": 0.65,
  "recommendation": "approve",
  "reasoning": "Quality: ... | Fraud: ... | Price: ...",
  "timestamp": "2025-10-23T12:00:00Z",
  "tx_hash": "0xabc123..." or null
}
```

## Python Test Script

```python
import asyncio
import httpx

async def test_validator():
    async with httpx.AsyncClient() as client:
        # Test validation
        response = await client.post(
            "http://localhost:8001/validate",
            json={
                "data_type": "chat_logs",
                "data_content": {"messages": [{"text": "Hello"}]},
                "seller_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
                "buyer_address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA",
                "price_glue": "0.01"
            },
            timeout=60.0
        )

        if response.status_code == 200:
            result = response.json()
            print(f"Validation Score: {result['overall_score']:.2f}")
            print(f"Recommendation: {result['recommendation']}")
        else:
            print(f"Error: {response.status_code}")

asyncio.run(test_validator())
```

## Understanding Results

### Quality Score (0.0 - 1.0)
- **0.9-1.0**: Excellent - Complete, accurate, well-formatted data
- **0.7-0.9**: Good - Minor issues but usable
- **0.5-0.7**: Fair - Some quality concerns
- **< 0.5**: Poor - Significant quality issues

### Fraud Score (0.0 - 1.0)
- **0.0-0.2**: Low risk - No fraud indicators
- **0.2-0.5**: Medium risk - Some suspicious patterns
- **0.5-0.7**: High risk - Multiple red flags
- **> 0.7**: Very high risk - Likely fraud

### Price Score (0.0 - 1.0)
- **0.9-1.0**: Excellent value - Fair or underpriced
- **0.7-0.9**: Good value - Reasonable pricing
- **0.5-0.7**: Acceptable - Slightly overpriced
- **< 0.5**: Poor value - Significantly overpriced

### Overall Score
Weighted average:
- Quality: 50% weight
- Fraud: 30% weight (inverted - lower is better)
- Price: 20% weight

### Recommendations
- **approve**: Overall ≥ 0.8 AND fraud < 0.2
- **reject**: Overall < 0.5 OR fraud > 0.7
- **review**: Everything else

## Troubleshooting

### "Could not connect to validator"
- Make sure validator is running: `python main.py`
- Check it's listening on port 8001
- Try: `curl http://localhost:8001/health`

### "OpenAI API error"
- Check OPENAI_API_KEY in .env is valid
- Verify you have API credits
- Check OpenAI API status

### "Agent not registered"
- Validator needs AVAX for registration fee (0.005 AVAX)
- Get AVAX from faucet: https://faucet.avax.network/
- Check validator wallet has balance

### "Validation taking too long"
- CrewAI can take 30-60 seconds per validation
- This is normal for GPT-4o with multiple agents
- Increase timeout in test script if needed

### "Transaction failed"
- Validator needs AVAX for gas (~0.01 AVAX per validation)
- Check validator wallet balance
- Verify ValidationRegistry contract is correct

## Performance Testing

### Test Concurrent Validations

```python
import asyncio
import httpx

async def validate(client, data_id):
    response = await client.post(
        "http://localhost:8001/validate",
        json={
            "data_type": "chat_logs",
            "data_content": {"id": data_id},
            "seller_address": "0x...",
            "buyer_address": "0x...",
            "price_glue": "0.01"
        },
        timeout=120.0
    )
    return response.json()

async def test_concurrent():
    async with httpx.AsyncClient() as client:
        tasks = [validate(client, i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        print(f"Completed {len(results)} validations")

asyncio.run(test_concurrent())
```

## Next Steps

After testing:
1. ✅ Verify all 4 test cases pass
2. ✅ Check validation scores make sense
3. ✅ Confirm on-chain submissions work
4. ✅ Monitor gas usage
5. 🔜 Deploy to production server
6. 🔜 Add API authentication
7. 🔜 Set up monitoring/alerts

## Monitoring

Watch logs while testing:

```bash
# Validator logs
tail -f validator.log

# Check validations on-chain
# Visit: https://testnet.snowtrace.io/address/0x9aF4590035C109859B4163fd8f2224b820d11bc2
# (ValidationRegistry contract)
```

---

**Questions?** Check `README.md` for full documentation.
