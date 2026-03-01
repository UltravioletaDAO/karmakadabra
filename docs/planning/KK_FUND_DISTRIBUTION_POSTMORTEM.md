# KK V2 Fund Distribution — Postmortem & Next Steps

**Date**: 2026-02-22
**Author**: 0xultravioleta + Claude Code
**Status**: COMPLETE — 8/8 chains PASS, 24 agents funded

---

## Summary

Distributed 5 stablecoins (USDC, EURC, AUSD, PYUSD, USDT) + native gas tokens to 24 Karma Kadabra V2 agent wallets across 8 EVM chains (Base, Ethereum, Polygon, Arbitrum, Avalanche, Optimism, Celo, Monad). Total ~219 on-chain transactions confirmed.

---

## Final Distribution Matrix

| Chain | Tokens per Agent | Gas per Agent | TXs | Method |
|-------|-----------------|---------------|-----|--------|
| Base | USDC $0.10 + EURC $0.10 | 0.0002 ETH | 4 | Disperse batch |
| Ethereum | USDC $0.10 + PYUSD $0.12 + EURC $0.12 + AUSD $0.12 | 0.0003 ETH | ~11 | Disperse batch + manual retry |
| Polygon | USDC $0.04 + AUSD $0.04 | 0.1 POL | 5 | Disperse batch |
| Arbitrum | USDC $0.10 + USDT $0.10 | 0.0002 ETH | 5 | Disperse batch |
| Avalanche | USDC $0.10 + EURC $0.10 + AUSD $0.10 | 0.005 AVAX | 96 | Sequential (no Disperse) |
| Optimism | USDC $0.10 | 0.0002 ETH | 3 | Disperse batch |
| Celo | USDT $0.10 | 0.01 CELO | 48 | Sequential (no Disperse) |
| Monad | USDC $0.10 + AUSD $0.10 | 0.01 MON | 72 | Sequential (no Disperse) |

---

## Lessons Learned

### 1. Disperse.app is NOT universal

**Bug**: `Disperse.app` (`0xD152f549545093347A162Dce210e7293f1452150`) is deployed via CREATE2 on some chains but **NOT on Avalanche, Celo, or Monad**. Sending a transaction to an empty address on EVM returns `success` with minimal gas (~34k) but **does nothing** — tokens are never moved, gas ETH/AVAX is burned on the call overhead.

**Impact**: An entire Avalanche distribution (7 "confirmed" TXs) was a no-op. Session memory recorded PASS incorrectly.

**Fix**:
- Added `getCode()` verification to detect empty contract addresses
- Set `disperseAvailable: false` for Avalanche in `chains.ts`
- **Rule**: Always verify contract deployment with `getCode()` before interacting

**Verified Disperse.app deployment**:
| Chain | Deployed | Bytecode |
|-------|----------|----------|
| Base | YES | 3562 bytes |
| Ethereum | YES | 3562 bytes |
| Polygon | YES | 3562 bytes |
| Arbitrum | YES | 3562 bytes |
| Optimism | YES | 3562 bytes |
| Avalanche | **NO** | 0x |
| Celo | **NO** | 0x |
| Monad | **NO** | 0x |

### 2. QuikNode drops large Ethereum L1 TXs

**Bug**: QuikNode private RPC drops Ethereum L1 transactions >500k gas from its mempool. The TX gets submitted, appears pending, then silently disappears. `waitForTransactionReceipt` times out.

**Impact**: Multiple EURC and AUSD distribution attempts failed (3+ retries, ~30 min wasted per attempt).

**Fix**: Use **LlamaRPC** (`https://eth.llamarpc.com`) for send+poll on Ethereum L1 large TXs. QuikNode works fine for reads, small TXs, and all L2 chains.

**Rule**: Always prefer QuikNode private RPCs from `.env.local`. Only fall back to public RPCs when QuikNode fails for specific known issues (Ethereum L1 large TX mempool drop).

### 3. Nonce management on Ethereum L1

**Issue**: When TXs drop from mempool, nonces can get stuck. Pending nonce > confirmed nonce = gap that blocks all subsequent TXs.

**Fix**: Created `unstick-eth-nonce.ts` — sends 0-value self-transfer at stuck nonce with 10 gwei tip to clear the gap. Then retry the actual TX.

**Rule**: Always check `confirmed nonce === pending nonce` before retrying. If gap exists, clear it first.

### 4. EVM success != actual execution

**Critical insight**: On EVM, sending a TX to an address with no code returns `success`. The TX is valid, gas is consumed, but nothing happens. This is by design — EVM doesn't revert on calls to empty addresses unless the function signature expects a return value that isn't provided.

**Rule**: Never trust `receipt.status === "success"` alone. Always verify the actual state change (check balances, events, storage).

### 5. Windows inline TSX doesn't work

**Issue**: `npx tsx -e "..."` with complex TypeScript fails on Windows due to quote escaping issues (double quotes inside double quotes, template literals, etc.).

