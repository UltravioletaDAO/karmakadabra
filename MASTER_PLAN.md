# 🎯 MASTER PLAN: Trustless Agent Economy
## AI Agent Microeconomy with ERC-8004 + A2A + x402

> **Version:** 1.6.2 | **Updated:** October 28, 2025 | **Status:** ✅ READY - Sprint 4 Active
>
> **Last Audit:** October 27, 2025 - Code audit completed, **WALLET INFRASTRUCTURE COMPLETE**
>
> **✅ MILESTONE ACHIEVED:** Central Marketplace API operational, serving 48 user agent cards
> **Current Priority:** Sprint 4 - Visualization & Agent Activation
>
> **📦 Latest Deployment (October 28, 2025):**
> - ✅ **Central Marketplace API:** Option C implementation complete (agents/marketplace/main.py)
> - ✅ **Agent Discovery:** Serves 48 static agent cards via A2A protocol
> - ✅ **Search & Stats:** Full-text search, engagement filtering, marketplace statistics
> - ✅ **Cost-effective:** One API instead of deploying 48 agents (~$100+/month saved)
> - ✅ **Endpoints:** /agents, /search, /stats, /agents/{username}/card all operational
> - ✅ **Tested locally:** All endpoints verified, loads 48 cards + 48 profiles
>
> **Previous Deployment (October 27, 2025):**
> - ✅ **Production Data Integration:** karma-hello and abracadabra now serve real production data
> - ✅ Created TXT→JSON conversion script for karma-hello logs (6 dates: 20251014-20251021, 2,685 messages)
> - ✅ Fixed Docker path mounting: `/data/karma-hello` for logs, `/transcripts` for abracadabra
> - ✅ Rebuilt and redeployed both agents to ECS Fargate with production data
> - ✅ **All E2E tests passing:** Health (5/5), Discovery, Validation, Purchase flows operational

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

### System Agent Wallets (Production Infrastructure)

