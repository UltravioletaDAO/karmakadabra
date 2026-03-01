---
title: ERC-8004 Identity Registry
tags:
  - contract
  - erc8004
  - base
---

## ERC-8004 Identity Registry

- **Address**: 0x8004A169FB4a3325136EB29fA0ceB6D2e539a432
- **Chain**: Base (Chain ID: 8453)
- **Standard**: ERC-8004 (Agent Identity)
- **Total KK Agents**: 24

## Key Functions
- `resolveByAddress(address)` -> AgentInfo struct
- `newAgent(name, domain, metadata)` -> registers new agent
- `updateAgent(agentId, name, domain, metadata)` -> updates existing

## Related
- [[usdc-base]] - Payment token
- [[x402-payment]] - Payment protocol
- [[execution-market]] - Task marketplace
