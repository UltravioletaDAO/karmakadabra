---
title: EIP-3009 Gasless Transfers
tags:
  - protocol
  - eip3009
  - gasless
---

## EIP-3009: Transfer With Authorization

Enables token transfers where the sender signs an off-chain authorization, and a third party (facilitator) submits the transaction and pays gas.

## Key Points
- Agents don't need ETH/AVAX for gas
- Nonces are random (not sequential) - prevents replay attacks
- Signatures use EIP-712 typed data
- `validAfter` and `validBefore` set time window (in SECONDS, not milliseconds)

## Related
- [[x402-payment]] - Protocol that uses EIP-3009
- [[usdc-base]] - Token that implements EIP-3009
