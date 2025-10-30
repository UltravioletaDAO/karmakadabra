# Balance Verification - Detecting Payment Issues

The `--check-balance` flag now validates that USDC transfers actually occur on-chain.

## The Problem

**Your Issue**: Tests show "SUCCESS" but the facilitator wallet doesn't receive funds.

**Root Cause**: The test-seller service returns 200 OK *before* verifying payment with the facilitator. This means:
1. Client sends payment authorization
2. Test-seller returns "Hello World!" immediately
3. Payment may or may not actually settle on-chain
4. Test shows "SUCCESS" even if no funds transferred

## The Solution

Use `--check-balance` to verify actual on-chain transfers:

```bash
python load_test.py --num-requests 5 --check-balance
```

This will:
1. Check buyer and seller balances BEFORE test
2. Run the requests
3. Check balances AFTER test
4. Compare actual vs expected changes
5. Show warnings if balances don't match

## Example Output

### If Payments Work Correctly

```
[BALANCE CHECK] Getting initial balances...
[BALANCE] Buyer (payer):  $50.000000 USDC
[BALANCE] Seller (payee): $0.000000 USDC

[0001] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0002] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0003] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0004] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0005] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...

[BALANCE CHECK] Getting final balances...
[BALANCE] Buyer (payer):  $49.950000 USDC (change: -$0.050000)
[BALANCE] Seller (payee): $0.050000 USDC (change: +$0.050000)
[BALANCE] Expected transfer: $0.050000 USDC
[BALANCE] ✓ Buyer balance change matches expected
[BALANCE] ✓ Seller balance change matches expected

============================================================
LOAD TEST RESULTS
============================================================
Total Requests:    5
Successful:        5 (100.0%)
Failed:            0
Total Cost:        $0.05 USDC
============================================================
```

### If Payments DON'T Actually Work

```
[BALANCE CHECK] Getting initial balances...
[BALANCE] Buyer (payer):  $50.000000 USDC
[BALANCE] Seller (payee): $0.000000 USDC

[0001] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0002] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0003] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0004] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
[0005] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...

[BALANCE CHECK] Getting final balances...
[BALANCE] Buyer (payer):  $50.000000 USDC (change: +$0.000000)
[BALANCE] Seller (payee): $0.000000 USDC (change: +$0.000000)
[BALANCE] Expected transfer: $0.050000 USDC
[BALANCE] ✗ WARNING: Buyer balance change ($0.000000) doesn't match expected ($0.050000)
[BALANCE] ✗ WARNING: Seller balance change ($0.000000) doesn't match expected ($0.050000)

============================================================
LOAD TEST RESULTS
============================================================
Total Requests:    5
Successful:        5 (100.0%)
Failed:            0
Total Cost:        $0.05 USDC
============================================================
```

**This reveals the problem!** Tests show "successful" but NO funds transferred.

## Why This Happens

The test-seller service doesn't actually verify payments with the facilitator. It:
1. Receives the x402Payment payload
2. Returns 200 OK immediately
3. Never calls facilitator to verify/settle

### Current test-seller code (main.py lines 142-195):

```python
@app.post("/hello")
async def post_hello_paid(request: Request):
    stats["total_requests"] += 1
    body = await request.json()
    payment = body.get("x402Payment")

    # Extract payer
    payer = payment.get("paymentPayload", {}).get("payload", {}).get("authorization", {}).get("from", "unknown")

    # In production, you would verify the payment with the facilitator here
    # For this test service, we'll trust the client has valid payment
    # ^^^^^ THIS IS THE PROBLEM! ^^^^^

    stats["paid_requests"] += 1
    return {"message": "Hello World! 🌍", "status": "paid", "price": "$0.01 USDC"}
```

The comment says "you would verify" but it doesn't!

## The Fix

The test-seller needs to:

1. **Call facilitator `/verify` endpoint** with the payment payload
2. **Check `isValid` response**
3. **If valid**, call facilitator `/settle` endpoint
4. **Only then** return success

This is the proper x402 flow:

```
Client → Test-Seller: POST /hello with x402Payment
Test-Seller → Facilitator: POST /verify with payment
Facilitator → Test-Seller: {isValid: true}
Test-Seller → Facilitator: POST /settle with payment
Facilitator → Blockchain: transferWithAuthorization()
Blockchain: USDC transferred on-chain
Facilitator → Test-Seller: {settled: true, txHash: "0x..."}
Test-Seller → Client: {message: "Hello World", txHash: "0x..."}
```

## Temporary Workaround

Until test-seller is fixed, you can:

1. **Use --check-balance** to detect the issue
2. **Manually verify on BaseScan**:
   ```
   Buyer:  https://basescan.org/address/0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011
   Seller: https://basescan.org/address/0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19
   ```

3. **Check facilitator wallet** (should show USDC transfers):
   ```
   https://basescan.org/address/0x103040545AC5031A11E8C03dd11324C7333a13C7
   ```

## Testing Commands

### Quick Test (1 request with balance check)
```bash
python load_test.py --num-requests 1 --check-balance --verbose
```

This shows:
- Initial balances
- Request details (nonce, signature)
- Response from test-seller
- Final balances
- Whether funds actually moved

### Load Test with Verification
```bash
python load_test.py --num-requests 10 --check-balance
```

### Concurrent Test with Verification
```bash
python load_test.py --num-requests 100 --concurrent --workers 10 --check-balance
```

## What to Check

After running with `--check-balance`:

1. **Do balances change?**
   - If NO → Payments not settling
   - If YES → Check if amounts match expected

2. **Do both buyer and seller change by same amount?**
   - Buyer should DECREASE
   - Seller should INCREASE
   - Amounts should be equal

3. **Does change match successful requests?**
   - If 10 requests succeed → expect $0.10 transfer
   - If only 5 actually succeed → balances show $0.05

## Next Steps

1. **Run test with balance checking**:
   ```bash
   python load_test.py --num-requests 1 --check-balance --verbose
   ```

2. **If balances don't change**:
   - Test-seller isn't calling facilitator
   - Need to fix test-seller to verify/settle payments

3. **If balances change correctly**:
   - Payments are working!
   - Facilitator should show transactions

## Expected Behavior

**Working x402 flow**:
- ✓ Client signs payment (EIP-712)
- ✓ Test-seller receives payment
- ✓ Test-seller calls facilitator /verify
- ✓ Facilitator verifies signature
- ✓ Test-seller calls facilitator /settle
- ✓ Facilitator executes transferWithAuthorization on-chain
- ✓ USDC moves from buyer to seller
- ✓ Test-seller returns response with TX hash
- ✓ Balances reflect actual transfer

**Current broken flow**:
- ✓ Client signs payment (EIP-712)
- ✓ Test-seller receives payment
- ✗ Test-seller skips verification
- ✗ Test-seller skips settlement
- ✗ No on-chain transaction
- ✗ No USDC transfer
- ✓ Test-seller returns "success" anyway
- ✗ Balances unchanged

Use `--check-balance` to detect this!
