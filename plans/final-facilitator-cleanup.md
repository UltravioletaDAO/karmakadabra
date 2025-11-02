# Final Facilitator Cleanup Plan

**Created**: 2025-11-02
**Status**: Ready for Execution
**Goal**: Complete cleanup of old facilitator deployment from karmacadabra monorepo

---

## Executive Summary

The facilitator has been successfully extracted to a standalone repository and is now running at:
- **Production Endpoint**: `facilitator.ultravioletadao.xyz`
- **Location**: Standalone AWS deployment (separate from karmacadabra infrastructure)

This plan will:
1. **Revert domain confusion** - Change all `facilitator.ultravioletadao.xyz` references to `facilitator.ultravioletadao.xyz`
2. **Destroy old Terraform resources** - Remove facilitator from karmacadabra ECS cluster
3. **Archive old code** - Move `x402-rs/` to `.unused/` for reference
4. **Update test configurations** - Point test-seller to production facilitator
5. **Clean AWS secrets** - Remove or archive facilitator-related secrets

**Critical Safety Feature**: Each step is reversible with clear rollback procedures.

---

## Pre-flight Checklist

**STOP AND VERIFY THESE BEFORE PROCEEDING:**

- [ ] **New facilitator is live and healthy**
  ```bash
  curl https://facilitator.ultravioletadao.xyz/health
  # Expected: {"status":"healthy"}
  ```

- [ ] **Test a payment flow**
  ```bash
  # From test-seller or any test script
  python test-seller/load_test.py --facilitator https://facilitator.ultravioletadao.xyz
  # Expected: Successful payment
  ```

- [ ] **Backup critical data**
  ```bash
  # Backup Terraform state
  cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate
  aws s3 cp s3://karmacadabra-terraform-state/ecs-fargate/terraform.tfstate \
    terraform.tfstate.backup-$(date +%Y%m%d)

  # Backup secrets (DO THIS IN SECURE ENVIRONMENT ONLY!)
  aws secretsmanager get-secret-value --secret-id karmacadabra-facilitator-mainnet \
    --query SecretString --output text > /secure/backup/facilitator-mainnet.json
  aws secretsmanager get-secret-value --secret-id karmacadabra-solana-keypair \
    --query SecretString --output text > /secure/backup/solana-keypair.json
  ```

- [ ] **All agents pointing to new facilitator**
  ```bash
  # Check .env files
  grep -r "FACILITATOR_URL" *-agent/.env
  # All should show: facilitator.ultravioletadao.xyz
  ```

- [ ] **Git working tree is clean**
  ```bash
  cd z:\ultravioleta\dao\karmacadabra
  git status
  # Expected: clean working tree
  ```

---

## CRITICAL DOMAIN CLARIFICATION

**Current Situation Analysis:**

After reviewing the documents, there's confusion about domains:
- `facilitator.ultravioletadao.xyz` was mentioned as "temporary during migration"
- `facilitator.ultravioletadao.xyz` is the MAIN production endpoint (standalone)
- `facilitator.karmacadabra.ultravioletadao.xyz` was the old embedded deployment

**The Truth** (based on AWS_FACILITATOR_INFRASTRUCTURE_EXTRACTION.md line 369):
- OLD: `facilitator.karmacadabra.ultravioletadao.xyz` (deprecated)
- NEW: `facilitator.ultravioletadao.xyz` (main production - standalone)
- TEMP: `facilitator.ultravioletadao.xyz` (should be removed)

**Action**: All references should point to `facilitator.ultravioletadao.xyz` (no "dev", no "karmacadabra" prefix).

---

## Step 1: Domain Reference Cleanup

**Goal**: Change all `facilitator.ultravioletadao.xyz` to `facilitator.ultravioletadao.xyz`

### 1.1 Update test-seller Configuration

```bash
cd z:\ultravioleta\dao\karmacadabra\test-seller

# Check current config
grep -n "FACILITATOR_URL" main.py .env* load_test*.py

# Update main.py (if hardcoded)
# Find: facilitator.ultravioletadao.xyz
# Replace: facilitator.ultravioletadao.xyz

# Update .env (if exists)
sed -i 's/facilitator\.dev\.ultravioletadao\.xyz/facilitator.ultravioletadao.xyz/g' .env
```

**Files to check**:
- `main.py` - Line ~18 (environment default)
- `.env` - FACILITATOR_URL variable
- `load_test.py` - Any hardcoded URLs
- `load_test_async.py` - Any hardcoded URLs

