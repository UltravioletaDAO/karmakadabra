# Test Seller Solana - x402 Payment System

Test service that sells "Hello World" messages for 0.01 USDC on **Solana mainnet** using x402 payment protocol.

## Architecture

```
Buyer (SPL Token) → Test Seller (FastAPI) → Facilitator (x402-rs) → Solana
```

- **Network**: Solana mainnet
- **Asset**: USDC (EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v)
- **Price**: 0.01 USDC per message
- **Protocol**: x402 (exact payment scheme)

## Setup

### 1. Generate Seller Keypair

The seller needs a Solana keypair to receive payments:

```bash
# Generate keypair
solana-keygen new --outfile seller_keypair.json

# Get public key
solana-keygen pubkey seller_keypair.json
```

### 2. Deploy Test Seller

Set environment variables and deploy to AWS ECS:

```bash
# Set seller public key
export SELLER_PUBKEY="<your_solana_public_key>"

# Deploy to ECS
cd test-seller-solana
chmod +x deploy.sh
./deploy.sh
```

The service will be available at:
```
https://test-seller-solana.karmacadabra.ultravioletadao.xyz
```

### 3. Generate Buyer Keypair

Buyers need a Solana keypair with SOL and USDC:

```bash
# Install dependencies
pip install -r requirements_loadtest.txt

# Generate keypair
python generate_keypair.py

# This creates: buyer_keypair.json
# Public key will be printed to console
```

### 4. Fund Buyer Wallet

The buyer needs:
- **SOL** for transaction fees (~0.000005 SOL per transaction)
- **USDC** for payments (0.01 USDC per request)

```bash
# Get buyer public key
python -c "import json; from solders.keypair import Keypair; kp = Keypair.from_bytes(bytes(json.load(open('buyer_keypair.json')))); print(kp.pubkey())"

# Fund with SOL (mainnet)
# Transfer SOL from another wallet or buy from an exchange

# Fund with USDC (mainnet)
# Transfer USDC to the buyer's public key
```

## Running Load Tests

### Sequential Test (5 requests)

```bash
python load_test_solana.py \
  --keypair buyer_keypair.json \
  --seller <SELLER_PUBKEY> \
  --num-requests 5 \
  --verbose
```

### Custom Configuration

```bash
# More requests
python load_test_solana.py \
  --keypair buyer_keypair.json \
  --seller <SELLER_PUBKEY> \
  --num-requests 20

# Different test-seller URL
TEST_SELLER_URL=http://localhost:8080 python load_test_solana.py \
  --keypair buyer_keypair.json \
  --seller <SELLER_PUBKEY> \
  --num-requests 5
```

## Local Development

### Run Test Seller Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SELLER_PUBKEY="<your_solana_public_key>"
export FACILITATOR_URL="https://facilitator.prod.ultravioletadao.xyz"

# Run server
python main.py
```

Server runs on `http://localhost:8080`

### Test Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Service info
curl http://localhost:8080/

# Make purchase (requires valid x402 payment)
curl -X POST http://localhost:8080/hello \
  -H "Content-Type: application/json" \
  -d @payment_payload.json
```

## Payment Flow

### 1. Buyer Creates Transaction

```python
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from spl.token.instructions import transfer_checked
import base64

