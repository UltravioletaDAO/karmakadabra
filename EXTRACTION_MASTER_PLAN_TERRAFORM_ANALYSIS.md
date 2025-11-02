# Terraform Infrastructure Extraction Analysis

**Date**: 2025-11-01
**Analyst**: Claude (Terraform Specialist Agent)
**Scope**: Extract facilitator-specific infrastructure from karmacadabra monorepo

---

## Executive Summary

The current `terraform/ecs-fargate/` directory contains a **multi-agent ECS deployment** managing 8 services (facilitator + 7 agents) through shared infrastructure. To create a standalone facilitator repository, we need to **extract facilitator-specific resources** while **preserving shared infrastructure** through Terraform data sources.

**Key Finding**: The infrastructure is **partially separable** - the facilitator uses dedicated resources (task definition, service, ECR repo, target group) but shares VPC, ALB, IAM roles, and security groups with other agents. Clean extraction requires a **hybrid approach**: duplicate some infrastructure, reference others.

---

## 1. Current Infrastructure Inventory

### 1.1 Multi-Tenant Resources (Shared Across All 8 Services)

**These resources support ALL agents, NOT just facilitator**:

```hcl
# VPC & Networking (vpc.tf)
- aws_vpc.main                            # COST: Free (but NAT ~$32/month)
- aws_internet_gateway.main               # COST: Free
- aws_subnet.public[2]                    # 2 AZs for ALB requirement
- aws_subnet.private[2]                   # ECS tasks run here
- aws_nat_gateway.main[1]                 # COST: $32/month (single NAT optimization)
- aws_eip.nat[1]                          # For NAT Gateway
- aws_route_table.public                  # Routes to IGW
- aws_route_table.private[2]              # Routes to NAT
- aws_vpc_endpoint.ecr_api[1]             # COST: ~$7/month
- aws_vpc_endpoint.ecr_dkr[1]             # COST: ~$7/month
- aws_vpc_endpoint.s3[1]                  # COST: Free (gateway endpoint)
- aws_vpc_endpoint.logs[1]                # COST: ~$7/month
- aws_vpc_endpoint.secretsmanager[1]      # COST: ~$7/month
- aws_security_group.vpc_endpoints[1]     # For VPC endpoint access

# Load Balancer (alb.tf)
- aws_lb.main                             # COST: $16-18/month + data transfer
- aws_lb_listener.http                    # Port 80 listener
- aws_lb_listener.https[1]                # Port 443 listener (if HTTPS enabled)

# Security Groups (security_groups.tf)
- aws_security_group.alb                  # ALB security group
- aws_security_group.ecs_tasks            # Shared by all ECS tasks
- aws_security_group_rule.validator_port  # Per-agent rules (8 total)
- aws_security_group_rule.karma_hello_port
- ... (6 more agent-specific rules)

# IAM Roles (iam.tf)
- aws_iam_role.ecs_task_execution         # Used by ALL task definitions
- aws_iam_role.ecs_task                   # Used by ALL running containers
- aws_iam_role.ecs_autoscaling            # For auto-scaling
- aws_iam_role.ecs_events                 # For scheduled tasks
- aws_iam_role_policy.ecs_secrets_access  # Secrets Manager access
- aws_iam_role_policy.task_secrets_access
- ... (10+ IAM policies attached to shared roles)

# ECS Cluster (main.tf)
- aws_ecs_cluster.main                    # SHARED: "karmacadabra-prod" cluster
- aws_ecs_cluster_capacity_providers.main # Fargate Spot configuration

# Service Discovery (main.tf)
- aws_service_discovery_private_dns_namespace.main[1]  # karmacadabra.local

# Route53 DNS (route53.tf)
- data.aws_route53_zone.main[1]           # Existing hosted zone: ultravioletadao.xyz
- aws_route53_record.base[1]              # karmacadabra.ultravioletadao.xyz -> ALB
- aws_acm_certificate.main[1]             # Wildcard cert: *.karmacadabra.ultravioletadao.xyz
- aws_acm_certificate_validation.main[1]  # DNS validation
```

**Shared Resource Cost Breakdown** (Monthly):
- **NAT Gateway**: $32 (single NAT)
- **ALB**: $16-18 + data transfer
- **VPC Endpoints (Interface)**: ~$28 (4 × $7/month)
- **Total Shared**: ~$76-78/month

**Current Split**: 8 agents share ~$76/month = **~$9.50/agent** in shared infrastructure costs.

---

### 1.2 Facilitator-Specific Resources

**These resources are ONLY for facilitator**:

```hcl
# ECR Repository (ecr.tf)
- aws_ecr_repository.agents["facilitator"]                # karmacadabra/facilitator
- aws_ecr_lifecycle_policy.agents["facilitator"]          # Keep last 5 images

# CloudWatch Logs (cloudwatch.tf)
- aws_cloudwatch_log_group.agents["facilitator"]          # /ecs/karmacadabra-prod/facilitator
- aws_cloudwatch_log_metric_filter.error_count["facilitator"]
- aws_cloudwatch_metric_alarm.high_cpu["facilitator"]
- aws_cloudwatch_metric_alarm.high_memory["facilitator"]
- aws_cloudwatch_metric_alarm.low_task_count["facilitator"]
- aws_cloudwatch_metric_alarm.unhealthy_targets["facilitator"]

# ECS Task Definition (main.tf)
- aws_ecs_task_definition.agents["facilitator"]
  * Family: karmacadabra-prod-facilitator
  * CPU: 2048 (2 vCPU) - HIGHER than other agents
  * Memory: 4096 (4 GB) - HIGHER than other agents
  * Container: x402-rs Rust binary
  * Secrets: EVM_PRIVATE_KEY, SOLANA_PRIVATE_KEY (NO OpenAI key)
  * Environment: 17 RPC URLs (Avalanche, Base, Celo, HyperEVM, Polygon, Optimism, Solana)

# ECS Service (main.tf)
- aws_ecs_service.agents["facilitator"]
  * Name: karmacadabra-prod-facilitator
  * Capacity Provider: FARGATE (on-demand, not Spot - more stable)
  * Desired Count: 1
  * Port: 8080
  * Health Check: /health

# Auto-Scaling (main.tf)
- aws_appautoscaling_target.ecs_service["facilitator"]    # 1-3 tasks
- aws_appautoscaling_policy.cpu["facilitator"]            # 75% CPU target
- aws_appautoscaling_policy.memory["facilitator"]         # 80% memory target

# ALB Target Group (alb.tf)
- aws_lb_target_group.agents["facilitator"]
  * Name: facili-* (6 char prefix)
  * Port: 8080
  * Health Check: /health

# ALB Listener Rules (alb.tf)
- aws_lb_listener_rule.agents_path["facilitator"]         # HTTP path: /facilitator/*
- aws_lb_listener_rule.agents_hostname["facilitator"]     # HTTP host: facilitator.karmacadabra.*
- aws_lb_listener_rule.agents_path_https["facilitator"]   # HTTPS path
- aws_lb_listener_rule.agents_hostname_https["facilitator"] # HTTPS host
- aws_lb_listener_rule.facilitator_root_http              # facilitator.ultravioletadao.xyz
- aws_lb_listener_rule.facilitator_root_https             # HTTPS version

# Route53 DNS (route53.tf)
- aws_route53_record.agents["facilitator"]                # facilitator.karmacadabra.ultravioletadao.xyz
- aws_route53_record.facilitator                          # facilitator.ultravioletadao.xyz (root)

# Secrets Manager (Data Source - main.tf)
- data.aws_secretsmanager_secret.agent_secrets["facilitator"]    # karmacadabra-facilitator-mainnet
- data.aws_secretsmanager_secret.solana_keypair                  # karmacadabra-solana-keypair
```

**Facilitator-Specific Cost** (Monthly):
- **ECS Fargate (2 vCPU / 4 GB, on-demand, 24/7)**: ~$35-45/month
- **CloudWatch Logs (7 days retention)**: ~$2/month
- **ECR Storage**: ~$0.50/month
- **Total Facilitator-Only**: ~$37-47/month
- **Share of ALB/VPC**: ~$9.50/month (1/8 of shared costs)
- **TOTAL FACILITATOR COST**: ~$46-56/month

---

### 1.3 Secrets Manager References

**Critical External Dependencies**:

```bash
# Facilitator uses TWO secrets (different structure from agents)
karmacadabra-facilitator-mainnet:
  {
    "private_key": "0x..."  # EVM private key (for Ethereum-based chains)
  }

karmacadabra-solana-keypair:
  {
    "private_key": "[...]"  # Solana keypair (JSON array format)
  }

# Other agents use single secret with OpenAI key
karmacadabra-{agent-name}:
  {
    "private_key": "0x...",
    "openai_api_key": "sk-proj-..."
  }
```

**Note**: In standalone repo, facilitator secrets MUST be renamed to avoid conflicts:
- `karmacadabra-facilitator-mainnet` → `facilitator-evm-private-key`
- `karmacadabra-solana-keypair` → `facilitator-solana-keypair`

---

## 2. Extraction Strategy

### 2.1 Goals

1. **Self-Contained Infrastructure**: Facilitator repo can deploy independently
2. **Zero Dependencies**: No terraform remote state references to karmacadabra
3. **Cost-Optimized**: Preserve Fargate Spot, single NAT, VPC endpoints
4. **Production-Ready**: HTTPS, custom domain, auto-scaling, alarms
5. **Clean Namespace**: Avoid resource name collisions with karmacadabra

---

### 2.2 Three-Tier Resource Classification

#### Tier 1: DUPLICATE (Create Independent Copies)

**Rationale**: These resources are cheap/free and provide operational independence.

