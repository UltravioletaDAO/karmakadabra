# Test Seller (Solana) - Hello World Service

A simple x402-enabled service that sells "Hello World" messages for 0.01 USDC on Solana Devnet.

## Overview

- **Endpoint**: https://test-seller-solana.karmacadabra.ultravioletadao.xyz
- **Price**: $0.01 USDC (10,000 micro-units with 6 decimals)
- **Network**: Solana Devnet
- **USDC Address**: 4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU
- **Protocol**: x402 payment protocol

## Purpose

Perfect for:
- Load testing the x402 facilitator with Solana payments
- Testing Solana payment integration
- Demonstrating cross-chain x402 support (compare with Base version)

## Endpoints

### GET /health
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "service": "test-seller-solana",
  "network": "solana-devnet",
  "price_usdc": "10000",
  "seller_address": "...",
  "facilitator": "https://facilitator.ultravioletadao.xyz"
}
```

### GET /stats
Service statistics.

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

### GET /hello
Returns 402 Payment Required with x402 payment requirements.

**Response** (HTTP 402):
```json
{
  "error": "payment_required",
  "message": "Payment required to access this resource",
  "x402": {
    "version": 1,
    "accepts": [{
      "scheme": "exact",
      "network": "solana",
      "maxAmountRequired": "10000",
      "resource": "https://test-seller-solana.karmacadabra.ultravioletadao.xyz/hello",
      "description": "Hello World message",
      "mimeType": "application/json",
      "payTo": "...",
      "maxTimeoutSeconds": 60,
      "asset": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
    }]
  }
}
```

### POST /hello
Process paid request with x402 payment.

**Request**:
```json
{
  "x402Payment": {
    "paymentPayload": { ... },
    "paymentRequirements": { ... }
  }
}
```

Or unwrapped format:
```json
{
  "paymentPayload": { ... },
  "paymentRequirements": { ... }
}
```

**Response**:
```json
{
  "message": "Hello World! 🌍 (from Solana)",
  "status": "paid",
  "price": "$0.01 USDC",
  "payer": "...",
  "seller": "...",
  "network": "solana-devnet",
  "tx_signature": "..."
}
```

## Configuration

### AWS Secrets Manager
The service loads configuration from AWS Secrets Manager secret: `karmacadabra-test-seller-solana`

**Required fields**:
```json
{
  "address": "SOLANA_PUBLIC_KEY",
  "private_key": "SOLANA_PRIVATE_KEY"
}
```

### Environment Variables (fallback)
- `SELLER_ADDRESS`: Solana wallet address
- `PRIVATE_KEY`: Solana wallet private key (optional, used by facilitator)
- `FACILITATOR_URL`: x402 facilitator URL (default: https://facilitator.ultravioletadao.xyz)
- `PORT`: Service port (default: 8080)

## Deployment

### Prerequisites
1. AWS CLI configured with proper credentials
2. Docker installed
3. Terraform 1.0+ installed
4. AWS Secrets Manager secret created: `karmacadabra-test-seller-solana`

### Steps

1. **Create Wallet and Store in AWS Secrets Manager**:
```bash
# Generate Solana wallet (use solana-keygen or similar)
# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name karmacadabra-test-seller-solana \
  --secret-string '{"address":"YOUR_SOLANA_ADDRESS","private_key":"YOUR_SOLANA_PRIVATE_KEY"}' \
  --region us-east-1
```

2. **Apply Terraform** (from `terraform/ecs-fargate/`):
```bash
terraform init
terraform plan
terraform apply
```

This creates:
- ECS Task Definition: `karmacadabra-prod-test-seller-solana`
- ECS Service: `karmacadabra-prod-test-seller-solana`
- Target Group: `karmacadabra-prod-test-seller-solana-tg`
- Route53 Record: `test-seller-solana.karmacadabra.ultravioletadao.xyz`
- ALB Listener Rules: HTTP (priority 750) + HTTPS (priority 1750)

3. **Build and Deploy**:
```bash
cd test-seller-solana
bash deploy.sh
```

4. **Verify Deployment**:
```bash
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health
```

## Testing

### Local Testing
```bash
# Run locally
python main.py

# Test health endpoint
curl http://localhost:8080/health

# Test payment required
curl http://localhost:8080/hello
```

### Production Testing
```bash
# Health check
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health

# Payment required
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/hello

# Stats
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/stats
```

## Monitoring

### ECS Service Status
```bash
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-test-seller-solana \
  --region us-east-1
```

### Logs
```bash
aws logs tail /ecs/karmacadabra-prod-test-seller-solana --follow --region us-east-1
```

### CloudWatch Metrics
Available in AWS CloudWatch under namespace `AWS/ECS`:
- CPUUtilization
- MemoryUtilization
- RequestCount
- TargetResponseTime

## Cost Estimate
- **ECS Fargate Spot** (0.25 vCPU / 0.5GB): ~$1.50/month
- **ECR**: ~$0.10/month for image storage
- **CloudWatch Logs**: ~$0.50/month (7-day retention)
- **Total**: ~$2.10/month

## Troubleshooting

### Service won't start
Check logs:
```bash
aws logs tail /ecs/karmacadabra-prod-test-seller-solana --follow --region us-east-1
```

Common issues:
- Secrets Manager permissions
- ECR image not found
- Port conflict

### 403 Access Denied
- Check DNS resolution
- Verify ALB listener rules
- Check security group settings

### Payment verification fails
- Ensure facilitator supports Solana
- Check USDC address is correct for Devnet
- Verify payment signature format

## Differences from Base Version

| Feature | test-seller (Base) | test-seller-solana (Solana) |
|---------|-------------------|---------------------------|
| Network | Base mainnet (8453) | Solana Devnet |
| USDC Address | 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 | 4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU |
| Transaction ID | tx_hash | tx_signature |
| Address Format | 0x... (EVM) | Base58 (Solana) |
| Message | "Hello World! 🌍" | "Hello World! 🌍 (from Solana)" |

## Architecture

```
┌─────────────────┐
│  Client/Buyer   │
└────────┬────────┘
         │ GET /hello (402 Payment Required)
         │
         ▼
┌─────────────────────────────┐
│  test-seller-solana         │
│  (FastAPI + x402)           │
│                             │
│  - Returns payment req      │
│  - Verifies via facilitator │
│  - Settles on-chain         │
└────────┬────────────────────┘
         │ POST /settle
         │
         ▼
┌─────────────────────────────┐
│  x402 Facilitator (Rust)    │
│                             │
│  - Verifies Solana sig      │
│  - Executes transfer        │
│  - Returns tx signature     │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Solana Devnet              │
│                             │
│  - USDC transfer settled    │
│  - On-chain verification    │
└─────────────────────────────┘
```

## Related Services
- **test-seller** (Base version): https://test-seller.karmacadabra.ultravioletadao.xyz
- **x402 Facilitator**: https://facilitator.ultravioletadao.xyz
- **Validator**: https://validator.karmacadabra.ultravioletadao.xyz
