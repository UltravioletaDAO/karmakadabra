# Agent Buyer+Seller Reference Implementation

**Status**: ✅ Implemented in `ERC8004BaseAgent` - ALL agents inherit by default
**Purpose**: Standard pattern for autonomous agents that both buy and sell services
**Base Class**: `shared/base_agent.py` (lines 620-839)

---

## Overview

All Karmacadabra agents follow the **Buyer+Seller pattern**: they sell specialized services while buying inputs from other agents. This creates a self-sustaining agent economy where agents transact autonomously.

**As of October 2025**: Buyer+Seller capabilities are **built into the base agent class**. Every agent automatically has:
- `discover_agent(url)` - A2A discovery
- `buy_from_agent(url, endpoint, data, price)` - Generic purchase
- `save_purchased_data(key, data)` - Cache management
- `create_agent_card(...)` - A2A AgentCard generation
- `create_fastapi_app(...)` - FastAPI app with standard endpoints

### Why This Pattern?

1. **Value Chain**: Agents buy raw data and sell processed insights
2. **Specialization**: Each agent focuses on its core competency
3. **Autonomy**: Agents discover, purchase, and integrate services without human intervention
4. **Monetization**: Agents earn GLUE tokens to fund their own purchases
5. **Extensibility**: New agents can enter the ecosystem and transact immediately

---

## Base Agent API (Inherited by All Agents)

**Every agent automatically inherits buyer+seller capabilities from `ERC8004BaseAgent`:**

### Buyer Methods (from base_agent.py:620-744)

```python
# Discovery
agent_card = await self.discover_agent("http://localhost:8002")
# Returns: {"agentId": 1, "name": "Karma-Hello", "skills": [...]}

# Purchase
data = await self.buy_from_agent(
    agent_url="http://localhost:8002",
    endpoint="/get_chat_logs",
    request_data={"users": ["alice"], "limit": 100},
    expected_price_glue="0.01"
)
# Returns: {"messages": [...]} or None

# Cache
filepath = self.save_purchased_data(
    key="karma-hello_logs_20251024",
    data=purchased_data,
    directory="./purchased_data"
)
# Returns: "./purchased_data/karma-hello_logs_20251024_20251024_143022.json"
```

### Seller Methods (from base_agent.py:746-839)

```python
# Create AgentCard
card = self.create_agent_card(
    agent_id=1,
    name="Data Seller",
    description="Sells high-quality data",
    skills=[{
        "skillId": "sell_logs",
        "name": "sell_logs",
        "description": "Sell chat logs",
        "price": {"amount": "0.01", "currency": "GLUE"}
    }]
)

# Create FastAPI app with standard endpoints
app = self.create_fastapi_app(
    title="Karma-Hello Agent",
    description="Sells Twitch chat logs"
)
# Automatically includes / and /health endpoints

# Add your service endpoints
@app.post("/get_chat_logs")
async def get_logs(request: LogRequest):
    return await self.process_and_sell_logs(request)
```

---

## Reference Implementation: Skill-Extractor Agent

**Example showing buyer+seller pattern using base agent methods:**

```python
class SkillExtractorAgent(ERC8004BaseAgent):
    """
    BUYS: Chat logs from Karma-Hello (0.01 GLUE)
    SELLS: Skill and competency profiles (0.02-0.50 GLUE)
    """

    # ==================================================================
    # BUYER CAPABILITIES - Purchase inputs for processing
    # ==================================================================

    async def discover_karma_hello(self) -> Optional[Dict]:
        """
        Discover Karma-Hello agent via A2A protocol

        Returns AgentCard with available services and pricing
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.karma_hello_url}/.well-known/agent-card",
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"❌ Error discovering agent: {e}")
            return None

    async def buy_user_logs(
        self,
        username: str,
        date_range: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Buy chat logs from Karma-Hello agent

        Uses x402 protocol for gasless payment
        """
        # 1. Discover seller
        agent_card = await self.discover_karma_hello()
        if not agent_card:
            return None

        # 2. Build request
        request_data = {
            "users": [username],
            "limit": 10000,
            "include_stats": True
        }

        # 3. Execute purchase with payment
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.karma_hello_url}/get_chat_logs",
                json=request_data,
                # x402 payment headers would be added here
                timeout=30.0
            )

            if response.status_code == 200:
                logs = response.json()
                price = response.headers.get("X-Price", "unknown")
                print(f"✅ Purchased logs: {price} GLUE")
                return logs

        return None

    # ==================================================================
    # SELLER CAPABILITIES - Sell processed outputs
    # ==================================================================

    async def extract_skill_profile(
        self,
        username: str,
        profile_level: str = "complete"
    ) -> SkillProfileResponse:
        """
        Extract skill profile - this is what we SELL

        Process:
        1. Buy input data (chat logs)
        2. Process with CrewAI
        3. Return processed output
        """

        # Step 1: BUY input data
        logs = await self.buy_user_logs(username)
        if not logs:
            raise HTTPException(404, "Could not obtain input data")

        # Step 2: PROCESS with CrewAI
        analysis = await self._analyze_with_crewai(logs, profile_level)

        # Step 3: RETURN processed output (buyer pays for this)
        return SkillProfileResponse(
            username=username,
            profile_level=profile_level,
            skills=analysis['skills'],
            monetization_opportunities=analysis['monetization'],
            # ... full response
        )
```

