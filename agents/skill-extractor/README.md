# Skill-Extractor Agent

**System Agent #6** - Skill & Interest Profiling Service

## Overview

The **Skill-Extractor Agent** is the 6th system agent in the Karmacadabra ecosystem, specializing in extracting skills, interests, tools, and monetization opportunities from chat logs. While Voice-Extractor focuses on *how users communicate* (linguistic style), Skill-Extractor focuses on *what users know* (competencies and expertise).

### Core Value Proposition

Transform raw chat history into actionable skill profiles that enable:
- **User Agents**: Self-awareness of their marketable skills
- **Buyers**: Discovery of agents with specific expertise
- **Ecosystem**: Dynamic skill-based matching and pricing

---

## Economic Model

**Skill-Extractor is a FULL economic participant** in the agent economy:

```
User Agent (buyer) → Skill-Extractor (0.05 GLUE via x402)
  └─> Skill-Extractor (buyer) → Karma-Hello (0.01 GLUE via x402)
      └─> Net profit: 0.04 GLUE per extraction (400% margin)
```

**Service Catalog**:
- **Basic Profile** (0.02 GLUE): Top 3 interests + top 3 skills
- **Standard Profile** (0.03 GLUE): Full interests (5+) + skills + tools
- **Complete Profile** (0.05 GLUE): Interests + skills + tools + monetization opportunities ← **Used for user agent bootstrap**
- **Enterprise Analysis** (0.50 GLUE): Custom deep-dive with competitive analysis

---

## Wallet Information

- **Address**: `TBD` (to be generated in Milestone 1.0)
- **Initial Balance**: **55,000 GLUE**
- **Role**: Skill profiling + economic participant
- **ERC-8004 Registration**: System Agent #6

---

## Architecture

### Data Flow

```
1. User Agent requests skill profile
   ↓
2. Skill-Extractor receives request with payment (0.05 GLUE via x402)
   ↓
3. Skill-Extractor buys historical logs from Karma-Hello (0.01 GLUE via x402)
   ↓
4. CrewAI crew analyzes logs (5-category extraction)
   ↓
5. Returns JSON profile to User Agent
   ↓
6. User Agent initializes with skill-based services
```

### Integration Points

**Buys from**:
- **Karma-Hello**: Historical chat logs (`karma-hello-agent/logs/users-historical/{username}.txt`)

**Sells to**:
- **User Agents**: Skill profiles for self-initialization
- **Client Agent**: Skill discovery for targeted purchasing
- **Any agent**: On-demand skill analysis

**Collaborates with**:
- **Voice-Extractor**: Combined profiles (voice + skills) for comprehensive agent creation
- **Validator**: Optional validation of skill claims

---

## Extraction Framework

Based on the **chat-user-profiler** methodology, Skill-Extractor performs 5-category analysis:

### 1️⃣ Interest Extraction

**What it identifies**:
- Recurring topics and sustained discussions
- Topic evolution over time (emerging vs. declining)
- Engagement depth (message length, follow-up questions, emotional markers)

**Scoring**: 0.0-1.0 based on Frequency (30%), Depth (40%), Emotional Intensity (30%)

**Example Output**:
```json
{
  "interests": [
    {
      "domain": "Blockchain Development",
      "score": 0.87,
      "evidence": ["Discussed smart contracts 23 times", "Asked advanced Solidity questions"],
      "trend": "growing"
    },
    {
      "domain": "AI/ML Systems",
      "score": 0.72,
      "evidence": ["Frequent LangChain discussions", "Built custom agents"],
      "trend": "stable"
    }
  ]
}
```

### 2️⃣ Skill & Sub-Skill Identification

**Methodology**:
- **Explicit skills**: Directly stated capabilities ("I built a Python script...")
- **Implicit skills**: Demonstrated through behavior (problem-solving, teaching, mediation)

**Skill Scoring**:
- 0.0-0.3: Beginner/curious
- 0.4-0.6: Intermediate
- 0.7-0.9: Advanced
- 0.9-1.0: Expert

**Two-tier hierarchy**:
```json
{
  "skills": [
    {
      "parent": "Programming",
      "score": 0.82,
      "sub_skills": [
        {"name": "Python", "score": 0.89},
        {"name": "JavaScript", "score": 0.67},
        {"name": "SQL", "score": 0.54}
      ]
    }
  ]
}
```

### 3️⃣ Tools & Platforms

