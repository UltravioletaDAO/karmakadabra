---
title: USDC on Base
tags:
  - contract
  - usdc
  - base
---

## USDC on Base

- **Address**: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
- **Chain**: Base (Chain ID: 8453)
- **Decimals**: 6
- **Standard**: ERC-20 + EIP-3009 (gasless transfers)

## EIP-3009 Functions
- `transferWithAuthorization(from, to, value, validAfter, validBefore, nonce, v, r, s)`
- Enables gasless payments - agents sign off-chain, facilitator executes on-chain

## Related
- [[erc8004-registry]] - Agent identities
- [[x402-payment]] - Payment protocol
- [[eip3009-gasless]] - Gasless transfer details
