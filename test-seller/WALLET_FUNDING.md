# Wallet Funding Guide for Load Testing

This guide explains how to fund your payer wallet with USDC on Base mainnet for load testing the test-seller endpoint.

## Overview

- **Test Endpoint**: https://test-seller.karmacadabra.ultravioletadao.xyz
- **Price**: $0.01 USDC per request
- **Network**: Base mainnet (Chain ID: 8453)
- **USDC Contract**: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`

## Wallets

### 1. Payer Wallet (YOU need to fund this)

This is YOUR wallet that will make test requests and pay for them. You need to:
- Create a new wallet OR use an existing one
- Fund it with USDC on Base mainnet
- Use the private key in the load testing script

**Generation** (if you don't have one):
```python
from eth_account import Account
import secrets

private_key = '0x' + secrets.token_hex(32)
account = Account.from_key(private_key)

print(f"Address: {account.address}")
print(f"Private Key: {private_key}")
```

**IMPORTANT**: Keep this private key secure! Use a dedicated test wallet, not your main wallet.

### 2. Seller Wallet (Already configured - NO action needed)

- **Address**: `0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19`
- **Purpose**: Receives USDC payments from test requests
- **Storage**: AWS Secrets Manager (`karmacadabra-test-seller`)
- **Status**: ✅ Already deployed and configured

This wallet will automatically receive payments when you make successful requests.

## How to Get USDC on Base

### Option 1: Bridge from Ethereum (Recommended)

1. **Official Base Bridge**: https://bridge.base.org/
   - Connect wallet (MetaMask/Coinbase Wallet)
   - Select "Ethereum → Base"
   - Enter USDC amount
   - Approve and confirm transaction
   - Wait ~10 minutes for bridging

2. **Cost**:
   - Ethereum gas: ~$5-20 (depends on network congestion)
   - Bridging fee: ~$1-5
   - Minimum recommended: Bridge $50+ USDC to make gas fees worthwhile

### Option 2: Buy Directly on Base

1. **Coinbase** (easiest if you have a Coinbase account):
   - Buy USDC on Coinbase
   - Withdraw to Base network (select "Base" as destination network)
   - Send to your payer wallet address

2. **Uniswap on Base**: https://app.uniswap.org/
   - Swap ETH → USDC on Base network
   - Make sure you have some ETH on Base for gas

3. **Other DEXes on Base**:
   - Aerodrome Finance
   - SushiSwap
   - PancakeSwap

### Option 3: Centralized Exchanges

Some exchanges support USDC withdrawals to Base network:
- Coinbase (native Base support)
- Binance (check if Base network available)
- Kraken (check if Base network available)

**IMPORTANT**: Always select "Base" or "Base Network" as the withdrawal network, NOT Ethereum!

## Funding Amounts

Calculate how much USDC you need:

| Test Size | Requests | Cost | Recommended |
|-----------|----------|------|-------------|
| Tiny | 10 | $0.10 | $1 USDC |
| Small | 100 | $1.00 | $5 USDC |
| Medium | 1,000 | $10.00 | $15 USDC |
| Large | 10,000 | $100.00 | $150 USDC |
| Massive | 100,000 | $1,000.00 | $1,200 USDC |

**Buffer**: Add 20-50% extra to account for failed requests and retries.

## Checking Your Balance

### Using the Load Test Script

```bash
python load_test.py \
  --private-key "0xYOUR_PRIVATE_KEY" \
  --check-balance
```

### Using Web3.py

```python
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
usdc_contract = w3.eth.contract(
    address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    abi=[{
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }]
)

balance = usdc_contract.functions.balanceOf("YOUR_ADDRESS").call()
print(f"Balance: ${balance / 1000000:.2f} USDC")
```

### Using Block Explorer

1. Go to https://basescan.org/
2. Enter your wallet address
3. Look for "USDC" in the token holdings
4. Should show balance in USDC (not micro-units)

### Using MetaMask

1. Add Base network to MetaMask:
   - Network Name: Base Mainnet
   - RPC URL: https://mainnet.base.org
   - Chain ID: 8453
   - Currency Symbol: ETH
   - Block Explorer: https://basescan.org

2. Add USDC token:
   - Click "Import tokens"
   - Contract: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
   - Symbol: USDC
   - Decimals: 6

3. View balance in MetaMask under "Assets"

## Running Load Tests

### Basic Test (10 requests)

```bash
python load_test.py \
  --private-key "0xYOUR_PRIVATE_KEY" \
  --num-requests 10 \
  --check-balance