**Comprehensive technology audit**:
- Development tools (IDEs, Git, Docker)
- Cloud platforms (AWS, Vercel)
- AI/ML tools (OpenAI, CrewAI, Cognee)
- Blockchain (Ethereum, Avalanche, Solidity)
- Creative tools (Figma, Blender)
- Data tools (MongoDB, PostgreSQL)

**Proficiency Indicators**:
- Mentions troubleshooting → practical user
- Discusses API limitations → power user
- Suggests alternatives → ecosystem awareness
- Teaches others → expert

### 4️⃣ Expression Style (Collaboration with Voice-Extractor)

**Note**: Detailed linguistic analysis is Voice-Extractor's domain. Skill-Extractor provides basic interaction style:
- Question-asking frequency (curious vs. declarative)
- Collaborative indicators (builds on others' ideas)
- Support patterns (community builder vs. independent)

**Output**:
```json
{
  "interaction_style": {
    "question_frequency": 0.68,
    "collaboration_score": 0.82,
    "community_engagement": "high"
  }
}
```

### 5️⃣ Monetization Potential

**Commercial viability analysis**:
- Market demand (existing services, job postings)
- Competitive landscape (oversaturated vs. niche)
- Price range (hourly rates, project fees)
- Unique positioning (rare skill combinations)
- Automation potential (scalable digital products)

**Monetization Score**:
- 0.0-0.3: Hobby-level
- 0.4-0.6: Serviceable skill, modest income
- 0.7-0.8: Strong market demand
- 0.9-1.0: High-value expertise, premium pricing

**Example**:
```json
{
  "monetization_opportunities": [
    {
      "service_name": "Smart Contract Security Audits",
      "score": 0.89,
      "rationale": "Advanced Solidity (0.91) + security awareness (0.84). Market pays $5k-50k per contract.",
      "pricing_model": "Per-contract: $500-2000",
      "target_market": "Early-stage DeFi protocols",
      "competitive_advantage": "Technical depth + clear communication",
      "next_steps": [
        "Complete 2-3 free audits for portfolio",
        "Obtain certification (CertiK, Trail of Bits)"
      ]
    }
  ]
}
```

---

## API Endpoints (via A2A Protocol)

### POST /api/extract-skills

**Request**:
```json
{
  "username": "cyberpaisa",
  "profile_level": "complete",  // basic | standard | complete | enterprise
  "include_monetization": true
}
```

**Payment**: X-Payment header with EIP-712 signature (0.05 GLUE for complete profile)

**Response**:
```json
{
  "user_id": "@cyberpaisa",
  "analysis_date": "2025-10-23",
  "data_coverage": {
    "message_count": 1247,
    "time_span": "2023-01-15 to 2025-10-23",
    "data_quality": "high",
    "confidence_level": 0.85
  },
  "interests": [...],
  "skills": [...],
  "tools_and_platforms": [...],
  "interaction_style": {...},
  "monetization_opportunities": [...],
  "top_3_monetizable_strengths": [
    {
      "strength": "Advanced Python automation",
      "why_it_matters": "Businesses pay $50-150/hour",
      "immediate_market": "Small businesses, solopreneurs"
    }
  ],
  "agent_potential_summary": "This user could become a high-value automation consultant agent, specializing in Python-based workflow optimization for non-technical entrepreneurs. Strong teaching ability enables scalable educational products."
}
```

---

## CrewAI Implementation

### Crew Structure

**5-agent crew for skill extraction**:

1. **Interest Analyst**
   - Role: Topic identification and trend analysis
   - Goal: Map all user interests with confidence scores
   - Tools: Text clustering, sentiment analysis

2. **Skill Assessor**
   - Role: Identify explicit and implicit skills
   - Goal: Create hierarchical skill taxonomy
   - Tools: Competency frameworks, evidence extraction

3. **Technology Auditor**
   - Role: Catalog all tools, platforms, and ecosystems
   - Goal: Build complete tech stack profile
   - Tools: Technology database, proficiency scoring

4. **Market Analyst**
   - Role: Evaluate monetization potential
   - Goal: Identify viable commercial opportunities
   - Tools: Market research, pricing databases

5. **Profile Synthesizer**
   - Role: Combine all analyses into cohesive profile
   - Goal: Generate actionable JSON output
   - Tools: Data aggregation, quality assurance

### Crew Workflow

```python
from crewai import Crew, Agent, Task

# Define agents
interest_analyst = Agent(
    role="Interest Analyst",
    goal="Extract all user interests from chat logs",
    backstory="Expert in psycholinguistic pattern recognition",
    tools=[text_clustering_tool, sentiment_tool]
)

skill_assessor = Agent(
    role="Skill Assessor",
    goal="Identify and score all demonstrated skills",
    backstory="Specialist in competency mapping",
    tools=[skill_taxonomy_tool, evidence_extraction_tool]
)

# ... (3 more agents)

# Define tasks
interest_task = Task(
    description="Analyze {username}'s chat logs and extract all interests",
    agent=interest_analyst,
    expected_output="JSON with interests array (domain, score, evidence, trend)"
)

# ... (4 more tasks)

# Create crew
skill_extraction_crew = Crew(
    agents=[interest_analyst, skill_assessor, tech_auditor, market_analyst, synthesizer],
    tasks=[interest_task, skill_task, tech_task, market_task, synthesis_task],
    verbose=True
)

# Execute
result = skill_extraction_crew.kickoff(inputs={"username": username, "logs": chat_logs})
```

---

## Comparison: Voice-Extractor vs. Skill-Extractor

| Aspect | Voice-Extractor | Skill-Extractor |
|--------|----------------|-----------------|
| **Focus** | *How* users communicate | *What* users know |
| **Categories** | 8 linguistic (modismos, sentence structure, vocabulary, etc.) | 5 professional (interests, skills, tools, monetization) |
| **Output** | Personality profile for agent voice | Competency profile for agent services |
| **Pricing** | 0.04 GLUE (full profile) | 0.05 GLUE (complete profile) |
| **Use Case** | Agent initialization (personality) | Agent initialization (capabilities) |
| **CrewAI Agents** | 8 (one per linguistic category) | 5 (interest, skill, tech, market, synthesis) |
| **Typical Buyers** | User agents (for voice clone) | User agents (for skill declaration) |

**Combined Power**: User agents buy from BOTH to create fully-realized profiles:
```
User Agent Initialization Cost:
- Voice-Extractor: 0.04 GLUE (personality)
- Skill-Extractor: 0.05 GLUE (capabilities)
- Total: 0.09 GLUE per agent
```

---

## Data Requirements

### Input: Historical Chat Logs

**Source**: `karma-hello-agent/logs/users-historical/{username}.txt`

**Format**:
```
[MM/DD/YYYY HH:MM:SS AM/PM] username: message
[10/21/2025 02:15:33 PM] cyberpaisa: I just finished building a Python script that scrapes...
[10/21/2025 02:16:12 PM] cyberpaisa: Using BeautifulSoup and Selenium for the dynamic content
```

**Minimum Requirements**:
- At least 50 messages for basic profile
- At least 200 messages for standard profile
- At least 500 messages for complete profile

**Quality Indicators**:
- Timespan: Longer = better trend analysis (minimum 1 month)
- Message diversity: Multiple topics = richer profile
- Interaction depth: Follow-up questions/discussions = higher confidence

### Output: JSON Profile

**File**: Stored in `skill-extractor-agent/profiles/{username}.json`

**Schema**: See API response above

**Versioning**: Profiles can be regenerated as new logs accumulate

---

## Deployment

### Prerequisites

1. ✅ Phase 1 complete (GLUE token deployed, facilitator running)
2. ✅ Phase 2 complete (base_agent.py with ERC-8004 integration)
3. ✅ Karma-Hello basic implementation complete (serves historical logs)

### Setup

```bash
cd skill-extractor-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add PRIVATE_KEY, RPC_URL, OPENAI_API_KEY, etc.

# Generate wallet
python scripts/generate_wallet.py

# Register agent
python scripts/register_agent.py

# Run agent
python main.py --mode seller
```

### Environment Variables

```bash
# Blockchain
PRIVATE_KEY=0x...  # Skill-Extractor agent wallet
RPC_URL_FUJI=https://api.avax-test.network/ext/bc/C/rpc
IDENTITY_REGISTRY=0x...
REPUTATION_REGISTRY=0x...
GLUE_TOKEN_ADDRESS=0x...

# x402 Facilitator
FACILITATOR_URL=https://facilitator.ultravioletadao.xyz

# AI
OPENAI_API_KEY=sk-...
MODEL=gpt-4o

# Data Source
KARMA_HELLO_URL=https://karma-hello.ultravioletadao.xyz
KARMA_HELLO_API=/api/logs

# Service Config
PORT=8085
PRICE_BASIC=0.02
PRICE_STANDARD=0.03
PRICE_COMPLETE=0.05
PRICE_ENTERPRISE=0.50
```

---

## Testing

### Unit Tests

```bash
pytest tests/test_interest_extraction.py
pytest tests/test_skill_scoring.py
pytest tests/test_monetization.py
```

### Integration Tests

```bash
# Test with mock logs
python tests/test_extraction_flow.py --mock

# Test with real historical logs (3 users)
python tests/test_extraction_flow.py --users cyberpaisa,0xjokker,artisan_maker
```

### End-to-End Test

```bash
# 1. Start Skill-Extractor
python main.py --mode seller &

# 2. Use Client-Agent to purchase profile
cd ../client-agent
python main.py --action buy \
  --seller skill-extractor \
  --service complete_profile \
  --params '{"username": "cyberpaisa"}'

# 3. Verify profile received
cat ../skill-extractor-agent/profiles/cyberpaisa.json
```

---

## Economic Analysis

### Revenue Model

**Per-extraction pricing**:
- Basic: 0.02 GLUE × 55 users = **1.10 GLUE** (if all users get basic)
- Standard: 0.03 GLUE × 55 users = **1.65 GLUE**
- Complete: 0.05 GLUE × 55 users = **2.75 GLUE** (bootstrap scenario)

**Costs**:
- Karma-Hello logs: 0.01 GLUE per extraction
- OpenAI API: ~$0.10 per extraction (GPT-4o tokens)
- Gas: ~$0 (gasless via EIP-3009)

**Net Margin**:
- Complete profile: 0.05 GLUE revenue - 0.01 GLUE cost = **0.04 GLUE profit** (80% margin)

**Bootstrap Economics**:
- 55 user agents × 0.05 GLUE = **2.75 GLUE revenue**
- 55 × 0.01 GLUE to Karma-Hello = **0.55 GLUE cost**
- **Net: 2.20 GLUE profit** from initial bootstrap

### Ongoing Revenue

After bootstrap, Skill-Extractor can sell:
- **Re-profiling**: As users chat more, agents buy updated profiles (monthly?)
- **Specialized analysis**: Deep-dives on specific skills (enterprise tier)
- **Competitive intelligence**: Compare skill profiles (multi-agent analysis)

**Projected**:
- 55 agents × 1 re-profile per quarter × 0.03 GLUE = **0.41 GLUE/quarter**
- 5 enterprise analyses per quarter × 0.50 GLUE = **2.50 GLUE/quarter**
- **Total**: ~**3 GLUE/quarter** ongoing

---

## Roadmap

### Phase 2.5.1 (Week 4): Initial Deployment
- [ ] Generate Skill-Extractor wallet
- [ ] Fund with 55,000 GLUE (from Milestone 1.0)
- [ ] Implement skill_extractor.py (inherit from ERC8004BaseAgent)
- [ ] Register in IdentityRegistry
- [ ] Implement A2A client to BUY from Karma-Hello
- [ ] Implement A2A server to SELL to User Agents
- [ ] Create CrewAI crew (5 agents)
- [ ] Test with 3 sample users
- [ ] Publish AgentCard

### Phase 2.5.2 (Week 5): Integration
- [ ] User Agent Template calls Skill-Extractor during initialization
- [ ] Combined profiles (Voice + Skill) enable rich agent creation
- [ ] Test: User agent initializes with both profiles, declares services

### Phase 3+ (Ongoing): Evolution
- [ ] Add skill-based agent discovery (search agents by skill)
- [ ] Implement skill verification (Validator confirms claimed skills)
- [ ] Build skill marketplace (agents bid on skill-specific tasks)
- [ ] Reputation integration (skill scores weighted by validation history)

---

## Contributing

See main project README for contribution guidelines.

**Skill-Extractor specific**:
- Improve extraction algorithms (better skill taxonomy)
- Add more monetization templates (industry-specific)
- Optimize CrewAI crew performance
- Build skill benchmarking (compare against industry standards)

---

## License

MIT License - See LICENSE file

---

## References

- **chat-user-profiler.md**: Full methodology for skill extraction
- **MONETIZATION_OPPORTUNITIES.md**: Service pricing and tiers
- **voice-extractor.md**: Complementary linguistic profiling
- **Phase 2.5 Milestones**: User Agent Bootstrap System
- **A2A Protocol**: https://github.com/pydantic/pydantic-ai
- **x402 Protocol**: https://www.x402.org
- **ERC-8004**: Bidirectional reputation standard

---

**Skill-Extractor Agent** - Transforming chat logs into marketable skills since 2025 🧠💼
