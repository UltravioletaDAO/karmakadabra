# Agent Collaboration Protocol

This document defines how specialized Claude Code agents collaborate on the Karmacadabra project.

## Agent Roster

### 1. future-architect
**Specialization**: Protocol-level architecture (x402-rs, A2A, ERC-8004, multi-chain)
**Location**: `.claude/agents/future-architect.md`

**Expertise**:
- x402-rs facilitator (Rust, stateless design)
- A2A discovery protocol (.well-known/agent-card)
- ERC-8004 registries (Identity, Reputation, Validation)
- EIP-3009 gasless payments + EIP-712 signatures
- Multi-chain integration strategy

**Invoke When**:
- Adding new blockchain support
- Debugging signature verification issues
- Designing A2A protocol extensions
- Protocol-level security analysis
- Facilitator architecture decisions

### 2. terraform-specialist
**Specialization**: Infrastructure as Code (AWS ECS Fargate, cost optimization)
**Location**: `.claude/agents/terraform-specialist.md`

**Expertise**:
- Cost-optimized ECS Fargate deployments ($79-96/month target)
- Multi-service orchestration (facilitator + Python agents)
- CloudWatch monitoring, ALB routing, VPC networking
- Secrets Manager integration, IAM security
- Blockchain-aware infrastructure (RPC endpoints, gas tracking)

**Invoke When**:
- Deploying to AWS infrastructure
- Cost optimization questions
- Scaling issues (CPU, memory, auto-scaling)
- Infrastructure troubleshooting (health checks, networking)
- Multi-region deployment planning

### 3. master-architect
**Specialization**: Ecosystem-level architecture (buyer+seller pattern, agent economy)
**Location**: `.claude/agents/master-architect.md`

**Expertise**:
- Buyer+seller agent pattern design
- Multi-layer stack integration (blockchain → facilitator → agents)
- New agent implementation planning
- System-wide architectural consistency
- Monetization opportunity design

**Invoke When**:
- Designing new AI agents
- Evaluating system-wide architectural changes
- Creating technical specs from MONETIZATION_OPPORTUNITIES.md
- Ensuring consistency with existing patterns
- Breaking changes that affect multiple components

## Collaboration Patterns

### Pattern 1: Protocol → Infrastructure Handoff

**Scenario**: Protocol change requires infrastructure changes

**Flow**:
```
User Request
    ↓
future-architect analyzes protocol implications
    ↓
future-architect creates "Infrastructure Impact" document
    ↓
terraform-specialist receives handoff
    ↓
terraform-specialist proposes infrastructure solution
    ↓
Joint decision on cost vs requirements trade-offs
    ↓
Implementation
```

**Example**: "Add support for Arbitrum network"

```markdown
## Handoff: future-architect → terraform-specialist

**Protocol Analysis (future-architect)**:
- EIP-3009 compatible: ✅
- EIP-712 domain: chain_id=42161, verifyingContract=0x...
- Code changes: Add to x402-rs/src/chain/evm.rs
- Signature verification: Standard EVM pattern

**Infrastructure Questions for terraform-specialist**:
1. RPC endpoint strategy: Alchemy (free tier) vs self-hosted?
2. Cost impact: +$0/month (Alchemy free) or +$170/month (EC2 node)?
3. CloudWatch metrics: Add "arbitrum" dimension to existing metrics?
4. VPC endpoint needed: Only if high volume (>10k tx/day)

**Infrastructure Response (terraform-specialist)**:
1. Recommendation: Start with Alchemy free tier (330 req/sec)
2. Cost: $0/month initially, monitor usage
3. CloudWatch: Yes, add dimension (no extra cost)
4. VPC endpoint: Not yet, revisit at 5k tx/day

**Decision**: Use Alchemy free tier, add to terraform.tfvars as RPC_URL_ARBITRUM
```

### Pattern 2: Infrastructure → Protocol Consultation

**Scenario**: Infrastructure decision affects protocol design

**Flow**:
```
Operational Issue (e.g., high costs, slow performance)
    ↓
terraform-specialist diagnoses infrastructure
    ↓
terraform-specialist identifies protocol-level question
    ↓
future-architect evaluates protocol constraints
    ↓
future-architect provides protocol guidance
    ↓
terraform-specialist implements infrastructure change
```

**Example**: "Should we cache RPC responses to reduce latency?"

