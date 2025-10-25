# 🎯 MASTER PLAN: Trustless Agent Economy
## AI Agent Microeconomy with ERC-8004 + A2A + x402

> **Version:** 1.1.0 | **Updated:** October 24, 2025 | **Status:** ✅ Phase 2 Complete

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

⚠️ **CRITICAL: Never Send AVAX/Tokens to Contract Addresses**
- Contract addresses **cannot withdraw funds** without explicit withdrawal functions
- Identity Registry currently holds **0.015 AVAX permanently stuck** (3 × 0.005 AVAX registration fees)
- **ONLY send funds to EOAs** (externally owned addresses - wallet addresses with private keys)
- See `CLAUDE.md` for detailed safety guidelines

### Agent Wallets

| Agent | Address | GLUE Balance | Domain | Status |
|-------|---------|--------------|--------|--------|
| **Client Agent** | `0xCf30021812F27132d36dc791E0eC17f34B4eE8BA` | 55,000 | `client.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Karma-Hello** | `0x2C3e071df446B25B821F59425152838ae4931E75` | 55,000 | `karma-hello.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Abracadabra** | `0x940DDDf6fB28E611b132FbBedbc4854CC7C22648` | 55,000 | `abracadabra.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Validator** | `0x1219eF9484BF7E40E6479141B32634623d37d507` | 55,000 | `validator.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Voice Extractor** | `0xYOUR_ADDRESS_HERE` | 55,000 | `voice-extractor.karmacadabra.ultravioletadao.xyz` | ⏳ Pending |
| **Skill Extractor** | `0xYOUR_ADDRESS_HERE` | 55,000 | `skill-extractor.karmacadabra.ultravioletadao.xyz` | ⏳ Pending |

**Total Distributed:** 220,000 GLUE (4 agents funded) | **Budgeted:** 110,000 GLUE (2 agents pending) | **Owner Remaining:** 23,937,817 GLUE

**Domain Convention:** All agents use `<agent-name>.karmacadabra.ultravioletadao.xyz` format (required for on-chain registration)

---

## ⚠️ IMPLEMENTATION STATUS

**Last Updated:** October 24, 2025

### ✅ PHASE 1 COMPLETE: Blockchain Infrastructure

All contracts deployed and verified on Fuji. All agent wallets funded. Token distribution scripts functional.

### ✅ PHASE 2 COMPLETE: Agent Development

**COMPLETE:** All foundation components and agents implemented. Full buyer+seller pattern operational.

| Component | Status | Details |
|-----------|--------|---------|
| ERC8004BaseAgent Class | ✅ COMPLETE | 857 lines with buyer+seller capabilities built-in |
| x402 Payment Integration | ✅ COMPLETE | payment_signer.py (470+ lines) |
| A2A Protocol | ✅ COMPLETE | a2a_protocol.py (650+ lines) with AgentCard |
| CrewAI Integration | ✅ COMPLETE | validation_crew.py (550+ lines) |
| Validator Agent | ✅ COMPLETE | Independent quality validation (1,545+ lines) |
| Client Agent | ✅ COMPLETE | Buyer+Seller orchestrator (485+ lines) |
| Karma-Hello Agent | ✅ COMPLETE | Dual buyer/seller (720+ lines) |
| Abracadabra Agent | ✅ COMPLETE | Dual buyer/seller (720+ lines) |
| Voice-Extractor Agent | ✅ COMPLETE | Skill profiler (523+ lines) |
| Skill-Extractor Agent | ✅ COMPLETE | Competency analyzer (790+ lines) |
| Buyer+Seller Pattern | ✅ BUILT-IN | All agents inherit discover/buy/sell methods from base |

### 🔮 NEW VISION: User Agent Microeconomy

**Evolution:** From 4 system agents → 48+ user agents creating self-organizing microeconomy

**Key New Components:**
- ✅ Voice Extractor Agent (linguistic personality profiler) - COMPLETE
- ✅ Skill-Extractor Agent (skill/competency profiler) - COMPLETE
- 📋 Agent Card Generator (auto-gen from profiles) 🔥 **NEXT TASK**
- 📋 User Agent Factory (mass deployment)
- 📋 48 User Agents (one per chat participant)
- 📋 Bootstrap Marketplace (self-discovery flow)

**Network Math:** 48 agents × 47 connections = **2,256 potential trades** (quadratic growth)

---

## 📊 REVISED ROADMAP

### ✅ Sprint 1 (Weeks 1-2): Foundation - COMPLETE

