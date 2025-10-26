# x402scan Listing Guide for Karmacadabra Facilitator

**Status**: Ready to submit (requires testnet chain support PR first)

**x402scan Repository**: https://github.com/Merit-Systems/x402scan

---

## Overview

x402scan is a manually curated registry of x402 facilitators. Unlike automated indexing, facilitators must submit a PR to be listed.

**Current Issue**: x402scan's UI only supports mainnet chains (BASE, SOLANA). Our facilitator is on **testnets** (Avalanche Fuji, Base Sepolia), so we need to add testnet support first.

---

## Step 1: Get Facilitator Wallet Address

The facilitator's **hot wallet address** (not token addresses) is needed. This is the wallet that pays gas fees.

**Command to retrieve:**
```bash
aws secretsmanager get-secret-value \
  --secret-id karmacadabra \
  --query SecretString \
  --output text | jq -r '.facilitator'
```

**Expected output:**
```json
{
  "address": "0x...",
  "private_key": "0x..."
}
```

**Save the address** - this goes in the `addresses` field.

---

## Step 2: Fork and Clone x402scan

```bash
git clone https://github.com/YOUR_USERNAME/x402scan
cd x402scan
git checkout -b add-testnet-support-and-karmacadabra
```

---

## Step 3: Add Testnet Chain Support

**File: `src/types/chain.ts`**

```typescript
export enum Chain {
  BASE = 'base',
  SOLANA = 'solana',
  POLYGON = 'polygon',
  OPTIMISM = 'optimism',
  BASE_SEPOLIA = 'base-sepolia',      // ← ADD THIS
  AVALANCHE_FUJI = 'avalanche-fuji',  // ← ADD THIS
}

export const SUPPORTED_CHAINS = Object.values([
  Chain.BASE,
  Chain.SOLANA,
  Chain.BASE_SEPOLIA,      // ← ADD THIS
  Chain.AVALANCHE_FUJI,    // ← ADD THIS
]);

export const CHAIN_LABELS: Record<Chain, string> = {
  [Chain.BASE]: 'Base',
  [Chain.SOLANA]: 'Solana',
  [Chain.POLYGON]: 'Polygon',
  [Chain.OPTIMISM]: 'Optimism',
  [Chain.BASE_SEPOLIA]: 'Base Sepolia',         // ← ADD THIS
  [Chain.AVALANCHE_FUJI]: 'Avalanche Fuji',     // ← ADD THIS
};

export const CHAIN_ICONS: Record<Chain, string> = {
  [Chain.BASE]: '/base.png',
  [Chain.SOLANA]: '/solana.png',
  [Chain.POLYGON]: '/polygon.png',
  [Chain.OPTIMISM]: '/optimism.png',
  [Chain.BASE_SEPOLIA]: '/base.png',            // ← ADD THIS (reuses Base logo)
  [Chain.AVALANCHE_FUJI]: '/avalanche.png',     // ← ADD THIS
};
```

**Note**: You'll need to add `/avalanche.png` logo to the `public/` directory.

---

## Step 4: Create Karmacadabra Logo

**Requirements:**
- Format: PNG
- Size: ~200x200px recommended
- Background: Transparent
- File: `public/karmacadabra.png`

**Design elements:**
- Ultravioleta DAO branding
- AI agent theme
- Blockchain/payment iconography

---

## Step 5: Add Karmacadabra Facilitator

**File: `src/lib/facilitators.ts`**

**Add this before the `export const facilitators` array:**

```typescript
const karmacadabraFacilitator: Facilitator = {
  id: 'karmacadabra',
  name: 'Karmacadabra',
  image: '/karmacadabra.png',
  link: 'https://github.com/UltravioletaDAO/karmacadabra',
  addresses: {
    [Chain.AVALANCHE_FUJI]: ['0xYOUR_FACILITATOR_WALLET_ADDRESS_HERE'],
    [Chain.BASE_SEPOLIA]: ['0xYOUR_FACILITATOR_WALLET_ADDRESS_HERE'],
  },
  color: 'var(--color-purple-600)',  // Or choose another color
};
```

**Then add to the array:**

```typescript
export const facilitators: Facilitator[] = [
  coinbaseFacilitator,
  x402rsFacilitator,
  payAiFacilitator,
  aurraCloudFacilitator,
  thirdwebFacilitator,
  corbitsFacilitator,
  daydreamsFacilitator,
  karmacadabraFacilitator,  // ← ADD THIS
];
```

