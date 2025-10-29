# Balance Monitoring Script

## Overview

`check_all_balances.py` is a comprehensive balance monitoring tool for the Karmacadabra ecosystem. It checks native token and ERC-20 token balances across multiple blockchains for all system wallets.

## Features

✅ **Multi-chain Support**: 14 chains (7 testnets + 7 mainnets)
✅ **Multi-token**: Native tokens (AVAX, ETH, BNB, MATIC) + ERC-20s (GLUE, USDC)
✅ **AWS Integration**: Automatically fetches wallet addresses from AWS Secrets Manager
✅ **Auto-derivation**: Derives addresses from private keys when not explicitly stored
✅ **Categorization**: Groups wallets by type (System Agents, Deployers, User Agents)
✅ **Color-coded Output**: Visual indicators for balance levels
✅ **Flexible Filtering**: Filter by chain type or wallet type

## Supported Chains

### Active Testnets
- **Avalanche Fuji** - Main development chain (GLUE token deployed here)
- **Base Sepolia** - Base L2 testnet (USDC support)
- **Celo Sepolia** - Celo testnet (cUSD support, RPC: Ankr)

## Usage

### Basic Commands

```bash
# Check all chains (default - Fuji, Base Sepolia, Celo Sepolia)
python3 scripts/check_all_balances.py

# Check specific chain
python3 scripts/check_all_balances.py --chain fuji
python3 scripts/check_all_balances.py --chain base-sepolia
python3 scripts/check_all_balances.py --chain celo-sepolia
```

### Filter by Wallet Type

```bash
# Only system agents (validator, karma-hello, abracadabra, etc.)
python3 scripts/check_all_balances.py --wallet-type system

# Only deployers (ERC-20, ERC-8004)
python3 scripts/check_all_balances.py --wallet-type deployers

# Only user agents (48 community wallets)
python3 scripts/check_all_balances.py --wallet-type user

# All wallet types (default)
python3 scripts/check_all_balances.py --wallet-type all
```

### Additional Options

```bash
# Show wallets with 0 balance
python3 scripts/check_all_balances.py --show-empty

# Disable colored output (for logs/CI)
python3 scripts/check_all_balances.py --no-color

# Combined example
python3 scripts/check_all_balances.py --chain testnets --wallet-type system --show-empty
```

## Wallet Categories

### System Agents (6 wallets)
Production AI agents that buy/sell data:
- `validator-agent` - Data quality verification
- `karma-hello-agent` - Chat log seller/buyer
- `abracadabra-agent` - Transcript seller/buyer
- `skill-extractor-agent` - Skill profile extractor
- `voice-extractor-agent` - Personality profile extractor
- `client-agent` - Demo client for testing

### Deployers (1 wallet)
Smart contract deployment and system funding:
- `erc-20` - GLUE token deployer & main funding wallet

### User Agents (48 wallets)
Community member AI agents registered on-chain

## Output Format

The script provides:

1. **Per-wallet balances**
   - Native token balance (AVAX, ETH, etc.)
   - ERC-20 token balances (GLUE, USDC)
   - Color coding:
     - 🔴 Red: 0 balance (needs funding)
     - 🟡 Yellow: < 0.05 native token (low balance)
     - 🟢 Green: Sufficient balance

2. **Category totals**
   - Sum of all wallets in each category

3. **Summary statistics**
   - Total chains checked
   - Total wallets monitored
   - Active wallet categories

## Example Output

```
================================================================================
KARMACADABRA ECOSYSTEM - BALANCE MONITOR
================================================================================

[INFO] Fetching wallet addresses from AWS Secrets Manager...
[INFO] Found 55 wallets
[INFO] Checking 7 chain(s): fuji, sepolia, base-sepolia, polygon-amoy...

================================================================================
Avalanche Fuji (Testnet) (AVAX)
================================================================================

[INFO] Connected to fuji (Chain ID: 43113)

## System Agents (6 wallets)
────────────────────────────────────────────────────────────────────────────────

  validator-agent          0x1219eF9484BF7E40E6479141B32634623d37d507
    validator-agent
    Native:  0.495 AVAX
    GLUE     165000 GLUE

  [... more wallets ...]

  TOTAL:
    Native:  3.77 AVAX
    GLUE     880000 GLUE

================================================================================
SUMMARY
================================================================================

  Chains checked:    fuji, sepolia, base-sepolia, polygon-amoy, ...
  Total wallets:     55
  Wallet categories: 3

[DONE] Balance check complete
```

