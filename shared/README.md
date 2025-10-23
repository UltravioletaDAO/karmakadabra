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

### `payment_signer.py` - EIP-712 Payment Signing

EIP-712/EIP-3009 signature creation for gasless GLUE Token payments.

**Features:**
- ✅ EIP-712 domain separator generation
- ✅ `transferWithAuthorization` signature creation
- ✅ Random nonce generation
- ✅ Time window management
- ✅ Signature verification
- ✅ GLUE amount conversion utilities

**Usage:**
```python
from shared import PaymentSigner, sign_payment

# Method 1: Using PaymentSigner class
signer = PaymentSigner(
    glue_token_address="0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743",
    chain_id=43113
)

signature = signer.sign_transfer_authorization(
    from_address="0xAlice...",
    to_address="0xBob...",
    value=signer.glue_amount("0.01"),  # 0.01 GLUE
    private_key="0x..."
)

# Method 2: Using convenience function
signature = sign_payment(
    from_address="0xAlice...",
    to_address="0xBob...",
    amount_glue="0.01",
    private_key="0x..."
)

# Use signature in x402 payment header or facilitator call
print(f"v={signature['v']}, r={signature['r']}, s={signature['s']}")
```

**Signature Output:**
```python
{
    'from': '0xAlice...',
    'to': '0xBob...',
    'value': 10000,  # 0.01 GLUE in smallest units
    'validAfter': 1698765432,
    'validBefore': 1698769032,
    'nonce': '0xab77...',
    'v': 28,
    'r': '0x9be1...',
    's': '0x2414...',
    'signature': '9be1...2414...',
    'amount_human': '0.010000'
}
```

---

### `x402_client.py` - x402 HTTP Payment Client

Python client for x402 payment protocol - enables gasless HTTP payments.

**Features:**
- ✅ Payment header generation (X-Payment with base64 payload)
- ✅ Facilitator API integration (/verify, /settle, /health)
- ✅ Automatic retry with exponential backoff
- ✅ Error handling for payment failures
- ✅ High-level buyer API (`buy_with_payment`)

**Usage (Buyer Agent):**
```python
from shared import X402Client

# Initialize client
async with X402Client(private_key="0x...") as client:
    # Buy data from seller
    response, settlement = await client.buy_with_payment(
        seller_url="https://karma-hello.xyz/api/logs",
        seller_address="0xBob...",
        amount_glue="0.01"
    )

    print(f"Data: {response.content}")
    print(f"TX Hash: {settlement['txHash']}")
```

**Usage (Convenience Function):**
```python
from shared import buy_from_agent

# One-liner purchase
data, settlement = await buy_from_agent(
    seller_url="https://karma-hello.xyz/api/logs",
    seller_address="0xBob...",
    amount_glue="0.01",
    buyer_private_key="0x..."
)
```

**Protocol Flow:**
1. Buyer creates signed payment (EIP-712)
2. Buyer sends HTTP with X-Payment header
3. Facilitator verifies signature
4. Seller returns data
5. Facilitator executes transferWithAuthorization()

---

### `a2a_protocol.py` - Agent-to-Agent Communication

A2A (Agent-to-Agent) protocol implementation for agent discovery and skill invocation.

**Features:**
- ✅ AgentCard publication and discovery
- ✅ Skill registration with pricing
- ✅ HTTP discovery endpoint (/.well-known/agent-card)
- ✅ Async client for skill invocation
- ✅ Integration with x402 payment protocol
- ✅ Pydantic data models

