# 🔍 SPRINT 2.9 & SPRINT 4 REVISION: x402scan + x402sync Integration

## Executive Summary

**Strategic Value:**

The integration of x402scan (frontend explorer) and x402sync (blockchain indexer) into Karmacadabra represents a **transformational upgrade** from a basic microeconomy to a **professionally observable, community-discoverable ecosystem**. This integration solves three critical gaps:

1. **Visibility Gap**: Currently, all transactions happen on-chain but there's no easy way to view the microeconomy in action. x402scan provides a production-ready explorer with embedded wallet, resource discovery, and real-time transaction tracking.

2. **Discovery Gap**: With 54 agents planned (6 system + 48 user agents), manual discovery via A2A protocol alone is insufficient. x402scan creates a **marketplace directory** where agents are automatically indexed and searchable.

3. **Trust Gap**: New buyers need to evaluate seller reputation. x402scan + x402sync creates a **public reputation ledger** by indexing all ERC-8004 events, making agent ratings, validations, and transaction history transparent and queryable.

**Why This Matters for Karmacadabra:**

- **Livestream Demonstrations**: x402scan provides a stunning visual interface to showcase the microeconomy live on stream (currently showing terminal outputs is less engaging)
- **User Adoption**: Embedded wallet in x402scan means anyone can interact with agents WITHOUT needing to install MetaMask or manage private keys
- **Network Effects**: Public visibility accelerates growth - agents see other agents' success, encouraging participation
- **Data-Driven Decisions**: Historical analytics enable agents to optimize pricing, service offerings, and target buyers
- **Community Growth**: Open explorer attracts developers, researchers, and integrators to build on Karmacadabra

**Synergies with 6 System Agents:**

| Agent | How x402scan Helps |
|-------|-------------------|
| **Validator** | Public validation history builds credibility; buyers can see validation success rate before requesting |
| **Karma-Hello** | Service catalog with pricing comparison; buyers discover chat log services by filtering "chat analytics" |
| **Abracadabra** | Transcript marketplace with sample quality scores; buyers compare prices per minute of audio |
| **Voice-Extractor** | Profile extraction showcase - buyers browse before/after examples from indexed transactions |
| **Skill-Extractor** | Skill marketplace - agents discover which skills are in-demand by analyzing transaction volumes |
| **Client-Agent** | Reference implementation - new agents learn payment flows by observing Client-Agent's transaction history |

**What New Use Cases Does It Enable?**

1. **Agent Onboarding**: New agents browse x402scan to understand market rates, popular services, and successful seller strategies
2. **Reputation Gaming Prevention**: Public indexing makes wash trading visible - validators can detect suspicious patterns
3. **Economic Research**: Researchers query x402sync database for microeconomy analysis (velocity of GLUE, agent liquidity, service demand elasticity)
4. **Developer APIs**: Third-party apps can integrate x402sync data (e.g., Discord bot showing real-time agent activity)
5. **Visualization for 48 User Agents**: When deploying 48 user agents, x402scan becomes the **control panel** to monitor bootstrap process, track self-discovery purchases, and visualize emerging network effects

---

## Architecture Integration

### Updated Layer Model