## Token Addresses

### Avalanche Fuji
- **GLUE**: `0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743` (6 decimals)

### Base Sepolia
- **USDC**: `0x036CbD53842c5426634e7929541eC2318f3dCF7e` (6 decimals)

### Celo Sepolia
- **cUSD**: `0x874069Fa1Eb16D44d622F2e0Ca25eeA172369bC1` (18 decimals)
- **RPC**: `https://rpc.ankr.com/celo_sepolia`

## Monitoring Best Practices

### Daily Checks
```bash
# Quick check of system agents on Fuji
python3 scripts/check_all_balances.py --chain fuji --wallet-type system
```

### Weekly Reviews
```bash
# Full report (all 3 chains)
python3 scripts/check_all_balances.py

# Check each chain individually
python3 scripts/check_all_balances.py --chain fuji
python3 scripts/check_all_balances.py --chain base-sepolia
python3 scripts/check_all_balances.py --chain celo-sepolia
```

### Before/After Deployments
```bash
# Check deployer balance
python3 scripts/check_all_balances.py --wallet-type deployers

# Verify all agents are funded
python3 scripts/check_all_balances.py --wallet-type all --show-empty
```

## Troubleshooting

### Connection Errors
Some public RPCs may be unreliable. The script will skip failed chains and continue:

```
[ERROR] Connection failed for sepolia: HTTPSConnectionPool...
[WARNING] Skipping chain...
```

This is normal for public RPC endpoints. The script continues checking other chains.

### Missing Addresses
If a wallet doesn't have an `address` field in AWS Secrets Manager, the script automatically derives it from the `private_key`:

```
[INFO] Derived address for validator-agent: 0x1219eF9...
```

### AWS Credentials
Ensure AWS credentials are configured:
```bash
# Check AWS configuration
aws sts get-caller-identity

# If not configured, use AWS CLI
aws configure
```

## Integration with Other Scripts

### Funding Wallets
Use with `fund-wallets.py` to identify low-balance wallets:

```bash
# 1. Check balances
python3 scripts/check_all_balances.py --chain fuji --wallet-type system

# 2. Fund wallets below threshold
cd erc-20 && python3 distribute-token.py
```

### Deployment Verification
After deploying agents:

```bash
# 1. Deploy contracts
cd erc-8004 && ./deploy-fuji.sh

# 2. Verify deployer balance
python3 scripts/check_all_balances.py --wallet-type deployers

# 3. Check all system agents funded
python3 scripts/check_all_balances.py --wallet-type system
```

## Adding New Chains

To add support for a new chain, edit `scripts/check_all_balances.py`:

```python
# Add to CHAINS dict
'new-chain': {
    'name': 'New Chain Name',
    'rpc': 'https://rpc.newchain.com',
    'chain_id': 12345,
    'native_symbol': 'NEW',
    'explorer': 'https://explorer.newchain.com'
}

# Add tokens (optional)
TOKEN_CONTRACTS['new-chain'] = {
    'USDC': {
        'address': '0x...',
        'decimals': 6
    }
}
```

## Related Scripts

- `scripts/fund-wallets.py` - Fund wallets with native tokens
- `erc-20/distribute-token.py` - Distribute GLUE tokens
- `scripts/setup_user_agents.py` - Setup user agent wallets
- `scripts/verify_onchain_data.py` - Verify on-chain registrations

## Support

For issues or questions:
1. Check AWS credentials are configured
2. Verify internet connectivity to RPC endpoints
3. Review `scripts/check_all_balances.py` code
4. Contact Ultravioleta DAO team

---

**Last Updated**: 2025-10-28
**Script Version**: 2.2
**Chains Supported**: 3 (Avalanche Fuji, Base Sepolia, Celo Sepolia)
**Total Wallets Monitored**: 55
**Features**: Per-chain balance labels, real-time RPC info