```

### Sequential Test (100 requests, one at a time)

```bash
python load_test.py \
  --private-key "0xYOUR_PRIVATE_KEY" \
  --num-requests 100
```

### Concurrent Test (1000 requests, 20 workers)

```bash
python load_test.py \
  --private-key "0xYOUR_PRIVATE_KEY" \
  --num-requests 1000 \
  --concurrent \
  --workers 20
```

### Heavy Load Test (10,000 requests)

```bash
python load_test.py \
  --private-key "0xYOUR_PRIVATE_KEY" \
  --num-requests 10000 \
  --concurrent \
  --workers 50
```

## Cost Breakdown

### Per Request
- **Payment**: $0.01 USDC
- **Gas**: $0 (EIP-3009 meta-transactions = gasless)
- **Facilitator Fee**: $0 (included in payment)
- **Total**: $0.01 USDC per successful request

### Total Test Costs

| Requests | Total Cost | Success Rate | Expected Cost |
|----------|------------|--------------|---------------|
| 10 | $0.10 | 95% | $0.095 |
| 100 | $1.00 | 95% | $0.95 |
| 1,000 | $10.00 | 95% | $9.50 |
| 10,000 | $100.00 | 95% | $95.00 |

**Note**: Failed requests don't cost money (payment not executed if verification fails).

## Security Best Practices

1. **Use a dedicated test wallet**
   - Don't use your main wallet
   - Create a new wallet just for load testing
   - Only fund it with the amount needed

2. **Store private key securely**
   - Use environment variables: `export PRIVATE_KEY="0x..."`
   - Or pass via command line (less secure, visible in history)
   - Never commit private keys to git

3. **Monitor spending**
   - Check balance before and after tests
   - Verify cost matches expected (num_requests × $0.01)
   - Alert if spending exceeds budget

4. **Withdrawal after testing**
   - Transfer remaining USDC back to main wallet
   - Or keep funded for future tests

## Troubleshooting

### "Insufficient funds" error

**Problem**: Wallet doesn't have enough USDC

**Solution**:
```bash
python load_test.py --private-key "0x..." --check-balance
```

### "Nonce already used" error

**Problem**: Duplicate nonce in EIP-3009 authorization

**Solution**: Each request generates a random nonce - should not happen. If it does, restart the test.

### "Transaction reverted" error

**Problem**: USDC transfer failed on-chain

**Possible causes**:
- USDC allowance not set (shouldn't be needed with EIP-3009)
- Contract paused (unlikely)
- Network congestion

**Solution**: Wait a few minutes and retry

### Bridge taking too long

**Problem**: USDC bridge from Ethereum → Base stuck

**Solution**:
1. Check bridge status: https://bridge.base.org/transactions
2. Usually takes 10-30 minutes
3. Contact Base support if > 1 hour

## Example Test Session

```bash
# Step 1: Generate test wallet
python -c "from eth_account import Account; import secrets; pk='0x'+secrets.token_hex(32); print(f'Address: {Account.from_key(pk).address}\\nPrivate Key: {pk}')"

# Output:
# Address: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4
# Private Key: 0x1234...

# Step 2: Fund wallet with USDC on Base
# (Use bridge.base.org or buy on Coinbase)

# Step 3: Check balance
python load_test.py --private-key "0x1234..." --check-balance

# Output:
# [INFO] USDC Balance: $50.00 USDC
# [INFO] Required for 10 requests: $0.10 USDC

# Step 4: Run test
python load_test.py --private-key "0x1234..." --num-requests 100

# Output:
# [0001] SUCCESS - Hello World! 🌍 - $0.01 USDC
# [0002] SUCCESS - Hello World! 🌍 - $0.01 USDC
# ...
# LOAD TEST RESULTS
# Total Requests:    100
# Successful:        95 (95.0%)
# Failed:            5
# Duration:          12.34s
# Requests/sec:      8.10
# Total Cost:        $0.95 USDC

# Step 5: Check final balance
python load_test.py --private-key "0x1234..." --check-balance

# Output:
# [INFO] USDC Balance: $49.05 USDC
```

## Summary

1. **Create/Use a test wallet** (or generate new one)
2. **Fund with USDC on Base** (bridge from Ethereum or buy directly)
3. **Check balance** using load_test.py or block explorer
4. **Run tests** with appropriate num-requests and workers
5. **Monitor costs** and success rates
6. **Withdraw remaining funds** after testing

**Ready to test?** Fund your wallet and run:
```bash
python load_test.py --private-key "0xYOUR_KEY" --num-requests 10 --check-balance
```
