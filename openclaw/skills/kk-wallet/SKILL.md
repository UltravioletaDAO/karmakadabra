---
name: kk-wallet
description: Check USDC balances, derive wallet addresses from HD mnemonic, and sign EIP-3009 payment authorizations for KK agents on Base mainnet.
metadata:
  openclaw:
    requires:
      bins: ["python3"]
      env: ["KK_AGENT_NAME", "KK_WALLET_INDEX"]
---

# kk-wallet

Wallet operations for KarmaCadabra agents on Base mainnet. Wraps three scripts that handle balance checking, address derivation, and payment signing.

## Scripts

All scripts are located in `scripts/kk/` relative to the repository root. They output JSON to stdout and errors to stderr.

### check_balance.py

Check the USDC balance for an agent on Base mainnet. Reads the agent's address from `data/config/wallets.json` and queries the USDC contract on-chain.

```bash
python3 scripts/kk/check_balance.py --agent kk-karma-hello
```

Arguments:
- `--agent` (required): Agent name as registered in `data/config/wallets.json` (e.g., `kk-karma-hello`, `kk-coordinator`)

Output:
```json
{
  "agent": "kk-karma-hello",
  "address": "0x...",
  "balance": "12.500000",
  "token": "USDC",
  "network": "base"
}
```

### derive_wallet.py

Derive an Ethereum wallet address from the swarm HD mnemonic stored in AWS Secrets Manager (`kk/swarm-seed`). Each agent has a unique derivation index.

```bash
python3 scripts/kk/derive_wallet.py --index 1
```

Arguments:
- `--index` (required): HD derivation index (integer). Path used: `m/44'/60'/0'/0/{index}`

Output:
```json
{
  "index": 1,
  "address": "0x...",
  "name": "kk-karma-hello",
  "derivation_path": "m/44'/60'/0'/0/1"
}
```

Requires AWS credentials with access to `kk/swarm-seed` secret in `us-east-2`.

### sign_payment.py

Sign an EIP-3009 `transferWithAuthorization` for USDC on Base. Produces a signed authorization that can be submitted to the x402 facilitator for on-chain execution.

```bash
python3 scripts/kk/sign_payment.py --agent kk-karma-hello --to 0xRecipientAddress --amount 0.01
```

Arguments:
- `--agent` (required): Agent name
- `--to` (required): Recipient wallet address
- `--amount` (required): Amount in USDC (float, e.g., `0.01`)

Output:
```json
{
  "from": "0x...",
  "to": "0x...",
  "value": "10000",
  "amount_usdc": "0.010000",
  "validAfter": 0,
  "validBefore": 1740600000,
  "nonce": "0x...",
  "v": 27,
  "r": "0x...",
  "s": "0x...",
  "signature": "...",
  "network": "base",
  "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
}
```

The signed authorization is valid for 1 hour. The private key is loaded from `PRIVATE_KEY` env var or AWS Secrets Manager.

## Dependencies

- `web3` (for balance checks and signing)
- `eth_account` (for HD derivation and EIP-712 signing)
- `boto3` (for AWS Secrets Manager access)
- `shared.contracts_config` (network configuration)

## Error Handling

All scripts exit with code 1 on failure and print a JSON error object to stderr:
```json
{"error": "description of what went wrong", "agent": "kk-karma-hello"}
```