```markdown
## Handoff: terraform-specialist → future-architect

**Infrastructure Context (terraform-specialist)**:
- Current RPC latency: 200ms average (p99: 500ms)
- Total facilitator latency: 2.5s (RPC is 20% of total)
- CloudWatch shows: 1000 RPC calls/day, mostly eth_chainId
- Cost: $0/month (under free tier)

**Protocol Question for future-architect**:
Can we cache RPC responses (eth_chainId, token address) to reduce latency?
- Would this break stateless design?
- Which data is safe to cache?
- How to handle cache invalidation?

**Protocol Response (future-architect)**:
✅ **Approve with constraints**:
- Safe to cache: chain_id, token_address (immutable)
- Cache strategy: In-memory HashMap, load on startup
- No Redis needed: Data never changes, no sync needed
- Expected impact: Saves ~40ms per request (200ms → 160ms)
- Maintains statelessness: Read-only cache, no writes

**Implementation**:
- terraform-specialist: No infrastructure changes needed
- future-architect: Add lazy_static config cache to x402-rs
```

### Pattern 3: New Agent Design (master-architect → others)

**Scenario**: Designing a new agent for the ecosystem

**Flow**:
```
New Agent Concept
    ↓
master-architect designs buyer+seller pattern
    ↓
future-architect evaluates protocol integration (ERC-8004, x402)
    ↓
terraform-specialist estimates deployment cost
    ↓
Joint recommendation: Approve/Modify/Reject
```

**Example**: "Create database-query agent that sells SQL insights"

```markdown
## Collaborative Design: database-query-agent

**Ecosystem Design (master-architect)**:
- BUYS: Database schemas (0.01 GLUE)
- SELLS: SQL query results (0.05 GLUE)
- Storage: PostgreSQL (RDS)
- CrewAI: Query planner + security validator
- Port: 8006

**Protocol Integration (future-architect)**:
- ERC-8004 registration: domain=database-query.karmacadabra.ultravioletadao.xyz
- A2A agent card: /api/query endpoint, payment required
- x402 payments: Standard EIP-3009 flow
- Multi-chain: Start with Avalanche, expand later
- Security: SQL injection prevention via validator crew

**Infrastructure Cost (terraform-specialist)**:
- ECS Task: 0.25 vCPU / 0.5GB RAM = $1.50/month (Spot)
- RDS PostgreSQL: db.t3.micro = $15/month
- ALB: Shared with existing agents = $0 incremental
- Total: ~$16.50/month

**Joint Decision**:
✅ **Approve** - Self-sustaining model (earns 0.05 GLUE per query)
- Projected usage: 100 queries/month = 5 GLUE earned
- Break-even: ~330 queries/month at current GLUE prices
- Recommendation: Deploy to production, monitor usage
```

### Pattern 4: Performance Troubleshooting

**Scenario**: System performance issues requiring multi-agent diagnosis

**Flow**:
```
Performance Issue Reported
    ↓
terraform-specialist checks CloudWatch metrics
    ↓
terraform-specialist identifies bottleneck type
    ↓
Branch:
  - Infrastructure bottleneck → terraform-specialist fixes
  - Protocol bottleneck → future-architect optimizes
  - Application bottleneck → master-architect redesigns
```

**Example**: "Facilitator slow during high traffic"

```markdown
## Performance Diagnosis: Facilitator Latency

**Infrastructure Analysis (terraform-specialist)**:
CloudWatch Metrics (last 24h):
- CPU: 25% average (not the bottleneck)
- Memory: 40% usage (plenty of headroom)
- Request count: 1000/day (low volume)
- Latency p99: 5 seconds (HIGH)
- Error rate: 2% (acceptable)

Bottleneck Location:
- ECS task healthy, not resource-constrained
- ALB latency: 50ms (not the issue)
- RPC call latency: 4.5s average (BOTTLENECK FOUND)

**Handoff to future-architect**: RPC endpoint is the bottleneck

**Protocol Analysis (future-architect)**:
Root Cause:
- Using public RPC endpoint (slow, rate-limited)
- Making 3 RPC calls per payment verification:
  1. eth_chainId (redundant, can cache)
  2. eth_call (check nonce unused)
  3. eth_sendRawTransaction (execute payment)

Optimization Strategy:
1. ✅ Cache chain_id (saves 1 RPC call)
2. ✅ Combine nonce check + execute in single tx (saves 1 RPC call)
3. 🤔 Switch to Alchemy/Infura (faster RPC)

**Infrastructure Response (terraform-specialist)**:
RPC Upgrade Cost Analysis:
- Current: Public RPC = $0/month (slow)
- Alchemy: Free tier = $0/month (fast, 330 req/sec)
- Self-hosted: EC2 node = $170/month (fastest)

**Joint Decision**:
1. future-architect: Implement caching + combined tx (code change)
2. terraform-specialist: Switch to Alchemy free tier (config change)
3. Expected result: 5s → 1s latency (80% improvement)
4. Cost impact: $0 (staying in free tier)
```

