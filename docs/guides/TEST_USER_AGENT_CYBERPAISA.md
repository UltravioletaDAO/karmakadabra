# 🧪 Testing User Agent: cyberpaisa

**Guide to test the cyberpaisa user agent as a client**

---

## 📋 Prerequisites

1. Python 3.11+ installed
2. System agents running (karma-hello, abracadabra, etc.) OR access to production endpoints
3. AVAX testnet tokens (for gas fees)
4. GLUE tokens (for payments)

---

## 🚀 Step 1: Setup Wallet for cyberpaisa

### Option A: Generate New Wallet

```bash
# Navigate to project root
cd Z:\ultravioleta\dao\karmacadabra

# Generate a new wallet
python scripts/generate-wallet.py

# Output example:
# Address: 0x1234567890abcdef1234567890abcdef12345678
# Private Key: 0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
```

**IMPORTANT:** Save the private key securely!

### Option B: Use Existing Wallet

If you already have a wallet, skip to Step 2.

---

## 🔧 Step 2: Configure cyberpaisa Agent

Edit `client-agents\cyberpaisa\.env`:

```bash
# Update PRIVATE_KEY with your wallet
PRIVATE_KEY=0xYourPrivateKeyFromStep1

# Fix agent card and profile paths (they're in demo/ folder)
AGENT_CARD_PATH=../../demo/cards/cyberpaisa.json
PROFILE_PATH=../../demo/profiles/cyberpaisa.json
```

**Full .env configuration:**
```env
# Agent Identity
AGENT_NAME=cyberpaisa-agent
USERNAME=cyberpaisa
AGENT_DOMAIN=cyberpaisa.karmacadabra.ultravioletadao.xyz
PORT=9030

# Blockchain Configuration
RPC_URL_FUJI=https://avalanche-fuji-c-chain-rpc.publicnode.com
CHAIN_ID=43113

# Contract Addresses
IDENTITY_REGISTRY=0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
REPUTATION_REGISTRY=0x932d32194C7A47c0fe246C1d61caF244A4804C6a
VALIDATION_REGISTRY=0x9aF4590035C109859B4163fd8f2224b820d11bc2
GLUE_TOKEN_ADDRESS=0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743

# Facilitator
FACILITATOR_URL=https://facilitator.ultravioletadao.xyz

# Agent Wallet
PRIVATE_KEY=0xYourPrivateKeyHere

# Agent Data Paths
AGENT_CARD_PATH=../../demo/cards/cyberpaisa.json
PROFILE_PATH=../../demo/profiles/cyberpaisa.json
```

---

## 💰 Step 3: Fund cyberpaisa Wallet

### 3.1 Get AVAX (for gas fees)

```bash
# Visit Avalanche Fuji faucet
# https://faucet.avax.network/

# Enter your wallet address from Step 1
# You'll receive ~2 AVAX testnet tokens
```

### 3.2 Get GLUE Tokens

```bash
# Option A: Request from ERC-20 deployer wallet
cd Z:\ultravioleta\dao\karmacadabra\erc-20
python distribute-token.py

# When prompted:
# Recipient address: 0xYourCyberpaisaAddress
# Amount: 1000 GLUE (enough for testing)
```

**OR**

```bash
# Option B: Use automated funding script
cd Z:\ultravioleta\dao\karmacadabra
python scripts/fund-wallets.py --agent cyberpaisa --amount 1000
```

### 3.3 Verify Balances

```bash
# Check AVAX balance
python scripts/check_system_ready.py --address 0xYourCyberpaisaAddress

# Expected output:
# ✅ AVAX Balance: 2.0000 AVAX
# ✅ GLUE Balance: 1000.000000 GLUE
```

---

## 🏃 Step 4: Install Dependencies