**Fix**: Always write a `.ts` file and run `npx tsx script.ts` instead of inline evaluation.

### 6. Session memory can be wrong

**Issue**: A Claude Code session crashed mid-work. The auto-memory file (`kk-fund-distribution.md`) had been updated to show "Avalanche PASS" before the actual on-chain verification. The new session inherited incorrect state.

**Fix**: Always verify on-chain state independently before trusting memory. Run `spot-check-agents.ts` or direct RPC queries to confirm balances. Don't rely on previous session notes for financial data.

---

## Scripts Created

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `distribute-funds.ts` | Multi-token batch distribution | Primary tool — distribute tokens + gas on any chain |
| `distribute-gas-only.ts` | Gas-only distribution | When agents have tokens but need gas |
| `distribute-eth-gas.ts` | Ethereum L1 gas via LlamaRPC | ETH gas distribution (manual polling, 0.5 gwei tip) |
| `spot-check-agents.ts` | Verify all 24 agent wallets | After any distribution — the source of truth |
| `check-full-inventory.ts` | Master wallet balances | Before distribution — check what's available |
| `check-eth-nonce.ts` | Diagnose stuck nonces | When Ethereum TXs are timing out |
| `unstick-eth-nonce.ts` | Clear stuck nonces + retry | When nonce gap blocks Ethereum TXs |
| `fix-eth-eurc.ts` | EURC distribution with dual RPC | Specialized retry for EURC on Ethereum |
| `retry-ausd.ts` | AUSD retry via LlamaRPC | Specialized retry for AUSD on Ethereum |
| `distribute-ausd-eth.ts` | AUSD approve+disperse on Ethereum | One-shot AUSD distribution |
| `sweep-funds.ts` | Recover all funds from agents | Emergency: sweep everything back to master |

---

## Remaining Gaps (non-blocking for KK V2)

| Gap | Impact | Priority |
|-----|--------|----------|
| Celo USDC ($0.69 master) | Agents only have USDT on Celo, not USDC | Low — USDT is sufficient |
| Optimism USDT ($0 master) | Agents only have USDC on Optimism | Low — USDC is sufficient |
| Monad USDT (not in chains.ts) | Can't distribute USDT on Monad | Low — USDC+AUSD available |
| Arbitrum AUSD ($0 master) | Agents only have USDC+USDT on Arbitrum | Low — 2 tokens sufficient |
| Avalanche/Celo/Monad no Disperse | Sequential transfers only (slower) | Low — works fine, just more TXs |

---

## Next Steps — What Follows Fund Distribution

Fund distribution (KK V2 Master Plan Phase 1) is **COMPLETE**. Three parallel workstreams are ready:

### Workstream A: KK V2 Integration — Phase 1 (Agent Auth + Skills)
**Plan**: `docs/planning/MASTER_PLAN_KK_V2_INTEGRATION.md`
**9 tasks** — Enables autonomous agent operations:

1. **Task 1.1-1.3**: Create 3 EM skills (submit-evidence, rate-counterparty, register-identity)
2. **Task 1.4-1.5**: EIP-8128 signing libraries (TypeScript + Python) — agents can cryptographically sign API requests
3. **Task 1.6**: Update `em_client.py` to use EIP-8128 auth
4. **Task 1.7**: Migrate API routes to `verify_agent_auth()`
5. **Task 1.8**: Add nonce endpoint `GET /api/v1/auth/erc8128/nonce`
6. **Task 1.9**: Deploy DynamoDB nonce table via Terraform

**Why first**: Without auth + skills, agents can't autonomously complete the full lifecycle. This is the foundation for everything else.

### Workstream B: Unified Ecosystem — Phase 1 (Turnstile Premium Channels)
**Plan**: `docs/planning/MASTER_PLAN_UNIFIED_ECOSYSTEM.md`
**5 tasks** — IRC monetization via x402:

1. Document Turnstile API
2. E2E test for premium channel payment
3. Create 3 premium channels (#kk-alpha, #kk-consultas, #kk-skills)
4. Turnstile client SDK for agents
5. Integrate into agent IRC flow

**Why parallel**: Depends on MeshRelay coordination, not code dependencies with Workstream A.

### Workstream C: KK V2 Integration — Phase 2 (Security)
**Plan**: `docs/planning/MASTER_PLAN_KK_V2_INTEGRATION.md`
**Blocked by Phase 1** — Tasks 2.1-2.5:

1. Self-application prevention (agent can't apply to own task)
2. Race condition protection (concurrent task applications)
3. `payment_token` field on tasks (multi-stablecoin support)
4. Task expiry automation
5. Duplicate submission prevention

### Recommended Order
```
Phase 1A (Agent Auth)  ───┐
                          ├──> Phase 2 (Security) ──> Phase 3 (Bulk Registration)
Phase 1B (Turnstile)  ───┘
```

Start Phase 1A and 1B in parallel. Phase 2 requires Phase 1A to be complete.
