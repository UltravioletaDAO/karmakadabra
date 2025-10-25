# Karmacadabra Quick Start Guide

## Status: Almost Ready!

### ✅ What's Working
- All blockchain contracts deployed
- All agent code restructured in `agents/` and `client-agents/`
- Python import paths fixed (can now import `shared` module)
- Demo scripts created

### ⚠️ What Needs to be Done

**Critical fixes before running demo:**

1. **Fund 2 agents with AVAX** (for gas fees)
2. **Register 3 agents on-chain**
3. **Update 3 wrong domain names**

---

## Step-by-Step Setup (5 minutes)

### Step 1: Fund Missing Agents

Two agents need AVAX for gas fees:
- skill-extractor: 0 AVAX → needs 0.5 AVAX
- voice-extractor: 0 AVAX → needs 0.5 AVAX

```powershell
# Run from project root
python scripts/fund_missing_agents.py --confirm
```

**What this does:**
- Uses ERC-20 deployer wallet from AWS Secrets Manager
- Sends 0.5 AVAX to each agent
- Total cost: 1.0 AVAX + gas fees

---

### Step 2: Register Missing Agents

Three agents are not registered on-chain yet:
- validator
- skill-extractor
- voice-extractor

```powershell
python scripts/register_missing_agents.py --confirm
```

**What this does:**
- Registers each agent with correct domain name
- Uses agent's own wallet (from AWS Secrets)
- Costs: 0.01 AVAX registration fee per agent

**Correct domain names:**
- `validator.karmacadabra.ultravioletadao.xyz`
- `skill-extractor.karmacadabra.ultravioletadao.xyz`
- `voice-extractor.karmacadabra.ultravioletadao.xyz`

---

### Step 3: Fix Wrong Domain Names

Three agents registered with wrong domains (missing subdomain):

```powershell
python scripts/update_domain_names.py --confirm
```

**What this fixes:**
- client: `client.karmacadabra.xyz` → `client.karmacadabra.ultravioletadao.xyz`
- karma-hello: `karma-hello.ultravioletadao.xyz` → `karma-hello.karmacadabra.ultravioletadao.xyz`
- abracadabra: `abracadabra.ultravioletadao.xyz` → `abracadabra.karmacadabra.ultravioletadao.xyz`

---

### Step 4: Verify System Ready

```powershell
python scripts/check_system_ready.py
```

This checks:
- ✅ All agents have AVAX for gas
- ✅ All agents have GLUE tokens
- ✅ All agents registered on-chain
- ✅ All domain names correct

---

## Run Demo (2 options)

### Option A: Simulated Demo (No blockchain needed)

Shows the buyer-seller pattern without real transactions:

```powershell
python scripts/demo_client_purchases.py
```

**Output:**
```
[STEP 1] Client → karma-hello (buy chat logs) - 0.01 GLUE
[STEP 2] Client → skill-extractor (buy skills) - 0.05 GLUE
  └─> skill-extractor → karma-hello (buy logs) - 0.01 GLUE
[STEP 3] Client → voice-extractor (buy personality) - 0.05 GLUE
  └─> voice-extractor → karma-hello (buy logs) - 0.01 GLUE

Economics:
  Client spent: 0.11 GLUE
  karma-hello earned: 0.03 GLUE
  skill-extractor profit: 0.04 GLUE (400% margin)
  voice-extractor profit: 0.04 GLUE (400% margin)
```

---

### Option B: Real Agents (Blockchain transactions)

**Terminal 1 - Start karma-hello:**
```powershell
cd agents/karma-hello
python main.py
```

**Terminal 2 - Start skill-extractor:**
```powershell
cd agents/skill-extractor
python main.py
```

**Terminal 3 - Start voice-extractor:**
```powershell
cd agents/voice-extractor
python main.py
```

**Terminal 4 - Run client agent:**
```powershell
cd client-agents/template
python main.py
```

---

## Troubleshooting

### Import Error: ModuleNotFoundError: No module named 'shared'

**Fixed!** This was caused by incorrect Python path in agent main.py files. The fix has been committed.

### Agent has 0 AVAX balance

Run step 1: `python scripts/fund_missing_agents.py --confirm`

### Agent not registered on-chain

Run step 2: `python scripts/register_missing_agents.py --confirm`

### Wrong domain name

Run step 3: `python scripts/update_domain_names.py --confirm`

### AWS Secrets Manager Error

Make sure:
- AWS CLI configured: `aws configure`
- Secret exists: `karmacadabra`
- Region: `us-east-1`

Check secret:
```powershell
aws secretsmanager get-secret-value --secret-id karmacadabra --region us-east-1
```

---

## Agent Ports

When running real agents, they listen on these ports:

| Agent | Port | URL |
|-------|------|-----|
| validator | 8001 | http://localhost:8001 |
| karma-hello | 8002 | http://localhost:8002 |
| abracadabra | 8003 | http://localhost:8003 |
| skill-extractor | 8004 | http://localhost:8004 |
| voice-extractor | 8005 | http://localhost:8005 |
| client (template) | 8006 | http://localhost:8006 |

---

## What Each Agent Does

**karma-hello** (Data Provider)
- SELLS: Twitch chat logs (0.01 GLUE)
- BUYS: Stream transcriptions from abracadabra
- Role: Raw data source for the ecosystem

**skill-extractor** (Processor)
- BUYS: Chat logs from karma-hello (0.01 GLUE)
- SELLS: Skill profiles (0.02-0.50 GLUE)
- Role: Extract competencies and expertise

**voice-extractor** (Processor)
- BUYS: Chat logs from karma-hello (0.01 GLUE)
- SELLS: Personality profiles (0.02-0.40 GLUE)
- Role: Extract communication style and tone

**abracadabra** (Data Provider)
- SELLS: Stream transcriptions (0.02 GLUE)
- BUYS: Chat logs from karma-hello
- Role: Rich transcript data source

**validator** (Verifier)
- SELLS: Data validation (0.001 GLUE)
- Role: Quality assurance using CrewAI

**client** (Orchestrator)
- BUYS: Everything
- SELLS: Comprehensive insights (1.00-2.00 GLUE)
- Role: Aggregates data from all sources

---

## Next Steps After Demo

1. **Deploy more client agents** - `client-agents/` has 48 user agents ready
2. **Test bidirectional transactions** - `tests/test_bidirectional_transactions.py`
3. **Run integration tests** - `tests/test_integration_level2.py`
4. **Monitor blockchain** - https://testnet.snowtrace.io

---

## Important Files

- `scripts/check_system_ready.py` - Check if system is ready
- `scripts/demo_client_purchases.py` - Run simulated demo
- `SYSTEM_STATUS_REPORT.md` - Detailed system status
- `AGENT_BUYER_SELLER_PATTERN.md` - Architecture explanation
- `ARCHITECTURE_GUIDE.md` - New folder structure guide

---

## Support

If you encounter issues:
1. Check `SYSTEM_STATUS_REPORT.md` for known issues
2. Run `python scripts/check_system_ready.py` to diagnose
3. Review agent logs in `logs/` directory
4. Check CLAUDE.md for troubleshooting section
