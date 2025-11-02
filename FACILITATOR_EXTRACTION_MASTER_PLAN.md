# Facilitator Extraction Master Plan

> **Mission**: Extract x402-rs facilitator from karmacadabra monorepo into a standalone, production-ready repository while preserving git history, infrastructure code, and all custom branding.

---

## Executive Summary

### What We're Extracting

The **x402-rs facilitator** is a production payment infrastructure component serving 17 blockchain networks. It started as a demo within karmacadabra but has evolved into a multi-network payment processor that:

- Processes gasless micropayments via HTTP 402 protocol
- Supports 17 networks (10 testnets + 7 mainnets)
- Has **CRITICAL custom branding** (Ultravioleta DAO landing page - 57KB HTML)
- Runs in production on AWS ECS Fargate
- Is referenced by karmacadabra agents but is architecturally independent

### Why Extract Now

1. **Architectural Independence**: Facilitator is Layer 2, agents are Layer 3 - clean separation exists
2. **Reusability**: Other projects (e.g., Lighthouse monitoring) want to use facilitator without pulling karmacadabra
3. **Deployment Isolation**: Facilitator has separate AWS infrastructure, can deploy independently
4. **Maintenance Clarity**: Upstream x402-rs updates should not touch karmacadabra codebase
5. **Security Scope**: Separate repos = separate security audit scopes

### Success Criteria

- [ ] Facilitator runs independently with `docker-compose up`
- [ ] All 57KB custom branding preserved (CRITICAL - see CLAUDE.md incident history)
- [ ] Production AWS infrastructure functional via Terraform
- [ ] Git history preserved for facilitator-specific commits
- [ ] Karmacadabra agents can still consume facilitator as external service
- [ ] Documentation complete for standalone usage
- [ ] Zero production downtime during cutover

### Risk Level: **MEDIUM-HIGH**

**High-risk areas**:
- Branding assets loss (happened before with upstream merge)
- AWS Secrets Manager references breaking
- Docker Compose networking changes
- Terraform state migration
- Production facilitator endpoint downtime

**Mitigation**: Comprehensive testing, staged rollout, rollback procedures

---

## Phase-by-Phase Breakdown

### Phase 1: Discovery & Inventory (Estimated: 4-6 hours)

**Goal**: Map every file, dependency, and reference related to facilitator

#### Task 1.1: File Inventory Categorization

Scan these directories and categorize EVERY file:

**Primary Scan Targets**:
```
x402-rs/                    # Core facilitator source
terraform/ecs-fargate/      # Infrastructure (SHARED with agents!)
scripts/                    # Look for facilitator-specific scripts
tests/                      # Look for facilitator/x402/payment tests
docs/                       # Facilitator documentation
Root level                  # docker-compose.yml, .gitignore, READMEs
```

**File Categories**:

1. **CORE** (must move - facilitator source code)
   - `x402-rs/src/` - All Rust source files
   - `x402-rs/static/` - **CRITICAL BRANDING** (57KB HTML, logos, favicon)
   - `x402-rs/Cargo.toml` - Rust dependencies
   - `x402-rs/Dockerfile` - Container build instructions
   - `x402-rs/.env.example` - Configuration template

2. **TESTS** (facilitator-specific tests to move)
   - Look for: `test_glue_payment*.py`, `test_usdc_payment*.py`, `test_facilitator*.py`
   - Look in: `scripts/`, `tests/`, `test-seller/`

3. **SCRIPTS** (deployment, testing, utilities)
   - Facilitator-specific deployment scripts
   - Payment testing utilities
   - AWS deployment automation

4. **DOCS** (facilitator documentation)
   - `x402-rs/README.md` - Main documentation
   - `docs/X402_FORK_STRATEGY.md` - Upstream merge strategy
   - Any x402-specific guides

5. **CONFIG** (environment, addresses, secrets)
   - `x402-rs/.env` (if exists - likely gitignored)
   - AWS Secrets Manager keys: `karmacadabra-facilitator-mainnet`, `karmacadabra-facilitator-testnet`
   - Terraform variable files referencing facilitator

6. **SHARED** (used by facilitator + other components - DECISION NEEDED)
   - `terraform/ecs-fargate/` - **CRITICAL DECISION POINT**
     - Contains BOTH facilitator + 5 agent infrastructure
     - Options: COPY entire dir, SPLIT by service, or REFERENCE externally
   - `docker-compose.yml` - Facilitator service definition (lines 35-78)
   - `.gitignore` - Facilitator-relevant entries
   - `README.md` - Facilitator sections (links, architecture diagrams)

**Deliverable**: `FACILITATOR_FILE_INVENTORY.md` with categorized file list

#### Task 1.2: Dependency Graph Mapping

**Import Analysis**:
```bash
# Find all Python imports of facilitator
cd z:\ultravioleta\dao\karmacadabra
grep -r "facilitator" --include="*.py" agents/ shared/ scripts/ tests/ | grep -v ".pyc"

# Find Terraform references
grep -r "facilitator" terraform/ --include="*.tf" --include="*.tfvars"

# Find docker-compose references
grep -r "facilitator" docker-compose*.yml
```

**Environment Variable Analysis**:
```bash
# Find all FACILITATOR_URL references
grep -r "FACILITATOR_URL" --include="*.py" --include=".env*"

# Find AWS Secrets Manager references
grep -r "karmacadabra-facilitator" terraform/ scripts/ --include="*.tf" --include="*.py"
```

**Deliverable**: Dependency graph showing:
- Which karmacadabra components import facilitator code
- Which agents call facilitator endpoints
- Which Terraform modules reference facilitator

#### Task 1.3: Git History Analysis

**Identify Facilitator-Specific Commits**:
```bash
# Commits touching x402-rs/
git log --oneline --all -- x402-rs/ > facilitator_commits.txt

# Commits referencing "facilitator" in message
git log --oneline --all --grep="facilitator" --grep="x402" >> facilitator_commits.txt

# Stats
git log --shortstat --all -- x402-rs/ | grep "files changed"
```

**Deliverable**:
- `facilitator_commits.txt` - List of relevant commit SHAs
- Decision: Preserve history via `git filter-branch` or fresh start with reference?

---

### Phase 2: Architecture Design (Estimated: 3-4 hours)

**Goal**: Design the target repository structure and integration strategy

#### Task 2.1: Target Repository Structure

**Proposed Structure** (based on standalone facilitator needs):

