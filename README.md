# x402 Protocol Compliant Implementation

This worktree contains **official x402 protocol-compliant** implementations of our test-seller services for both EVM and Solana (SVM) networks.

## Purpose

Create test-seller implementations that **exactly match** the official [Coinbase x402 protocol specification](https://github.com/coinbase/x402), enabling:

1. Correct payment flow (verify → process → settle)
2. Proper use of X-PAYMENT and X-PAYMENT-RESPONSE headers
3. Standard field naming (camelCase with Pydantic aliases)
4. Critical Solana-specific fields (`extra.feePayer`)
5. Compatibility with official x402 clients and facilitators

## Directory Structure

```
karmacadabra-x402-protocol/
├── .x402-reference/          # Official x402 repo (reference implementation)
├── test-seller-x402/         # EVM-compliant test seller (Base mainnet)
├── test-seller-solana-x402/  # SVM-compliant test seller (Solana mainnet)
├── ANALYSIS.md               # Detailed comparison of old vs new
└── README.md                 # This file
```

## Key Differences from Original Implementation

### Original (Custom) Implementation

**Request Flow:**
```
1. Client → GET /hello → Server
2. Server → 402 with custom structure → Client
3. Client → POST /hello with JSON body {"x402Payment": {...}} → Server
4. Server → POST /settle (directly) → Facilitator
5. Server → Response → Client
```

**Issues:**
- Custom 402 response structure (not standard)
- Payment in JSON body (not X-PAYMENT header)
- Skips `/verify` step
- No X-PAYMENT-RESPONSE header
- Missing `extra.feePayer` for Solana

### New (x402-Compliant) Implementation

**Request Flow:**
```
1. Client → GET /hello → Server
2. Server → 402 with x402PaymentRequiredResponse → Client
3. Client → POST /hello with X-PAYMENT header (base64) → Server
4. Server → POST /verify → Facilitator (validate payment)
5. Facilitator → VerifyResponse {isValid: true} → Server
6. Server processes resource
7. Server → POST /settle → Facilitator (execute transaction)
8. Facilitator → SettleResponse {success: true, transaction: "hash"} → Server
9. Server → Response + X-PAYMENT-RESPONSE header → Client
```

**Improvements:**
- Standard x402PaymentRequiredResponse structure
- X-PAYMENT header (base64-encoded PaymentPayload)
- Two-phase verify-then-settle flow
- X-PAYMENT-RESPONSE header with settlement details
- `extra.feePayer` field for Solana (CRITICAL)

## Quick Start

See `test-seller-x402/` and `test-seller-solana-x402/` directories for implementation details and deployment instructions.

## Critical Solana Field: `extra.feePayer`

**Why it's critical:**

In Solana, transactions require a **fee payer** who signs the transaction and pays for execution. The `extra.feePayer` field in PaymentRequirements tells clients which address will sign as fee payer (typically the facilitator).

**Without this field:**
- Client doesn't know who will sign as fee payer
- Can't construct transaction with correct signer positions
- Facilitator receives invalid/unsigned transaction
- Settlement fails silently

**This was the root cause of our original Solana settlement failures.**

## Protocol Compliance Checklist

### EVM Implementation
- [x] Returns `x402PaymentRequiredResponse` on GET (402)
- [x] Field naming: `maxAmountRequired`, `payTo`, `mimeType` (camelCase)
- [x] Accepts `X-PAYMENT` header (base64-encoded)
- [x] Calls facilitator `/verify` before processing
- [x] Calls facilitator `/settle` only on success (2xx)
- [x] Returns `X-PAYMENT-RESPONSE` header
- [x] EIP-3009 payload structure
- [x] EIP712Domain in `extra`

### Solana Implementation
- [x] Returns `x402PaymentRequiredResponse` on GET (402)
- [x] Field naming: `maxAmountRequired`, `payTo`, `mimeType` (camelCase)
- [x] **CRITICAL**: Includes `extra.feePayer` with facilitator pubkey
- [x] Accepts `X-PAYMENT` header (base64-encoded)
- [x] Calls facilitator `/verify` before processing
- [x] Calls facilitator `/settle` only on success (2xx)
- [x] Returns `X-PAYMENT-RESPONSE` header
- [x] Solana payload structure: `{transaction: "base64-encoded-tx"}`

## Official x402 Specification References

- **Protocol Overview**: `.x402-reference/README.md`
- **EVM (exact scheme)**: `.x402-reference/specs/schemes/exact/scheme_exact_evm.md`
- **Solana (exact scheme)**: `.x402-reference/specs/schemes/exact/scheme_exact_svm.md`
- **Python Implementation**: `.x402-reference/python/x402/`

See `ANALYSIS.md` for detailed comparison and migration guide.