## Decision Matrix

When multiple agents could handle a task, use this matrix:

| Task Type | Primary Agent | Consult Agents | Reason |
|-----------|--------------|----------------|--------|
| Add new blockchain | future-architect | terraform-specialist | Protocol first, then infrastructure |
| Scale facilitator | terraform-specialist | future-architect | Infrastructure first, verify statelessness |
| Design new agent | master-architect | future-architect, terraform-specialist | Ecosystem design, then protocol + infra |
| Debug signature | future-architect | - | Pure protocol issue |
| Debug health check | terraform-specialist | - | Pure infrastructure issue |
| Cost optimization | terraform-specialist | future-architect | Infra optimization, check protocol impact |
| A2A extension | future-architect | terraform-specialist | Protocol design, check hosting costs |
| Buyer+seller pattern | master-architect | future-architect | Ecosystem pattern, protocol integration |

## Communication Protocol

### Handoff Document Template

```markdown
## Handoff: [Source Agent] → [Target Agent]

**Context**:
- Task: [What needs to be done]
- Current state: [Where we are now]
- Goal: [What we're trying to achieve]

**[Source Agent] Analysis**:
- Key findings: [What we learned]
- Constraints: [Limitations to consider]
- Recommendations: [Initial thoughts]

**Questions for [Target Agent]**:
1. [Specific question]
2. [Another question]
3. [Trade-off to evaluate]

**Expected Output from [Target Agent]**:
- [What we need back]
- [Decision format]
- [Next steps]
```

### Joint Decision Template

```markdown
## Joint Decision: [Topic]

**Participants**: [future-architect, terraform-specialist, master-architect]

**Proposal**: [What's being proposed]

**Analysis by Agent**:

**future-architect** (protocol perspective):
- Protocol impact: [How this affects protocols]
- Backward compatibility: [Breaking changes?]
- Security implications: [New risks?]
- Recommendation: ✅ Approve / ⚠️ Modify / ❌ Reject

**terraform-specialist** (infrastructure perspective):
- Cost impact: [Monthly $ change]
- Scalability: [Can this handle growth?]
- Operational complexity: [Easier or harder to maintain?]
- Recommendation: ✅ Approve / ⚠️ Modify / ❌ Reject

**master-architect** (ecosystem perspective):
- Pattern consistency: [Aligns with buyer+seller?]
- Composability: [Enables or hinders agent interaction?]
- Long-term viability: [Sustainable for 50+ agents?]
- Recommendation: ✅ Approve / ⚠️ Modify / ❌ Reject

**Final Decision**: [Consensus or escalation to user]

**Action Items**:
- [ ] [Agent]: [Specific task]
- [ ] [Agent]: [Another task]
```

## Collaboration Anti-Patterns (Avoid These)

### ❌ Anti-Pattern 1: Silent Decision-Making

**Wrong**:
```
terraform-specialist decides to add Redis cache without consulting future-architect
→ Breaks stateless design principle
→ Introduces infrastructure complexity
→ Protocol implications ignored
```

**Right**:
```
terraform-specialist: "I see we could reduce latency with Redis caching.
Let me check with future-architect if this breaks statelessness."
→ Handoff to future-architect
→ future-architect: "❌ Breaks stateless design. Use in-memory cache for immutable data instead."
→ Aligned solution
```

### ❌ Anti-Pattern 2: Over-Consulting

**Wrong**:
```
terraform-specialist asks future-architect about every CloudWatch metric configuration
→ Slows down obvious infrastructure tasks
→ future-architect doesn't add value to pure infra decisions
```

