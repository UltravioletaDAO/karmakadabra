# Quick Start - Test Seller Load Testing

## TL;DR - Copy & Paste Commands

### 1. Install Dependencies

```bash
cd test-seller
pip install -r load_test_requirements.txt
```

### 2. Check Service Health

```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/health | jq .
```

### 3. Check Test-Buyer Wallet Balance

```bash
python load_test.py --check-balance --num-requests 0
```

**Test-buyer wallet**: `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011`

### 4. Fund Test-Buyer Wallet (If Needed)

**Fastest method** - Direct transfer if you have USDC on Base:
- Send USDC to: `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011`
- Network: Base mainnet

**Alternative** - Bridge from Ethereum:
- Go to https://bridge.base.org/
- Send USDC to: `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011`
- Wait ~10 minutes

### 5. Run Load Test

**Tiny test (10 requests, $0.10 USDC)**:
```bash
python load_test.py --num-requests 10
```

**Medium test (1000 requests, $10 USDC, concurrent)**:
```bash
python load_test.py --num-requests 1000 --concurrent --workers 20
```

**Large test (10000 requests, $100 USDC, heavy load)**:
```bash
python load_test.py --num-requests 10000 --concurrent --workers 50
```

### 6. Check Results

```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/stats | jq .
```

## That's It!

See `TEST_SCRIPTS.md` for more examples and troubleshooting.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Test-Buyer Wallet (AWS Secrets Manager)                    │
│ 0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011                  │
│ - Stored in: karmacadabra-test-buyer                       │
│ - Auto-loaded by load_test.py                              │
│ - YOU MUST FUND WITH USDC ON BASE                          │
└─────────────────────────────────────────────────────────────┘
                          ↓ Signs EIP-3009 payment
┌─────────────────────────────────────────────────────────────┐
│ x402 Facilitator                                            │
│ https://facilitator.ultravioletadao.xyz                     │
│ - Verifies EIP-712 signature                                │
│ - Executes transferWithAuthorization on-chain               │
└─────────────────────────────────────────────────────────────┘
                          ↓ Transfers USDC
┌─────────────────────────────────────────────────────────────┐
│ Test-Seller Service                                         │
│ https://test-seller.karmacadabra.ultravioletadao.xyz          │
│ - Receives: $0.01 USDC per request                          │
│ - Returns: "Hello World! 🌍"                                 │
│ - Seller wallet: 0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19│
└─────────────────────────────────────────────────────────────┘
```

## Key Files

- `load_test.py` - Main load testing script (uses AWS test-buyer by default)
- `load_test_requirements.txt` - Python dependencies
- `TEST_SCRIPTS.md` - Detailed examples and monitoring commands
- `WALLET_FUNDING.md` - Complete guide on funding wallets
- `DEPLOYMENT.md` - Infrastructure deployment guide

## Configuration

Everything is pre-configured:
- ✅ Test-seller deployed to ECS
- ✅ DNS configured: test-seller.karmacadabra.ultravioletadao.xyz
- ✅ Test-buyer wallet in AWS Secrets Manager
- ✅ Test-seller wallet in AWS Secrets Manager
- 🔄 **YOU ONLY NEED TO FUND THE TEST-BUYER WALLET**

## Wallet Info

| Role | Address | Storage | Status |
|------|---------|---------|--------|
| **Test-Buyer** (Payer) | `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011` | AWS: `karmacadabra-test-buyer` | ⚠️ **NEEDS FUNDING** |
| **Test-Seller** (Receiver) | `0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19` | AWS: `karmacadabra-test-seller` | ✅ Ready |

## Costs

| Test Size | Requests | Cost (USDC) | Time |
|-----------|----------|-------------|------|
| Tiny | 10 | $0.10 | ~1s |
| Small | 100 | $1.00 | ~5s |
| Medium | 1,000 | $10.00 | ~1min |
| Large | 10,000 | $100.00 | ~8min |
| Massive | 100,000 | $1,000.00 | ~1.5hrs |

## Monitoring

**Real-time logs**:
```bash
aws logs tail /ecs/karmacadabra-prod/test-seller --follow --region us-east-1
```

**Service stats**:
```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/stats | jq .
```

**ECS service**:
```bash
aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-test-seller --region us-east-1
```

## Common Issues

**"Failed to load from AWS Secrets Manager"**
→ Configure AWS CLI: `aws configure`

**"Insufficient funds"**
→ Fund test-buyer: Send USDC to `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011` on Base

**Service not responding**
→ Check health: `curl https://test-seller.karmacadabra.ultravioletadao.xyz/health`

## Support

For detailed documentation, see:
- `TEST_SCRIPTS.md` - Full command reference
- `WALLET_FUNDING.md` - How to get USDC on Base
- `DEPLOYMENT.md` - Infrastructure details