```hcl
# VPC & Networking (NEW VPC for facilitator)
resource "aws_vpc" "facilitator" {
  cidr_block = "10.1.0.0/16"  # Different CIDR to avoid conflicts
  # ... same config as karmacadabra
}

# Why duplicate VPC instead of sharing?
# - Operational independence (can tear down facilitator without affecting agents)
# - VPC is free (only NAT/endpoints cost money)
# - Avoids complex cross-stack dependencies
# - Clean namespace separation

# Security Groups (facilitator-specific)
resource "aws_security_group" "facilitator_alb" {
  name_prefix = "facilitator-alb-"
  # ... same rules, different VPC
}

resource "aws_security_group" "facilitator_tasks" {
  name_prefix = "facilitator-tasks-"
  # ... same rules, different VPC
}

# IAM Roles (facilitator-specific)
resource "aws_iam_role" "facilitator_task_execution" {
  name_prefix = "facilitator-task-exec-"
  # ... same policies, different name to avoid conflicts
}

resource "aws_iam_role" "facilitator_task" {
  name_prefix = "facilitator-task-"
  # ... same policies, different name
}

# Why duplicate IAM roles?
# - Different secret ARN patterns (no wildcard karmacadabra-*)
# - Independent lifecycle (can update facilitator IAM without touching agents)
# - Principle of least privilege (only facilitator secrets access)

# ECS Cluster (NEW cluster)
resource "aws_ecs_cluster" "facilitator" {
  name = "facilitator-prod"
  # ... same settings (Container Insights, Fargate Spot)
}

# Why new cluster instead of shared?
# - Clean separation (facilitator repo owns entire cluster)
# - No accidental impact on agent deployments
# - Simpler disaster recovery (destroy/recreate independently)
```

**Cost Impact of Duplication**:
- VPC: $0 (VPCs are free)
- IAM Roles: $0 (roles are free)
- ECS Cluster: $0 (clusters are free)
- **Net Cost**: $0

---

#### Tier 2: EXTRACT & RENAME (Move Resources, Change Names)

**Rationale**: Facilitator-specific resources that already exist, just rename for clarity.

```hcl
# From: karmacadabra/facilitator
# To:   facilitator/facilitator

# ECR Repository
resource "aws_ecr_repository" "facilitator" {
  name = "facilitator/facilitator"  # Changed from karmacadabra/facilitator
  # ... same lifecycle policies
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "facilitator" {
  name = "/ecs/facilitator-prod/facilitator"  # Changed from /ecs/karmacadabra-prod/facilitator
  retention_in_days = 7
}

# ECS Task Definition
resource "aws_ecs_task_definition" "facilitator" {
  family = "facilitator-prod-facilitator"  # Changed from karmacadabra-prod-facilitator
  cpu    = 2048
  memory = 4096
  # ... rest same
}

# ECS Service
resource "aws_ecs_service" "facilitator" {
  name    = "facilitator-prod-facilitator"
  cluster = aws_ecs_cluster.facilitator.id  # Points to new cluster
  # ... rest same
}
```

**Migration Impact**:
- **Requires new Docker images** pushed to new ECR repo
- **Requires service deletion** in karmacadabra stack
- **DNS cutover** (update Route53 records to point to new ALB)
- **Zero downtime possible** with blue/green deployment

---

#### Tier 3: RECREATE (New Resources, Different Configuration)

**Rationale**: Resources that need modification for standalone deployment.

```hcl
# ALB (NEW - facilitator doesn't need multi-service routing)
resource "aws_lb" "facilitator" {
  name               = "facilitator-prod-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.facilitator_alb.id]
  idle_timeout       = 180  # Critical for Base mainnet tx settlement
}

# Why new ALB instead of sharing?
# - Karmacadabra ALB has 8 listener rules (complex)
# - Facilitator only needs 1 target group (simple)
# - Independent scaling (facilitator traffic != agent traffic)
# COST: +$16/month (new ALB)

# Target Group (simplified)
resource "aws_lb_target_group" "facilitator" {
  name_prefix = "facil-"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.facilitator.id
  target_type = "ip"

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

# HTTP Listener (single rule - no complex routing)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.facilitator.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.facilitator.arn
  }
}

# HTTPS Listener (single rule)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.facilitator.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.facilitator.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.facilitator.arn
  }
}

# Route53 DNS (NEW records)
resource "aws_route53_record" "facilitator" {
  zone_id = data.aws_route53_zone.ultravioleta.zone_id
  name    = "facilitator.ultravioletadao.xyz"
  type    = "A"

  alias {
    name                   = aws_lb.facilitator.dns_name
    zone_id                = aws_lb.facilitator.zone_id
    evaluate_target_health = true
  }
}

# ACM Certificate (NEW - facilitator.ultravioletadao.xyz only)
resource "aws_acm_certificate" "facilitator" {
  domain_name       = "facilitator.ultravioletadao.xyz"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Why new certificate instead of reusing wildcard?
# - Standalone repo shouldn't depend on karmacadabra cert
# - Independent lifecycle (can delete karmacadabra stack without breaking facilitator)
# - More restrictive (only facilitator subdomain, not wildcard)
# COST: $0 (ACM certificates are free)
```

---

### 2.3 State Management Strategy

**Current State File**:
```
s3://karmacadabra-terraform-state/ecs-fargate/terraform.tfstate
```

