# 🎯 Karmacadabra: Trustless Agent Economy

> AI agents that autonomously buy/sell data using blockchain-based gasless micropayments

**[🇪🇸 Versión en Español](./README.es.md)** | **🇺🇸 English Version**

[![Avalanche](https://img.shields.io/badge/Avalanche-Fuji-E84142?logo=avalanche)](https://testnet.snowtrace.io/)
[![ERC-8004](https://img.shields.io/badge/ERC--8004%20Extended-Bidirectional%20Rating-blue)](https://eips.ethereum.org/EIPS/eip-8004)
[![x402](https://img.shields.io/badge/x402-Payment%20Protocol-green)](https://www.x402.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)

---

## 📦 What's Implemented

### ✅ Phase 1: Blockchain Infrastructure (COMPLETE)

**Deployed on Avalanche Fuji Testnet** - October 22, 2025

| Contract | Address | Chain ID |
|----------|---------|----------|
| **GLUE Token (EIP-3009)** | [\`0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743\`](https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743) | 43113 |
| **Identity Registry** | [\`0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618\`](https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618) | 43113 |
| **Reputation Registry** | [\`0x932d32194C7A47c0fe246C1d61caF244A4804C6a\`](https://testnet.snowtrace.io/address/0x932d32194C7A47c0fe246C1d61caF244A4804C6a) | 43113 |
| **Validation Registry** | [\`0x9aF4590035C109859B4163fd8f2224b820d11bc2\`](https://testnet.snowtrace.io/address/0x9aF4590035C109859B4163fd8f2224b820d11bc2) | 43113 |
| **Transaction Logger** | [\`0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654\`](https://testnet.snowtrace.io/address/0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654) | 43113 |

**Agent Wallets** (Funded with 55,000 GLUE each):
- Validator: \`0x1219eF9484BF7E40E6479141B32634623d37d507\`
- Karma-Hello: \`0x2C3e071df446B25B821F59425152838ae4931E75\`
- Abracadabra: \`0x940DDDf6fB28E611b132FbBedbc4854CC7C22648\`
- Client Agent: \`0xCf30021812F27132d36dc791E0eC17f34B4eE8BA\`

### ✅ Sprint 1: Foundation (COMPLETE - October 2025)

**Python Shared Utilities** (\`shared/\`) - 3,100+ lines of production code:

1. **\`base_agent.py\`** (600+ lines) - ERC-8004 integration, reputation, Web3.py, AWS Secrets
2. **\`payment_signer.py\`** (470+ lines) - EIP-712 signing, EIP-3009 signatures
3. **\`x402_client.py\`** (530+ lines) - x402 HTTP payment protocol
4. **\`a2a_protocol.py\`** (650+ lines) - Agent discovery, AgentCard, Skills
5. **\`validation_crew.py\`** (550+ lines) - CrewAI validation pattern
6. **\`tests/\`** (1,200+ lines) - 26 passing unit tests + integration framework

**API Docs**: [\`shared/README.md\`](./shared/README.md)

### 🔴 Phase 2: Agent Development (NEXT)

Foundation complete, now implementing agents:
- Validator - Data quality verification
- Karma-Hello - Twitch chat logs
- Abracadabra - Stream transcripts
- Client - Generic buyer

---

## 🏗️ Architecture

\`\`\`
┌────────────────────────────────────────┐
│ Avalanche Fuji (Layer 1)               │
│ • GLUE Token (EIP-3009)                │
│ • ERC-8004 Registries                  │
└────────────┬───────────────────────────┘
             │ Web3.py
┌────────────┴───────────────────────────┐
│ x402 Facilitator (Layer 2 - Rust)     │
│ • Verifies EIP-712 signatures          │
│ • Executes on-chain transfers          │
└────────────┬───────────────────────────┘
             │ httpx
┌────────────┴───────────────────────────┐
│ AI Agents (Layer 3 - Python)          │
│ • A2A discovery • CrewAI validation    │
└────────────────────────────────────────┘
\`\`\`

**Key Innovation**: Agents don't need gas - they sign payments off-chain (EIP-712), facilitator executes on-chain.

---

## 🚀 Quick Start

\`\`\`bash
git clone https://github.com/ultravioletadao/karmacadabra.git
cd karmacadabra/shared
pip install web3 boto3 eth-account python-dotenv httpx pydantic crewai
cd tests && pytest -m unit  # 26 passing tests
\`\`\`

**Usage Example:**

\`\`\`python
from shared import ERC8004BaseAgent, sign_payment, X402Client

# Register agent
agent = ERC8004BaseAgent(
    agent_name="my-agent",
    agent_domain="my-agent.ultravioletadao.xyz"
)
agent_id = agent.register_agent()

# Sign payment
sig = sign_payment(
    from_address="0xBuyer...",
    to_address="0xSeller...",
    amount_glue="0.01",
    private_key="0x..."
)

# Buy data
async with X402Client(private_key="0x...") as client:
    response, settlement = await client.buy_with_payment(
        seller_url="https://seller.xyz/api/data",
        seller_address="0xSeller...",
        amount_glue="0.01"
    )
\`\`\`

---

## 📚 Documentation

- **[MASTER_PLAN.md](./MASTER_PLAN.md)** - Roadmap and architecture
- **[shared/README.md](./shared/README.md)** - API reference
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Technical decisions
- **[shared/tests/README.md](./shared/tests/README.md)** - Testing guide

---

## 🧪 Testing

\`\`\`bash
cd shared/tests
pytest -m unit              # 26 passing tests (fast)
pytest -m integration       # Fuji testnet integration
pytest --cov=shared         # With coverage
\`\`\`

---

## 🏔️ Why Avalanche?

- **Ultravioleta DAO's home** - Where our DAO was born
- **2-second finality** - Instant agent transactions
- **Low gas fees** - 0.01 GLUE micropayments viable
- **EVM compatible** - Full Solidity support

**ERC-8004 Extended**: Custom bidirectional reputation (buyers + sellers rate each other)

---

## 💡 Technologies

| Tech | Status |
|------|--------|
| Solidity + Foundry | ✅ Deployed |
| Rust (x402) | ⚠️ External |
| Python 3.11 | ✅ Foundation ready |
| Web3.py | ✅ Integrated |
| CrewAI | ✅ Pattern implemented |
| pytest | ✅ 26 tests passing |

---

## 🔧 Tools

\`\`\`bash
# Generate wallet
python generate-wallet.py --name my-agent

# Distribute GLUE
cd erc-20 && python distribute-token.py

# Check agent
python -c "from shared import ERC8004BaseAgent; ..."
\`\`\`

---

## 🚧 Roadmap

- ✅ Phase 1: Contracts deployed
- ✅ Sprint 1: Foundation complete
- 🔴 Sprint 2: Agents (in progress)
- 📋 Phase 3: Production data
- 📋 Phase 4: Mainnet

**Full roadmap**: [MASTER_PLAN.md](./MASTER_PLAN.md)

---

## 🔗 Links

- [Snowtrace Explorer](https://testnet.snowtrace.io/)
- [GLUE Token](https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743)
- [Fuji Faucet](https://faucet.avax.network/)
- [ERC-8004 Spec](https://eips.ethereum.org/EIPS/eip-8004)
- [x402 Protocol](https://www.x402.org)

---

**Built with ❤️ by Ultravioleta DAO on Avalanche**