The introduction of x402scan/x402sync creates a new **observability layer** between the blockchain and agents:

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: BLOCKCHAIN (Avalanche Fuji Testnet)                   │
│ • GLUE Token (0x3D19A80b...)                                    │
│ • Identity Registry (0xB0a405a7...)                             │
│ • Reputation Registry (0x932d32194...)                          │
│ • Validation Registry (0x9aF4590035...)                         │
│ • Transaction Logger (0x85ea82dDc...)                           │
│                                                                 │
│ Events Emitted:                                                 │
│ • Transfer(from, to, value)                                     │
│ • TransferWithAuthorization(from, to, value, nonce)             │
│ • AgentRegistered(agentId, domain, address)                     │
│ • FeedbackSubmitted(from, to, rating, comment)                  │
│ • ValidationRequested(requestId, dataHash, buyer, seller)       │
│ • ValidationResponded(requestId, score, validator)              │
│ • MessageLogged(sender, recipient, message)                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (blockchain events)
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2.5: INDEXING & OBSERVABILITY (NEW!)                     │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ x402sync (TypeScript Indexer)                           │   │
│ │ • Trigger.dev event-driven jobs                         │   │
│ │ • Prisma ORM for data modeling                          │   │
│ │ • PostgreSQL database                                   │   │
│ │ • Indexes: GLUE transfers, agent registrations,         │   │
│ │   reputation updates, validations, messages             │   │
│ │ • REST API: /api/agents, /api/transactions, /api/stats  │   │
│ └─────────────────────────────────────────────────────────┘   │
│                              ↓ (indexed data)                   │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ x402scan (Next.js Frontend)                             │   │
│ │ • Resource discovery (/add_resources=true)              │   │
│ │ • Agent directory (search, filter, sort)                │   │
│ │ • Embedded crypto wallet (GLUE payments)                │   │
│ │ • Transaction explorer (real-time feed)                 │   │
│ │ • Reputation dashboard (ERC-8004 visualization)         │   │
│ │ • Analytics charts (volume, popularity, pricing)        │   │
│ │ • Facilitator registry (x402-rs endpoint)               │   │
│ │ • Deployed: scan.karmacadabra.ultravioletadao.xyz       │   │
│ └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (agent discovery)
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: PAYMENT FACILITATOR (Rust)                            │
│ • x402-rs (facilitator.ultravioletadao.xyz)                     │
│ • Verifies EIP-712 signatures                                   │
│ • Executes transferWithAuthorization()                          │
│ • Stateless (no database - x402sync handles historical data)    │
│                                                                 │
│ NEW: Emit events for x402sync to index                         │
│ • Settlement completed events                                   │
│ • Payment verification events                                   │
│ • Facilitator fee events (future)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (payment verification)
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: AI AGENTS (Python + CrewAI)                           │
│ • 6 System Agents + 48 User Agents                              │
│ • Each publishes A2A AgentCard                                  │
│ • Each auto-registers in x402scan upon startup                  │
│ • Each tracks analytics via x402sync API                        │
└─────────────────────────────────────────────────────────────────┘
```

**Key Architectural Insights:**

1. **x402-rs remains stateless**: It doesn't need a database. All historical data lives in x402sync's PostgreSQL.

2. **x402sync becomes single source of truth**: All queries for historical data go to x402sync API, not directly to blockchain (faster, cheaper).

3. **x402scan is THE public interface**: Replaces need for custom visualization dashboard in Sprint 4.

4. **Agents auto-register**: When agents start, they call `POST x402scan/api/resources/submit` with their AgentCard URL.

5. **Embedded wallet flow**: Users browse x402scan → find Karma-Hello → click "Buy Chat Logs" → embedded wallet signs EIP-3009 → payment succeeds → data returned. All without leaving browser.

---

## Chronological Placement Decision

### **RECOMMENDATION: Option D (Hybrid Approach) - STRONGLY RECOMMENDED**

**Justification:**

After analyzing all four options against Karmacadabra's unique constraints (livestream demonstrations, 48 user agent rollout, AWS-based infrastructure, granular commits), Option D emerges as optimal:

**Why Option D (Hybrid)?**

1. **Deploy x402sync NOW (Sprint 2.9)**
   - ✅ **Zero regret move**: Start indexing immediately while Sprint 2 is fresh
   - ✅ **Data from day 1**: When 48 user agents launch, we have complete historical context
   - ✅ **Small scope**: x402sync deployment is ~3-5 days (fork, configure, deploy indexer)
   - ✅ **Low risk**: Indexer runs independently - if it breaks, agents still work
   - ✅ **Testing value**: Validate indexing accuracy NOW with 6 system agents before scaling to 54

2. **Deploy x402scan in Sprint 4 (Replace/Enhance Custom Viz)**
   - ✅ **Production-ready UI**: Merit-Systems has battle-tested code (85 stars, 8 contributors)
   - ✅ **Embedded wallet**: No need to build payment UI from scratch
   - ✅ **Community credibility**: x402scan is recognized in x402 ecosystem - instant legitimacy
   - ✅ **Time savings**: Replacing Sprint 4's custom D3.js graphs with x402scan saves 2-3 weeks
   - ✅ **Livestream wow factor**: Professional explorer is more impressive than custom charts

**Timeline Comparison:**

| Option | x402sync Start | x402scan Launch | User Agents Launch | Total Duration |
|--------|---------------|----------------|-------------------|---------------|
| A | Week 5 | Week 5 | Week 8 | 8 weeks |
| B | Week 7 | Week 7 | Week 5 | 7 weeks |
| C | Week 7 | Week 9 | Week 5 | 9 weeks |
| **D** | **Week 3** | **Week 7** | **Week 5** | **7 weeks** |

**Option D is fastest while preserving data completeness.**

---

## Detailed Implementation Phases

### Sprint 2.9: x402sync Indexer Deployment (1 Week - October 24-31, 2025)

**Goal:** Deploy blockchain indexer to capture all Karmacadabra transactions from day 1

**Duration:** 5-7 days

**Prerequisites:**
- ✅ Phase 1 complete (contracts deployed to Fuji)
- ✅ Sprint 2 complete (6 agents operational and tested)
- ✅ AWS infrastructure ready (EC2, RDS, or Render.com account)

**Tasks:**

#### Day 1: Setup & Configuration

- [ ] **Task 2.9.1**: Fork x402sync repository
  - Fork https://github.com/merit-Systems/x402sync to ultravioletadao GitHub
  - Clone to local: `Z:\ultravioleta\dao\karmacadabra\x402sync`
  - Create branch: `feature/karmacadabra-integration`
  - **Estimated time**: 30 minutes

- [ ] **Task 2.9.2**: Configure Avalanche Fuji support
  - Edit `src/config/chains.ts` to add Fuji testnet configuration
  - Add to supported chains in `src/config/index.ts`
  - **Estimated time**: 1 hour
  - **Test**: `npm run build` should succeed

- [ ] **Task 2.9.3**: Design Prisma schema for Karmacadabra
  - Create `prisma/schema.prisma` (see Database Schema section below)
  - **Estimated time**: 2-3 hours
  - **Test**: `npx prisma validate` should pass

#### Day 2: Database & Contract Configuration

- [ ] **Task 2.9.4**: Setup PostgreSQL database
  - Create RDS PostgreSQL instance or Render.com database
  - Save connection string to AWS Secrets Manager
  - **Estimated time**: 1 hour
  - **Test**: `psql $DATABASE_URL -c "SELECT 1"` should succeed

- [ ] **Task 2.9.5**: Configure contract addresses
  - Edit `src/config/contracts/karmacadabra.ts` with deployed contract addresses
  - **Estimated time**: 30 minutes

- [ ] **Task 2.9.6**: Add contract ABIs
  - Copy ABIs from Karmacadabra contract builds
  - Place in `src/abis/karmacadabra/`
  - **Estimated time**: 1 hour

#### Day 3-4: Trigger.dev Jobs Implementation

- [ ] **Task 2.9.7**: Create GLUE Token event indexing job
  - Index Transfer and TransferWithAuthorization events
  - **Estimated time**: 3-4 hours

- [ ] **Task 2.9.8**: Create Identity Registry event indexing job
  - Index AgentRegistered and AgentUpdated events
  - **Estimated time**: 2-3 hours

- [ ] **Task 2.9.9**: Create Reputation Registry event indexing job
  - Index FeedbackSubmitted events
  - **Estimated time**: 2-3 hours

- [ ] **Task 2.9.10**: Create Validation Registry event indexing job
  - Index ValidationRequested and ValidationResponded events
  - **Estimated time**: 3-4 hours

- [ ] **Task 2.9.11**: Create Transaction Logger event indexing job
  - Index MessageLogged events
  - **Estimated time**: 2-3 hours

#### Day 5: API & Deployment

- [ ] **Task 2.9.12**: Create REST API endpoints
  - Implement /api/agents, /api/transactions, /api/validations, /api/stats
  - **Estimated time**: 4-5 hours

- [ ] **Task 2.9.13**: Setup environment variables
  - Create `.env` with database URL, RPC URL, etc.
  - **Estimated time**: 30 minutes

- [ ] **Task 2.9.14**: Deploy to hosting platform
  - Deploy to Render.com or AWS EC2
  - **Estimated time**: 2-3 hours

#### Day 6-7: Testing & Validation

- [ ] **Task 2.9.15**: Historical data backfill
  - Index all events from contract deployment to current
  - **Estimated time**: 3 hours

- [ ] **Task 2.9.16**: Data validation
  - Compare indexed data vs on-chain (100% match required)
  - **Estimated time**: 2 hours

- [ ] **Task 2.9.17**: Performance testing
  - Load test API endpoints (target <200ms p95 latency)
  - **Estimated time**: 1 hour

- [ ] **Task 2.9.18**: Monitoring setup
  - Add health check, uptime monitoring, alerts
  - **Estimated time**: 1 hour

**Deliverables:**

1. ✅ Deployed x402sync instance at `https://x402sync.karmacadabra.ultravioletadao.xyz`
2. ✅ PostgreSQL database with complete historical data
3. ✅ REST API responding <200ms
4. ✅ All 5 contract event types indexed
5. ✅ 100% data accuracy
6. ✅ Monitoring operational

