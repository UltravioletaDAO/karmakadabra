# Voice-Extractor Agent

**System Agent #5** - Linguistic Style & Communication Pattern Analysis

## Overview

The **Voice-Extractor Agent** is the 5th system agent in the Karmacadabra ecosystem, specializing in extracting linguistic style, communication patterns, and personality markers from chat logs. While Skill-Extractor focuses on *what users know* (competencies), Voice-Extractor focuses on *how users communicate* (linguistic style and personality).

### Core Value Proposition

Transform raw chat history into personality profiles that enable:
- **User Agents**: Authentic voice cloning for natural communication
- **Buyers**: Discovery of agents with specific communication styles
- **Ecosystem**: Personality-based matching and interaction design

---

## Economic Model

**Voice-Extractor is a FULL economic participant** in the agent economy:

```
User Agent (buyer) → Voice-Extractor (0.04 GLUE via x402)
  └─> Voice-Extractor (buyer) → Karma-Hello (0.01 GLUE via x402)
      └─> Net profit: 0.03 GLUE per extraction (300% margin)
```

**Service Catalog**:
- **Basic Profile** (0.02 GLUE): Top 3 personality traits + basic style
- **Standard Profile** (0.03 GLUE): Full personality (5+ traits) + communication patterns
- **Complete Profile** (0.04 GLUE): Full linguistic analysis (8 categories) ← **Used for user agent bootstrap**
- **Enterprise Analysis** (0.40 GLUE): Custom deep-dive with psychological profiling

---

## Wallet Information

- **Address**: `TBD` (to be generated in Phase 2.5)
- **Initial Balance**: **55,000 GLUE**
- **Role**: Linguistic profiling + economic participant
- **ERC-8004 Registration**: System Agent #5

---

## Architecture

### Data Flow

```
1. User Agent requests voice profile
   ↓
2. Voice-Extractor receives request with payment (0.04 GLUE via x402)
   ↓
3. Voice-Extractor buys historical logs from Karma-Hello (0.01 GLUE via x402)
   ↓
4. CrewAI crew analyzes logs (8-category linguistic extraction)
   ↓
5. Returns JSON personality profile to User Agent
   ↓
6. User Agent initializes with authentic voice clone
```

### Integration Points

**Buys from**:
- **Karma-Hello**: Historical chat logs (`karma-hello-agent/logs/users-historical/{username}.txt`)

**Sells to**:
- **User Agents**: Voice profiles for personality initialization
- **Client Agent**: Style-based agent discovery
- **Any agent**: On-demand communication analysis

**Collaborates with**:
- **Skill-Extractor**: Combined profiles (voice + skills) for comprehensive agent creation
- **Validator**: Optional validation of personality consistency

---

## Extraction Framework

Based on **psycholinguistic analysis**, Voice-Extractor performs 8-category analysis:

### 1️⃣ Modismos & Expressions (Idioms)

**What it identifies**:
- Recurring phrases and signature expressions
- Regional/cultural linguistic markers
- Unique catchphrases and verbal tics
- Slang usage patterns

**Scoring**: 0.0-1.0 based on Frequency (40%), Uniqueness (40%), Consistency (20%)

**Example Output**:
```json
{
  "modismos": {
    "score": 0.82,
    "signature_phrases": [
      "let's goooo!",
      "that's wild",
      "honestly though"
    ],
    "regional_markers": ["latinoamerica", "costa_rica"],
    "frequency": "high",
    "uniqueness": 0.78
  }
}
```

### 2️⃣ Sentence Structure

**What it identifies**:
- Average sentence length and complexity
- Question vs. statement ratio
- Use of fragments vs. complete sentences
- Punctuation patterns (emojis, ellipses, exclamation marks)

**Scoring**: Complexity (0-1), Formality (0-1), Expressiveness (0-1)

**Example Output**:
```json
{
  "sentence_structure": {
    "avg_length": "short",
    "complexity": 0.45,
    "formality": 0.32,
    "expressiveness": 0.89,
    "question_ratio": 0.35,
    "fragment_usage": "frequent",
    "emoji_frequency": "high"
  }
}
```

### 3️⃣ Vocabulary & Word Choice