```
facilitator/                          # New repo root
├── src/                              # Rust source (from x402-rs/src/)
│   ├── main.rs                       # Entrypoint
│   ├── handlers.rs                   # HTTP endpoints
│   ├── network.rs                    # Network configs (17 networks)
│   ├── chain/                        # Blockchain integrations
│   │   ├── evm.rs
│   │   └── solana.rs
│   ├── facilitator.rs                # Core logic
│   └── telemetry.rs                  # OpenTelemetry
├── static/                           # **CRITICAL BRANDING ASSETS**
│   ├── index.html                    # 57KB Ultravioleta DAO landing page
│   ├── favicon.ico
│   ├── logo.png
│   └── images/                       # Network logos
│       ├── avalanche.png
│       ├── base.png
│       ├── celo.png
│       ├── hyperevm.png
│       ├── polygon.png
│       ├── solana.png
│       └── optimism.png
├── crates/                           # Workspace crates (from x402-rs/crates/)
│   ├── x402-axum/                    # Server middleware
│   └── x402-reqwest/                 # Client middleware
├── examples/                         # Usage examples
│   ├── x402-axum-example/
│   └── x402-reqwest-example/
├── tests/                            # All facilitator tests
│   ├── integration/                  # End-to-end payment tests
│   │   ├── test_glue_payment_simple.py
│   │   ├── test_usdc_payment_base.py
│   │   └── test_payment_stress.py
│   └── unit/                         # Rust unit tests
├── scripts/                          # Deployment & testing utilities
│   ├── deploy/
│   │   ├── build-and-push.sh         # Docker build + ECR push
│   │   ├── deploy-to-fargate.sh      # ECS deployment
│   │   └── rollback.sh               # Emergency rollback
│   ├── test/
│   │   ├── test_all_networks.py      # Verify all 17 networks
│   │   └── test_production.py        # Production smoke tests
│   └── monitoring/
│       ├── check_health.sh           # Health check script
│       └── view_logs.sh              # CloudWatch log viewer
├── terraform/                        # **DECISION POINT - See Task 2.2**
│   ├── facilitator-only/             # Option 1: Facilitator-only infra
│   │   ├── main.tf                   # ECS service for facilitator
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   └── examples/                     # Example deployments
│       ├── aws-ecs-fargate/          # Full AWS example
│       └── docker-compose/           # Local testing
├── docs/                             # Documentation
│   ├── QUICKSTART.md                 # 5-minute setup guide
│   ├── DEPLOYMENT.md                 # AWS/GCP/Azure deployment guides
│   ├── NETWORKS.md                   # Supported networks & RPC config
│   ├── CUSTOMIZATION.md              # How to customize branding
│   ├── UPSTREAM_MERGE.md             # Safe merge strategy (from CLAUDE.md)
│   └── ARCHITECTURE.md               # Technical deep dive
├── .github/                          # CI/CD workflows
│   └── workflows/
│       ├── test.yml                  # Run tests on PR
│       ├── build.yml                 # Build Docker image
│       └── deploy.yml                # Deploy to production (manual trigger)
├── Cargo.toml                        # Rust workspace root
├── Dockerfile                        # Multi-stage Docker build
├── docker-compose.yml                # Local development stack
├── .env.example                      # Configuration template
├── .gitignore                        # Ignore patterns
├── README.md                         # Main documentation
├── LICENSE                           # Apache-2.0
└── CHANGELOG.md                      # Version history

Total directories: ~15
Total files (estimated): ~80-100
```

**Key Decisions**:

1. **Keep Rust workspace structure** (crates/, examples/) - facilitator is already a workspace
2. **Move all branding assets** - static/ folder is CRITICAL, must preserve exactly
3. **Separate tests/** - Extract only facilitator-specific tests, not agent tests
4. **Terraform decision** - See Task 2.2

#### Task 2.2: Terraform Infrastructure Decision

**Problem**: `terraform/ecs-fargate/` contains infrastructure for:
- 1 facilitator service
- 5 agent services (validator, karma-hello, abracadabra, skill-extractor, voice-extractor)
- Shared VPC, ALB, Route53, CloudWatch, ECR repositories

**Option 1: COPY Entire Terraform Directory** ✅ **RECOMMENDED**

```
facilitator/
└── terraform/
    ├── ecs-fargate/          # Full copy from karmacadabra
    │   ├── main.tf           # Keep all services, simplify later
    │   ├── networking.tf
    │   ├── alb.tf
    │   └── ...
    └── facilitator-only/     # Future: Simplified single-service version
        └── main.tf
```

**Pros**:
- Works immediately (no Terraform rewrite)
- Preserves all working infrastructure code
- Can deploy facilitator + agents together if needed
- Gradual simplification possible

**Cons**:
- Contains agent infrastructure (can remove later)
- Larger terraform/ directory

**Option 2: SPLIT Terraform by Service** ❌ **NOT RECOMMENDED**

Extract only facilitator-specific resources (ECS service, task definition, ALB rules).

**Pros**: Clean separation

**Cons**:
- Breaks shared resources (VPC, ALB, NAT Gateway)
- Requires rewriting Terraform modules
- High risk of breaking production
- Shared ALB means agents + facilitator MUST deploy together

**Option 3: REFERENCE External Terraform** ❌ **NOT RECOMMENDED**

Keep Terraform in karmacadabra, reference via remote state.

**Pros**: DRY (Don't Repeat Yourself)

**Cons**:
- Tight coupling between repos
- Can't deploy facilitator without karmacadabra repo
- Version drift issues

**DECISION**: **Option 1 (COPY)** with future cleanup plan

**Action Items**:
- Copy entire `terraform/ecs-fargate/` to `facilitator/terraform/ecs-fargate/`
- Add comment to `variables.tf`: "Contains agent infrastructure - safe to remove if deploying facilitator standalone"
- Create `terraform/facilitator-only/` as future simplification target
- Document in `terraform/README.md` which resources are facilitator-specific

#### Task 2.3: Dependency Resolution Strategy

**For each dependency category, decide: MOVE, COPY, EXTRACT, or EXTERNAL**

| Dependency | Strategy | Justification |
|------------|----------|---------------|
| **x402-rs/src/** | **MOVE** | Core facilitator code, no shared usage |
| **x402-rs/static/** | **MOVE** | Critical branding, facilitator-specific |
| **x402-rs/Cargo.toml** | **MOVE** | Rust dependencies |
| **x402-rs/Dockerfile** | **MOVE** | Container build |
| **terraform/ecs-fargate/** | **COPY** | Shared infra, but facilitator needs independent deployment |
| **docker-compose.yml** (facilitator service) | **EXTRACT** | Copy facilitator service, rewrite networking |
| **test-seller/** (payment test harness) | **COPY** | Useful for facilitator testing |
| **scripts/test_*_payment*.py** | **COPY** | Facilitator-specific test scripts |
| **scripts/deploy-*.py** (if facilitator-specific) | **COPY** | Deployment automation |
| **docs/X402_FORK_STRATEGY.md** | **MOVE** | Facilitator-specific upstream merge guide |
| **.gitignore** (facilitator entries) | **EXTRACT** | Merge relevant entries |
| **README.md** (facilitator sections) | **EXTRACT** | Rewrite for standalone usage |
| **AWS Secrets Manager** | **EXTERNAL** | Shared service, reference by key name |
| **GLUE token contract** | **EXTERNAL** | Blockchain contract, reference by address |
| **Agent discovery** | **EXTERNAL** | Agents call facilitator via HTTPS |

**Shared Libraries** (NOT extracted - facilitator is Rust, agents are Python):
- `shared/base_agent.py` - Agents only, stays in karmacadabra
- `shared/x402_client.py` - Python client for calling facilitator, stays in karmacadabra
- `crates/x402-axum/` - Rust middleware, MOVES to facilitator (it's part of x402-rs workspace)
- `crates/x402-reqwest/` - Rust client middleware, MOVES to facilitator

**Key Insight**: Facilitator is Rust, agents are Python. Zero code overlap except HTTP API contract.

#### Task 2.4: Integration Strategy (Karmacadabra → Facilitator)

**After extraction, how do karmacadabra agents consume facilitator?**

**Current State** (monorepo):
```python
# Agent imports local facilitator via docker-compose
FACILITATOR_URL = "http://facilitator:9000"  # Docker Compose service name
```

**Post-Extraction State** (separate repos):

**Option A: Production HTTPS Endpoint** ✅ **RECOMMENDED for Production**
```python
# Agent calls production facilitator
FACILITATOR_URL = "https://facilitator.ultravioletadao.xyz"
```

**Option B: Docker Compose Link** ✅ **RECOMMENDED for Local Development**
```yaml
# karmacadabra/docker-compose.yml
services:
  karma-hello:
    environment:
      - FACILITATOR_URL=http://facilitator:9000
    # ...

  facilitator:
    image: ghcr.io/ultravioletadao/facilitator:latest  # Pull from external registry
    ports:
      - "9000:8080"
```

**Option C: Git Submodule** ❌ **NOT RECOMMENDED**
- Tight coupling
- Complex for contributors

**DECISION**:
- **Production**: Agents call `https://facilitator.ultravioletadao.xyz`
- **Local Dev**: Docker Compose pulls `ghcr.io/ultravioletadao/facilitator:latest`
- **Testing**: Agents can override `FACILITATOR_URL` via .env

**Action Items**:
1. Update karmacadabra `docker-compose.yml` to use external facilitator image
2. Update agent `.env.example` with production facilitator URL
3. Document in karmacadabra README: "Facilitator is now external service"
4. Add GitHub Actions workflow to facilitator repo: publish Docker image on release

---

### Phase 3: Extraction Execution (Estimated: 6-8 hours)

**Goal**: Physically move files and create standalone repository

#### Task 3.1: Git History Preservation Strategy

**Option A: `git filter-branch` (Preserve Full History)** ✅ **RECOMMENDED**

Extract `x402-rs/` directory with full commit history:

```bash
# Clone karmacadabra
cd z:\ultravioleta\dao\
git clone karmacadabra facilitator-temp
cd facilitator-temp

# Filter to only x402-rs/ commits
git filter-branch --prune-empty --subdirectory-filter x402-rs -- --all

# Result: facilitator-temp/ now has x402-rs/ as root with full history
# Rename to match new structure
mkdir src static crates
# ... move files ...

# Push to new repo
git remote set-url origin https://github.com/ultravioletadao/facilitator.git
git push -u origin main
```

**Pros**:
- Preserves commit history for debugging/attribution
- `git blame` shows original authors
- Commit SHAs preserved (useful for referencing)

**Cons**:
- Includes commits unrelated to facilitator if files were in root before
- Filter-branch can be slow on large repos

**Option B: Fresh Start with Reference** ❌ **NOT RECOMMENDED**

Create new repo, copy files, reference karmacadabra in commit message.

**Pros**: Clean history

**Cons**: Lose valuable commit context (e.g., "why was this changed?")

**DECISION**: **Option A** - Preserve history via `git filter-branch`

**Safety**:
- Work in `facilitator-temp/` clone, not original karmacadabra
- Verify history before pushing to new repo
- Tag karmacadabra at extraction point: `git tag facilitator-extraction-2025-11-01`

#### Task 3.2: File Migration Checklist

**Step-by-step file movement** (execute in order):

**3.2.1: Create Target Repository**
```bash
mkdir z:\ultravioleta\dao\facilitator
cd z:\ultravioleta\dao\facilitator
git init
echo "# x402-rs Facilitator" > README.md
git add README.md
git commit -m "Initial commit"
```

**3.2.2: Move Core Rust Code**
```bash
# From karmacadabra/x402-rs/ → facilitator/src/
cp -r z:\ultravioleta\dao\karmacadabra\x402-rs\src z:\ultravioleta\dao\facilitator\src
cp z:\ultravioleta\dao\karmacadabra\x402-rs\Cargo.toml z:\ultravioleta\dao\facilitator\
cp -r z:\ultravioleta\dao\karmacadabra\x402-rs\crates z:\ultravioleta\dao\facilitator\
cp -r z:\ultravioleta\dao\karmacadabra\x402-rs\examples z:\ultravioleta\dao\facilitator\

# Verify build works
cd z:\ultravioleta\dao\facilitator
cargo build --release
```

**3.2.3: Move CRITICAL Branding Assets** ⚠️ **EXTRA CARE REQUIRED**
```bash
# CRITICAL: Preserves 57KB Ultravioleta DAO landing page
cp -r z:\ultravioleta\dao\karmacadabra\x402-rs\static z:\ultravioleta\dao\facilitator\static

# VERIFY branding intact
ls -lh z:\ultravioleta\dao\facilitator\static\index.html
# Should show ~57KB file

# VERIFY content
grep "Ultravioleta DAO" z:\ultravioleta\dao\facilitator\static\index.html
# Should find multiple matches

# VERIFY all assets
ls z:\ultravioleta\dao\facilitator\static\images\
# Should list: avalanche.png, base.png, celo.png, hyperevm.png, polygon.png, solana.png, optimism.png
```

**3.2.4: Move Configuration Files**
```bash
cp z:\ultravioleta\dao\karmacadabra\x402-rs\.env.example z:\ultravioleta\dao\facilitator\.env.example
cp z:\ultravioleta\dao\karmacadabra\x402-rs\Dockerfile z:\ultravioleta\dao\facilitator\
cp z:\ultravioleta\dao\karmacadabra\x402-rs\LICENSE z:\ultravioleta\dao\facilitator\LICENSE
```

**3.2.5: Extract Docker Compose Service**
```bash
# Create new docker-compose.yml with ONLY facilitator
# Base on karmacadabra/docker-compose.yml lines 35-78
cat > z:\ultravioleta\dao\facilitator\docker-compose.yml << 'EOF'
version: '3.8'

services:
  facilitator:
    build: .
    container_name: facilitator
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - HOST=0.0.0.0
      - RUST_LOG=info
      # ... (copy full env from karmacadabra)
    env_file:
      - .env
    restart: unless-stopped
EOF
```

**3.2.6: Copy Terraform Infrastructure**
```bash
mkdir -p z:\ultravioleta\dao\facilitator\terraform
cp -r z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate z:\ultravioleta\dao\facilitator\terraform\

# Add README explaining agent services can be removed
cat > z:\ultravioleta\dao\facilitator\terraform\README.md << 'EOF'
# Terraform Infrastructure

This directory contains the COMPLETE ECS Fargate infrastructure from karmacadabra.

Currently includes:
- 1 facilitator service (required)
- 5 agent services (optional - can be removed for standalone deployment)
- Shared VPC, ALB, NAT Gateway (required)

See `facilitator-only/` for simplified single-service deployment (future).
EOF
```

**3.2.7: Copy Test Files**
```bash
mkdir -p z:\ultravioleta\dao\facilitator\tests\integration

# Find and copy facilitator-specific tests
cp z:\ultravioleta\dao\karmacadabra\scripts\test_glue_payment_simple.py z:\ultravioleta\dao\facilitator\tests\integration\
cp z:\ultravioleta\dao\karmacadabra\scripts\test_usdc_payment_base.py z:\ultravioleta\dao\facilitator\tests\integration\
# ... copy other test_*_payment*.py files
```

**3.2.8: Copy Deployment Scripts**
```bash
mkdir -p z:\ultravioleta\dao\facilitator\scripts\deploy

# Copy facilitator-specific deployment scripts
# (identify from karmacadabra/scripts/ which are facilitator-only)
```

**3.2.9: Extract Documentation**
```bash
mkdir -p z:\ultravioleta\dao\facilitator\docs

# Move facilitator-specific docs
cp z:\ultravioleta\dao\karmacadabra\docs\X402_FORK_STRATEGY.md z:\ultravioleta\dao\facilitator\docs\UPSTREAM_MERGE.md

# Extract facilitator sections from main README
# (manual task - rewrite for standalone usage)
```

**3.2.10: Create .gitignore**
```bash
# Merge facilitator-relevant entries from karmacadabra/.gitignore
cat > z:\ultravioleta\dao\facilitator\.gitignore << 'EOF'
# Environment files
.env
.env.*

# Rust
target/
Cargo.lock

# Logs
*.log
logs/

# Docker
docker-compose.override.yml

# Terraform
terraform/.terraform/
*.tfstate
*.tfstate.backup

# IDE
.vscode/
.idea/
EOF
```

**3.2.11: Verify Standalone Build**
```bash
cd z:\ultravioleta\dao\facilitator

# Rust build
cargo build --release
# ✅ Should succeed

# Docker build
docker build -t facilitator:test .
# ✅ Should succeed

# Run locally
docker run -p 8080:8080 --env-file .env facilitator:test &
sleep 5
curl http://localhost:8080/health
# ✅ Should return {"status":"healthy"}

curl http://localhost:8080/
# ✅ Should return Ultravioleta DAO landing page (check for "Ultravioleta DAO" text)
```

#### Task 3.3: Update Karmacadabra References

**After extraction, update karmacadabra to reference external facilitator**

**3.3.1: Update docker-compose.yml**
```yaml
# karmacadabra/docker-compose.yml
services:
  # Remove facilitator build, use external image
  facilitator:
    image: ghcr.io/ultravioletadao/facilitator:latest  # External image
    container_name: karmacadabra-facilitator
    ports:
      - "9000:8080"
    environment:
      # ... same env as before
    env_file:
      - facilitator.env  # New file for facilitator-only config
```

**3.3.2: Update Agent .env.example**
```bash
# agents/*/,env.example
# Change:
# FACILITATOR_URL=http://localhost:9000
# To:
FACILITATOR_URL=https://facilitator.ultravioletadao.xyz  # Production default
# Or: http://facilitator:9000 for docker-compose local dev
```

**3.3.3: Update README.md**
```markdown
# karmacadabra/README.md