**Note**: The same wallet address can be used for both chains if it's the same hot wallet.

---

## Step 6: Commit and Push

```bash
# Add testnet chain support
git add src/types/chain.ts
git add public/avalanche.png  # If you added it
git commit -m "Add testnet chain support (Base Sepolia, Avalanche Fuji)

- Add BASE_SEPOLIA and AVALANCHE_FUJI to Chain enum
- Add chain labels and icons
- Backend already supports these chains in schema
- Needed for testnet facilitators like Karmacadabra"

# Add Karmacadabra facilitator
git add src/lib/facilitators.ts
git add public/karmacadabra.png
git commit -m "Add Karmacadabra facilitator

- Payment facilitator for trustless AI agent economy
- Supports Avalanche Fuji (GLUE, USDC, WAVAX)
- Supports Base Sepolia (USDC)
- Deployed at https://facilitator.ultravioletadao.xyz
- Operator: Ultravioleta DAO"

git push origin add-testnet-support-and-karmacadabra
```

---

## Step 7: Create Pull Request

**PR Title:**
```
Add testnet support and Karmacadabra facilitator
```

**PR Description:**

```markdown
## Summary

This PR adds two improvements:

1. **Testnet chain support** - Adds Base Sepolia and Avalanche Fuji to the Chain enum
2. **Karmacadabra facilitator** - First testnet-focused facilitator

## Changes

### Testnet Chain Support

- Added `Chain.BASE_SEPOLIA` and `Chain.AVALANCHE_FUJI` to `src/types/chain.ts`
- These chains are already supported in the backend schema but weren't exposed in the UI
- Enables listing testnet facilitators

### Karmacadabra Facilitator

**URL:** https://facilitator.ultravioletadao.xyz

**Description:** Payment facilitator for Karmacadabra's trustless AI agent economy where autonomous agents buy/sell data services using blockchain micropayments.

**Networks Supported:**
- ✅ Avalanche Fuji (GLUE, USDC, WAVAX)
- ✅ Base Sepolia (USDC)

**Use Case:**
- Karma-Hello agents selling Twitch chat logs
- Abracadabra agents selling stream transcriptions
- Validator agents providing quality verification
- All payments use EIP-3009 gasless meta-transactions

**Health Check:**
```bash
curl https://facilitator.ultravioletadao.xyz/health
# {"kinds":[{"network":"avalanche-fuji","scheme":"exact","x402Version":1},{"network":"base-sepolia","scheme":"exact","x402Version":1}]}
```

**Operator:** Ultravioleta DAO
**Status:** Production (AWS Fargate)
**Documentation:** https://github.com/UltravioletaDAO/karmacadabra

## Testing

- [x] Health endpoint returns expected response
- [x] Facilitator accepts payments on Avalanche Fuji
- [x] Facilitator accepts payments on Base Sepolia
- [x] Logo renders correctly
- [x] Chain icons display properly

## Screenshots

(Add screenshot of facilitator card in x402scan UI)
```

---

## Alternative: Wait for Mainnet Deployment

If x402scan maintainers reject testnet support, you can:

1. **Deploy to mainnet chains** (Base, Avalanche C-Chain)
2. **List only after mainnet deployment**
3. **Use existing Chain.BASE** if you add Base mainnet support

---

## Verification After Merge

Once merged, your facilitator should appear at:
- **Dashboard**: https://x402scan.com
- **Facilitator detail**: https://x402scan.com/facilitators/karmacadabra

**Expected display:**
- Karmacadabra logo
- Links to GitHub documentation
- Shows Avalanche Fuji and Base Sepolia networks
- Lists facilitator wallet addresses

---

## Questions to Ask x402scan Maintainers

If unsure about testnet support:

1. "Do you accept testnet facilitators, or mainnet only?"
2. "Should testnet chains be in a separate UI section?"
3. "Is there a plan to add testnet support to the Chain enum?"
4. "Can we use the same wallet address for multiple chains?"

---

## Next Steps

- [ ] Retrieve facilitator wallet address from AWS
- [ ] Create Karmacadabra logo (200x200px PNG)
- [ ] Fork x402scan repository
- [ ] Make changes to chain.ts and facilitators.ts
- [ ] Test locally (if possible)
- [ ] Submit PR
- [ ] Respond to review feedback
- [ ] Announce listing on social media

---

**Last Updated:** October 26, 2025
**Facilitator URL:** https://facilitator.ultravioletadao.xyz
**Health Status:** ✅ Active