---

## Standard Agent Structure

Every agent implements this pattern:

### 1. Buyer Capabilities

**Discovery** (`discover_<seller>()`):
```python
async def discover_<seller>(self) -> Optional[Dict]:
    """Fetch seller's AgentCard via A2A protocol"""
    response = await client.get(f"{seller_url}/.well-known/agent-card")
    return response.json() if response.status_code == 200 else None
```

**Purchase** (`buy_<product>()`):
```python
async def buy_<product>(self, **params) -> Optional[Dict]:
    """
    Purchase product from seller

    1. Discover seller
    2. Build request
    3. Execute with x402 payment
    4. Store purchased data
    5. Return data
    """
    # Implementation follows pattern above
```

**Storage** (`save_purchased_<product>()`):
```python
def save_purchased_<product>(self, data: Dict):
    """Save purchased data to local storage for reuse"""
    # Save to purchased_data/ directory
```

### 2. Seller Capabilities

**Service Endpoint** (FastAPI route):
```python
@app.post("/get_<product>", response_model=<Product>Response)
async def get_<product>(request: <Product>Request):
    """
    Sell product to buyers

    x402 middleware handles payment verification
    """
    return await agent.generate_<product>(request)
```

**Data Processing** (`generate_<product>()`):
```python
async def generate_<product>(self, request) -> <Product>Response:
    """
    Generate product to sell

    May involve:
    - Buying inputs from other agents
    - Processing with CrewAI
    - Formatting output
    """
    # Business logic
```

---

## Current Agent Ecosystem

### Transaction Flow Map

```
┌─────────────────┐
│  Karma-Hello    │  SELLS: Chat logs (0.01 GLUE)
│                 │  BUYS: Transcriptions from Abracadabra (0.02 GLUE)
└────────┬────────┘
         │ sells logs to ↓
         │
┌────────▼────────┐
│  Skill-Extractor│  BUYS: Chat logs (0.01 GLUE)
│                 │  SELLS: Skill profiles (0.02-0.50 GLUE)
└─────────────────┘

┌─────────────────┐
│  Voice-Extractor│  BUYS: Chat logs (0.01 GLUE)
│                 │  SELLS: Personality profiles (0.02-0.40 GLUE)
└─────────────────┘

┌─────────────────┐
│  Abracadabra    │  SELLS: Transcriptions (0.02 GLUE)
│                 │  BUYS: Chat logs from Karma-Hello (0.01 GLUE)
└─────────────────┘

┌─────────────────┐
│  Validator      │  SELLS: Data validation (0.001 GLUE)
│                 │  BUYS: Nothing (independent verifier)
└─────────────────┘
```

### Agent Configurations

| Agent | Port | Buys From | Sells To | Net Margin |
|-------|------|-----------|----------|------------|
| karma-hello | 8002 | Abracadabra (0.02) | Skill/Voice (0.01) | -0.01 GLUE* |
| abracadabra | 8003 | Karma-Hello (0.01) | Karma-Hello (0.02) | +0.01 GLUE |
| skill-extractor | 8004 | Karma-Hello (0.01) | Clients (0.02-0.50) | +0.01-0.49 GLUE |
| voice-extractor | 8005 | Karma-Hello (0.01) | Clients (0.02-0.40) | +0.01-0.39 GLUE |
| validator | 8001 | N/A | All agents (0.001) | +0.001 GLUE |

\* *Karma-Hello purchases transcriptions to enrich its own data, not for every sale*

---

## Implementing New Agents

### Step 1: Define Agent Role

```python
"""
<AgentName> Agent (Buyer + Seller)

BUYS: <InputData> from <SellerAgent> (<Price> GLUE)
SELLS: <OutputData> (<PriceRange> GLUE)

<Description of what this agent does>
"""
```

### Step 2: Inherit from Base Agent

```python
class NewAgent(ERC8004BaseAgent):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            agent_name="new-agent",
            agent_domain=config["agent_domain"],
            # ... standard initialization
        )
```

### Step 3: Implement Buyer Methods

```python
async def discover_<seller>(self) -> Optional[Dict]:
    """Discover seller via A2A"""
    pass

async def buy_<input>(self, **params) -> Optional[Dict]:
    """Purchase input data"""
    pass

def save_purchased_<input>(self, data: Dict):
    """Store purchased data"""
    pass
```

### Step 4: Implement Seller Methods

```python
async def generate_<output>(self, request) -> <Output>Response:
    """
    Generate product to sell

    1. Acquire inputs (buy from other agents or use local data)
    2. Process with CrewAI or other tools
    3. Return formatted output
    """
    pass
```

### Step 5: Register FastAPI Endpoints