**Success Criteria:**

- ✅ 100% of on-chain events indexed
- ✅ <1 minute indexing latency
- ✅ API responds <200ms
- ✅ All 6 system agents visible
- ✅ At least 10 test transactions indexed

**Estimated Cost:** $14/month (Render.com Starter)

---

### Sprint 4 (Revised): x402scan Frontend Deployment (2 Weeks - November 10-24, 2025)

**Goal:** Deploy production-ready blockchain explorer for Karmacadabra ecosystem

**Duration:** 10-12 days

**Prerequisites:**
- ✅ Sprint 2.9 complete (x402sync operational)
- ✅ Sprint 3 complete (48 user agents deployed)
- ✅ Domain configured: `scan.karmacadabra.ultravioletadao.xyz`

**Tasks:**

#### Week 1: Fork, Customize & Brand

**Day 1-2: Repository Setup**

- [ ] **Task 4.1**: Fork x402scan repository
  - Fork https://github.com/Merit-Systems/x402scan
  - Clone to local
  - Install dependencies
  - **Estimated time**: 1 hour

- [ ] **Task 4.2**: Configure environment variables
  - Create `.env.local` with API URLs, chain ID, etc.
  - **Estimated time**: 30 minutes

- [ ] **Task 4.3**: Customize branding
  - Update logo, favicon, color scheme
  - Karmacadabra purple theme
  - **Estimated time**: 2-3 hours

