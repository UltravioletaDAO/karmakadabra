# 🎯 MASTER PLAN: Trustless Agent Economy
## AI Agent Microeconomy with ERC-8004 + A2A + x402

> **Version:** 1.0.0 | **Updated:** October 2025 | **Status:** 🚀 Phase 1 Complete

---

## 📍 Deployed Contracts (Avalanche Fuji Testnet)

| Contract | Address | Status |
|----------|---------|--------|
| **GLUE Token (EIP-3009)** | `0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743` | ✅ [Verified](https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743) |
| **Identity Registry** | `0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618` | ✅ [Verified](https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618) |
| **Reputation Registry** | `0x932d32194C7A47c0fe246C1d61caF244A4804C6a` | ✅ [Verified](https://testnet.snowtrace.io/address/0x932d32194C7A47c0fe246C1d61caF244A4804C6a) |
| **Validation Registry** | `0x9aF4590035C109859B4163fd8f2224b820d11bc2` | ✅ [Verified](https://testnet.snowtrace.io/address/0x9aF4590035C109859B4163fd8f2224b820d11bc2) |
| **Transaction Logger** | `0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654` | ✅ [Verified](https://testnet.snowtrace.io/address/0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654) |

**Deployed:** October 22, 2025 | **Chain ID:** 43113 | **Registration Fee:** 0.005 AVAX

### Agent Wallets

| Agent | Address | GLUE Balance | Status |
|-------|---------|--------------|--------|
| **Validator** | `0x1219eF9484BF7E40E6479141B32634623d37d507` | 55,000 | ✅ Funded |
| **Karma-Hello** | `0x2C3e071df446B25B821F59425152838ae4931E75` | 55,000 | ✅ Funded |
| **Abracadabra** | `0x940DDDf6fB28E611b132FbBedbc4854CC7C22648` | 55,000 | ✅ Funded |
| **Client Agent** | `0xCf30021812F27132d36dc791E0eC17f34B4eE8BA` | 55,000 | ✅ Funded |

**Total Distributed:** 220,000 GLUE (4 agents) | **Owner Remaining:** 23,937,817 GLUE

---

## ⚠️ IMPLEMENTATION STATUS

**Last Updated:** October 23, 2025

### ✅ PHASE 1 COMPLETE: Blockchain Infrastructure

All contracts deployed and verified on Fuji. All agent wallets funded. Token distribution scripts functional.

### 🔴 PHASE 2 NOT STARTED: Agent Development

**CRITICAL:** Zero Python agent code exists. All agents documented but not implemented.

| Component | Status | Gap |
|-----------|--------|-----|
| ERC8004BaseAgent Class | ❌ NO CODE | Core foundation missing |
| x402 Payment Integration | ❌ NO CODE | No signing/verification |
| A2A Protocol | ❌ NO CODE | No AgentCard implementation |
| CrewAI Integration | ❌ NO CODE | No crews defined |
| All Agent Implementations | ❌ EMPTY | Only READMEs + data folders |

### 🔮 NEW VISION: User Agent Microeconomy

**Evolution:** From 4 system agents → 48+ user agents creating self-organizing microeconomy

**Key New Components (all need implementation):**
- Voice Extractor Agent (🔥 CRITICAL - bootstrap needed)
- Profile Extraction Pipeline (CrewAI crew)
- Agent Card Generator (auto-gen from profiles)
- User Agent Factory (mass deployment)
- 48 User Agents (one per chat participant)
- Bootstrap Marketplace (self-discovery flow)

**Network Math:** 48 agents × 47 connections = **2,256 potential trades** (quadratic growth)

---

## 📊 REVISED ROADMAP

### Sprint 1 (Weeks 1-2): Foundation - START HERE 🔴 BLOCKER

**Goal:** Build core infrastructure for all agents

| Task | Effort | Deliverable |
|------|--------|-------------|
| Create base_agent.py with ERC8004BaseAgent | 2-3 days | Working base class |
| Web3.py contract integration | 1 day | Read/write Fuji contracts |
| EIP-712 payment signing | 2 days | Sign payment authorizations |
| x402 HTTP client (Python) | 1-2 days | Send payments in headers |
| A2A AgentCard implementation | 2 days | Publish/discover agents |
| First CrewAI crew | 1 day | Pattern for other crews |
| Integration tests | 1 day | Foundation verified |

**Output:** `shared/base_agent.py`, `shared/eip712_signer.py`, `shared/x402_client.py`, `shared/a2a_protocol.py`

### Sprint 2 (Weeks 3-4): System Agents

**Order (sequential):**
1. Validator Agent (validates foundation)
2. Client Agent (reference buyer)
3. Data Source Integration (static demo files)
4. Karma-Hello Seller
5. Abracadabra Seller
6. Voice Extractor (enables user agents)

**Milestone 2.3: Client Agent** ✅ Wallet created and funded
- Address: `0xCf30021812F27132d36dc791E0eC17f34B4eE8BA`
- Balance: 55,000 GLUE
- Purpose: Generic buyer (no selling)

### Sprint 3 (Weeks 5-6): User Agent System

**Milestones:**
1. Profile extraction (48 users from Oct 21 stream)
2. Agent Card auto-generator
3. User agent template + factory
4. Mass deployment (48 agents)
5. Bootstrap marketplace test

### Sprint 4 (Weeks 7-8): Visualization

**Components:**
1. Contract interaction viewer (real-time Fuji events)
2. Agent network graph (D3.js)
3. Transaction flow tracer
4. Agent directory (search/filter)
5. Dashboard overview (metrics)

---

## 🏗️ Architecture

### Three-Layer System

**Layer 1: Blockchain (Avalanche Fuji)**
- GLUE Token: ERC-20 + EIP-3009 for gasless transfers
- ERC-8004 Registries: Identity, Reputation, Validation

**Layer 2: Payment Facilitator (Rust)**
- x402-rs: HTTP 402 payment protocol
- Verifies EIP-712 signatures, executes `transferWithAuthorization()`
- Stateless (no DB, all state on-chain)
- Public endpoint: `facilitator.ultravioletadao.xyz`

**Layer 3: AI Agents (Python + CrewAI)**
- Karma-Hello: Sells stream logs, buys transcripts
- Abracadabra: Sells transcripts, buys logs
- Validator: Independent validation service
- A2A protocol for discovery/communication

### Data Flow (Payment Transaction)

```
1. Buyer discovers Seller via A2A (/.well-known/agent-card)
2. Buyer signs EIP-712 payment off-chain
3. Buyer sends HTTP request with X-Payment header
4. Seller's x402 middleware extracts payment, calls facilitator /verify
5. (Optional) Seller requests validation from Validator
6. Validator analyzes quality (CrewAI), submits score on-chain (PAYS GAS)
7. Facilitator executes transferWithAuthorization() (gasless for agents)
8. Seller returns data
```

**Duration:** ~2-3 seconds end-to-end, gasless for buyer/seller

---

## 🧩 Components

### 1. GLUE Token (`erc-20/`)

**Status:** ✅ Deployed to Fuji

**Features:**
- ERC-20 standard + EIP-3009 (gasless transfers via `transferWithAuthorization()`)
- EIP-2612 Permit (gasless approvals)
- EIP-712 typed data hashing
- Nonce-based replay protection
- Time-window validation

**Deployment:**
```bash
cd erc-20
cp .env.example .env && nano .env  # Configure PRIVATE_KEY
./deploy-fuji.sh
```

**Parameters:**
- Initial Supply: 24,157,817 GLUE
- Decimals: 6 (matching USDC)
- Owner: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8

### 2. ERC-8004 Registries (`erc-8004/`)

**Status:** ✅ Deployed to Fuji

**Contracts:**
- `IdentityRegistry.sol` - Agent registration with domains
- `ReputationRegistry.sol` - Feedback and ratings
- `ValidationRegistry.sol` - Quality validation scores

**Deployment:**
```bash
cd erc-8004
./deploy-fuji.sh
```

**Usage:**
- Each agent registers with unique ID in IdentityRegistry
- Reputation builds per transaction in ReputationRegistry
- Validations recorded on-chain in ValidationRegistry
- **Only Validator pays gas** (~0.01 AVAX per validation)

### 3. x402 Facilitator (`x402-rs/`)

**Status:** ⏸️ External facilitator for now (needs Rust 2024 edition)

**Purpose:** HTTP 402 payment handler for Fuji

**Endpoints:**
- `POST /verify` - Verify EIP-712 signature
- `POST /settle` - Execute on-chain settlement
- `GET /supported` - List payment methods
- `GET /health` - Health check

**Deployment:**
```bash
cd x402-rs
./deploy-facilitator.sh init
cp .env.example .env && nano .env  # Configure
./deploy-facilitator.sh build
./deploy-facilitator.sh deploy
```

**Configuration:** See `x402-rs/.env.example` for complete setup

### 4. Karma-Hello Agent (`karma-hello-agent/`)

**Status:** 🔴 Not implemented (only README + data)

**Purpose:** Sells Twitch stream chat logs (0.01-1.00 GLUE/service)

**Data Source:** MongoDB at `z:\ultravioleta\ai\cursor\karma-hello`

**Services (see MONETIZATION_OPPORTUNITIES.md):**
- Tier 1 (0.01-0.05 GLUE): Chat logs, user activity, token economics
- Tier 2 (0.05-0.15 GLUE): ML predictions, sentiment analysis
- Tier 3-6: Advanced analytics, custom models (up to 200 GLUE)

**Implementation Pattern:**
```python
class KarmaHelloSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self):
        self.register_agent(domain="karma-hello-seller.ultravioletadao.xyz")
        self.db = MongoClient(...)["karma_hello"]

    @x402_required(price=GLUE.amount("0.01"))
    async def get_logs_handler(self, request):
        crew = Crew(agents=[formatter, validator])
        return crew.kickoff(inputs={"data": raw_logs})
```

### 5. Abracadabra Agent (`abracadabra-agent/`)

**Status:** 🔴 Not implemented (only README + data)

**Purpose:** Sells stream transcriptions + AI analysis (0.02-3.00 GLUE/service)

**Data Source:** SQLite (`analytics.db`) + Cognee knowledge graph at `z:\ultravioleta\ai\cursor\abracadabra`

**Services (see MONETIZATION_OPPORTUNITIES.md):**
- Tier 1 (0.02-0.08 GLUE): Raw/enhanced transcripts, multi-language
- Tier 2 (0.10-0.25 GLUE): Clip generation, blog posts, social media
- Tier 3-6: Video editing, image generation, custom AI (up to 100 GLUE)

**Implementation Pattern:**
```python
class AbracadabraSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self):
        self.register_agent(domain="abracadabra-seller.ultravioletadao.xyz")
        self.db = sqlite3.connect("analytics.db")
        self.cognee = CogneeClient()

    @x402_required(price=GLUE.amount("0.02"))
    async def get_transcript_handler(self, request):
        crew = Crew(agents=[enricher, analyzer])
        return crew.kickoff(inputs={"transcript": data})
```

### 6. Validator Agent (`validator/`)

**Status:** 🔴 Not implemented (only README)

**Purpose:** Independent quality validation (0.001 GLUE/validation)

**Role:** Validates data quality before each transaction

**Implementation:**
```python
class ValidatorAgent(ERC8004BaseAgent):
    def __init__(self):
        self.register_agent(domain="validator.ultravioletadao.xyz")
        self.validator_crew = Crew(
            agents=[quality_analyst, price_reviewer, fraud_detector]
        )

    async def validate_transaction(self, data_hash, seller_id, buyer_id):
        data = await self.load_data(data_hash)
        report = self.validator_crew.kickoff(inputs={"data": data})
        score = self.extract_score(report)

        # PAY GAS (~0.01 AVAX) to submit on-chain
        tx = await self.submit_validation_response(data_hash, score)
        return ValidationResult(score=score, tx_hash=tx)
```

**Validation Criteria:**
- Logs: Valid timestamps, existing user IDs, no duplicates, valid JSON
- Transcripts: Audio exists, coherent text, timestamps match duration, relevant topics

**Economics:** Fee of 0.001 GLUE may not cover gas costs (0.01 AVAX). Consider:
- Increase fee to 0.01+ GLUE
- Batch validations (multiple items per tx)
- Layer 2 deployment for lower gas

---

## 🔄 Transaction Flow Example

### Karma-Hello buys Transcript from Abracadabra

```
1. KarmaHello Buyer detects need for transcript (stream_id=12345)
2. A2A Discovery → GET /.well-known/agent-card from Abracadabra
3. Sign EIP-712: from=KH, to=Abra, value=0.02 GLUE, nonce=random
4. HTTP POST /api/transcripts with X-Payment header
5. Abracadabra x402 middleware extracts X-Payment
6. POST facilitator/verify → Verify EIP-712 signature
7. (Optional) validationRequest() on-chain (buyer pays 0.001 GLUE)
8. Validator downloads transcript, CrewAI validates quality
9. Validator PAYS GAS (0.01 AVAX) to submit validationResponse(score=95)
10. Facilitator POST /settle → Execute transferWithAuthorization()
11. GLUE Token: KH -0.02 GLUE, Abra +0.02 GLUE
12. Abracadabra queries DB + Cognee, formats with CrewAI
13. Response 200 OK with JSON transcript
14. KarmaHello integrates transcript with MongoDB logs
```

**Costs:**
- Buyer: -0.021 GLUE total (-0.02 seller, -0.001 validator), 0 gas
- Seller: +0.02 GLUE, 0 gas
- Validator: +0.001 GLUE, -0.01 AVAX gas (not sustainable at testnet prices)
- Facilitator: 0 GLUE, 0 gas (stateless verification)

---

## 🔧 Technologies & Protocols

### ERC-8004: Trust Frameworks

**Spec:** https://eips.ethereum.org/EIPS/eip-8004

**Key Functions:**
- `IdentityRegistry.newAgent(domain, address)` → agentId
- `ReputationRegistry.rateClient(agent, rating)`
- `ValidationRegistry.validationResponse(dataHash, score)` ← **PAYS GAS**

### A2A Protocol: Agent Discovery

**Spec:** https://ai.pydantic.dev/a2a/

**AgentCard Example:**
```json
{
  "agentId": 1,
  "name": "Karma-Hello Seller",
  "skills": [{
    "skillId": "get_logs",
    "price": {"amount": "0.01", "currency": "GLUE"},
    "inputSchema": {...},
    "outputSchema": {...}
  }],
  "trustModels": ["erc-8004"],
  "paymentMethods": ["x402-eip3009"]
}
```

Published at: `https://karma-hello-seller.ultravioletadao.xyz/.well-known/agent-card`

### x402 Protocol: HTTP Micropayments

**Spec:** https://www.x402.org

**Flow:**
1. Server returns `402 Payment Required` with payment details
2. Client signs EIP-712 authorization off-chain
3. Client sends request with `X-Payment` header
4. Server calls facilitator `/verify` and `/settle`
5. Server returns resource

**Advantages:** Standard HTTP, stateless, gasless, atomic

### EIP-3009: Gasless Transfers

**Spec:** https://eips.ethereum.org/EIPS/eip-3009

**Core Function:**
```solidity
function transferWithAuthorization(
    address from, address to, uint256 value,
    uint256 validAfter, uint256 validBefore, bytes32 nonce,
    uint8 v, bytes32 r, bytes32 s
) external;
```

**How it works:**
1. User signs EIP-712 message off-chain (no gas)
2. Relayer (facilitator) submits signature on-chain (pays gas)
3. Contract verifies signature and executes transfer
4. User's tokens move without user paying gas

**Why critical for agents:** AI agents can't hold ETH/AVAX for gas. EIP-3009 enables operation without gas funds.

### CrewAI: Multi-Agent Orchestration

**Validator Crew Example:**
```python
validator_crew = Crew(
    agents=[
        Agent(role="Quality Analyst", tools=[check_schema, verify_timestamps]),
        Agent(role="Fraud Detector", tools=[similarity_check, blockchain_verify]),
        Agent(role="Price Reviewer", tools=[market_check, historical_prices])
    ],
    tasks=[quality_task, fraud_task, price_task]
)
```

---

## 📚 Development Guide

### Setup Environment

**Requirements:** Python 3.11+, Rust 1.75+, Foundry, Node.js 18+

```bash
# 1. Clone and setup
git clone https://github.com/ultravioletdao/karmacadabra.git
cd karmacadabra

# 2. Install Foundry
curl -L https://foundry.paradigm.xyz | bash && foundryup

# 3. Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 4. Setup Python agents
cd validator && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cd ../karma-hello-agent && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cd ../abracadabra-agent && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# 5. Build facilitator
cd ../x402-rs && cargo build --release
```

### Configure AWS Secrets Manager (Recommended)

All agent private keys can be stored centrally in AWS Secrets Manager for security. Agents will automatically fetch keys from AWS when `.env` files are empty.

**Setup (one-time):**
```bash
# 1. Configure AWS CLI
aws configure
# Enter AWS Access Key ID, Secret Access Key, region: us-east-1

# 2. Store all private keys in AWS
python scripts/setup-secrets.py
# Creates secret 'karmacadabra' with all agent keys

# 3. (Optional) Clear local .env files
python scripts/clear-env-keys.py

# 4. Test retrieval
python -m shared.secrets_manager validator-agent
# [AWS Secrets] Retrieved key for 'validator-agent' from AWS
```

**How it works:**
- If `PRIVATE_KEY` in `.env` is filled → uses local key (development)
- If `PRIVATE_KEY` in `.env` is empty → fetches from AWS (production)

**Full documentation**: [shared/AWS_SECRETS_SETUP.md](./shared/AWS_SECRETS_SETUP.md)

### Deploy Contracts

**Step 1: Deploy GLUE Token**
```bash
cd erc-20
cp .env.example .env && nano .env  # Set PRIVATE_KEY
forge build && ./deploy-fuji.sh
# Output: GLUE Token deployed at 0x...
```

**Step 2: Deploy ERC-8004 Registries**
```bash
cd ../erc-8004
cp .env.fuji.example .env.fuji && source .env.fuji
cd contracts && forge build && cd ..
./deploy-fuji.sh
# Output: IdentityRegistry, ReputationRegistry, ValidationRegistry addresses
```

**Step 3: Setup Facilitator**
```bash
cd ../x402-rs
cp .env.example .env && nano .env  # Configure RPC_URL, PRIVATE_KEY, GLUE_TOKEN_ADDRESS
cargo run  # Test locally
docker build -t x402-facilitator . && docker run -d --env-file .env -p 8080:8080 x402-facilitator
```

**Step 4: Deploy Agents**
```bash
# Configure each agent
cd ../validator && cp .env.example .env && nano .env
cd ../karma-hello-agent && cp .env.example .env && nano .env
cd ../abracadabra-agent && cp .env.example .env && nano .env

# Register and run (once implemented)
python main.py --mode validator
python main.py --mode seller --port 8081
python main.py --mode buyer
```

### Testing End-to-End

```bash
# Demo script (once implemented)
python demo.py

# Expected output:
# ✅ All contracts deployed
# ✅ All agents registered
# ✅ KarmaHello bought transcript: 0.02 GLUE, score 95/100
# ✅ Abracadabra bought logs: 0.01 GLUE, score 98/100
# ✅ All transactions verified on-chain
# 🎉 Demo complete
```

### Local Testing with Anvil

```bash
# Terminal 1: Run Anvil
anvil --chain-id 43113 --port 8545

# Terminal 2: Deploy contracts
cd erc-20 && forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
cd ../erc-8004 && forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast

# Terminal 3: Run facilitator
cd ../x402-rs && RPC_URL_FUJI=http://localhost:8545 cargo run

# Terminals 4-6: Run agents
python main.py  # validator, karma-hello, abracadabra

# Terminal 7: Run demo
python demo.py --network local
```

---

## 💰 Monetization

**Full catalog:** See `MONETIZATION_OPPORTUNITIES.md` for 50+ services

### Service Tiers

**Karma-Hello (6 Tiers):**
- Tier 1 (0.01-0.05 GLUE): Chat logs, user activity, token economics
- Tier 2 (0.05-0.15 GLUE): ML predictions, user segmentation, sentiment
- Tier 3 (0.15-0.30 GLUE): Fraud detection, economic health, gamification
- Tier 4-6 (0.30-200 GLUE): A/B testing, custom models, enterprise

**Abracadabra (6 Tiers):**
- Tier 1 (0.02-0.08 GLUE): Raw/enhanced transcripts, multi-language
- Tier 2 (0.10-0.25 GLUE): Clip generation, blog posts, social media
- Tier 3 (0.25-0.50 GLUE): Predictive engine, recommendations, knowledge graph
- Tier 4-6 (0.50-100 GLUE): Video editing, image generation, custom AI, enterprise

**Cross-Platform Bundles (20-30% discount):**
- Complete Stream Context: 0.25 GLUE
- Auto Content Generator: 1.80 GLUE
- Predictive Intelligence Package: 0.90 GLUE

### Implementation Schedule

**Phase 3-4 (Weeks 4-5):** Tier 1-2 services (0.01-0.25 GLUE/request)
**Phase 5 (Week 6):** Tier 3-4 services (0.15-2.00 GLUE/request)
**Phase 6+ (Month 2+):** Tier 5-6 enterprise (10-200 GLUE/project)

---

## ❓ Critical Decisions Needed

### Q1: Data Source Strategy
- **Option A:** Static demo files (48 user logs from Oct 21, one-time extraction) - FASTER
- **Option B:** Connect to production MongoDB/SQLite - SCALABLE
- **Decision:** ___________________

### Q2: Message Quality Integration
How should Karma-Hello's quality service use main app's evaluation logic?
- **Option A:** MCP Server (Model Context Protocol)
- **Option B:** REST API endpoint
- **Option C:** Direct MongoDB access
- **Decision:** ___________________

### Q3: User Agent Deployment
- **Option A:** Start with 3-5 test users, verify, scale to 48 - RECOMMENDED
- **Option B:** Deploy all 48 at once
- **Decision:** ___________________

---

## 📖 References

### Official Documentation
- **ERC-8004 Spec:** https://eips.ethereum.org/EIPS/eip-8004
- **A2A Protocol:** https://ai.pydantic.dev/a2a/
- **x402 Protocol:** https://www.x402.org
- **EIP-3009:** https://eips.ethereum.org/EIPS/eip-3009
- **EIP-712:** https://eips.ethereum.org/EIPS/eip-712
- **CrewAI Docs:** https://docs.crewai.com

### Trustless Agents Course
- **URL:** https://intensivecolearn.ing/en/programs/trustless-agents
- **Content:** Agent identity, trust models, payment integration, multi-agent orchestration, marketplace building

### Tools
- **Foundry:** https://book.getfoundry.sh
- **Snowtrace (Fuji):** https://testnet.snowtrace.io
- **Avalanche Faucet:** https://faucet.avax.network
- **Pydantic AI:** https://ai.pydantic.dev

---

## 🎯 Next Steps

### Immediate (Today)
1. [ ] Create complete directory structure
2. [ ] Write all base READMEs
3. [ ] Setup Git repository
4. [ ] Create `feature/phase-1-blockchain` branch

### This Week
1. [x] Deploy GLUE Token ✅
2. [x] Deploy ERC-8004 to Fuji ✅
3. [ ] Configure x402 facilitator
4. [ ] Test infrastructure

### Next 2 Weeks
1. [ ] Base agent architecture
2. [ ] Validator agent
3. [ ] Client agent (generic buyer)
4. [ ] Karma-Hello agents (Tier 1-2 services)

---

## 📝 Implementation Notes

### Security
- **Never commit `.env` files** - use .gitignore
- Use test wallets for Fuji only
- Rotate keys before mainnet
- Audit contracts before production
- Rate limiting on facilitator

### Performance
- **Target latency:** <3s per transaction
- **Throughput:** 100 tx/min (Fuji limit)
- **Caching:** Redis for AgentCards
- **Monitoring:** OpenTelemetry + Grafana

### Costs

**Fuji Testnet (Free):**
- AVAX testnet from faucet
- All transactions free (testnet gas)

**Mainnet (Future):**
- GLUE tokens: $0.01 USD each
- Gas per tx: ~$0.001-0.01 AVAX
- Facilitator: $50/month server

---

## ✅ Completion Checklist

### Phase 1: Blockchain ✅
- [x] GLUE Token deployed on Fuji
- [x] ERC-8004 registries deployed
- [x] All contracts verified on Snowtrace
- [x] Agent wallets created and funded
- [x] AWS Secrets Manager configured for all private keys
- [ ] x402 facilitator running
- [ ] Testing suite passing

### Phase 2: Base Agents 🔴
- [ ] base_agent.py implemented
- [ ] Validator agent working
- [ ] Client agent operational
- [ ] ERC-8004 integration complete
- [ ] A2A protocol working
- [ ] CrewAI crews functional

### Phase 3-4: Service Agents 🔴
- [ ] Karma-Hello seller/buyer deployed
- [ ] Abracadabra seller/buyer deployed
- [ ] APIs with x402 working
- [ ] Data integration complete

### Phase 5: Testing & Demo 🔴
- [ ] End-to-end flow working
- [ ] Demo script complete
- [ ] Video tutorial recorded
- [ ] Full documentation written

---

**🎉 End of Master Plan**

**Version:** 1.0.0 | **Author:** Ultravioleta DAO | **License:** MIT
