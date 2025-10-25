# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🚨 CRITICAL RULES - READ FIRST

### SECURITY: NEVER Show Private Keys in Output
**⚠️ THIS REPOSITORY IS SHARED ON LIVE STREAMS**

**ABSOLUTE RULES:**
- ❌ NEVER display contents of .env files
- ❌ NEVER echo PRIVATE_KEY values in commands
- ❌ NEVER show wallet private keys in ANY output
- ❌ NEVER include sensitive data in code examples
- ✅ Use placeholders like `0x...` or `$PRIVATE_KEY` in examples
- ✅ Use environment variable references instead of values
- ✅ Assume all terminal output is publicly visible

**Why**: This codebase is demonstrated in public streams. Exposing private keys would compromise wallets.

### Gas Funding for Agents
**When agents need AVAX for gas fees:**

- ✅ **Use ERC-20 deployer wallet** (stored in AWS Secrets Manager under `erc-20` key)
- ✅ This wallet has AVAX for deploying contracts and can fund agent wallets
- ✅ Access via: `distribute-token.py` (automatically uses AWS Secrets Manager)
- ❌ **DO NOT store ERC-20 deployer key in .env files**
- ⚠️ **Rotate ERC-20 key separately**: Use `python scripts/rotate-system.py --rotate-erc20` (NOT rotated by default)

**Why separate rotation**: ERC-20 deployer owns the GLUE token contract. Rotating it requires redeploying the entire token, so it's only rotated when specifically needed.

### .env Files: Public Addresses vs Private Keys
**IMPORTANT DISTINCTION: Public addresses are NOT secret**

**SAFE to store in .env files:**
- ✅ **Public addresses** (`AGENT_ADDRESS=0x...`) - These are visible on blockchain anyway
- ✅ **Contract addresses** - Public information
- ✅ **RPC URLs** - Public endpoints
- ✅ **Domain names** - Public DNS records

**NEVER store in .env files (unless overriding for local testing):**
- ❌ **Private keys** (`PRIVATE_KEY=`) - ALWAYS leave empty, fetched from AWS
- ❌ **OpenAI API keys** (`OPENAI_API_KEY=`) - ALWAYS leave empty, fetched from AWS
- ❌ **Mnemonics/seed phrases** - NEVER in any file

**Pattern used in this project:**
```bash
# ✅ CORRECT .env pattern
PRIVATE_KEY=  # Leave empty - fetched from AWS Secrets Manager
OPENAI_API_KEY=  # Leave empty - fetched from AWS Secrets Manager
AGENT_ADDRESS=0x2C3e071df446B25B821F59425152838ae4931E75  # Public address (safe to store)
```

**Override pattern (for local testing only):**
```bash
# If you set these in .env, they OVERRIDE AWS Secrets Manager
PRIVATE_KEY=0x1234...  # Only for testing!
OPENAI_API_KEY=sk-proj-...  # Only for testing!
```

**Why public addresses in .env?**
- Makes it easy to reference addresses without AWS lookups
- Useful for quick checks and scripts (`python scripts/check_system_ready.py`)
- No security risk - addresses are visible on blockchain explorers anyway

**All .env files updated:** karma-hello, skill-extractor, voice-extractor, abracadabra, validator all follow this pattern.

### Contract Address Safety
**⚠️ NEVER SEND AVAX OR TOKENS TO CONTRACT ADDRESSES**

**ABSOLUTE RULES:**
- ❌ **NEVER send AVAX to contract addresses** (0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618, etc.)
- ❌ **NEVER send test AVAX to contract addresses**
- ❌ **NEVER send tokens (GLUE or any ERC-20) to contract addresses**
- ⚠️ **Funds sent to contracts are PERMANENTLY LOST** if there's no withdrawal function
- ✅ **Only send AVAX/tokens to externally owned addresses (EOAs)** - wallet addresses controlled by private keys
- ✅ **Check contract code for withdrawal functions** before sending any funds

