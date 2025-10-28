# Week 2: Self-Contained Folder Structure Plan

**Date:** October 28, 2025
**Goal:** Make `contribution/` folder completely self-contained and portable
**Reason:** This folder will be packaged for EIP-8004 contribution submission

---

## Design Principles

1. ✅ **Self-contained:** All code, scripts, and dependencies in `contribution/`
2. ✅ **Portable:** Can be zipped and run on another machine
3. ✅ **No external deps:** Don't rely on `/shared/` or `/scripts/` outside contribution
4. ✅ **Documented:** Everything has README explaining what it does
5. ✅ **Reproducible:** Anyone can run the same tests and get same results

---

## Proposed Folder Structure

```
contribution/
├── README.md                           # Overview of the contribution package
├── PLAN-WEEK2-FOLDER-STRUCTURE.md     # This file (the plan)
│
├── 0-MASTER-PLAN.md                    # Overall roadmap (exists)
├── 0.1-GETTING-STARTED.md              # Setup guide (exists)
├── 0.2-PROGRESS-TRACKER.md             # Daily progress (exists)
├── 00-FILE-INDEX.md                    # Navigation guide (exists)
│
├── week1/                              # Week 1 deliverables (complete)
│   ├── 1.0-CHECKLIST.md
│   ├── 1.1-DAY1-SUMMARY.md
│   ├── 1.2-DAY2-TEST-RESULTS.md
│   ├── 1.3-DAY3-PYTHON-IMPLEMENTATION.md
│   ├── 1.4-DAY4-INTEGRATION-TESTS.md
│   └── 1.5-DAY5-EVIDENCE-PACKAGE.md
│
├── week2/                              # Week 2 work (current)
│   ├── 2.0-CHECKLIST.md                # ✅ Created
│   ├── 2.1-GETTING-STARTED.md          # ✅ Created
│   ├── 2.2-DAY1-SIMULATION-DESIGN.md   # TODO
│   ├── 2.3-DAY2-SCRIPT-IMPLEMENTATION.md  # TODO
│   ├── 2.4-DAY3-EXECUTION-RESULTS.md   # TODO
│   ├── 2.5-DAY4-ANALYSIS.md            # TODO
│   ├── 2.6-DAY5-EDGE-CASES.md          # TODO
│   └── data/                           # Transaction data outputs
│       ├── transactions.csv            # All 100+ transactions
│       ├── transaction_hashes.txt      # On-chain proof
│       ├── screenshots/                # Snowtrace screenshots
│       └── analysis/                   # Statistical analysis outputs
│
├── scripts/                            # 🆕 Self-contained scripts
│   ├── README.md                       # What each script does
│   ├── requirements.txt                # Python dependencies
│   ├── simulate_marketplace.py         # Main simulation script
│   ├── verify_system_ready.py          # Check 54 agents ready
│   ├── analyze_ratings.py              # Statistical analysis
│   ├── export_transactions.py          # Export to CSV
│   └── utils/                          # Helper utilities
│       ├── __init__.py
│       ├── agent_loader.py             # Load agent configs
│       ├── transaction_logger.py       # Log transactions
│       └── web3_helper.py              # Web3 utilities
│
├── shared/                             # 🆕 Copied dependencies (minimal)
│   ├── __init__.py
│   ├── agent_config.py                 # Copy from /shared/
│   ├── base_agent.py                   # Copy from /shared/ (or reference key methods)
│   ├── secrets_manager.py              # Copy from /shared/
│   └── README.md                       # Explains what's copied
│
├── contracts/                          # 🆕 Contract code for reference
│   ├── ReputationRegistry.sol          # The modified contract
│   ├── ReputationRegistry.abi.json     # ABI for interactions
│   ├── deployed_addresses.json         # Contract addresses on Fuji
│   └── README.md                       # Deployment info
│
├── tests/                              # 🆕 Week 2 specific tests
│   ├── test_simulation_script.py       # Test the simulator
│   ├── test_rating_methods.py          # Test bidirectional methods
│   └── test_data_analysis.py           # Test analysis functions
│
├── data/                               # 🆕 All data outputs (Week 2+)
│   ├── week2/                          # Week 2 transaction data
│   │   ├── transactions.csv
│   │   ├── raw_data.json
│   │   └── analysis_results.json
│   ├── week3/                          # Week 3 security data
│   └── README.md
│
├── analysis/                           # 🆕 Analysis notebooks & results
│   ├── rating_patterns.ipynb           # Jupyter notebook
│   ├── statistical_summary.md          # Text summary
│   ├── visualizations/                 # Charts and graphs
│   │   ├── rating_correlation.png
│   │   ├── network_graph.html
│   │   └── histograms.png
│   └── README.md
│
├── plans/                              # 🆕 Detailed execution plans
│   ├── week2-implementation-plan.md    # Detailed Week 2 plan
│   ├── simulation-scenarios.md         # Transaction scenarios
│   └── data-analysis-plan.md           # Analysis methodology
│
├── docs/                               # 🆕 Supporting documentation
│   ├── SETUP.md                        # How to run everything
│   ├── DEPENDENCIES.md                 # What's needed
│   ├── TESTING.md                      # How to test
│   └── TROUBLESHOOTING.md              # Common issues
│
└── .env.example                        # 🆕 Example configuration
```

