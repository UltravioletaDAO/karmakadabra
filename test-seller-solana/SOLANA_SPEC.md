# Solana x402 Payment Specification
**Source**: Facilitator implementation analysis (`Z:\ultravioleta\dao\facilitator\src\chain\solana.rs`)
**Author**: Rust expert analysis
**Date**: 2025-11-02

## Executive Summary

This document specifies the EXACT transaction structure required by the x402-rs facilitator for Solana payments, derived from analyzing the facilitator's Rust source code.

---

## Critical Requirements

### 1. Transaction Structure

**Facilitator expects** (`solana.rs:391-405`):
```
Position 0: SetComputeUnitLimit instruction
Position 1: SetComputeUnitPrice instruction
Position 2: TransferChecked OR CreateAssociatedTokenAccount
Position 3: TransferChecked (only if position 2 is CreateATA)
```

**For existing seller ATA** (3 instructions):
```rust
// Instruction 0
set_compute_unit_limit(200_000)

// Instruction 1
set_compute_unit_price(MAX: 5_000_000 microlamports)

// Instruction 2
transfer_checked(TransferCheckedParams {
    source: buyer_ata,        // Account 0 in instruction
    mint: usdc_mint,          // Account 1 in instruction
    dest: seller_ata,         // Account 2 in instruction
    owner: buyer_pubkey,      // Account 3 in instruction (authority)
    amount: price,
    decimals: 6,
})
```

### 2. Required Signers Structure

**CRITICAL** (`solana.rs:607-615`):
- The facilitator MUST be in the required signers list
- The facilitator's `sign()` method searches for its pubkey in `static_account_keys()[..num_required_signatures]`
- If NOT found → returns `"invalid_exact_svm_payload_transaction_simulation_failed"`

**Two valid approaches:**

**Option A: Facilitator as Fee Payer** (gasless for buyer):
```
required_signers = [facilitator_pubkey, buyer_pubkey]
signatures = [Signature::default(), buyer_signature]
```

**Option B: Buyer as Fee Payer** (buyer pays SOL fees):
```
required_signers = [buyer_pubkey, facilitator_pubkey]
signatures = [buyer_signature, Signature::default()]
```

**Option A is RECOMMENDED** for true gasless experience.

### 3. Blockhash Handling

**CRITICAL** (`solana.rs:410`):
```rust
replace_recent_blockhash: false  // Facilitator does NOT replace it
```

**Implications:**
- Client MUST fetch a RECENT blockhash from Solana RPC
- Hash.default() will fail simulation
- Blockhash must be valid at simulation time (~1-2 minutes window)

**Correct approach**:
```python
from solana.rpc.api import Client
client = Client("https://api.mainnet-beta.solana.com")
recent_blockhash = client.get_latest_blockhash().value.blockhash
```

### 4. Transaction Signing Flow

**Client Side:**
1. Create MessageV0 with facilitator as payer
2. Sign with buyer's keypair at correct position
3. Create partial transaction with placeholder for facilitator
4. Serialize to base64

**Facilitator Side** (`solana.rs:407, 470`):
1. Deserialize transaction from base64
2. Call `sign(&self.keypair)` → finds facilitator position, adds signature
3. Simulate transaction with `sig_verify: false`
4. If settle: sign again, verify fully_signed, send_and_confirm

### 5. Payer vs Authority

**Important distinction** (`solana.rs:427`):
```rust
let payer: SolanaAddress = transfer_instruction.authority.into();
```

- **Fee Payer** (position 0): Who pays SOL transaction fees (facilitator recommended)
- **Transfer Authority** (instruction account 3): Who authorizes the USDC transfer (buyer)
- **Returned payer**: The authority (buyer), NOT the fee payer

This is gasless: buyer doesn't pay SOL fees, only authorizes USDC transfer.

---

## Implementation from Golden Source

### Load Test Transaction Creation

