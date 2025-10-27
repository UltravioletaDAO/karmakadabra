# 🚀 Quick Start: cyberpaisa Agent

## Option 1: Automated Setup (Recommended)

```powershell
# Run setup (creates venv, installs dependencies)
.\setup.bat
# or
.\setup.ps1
```

Then run the agent:
```powershell
.\run.bat
# or
.\run.ps1
```

---

## Option 2: Manual Setup

### Step 1: Create Virtual Environment
```powershell
python -m venv venv
```

### Step 2: Activate Virtual Environment

**Windows CMD:**
```cmd
venv\Scripts\activate.bat
```

**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**If you get an error about execution policy:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Configure Wallet

**Generate new wallet:**
```powershell
cd ..\..
python scripts\generate-wallet.py
```

**Edit `.env` file:**
```env
PRIVATE_KEY=0xYourPrivateKeyHere
```

### Step 5: Fund Wallet

**Get AVAX testnet:**
- Go to: https://faucet.avax.network/
- Enter your wallet address
- Get 2 AVAX

**Get GLUE tokens:**
```powershell
cd ..\..\erc-20
python distribute-token.py
# Enter cyberpaisa wallet address
# Amount: 1000 GLUE
```

### Step 6: Run Agent
```powershell
cd ..\client-agents\cyberpaisa
python main.py
```

---

## 🧪 Testing

### Test as Client (Buying Services)
```powershell
# From project root
python tests\test_cyberpaisa_client.py
```

### Test as Server (Selling Services)
```powershell
# Terminal 1: Start agent
cd client-agents\cyberpaisa
python main.py

# Terminal 2: Test endpoints
curl http://localhost:9030/health
curl http://localhost:9030/.well-known/agent-card
curl http://localhost:9030/profile
```

---

## ❌ Troubleshooting

### Error: "Module 'shared' not found"
**Cause:** Python can't find the shared library

**Solution:**
The `main.py` file adds the project root to sys.path. Make sure you're running from the correct directory:
```powershell
cd Z:\ultravioleta\dao\karmacadabra\client-agents\cyberpaisa
python main.py
```

### Error: "Activate.ps1 cannot be loaded"
**Cause:** PowerShell execution policy

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Error: "PRIVATE_KEY not found"
**Cause:** .env file not configured

**Solution:**
1. Generate wallet: `python scripts\generate-wallet.py`
2. Edit `.env` and add PRIVATE_KEY
3. Or use automated setup: `python scripts\setup_user_agent.py cyberpaisa`

### Error: "Insufficient AVAX/GLUE"
**Cause:** Wallet needs funding

**Solution:**
- AVAX: https://faucet.avax.network/
- GLUE: `python erc-20\distribute-token.py`

---

## 📖 Documentation

- **Full Guide:** `..\..\docs\guides\TEST_USER_AGENT_CYBERPAISA.md`
- **Buyer+Seller Pattern:** `..\..\docs\guides\AGENT_BUYER_SELLER_PATTERN.md`
- **Master Plan:** `..\..\MASTER_PLAN.md`

---

## ✅ Success Checklist

- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] PRIVATE_KEY configured in .env
- [ ] Wallet funded with AVAX (>0.1)
- [ ] Wallet funded with GLUE (>10)
- [ ] Agent starts on port 9030
- [ ] Health endpoint responds
- [ ] Can buy from karma-hello

---

**Need help?** Check the troubleshooting section above or see the full guide.
