# Client Agent Testing Guide

**Test the complete buyer+seller pattern with your running agents**

---

## Prerequisites

You mentioned you have these agents running:
- ✅ karma-hello (port 9002)
- ✅ skill-extractor (port 9004)
- ✅ voice-extractor (port 9005)

---

## Step 1: Verify Agents Are Running

From PowerShell:

```powershell
# Check ports are listening
netstat -ano | findstr "9002 9004 9005"

# Test health endpoints
curl http://localhost:9002/health
curl http://localhost:9004/health
curl http://localhost:9005/health
```

**Expected:** Each should return `{"status": "ok"}` or similar

---

## Step 2: Test Agent Discovery (A2A Protocol)

```powershell
# Discover karma-hello
curl http://localhost:9002/.well-known/agent-card

# Discover skill-extractor
curl http://localhost:9004/.well-known/agent-card

# Discover voice-extractor
curl http://localhost:9005/.well-known/agent-card
```

**Expected:** Each returns JSON with agent info, skills, and pricing

**Example output:**
```json
{
  "agent_id": "karma-hello",
  "domain": "karma-hello.karmacadabra.ultravioletadao.xyz",
  "version": "1.0.0",
  "skills": [
    {
      "name": "get_chat_logs",
      "description": "Get chat logs for a user",
      "pricing": {
        "amount": "0.01",
        "currency": "GLUE"
      }
    }
  ]
}
```

---

## Step 3: Run Client Agent (Default Demo)

```powershell
cd client-agents\template
python main.py
```

**What this does:**
1. Initializes client agent with wallet from AWS Secrets Manager
2. Discovers karma-hello at `http://localhost:9002`
3. Attempts to buy chat logs (0.01 GLUE)
4. Shows buyer+seller capabilities

**Expected output:**
```
[INFO] [client-agent] Loading private key from AWS Secrets Manager
[AWS Secrets] Retrieved key for 'client-agent' from AWS
[INFO] [client-agent] Wallet address: 0xCf30021812F27132d36dc791E0eC17f34B4eE8BA
[INFO] [client-agent] Balance: 0.0950 AVAX

BUYER CAPABILITIES:
1. Discovering Karma-Hello agent...
   ✅ Found agent at http://localhost:9002
   Skills: get_chat_logs (0.01 GLUE)

2. Buying chat logs...
   ✅ Signed payment authorization
   ✅ Sent request to karma-hello
   ✅ Received chat logs (1234 bytes)
   ✅ Saved to: purchased_data/karma-hello/test_user_20251025.json

SELLER CAPABILITIES:
3. Agent can SELL comprehensive reports at 1.00 GLUE
```

---

## Step 4: Test Complete Value Chain

### Test 4A: Skill-Extractor Buying from Karma-Hello

This tests the **agent-to-agent purchase** flow:

```powershell
# In skill-extractor logs, you should see:
# [INFO] Buying chat logs from karma-hello
# [INFO] Purchased 500 messages for 0.01 GLUE
# [INFO] Processing with CrewAI...
```

To trigger this, the client needs to request a skill profile:

```powershell
cd client-agents\template
python main.py --buy-skills --user 0xultravioleta
```

**Expected flow:**
1. Client contacts skill-extractor (port 9004)
2. Skill-extractor buys logs from karma-hello (port 9002) - pays 0.01 GLUE
3. Skill-extractor processes logs with CrewAI
4. Client receives skill profile - pays 0.05 GLUE
5. Net profit for skill-extractor: 0.04 GLUE (400% margin)

### Test 4B: Voice-Extractor Buying from Karma-Hello

```powershell
cd client-agents\template
python main.py --buy-voice --user 0xultravioleta
```

**Expected flow:**
1. Client contacts voice-extractor (port 9005)
2. Voice-extractor buys logs from karma-hello (port 9002) - pays 0.01 GLUE
3. Voice-extractor analyzes personality with CrewAI
4. Client receives personality profile - pays 0.04 GLUE
5. Net profit for voice-extractor: 0.03 GLUE (300% margin)

---

## Step 5: Check Transaction Logs

After purchases, check the blockchain:

```powershell
# View client agent transactions
curl "https://testnet.snowtrace.io/address/0xCf30021812F27132d36dc791E0eC17f34B4eE8BA"

# View karma-hello transactions (should show incoming GLUE)
curl "https://testnet.snowtrace.io/address/0x2C3e071df446B25B821F59425152838ae4931E75"

# View skill-extractor transactions (should show outgoing to karma-hello, incoming from client)
curl "https://testnet.snowtrace.io/address/0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9"
```

---

## Step 6: Check Purchased Data

After successful purchases, check the `purchased_data/` directory:

```powershell
dir client-agents\template\purchased_data\

# Expected structure:
# purchased_data/
# ├── karma-hello/
# │   └── test_user_20251025.json           # Chat logs
# ├── skill-extractor/
# │   └── 0xultravioleta_skills_20251025.json   # Skill profile
# └── voice-extractor/
#     └── 0xultravioleta_voice_20251025.json    # Personality profile
```

---

## Troubleshooting

### Error: "Connection refused"

**Problem:** Agent not running or wrong port

**Fix:**
```powershell
# Check what's running
netstat -ano | findstr "900"

# Restart agent
cd agents\karma-hello
python main.py
```

### Error: "Discovery failed"

**Problem:** Agent not exposing A2A endpoint

**Fix:** Check agent logs for errors, ensure FastAPI server started correctly

### Error: "Payment authorization failed"

**Problem:** Client doesn't have GLUE tokens or AVAX for gas

**Fix:**
```powershell
# Check balances
cd scripts
python check_system_ready.py

# Fund if needed
python fund_missing_agents.py
```

### Error: "Agent not registered"

**Problem:** Agent not registered in Identity Registry

**Fix:**
```powershell
cd scripts
python register_seller.py
```

### Error: "Facilitator error"

**Problem:** Can't reach x402 facilitator at https://facilitator.ultravioletadao.xyz

**Fix:** Check internet connection, or run local facilitator:
```powershell
cd x402-rs
cargo run
```

Then update .env:
```
FACILITATOR_URL=http://localhost:8080
```

---

## Success Criteria

✅ All 3 seller agents respond to health checks
✅ All 3 seller agents expose /.well-known/agent-card
✅ Client can discover all 3 sellers
✅ Client can purchase from karma-hello (direct purchase)
✅ Client can purchase from skill-extractor (triggers agent-to-agent purchase)
✅ Client can purchase from voice-extractor (triggers agent-to-agent purchase)
✅ Purchased data saved to purchased_data/ directory
✅ Transactions visible on Snowtrace
✅ Agent balances updated correctly

---

## Next Steps After Testing

1. **Check balances:**
   ```powershell
   python scripts/check_system_ready.py
   ```

2. **View transaction history:**
   - Karma-Hello: https://testnet.snowtrace.io/address/0x2C3e071df446B25B821F59425152838ae4931E75
   - Skill-Extractor: https://testnet.snowtrace.io/address/0xC1d5f7478350eA6fb4ce68F4c3EA5FFA28C9eaD9
   - Voice-Extractor: https://testnet.snowtrace.io/address/0xDd63D5840090B98D9EB86f2c31974f9d6c270b17

3. **Deploy with Docker Compose:**
   ```powershell
   docker-compose up -d
   docker-compose logs -f
   ```

---

## Quick Reference

**Start agents manually:**
```powershell
# Terminal 1
cd agents\karma-hello && python main.py

# Terminal 2
cd agents\skill-extractor && python main.py

# Terminal 3
cd agents\voice-extractor && python main.py
```

**Run client tests:**
```powershell
# Terminal 4
cd client-agents\template

# Test 1: Simple purchase
python main.py

# Test 2: Skill profile (agent-to-agent)
python main.py --buy-skills --user 0xultravioleta

# Test 3: Voice profile (agent-to-agent)
python main.py --buy-voice --user 0xultravioleta
```

**Start with Docker:**
```powershell
docker-compose up -d
docker-compose ps
docker-compose logs -f
```

---

**Status:** Ready for testing!
**Run:** `python main.py` in `client-agents/template/`
