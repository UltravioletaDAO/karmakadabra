# Base Sepolia Deployment - Contract Addresses

**Deployment Date:** 2025-11-03
**Network:** Base Sepolia Testnet
**Chain ID:** 84532
**RPC URL:** https://sepolia.base.org
**Explorer:** https://sepolia.basescan.org

---

## 📦 GLUE Token (ERC-20 with EIP-3009)

| Property | Value |
|----------|-------|
| **Contract Address** | `0xfEe5CC33479E748f40F5F299Ff6494b23F88C425` |
| **Token Name** | Gasless Ultravioleta DAO Extended Token |
| **Symbol** | GLUE |
| **Decimals** | 6 |
| **Initial Supply** | 24,157,817 GLUE |
| **Owner** | `0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8` |
| **Gas Used** | 2,022,556 |
| **Explorer** | [View on BaseScan](https://sepolia.basescan.org/address/0xfEe5CC33479E748f40F5F299Ff6494b23F88C425) |

**Features:**
- EIP-2612 Permit (gasless approvals)
- EIP-3009 transferWithAuthorization (gasless transfers)
- EIP-712 typed structured data hashing

---

## 🔐 ERC-8004 Registries

### Identity Registry

| Property | Value |
|----------|-------|
| **Contract Address** | `0x8a20f665c02a33562a0462a0908a64716Ed7463d` |
| **Registration Fee** | 0.005 ETH |
| **Explorer** | [View on BaseScan](https://sepolia.basescan.org/address/0x8a20f665c02a33562a0462a0908a64716Ed7463d) |

### Reputation Registry

| Property | Value |
|----------|-------|
| **Contract Address** | `0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F` |
| **Depends On** | IdentityRegistry |
| **Explorer** | [View on BaseScan](https://sepolia.basescan.org/address/0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F) |

### Validation Registry

| Property | Value |
|----------|-------|
| **Contract Address** | `0x3C545DBeD1F587293fA929385442A459c2d316c4` |
| **Depends On** | IdentityRegistry |
| **Expiration Slots** | 1000 |
| **Explorer** | [View on BaseScan](https://sepolia.basescan.org/address/0x3C545DBeD1F587293fA929385442A459c2d316c4) |

---

## 💰 Agent Wallets (Funded)

All system agent wallets have been funded with 0.005 ETH for gas:

| Agent | Address | Balance |
|-------|---------|---------|
| **Validator** | `0x1219eF9484BF7E40E6479141B32634623d37d507` | 0.005 ETH |
| **Karma-Hello** | `0x2C3e071df446B25B821F59425152838ae4931E75` | 0.005 ETH |
| **Abracadabra** | `0x940DDDf6fB28E611b132FbBedbc4854CC7C22648` | 0.005 ETH |
| **Skill Extractor** | `0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9` | 0.005 ETH |
| **Voice Extractor** | `0x8E0Db88181668cDe24660d7eE8Da18a77DdBBF96` | 0.005 ETH |

---

## 🔧 Configuration for Agents

**Environment Variables:**

```bash
# Base Sepolia Network
NETWORK=base-sepolia
CHAIN_ID=84532
RPC_URL=https://sepolia.base.org

# GLUE Token
GLUE_TOKEN_ADDRESS=0xfEe5CC33479E748f40F5F299Ff6494b23F88C425

# ERC-8004 Registries
IDENTITY_REGISTRY=0x8a20f665c02a33562a0462a0908a64716Ed7463d
REPUTATION_REGISTRY=0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F
VALIDATION_REGISTRY=0x3C545DBeD1F587293fA929385442A459c2d316c4

# Explorer
EXPLORER_URL=https://sepolia.basescan.org
```

**Python Configuration (shared/contracts_config.py):**

```python
BASE_SEPOLIA = {
    "chain_id": 84532,
    "rpc_url": "https://sepolia.base.org",
    "glue_token": "0xfEe5CC33479E748f40F5F299Ff6494b23F88C425",
    "identity_registry": "0x8a20f665c02a33562a0462a0908a64716Ed7463d",
    "reputation_registry": "0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F",
    "validation_registry": "0x3C545DBeD1F587293fA929385442A459c2d316c4",
    "explorer_url": "https://sepolia.basescan.org"
}
```

---

## 📊 Deployment Summary

**Total Contracts Deployed:** 4
- GLUE Token: ✅
- Identity Registry: ✅
- Reputation Registry: ✅
- Validation Registry: ✅

**Total Gas Used:** 4,505,000 (approx)
**Total Cost:** ~0.004505 ETH

**Agent Funding:**
- Agents Funded: 5
- Amount per Agent: 0.005 ETH
- Total Funded: 0.025 ETH

**Deployer Balance Remaining:** ~0.220 ETH

---

## ✅ Next Steps

1. **Register Agents On-Chain:**
   ```bash
   python scripts/register_agents_base_sepolia.py
   ```

2. **Distribute GLUE Tokens:**
   ```bash
   python scripts/distribute_glue_base_sepolia.py
   ```

3. **Verify Contracts (Manual):**
   - Go to https://sepolia.basescan.org/
   - Enter contract addresses
   - Use "Verify and Publish" with Solidity compiler version 0.8.20

4. **Update Agent Configurations:**
   - Update `shared/contracts_config.py` with Base Sepolia config
   - Update agent `.env` files to use Base Sepolia addresses

---

## 🔗 Useful Links

- **Base Sepolia Faucet:** https://www.alchemy.com/faucets/base-sepolia
- **Base Sepolia Bridge:** https://bridge.base.org/
- **Base Sepolia Explorer:** https://sepolia.basescan.org/
- **RPC Endpoint:** https://sepolia.base.org
- **Chain ID:** 84532

---

**Status:** ✅ ALL DEPLOYMENTS COMPLETE
**Branch:** `base-sepolia-deployment`
**Worktree:** `Z:\ultravioleta\dao\karmacadabra-base-sepolia`