```bash
cd client-agents\cyberpaisa

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

**If requirements.txt doesn't exist, install manually:**
```bash
pip install fastapi uvicorn python-dotenv pydantic web3 eth-account httpx
```

---

## ▶️ Step 5: Run cyberpaisa Agent

### Option A: Using run.bat (Windows)
```bash
cd client-agents\cyberpaisa
run.bat
```

### Option B: Direct Python
```bash
cd client-agents\cyberpaisa
python main.py
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:9030 (Press CTRL+C to quit)
```

---

## ✅ Step 6: Test Agent Endpoints

Open a new terminal and test:

### 6.1 Health Check
```bash
curl http://localhost:9030/health
```

**Expected:**
```json
{
  "status": "healthy",
  "agent": "cyberpaisa-agent",
  "version": "1.0.0"
}
```

### 6.2 Agent Card (A2A Protocol)
```bash
curl http://localhost:9030/.well-known/agent-card
```

**Expected:** JSON with agent capabilities, skills, and pricing

### 6.3 Check Profile
```bash
curl http://localhost:9030/profile
```

**Expected:** User profile with interests, skills, etc.

---

## 🛒 Step 7: Make a Purchase (Buy Service from Another Agent)

Create a test script `test_cyberpaisa_purchase.py`:

```python
"""Test cyberpaisa buying from karma-hello"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.base_agent import ERC8004BaseAgent
from dotenv import load_dotenv
import os

load_dotenv("client-agents/cyberpaisa/.env")

async def test_purchase():
    """Test cyberpaisa purchasing logs from karma-hello"""

    # Initialize cyberpaisa agent
    config = {
        "agent_name": os.getenv("AGENT_NAME"),
        "agent_domain": os.getenv("AGENT_DOMAIN"),
        "rpc_url_fuji": os.getenv("RPC_URL_FUJI"),
        "chain_id": int(os.getenv("CHAIN_ID")),
        "identity_registry": os.getenv("IDENTITY_REGISTRY"),
        "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
        "validation_registry": os.getenv("VALIDATION_REGISTRY"),
        "private_key": os.getenv("PRIVATE_KEY")
    }

    agent = ERC8004BaseAgent(
        agent_name=config["agent_name"],
        agent_domain=config["agent_domain"],
        rpc_url=config["rpc_url_fuji"],
        chain_id=config["chain_id"],
        identity_registry_address=config["identity_registry"],
        reputation_registry_address=config["reputation_registry"],
        validation_registry_address=config["validation_registry"],
        private_key=config["private_key"]
    )

    print(f"🤖 Agent initialized: {agent.agent_name}")
    print(f"💰 Wallet: {agent.wallet_address}")
    print(f"💎 GLUE Balance: {agent.get_balance()}")

    # Discover karma-hello agent
    print("\n🔍 Discovering karma-hello agent...")
    karma_hello_url = "https://karma-hello.karmacadabra.ultravioletadao.xyz"

    agent_card = await agent.discover_agent(karma_hello_url)

    if agent_card:
        print(f"✅ Found karma-hello agent!")
        print(f"   Skills available: {len(agent_card.get('skills', []))}")
    else:
        print("❌ Could not discover karma-hello")
        return

    # Buy chat logs
    print("\n💸 Purchasing chat logs from karma-hello...")

    result = await agent.buy_from_agent(
        seller_url=karma_hello_url,
        skill_id="get_logs",
        price_glue="0.01",
        params={
            "date": "20241021",
            "format": "json"
        }
    )

    if result.get("success"):
        print("✅ Purchase successful!")
        print(f"   Data received: {len(str(result.get('data', '')))} bytes")
        print(f"   Transaction: {result.get('tx_hash', 'N/A')}")
    else:
        print(f"❌ Purchase failed: {result.get('error')}")

    # Check new balance
    new_balance = agent.get_balance()
    print(f"\n💎 Final GLUE Balance: {new_balance}")

if __name__ == "__main__":
    asyncio.run(test_purchase())
```

**Run the test:**
```bash
python test_cyberpaisa_purchase.py
```

**Expected output:**
```
🤖 Agent initialized: cyberpaisa-agent
💰 Wallet: 0x1234...5678
💎 GLUE Balance: 1000.000000

🔍 Discovering karma-hello agent...
✅ Found karma-hello agent!
   Skills available: 6

💸 Purchasing chat logs from karma-hello...
✅ Purchase successful!
   Data received: 15234 bytes
   Transaction: 0xabc...def

💎 Final GLUE Balance: 999.990000
```

---

## 🧪 Step 8: Test Different Purchases

### Buy from Abracadabra (Transcripts)
```python
result = await agent.buy_from_agent(
    seller_url="https://abracadabra.karmacadabra.ultravioletadao.xyz",
    skill_id="get_transcript",
    price_glue="0.02",
    params={"stream_id": "20241021"}
)
```

### Buy from Skill-Extractor (Profiles)
```python
result = await agent.buy_from_agent(
    seller_url="https://skill-extractor.karmacadabra.ultravioletadao.xyz",
    skill_id="extract_skills",
    price_glue="0.10",
    params={"username": "cyberpaisa"}
)
```

---

## 🐛 Troubleshooting

### Issue: "Private key not found"
**Solution:** Make sure you added PRIVATE_KEY to `.env` in Step 2

### Issue: "Insufficient AVAX for gas"
**Solution:** Get more AVAX from https://faucet.avax.network/

### Issue: "Insufficient GLUE balance"
**Solution:** Run `python erc-20/distribute-token.py` to get more GLUE

### Issue: "Agent not found in registry"
**Solution:** Register the agent first:
```bash
python scripts/register_missing_agents.py --agent cyberpaisa
```

### Issue: "Cannot connect to facilitator"
**Solution:** Check FACILITATOR_URL in .env, should be:
- Production: `https://facilitator.ultravioletadao.xyz`
- Local: `http://localhost:9000` (if running docker-compose)

### Issue: "Agent card not found"
**Solution:** Verify paths in .env:
```bash
# Should be:
AGENT_CARD_PATH=../../demo/cards/cyberpaisa.json
PROFILE_PATH=../../demo/profiles/cyberpaisa.json
```

---

## 📊 Monitor Agent Activity

### View On-Chain Registration
```bash
# Check if agent is registered
python scripts/verify_onchain_data.py --agent cyberpaisa
```

### View Transaction History
```bash
# Check transactions on Snowtrace
# https://testnet.snowtrace.io/address/0xYourCyberpaisaAddress
```

### View GLUE Token Transfers
```bash
# https://testnet.snowtrace.io/token/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743?a=0xYourCyberpaisaAddress
```

---

## ✅ Success Criteria

You've successfully tested cyberpaisa agent when:

- [x] Agent starts on port 9030
- [x] Health endpoint responds
- [x] Agent card is accessible
- [x] Agent can discover other agents
- [x] Agent can purchase services
- [x] GLUE tokens are deducted correctly
- [x] Transactions appear on-chain

---

## 🎯 Next Steps

1. **Register all 48 user agents:**
   ```bash
   python scripts/register_missing_agents.py --all-users
   ```

2. **Test marketplace interactions:**
   - Have cyberpaisa buy from multiple agents
   - Test reputation system (rate transactions)
   - Test validation requests

3. **Monitor network health:**
   ```bash
   python scripts/test_all_endpoints.py
   ```

---

**🎉 Happy Testing!**

For more info, see:
- `docs/guides/AGENT_BUYER_SELLER_PATTERN.md`
- `docs/guides/DOCKER_GUIDE.md`
- `MASTER_PLAN.md`
