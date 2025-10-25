# Alternative Fiat On-Ramps Research

**Date:** October 24, 2025
**Context:** Sprint 2.9 - Coinbase Payments MCP DEFERRED due to Windows installation blocker
**Objective:** Identify viable alternative fiat on-ramp solutions for Karmacadabra agents

---

## Executive Summary

**Research Question:** Can alternative fiat on-ramps enable credit card → GLUE token payments on Avalanche Fuji testnet?

**Answer:** ❌ **NO** - None of the major fiat on-ramp providers support Avalanche Fuji testnet in their sandbox environments.

**Critical Finding:** All major providers (Stripe, Moonpay, Transak, Ramp Network, OnRamper) support Avalanche **mainnet only**. Testing with custom tokens (GLUE) on testnet (Fuji) is **not possible** without deploying to mainnet.

**Impact:** Fiat on-ramp integration for Karmacadabra would require:
1. Migrating to Avalanche mainnet (significant risk + cost)
2. Deploying GLUE token to mainnet (security audit required)
3. Funding all agents with real AVAX for gas
4. Using real money for testing (expensive + risky)

**Recommendation:** ❌ **DO NOT PURSUE** fiat on-ramp integration at this time

---

## 1. Stripe Crypto On-Ramp

**Website:** https://stripe.com/crypto
**Docs:** https://docs.stripe.com/crypto/onramp
**Status:** ⚠️ **PARTIAL SUPPORT** - Mainnet only

### ✅ Pros

- **Avalanche mainnet support**: AVAX and USDC on Avalanche C-Chain
- **Major integration**: Partnered directly with Avalanche Foundation
- **Testing environment exists**: Sandbox mode available after application approval
- **Geographic coverage**: Global (except NY for some assets, EU restrictions)
- **Payment methods**: ACH, debit, credit cards
- **Established provider**: Trusted brand, used by Core wallet

### ❌ Cons

- **NO testnet support documented**: No explicit mention of Avalanche Fuji testnet
- **NO custom token support**: Limited to AVAX and USDC on Avalanche
- **Requires application**: Must submit application and wait for approval
- **No pricing transparency**: Fees not publicly documented
- **Sandbox limitations**: Testing environment details unclear

### 🔍 Technical Details

**Supported on Avalanche:**
- AVAX (native token)
- USDC (ERC-20)

**Test Mode:**
- Sandbox available after application approval
- Test values: `000000` for OTP, `000000000` for SSN, `4242424242424242` for card
- `livemode: false` parameter for test transactions

**Integration Method:**
- REST API: `POST /v1/crypto/onramp_sessions`
- Embeddable widget or hosted redirect
- Webhook notifications for transaction events

### 📊 Karmacadabra Compatibility Assessment

| Requirement | Supported? | Notes |
|------------|------------|-------|
| Avalanche Fuji testnet | ❌ **NO** | Only mainnet documented |
| GLUE token (custom ERC-20) | ❌ **NO** | Only AVAX + USDC |
| 0.01 GLUE micropayments | ❌ **NO** | Cannot support GLUE |
| 48 agent programmatic access | ✅ YES | API available |
| Testing without real money | ⚠️ **UNCLEAR** | Sandbox exists but testnet unsupported |

**Estimated Integration Effort:** 2-3 weeks (mainnet only)
**Estimated Cost:** Unknown (pricing not public) + AVAX gas fees

**Verdict:** ❌ **NOT VIABLE** - No testnet or custom token support

---

## 2. Moonpay

**Website:** https://www.moonpay.com
**Docs:** https://dev.moonpay.com
**Avalanche Hub:** https://build.avax.network/integrations/moonpay
**Status:** ⚠️ **PARTIAL SUPPORT** - Mainnet only

### ✅ Pros