**Why**: Smart contracts without withdrawal mechanisms cannot return funds. Once AVAX/tokens are sent to these contracts, they are stuck forever with no recovery method.

**Current Issue**: The Identity Registry contract (0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618) has accumulated 0.015 AVAX from registration fees that cannot be withdrawn. This is a design flaw - registration fees should either:
1. Go to a treasury wallet (EOA) that can redistribute funds
2. Have a withdrawal function in the contract
3. Be set to zero if fees are not needed

**How to identify contract addresses:**
- Contract addresses are created when you deploy with `forge create` or similar
- They appear as "To: [Contract 0x...]" on block explorers like Snowtrace
- EOA addresses appear as "To: 0x..." without "[Contract]" label

### Documentation Synchronization
**ALWAYS update both language versions in parallel:**

- ✅ **README.md** ↔️ **README.es.md** (English ↔️ Spanish)
- When updating architecture diagrams, feature descriptions, or any content in one README, **IMMEDIATELY update the other**
- This is **NON-NEGOTIABLE** - bilingual documentation must stay synchronized

**Why**: This project serves both English and Spanish-speaking communities. Outdated translations create confusion and undermine trust.

**Enforcement**: Before committing documentation changes, verify both READMEs have been updated. If you modify one, you MUST modify the other.

### File Organization
**ALWAYS maintain clean root directory structure:**

**📁 Root Directory Structure:**
```
karmacadabra/
├── tests/          # ALL test files go here
├── scripts/        # ALL utility scripts go here
├── logs/           # ALL log files go here
├── data/           # Sample/test data
├── .claude/        # Claude Code configuration
├── shared/         # Shared libraries (base_agent, a2a_protocol, etc.)
├── *-agent/        # Agent implementations (karma-hello-agent, validator, etc.)
├── erc-20/         # GLUE token contracts
├── erc-8004/       # ERC-8004 registry contracts
├── x402-rs/        # x402 facilitator (Rust)
├── *.md            # Documentation files (README, MASTER_PLAN, etc.)
├── .env            # Environment configuration (gitignored)
├── .gitignore      # Git ignore rules
└── LICENSE         # Project license
```