**Right**:
```
terraform-specialist configures standard CloudWatch metrics independently
Only consults future-architect when metrics need blockchain-specific dimensions
```

### ❌ Anti-Pattern 3: Scope Creep

**Wrong**:
```
future-architect starts recommending Terraform modules
→ Outside protocol expertise
→ Duplicates terraform-specialist knowledge
```

**Right**:
```
future-architect specifies protocol requirements
Hands off to terraform-specialist for Terraform implementation
```

## Success Metrics

**Good Collaboration Indicators**:
- ✅ Clear handoff documents with specific questions
- ✅ Joint decisions on cross-cutting concerns
- ✅ Agents stay within their expertise domains
- ✅ Fast iteration (not waiting for unnecessary approvals)
- ✅ Cost-aware protocol decisions
- ✅ Protocol-aware infrastructure implementations

**Poor Collaboration Indicators**:
- ❌ Agents making decisions outside their domain
- ❌ Conflicting recommendations without resolution
- ❌ Lack of communication on cross-cutting changes
- ❌ Protocol changes breaking infrastructure
- ❌ Infrastructure changes breaking protocols
- ❌ User having to mediate obvious decisions

## Real-World Example: Multi-Chain Expansion

**User Request**: "Add support for 5 new EVM chains: Arbitrum, Optimism Mainnet, BSC, Fantom, Gnosis"

**Collaboration Flow**:

### Step 1: Protocol Analysis (future-architect)
```markdown
## Multi-Chain Expansion: 5 New EVM Chains

**Protocol Compatibility**:
- All 5 chains: EVM-compatible ✅
- EIP-3009 support: Need to verify per chain
- EIP-712 support: Standard across all ✅

**Protocol Work Required**:
- Deploy GLUE token to 5 chains (Foundry scripts exist)
- Configure EIP-712 domains (chain_ids: 42161, 10, 56, 250, 100)
- No x402-rs code changes (reuse evm.rs module)
- Test signature verification on each chain

**Risks**:
- Some chains may not support EIP-3009 natively
- Gas costs vary significantly (BSC cheap, Arbitrum moderate)
- RPC reliability varies by chain

**Handoff to terraform-specialist**:
Need RPC endpoints for 5 chains + cost analysis
```

### Step 2: Infrastructure Analysis (terraform-specialist)
```markdown
## Infrastructure: 5 New Chain RPC Endpoints

**RPC Strategy Analysis**:
| Chain | RPC Provider | Cost (Free Tier) | Cost (Self-Hosted) |
|-------|--------------|------------------|-------------------|
| Arbitrum | Alchemy | $0 (5M req/mo) | $170/mo |
| Optimism | Alchemy | $0 (5M req/mo) | $170/mo |
| BSC | Public | $0 (rate-limited) | $170/mo |
| Fantom | Ankr | $0 (500 req/min) | $170/mo |
| Gnosis | Public | $0 (rate-limited) | $170/mo |

**Recommendation**: Use free tiers initially
**Total Cost Impact**: $0/month (all within free tiers)
**Monitor**: Add CloudWatch metrics per chain to track usage

**Infrastructure Changes**:
1. Add 5 RPC_URL_* environment variables to terraform/ecs-fargate/main.tf
2. Add CloudWatch dimensions for new chains
3. Update Secrets Manager with RPC endpoints
4. Add health checks per chain

**Handoff back to future-architect**: Confirm no protocol blockers
```

### Step 3: Joint Decision
```markdown
## Decision: Approve Multi-Chain Expansion

**future-architect**: ✅ Approve
- Protocol compatible
- No breaking changes
- Standard EVM integration pattern

**terraform-specialist**: ✅ Approve
- Zero cost impact (free tiers)
- Simple configuration changes
- Monitoring in place

**Action Items**:
1. future-architect: Deploy GLUE tokens to 5 chains (2 hours)
2. future-architect: Update x402-rs config with chain_ids (30 min)
3. terraform-specialist: Add RPC URLs to terraform (30 min)
4. terraform-specialist: Deploy updated facilitator (15 min)
5. future-architect: Test signature verification (1 hour)

**Timeline**: 4-5 hours total, low risk
```

---

**Summary**: Effective collaboration = clear boundaries + proactive handoffs + joint decisions on cross-cutting concerns

**Key Principle**: Consult early, decide together, execute independently