```python
def create_transfer_transaction(buyer: Keypair, seller: Pubkey) -> str:
    """
    Creates partially-signed Solana transaction per facilitator spec.

    Facilitator requirements:
    - Position 0: compute_limit
    - Position 1: compute_price
    - Position 2: transfer_checked
    - Facilitator as fee payer (required signer #0)
    - Buyer signs at position determined by account_keys ordering
    - Recent blockhash from RPC (NOT Hash.default())
    """
    # ATAs
    buyer_ata = get_associated_token_address(buyer.pubkey(), USDC_MINT)
    seller_ata = get_associated_token_address(seller, USDC_MINT)

    # Instructions (per facilitator validation order)
    instructions = [
        set_compute_unit_limit(200_000),
        set_compute_unit_price(1_000_000),  # 1M microlamports, max 5M
        transfer_checked(TransferCheckedParams(
            program_id=TOKEN_PROGRAM_ID,
            source=buyer_ata,
            mint=USDC_MINT,
            dest=seller_ata,
            owner=buyer.pubkey(),  # Authority (reported as payer)
            amount=10_000,  # 0.01 USDC
            decimals=6,
        ))
    ]

    # Get RECENT blockhash (facilitator won't replace it)
    from solana.rpc.api import Client
    client = Client("https://api.mainnet-beta.solana.com")
    recent_blockhash = client.get_latest_blockhash().value.blockhash

    # Facilitator as fee payer (makes it required signer #0)
    FACILITATOR_PUBKEY = Pubkey.from_string("F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq")

    message = MessageV0.try_compile(
        payer=FACILITATOR_PUBKEY,
        instructions=instructions,
        address_lookup_table_accounts=[],
        recent_blockhash=recent_blockhash,
    )

    # Find buyer position in required signers
    num_required = message.header.num_required_signatures
    static_keys = list(message.account_keys)
    buyer_pos = static_keys[:num_required].index(buyer.pubkey())

    # Create signature list with placeholders
    from solders.signature import Signature as SoldersSignature
    signatures = [SoldersSignature.default()] * num_required

    # Buyer signs the message
    msg_bytes = bytes(message)
    buyer_signature = buyer.sign_message(msg_bytes)
    signatures[buyer_pos] = buyer_signature

    # Create partial transaction
    tx = VersionedTransaction.populate(message, signatures)

    # Serialize to base64
    tx_bytes = bytes(tx)
    return base64.b64encode(tx_bytes).decode('utf-8')
```

### x402 Payment Payload

```python
payload = {
    "x402Version": 1,
    "paymentPayload": {
        "x402Version": 1,
        "scheme": "exact",
        "network": "solana",  # or "solana-devnet"
        "payload": {
            "transaction": transaction_b64
        }
    },
    "paymentRequirements": {
        "scheme": "exact",
        "network": "solana",
        "maxAmountRequired": "10000",  # String, not int
        "resource": "https://seller.example.com/resource",  # Full URL required
        "description": "Purchase description",
        "mimeType": "application/json",
        "payTo": str(seller_pubkey),  # Seller's Solana address
        "maxTimeoutSeconds": 60,
        "asset": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC mainnet
        "extra": {
            "name": "USD Coin",
            "decimals": 6
        }
    }
}
```

### Test Seller Implementation

