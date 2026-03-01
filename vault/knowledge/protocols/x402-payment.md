---
title: x402 Payment Protocol
tags:
  - protocol
  - x402
  - payments
---

## x402 Payment Protocol

- **Facilitator**: https://facilitator.ultravioletadao.xyz
- **Standard**: HTTP 402 Payment Required
- **Execution**: Stateless, verifies EIP-712 signatures

## Flow
1. Buyer signs payment authorization off-chain (EIP-712)
2. Buyer sends HTTP request with payment header
3. Facilitator verifies signature
4. Facilitator executes `transferWithAuthorization()` on-chain
5. Response returned to buyer

## Related
- [[eip3009-gasless]] - Underlying transfer mechanism
- [[usdc-base]] - Payment token
- [[execution-market]] - Where x402 payments originate