- **Avalanche mainnet support**: AVAX purchases available
- **100+ cryptocurrencies**: Wide token coverage
- **Sandbox environment**: Dedicated testnet sandbox with test cards
- **Skip KYC in sandbox**: Easier testing flow
- **Web SDK available**: Easy integration with `currencyCode: 'avax'`
- **Developer dashboard**: Self-service API key generation

### ❌ Cons

- **NO Avalanche testnet in sandbox**: Fuji not in supported testnet list
- **NO custom token support**: Cannot add GLUE token
- **Limited sandbox tokens**: Only 8 testnets supported
- **Rate limiting**: Frequent actions trigger rate limits
- **Geographic restrictions**: Some regions unsupported

### 🔍 Technical Details

**Supported Testnets in Sandbox:**

| Token | Testnet |
|-------|---------|
| Bitcoin | Testnet3 |
| Ethereum | Sepolia |
| ERC-20 tokens | Sepolia |
| Solana | Testnet |
| Binance Coin | Testnet |
| TON | Testnet |
| Stellar | Testnet |
| Litecoin | Testnet |

**❌ NOT Supported:** Avalanche Fuji testnet

**Integration Method:**
- Web SDK: `@moonpay/moonpay-react`
- Direct API: `https://api.moonpay.com/`
- Widget embed or redirect flow

**Testing Capabilities:**
- Test credit cards provided
- Skip KYC document submission
- Return testnet coins via designated wallets
- Empty testnet wallets cause transaction failures

### 📊 Karmacadabra Compatibility Assessment

| Requirement | Supported? | Notes |
|------------|------------|-------|
| Avalanche Fuji testnet | ❌ **NO** | Not in sandbox testnet list |
| GLUE token (custom ERC-20) | ❌ **NO** | No custom token addition |
| 0.01 GLUE micropayments | ❌ **NO** | Cannot support GLUE |
| 48 agent programmatic access | ✅ YES | API available |
| Testing without real money | ⚠️ **PARTIAL** | Sandbox works for 8 other testnets |

**Estimated Integration Effort:** 2-3 weeks (mainnet only)
**Estimated Cost:** Fees vary by payment method + AVAX gas fees

**Verdict:** ❌ **NOT VIABLE** - No Avalanche testnet support

---

## 3. Transak

**Website:** https://transak.com
**Docs:** https://docs.transak.com
**Avalanche Hub:** https://build.avax.network/integrations/transak
**Status:** ⚠️ **PARTIAL SUPPORT** - Mainnet only

### ✅ Pros

- **Avalanche mainnet support**: 130+ cryptocurrencies including Avalanche
- **Custom L1 support**: Native tokens for custom Layer 1 networks
- **Request custom tokens**: Can submit due diligence form for new assets
- **Global coverage**: 100+ countries
- **Staging environment**: Test mode with TRNSK test token
- **Comprehensive SDK**: On-ramp and off-ramp widgets

### ❌ Cons

- **NO Avalanche Fuji testnet**: Not in supported testnet list
- **Custom token approval required**: Compliance review process
- **Limited test token**: Only TRNSK on specific networks
- **Dummy orders only**: Unsupported chains show UX but don't deliver tokens
- **No native token delivery in test**: ETH, MATIC, BNB not delivered in staging

### 🔍 Technical Details

**Supported Testnets in Staging:**

| Network | Testnet |
|---------|---------|
| Ethereum | Sepolia |
| Polygon | Amoy |
| Arbitrum | Sepolia |
| Optimism | Sepolia |
| Binance Smart Chain | BSC Testnet |
| Base | Sepolia |
| Linea | Sepolia |

**❌ NOT Supported:** Avalanche Fuji testnet

**Test Token System:**
- **TRNSK**: Transak Test Token deployed on supported networks
- ERC-20 purchases deliver TRNSK instead of actual tokens
- Off-ramp requires official testnet tokens for reconciliation
- Dummy orders possible for unsupported chains (UX only, no delivery)

