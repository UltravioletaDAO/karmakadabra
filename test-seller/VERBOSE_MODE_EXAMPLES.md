# Verbose Mode Examples

The `--verbose` or `-v` flag shows detailed request/response information for debugging and monitoring.

## Basic Usage

```bash
# Single request with full details
python load_test.py --num-requests 1 --verbose

# Or use short form
python load_test.py --num-requests 1 -v
```

## What Verbose Mode Shows

### Request Details
- **Nonce**: Random 32-byte value used for EIP-3009
- **Signature**: EIP-712 signature (truncated for readability)
- **Valid Time Range**: `validAfter` and `validBefore` timestamps

### Response Details
- **HTTP Status**: Response code from test-seller
- **Message**: "Hello World! 🌍"
- **Price**: "$0.01 USDC"
- **Payer**: Your wallet address
- **Seller**: Test-seller wallet address
- **Network**: "base"
- **Transaction Hash**: On-chain settlement TX (if available)
- **BaseScan Link**: Direct link to view transaction

## Example Output

### Standard Mode (Default)
```
[0001] SUCCESS - Hello World! 🌍 - $0.01 USDC - Payer: 0x6bdc03ae...
```

### Verbose Mode (--verbose or -v)
```
[0001] ========== REQUEST DETAILS ==========
[0001] Nonce: 0xa0c6b1edb9fed5b5cd99626dadf0e60b56013f94839d4fdcfa0117cce1f74485
[0001] Signature: 0xa403cca73a6e9e0f...5b8c97dcd09d307e8
[0001] Valid: 1761329327 to 1761829987
[0001] ========== RESPONSE ==========
[0001] Status: 200
[0001] Message: Hello World! 🌍
[0001] Price: $0.01 USDC
[0001] Payer: 0x6bdc03ae4BBAb31843dDDaAE749149aE675ea011
[0001] Seller: 0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19
[0001] Network: base
[0001] TX Hash: 0x1234567890abcdef...  (if available)
[0001] BaseScan: https://basescan.org/tx/0x1234567890abcdef...
[0001] =====================================
```

## Use Cases

### 1. Debugging Failed Requests
```bash
# See why a request failed
python load_test.py --num-requests 1 --verbose
```

If a request fails, verbose mode shows:
- Full error response from server
- HTTP status code
- Error message details
- Stack trace (for exceptions)

### 2. Verifying Signature Generation
```bash
# Check that signatures are being generated correctly
python load_test.py --num-requests 1 --verbose
```

Useful for:
- Confirming nonce randomness
- Verifying signature format
- Checking timestamp validity

### 3. Monitoring On-Chain Settlement
```bash
# Get transaction hashes for on-chain verification
python load_test.py --num-requests 5 --verbose
```

Then check transactions on BaseScan:
```
https://basescan.org/tx/0x...
```

### 4. Load Testing with Details
```bash
# Concurrent test with full details
python load_test.py --num-requests 10 --concurrent --workers 3 --verbose
```

Shows details for all requests (note: output may interleave with concurrent execution)

## Combining with Other Flags

### Verbose + Balance Check
```bash
python load_test.py --num-requests 1 --verbose --check-balance
```

### Verbose + Custom Private Key
```bash
python load_test.py --num-requests 1 --verbose --private-key "0xYOUR_KEY"
```

### Verbose + Concurrent + Many Workers
```bash
python load_test.py --num-requests 100 --concurrent --workers 20 --verbose
```

**Warning**: Verbose mode with many concurrent requests produces a LOT of output!

## Error Verbose Output

### Example: Payment Invalid
```
[0001] FAILED - HTTP 400
[0001] ========== ERROR RESPONSE ==========
[0001] Error: {
  "error": "payment_invalid",
  "message": "Signature verification failed",
  "details": "Invalid signature for transferWithAuthorization"
}
[0001] ===================================
```

### Example: Insufficient Funds
```
[0001] FAILED - HTTP 402
[0001] ========== ERROR RESPONSE ==========
[0001] Error: {
  "error": "insufficient_funds",
  "message": "Payer has insufficient USDC balance",
  "required": "10000",
  "available": "5000"
}
[0001] ===================================
```

### Example: Network Error
```
[0001] ERROR - Connection refused
[0001] Traceback: ...
  File "load_test.py", line 194, in make_paid_request
    response = requests.post(...)
  requests.exceptions.ConnectionError: ...
```

## Best Practices

1. **Use verbose for debugging**: Start with `--verbose` when testing new setups
2. **Disable for load tests**: Remove `--verbose` for high-volume tests (cleaner output)
3. **Save verbose output**: Redirect to file for later analysis
   ```bash
   python load_test.py --num-requests 10 --verbose > test_output.log 2>&1
   ```
4. **Check first request**: Always use `--verbose` for the first request to ensure everything works

## Quick Reference

| Command | Description |
|---------|-------------|
| `--verbose` | Enable verbose mode (full form) |
| `-v` | Enable verbose mode (short form) |
| No flag | Standard mode (concise output) |

## Performance Impact

- **Standard mode**: ~0.1s per request (with delay)
- **Verbose mode**: ~0.1s per request (minimal overhead)

Verbose mode only affects output, not performance. The logging is lightweight.

## Example Test Session

```bash
# 1. Test single request with full details
python load_test.py --num-requests 1 --verbose

# Output shows all request/response details

# 2. If successful, run larger test without verbose
python load_test.py --num-requests 100 --concurrent --workers 10

# Cleaner output for monitoring progress

# 3. If issues occur, re-run with verbose
python load_test.py --num-requests 5 --verbose

# Debug the specific failure
```