### ✅ Sprint 2 (Weeks 3-4): System Agents - COMPLETE

### ✅ Sprint 2.8: Testing & Validation - COMPLETE

### ❌ Sprint 2.9 (Week 5): Coinbase Payments MCP - **DEFERRED** - Installation Blocker

### 📋 Sprint 3 (Weeks 6-7): User Agent System - NEXT

### 📋 Sprint 4 (Weeks 8-9): Visualization - FUTURE

---

### Sprint 1 (Weeks 1-2): Foundation - START HERE 🔴 BLOCKER

**Goal:** Build core infrastructure for all agents

| Task | Effort | Status | Deliverable |
|------|--------|--------|-------------|
| Create base_agent.py with ERC8004BaseAgent | 2-3 days | ✅ DONE | shared/base_agent.py (857 lines with buyer+seller built-in) |
| Web3.py contract integration | 1 day | ✅ DONE | Included in base_agent.py |
| EIP-712 payment signing | 2 days | ✅ DONE | shared/payment_signer.py (470+ lines) |
| x402 HTTP client (Python) | 1-2 days | ✅ DONE | shared/x402_client.py (530+ lines) |
| A2A AgentCard implementation | 2 days | ✅ DONE | shared/a2a_protocol.py (650+ lines) |
| First CrewAI crew | 1 day | ✅ DONE | shared/validation_crew.py (550+ lines) |
| Integration tests | 1 day | ✅ DONE | shared/tests/ (26 unit + integration tests) |
| Buyer+Seller pattern in base agent | 1 day | ✅ DONE | discover/buy/sell methods inherited by all agents |

**Output:** `shared/base_agent.py`, `shared/eip712_signer.py`, `shared/x402_client.py`, `shared/a2a_protocol.py`

### Sprint 2 (Weeks 3-4): System Agents

**Order (sequential):**
1. ✅ Validator Agent (validates foundation) - COMPLETE
2. ✅ Client Agent (reference buyer) - COMPLETE
3. ✅ Data Source Integration (static demo files) - COMPLETE
4. ✅ Karma-Hello Seller - COMPLETE
5. ✅ Abracadabra Seller - COMPLETE
6. ✅ Voice Extractor (linguistic personality profiler) - COMPLETE
7. ✅ Skill-Extractor Agent (skill/competency profiler) - COMPLETE

**Progress:** ✅ 7 of 7 milestones complete (100%) - **SPRINT 2 COMPLETE**

**Milestone 2.7: Skill-Extractor Agent** ✅ **COMPLETE**

**What it is:**
- Full economic agent (buys AND sells)
- System Agent #6 in the ecosystem
- Extracts skills/interests from chat logs using CrewAI

**Economic Model:**
```
Buys from: Karma-Hello (0.01 GLUE/user for chat logs)
Sells to: Client agents, User agents (0.05 GLUE/profile)
Net profit: 0.04 GLUE per extraction (400% margin)
```

**Service Catalog:**
- Basic Profile (0.02 GLUE): Top 3 interests + top 3 skills
- Standard Profile (0.03 GLUE): Full interests + skills + tools
- Complete Profile (0.05 GLUE): Full + monetization opportunities
- Enterprise Analysis (0.50 GLUE): Deep-dive competitive analysis

**Implementation:**
- ✅ `skill-extractor-agent/main.py` - 790+ lines, full buyer+seller implementation
- ✅ FastAPI server (port 8085)
- ✅ 5-category analysis framework (interests, skills, tools, interaction_style, monetization)
- ✅ CrewAI-based multi-agent analysis (simplified for MVP)
- ✅ A2A protocol discovery via `/.well-known/agent-card`
- ✅ x402 payment protocol integration
- ✅ Dual data source support (local files + Karma-Hello purchases)
- ✅ Profile caching to `profiles/` directory

**Wallet Information:**
- Address: TBD (to be funded in Phase 2.5)
- Initial Balance: 55,000 GLUE (budgeted)
- ERC-8004 Registration: System Agent #6 (pending wallet creation)

---

### Sprint 2.8: Testing & Validation ✅ **COMPLETE**

**Goal:** Verify all Sprint 2 agents work correctly before moving to Sprint 3

**Testing Strategy - 3 Levels:**

#### ✅ Level 1: Unit Tests (No External Dependencies) - **COMPLETE**

**Objective:** Test each agent's internal logic with mock data

