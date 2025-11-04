# Manual Contract Verification on Basescan - Base Sepolia

If automated verification doesn't work, follow these instructions to manually verify each contract on Basescan.

---

## Prerequisites

1. Go to https://basescan.org/ and create an account
2. You'll need the contract source code and compiler settings

---

## Contract 1: GLUE Token

**Address**: `0xfEe5CC33479E748f40F5F299Ff6494b23F88C425`

1. Go to: https://sepolia.basescan.org/address/0xfEe5CC33479E748f40F5F299Ff6494b23F88C425#code
2. Click **"Verify and Publish"**
3. Fill in the form:
   - **Compiler Type**: Solidity (Single file)
   - **Compiler Version**: v0.8.20+commit.a1b79de6
   - **Open Source License Type**: MIT
4. Click **Continue**
5. Paste the flattened contract code:

```bash
# In PowerShell/Windows Terminal:
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\erc-20
forge flatten src/GLUE.sol > GLUE_flattened.sol
```

6. Paste contents of `GLUE_flattened.sol` into the text area
7. **Constructor Arguments**: (leave empty - no constructor args)
8. **Optimization**: Enabled with 200 runs
9. Click **"Verify and Publish"**

---

## Contract 2: Identity Registry

**Address**: `0x8a20f665c02a33562a0462a0908a64716Ed7463d`

1. Go to: https://sepolia.basescan.org/address/0x8a20f665c02a33562a0462a0908a64716Ed7463d#code
2. Click **"Verify and Publish"**
3. Fill in the form:
   - **Compiler Type**: Solidity (Single file)
   - **Compiler Version**: v0.8.20+commit.a1b79de6
   - **Open Source License Type**: MIT
4. Click **Continue**
5. Paste the flattened contract code:

```bash
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\erc-8004\contracts
forge flatten src/IdentityRegistry.sol > IdentityRegistry_flattened.sol
```

6. Paste contents of `IdentityRegistry_flattened.sol` into the text area
7. **Constructor Arguments**: (leave empty - no constructor args)
8. **Optimization**: Enabled with 200 runs
9. Click **"Verify and Publish"**

---

## Contract 3: Reputation Registry

**Address**: `0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F`

1. Go to: https://sepolia.basescan.org/address/0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F#code
2. Click **"Verify and Publish"**
3. Fill in the form:
   - **Compiler Type**: Solidity (Single file)
   - **Compiler Version**: v0.8.20+commit.a1b79de6
   - **Open Source License Type**: MIT
4. Click **Continue**
5. Paste the flattened contract code:

```bash
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\erc-8004\contracts
forge flatten src/ReputationRegistry.sol > ReputationRegistry_flattened.sol
```

6. Paste contents of `ReputationRegistry_flattened.sol` into the text area
7. **Constructor Arguments**: You need to encode the Identity Registry address

```python
# In Python:
from eth_abi import encode

identity_registry = "0x8a20f665c02a33562a0462a0908a64716Ed7463d"
constructor_args = encode(['address'], [identity_registry]).hex()
print(constructor_args)
# Output: 0000000000000000000000008a20f665c02a33562a0462a0908a64716ed7463d
```

8. **Optimization**: Enabled with 200 runs
9. Click **"Verify and Publish"**

---

## Contract 4: Validation Registry

**Address**: `0x3C545DBeD1F587293fA929385442A459c2d316c4`

1. Go to: https://sepolia.basescan.org/address/0x3C545DBeD1F587293fA929385442A459c2d316c4#code
2. Click **"Verify and Publish"**
3. Fill in the form:
   - **Compiler Type**: Solidity (Single file)
   - **Compiler Version**: v0.8.20+commit.a1b79de6
   - **Open Source License Type**: MIT
4. Click **Continue**
5. Paste the flattened contract code:

```bash
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia\erc-8004\contracts
forge flatten src/ValidationRegistry.sol > ValidationRegistry_flattened.sol
```

6. Paste contents of `ValidationRegistry_flattened.sol` into the text area
7. **Constructor Arguments**: You need to encode the Identity Registry address and expiration slots

```python
# In Python:
from eth_abi import encode

identity_registry = "0x8a20f665c02a33562a0462a0908a64716Ed7463d"
expiration_slots = 1000
constructor_args = encode(['address', 'uint256'], [identity_registry, expiration_slots]).hex()
print(constructor_args)
# Output: 0000000000000000000000008a20f665c02a33562a0462a0908a64716ed7463d00000000000000000000000000000000000000000000000000000000000003e8
```

8. **Optimization**: Enabled with 200 runs
9. Click **"Verify and Publish"**

---

## Quick Commands Summary

Generate all flattened files at once:

**PowerShell:**
```powershell
cd Z:\ultravioleta\dao\karmacadabra-base-sepolia

# GLUE Token
cd erc-20
forge flatten src/GLUE.sol > GLUE_flattened.sol

# ERC-8004 Contracts
cd ..\erc-8004\contracts
forge flatten src/IdentityRegistry.sol > IdentityRegistry_flattened.sol
forge flatten src/ReputationRegistry.sol > ReputationRegistry_flattened.sol
forge flatten src/ValidationRegistry.sol > ValidationRegistry_flattened.sol

cd ..\..
```

---

## Verification Status

After verification, update this checklist:

- [ ] GLUE Token: https://sepolia.basescan.org/address/0xfEe5CC33479E748f40F5F299Ff6494b23F88C425
- [ ] Identity Registry: https://sepolia.basescan.org/address/0x8a20f665c02a33562a0462a0908a64716Ed7463d
- [ ] Reputation Registry: https://sepolia.basescan.org/address/0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F
- [ ] Validation Registry: https://sepolia.basescan.org/address/0x3C545DBeD1F587293fA929385442A459c2d316c4

---

## Troubleshooting

**Error: "Constructor arguments mismatch"**
- Make sure you're encoding the constructor arguments correctly
- Check that the address is checksummed correctly
- Use the Python script above to generate the exact hex encoding

**Error: "Compilation failed"**
- Verify you're using Solidity 0.8.20
- Check that optimization is enabled with 200 runs
- Make sure you're using the flattened source code

**Error: "Contract already verified"**
- Contract may already be verified by someone else
- Check if the contract page shows "Contract Source Code Verified"