**What it identifies**:
- Lexical diversity (unique words / total words)
- Technical vs. colloquial vocabulary
- Positive/negative word balance
- Abstract vs. concrete language

**Scoring**: Diversity (0-1), Technical Level (0-1), Tone (0-1)

**Example Output**:
```json
{
  "vocabulary": {
    "diversity": 0.67,
    "technical_level": 0.72,
    "tone": 0.85,
    "word_categories": {
      "technical": 0.45,
      "colloquial": 0.55,
      "positive": 0.72,
      "negative": 0.18
    },
    "signature_words": ["actually", "basically", "literally"]
  }
}
```

### 4️⃣ Humor & Sarcasm

**What it identifies**:
- Joke frequency and types
- Sarcasm markers and irony
- Self-deprecating humor
- Pop culture references

**Scoring**: 0.0-1.0 based on Frequency (40%), Effectiveness (40%), Originality (20%)

**Example Output**:
```json
{
  "humor": {
    "score": 0.71,
    "types": ["observational", "self_deprecating", "memes"],
    "sarcasm_frequency": 0.45,
    "reference_style": "internet_culture",
    "timing": "natural"
  }
}
```

### 5️⃣ Empathy & Support

**What it identifies**:
- Supportive language patterns
- Empathetic responses to others
- Encouragement frequency
- Community-building behaviors

**Scoring**: 0.0-1.0 based on Frequency (30%), Genuineness (40%), Impact (30%)

**Example Output**:
```json
{
  "empathy": {
    "score": 0.88,
    "support_frequency": "high",
    "response_patterns": ["validating", "encouraging", "helping"],
    "community_role": "supporter",
    "emotional_intelligence": 0.82
  }
}
```

### 6️⃣ Formality & Tone

**What it identifies**:
- Formal vs. casual register
- Professional vs. friendly tone
- Politeness markers
- Authority vs. peer language

**Scoring**: Formality (0-1), Friendliness (0-1), Authority (0-1)

**Example Output**:
```json
{
  "formality": {
    "level": 0.35,
    "friendliness": 0.92,
    "authority": 0.48,
    "politeness": 0.73,
    "register": "casual_professional",
    "adaptation": "context_aware"
  }
}
```

### 7️⃣ Engagement Style

**What it identifies**:
- Question-asking patterns
- Follow-up engagement
- Conversation initiation
- Topic switching behavior

**Scoring**: Proactivity (0-1), Persistence (0-1), Curiosity (0-1)

**Example Output**:
```json
{
  "engagement": {
    "proactivity": 0.78,
    "persistence": 0.65,
    "curiosity": 0.91,
    "question_ratio": 0.42,
    "follow_up_rate": 0.73,
    "conversation_style": "collaborative"
  }
}
```

### 8️⃣ Rhythm & Timing

**What it identifies**:
- Response time patterns
- Message length consistency
- Burst vs. steady communication
- Time-of-day patterns

**Scoring**: Consistency (0-1), Responsiveness (0-1), Activity Level (0-1)

**Example Output**:
```json
{
  "rhythm": {
    "consistency": 0.62,
    "responsiveness": 0.84,
    "activity_level": 0.75,
    "preferred_times": ["evening", "late_night"],
    "message_pattern": "burst_communicator",
    "avg_response_time": "2-5_minutes"
  }
}
```

---

## CrewAI Implementation

Voice-Extractor uses an **8-agent CrewAI crew**, one per linguistic category:

```python
from crewai import Agent, Task, Crew

# Define linguistic analysts
modismo_analyst = Agent(
    role="Modismo & Expression Analyst",
    goal="Extract signature phrases and linguistic markers",
    backstory="Expert in sociolinguistics and regional dialects",
    tools=[pattern_recognition_tool, frequency_analyzer]
)

structure_analyst = Agent(
    role="Sentence Structure Analyst",
    goal="Analyze grammatical patterns and complexity",
    backstory="Syntactician specializing in digital communication",
    tools=[syntax_parser, complexity_scorer]
)

vocabulary_analyst = Agent(
    role="Vocabulary Analyst",
    goal="Assess word choice and lexical diversity",
    backstory="Lexicographer with expertise in colloquial language",
    tools=[lexical_diversity_tool, tone_analyzer]
)

humor_analyst = Agent(
    role="Humor & Sarcasm Analyst",
    goal="Detect joke patterns and irony",
    backstory="Computational humor researcher",
    tools=[sarcasm_detector, reference_matcher]
)

empathy_analyst = Agent(
    role="Empathy Analyst",
    goal="Identify supportive and empathetic patterns",
    backstory="Social psychologist studying online interactions",
    tools=[sentiment_analyzer, support_detector]
)

formality_analyst = Agent(
    role="Formality & Tone Analyst",
    goal="Assess register and politeness levels",
    backstory="Pragmatics expert in digital discourse",
    tools=[register_classifier, politeness_scorer]
)

engagement_analyst = Agent(
    role="Engagement Style Analyst",
    goal="Analyze interaction patterns and curiosity",
    backstory="Conversational analyst",
    tools=[engagement_tracker, question_analyzer]
)

rhythm_analyst = Agent(
    role="Rhythm & Timing Analyst",
    goal="Extract temporal communication patterns",
    backstory="Chronolinguist studying digital rhythms",
    tools=[timing_analyzer, pattern_detector]
)

# Synthesis agent combines all profiles
synthesis_agent = Agent(
    role="Voice Profile Synthesizer",
    goal="Combine all analyses into coherent personality profile",
    backstory="Personality psychologist specializing in digital personas",
    tools=[profile_merger, consistency_checker]
)

# Define crew
voice_extraction_crew = Crew(
    agents=[
        modismo_analyst,
        structure_analyst,
        vocabulary_analyst,
        humor_analyst,
        empathy_analyst,
        formality_analyst,
        engagement_analyst,
        rhythm_analyst,
        synthesis_agent
    ],
    tasks=[
        # One task per analyst
        Task(description="Extract modismos", agent=modismo_analyst),
        Task(description="Analyze structure", agent=structure_analyst),
        # ... etc
        Task(description="Synthesize profile", agent=synthesis_agent)
    ],
    process="sequential"
)

# Execute
result = voice_extraction_crew.kickoff(inputs={"username": username, "logs": chat_logs})
```

---

## Output Format

Voice-Extractor returns a comprehensive JSON profile:

```json
{
  "username": "cyberpaisa",
  "analysis_date": "2025-10-23T14:30:00Z",
  "message_count": 1247,
  "date_range": "2025-01-15 to 2025-10-21",

  "personality_summary": {
    "primary_traits": ["friendly", "curious", "technical"],
    "communication_style": "casual_professional",
    "engagement_level": "high",
    "uniqueness_score": 0.78
  },

  "linguistic_profile": {
    "modismos": { /* ... */ },
    "sentence_structure": { /* ... */ },
    "vocabulary": { /* ... */ },
    "humor": { /* ... */ },
    "empathy": { /* ... */ },
    "formality": { /* ... */ },
    "engagement": { /* ... */ },
    "rhythm": { /* ... */ }
  },

  "voice_clone_parameters": {
    "temperature": 0.72,
    "top_p": 0.88,
    "frequency_penalty": 0.35,
    "presence_penalty": 0.42,
    "signature_phrases": ["let's gooo!", "honestly though"],
    "emoji_style": "moderate",
    "response_length": "short_medium"
  },

  "confidence_score": 0.85,
  "data_quality": "high"
}
```

---

## Comparison: Voice-Extractor vs. Skill-Extractor

| Aspect | Voice-Extractor | Skill-Extractor |
|--------|----------------|-----------------|
| **Focus** | *How* users communicate | *What* users know |
| **Categories** | 8 linguistic (modismos, structure, vocabulary, etc.) | 5 professional (interests, skills, tools, monetization) |
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

## Use Cases

### 1. User Agent Bootstrap
```python
# New user agent cyberpaisa initializes
voice_profile = await voice_extractor.get_profile(user="cyberpaisa", pay="0.04 GLUE")
skill_profile = await skill_extractor.get_profile(user="cyberpaisa", pay="0.05 GLUE")

# Agent configures itself
agent.personality = voice_profile["voice_clone_parameters"]
agent.services = skill_profile["monetization_opportunities"]
agent.publish_agent_card()
```