**RULES:**
- ✅ **tests/** - ALL test files: `test_*.py`, `*_test.py`, test scripts
- ✅ **scripts/** - ALL utility scripts: setup, deployment, wallet management, system utilities
- ✅ **logs/** - ALL log files: `*.log`, debug outputs, test results (gitignored)
- ✅ **Root** - ONLY: agent folders, contract folders, documentation (*.md), config files (.env, .gitignore)
- ❌ **Never in root**: individual test files, utility scripts, log files, temporary files

**Examples:**
```bash
# Tests
tests/test_level3_e2e.py              ✅
tests/test_integration_level2.py      ✅
test_validator.py                     ❌ (put in tests/)

# Scripts
scripts/generate-wallet.py            ✅
scripts/rotate-system.py               ✅
setup_agents.py                        ❌ (put in scripts/)

# Logs
logs/validator_port8010.log            ✅
logs/debug_output.log                  ✅
test_results.log                       ❌ (put in logs/)
```

**When creating new files:**
1. Test file? → `tests/`
2. Utility script? → `scripts/`
3. Log/debug output? → `logs/`
4. Documentation? → Root (*.md)
5. Agent code? → `<agent-name>/`
6. Shared library? → `shared/`

**Why this matters**: Clean root directory improves navigation, prevents clutter, and makes the project structure immediately clear to contributors.

---

## Project Overview

**Karmacadabra** is a trustless agent economy where AI agents autonomously buy/sell data using blockchain-based payments. The system enables:

- **Karma-Hello agents** selling Twitch stream chat logs (0.01-1.00 GLUE per service)
- **Abracadabra agents** selling stream transcriptions + AI analysis (0.02-3.00 GLUE per service)
- **Validator agents** providing quality verification (0.001 GLUE per validation)
- **Gasless micropayments** using EIP-3009 meta-transactions via x402 protocol
- **On-chain reputation** using ERC-8004 registries on Avalanche Fuji testnet

**Key Innovation**: Agents operate autonomously without needing ETH/AVAX for gas fees, using signed payment authorizations settled by a facilitator.

---

## Architecture: Three-Layer System

### Layer 1: Blockchain (Avalanche Fuji Testnet)
- **GLUE Token** (`erc-20/`): ERC-20 with EIP-3009 for gasless transfers at 0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
- **ERC-8004 Registries** (`erc-8004/`): Identity, Reputation, Validation contracts
- All agents register on-chain and build reputation through transactions

### Layer 2: Payment Facilitator (Rust)
- **x402-rs** (`x402-rs/`): HTTP 402 payment protocol implementation
- Verifies EIP-712 signatures and executes `transferWithAuthorization()` on-chain
- Stateless design - no database, all state on blockchain
- Public endpoint: `facilitator.ultravioletadao.xyz`

### Layer 3: AI Agents (Python + CrewAI)
- **karma-hello-agent/**: Sells stream logs from MongoDB, buys transcripts
- **abracadabra-agent/**: Sells transcripts from SQLite+Cognee, buys logs
- **validator/**: Independent validation service using CrewAI crews
- All agents use A2A protocol (Pydantic AI) for discovery and communication

---

## Data Flow: Payment Transaction

```
1. Buyer discovers Seller via A2A AgentCard (/.well-known/agent-card)
2. Buyer signs EIP-712 payment authorization off-chain
3. Buyer sends HTTP request with X-Payment header to Seller
4. Seller's x402 middleware extracts payment, calls facilitator /verify
5. (Optional) Seller requests validation from Validator agent
6. Validator analyzes data quality using CrewAI crew, submits score on-chain
7. Facilitator executes transferWithAuthorization() - no gas needed by agents
8. Seller returns data, Buyer integrates into knowledge base
```

**Duration**: ~2-3 seconds end-to-end, completely gasless for agents

---

## Agent Buyer+Seller Pattern

**⚠️ CRITICAL**: All agents implement the **Buyer+Seller pattern** - they both buy inputs and sell outputs.

**Reference Documentation**: See `AGENT_BUYER_SELLER_PATTERN.md` for complete implementation guide.

### Pattern Overview

Every agent in Karmacadabra:
1. **BUYS** data/services from other agents to acquire inputs
2. **SELLS** processed outputs to earn GLUE tokens
3. **DISCOVERS** services via A2A protocol (`/.well-known/agent-card`)
4. **TRANSACTS** autonomously using x402 gasless payments

### Current Agent Ecosystem

| Agent | BUYS | SELLS | Port |
|-------|------|-------|------|
| karma-hello | Transcriptions (0.02) | Chat logs (0.01) | 8002 |
| abracadabra | Chat logs (0.01) | Transcriptions (0.02) | 8003 |
| skill-extractor | Chat logs (0.01) | Skill profiles (0.02-0.50) | 8004 |
| voice-extractor | Chat logs (0.01) | Personality profiles (0.02-0.40) | 8005 |
| validator | N/A | Data validation (0.001) | 8001 |

### Example Value Chain

```
1. Skill-Extractor wants to analyze a user
2. BUYS chat logs from Karma-Hello (0.01 GLUE)
3. Processes logs with CrewAI to extract skills
4. SELLS skill profile to client (0.10 GLUE)
5. Net profit: 0.09 GLUE
```

### Why This Pattern?

- **Self-sustaining**: Agents earn to fund their own purchases
- **Composable**: Services build on other services
- **Specialized**: Each agent focuses on one thing
- **Autonomous**: No human intervention needed
- **Extensible**: New agents join seamlessly

**When implementing new agents**, always follow this pattern:
1. Define what you BUY (inputs)
2. Define what you SELL (outputs)
3. Implement discovery methods (`discover_<seller>()`)
4. Implement purchase methods (`buy_<product>()`)
5. Implement service generation (`generate_<output>()`)
6. Test bidirectional transactions

**See also**: `tests/test_bidirectional_transactions.py` for comprehensive tests

---

## Component Commands

### Smart Contracts (Foundry)

**Deploy GLUE Token to Fuji:**
```bash
cd erc-20
forge build
./deploy-fuji.sh  # or deploy-fuji.ps1 on Windows
```

**Deploy ERC-8004 Registries:**
```bash
cd erc-8004
cd contracts && forge build && cd ..
./deploy-fuji.sh
```

**Run contract tests:**
```bash
cd erc-8004/contracts
forge test -vv
forge test --match-test testValidationFlow  # single test
```

### x402 Facilitator (Rust)

**Build and run:**
```bash
cd x402-rs
cargo build --release
cargo run  # starts on localhost:8080
```

**Run tests:**
```bash
cargo test
cargo test --package x402-axum -- --nocapture  # single crate with output
```

**Health check:**
```bash
curl http://localhost:8080/health
curl http://localhost:8080/supported  # list payment methods
```

### Python Agents

**Setup any agent:**
```bash
cd karma-hello-agent  # or abracadabra-agent or validator
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Register agent on-chain:**
```bash
python scripts/register_seller.py  # or register_validator.py
```

**Run agent:**
```bash
python main.py --mode seller  # for seller agents
python main.py --mode buyer   # for buyer agents
python main.py                # for validator
```

**Run tests:**
```bash
pytest tests/
pytest tests/test_seller.py::test_get_logs -v  # single test
```

---

## Critical Data Locations

### Product Data (What Agents Sell)

**Karma-Hello logs:**
```
karma-hello-agent/logs/YYYYMMDD/
├── full.txt                    # Complete chat for the day
├── {username}.txt              # Per-user message logs
└── ...
```
Source: MongoDB at `z:\ultravioleta\ai\cursor\karma-hello`
Format: `[MM/DD/YYYY HH:MM:SS AM/PM] username: message`

**Abracadabra transcripts:**
```
abracadabra-agent/transcripts/YYYYMMDD/{stream_id}/
├── transcripcion.json          # Main product (3.3MB)
├── ideas_extraidas.json        # 5 ideas with brainstorming (21KB)
├── imagenes_generadas/         # 20 DALL-E 3 images
├── resumen_completo.txt        # Blog post (3.8KB)
├── tweet.txt                   # Generated tweet (318B)
├── segmentos/                  # Detected clips
└── ...
```
Source: SQLite at `z:\ultravioleta\ai\cursor\abracadabra\analytics.db` + Cognee graph (640+ topics)

### Configuration Pattern

All components follow this pattern:
```bash
cp .env.example .env
# Edit .env with your keys and addresses
```

**Critical .env variables:**
- `PRIVATE_KEY`: Wallet private key for signing transactions
- `RPC_URL_FUJI`: Avalanche Fuji RPC endpoint
- `IDENTITY_REGISTRY`: Address from ERC-8004 deployment
- `GLUE_TOKEN_ADDRESS`: Address from GLUE token deployment
- `FACILITATOR_URL`: x402 facilitator endpoint
- `OPENAI_API_KEY`: For CrewAI agents (GPT-4o)

### Domain Naming Convention

**All agent domains MUST use the ultravioletadao.xyz namespace:**

- ✅ **Base domain**: `karmacadabra.ultravioletadao.xyz`
- ✅ **Agent subdomains**: `<agent-name>.karmacadabra.ultravioletadao.xyz`

**Examples:**
```
karma-hello.karmacadabra.ultravioletadao.xyz
abracadabra.karmacadabra.ultravioletadao.xyz
validator.karmacadabra.ultravioletadao.xyz
client.karmacadabra.ultravioletadao.xyz
voice-extractor.karmacadabra.ultravioletadao.xyz
skill-extractor.karmacadabra.ultravioletadao.xyz
```

**Why this matters:**
- Agent domains are registered on-chain in the Identity Registry
- Domains identify agents in the A2A protocol (AgentCard at `/.well-known/agent-card`)
- Consistent naming prevents registration conflicts
- Once registered, changing domains requires using `updateAgent()` function

**Wrong examples (DO NOT USE):**
- ❌ `karma-hello-seller.ultravioletadao.xyz` (missing karmacadabra subdomain)
- ❌ `karma-hello.karmacadabra.xyz` (wrong TLD)
- ❌ `karma-hello-agent.local` (not under ultravioletadao.xyz)

---

## Agent Configuration and Secrets Management

### Loading Agent Configuration

All agents use the same pattern to load configuration from .env files and AWS Secrets Manager:

```python
from shared.agent_config import load_agent_config

# Load complete configuration (fetches PRIVATE_KEY and OPENAI_API_KEY from AWS)
config = load_agent_config("karma-hello-agent")

# Access credentials (fetched from AWS Secrets Manager or .env override)
print(config.private_key)  # Fetched from AWS or .env
print(config.openai_api_key)  # Fetched from AWS or .env

# Access public config (from .env)
print(config.agent_address)  # From .env - safe to store
print(config.agent_domain)  # From .env
print(config.rpc_url)  # From .env
print(config.identity_registry)  # From .env
```

### Secret Fetching Logic

**Priority Order:**
1. **Environment variable** (.env file) - if set and non-empty → use it
2. **AWS Secrets Manager** - if env var is empty → fetch from AWS

**Example with PRIVATE_KEY:**
```python
from shared.secrets_manager import get_private_key

# If .env has PRIVATE_KEY=0x123... → uses that
# If .env has PRIVATE_KEY= (empty) → fetches from AWS
private_key = get_private_key("karma-hello-agent")
```

**Example with OPENAI_API_KEY:**
```python
from shared.secrets_manager import get_openai_api_key

# If .env has OPENAI_API_KEY=sk-proj-... → uses that
# If .env has OPENAI_API_KEY= (empty) → fetches from AWS
openai_key = get_openai_api_key("karma-hello-agent")
```

### AWS Secrets Manager Structure

The `karmacadabra` secret in AWS contains:

```json
{
  "karma-hello-agent": {
    "private_key": "0xf40...",
    "openai_api_key": "sk-proj-Uwi...",
    "address": "0x2C3e071df446B25B821F59425152838ae4931E75"
  },
  "skill-extractor-agent": {
    "private_key": "0x8d1...",
    "openai_api_key": "sk-proj-E_h...",
    "address": "0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9"
  },
  "client-agent": {
    "private_key": "0xa23...",
    "openai_api_key": "sk-proj-Skk...",
    "address": "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA"
  }
}
```

### Adding OpenAI Keys to AWS

To add or update OpenAI API keys:

```bash
python scripts/add_openai_keys_to_aws.py
```

This script updates the existing `karmacadabra` secret with `openai_api_key` for each agent.

### Testing Secret Retrieval

```bash
# Test PRIVATE_KEY and OPENAI_API_KEY retrieval
python shared/secrets_manager.py validator-agent

# Test complete config loading
python shared/agent_config.py validator-agent
```

---

## Agent Implementation Pattern

All agents inherit from `ERC8004BaseAgent` and implement:

```python
class KarmaHelloSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self, config):
        # Register identity on-chain
        self.agent_id = self.register_agent(
            domain="karma-hello-seller.ultravioletadao.xyz"
        )

        # Data source: Local files OR production DB
        if config.USE_LOCAL_FILES:
            self.data_path = "karma-hello-agent/logs"
        else:
            self.db = MongoClient(config.MONGO_URI)["karma_hello"]

        # Publish A2A AgentCard
        self.publish_agent_card()

    @x402_required(price=GLUE.amount("0.01"))
    async def get_logs(self, request):
        # CrewAI crew formats/validates data
        crew = Crew(agents=[formatter, validator])
        return crew.kickoff(inputs={"data": raw_logs})
```

**Key pattern**: Agents support both local file testing and production database queries.

---

## Monetization: 50+ Services

Full catalog in `MONETIZATION_OPPORTUNITIES.md`. Quick reference:

**Karma-Hello (6 tiers):**
- Tier 1 (0.01-0.05 GLUE): Chat logs, user activity, token economics
- Tier 2 (0.05-0.15 GLUE): ML predictions, sentiment analysis
- Tier 3 (0.15-0.30 GLUE): Fraud detection, economic health
- Tier 4-6: A/B testing, custom models, enterprise (up to 200 GLUE)

**Abracadabra (6 tiers):**
- Tier 1 (0.02-0.08 GLUE): Raw/enhanced transcripts, multi-language
- Tier 2 (0.10-0.25 GLUE): Clip generation, blog posts, social media
- Tier 3 (0.25-0.50 GLUE): Predictive engine, recommendations
- Tier 4-6: Video editing, image generation, enterprise (up to 100 GLUE)

**Mapping files to services:**
- `logs/YYYYMMDD/full.txt` → Chat Logs service (0.01 GLUE)
- `transcripts/YYYYMMDD/{id}/transcripcion.json` → Raw Transcript (0.02 GLUE)
- `transcripts/YYYYMMDD/{id}/ideas_extraidas.json` → Idea Extraction (1.20 GLUE)
- `transcripts/YYYYMMDD/{id}/imagenes_generadas/` → Image Generation (0.80 GLUE)

---

## Development Workflow

### Git Workflow - GRANULAR COMMITS REQUIRED

**🚨 CRITICAL: Commit after EVERY completed task in MASTER_PLAN.md**

**Rules:**
1. **ONE task = ONE commit** - Do NOT accumulate changes
2. When you mark a checklist item as `[x]` in MASTER_PLAN.md → commit immediately
3. Commit message must reference the specific task completed
4. Use descriptive commit messages with context

**Example workflow:**
```bash
# Complete a task (e.g., "Create base_agent.py")
# Mark [x] in MASTER_PLAN.md

# Immediately commit:
git add shared/base_agent.py MASTER_PLAN.md
git commit -m "Implement ERC8004BaseAgent base class

- Created shared/base_agent.py with core agent functionality
- Web3.py integration for Fuji contracts
- AWS Secrets Manager integration
- Identity Registry registration
- MASTER_PLAN.md: Phase 2 Task 1 complete

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

git push
```

**Why granular commits:**
- Easier rollback if something breaks
- Clear progress tracking
- Better collaboration (small, focused changes)
- Matches MASTER_PLAN.md structure exactly

**What gets committed together:**
- The code/files for that specific task
- Updated MASTER_PLAN.md with `[x]` marked
- Related tests (if applicable)
- Updated README if the task requires it

**Do NOT commit together:**
- Multiple unrelated MASTER_PLAN tasks
- "Batch" commits with 5+ tasks
- Mixing Phase 1 and Phase 2 work

### Phase 1: Blockchain Infrastructure (Current)
```bash
# 1. Deploy contracts
cd erc-20 && ./deploy-fuji.sh && cd ..
cd erc-8004 && ./deploy-fuji.sh && cd ..

# 2. Save addresses to all agent .env files
# Copy IDENTITY_REGISTRY, REPUTATION_REGISTRY, VALIDATION_REGISTRY, GLUE_TOKEN

# 3. Start facilitator
cd x402-rs && cargo run &
```

### Phase 2: Agent Development
```bash
# 1. Implement base_agent.py with ERC-8004 integration
# 2. Implement validator_agent.py (based on Bob from erc-8004-example)
# 3. Test registration: python scripts/register_validator.py
```

### Phase 3-4: Service Agents
```bash
# Implement sellers (server agents with x402-axum middleware)
# Implement buyers (client agents with x402-reqwest)
# Test with local data files first, then connect to production DBs
```

### Testing End-to-End
```bash
python demo.py  # runs complete flow simulation
```

---

## Key Technical Decisions

### Why EIP-3009 (not regular ERC-20)?
Agents can't hold ETH/AVAX for gas. EIP-3009 allows off-chain signing + relayer execution, making transactions gasless for agents.

### Why Fuji testnet?
Free, fast (2s blocks), EVM-compatible. Mainnet deployment requires audits.

### Why x402 protocol?
Standard HTTP 402 status code for payments. Stateless, works with existing HTTP clients, no custom payment channels needed.

### Why A2A protocol?
Standard for agent discovery and skill invocation. AgentCard at `/.well-known/agent-card` declares capabilities and pricing.

### Why CrewAI?
Multi-agent workflows for complex tasks (validation requires quality analyst + fraud detector + price reviewer working together).

### Why separate validator?
Trustless verification - buyers don't trust sellers' data quality. Independent validator with on-chain reputation provides credible verification.

---

## Common Issues

**"insufficient funds for gas"**
→ Get AVAX testnet from https://faucet.avax.network/

**"agent not found in registry"**
→ Run `python scripts/register_*.py` to register on-chain first

**"AddressAlreadyRegistered" during newAgent()**
→ Agent address is already registered with a different domain
→ Use `updateAgent()` to change the domain, not `newAgent()`
→ Check registration: `cast call <IDENTITY_REGISTRY> "resolveByAddress(address)" <AGENT_ADDRESS>`

**"facilitator connection refused"**
→ Ensure x402-rs is running: `curl http://localhost:8080/health`

**"Agent hangs on startup waiting for registration"**
→ Agent is already registered but trying to re-register
→ Fixed in shared/base_agent.py - now checks `resolveByAddress()` before attempting registration
→ If you see this with old code, manually check registration:
   `python -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('https://avalanche-fuji-c-chain-rpc.publicnode.com')); print(w3.eth.contract(address='<IDENTITY_REGISTRY>', abi=[...]).functions.resolveByAddress('<AGENT_ADDRESS>').call())"`

**"nonce already used"**
→ EIP-3009 uses random nonces - generate a new one (happens on signature replay)

**CrewAI timeouts**
→ Check OPENAI_API_KEY is valid, model is gpt-4o (not gpt-3.5)

**Validator health endpoint not responding**
→ Validator (port 8001) starts but /health endpoint returns "Server disconnected"
→ Status: Known issue, validator needs debugging
→ Likely causes: FastAPI app initialization issue, CrewAI dependency loading, or missing OpenAI key
→ Workaround: Check validator logs directly: `cd validator && python main.py` (will show startup errors)

**Client-agent doesn't run as a server**
→ The `client-agent/` is a buyer agent, not a seller
→ It doesn't expose HTTP endpoints or listen on a port
→ Use it to test purchasing flows: `cd client-agent && python main.py`
→ It's a library/CLI tool, not a FastAPI server

---

## Documentation Map

- **MASTER_PLAN.md**: Complete vision, roadmap, all components explained
- **ARCHITECTURE.md**: Technical decisions, stack, data flows
- **MONETIZATION_OPPORTUNITIES.md**: All 50+ services with pricing
- **QUICKSTART.md**: 30-minute setup guide
- **Component READMEs**: Each folder has detailed README with code examples

**Start here**: Read `QUICKSTART.md` (30 min) → `MASTER_PLAN.md` (60 min) → component READMEs

---

## Windows-Specific Notes

This project is developed on Windows (Z: drive paths visible in code).

**PowerShell scripts available:**
- `erc-8004/deploy-fuji.ps1`
- `erc-8004/deploy-fuji.bat`

**Path handling:**
```python
# Use raw strings for Windows paths
logs_path = r"z:\ultravioleta\dao\karmacadabra\karma-hello-agent\logs"
# Or forward slashes work in Python
logs_path = "z:/ultravioleta/dao/karmacadabra/karma-hello-agent/logs"
```

**Virtual environments:**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```