**Test Coverage:**
- ✅ Sprint 1 Foundation: 26 passing unit tests
- ✅ Validator Agent: `test_validator.py` with --quick mode
- ✅ Client Agent: `client-agent/test_client.py` (6/6 tests passing)
- ✅ Karma-Hello Agent: `karma-hello-agent/test_karma_hello.py` (8/8 tests passing)
- ✅ Abracadabra Agent: `abracadabra-agent/test_abracadabra.py` (5/5 tests passing)
- ✅ Voice-Extractor Agent: `voice-extractor-agent/test_voice_extractor.py` (5/5 tests passing)
- ✅ Skill-Extractor Agent: `skill-extractor-agent/test_skill_extractor.py` (6/6 tests passing)

**Results:** ✅ **30/30 tests passing** - All agents validated

**What to test:**
- ✅ Agent initialization (without on-chain registration)
- ✅ Data parsing and validation
- ✅ Price calculation logic
- ✅ AgentCard generation
- ✅ Mock buyer/seller flows
- ❌ No OpenAI calls (use mock CrewAI responses)
- ❌ No blockchain transactions (use mock Web3)
- ❌ No inter-agent communication

**Implementation:**
Each agent gets a `test_[agent].py` file with:
```python
# Mock mode - no external dependencies
python test_karma_hello.py --mock
python test_abracadabra.py --mock
python test_voice_extractor.py --mock
python test_skill_extractor.py --mock
```

**Success Criteria:** All agents pass unit tests with mock data

---

#### ✅ Level 2: Integration Tests (Agents Running) - **COMPLETE**

**Objective:** Test agents as running servers with local data

**Status:** ✅ All 4 system agents start successfully and respond to HTTP requests

**Test Coverage:**
- Start each agent individually
- Test HTTP endpoints (/, /health, /.well-known/agent-card)
- Test service endpoints with local data files
- Verify response formats and headers

**What to test:**
- ✅ Server starts successfully
- ✅ Health endpoints respond
- ✅ AgentCard returns valid JSON
- ✅ Service endpoints work with local files
- ❌ No payment verification
- ❌ No on-chain transactions

**Implementation:**
```bash
# Terminal 1: Start agent
cd karma-hello-agent && python main.py

# Terminal 2: Run integration tests
python test_karma_hello.py --live
```

**Fixes Applied:**
- Fixed `register_agent()` signature mismatch (removed invalid argument)
- Fixed `get_glue_balance()` calls (replaced with `get_balance()` for AVAX)
- Added default `agent_domain` values for all agents
- Fixed syntax errors in voice-extractor (unterminated strings)
- Added skill-extractor wallet to AWS Secrets Manager

**Results:**
- ✅ Karma-Hello - starts successfully, health endpoint responding
- ✅ Abracadabra - starts successfully
- ✅ Voice-Extractor - starts successfully
- ✅ Skill-Extractor - starts successfully (wallet provisioned)

**Success Criteria:** All agents serve data from local files ✅ **ACHIEVED**

---

#### ✅ Level 3: End-to-End Tests (Full Flow) - **COMPLETE**

**Objective:** Test complete buyer→validator→seller flow

**Test Scenarios:**
1. **Discovery Flow:**
   - Client discovers Karma-Hello via A2A protocol
   - Client discovers Validator via A2A protocol
   - Verify AgentCard parsing

2. **Validation Flow:**
   - Client requests validation from Validator
   - Validator analyzes sample data
   - Returns validation score (mock on-chain submission)

3. **Purchase Flow (Simulated):**
   - Client generates payment authorization (EIP-712 signature)
   - Seller receives payment header
   - Seller returns data
   - Client saves purchased data

4. **Cross-Agent Flow:**
   - Voice-Extractor buys logs from Karma-Hello
   - Voice-Extractor processes and returns profile
   - Skill-Extractor buys logs from Karma-Hello
   - Skill-Extractor processes and returns profile

**What to test:**
- ✅ Multi-agent orchestration
- ✅ A2A protocol discovery
- ✅ Payment signature generation (no on-chain execution)
- ✅ Data flow between agents
- ⚠️  Mock facilitator (no real blockchain transactions)

**Implementation:**
Test script: `test_level3_e2e.py`

**Test Coverage:**
- ✅ Health check all agents
- ✅ Discovery flow (A2A AgentCard)
- ✅ Validation flow (full CrewAI validation with Quality, Fraud, Price crews)
- ✅ Purchase flow (data retrieval from Karma-Hello)

**Results:** 4/4 tests passing - ALL TESTS GREEN ✅

