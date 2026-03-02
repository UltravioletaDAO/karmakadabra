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

### Facilitator DNS - DO NOT TOUCH
**⚠️ CRITICAL: User manages facilitator infrastructure separately**

- **Facilitator address**: `facilitator.ultravioletadao.xyz` (punto final, no discutir)
- ❌ **NEVER attempt to create/modify facilitator DNS records**
- ❌ **NEVER attempt to deploy/configure facilitator**
- ✅ User handles facilitator setup independently
- ✅ If facilitator has DNS issues, report to user - DO NOT fix

**Why separate**: Facilitator is critical infrastructure managed outside normal deployment flow.

### ECS Docker Deployments - CRITICAL CHECKLIST
**⚠️ INCIDENT: 2025-11-02 - 2 HOURS WASTED ON SIMPLE URL CHANGE**

**PROBLEM**: Changed `facilitator.prod.ultravioletadao.xyz` → `facilitator.ultravioletadao.xyz` in code, but ECS kept serving old code.

**ROOT CAUSES**:
1. Docker cache prevented new code from being copied to image
2. Pushed to WRONG ECR repository (didn't check task definition first)
3. ECS cached `:latest` tag, didn't pull fresh image

**MANDATORY CHECKLIST - FOLLOW BEFORE EVERY DEPLOYMENT:**

```bash
# 🚨 STEP 1: CHECK TASK DEFINITION FIRST - DO NOT SKIP
aws ecs describe-task-definition \
  --task-definition SERVICE-NAME:1 \
  --region us-east-1 \
  --query 'taskDefinition.containerDefinitions[0].image' \
  --output text
# Example output: 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/test-seller:latest
#                                                              ^^^^^^^^^^^ THIS IS THE REPO NAME

# 🚨 STEP 2: FOR CODE CHANGES - ALWAYS USE --no-cache
docker build --no-cache --platform linux/amd64 -t SERVICE:latest .

# 🚨 STEP 3: TAG AND PUSH TO CORRECT REPOSITORY (from Step 1)
docker tag SERVICE:latest ECR_REPO_FROM_STEP_1:latest
docker push ECR_REPO_FROM_STEP_1:latest

# 🚨 STEP 4: VERIFY IMAGE DIGEST MATCHES
# Get latest in ECR:
aws ecr describe-images \
  --repository-name REPO_NAME \
  --region us-east-1 \
  --query 'sort_by(imageDetails,&imagePushedAt)[-1].imageDigest' \
  --output text

# 🚨 STEP 5: FORCE FRESH PULL - STOP OLD TASK FIRST
aws ecs stop-task \
  --cluster karmacadabra-prod \
  --task TASK_ID \
  --reason "Force pull latest image" \
  --region us-east-1

aws ecs update-service \
  --cluster karmacadabra-prod \
  --service SERVICE_NAME \
  --force-new-deployment \
  --region us-east-1

# 🚨 STEP 6: WAIT AND VERIFY
sleep 90
curl -s https://SERVICE.karmacadabra.ultravioletadao.xyz/health
# VERIFY the change is actually there
```

**WHAT WENT WRONG (2025-11-02 incident)**:
1. ❌ Used deploy.sh which hit Docker cache → old code stayed
2. ❌ Rebuilt with `--no-cache` but pushed to `karmacadabra-prod-test-seller`
3. ❌ Task definition pointed to `karmacadabra/test-seller` (different repo!)
4. ❌ ECS kept pulling old cached image from correct repo
5. ❌ Took 2 HOURS to realize repository mismatch

### x402-rs Facilitator Upgrades - CRITICAL SAFEGUARDS
**⚠️ THIS IS USER-FACING INFRASTRUCTURE WITH DAO BRANDING - LIVE STREAM VISIBLE**

**INCIDENT HISTORY**: In the 0.7.9 → 0.9.0 upgrade, we used `cp -r upstream/* x402-rs/` which **OVERWROTE**:
- Custom branded landing page (Ultravioleta DAO branding, 57KB HTML vs upstream's "Hello from x402-rs!" text)
- Custom `get_root()` handler that served HTML via `include_str!()`
- All static assets (logos, favicon, network images)
- Recovery required: git history restoration, handler code rewrite, Docker rebuild, ECS redeploy

**🚨 NEVER USE `cp -r` OR MASS FILE COPY FROM UPSTREAM 🚨**

#### Protected Files - DO NOT OVERWRITE

**Tier 1: NEVER Copy from Upstream (Immediate Production Breakage)**
```
x402-rs/static/                      # Entire folder - Ultravioleta DAO branding
├── index.html                       # 57,662 bytes - custom branded landing page
├── favicon.ico                      # DAO favicon
└── images/                          # Network logos (avalanche.png, base.png, etc.)

x402-rs/Dockerfile                   # Custom: RUN rustup default nightly (edition 2024)
x402-rs/.env                         # If exists - production secrets
terraform/ecs-fargate/               # AWS deployment configs (not in x402-rs but related)
```

**Tier 2: Merge with EXTREME Care (Silent Integration Failures)**
```
x402-rs/src/handlers.rs              # Lines ~76-85: get_root() uses include_str!("../static/index.html")
                                     # Upstream: Returns Html("Hello from x402-rs!")
                                     # Ours: Returns Html(include_str!("../static/index.html"))

x402-rs/src/network.rs               # ALL 17 FUNDED NETWORKS - NEVER REMOVE ANY:
                                     # Mainnets (7): Base, Avalanche, Celo, HyperEVM, Polygon, Solana, Optimism
                                     # Testnets (10): Base Sepolia, Avalanche Fuji, Celo Sepolia, HyperEVM Testnet,
                                     #                Polygon Amoy, Solana Devnet, Optimism Sepolia, Sei, Sei Testnet, XDC
                                     # ⚠️ ALL wallets are funded - removing networks BREAKS production
                                     # Each has: Network enum, Display impl, NetworkFamily, variants(), USDC deployment

x402-rs/src/main.rs                  # AWS Secrets Manager integration (if implemented)
x402-rs/Cargo.toml                   # AWS SDK dependencies, custom version pins
```

**Tier 3: Safe to Upgrade (But Test Extensively)**
```
x402-rs/src/auth.rs                  # Core payment verification - test with test_glue_payment_simple.py
x402-rs/src/error.rs                 # Error handling
x402-rs/tests/                       # Our custom tests - preserve these
```

#### Safe Upgrade Process (MANDATORY - Follow Exactly)

**Step 1: Prepare Git Branch Strategy**
```bash
cd x402-rs

# First time only: Create upstream tracking branch
git checkout -b upstream-mirror
git remote add upstream https://github.com/polyphene/x402-rs  # Verify URL first
git fetch upstream
git reset --hard upstream/main
git push origin upstream-mirror

# Create production branch (first time only)
git checkout -b karmacadabra-production
git push origin karmacadabra-production
```

**Step 2: Before ANY Upgrade - Backup Customizations**
```bash
# Create timestamped backup
$VERSION = "0.9.0"  # Change to target version
$BACKUP_DIR = "x402-rs-backup-$VERSION-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# Backup critical files
mkdir $BACKUP_DIR
cp x402-rs/static/ $BACKUP_DIR/static/ -Recurse
cp x402-rs/src/handlers.rs $BACKUP_DIR/
cp x402-rs/src/network.rs $BACKUP_DIR/
cp x402-rs/Dockerfile $BACKUP_DIR/
cp x402-rs/Cargo.toml $BACKUP_DIR/

# Document current state
cd x402-rs
git diff upstream-mirror > ../$BACKUP_DIR/our-customizations.patch
cd ..

Write-Host "Backup saved to: $BACKUP_DIR"
```

**Step 3: Fetch Upstream Changes**
```bash
# Update upstream mirror
git checkout upstream-mirror
git pull upstream main  # Or specific tag: git pull upstream v0.10.0

# Review what changed
git log --oneline HEAD~10..HEAD  # Last 10 upstream commits
git diff HEAD~1 -- src/handlers.rs src/network.rs  # Check critical files
```

**Step 4: Merge with Surgical Precision**
```bash
# Switch to production branch
git checkout karmacadabra-production

# Attempt merge (will likely have conflicts)
git merge upstream-mirror

# ⚠️ RESOLVE CONFLICTS CAREFULLY ⚠️
# For each conflict, decide:
# - handlers.rs: KEEP our include_str!() version
# - network.rs: KEEP our custom networks, ADD new upstream networks if any
# - Cargo.toml: MERGE dependencies (keep AWS SDK + add new upstream deps)
# - Dockerfile: KEEP our nightly Rust line

# Check what files have conflicts
git status

# For each conflicted file:
# 1. Open in editor
# 2. Search for <<<<<<< HEAD markers
# 3. Keep our customizations, integrate upstream improvements
# 4. Mark resolved: git add <file>
```

**Step 5: Restore Static Files (ALWAYS - Even if No Conflict)**
```bash
# Static files should NEVER come from upstream
# Force restore from backup
cp $BACKUP_DIR/static/ x402-rs/static/ -Recurse -Force

# Verify branding intact
Select-String -Path x402-rs/static/index.html -Pattern "Ultravioleta DAO"
# Should output line containing "Ultravioleta DAO"
```

**Step 6: Manual Code Verification**
```bash
# Check critical functions preserved
Select-String -Path x402-rs/src/handlers.rs -Pattern "include_str"
# Should find: include_str!("../static/index.html")

# Check custom networks preserved
Select-String -Path x402-rs/src/network.rs -Pattern "HyperEVM|Optimism"
# Should find both networks

# Check Dockerfile preserved
Select-String -Path x402-rs/Dockerfile -Pattern "rustup default nightly"
# Should find nightly setup
```

**Step 7: MANDATORY Testing Checklist**
```bash
# 1. Build test
cd x402-rs
cargo clean  # Force full rebuild
cargo build --release
# ✅ Must succeed without errors

# 2. Run locally
cargo run &
$FACILITATOR_PID = $LastExitCode
Start-Sleep -Seconds 5

# 3. Health check
curl http://localhost:8080/health
# ✅ Must return 200 OK

# 4. Branding verification
$response = curl http://localhost:8080/
$response -match "Ultravioleta DAO"
# ✅ Must be True

# 5. Custom networks verification
curl http://localhost:8080/networks | Select-String "HyperEVM"
# ✅ Must find HyperEVM

# 6. Payment flow test
cd ../scripts
python test_glue_payment_simple.py --facilitator http://localhost:8080
# ✅ Must complete payment successfully

# 7. Stop test instance
Stop-Process -Id $FACILITATOR_PID

# 8. Docker build test
cd ../x402-rs
docker build -t x402-test:latest .
# ✅ Must build successfully

# 9. Docker runtime test
docker run -d -p 8080:8080 --name x402-test x402-test:latest
Start-Sleep -Seconds 5
curl http://localhost:8080/ | Select-String "Ultravioleta"
# ✅ Must find "Ultravioleta"

docker stop x402-test
docker rm x402-test
```

**Step 8: Production Deployment (ONLY After All Tests Pass)**
```bash
# Commit merge
git add .
git commit -m "Merge upstream x402-rs v0.X.X

- Preserved Ultravioleta DAO branding (static/)
- Preserved custom handlers (include_str! in get_root)
- Preserved custom networks (HyperEVM, Optimism, Polygon, Solana)
- Integrated upstream improvements: [LIST WHAT YOU TOOK FROM UPSTREAM]

Tested:
- [x] Local cargo build/run
- [x] Branding verification
- [x] Payment flow
- [x] Docker build/run
- [x] All endpoints responding

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push to repository
git push origin karmacadabra-production

# Deploy to ECS (triggers automatic build + deploy via Terraform/CI)
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-facilitator \
  --force-new-deployment \
  --region us-east-1

# Monitor deployment
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1 \
  --query 'services[0].deployments'

# Wait for healthy
Start-Sleep -Seconds 60

# Verify production
curl https://facilitator.karmacadabra.ultravioletadao.xyz/health
curl https://facilitator.karmacadabra.ultravioletadao.xyz/ | Select-String "Ultravioleta"
```

**Step 9: Post-Deployment Verification**
```bash
# Test production payment flow
cd scripts
python test_glue_payment_simple.py --production
# ✅ Must succeed

# Test from each agent (they depend on facilitator)
curl https://validator.karmacadabra.ultravioletadao.xyz/health
curl https://karma-hello.karmacadabra.ultravioletadao.xyz/health
# All should respond

# Check ECS logs for errors
aws logs tail /ecs/karmacadabra-prod-facilitator --follow --region us-east-1
# Should show no errors
```

#### Emergency Rollback Procedure

**If production breaks after deployment:**

```bash
# 1. Immediate: Roll back ECS to previous task definition
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-facilitator \
  --task-definition karmacadabra-prod-facilitator:PREVIOUS_REVISION \
  --force-new-deployment \
  --region us-east-1

# 2. Git: Revert to last working commit
git log --oneline -5  # Find last good commit
git revert HEAD  # Or git reset --hard <commit> if not pushed
git push origin karmacadabra-production

# 3. Restore from backup
cp $BACKUP_DIR/* x402-rs/ -Recurse -Force

# 4. Verify local, then redeploy
# Follow Step 7 (testing) and Step 8 (deployment) again
```

#### Architectural Decision: When to Fork vs Merge

**Merge from upstream when:**
- ✅ Upstream adds features we want (new networks, better error handling)
- ✅ Security patches or bug fixes
- ✅ Performance improvements
- ✅ We can preserve customizations via git merge

**Maintain permanent fork when:**
- ❌ Upstream makes breaking API changes incompatible with our agents
- ❌ Upstream removes features we depend on
- ❌ Customizations become too extensive (>30% of codebase modified)
- ❌ Upstream project abandoned or changes license

**Current status**: MERGE strategy is viable. Customizations are isolated (~5% of codebase).

**Review quarterly**: Check upstream activity, evaluate fork burden.

#### Prevention: Automation (Future Enhancement)

**Option 1: Pre-commit hook** (prevents accidental commits)
```bash
# .git/hooks/pre-commit
#!/bin/bash
if git diff --cached --name-only | grep -q "x402-rs/static/"; then
  echo "⚠️  WARNING: You are committing changes to x402-rs/static/"
  echo "This folder contains custom Ultravioleta DAO branding."
  echo "Are you SURE this is intentional? (Ctrl+C to cancel)"
  read -p "Continue? (yes/no): " confirm
  if [ "$confirm" != "yes" ]; then
    exit 1
  fi
fi
```

**Option 2: CI/CD verification** (catches before production)
```yaml
# .github/workflows/verify-branding.yml
name: Verify x402-rs Branding
on: [push, pull_request]
jobs:
  check-branding:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Verify Ultravioleta branding present
        run: |
          grep -q "Ultravioleta DAO" x402-rs/static/index.html || exit 1
          grep -q "include_str!" x402-rs/src/handlers.rs || exit 1
          grep -q "HyperEVM" x402-rs/src/network.rs || exit 1
```

**Option 3: Separate overlay directory** (advanced - requires build script)
```
x402-rs/
├── upstream/          # Pure upstream code (git subtree)
├── overlays/
│   ├── static/        # Our branded files
│   ├── handlers.patch # Patch for include_str!()
│   └── network.patch  # Patch for custom networks
└── build.sh           # Applies overlays to upstream
```

**Recommendation**: Start with **manual process** (this document). Add **CI/CD verification** (Option 2) next sprint. Consider **overlay system** (Option 3) only if we fork >5 files.

### Documentation Synchronization
- ✅ **README.md** ↔️ **README.es.md** MUST stay synchronized
- Update both when changing architecture, features, or any content
- **NON-NEGOTIABLE** for bilingual community

### File Organization - STRICT ROOT DIRECTORY RULES

**⚠️ ROOT DIRECTORY POLLUTION IS A RECURRING PROBLEM**

**ONLY 4 markdown files allowed in root:**
1. `README.md` - Main documentation (English)
2. `README.es.md` - Main documentation (Spanish) - MUST stay synced with README.md
3. `MASTER_PLAN.md` - Project vision and roadmap
4. `CLAUDE.md` - This file (AI assistant guidelines)

**ALL other documentation MUST be organized:**

```
karmacadabra/
├── plans/                    # Major architectural plans and master plans
│   ├── FACILITATOR_CLEANUP_PLAN.md
│   ├── FACILITATOR_EXTRACTION_MASTER_PLAN.md
│   └── rpc-resilience-master-plan.md
│
├── docs/
│   ├── reports/              # Bug investigations, infrastructure analysis
│   │   ├── BASE_USDC_BUG_INVESTIGATION_REPORT.md
│   │   ├── AWS_INFRASTRUCTURE_ANALYSIS_*.md
│   │   ├── GLUE_PAYMENT_DEBUG_SUMMARY.md
│   │   └── *_BUG.md, *_INVESTIGATION.md, *_ANALYSIS.md
│   │
│   ├── plans/                # Sprint plans, status reports, daily check-ins
│   │   ├── SPRINT_*_SUMMARY.md
│   │   ├── DEPLOYMENT_SUCCESS.md
│   │   └── SYSTEM_STATUS_REPORT.md
│   │
│   ├── guides/               # How-to guides and tutorials
│   │   ├── QUICKSTART.md
│   │   └── DOCKER_GUIDE.md
│   │
│   ├── ARCHITECTURE.md       # Technical architecture docs
│   ├── MONETIZATION_OPPORTUNITIES.md
│   ├── *_SUMMARY.md          # Project summaries
│   ├── *_DELIVERY.md         # Delivery documentation
│   └── *_LOCATION.md         # Configuration locations
│
├── tests/                    # ALL test files
├── scripts/                  # ALL utility scripts
├── logs/                     # ALL log files (gitignored)
├── shared/                   # Shared libraries
├── *-agent/                  # Agent implementations
├── erc-20/                   # GLUE token
├── erc-8004/                 # Registry contracts
└── x402-rs/                  # Facilitator (Rust)
```

**Classification Rules:**

**→ `plans/`** (root-level, major plans):
- ✅ Master plans with >20KB content
- ✅ Multi-sprint architectural roadmaps
- ✅ Major feature integration plans
- ✅ Pattern: `*_MASTER_PLAN.md`, `*-integration-plan.md`

**→ `docs/reports/`** (investigations & analysis):
- ✅ Bug investigation reports
- ✅ Infrastructure analysis
- ✅ Debug summaries
- ✅ Technical diagrams
- ✅ Pattern: `*_BUG*.md`, `*_INVESTIGATION*.md`, `*_ANALYSIS*.md`, `*_DEBUG*.md`, `*_DIAGRAM.md`, `*_EXTRACTION*.md`

**→ `docs/plans/`** (smaller plans & status):
- ✅ Sprint summaries
- ✅ Daily check-ins
- ✅ Deployment reports
- ✅ System status
- ✅ Pattern: `SPRINT_*.md`, `DAILY_*.md`, `DEPLOYMENT_*.md`, `SYSTEM_*.md`

**→ `docs/`** (general documentation):
- ✅ Feature summaries
- ✅ Delivery documentation
- ✅ Configuration locations
- ✅ Architecture docs
- ✅ Monetization docs
- ✅ Pattern: `*_SUMMARY.md`, `*_DELIVERY.md`, `*_LOCATION.md`, `ARCHITECTURE*.md`

**→ `docs/guides/`** (tutorials):
- ✅ Quickstart guides
- ✅ How-to documentation
- ✅ Setup tutorials
- ✅ Pattern: `*_GUIDE.md`, `QUICKSTART*.md`, `HOW_TO_*.md`

**ENFORCEMENT:**

**Before creating ANY new .md file, ask:**
1. Is this README.md, README.es.md, MASTER_PLAN.md, or CLAUDE.md? → Root only if yes
2. Is this a major architectural plan (>20KB)? → `plans/`
3. Is this a bug report or investigation? → `docs/reports/`
4. Is this a sprint/status/deployment report? → `docs/plans/`
5. Is this a tutorial or guide? → `docs/guides/`
6. Everything else → `docs/`

**❌ NEVER create files in root without explicit justification**
**✅ ALWAYS use organized folders for new documentation**

**Cleanup checklist (run quarterly):**
```bash
# List all .md files in root (should only show 4)
ls -1 *.md
# Expected: CLAUDE.md, MASTER_PLAN.md, README.md, README.es.md

# If there are more, classify and move them:
# - Plans → plans/
# - Reports → docs/reports/
# - Status → docs/plans/
# - Docs → docs/
```

### JSON File Organization - NO .json FILES IN ROOT

**⚠️ CRITICAL: NO .json FILES SHOULD EVER EXIST IN ROOT DIRECTORY**

All JSON configuration files must be organized in appropriate subdirectories:

**→ `terraform/ecs-fargate/task-definitions/`** (ECS task definitions):
- ✅ All ECS Fargate task definition JSON files
- ✅ Pattern: `*-task-def*.json`, `task-def-*.json`
- ✅ Examples: `facilitator-task-def-mainnet.json`, `test-seller-solana.json`

**→ `terraform/ecs-fargate/service-configs/`** (ECS service configs):
- ✅ ECS service creation configurations
- ✅ Pattern: `create-service-*.json`, `*-service-config.json`
- ✅ Examples: `create-service-solana.json`

**→ `terraform/ecs-fargate/route53-changes/`** (DNS configurations):
- ✅ Route53 DNS change batch files
- ✅ Pattern: `route53-change-*.json`, `dns-*.json`
- ✅ Examples: `route53-change-solana.json`

**→ Component-specific folders** (other configs):
- `erc-20/`: Token contract configs
- `erc-8004/`: Registry contract configs
- `*-agent/`: Agent-specific configurations
- `scripts/`: Script configuration files

**ENFORCEMENT:**

**Before creating ANY .json file:**
1. Is this an ECS task definition? → `terraform/ecs-fargate/task-definitions/`
2. Is this an ECS service config? → `terraform/ecs-fargate/service-configs/`
3. Is this a Route53 DNS change? → `terraform/ecs-fargate/route53-changes/`
4. Is this agent/contract config? → Respective component folder
5. Is this a script config? → `scripts/` or component folder

**❌ NEVER create .json files in root**
**✅ ALWAYS place in appropriate infrastructure or component folder**

**When moving .json files:**
- ❌ Don't just move - ALWAYS search for references first
- ✅ Use grep to find all references: `grep -r "filename.json"`
- ✅ Update ALL references to new paths
- ✅ Test scripts/tools that use the file

**Verification:**
```bash
# Should return empty or error
ls -1 *.json 2>/dev/null
# Expected: "No such file or directory" or nothing
```

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

---

## Obsidian Vault — Shared Agent State

KarmaCadabra uses an **Obsidian Vault** (`vault/`) as a shared state layer between all 24 agents. The vault is a directory of markdown files with YAML frontmatter, synced via git.

### Architecture
- **Location**: `vault/` subdirectory in repo root
- **Sync**: Agents read/write directly to filesystem, commit/push via git
- **Library**: `lib/vault_sync.py` uses `python-frontmatter` for YAML metadata
- **Conflict avoidance**: Each agent writes ONLY to `vault/agents/<agent-name>/`
- **Human view**: Open `vault/` as an Obsidian vault with Dataview plugin for dashboards

### Vault Structure
```
vault/
  agents/<agent-name>/state.md    # Per-agent status (frontmatter + body)
  agents/<agent-name>/memory.md   # Long-term learnings
  agents/<agent-name>/log-*.md    # Daily activity logs
  shared/config.md                # Network config, pricing
  shared/supply-chain.md          # Data flow between agents
  shared/ledger.md                # Transaction history
  shared/tasks.md                 # Shared task board
  knowledge/                      # Contracts, APIs, protocols docs
  dashboards/                     # Dataview queries for monitoring
  projects/                       # Cross-project links (AbraCadabra, KarmaGelou, EM)
```

### Agent State Format
Each agent's `state.md` has YAML frontmatter with:
- `agent_id`, `status`, `role`, `last_heartbeat`, `current_task`
- `wallet`, `executor_id`, `erc8004_id`, `chain`
- `daily_revenue_usdc`, `daily_spent_usdc`, `tasks_completed`
- `tags`, `aliases` (for Obsidian search/Dataview)

### Usage in Code
```python
from lib.vault_sync import VaultSync

vault = VaultSync("/app/vault", "kk-karma-hello")
vault.pull()
vault.write_state({"status": "active", "current_task": "publishing"})
vault.append_log("Published 5 bundles on EM")
vault.commit_and_push("published data bundles")

# Read peer state
peer = vault.read_peer_state("kk-skill-extractor")
print(peer["status"])  # "active"
```

### Wikilinks Convention
Use `[[agent-name]]` wikilinks to cross-reference between vault notes:
- `[[kk-karma-hello]]` links to that agent's state
- `[[execution-market]]` links to API docs in knowledge/
- `[[supply-chain]]` links to the data flow diagram

### Rules
- Agents write ONLY to their own `vault/agents/<name>/` directory
- Shared files (`vault/shared/`) written by coordinator or heartbeat only
- Log files use `merge=union` in `.gitattributes` to prevent conflicts
- All timestamps in ISO 8601 UTC format
- Tags use plural form: `tags`, `aliases` (Obsidian standard)

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

## Claude Code Skills (Operational Knowledge)

Three custom skills are installed at `.claude/skills/` that encode operational knowledge for the KK swarm. Use them proactively:

### kk-deploy
**Trigger**: "deploy", "build and push", "restart agents", "update agents", "rebuild Docker"
**What**: Full Docker build + ECR push + deploy to 7 EC2 agents pipeline. Has all agent IPs, ECR repo, SSH key path, and parallel deploy pattern. Use after committing code changes to `heartbeat.py`, `services/`, `lib/`, `cron/`, `openclaw/`.

### kk-swarm-monitor
**Trigger**: "check agents", "monitor swarm", "check logs", "agent health", "check heartbeats", "check balances"
**What**: Monitoring and diagnostics for 7 EC2 agents. SSH log checks, `swarm_ops.py` commands, IRC checks, vault state inspection. Use proactively after deployments.

### kk-em-operations
**Trigger**: "EM tasks", "escrow flow", "browse marketplace", "debug EM", "supply chain", "bounties"
**What**: Execution Market API operations. Documents the correct escrow flow (BUYER posts bounty → SELLER applies → assign → submit → approve), evidence format, common errors (422/409/429), and supply chain steps.

### irc-agent
**Trigger**: "connect to IRC", "chat on IRC", "join IRC"
**What**: IRC communication for Claude Code sessions. Connects to MeshRelay for inter-agent collaboration.

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

## Launching New Community Agents

When the user asks to launch a new agent, follow the onboarding pipeline in `docs/guides/AGENT_ONBOARDING.md`. The full checklist:

1. Verify agent exists in `data/config/identities.json` (address, executor_id, ERC-8004 agent_id)
2. Create `openclaw/agents/kk-<name>/SOUL.md` (use existing community agent as template, keep BASE SOUL)
3. Copy `HEARTBEAT.md` from existing agent
4. Fund wallet ($5+ USDC on Base + gas) via `blockchain/fund-agents.ts`
5. Create AWS secret `kk/kk-<name>` in us-east-1 with `{"private_key":"0x..."}`
6. Add to `terraform/openclaw/variables.tf` agents map
7. Rebuild Docker image (`docker build --no-cache -f Dockerfile.openclaw`) and push to ECR
8. `terraform apply` to create EC2 instance
9. Verify: container running, IRC connected, skills loaded, S3 cron active

**Available agents** (registered but not deployed): HD indices 7-10, 12-23. Check `identities.json`.

---

## Documentation Map

- **MASTER_PLAN.md**: Vision, roadmap, all components
- **docs/ARCHITECTURE.md**: Technical decisions, data flows
- **docs/MONETIZATION_OPPORTUNITIES.md**: 50+ services with pricing
- **docs/guides/QUICKSTART.md**: 30-minute setup
- **docs/guides/AGENT_ONBOARDING.md**: New agent launch pipeline
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
- mira, NUCNA ok NUNCA le agreges emotes a los logs de rust, se daña el build o algo malo siempre pasa
- The latest nightly now defaults to edition 2024, which has breaking changes that are incompatible       
  with the current codebase.
- i think the nightly build is not gonna ever work, never use it
- OK COMMIT EVERY TIME YOU DEEM IT NESSESARY
- if you need to check the facilitator code, use this Z:\ultravioleta\dao\facilitator
- the facilitator is running in aws fargate in us-east-2 and this is the command to check the logs so you know:\
\
Check facilitator logs:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/facilitator-production \
  --filter-pattern "[SETTLEMENT]" \
  --region us-east-2
```
- dont proceed with the facilitator implementation the facilitator with testnet functionality is already live at facilitator.ultravioletadao.xyz