**New State File** (facilitator repo):
```
s3://facilitator-terraform-state/production/terraform.tfstate
```

**Migration Options**:

#### Option A: Clean Slate (Recommended)

**Pros**:
- Simplest approach
- No terraform state manipulation
- Clean separation
- Easy to test in parallel

**Cons**:
- Requires downtime (destroy old, create new)
- Requires DNS cutover
- Requires new ECR push

**Steps**:
1. Deploy facilitator infrastructure to new AWS resources
2. Push x402-rs Docker image to new ECR repo
3. Verify facilitator service healthy at new ALB DNS name
4. Update Route53 record (facilitator.ultravioletadao.xyz → new ALB)
5. Wait for DNS propagation (TTL)
6. Delete facilitator resources from karmacadabra stack
7. Update karmacadabra variables.tf (remove facilitator from agents map)

**Downtime**: 2-5 minutes during DNS cutover

---

#### Option B: Terraform State Import (Advanced)

**Pros**:
- Zero downtime possible
- Preserves existing resources
- No new ALB needed initially

**Cons**:
- Complex state manipulation
- High risk of mistakes
- Still requires eventual separation for independence

**Steps**:
1. Create new terraform backend (S3 bucket)
2. Write facilitator terraform code
3. Import existing resources into new state:
   ```bash
   terraform import aws_ecs_service.facilitator arn:aws:ecs:...
   terraform import aws_ecs_task_definition.facilitator arn:aws:ecs:...
   # ... 20+ import commands
   ```
4. Remove facilitator from karmacadabra state:
   ```bash
   cd karmacadabra/terraform/ecs-fargate
   terraform state rm 'aws_ecs_service.agents["facilitator"]'
   terraform state rm 'aws_ecs_task_definition.agents["facilitator"]'
   # ... 20+ state rm commands
   ```
5. Apply both stacks to verify no changes

**Recommendation**: **Avoid Option B** - too error-prone for production system. Use Option A with blue/green deployment.

---

### 2.4 Cost Impact Analysis

**Current Karmacadabra Stack** (8 agents):
- Fargate: $79-96/month
- ALB: $16/month
- NAT: $32/month
- VPC Endpoints: $28/month
- CloudWatch: $8/month
- **Total**: ~$163-180/month

**After Extraction**:

**Karmacadabra Stack** (7 agents remaining):
- Fargate: $44-56/month (removed 2 vCPU facilitator)
- ALB: $16/month (still need ALB for 7 agents)
- NAT: $32/month (shared resource)
- VPC Endpoints: $28/month (shared resource)
- CloudWatch: $6/month (reduced)
- **Total**: ~$126-138/month

**Facilitator Stack** (standalone):
- Fargate (2 vCPU / 4 GB, 24/7): $35-45/month
- ALB: $16/month (NEW)
- NAT: $32/month (NEW)
- VPC Endpoints: $28/month (NEW)
- CloudWatch: $2/month
- **Total**: ~$113-123/month

**NET COST INCREASE**: ~$76-81/month

**Why More Expensive?**
- **Duplicated ALB**: +$16/month
- **Duplicated NAT**: +$32/month
- **Duplicated VPC Endpoints**: +$28/month
- **Total Overhead**: ~$76/month

**Cost Optimization Opportunities**:

1. **Remove VPC Endpoints** (if willing to increase NAT data transfer):
   - **Savings**: -$28/month
   - **Trade-off**: Higher NAT data transfer costs (~$5-10/month)
   - **Net Savings**: ~$18-23/month

2. **Use NAT Instance Instead of NAT Gateway**:
   - **Savings**: -$32/month (NAT Gateway) + $8/month (t4g.nano NAT instance) = -$24/month
   - **Trade-off**: Requires NAT instance maintenance, lower throughput
   - **Net Savings**: ~$24/month

3. **Use Application Load Balancer with Target Type = IP** (current):
   - Already optimized (no Network Load Balancer needed)

4. **Fargate Spot** (already used):
   - Already 70% cheaper than on-demand

5. **Right-Size Facilitator Tasks**:
   - Current: 2 vCPU / 4 GB
   - Test: 1 vCPU / 2 GB (50% cost reduction)
   - Monitor: CPU/memory utilization
   - **Potential Savings**: -$17-22/month

**Aggressive Cost Optimization** (all above):
- Remove VPC Endpoints: -$28/month
- NAT Instance: -$24/month
- Right-size tasks: -$20/month
- **NEW TOTAL**: ~$41-51/month
- **NET INCREASE from original**: ~$4-10/month (acceptable)

---

## 3. Recommended Directory Structure