**Integration Method:**
- JavaScript SDK: `@transak/transak-sdk`
- Query parameter configuration
- Webhook events for transaction status
- API endpoints for programmatic access

**Custom Token Listing Process:**
1. Fill out due diligence form
2. Compliance team review
3. Listing approval (straightforward if compliant)
4. Integration setup

### 📊 Karmacadabra Compatibility Assessment

| Requirement | Supported? | Notes |
|------------|------------|-------|
| Avalanche Fuji testnet | ❌ **NO** | Not in staging testnet list |
| GLUE token (custom ERC-20) | ⚠️ **MAYBE** | Requires compliance approval |
| 0.01 GLUE micropayments | ⚠️ **MAYBE** | If GLUE approved on mainnet |
| 48 agent programmatic access | ✅ YES | API available |
| Testing without real money | ❌ **NO** | No Fuji testnet support |

**Estimated Integration Effort:**
- Staging integration: 1 week
- GLUE token listing: 2-4 weeks (compliance review)
- Mainnet deployment: 1-2 weeks
- **Total: 4-7 weeks**

**Estimated Cost:** Transaction fees + AVAX gas fees

**Verdict:** ⚠️ **POSSIBLE BUT RISKY** - Requires mainnet deployment + GLUE compliance approval

---

## 4. Ramp Network

**Website:** https://ramp.network
**Docs:** https://docs.ramp.network
**Avalanche Hub:** https://build.avax.network/integrations/ramp-network
**Status:** ⚠️ **LIMITED INFORMATION**

### ✅ Pros

- **Avalanche mainnet support**: AVAX purchases via SDK
- **SDK available**: `@ramp-network/ramp-instant-sdk`
- **REST API**: Full API access at `https://api.rampnetwork.com/api/host-api/v3/`
- **Partner form**: Easy API key request process

### ❌ Cons

- **NO testnet information found**: Documentation search yielded no testnet details
- **Limited research data**: Fewer search results than other providers
- **Requires partner approval**: Must contact `partner@ramp.network`

### 🔍 Technical Details

**Integration Method:**
- SDK: `@ramp-network/ramp-instant-sdk`
- REST API V3
- API key required (request via form)

**Documentation Gaps:**
- No testnet documentation found
- No custom token information
- No sandbox environment mentioned

### 📊 Karmacadabra Compatibility Assessment

| Requirement | Supported? | Notes |
|------------|------------|-------|
| Avalanche Fuji testnet | ⚠️ **UNKNOWN** | No documentation found |
| GLUE token (custom ERC-20) | ⚠️ **UNKNOWN** | Not documented |
| 0.01 GLUE micropayments | ⚠️ **UNKNOWN** | Cannot assess |
| 48 agent programmatic access | ✅ YES | API available |
| Testing without real money | ⚠️ **UNKNOWN** | No testnet info |

**Estimated Integration Effort:** Unknown (requires discovery)
**Estimated Cost:** Unknown

**Verdict:** ⚠️ **INSUFFICIENT DATA** - Would require direct contact with Ramp Network

---

## 5. OnRamper

**Website:** https://www.onramper.com
**Docs:** https://docs.onramper.com
**Status:** 🔄 **AGGREGATOR**

### ✅ Pros

- **30+ onramps in one integration**: Access multiple providers through single API
- **Sandbox environment**: `https://buy.onramper.dev` with `pk_test` keys
- **Production environment**: `https://buy.onramper.com` with `pk_prod` keys
- **Flexibility**: Can leverage whichever underlying onramp supports your needs

### ❌ Cons

- **Non-standardized sandboxes**: Underlying onramp sandboxes vary
- **Recommends production testing**: "We generally recommend testing in production environments"
- **Some onramps lack sandboxes**: Production environments accessible via sandbox domain
- **Empty testnet wallets**: "Testnet wallets used by onramps can be empty"
- **No guaranteed Avalanche testnet**: Depends on underlying providers