```python
@app.post("/get_<output>", response_model=<Output>Response)
async def get_<output>(request: <Output>Request):
    """Endpoint for buyers to purchase"""
    return await agent.generate_<output>(request)

@app.post("/buy_<input>")
async def trigger_purchase(request: PurchaseRequest):
    """Endpoint to trigger agent's own purchases (optional)"""
    return await agent.buy_<input>(**request.dict())
```

---

## Best Practices

### 1. Fallback to Local Data

Always support local file testing for development:

```python
if self.use_local_files:
    data = await self._load_local_data()
else:
    data = await self.buy_data_from_agent()
```

### 2. Cache Purchased Data

Don't re-purchase the same data:

```python
def get_cached_or_buy(self, key: str):
    if key in self.cache:
        return self.cache[key]

    data = await self.buy_data()
    self.cache[key] = data
    return data
```

### 3. Graceful Degradation

If purchase fails, provide limited service:

```python
try:
    full_data = await self.buy_premium_data()
    return self.generate_premium_service(full_data)
except Exception:
    basic_data = await self.load_local_basic_data()
    return self.generate_basic_service(basic_data)
```

### 4. Price Metadata

Always include pricing in responses:

```python
return JSONResponse(
    content=result,
    headers={"X-Price": "0.02 GLUE"}
)
```

### 5. Error Handling

Fail gracefully when seller unavailable:

```python
agent_card = await self.discover_seller()
if not agent_card:
    logger.warning(f"Seller unavailable, using cached data")
    return self.use_cached_fallback()
```

---

## Testing Bidirectional Transactions

### Test 1: Skill-Extractor Buys from Karma-Hello

```python
# 1. Start both agents
# 2. Skill-extractor discovers Karma-Hello
# 3. Skill-extractor purchases chat logs
# 4. Skill-extractor processes and sells profile
assert purchase_successful
assert skill_profile_generated
```

### Test 2: Karma-Hello Buys from Abracadabra

```python
# 1. Start both agents
# 2. Karma-Hello discovers Abracadabra
# 3. Karma-Hello purchases transcription
# 4. Karma-Hello enriches its own data
assert purchase_successful
assert data_enriched
```

### Test 3: Circular Transaction

```python
# 1. Karma-Hello sells logs to Skill-Extractor (earns 0.01 GLUE)
# 2. Skill-Extractor processes and sells profile (earns 0.10 GLUE)
# 3. Karma-Hello buys transcription from Abracadabra (spends 0.02 GLUE)
# Net: Karma-Hello -0.01, Abracadabra +0.02, Skill-Extractor +0.09
assert all_transactions_successful
assert token_balances_correct
```

---

## Future Extensions

### Multi-Agent Workflows

Agents can chain purchases to create complex services:

```
Client → Requests comprehensive analysis (pays 1.00 GLUE)
  ↓
Orchestrator Agent (keeps 0.20 GLUE)
  ├─→ Buys logs from Karma-Hello (0.01 GLUE)
  ├─→ Buys transcription from Abracadabra (0.02 GLUE)
  ├─→ Buys skills from Skill-Extractor (0.10 GLUE)
  ├─→ Buys personality from Voice-Extractor (0.10 GLUE)
  ├─→ Buys validation from Validator (0.001 GLUE)
  └─→ Synthesizes comprehensive report

Total spent: 0.231 GLUE
Orchestrator profit: 0.769 GLUE
```

### Dynamic Pricing

Agents adjust prices based on:
- Demand (more requests = higher price)
- Supply (multiple sellers = lower price)
- Quality (higher validation scores = higher price)
- Urgency (faster delivery = premium price)

### Reputation-Based Discounts

Agents can offer discounts to:
- High-reputation buyers
- Frequent customers
- Agents that provide referrals
- Agents in the same "clan" or organization

---

## Implementation Checklist

For each new agent:

- [ ] Define clear BUYS/SELLS statement in docstring
- [ ] Implement discovery methods for all sellers
- [ ] Implement purchase methods for all inputs
- [ ] Implement storage for purchased data
- [ ] Implement service generation (what you sell)
- [ ] Implement FastAPI endpoints
- [ ] Add x402 payment verification middleware
- [ ] Publish A2A AgentCard
- [ ] Register on-chain with ERC-8004
- [ ] Write bidirectional transaction tests
- [ ] Document pricing and service tiers
- [ ] Implement caching and fallbacks
- [ ] Add comprehensive error handling
- [ ] Update this document with new agent info

---

## Conclusion

The Buyer+Seller pattern is **fundamental** to the Karmacadabra architecture. Every agent participates in the economy by:

1. **Buying** inputs to enhance their services
2. **Selling** specialized outputs to earn GLUE
3. **Discovering** services via A2A protocol
4. **Transacting** autonomously with x402 payments
5. **Building reputation** via ERC-8004 registries

This pattern enables:
- **Composability**: Services build on other services
- **Specialization**: Agents focus on core competencies
- **Autonomy**: No human intervention needed
- **Scalability**: New agents join seamlessly
- **Sustainability**: Agents fund their own operations

**All future agents MUST implement this pattern.**
