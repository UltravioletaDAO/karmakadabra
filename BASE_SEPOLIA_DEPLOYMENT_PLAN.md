# Base Sepolia Deployment Plan
## GLUE Token + ERC-8004 Registries

**Created:** 2025-11-03
**Status:** Planning Phase
**Branch:** `base-sepolia-deployment`
**Worktree:** `Z:\ultravioleta\dao\karmacadabra-base-sepolia`

---

## 📋 Overview

Deploy complete Karmacadabra infrastructure to Base Sepolia testnet:
1. **GLUE Token** (ERC-20 with EIP-3009 gasless transfers)
2. **ERC-8004 Registries** (Identity, Reputation, Validation)

**Strategy:** Reuse existing agent wallets, fund only what's needed for registration.

---

## 💰 Wallet Infrastructure Analysis

### ✅ Deployer Wallet (ERC-20 Owner)

| Property | Value |
|----------|-------|
| Address | `0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8` |
| Source | AWS Secrets Manager: `karmacadabra` → `erc-20` |
| Base Sepolia Balance | **0.049 ETH** ✅ |
| Status | **READY - Sufficient for deployment** |

**Deployment Costs Estimate:**
- GLUE Token: ~0.003 ETH
- Identity Registry: ~0.005 ETH
- Reputation Registry: ~0.003 ETH
- Validation Registry: ~0.003 ETH
- **Total:** ~0.014 ETH
- **Buffer:** 0.049 - 0.014 = **0.035 ETH remaining** ✅

### 🔴 System Agent Wallets (Need Funding)

| Agent | Address | Base Sepolia Balance | Action Required |
|-------|---------|---------------------|-----------------|
| **Validator** | `0x1219eF9484BF7E40E6479141B32634623d37d507` | 0 ETH | Fund 0.02 ETH |
| **Karma-Hello** | `0x2C3e071df446B25B821F59425152838ae4931E75` | 0 ETH | Fund 0.02 ETH |
| **Abracadabra** | `0x940DDDf6fB28E611b132FbBedbc4854CC7C22648` | 0 ETH | Fund 0.02 ETH |
| **Skill Extractor** | `0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9` | 0 ETH | Fund 0.02 ETH |
| **Voice Extractor** | `0x8e0Db88181668cdE24660D7Ee8dA18A77DDbbF96` | 0 ETH | Fund 0.02 ETH |

**Total Funding Needed:** 5 agents × 0.02 ETH = **0.10 ETH**

**Funding Breakdown per Agent:**
- On-chain registration: ~0.005 ETH (registration fee)
- Initial operations: ~0.010 ETH (transactions, verifications)
- Buffer: ~0.005 ETH
- **Total:** 0.02 ETH per agent

---

## 📦 Deployment Steps

### Phase 1: Prepare Deployment Scripts ✅

**Tasks:**
- [x] Analyze existing `erc-20/deploy-fuji.sh` and `Deploy.s.sol`
- [x] Analyze existing `erc-8004/deploy-fuji.sh` and `Deploy.s.sol`
- [ ] Create `erc-20/deploy-base-sepolia.sh`
- [ ] Create `erc-20/script/DeployBaseSepolia.s.sol`
- [ ] Create `erc-8004/deploy-base-sepolia.sh`
- [ ] Update `erc-8004/contracts/script/Deploy.s.sol` (already chain-agnostic)

**Script Changes:**

**erc-20/deploy-base-sepolia.sh:**
```bash
NETWORK="base-sepolia"
CHAIN_ID=84532
OWNER_WALLET="0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8"
INITIAL_SUPPLY=24157817  # Same as Fuji
RPC_URL="https://sepolia.base.org"
```

**erc-8004/deploy-base-sepolia.sh:**
```bash
BASE_SEPOLIA_RPC_URL="https://sepolia.base.org"
BASE_SEPOLIA_CHAIN_ID=84532
```

### Phase 2: Deploy GLUE Token

**Command:**
```bash
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\erc-20
./deploy-base-sepolia.sh
```