### 1.2 Update test-seller-solana Configuration

```bash
cd z:\ultravioleta\dao\karmacadabra\test-seller-solana

# Update main.py line 18
# FROM: FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://facilitator.ultravioletadao.xyz")
# (Already correct!)

# Verify no .dev references
grep -r "facilitator.dev" .
# Expected: No results
```

### 1.3 Update Terraform Variables (if any domain references exist)

```bash
cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate

# Search for domain references
grep -rn "facilitator\.dev" .
grep -rn "facilitator\.karmacadabra" .

# If found, update to: facilitator.ultravioletadao.xyz
```

### 1.4 Update Agent Configurations

```bash
cd z:\ultravioleta\dao\karmacadabra

# Check all agent .env files
find . -name ".env*" -type f -exec grep -H "FACILITATOR_URL" {} \;

# Update each agent's .env
for agent in validator-agent karma-hello-agent abracadabra-agent skill-extractor-agent voice-extractor-agent; do
  if [ -f "$agent/.env" ]; then
    sed -i 's/facilitator\.dev\.ultravioletadao\.xyz/facilitator.ultravioletadao.xyz/g' "$agent/.env"
  fi
done
```

### 1.5 Update Documentation

```bash
# Update README files
grep -rn "facilitator\.dev" README*.md docs/*.md

# Update CLAUDE.md if needed
nano CLAUDE.md
# Change any references from .dev to main domain
```

### Verification

```bash
# Verify no .dev references remain
cd z:\ultravioleta\dao\karmacadabra
grep -r "facilitator\.dev" --exclude-dir=.git --exclude-dir=.unused --exclude-dir=node_modules

# Test connectivity
curl https://facilitator.ultravioletadao.xyz/health
curl https://facilitator.ultravioletadao.xyz/networks

# Test from test-seller
cd test-seller
python load_test.py --facilitator https://facilitator.ultravioletadao.xyz --count 5
```

**Rollback**: If issues occur, revert files:
```bash
git checkout test-seller/main.py test-seller/.env *-agent/.env
```

---

## Step 2: Destroy Old Terraform Infrastructure

**Goal**: Remove facilitator resources from karmacadabra ECS cluster

**WARNING**: This destroys AWS resources. Ensure new facilitator is working first!

### 2.1 Review Current Terraform State

```bash
cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate

# List facilitator resources
terraform state list | grep facilitator

# Expected resources to be destroyed:
# - aws_ecs_service.agents["facilitator"]
# - aws_ecs_task_definition.agents["facilitator"]
# - aws_lb_target_group.agents["facilitator"]
# - aws_lb_listener_rule.facilitator_*
# - aws_cloudwatch_log_group.agents["facilitator"]
# - aws_cloudwatch_metric_alarm.*["facilitator"]
# - aws_appautoscaling_target.ecs_service["facilitator"]
# - aws_appautoscaling_policy.*["facilitator"]
# - data.aws_secretsmanager_secret.agent_secrets["facilitator"]
```

### 2.2 Remove Facilitator from variables.tf

```bash
cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate

# Backup current file
cp variables.tf variables.tf.backup

# Edit variables.tf
nano variables.tf
```

**Find** (around line with `variable "agents"`):
```hcl
variable "agents" {
  description = "Map of agent configurations"
  type = map(object({
    name   = string
    port   = number
    cpu    = number
    memory = number
    # ...
  }))
  default = {
    "facilitator" = {
      name   = "facilitator"
      port   = 8080
      cpu    = 1024
      memory = 2048
      # ...
    },
    "validator" = {
      # ...
    },
    # ... other agents
  }
}
```

**Replace with** (remove `"facilitator"` entry):
```hcl
variable "agents" {
  description = "Map of agent configurations"
  type = map(object({
    name   = string
    port   = number
    cpu    = number
    memory = number
    # ...
  }))
  default = {
    "validator" = {
      # ...
    },
    "karma-hello" = {
      # ...
    },
    "abracadabra" = {
      # ...
    },
    "skill-extractor" = {
      # ...
    },
    "voice-extractor" = {
      # ...
    }
    # facilitator removed - now standalone
  }
}
```

### 2.3 Remove Facilitator-Specific Resources

Check if there are facilitator-specific resources in other files:

```bash
# Search for hardcoded facilitator references
grep -rn "facilitator" *.tf | grep -v "var.agents"

# Common files to check:
# - alb.tf (listener rules)
# - route53.tf (DNS records)
# - ecr.tf (ECR repository)
```

**Example removal from `alb.tf` (if exists)**:
```hcl
# Remove or comment out facilitator-specific listener rules
# resource "aws_lb_listener_rule" "facilitator_root_http" {
#   ...
# }
# resource "aws_lb_listener_rule" "facilitator_root_https" {
#   ...
# }
```

**Example removal from `route53.tf` (if exists)**:
```hcl
# Remove facilitator DNS record
# resource "aws_route53_record" "facilitator" {
#   ...
# }
```

### 2.4 Plan Terraform Changes

```bash
cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate

# Initialize (refresh state)
terraform init

# Plan destruction
terraform plan -out=remove-facilitator.tfplan

# CRITICAL: Review plan carefully
terraform show remove-facilitator.tfplan

# Verify what will be DESTROYED:
# ✅ ECS service: karmacadabra-prod-facilitator
# ✅ ECS task definition family
# ✅ ALB target group (facilitator)
# ✅ CloudWatch log group
# ✅ CloudWatch alarms (5)
# ✅ Auto-scaling policies

# Verify what will be KEPT:
# ✅ VPC, subnets, NAT Gateway, Internet Gateway
# ✅ ALB (shared by other agents)
# ✅ ECS cluster (shared by other agents)
# ✅ Other agent services (validator, karma-hello, etc.)
# ✅ Security groups (shared)
```

**Expected Output**:
```
Plan: 0 to add, 0 to change, 12 to destroy.
```

### 2.5 Apply Terraform Destruction

```bash
# Apply destruction
terraform apply remove-facilitator.tfplan

# Monitor destruction
watch -n 5 'aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1 2>&1'

# Expected: Service not found (after ~2 minutes)
```

### Verification

```bash
# Verify facilitator service is gone
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1
# Expected: ServiceNotFoundException

# Verify other agents still running
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-validator karmacadabra-prod-karma-hello \
  --region us-east-1 \
  --query 'services[*].[serviceName,status,runningCount,desiredCount]'
# Expected: All agents ACTIVE with running tasks

# Verify new facilitator still works
curl https://facilitator.ultravioletadao.xyz/health
```

**Rollback**: If other agents break:
```bash
# Restore variables.tf
cp variables.tf.backup variables.tf

# Recreate facilitator service
terraform apply

# Wait for service to stabilize
aws ecs wait services-stable \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1
```

---

## Step 3: Archive Old Facilitator Code

**Goal**: Move `x402-rs/` directory to `.unused/` for reference

### 3.1 Create Archive Directory

```bash
cd z:\ultravioleta\dao\karmacadabra

# Create archive structure
mkdir -p .unused/facilitator-extraction-2025-11-02/{code,docs,scripts,tests}
```

### 3.2 Move x402-rs Directory

```bash
# Move entire x402-rs directory
mv x402-rs/ .unused/facilitator-extraction-2025-11-02/code/x402-rs/

# Verify move
ls -la .unused/facilitator-extraction-2025-11-02/code/x402-rs/
# Expected: All x402-rs files and directories
```

### 3.3 Move Facilitator-Specific Documentation

```bash
cd z:\ultravioleta\dao\karmacadabra

# Move root-level facilitator docs
mv AWS_FACILITATOR_INFRASTRUCTURE_EXTRACTION.md .unused/facilitator-extraction-2025-11-02/docs/
mv FACILITATOR_CLEANUP_PLAN.md .unused/facilitator-extraction-2025-11-02/docs/
mv facilitator-task-def-mainnet*.json .unused/facilitator-extraction-2025-11-02/docs/

# Move extraction planning docs
mv x402-rs/EXTRACTION_MASTER_PLAN.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
mv FACILITATOR_EXTRACTION_MASTER_PLAN.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
mv EXTRACTION_MASTER_PLAN_TERRAFORM_ANALYSIS.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
mv TERRAFORM_EXTRACTION_SUMMARY.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
mv TERRAFORM_EXTRACTION_DIAGRAM.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true

# Move facilitator-specific docs from docs/
mv docs/FACILITATOR_TESTING.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
mv docs/FACILITATOR_WALLET_ROTATION.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
mv docs/X402_FORK_STRATEGY.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true

# Move bug reports
mv BASE_USDC_BUG_INVESTIGATION_REPORT.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
mv FACILITATOR_VALIDATION_BUG.md .unused/facilitator-extraction-2025-11-02/docs/ 2>/dev/null || true
```