---

## What Needs to Be Created

### Immediate (Week 2 Start)

#### 1. `contribution/scripts/` folder
**Purpose:** All executable scripts for Week 2

**Files to create:**
- `README.md` - What each script does
- `requirements.txt` - Python dependencies (web3, pandas, matplotlib, etc.)
- `simulate_marketplace.py` - Main simulation script
- `verify_system_ready.py` - Check all 54 agents are ready
- `analyze_ratings.py` - Statistical analysis of results
- `export_transactions.py` - Export data to CSV

#### 2. `contribution/shared/` folder
**Purpose:** Minimal dependencies copied from main repo

**Files to copy:**
- `agent_config.py` - From `/shared/agent_config.py`
- `base_agent.py` - From `/shared/base_agent.py` (or document key methods)
- `secrets_manager.py` - From `/shared/secrets_manager.py`
- `README.md` - Explain what's copied and why

#### 3. `contribution/contracts/` folder
**Purpose:** Contract code for reference

**Files to create:**
- `ReputationRegistry.sol` - Copy from `/erc-8004/contracts/src/`
- `ReputationRegistry.abi.json` - Extract ABI
- `deployed_addresses.json` - Contract addresses
- `README.md` - Deployment information

#### 4. `contribution/plans/` folder
**Purpose:** Detailed implementation plans

**Files to create:**
- `week2-implementation-plan.md` - Detailed Week 2 execution plan
- `simulation-scenarios.md` - All 6 transaction scenarios detailed
- `data-analysis-plan.md` - How we'll analyze the data

#### 5. `contribution/docs/` folder
**Purpose:** Setup and usage documentation

**Files to create:**
- `SETUP.md` - How to set up the environment
- `DEPENDENCIES.md` - Required packages and tools
- `TESTING.md` - How to run tests
- `TROUBLESHOOTING.md` - Common issues and solutions

---

## Dependencies to Document

### Python Packages (for `scripts/requirements.txt`)
```txt
web3>=6.0.0
eth-account>=0.8.0
python-dotenv>=1.0.0
pandas>=2.0.0
matplotlib>=3.7.0
seaborn>=0.12.0
jupyter>=1.0.0
requests>=2.31.0
```

### External Dependencies
- Python 3.9+
- Access to Avalanche Fuji RPC
- AWS credentials (for Secrets Manager) OR local .env with keys
- 54 agent .env files (in main repo, referenced)

---

## Data Flow Design

### Input Data
```
Main Repo → contribution/
- Agent addresses (from /client-agents/*/. env)
- Contract addresses (from /erc-8004/.env.fuji)
- Base agent code (copied to contribution/shared/)
```

### Processing
```
contribution/scripts/simulate_marketplace.py
  ↓
Executes 100+ transactions on Fuji testnet
  ↓
Logs to contribution/week2/data/transactions.csv
```

### Analysis
```
contribution/scripts/analyze_ratings.py
  ↓
Reads contribution/week2/data/transactions.csv
  ↓
Outputs to contribution/analysis/
```

### Outputs
```
contribution/week2/
  ├── data/transactions.csv           # Raw data
  ├── 2.4-DAY4-ANALYSIS.md            # Text analysis
  └── 2.6-DAY5-EDGE-CASES.md          # Documented cases

contribution/analysis/
  ├── rating_patterns.ipynb            # Interactive analysis
  ├── statistical_summary.md           # Key findings
  └── visualizations/*.png             # Charts
```

---

## Scripts to Create - Detailed

### 1. `scripts/simulate_marketplace.py`
**Purpose:** Execute 100+ transactions with bidirectional ratings

**Functions:**
```python
def load_agents() -> list[ERC8004BaseAgent]:
    """Load all 54 agent configs from main repo"""

def scenario_good_transaction(buyer, seller) -> dict:
    """Simulate mutual 5/5 ratings"""

def scenario_bad_client(buyer, seller) -> dict:
    """Simulate seller rates client low"""

def scenario_bad_seller(buyer, seller) -> dict:
    """Simulate client rates seller low"""

def scenario_disputed(buyer, seller) -> dict:
    """Simulate asymmetric ratings"""

def scenario_validator_rating(seller, validator) -> dict:
    """Simulate seller rating validator"""

def execute_scenario(scenario_func, agents, count=20) -> list[dict]:
    """Execute a scenario N times with different agent pairs"""

def export_to_csv(transactions, filepath):
    """Export all transaction data to CSV"""

def main():
    """Main execution: run all scenarios and export data"""
```