**Day 3-4: Facilitator & Agent Integration**

- [ ] **Task 4.4**: Configure facilitator in x402scan
  - Add Ultravioleta DAO facilitator to registry
  - **Estimated time**: 1 hour

- [ ] **Task 4.5**: Build agent directory component
  - Search, filter, sort by reputation/volume
  - **Estimated time**: 5-6 hours

- [ ] **Task 4.6**: Build service catalog component
  - List all services, price comparison
  - **Estimated time**: 4-5 hours

**Day 5: Embedded Wallet Integration**

- [ ] **Task 4.7**: Integrate embedded wallet for GLUE payments
  - RainbowKit + wagmi configuration
  - **Estimated time**: 3-4 hours

- [ ] **Task 4.8**: Implement EIP-3009 payment signing
  - Sign payment authorizations
  - **Estimated time**: 2-3 hours

- [ ] **Task 4.9**: Build "Buy Now" flow
  - Complete purchase flow with modal, loading states
  - **Estimated time**: 4-5 hours

#### Week 2: Dashboards & Analytics

**Day 6-7: Reputation Visualization**

- [ ] **Task 4.10**: Build ERC-8004 reputation dashboard
  - Rating distribution, timeline, feedback list
  - **Estimated time**: 5-6 hours

- [ ] **Task 4.11**: Build validation history viewer
  - Show validations performed/received
  - **Estimated time**: 4-5 hours

**Day 8: Transaction Analytics**

- [ ] **Task 4.12**: Build transaction explorer
  - Real-time feed, filters, export
  - **Estimated time**: 6-7 hours

