# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

---

## 🚨 CRITICAL RULES - READ FIRST

### SECURITY: NEVER Show Private Keys
**⚠️ THIS REPOSITORY IS SHARED ON LIVE STREAMS**

- ❌ NEVER display .env file contents, PRIVATE_KEY values, or wallet keys
- ✅ Use placeholders like `0x...` or `$PRIVATE_KEY` in examples
- ✅ Assume all terminal output is publicly visible

### Gas Funding for Agents
- ✅ Use ERC-20 deployer wallet (AWS Secrets Manager `erc-20` key) for funding agents
- ✅ Access via: `distribute-token.py` (uses AWS automatically)
- ❌ DO NOT store ERC-20 deployer key in .env files
- ⚠️ Rotate separately: `python scripts/rotate-system.py --rotate-erc20`

**Why separate**: ERC-20 deployer owns GLUE token contract. Rotation requires redeploying the entire token.

### OpenAI API Key Rotation
**Quick process (5 minutes):**

1. Generate 6 new keys on OpenAI platform: karma-hello-agent-YYYY, abracadabra-agent-YYYY, validator-agent-YYYY, voice-extractor-agent-YYYY, skill-extractor-agent-YYYY, client-agent-YYYY
2. Save to `.unused/keys.txt` (gitignored)
3. Run: `python3 scripts/rotate_openai_keys.py`
4. Redeploy ECS services:
   ```bash
   for service in facilitator validator abracadabra voice-extractor skill-extractor karma-hello; do
     aws ecs update-service --cluster karmacadabra-prod --service karmacadabra-prod-${service} --force-new-deployment --region us-east-1
   done
   ```
5. Revoke old keys immediately

**Verify**: `curl https://validator.karmacadabra.ultravioletadao.xyz/health`

### SMART CONTRACT SAFETY - EXTREMELY CRITICAL
**⚠️ CONTRACTS ARE IMMUTABLE - ERRORS CANNOT BE UNDONE**

**MANDATORY RULES:**

1. **✅ ALWAYS read Solidity source code FIRST** (`erc-8004/contracts/src/` or `erc-20/contracts/`)
   - NEVER guess function signatures or return types
   - Example: `resolveByAddress()` returns `AgentInfo` struct (tuple), NOT `uint256`

2. **✅ ALWAYS use correct ABIs from contract source**
   - Solidity structs return tuples in web3.py
   - Test with small queries before state changes

3. **✅ ALWAYS test read operations before write operations**
   ```python
   # Test ABI correctness first
   result = contract.functions.resolveByAddress(KNOWN_ADDRESS).call()
   print(f"Test: {type(result)}, {result}")
   ```

4. **✅ UNDERSTAND costs**: 48 agents × 0.005 AVAX = 0.24 AVAX, registration errors can't be deleted

5. **✅ CHECK contract addresses** match `erc-8004/.env.deployed` and `erc-20/.env.deployed`

6. **✅ VERIFY function effects**: `newAgent()` reverts if address registered, use `updateAgent()` instead

7. **✅ TEST with Snowtrace**: https://testnet.snowtrace.io/

**Prevention checklist:**
- [ ] Read Solidity source
- [ ] Build correct ABI from source
- [ ] Test with known data
- [ ] Verify output format
- [ ] Use cast/foundry: `cast call <address> "functionName(type)" <args>`

### .env Files: Public vs Private Data

**SAFE to store:**
- ✅ Public addresses, contract addresses, RPC URLs, domain names

**NEVER store (unless local testing override):**
- ❌ Private keys (leave `PRIVATE_KEY=` empty, fetched from AWS)
- ❌ OpenAI API keys (leave `OPENAI_API_KEY=` empty, fetched from AWS)

**Pattern:**
```bash
PRIVATE_KEY=  # Empty - fetched from AWS
OPENAI_API_KEY=  # Empty - fetched from AWS
AGENT_ADDRESS=0x2C3...  # Public (safe to store)
```

### Contract Address Safety
- ❌ **NEVER send AVAX/tokens to contract addresses** - funds are PERMANENTLY LOST without withdrawal functions
- ✅ Only send to EOAs (wallet addresses with private keys)
- Check contract code for withdrawal functions before sending funds

### Documentation Synchronization
- ✅ **README.md** ↔️ **README.es.md** MUST stay synchronized
- Update both when changing architecture, features, or any content
- **NON-NEGOTIABLE** for bilingual community

### File Organization
```
karmacadabra/
├── tests/          # ALL test files
├── scripts/        # ALL utility scripts
├── logs/           # ALL log files (gitignored)
├── shared/         # Shared libraries
├── *-agent/        # Agent implementations
├── erc-20/         # GLUE token
├── erc-8004/       # Registry contracts
├── x402-rs/        # Facilitator (Rust)
└── *.md            # Documentation only
```

**Rules**: tests → `tests/`, scripts → `scripts/`, logs → `logs/`, never in root

