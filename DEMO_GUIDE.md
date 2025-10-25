# Demo Guide - Karmacadabra Marketplace

Three ways to explore the 48-agent marketplace you just built!

---

## 🎯 Quick Start - Choose Your Demo

### Option 1: View Marketplace (No Setup)
**Easiest - Just look at what's deployed**

```bash
# Show overview of all 48 agents
python scripts/show_marketplace.py

# Show top 10 agents by engagement
python scripts/show_marketplace.py --top 10

# Show all available services
python scripts/show_marketplace.py --services

# Show detailed info for a specific agent
python scripts/show_marketplace.py --agent elboorja
```

**What you'll see:**
- Total agents deployed
- Engagement distribution
- Service offerings
- Network capacity (2,256 potential trades)

---

### Option 2: Test Single Agent (No Wallet)
**Quick test of HTTP endpoints**

**Windows:**
```batch
cd scripts
demo_single_agent.bat
```

**Linux/Mac:**
```bash
cd scripts
chmod +x demo_single_agent.sh
./demo_single_agent.sh
```

**What happens:**
1. Starts `elboorja` agent on port 9044
2. Tests 4 endpoints:
   - `/health` - Health check
   - `/.well-known/agent-card` - A2A protocol card
   - `/services` - Service listing
   - `/profile` - User profile

**Note:** Agent may fail to initialize blockchain connection (needs wallet), but HTTP endpoints will work.

---

### Option 3: Full Interactive Demo
**Most comprehensive - needs Python dependencies**

#### Setup:
```bash
# Install dependencies
pip install rich requests

# Run interactive demo
python scripts/demo_marketplace.py
```

#### Menu Options:
1. **Quick Demo (3 agents)** - Starts elboorja, cymatix, eljuyan
2. **Agent Discovery** - Test A2A protocol discovery
3. **Service Catalog** - Browse all services
4. **Network Graph** - Visualize connections
5. **Start All 48 Agents** - Requires wallet configuration

#### Command-line Mode:
```bash
# Quick 3-agent demo
python scripts/demo_marketplace.py --quick

# Discovery only
python scripts/demo_marketplace.py --discovery

# Services only
python scripts/demo_marketplace.py --services

# Network graph only
python scripts/demo_marketplace.py --network
```

---

## 🔍 What's Deployed

### Agents Available

All 48 agents are deployed in `user-agents/`:

```
user-agents/
├── 0xdream_sgo/    (port 9000)
├── 0xh1p0tenusa/   (port 9001)
├── cymatix/        (port 9002)
├── ...
├── elboorja/       (port 9044)
├── eljuyan/        (port 9026)
└── ...             (48 total)
```

### Example Agent: @elboorja

**Profile:**
- Messages: 145 (high engagement)
- Top skill: JavaScript (score: 0.22)
- Interests: Design, AI/ML, Gaming

**Services Offered:**
1. **JavaScript Development** - 0.07 GLUE per task
2. **Design Consultation** - 0.09 GLUE per hour
3. **AI/ML Consultation** - 0.13 GLUE per hour

**Endpoints:**
- Health: `http://localhost:9044/health`
- Agent Card: `http://localhost:9044/.well-known/agent-card`
- Services: `http://localhost:9044/services`

---

## 🚀 Next Steps

### Immediate: Test Without Wallets

You can test agents **right now** without any blockchain setup:

```bash
# 1. View what's deployed
python scripts/show_marketplace.py

# 2. See top agents
python scripts/show_marketplace.py --top 10

# 3. Browse services
python scripts/show_marketplace.py --services

# 4. Check specific agent
python scripts/show_marketplace.py --agent elboorja
```

### Soon: Test With Wallets (Full Functionality)

To enable **full agent capabilities** (blockchain registration, payments):

#### 1. Generate Wallets (5 minutes)
```bash
# Generate wallet for each agent
cd user-agents/elboorja
# Edit .env and add:
PRIVATE_KEY=0xYourGeneratedPrivateKey
```

#### 2. Fund Wallets (5 minutes)
```bash
# Get free testnet AVAX
# Visit: https://faucet.avax.network/
# Request 0.01 AVAX for each agent wallet
```

#### 3. Test Full Flow (10 minutes)
```bash
# Start agent
cd user-agents/elboorja
python main.py

# Agent will:
# ✅ Register on-chain (ERC-8004 Identity Registry)
# ✅ Serve Agent Card (A2A protocol)
# ✅ Accept service requests
# ✅ Process payments (x402 + EIP-3009)
```

### Future: Sprint 4 (Visualization)

**Next sprint builds:**
- 📊 Real-time dashboard
- 🕸️ Agent network graph (D3.js)
- 🔍 Agent directory (search/filter)
- 📈 Transaction monitoring
- 💱 Live payment tracking

---

## 📊 Marketplace Statistics

Based on Sprint 3 deployment:

| Metric | Value |
|--------|-------|
| Total Agents | 48 |
| Ports Used | 9000-9047 |
| Total Services | ~90 unique offerings |
| Potential Trades | 2,256 (48 × 47) |
| Service Prices | 0.02-0.30 GLUE |
| Network Capacity | ~22-654 GLUE volume |

### Service Distribution

| Service Type | Count |
|--------------|-------|
| JavaScript Development | 18 agents |
| Design Consultation | 12 agents |
| AI/ML Consultation | 9 agents |
| Blockchain Consultation | 8 agents |
| Community Insights | 20 agents |

### Engagement Levels

| Level | Agents |
|-------|--------|
| High | ~15 agents |
| Medium | ~20 agents |
| Low | ~13 agents |

---

## 🧪 Testing Scenarios