**Command-line interface:**
```bash
# Dry run (no transactions)
python scripts/simulate_marketplace.py --dry-run

# Execute 100 transactions
python scripts/simulate_marketplace.py --execute --count 100

# Execute specific scenario
python scripts/simulate_marketplace.py --scenario bad_client --count 20
```

### 2. `scripts/verify_system_ready.py`
**Purpose:** Verify all 54 agents are registered and funded

**Functions:**
```python
def check_agent_registration(agent_address) -> bool:
    """Check if agent is registered on-chain"""

def check_agent_balance(agent_address) -> dict:
    """Check AVAX and GLUE balances"""

def verify_all_agents() -> dict:
    """Check all 54 agents, return summary"""

def main():
    """Print verification report"""
```

### 3. `scripts/analyze_ratings.py`
**Purpose:** Statistical analysis of transaction data

**Functions:**
```python
def load_transactions(csv_path) -> pd.DataFrame:
    """Load transaction CSV into pandas"""

def calculate_correlation(df) -> float:
    """Calculate buyer vs seller rating correlation"""

def find_asymmetric_ratings(df, threshold=2) -> pd.DataFrame:
    """Find transactions with rating difference > threshold"""

def generate_visualizations(df, output_dir):
    """Create histograms, scatter plots, network graphs"""

def export_summary(analysis_results, output_path):
    """Export markdown summary"""
```

---

## Execution Plan - Week 2

### Day 1 (4 hours): Setup & Design
**Tasks:**
- [ ] Create folder structure
- [ ] Copy dependencies to `contribution/shared/`
- [ ] Copy contract code to `contribution/contracts/`
- [ ] Create `contribution/scripts/requirements.txt`
- [ ] Write detailed simulation scenarios in `plans/simulation-scenarios.md`
- [ ] Write `docs/SETUP.md` for how to run everything

**Output:** Complete folder structure, no execution yet

### Day 2 (4 hours): Implement Simulation Script
**Tasks:**
- [ ] Implement `scripts/simulate_marketplace.py`
- [ ] Implement scenario functions (all 6)
- [ ] Implement transaction logging
- [ ] Implement CSV export
- [ ] Test with `--dry-run` mode

**Output:** Working simulation script (tested, not executed)

### Day 3 (4 hours): Execute Transactions
**Tasks:**
- [ ] Run `verify_system_ready.py` - confirm 54 agents ready
- [ ] Execute simulation: 100+ transactions
- [ ] Monitor on Snowtrace
- [ ] Export to CSV
- [ ] Take screenshots of key transactions
- [ ] Write `2.4-DAY3-EXECUTION-RESULTS.md`

**Output:** 100+ transactions on-chain, data exported

### Day 4 (4 hours): Analysis
**Tasks:**
- [ ] Implement `scripts/analyze_ratings.py`
- [ ] Run statistical analysis
- [ ] Generate visualizations
- [ ] Create Jupyter notebook for interactive analysis
- [ ] Write `2.5-DAY4-ANALYSIS.md`

**Output:** Statistical findings documented

### Day 5 (4 hours): Document Edge Cases
**Tasks:**
- [ ] Identify 6+ interesting edge cases from data
- [ ] For each: document transaction hash, ratings, significance
- [ ] Take Snowtrace screenshots
- [ ] Write `2.6-DAY5-EDGE-CASES.md`
- [ ] Update progress tracker
- [ ] Write Week 2 summary

**Output:** Complete Week 2 package ready for EIP submission

---

## Questions to Confirm Before Proceeding

1. **Folder structure:** Does the proposed structure make sense?
2. **Scripts location:** `contribution/scripts/` is the right place?
3. **Dependencies:** Should we copy all of `/shared/` or just key files?
4. **Agent configs:** Should we reference agent .env files from main repo, or copy them too?
5. **Testing:** Should we create tests in `contribution/tests/` or reference main repo tests?
6. **Data export:** CSV format sufficient, or also JSON/SQLite?

---

## Next Steps (After Approval)

1. **Create folder structure** - Set up all directories
2. **Copy dependencies** - Get required files into contribution/
3. **Write simulation scenarios document** - Detail all 6 scenarios
4. **Create requirements.txt** - List all Python packages
5. **Implement verify_system_ready.py** - First script (simpler)
6. **Implement simulate_marketplace.py** - Main script
7. **Test with dry-run** - Verify everything works
8. **Execute transactions** - Run for real
9. **Analyze results** - Statistical analysis
10. **Document findings** - Complete Week 2

---

**Status:** ⏸️ WAITING FOR APPROVAL

**Please review this plan and confirm:**
- ✅ Folder structure is correct
- ✅ Script design makes sense
- ✅ Execution plan is clear
- ✅ Any changes needed

**Then I'll proceed with implementation!**