---

## 🧠 System Thinking & Code Quality

### Before Modifying Complex Scripts

1. ✅ Read ENTIRE script - map data flow and dependencies
2. ✅ Check existing working code FIRST - copy patterns from `scripts/`
3. ✅ Trace execution mentally - "If I change Step 2, what breaks in Steps 3-5?"
4. ✅ State your plan EXPLICITLY before coding
5. ✅ Test incrementally - use grep to find all usages
6. ✅ **ALWAYS test dry-runs** - MANDATORY before presenting code to user

### When Refactoring Architecture

1. Map ALL affected code paths (use grep)
2. Update storage AND retrieval atomically
3. Verify consistency - use same attribute names as working code
4. Document OLD vs NEW architecture

### Learning from Working Code

```bash
# Find patterns before coding
grep -r "pattern" scripts/
grep -r "rawTransaction\|raw_transaction" scripts/
```

- `rawTransaction` vs `raw_transaction` - details matter, verify against working code
- Copy working patterns wholesale - consistency > cleverness
- For smart contracts: ALWAYS read `.sol` file for exact return types

### Common Failures to Avoid

**❌ DON'T:**
- Give untested code - run dry-runs first
- Guess smart contract ABIs - read Solidity source
- Work from memory - check working examples
- Skip testing with known data

**✅ DO:**
- Trace data flows before coding
- Verify attribute names against actual usage
- Test ABIs with known addresses before batch operations

---

## Project Overview

**Karmacadabra**: Trustless agent economy with AI agents buying/selling data using blockchain payments.

- **Agents**: karma-hello (chat logs), abracadabra (transcripts), validator (quality checks)
- **Payments**: Gasless micropayments via EIP-3009 + x402 protocol
- **Reputation**: ERC-8004 registries on Avalanche Fuji
- **Innovation**: Agents operate without ETH/AVAX using signed payment authorizations

## Architecture

**Layer 1 - Blockchain (Avalanche Fuji)**
- GLUE Token (ERC-20 + EIP-3009): 0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
- ERC-8004 Registries: Identity, Reputation, Validation contracts

**Layer 2 - Payment Facilitator (Rust)**
- x402-rs: HTTP 402 payment protocol
- Verifies EIP-712 signatures, executes `transferWithAuthorization()`
- Stateless design, endpoint: `facilitator.ultravioletadao.xyz`

**Layer 3 - AI Agents (Python + CrewAI)**
- karma-hello: Sells logs (MongoDB), buys transcripts
- abracadabra: Sells transcripts (SQLite+Cognee), buys logs
- validator: Quality verification with CrewAI crews
- All use A2A protocol for discovery

**Payment Flow**: Buyer discovers Seller → signs payment off-chain → sends HTTP request → Seller verifies → facilitator executes on-chain → ~2-3s total

## Agent Buyer+Seller Pattern

**All agents buy inputs and sell outputs**. See `docs/AGENT_BUYER_SELLER_PATTERN.md` for details.

| Agent | BUYS | SELLS | Port |
|-------|------|-------|------|
| karma-hello | Transcriptions (0.02) | Chat logs (0.01) | 8002 |
| abracadabra | Chat logs (0.01) | Transcriptions (0.02) | 8003 |
| skill-extractor | Chat logs (0.01) | Skill profiles (0.02-0.50) | 8004 |
| voice-extractor | Chat logs (0.01) | Personality profiles (0.02-0.40) | 8005 |
| validator | N/A | Validation (0.001) | 8001 |

**Pattern**: Self-sustaining, composable, specialized, autonomous, extensible

---

## Running the Stack

### Docker Compose (Recommended)

```bash
# Start all agents
scripts\docker-start.bat  # Windows
bash scripts/docker-start.sh  # Linux/Mac
docker-compose up -d  # Manual

# View logs
docker-compose logs -f
docker-compose logs -f karma-hello

# Stop
docker-compose down
```

**Ports**: validator (9001), karma-hello (9002), abracadabra (9003), skill-extractor (9004), voice-extractor (9005)

See `docs/guides/DOCKER_GUIDE.md` for details.

---

## Component Commands

### Smart Contracts (Foundry)

```bash
# Deploy GLUE Token
cd erc-20 && forge build && ./deploy-fuji.sh

# Deploy ERC-8004 Registries
cd erc-8004 && cd contracts && forge build && cd .. && ./deploy-fuji.sh

# Test
cd erc-8004/contracts && forge test -vv
```

### x402 Facilitator (Rust)

```bash
cd x402-rs
cargo build --release && cargo run  # localhost:8080
cargo test
curl http://localhost:8080/health
```

### Python Agents (Manual)

```bash
cd agents/karma-hello
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/register_seller.py
python main.py --mode seller
pytest tests/
```

---

## Critical Configuration

### Data Locations

