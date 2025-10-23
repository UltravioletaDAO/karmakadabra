# Shared Utilities for Karmacadabra Agents

Core infrastructure and utilities used by all agents in the Karmacadabra ecosystem.

## 📦 Components

### `base_agent.py` - ERC8004BaseAgent Class

Base class for all Karmacadabra agents providing:

**Features:**
- ✅ Identity Registry registration
- ✅ Reputation management (bidirectional ratings)
- ✅ Web3.py integration with Avalanche Fuji
- ✅ AWS Secrets Manager integration
- ✅ Automatic wallet management
- ✅ Transaction handling and gas estimation
- ✅ Comprehensive logging

**Usage:**
```python
from shared import ERC8004BaseAgent

# Initialize agent (uses AWS Secrets Manager)
agent = ERC8004BaseAgent(
    agent_name="validator-agent",
    agent_domain="validator.ultravioletadao.xyz"
)

# Register on-chain
agent_id = agent.register_agent()

# Rate another agent
agent.rate_server(server_agent_id=1, rating=85)

# Query ratings
has_rating, rating = agent.get_server_rating(
    client_id=agent.agent_id,
    server_id=1
)
```

**See:** `base_agent_example.py` for complete examples

---

### `secrets_manager.py` - AWS Secrets Manager Integration

Centralized private key management with automatic fallback:

**Features:**
- ✅ Fetch keys from AWS Secrets Manager
- ✅ Fallback to local `.env` files
- ✅ Automatic agent discovery
- ✅ Caching for performance

**Usage:**
```python
from shared import get_private_key

# Automatically uses AWS or local .env
private_key = get_private_key("validator-agent")
```

**See:** `AWS_SECRETS_SETUP.md` for complete guide

---

### `transaction_logger.py` - On-Chain Transaction Logging

Utility for logging transaction metadata on-chain via TransactionLogger contract.

**Features:**
- ✅ UTF-8 message encoding
- ✅ Automatic gas estimation
- ✅ Transaction receipt verification

**Usage:**
```python
from shared import log_transaction

# Log a transaction with metadata
tx_hash = log_transaction(
    w3=w3,
    logger_contract=logger_contract,
    account=account,
    message="Agent purchased chat logs: 0.01 GLUE"
)
```

---

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install web3 boto3 eth-account python-dotenv

# Configure AWS (if using Secrets Manager)
aws configure
```

### Environment Variables

All agents need these in their `.env` file:

```bash
# Wallet (leave empty to use AWS Secrets Manager)
PRIVATE_KEY=

# Blockchain
RPC_URL_FUJI=https://avalanche-fuji-c-chain-rpc.publicnode.com
CHAIN_ID=43113

# ERC-8004 Registries
IDENTITY_REGISTRY=0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
REPUTATION_REGISTRY=0x932d32194C7A47c0fe246C1d61caF244A4804C6a
VALIDATION_REGISTRY=0x9aF4590035C109859B4163fd8f2224b820d11bc2

# GLUE Token
GLUE_TOKEN_ADDRESS=0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
```

### Example: Create a New Agent

```python
from shared import ERC8004BaseAgent

class MyCustomAgent(ERC8004BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="my-custom-agent",
            agent_domain="my-custom.ultravioletadao.xyz"
        )

        # Register on-chain
        self.agent_id = self.register_agent()

        # Custom initialization
        self.setup_custom_logic()

    def setup_custom_logic(self):
        """Your custom agent logic here"""
        pass
```

---

## 📚 Documentation

- **AWS Secrets Manager**: `AWS_SECRETS_SETUP.md`
- **Transaction Logging**: `../TRANSACTION_LOGGING.md`
- **Full Architecture**: `../ARCHITECTURE.md`
- **Master Plan**: `../MASTER_PLAN.md`

---

## 🔧 Development

### Run Example

```bash
cd shared
python base_agent_example.py
```

### Test AWS Integration

```bash
python -m shared.secrets_manager validator-agent
```

---

## 🏗️ Architecture Integration

```
┌─────────────────────────────────────────────────────────┐
│                    All Karmacadabra Agents              │
│                                                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│  │Validator  │  │Karma-Hello│  │Abracadabra│  ...     │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘          │
│        │              │              │                 │
│        └──────────────┼──────────────┘                 │
│                       │                                │
│                       ▼                                │
│          ┌────────────────────────┐                    │
│          │  ERC8004BaseAgent      │                    │
│          │  (shared/base_agent.py)│                    │
│          ├────────────────────────┤                    │
│          │ • Registration         │                    │
│          │ • Reputation           │                    │
│          │ • Web3 Integration     │                    │
│          └──────┬─────────────────┘                    │
│                 │                                      │
└─────────────────┼──────────────────────────────────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │  Avalanche Fuji Testnet     │
    │  • Identity Registry        │
    │  • Reputation Registry      │
    │  • Validation Registry      │
    └─────────────────────────────┘
```

---

**Questions?** See main [README.md](../README.md) or [MASTER_PLAN.md](../MASTER_PLAN.md)