### 2. Style-Based Agent Discovery
```python
# Client wants friendly, technical agents
results = await client.discover_agents(
    filters={
        "personality_traits": ["friendly", "technical"],
        "formality": {"max": 0.4},
        "empathy": {"min": 0.7}
    }
)
```

### 3. Communication Adaptation
```python
# Agent adapts to buyer's style
buyer_style = await voice_extractor.get_profile(user=buyer_id)
agent.adapt_communication(
    formality=buyer_style["formality"]["level"],
    humor=buyer_style["humor"]["frequency"],
    emoji_usage=buyer_style["sentence_structure"]["emoji_frequency"]
)
```

---

## Technical Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.11+ | Agent runtime |
| **Framework** | CrewAI | Multi-agent orchestration |
| **LLM** | GPT-4o | Linguistic analysis |
| **NLP** | spaCy + NLTK | Text processing |
| **Data Source** | Karma-Hello logs | Chat history |
| **Payment** | x402 + EIP-3009 | Gasless micropayments |
| **Identity** | ERC-8004 | On-chain registration |
| **Blockchain** | Avalanche Fuji | Testnet deployment |

---

## Project Structure

```
voice-extractor-agent/
├── README.md                  # This file
├── .env.example              # Configuration template
├── requirements.txt          # Python dependencies
│
├── agents/
│   ├── __init__.py
│   ├── voice_extractor.py    # Main agent logic
│   ├── linguistic_analysts.py # 8 CrewAI agents
│   └── synthesizer.py        # Profile synthesis
│
├── scripts/
│   ├── register_agent.py     # ERC-8004 registration
│   ├── generate_wallet.py    # Wallet creation
│   └── test_extraction.py    # Local testing
│
└── tests/
    ├── test_modismos.py
    ├── test_structure.py
    ├── test_vocabulary.py
    └── test_full_profile.py
```

---

## Setup & Deployment

### Prerequisites

```bash
# Python 3.11+
python --version

# Virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Required variables**:
```bash
# Wallet
PRIVATE_KEY=0x...                          # Agent wallet private key
AGENT_ADDRESS=0x...                        # Agent wallet address

# Blockchain
RPC_URL_FUJI=https://avalanche-fuji-c-chain-rpc.publicnode.com
CHAIN_ID=43113

# ERC-8004 Contracts
IDENTITY_REGISTRY=0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
REPUTATION_REGISTRY=0x932d32194C7A47c0fe246C1d61caF244A4804C6a
VALIDATION_REGISTRY=0x9aF4590035C109859B4163fd8f2224b820d11bc2

# GLUE Token
GLUE_TOKEN_ADDRESS=0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743

# x402 Facilitator
FACILITATOR_URL=https://facilitator.ultravioletadao.xyz

# OpenAI (for CrewAI)
OPENAI_API_KEY=sk-...

# Karma-Hello Integration
KARMA_HELLO_URL=https://karma-hello.karmacadabra.ultravioletadao.xyz
```

### Registration

```bash
# Register agent on-chain
python scripts/register_agent.py

# Expected output:
# ✅ Agent registered!
# - Agent ID: 5
# - Domain: voice-extractor.ultravioletadao.xyz
# - Tx Hash: 0x...
```

### Run Agent

```bash
# Start voice-extractor server
python main.py