```
facilitator/
├── terraform/
│   ├── environments/
│   │   ├── production/
│   │   │   ├── main.tf              # Symlink to ../../modules/facilitator-service/main.tf
│   │   │   ├── terraform.tfvars     # Production config
│   │   │   └── backend.tf           # S3 backend: facilitator-prod.tfstate
│   │   └── staging/
│   │       ├── main.tf              # Symlink to ../../modules/facilitator-service/main.tf
│   │       ├── terraform.tfvars     # Staging config
│   │       └── backend.tf           # S3 backend: facilitator-staging.tfstate
│   ├── modules/
│   │   └── facilitator-service/     # Reusable module
│   │       ├── main.tf              # ECS cluster, service, task definition
│   │       ├── vpc.tf               # VPC, subnets, NAT, VPC endpoints
│   │       ├── alb.tf               # Load balancer, target group, listeners
│   │       ├── iam.tf               # Task execution/task roles
│   │       ├── security_groups.tf   # ALB + ECS tasks SGs
│   │       ├── cloudwatch.tf        # Logs, alarms
│   │       ├── ecr.tf               # Container registry
│   │       ├── route53.tf           # DNS records
│   │       ├── acm.tf               # SSL certificate
│   │       ├── variables.tf         # Input variables
│   │       ├── outputs.tf           # Output values
│   │       └── README.md            # Module documentation
│   ├── Makefile                     # Deployment commands
│   └── README.md                    # Infrastructure guide
├── x402-rs/                         # Application code (already exists)
├── Dockerfile                       # Container build
├── .github/
│   └── workflows/
│       ├── deploy-production.yml    # CI/CD for production
│       └── deploy-staging.yml       # CI/CD for staging
└── docs/
    ├── INFRASTRUCTURE.md            # Architecture diagrams
    ├── DEPLOYMENT.md                # Deployment runbook
    └── COST_ANALYSIS.md             # Monthly cost breakdown
```

---

## 4. Migration Plan (Production-Ready)

### 4.1 Phase 1: Preparation (Day 1)

**Tasks**:
1. Create new S3 bucket for facilitator terraform state
   ```bash
   aws s3api create-bucket \
     --bucket facilitator-terraform-state \
     --region us-east-1

   aws s3api put-bucket-versioning \
     --bucket facilitator-terraform-state \
     --versioning-configuration Status=Enabled

   aws dynamodb create-table \
     --table-name facilitator-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
   ```

2. Copy terraform code from `karmacadabra/terraform/ecs-fargate/` to `facilitator/terraform/modules/facilitator-service/`

3. Modify terraform code:
   - Change `for_each = var.agents` to single facilitator resource
   - Remove agent-specific conditionals (`each.key == "facilitator"`)
   - Simplify ALB listener rules (no path-based routing needed)
   - Update secret names (`karmacadabra-facilitator-mainnet` → `facilitator-evm-private-key`)
   - Update resource names (`karmacadabra-prod-facilitator` → `facilitator-prod`)

4. Create `terraform/environments/production/terraform.tfvars`:
   ```hcl
   project_name = "facilitator"
   environment  = "prod"
   aws_region   = "us-east-1"

   vpc_cidr     = "10.1.0.0/16"  # Different from karmacadabra (10.0.0.0/16)

   # Cost optimizations
   use_fargate_spot   = true
   single_nat_gateway = true
   enable_vpc_endpoints = false  # Save $28/month, use NAT for AWS API calls

   # Task sizing
   task_cpu    = 2048  # 2 vCPU (test 1024 after deployment)
   task_memory = 4096  # 4 GB (test 2048 after deployment)

   # Domain
   domain_name = "facilitator.ultravioletadao.xyz"
   enable_https = true
   ```

5. Create AWS Secrets Manager secrets (NEW names):
   ```bash
   # Copy existing secrets with new names
   aws secretsmanager create-secret \
     --name facilitator-evm-private-key \
     --description "Facilitator EVM private key for mainnet" \
     --secret-string '{"private_key":"0x..."}'

   aws secretsmanager create-secret \
     --name facilitator-solana-keypair \
     --description "Facilitator Solana keypair for mainnet" \
     --secret-string '{"private_key":"[...]"}'
   ```

---

### 4.2 Phase 2: Testing (Day 2-3)

**Tasks**:
1. Deploy staging environment:
   ```bash
   cd facilitator/terraform/environments/staging
   terraform init
   terraform plan
   terraform apply
   ```

2. Build and push x402-rs Docker image to new ECR repo:
   ```bash
   cd facilitator/x402-rs
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

   docker build -t facilitator:latest .

   ECR_URL=$(cd ../terraform/environments/staging && terraform output -raw ecr_repository_url)
   docker tag facilitator:latest $ECR_URL:latest
   docker push $ECR_URL:latest
   ```

3. Force ECS service deployment:
   ```bash
   aws ecs update-service \
     --cluster facilitator-staging \
     --service facilitator-staging \
     --force-new-deployment
   ```

4. Verify health:
   ```bash
   ALB_DNS=$(cd ../terraform/environments/staging && terraform output -raw alb_dns_name)
   curl http://$ALB_DNS/health
   # Expected: {"status":"healthy","networks":[...]}

   # Test payment flow
   cd ../../scripts
   python test_facilitator.py --url http://$ALB_DNS
   ```

5. Load test (optional):
   ```bash
   # Use locust/k6 to simulate production traffic
   k6 run --vus 100 --duration 5m load-test.js
   ```

---

### 4.3 Phase 3: Production Deployment (Day 4)