### 3.4 Move Facilitator-Specific Scripts

```bash
cd z:\ultravioleta\dao\karmacadabra

# Move facilitator test scripts
mv scripts/test_glue_payment_simple.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/test_usdc_payment_base.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/test_base_usdc_stress.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/test_facilitator_verbose.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/check_facilitator_config.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/diagnose_usdc_payment.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/compare_domain_separator.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/compare_usdc_contracts.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/verify_full_stack.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/usdc_contracts_facilitator.json .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true

# Move facilitator secrets scripts
mv scripts/setup_facilitator_secrets.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/migrate_facilitator_secrets.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/rotate-facilitator-wallet.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/create_testnet_facilitator_secret.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/split_facilitator_secrets.py .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
mv scripts/upgrade_facilitator.ps1 .unused/facilitator-extraction-2025-11-02/scripts/ 2>/dev/null || true
```

### 3.5 Move Facilitator Tests

```bash
cd z:\ultravioleta\dao\karmacadabra

# Move x402 tests
mv tests/x402/ .unused/facilitator-extraction-2025-11-02/tests/ 2>/dev/null || true
mv tests/test_facilitator.py .unused/facilitator-extraction-2025-11-02/tests/ 2>/dev/null || true
```

### 3.6 Update .gitignore

```bash
cd z:\ultravioleta\dao\karmacadabra

# Add .unused to .gitignore (if not already there)
if ! grep -q "^.unused/" .gitignore; then
  echo "" >> .gitignore
  echo "# Archived facilitator extraction (2025-11-02)" >> .gitignore
  echo ".unused/facilitator-extraction-2025-11-02/" >> .gitignore
fi
```

### Verification

```bash
# Verify x402-rs moved
ls x402-rs/
# Expected: No such file or directory

ls .unused/facilitator-extraction-2025-11-02/code/x402-rs/
# Expected: All x402-rs contents

# Verify project still builds (no broken imports)
cd z:\ultravioleta\dao\karmacadabra
grep -r "from x402" . --exclude-dir=.unused --exclude-dir=.git
grep -r "import x402" . --exclude-dir=.unused --exclude-dir=.git
# Expected: No results (agents use HTTP, not direct imports)
```

**Rollback**: If needed:
```bash
# Restore x402-rs
cp -r .unused/facilitator-extraction-2025-11-02/code/x402-rs/ .

# Restore docs
cp .unused/facilitator-extraction-2025-11-02/docs/*.md .
```

---

## Step 4: Clean AWS Secrets Manager

**Goal**: Archive or delete old facilitator secrets from us-east-1

**CRITICAL**: Only do this AFTER confirming new facilitator has its own secrets working.

### 4.1 Verify New Facilitator Secrets Exist

```bash
# Check new facilitator secrets (in standalone deployment)
aws secretsmanager list-secrets --region us-east-1 | grep facilitator

# Expected to see:
# - facilitator-evm-private-key (new standalone)
# - facilitator-solana-keypair (new standalone)
# - karmacadabra-facilitator-mainnet (old - to delete)
# - karmacadabra-solana-keypair (old - to delete)
```

### 4.2 Option A: Delete Old Secrets (30-day recovery)

**Recommended**: This allows recovery within 30 days.

```bash
# Mark for deletion (30-day recovery period)
aws secretsmanager delete-secret \
  --secret-id karmacadabra-facilitator-mainnet \
  --recovery-window-in-days 30 \
  --region us-east-1

aws secretsmanager delete-secret \
  --secret-id karmacadabra-solana-keypair \
  --recovery-window-in-days 30 \
  --region us-east-1

# Verify deletion scheduled
aws secretsmanager describe-secret --secret-id karmacadabra-facilitator-mainnet --region us-east-1
# Expected: DeletedDate field present
```

### 4.2 Option B: Keep Old Secrets (No Cost)

**Conservative**: Keep secrets indefinitely for backup.

```bash
# No action needed - secrets remain
# Cost: $0 (Secrets Manager charges per access, not storage)

# Optionally add tag for reference
aws secretsmanager tag-resource \
  --secret-id karmacadabra-facilitator-mainnet \
  --tags Key=Status,Value=Archived Key=ArchivedDate,Value=$(date +%Y-%m-%d) \
  --region us-east-1
```