- [ ] **Task 4.13**: Build analytics dashboard
  - Economy stats, agent leaderboards, service popularity
  - **Estimated time**: 8-10 hours

**Day 9: Polish & Testing**

- [ ] **Task 4.14**: Build agent profile pages
  - Overview, services, reputation, transactions
  - **Estimated time**: 4-5 hours

- [ ] **Task 4.15**: Responsive design
  - Test on mobile, tablet
  - **Estimated time**: 3-4 hours

- [ ] **Task 4.16**: Performance optimization
  - Next.js ISR, image optimization, pagination
  - **Estimated time**: 3-4 hours

**Day 10: Deployment**

- [ ] **Task 4.17**: Deploy to Vercel
  - Connect GitHub, configure domain
  - **Estimated time**: 1 hour

- [ ] **Task 4.18**: DNS configuration
  - Add CNAME record
  - **Estimated time**: 30 minutes

- [ ] **Task 4.19**: Final testing checklist
  - Agent directory, service catalog, embedded wallet, etc.
  - **Estimated time**: 2-3 hours

- [ ] **Task 4.20**: Documentation & launch
  - Update README, write blog post, share on social media
  - **Estimated time**: 2-3 hours

**Deliverables:**

1. ✅ Live x402scan at `https://scan.karmacadabra.ultravioletadao.xyz`
2. ✅ Embedded wallet supporting GLUE
3. ✅ Agent directory (54 agents)
4. ✅ Service catalog (50+ services)
5. ✅ Reputation dashboards
6. ✅ Transaction explorer
7. ✅ Analytics dashboard
8. ✅ Mobile responsive
9. ✅ Complete purchase flow

**Success Criteria:**

- ✅ All 54 agents discoverable
- ✅ <2s page load (Lighthouse >90)
- ✅ Real-time updates <30s
- ✅ Embedded wallet works
- ✅ 100% reputation data visible
- ✅ Mobile responsive
- ✅ Zero TypeScript errors

**Estimated Cost:** $20/month (Vercel Pro) or $0 (Hobby tier for MVP)

---

### Sprint 4.5: Advanced Analytics & Features (1 Week - November 25 - December 1, 2025)

**Goal:** Add Karmacadabra-specific features beyond generic x402scan

**Duration:** 5-7 days

**Tasks:**

- [ ] **Task 4.5.1**: Real-time WebSocket feed (4-5 hours)
- [ ] **Task 4.5.2**: Agent reputation scoring algorithm (3-4 hours)
- [ ] **Task 4.5.3**: Service recommendation engine (5-6 hours)
- [ ] **Task 4.5.4**: Historical pricing charts (4-5 hours)
- [ ] **Task 4.5.5**: Economic analytics with ML (6-8 hours)
- [ ] **Task 4.5.6**: API documentation (OpenAPI/Swagger) (4-5 hours)
- [ ] **Task 4.5.7**: Public API keys with rate limiting (5-6 hours)
- [ ] **Task 4.5.8**: Marketplace matching suggestions (6-8 hours)
- [ ] **Task 4.5.9**: Multi-chain preparation (4-5 hours)

**Deliverables:**

1. ✅ Real-time transaction feed
2. ✅ Advanced reputation scoring
3. ✅ Service recommendations
4. ✅ Historical pricing charts
5. ✅ Economic analytics
6. ✅ API documentation
7. ✅ Public API keys
8. ✅ Marketplace matching
9. ✅ Multi-chain support

---

## Database Schema Design (Prisma)

Complete schema at `x402sync/prisma/schema.prisma`:

```prisma
// Karmacadabra x402sync Database Schema

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Agent {
  id                Int      @id @default(autoincrement())
  agentId           Int      @unique
  address           String   @unique
  domain            String   @unique
  name              String?
  agentType         AgentType
  glueBalance       BigInt   @default(0)
  registeredAt      DateTime
  updatedAt         DateTime @updatedAt
  lastActiveAt      DateTime?

  totalTransactions Int      @default(0)
  totalGlueSent     BigInt   @default(0)
  totalGlueReceived BigInt   @default(0)
  averageRating     Float?
  reputationScore   Float    @default(0)
  validationSuccessRate Float? @default(0)

  agentCardUrl      String?
  agentCardData     Json?

  sentTransfers     Transfer[] @relation("Sender")
  receivedTransfers Transfer[] @relation("Receiver")
  feedbackGiven     Reputation[] @relation("FeedbackFrom")
  feedbackReceived  Reputation[] @relation("FeedbackTo")
  validationsPerformed Validation[] @relation("Validator")
  validationsReceived  Validation[] @relation("Validated")
  services          Service[]

  @@index([agentType])
  @@index([reputationScore])
  @@index([totalTransactions])
}

enum AgentType {
  SYSTEM
  USER
}

model Transfer {
  id              Int      @id @default(autoincrement())
  txHash          String   @unique
  blockNumber     Int
  blockTimestamp  DateTime
  fromAddress     String
  toAddress       String
  amount          BigInt
  nonce           String?
  isEIP3009       Boolean  @default(false)

  sender          Agent    @relation("Sender", fields: [fromAddress], references: [address])
  receiver        Agent    @relation("Receiver", fields: [toAddress], references: [address])
  serviceTransaction ServiceTransaction?

  @@index([fromAddress])
  @@index([toAddress])
  @@index([blockTimestamp])
  @@index([blockNumber])
}

model Reputation {
  id              Int      @id @default(autoincrement())
  txHash          String   @unique
  blockNumber     Int
  blockTimestamp  DateTime
  fromAddress     String
  toAddress       String
  rating          Int
  comment         String?
  feedbackType    FeedbackType

  from            Agent    @relation("FeedbackFrom", fields: [fromAddress], references: [address])
  to              Agent    @relation("FeedbackTo", fields: [toAddress], references: [address])

  @@index([toAddress])
  @@index([fromAddress])
  @@index([rating])
  @@index([blockTimestamp])
}

enum FeedbackType {
  BUYER_TO_SELLER
  SELLER_TO_BUYER
}

model Validation {
  id              Int      @id @default(autoincrement())
  requestId       Int      @unique
  requestTxHash   String
  requestBlockNumber Int
  requestTimestamp DateTime
  dataHash        String
  buyerAddress    String
  sellerAddress   String
  responseTxHash  String?
  responseBlockNumber Int?
  responseTimestamp DateTime?
  validatorAddress String?
  score           Int?
  metadata        String?
  status          ValidationStatus @default(PENDING)
  durationSeconds Int?

  validator       Agent?   @relation("Validator", fields: [validatorAddress], references: [address])
  seller          Agent    @relation("Validated", fields: [sellerAddress], references: [address])

  @@index([requestId])
  @@index([validatorAddress])
  @@index([sellerAddress])
  @@index([status])
  @@index([score])
}

enum ValidationStatus {
  PENDING
  COMPLETED
  EXPIRED
}

model Service {
  id              Int      @id @default(autoincrement())
  agentId         Int
  skillId         String
  name            String
  description     String?
  category        ServiceCategory
  priceGlue       BigInt
  priceUsd        Float?
  inputSchema     Json?
  outputSchema    Json?
  totalSales      Int      @default(0)
  totalRevenue    BigInt   @default(0)
  averageRating   Float?

  agent           Agent    @relation(fields: [agentId], references: [agentId])
  transactions    ServiceTransaction[]

  @@unique([agentId, skillId])
  @@index([category])
  @@index([priceGlue])
  @@index([totalSales])
}

enum ServiceCategory {
  CHAT_LOGS
  TRANSCRIPTS
  VOICE_PROFILES
  SKILL_PROFILES
  VALIDATION
  ANALYTICS
  OTHER
}

model ServiceTransaction {
  id              Int      @id @default(autoincrement())
  transferId      Int      @unique
  serviceId       Int?
  serviceName     String?
  serviceEndpoint String?
  requestParams   Json?
  validationId    Int?
  responseTime    Int?
  dataSize        Int?

  transfer        Transfer @relation(fields: [transferId], references: [id])
  service         Service? @relation(fields: [serviceId], references: [id])

  @@index([serviceId])
}

model IndexerState {
  id              Int      @id @default(autoincrement())
  contractAddress String   @unique
  chainId         Int
  lastIndexedBlock Int     @default(0)
  lastUpdated     DateTime @updatedAt

  @@unique([contractAddress, chainId])
}

model FacilitatorRegistry {
  id              Int      @id @default(autoincrement())
  name            String
  url             String   @unique
  chainId         Int
  supportedTokens Json
  description     String?
  totalSettlements Int     @default(0)
  totalVolume     BigInt   @default(0)
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  @@index([chainId])
}

model DailyStats {
  id              Int      @id @default(autoincrement())
  date            DateTime @unique @db.Date
  totalTransactions Int
  totalVolume     BigInt
  activeAgents    Int
  totalServiceCalls Int
  mostPopularService String?
  totalValidations Int
  averageValidationScore Float?
  glueVelocity    Float?
  createdAt       DateTime @default(now())

  @@index([date])
}
```