**Tasks**:
1. Deploy production infrastructure:
   ```bash
   cd facilitator/terraform/environments/production
   terraform init
   terraform plan -out=tfplan
   # REVIEW PLAN CAREFULLY
   terraform apply tfplan
   ```

2. Build and push production Docker image:
   ```bash
   cd facilitator/x402-rs
   docker build -t facilitator:v1.0.0 .

   ECR_URL=$(cd ../terraform/environments/production && terraform output -raw ecr_repository_url)
   docker tag facilitator:v1.0.0 $ECR_URL:v1.0.0
   docker tag facilitator:v1.0.0 $ECR_URL:latest
   docker push $ECR_URL:v1.0.0
   docker push $ECR_URL:latest
   ```

3. Verify new facilitator service healthy:
   ```bash
   NEW_ALB=$(cd ../terraform/environments/production && terraform output -raw alb_dns_name)
   curl http://$NEW_ALB/health
   # Should return 200 OK

   # Test transaction
   python test_facilitator.py --url http://$NEW_ALB
   ```

4. **DNS Cutover** (zero downtime):
   ```bash
   # Current: facilitator.ultravioletadao.xyz → karmacadabra ALB
   # New:     facilitator.ultravioletadao.xyz → facilitator ALB

   # Option A: Manual (in Route53 console)
   # 1. Go to Route53 → ultravioletadao.xyz hosted zone
   # 2. Edit facilitator.ultravioletadao.xyz A record
   # 3. Change Alias target from karmacadabra ALB to facilitator ALB
   # 4. Save changes (propagates in ~60s due to low TTL)

   # Option B: Terraform (if managing DNS with terraform)
   cd facilitator/terraform/environments/production
   terraform apply  # This creates new Route53 record pointing to new ALB
   ```

5. Verify DNS propagation:
   ```bash
   # Wait 2-5 minutes for DNS propagation
   dig facilitator.ultravioletadao.xyz
   # Should show new ALB IP address

   curl https://facilitator.ultravioletadao.xyz/health
   # Should return 200 OK from NEW infrastructure
   ```

6. Monitor CloudWatch metrics:
   - CPU utilization (target <75%)
   - Memory utilization (target <80%)
   - Request count
   - Target health
   - Error rate

---

### 4.4 Phase 4: Cleanup (Day 5)

**Tasks**:
1. Remove facilitator from karmacadabra terraform:
   ```bash
   cd karmacadabra/terraform/ecs-fargate

   # Edit variables.tf
   # Remove facilitator from agents map:
   # agents = {
   #   # facilitator = { ... }  # REMOVE THIS
   #   validator = { ... }
   #   karma-hello = { ... }
   #   # ... rest of agents
   # }

   terraform plan
   # Should show:
   # - Destroy aws_ecs_service.agents["facilitator"]
   # - Destroy aws_ecs_task_definition.agents["facilitator"]
   # - Destroy aws_lb_target_group.agents["facilitator"]
   # - Destroy aws_lb_listener_rule.agents_*["facilitator"]
   # - Destroy aws_cloudwatch_log_group.agents["facilitator"]
   # - Destroy aws_ecr_repository.agents["facilitator"]
   # - Destroy 10+ other facilitator resources

   terraform apply
   ```

2. Verify karmacadabra agents still healthy:
   ```bash
   for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
     curl https://$agent.karmacadabra.ultravioletadao.xyz/health
   done
   # All should return 200 OK
   ```

3. Delete old facilitator ECR images (if not reusing repo name):
   ```bash
   # Facilitator images now in new ECR repo: facilitator/facilitator
   # Old ECR repo: karmacadabra/facilitator (deleted by terraform destroy)
   ```

4. Update documentation:
   - `karmacadabra/README.md`: Remove facilitator references
   - `facilitator/README.md`: Add standalone deployment guide

---

### 4.5 Phase 5: Cost Optimization (Ongoing)