# Server starts on: http://localhost:8005
```

---

## API Endpoints

### `POST /api/extract-voice`

Extract voice profile from username.

**Request**:
```json
{
  "username": "cyberpaisa",
  "tier": "complete"
}
```

**Response** (with `X-Payment: 0.04 GLUE` header):
```json
{
  "username": "cyberpaisa",
  "personality_summary": { /* ... */ },
  "linguistic_profile": { /* ... */ },
  "voice_clone_parameters": { /* ... */ },
  "confidence_score": 0.85
}
```

### `GET /.well-known/agent-card`

A2A protocol agent card.

**Response**:
```json
{
  "name": "Voice-Extractor",
  "version": "1.0.0",
  "description": "Linguistic style and personality extraction from chat logs",
  "skills": [
    {
      "name": "voice_profile_extraction",
      "price": "0.04 GLUE",
      "input_schema": {
        "username": "string",
        "tier": "basic|standard|complete|enterprise"
      }
    }
  ],
  "payment_methods": ["eip3009"],
  "endpoint": "https://voice-extractor.karmacadabra.ultravioletadao.xyz"
}
```

---

## Roadmap

### Phase 2.5.1 (Week 4): Initial Deployment
- [ ] Generate Voice-Extractor wallet
- [ ] Fund with 55,000 GLUE (from Milestone 1.0)
- [ ] Implement voice_extractor.py (inherit from ERC8004BaseAgent)
- [ ] Register in IdentityRegistry
- [ ] Implement A2A client to BUY from Karma-Hello
- [ ] Implement A2A server to SELL to User Agents
- [ ] Create CrewAI crew (8 linguistic analysts)
- [ ] Test with 3 sample users
- [ ] Publish AgentCard

### Phase 2.5.2 (Week 5): Integration
- [ ] Integrate with Skill-Extractor (combined profiles)
- [ ] Test end-to-end payment flow (x402 + EIP-3009)
- [ ] Deploy to staging environment
- [ ] Performance testing (target: <30s per extraction)

### Phase 2.5.3 (Week 6): User Agent Bootstrap
- [ ] Integrate with User Agent Factory
- [ ] Mass extraction for 48 users
- [ ] Quality validation (Validator agent collaboration)
- [ ] Production deployment

---

## Pricing Tiers

| Tier | Price | What's Included | Typical Buyer |
|------|-------|----------------|---------------|
| **Basic** | 0.02 GLUE | Top 3 personality traits + basic style | Quick personality check |
| **Standard** | 0.03 GLUE | Full personality (5+ traits) + communication patterns | General agent setup |
| **Complete** | 0.04 GLUE | All 8 categories + voice clone params | User agent bootstrap ⭐ |
| **Enterprise** | 0.40 GLUE | Custom deep-dive + psychological profiling | Professional agents |

**Recommended**: User agents should buy **Complete** tier for authentic voice cloning.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Test specific category
pytest tests/test_modismos.py -v

# Test full extraction
python scripts/test_extraction.py --username cyberpaisa
```

**Expected output**:
```
Voice Profile Extraction Test
=============================
Username: cyberpaisa
Messages analyzed: 1,247

Personality Summary:
  Primary traits: friendly, curious, technical
  Communication style: casual_professional
  Uniqueness score: 0.78

Linguistic Profile:
  ✓ Modismos: 0.82
  ✓ Structure: 0.65
  ✓ Vocabulary: 0.71
  ✓ Humor: 0.73
  ✓ Empathy: 0.88
  ✓ Formality: 0.35
  ✓ Engagement: 0.79
  ✓ Rhythm: 0.68

Confidence: 85%
Cost: 0.04 GLUE
Time: 28.3s
```

---

## Performance Metrics

**Target Performance**:
- **Extraction Time**: <30 seconds (8-agent CrewAI crew)
- **Accuracy**: >80% confidence score
- **Cost Efficiency**: 300% margin (0.03 GLUE profit per extraction)
- **Throughput**: 120 extractions/hour

---

## Security & Privacy

⚠️ **Sensitive Data Handling**:
- Chat logs contain personal communication patterns
- Profiles should be encrypted at rest
- Access controlled via payment (x402)
- No persistent storage of user logs (buy from Karma-Hello per request)

**Privacy Guarantee**:
- Logs purchased from Karma-Hello are analyzed in-memory
- Only final profile is returned
- No log retention after extraction
- Profile ownership transfers to buyer

---

## References

- **Skill-Extractor**: Complementary competency profiling
- **MONETIZATION_OPPORTUNITIES.md**: Service pricing and tiers
- **chat-user-profiler.md**: Base methodology for personality extraction
- **Phase 2.5 Milestones**: User Agent Bootstrap System
- **A2A Protocol**: https://github.com/pydantic/pydantic-ai
- **x402 Protocol**: https://www.x402.org
- **ERC-8004**: Bidirectional reputation standard
- **CrewAI Docs**: https://docs.crewai.com/

---

**Desarrollado con ❤️ por Ultravioleta DAO**

*Enabling authentic AI personalities through linguistic analysis*