### Verification

```bash
# Test new facilitator still works
curl https://facilitator.ultravioletadao.xyz/health

# Test payment with new facilitator
cd z:\ultravioleta\dao\karmacadabra\test-seller
python load_test.py --facilitator https://facilitator.ultravioletadao.xyz --count 3
```

**Rollback**: If secrets were deleted:
```bash
# Restore within 30 days
aws secretsmanager restore-secret \
  --secret-id karmacadabra-facilitator-mainnet \
  --region us-east-1
```

---

## Step 5: Update Documentation

**Goal**: Update karmacadabra docs to reference standalone facilitator

### 5.1 Update README.md

```bash
cd z:\ultravioleta\dao\karmacadabra
nano README.md
```

**Find**:
```markdown
## Architecture

**Layer 1 - Blockchain**: Avalanche Fuji (GLUE token, ERC-8004 registries)
**Layer 2 - Payment Facilitator**: x402-rs (in this repo)
**Layer 3 - AI Agents**: karma-hello, abracadabra, validator, etc.
```

**Replace with**:
```markdown
## Architecture

**Layer 1 - Blockchain**: Avalanche Fuji (GLUE token, ERC-8004 registries)
**Layer 2 - Payment Facilitator**: [Standalone Repository](https://github.com/ultravioletadao/facilitator)
  - Deployed at: `facilitator.ultravioletadao.xyz`
  - Supports 17 networks (EVM + Solana)
**Layer 3 - AI Agents**: karma-hello, abracadabra, validator, etc.
```

### 5.2 Update README.es.md

```bash
nano README.es.md
```

Apply same changes in Spanish:
```markdown
**Capa 2 - Facilitador de Pagos**: [Repositorio Independiente](https://github.com/ultravioletadao/facilitator)
  - Desplegado en: `facilitator.ultravioletadao.xyz`
  - Soporta 17 redes (EVM + Solana)
```

### 5.3 Update CLAUDE.md

```bash
nano CLAUDE.md
```

**Add** (after Project Overview section):
```markdown
### Facilitator Extraction (2025-11-02)

The x402-rs payment facilitator was extracted from this monorepo into a standalone repository:
- **Repository**: https://github.com/ultravioletadao/facilitator
- **Production**: https://facilitator.ultravioletadao.xyz
- **Archived Code**: `.unused/facilitator-extraction-2025-11-02/`

All agents connect to the standalone facilitator via HTTPS. No code dependencies remain.
```

**Find** (in x402-rs Facilitator Upgrades section):
```markdown
### x402-rs Facilitator Upgrades - CRITICAL SAFEGUARDS
```

**Add note**:
```markdown
> **NOTE**: x402-rs facilitator extracted to standalone repo on 2025-11-02.
> This section preserved for historical reference only.
> See: `.unused/facilitator-extraction-2025-11-02/`
```

### 5.4 Update docker-compose.yml (if needed)

```bash
nano docker-compose.yml
```

If facilitator service exists, remove it:
```yaml
# Remove this section:
# facilitator:
#   build:
#     context: ./x402-rs
#   ports:
#     - "8080:8080"
#   ...
```

Update agent environment variables to point to production:
```yaml
services:
  karma-hello:
    environment:
      - FACILITATOR_URL=https://facilitator.ultravioletadao.xyz
  # ... (same for all agents)
```

### Verification

```bash
# Verify documentation consistency
grep -r "x402-rs" README*.md CLAUDE.md
# Should only reference archived location or standalone repo

# Verify no broken links
grep -r "facilitator.dev" README*.md CLAUDE.md docs/*.md
# Expected: No results
```

---

## Step 6: Git Commit and Final Verification

### 6.1 Review Changes

```bash
cd z:\ultravioleta\dao\karmacadabra

# Check git status
git status

# Review diff
git diff

# Check removed files
git status | grep deleted
# Expected: x402-rs/ and facilitator-related files
```

### 6.2 Commit Changes

