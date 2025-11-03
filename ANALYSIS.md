# x402 Protocol Compliance Analysis

## Current Implementation vs Official Protocol

### test-seller (EVM) - Key Differences

#### 1. **402 Response Structure** ❌
**Current:**
```json
{
  "error": "payment_required",
  "message": "Payment required to access this resource",
  "x402": {
    "version": 1,
    "accepts": [...]
  }
}
```

**Official x402:**
```json
{
  "x402Version": 1,
  "accepts": [...],
  "error": "Payment required to access this resource"
}
```

#### 2. **Payment Flow** ❌
**Current:**
- Client sends POST request with payment in JSON body
- Body format: `{"x402Payment": {paymentPayload, paymentRequirements}}`
- Server calls facilitator `/settle` directly

**Official x402:**
- Client sends request with `X-PAYMENT` header (base64 encoded)
- Server extracts header, calls facilitator `/verify` first
- If valid, processes request and returns 2xx
- Only on 2xx response, calls facilitator `/settle`
- Returns `X-PAYMENT-RESPONSE` header with settlement result

#### 3. **Middleware Pattern** ❌
**Current:** Manual implementation with explicit payment handling

**Official x402:** Uses `require_payment()` middleware decorator:
```python
from x402.fastapi.middleware import require_payment

@app.get("/hello")
@require_payment(
    price="0.01",  # or TokenAmount
    pay_to_address=SELLER_ADDRESS,
    description="Hello World message",
    network="base"
)
async def hello(request: Request):
    # Middleware handles all payment logic
    return {"message": "Hello World"}
```

#### 4. **Field Naming** ❌
**Current:** Inconsistent camelCase/snake_case

**Official:** Strict camelCase for protocol fields with Pydantic aliases:
- `maxAmountRequired` (not `max_amount_required`)
- `payTo` (not `pay_to`)
- `maxTimeoutSeconds` (not `max_timeout_seconds`)

#### 5. **PaymentRequirements Extra Field** ⚠️
**Current (EVM):**
```json
"extra": {
  "name": "USD Coin",
  "version": "2"
}
```

**Official (EVM):**
```json
"extra": {
  "name": "USD Coin",
  "version": "2"
}
```
✅ This part is actually correct for EVM (EIP712Domain info)

---

### test-seller-solana (SVM) - Key Differences

#### 1. **Missing GET Endpoint** ❌
**Current:** Only POST /hello exists

**Official:** Must have GET endpoint that returns 402 with PaymentRequirements

#### 2. **Missing Critical Fields** ❌
**Current PaymentRequirements:**
```json
{
  "scheme": "exact",
  "network": "solana",
  "maxAmountRequired": "10000",
  "asset": "EPj...",
  "payTo": "seller-pubkey",
  // Missing extra.feePayer ❌
}
```

**Official PaymentRequirements (SVM):**
```json
{
  "scheme": "exact",
  "network": "solana",
  "maxAmountRequired": "10000",
  "asset": "EPj...",
  "payTo": "seller-pubkey",
  "extra": {
    "feePayer": "facilitator-pubkey"  // ⚠️ CRITICAL - facilitator must sign as fee payer
  }
}
```

#### 3. **Payment Flow** ❌
**Current:**
- POST /hello with full payment in body
- Direct call to facilitator `/settle`

**Official:**
- GET /hello → 402 with requirements
- Client creates partially-signed transaction
- POST with `X-PAYMENT` header
- Server calls `/verify`, then processes, then `/settle` on success

#### 4. **Response Headers** ❌
**Current:** No special headers

**Official:** Must include `X-PAYMENT-RESPONSE` header on successful payment

---

## Protocol Specification Summary

### Official x402 Flow (Both EVM and SVM)

```
1. Client → GET /resource → Server
2. Server → 402 Response with PaymentRequirements → Client
3. Client creates payment authorization (EIP-3009 or Solana tx)
4. Client → Request with X-PAYMENT header → Server
5. Server → POST /verify → Facilitator
6. Facilitator → VerifyResponse {isValid: true} → Server
7. Server processes request → generates 2xx response
8. Server → POST /settle → Facilitator
9. Facilitator → SettleResponse {success: true, transaction: "hash"} → Server
10. Server → 2xx + X-PAYMENT-RESPONSE header → Client
```

### Key Requirements

#### For Resource Servers:
1. ✅ Return proper `x402PaymentRequiredResponse` structure on 402
2. ✅ Accept payment in `X-PAYMENT` header (base64 encoded)
3. ✅ Call facilitator `/verify` before processing
4. ✅ Only call facilitator `/settle` if resource generation succeeds (2xx)
5. ✅ Include `X-PAYMENT-RESPONSE` header in successful response

#### For SVM (Solana):
1. ✅ Include `extra.feePayer` with facilitator pubkey in PaymentRequirements
2. ✅ Client creates partially-signed transaction (client + placeholder for facilitator)
3. ✅ Facilitator adds signature as fee payer and submits

#### For EVM (Ethereum/Base):
1. ✅ Include EIP712Domain info in `extra` field
2. ✅ Client signs EIP-3009 transferWithAuthorization
3. ✅ Facilitator executes the signed authorization

---

## Migration Strategy

### Phase 1: Create New Compliant Implementations
- [ ] Install official `x402` Python package
- [ ] Create `test-seller-x402/` using official middleware
- [ ] Create `test-seller-solana-x402/` using official types
- [ ] Test against official facilitator

### Phase 2: Update Clients
- [ ] Update `load_test.py` to use X-PAYMENT header
- [ ] Update `load_test_solana_v4.py` to include feePayer in requirements
- [ ] Test end-to-end flow

### Phase 3: Documentation
- [ ] Document migration path from custom to official protocol
- [ ] Update architecture docs
- [ ] Create comparison guide

---

## Dependencies

### Official x402 Python Package
```bash
pip install x402
```

Provides:
- `x402.fastapi.middleware.require_payment()` - FastAPI decorator
- `x402.types.PaymentRequirements` - Pydantic models
- `x402.facilitator.FacilitatorClient` - HTTP client for facilitator
- Automatic handling of verify/settle flow
- Base64 encoding/decoding of headers

### Without Package (Manual Implementation)
Must implement:
1. Base64 encoding/decoding of X-PAYMENT header
2. Proper camelCase field naming with Pydantic aliases
3. Two-phase verify then settle flow
4. X-PAYMENT-RESPONSE header generation

---

## Critical Findings

### Why Our Current Implementation Fails Settlement

**Root Cause 1: Missing Verify Step**
We call `/settle` directly without calling `/verify` first. The official protocol requires:
1. Call `/verify` to validate payment structure
2. Process the resource request
3. Only call `/settle` if processing succeeds

**Root Cause 2 (Solana): Missing feePayer**
Our PaymentRequirements don't include `extra.feePayer`, so clients don't know which address will sign as fee payer.

**Root Cause 3: Wrong Request Structure**
We send `{x402Version, paymentPayload, paymentRequirements}` in body, but should send base64-encoded payment in `X-PAYMENT` header.

---

## Next Steps

1. Create compliant test-seller implementations in this worktree
2. Test with official x402 Python package
3. Verify against facilitator with proper logging
4. Document differences and migration path