## Payment Facilitator

The x402 facilitator is now a **separate repository**:

**Repository**: [github.com/ultravioletadao/facilitator](https://github.com/ultravioletadao/facilitator)
**Production**: https://facilitator.ultravioletadao.xyz

For local development, the facilitator runs as a Docker service. For production, agents call the hosted endpoint.

See [facilitator repository](https://github.com/ultravioletadao/facilitator) for deployment instructions.
```

**3.3.4: Update Documentation Links**
```bash
# Find all docs mentioning x402-rs/
grep -r "x402-rs" karmacadabra/docs/ --include="*.md"

# Update links to point to new repo
# Example:
# Old: [x402-rs README](../x402-rs/README.md)
# New: [Facilitator README](https://github.com/ultravioletadao/facilitator)
```

---

### Phase 4: Testing & Validation (Estimated: 4-6 hours)

**Goal**: Verify facilitator works standalone AND karmacadabra still works

#### Task 4.1: Standalone Facilitator Testing

**Test Matrix**:

| Test | Command | Expected Result |
|------|---------|-----------------|
| **Rust Build** | `cargo build --release` | Success, binary at `target/release/x402-rs` |
| **Docker Build** | `docker build -t facilitator:test .` | Success, image tagged |
| **Docker Run** | `docker run -p 8080:8080 facilitator:test` | Container starts |
| **Health Check** | `curl http://localhost:8080/health` | `{"status":"healthy"}` |
| **Branding Verification** | `curl http://localhost:8080/ | grep "Ultravioleta DAO"` | Found (CRITICAL) |
| **Supported Networks** | `curl http://localhost:8080/supported` | Lists 17 networks |
| **Payment Verification** | `python tests/integration/test_glue_payment_simple.py` | Payment verified |
| **Docker Compose** | `docker-compose up -d && curl localhost:8080/health` | Healthy |
| **Terraform Plan** | `cd terraform/ecs-fargate && terraform plan` | No errors |

**Critical Tests**:
1. **Branding Intact**: `static/index.html` is 57KB and contains "Ultravioleta DAO"
2. **All 17 Networks**: `/supported` returns all expected networks
3. **Payment Flow**: End-to-end payment verification works

#### Task 4.2: Karmacadabra Integration Testing

**Test that karmacadabra agents can still use facilitator**

**4.2.1: Local Docker Compose Test**
```bash
# karmacadabra directory
cd z:\ultravioleta\dao\karmacadabra

# Start facilitator (pulls from ghcr.io)
docker-compose up -d facilitator

# Start agent
docker-compose up -d karma-hello

# Test agent → facilitator payment
docker exec karmacadabra-karma-hello python -c "
import requests
response = requests.get('http://facilitator:9000/health')
print(response.json())
"
# ✅ Should print {"status":"healthy"}
```

**4.2.2: Production Endpoint Test**
```bash
# Test agent calls production facilitator
cd z:\ultravioleta\dao\karmacadabra
python scripts/test_production_stack.py
# ✅ All agents should successfully call facilitator
```

**4.2.3: End-to-End Purchase Test**
```bash
# Test complete buyer → seller → facilitator flow
python scripts/demo_client_purchases.py --production
# ✅ Should complete purchase successfully
```

#### Task 4.3: Rollback Testing

**Verify we can rollback if extraction breaks production**

**4.3.1: Pre-Extraction Snapshot**
```bash
# Tag karmacadabra at extraction point
cd z:\ultravioleta\dao\karmacadabra
git tag -a facilitator-extraction-v1 -m "Pre-facilitator extraction snapshot"
git push origin facilitator-extraction-v1
```

**4.3.2: Rollback Procedure**
```bash
# If extraction breaks production:

# Step 1: Revert karmacadabra docker-compose.yml
cd z:\ultravioleta\dao\karmacadabra
git checkout facilitator-extraction-v1 -- docker-compose.yml

# Step 2: Rebuild facilitator from source
docker-compose build facilitator

# Step 3: Restart services
docker-compose up -d facilitator
docker-compose restart karma-hello abracadabra

# Step 4: Verify health
curl http://localhost:9000/health
python scripts/test_production_stack.py
```

**4.3.3: Production Rollback (AWS)**
```bash
# Rollback ECS service to previous task definition
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-facilitator \
  --task-definition karmacadabra-prod-facilitator:PREVIOUS_REVISION \
  --region us-east-1

# Monitor rollback
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1
```

---

### Phase 5: Documentation & CI/CD (Estimated: 3-4 hours)

**Goal**: Complete standalone documentation and automate deployment

#### Task 5.1: Write Standalone Documentation

**Required Documents**:

**5.1.1: README.md** (Main entry point)
```markdown
# x402-rs Facilitator

> Production-grade payment facilitator for HTTP 402 micropayments across 17 blockchain networks.

## Features
- 17 networks supported (Avalanche, Base, Celo, Polygon, Solana, Optimism, etc.)
- EIP-3009 gasless transfers
- Custom Ultravioleta DAO branding
- Production-ready (AWS ECS Fargate deployment)

## Quick Start
```bash
docker-compose up -d
curl http://localhost:8080/health
```

See [QUICKSTART.md](docs/QUICKSTART.md) for detailed setup.
```

**5.1.2: docs/QUICKSTART.md**
```markdown
# Quick Start Guide

Get the facilitator running in 5 minutes.

## Local Development
1. Clone: `git clone https://github.com/ultravioletadao/facilitator.git`
2. Configure: `cp .env.example .env` (add private keys)
3. Run: `docker-compose up -d`
4. Test: `curl http://localhost:8080/health`

## Production Deployment
See [DEPLOYMENT.md](DEPLOYMENT.md) for AWS/GCP/Azure guides.
```

**5.1.3: docs/DEPLOYMENT.md**
```markdown
# Production Deployment Guide

## AWS ECS Fargate (Recommended)

### Prerequisites
- AWS CLI configured
- Docker installed
- Terraform 1.0+

### Steps
1. Build & push image: `./scripts/deploy/build-and-push.sh`
2. Deploy infrastructure: `cd terraform/ecs-fargate && terraform apply`
3. Verify: `curl https://facilitator.your-domain.com/health`

See [terraform/ecs-fargate/README.md](../terraform/ecs-fargate/README.md) for details.

## Docker Compose
See [QUICKSTART.md](QUICKSTART.md)

## Kubernetes
Coming soon - contributions welcome!
```

**5.1.4: docs/NETWORKS.md**
```markdown
# Supported Networks

The facilitator supports 17 blockchain networks:

## Mainnets (7)
1. **Avalanche C-Chain** - RPC: https://avalanche-c-chain-rpc.publicnode.com
2. **Base** - RPC: https://mainnet.base.org
3. **Celo** - RPC: https://rpc.celocolombia.org
4. **Polygon** - RPC: https://polygon.drpc.org
5. **Optimism** - RPC: https://public-op-mainnet.fastnode.io
6. **Solana** - RPC: https://api.mainnet-beta.solana.com
7. **HyperEVM** - RPC: https://rpc.hyperliquid.xyz/evm

## Testnets (10)
1. **Avalanche Fuji** - RPC: https://avalanche-fuji-c-chain-rpc.publicnode.com
2. **Base Sepolia** - RPC: https://sepolia.base.org
... (continue list)

## Configuration
Set RPC URLs via environment variables:
```bash
RPC_URL_AVALANCHE_FUJI=https://your-rpc-endpoint.com
```

See [.env.example](.env.example) for full list.
```

**5.1.5: docs/CUSTOMIZATION.md**
```markdown
# Customizing the Facilitator

## Branding

The facilitator includes a custom landing page at `/` (root endpoint).

**Location**: `static/index.html`

**Customization Steps**:
1. Edit `static/index.html` with your branding
2. Replace `static/logo.png` with your logo
3. Update `static/favicon.ico`
4. Rebuild: `docker build -t facilitator:custom .`

**IMPORTANT**: The landing page is served via `include_str!()` in `src/handlers.rs`. If you move `static/`, update line 76:

```rust
// src/handlers.rs
pub async fn get_index() -> Html<&'static str> {
    Html(include_str!("../static/index.html"))  // Update path if moved
}
```

## Adding Networks
See [NETWORKS.md](NETWORKS.md)
```

**5.1.6: docs/UPSTREAM_MERGE.md**
```markdown
# Merging Upstream x402-rs Updates

This facilitator is a fork of [polyphene/x402-rs](https://github.com/polyphene/x402-rs) with custom branding and additional networks.

## Safe Merge Process

⚠️ **NEVER use `cp -r` to copy upstream files** - this will overwrite custom branding!

### Protected Files (DO NOT OVERWRITE)
- `static/` - Entire folder (custom Ultravioleta DAO branding)
- `src/handlers.rs` - Lines 76-85 (custom `get_index()` function)
- `src/network.rs` - Custom networks (HyperEVM, Optimism, Polygon, Solana)

### Step-by-Step Merge
```bash
# 1. Add upstream remote
git remote add upstream https://github.com/polyphene/x402-rs
git fetch upstream

# 2. Create merge branch
git checkout -b merge-upstream-vX.X.X

# 3. Merge carefully
git merge upstream/main

# 4. Resolve conflicts (preserve custom files)
# For static/: ALWAYS keep ours
git checkout --ours static/

# For src/handlers.rs: MANUALLY merge, keep include_str!() line
# For src/network.rs: ADD upstream networks, KEEP our custom ones

# 5. Test extensively (see TESTING.md)
cargo build --release
cargo test
docker build -t facilitator:test .
# ... run full test suite

# 6. Merge to main only if all tests pass
git checkout main
git merge merge-upstream-vX.X.X
```

See [karmacadabra CLAUDE.md](https://github.com/ultravioletadao/karmacadabra/blob/main/CLAUDE.md) lines 96-456 for full procedure history.
```

#### Task 5.2: GitHub Actions CI/CD

**5.2.1: .github/workflows/test.yml**
```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Rust Build
        run: cargo build --release

      - name: Rust Tests
        run: cargo test

      - name: Docker Build
        run: docker build -t facilitator:test .

      - name: Verify Branding
        run: |
          docker run -d -p 8080:8080 --name test facilitator:test
          sleep 5
          curl http://localhost:8080/ | grep "Ultravioleta DAO" || exit 1
          docker stop test
```

**5.2.2: .github/workflows/publish.yml**
```yaml
name: Publish Docker Image

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Login to GitHub Container Registry
        run: echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin

      - name: Build and Push
        run: |
          docker build -t ghcr.io/ultravioletadao/facilitator:latest .
          docker build -t ghcr.io/ultravioletadao/facilitator:${{ github.event.release.tag_name }} .
          docker push ghcr.io/ultravioletadao/facilitator:latest
          docker push ghcr.io/ultravioletadao/facilitator:${{ github.event.release.tag_name }}
```

**5.2.3: .github/workflows/deploy.yml**
```yaml
name: Deploy to Production

on:
  workflow_dispatch:  # Manual trigger only

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Force ECS Update
        run: |
          aws ecs update-service \
            --cluster facilitator-prod \
            --service facilitator \
            --force-new-deployment
```

#### Task 5.3: Version & Changelog

**5.3.1: CHANGELOG.md**
```markdown
# Changelog

All notable changes to the facilitator will be documented here.

## [1.0.0] - 2025-11-01

### Added
- Extracted from karmacadabra monorepo
- 17 network support (7 mainnets, 10 testnets)
- Custom Ultravioleta DAO branding
- AWS ECS Fargate deployment
- Docker Compose local development
- Full documentation suite

### Changed
- Standalone repository structure
- Independent versioning from karmacadabra

### Infrastructure
- Terraform modules for AWS deployment
- GitHub Actions CI/CD pipelines
```

**5.3.2: Update Cargo.toml Version**
```toml
[package]
name = "x402-rs"
version = "1.0.0"  # Reset to 1.0.0 for standalone release
authors = ["Sergey Ukustov <sergey@ukstv.me>", "Ultravioleta DAO"]
edition = "2021"
license = "Apache-2.0"
repository = "https://github.com/ultravioletadao/facilitator"
description = "Production payment facilitator for HTTP 402 micropayments - Ultravioleta DAO fork"
```

---

### Phase 6: Production Cutover (Estimated: 2-3 hours + monitoring)

**Goal**: Zero-downtime migration to new facilitator repository

#### Task 6.1: Pre-Cutover Checklist

**Critical Verifications** (MUST pass before cutover):

- [ ] Facilitator Docker image builds successfully
- [ ] Facilitator runs standalone via `docker-compose up`
- [ ] Health endpoint returns 200 OK
- [ ] Branding verification: Landing page contains "Ultravioleta DAO"
- [ ] All 17 networks listed in `/supported`
- [ ] Payment verification test passes (`test_glue_payment_simple.py`)
- [ ] Terraform plan succeeds (no errors)
- [ ] GitHub Actions workflows configured
- [ ] AWS Secrets Manager keys accessible from new repo
- [ ] CloudWatch logs configured
- [ ] Rollback procedure documented and tested

#### Task 6.2: Staged Rollout Strategy

**Phase 6.2.1: Development Environment** (Day 1)
```bash
# Deploy to dev environment first
cd facilitator/terraform/ecs-fargate
terraform workspace new dev
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars

# Test dev deployment
curl https://facilitator-dev.ultravioletadao.xyz/health

# Run integration tests
cd ../../tests/integration
python test_all_networks.py --env dev
```

**Phase 6.2.2: Staging Environment** (Day 2-3)
```bash
# Deploy to staging
terraform workspace new staging
terraform apply -var-file=staging.tfvars

# Test with staging agents
# Update karmacadabra staging agents to point to new facilitator
FACILITATOR_URL=https://facilitator-staging.ultravioletadao.xyz python scripts/demo_client_purchases.py
```

**Phase 6.2.3: Production Cutover** (Day 4-5)

**Pre-Cutover** (30 minutes before):
```bash
# 1. Tag current production state
cd z:\ultravioleta\dao\karmacadabra
git tag production-pre-facilitator-extraction
git push origin production-pre-facilitator-extraction

# 2. Notify monitoring (if applicable)
# Disable alerts temporarily to avoid false alarms

# 3. Take final backup
aws ecs describe-task-definition \
  --task-definition karmacadabra-prod-facilitator \
  > facilitator-task-def-backup.json
```

**Cutover Execution** (Estimated: 15-20 minutes):
```bash
# 1. Deploy new facilitator
cd facilitator/terraform/ecs-fargate
terraform workspace select prod
terraform apply -var-file=prod.tfvars -auto-approve

# 2. Monitor deployment
watch -n 2 'aws ecs describe-services \
  --cluster facilitator-prod \
  --services facilitator \
  --query "services[0].deployments"'

# 3. Wait for healthy status
# Should see: runningCount=1, desiredCount=1, health=HEALTHY

# 4. Verify endpoints
curl https://facilitator.ultravioletadao.xyz/health
# ✅ Should return {"status":"healthy"}

curl https://facilitator.ultravioletadao.xyz/ | grep "Ultravioleta DAO"
# ✅ Should find branding text

# 5. Run smoke tests
cd facilitator/tests/integration
python test_production.py
# ✅ All tests should pass
```

**Post-Cutover Verification** (30 minutes):
```bash
# 6. Test from karmacadabra agents
cd z:\ultravioleta\dao\karmacadabra
python scripts/test_production_stack.py
# ✅ All 5 agents should call facilitator successfully

# 7. Monitor CloudWatch logs
aws logs tail /ecs/facilitator-prod/facilitator --follow
# Look for: No errors, successful payment verifications

# 8. Check metrics
# ALB target health, ECS task CPU/memory, request count

# 9. Re-enable monitoring alerts
```

**Rollback Decision Point**:
- If ANY test fails → Execute Task 6.3 (Rollback)
- If all tests pass → Continue to Task 6.4 (Cleanup)

#### Task 6.3: Emergency Rollback Procedure

**Trigger Conditions**:
- Health endpoint returns 500
- Branding missing (no "Ultravioleta DAO")
- Payment verification fails
- Agents can't reach facilitator
- ECS task keeps restarting

**Rollback Steps** (Execute immediately):
```bash
# 1. Revert to old karmacadabra facilitator
cd z:\ultravioleta\dao\karmacadabra
git checkout production-pre-facilitator-extraction -- docker-compose.yml terraform/

# 2. Redeploy old facilitator
cd terraform/ecs-fargate
terraform apply -auto-approve

# 3. Force restart
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-facilitator \
  --force-new-deployment \
  --region us-east-1

# 4. Monitor until healthy
watch -n 2 'curl -s https://facilitator.ultravioletadao.xyz/health'

# 5. Verify agents work
cd ../..
python scripts/test_production_stack.py

# 6. Investigate failure
# Review: CloudWatch logs, ECS events, Terraform plan diff
```

#### Task 6.4: Post-Cutover Cleanup

**After 48-hour stable period**:

```bash
# 1. Remove facilitator from karmacadabra repo
cd z:\ultravioleta\dao\karmacadabra
git rm -r x402-rs/
git commit -m "Remove facilitator (now external repo at github.com/ultravioletadao/facilitator)"

# 2. Update karmacadabra README
# Add link to facilitator repo
# Update architecture diagrams

# 3. Archive old terraform state
cd terraform/ecs-fargate
terraform state rm aws_ecs_service.agents["facilitator"]
terraform state rm aws_ecs_task_definition.agents["facilitator"]
# ... remove facilitator-specific resources

# 4. Cleanup Docker Compose
# karmacadabra/docker-compose.yml now uses external image

# 5. Update documentation
# All references to x402-rs/ should point to new repo
```

---

## File Inventory System

### Automated Inventory Script

**Create**: `scripts/inventory_facilitator.py`

```python
#!/usr/bin/env python3
"""
Facilitator File Inventory Generator
Scans karmacadabra repo and categorizes all facilitator-related files
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path("z:/ultravioleta/dao/karmacadabra")
CATEGORIES = {
    "CORE": [],
    "TESTS": [],
    "SCRIPTS": [],
    "DOCS": [],
    "CONFIG": [],
    "SHARED": [],
    "UNKNOWN": []
}

def categorize_file(filepath: str) -> str:
    """Categorize file based on path and content"""

    # CORE: Rust source code
    if filepath.startswith("x402-rs/src/") or filepath.startswith("x402-rs/crates/"):
        return "CORE"
    if filepath.endswith(".rs") and "x402" in filepath:
        return "CORE"

    # CORE: Branding assets (CRITICAL)
    if filepath.startswith("x402-rs/static/"):
        return "CORE"

    # CORE: Configuration
    if filepath in ["x402-rs/Cargo.toml", "x402-rs/Dockerfile", "x402-rs/.env.example"]:
        return "CORE"

    # TESTS: Payment tests
    if "test" in filepath.lower() and any(x in filepath for x in ["payment", "x402", "facilitator", "usdc", "glue"]):
        return "TESTS"

    # SCRIPTS: Deployment/testing utilities
    if filepath.startswith("scripts/") and any(x in filepath for x in ["deploy", "facilitator", "payment"]):
        return "SCRIPTS"

    # DOCS: Documentation
    if filepath.startswith("docs/") and any(x in filepath for x in ["x402", "facilitator", "payment"]):
        return "DOCS"
    if filepath in ["x402-rs/README.md", "docs/X402_FORK_STRATEGY.md"]:
        return "DOCS"

    # CONFIG: Environment, secrets
    if filepath.endswith(".env") or ".env." in filepath:
        return "CONFIG"

    # SHARED: Terraform, docker-compose
    if filepath.startswith("terraform/ecs-fargate/"):
        return "SHARED"
    if "docker-compose" in filepath:
        return "SHARED"

    return "UNKNOWN"

def find_facilitator_files() -> Dict[str, List[str]]:
    """Scan repo for facilitator-related files"""

    os.chdir(REPO_ROOT)

    # Find all files in x402-rs/
    x402_files = subprocess.run(
        ["git", "ls-files", "x402-rs/"],
        capture_output=True,
        text=True
    ).stdout.strip().split("\n")

    # Find files mentioning "facilitator" in scripts/
    script_files = subprocess.run(
        ["git", "grep", "-l", "facilitator", "scripts/"],
        capture_output=True,
        text=True
    ).stdout.strip().split("\n")

    # Find terraform files mentioning "facilitator"
    terraform_files = subprocess.run(
        ["git", "grep", "-l", "facilitator", "terraform/"],
        capture_output=True,
        text=True
    ).stdout.strip().split("\n")

    # Find test files
    test_files = subprocess.run(
        ["git", "ls-files", "tests/", "test-seller/"],
        capture_output=True,
        text=True
    ).stdout.strip().split("\n")

    all_files = set(x402_files + script_files + terraform_files + test_files)
    all_files.discard("")  # Remove empty strings

    for filepath in sorted(all_files):
        category = categorize_file(filepath)
        CATEGORIES[category].append(filepath)

    return CATEGORIES

def generate_inventory_markdown() -> str:
    """Generate markdown inventory report"""

    inventory = find_facilitator_files()

    md = "# Facilitator File Inventory\n\n"
    md += f"**Generated**: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}\n\n"
    md += f"**Total Files**: {sum(len(v) for v in inventory.values())}\n\n"
    md += "---\n\n"

    for category, files in inventory.items():
        md += f"## {category} ({len(files)} files)\n\n"

        if category == "CORE":
            md += "**Action**: MOVE to facilitator repo\n\n"
        elif category == "TESTS":
            md += "**Action**: COPY to facilitator/tests/\n\n"
        elif category == "SCRIPTS":
            md += "**Action**: COPY facilitator-specific scripts\n\n"
        elif category == "DOCS":
            md += "**Action**: MOVE or EXTRACT sections\n\n"
        elif category == "CONFIG":
            md += "**Action**: COPY .env.example, reference secrets externally\n\n"
        elif category == "SHARED":
            md += "**Action**: COPY (terraform), EXTRACT (docker-compose service)\n\n"
        else:
            md += "**Action**: REVIEW MANUALLY\n\n"

        for filepath in sorted(files):
            size = os.path.getsize(os.path.join(REPO_ROOT, filepath)) if os.path.exists(os.path.join(REPO_ROOT, filepath)) else 0
            md += f"- `{filepath}` ({size:,} bytes)\n"

        md += "\n"

    return md

if __name__ == "__main__":
    markdown = generate_inventory_markdown()

    output_file = REPO_ROOT / "FACILITATOR_FILE_INVENTORY.md"
    output_file.write_text(markdown)

    print(f"✅ Inventory saved to: {output_file}")
    print(f"\nSummary:")
    for category, files in CATEGORIES.items():
        print(f"  {category}: {len(files)} files")
```

**Usage**:
```bash
cd z:\ultravioleta\dao\karmacadabra
python scripts/inventory_facilitator.py
# Generates: FACILITATOR_FILE_INVENTORY.md
```

---

## Risk Assessment

### Critical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Branding Assets Lost** | MEDIUM | CRITICAL | Triple-verify static/ copy, automated test in CI |
| **Production Downtime** | LOW | HIGH | Staged rollout, rollback tested |
| **Terraform State Corruption** | LOW | HIGH | S3 backend with versioning, backup state |
| **AWS Secrets Manager Access Broken** | MEDIUM | CRITICAL | Test IAM roles pre-cutover |
| **Agent Integration Breaks** | MEDIUM | HIGH | Integration tests, docker-compose test |
| **Git History Lost** | LOW | MEDIUM | Use filter-branch, verify before push |
| **Network Config Missing** | LOW | MEDIUM | Test all 17 networks pre-cutover |
| **Docker Image Build Fails** | LOW | MEDIUM | Test multi-stage build locally |

### Risk Mitigation Strategies

**For Branding Loss**:
- Automated test: `curl / | grep "Ultravioleta DAO" || exit 1`
- Manual verification before each push
- CI/CD workflow includes branding check
- Backup static/ to separate location

**For Production Downtime**:
- Blue-green deployment via ECS
- Staged rollout (dev → staging → prod)
- Rollback procedure tested and documented
- Monitoring alerts configured

**For Terraform Issues**:
- S3 backend with versioning enabled
- DynamoDB locking
- `terraform plan` before every `apply`
- Backup .tfstate before major changes

**For Secrets Access**:
- Test IAM roles in dev environment first
- Document secret key names clearly
- Verify ECS task execution role has GetSecretValue permission
- Test secrets fetch in Docker locally

---

## Success Metrics

### Technical Metrics

- [ ] **Build Success**: Rust build completes without errors
- [ ] **Test Coverage**: All integration tests pass (payment verification, network support)
- [ ] **Docker Image Size**: <100MB (multi-stage build optimization)
- [ ] **Health Endpoint**: Returns 200 OK within 1 second
- [ ] **Branding Intact**: 57KB HTML file with "Ultravioleta DAO" text
- [ ] **Network Support**: All 17 networks return valid responses
- [ ] **Terraform Plan**: No errors, no drift

### Operational Metrics

- [ ] **Zero Downtime**: Production cutover with 0 failed requests
- [ ] **Agent Integration**: All 5 karmacadabra agents can call facilitator
- [ ] **Documentation Complete**: README + 6 docs written
- [ ] **CI/CD Functional**: GitHub Actions workflows run successfully
- [ ] **Rollback Tested**: Can revert to pre-extraction state in <5 minutes

### Project Metrics

- [ ] **Extraction Time**: Completed within estimated 20-25 hours
- [ ] **Git History**: Preserved for facilitator-specific commits
- [ ] **Community Impact**: Zero disruption to karmacadabra users
- [ ] **Reusability**: Lighthouse or other projects can use facilitator standalone

---

## Next Steps

**Immediate Actions** (Week 1):
1. Run inventory script: `python scripts/inventory_facilitator.py`
2. Review generated `FACILITATOR_FILE_INVENTORY.md`
3. Create `facilitator-temp/` working directory for git history extraction
4. Execute Phase 1 (Discovery) tasks

**Week 2**:
1. Complete Phase 2 (Architecture Design)
2. Get stakeholder approval on Terraform strategy
3. Begin Phase 3 (Extraction Execution)

**Week 3**:
1. Complete extraction
2. Execute Phase 4 (Testing)
3. Write documentation (Phase 5)

**Week 4**:
1. Deploy to dev/staging
2. Execute production cutover (Phase 6)
3. Monitor for 48 hours
4. Execute cleanup if stable

---

## Questions for User

Before proceeding, clarify:

1. **Git History**: Preserve via `filter-branch` or fresh start? (Recommend: preserve)
2. **Terraform Strategy**: Copy entire ecs-fargate/ or split? (Recommend: copy)
3. **Versioning**: Start at v1.0.0 or continue from x402-rs version? (Recommend: v1.0.0)
4. **Repository Name**: `facilitator` or `x402-rs-facilitator`? (Recommend: `facilitator`)
5. **Production Cutover Date**: When is the earliest safe window? (Need monitoring access)
6. **Rollback Authority**: Who can authorize emergency rollback? (Define decision maker)
7. **Documentation Priority**: Which docs are MUST-HAVE vs NICE-TO-HAVE for v1.0.0?

---

## Appendix: Command Reference

### Quick Commands

**Inventory**:
```bash
python scripts/inventory_facilitator.py
```

**Build Test**:
```bash
cd facilitator && cargo build --release && docker build -t facilitator:test .
```

**Branding Verification**:
```bash
docker run -d -p 8080:8080 facilitator:test
curl http://localhost:8080/ | grep "Ultravioleta DAO"
docker stop $(docker ps -q --filter ancestor=facilitator:test)
```

**Health Check**:
```bash
curl https://facilitator.ultravioletadao.xyz/health
```

**Rollback**:
```bash
git checkout production-pre-facilitator-extraction -- terraform/ docker-compose.yml
terraform apply -auto-approve
```

---

**END OF MASTER PLAN**

This plan covers:
- ✅ Phase-by-phase breakdown (6 phases, 20+ tasks)
- ✅ File inventory system (automated categorization)
- ✅ Dependency resolution strategy
- ✅ Git history preservation
- ✅ Risk assessment (8 critical risks identified)
- ✅ Target repository structure (detailed tree)
- ✅ Testing strategy (unit, integration, e2e)
- ✅ Production cutover plan (staged rollout)
- ✅ Rollback procedures
- ✅ Documentation requirements
- ✅ CI/CD automation

Ready to proceed with Phase 1 (Discovery) upon approval.
