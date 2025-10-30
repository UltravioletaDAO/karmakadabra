# Smart Contract Reference

This folder contains the ERC-8004 smart contract code modified with bidirectional trust pattern for reference and verification.

## Files

### ReputationRegistry.sol
**Source:** `/erc-8004/contracts/src/ReputationRegistry.sol`
**Purpose:** Modified ERC-8004 Reputation Registry with bidirectional rating support

**Key Additions (Week 1):**
- `rateValidator(uint256 agentValidatorId, uint8 rating)` - Server rates validator
- `ValidatorRated` event - Emitted when validator is rated
- `getValidatorRating(uint256 validatorId, uint256 serverId)` - Query validator rating

**Already Existing:**
- `rateClient(uint256 agentClientId, uint8 rating)` - Server rates client
- `ClientRated` event - Emitted when client is rated

## Deployed Contracts (Fuji Testnet)

### Identity Registry
**Address:** `0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618`
**Purpose:** Agent registration and identity management
**Key Functions:**
- `newAgent(string domain)` - Register new agent
- `updateAgent(uint256 agentId, string domain)` - Update agent domain
- `resolveByAddress(address agentAddress)` - Get agent info by address
- `resolve(uint256 agentId)` - Get agent info by ID

### Reputation Registry
**Address:** Integrated with Identity Registry
**Purpose:** Store bidirectional ratings
**Key Functions:**
- `rateClient(uint256 clientId, uint8 rating)` - Rate client (1-100)
- `rateValidator(uint256 validatorId, uint8 rating)` - Rate validator (1-100)
- `getClientRating(uint256 clientId, uint256 serverId)` - Get rating
- `getValidatorRating(uint256 validatorId, uint256 serverId)` - Get rating

### GLUE Token
**Address:** `0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743`
**Standard:** ERC-20 with EIP-3009 (gasless transfers)
**Purpose:** Payment currency for agent transactions

## Verification

### View on Snowtrace
- Identity Registry: https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
- GLUE Token: https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743

### Test with Foundry
```bash
cd /mnt/z/ultravioleta/dao/karmacadabra/erc-8004/contracts
forge test -vv --match-test testBidirectionalRating
```

## Gas Costs (From Week 1 Testing)

| Function | Gas Cost | vs rateClient() |
|----------|----------|----------------|
| rateClient() | 88,852 | baseline |
| rateValidator() | 88,866 | +14 (+0.02%) |

**Conclusion:** Bidirectional rating adds negligible gas overhead.

## ABI Reference

For Python interactions, the key ABI entries are:

```python
# rateValidator function
{
    "name": "rateValidator",
    "type": "function",
    "inputs": [
        {"name": "agentValidatorId", "type": "uint256"},
        {"name": "rating", "type": "uint8"}
    ],
    "outputs": [],
    "stateMutability": "nonpayable"
}

# ValidatorRated event
{
    "name": "ValidatorRated",
    "type": "event",
    "inputs": [
        {"name": "validatorId", "type": "uint256", "indexed": true},
        {"name": "serverId", "type": "uint256", "indexed": true},
        {"name": "rating", "type": "uint8", "indexed": false}
    ]
}
```

## Next Steps

For Week 2, these contracts will be used to:
1. Execute 100+ transactions with bidirectional ratings
2. Verify all ratings are stored correctly on-chain
3. Export transaction data for statistical analysis

See `../week2/2.0-CHECKLIST.md` for execution plan.