| Agent | Address | GLUE Balance | Domain | Status |
|-------|---------|--------------|--------|--------|
| **Validator** | `0x1219eF9484BF7E40E6479141B32634623d37d507` | 55,000 | `validator.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Karma-Hello** | `0x2C3e071df446B25B821F59425152838ae4931E75` | 55,000 | `karma-hello.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Abracadabra** | `0x940DDDf6fB28E611b132FbBedbc4854CC7C22648` | 55,000 | `abracadabra.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Skill Extractor** | `0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9` | 55,000 | `skill-extractor.karmacadabra.ultravioletadao.xyz` | ✅ Funded |
| **Voice Extractor** | `0x8e0Db88181668cdE24660D7Ee8dA18A77DDbbF96` | 55,000 | `voice-extractor.karmacadabra.ultravioletadao.xyz` | ✅ Funded |

**Total System Agents:** 5 | **Total Distributed:** 275,000 GLUE | **Owner Remaining:** 23,882,817 GLUE

**Note:** Client Agent (0xCf30021812F27132d36dc791E0eC17f34B4eE8BA) is a testing/orchestrator agent, not part of production system agents.

### User Agent Ecosystem (48 Agents)

**Status:** ✅ **DEPLOYED** - 48 user agents generated and ready for marketplace
- Location: `client-agents/` (49 folders: 48 users + 1 template)
- Template: 486 lines with full buyer+seller capabilities
- Each user agent: ~310 lines (simplified from template)
- All inherit from ERC8004BaseAgent with discover/buy/sell methods

**User agents:** 0xultravioleta, fredinoo, f3l1p3_bx, eljuyan, elboorja, elbitterx, efeksellindo, dzepequeno, dogonpayy, djhohn, detx8, derek_farming, davidzoh_, davidtherich, datbo0i_lp, darelou, daniel_02s, cymatix, cyberpaisa, craami, collin_0108, coleguin_, celacaftt, calde333, cabomarzo, byparcero, aricreando, andres92____, allan__lp, alej0lr420, alej_o, akawolfcito, aka_r3c, acpm444, abu_ela, 1nocty, 0xyuls, 0xsoulavax, 0xroypi, 0xpineda, 0xmabu_, 0xkysaug, 0xjuanwx_, 0xjuandi, 0xjokker, 0xj4an, 0xh1p0tenusa, 0xdream_sgo

**Total Agents in Ecosystem:** 5 system agents + 48 user agents = **53 agents**

**Domain Convention:** All agents use `<agent-name>.karmacadabra.ultravioletadao.xyz` format (required for on-chain registration)

---

## ⚠️ IMPLEMENTATION STATUS

**Last Updated:** October 28, 2025
**Last Audit:** October 27, 2025 - Full codebase audit completed (see AUDIT_FINDINGS_2025-10-27.md)

### ✅ PHASE 1 COMPLETE: Blockchain Infrastructure

All contracts deployed and verified on Fuji. All system agent wallets funded. Token distribution scripts functional.

### ✅ PHASE 2 COMPLETE: Agent Development

**COMPLETE:** All foundation components and 5 system agents implemented. Full buyer+seller pattern operational.

| Component | Status | Details | Location |
|-----------|--------|---------|----------|
| ERC8004BaseAgent Class | ✅ COMPLETE | 857 lines with buyer+seller capabilities built-in | shared/base_agent.py |
| x402 Payment Integration | ✅ COMPLETE | payment_signer.py (470 lines) | shared/payment_signer.py |
| A2A Protocol | ✅ COMPLETE | a2a_protocol.py (599 lines) with AgentCard | shared/a2a_protocol.py |
| CrewAI Integration | ✅ COMPLETE | validation_crew.py (558 lines) | shared/validation_crew.py |
| Validator Agent | ✅ COMPLETE | Independent quality validation (443 lines) | validator/main.py |
| Karma-Hello Agent | ✅ COMPLETE + DATA | Dual buyer/seller with production logs (571 lines, 6 dates, 2,685 msgs) | agents/karma-hello/main.py |
| Abracadabra Agent | ✅ COMPLETE + DATA | Dual buyer/seller with production transcripts (565 lines, 6 streams) | agents/abracadabra/main.py |
| Skill-Extractor Agent | ✅ COMPLETE | Bidirectional AI agent profiler (963 lines) | agents/skill-extractor/main.py |
| Voice-Extractor Agent | ✅ COMPLETE | Personality profiler (524 lines) | agents/voice-extractor/main.py |
| Buyer+Seller Pattern | ✅ BUILT-IN | All agents inherit discover/buy/sell methods from base | shared/base_agent.py |

**Total System Agents:** 5 (Validator, Karma-Hello, Abracadabra, Skill-Extractor, Voice-Extractor)
**Total Code Lines (shared + agents):** 4,124 (shared) + 3,110 (agents) = **7,234 lines**

### ✅ PHASE 3 COMPLETE: User Agent Microeconomy

**Evolution:** From 5 system agents → 48 user agents creating self-organizing microeconomy

**🎉 INFRASTRUCTURE COMPLETE (2025-10-27):**
User agent code AND wallet infrastructure are both ready:
- ✅ **48 wallets generated** and stored in AWS Secrets Manager
- ✅ **AVAX distributed** to all agents (0.05 AVAX each = 2.4 AVAX total)
- ✅ **GLUE distributed** to all agents (10,946 GLUE each avg = 525K GLUE total)
- ✅ **On-chain registration** complete (ERC-8004 IDs: 7-54)
- ✅ **All agents verified** with 100% success rate

**Code Status (Complete):**
- ✅ Voice Extractor Agent (linguistic personality profiler) - COMPLETE
- ✅ Skill-Extractor Agent (bidirectional AI agent profiler: skills + needs + opportunities) - COMPLETE
- ✅ User Agent Template (486 lines with full buyer+seller) - COMPLETE (client-agents/template/)
- ✅ User Agent Factory (mass deployment) - COMPLETE (48 agents generated)
- ✅ 48 User Agents (one per chat participant) - DEPLOYED & FUNDED (client-agents/)

**Infrastructure Status (ALL COMPLETE):**
- ✅ Wallet Generation (48 wallets) - **COMPLETE**
- ✅ AVAX Distribution (2.4 AVAX distributed) - **COMPLETE**
- ✅ GLUE Distribution (525K GLUE distributed) - **COMPLETE**
- ✅ On-chain Registration (48 agents, IDs 7-54) - **COMPLETE**
- 📋 Agent Card Generator (auto-gen from profiles) - PENDING (Sprint 4)
- 📋 Bootstrap Marketplace (self-discovery flow) - READY (Sprint 4)

**Network Math:** 53 agents total (5 system + 48 user) × 52 connections = **2,756 potential trades** (quadratic growth)

**User Agent Status:**
- Location: `client-agents/` directory
- Each agent: ~310 lines (simplified from 486-line template)
- All inherit ERC8004BaseAgent with discover/buy/sell methods
- Ready for on-chain registration and marketplace activation

---

## 📊 REVISED ROADMAP

### ✅ Sprint 1 (Weeks 1-2): Foundation - COMPLETE

### ✅ Sprint 2 (Weeks 3-4): System Agents - COMPLETE

### ✅ Sprint 2.8: Testing & Validation - COMPLETE

### ✅ Sprint 3 (Weeks 5-6): User Agent System - COMPLETE

### ✅ Sprint 3.5: Wallet Infrastructure - COMPLETE

### 🔥 Sprint 4 (Weeks 7-8): Marketplace Bootstrap & Visualization - **CURRENT PRIORITY**

### ⏸️ Sprint 5 (Future): Coinbase Payments MCP - **DEFERRED** - Awaiting Testnet Support

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
- ✅ `skill-extractor-agent/main.py` - 963 lines, bidirectional AI agent profiler
- ✅ FastAPI server (port 9004)
- ✅ **Bidirectional Analysis:** User sells (skills) + User needs to buy (gaps, shopping list)
- ✅ **Market Opportunities:** UNMET_NEED, UPSELL, COMPLEMENTARY signals for other agents
- ✅ **Revenue Projections:** Monthly income, break-even, passive income potential
- ✅ **Agent Identity Design:** Autonomous agent personality + implementation roadmap
- ✅ 20-field comprehensive output (skills, needs, opportunities, revenue, identity, etc.)
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

### Sprint 3 (Weeks 5-6): User Agent System 🚧 **BLOCKED**

**⚠️ CRITICAL BLOCKER: Wallet Infrastructure Missing**

**Milestones:**
1. ⏳ Automated profile extraction (using Skill-Extractor Agent for 48 users) - PARTIAL
2. 📋 Agent Card auto-generator - PENDING (moved to Sprint 4)
3. ✅ User agent template + factory - **COMPLETE** (client-agents/template/ - 486 lines)
4. ✅ Mass deployment (48 agents) - **CODE COMPLETE** (client-agents/ with 48 user agents)
5. ❌ Wallet infrastructure - **MISSING** → **BLOCKING ALL TESTING**

**Completed Deliverables (Code Only):**
- ✅ User Agent Template: 486 lines with full buyer+seller capabilities
- ✅ 48 User Agents Generated: Each ~310 lines, inherit from ERC8004BaseAgent
- ✅ Agent Factory Automation: Scripts to generate agents from template
- ✅ Directory Structure: `client-agents/` with 49 folders (48 users + template)

**BLOCKED Deliverables (Infrastructure Missing):**
- ❌ **48 Wallets Generated** - NONE EXIST
- ❌ **AVAX Distribution** - No testnet AVAX in user wallets
- ❌ **GLUE Distribution** - No GLUE tokens in user wallets
- ❌ **On-chain Registration** - Cannot register without funded wallets
- ❌ **Bootstrap marketplace test** - Cannot test without wallets

**Deferred to Sprint 4:**
- Agent Card auto-generator (milestone 2)
- Bootstrap marketplace test (milestone 5) - **NOW BLOCKED**
- Profile extraction automation (milestone 1 completion)

### Sprint 3.5: Wallet Infrastructure Setup ✅ **COMPLETE**

**Goal:** Unblock Sprint 3 by creating wallet infrastructure for 48 user agents

**Scripts Used:**

1. ✅ **Unified Setup Script** - `scripts/setup_48_user_agents.py`
   - Generated 48 wallets
   - Stored keys in AWS Secrets Manager
   - Updated all `.env` files
   - Distributed AVAX (0.05 per agent)
   - Distributed GLUE (1,000 per agent initially, now 10,946 avg from trading)
   - Registered agents on-chain
   - Idempotent (safe to run multiple times)

2. ✅ **Verification Script** - `scripts/verify_user_agents.py`
   - Checked all 48 agents
   - Verified AVAX balance (≥0.05)
   - Verified GLUE balance (≥1,000)
   - Verified on-chain registration
   - Provided detailed summary

**Resources Distributed:**
- AVAX: **2.4 AVAX** (48 × 0.05) ✅ Distributed
- GLUE: **525K GLUE** (48 × 10,946 avg) ✅ Distributed and earned from trading
- Time: **Completed** (all transactions confirmed)

**Verification Results:**
```bash
python scripts/verify_user_agents.py
```

**Success Criteria:** ✅ **ALL ACHIEVED**
- [x] All 48 wallets generated and stored securely
- [x] All 48 wallets have ≥0.05 AVAX
- [x] All 48 wallets have ≥1,000 GLUE (avg 10,946 GLUE)
- [x] All 48 agents registered on-chain (IDs 7-54)
- [x] All 48 `.env` files configured correctly
- [x] `verify_user_agents.py` shows 100% on all checks

### Sprint 3.9: Marketplace Strategy Decision ✅ **COMPLETE**

**Context:** Sprint 3 created 48 user agents (code + wallets + on-chain registration), but they weren't deployed as HTTP services. This blocked agent discovery via A2A protocol.

**Three Options Considered:**

**Option A: Deploy All to ECS**
- Pro: Always online, scalable, production-ready
- Con: ~$100+/month for 48 agents (2 vCPU + 4GB RAM each)
- Con: Complex Terraform setup for 48 services

**Option B: On-Demand Local Execution**
- Pro: Free, flexible
- Con: Not truly autonomous (requires manual startup)
- Con: Not accessible via domain names

**Option C: Central Marketplace + Static Cards** ✅ **CHOSEN**
- Pro: Cheap (one API server instead of 48)
- Pro: Simple implementation (FastAPI + JSON files)
- Pro: Provides full A2A discovery
- Pro: Can spin up individual agents on-demand when needed
- Con: Not truly decentralized (single point of discovery)

**Decision Rationale:**
- **Cost-effective MVP**: Saves ~$100/month while providing full discovery
- **Agents ready**: 48 user agents exist (wallets funded, registered on-chain)
- **Dormant until needed**: Agents can be activated when clients want to purchase
- **Matches current scale**: System agents (5) handle most traffic, user agents (48) are passive

**Implementation:** `agents/marketplace/main.py` (324 lines)
- Loads 48 agent cards from `demo/cards/*.json`
- Loads 48 profiles from `demo/profiles/*.json`
- Serves A2A protocol agent cards at `/agents/{username}/card`
- Provides search, filtering, and marketplace statistics
- Port 9000 (standard marketplace port)

**Testing:**
```bash
cd agents/marketplace
pip install -r requirements.txt
python main.py

# Test endpoints
curl http://localhost:9000/health          # → 48 agents loaded
curl http://localhost:9000/agents          # → List all agents
curl http://localhost:9000/search?q=blockchain  # → 16 results
curl http://localhost:9000/stats           # → Marketplace stats
```

**Next Steps:**
- Deploy marketplace to ECS (one service, low cost)
- Test agent discovery via marketplace
- Optionally: Spin up individual user agents on-demand

---

### Sprint 4 (Weeks 7-8): Marketplace Activation & Visualization 🔥 **CURRENT PRIORITY**

**✅ UNBLOCKED:** Sprint 3.5 wallet infrastructure complete - all 48 agents ready

**Priority 1: Marketplace Bootstrap (from Sprint 3):**

#### Sprint 4 Task 1: Central Marketplace API (Option C) ✅ **COMPLETE**

**What:** FastAPI service serving 48 static agent cards via A2A protocol

**Implementation:** `agents/marketplace/main.py` (324 lines)

**Features:**
- ✅ Loads 48 agent cards from `demo/cards/*.json`
- ✅ Loads 48 profiles from `demo/profiles/*.json`
- ✅ Endpoint: `/agents` - List all agents
- ✅ Endpoint: `/search` - Full-text search across agents
- ✅ Endpoint: `/stats` - Marketplace statistics
- ✅ Endpoint: `/agents/{username}/card` - A2A protocol agent card
- ✅ Cost-effective: One API instead of 48 deployed agents (~$100+/month saved)

**Testing:**
```bash
cd agents/marketplace
python main.py
curl http://localhost:9000/health          # → 48 agents loaded
curl http://localhost:9000/agents          # → List all
curl http://localhost:9000/search?q=blockchain  # → 16 results
```

**Deployment Strategy:** Agents remain dormant, spun up on-demand when clients purchase

**Status:** ✅ Tested locally, all endpoints operational

---

#### Sprint 4 Task 2: Facilitator Dual Wallet Display ✅ **COMPLETE**

**Goal:** Update facilitator landing page to show separate testnet and mainnet wallet balances

**Context:**
- Current state: Single wallet display at `https://facilitator.ultravioletadao.xyz`
- Reality: We use TWO wallets (testnet: 0x3403..., mainnet: 0x1030...)
- Need: Transparent display of both wallets' balances across 3 networks each

**Tasks:**

**2.1: Update HTML Structure** (`x402-rs/static/index.html`)
- [ ] Split wallet section into two: "Testnet Wallets" and "Mainnet Wallets"
- [ ] Move wallet sections up (after network badges, before "Service Online" status)
- [ ] Add 6 balance cards total:
  - Testnet: Avalanche Fuji, Base Sepolia, Celo Sepolia
  - Mainnet: Avalanche C-Chain, Base, Celo
- [ ] Update card styling for clarity (testnet=blue accent, mainnet=green accent)

**2.2: Update JavaScript** (`x402-rs/static/index.html` - inline script)
- [ ] Hardcode both wallet addresses in fetchWalletBalances():
  ```javascript
  const TESTNET_WALLET = '0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8';
  const MAINNET_WALLET = '0x103040545AC5031A11E8C03dd11324C7333a13C7';
  ```
- [ ] Fetch balances from appropriate RPC endpoints:
  - Avalanche Fuji RPC for testnet AVAX
  - Avalanche Mainnet RPC for mainnet AVAX
  - Base Sepolia RPC for testnet ETH
  - Base Mainnet RPC for mainnet ETH
  - Celo Sepolia RPC for testnet CELO
  - Celo Mainnet RPC for mainnet CELO
- [ ] Display 6 balance cards with proper formatting (4 decimals for crypto)

**2.3: RPC Configuration**
- [ ] Add RPC URLs to facilitator environment variables (or hardcode in JS)
- [ ] Test RPC connectivity for all 6 networks
- [ ] Handle RPC errors gracefully (show "N/A" if fetch fails)

**2.4: Testing**
- [ ] Test locally: `cd x402-rs && cargo run`
- [ ] Verify both wallets display correctly
- [ ] Verify balance fetching works for all 6 networks
- [ ] Test responsive layout (mobile + desktop)
- [ ] Verify auto-refresh works (every 30 seconds)

**Files Modified:**
- `x402-rs/static/index.html` (HTML structure + JavaScript)
- Optionally: `x402-rs/.env` (if RPC URLs added to config)

**Estimated Effort:** 2-4 hours

**Success Criteria:**
- [x] Landing page shows 6 wallet balance cards (3 testnet + 3 mainnet)
- [x] Balances update automatically every 30 seconds
- [x] Clear visual distinction between testnet and mainnet
- [x] Responsive design works on mobile and desktop

---

#### Sprint 4 Task 3: Facilitator Network Monitor 📋 **PENDING**

**Goal:** Create a comprehensive monitoring system tracking uptime and health of ALL x402 facilitators in the ecosystem (not just ours)

**Context:**
- Inspiration: [x402scan facilitators config](https://github.com/Merit-Systems/x402scan/blob/main/facilitators/config.ts)
- Tracks 9 facilitators: Coinbase, AurraCloud, thirdweb, X402rs/Karmacadabra, PayAI, Corbits, Daydreams, Mogami, Open X402
- Provides ecosystem visibility and competitive intelligence

**Tasks:**

**3.1: DynamoDB Table Setup** (`terraform/ecs-fargate/dynamodb.tf`)
- [ ] Create new Terraform file `dynamodb.tf`
- [ ] Define `facilitator-uptime-metrics` table:
  - Partition key: `facilitator_id` (string)
  - Sort key: `timestamp` (number - Unix timestamp)
  - Attributes: status, response_time, wallet_balances, last_error
  - TTL: 90 days (auto-delete old metrics)
  - Billing mode: PAY_PER_REQUEST (no capacity planning needed)
- [ ] Create GSI for querying by timestamp (for time-series queries)
- [ ] Terraform apply to create table

**3.2: Rust Backend Implementation** (`x402-rs/src/facilitator_monitor.rs`)
- [ ] Create new Rust module `facilitator_monitor.rs`
- [ ] Define structs from x402scan config:
  ```rust
  pub struct Facilitator {
      pub id: String,
      pub name: String,
      pub url: String,
      pub logo_url: Option<String>,
      pub wallet_addresses: Vec<WalletAddress>,
  }
  pub struct WalletAddress {
      pub address: String,
      pub network: Network,
  }
  ```
- [ ] Function: `ping_facilitator_health(url: &str) -> Result<HealthStatus>`
  - Call `/health` endpoint
  - Measure response time
  - Parse status (live/down)
- [ ] Function: `fetch_wallet_balances(addresses: &[WalletAddress]) -> Vec<Balance>`
  - Use Web3 RPC calls to fetch balances
  - Support multiple networks (Avalanche, Base, Celo)
- [ ] Function: `store_metrics(db: &DynamoDbClient, metrics: &Metrics)`
  - Store in DynamoDB with timestamp
  - Include uptime %, response time, wallet balances
- [ ] Add DynamoDB dependencies to `Cargo.toml`:
  ```toml
  aws-sdk-dynamodb = "1.5"
  tokio = { version = "1", features = ["time"] }
  ```

**3.3: REST API Endpoint** (`x402-rs/src/handlers.rs`)
- [ ] Add new endpoint: `GET /facilitators/monitor`
- [ ] Query DynamoDB for latest metrics (last 24 hours)
- [ ] Calculate uptime percentage for each facilitator
- [ ] Return JSON with facilitator status:
  ```json
  {
    "facilitators": [
      {
        "id": "x402rs",
        "name": "X402rs (Karmacadabra)",
        "status": "live",
        "uptime_24h": 99.8,
        "avg_response_time_ms": 120,
        "wallet_balances": [
          { "network": "avalanche_fuji", "balance": "2.197 AVAX" }
        ],
        "last_ping": 1698765432
      }
    ]
  }
  ```

**3.4: Background Task** (`x402-rs/src/main.rs`)
- [ ] Add background task using `tokio::time::interval`
- [ ] Ping all 9 facilitators every 5 minutes
- [ ] Store results in DynamoDB
- [ ] Handle errors gracefully (don't crash on failed pings)
- [ ] Log monitoring activity to CloudWatch

**3.5: Frontend Integration** (`x402-rs/static/index.html`)
- [ ] Add new collapsible section: "Facilitator Network Monitor"
- [ ] Grid layout with facilitator cards:
  - Logo (if available)
  - Name
  - Status indicator (green=live, red=down, yellow=degraded)
  - Uptime % (last 24h)
  - Avg response time
  - Wallet balances (collapsed, expand to view)
  - Last ping timestamp
- [ ] JavaScript to fetch from `/facilitators/monitor` endpoint
- [ ] Auto-refresh every 30 seconds
- [ ] Sorting options: name, uptime %, response time
- [ ] Filter options: show all / only live / only down

**3.6: Terraform IAM Permissions** (`terraform/ecs-fargate/iam.tf`)
- [ ] Add DynamoDB read/write permissions to ECS task role:
  ```hcl
  resource "aws_iam_role_policy" "facilitator_dynamodb" {
    role = aws_iam_role.ecs_task_role.name
    policy = jsonencode({
      Statement = [{
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.facilitator_metrics.arn
      }]
    })
  }
  ```

**3.7: Testing**
- [ ] Unit tests for Rust monitoring functions
- [ ] Integration test: ping facilitator health endpoints
- [ ] Test DynamoDB write/read operations
- [ ] Test REST endpoint returns valid JSON
- [ ] Test frontend rendering and auto-refresh
- [ ] Load test: ensure monitoring doesn't impact facilitator performance

**Files Created/Modified:**
- NEW: `terraform/ecs-fargate/dynamodb.tf`
- NEW: `x402-rs/src/facilitator_monitor.rs`
- MODIFIED: `x402-rs/src/handlers.rs` (add `/facilitators/monitor` endpoint)
- MODIFIED: `x402-rs/src/main.rs` (add background task)
- MODIFIED: `x402-rs/static/index.html` (add monitoring section)
- MODIFIED: `x402-rs/Cargo.toml` (add DynamoDB dependency)
- MODIFIED: `terraform/ecs-fargate/iam.tf` (add DynamoDB permissions)

**Estimated Effort:** 2-3 days

**Success Criteria:**
- [x] DynamoDB table created and accessible
- [x] Rust backend pings all 9 facilitators every 5 minutes
- [x] Metrics stored in DynamoDB with proper TTL
- [x] REST endpoint returns accurate facilitator status
- [x] Frontend displays real-time network health
- [x] Auto-refresh works smoothly
- [x] No performance degradation on facilitator (monitoring is lightweight)

**Benefits:**
- Ecosystem visibility: See all facilitators at a glance
- Competitive intelligence: Compare uptime and performance
- User trust: Transparency builds confidence
- Differentiation: Show we're the most reliable facilitator
- Early warning: Detect network-wide issues

---

**Remaining Sprint 4 Tasks:**

2. 📋 Complete profile extraction automation (Skill + Voice extractors)
3. 📋 Bootstrap marketplace test (agent discovery and first transactions) - **READY**
4. ✅ User agent on-chain registration (53 agents total) - **COMPLETE** (IDs 1-6, 7-54)

**Priority 2: Visualization & Monitoring:**
1. 📋 Contract interaction viewer (real-time Fuji events)
2. 📋 Agent network graph (D3.js - 53 nodes, 2,756 potential edges)
3. 📋 Transaction flow tracer
4. 📋 Agent directory (search/filter 53 agents)
5. 📋 Dashboard overview (metrics: agents, transactions, GLUE flow)

**Success Criteria:**
- All 53 agents registered on-chain
- Agent cards published for all user agents
- First inter-agent transactions executed
- Real-time monitoring dashboard operational
- Facilitator network monitor showing ecosystem health

---

### Sprint 5 (Future): Coinbase Payments MCP Integration ⏸️ **DEFERRED** - Awaiting Testnet Support

**Goal:** Enable fiat payments via Coinbase MCP to massively expand user base

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

**Decision:** ⏸️ **DEFER Sprint 5** until conditions met

**Reasoning:**
- 🔴 Installation blocker prevents POC completion
- 🔴 Cannot validate critical assumptions (testnet, GLUE token, fees)
- 🔴 Alternative fiat on-ramps don't support Avalanche Fuji testnet
- 🟡 Mainnet migration requires $10K-$50K security audit (premature)
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

**Recommendation:** ✅ **Continue with crypto-only payments** until revisit criteria met

**Full Analysis:**
- POC Results: `plans/COINBASE_MCP_POC_RESULTS.md`
- Alternative Fiat On-Ramps Research: `plans/ALTERNATIVE_FIAT_ONRAMPS_RESEARCH.md`
- Sprint 2.9 Summary: `plans/SPRINT_2_9_SUMMARY.md`
- GitHub Issue Draft: `plans/GITHUB_ISSUE_PAYMENTS_MCP.md`
- Original Integration Plan: `plans/COINBASE_PAYMENTS_MCP_INTEGRATION.md` (for future reference)

**Revisit Criteria:** Reconsider fiat on-ramp integration when:
- ✅ Coinbase Payments MCP Windows installer fixed
- ✅ Any major provider adds Avalanche Fuji testnet support
- ✅ Karmacadabra proves market demand (1,000+ transactions/month on testnet)
- ✅ External funding secured ($50K+ for audit + mainnet migration)
- ✅ Halliday adds Fuji testnet support (Intent Orchestration Protocol)

---

## 🏗️ Architecture

### Three-Layer System

**Layer 1: Blockchain (Avalanche Fuji)**
- GLUE Token: ERC-20 + EIP-3009 for gasless transfers
- ERC-8004 Registries: Identity, Reputation, Validation

**Layer 2: Payment Facilitator (Rust)** ✅ DEPLOYED
- x402-rs: HTTP 402 payment protocol
- Verifies EIP-712 signatures, executes `transferWithAuthorization()`
- Stateless (no DB, all state on-chain)
- Production: `https://facilitator.ultravioletadao.xyz`
- Local: `http://localhost:9000` (docker-compose)
- Wallet: 2.197 AVAX for gas fees
- Image: `ukstv/x402-facilitator:latest`

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

## 📊 Production Data Migration (MongoDB & SQLite)

### Current Status: Mock Data Approach

**October 27, 2025 - Status:**
- ✅ Mock data files created for testing (karma-hello logs + abracadabra transcripts)
- ✅ Agents configured to read from `/app/data/` directory
- ✅ Dockerfile configured to copy mock data into containers
- ❌ Docker builds blocked on Windows (fsutil walker panic - see `data/README.md`)
- 📋 MongoDB production data migration documented below (PENDING IMPLEMENTATION)

**Why Mock Data First:**
- Fast testing without database setup
- No external dependencies
- Consistent test data across environments
- Easier Docker image building (when working)
- Good for development and CI/CD

**Why Migrate to Production Databases:**
- Real data from actual Twitch streams (not static)
- Continuous updates as new streams happen
- Larger dataset (months of chat logs and transcripts)
- Better testing of query performance and edge cases
- Realistic production environment

### MongoDB Migration Guide (Karma-Hello Agent)

**Current Data Location:** `z:\ultravioleta\ai\cursor\karma-hello`

**Step 1: Set Up MongoDB Atlas (Free Tier)**

1. **Create MongoDB Atlas Account:**
   ```bash
   # Visit: https://www.mongodb.com/cloud/atlas/register
   # Create free tier cluster (M0 - 512MB storage)
   # Region: AWS us-east-1 (same as ECS for low latency)
   ```

2. **Configure Network Access:**
   ```bash
   # MongoDB Atlas → Network Access → Add IP Address
   # Option 1: Allow access from anywhere (0.0.0.0/0) - easiest for testing
   # Option 2: Add ECS NAT Gateway IPs (more secure)
   # Get NAT IPs from: terraform/ecs-fargate/outputs.tf
   ```

3. **Create Database User:**
   ```bash
   # MongoDB Atlas → Database Access → Add New Database User
   # Username: karmacadabra-agent
   # Password: Generate secure password (save to AWS Secrets Manager)
   # Role: Read and Write to any database
   ```

4. **Get Connection String:**
   ```
   mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

**Step 2: Load Production Data**

1. **Export Data from Local MongoDB:**
   ```bash
   # If data is in local MongoDB
   mongodump --uri="mongodb://localhost:27017/karma_hello" --out=./backup

   # If data is in files, use migration script
   python scripts/migrate_karma_hello_to_atlas.py \
     --source-dir="z:\ultravioleta\ai\cursor\karma-hello" \
     --atlas-uri="mongodb+srv://..." \
     --database="karma_hello"
   ```

2. **Restore to Atlas:**
   ```bash
   mongorestore --uri="mongodb+srv://..." ./backup
   ```

**Migration Script Template** (`scripts/migrate_karma_hello_to_atlas.py`):
```python
"""
Migrate karma-hello data from local files/MongoDB to MongoDB Atlas.
"""
import os
import json
from pymongo import MongoClient
from datetime import datetime

def migrate_karma_hello_data(source_dir: str, atlas_uri: str, database: str):
    """
    Migrate karma-hello chat logs from local files to MongoDB Atlas.

    Args:
        source_dir: Path to karma-hello data (z:\ultravioleta\ai\cursor\karma-hello)
        atlas_uri: MongoDB Atlas connection string
        database: Database name (e.g., 'karma_hello')
    """
    client = MongoClient(atlas_uri)
    db = client[database]

    # Create collections
    messages_collection = db['messages']
    streams_collection = db['streams']
    users_collection = db['users']

    # Create indexes for performance
    messages_collection.create_index([('timestamp', 1), ('user', 1)])
    messages_collection.create_index([('stream_id', 1)])
    users_collection.create_index([('username', 1)], unique=True)

    # Parse local files and insert
    logs_dir = os.path.join(source_dir, 'logs')
    for date_folder in os.listdir(logs_dir):
        date_path = os.path.join(logs_dir, date_folder)
        if not os.path.isdir(date_path):
            continue

        # Process full.txt for each date
        full_txt = os.path.join(date_path, 'full.txt')
        if os.path.exists(full_txt):
            stream_id = f"stream_{date_folder}"
            messages = parse_chat_log(full_txt, stream_id)

            if messages:
                messages_collection.insert_many(messages)
                print(f"[INFO] Loaded {len(messages)} messages for {date_folder}")

    print(f"[SUCCESS] Migration complete")
    print(f"  Messages: {messages_collection.count_documents({})}")
    print(f"  Streams: {streams_collection.count_documents({})}")
    print(f"  Users: {users_collection.count_documents({})}")

def parse_chat_log(file_path: str, stream_id: str) -> list:
    """Parse karma-hello chat log format."""
    messages = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Format: [MM/DD/YYYY HH:MM:SS AM/PM] username: message
            if line.strip().startswith('['):
                try:
                    timestamp_str = line[1:line.index(']')]
                    rest = line[line.index(']')+2:]
                    username = rest[:rest.index(':')]
                    message = rest[rest.index(':')+2:].strip()

                    messages.append({
                        'timestamp': datetime.strptime(timestamp_str, '%m/%d/%Y %I:%M:%S %p'),
                        'user': username,
                        'message': message,
                        'stream_id': stream_id
                    })
                except Exception as e:
                    print(f"[WARN] Failed to parse line: {line[:50]}... - {e}")
    return messages

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--atlas-uri', required=True)
    parser.add_argument('--database', default='karma_hello')
    args = parser.parse_args()

    migrate_karma_hello_data(args.source_dir, args.atlas_uri, args.database)
```

**Step 3: Update Agent Configuration**

1. **Store MongoDB URI in AWS Secrets Manager:**
   ```bash
   # Update karma-hello-agent secret
   python scripts/update_agent_secret.py \
     --agent karma-hello-agent \
     --key MONGO_URI \
     --value "mongodb+srv://..."
   ```

2. **Update Agent Code** (`agents/karma-hello/main.py`):
   ```python
   # Change from:
   config = {
       "use_local_files": True,
       "local_data_path": "/app/data/karma-hello"
   }

   # To:
   config = {
       "use_local_files": os.getenv("USE_LOCAL_FILES", "false").lower() == "true",
       "local_data_path": "/app/data/karma-hello",
       "mongo_uri": config.mongo_uri  # From AWS Secrets Manager
   }
   ```

3. **Update ECS Task Definition** (Terraform):
   ```hcl
   # terraform/ecs-fargate/ecs.tf

   resource "aws_ecs_task_definition" "karma_hello" {
     # ... existing config ...

     container_definitions = jsonencode([{
       name  = "karma-hello"
       image = "${aws_ecr_repository.agent_repos["karma-hello"].repository_url}:latest"

       environment = [
         { name = "USE_LOCAL_FILES", value = "false" },  # Switch to MongoDB
         { name = "PORT", value = "9002" },
         { name = "AGENT_NAME", value = "karma-hello-agent" },
       ]

       secrets = [
         {
           name      = "PRIVATE_KEY"
           valueFrom = "${aws_secretsmanager_secret.agent_secrets["karma-hello"].arn}:private_key::"
         },
         {
           name      = "OPENAI_API_KEY"
           valueFrom = "${aws_secretsmanager_secret.agent_secrets["karma-hello"].arn}:openai_api_key::"
         },
         {
           name      = "MONGO_URI"  # NEW: MongoDB connection
           valueFrom = "${aws_secretsmanager_secret.agent_secrets["karma-hello"].arn}:mongo_uri::"
         }
       ]
     }])
   }
   ```

4. **Deploy Updated Configuration:**
   ```bash
   cd terraform/ecs-fargate
   terraform plan -out=tfplan
   terraform apply tfplan

   # Force new deployment to pick up environment changes
   aws ecs update-service \
     --cluster karmacadabra-cluster \
     --service karma-hello \
     --force-new-deployment
   ```

**Step 4: Verify MongoDB Connection**

```bash
# Test MongoDB connection from ECS
aws ecs execute-command \
  --cluster karmacadabra-cluster \
  --task <task-id> \
  --container karma-hello \
  --command "python -c 'from pymongo import MongoClient; client = MongoClient(\"mongodb+srv://...\"); print(client.server_info())'" \
  --interactive
```

### SQLite + Cognee Migration Guide (Abracadabra Agent)

**Current Data Location:** `z:\ultravioleta\ai\cursor\abracadabra`

**Step 1: Upload SQLite Database to S3**

1. **Create S3 Bucket:**
   ```bash
   aws s3 mb s3://karmacadabra-abracadabra-data --region us-east-1
   ```

2. **Upload Database:**
   ```bash
   aws s3 cp "z:\ultravioleta\ai\cursor\abracadabra\analytics.db" \
     s3://karmacadabra-abracadabra-data/analytics.db
   ```

3. **Download in Container** (add to Dockerfile or startup script):
   ```dockerfile
   # agents/abracadabra/entrypoint.sh
   #!/bin/bash

   # Download SQLite database from S3
   if [ "$USE_LOCAL_FILES" = "false" ]; then
     echo "[INFO] Downloading production database from S3..."
     aws s3 cp s3://karmacadabra-abracadabra-data/analytics.db /app/data/analytics.db
     echo "[INFO] Database downloaded"
   fi

   # Start agent
   python main.py
   ```

**Alternative: Migrate to PostgreSQL (Recommended for Production)**

**Why PostgreSQL over SQLite:**
- Concurrent access (SQLite locks entire database)
- Better performance for large datasets
- Native JSON support for transcripts
- Integration with AWS RDS (managed, backups, replication)
- Easier scaling

**Step 2: Set Up PostgreSQL (AWS RDS)**

1. **Create RDS Instance:**
   ```bash
   # Via Terraform (recommended)
   cd terraform/ecs-fargate

   # Add to ecs.tf:
   resource "aws_db_instance" "abracadabra_postgres" {
     identifier           = "karmacadabra-abracadabra"
     engine              = "postgres"
     engine_version      = "15.4"
     instance_class      = "db.t4g.micro"  # Free tier eligible
     allocated_storage   = 20
     storage_encrypted   = true

     db_name  = "abracadabra"
     username = "abracadabra_agent"
     password = random_password.db_password.result

     vpc_security_group_ids = [aws_security_group.rds.id]
     db_subnet_group_name   = aws_db_subnet_group.rds.name

     backup_retention_period = 7
     skip_final_snapshot     = false
     final_snapshot_identifier = "abracadabra-final-snapshot"
   }
   ```

2. **Migrate Data from SQLite to PostgreSQL:**
   ```bash
   # Use pgloader for migration
   apt-get install pgloader

   pgloader \
     "z:\ultravioleta\ai\cursor\abracadabra\analytics.db" \
     "postgresql://username:password@rds-endpoint:5432/abracadabra"
   ```

3. **Update Abracadabra Agent:**
   ```python
   # Change from:
   import sqlite3
   db = sqlite3.connect('/app/data/analytics.db')

   # To:
   import psycopg2
   db = psycopg2.connect(
       host=config.postgres_host,
       database='abracadabra',
       user=config.postgres_user,
       password=config.postgres_password
   )
   ```

### Cognee Knowledge Graph Integration

**Current Data:** Cognee graph at `z:\ultravioleta\ai\cursor\abracadabra`

**Options:**

1. **Option A: S3 Backup/Restore (Simple)**
   ```bash
   # Backup Cognee data
   aws s3 sync "z:\ultravioleta\ai\cursor\abracadabra\.cognee" \
     s3://karmacadabra-abracadabra-data/cognee-graph/

   # Restore on container startup
   aws s3 sync s3://karmacadabra-abracadabra-data/cognee-graph/ \
     /app/data/.cognee
   ```

2. **Option B: Migrate to Neo4j (Production-Grade)**
   - Use AWS Neptune or self-hosted Neo4j
   - Better graph query performance
   - Native graph database features

### Benefits: Mock Data vs. Production Databases

| Feature | Mock Data | MongoDB/PostgreSQL |
|---------|-----------|-------------------|
| **Setup Time** | Minutes | Hours (first time) |
| **Data Freshness** | Static (Oct 21, 2024) | Real-time updates |
| **Data Volume** | 48 messages, 1 transcript | Months of history |
| **Testing** | Consistent, reproducible | Realistic edge cases |
| **Cost** | $0 | MongoDB Free Tier: $0<br>RDS t4g.micro: ~$15/month |
| **Performance** | Fast (local files) | Depends on query optimization |
| **Scaling** | No scaling needed | Handles thousands of streams |
| **Maintenance** | Zero | Database backups, updates |

**Recommendation:**
- **Phase 3-4 (Testing):** Use mock data for rapid iteration
- **Phase 5 (Production):** Migrate to MongoDB/PostgreSQL for real workloads
- **Phase 6 (Scale):** Add read replicas, caching (Redis), CDN for static assets

### Migration Checklist

**Karma-Hello MongoDB Migration:**
- [ ] Create MongoDB Atlas free tier cluster
- [ ] Configure network access (ECS NAT IPs)
- [ ] Create database user and store credentials in AWS Secrets Manager
- [ ] Run migration script to load data
- [ ] Update `agents/karma-hello/main.py` to support MongoDB
- [ ] Update Terraform to inject MONGO_URI from Secrets Manager
- [ ] Deploy updated task definition
- [ ] Verify agent can query MongoDB
- [ ] Test purchase flows with production data

**Abracadabra PostgreSQL Migration:**
- [ ] Create AWS RDS PostgreSQL instance (or use Atlas)
- [ ] Migrate SQLite data using pgloader
- [ ] Upload Cognee graph to S3
- [ ] Update `agents/abracadabra/main.py` to support PostgreSQL
- [ ] Add S3 sync to container startup script
- [ ] Update Terraform to inject database credentials
- [ ] Deploy updated task definition
- [ ] Verify agent can query PostgreSQL and Cognee
- [ ] Test transcript generation with production data

**Future Enhancements:**
- [ ] Implement database connection pooling
- [ ] Add read replicas for high availability
- [ ] Set up automated backups
- [ ] Monitor query performance (CloudWatch RDS metrics)
- [ ] Add Redis caching layer for frequently accessed data
- [ ] Implement data retention policies (archive old streams)

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

**Services (see docs/MONETIZATION_OPPORTUNITIES.md):**
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

**Services (see docs/MONETIZATION_OPPORTUNITIES.md):**
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

**Full catalog:** See `docs/MONETIZATION_OPPORTUNITIES.md` for 50+ services

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

## ❓ Critical Decisions

### Q1: Data Source Strategy ✅ **DECIDED**

- **Option A:** Static demo files (48 user logs from Oct 21, one-time extraction) - FASTER
- **Option B:** Connect to production MongoDB/SQLite - SCALABLE
- **Decision:** **OPTION A (Mock Data) - October 27, 2025**

**Rationale:**
- Fast iteration during testing phase
- No external database dependencies
- Docker images easier to build (when working on Linux/WSL2)
- Consistent test data across all environments

**Next Steps:**
- Continue using mock data for Phase 3-4 (testing)
- Migrate to MongoDB/PostgreSQL for Phase 5 (production workloads)
- See **"Production Data Migration (MongoDB & SQLite)"** section above for complete migration guide

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
- [x] Validator agent working (443 lines, AgentCard + CrewAI validation)
- [x] Karma-Hello agent operational (571 lines)
- [x] Abracadabra agent operational (565 lines)
- [x] Skill-Extractor agent operational (963 lines - bidirectional AI agent profiler)
- [x] Voice-Extractor agent operational (524 lines)
- [x] ERC-8004 integration complete
- [x] A2A protocol working
- [x] CrewAI crews functional
- [x] Buyer+Seller pattern - ALL agents inherit discover/buy/sell methods

### Phase 3: User Agent System 🚧 **BLOCKED** - Wallet Infrastructure Missing
- [x] User agent template created (486 lines)
- [x] 48 User agents generated (~310 lines each) - CODE ONLY
- [x] Agent factory automation
- [x] client-agents/ directory structure (49 folders)
- [ ] **48 Wallets generated** - **BLOCKING** ⚠️
- [ ] **AVAX distributed (24 AVAX)** - **BLOCKING** ⚠️
- [ ] **GLUE distributed (48,000 GLUE)** - **BLOCKING** ⚠️
- [ ] **On-chain registration (48 agents)** - **BLOCKED** ⚠️
- [ ] Agent Card auto-generator (deferred to Phase 4)
- [ ] Bootstrap marketplace test - **BLOCKED BY WALLETS** ⚠️

### Phase 4: Service Agents in Production 🔵 IN PROGRESS
- [x] Karma-Hello seller/buyer deployed (production)
- [x] Abracadabra seller/buyer deployed (production)
- [x] Skill-Extractor deployed (production)
- [x] Voice-Extractor deployed (production)
- [x] APIs with x402 working
- [ ] User agents on-chain registration (48 agents)
- [ ] Marketplace bootstrap testing

### Phase 5: Testing & Demo ✅ **COMPLETE**
- [x] End-to-end flow working (4/4 Level 3 tests passing)
- [x] Facilitator testing (6/6 tests passing)
- [x] System state verification scripts
- [x] Bidirectional transaction tests
- [x] Integration tests (Level 2)
- [ ] Demo script for 48-agent marketplace (pending)
- [ ] Video tutorial recorded (pending)
- [ ] Full documentation written (in progress)

### Phase 6: Production Deployment (AWS ECS Fargate) ✅ **COMPLETE**

**Infrastructure:**
- [x] Terraform infrastructure created (VPC, ALB, ECS, ECR, Route53, CloudWatch)
- [x] Cost-optimized configuration (~$81-96/month using Fargate Spot)
- [x] Multi-agent Docker images built and pushed to ECR
- [x] All 6 services deployed and running:
  - [x] **Facilitator** (Port 9000) - https://facilitator.ultravioletadao.xyz ⭐ NEW
  - [x] Validator (Agent ID: 4, Port 9001) - https://validator.karmacadabra.ultravioletadao.xyz
  - [x] Karma-Hello (Agent ID: 1, Port 9002) - https://karma-hello.karmacadabra.ultravioletadao.xyz
  - [x] Abracadabra (Agent ID: 2, Port 9003) - https://abracadabra.karmacadabra.ultravioletadao.xyz
  - [x] Skill-Extractor (Agent ID: 6, Port 9004) - https://skill-extractor.karmacadabra.ultravioletadao.xyz
  - [x] Voice-Extractor (Agent ID: 5, Port 9005) - https://voice-extractor.karmacadabra.ultravioletadao.xyz
- [x] AWS Secrets Manager integration (separate secret per service)
- [x] Health checks passing for all services (HTTP 200 responses)
- [x] ALB routing configured (path-based + hostname-based + root domain for facilitator)
- [x] Auto-scaling policies active (1-3 tasks per service)

**Deployment Automation (Idempotent Scripts):** ⭐ NEW
- [x] **fund-wallets.py** - Generic wallet funding from ERC-20 deployer (AWS Secrets Manager)
- [x] **build-and-push.py** - Build Docker images and push to ECR (supports prebuilt images)
- [x] **deploy-to-fargate.py** - Terraform apply + ECS force deployment
- [x] **deploy-all.py** - Master orchestration (fund → build → deploy → verify)
- [x] **test_all_endpoints.py** - Comprehensive endpoint testing (facilitator + all agents, 13 endpoints)
- [x] All scripts fully idempotent - safe to run multiple times
- [x] Comprehensive error handling and status reporting
- [x] Documentation: `scripts/README.md`

**Local Development:** ⭐ NEW
- [x] Docker-compose configuration updated with facilitator
- [x] All 6 services can run locally on ports 9000-9005
- [x] Facilitator uses prebuilt image (ukstv/x402-facilitator:latest)
- [x] Local testing guide: `docs/guides/DOCKER_GUIDE.md`

**Infrastructure as Code:**
- [x] Architecture diagrams created (5 Terraform/AWS diagrams)
- [x] Deployment documentation complete
- [x] CloudWatch monitoring configured (Logs, Metrics, Container Insights, Alarms)
- [x] DNS configured (Route53 A records + facilitator root domain)
- [x] HTTPS/SSL certificates (ACM cert with facilitator.ultravioletadao.xyz SAN)
- [x] Production testing scripts (test_production_stack.py)
- [x] User testing guide (docs/guides/GUIA_PRUEBAS_PRODUCCION.md)
- [ ] CloudWatch Dashboard fixed (validation error - non-critical)
- [ ] Disaster recovery plan documented

**Facilitator Details:**
- Image: `ukstv/x402-facilitator:latest` (prebuilt Rust x402-rs)
- Network: Avalanche Fuji testnet
- Wallet: 2.197 AVAX funded for gas fees
- Tokens: GLUE, USDC (Fuji), WAVAX (Fuji)
- Endpoints: `/health`, `/supported`, `/verify`, `/settle`

⚠️ **Note on Local Builds:** Building x402-rs from local source requires Rust nightly toolchain (Rust 2024 edition features like "let chains"). Current deployment uses prebuilt image `ukstv/x402-facilitator:latest` for stability. Future local builds will require:
```bash
rustup toolchain install nightly
rustup default nightly
cargo build --release
```

**Status:** ✅ Production-ready with HTTPS, all 6 services operational
**Cost:** ~$81-96/month (Fargate Spot + ALB + NAT Gateway)
**Testing:** All services passing health checks
**Documentation:** See `scripts/README.md` and `terraform/ecs-fargate/`

---

### Phase 7: Infrastructure Hardening & Multi-Network Expansion 🔥 **IN PROGRESS**

**Goal:** Enhance security, expand to mainnet networks, and improve operational resilience

**Multi-Network Facilitator Support:** ✅ **COMPLETE**
- [x] Base Sepolia network support added (USDC payments)
- [x] Base Mainnet network support added (USDC payments)
- [x] Avalanche Mainnet network support added (GLUE payments)
- [x] Facilitator now supports **4 networks**:
  - [x] Avalanche Fuji (testnet) - GLUE payments
  - [x] Avalanche Mainnet - GLUE payments
  - [x] Base Sepolia (testnet) - USDC payments
  - [x] Base Mainnet - USDC payments
- [x] Fixed x402 payment payload format (signature encoding + schema)
- [x] All 6 facilitator integration tests passing
- [x] Facilitator wallet separation (testnet vs mainnet)
  - [x] `karmacadabra-facilitator-testnet` → 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
  - [x] `karmacadabra-facilitator-mainnet` → 0x103040545AC5031A11E8C03dd11324C7333a13C7

**Wallet Security & Separation:** 🔄 **IN PROGRESS**

*Objective:* Separate testnet and mainnet wallets for all services to prevent accidental mainnet fund usage and improve key rotation security.

**Facilitator Wallets:**
- [x] Create `karmacadabra-facilitator-testnet` secret
- [x] Create `karmacadabra-facilitator-mainnet` secret
- [x] Migration scripts created (`scripts/split_facilitator_secrets.py`, etc.)
- [x] Documentation: `docs/migration/FACILITATOR_SECRETS_MIGRATION.md`
- [ ] Update Terraform to use network-specific secrets
- [ ] Update Docker Compose to use network-specific secrets
- [ ] Delete old `karmacadabra-facilitator` secret

**Agent Wallets:** ⏳ **PENDING**
- [ ] Create testnet/mainnet secret pairs for all agents:
  - [ ] `karmacadabra-karma-hello-testnet` / `karmacadabra-karma-hello-mainnet`
  - [ ] `karmacadabra-validator-testnet` / `karmacadabra-validator-mainnet`
  - [ ] `karmacadabra-skill-extractor-testnet` / `karmacadabra-skill-extractor-mainnet`
  - [ ] `karmacadabra-voice-extractor-testnet` / `karmacadabra-voice-extractor-mainnet`
  - [ ] `karmacadabra-abracadabra-testnet` / `karmacadabra-abracadabra-mainnet`
  - [ ] `karmacadabra-client-testnet` / `karmacadabra-client-mainnet`
- [ ] Update agent code to load network-specific keys
- [ ] Update Terraform to inject network-specific secrets
- [ ] Migration guide for agent wallets (`AGENT_WALLET_MIGRATION.md`)

**Security Hardening:**
- [ ] Implement key rotation schedule (30-90 days)
- [ ] Set up CloudWatch alarms for low wallet balances
- [ ] Implement wallet balance monitoring dashboard
- [ ] Add audit logging for all wallet operations
- [ ] Document disaster recovery procedures
- [ ] **Migrate from AWS Secrets Manager to HashiCorp Vault**
  - **Why:** Better secrets rotation, dynamic credentials, fine-grained access control, comprehensive audit logging
  - **Current:** All agent keys stored in AWS Secrets Manager (system agents: top-level, user agents: under `user-agents` key)
  - **Target:** HashiCorp Vault with dynamic secrets, automatic rotation, and enhanced security
  - **Benefits:**
    - Dynamic database credentials (rotate automatically)
    - Time-limited tokens for agent authentication
    - Detailed audit trail of all secret access
    - Policy-based access control (agents can only read own secrets)
    - Secrets versioning and rollback
    - Better integration with Kubernetes/ECS
  - **Tasks:**
    - [ ] Set up HashiCorp Vault cluster (Cloud or self-hosted)
    - [ ] Design secret hierarchy and access policies
    - [ ] Migrate system agent secrets (5 agents)
    - [ ] Migrate user agent secrets (48 agents)
    - [ ] Update `shared/secrets_manager.py` to support Vault
    - [ ] Implement Vault token refresh mechanism
    - [ ] Test failover and backup procedures
    - [ ] Document Vault operations and disaster recovery
  - **Priority:** Medium (current AWS setup works, but Vault provides production-grade features)
  - **Estimated effort:** 2-3 weeks

**Infrastructure Improvements:**
- [ ] CloudWatch Dashboard validation error fix
- [ ] Disaster recovery plan documentation
- [ ] Backup and restore procedures for secrets
- [ ] Network failover testing (testnet ↔ mainnet)

**Benefits:**
- 🔒 Improved security: Mainnet keys isolated from testnet operations
- 🔄 Easier key rotation: Rotate testnet keys without affecting mainnet
- 💰 Cost savings: Prevent accidental mainnet transactions during testing
- 🎯 Better compliance: Separate environments for audit purposes
- 🚀 Mainnet readiness: Infrastructure prepared for production traffic

**Status:** 25% Complete (facilitator wallets separated, agent wallets pending)

**Documentation:**
- `docs/migration/FACILITATOR_SECRETS_MIGRATION.md` - Complete facilitator wallet separation guide
- `scripts/create_testnet_facilitator_secret.py` - Testnet secret creation
- `scripts/split_facilitator_secrets.py` - Migration automation

---

**🎉 End of Master Plan**

**Version:** 1.6.2 | **Author:** Ultravioleta DAO | **License:** MIT
