---
name: kk-x402
description: Sign EIP-3009 USDC payment authorizations for the x402 HTTP payment protocol on Base mainnet.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["KK_AGENT_NAME"]
---

# kk-x402

x402 payment signing for KarmaCadabra agents. Produces EIP-3009 `transferWithAuthorization` signatures that the x402 facilitator executes on-chain. This is the core payment mechanism that enables agents to buy and sell data without holding ETH for gas.

## Constants

| Constant | Value |
|----------|-------|
| USDC Contract (Base) | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| Chain ID | `8453` (Base mainnet) |
| Facilitator URL | `https://facilitator.ultravioletadao.xyz` |
| USDC Decimals | `6` |

## Script

### sign_payment.py

Located at `scripts/kk/sign_payment.py`. Signs an EIP-3009 `transferWithAuthorization` for USDC on Base.

```bash
python3 scripts/kk/sign_payment.py --agent kk-karma-hello --to 0xRecipientAddress --amount 0.01
```

Arguments:
- `--agent` (required): Agent name. Used to look up wallet address in `data/config/wallets.json` and private key from env var or AWS Secrets Manager.
- `--to` (required): Recipient wallet address (the seller's address)
- `--amount` (required): Amount in USDC (float, e.g., `0.01` = 1 cent)

Output:
```json
{
  "from": "0xBuyerAddress",
  "to": "0xSellerAddress",
  "value": "10000",
  "amount_usdc": "0.010000",
  "validAfter": 0,
  "validBefore": 1740600000,
  "nonce": "0xrandom32bytes...",
  "v": 27,
  "r": "0x...",
  "s": "0x...",
  "signature": "full_hex_signature",
  "network": "base",
  "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
}
```

## Payment Flow

The x402 protocol works as follows:

1. **Buyer agent** discovers a seller's HTTP endpoint (via IRC or EM)
2. Buyer makes an HTTP request to the seller's endpoint
3. Seller responds with `HTTP 402 Payment Required` and includes pricing info
4. Buyer signs an EIP-3009 authorization using `sign_payment.py`
5. Buyer re-sends the request with the signed authorization in the `X-PAYMENT` header
6. Seller's middleware forwards the authorization to the facilitator
7. **Facilitator** calls `transferWithAuthorization()` on the USDC contract on Base
8. Funds transfer from buyer to seller on-chain
9. Seller returns the requested data

## EIP-3009 Details

The signature authorizes a single USDC transfer with:
- **validAfter**: 0 (immediately valid)
- **validBefore**: current time + 1 hour
- **nonce**: random 32-byte value (prevents replay attacks)

The authorization is gasless for the signer. The facilitator pays the gas to execute the transfer on-chain.

## Dependencies

- `web3`, `eth_account` (signing)
- `shared.contracts_config` (network and token config)
- Private key from `PRIVATE_KEY` env var or AWS Secrets Manager

## Error Handling

Exit code 1 on failure with JSON error to stderr:
```json
{"error": "No private key available for kk-karma-hello. Set PRIVATE_KEY env var or configure AWS credentials."}
```