# Create SPL Token TransferChecked instruction
# Sign transaction with buyer's key
# Serialize to bytes → base64
tx_b64 = base64.b64encode(bytes(tx)).decode('utf-8')
```

### 2. Buyer Sends to Test Seller

```json
{
  "x402Version": 1,
  "paymentPayload": {
    "x402Version": 1,
    "scheme": "exact",
    "network": "solana",
    "payload": {
      "transaction": "<base64_encoded_transaction>"
    }
  },
  "paymentRequirements": {
    "scheme": "exact",
    "network": "solana",
    "maxAmountRequired": "10000",
    "payTo": "<seller_public_key>",
    "asset": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "maxTimeoutSeconds": 60
  }
}
```

### 3. Test Seller Forwards to Facilitator

```python
response = requests.post(
    f"{FACILITATOR_URL}/settle",
    json=payment_data,
    timeout=90
)
```

### 4. Facilitator Processes

- Validates transaction structure
- Checks compute budget instructions
- Verifies transfer amount/recipient
- Signs transaction with facilitator key
- Submits to Solana network
- Waits for confirmation

### 5. Seller Returns Content

```json
{
  "message": "Hello World! 🌎",
  "price": "0.01 USDC",
  "payer": "<buyer_pubkey>",
  "tx_hash": "<solana_transaction_signature>",
  "network": "solana"
}
```

## Transaction Structure

The buyer's transaction must include these instructions in order:

```
1. SetComputeUnitLimit(200000)
2. SetComputeUnitPrice(1000000)  # Max 5M microlamports
3. TransferChecked {
     source: buyer's USDC ATA
     dest: seller's USDC ATA
     mint: USDC
     amount: 10000 (0.01 USDC)
     decimals: 6
   }
```

## AWS ECS Configuration

### Task Definition

Located at: `z:/ultravioleta/dao/karmacadabra/terraform/ecs-fargate/task-definitions/test-seller-solana.json`

Key configuration:
```json
{
  "family": "karmacadabra-prod-test-seller-solana",
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [{
    "name": "test-seller-solana",
    "image": "518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/test-seller-solana:latest",
    "environment": [
      {"name": "SELLER_PUBKEY", "value": "<set_this>"},
      {"name": "FACILITATOR_URL", "value": "https://facilitator.prod.ultravioletadao.xyz"}
    ],
    "portMappings": [{"containerPort": 8080}]
  }]
}
```

## Monitoring

### Check Service Health

```bash
# Health endpoint
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health

# Expected response
{
  "status": "healthy",
  "service": "test-seller-solana",
  "seller_pubkey": "...",
  "network": "solana"
}
```

### Check ECS Logs

```bash
aws logs tail /ecs/karmacadabra-prod-test-seller-solana --follow --region us-east-1
```

### Verify Transaction on Solscan

```bash
# Get tx hash from response
TX_HASH="<transaction_signature>"

# View on explorer
open "https://solscan.io/tx/${TX_HASH}"
```

## Troubleshooting

### "Seller not configured"

Set `SELLER_PUBKEY` environment variable:
```bash
export SELLER_PUBKEY="<your_solana_public_key>"
```

### "insufficient funds"

Buyer needs:
- SOL for transaction fees
- USDC for payment (0.01 USDC minimum)

### "invalid_exact_svm_payload_transaction_simulation_failed"

Transaction failed simulation. Common causes:
- Buyer's USDC balance < 0.01
- ATA doesn't exist
- Compute budget too low

### "Payment verification failed"

Check facilitator logs:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/facilitator-production \
  --filter-pattern "[SETTLEMENT]" \
  --region us-east-2
```

## Security

⚠️  **Test Environment Only**

- This is for testing x402 payment flow
- DO NOT use for production payments
- Buyer keypairs are stored locally - secure them properly
- Seller keypair should be in AWS Secrets Manager for production

## Differences from EVM (Base)

| Aspect | Solana | EVM (Base) |
|--------|--------|------------|
| Payment Format | VersionedTransaction (base64) | EIP-3009 signature + authorization |
| Fee Payer | Facilitator + Buyer | Facilitator only |
| Confirmation Time | ~400ms (finalized) | 2-60s (variable) |
| Asset Standard | SPL Token | ERC-20 |
| Transaction Size | ~300 bytes | ~200 bytes |
| Compute Budget | Required (200k units) | Gas limit (auto) |

## Cost Analysis

### Per Transaction

- **USDC Payment**: 0.01 USDC
- **SOL Fee**: ~0.000005 SOL (~$0.0005 at $100/SOL)
- **Total**: ~$0.0105 USD

### 100 Transactions

- **USDC**: $1.00
- **SOL Fees**: ~$0.05
- **Total**: ~$1.05 USD

## License

MIT License - For testing purposes only
