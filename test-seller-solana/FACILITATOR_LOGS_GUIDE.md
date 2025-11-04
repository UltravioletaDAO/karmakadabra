# How to Check Facilitator Logs

## Current Status

✅ **Buyer Balance**: 4.585501 USDC (sufficient)
✅ **Seller ATA**: Exists with 0.24 USDC
✅ **Facilitator SOL**: 0.11 SOL (sufficient)
✅ **Transaction Validation**: Passes `/verify` endpoint
❌ **Settlement**: Times out after 90s

## Facilitator Deployment Location

According to `DEPLOYMENT.md`, the facilitator is deployed on **Cherry Servers** (not AWS ECS).

**URL**: https://facilitator.ultravioletadao.xyz
**Server**: Cherry Servers VPS running Docker

## How to Access Logs

### Option 1: SSH to Cherry Servers (If you have access)

```bash
# SSH into the server
ssh user@facilitator-server-ip

# Check facilitator Docker container logs
docker ps | grep facilitator
docker logs -f <container-id> --tail 100

# Or if using docker-compose
cd /path/to/facilitator
docker-compose logs -f facilitator --tail 100
```

### Option 2: Check Docker Logs

```bash
# List all running containers
docker ps

# Get facilitator logs
docker logs <facilitator-container-id> -f

# Filter for Solana-specific logs
docker logs <facilitator-container-id> --tail 500 | grep -i "solana\|settlement\|transaction"
```

### Option 3: Check systemd/service logs (if running as service)

```bash
# If facilitator is running as a systemd service
sudo journalctl -u facilitator -f --since "5 minutes ago"

# Or check general logs
sudo journalctl -f | grep facilitator
```

## What to Look For in Logs

After enabling logging (per STATUS_REPORT.md), you should see:

### 1. Transaction Submission
```
Submitting Solana transaction for settlement. Network: solana, Payer: Hn344Scr...
```

### 2. Transaction Signature (If sent successfully)
```
Sending transaction to Solana...
Transaction signature: <signature>
```

### 3. Confirmation Success
```
Transaction confirmed successfully! Signature: <sig>
Explorer: https://solscan.io/tx/<sig>
```

### 4. Timeout Error (If timeout fix was applied)
```
Transaction confirmation timeout after 60s. Signature: <sig>
Explorer: https://solscan.io/tx/<sig>
```

### 5. Other Errors
```
Transaction settlement failed. Error: <error details>
```

## Expected Log Flow for Our Test

When running:
```bash
python load_test_solana_v4.py --seller Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB --num-requests 1
```

**Expected facilitator logs**:
1. Request received at `/settle`
2. Transaction validation starts
3. Signature verification
4. Simulation
5. **"Submitting Solana transaction for settlement..."** ← Critical log
6. Transaction sent to RPC
7. Either:
   - "Transaction confirmed successfully!" + signature
   - "Transaction confirmation timeout after 60s" + signature

## If You Don't See Logs

### Check if logging was actually enabled

The facilitator should have these changes in `src/chain/solana.rs`:

```rust
// Around line 468
tracing::info!(
    "Submitting Solana transaction for settlement. Network: {}, Payer: {}",
    self.network(),
    verification.payer.pubkey
);
```

### Verify log level is set to INFO

Check facilitator's environment variables or config:
```bash
# Should have
RUST_LOG=info

# Or more verbose
RUST_LOG=debug
```

### Restart facilitator after logging changes

```bash
# If using Docker
docker-compose restart facilitator

# If using systemd
sudo systemctl restart facilitator

# Check it's running
curl https://facilitator.ultravioletadao.xyz/health
```

## Manual Test to Trigger Logs

Run this command which should generate logs immediately:

```bash
cd Z:\ultravioleta\dao\karmacadabra\test-seller-solana
python test_verify_only.py
```

This hits `/verify` only (no settlement), so you should see validation logs without the 90s wait.

## Next Steps

1. **Access facilitator logs** using one of the methods above
2. **Run test again** while tailing logs:
   ```bash
   # Terminal 1 (server): tail logs
   docker logs -f <facilitator-container> --tail 50

   # Terminal 2 (local): run test
   python load_test_solana_v4.py --seller Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB --num-requests 1
   ```

3. **Look for transaction signature** in logs
4. **Check transaction on Solscan**: https://solscan.io/tx/{signature}
5. **Report what you find**:
   - Is transaction sent to Solana?
   - Does it appear on-chain?
   - Is it confirmed, pending, or failed?
   - What's the actual error message from Solana RPC?

## Troubleshooting Guide

### If logs show "Transaction sent" but never confirms:

**Possible causes**:
1. Network congestion (unlikely with max priority fee)
2. RPC endpoint issues
3. Transaction being rejected silently

**Solution**: Check transaction on Solscan with signature from logs

### If logs show no transaction sent:

**Possible causes**:
1. Error before `send()` call
2. Logging not enabled correctly
3. Different code path being executed

**Solution**: Enable `RUST_LOG=debug` for more verbose logging

### If no logs appear at all:

**Possible causes**:
1. Wrong container/service
2. Logs being written to file instead of stdout
3. Facilitator not restarted after logging changes

**Solution**: Verify facilitator is running updated code

---

## Summary

**Current evidence**:
- ✅ All accounts funded correctly
- ✅ Transaction structure valid (passes `/verify`)
- ❌ Settlement times out → need facilitator logs to diagnose

**Most likely issue**: Transaction is sent but not confirming on Solana blockchain

**Action required**: Access facilitator server logs to see transaction signature and actual error