---

## Integration Impact Analysis

### Smart Contracts - No Changes Needed ✅

All events already emitted. Optional enhancement: Add `ServicePurchased` event to Transaction Logger.

### x402-rs Facilitator - Minimal Changes

Optional enhancements:
1. Settlement event logging
2. `/metrics` endpoint
3. Enhanced health check

### Agent Code (Python) - Minor Updates

Add to `shared/base_agent.py`:

```python
def _register_with_x402scan(self):
    """Submit AgentCard to x402scan for discovery."""
    try:
        x402scan_url = "https://scan.karmacadabra.ultravioletadao.xyz/api/resources/submit"

        payload = {
            "url": f"https://{self.agent_domain}/.well-known/agent-card",
            "type": "agent",
            "chain_id": 43113,
            "metadata": {
                "agent_id": self.agent_id,
                "agent_type": "system",
                "services": self.get_service_list()
            }
        }

        response = httpx.post(x402scan_url, json=payload, timeout=10.0)

        if response.status_code == 200:
            self.logger.info(f"[x402scan] Registered AgentCard: {self.agent_domain}")
        else:
            self.logger.warning(f"[x402scan] Registration failed: {response.status_code}")
    except Exception as e:
        self.logger.warning(f"[x402scan] Registration error: {e}")
```

**Impact**: ~15 minutes to add to base class, all agents inherit.

---

## Timeline

| Week | Phase | Key Deliverables |
|------|-------|-----------------|
| **Week 3** (Oct 24-31) | **Sprint 2.9: x402sync** | Indexer deployed, all events indexed |
| **Week 4** (Nov 1-8) | Sprint 3 prep | User agent profiles extracted |
| **Week 5-6** (Nov 9-22) | **Sprint 3: User Agents** | 48 user agents deployed |
| **Week 7-8** (Nov 23-Dec 6) | **Sprint 4: x402scan** | Explorer live, embedded wallet |
| **Week 9** (Dec 7-13) | **Sprint 4.5: Advanced** | Real-time feed, API docs |

---

## Budget Estimate

### Monthly Recurring Costs

| Component | Provider | Monthly Cost |
|-----------|----------|-------------|
| x402sync Hosting | Render.com | $7 |
| PostgreSQL Database | Render.com | $7 |
| x402scan Hosting | Vercel Hobby (free) or Pro | $0-20 |
| Trigger.dev | Free tier | $0 |
| Monitoring | UptimeRobot | $0 |
| **TOTAL (MVP)** | | **$14/month** |
| **TOTAL (Production)** | | **$34/month** |

### Development Time

| Sprint | Duration | Hours |
|--------|----------|-------|
| Sprint 2.9 (x402sync) | 1 week | 40 hours |
| Sprint 4 (x402scan) | 2 weeks | 80-120 hours |
| Sprint 4.5 (Advanced) | 1 week | 40 hours |
| **TOTAL** | **4 weeks** | **160-200 hours** |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Merit-Systems stops maintaining x402scan | Medium | High | Fork early, contribute back, maintain independent fork |
| Fork divergence from upstream | High | Medium | Document customizations separately, sync regularly |
| PostgreSQL costs scale | Low | Medium | Use free tier for MVP, implement data retention |
| x402sync downtime breaks economy | Low | High | Agents work independently, setup monitoring |
| Blockchain reorgs on Fuji | Medium | Low | Wait for confirmations, reorg detection |
| Database scaling (100k+ txs) | Medium | Medium | Pagination, indexes, archiving, read replicas |
| API abuse | Medium | Medium | Rate limiting, API keys, Cloudflare protection |
| Embedded wallet security | Medium | High | Use audited libraries, transaction limits, warnings |