### 🔍 Technical Details

**Two Environments:**
- **Sandbox**: `pk_test` API key prefix, `https://buy.onramper.dev`
- **Production**: `pk_prod` API key prefix, `https://buy.onramper.com`

**Important Note:** OnRamper aggregates other providers (Moonpay, Transak, Ramp, etc.), so Avalanche testnet support depends on whether ANY of the underlying providers support it.

**Testing Philosophy:**
- Recommends production testing due to sandbox inconsistencies
- Some providers don't have dedicated sandboxes
- Testnet wallets may be empty

### 📊 Karmacadabra Compatibility Assessment

| Requirement | Supported? | Notes |
|------------|------------|-------|
| Avalanche Fuji testnet | ❌ **NO** | Underlying providers don't support Fuji |
| GLUE token (custom ERC-20) | ❌ **NO** | Depends on providers (none support it) |
| 0.01 GLUE micropayments | ❌ **NO** | Cannot support GLUE |
| 48 agent programmatic access | ✅ YES | API available |
| Testing without real money | ❌ **NO** | Recommends production testing |

**Estimated Integration Effort:** 1-2 weeks (but no testnet support)
**Estimated Cost:** Varies by underlying provider

**Verdict:** ❌ **NOT VIABLE** - Aggregates providers that don't support Avalanche testnet

---

## 6. Other Providers Considered

### Striga
- **Website:** https://www.striga.com
- **Notes:** General stablecoin on/off ramp API
- **Avalanche Testnet:** No information found

### ChangeNOW
- **Website:** https://changenow.io
- **Notes:** Fiat on-ramp API supporting 50+ currencies
- **Avalanche Testnet:** No information found

### Kriptomat
- **Website:** https://kriptomat.io
- **Notes:** General fiat-to-crypto on-ramp
- **Avalanche Testnet:** No information found

**Note:** These providers require deeper investigation but are unlikely to support Avalanche Fuji testnet based on industry patterns.

---

## Critical Findings Summary

### ❌ Universal Blocker: No Avalanche Fuji Testnet Support

**Every major fiat on-ramp provider supports Avalanche MAINNET only.**

**Supported Testnets Across Providers:**
- ✅ Ethereum Sepolia (Stripe, Moonpay, Transak)
- ✅ Polygon Amoy (Transak)
- ✅ Binance Smart Chain Testnet (Moonpay, Transak)
- ✅ Arbitrum Sepolia (Transak)
- ✅ Optimism Sepolia (Transak)
- ✅ Base Sepolia (Transak)
- ✅ Solana Testnet (Moonpay)
- ✅ Bitcoin Testnet (Moonpay)
- ❌ **Avalanche Fuji** - **NOT SUPPORTED BY ANY PROVIDER**

### Why This Matters for Karmacadabra

**Current Architecture:**
- **Blockchain:** Avalanche Fuji testnet (Chain ID 43113)
- **Token:** GLUE (custom ERC-20 at `0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743`)
- **Network:** Testnet-only (all agents, contracts, facilitator on Fuji)

**To Use Fiat On-Ramps, We Would Need To:**

1. **Migrate to Avalanche Mainnet**
   - Redeploy GLUE token contract
   - Redeploy ERC-8004 registries (Identity, Reputation, Validation)
   - Re-register all 7+ agents on mainnet
   - Update all agent `.env` files with mainnet addresses
   - Configure x402-rs facilitator for mainnet
   - **Risk:** Real money, real gas fees, security audit required

2. **Get GLUE Token Listed**
   - Submit compliance review (Transak requires this)
   - Wait for approval (2-4 weeks)
   - Integrate with approved provider
   - **Risk:** May be rejected, no guarantee of approval

3. **Fund All Agents with Real AVAX**
   - 48 user agents need AVAX for gas
   - Validator needs AVAX
   - Karma-Hello, Abracadabra, client-agent need AVAX
   - **Cost:** Unknown but significant (AVAX mainnet gas fees)

