# GLUE Payment Debugging Summary - WSL Session
**Date**: 2025-10-30
**Status**: ⚠️ EIP-712 Parameters Fixed, Payment Still Failing

## 🎯 Problem Identified
GLUE token payments were failing with HTTP 402 "Payment verification failed". Root cause was **EIP-712 domain parameter mismatch**.

## ✅ Fixes Applied

### 1. On-Chain Contract Parameters (Verified)
```
Token Address: 0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
Network: Avalanche Fuji (Chain ID: 43113)
Token name(): "GLUE Token" (exactly 10 characters)
Token symbol(): "GLUE"
EIP-712 version: "1" (from ERC20Permit)
DOMAIN_SEPARATOR: 0xc536b159d4002c0f707b67357db52990aabd3392b6e32c1f8e37d5651a1ccf45
```

**Critical Discovery**: The deployed contract uses `"GLUE Token"` as the name, NOT `"Gasless Ultravioleta DAO Extended Token"` as shown in the source code at `erc-20/src/GLUE.sol:80`.

### 2. Facilitator Fixed (`x402-rs`)
**File**: `/mnt/z/ultravioleta/dao/karmacadabra/x402-rs/src/network.rs`
**Line**: 198-212

```rust
/// Lazily initialized known GLUE deployment on Avalanche Fuji testnet as [`USDCDeployment`].
/// NOTE: Karmacadabra uses GLUE token, not USDC, on Fuji testnet.
static USDC_AVALANCHE_FUJI: Lazy<USDCDeployment> = Lazy::new(|| {
    USDCDeployment(TokenDeployment {
        asset: TokenAsset {
            address: address!("0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743").into(),  // ✅ GLUE address
            network: Network::AvalancheFuji,
        },
        decimals: 6,
        eip712: Some(TokenDeploymentEip712 {
            name: "GLUE Token".into(),  // ✅ Fixed from "Gasless..."
            version: "1".into(),        // ✅ Fixed from "2"
        }),
    })
});
```

**Deployment**:
- ✅ Built: `cargo build --release`
- ✅ Docker image: `sha256:df96b6bbeecc8fb65ad5af69b27039e9e25c85aac2088f06dc159c2e5f694891`
- ✅ Pushed to ECR: `518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/facilitator:latest`
- ✅ Deployed on ECS: Task running with correct image

### 3. karma-hello Fixed
**File**: `/mnt/z/ultravioleta/dao/karmacadabra/agents/karma-hello/x402_middleware.py`
**Line**: 144-147

```python
"extra": {
    "name": "GLUE Token",  # ✅ Fixed from "Gasless..."
    "version": "1"
}
```

**Deployment**:
- ✅ Built: `docker build -f Dockerfile.agent --build-arg AGENT_NAME=karma-hello`
- ✅ Docker image: `sha256:da19d76a55b82867d54537107f73537737e0c5101e3aae3264bcbe8ca1cb114e`
- ✅ Pushed to ECR: `518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/karma-hello:latest`
- ✅ Deployed on ECS: Task running with correct image (started: 1761824718)

### 4. Test Script Fixed
**File**: `/mnt/z/ultravioleta/dao/karmacadabra/scripts/test_glue_payment_simple.py`
**Line**: 44-50

```python
domain = {
    "name": "GLUE Token",  # ✅ Fixed
    "version": "1",        # ✅ Fixed
    "chainId": CHAIN_ID,
    "verifyingContract": Web3.to_checksum_address(GLUE_TOKEN)
}
```

## ⚠️ Current Status

**All fixes deployed and verified**, but payments still fail with:
```
HTTP Status: 402
Response: {"detail":"Payment verification failed - transaction not executed"}
```

### Verified Working:
- ✅ EIP-712 domain parameters match on-chain contract
- ✅ Facilitator has correct GLUE config
- ✅ karma-hello sends correct extra fields
- ✅ Test signatures are valid (verified against computed domain separator)
- ✅ Buyer has sufficient balance (220,000 GLUE)
- ✅ Both services are healthy and responding