```python
@app.post("/resource")
async def sell_resource(payment: X402PaymentSolana):
    """
    Validates and forwards payment to facilitator.

    Facilitator responses:
    - Validation failure: {"isValid": false, "invalidReason": "..."}
    - Settlement success: {"success": true, "payer": "...", "transaction": "..."}
    - Settlement failure: {"success": false, "error_reason": "..."}
    """
    # Validate payment structure
    if payment.paymentRequirements.maxAmountRequired != EXPECTED_PRICE:
        raise HTTPException(402, "Incorrect price")

    if payment.paymentRequirements.payTo != SELLER_PUBKEY:
        raise HTTPException(402, "Incorrect recipient")

    if payment.paymentRequirements.asset != USDC_MINT:
        raise HTTPException(402, "Incorrect asset")

    # Forward to facilitator
    response = requests.post(
        f"{FACILITATOR_URL}/settle",
        json=payment.dict(),
        timeout=90  # Solana confirmation can take 60-90s
    )

    if response.status_code != 200:
        raise HTTPException(402, f"Facilitator error: {response.text}")

    data = response.json()

    # Check if it's a validation response or settlement response
    if "isValid" in data and not data["isValid"]:
        # Validation failed
        reason = data.get("invalidReason", "Unknown validation error")
        raise HTTPException(402, f"Payment validation failed: {reason}")

    if not data.get("success"):
        # Settlement failed
        reason = data.get("error_reason", "Unknown settlement error")
        raise HTTPException(402, f"Payment settlement failed: {reason}")

    # Success!
    tx_hash = data.get("transaction")
    payer = data.get("payer")  # This is the buyer (authority), not fee payer

    return {
        "message": "Resource delivered",
        "tx_hash": tx_hash,
        "payer": payer
    }
```

---

## Common Errors & Solutions

### Error: `invalid_exact_svm_payload_transaction_simulation_failed`

**Cause 1**: Facilitator not in required signers
- **Solution**: Use facilitator as fee payer OR add facilitator as additional signer

**Cause 2**: Simulation actually failed (insufficient balance, invalid ATA, etc.)
- **Solution**: Check buyer has USDC and SOL, seller ATA exists

**Cause 3**: Stale blockhash
- **Solution**: Fetch recent blockhash, ensure < 2 minutes old

### Error: 90-second timeout

**Cause**: Transaction is valid but stuck in `send_and_confirm()` loop
- **Likely**: Network congestion or transaction dropped
- **Solution**: Check Solana status, verify transaction wasn't confirmed

### Error: `undersigned transaction`

**Cause**: Buyer didn't sign, or signature in wrong position
- **Solution**: Verify buyer_pos calculation, ensure signature placed correctly

---

## Testing Checklist

**Before testing:**
- [ ] Seller ATA created and exists on-chain
- [ ] Buyer has USDC balance ≥ payment amount
- [ ] Buyer has SOL balance ≥ 0.001 (for emergencies)
- [ ] Facilitator wallet has SOL for transaction fees

**Transaction validation:**
- [ ] 3 instructions (compute_limit, compute_price, transfer_checked)
- [ ] Facilitator in required signers (position 0 as payer)
- [ ] Buyer signature at correct position
- [ ] Recent blockhash (< 2 minutes old)
- [ ] All amounts match (transaction vs requirements)

**Response validation:**
- [ ] Seller checks `isValid` field for validation errors
- [ ] Seller checks `success` field for settlement errors
- [ ] Transaction hash returned and viewable on Solscan
- [ ] Payer matches buyer pubkey (authority)

---

## Network-Specific Values

### Mainnet
- **Network**: `"solana"`
- **RPC**: `https://api.mainnet-beta.solana.com`
- **USDC Mint**: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- **Facilitator**: `F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq`
- **Explorer**: `https://solscan.io/tx/{signature}`

### Devnet
- **Network**: `"solana-devnet"`
- **RPC**: `https://api.devnet.solana.com`
- **USDC Mint**: (varies by deployment)
- **Facilitator**: (check `/networks` endpoint)
- **Explorer**: `https://solscan.io/tx/{signature}?cluster=devnet`

---

## References

**Source code**:
- `facilitator/src/chain/solana.rs:348-429` - verify_transfer
- `facilitator/src/chain/solana.rs:600-623` - sign()
- `facilitator/src/chain/solana.rs:468-493` - settle()
- `facilitator/src/chain/solana.rs:213-345` - verify_transfer_instruction

**Key insights**:
1. Facilitator searches for its pubkey in required signers (line 610-615)
2. Facilitator does NOT replace blockhash (line 410)
3. Payer returned is authority, not fee payer (line 427)
4. Simulation must pass before settlement (line 417-425)
5. Full signing verification before send (line 472)