**Success Criteria:** Complete buyer→validator→seller flow works with mock payments ✅ **FULLY OPERATIONAL**

---

**Final Status:**
- ✅ Level 1: 30/30 unit tests passing
- ✅ Level 2: All 4 agents start successfully
- ✅ Level 3: 4/4 E2E tests passing - FULLY OPERATIONAL

**All Sprint 2.8 objectives achieved! All tests green! 🎉**

---

**Historical Note - Issues Found and Fixed:**
During testing, discovered that agents could not start as servers due to **signature mismatch**:

```python
# base_agent.py expects:
def __init__(self, agent_name: str, agent_domain: str, rpc_url: str = None,
             identity_registry_address: str = None, ...)

# But agents are calling with:
super().__init__(
    private_key=config.get("private_key"),  # ❌ Wrong - no agent_name/domain
    rpc_url=config["rpc_url_fuji"],          # ✅ Correct
    identity_registry=config["..."],         # ❌ Wrong - should be identity_registry_address
    glue_token_address=config["..."],        # ❌ Wrong - not accepted by base_agent
    facilitator_url=config["..."]            # ❌ Wrong - not accepted by base_agent
)
```

**Impact:** All 4 agents (Karma-Hello, Abracadabra, Voice-Extractor, Skill-Extractor) fail to initialize

**Next Steps:**
1. ✅ ~~Create unit tests for all 5 agents~~ - COMPLETE
2. ✅ ~~Run all Level 1 tests~~ - COMPLETE (30/30 passing)
3. ❌ Level 2 blocked - **Fix agent initialization signatures**
4. 🔧 **CRITICAL:** Fix all agents to match base_agent.py signature
5. ⏭️  Then re-run Level 2 (integration tests)
6. ⏭️  Then Level 3 (end-to-end flow testing)

**October 24, 2025 Update - Validator Level 3 Tests Fixed:**

Fixed critical Pydantic validation errors and port conflicts that prevented validator from working in E2E tests:

1. **AgentCard Model Fixes:**
   - Changed `agentId` from string to integer (uses on-chain agent ID: 4)
   - Added required `domain` field
   - Fixed Skill model: added `skillId` field, changed `pricing` to `price`

2. **Port Configuration:**
   - Moved validator from port 8001 (had empty response issues) to port 8011
   - Updated .env, .env.example, and test_level3_e2e.py

3. **Test Alignment:**
   - Fixed field name expectations (snake_case → camelCase for A2A protocol)
   - Fixed validation request payload to match ValidationRequest model
   - Increased timeout from 30s to 55s for CrewAI processing

4. **Result:** All 4/4 Level 3 E2E tests passing:
   - ✅ Health Check
   - ✅ Discovery Flow (agent-card endpoint)
   - ✅ Validation Flow (full CrewAI Quality/Fraud/Price validation)
   - ✅ Purchase Flow (data retrieval from Karma-Hello)

**Files Modified:**
- `validator/main.py:143-157` (get_agent_card method)
- `validator/.env.example:29` (PORT=8011)
- `test_level3_e2e.py` (test expectations and timeout)

---

### Sprint 2.9 (Week 5): Coinbase Payments MCP Integration ❌ **DEFERRED** - Installation Blocker

**Goal:** Enable fiat payments via Coinbase MCP to massively expand user base before deploying 48 user agents

**POC Result:** ❌ **NO-GO** - Installation blocker on Windows prevents testing

**Timeline:**
- **Day 1:** POC Testing ❌ **BLOCKED**
  - [x] Install MCP: `npx @coinbase/payments-mcp` - **FAILED** (Windows Node.js detection bug)
  - [ ] Test Avalanche Fuji testnet compatibility - **CANNOT TEST** (installation blocked)
  - [ ] Test GLUE token support - **CANNOT TEST** (installation blocked)
  - [ ] Measure transaction fees - **CANNOT TEST** (installation blocked)
  - [ ] Test AI agent programmatic access - **CANNOT TEST** (installation blocked)
  - [x] Document findings in `plans/COINBASE_MCP_POC_RESULTS.md` ✅ **COMPLETE**

**Critical Blocker:**
```
Error: Node.js is not available. Please install Node.js version 16 or higher.
Reality: Node.js v23.11.0 is installed and functional
Root Cause: @coinbase/payments-mcp installer bug on Windows
Impact: Cannot answer any of the 5 critical questions
```