**Usage (Seller Agent):**
```python
from shared import ERC8004BaseAgent, A2AServer

class MySellerAgent(ERC8004BaseAgent, A2AServer):
    def __init__(self):
        super().__init__(
            agent_name="my-seller",
            agent_domain="my-seller.ultravioletadao.xyz"
        )

        # Register on-chain
        self.agent_id = self.register_agent()

        # Add skills
        self.add_skill(
            skill_id="get_data",
            name="Get Data",
            description="Retrieve data from database",
            price_amount="0.01",
            input_schema={"type": "object"}
        )

        # Publish AgentCard
        self.publish_agent_card(
            name="My Data Seller",
            description="Sells data services"
        )

    # Later in FastAPI:
    @app.get("/.well-known/agent-card")
    async def agent_card():
        return self.get_agent_card_json()
```

**Usage (Buyer Agent):**
```python
from shared import A2AClient

async with A2AClient() as client:
    # Discover agent
    card = await client.discover("my-seller.ultravioletadao.xyz")

    # Find skill
    skill = card.find_skill("get_data")
    print(f"Price: {skill.price.amount} {skill.price.currency}")

    # Invoke skill with payment
    response = await client.invoke_skill(
        agent_card=card,
        skill_id="get_data",
        params={"query": "stream_12345"},
        payment_header=x402_payment_header
    )
```

**AgentCard Schema:**
```python
{
  "agentId": 1,
  "name": "My Data Seller",
  "description": "Sells data services",
  "version": "1.0.0",
  "domain": "my-seller.ultravioletadao.xyz",
  "skills": [
    {
      "skillId": "get_data",
      "name": "Get Data",
      "description": "Retrieve data from database",
      "price": {"amount": "0.01", "currency": "GLUE"},
      "inputSchema": {"type": "object"},
      "outputSchema": {},
      "endpoint": "/api/get_data"
    }
  ],
  "trustModels": ["erc-8004"],
  "paymentMethods": ["x402-eip3009-GLUE"],
  "registrations": [
    {
      "contract": "IdentityRegistry",
      "address": "0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618",
      "agentId": 1,
      "network": "avalanche-fuji:43113"
    }
  ]
}
```

---

### `validation_crew.py` - CrewAI Validation Pattern

Reusable multi-agent validation crew for data quality verification using CrewAI.

**Features:**
- ✅ Three-agent validation system (Quality, Fraud, Price)
- ✅ Automated scoring (0-100 scale)
- ✅ CrewAI tools for schema/timestamp/similarity checks
- ✅ Detailed validation reports
- ✅ Pass/fail thresholds
- ✅ Issue detection and reporting

**Agents:**
1. **Quality Analyst** - Schema compliance, timestamp validation, required fields
2. **Fraud Detector** - Duplicate detection, authenticity verification
3. **Price Reviewer** - Market rate comparison, price fairness

**Usage:**
```python
from shared import ValidationCrew

# Initialize crew
crew = ValidationCrew(openai_api_key="sk-...")

# Validate transaction data
result = crew.validate(
    data={
        "messages": [...],
        "timestamp": 1698765432
    },
    data_type="logs",
    seller_id=1,
    buyer_id=2,
    price="0.01"
)

# Check result
if result.passed:
    print(f"Validation passed! Score: {result.score}/100")
else:
    print(f"Validation failed. Issues: {result.issues}")

# Detailed scores
print(f"Quality: {result.quality_score}/100")
print(f"Fraud: {result.fraud_score}/100")
print(f"Price: {result.price_score}/100")
```

**ValidationResult Schema:**
```python
{
    "score": 85,                    # Overall score (weighted average)
    "quality_score": 90,            # Quality analyst score
    "fraud_score": 95,              # Fraud detector score
    "price_score": 70,              # Price reviewer score
    "passed": True,                 # Passed threshold (>= 70)
    "report": "Detailed analysis...",
    "issues": []                    # List of detected issues
}
```

**CrewAI Tools Included:**
- `CheckSchemaTool` - JSON schema validation
- `VerifyTimestampsTool` - Timestamp validity checks
- `SimilarityCheckTool` - Duplicate detection
- `MarketCheckTool` - Price fairness verification

This pattern is used by the Validator agent and can be adapted for other validation needs.

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
