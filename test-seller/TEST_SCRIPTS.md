# Ready-to-Use Test Scripts

Copy and paste these commands to test the test-seller service.

## Prerequisites

```bash
cd test-seller
pip install -r load_test_requirements.txt
```

## Configuration

The test-buyer wallet is already configured in AWS Secrets Manager:
- **Address**: `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011`
- **Secret**: `karmacadabra-test-buyer`

**IMPORTANT**: Fund this wallet with USDC on Base mainnet before running tests!

## Quick Tests

### 1. Check Service Health

```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/health | jq .
```

**Expected output**:
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

### 2. Check Service Stats

```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/stats | jq .
```

### 3. Test 402 Payment Required

```bash
curl -i https://test-seller.karmacadabra.ultravioletadao.xyz/hello
```

**Expected**: HTTP 402 with x402 payment requirements

## Load Tests (Using AWS Test-Buyer Wallet)

### Tiny Test (10 requests) - Cost: $0.10 USDC

```bash
python load_test.py --num-requests 10 --check-balance
```

### Small Test (100 requests, sequential) - Cost: $1.00 USDC

```bash
python load_test.py --num-requests 100
```

### Medium Test (1000 requests, concurrent) - Cost: $10.00 USDC

```bash
python load_test.py --num-requests 1000 --concurrent --workers 20
```

### Large Test (10000 requests, heavy load) - Cost: $100.00 USDC

```bash
python load_test.py --num-requests 10000 --concurrent --workers 50
```

## Load Tests (Using Custom Private Key)

If you want to use your own wallet instead of the AWS test-buyer:

```bash
python load_test.py --private-key "0xYOUR_PRIVATE_KEY_HERE" --num-requests 10 --check-balance
```

## Check Test-Buyer Balance

```bash
python -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://mainnet.base.org'))
usdc = w3.eth.contract(
    address='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    abi=[{'constant': True, 'inputs': [{'name': '_owner', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': 'balance', 'type': 'uint256'}], 'type': 'function'}]
)
balance = usdc.functions.balanceOf('0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011').call()
print(f'Balance: \${balance / 1000000:.2f} USDC')
"
```

## Fund Test-Buyer Wallet

### Option 1: Bridge from Ethereum (Recommended for large amounts)

1. Go to https://bridge.base.org/
2. Connect your wallet
3. Select "Ethereum → Base"
4. Send USDC to: `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011`
5. Wait ~10 minutes for bridge

### Option 2: Direct Transfer (Recommended for small amounts)

If you already have USDC on Base:

1. Open MetaMask/Coinbase Wallet
2. Switch to Base network
3. Send USDC to: `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011`

### Option 3: Buy on Coinbase

1. Buy USDC on Coinbase
2. Withdraw to Base network
3. Address: `0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011`

## Monitoring

### View Real-Time Logs

```bash
aws logs tail /ecs/karmacadabra-prod/test-seller --follow --region us-east-1
```

### Check ECS Service Status

```bash
aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-test-seller --region us-east-1 --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### Check Target Health

```bash
aws elbv2 describe-target-health --target-group-arn $(aws elbv2 describe-target-groups --names karmacadabra-prod-test-seller-tg --query 'TargetGroups[0].TargetGroupArn' --output text --region us-east-1) --region us-east-1
```

## Example Test Session

```bash
# 1. Check service is healthy
curl https://test-seller.karmacadabra.ultravioletadao.xyz/health | jq .

# 2. Check test-buyer balance
python load_test.py --check-balance --num-requests 0

# Output:
# [INFO] Loaded test-buyer wallet from AWS Secrets Manager
# [INIT] Payer wallet: 0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011
# [INFO] Checking USDC balance for 0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011...
# [INFO] USDC Balance: $50.00 USDC
# [INFO] Required for 0 requests: $0.00 USDC

# 3. Run small test (10 requests)
python load_test.py --num-requests 10

# Output:
# [INFO] Loaded test-buyer wallet from AWS Secrets Manager
# [INIT] Payer wallet: 0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011
# [INIT] Test seller: https://test-seller.karmacadabra.ultravioletadao.xyz
# [INIT] Price per request: $0.01 USDC
#
# [START] Sequential test: 10 requests
# ============================================================
# [0001] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0002] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0003] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0004] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0005] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0006] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0007] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0008] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0009] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0010] SUCCESS - Hello World! 🌍 - $0.01 USDC
#
# ============================================================
# LOAD TEST RESULTS
# ============================================================
# Total Requests:    10
# Successful:        10 (100.0%)
# Failed:            0
# Duration:          12.34s
# Requests/sec:      0.81
# Total Cost:        $0.10 USDC
# ============================================================

# 4. Check stats after test
curl https://test-seller.karmacadabra.ultravioletadao.xyz/stats | jq .

# Output:
# {
#   "total_requests": 10,
#   "paid_requests": 10,
#   "unpaid_requests": 0,
#   "total_revenue_usdc": "$0.10",
#   "price_per_request": "$0.01"
# }

# 5. Run concurrent test (1000 requests)
python load_test.py --num-requests 1000 --concurrent --workers 20

# This will take ~1-2 minutes and cost ~$10 USDC
```

## Troubleshooting

### "Failed to load from AWS Secrets Manager"

**Solution**: Configure AWS credentials
```bash
aws configure
```

Or set environment variables:
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

### "Insufficient funds" error

**Check balance**:
```bash
python load_test.py --check-balance --num-requests 0
```

**Fund wallet**: See "Fund Test-Buyer Wallet" section above

### "Connection refused" or "Service unavailable"

**Check service status**:
```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/health
```

If not responding, check ECS service:
```bash
aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-test-seller --region us-east-1
```

### "Nonce already used" error

This should not happen (each request generates random nonce). If it does, wait 1 minute and retry.

### "Payment invalid" or "Verification failed"

**Possible causes**:
- Insufficient USDC balance
- Invalid signature (code issue)
- Facilitator connection issue

**Debug**:
1. Check test-buyer balance
2. Check facilitator health: `curl https://facilitator.ultravioletadao.xyz/health`
3. View facilitator logs for detailed error

## Cost Calculator

| Requests | Cost (USDC) | Time (sequential) | Time (20 workers) |
|----------|-------------|-------------------|-------------------|
| 10 | $0.10 | ~1s | ~1s |
| 100 | $1.00 | ~10s | ~5s |
| 1,000 | $10.00 | ~100s | ~50s |
| 10,000 | $100.00 | ~1000s (~17min) | ~500s (~8min) |
| 100,000 | $1,000.00 | ~10000s (~3hrs) | ~5000s (~1.5hrs) |

**Note**: Times are approximate. Actual performance depends on network conditions and facilitator load.

## Next Steps

1. ✅ Service deployed and healthy
2. ✅ Test-buyer wallet configured
3. 🔄 **Fund test-buyer wallet** (Required!)
4. ✅ Run tests with commands above
5. 📊 Monitor results and costs