### Still Unknown:
- ❌ Why facilitator rejects the payment after all fixes
- ❌ Whether facilitator is actually receiving the correct parameters
- ❌ If there's another validation step failing

## 🔍 Debugging Steps for Next Session

### 1. Check Facilitator Logs
The facilitator should log why it's rejecting payments. Check ECS logs:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/karmacadabra-prod-facilitator \
  --start-time $(($(date +%s) - 600))000 \
  --region us-east-1
```

Look for:
- Signature verification failures
- Balance check failures  
- Domain separator mismatches
- Any error messages

### 2. Test Facilitator Directly
Create a minimal test that calls `/settle` with known-good parameters:
```python
# Test script at scripts/test_glue_payment_simple.py exists
python3 scripts/test_glue_payment_simple.py
```

If still fails, try `/verify` endpoint first to see detailed error.

### 3. Compare with Working USDC
Check if facilitator works with actual USDC on Fuji to isolate if it's a GLUE-specific issue:
```bash
# USDC on Fuji: 0x5425890298aed601595a70AB815c96711a31Bc65
```

### 4. Check Contract Balance Requirements
Verify the facilitator wallet has AVAX for gas:
```python
from web3 import Web3
w3 = Web3(Web3.HTTPProvider("https://avalanche-fuji-c-chain-rpc.publicnode.com"))
facilitator = "0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8"
balance = w3.eth.get_balance(facilitator)
print(f"Facilitator AVAX: {w3.from_wei(balance, 'ether')} AVAX")
```

### 5. Verify Signature Format
The signature might need to be in a specific format. Check:
- Is it 65 bytes (r=32, s=32, v=1)?
- Is v=27 or v=28 (not v=0 or v=1)?
- Are r and s properly hex-encoded with 0x prefix?

## 📊 EIP-712 Verification Test Results

```python
# Verification test performed:
On-chain DOMAIN_SEPARATOR: c536b159d4002c0f707b67357db52990aabd3392b6e32c1f8e37d5651a1ccf45

Version '1' + "GLUE Token":
  Computed: c536b159d4002c0f707b67357db52990aabd3392b6e32c1f8e37d5651a1ccf45
  Match: ✅ TRUE

Version '2' + "GLUE Token":
  Computed: f1a150679ee16f864172545fa5edacc7825752b992315283f01cc6846efcec02
  Match: ❌ FALSE
```

## 🔧 Files Modified

1. `x402-rs/src/network.rs` (lines 198-212)
2. `agents/karma-hello/x402_middleware.py` (lines 144-147)
3. `scripts/test_glue_payment_simple.py` (lines 44-50)

## 📝 Git Status

All changes are currently **uncommitted**. Consider:
```bash
git status  # See modified files
git diff    # Review changes
git add x402-rs/src/network.rs agents/karma-hello/x402_middleware.py scripts/test_glue_payment_simple.py
git commit -m "Fix EIP-712 parameters to match deployed GLUE contract

- Update facilitator to use 'GLUE Token' name and version '1'
- Update karma-hello middleware to send correct EIP-712 params
- Update test script with correct domain parameters

Verified against on-chain DOMAIN_SEPARATOR: c536b159...
"
```

## 🎯 Next Actions

1. **Immediate**: Check facilitator logs for rejection reason
2. **Test**: Verify facilitator can process ANY valid payment
3. **Debug**: Add more logging to karma-hello middleware
4. **Consider**: Test with a fresh wallet to rule out nonce issues
5. **Fallback**: Try redeploying contracts with correct name in source code

## 💡 Lessons Learned

1. **Always verify on-chain data** - Don't trust source code matches deployed contracts
2. **EIP-712 is extremely sensitive** - Even minor mismatches cause signature failures
3. **Version numbers matter** - "1" vs "2" creates completely different domain separators
4. **Test incrementally** - Verify each layer (domain separator, signature, facilitator) separately

