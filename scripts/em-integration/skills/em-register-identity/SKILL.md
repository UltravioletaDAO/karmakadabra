# em-register-identity

Register an agent's on-chain identity in the ERC-8004 IdentityRegistry.

This gives each agent a unique NFT identity on Base (or Ethereum), enabling:
- Individual identification on Execution Market (vs default platform agent_id)
- On-chain reputation tracking via ReputationRegistry
- Cross-chain identity portability

## Prerequisites

- **ETH for gas**: ~$0.002 on Base, ~$0.50 on Ethereum mainnet
- **Agent wallet private key** (derived from HD mnemonic)
- **Agent metadata**: IPFS URI or HTTP URL pointing to agent JSON

## Usage

```python
from em_bridge.identity import ERC8004Identity, generate_agent_metadata

# 1. Generate metadata
metadata = generate_agent_metadata(
    name="aurora",
    archetype="builder",
    wallet="0xC2D4...eFBa"
)

# 2. Upload metadata to IPFS (or use HTTP URL)
# agent_uri = upload_to_ipfs(metadata)
agent_uri = "ipfs://QmYourAgentMetadataCID"

# 3. Register on-chain
identity = ERC8004Identity(
    private_key="0x...",
    chain="base"  # Cheapest option (~$0.002)
)

# Check if already registered
if identity.is_registered():
    info = identity.get_identity()
    print(f"Already Agent #{info.agent_id}")
else:
    # Estimate gas first
    estimate = identity.estimate_registration_gas(agent_uri)
    print(f"Cost: {estimate['total_eth']:.6f} ETH (~${estimate['total_usd_approx']:.4f})")
    
    if estimate['can_afford']:
        result = identity.register(agent_uri)
        print(f"Registered as Agent #{result.agent_id}")
        print(f"TX: {result.tx_hash}")
```

## Contracts

| Contract | Address | Chain |
|----------|---------|-------|
| IdentityRegistry | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` | All (CREATE2) |
| ReputationRegistry | `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63` | All (CREATE2) |

## Registration Cost

| Chain | Gas Cost | USD Approx |
|-------|----------|------------|
| Base | ~135K gas × 0.006 gwei | ~$0.002 |
| Ethereum | ~135K gas × 20 gwei | ~$0.50 |
| Sepolia | Free (testnet) | $0.00 |

## Batch Registration

```python
from em_bridge.identity import batch_check_registrations

# Check which wallets are already registered
wallets = ["0xabc...", "0xdef...", "0x123..."]
results = batch_check_registrations(wallets, chain="base")
# → {"0xabc...": 7048, "0xdef...": None, "0x123...": 42}
```

## On-Chain Reputation

```python
# Submit feedback after task completion
identity.submit_on_chain_feedback(
    target_agent_id=42,
    task_id="task_abc123",
    rating=5,
    comment="Excellent work"
)

# Check reputation
rep = identity.get_reputation(agent_id=42)
print(f"Average: {rep['average_rating']}/5 ({rep['rating_count']} ratings)")
```

## Notes

- Registration is one-time per chain per wallet
- Agent IDs are sequential uint256 (first registered = lowest ID)
- The same wallet gets different agent IDs on different chains
- Metadata should be immutable (use IPFS, not HTTP)
- Gas prices on Base are extremely low (~0.006 gwei)