---

## Success Metrics

### Technical Metrics

| Metric | Target |
|--------|--------|
| Indexing latency | <1 minute |
| Query performance | <200ms (p95) |
| Uptime | 99.9% |
| Data completeness | 100% |
| Page load time | <2s (Lighthouse >90) |

### User Metrics

| Metric | Target (Month 1) |
|--------|-----------------|
| Daily active users | 50+ |
| Agent profile views | 100+ |
| Wallet transactions | 20+ |
| API calls | 1,000+/week |
| GitHub stars | 20+ |

### Business Metrics

| Metric | Target |
|--------|--------|
| Transaction increase | +50% |
| Facilitator submissions | 2+ |
| Developer adoption | 3+ external apps |
| Livestream engagement | +30% viewers |

---

## Community & Open Source Strategy

### Contributing Back

1. **Avalanche support to upstream** - PR to Merit-Systems (4-6 hours)
2. **ERC-8004 integration** - Generic reputation visualization (8-10 hours)
3. **Embedded wallet improvements** - Better UX (6-8 hours)
4. **Documentation** - Customization tutorial (4-5 hours)

### Sharing Karmacadabra Fork

- Repository: `ultravioletadao/x402scan-karmacadabra`
- MIT license, acknowledge Merit-Systems
- Blog post: "Introducing Karmacadabra Explorer"
- Distribution: Twitter, Discord, Hacker News

---

## Future Enhancements (Post-MVP)

### Phase 5+ Features

- Real-time WebSocket feed
- Advanced analytics (ML predictions, cohort analysis)
- Marketplace features (escrow, subscriptions, bundles)
- Developer tools (GraphQL API, SDKs, CLI)
- Governance (DAO voting, dispute resolution)
- Multi-chain support (mainnet, Ethereum L2s)
- Mobile app (React Native)
- Enterprise (white-label, SLA tiers)

---

## Next Steps (Immediate Action Items)

### This Week (October 24-31, 2025)

**Day 1 (Today):**
- [ ] Review this sub master plan with team
- [ ] Approve Option D (Hybrid Approach)
- [ ] Create GitHub issues for Sprint 2.9 tasks
- [ ] Setup Render.com or AWS RDS account

**Day 2-3:**
- [ ] Fork x402sync repository
- [ ] Design Prisma schema
- [ ] Configure Avalanche Fuji support
- [ ] Setup PostgreSQL database

**Day 4-5:**
- [ ] Implement Trigger.dev jobs
- [ ] Create REST API endpoints
- [ ] Deploy to Render.com

**Day 6-7:**
- [ ] Historical data backfill
- [ ] Data validation
- [ ] Performance testing
- [ ] Monitoring setup

**By October 31:**
✅ x402sync operational, indexing all transactions, API responding <200ms

---

**End of Sub Master Plan**

---

**Document Metadata:**

- **Version**: 1.0.0
- **Date**: October 24, 2025
- **Estimated Read Time**: 45-60 minutes
- **Integration with MASTER_PLAN.md**: Insert after Sprint 2.8

---

## Summary: What You're Getting

**x402sync (Backend):**
- TypeScript blockchain indexer
- Prisma ORM + PostgreSQL
- Trigger.dev event-driven jobs
- REST API for historical data
- **Cost**: $14/month
- **Effort**: 1 week (40 hours)

**x402scan (Frontend):**
- Next.js web explorer
- Embedded wallet (RainbowKit)
- Agent directory + service marketplace
- Reputation dashboards
- Transaction explorer
- Analytics charts
- **Cost**: $20/month (or $0 with Hobby tier)
- **Effort**: 2 weeks (80-120 hours)

**Total Investment:**
- **Time**: 4 weeks
- **Money**: $34/month recurring
- **Result**: Production-ready explorer with embedded wallet, complete visibility into microeconomy, professional interface for livestreams, API for developers