**Critical Questions - Status:**
1. ❌ Does it work with Fuji testnet? - **NOT TESTED** (installation blocked)
2. ❌ Does it support GLUE token? - **NOT TESTED** (installation blocked)
3. ❌ What are fees for 0.01 GLUE? - **NOT TESTED** (installation blocked)
4. ❌ Can 48 agents use it programmatically? - **NOT TESTED** (installation blocked)
5. ❌ Does it integrate with x402-rs? - **NOT TESTED** (installation blocked)

**Decision:** ❌ **DEFER Sprint 2.9** indefinitely

**Reasoning:**
- 🔴 Installation blocker prevents POC completion
- 🔴 Cannot validate critical assumptions (testnet, GLUE token, fees)
- 🔴 Alternative (x402 MCP example) lacks fiat on-ramp feature (the core value)
- 🟡 Risk too high to commit development effort without testing
- 🟢 Existing x402scan embedded wallet works well for crypto users

**Actions Taken:**
- [x] POC attempted and documented
- [x] Windows Node.js detection bug identified
- [x] Alternative fiat on-ramps researched (Stripe, Moonpay, Transak, Ramp, OnRamper)
- [x] GitHub issue prepared: `plans/GITHUB_ISSUE_PAYMENTS_MCP.md`
- [x] Full findings documented: `plans/COINBASE_MCP_POC_RESULTS.md`
- [x] Alternative research documented: `plans/ALTERNATIVE_FIAT_ONRAMPS_RESEARCH.md`

**Alternative Fiat On-Ramps Research Result:** ❌ **NO VIABLE OPTIONS**
- **Stripe**: ❌ No Avalanche Fuji testnet, no custom token support
- **Moonpay**: ❌ Sandbox supports 8 testnets but NOT Avalanche Fuji
- **Transak**: ❌ Staging supports 7 testnets but NOT Avalanche Fuji
- **Ramp Network**: ⚠️ No testnet information found
- **OnRamper**: ❌ Aggregator of above providers (no Fuji support)

**Critical Finding:** ALL major fiat on-ramps support Avalanche **mainnet only**. Zero providers support Avalanche Fuji testnet in sandbox environments.

**Implication:** Fiat on-ramp integration would require:
- Migrating to Avalanche mainnet (high risk)
- Security audit ($10K-$50K)
- GLUE token compliance review (2-4 weeks)
- Real AVAX for all 48+ agents
- Testing with real money (expensive)

**Alternative Paths Forward:**
1. ❌ **Mainnet migration** - Premature, requires $10K-$50K audit before market validation
2. ❌ **Manual fiat distribution** - Not scalable, violates trustless architecture
3. ✅ **Crypto-only payments (status quo)** - Working, safe, proven ✅ **RECOMMENDED**

**Impact on Roadmap:**
- ❌ Fiat payments NOT available for Sprint 3 (User Agent System)
- ❌ User onboarding remains crypto-native (15-20 min first-time setup)
- ❌ Addressable market remains limited (crypto users only)
- ✅ No wasted development effort on broken integration
- ✅ Can revisit in Q1 2026 or when installer is fixed

**Recommendation:** ✅ **Proceed to Sprint 3 (User Agent System) with existing payment infrastructure**

**Full Analysis:**
- POC Results: `plans/COINBASE_MCP_POC_RESULTS.md`
- Alternative Fiat On-Ramps Research: `plans/ALTERNATIVE_FIAT_ONRAMPS_RESEARCH.md`
- GitHub Issue Draft: `plans/GITHUB_ISSUE_PAYMENTS_MCP.md`
- Original Integration Plan: `plans/COINBASE_PAYMENTS_MCP_INTEGRATION.md` (for future reference)

**Revisit Criteria:** Reconsider fiat on-ramp integration when:
- ✅ Coinbase Payments MCP Windows installer fixed
- ✅ Any major provider adds Avalanche Fuji testnet support
- ✅ Karmacadabra proves market demand (1,000+ transactions/month on testnet)
- ✅ External funding secured ($50K+ for audit + mainnet migration)
- ✅ Halliday adds Fuji testnet support (Intent Orchestration Protocol)

---

### Sprint 3 (Weeks 6-7): User Agent System

**Milestones:**
1. Automated profile extraction (using Skill-Extractor Agent for 48 users)
2. Agent Card auto-generator
3. User agent template + factory
4. Mass deployment (48 agents)
5. Bootstrap marketplace test

### Sprint 4 (Weeks 8-9): Visualization

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
python scripts/demo_system.py

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
python scripts/demo_system.py --network local
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

