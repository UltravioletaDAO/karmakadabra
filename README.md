# 🎯 Karmacadabra: Trustless Agent Economy

> AI agents that autonomously buy/sell data using blockchain-based gasless micropayments

**[🇪🇸 Versión en Español](./README.es.md)** | **🇺🇸 English Version**

> **⚡ Important:** This implements an **ERC-8004 EXTENDED version** with bidirectional reputation (NOT the base spec!) deployed on **Base Sepolia** (previously Avalanche Fuji). Both buyers and sellers rate each other after transactions.

[![Base](https://img.shields.io/badge/Base-Sepolia-0052FF?logo=ethereum)](https://sepolia.basescan.org/)
[![Multi-Chain](https://img.shields.io/badge/Multi--Chain-Fuji%20+%20Base-purple)](https://github.com/UltravioletaDAO/karmacadabra)
[![ERC-8004](https://img.shields.io/badge/ERC--8004%20Extended-Bidirectional%20Rating-blue)](https://eips.ethereum.org/EIPS/eip-8004)
[![x402](https://img.shields.io/badge/x402-Payment%20Protocol-green)](https://www.x402.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-Latest-orange?logo=rust)](https://www.rust-lang.org/)
[![Deployed](https://img.shields.io/badge/Deployed-Base%20Sepolia-success)](https://sepolia.basescan.org/)

---

## 🎯 What is Karmacadabra?

**Karmacadabra** is an ecosystem of autonomous AI agents that **buy and sell data** without human intervention using:

- **ERC-8004 Extended** - **NOT the base implementation!** This is a custom extension enabling **bidirectional reputation** (both buyers and sellers rate each other)
- **A2A protocol** (Pydantic AI) for agent-to-agent communication
- **x402 + EIP-3009** for HTTP micropayments (gasless!)
- **CrewAI** for multi-agent orchestration
- **Multi-chain support** - Base Sepolia (primary) + Avalanche Fuji (backup)

### 🌐 Multi-Chain Strategy - Now on Base Sepolia

**Karmacadabra migrated to Base Sepolia** (Nov 2025) as the primary testnet:

- **Ethereum L2 ecosystem**: Access to broader developer tooling and community
- **Fast finality**: 2-second block times for instant agent transactions
- **Low costs**: Optimistic rollup reduces gas fees significantly
- **Mainnet path**: Clearer path to Base Mainnet deployment

**Avalanche Fuji remains as backup network** - all contracts deployed on both testnets with identical agent infrastructure.

See `docs/BASE_SEPOLIA_INTEGRATION_COMPLETE.md` for full multi-chain details.

### The Problem We Solve

**Karma-Hello** has rich Twitch chat logs but no audio context.
**Abracadabra** has stream transcriptions but no chat data.

**Solution**: Agents autonomously negotiate and purchase complementary data, building a complete streaming context. All transactions are verified, on-chain, and gasless.

### Buyer+Seller Ecosystem

![Agent Relationships - Buyer+Seller Pattern](./docs/images/architecture/agent-relationships-buyerseller-pattern-ecosystem.png)

*All agents implement the buyer+seller pattern - they both purchase inputs and sell outputs, creating a self-sustaining circular economy.*

---

## 🎯 Key Features

- ✅ **Gasless Micropayments**: Agents don't need ETH/AVAX for gas
- ✅ **Bidirectional Reputation**: Custom ERC-8004 extension - buyers AND sellers rate each other (not in base spec!)
- ✅ **Native to Avalanche**: Deployed on our home chain for optimal performance
- ✅ **Trustless Validation**: Independent validators verify data quality
- ✅ **Agent Discovery**: A2A protocol AgentCards at `/.well-known/agent-card`
- ✅ **Multi-Agent Workflows**: CrewAI crews for complex tasks
- ✅ **50+ Monetizable Services**: From $0.01 to $200 GLUE per service

---

## 🚀 **LIVE ON BASE SEPOLIA** - Migrated November 4, 2025

### Primary Network: Base Sepolia (Chain ID: 84532)

| Contract | Address | Status |
|----------|---------|--------|
| **GLUE Token (EIP-3009)** | [`0xfEe5CC33479E748f40F5F299Ff6494b23F88C425`](https://sepolia.basescan.org/address/0xfEe5CC33479E748f40F5F299Ff6494b23F88C425) | ✅ Verified (Sourcify) |
| **Identity Registry** | [`0x8a20f665c02a33562a0462a0908a64716Ed7463d`](https://sepolia.basescan.org/address/0x8a20f665c02a33562a0462a0908a64716Ed7463d) | ✅ Verified (Sourcify) |
| **Reputation Registry** | [`0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F`](https://sepolia.basescan.org/address/0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F) | ✅ Verified (Sourcify) |
| **Validation Registry** | [`0x3C545DBeD1F587293fA929385442A459c2d316c4`](https://sepolia.basescan.org/address/0x3C545DBeD1F587293fA929385442A459c2d316c4) | ✅ Verified (Sourcify) |

**Network**: Base Sepolia Testnet (Chain ID: 84532)
**Registration Fee**: 0.005 ETH
**Token Supply**: 24,157,817 GLUE (6 decimals)
**Block Explorer**: https://sepolia.basescan.org

### Backup Network: Avalanche Fuji (Chain ID: 43113)

Contracts also deployed on Avalanche Fuji for redundancy. See `docs/BASE_SEPOLIA_INTEGRATION_COMPLETE.md` for addresses.

### Agent Wallets (Base Sepolia - Funded)

| Agent | Wallet Address | GLUE Balance | Registry ID | Domain |
|-------|----------------|--------------|-------------|--------|
| **Validator** | [`0x1219eF9484BF7E40E6479141B32634623d37d507`](https://sepolia.basescan.org/address/0x1219eF9484BF7E40E6479141B32634623d37d507) | 110,000 GLUE | #1 | `validator.karmacadabra.ultravioletadao.xyz` |
| **Karma-Hello** | [`0x2C3e071df446B25B821F59425152838ae4931E75`](https://sepolia.basescan.org/address/0x2C3e071df446B25B821F59425152838ae4931E75) | 55,000 GLUE | #2 | `karma-hello.karmacadabra.ultravioletadao.xyz` |
| **Abracadabra** | [`0x940DDDf6fB28E611b132FbBedbc4854CC7C22648`](https://sepolia.basescan.org/address/0x940DDDf6fB28E611b132FbBedbc4854CC7C22648) | 55,000 GLUE | #3 | `abracadabra.karmacadabra.ultravioletadao.xyz` |
| **Skill-Extractor** | [`0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9`](https://sepolia.basescan.org/address/0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9) | 55,000 GLUE | #4 | `skill-extractor.karmacadabra.ultravioletadao.xyz` |
| **Voice-Extractor** | [`0x8E0Db88181668cDe24660d7eE8Da18a77DdBBF96`](https://sepolia.basescan.org/address/0x8E0Db88181668cDe24660d7eE8Da18a77DdBBF96) | 55,000 GLUE | #5 | `voice-extractor.karmacadabra.ultravioletadao.xyz` |

**Total Distributed**: 330,000 GLUE | **All agents registered on-chain** | **Gas funded**: 0.005-0.007 ETH each

**Domain Convention**: All agents use `<agent-name>.karmacadabra.ultravioletadao.xyz` format (registered on-chain)

**View All Contracts**: [Base Sepolia Explorer](https://sepolia.basescan.org/)

---

## 📦 What's Implemented

### ✅ Phase 1: Blockchain Infrastructure (COMPLETE)

**Deployed on Avalanche Fuji Testnet** - October 22, 2025

All smart contracts are live and verified on Snowtrace. Agent wallets have been created and funded with 55,000 GLUE each.

**Infrastructure Status:**
- ✅ GLUE Token (EIP-3009) deployed and verified
- ✅ ERC-8004 Extended registries (Identity, Reputation, Validation) deployed
- ✅ TransactionLogger contract deployed
- ✅ 6 agent wallets created and funded (Client, Validator, Karma-Hello, Abracadabra, Voice-Extractor, Skill-Extractor)
- ✅ AWS Secrets Manager configured for centralized key management
- ✅ x402 facilitator deployed to AWS Fargate (https://facilitator.ultravioletadao.xyz)

### ✅ Foundation Components (COMPLETE - October 2025)

**Python Shared Utilities** (`shared/`) - **3,300+ lines** of production-ready code:

1. **`base_agent.py`** (857 lines) - ERC-8004 integration, **buyer+seller pattern built-in**, reputation system, Web3.py, AWS Secrets
   - **ALL agents inherit**: `discover_agent()`, `buy_from_agent()`, `save_purchased_data()`, `create_agent_card()`, `create_fastapi_app()`
2. **`payment_signer.py`** (470+ lines) - EIP-712 signing, EIP-3009 payment signatures
3. **`x402_client.py`** (530+ lines) - x402 HTTP payment protocol client
4. **`a2a_protocol.py`** (650+ lines) - Agent discovery, AgentCard, Skills
5. **`validation_crew.py`** (550+ lines) - CrewAI validation pattern (Quality + Fraud + Price)
6. **`tests/`** (1,200+ lines) - **26 passing unit tests** + integration test framework

**Testing:** ✅ All tests passing - Unit (30/30), Integration (4/4 agents starting), E2E (4/4 complete flow)

**Documentation:**
- API Reference: [`shared/README.md`](./shared/README.md)
- Testing Guide: [`shared/tests/README.md`](./shared/tests/README.md)
- Architecture: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)

### ✅ Phase 2: Agent Development (COMPLETE - October 2025)

**System Agents** - Marketplace infrastructure complete (7/7 components)

#### ✅ Validator Agent (COMPLETE)
**Independent data quality verification service** - `validator/` - **1,545+ lines**

**What it does:**
- Multi-agent validation using CrewAI (9 AI agents across 3 crews)
- Quality analysis + fraud detection + price review
- On-chain validation score submission (validator pays gas)
- FastAPI server with A2A protocol support

**Key Files:**
1. `main.py` (470+ lines) - ValidatorAgent class, FastAPI server
2. `crews/quality_crew.py` (200+ lines) - Quality validation crew
3. `crews/fraud_crew.py` (200+ lines) - Fraud detection crew
4. `crews/price_crew.py` (200+ lines) - Price fairness crew
5. `test_validator.py` (280+ lines) - Testing suite with --quick, --live, --crews modes
6. `README.md` (330+ lines) - Full documentation
7. `TESTING.md` (280+ lines) - Testing guide

**Testing:**
```bash
cd validator
python test_validator.py --quick  # Mock test (no dependencies)
python test_validator.py --live   # Test with running validator
```

**Deployment:**
- Wallet: `0x1219eF9484BF7E40E6479141B32634623d37d507`
- Balance: 55,000 GLUE
- Validation fee: 0.001 GLUE per validation
- Port: 8001

#### ✅ Client Agent (COMPLETE)
**Buyer+Seller orchestrator - comprehensive user insights marketplace** - `client-agent/` - **485 lines**

**What it does:**
- **BUYS** data from 5 agents using **inherited base agent methods** (0.211 GLUE cost)
  - Chat logs from Karma-Hello (0.01 GLUE)
  - Skills from Skill-Extractor (0.10 GLUE)
  - Personality from Voice-Extractor (0.10 GLUE)
  - Validation from Validator (0.001 GLUE)
- **SELLS** comprehensive user reports synthesized from multiple sources (1.00 GLUE)
- **Economics**: 0.789 GLUE profit per report (374% margin)

**Key Features:**
- Uses **inherited buyer methods**: `discover_agent()`, `buy_from_agent()`, `save_purchased_data()`
- Uses **inherited seller methods**: `create_agent_card()`, `create_fastapi_app()`
- Multi-agent orchestration (buys from 5 agents, synthesizes 1 report)
- A2A protocol discovery + x402 payment handling
- Demonstrates complete buyer+seller pattern

**Key Files:**
1. `main.py` (485 lines) - ClientAgent class with complete buyer+seller orchestration
2. `.env.example` (40+ lines) - Configuration template
3. `README.md` (230+ lines) - Usage documentation

**Deployment:**
- Wallet: `0xCf30021812F27132d36dc791E0eC17f34B4eE8BA`
- Balance: 220,000 GLUE
- Sells at: 1.00 GLUE per comprehensive report
- Spends: 0.211 GLUE per report generation

#### ✅ Data Integration (COMPLETE)
**Sample data files for testing** - `data/` - **495+ lines**

**What it provides:**
- Realistic chat logs from Karma-Hello seller
- Realistic transcriptions from Abracadabra seller
- Both files designed to pass validation (0.8-0.9 scores)

**Key Files:**
1. `karma-hello/chat_logs_20251023.json` - 156 messages, 23 users, 2-hour stream
2. `abracadabra/transcription_20251023.json` - 15 segments, 2-hour transcript
3. `README.md` (300+ lines) - Data format documentation

**Sample Data Stats:**
- Chat logs: 156 messages from 23 unique users
- Transcription: 15 segments, 7200 seconds (2 hours)
- Both share `stream_id: stream_20251023_001` for complementary data testing

#### ✅ Karma-Hello Agent (COMPLETE)
**Twitch chat log seller + buyer** - `karma-hello-agent/` - **720+ lines**

**What it does:**
- **SELLS** chat logs from MongoDB via x402 protocol
- **BUYS** transcriptions from Abracadabra agent
- FastAPI server with A2A protocol support
- Local file fallback for testing
- Multi-tier pricing (0.01-200 GLUE)

**Key Features:**
- MongoDB integration for production logs
- Buyer capabilities added (purchases transcriptions)
- Storage: `purchased_transcriptions/` directory
- Port: 8002

**Deployment:**
- Wallet: `0x2C3e071df446B25B821F59425152838ae4931E75`
- Balance: 55,000 GLUE

#### ✅ Abracadabra Agent (COMPLETE)
**Stream transcript seller + buyer** - `abracadabra-agent/` - **720+ lines**

**What it does:**
- **SELLS** transcripts from SQLite+Cognee via x402 protocol
- **BUYS** chat logs from Karma-Hello agent
- FastAPI server with A2A protocol support
- Multi-tier pricing (0.02-300 GLUE)

**Key Features:**
- SQLite integration for transcript storage
- Buyer capabilities added (purchases chat logs)
- Storage: `purchased_chat_logs/` directory
- Port: 8003

**Deployment:**
- Wallet: `0x940DDDf6fB28E611b132FbBedbc4854CC7C22648`
- Balance: 55,000 GLUE

#### ✅ Voice-Extractor Agent (COMPLETE)
**Linguistic personality profiler** - `voice-extractor-agent/` - **523+ lines**

**What it does:**
- **BUYS** chat logs from Karma-Hello (0.01 GLUE)
- **SELLS** linguistic personality profiles (0.02-0.40 GLUE)
- 8-category psycholinguistic analysis
- Multi-tier pricing (basic, standard, complete, enterprise)

**Key Features:**
- CrewAI-based analysis (simplified for MVP)
- A2A protocol discovery
- x402 payment integration
- Port: 8005

**Economic Model:**
- Net profit: 0.03 GLUE per extraction (300% margin)
- Initial balance: 55,000 GLUE (budgeted)

#### ✅ Skill-Extractor Agent (COMPLETE)
**Skill and competency profiler** - `skill-extractor-agent/` - **790+ lines**

**What it does:**
- **BUYS** chat logs from Karma-Hello (0.01 GLUE)
- **SELLS** skill/competency profiles (0.02-0.50 GLUE)
- 5-category extraction framework
- Multi-tier pricing (basic, standard, complete, enterprise)

**Key Features:**
- Interest extraction + skill identification
- Tools/platforms audit + monetization analysis
- CrewAI-based multi-agent analysis
- Port: 8085

**5 Analysis Categories:**
1. Interest Extraction (recurring topics, engagement depth)
2. Skill & Sub-Skill Identification (2-level hierarchy)
3. Tools & Platforms (comprehensive tech stack audit)
4. Interaction Style (collaboration patterns)
5. Monetization Potential (commercial viability analysis)

**Economic Model:**
- Net profit: 0.04 GLUE per extraction (400% margin)
- Initial balance: 55,000 GLUE (budgeted)

---

### ✅ Phase 6: Production Deployment (COMPLETE - October 26, 2025)

**AWS ECS Fargate Infrastructure** - All 5 agents deployed to production with HTTPS

**Live Production Endpoints:**

| Agent | HTTPS Endpoint | AgentCard Discovery |
|-------|---------------|-------------------|
| **Validator** | [https://validator.karmacadabra.ultravioletadao.xyz](https://validator.karmacadabra.ultravioletadao.xyz/health) | [/.well-known/agent-card](https://validator.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Karma-Hello** | [https://karma-hello.karmacadabra.ultravioletadao.xyz](https://karma-hello.karmacadabra.ultravioletadao.xyz/health) | [/.well-known/agent-card](https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Abracadabra** | [https://abracadabra.karmacadabra.ultravioletadao.xyz](https://abracadabra.karmacadabra.ultravioletadao.xyz/health) | [/.well-known/agent-card](https://abracadabra.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Skill-Extractor** | [https://skill-extractor.karmacadabra.ultravioletadao.xyz](https://skill-extractor.karmacadabra.ultravioletadao.xyz/health) | [/.well-known/agent-card](https://skill-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Voice-Extractor** | [https://voice-extractor.karmacadabra.ultravioletadao.xyz](https://voice-extractor.karmacadabra.ultravioletadao.xyz/health) | [/.well-known/agent-card](https://voice-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |

**Infrastructure Components:**
- ✅ **Compute**: AWS ECS Fargate with Spot instances (70% cost savings)
- ✅ **SSL/TLS**: ACM wildcard certificate with automatic DNS validation
- ✅ **Networking**: VPC, Application Load Balancer, Route53 DNS
- ✅ **Security**: AWS Secrets Manager, Security Groups, IAM roles
- ✅ **Monitoring**: CloudWatch Logs, Metrics, Container Insights, Alarms
- ✅ **Auto-scaling**: 1-3 tasks per service based on CPU/Memory
- ✅ **Cost**: Optimized at ~$81-96/month

**Test the Production Stack:**
```bash
# Verify ALL endpoints (facilitator + all agents)
python scripts/test_all_endpoints.py

# Alternative: Test only agents (no facilitator)
python scripts/test_production_stack.py

# Test agent-to-agent purchases (requires GLUE tokens)
python scripts/demo_client_purchases.py --production
```

**Endpoints tested by `test_all_endpoints.py`:**
- **Facilitator**: `/health`, `/supported`, `/verify`
- **All 5 Agents**: `/health`, `/.well-known/agent-card`
- **Total**: 13 endpoints verified in ~5 seconds

**Documentation**: See [`docs/guides/GUIA_PRUEBAS_PRODUCCION.md`](./docs/guides/GUIA_PRUEBAS_PRODUCCION.md) for complete testing guide

---

## 🔐 Security Architecture

![Security Architecture - Key Management](./docs/images/architecture/security-architecture-key-management-and-access-control.png)

*AWS Secrets Manager provides centralized, secure key management with rotation support and audit trails.*

⚠️ **CRITICAL SECURITY POLICY**: Private keys are **NEVER stored in `.env` files**. All keys are fetched from AWS Secrets Manager at runtime. For detailed setup instructions, see [shared/AWS_SECRETS_SETUP.md](./shared/AWS_SECRETS_SETUP.md).

---

## 🏗️ Architecture

### Three-Layer System

![High-Level Architecture](./docs/images/architecture/high-level-architecture-three-layer-system.png)

*Karmacadabra's three-layer architecture: Blockchain (Layer 1), Payment Facilitator (Layer 2), AI Agents (Layer 3)*

```
┌──────────────────────────────────────────────────────────────────┐
│   AVALANCHE FUJI TESTNET (Our Home - Layer 1)                   │
│  ┌──────────────────┐    ┌─────────────────────────────────┐    │
│  │  GLUE Token      │    │ ERC-8004 EXTENDED               │    │
│  │  (EIP-3009)      │    │  (Bidirectional!)               │    │
│  │  Gasless txs ✓   │    │  • Identity Registry            │    │
│  └──────────────────┘    │  • Reputation Registry          │    │
│                          │  • Validation Registry          │    │
│                          │    ❗Validator writes here❗    │    │
│                          └─────────────┬───────────────────┘    │
│                                        │ validationResponse()   │
└────────────────────────────────────────┼────────────────────────┘
                          ▲              │ (Validator pays gas!)
                          │              ▼
┌─────────────────────────┴─────────┬────────────────────────────┐
│   x402 Facilitator (Rust)         │   Validator Agent (Python) │
│   • Verifies EIP-712 signatures   │   • Listens for requests   │
│   • Executes transferWith...()    │   • CrewAI validates data  │
│   • Stateless (no DB)             │   • Pays ~0.01 AVAX gas    │
└───────────┬────────────────────────┴────────────────────────────┘
            │
            ▲                            ▲
┌───────────┴────────┐      ┌───────────┴────────┐
│ Karma-Hello Agent  │      │ Abracadabra Agent  │
│ • Sells: Chat logs │◄────►│ • Sells: Transcripts│
│ • Buys: Transcripts│      │ • Buys: Chat logs   │
│ • Price: 0.01 GLUE │      │ • Price: 0.02 GLUE  │
│ • Data: MongoDB    │      │ • Data: SQLite      │
│ • Gas: 0 (gasless!)│      │ • Gas: 0 (gasless!) │
└────────────────────┘      └─────────────────────┘
            ▲                            ▲
            └────────┬───────────────────┘
                     ▼
         ┌────────────────────┐
         │  Validator Agent   │
         │  • CrewAI crew     │
         │  • Quality score   │
         │  • Fee: 0.001 GLUE │
         └────────────────────┘
```

---

## 💳 x402 Payment Facilitator

The **x402 facilitator** is the payment processing engine that enables gasless micropayments between agents. It's written in Rust and implements the HTTP 402 Payment Required protocol.

### What It Does

The facilitator sits between buyer and seller agents, verifying payment signatures and executing blockchain transactions:

1. **Payment Verification**: Receives EIP-712 signed payment authorizations from buyers
2. **Signature Validation**: Verifies the cryptographic signature matches the payment details
3. **On-Chain Execution**: Calls `transferWithAuthorization()` on the GLUE token contract
4. **Settlement**: Transfers GLUE from buyer to seller (facilitator pays gas, not agents)
5. **Response**: Returns success/failure to enable the seller to deliver data

**Key Innovation**: Agents never need AVAX/ETH for gas fees. They only sign off-chain payment authorizations.

### Endpoints

**Production**: `https://facilitator.ultravioletadao.xyz`
**Local**: `http://localhost:9000`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (returns service status) |
| `/supported` | GET | List supported payment methods (GLUE, USDC, WAVAX) |
| `/verify` | POST | Verify payment signature without executing |
| `/settle` | POST | Execute payment on-chain (transfers tokens) |

### Architecture

**Technology**: Rust + Axum web framework
**Image**: `ukstv/x402-facilitator:latest` (prebuilt)
**Network**: Avalanche Fuji testnet
**Wallet**: 2.197 AVAX for gas fees (funded from ERC-20 deployer)

**Environment Variables**:
```bash
PORT=8080
HOST=0.0.0.0
RUST_LOG=info
SIGNER_TYPE=private-key
RPC_URL_AVALANCHE_FUJI=https://avalanche-fuji-c-chain-rpc.publicnode.com
GLUE_TOKEN_ADDRESS=0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
EVM_PRIVATE_KEY=<from AWS Secrets Manager>
```

### Economic Model

The facilitator **does not charge fees** - it's a public service for the Karmacadabra economy:

- ✅ Free payment verification
- ✅ Free transaction settlement
- ✅ Facilitator pays all gas fees
- ⚠️ Requires funding: ~1-2 AVAX per month for gas

**Why no fees?** The facilitator is infrastructure for the agent economy. Agent service fees (0.001-200 GLUE) already provide value capture. The facilitator's role is to enable frictionless transactions.

### Deployment

**Docker Compose (Local Testing)**:
```bash
# Facilitator runs on port 9000
docker-compose up -d facilitator
curl http://localhost:9000/health
curl http://localhost:9000/supported
```

**AWS ECS Fargate (Production)**:
```bash
# Deploy with automated scripts
python scripts/deploy-all.py

# Or individual components
python scripts/fund-wallets.py --confirm        # Fund facilitator wallet
python scripts/build-and-push.py facilitator    # Build Docker image
python scripts/deploy-to-fargate.py facilitator # Deploy to Fargate
```

**Monitoring**:
```bash
# Check facilitator health
curl https://facilitator.ultravioletadao.xyz/health

# View logs
aws logs tail /ecs/karmacadabra-prod/facilitator --follow

# Check wallet balance
cast balance 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8 --rpc-url https://avalanche-fuji-c-chain-rpc.publicnode.com
```

### Integration with Agents

Agents use the facilitator through the `x402_client.py` shared library:

```python
from shared.x402_client import X402Client

# Buyer agent creates payment
client = X402Client(
    facilitator_url="https://facilitator.ultravioletadao.xyz",
    private_key=os.getenv("PRIVATE_KEY")
)

# Sign payment authorization (off-chain)
payment = client.create_payment(
    to="0x2C3e071df446B25B821F59425152838ae4931E75",  # Seller
    amount=Decimal("0.01"),  # 0.01 GLUE
    token_address="0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"
)

# Make HTTP request with X-Payment header
response = requests.get(
    "https://karma-hello.karmacadabra.ultravioletadao.xyz/logs/20251022",
    headers={"X-Payment": payment}
)
```

**Seller agent verifies through middleware**:
```python
from shared.base_agent import ERC8004BaseAgent

class KarmaHelloAgent(ERC8004BaseAgent):
    def __init__(self):
        super().__init__()
        # x402 middleware automatically verifies payments
        self.app.add_middleware(X402Middleware, facilitator_url=self.facilitator_url)
```

**Source Code**: `x402-rs/` directory | [x402-rs/README.md](./x402-rs/README.md)

---

## 💰 What Can Be Monetized?

### Karma-Hello Services (20+ products)
- **Tier 1** (0.01 GLUE): Chat logs, user activity
- **Tier 2** (0.10 GLUE): ML predictions, sentiment analysis
- **Tier 3** (0.20 GLUE): Fraud detection, economic health
- **Enterprise** (up to 200 GLUE): White-label, custom models

### Abracadabra Services (30+ products)
- **Tier 1** (0.02 GLUE): Raw transcripts, enhanced transcripts
- **Tier 2** (0.15 GLUE): Clip generation, blog posts
- **Tier 3** (0.35 GLUE): Predictive engine, recommendations
- **Tier 4** (1.50 GLUE): Auto video editing, image generation
- **Enterprise** (up to 100 GLUE): Custom AI models

**Full catalog**: [docs/MONETIZATION_OPPORTUNITIES.md](./docs/MONETIZATION_OPPORTUNITIES.md)

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Blockchain** | Avalanche Fuji | EVM testnet for smart contracts |
| **Contracts** | Solidity + Foundry | ERC-8004 registries + GLUE token |
| **Facilitator** | Rust (Axum) | x402 payment verification |
| **Agents** | Python 3.11+ | AI agent runtime |
| **AI Framework** | CrewAI | Multi-agent orchestration |
| **LLM** | GPT-4o | Analysis and validation |
| **Web3** | web3.py + ethers-rs | Blockchain interaction |
| **Data** | MongoDB + SQLite + Cognee | Agent data sources |
| **Cloud** | AWS ECS Fargate, ALB, Route53 | Production hosting |
| **Security** | AWS Secrets Manager, IAM | Key management & access control |
| **Monitoring** | CloudWatch Logs, Metrics | Observability |

---

## 🔗 Related Projects

### Lighthouse - Universal Monitoring for Web3

**Repository:** [github.com/UltravioletaDAO/lighthouse](https://github.com/UltravioletaDAO/lighthouse)

Lighthouse is a **standalone universal monitoring platform** that monitors Karmacadabra agents and any other Web3 service.

**Key Features:**
- AWS Synthetics alternative (50x cheaper: $0.20/mo vs $51.84/mo)
- Crypto-native payments (USDC on Avalanche, Base, Polygon)
- Multi-chain support
- TimescaleDB for time-series data
- Trustless design (users control alert keys)

**Tech Stack:**
- Rust backend (Axum framework)
- PostgreSQL + TimescaleDB (time-series optimization)
- Docker Compose + Terraform (AWS EC2 + EBS)
- Python workers (Celery + Playwright for canary flows)

**Status:** Design phase complete, ready for Phase 1 development (Nov 2025)

**Relationship to Karmacadabra:**
- Lighthouse monitors Karmacadabra agents as one of many customers
- Uses x402 facilitator as external service (optional)
- No code dependencies - fully standalone
- Developed within this repository initially, extracted Oct 2025

**Documentation:**
- [Master Plan](https://github.com/UltravioletaDAO/lighthouse/blob/main/lighthouse-master-plan.md) - Complete architecture (60+ pages)
- [Deployment Guide](https://github.com/UltravioletaDAO/lighthouse/blob/main/DEPLOYMENT-STEP-BY-STEP.md) - Granular step-by-step
- [Database Architecture](https://github.com/UltravioletaDAO/lighthouse/blob/main/DATABASE-ARCHITECTURE-ANALYSIS.md) - Why TimescaleDB

---

## 📚 Documentation

| Document | Description | Time |
|----------|-------------|------|
| [docs/guides/QUICKSTART.md](./docs/guides/QUICKSTART.md) | Get running in 30 minutes | 30 min |
| [MASTER_PLAN.md](./MASTER_PLAN.md) | Complete vision & roadmap | 60 min |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Technical deep dive | 45 min |
| [docs/architecture-diagrams.md](./docs/architecture-diagrams.md) | Visual architecture diagrams | 15 min |
| [docs/MONETIZATION_OPPORTUNITIES.md](./docs/MONETIZATION_OPPORTUNITIES.md) | All services & pricing | 30 min |
| [CLAUDE.md](./CLAUDE.md) | Developer guidance | 15 min |
| [docs/INDEX.md](./docs/INDEX.md) | Documentation index | 5 min |

**Component READMEs**: Each folder has detailed setup instructions.

---

## 🚀 Quick Start

**✨ Contracts already deployed!** You can start building agents immediately.

### Option 1: Docker Compose (Fastest - Recommended)

Run all 6 services with one command:

```bash
# 1. Clone repository
git clone https://github.com/ultravioletadao/karmacadabra.git
cd karmacadabra

# 2. Create .env files from examples
for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
  cp agents/$agent/.env.example agents/$agent/.env
done
cp x402-rs/.env.example x402-rs/.env

# 3. Configure AWS credentials (for private keys & OpenAI keys)
aws configure

# 4. Start all services
docker-compose up -d

# 5. Check status
docker-compose ps
curl http://localhost:9000/health  # facilitator
curl http://localhost:9002/health  # karma-hello
```

**Services running:**
- Facilitator (9000) - `http://localhost:9000/health`
- Validator (9001) - `http://localhost:9001/health`
- Karma-Hello (9002) - `http://localhost:9002/health`
- Abracadabra (9003) - `http://localhost:9003/health`
- Skill-Extractor (9004) - `http://localhost:9004/health`
- Voice-Extractor (9005) - `http://localhost:9005/health`

**A2A Protocol Discovery:**
- Validator: `http://localhost:9001/.well-known/agent-card`
- Karma-Hello: `http://localhost:9002/.well-known/agent-card`
- Abracadabra: `http://localhost:9003/.well-known/agent-card`
- Skill-Extractor: `http://localhost:9004/.well-known/agent-card`
- Voice-Extractor: `http://localhost:9005/.well-known/agent-card`

**Facilitator Endpoints:**
- Health: `http://localhost:9000/health`
- Supported methods: `http://localhost:9000/supported`

**View logs:** `docker-compose logs -f`
**Stop:** `docker-compose down`

**Full Docker guide**: See [docs/guides/DOCKER_GUIDE.md](./docs/guides/DOCKER_GUIDE.md)

---

### Option 2: Production Deployment (AWS ECS Fargate)

**🌐 Deploy to AWS with Terraform** - Cost-optimized infrastructure using Fargate Spot

#### Complete Infrastructure

![ECS Fargate Infrastructure](./docs/images/architecture/terraform-ecs-fargate-complete-infrastructure.png)

*Complete AWS infrastructure: VPC with public/private subnets, Application Load Balancer, ECS Fargate cluster with 5 services, ECR repositories, Route53 DNS, CloudWatch monitoring, and Secrets Manager integration.*

#### Deployment Flow

![Deployment Flow](./docs/images/architecture/terraform-deployment-flow-build-to-ecs.png)

*End-to-end deployment process: Local Docker build → Push to ECR → Terraform apply → ECS pulls images → Tasks running*

#### ALB Routing Strategy

![ALB Routing](./docs/images/architecture/terraform-alb-routing-path-and-hostname.png)

*Application Load Balancer routing with both path-based (`/validator/health`) and hostname-based (`validator.karmacadabra.ultravioletadao.xyz`) rules directing traffic to the correct ECS service.*

#### Cost Optimization with Fargate Spot

![Cost Optimization](./docs/images/architecture/terraform-fargate-spot-cost-optimization.png)

*Monthly cost breakdown (~$81-96/month) using Fargate Spot (70% savings), with capacity providers, auto-scaling policies, and optimization strategies.*

#### Secrets Management

![Secrets Management](./docs/images/architecture/terraform-secrets-management-ecs.png)

*Secure secret handling: ECS tasks fetch private keys and API keys from AWS Secrets Manager at runtime using IAM execution roles - no secrets in containers or environment variables.*

#### Quick Deploy Commands

```bash
# 1. Build and push Docker images to ECR
cd terraform/ecs-fargate
./build-and-push.ps1  # or .sh on Linux/Mac

# 2. Deploy infrastructure with Terraform
terraform init
terraform plan
terraform apply -auto-approve

# 3. Monitor deployment
./deploy-and-monitor.ps1  # or .sh on Linux/Mac

# 4. Force fresh image pull (when updating containers)
./force-image-pull.ps1
```

**Cost**: ~$81-96/month (Fargate Spot + ALB + NAT Gateway)
**Services**: 6 services (facilitator, validator, karma-hello, abracadabra, skill-extractor, voice-extractor)
**Scaling**: Auto-scales 1-3 tasks per service based on CPU/memory

**Full deployment guide**: See [terraform/ecs-fargate/DEPLOYMENT_GUIDE.md](./terraform/ecs-fargate/DEPLOYMENT_GUIDE.md)

#### Production Endpoints (AWS ECS Fargate)

**ALB URL**: `karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com`

| Service | Path-Based (ALB) | Hostname-Based (Custom Domain) | Port | Type |
|---------|------------------|--------------------------------|------|------|
| **Facilitator** | `http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/health` | `https://facilitator.ultravioletadao.xyz/health` | 9000 | Payment |
| **Validator** | `http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/validator/health` | `http://validator.karmacadabra.ultravioletadao.xyz/health` | 9001 | Agent |
| **Karma-Hello** | `http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/karma-hello/health` | `http://karma-hello.karmacadabra.ultravioletadao.xyz/health` | 9002 | Agent |
| **Abracadabra** | `http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/abracadabra/health` | `http://abracadabra.karmacadabra.ultravioletadao.xyz/health` | 9003 | Agent |
| **Skill-Extractor** | `http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/skill-extractor/health` | `http://skill-extractor.karmacadabra.ultravioletadao.xyz/health` | 9004 | Agent |
| **Voice-Extractor** | `http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/voice-extractor/health` | `http://voice-extractor.karmacadabra.ultravioletadao.xyz/health` | 9005 | Agent |

**A2A Protocol Endpoints** (Agent Discovery):
- Validator: `http://validator.karmacadabra.ultravioletadao.xyz/.well-known/agent-card`
- Karma-Hello: `http://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card`
- Abracadabra: `http://abracadabra.karmacadabra.ultravioletadao.xyz/.well-known/agent-card`
- Skill-Extractor: `http://skill-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card`
- Voice-Extractor: `http://voice-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card`

**Note**: Custom domain endpoints require DNS propagation (Route53 records pending configuration)

---

### Option 3: Manual Setup

```bash
# 1. Clone repository
git clone https://github.com/ultravioletadao/karmacadabra.git
cd karmacadabra

# 2. Get testnet AVAX
# Visit: https://faucet.avax.network/

# 3. Configure environment
cd validator
cp .env.example .env
# Add your keys:
# - PRIVATE_KEY (for your test wallet)
# - OPENAI_API_KEY (for CrewAI)
# - Contract addresses are already set!

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run validator agent
python main.py
```

**Deployed Contracts**: All ERC-8004 registries are live on Fuji!
**Full guide**: See [docs/guides/QUICKSTART.md](./docs/guides/QUICKSTART.md)

---

## 🔧 Requirements

- **Python** 3.11+
- **Rust** latest stable
- **Foundry** (forge, anvil, cast)
- **Node.js** 18+ (optional, for frontend)
- **AVAX** on Fuji testnet (free from faucet)
- **OpenAI API key** (for CrewAI agents)
- **AWS Account** (for production deployment)
- **Docker** (for containerized deployment)

---

## 🧰 Developer Toolbox

Utility scripts for managing wallets, tokens, and agent deployments:

### Wallet Generator
Generate new EVM-compatible wallets for agents:

```bash
# Generate wallet and auto-save to .env
python scripts/generate-wallet.py client-agent --auto-save

# Generate for multiple agents
python scripts/generate-wallet.py client-agent-2 --auto-save
python scripts/generate-wallet.py validator-2 --auto-save

# Interactive mode (prompts before saving)
python scripts/generate-wallet.py my-agent
```

**Features**:
- Creates Ethereum-compatible wallets (works on all EVM chains)
- Auto-saves private key and address to agent `.env` file
- Shows security warnings and best practices
- Displays Fuji testnet info and next steps
- Reusable for unlimited agents

### Token Distributor
Distribute tokens (GLUE/UVD/etc.) to agent wallets:

```bash
cd erc-20
python distribute-token.py
```

**Features**:
- Automatically loads wallet addresses from agent `.env` files
- Configurable amounts (currently 55,000 GLUE for all agents)
- Supports any ERC-20 token (configure via UVD_TOKEN_ADDRESS in .env)
- Shows before/after balances
- Transaction links on Snowtrace
- Supports: validator, karma-hello-agent, abracadabra-agent, client-agent

**Agents**:
| Agent | Funded | Balance |
|-------|--------|---------|
| Validator | ✅ | 55,000 GLUE |
| Karma-Hello | ✅ | 55,000 GLUE |
| Abracadabra | ✅ | 55,000 GLUE |
| Client-Agent | ✅ | 55,000 GLUE |

### System Rotation (Security)
Complete infrastructure rotation for key compromise scenarios:

```bash
# Dry run (shows what would happen, makes no changes)
python scripts/rotate-system.py

# Execute actual rotation (requires confirmation)
python scripts/rotate-system.py --confirm

# Refill wallets with GLUE only (no rotation)
python scripts/rotate-system.py --refill

# Refill wallets with GLUE (execute)
python scripts/rotate-system.py --refill --confirm

# Rotate ERC-20 deployer wallet only (separate from agent rotation)
python scripts/rotate-system.py --rotate-erc20 --confirm
```

**What it does**:
1. 🔑 Generates new wallets for ALL agents (validator, karma-hello, abracadabra, client, voice-extractor, skill-extractor)
2. ☁️ Updates AWS Secrets Manager with new private keys
3. 📜 Redeploys ERC-20 GLUE token contract
4. 🏛️ Redeploys ERC-8004 registries (Identity, Reputation, Validation)
5. 📝 Updates all agent `.env` files with new contract addresses
6. 💰 Funds all wallets with testnet AVAX (manual step)
7. 🎁 Distributes GLUE tokens to all agents
8. 📄 Updates MASTER_PLAN.md with new contract & wallet addresses

**Use cases**:
- 🚨 **Key compromise**: Rotate immediately if private keys are exposed
- 🔄 **Clean reset**: Start fresh with new infrastructure
- 🧪 **Testing**: Validate deployment automation
- 🎥 **Post-stream**: Rotate keys after public demonstrations
- 💰 **Wallet refill**: Top up agent wallets with GLUE tokens (use `--refill` flag)

**Safety**:
- ⚠️ Requires `--confirm` flag to execute (defaults to dry-run)
- ⚠️ Requires typing 'ROTATE' to confirm destructive changes
- ⚠️ Invalidates ALL existing wallets and contracts
- ✅ Safe dry-run mode shows exactly what would happen

**Gas Funding**:
- 💰 **Need AVAX for gas?** Use ERC-20 deployer wallet (stored in AWS Secrets Manager)
- 🔑 Access via: `distribute-token.py` (automatically uses AWS Secrets Manager)
- ⚠️ **ERC-20 deployer is NOT rotated by default** (owns GLUE token contract)
- 🔄 Rotate separately: `python scripts/rotate-system.py --rotate-erc20 --confirm`

### User Agent Marketplace Rebuild
Idempotent pipeline to rebuild the entire 48-agent marketplace from chat logs:

```bash
# Full rebuild with all users (weekly update after new streams)
python scripts/rebuild_user_agent_marketplace.py --force

# Add 20 more users (expand from 48 to 68)
python scripts/rebuild_user_agent_marketplace.py --users 68 --force

# Just regenerate agent cards (after profile updates)
python scripts/rebuild_user_agent_marketplace.py --skip-extract --force

# Preview changes without executing
python scripts/rebuild_user_agent_marketplace.py --dry-run

# Process specific number of users
python scripts/rebuild_user_agent_marketplace.py --users 30
```

**What it does**:
1. 👤 **Profile Extraction** - Analyzes chat logs, extracts skills/interests/tools
2. 🃏 **Agent Card Generation** - Converts profiles to A2A protocol cards with dynamic pricing
3. 🚀 **Agent Deployment** - Creates 48 FastAPI agents with unique ports (9000-9047)

**Features**:
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Incremental** - Add more users without rebuilding everything
- ✅ **Safe** - Backs up existing data on `--force`
- ✅ **Preserves wallets** - Restores .env files with PRIVATE_KEY after rebuild
- ✅ **Flexible** - Skip individual steps with `--skip-*` flags

### Balance Monitoring
Monitor all wallet balances across multiple chains in a unified matrix view:

```bash
# Check all chains (testnets + mainnets)
python3 scripts/check_all_balances.py

# Check only testnets (Fuji, Base Sepolia, Celo Sepolia)
python3 scripts/check_all_balances.py --chain testnets

# Check only mainnets (Avalanche, Base, Celo)
python3 scripts/check_all_balances.py --chain mainnets

# Filter by wallet type
python3 scripts/check_all_balances.py --wallet-type system        # System agents
python3 scripts/check_all_balances.py --wallet-type facilitators  # Facilitators
python3 scripts/check_all_balances.py --wallet-type deployers     # Deployers
python3 scripts/check_all_balances.py --wallet-type user          # User agents

# Show wallets with 0 balance
python3 scripts/check_all_balances.py --show-empty

# Combined filtering
python3 scripts/check_all_balances.py --chain testnets --wallet-type system
```

**What it monitors**:
- 📊 **57 wallets** across all categories
- 🌐 **6 chains** - Fuji, Base Sepolia, Celo Sepolia (testnets) + Avalanche, Base, Celo (mainnets)
- 💎 **Native tokens** - AVAX, ETH, CELO
- 🪙 **ERC-20 tokens** - GLUE, USDC, cUSD

**Features**:
- ✅ **Matrix display** - Wallets as rows, chains as columns
- ✅ **Color-coded** - Red (empty), Yellow (low <0.05), Green (sufficient)
- ✅ **Auto-derives addresses** - From AWS Secrets Manager private keys
- ✅ **Flexible filtering** - By chain group and wallet type
- ✅ **Multi-network** - Testnets and mainnets in one view

**Wallet categories**:
| Category | Count | Examples |
|----------|-------|----------|
| System Agents | 7 | validator, karma-hello, abracadabra, skill-extractor, voice-extractor |
| Facilitators | 2 | facilitator-testnet, facilitator-mainnet |
| Deployers | 1 | erc-20 |
| User Agents | 48 | Community member wallets |

📚 **Full documentation**: [scripts/README_check_all_balances.md](./scripts/README_check_all_balances.md)

---

## 🤝 Contributing

1. Read [MASTER_PLAN.md](./MASTER_PLAN.md) to understand the vision
2. Check the roadmap for available tasks
3. Implement following the architecture in [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
4. Write tests for all new code
5. Submit PR with documentation

---

## 📖 Learn More

- **ERC-8004 Base Spec**: https://eips.ethereum.org/EIPS/eip-8004 (we extend this with bidirectional ratings!)
- **A2A Protocol**: https://ai.pydantic.dev/a2a/
- **x402 Protocol**: https://www.x402.org
- **EIP-3009**: https://eips.ethereum.org/EIPS/eip-3009
- **CrewAI**: https://docs.crewai.com/
- **Avalanche Docs**: https://docs.avax.network/ (our home chain!)

### Trustless Agents Course
https://intensivecolearn.ing/en/programs/trustless-agents

---

## ⚠️ Disclaimer

**TESTNET ONLY**: This project is currently deployed on Avalanche Fuji testnet. Do not use with real funds. Smart contracts have not been audited.

For mainnet deployment:
- [ ] Smart contract audit by reputable firm
- [ ] Bug bounty program
- [ ] Timelock for admin functions
- [ ] Multi-sig for contract ownership

---

## 📄 License

MIT License - See [LICENSE](./LICENSE)

---

## 🌟 Acknowledgments

- **[Trustless Agents Course](https://intensivecolearn.ing/en/programs/trustless-agents)** by Intensive CoLearning
- **ERC-8004 Base Specification** (which we extended for bidirectional reputation)
- **x402-rs** protocol implementation
- **Pydantic AI** A2A protocol
- **Avalanche** - our home blockchain and the foundation of Ultravioleta DAO

---

## 💬 Contact

- **Project**: Ultravioleta DAO
- **Repo**: https://github.com/ultravioletadao/karmacadabra
- **Docs**: Start with [docs/guides/QUICKSTART.md](./docs/guides/QUICKSTART.md)

---

**Built with ❤️ by Ultravioleta DAO**

*Empowering autonomous AI agents to create a trustless data economy*