4. **Security Audit Required**
   - GLUE token (EIP-3009 implementation)
   - ERC-8004 registries (3 contracts)
   - x402-rs facilitator (Rust codebase)
   - **Cost:** $10,000 - $50,000 (typical smart contract audit)
   - **Timeline:** 4-8 weeks

5. **Testing Becomes Expensive**
   - Every transaction costs real AVAX
   - Every GLUE transfer is real value
   - Mistakes = lost money
   - **Risk:** Development testing on mainnet is dangerous

---

## Alternative Architectures Considered

### Option A: Hybrid Mainnet/Testnet

**Idea:** Deploy GLUE on mainnet for fiat on-ramp, keep agents on testnet

**Problems:**
- ❌ Agents on testnet can't interact with mainnet GLUE contract
- ❌ x402-rs facilitator can't span two networks
- ❌ ERC-8004 registries must be on same network as token
- ❌ Completely incompatible architecture

**Verdict:** ❌ **NOT FEASIBLE**

---

### Option B: Mainnet-Only Deployment

**Idea:** Migrate entire Karmacadabra system to Avalanche mainnet

**Requirements:**
- ✅ Deploy all contracts to mainnet (GLUE + 3 ERC-8004 registries)
- ✅ Get GLUE listed with fiat on-ramp (Transak most likely)
- ✅ Security audit ($10K-$50K)
- ✅ Fund all agents with real AVAX
- ✅ Update facilitator for mainnet
- ✅ Re-register all agents on mainnet

**Benefits:**
- ✅ Fiat on-ramp available (credit card → GLUE)
- ✅ Real on-chain reputation
- ✅ Production-ready system

**Costs:**
- 💰 Security audit: $10,000 - $50,000
- 💰 AVAX gas fees: $500+ for deployment + ongoing
- 💰 Development risk: Real money testing
- ⏱️ Timeline: 8-12 weeks (audit + integration + testing)
- ⏱️ Compliance: 2-4 weeks (GLUE token listing approval)

**Risks:**
- 🔴 **HIGH RISK**: Real money development
- 🔴 **AUDIT REQUIRED**: GLUE + ERC-8004 + x402-rs
- 🔴 **COMPLIANCE UNKNOWN**: GLUE may be rejected by providers
- 🟡 **EXPENSIVE**: $10K-$50K upfront before any revenue

**Verdict:** ⚠️ **POSSIBLE BUT PREMATURE** - Should validate market first with testnet

---

### Option C: Testnet-Only + Manual Fiat On-Ramp

**Idea:** Keep testnet architecture, manually distribute GLUE to users who pay via traditional methods

**Flow:**
1. User pays $10 USD via PayPal/Venmo/bank transfer
2. Admin manually sends 1000 GLUE to user's wallet
3. User uses GLUE in Karmacadabra ecosystem
4. Fully manual, no integration needed

**Benefits:**
- ✅ Zero development cost
- ✅ Keep testnet architecture (safe)
- ✅ Accepts fiat payments (sort of)
- ✅ Works immediately

**Drawbacks:**
- ❌ **NOT SCALABLE**: Manual process for each user
- ❌ **TERRIBLE UX**: Email admin, wait for manual approval, hope they respond
- ❌ **NO AUTONOMY**: Defeats purpose of autonomous agent economy
- ❌ **TRUST REQUIRED**: Users must trust admin to send GLUE
- ❌ **CENTRALIZED**: Single point of failure (admin)

**Verdict:** ❌ **NOT ALIGNED** - Violates trustless architecture principles

---

### Option D: Keep Crypto-Only Payments (Status Quo)

**Idea:** Maintain current x402scan embedded wallet architecture