```bash
# Stage all changes
git add -A

# Commit with detailed message
git commit -m "Extract facilitator to standalone repository

Facilitator successfully extracted and deployed independently at:
https://facilitator.ultravioletadao.xyz

Changes:
- Removed x402-rs/ directory (moved to .unused/)
- Destroyed facilitator resources from karmacadabra ECS cluster
- Updated all domain references from .dev to production
- Archived facilitator-specific scripts, tests, and docs
- Updated documentation to reference standalone repository

All agents continue functioning with standalone facilitator.

Infrastructure changes:
- Removed facilitator from terraform/ecs-fargate/variables.tf
- Destroyed AWS resources: ECS service, task definition, target group,
  CloudWatch logs, alarms, auto-scaling policies
- Kept shared infrastructure: VPC, ALB, ECS cluster (other agents)

Archived at: .unused/facilitator-extraction-2025-11-02/

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 6.3 Final End-to-End Test

```bash
# Test 1: Standalone facilitator health
curl https://facilitator.ultravioletadao.xyz/health
# Expected: {"status":"healthy"}

# Test 2: Payment flow from test-seller
cd z:\ultravioleta\dao\karmacadabra\test-seller
python load_test.py --facilitator https://facilitator.ultravioletadao.xyz --count 10
# Expected: All payments successful

# Test 3: Agent connectivity
for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
  curl https://${agent}.karmacadabra.ultravioletadao.xyz/health
done
# Expected: All agents healthy

# Test 4: Verify no facilitator service in old cluster
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1 2>&1 | grep ServiceNotFoundException
# Expected: ServiceNotFoundException

# Test 5: Other agents still running
aws ecs list-services --cluster karmacadabra-prod --region us-east-1
# Expected: validator, karma-hello, abracadabra, skill-extractor, voice-extractor
```

---

## Rollback Procedures

### Emergency Rollback (if production breaks)

**Scenario**: New facilitator stops working, need to restore old deployment.

```bash
# 1. Restore Terraform variables
cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate
cp variables.tf.backup variables.tf

# 2. Restore x402-rs code
cd z:\ultravioleta\dao\karmacadabra
cp -r .unused/facilitator-extraction-2025-11-02/code/x402-rs/ .

# 3. Re-deploy facilitator to karmacadabra cluster
cd terraform/ecs-fargate
terraform init
terraform plan
terraform apply

# 4. Wait for service to stabilize
aws ecs wait services-stable \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1

# 5. Update agent configs to point back
for agent in *-agent; do
  if [ -f "$agent/.env" ]; then
    sed -i 's|facilitator.ultravioletadao.xyz|facilitator.karmacadabra.ultravioletadao.xyz|g' "$agent/.env"
  fi
done

# 6. Restart agents
# (via AWS ECS or docker-compose)
```

### Partial Rollback (if only code needed)

```bash
# Restore only x402-rs directory
cp -r .unused/facilitator-extraction-2025-11-02/code/x402-rs/ .

