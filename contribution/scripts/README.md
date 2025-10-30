# Contribution Scripts

Self-contained scripts for Week 2 data collection and analysis.

## Overview

These scripts execute 100+ marketplace transactions with bidirectional ratings, collect on-chain data, and perform statistical analysis for the EIP-8004 contribution.

## Setup

### Install Dependencies
```bash
cd contribution/scripts
python3 -m pip install -r requirements.txt
```

### Environment Configuration
Scripts access agent configurations from the main repo:
- Agent .env files: `/client-agents/*/. env`
- System contracts: `/erc-8004/.env.fuji`
- AWS Secrets Manager: `karmacadabra` secret

## Scripts

### 1. verify_system_ready.py
**Purpose:** Verify all 54 agents are registered and funded

**Usage:**
```bash
python verify_system_ready.py
```

**What it checks:**
- All 54 agents registered on-chain (IDs #1-54)
- AVAX balance sufficient for gas (>0.01 AVAX)
- GLUE balance sufficient for transactions (>1000 GLUE)
- Bidirectional rating methods available

**Output:** Console report showing agent status

---

### 2. simulate_marketplace.py
**Purpose:** Execute 100+ transactions with bidirectional ratings

**Usage:**
```bash
# Dry run (no actual transactions)
python simulate_marketplace.py --dry-run --count 100

# Execute for real
python simulate_marketplace.py --execute --count 100

# Execute specific scenario
python simulate_marketplace.py --scenario bad_client --count 20 --execute

# Output to custom file
python simulate_marketplace.py --execute --count 100 --output ../data/week2/my_transactions.csv
```

**Scenarios:**
1. `good_transaction` - Mutual 5/5 ratings (20 transactions)
2. `bad_client` - Seller rates client low (10 transactions)
3. `bad_seller` - Client rates seller low (10 transactions)
4. `disputed` - Asymmetric ratings (20 transactions)
5. `validator_rating` - Seller rates validator (20 transactions)
6. `rating_history` - Multiple transactions same agents (20 transactions)

**Output:**
- CSV file with all transaction data
- Transaction hashes for on-chain verification
- Summary statistics

**Example Output CSV:**
```csv
timestamp,buyer_id,seller_id,buyer_rating,seller_rating,tx_hash,scenario
2025-10-28 10:15:23,3,1,95,92,0xabc...,good_transaction
2025-10-28 10:15:45,3,2,88,15,0xdef...,bad_client
...
```

---

### 3. analyze_ratings.py
**Purpose:** Statistical analysis of transaction data

**Usage:**
```bash
# Analyze data from simulate_marketplace.py
python analyze_ratings.py --input ../data/week2/transactions.csv

# Generate visualizations
python analyze_ratings.py --input ../data/week2/transactions.csv --visualize --output ../analysis
```

**Analyses performed:**
- Rating correlation (buyer vs seller ratings)
- Asymmetry detection (ratings differ >2 points)
- Trust score evolution over time
- Scenario comparison (good vs bad actors)
- Network graph of rating flows

**Output:**
- Statistical summary (markdown)
- Visualizations (PNG)
- JSON with key metrics

---

### 4. export_transactions.py
**Purpose:** Export on-chain transaction data

**Usage:**
```bash
# Export specific transaction hashes
python export_transactions.py --hashes 0xabc...,0xdef...

# Export all transactions from time range
python export_transactions.py --from-block 47245000 --to-block 47246000

# Export with screenshots
python export_transactions.py --hashes 0xabc... --screenshot
```

**Output:**
- JSON with transaction details
- Snowtrace URLs for each transaction
- Optional: Screenshots of key transactions

---

## Utilities (scripts/utils/)

### agent_loader.py
Load agent configurations from main repo

```python
from utils.agent_loader import load_all_agents, load_agent_by_name

# Load all 54 agents
agents = load_all_agents()

# Load specific agent
karma_hello = load_agent_by_name("karma-hello")
```

### transaction_logger.py
Log transactions to CSV/JSON

```python
from utils.transaction_logger import TransactionLogger

logger = TransactionLogger("../data/week2/transactions.csv")
logger.log_transaction(buyer_id, seller_id, buyer_rating, seller_rating, tx_hash)
logger.save()
```

### web3_helper.py
Web3 utility functions

```python
from utils.web3_helper import get_w3, get_contract, wait_for_transaction

w3 = get_w3()
contract = get_contract(w3, "IdentityRegistry")
receipt = wait_for_transaction(w3, tx_hash)
```

---

## Data Flow

```
1. verify_system_ready.py
   ↓
   Confirms all 54 agents ready

2. simulate_marketplace.py --execute
   ↓
   Executes 100+ transactions
   ↓
   Outputs: ../data/week2/transactions.csv

3. analyze_ratings.py
   ↓
   Reads ../data/week2/transactions.csv
   ↓
   Outputs: ../analysis/statistical_summary.md
            ../analysis/visualizations/*.png

4. export_transactions.py
   ↓
   Fetches on-chain data
   ↓
   Outputs: ../data/week2/on_chain_data.json
```

---

## Troubleshooting

**ImportError: No module named 'lib'**
```bash
# Scripts automatically add ../lib to path
# If issues, manually add:
export PYTHONPATH="${PYTHONPATH}:../lib"
```

**Connection refused to Fuji RPC**
```bash
# Check RPC in main repo
cat ../../erc-8004/.env.fuji | grep RPC_URL

# Try alternative RPC
export RPC_URL_FUJI="https://api.avax-test.network/ext/bc/C/rpc"
```

**AWS credentials not found**
```bash
# Configure AWS CLI
aws configure

# Or use .env overrides in agent folders
```

**Transactions failing**
```bash
# Check AVAX balance
python verify_system_ready.py

# Fund agent if needed (from main repo)
cd ../..
python scripts/fund-wallets.py
```

---

## Testing

All scripts support `--dry-run` mode for testing without blockchain transactions:

```bash
python verify_system_ready.py --dry-run
python simulate_marketplace.py --dry-run --count 10
python analyze_ratings.py --dry-run --input test_data.csv
```

---

## Next Steps

After running scripts:
1. Review output in `../data/week2/`
2. Check visualizations in `../analysis/`
3. Document findings in `../week2/2.4-DAY4-ANALYSIS.md`
4. Identify edge cases for `../week2/2.6-DAY5-EDGE-CASES.md`

---

**For complete Week 2 plan, see:** `../week2/2.0-CHECKLIST.md`