**Week 1-2**:
1. Monitor CloudWatch metrics:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ECS \
     --metric-name CPUUtilization \
     --dimensions Name=ServiceName,Value=facilitator-prod Name=ClusterName,Value=facilitator-prod \
     --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 3600 \
     --statistics Average,Maximum
   ```

2. If CPU <50% and Memory <50% for 7 days, reduce task size:
   ```hcl
   # terraform/environments/production/terraform.tfvars
   task_cpu    = 1024  # 1 vCPU (from 2048)
   task_memory = 2048  # 2 GB (from 4096)
   ```
   **Savings**: ~$17-22/month

3. If NAT data transfer <100GB/month, consider NAT instance:
   ```bash
   # Check NAT data transfer costs
   aws ce get-cost-and-usage \
     --time-period Start=2025-10-01,End=2025-10-31 \
     --granularity MONTHLY \
     --metrics BlendedCost \
     --filter file://nat-filter.json
   ```
   If <$5/month data transfer, NAT instance is cheaper.

4. Monitor VPC endpoint usage:
   ```bash
   # If ECR pulls <500GB/month, VPC endpoints cost more than NAT data transfer
   # Consider disabling VPC endpoints and using NAT for AWS API calls
   ```

**Month 1 Target**: Reduce facilitator costs to ~$50-60/month

---

## 5. Risk Analysis

### 5.1 High-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| DNS cutover causes downtime | Medium | High | Use low TTL (60s), test in staging first |
| New ALB URL not accessible | Low | High | Verify security groups allow 0.0.0.0/0:80,443 |
| Secrets not accessible in new account | Low | Critical | Copy secrets BEFORE deployment, test staging |
| Task won't start (IAM permissions) | Medium | High | Test staging, use same IAM policies as karmacadabra |
| Cost overruns (forgot Spot) | Low | Medium | Always set `use_fargate_spot = true` |
| Terraform state corruption | Low | Critical | Use S3 versioning + DynamoDB locks |

### 5.2 Rollback Plan

**If production deployment fails**:
1. **Immediate**: Revert DNS record to old karmacadabra ALB (60s propagation)
2. **Within 5 min**: Scale down new facilitator service to 0 tasks
3. **Within 10 min**: Scale up old facilitator service in karmacadabra stack
4. **Within 30 min**: Investigate issue, fix terraform code
5. **Next day**: Retry deployment with fixes

**If DNS propagation issues**:
- Use CloudFlare/Route53 health checks to automatically failover
- Keep old facilitator running for 24 hours after cutover
- Monitor error rates in both old and new services

---

## 6. Testing Checklist

### Pre-Deployment
- [ ] Terraform validate passes
- [ ] Terraform plan shows expected resources (60+ resources created)
- [ ] Staging environment deployed successfully
- [ ] Health endpoint responds (http://alb-dns/health)
- [ ] Payment flow works (test with scripts/test_facilitator.py)
- [ ] CloudWatch logs visible
- [ ] Auto-scaling tested (scale up to 3 tasks, back down to 1)
- [ ] Secrets accessible from ECS tasks
- [ ] VPC endpoints working (ECR pull succeeds)

### Post-Deployment
- [ ] HTTPS endpoint responds (https://facilitator.ultravioletadao.xyz/health)
- [ ] DNS resolves correctly (dig facilitator.ultravioletadao.xyz)
- [ ] ALB target health = healthy
- [ ] ECS service RUNNING state
- [ ] CloudWatch alarms in OK state
- [ ] Cost estimate matches projection (~$50-60/month)
- [ ] Old karmacadabra facilitator scaled down
- [ ] Integration tests pass (Python agents can call facilitator)

---

## 7. Critical Variables

**Must be set correctly** in `terraform.tfvars`:

```hcl
# COST-CRITICAL
use_fargate_spot         = true   # 70% cost savings
single_nat_gateway       = true   # ~$32/month savings
enable_vpc_endpoints     = false  # Save $28/month (acceptable for facilitator)

# NETWORK-CRITICAL
vpc_cidr = "10.1.0.0/16"  # MUST be different from karmacadabra (10.0.0.0/16)

# DOMAIN-CRITICAL
domain_name  = "facilitator.ultravioletadao.xyz"
enable_https = true

# TASK-CRITICAL (Start large, optimize later)
task_cpu    = 2048  # 2 vCPU (test 1024 after 1 week)
task_memory = 4096  # 4 GB (test 2048 after 1 week)

# ALB-CRITICAL (Base mainnet needs >60s for tx confirmation)
alb_idle_timeout = 180  # 3 minutes (accommodates Base mainnet settlement)

# SECRETS-CRITICAL
# In AWS Secrets Manager, create:
# - facilitator-evm-private-key: {"private_key": "0x..."}
# - facilitator-solana-keypair: {"private_key": "[...]"}
```

---

## 8. Terraform Code Diff (Key Changes)

### From (karmacadabra multi-agent):
```hcl
resource "aws_ecs_task_definition" "agents" {
  for_each = var.agents  # 8 agents

  family = "${var.project_name}-${var.environment}-${each.key}"
  cpu    = each.key == "facilitator" ? var.facilitator_task_cpu : var.task_cpu
  memory = each.key == "facilitator" ? var.facilitator_task_memory : var.task_memory

  container_definitions = jsonencode([{
    name  = each.key
    image = "${aws_ecr_repository.agents[each.key].repository_url}:latest"

    secrets = each.key == "facilitator" ? [
      { name = "EVM_PRIVATE_KEY", valueFrom = "..." }
    ] : [
      { name = "PRIVATE_KEY", valueFrom = "..." }
    ]
  }])
}

resource "aws_ecs_service" "agents" {
  for_each = var.agents
  # ...
}