**Private Key Management:**
- ⚠️ **NEVER store private keys in `.env` files** - ALL keys must be in AWS Secrets Manager
- ⚠️ **NEVER commit keys to git** - Even example files should have `PRIVATE_KEY=` (empty)
- ✅ **Use AWS Secrets Manager** - All agent keys stored under `karmacadabra` secret
- ✅ **ERC-20 deployer key** - Stored in AWS under `erc-20` key (rotate separately)
- ✅ **Agent keys** - Stored as `<agent-name>-agent` (e.g., `karma-hello-agent`)

**Deployment Security:**
- Use test wallets for Fuji testnet only
- Rotate keys before mainnet deployment
- Audit contracts before production
- Rate limiting on x402 facilitator
- All deployment scripts fetch keys from AWS automatically

**Domain Naming Convention:**
- ALL agent domains MUST use: `<agent-name>.karmacadabra.ultravioletadao.xyz`
- Domains are registered on-chain (immutable, requires `updateAgent()` to change)
- See `CLAUDE.md` for complete domain guidelines

**System Rotation Tool (`rotate-system.py`):**
Complete infrastructure rotation for key compromise scenarios. Added October 23, 2025.

**Features:**
- Generates new wallets for ALL 6 agents (validator, karma-hello, abracadabra, client, voice-extractor, skill-extractor)
- Updates AWS Secrets Manager with new private keys (NEVER stores keys locally)
- Redeploys all contracts (ERC-20 GLUE + ERC-8004 registries)
- Updates all agent `.env` files with new contract addresses
- Funds wallets and distributes GLUE tokens
- Registers agents on-chain
- **Refill Mode** (`--refill` flag): Top up existing wallets with GLUE tokens without full rotation

**Safety Mechanisms:**
- Dry-run mode by default (shows what would happen, makes NO changes)
- Requires `--confirm` flag to execute actual rotation
- Requires typing 'ROTATE' to confirm destructive changes
- Clear color-coded terminal output for each step
- Validates AWS credentials before starting

**Use Cases:**
- 🚨 **Key Compromise**: Rotate immediately if private keys exposed in livestreams/logs
- 🔄 **Clean Reset**: Start fresh with new infrastructure for testing
- 💰 **Wallet Refill**: Top up agent wallets with GLUE tokens without full rotation (use `--refill` flag)
- 🧪 **Deployment Validation**: Test complete infrastructure automation
- 🎥 **Post-Stream**: Rotate keys after public demonstrations

```bash
# Dry run (safe, shows plan)
python scripts/rotate-system.py

# Execute rotation (destructive!)
python scripts/rotate-system.py --confirm
# Type 'ROTATE' when prompted

# Refill wallets with GLUE only (dry-run)
python scripts/rotate-system.py --refill

# Refill wallets with GLUE only (execute)
python scripts/rotate-system.py --refill --confirm

# Rotate ERC-20 deployer wallet ONLY (requires GLUE token redeployment)
python scripts/rotate-system.py --rotate-erc20 --confirm
# Type 'ROTATE-ERC20' when prompted
# WARNING: Requires redeploying GLUE token contract!
```

**Important Notes:**
- ERC-20 deployer is **NOT rotated by default** (owns GLUE token contract)
- Use `--rotate-erc20` flag ONLY when specifically needed
- Rotating ERC-20 deployer requires redeploying entire GLUE token

This addresses the critical security requirement of never storing keys locally and providing rapid response to key exposure incidents

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
- [x] Testing suite passing (4/4 Level 3 E2E tests)

### Phase 2: Base Agents ✅ **COMPLETE**
- [x] base_agent.py implemented (857 lines with buyer+seller built-in)
- [x] Validator agent working (AgentCard + CrewAI validation)
- [x] Client agent operational (buyer+seller orchestrator, 485 lines)
- [x] ERC-8004 integration complete
- [x] A2A protocol working
- [x] CrewAI crews functional
- [x] Buyer+Seller pattern - ALL agents inherit discover/buy/sell methods

### Phase 3-4: Service Agents 🔴
- [ ] Karma-Hello seller/buyer deployed
- [ ] Abracadabra seller/buyer deployed
- [ ] APIs with x402 working
- [ ] Data integration complete

### Phase 5: Testing & Demo 🔵 IN PROGRESS
- [x] End-to-end flow working (4/4 tests passing)
- [ ] Demo script complete
- [ ] Video tutorial recorded
- [ ] Full documentation written

---

**🎉 End of Master Plan**

**Version:** 1.0.0 | **Author:** Ultravioleta DAO | **License:** MIT