**Current Flow:**
1. User visits x402scan.ultravioletadao.xyz
2. Connects RainbowKit wallet (MetaMask, Coinbase Wallet, etc.)
3. Adds Avalanche Fuji testnet (one-time setup)
4. Gets free AVAX from faucet (https://faucet.avax.network)
5. Buys GLUE from agent (0.01 AVAX → 100 GLUE)
6. Uses GLUE to purchase agent services
7. Fully autonomous, on-chain, trustless

**Benefits:**
- ✅ Already working (Level 3 E2E tests passing)
- ✅ Zero additional development cost
- ✅ Trustless architecture maintained
- ✅ Safe testnet environment
- ✅ Free testnet AVAX from faucet

**Drawbacks:**
- ❌ **CRYPTO-NATIVE ONLY**: Requires crypto wallet knowledge
- ❌ **15-20 MIN ONBOARDING**: First-time setup is long
- ❌ **LIMITED MARKET**: Only crypto users
- ❌ **TESTNET FEELS TOY**: Users know it's "play money"

**Market Impact:**
- Current addressable market: ~5% of population (crypto users)
- Projected transaction volume: 100-500 transactions/month
- User growth rate: Slow (crypto adoption barrier)

**Verdict:** ✅ **WORKING & SAFE** - Proven architecture, limited market

---

## Decision Matrix

| Option | Dev Cost | Timeline | Risk | Market Size | Autonomy | Recommendation |
|--------|----------|----------|------|-------------|----------|----------------|
| **A: Hybrid Mainnet/Testnet** | N/A | N/A | N/A | N/A | N/A | ❌ **NOT FEASIBLE** |
| **B: Mainnet-Only** | $10K-$50K | 8-12 weeks | 🔴 High | 🟢 100% | ✅ Full | ⚠️ **PREMATURE** |
| **C: Manual Fiat On-Ramp** | $0 | 1 day | 🟢 Low | 🟡 50% | ❌ None | ❌ **NOT ALIGNED** |
| **D: Crypto-Only (Status Quo)** | $0 | 0 weeks | 🟢 Low | 🟡 5% | ✅ Full | ✅ **RECOMMENDED** |

---

## Recommendation: Defer Fiat On-Ramp Integration

### ✅ Recommended Path: Sprint 3 with Crypto-Only Payments

**Reasoning:**

1. **No Viable Testnet Solution Exists**
   - Zero fiat on-ramps support Avalanche Fuji testnet
   - Cannot validate assumptions without mainnet deployment
   - Mainnet deployment = high risk + high cost

2. **Market Validation Required First**
   - Prove demand with crypto users first
   - 48 user agents in Sprint 3 will generate real usage data
   - If successful → justify mainnet migration cost
   - If unsuccessful → avoid wasted $10K-$50K audit cost

3. **Current Architecture Works**
   - Level 3 E2E tests passing (30/30 tests)
   - x402scan embedded wallet functional
   - Agent payments working end-to-end
   - Zero bugs blocking production use

4. **Phased Approach is Safer**
   - **Phase 1 (Now):** Crypto-only testnet (Sprint 3)
   - **Phase 2 (3-6 months):** Gather usage data, refine UX
   - **Phase 3 (6-12 months):** If demand proven → mainnet migration + audit + fiat on-ramp
   - **Phase 4 (12+ months):** Scale with fiat payments

### Timeline Comparison

**If we pursue fiat on-ramp now:**
- Week 5-6: Research alternatives (DONE)
- Week 7-10: Mainnet deployment + re-registration
- Week 11-18: Security audit
- Week 19-20: GLUE compliance review
- Week 21-23: Fiat on-ramp integration
- Week 24+: Sprint 3 (User Agent System)
- **Total delay:** 19 weeks before user agents deployed

**If we defer fiat on-ramp (recommended):**
- Week 5: Proceed to Sprint 3 immediately
- Week 6-7: Deploy 48 user agents
- Week 8-9: Gather usage data
- Week 10+: Make data-driven decision on fiat on-ramp ROI
- **Total delay:** 0 weeks

**Savings:** 19 weeks + $10K-$50K audit cost

---

## Future Revisit Criteria

**Revisit fiat on-ramp integration when ONE of these is true:**

1. **✅ Coinbase Payments MCP Windows installer is fixed**
   - Monitor: https://github.com/coinbase/payments-mcp/issues
   - Timeline: Unknown (could be weeks or never)
   - Value: Original POC can be completed

2. **✅ Avalanche Fuji testnet support added by major provider**
   - Monitor: Stripe, Moonpay, Transak documentation updates
   - Timeline: Unlikely (testnets are low priority for fiat on-ramps)
   - Value: Can test with GLUE before mainnet migration

3. **✅ Karmacadabra proves market demand on testnet**
   - Metric: 1,000+ transactions/month on testnet
   - Metric: 100+ active users (non-test wallets)
   - Metric: User feedback requesting fiat payments
   - Timeline: 3-6 months after Sprint 3 deployment
   - Value: Justifies $10K-$50K audit + mainnet migration cost

4. **✅ External funding secured**
   - Metric: $50K+ grant or investment
   - Use: Security audit + mainnet deployment
   - Timeline: Dependent on fundraising efforts
   - Value: De-risks mainnet migration financially

5. **✅ Halliday (Intent Orchestration Protocol) adds Fuji testnet**
   - Note: Halliday enables Stripe onramp to "any token on any subnet"
   - Monitor: https://www.halliday.xyz (Avalanche ecosystem partner)
   - Timeline: Unknown
   - Value: Potential workaround for custom token + testnet

---

## Lessons Learned

1. **Testnet-first development has limits**
   - Fiat on-ramps only support mainnet
   - Realistic for smart contract testing
   - Unrealistic for fiat payment integrations

2. **Custom tokens are not first-class citizens**
   - All providers prioritize major tokens (BTC, ETH, USDC)
   - Custom L1 tokens require compliance review
   - No guarantees of approval

3. **Avalanche ecosystem is mainnet-focused**
   - Fuji testnet excellent for development
   - Missing from fiat on-ramp provider support
   - Divergence from Ethereum (Sepolia well-supported)

4. **POC phase successfully prevented waste**
   - Without POC, might have committed to 2-3 week integration
   - Blocker discovered in Day 1 of POC
   - Research completed in 1 day vs. 2-3 weeks wasted effort

---

## Appendix: Provider Contact Information

### For Future Reference

**Stripe:**
- Docs: https://docs.stripe.com/crypto/onramp
- Application: https://stripe.com/crypto (submit application)

**Moonpay:**
- Docs: https://dev.moonpay.com
- Dashboard: https://www.moonpay.com/developers

**Transak:**
- Docs: https://docs.transak.com
- Support: https://support.transak.com/en/
- Custom token request: Via due diligence form

**Ramp Network:**
- Docs: https://docs.ramp.network
- Partner email: partner@ramp.network

**OnRamper:**
- Docs: https://docs.onramper.com
- Website: https://www.onramper.com

**Halliday (Intent Orchestration):**
- Website: https://www.halliday.xyz
- Note: Enables Stripe onramp to custom tokens

---

## Related Documents

- **POC Results:** `plans/COINBASE_MCP_POC_RESULTS.md`
- **Original Integration Plan:** `plans/COINBASE_PAYMENTS_MCP_INTEGRATION.md`
- **GitHub Issue Draft:** `plans/GITHUB_ISSUE_PAYMENTS_MCP.md`
- **Master Plan:** `MASTER_PLAN.md` (Sprint 2.9 marked DEFERRED)

---

**Research Status:** ✅ **COMPLETE**

**Next Action:** ✅ **Proceed to Sprint 3 (User Agent System)** with existing x402scan embedded wallet

**Fiat On-Ramp Status:** ❌ **DEFERRED** - Revisit in 3-6 months or when criteria met
