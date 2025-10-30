# Test Seller - Load Testing Endpoint

A minimal x402-enabled service that sells "Hello World" messages for $0.01 USDC on Base mainnet. Designed for load testing the x402 facilitator with real payments.

## Overview

- **Endpoint**: https://test-seller.karmacadabra.ultravioletadao.xyz
- **Price**: $0.01 USDC per request (10000 micro-units, 6 decimals)
- **Network**: Base mainnet
- **Seller Wallet**: `0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19`
- **USDC Contract**: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`

## Endpoints

### `GET /health`
Health check endpoint

**Response**:
```json
{
  "status": "healthy",
  "service": "test-seller",
  "network": "base",
  "price_usdc": "10000",
  "seller_address": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
  "facilitator": "https://facilitator.ultravioletadao.xyz"
}
```

### `GET /stats`
Service statistics

**Response**:
```json
{
  "total_requests": 1250,
  "paid_requests": 1200,
  "unpaid_requests": 50,
  "total_revenue_usdc": "$12.00",
  "price_per_request": "$0.01"
}
```

### `GET /hello`
Returns 402 Payment Required with x402 payment details

**Response (402)**:
```json
{
  "error": "payment_required",
  "message": "Payment required to access this resource",
  "x402": {
    "version": 1,
    "accepts": [
      {
        "scheme": "exact",
        "network": "base",
        "maxAmountRequired": "10000",
        "resource": "https://test-seller.karmacadabra.ultravioletadao.xyz/hello",
        "description": "Hello World message",
        "mimeType": "application/json",
        "payTo": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
        "maxTimeoutSeconds": 60,
        "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "extra": {
          "name": "USD Coin",
          "version": "2"
        }
      }
    ]
  }
}
```

### `POST /hello`
Process paid request with x402 payment

**Request Body**:
```json
{
  "x402Payment": {
    "x402Version": 1,
    "paymentPayload": {
      "x402Version": 1,
      "scheme": "exact",
      "network": "base",
      "payload": {
        "signature": "0xa403cca...",
        "authorization": {
          "from": "0xPayer...",
          "to": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
          "value": "10000",
          "validAfter": "1761329327",
          "validBefore": "1761829987",
          "nonce": "0xa0c6b1ed..."
        }
      }
    },
    "paymentRequirements": { ... }
  }
}
```

**Response (200)**:
```json
{
  "message": "Hello World! 🌍",
  "status": "paid",
  "price": "$0.01 USDC",
  "payer": "0xPayer...",
  "seller": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
  "network": "base",
  "timestamp": "2025-10-30T12:00:00Z"
}
```

### `GET /`
Root endpoint with service information

## Wallet Funding for Load Testing

### Payer Wallet (Your Test Wallet)
You need to fund YOUR wallet that will make the test requests:

1. **Get USDC on Base mainnet**:
   - Bridge from Ethereum: https://bridge.base.org/
   - Or buy directly on Base using Coinbase/exchanges

2. **Amount needed**:
   - Each request costs $0.01 USDC
   - For 1000 requests: $10 USDC
   - For 10000 requests: $100 USDC
   - Add gas buffer: ~$1-5 extra for EIP-3009 signatures (no gas needed, but good to have)

3. **Recommended test amounts**:
   - Light testing (100 requests): $5 USDC
   - Medium testing (1000 requests): $15 USDC
   - Heavy testing (10000 requests): $150 USDC

### Seller Wallet (Already Configured)
The test-seller service uses wallet `0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19` stored in AWS Secrets Manager (`karmacadabra-test-seller`). No action needed - this wallet will receive USDC from your test payments.

## Local Development

```bash
# Create .env file
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Run locally (uses AWS Secrets Manager by default)
python main.py

# Or with local override
SELLER_ADDRESS=0x... PRIVATE_KEY=0x... python main.py
```

## Docker Build & Push

```bash
# Build for linux/amd64
docker build --platform linux/amd64 -t test-seller:latest .

# Tag for ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com
docker tag test-seller:latest 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-test-seller:latest

# Push to ECR
docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-test-seller:latest
```

## Terraform Deployment

The test-seller service is configured in `terraform/ecs-fargate/`:

1. **Added to agents map** in `variables.tf`:
```hcl
test-seller = {
  port              = 8080
  health_check_path = "/health"
  priority          = 700
}
```

2. **Custom Route53 record** in `route53.tf`:
```hcl
resource "aws_route53_record" "test_seller" {
  name = "test.base.${var.base_domain}"
  # Points to ALB
}
```

3. **ALB routing rules** in `alb.tf`:
```hcl
resource "aws_lb_listener_rule" "test_seller_http" {
  priority = 15
  condition {
    host_header {
      values = ["test-seller.karmacadabra.ultravioletadao.xyz"]
    }
  }
}
```

**Deploy**:
```bash
cd terraform/ecs-fargate
terraform init
terraform plan
terraform apply
```

## Load Testing

See `tests/x402/` for comprehensive load testing scripts:

- **Python**: `tests/x402/python/test_facilitator.py`
- **k6**: `tests/x402/load/k6_load_test.js`
- **Artillery**: `tests/x402/load/artillery_config.yml`

## Architecture

```
[Payer Wallet (Your Test Wallet)]
        |
        | Signs EIP-3009 authorization
        v
[x402 Facilitator] ← Verifies signature, executes on-chain
        |
        | Transfers USDC
        v
[Test Seller: 0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19]
        |
        | Returns "Hello World"
        v
[Payer receives response]
```

## Cost Estimate

**ECS Fargate Spot**:
- 0.25 vCPU / 0.5GB RAM
- ~$1.50/month (Spot pricing)

**ALB**:
- Already exists (shared with other services)
- No additional cost

**Route53**:
- $0.50/month per hosted zone (already exists)
- $0.40 per million queries

**Total**: ~$2/month for dedicated test endpoint

## Security

- Private key stored in AWS Secrets Manager (`karmacadabra-test-seller`)
- No private keys in environment variables or code
- Production uses IAM roles for Secrets Manager access
- Local development can override with `.env` (for testing only)

## Monitoring

Check service status:
```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/health
curl https://test-seller.karmacadabra.ultravioletadao.xyz/stats
```

View ECS logs:
```bash
aws logs tail /ecs/karmacadabra-prod-test-seller --follow --region us-east-1
```

## Troubleshooting

**"payment_required" on GET /hello**: Expected behavior - use POST with x402Payment

**"Missing x402Payment in request body"**: POST request needs payment metadata

**Service not responding**: Check ECS service status
```bash
aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-test-seller --region us-east-1
```

**DNS not resolving**: Wait for Route53 propagation (~5 minutes)
```bash
nslookup test-seller.karmacadabra.ultravioletadao.xyz
```