**Karma-Hello logs**: `karma-hello-agent/logs/YYYYMMDD/full.txt` (MongoDB source)
**Abracadabra transcripts**: `abracadabra-agent/transcripts/YYYYMMDD/{id}/transcripcion.json` (SQLite+Cognee)

### Environment Variables

```bash
cp .env.example .env
```

**Critical vars**: PRIVATE_KEY, RPC_URL_FUJI, IDENTITY_REGISTRY, GLUE_TOKEN_ADDRESS, FACILITATOR_URL, OPENAI_API_KEY

### Domain Naming Convention

**All agents use**: `<agent-name>.karmacadabra.ultravioletadao.xyz`

Examples:
- karma-hello.karmacadabra.ultravioletadao.xyz
- validator.karmacadabra.ultravioletadao.xyz

**Why**: Domains registered on-chain, identify agents in A2A protocol

### Agent Configuration

All agents load config from AWS Secrets Manager:

```python
from shared.agent_config import load_agent_config
config = load_agent_config("karma-hello-agent")  # Fetches from AWS
```

**Priority**: .env override (if set) → AWS Secrets Manager (if empty)

**AWS Structure**:
```json
{
  "karma-hello-agent": {
    "private_key": "0x...",
    "openai_api_key": "sk-proj-...",
    "address": "0x..."
  }
}
```

**Test**: `python shared/secrets_manager.py validator-agent`

### Agent Implementation

```python
class KarmaHelloSeller(ERC8004BaseAgent, A2AServer):
    def __init__(self, config):
        self.agent_id = self.register_agent(domain="karma-hello-seller.ultravioletadao.xyz")
        self.publish_agent_card()

    @x402_required(price=GLUE.amount("0.01"))
    async def get_logs(self, request):
        crew = Crew(agents=[formatter, validator])
        return crew.kickoff(inputs={"data": raw_logs})
```

---

## Development Workflow

### Git Workflow - GRANULAR COMMITS

**🚨 ONE task = ONE commit**. Commit after marking `[x]` in MASTER_PLAN.md.

```bash
git add shared/base_agent.py MASTER_PLAN.md
git commit -m "Implement ERC8004BaseAgent base class

- Created shared/base_agent.py
- Web3.py + AWS Secrets Manager integration
- MASTER_PLAN.md: Phase 2 Task 1 complete

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Why**: Easier rollback, clear progress, better collaboration

### Testing

```bash
# Test all production endpoints
python scripts/test_all_endpoints.py

# Test agent transactions
python scripts/demo_client_purchases.py --production
```

---

## Technical Decisions

- **EIP-3009**: Gasless transactions (agents don't hold ETH/AVAX)
- **Fuji testnet**: Free, fast (2s blocks), EVM-compatible
- **x402 protocol**: Standard HTTP 402 for payments, stateless
- **A2A protocol**: Agent discovery via `/.well-known/agent-card`
- **CrewAI**: Multi-agent workflows for validation
- **Separate validator**: Trustless verification with on-chain reputation

---

## Common Issues

**"insufficient funds for gas"** → Get AVAX from https://faucet.avax.network/

**"agent not found in registry"** → Run `python scripts/register_*.py`

**"AddressAlreadyRegistered"** → Use `updateAgent()`, not `newAgent()`. Check: `cast call <REGISTRY> "resolveByAddress(address)" <ADDRESS>`

**"Agent hangs on startup"** → Already registered, fixed in shared/base_agent.py

**"facilitator connection refused"** → Ensure x402-rs running: `curl http://localhost:8080/health`

**"nonce already used"** → EIP-3009 uses random nonces, generate new one

**CrewAI timeouts** → Check OPENAI_API_KEY valid, model is gpt-4o

**Validator /health not responding** → Known issue, check logs: `cd validator && python main.py`

**Client-agent no server** → It's a buyer (CLI tool), not seller. Use: `cd client-agent && python main.py`

---

## Documentation Map

- **MASTER_PLAN.md**: Vision, roadmap, all components
- **docs/ARCHITECTURE.md**: Technical decisions, data flows
- **docs/MONETIZATION_OPPORTUNITIES.md**: 50+ services with pricing
- **docs/guides/QUICKSTART.md**: 30-minute setup
- **Component READMEs**: Detailed guides per folder

**Start**: `QUICKSTART.md` (30 min) → `MASTER_PLAN.md` (60 min) → component READMEs

---

## Windows-Specific

Developed on Windows (Z: drive paths).

```python
# Path handling
logs_path = r"z:\ultravioleta\dao\karmacadabra\karma-hello-agent\logs"  # raw string
logs_path = "z:/ultravioleta/dao/karmacadabra/karma-hello-agent/logs"   # forward slashes
```

**Scripts**: `erc-8004/deploy-fuji.ps1`, `erc-8004/deploy-fuji.bat`
**venv**: `venv\Scripts\activate` (Windows), `source venv/bin/activate` (Linux/Mac)
