# 🎯 Karmacadabra: Trustless Agent Economy

> AI agents that autonomously buy/sell data using blockchain-based gasless micropayments

**[🇪🇸 Versión en Español](./README.es.md)** | **🇺🇸 English Version**

> **⚡ Important:** This implements an **ERC-8004 EXTENDED version** with bidirectional reputation (NOT the base spec!) deployed on **Avalanche** - the home of **Ultravioleta DAO**. Both buyers and sellers rate each other after transactions.

[![Avalanche](https://img.shields.io/badge/Avalanche-Fuji-E84142?logo=avalanche)](https://testnet.snowtrace.io/)
[![ERC-8004](https://img.shields.io/badge/ERC--8004%20Extended-Bidirectional%20Rating-blue)](https://eips.ethereum.org/EIPS/eip-8004)
[![x402](https://img.shields.io/badge/x402-Payment%20Protocol-green)](https://www.x402.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-Latest-orange?logo=rust)](https://www.rust-lang.org/)
[![Deployed](https://img.shields.io/badge/Deployed-Fuji%20Testnet-success)](https://testnet.snowtrace.io/)

---

## 🚀 **LIVE ON FUJI TESTNET** - Deployed October 22, 2025

| Contract | Address | Status |
|----------|---------|--------|
| **GLUE Token (EIP-3009)** | [`0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743`](https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743) | ✅ Verified |
| **Identity Registry** | [`0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618`](https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618) | ✅ Verified |
| **Reputation Registry** | [`0x932d32194C7A47c0fe246C1d61caF244A4804C6a`](https://testnet.snowtrace.io/address/0x932d32194C7A47c0fe246C1d61caF244A4804C6a) | ✅ Verified |
| **Validation Registry** | [`0x9aF4590035C109859B4163fd8f2224b820d11bc2`](https://testnet.snowtrace.io/address/0x9aF4590035C109859B4163fd8f2224b820d11bc2) | ✅ Verified |
| **Transaction Logger** | [`0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654`](https://testnet.snowtrace.io/address/0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654) | ✅ Verified |

**Network**: Avalanche Fuji Testnet (Chain ID: 43113)
**Registration Fee**: 0.005 AVAX
**Token Supply**: 24,157,817 GLUE (6 decimals)

### Agent Wallets (Funded with 55,000 GLUE each)

| Agent | Wallet Address | GLUE Balance |
|-------|----------------|--------------|
| **Validator** | [`0x1219eF9484BF7E40E6479141B32634623d37d507`](https://testnet.snowtrace.io/address/0x1219eF9484BF7E40E6479141B32634623d37d507) | 55,000 GLUE |
| **Karma-Hello** | [`0x2C3e071df446B25B821F59425152838ae4931E75`](https://testnet.snowtrace.io/address/0x2C3e071df446B25B821F59425152838ae4931E75) | 55,000 GLUE |
| **Abracadabra** | [`0x940DDDf6fB28E611b132FbBedbc4854CC7C22648`](https://testnet.snowtrace.io/address/0x940DDDf6fB28E611b132FbBedbc4854CC7C22648) | 55,000 GLUE |
| **Client Agent** | [`0xCf30021812F27132d36dc791E0eC17f34B4eE8BA`](https://testnet.snowtrace.io/address/0xCf30021812F27132d36dc791E0eC17f34B4eE8BA) | 55,000 GLUE |

**View All Contracts**: [Snowtrace Explorer](https://testnet.snowtrace.io/)

---

### ✅ Sprint 1: Foundation Complete (October 2025)

**Python Shared Utilities** (`shared/`) - **3,100+ lines** of production-ready code:

1. **`base_agent.py`** (600+ lines) - ERC-8004 integration, reputation, Web3.py, AWS Secrets
2. **`payment_signer.py`** (470+ lines) - EIP-712 signing, EIP-3009 signatures
3. **`x402_client.py`** (530+ lines) - x402 HTTP payment protocol client
4. **`a2a_protocol.py`** (650+ lines) - Agent discovery, AgentCard, Skills
5. **`validation_crew.py`** (550+ lines) - CrewAI validation pattern
6. **`tests/`** (1,200+ lines) - **26 passing unit tests** + integration framework

**Status**: Foundation complete, ready for agent development (Sprint 2)

**API Documentation**: [`shared/README.md`](./shared/README.md) | **Testing Guide**: [`shared/tests/README.md`](./shared/tests/README.md)


---

### ✅ Sprint 1: Foundation Complete (October 2025)

**Python Shared Utilities** (`shared/`) - **3,100+ lines** of production-ready code:

1. **`base_agent.py`** (600+ lines) - ERC-8004 integration, reputation, Web3.py, AWS Secrets
2. **`payment_signer.py`** (470+ lines) - EIP-712 signing, EIP-3009 signatures
3. **`x402_client.py`** (530+ lines) - x402 HTTP payment protocol client
4. **`a2a_protocol.py`** (650+ lines) - Agent discovery, AgentCard, Skills
5. **`validation_crew.py`** (550+ lines) - CrewAI validation pattern
6. **`tests/`** (1,200+ lines) - **26 passing unit tests** + integration framework

**Status**: Foundation complete, ready for agent development (Sprint 2)

**API Documentation**: [`shared/README.md`](./shared/README.md) | **Testing Guide**: [`shared/tests/README.md`](./shared/tests/README.md)


---

## 🎯 What is Karmacadabra?

**Karmacadabra** is an ecosystem of autonomous AI agents that **buy and sell data** without human intervention using:

- **ERC-8004 Extended** - **NOT the base implementation!** This is a custom extension enabling **bidirectional reputation** (both buyers and sellers rate each other)
- **A2A protocol** (Pydantic AI) for agent-to-agent communication
- **x402 + EIP-3009** for HTTP micropayments (gasless!)
- **CrewAI** for multi-agent orchestration

### 🏔️ Deployed on Avalanche - Our Home

**Karmacadabra lives on Avalanche**, the native blockchain home of **Ultravioleta DAO**. We chose Avalanche for:

- **Fast finality**: 2-second block times for instant agent transactions
- **Low costs**: Minimal gas fees make micropayments economically viable
- **EVM compatibility**: Full Solidity support with Ethereum tooling
- **DAO alignment**: Avalanche is where Ultravioleta DAO was born and thrives

Currently on **Fuji testnet**, with mainnet deployment planned after audits.

### The Problem We Solve

**Karma-Hello** has rich Twitch chat logs but no audio context.
**Abracadabra** has stream transcriptions but no chat data.

**Solution**: Agents autonomously negotiate and purchase complementary data, building a complete streaming context. All transactions are verified, on-chain, and gasless.

---

## 🚀 Quick Start (30 minutes)

**✨ Contracts already deployed!** You can start building agents immediately.

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
**Full guide**: See [QUICKSTART.md](./QUICKSTART.md)

---

## 🔐 AWS Secrets Manager (Security)

All agent private keys are stored centrally in **AWS Secrets Manager** for security. The agents automatically fetch keys from AWS when `.env` files are empty, or use local keys if filled (for testing).

### Quick Setup

```bash
# 1. Configure AWS CLI (one-time)
aws configure
# Enter your AWS Access Key ID, Secret Access Key, region (us-east-1)

# 2. Store all keys in AWS Secrets Manager
python scripts/setup-secrets.py
# Creates secret 'karmacadabra' with all agent private keys

# 3. (Optional) Clear local .env files
python scripts/clear-env-keys.py
# Empties PRIVATE_KEY in all .env files

# 4. Test retrieval
python -m shared.secrets_manager validator-agent
# [AWS Secrets] Retrieved key for 'validator-agent' from AWS
```

**How it works:**
- If `PRIVATE_KEY` in `.env` is **filled** → uses local key (development)
- If `PRIVATE_KEY` in `.env` is **empty** → fetches from AWS (production)

**Full guide**: See [shared/AWS_SECRETS_SETUP.md](./shared/AWS_SECRETS_SETUP.md)

---

## 🏗️ Architecture

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

**Full catalog**: [MONETIZATION_OPPORTUNITIES.md](./MONETIZATION_OPPORTUNITIES.md)

---

## 📂 Repository Structure

```
karmacadabra/
├── erc-20/                    # GLUE Token (EIP-3009)
├── erc-8004/                  # ERC-8004 Extended - Bidirectional reputation registries
├── x402-rs/                   # Payment facilitator (Rust)
├── validator/                 # Validator agent (Python + CrewAI)
├── karma-hello-agent/         # Chat log seller/buyer agents
├── abracadabra-agent/         # Transcript seller/buyer agents
├── client-agent/              # Generic buyer agent
├── voice-extractor-agent/     # Linguistic analysis agent
├── skill-extractor-agent/     # Skill profiling agent
├── shared/                    # Shared utilities (AWS Secrets Manager, etc.)
├── scripts/                   # Setup and deployment scripts
├── MASTER_PLAN.md            # Complete vision & roadmap
├── ARCHITECTURE.md           # Technical architecture
├── MONETIZATION_OPPORTUNITIES.md
├── QUICKSTART.md             # 30-min setup guide
├── CLAUDE.md                 # Claude Code guidance
└── INDEX.md                  # Documentation index
```

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

---

## 🎯 Key Features

✅ **Gasless Micropayments**: Agents don't need ETH/AVAX for gas
✅ **Bidirectional Reputation**: Custom ERC-8004 extension - buyers AND sellers rate each other (not in base spec!)
✅ **Native to Avalanche**: Deployed on our home chain for optimal performance
✅ **Trustless Validation**: Independent validators verify data quality
✅ **Agent Discovery**: A2A protocol AgentCards at `/.well-known/agent-card`
✅ **Multi-Agent Workflows**: CrewAI crews for complex tasks
✅ **50+ Monetizable Services**: From $0.01 to $200 GLUE per service

---

## 📚 Documentation

| Document | Description | Time |
|----------|-------------|------|
| [QUICKSTART.md](./QUICKSTART.md) | Get running in 30 minutes | 30 min |
| [MASTER_PLAN.md](./MASTER_PLAN.md) | Complete vision & roadmap | 60 min |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Technical deep dive | 45 min |
| [MONETIZATION_OPPORTUNITIES.md](./MONETIZATION_OPPORTUNITIES.md) | All services & pricing | 30 min |
| [CLAUDE.md](./CLAUDE.md) | Developer guidance | 15 min |
| [INDEX.md](./INDEX.md) | Documentation index | 5 min |

**Component READMEs**: Each folder has detailed setup instructions.

---

## 🧪 Development Status

| Phase | Component | Status |
|-------|-----------|--------|
| **Phase 1** | ERC-8004 Extended Registries | ✅ **DEPLOYED & VERIFIED** |
| **Phase 1** | GLUE Token | ✅ **DEPLOYED & VERIFIED** |
| **Phase 1** | TransactionLogger | ✅ **DEPLOYED & VERIFIED** |
| **Phase 1** | Token Distribution | ✅ **COMPLETE** (55,000 GLUE to each agent) |
| **Phase 1** | x402 Facilitator | ⏸️ Ready (requires Rust nightly - using external facilitator) |
| **Phase 2** | Validator Agent | 🔄 **IN PROGRESS** |
| **Phase 3** | Karma-Hello Agents | 🔴 To implement |
| **Phase 4** | Abracadabra Agents | 🔴 To implement |
| **Phase 5** | End-to-end Testing | 🔴 Pending |

**Current Phase**: Phase 2 - Implementing Python agents
**Last Updated**: October 22, 2025

---

## 🧰 Developer Toolbox

Utility scripts for managing wallets, tokens, and agent deployments:

### Wallet Generator
Generate new EVM-compatible wallets for agents:

```bash
# Generate wallet and auto-save to .env
python generate-wallet.py client-agent --auto-save

# Generate for multiple agents
python generate-wallet.py client-agent-2 --auto-save
python generate-wallet.py validator-2 --auto-save

# Interactive mode (prompts before saving)
python generate-wallet.py my-agent
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

---

## 🔧 Requirements

- **Python** 3.11+
- **Rust** latest stable
- **Foundry** (forge, anvil, cast)
- **Node.js** 18+ (optional, for frontend)
- **AVAX** on Fuji testnet (free from faucet)
- **OpenAI API key** (for CrewAI agents)

---

## 🚦 Getting Started

### 1. Prerequisites
```bash
# Install Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Python 3.11+
python --version  # Should be 3.11 or higher
```

### 2. Get Testnet AVAX
Visit https://faucet.avax.network/ and request AVAX for your wallet.

### 3. Deploy Infrastructure
```bash
cd erc-20
cp .env.example .env
# Edit .env with your PRIVATE_KEY
./deploy-fuji.sh

cd ../erc-8004
./deploy-fuji.sh

cd ../x402-rs
cargo build --release
cargo run
```

### 4. Run Demo
```bash
python demo.py
```

See [QUICKSTART.md](./QUICKSTART.md) for detailed instructions.

---

## 🤝 Contributing

1. Read [MASTER_PLAN.md](./MASTER_PLAN.md) to understand the vision
2. Check the roadmap for available tasks
3. Implement following the architecture in [ARCHITECTURE.md](./ARCHITECTURE.md)
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
- **Docs**: Start with [QUICKSTART.md](./QUICKSTART.md)

---

**Built with ❤️ by Ultravioleta DAO**

*Empowering autonomous AI agents to create a trustless data economy*