variable "agents" {
  type = map(object({
    port              = number
    health_check_path = string
    priority          = number
  }))
  default = {
    facilitator = { port = 8080, health_check_path = "/health", priority = 50 }
    validator   = { port = 9001, health_check_path = "/health", priority = 100 }
    # ... 6 more agents
  }
}
```

### To (facilitator standalone):
```hcl
resource "aws_ecs_task_definition" "facilitator" {
  family = "${var.project_name}-${var.environment}"
  cpu    = var.task_cpu
  memory = var.task_memory

  container_definitions = jsonencode([{
    name  = "facilitator"
    image = "${aws_ecr_repository.facilitator.repository_url}:latest"

    secrets = [
      { name = "EVM_PRIVATE_KEY", valueFrom = "${data.aws_secretsmanager_secret.evm_key.arn}:private_key::" },
      { name = "SOLANA_PRIVATE_KEY", valueFrom = "${data.aws_secretsmanager_secret.solana_key.arn}:private_key::" }
    ]
  }])
}

resource "aws_ecs_service" "facilitator" {
  name = "${var.project_name}-${var.environment}"
  # ...
}

variable "task_cpu" {
  type    = number
  default = 2048  # Simplified - single value, no map
}

variable "task_memory" {
  type    = number
  default = 4096
}

# No agents map needed - single service
```

**Key Simplifications**:
- Remove `for_each` loops (single service)
- Remove conditional logic (`each.key == "facilitator"`)
- Simplify variables (no multi-agent maps)
- Simplify ALB rules (single target group)
- Remove agent-specific security group rules

---

## 9. Files to Create

### New Files in `facilitator/terraform/`:

```
terraform/
├── modules/facilitator-service/
│   ├── main.tf                    # ECS cluster, service, task definition
│   ├── vpc.tf                     # Copy from karmacadabra, change CIDR
│   ├── alb.tf                     # Simplified (1 target group, no path routing)
│   ├── iam.tf                     # Copy from karmacadabra, rename roles
│   ├── security_groups.tf         # Copy from karmacadabra, remove agent-specific rules
│   ├── cloudwatch.tf              # Simplified (1 log group, 5 alarms)
│   ├── ecr.tf                     # 1 repository (facilitator)
│   ├── route53.tf                 # 1 DNS record (facilitator.ultravioletadao.xyz)
│   ├── acm.tf                     # 1 certificate (facilitator.ultravioletadao.xyz)
│   ├── variables.tf               # Simplified (no agents map)
│   ├── outputs.tf                 # ALB DNS, ECR URL, etc.
│   └── README.md
├── environments/production/
│   ├── main.tf                    # module "facilitator" { source = "../../modules/facilitator-service" }
│   ├── backend.tf                 # S3 backend config
│   ├── terraform.tfvars           # Production config
│   └── outputs.tf                 # Proxy module outputs
├── environments/staging/
│   ├── main.tf
│   ├── backend.tf
│   ├── terraform.tfvars
│   └── outputs.tf
├── Makefile                       # Copy from karmacadabra, simplify (no multi-agent)
└── README.md                      # Infrastructure overview
```

### Modified Files in `facilitator/`:

```
x402-rs/
├── Dockerfile                     # Already exists - no changes needed
├── src/                           # Already exists - no changes needed
└── static/                        # Already exists - no changes needed

.github/workflows/
├── deploy-production.yml          # NEW - CI/CD pipeline
│   # On push to main:
│   # 1. Build Docker image
│   # 2. Push to ECR
│   # 3. Update ECS service
└── deploy-staging.yml             # NEW - CI/CD for staging

docs/
├── INFRASTRUCTURE.md              # NEW - Architecture diagrams
├── DEPLOYMENT.md                  # NEW - Runbook
└── COST_ANALYSIS.md               # NEW - Monthly cost breakdown

scripts/
├── test_facilitator.py            # Already exists - no changes
└── deploy.sh                      # NEW - One-click deployment script
```

---

## 10. Next Steps

1. **Review this analysis** with team
2. **Approve cost increase** (~$76/month for full duplication, or ~$40/month with optimizations)
3. **Choose migration approach** (recommend Option A: Clean Slate)
4. **Assign owner** for terraform migration
5. **Schedule deployment** (recommend off-peak hours, weekend)
6. **Create rollback runbook**
7. **Test in staging** (full end-to-end test)
8. **Deploy to production** (follow Phase 3 steps)
9. **Monitor for 1 week** (watch costs, performance)
10. **Optimize** (right-size tasks, remove unnecessary VPC endpoints)

---

## 11. Conclusion

**Feasibility**: ✅ **Highly Feasible**

The facilitator infrastructure is **extractable** with moderate effort. The current multi-agent architecture is well-organized, making separation straightforward. Key success factors:

1. **Clean Resource Separation**: Facilitator resources are already isolated (separate task definition, service, target group)
2. **Terraform Best Practices**: Code uses `for_each` and modules, easy to refactor
3. **Cost Impact Manageable**: With optimizations, cost increase is ~$4-10/month vs original
4. **Zero Downtime Possible**: Blue/green deployment via DNS cutover
5. **Rollback Simple**: Revert DNS record if issues occur

**Recommendation**: Proceed with extraction. The operational independence and clean separation are worth the cost overhead.

**Timeline**: 5 days (1 day prep, 2 days testing, 1 day production, 1 day cleanup)

**Effort**: Medium (20-30 hours of terraform work)

**Risk**: Low-Medium (mitigated by staging testing and rollback plan)

---

**End of Analysis**