# Restore only specific scripts
cp .unused/facilitator-extraction-2025-11-02/scripts/*.py scripts/
```

---

## Post-Cleanup Monitoring

### Week 1: Intensive Monitoring

**Daily checks**:
```bash
# Facilitator health
curl https://facilitator.ultravioletadao.xyz/health

# CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=facilitator-production \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum

# Error logs
aws logs tail /ecs/facilitator-production --follow --since 24h | grep -i error

# Test payment
python test-seller/load_test.py --facilitator https://facilitator.ultravioletadao.xyz --count 5
```

### Week 2-4: Gradual Reduction

**Every 2-3 days**:
- Health checks
- Payment flow tests
- CloudWatch error scan

### Success Criteria

- [ ] **Zero downtime** during entire cleanup process
- [ ] **All tests passing** for 1+ weeks
- [ ] **No error spikes** in CloudWatch
- [ ] **Cost reduction** visible in AWS billing
- [ ] **All agents healthy** and communicating with facilitator
- [ ] **Documentation up to date**
- [ ] **Clean git history** with meaningful commits

---

## Cost Impact

### Before Cleanup
- Facilitator share in karmacadabra cluster: ~$59/month
- Shared infrastructure costs (VPC, ALB, NAT): ~$15/month facilitator share

### After Cleanup
- Facilitator removed from karmacadabra: -$59/month
- Standalone facilitator (separate deployment): +$110-130/month
- **Net change**: +$51-71/month for standalone operation

**Justification**:
- Complete isolation and independence
- Can deploy/update facilitator without affecting agents
- Easier to scale and optimize separately
- Worth the cost for operational flexibility

---

## Files Modified Summary

### Deleted/Moved
- `x402-rs/` (entire directory) → `.unused/facilitator-extraction-2025-11-02/code/`
- `scripts/test_*_facilitator*.py` → `.unused/facilitator-extraction-2025-11-02/scripts/`
- `scripts/*facilitator*.py` → `.unused/facilitator-extraction-2025-11-02/scripts/`
- `tests/x402/` → `.unused/facilitator-extraction-2025-11-02/tests/`
- `docs/FACILITATOR_*.md` → `.unused/facilitator-extraction-2025-11-02/docs/`
- `*FACILITATOR*.md` (root) → `.unused/facilitator-extraction-2025-11-02/docs/`
- `facilitator-task-def-*.json` → `.unused/facilitator-extraction-2025-11-02/docs/`

### Modified
- `terraform/ecs-fargate/variables.tf` - Removed facilitator from agents map
- `test-seller/main.py` - Updated facilitator URL
- `test-seller/.env` - Updated FACILITATOR_URL
- `test-seller-solana/main.py` - Verified correct URL
- `*-agent/.env` - Updated FACILITATOR_URL for all agents
- `README.md` - Updated architecture section
- `README.es.md` - Updated architecture section
- `CLAUDE.md` - Added extraction note
- `docker-compose.yml` - Removed facilitator service (if existed)
- `.gitignore` - Added .unused/ entry

### AWS Resources Destroyed
- `aws_ecs_service.agents["facilitator"]`
- `aws_ecs_task_definition.agents["facilitator"]`
- `aws_lb_target_group.agents["facilitator"]`
- `aws_lb_listener_rule.facilitator_*` (4 rules)
- `aws_cloudwatch_log_group.agents["facilitator"]`
- `aws_cloudwatch_metric_alarm.*["facilitator"]` (5 alarms)
- `aws_appautoscaling_target.ecs_service["facilitator"]`
- `aws_appautoscaling_policy.*["facilitator"]` (2 policies)

### AWS Secrets (Optional)
- `karmacadabra-facilitator-mainnet` - Deleted (30-day recovery) or archived
- `karmacadabra-solana-keypair` - Deleted (30-day recovery) or archived

---

## Timeline

**Estimated Duration**: 3-4 hours for full cleanup

| Step | Duration | Can Parallelize |
|------|----------|-----------------|
| Pre-flight checks | 15 min | No |
| Domain reference cleanup | 30 min | Yes |
| Terraform destruction | 30-45 min | No |
| Archive old code | 15 min | Yes |
| Clean AWS secrets | 10 min | Yes |
| Update documentation | 30 min | Yes |
| Git commit & verification | 20 min | No |
| **Total** | **3-4 hours** | |

**Recommended Schedule**:
- **Morning (9-10am)**: Pre-flight checks + Domain cleanup
- **Midday (11am-12pm)**: Terraform destruction + monitoring
- **Afternoon (2-3pm)**: Archive code + documentation + commit
- **Continuous**: Monitor for 24-48 hours

---

## Questions & Answers

**Q: Can I skip the Terraform destruction step?**
A: Technically yes, but you'll pay ~$59/month for unused resources. Not recommended.

**Q: What if I need the old facilitator code later?**
A: It's in `.unused/facilitator-extraction-2025-11-02/code/x402-rs/` - fully restorable.

**Q: Will this affect agent deployments?**
A: No. Agents use HTTPS endpoints, no code dependencies on x402-rs.

**Q: Can I rollback after committing?**
A: Yes. All steps are reversible. See Rollback Procedures section.

**Q: What if the new facilitator has issues after 1 week?**
A: You can restore old deployment from Terraform state backup within 30 days.

**Q: Should I delete the old AWS secrets?**
A: Recommended with 30-day recovery window. Or keep them archived (no cost).

---

## Conclusion

This cleanup removes all old facilitator infrastructure from karmacadabra while preserving:
- ✅ Full functionality with standalone facilitator
- ✅ All agent connectivity
- ✅ Historical reference in `.unused/`
- ✅ Rollback capability for 30 days
- ✅ Cost optimization opportunity

**Final Verification**: Run all tests in "Step 6.3 Final End-to-End Test" before considering cleanup complete.

**Next Steps After Cleanup**:
1. Monitor facilitator for 1 week
2. Consider cost optimizations (task size, Fargate Spot)
3. Document lessons learned
4. Update team about new facilitator location

---

**Created**: 2025-11-02
**Status**: Ready for Execution
**Estimated Duration**: 3-4 hours + 1 week monitoring
**Risk Level**: Low (all steps reversible)

**Questions?** Review the Rollback Procedures section or consult AWS documentation.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