**Expected Output:**
- GLUE Token address (save to `.env.base-sepolia`)
- Initial supply minted to owner: 24,157,817 GLUE
- Verification on Base Sepolia Etherscan

**Verification:**
```bash
cast call <GLUE_ADDRESS> "totalSupply()" --rpc-url https://sepolia.base.org
cast call <GLUE_ADDRESS> "balanceOf(address)" 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8 --rpc-url https://sepolia.base.org
```

### Phase 3: Deploy ERC-8004 Registries

**Command:**
```bash
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\erc-8004
./deploy-base-sepolia.sh
```

**Deployment Order:**
1. Identity Registry (no dependencies)
2. Reputation Registry (depends on Identity)
3. Validation Registry (depends on Identity)

**Expected Output:**
- 3 contract addresses (save to `.env.base-sepolia`)
- Registration fee: 0.005 AVAX equivalent (~0.001 ETH on Base Sepolia)

**Verification:**
```bash
cast call <IDENTITY_ADDRESS> "REGISTRATION_FEE()" --rpc-url https://sepolia.base.org
```

### Phase 4: Fund Agent Wallets

**⚠️ CRITICAL: User must fund wallets before agent operations**

**Option 1: Manual Funding (Recommended)**
```bash
# User sends from their wallet via MetaMask/CLI:
# 0.02 ETH → 0x1219eF9484BF7E40E6479141B32634623d37d507 (Validator)
# 0.02 ETH → 0x2C3e071df446B25B821F59425152838ae4931E75 (Karma-Hello)
# 0.02 ETH → 0x940DDDf6fB28E611b132FbBedbc4854CC7C22648 (Abracadabra)
# 0.02 ETH → 0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9 (Skill Extractor)
# 0.02 ETH → 0x8e0Db88181668cdE24660D7Ee8dA18A77DDbbF96 (Voice Extractor)
```

**Option 2: Automated Script**
```bash
python scripts/fund_agents_base_sepolia.py --amount 0.02
```

**Verification:**
```bash
cast balance 0x1219eF9484BF7E40E6479141B32634623d37d507 --rpc-url https://sepolia.base.org
# Repeat for each agent
```

### Phase 5: Distribute GLUE Tokens

**Command:**
```bash
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\scripts
python distribute_glue_base_sepolia.py
```

**Distribution:**
- 55,000 GLUE per system agent (5 agents = 275,000 GLUE)
- Owner retains: 24,157,817 - 275,000 = 23,882,817 GLUE

**Verification:**
```bash
cast call <GLUE_ADDRESS> "balanceOf(address)" 0x1219eF9484BF7E40E6479141B32634623d37d507 --rpc-url https://sepolia.base.org
# Should return: 55000000000 (55k GLUE with 6 decimals)
```

### Phase 6: Register Agents On-Chain

**Command:**
```bash
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\scripts
python register_agents_base_sepolia.py
```

**Registers:**
1. Validator → ERC-8004 ID 1
2. Karma-Hello → ERC-8004 ID 2
3. Abracadabra → ERC-8004 ID 3
4. Skill Extractor → ERC-8004 ID 4
5. Voice Extractor → ERC-8004 ID 5

**Verification:**
```bash
cast call <IDENTITY_ADDRESS> "resolveByAddress(address)" 0x1219eF9484BF7E40E6479141B32634623d37d507 --rpc-url https://sepolia.base.org
# Should return agent info tuple
```

### Phase 7: Update Configuration Files

**Files to Update:**

1. **`erc-20/.env.base-sepolia`** (create new)
```env
NETWORK=base-sepolia
CHAIN_ID=84532
GLUE_TOKEN_ADDRESS=<deployed_address>
OWNER_ADDRESS=0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
RPC_URL=https://sepolia.base.org
```

2. **`erc-8004/.env.base-sepolia`** (create new)
```env
NETWORK=base-sepolia
CHAIN_ID=84532
IDENTITY_REGISTRY=<deployed_address>
REPUTATION_REGISTRY=<deployed_address>
VALIDATION_REGISTRY=<deployed_address>
RPC_URL=https://sepolia.base.org
```