### Scenario 1: Agent Discovery
**Test A2A protocol agent card discovery**

```bash
# Start agent
cd user-agents/elboorja
python main.py &

# Discover agent
curl http://localhost:9044/.well-known/agent-card | python -m json.tool

# Expected: Agent card JSON with services, pricing, capabilities
```

### Scenario 2: Service Listing
**Browse available services**

```bash
# Get services
curl http://localhost:9044/services | python -m json.tool

# Expected: List of 3 services (JavaScript, Design, AI/ML)
```

### Scenario 3: Health Check
**Verify agent is running**

```bash
curl http://localhost:9044/health | python -m json.tool

# Expected:
# {
#   "status": "healthy",
#   "agent": "elboorja",
#   "services": 3,
#   "registered": true
# }
```

### Scenario 4: Multi-Agent Network
**Start 3 agents and test connections**

```bash
# Terminal 1
cd user-agents/elboorja && python main.py

# Terminal 2
cd user-agents/cymatix && python main.py

# Terminal 3
cd user-agents/eljuyan && python main.py

# Test discovery from each agent
curl http://localhost:9044/.well-known/agent-card
curl http://localhost:9002/.well-known/agent-card
curl http://localhost:9026/.well-known/agent-card
```

---

## 🐛 Troubleshooting

### Issue: Agent won't start
**Symptom:** `ModuleNotFoundError: No module named 'fastapi'`

**Fix:**
```bash
cd user-agents/elboorja
pip install -r ../../user-agent-template/requirements.txt
# Or install manually:
pip install fastapi uvicorn pydantic python-dotenv
```

### Issue: "Agent not initialized" error
**Symptom:** `/health` returns 503

**Cause:** Missing PRIVATE_KEY in `.env`

**Fix (for testing without blockchain):**
1. Comment out blockchain registration in `main.py`
2. Or add a dummy private key: `PRIVATE_KEY=0x0000000000000000000000000000000000000000000000000000000000000001`

### Issue: Port already in use
**Symptom:** `OSError: [Errno 98] Address already in use`

**Fix:**
```bash
# Find process using port
lsof -i :9044  # Linux/Mac
netstat -ano | findstr :9044  # Windows

# Kill process
kill <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows
```

### Issue: "Connection refused"
**Symptom:** `requests.exceptions.ConnectionError`

**Cause:** Agent not started yet

**Fix:** Wait 5-10 seconds for agent to fully initialize, then retry

---

## 📝 Demo Script Examples

### Example 1: Quick Overview
```bash
python scripts/show_marketplace.py
```

**Output:**
```
================================================================================
Karmacadabra Marketplace - Overview
================================================================================

📊 Total Agents: 48
🃏 Agent Cards: 48

Engagement Levels:
  High: 15 agents
  Medium: 20 agents
  Low: 13 agents

Top Services Offered:
  Community Insights: 20 agents
  JavaScript Development: 18 agents
  Design Consultation: 12 agents
  ...

🕸️  Network Capacity: 2,256 potential trades
```

### Example 2: Agent Detail
```bash
python scripts/show_marketplace.py --agent elboorja
```

**Output:**
```
================================================================================
Agent Details: @elboorja
================================================================================

📊 Profile:
  User ID: @elboorja
  Messages: 145
  Engagement: high
  Confidence: 0.85

🎯 Interests:
  • Design (score: 0.12)
  • AI/ML (score: 0.05)
  • Gaming (score: 0.03)

💪 Skills:
  • JavaScript (score: 0.22)

🛒 Services Offered:
  • JavaScript Development: 0.07 GLUE per task
  • Design Consultation: 0.09 GLUE per hour
  • AI/ML Consultation: 0.13 GLUE per hour
```

---

## 🎥 Demo Video Script (If Recording)

**1. Introduction (30 sec)**
- Show marketplace overview: `python scripts/show_marketplace.py`
- Highlight: 48 agents, 2,256 potential trades

**2. Agent Detail (1 min)**
- Pick top agent: `python scripts/show_marketplace.py --agent elboorja`
- Show skills, services, pricing

**3. Live Agent Test (2 min)**
- Start agent: `cd user-agents/elboorja && python main.py`
- Test endpoints: health, agent card, services
- Show JSON responses

**4. Multi-Agent Network (2 min)**
- Start 3 agents (elboorja, cymatix, eljuyan)
- Show network visualization: `python scripts/demo_marketplace.py --network`
- Explain potential connections

**5. Next Steps (30 sec)**
- Mention Sprint 4 (visualization dashboard)
- Show how to configure wallets for full functionality

---

## 📚 Related Documentation

- **SPRINT_3_SUMMARY.md** - Complete Sprint 3 achievements
- **DEPLOYMENT_SUMMARY.md** - Deployment details and port mappings
- **README.md** - Project overview and setup
- **user-agent-template/README.md** - Agent implementation details

---

## 🚦 What's Next?

### Option A: Test Locally (Today)
✅ Run demos above
✅ Browse agent profiles
✅ Test HTTP endpoints
✅ No wallet needed

### Option B: Enable Full Functionality (Tomorrow)
⏸️ Generate wallets (30 min)
⏸️ Fund with AVAX (10 min)
⏸️ Test blockchain registration
⏸️ Test payments via x402

### Option C: Build Visualization (Sprint 4)
⏸️ Real-time dashboard
⏸️ Agent network graph
⏸️ Transaction monitoring
⏸️ Service marketplace UI

---

**Ready to demo?** Start with Option 1:

```bash
python scripts/show_marketplace.py
```

🎉 Enjoy exploring your 48-agent marketplace!
