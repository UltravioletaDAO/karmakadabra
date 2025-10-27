# 🚀 Sprint 3.5 Execution Guide

**Goal:** Setup ALL user agents with wallets, AVAX, GLUE, and on-chain registration

**Status:** Scripts ready, awaiting execution
**Dynamic:** Automatically detects all agents in `client-agents/` folder (currently 48, expandable)

---

## ✅ Prerequisites

- [x] ERC-20 deployer wallet (0x34033041...) has AVAX and GLUE ✅
- [x] AWS Secrets Manager configured ✅
- [x] Scripts created (`setup_48_user_agents.py`, `verify_user_agents.py`) ✅

---

## 📊 Resource Requirements

**DYNAMIC:** Requirements calculated based on agent count in `client-agents/` folder

| Resource | Target Balance | Source |
|----------|--------|--------|
| **AVAX** | 0.05 AVAX per agent (tops up if < 0.05) | 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8 |
| **GLUE** | 10,946 GLUE per agent (tops up if < 10,946) | ERC-20 deployer wallet |
| **Time** | ~30-60 minutes | Transaction confirmations |

**Note:** Script uses intelligent top-up logic - only sends what's needed to reach target balances
**Example:** Agent with 1,000 GLUE receives 9,946 GLUE to reach 10,946 total

---

## 🎯 Execution Steps

### Step 1: Dry-Run (Check what will happen)

```bash
# From project root
python scripts/setup_user_agents.py
```

**Expected output:**
- Automatically detects all agents in `client-agents/` folder
- Shows N agents to be set up
- Checks deployer wallet balances
- Displays what WOULD happen (no actual transactions)

---

### Step 2: Execute Setup (Actually do it)

```bash
python scripts/setup_user_agents.py --execute
```