3. **`x402-rs/.env`** (add Base Sepolia config)
```env
BASE_SEPOLIA_GLUE_TOKEN=<deployed_address>
BASE_SEPOLIA_IDENTITY_REGISTRY=<deployed_address>
BASE_SEPOLIA_RPC_URL=https://sepolia.base.org
```

4. **`shared/contracts_config.py`** (add Base Sepolia)
```python
BASE_SEPOLIA = {
    "chain_id": 84532,
    "glue_token": "<deployed_address>",
    "identity_registry": "<deployed_address>",
    "reputation_registry": "<deployed_address>",
    "validation_registry": "<deployed_address>",
    "rpc_url": "https://sepolia.base.org"
}
```

### Phase 8: Verify Entire Deployment

**Verification Checklist:**
- [ ] GLUE token deployed and verified on Base Sepolia Etherscan
- [ ] Total supply: 24,157,817 GLUE
- [ ] Owner balance: 23,882,817 GLUE
- [ ] ERC-8004 registries deployed and verified
- [ ] 5 system agents funded with 0.02 ETH each
- [ ] 5 system agents distributed 55,000 GLUE each
- [ ] 5 system agents registered on-chain (IDs 1-5)
- [ ] All contracts verified on https://sepolia.basescan.org
- [ ] Configuration files updated

**Test End-to-End Flow:**
```bash
# From validator agent
cd validator
python test_base_sepolia_registration.py

# Should verify:
# - Agent can query registry
# - Agent balance is correct
# - Agent can execute test transaction
```

---

## 🚨 Risk Assessment

### Low Risk ✅
- **Deployer wallet funded:** 0.049 ETH sufficient
- **Scripts proven:** Reusing tested Fuji deployment logic
- **Contracts verified:** Same Solidity code as Fuji

### Medium Risk ⚠️
- **Agent wallet funding:** Manual process, error-prone
  - **Mitigation:** Provide clear checklist and verification commands
- **Contract verification:** Etherscan API may timeout
  - **Mitigation:** Manual verification fallback documented

### Critical Dependencies 🔴
- **User must fund 5 agent wallets:** 0.10 ETH total
  - If skipped: Agents cannot register or operate
  - **Action:** User must confirm funding before Phase 4

---

## 📊 Cost Summary

| Item | Cost (ETH) | Status |
|------|-----------|--------|
| **Contract Deployments** | 0.014 | ✅ Covered by deployer |
| **Agent Wallet Funding** | 0.100 | 🔴 **User must provide** |
| **Buffer** | 0.035 | ✅ Deployer has buffer |
| **Total Required** | **0.114 ETH** | ⚠️ User needs 0.10 ETH |

**Sources:**
- Deployer wallet: 0.049 ETH (sufficient for deployments)
- **User must obtain:** 0.10 ETH for agent funding

**How to get Base Sepolia ETH:**
- Faucet: https://www.alchemy.com/faucets/base-sepolia
- Bridge from Sepolia: https://bridge.base.org/

---

## 📝 Next Steps

1. **User confirms:** Ready to provide 0.10 ETH for agent funding
2. **Create deployment scripts:** `deploy-base-sepolia.sh` for both projects
3. **Execute Phase 2:** Deploy GLUE token
4. **Execute Phase 3:** Deploy ERC-8004 registries
5. **User funds agents:** 0.02 ETH × 5 wallets
6. **Execute Phase 5:** Distribute GLUE
7. **Execute Phase 6:** Register agents
8. **Execute Phase 8:** Verify deployment

---

## 🔗 Resources

- **Base Sepolia RPC:** https://sepolia.base.org
- **Base Sepolia Explorer:** https://sepolia.basescan.org
- **Base Sepolia Chain ID:** 84532
- **Base Sepolia Faucet:** https://www.alchemy.com/faucets/base-sepolia
- **Worktree Location:** `Z:\ultravioleta\dao\karmacadabra-base-sepolia`
- **Git Branch:** `base-sepolia-deployment`

---

**Status:** ✅ Planning complete, ready to create deployment scripts
**Blockers:** None (deployer funded, scripts analyzed)
**User Action Required:** Confirm 0.10 ETH funding commitment for agents