**What it does:**
1. ✅ Generates wallets for ALL agents (or uses existing - idempotent)
2. ✅ Stores ALL private keys in ONE AWS secret (`karmacadabra['user-agents']`)
3. ✅ Updates all `.env` files with AGENT_ADDRESS (NOT private keys)
4. ✅ Tops up AVAX to 0.05 per agent (only sends what's needed to reach target)
5. ✅ Tops up GLUE to 10,946 per agent (only sends what's needed to reach target)
6. ✅ Registers all agents on-chain

**IMPORTANT FEATURES:**
- **DYNAMIC:** Automatically detects ALL agents in `client-agents/` folder
- **IDEMPOTENT:** Safe to run multiple times - checks existing state before acting
- **SCALABLE:** Add new agents to `client-agents/` folder and re-run
- **SECURE:** Private keys NEVER written to `.env` files
- **CENTRALIZED:** All wallets in single AWS secret: `karmacadabra['user-agents']`
- Each agent reads the shared secret at runtime and extracts only its own key

**Estimated time:** 30-60 minutes (scales with agent count)

---

### Step 3: Verify Setup

```bash
python scripts/verify_user_agents.py
```

**Expected output:**
```
🔍 VERIFY USER AGENTS SETUP (48 agents)
================================

[1/48] 0xdream_sgo    | ✅ AVAX: 0.0500 | ✅ GLUE: 1000 | ✅ Registered (ID: 7)
[2/48] 0xh1p0tenusa   | ✅ AVAX: 0.0500 | ✅ GLUE: 1000 | ✅ Registered (ID: 8)
...
[48/48] fredinoo      | ✅ AVAX: 0.0500 | ✅ GLUE: 1000 | ✅ Registered (ID: 54)

📊 SUMMARY
================================
Total agents:     48
Wallets OK:       48/48 (100%)
AVAX OK:          48/48 (100%)
GLUE OK:          48/48 (100%)
Registered:       48/48 (100%)

✅ ALL CHECKS PASSED!
```

**Note:** Agent count adjusts automatically based on `client-agents/` folder contents

---

### Step 4: Test One Agent

```bash
# Test cyberpaisa agent as a client
python tests/test_cyberpaisa_client.py
```

**Expected output:**
```
✅ Agent initialized: cyberpaisa-agent
   Wallet: 0x...
   💎 Initial GLUE Balance: 1000.000000

✅ Discovered karma-hello agent!
✅ Purchase successful!
   📦 Data received: 15234 bytes
```

---

## 🔧 Optional: Step-by-Step Execution

If you want more control, run each step separately:

### A. Generate Wallets Only
```bash
python scripts/setup_user_agents.py --execute --skip-avax --skip-glue --skip-registration
```

### B. Distribute AVAX Only
```bash
python scripts/setup_user_agents.py --execute --skip-wallets --skip-glue --skip-registration
```

### C. Distribute GLUE Only
```bash
python scripts/setup_user_agents.py --execute --skip-wallets --skip-avax --skip-registration
```

### D. Register On-Chain Only
```bash
python scripts/setup_user_agents.py --execute --skip-wallets --skip-avax --skip-glue
```

---

## ❌ Troubleshooting

### Issue: "Insufficient AVAX in deployer wallet"

**Check balance:**
```bash
python -c "from web3 import Web3; w3=Web3(Web3.HTTPProvider('https://avalanche-fuji-c-chain-rpc.publicnode.com')); print(f'AVAX: {w3.from_wei(w3.eth.get_balance(\"0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8\"), \"ether\")}')"
```

**Solution:** Get more testnet AVAX from https://faucet.avax.network/

---

### Issue: "Insufficient GLUE in deployer wallet"

**Check balance:**
```bash
cd erc-20
python -c "from web3 import Web3; w3=Web3(Web3.HTTPProvider('https://avalanche-fuji-c-chain-rpc.publicnode.com')); contract=w3.eth.contract(address='0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743', abi=[{'inputs':[{'name':'account','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'stateMutability':'view','type':'function'}]); print(f'GLUE: {contract.functions.balanceOf(\"0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8\").call()/1e6:,.0f}')"
```

**Solution:** GLUE supply should be sufficient (23M+ available)

---

### Issue: "Failed to store in AWS"

**Check AWS credentials:**
```bash
aws sts get-caller-identity
```

**Solution:** Configure AWS CLI with proper credentials

---

### Issue: "Script regenerates wallets every time"

**Expected behavior:** Script is idempotent - it checks AWS for existing wallets and reuses them

**If regenerating anyway:**
- Check AWS secret exists: `aws secretsmanager get-secret-value --secret-id karmacadabra --query SecretString`
- Look for `"user-agents"` key in the JSON
- If missing, wallets will be regenerated (this is normal for first run)

---

### Issue: "How do agents read their private keys?"

**Answer:** Agents use `shared/secrets_manager.py`

**Code example:**
```python
from shared.secrets_manager import get_private_key

# Agent reads shared AWS secret and extracts only its own key
private_key = get_private_key("cyberpaisa")  # Fetches from AWS['user-agents']['cyberpaisa']
```

**Priority order:**
1. If `PRIVATE_KEY` is set in `.env` → use that (for local testing)
2. Otherwise → fetch from AWS Secrets Manager `karmacadabra['user-agents'][agent_name]`

---

### Issue: "Registration failed - already registered"

**Normal behavior:** Script checks if already registered and skips

**Manual check:**
```bash
python scripts/verify_user_agents.py
```

---

## ✅ Success Criteria

Sprint 3.5 is complete when:

- [x] `verify_user_agents.py` shows 100% on all checks
- [x] Can run `python tests/test_cyberpaisa_client.py` successfully
- [x] Can start any user agent: `cd client-agents/cyberpaisa && python main.py`

---

## 🎯 After Completion

Once Sprint 3.5 is done:

1. **Update MASTER_PLAN.md:**
   - Mark Sprint 3.5 as COMPLETE
   - Mark Sprint 3 as COMPLETE
   - Unblock Sprint 4

2. **Test Marketplace:**
   - Run full marketplace tests
   - Test inter-agent transactions
   - Bootstrap 48-agent economy

3. **Documentation:**
   - Update deployment docs
   - Create marketplace guide
   - Document network topology

4. **Future Migration (Phase 7+):**
   - Migrate from AWS Secrets Manager to HashiCorp Vault
   - Better secrets rotation, dynamic credentials, audit logging
   - See MASTER_PLAN.md Phase 7 for details

---

## 📞 Need Help?

**Common commands:**
```bash
# Check deployer balance
python scripts/check_system_ready.py --address 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8

# Verify all agents
python scripts/verify_user_agents.py

# Re-run setup (idempotent - safe to run multiple times, handles new agents automatically)
python scripts/setup_user_agents.py --execute

# Test single agent
python tests/test_cyberpaisa_client.py
```

---

**Architecture:** Single AWS secret for ALL wallets (not separate secrets)
**Security:** Private keys never written to .env files
**Idempotent:** Safe to run multiple times, checks existing state
**Dynamic:** Automatically detects all agents in client-agents/ folder
**Scalable:** Add new agents anytime, re-run script to provision them

**Last Updated:** October 27, 2025
**Status:** Ready for execution
**Estimated Time:** 30-60 minutes (scales with agent count)
