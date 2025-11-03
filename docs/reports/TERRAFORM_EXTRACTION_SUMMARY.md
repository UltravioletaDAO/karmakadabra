# Terraform Extraction Summary (for EXTRACTION_MASTER_PLAN.md)

**This document provides the TL;DR version for integration into the main extraction plan.**

---

## Terraform Infrastructure Analysis

### Current State

The facilitator shares infrastructure with 7 other karmacadabra agents via a **multi-tenant ECS deployment**:

- **Shared Resources** (8 services total):
  - VPC + NAT Gateway ($32/month)
  - Application Load Balancer ($16/month)
  - ECS Cluster (karmacadabra-prod)
  - IAM Roles (ecs_task_execution, ecs_task)
  - Security Groups (alb, ecs_tasks)
  - VPC Endpoints ($28/month)

- **Facilitator-Specific Resources**:
  - ECS Task Definition (2 vCPU / 4 GB, Fargate on-demand)
  - ECS Service (karmacadabra-prod-facilitator)
  - ALB Target Group + 4 Listener Rules
  - ECR Repository (karmacadabra/facilitator)
  - CloudWatch Log Group + 5 Alarms
  - Route53 DNS Records (2 domains)

**Current Facilitator Cost**: ~$46-56/month
- Fargate (2 vCPU / 4 GB): $35-45/month
- Share of shared infra: $9.50/month

---

## Extraction Strategy

### Recommended Approach: **Full Duplication**

**Create new standalone infrastructure** with these resources:

| Resource | Action | Rationale |
|----------|--------|-----------|
| VPC | Duplicate | Free, operational independence |
| NAT Gateway | Duplicate | Required for private subnets |
| ALB | Duplicate | Simpler routing (no multi-agent paths) |
| ECS Cluster | Duplicate | Clean separation |
| IAM Roles | Duplicate | Different secret ARN patterns |
| Security Groups | Duplicate | Facilitator-specific rules |
| VPC Endpoints | Optional | $28/month, can use NAT instead |

**Why not share infrastructure?**
- Operational independence (can destroy facilitator without affecting agents)
- Zero terraform state dependencies
- Simpler disaster recovery
- Clean namespace separation

---

## Cost Impact

### Without Optimization (Full Duplication)

**New Facilitator Stack**:
- Fargate (2 vCPU / 4 GB, 24/7): $35-45/month
- ALB: $16/month (NEW)
- NAT Gateway: $32/month (NEW)
- VPC Endpoints: $28/month (NEW)
- CloudWatch: $2/month
- **Total**: ~$113-123/month

**Net Increase**: +$76/month (from $46 to $113-123)

### With Aggressive Optimization

Apply these cost optimizations:

1. **Remove VPC Endpoints**: -$28/month
   - Use NAT for AWS API calls (ECR, Secrets Manager, CloudWatch)
   - Trade-off: +$5-10/month NAT data transfer

2. **Right-Size Tasks**: -$20/month
   - Test 1 vCPU / 2 GB (50% smaller)
   - Monitor CPU/memory <50% for 1 week before reducing

3. **Use NAT Instance**: -$24/month
   - t4g.nano NAT instance ($8/month) vs NAT Gateway ($32/month)
   - Trade-off: Requires maintenance, lower throughput

**Optimized Total**: ~$41-51/month
**Net Increase from Original**: +$4-10/month ✅ **Acceptable**

---

## Migration Plan (5 Days)

### Day 1: Preparation
- Create S3 backend for facilitator terraform state
- Copy terraform code from `karmacadabra/terraform/ecs-fargate/` to `facilitator/terraform/`
- Simplify code (remove `for_each` loops, agent map)
- Create new AWS Secrets Manager secrets (`facilitator-evm-private-key`, `facilitator-solana-keypair`)

### Day 2-3: Testing
- Deploy staging environment (`facilitator-staging`)
- Build and push Docker image to new ECR
- Test health endpoint
- Load test payment flow
- Verify auto-scaling

### Day 4: Production Deployment
- Deploy production infrastructure (`facilitator-prod`)
- Push production Docker image (tag v1.0.0)
- Verify health at new ALB DNS
- **DNS Cutover**: Update `facilitator.ultravioletadao.xyz` → new ALB
- Monitor for 2 hours

### Day 5: Cleanup
- Remove facilitator from karmacadabra terraform
- Delete old facilitator resources
- Update documentation

---

## Critical Variables

**Must be set in terraform.tfvars**:

```hcl
# COST-CRITICAL
use_fargate_spot   = true   # 70% savings (but facilitator uses on-demand for stability)
single_nat_gateway = true   # Save $32/month vs multi-AZ

# NETWORK-CRITICAL
vpc_cidr = "10.1.0.0/16"    # DIFFERENT from karmacadabra (10.0.0.0/16)

# ALB-CRITICAL
alb_idle_timeout = 180      # 3 minutes (Base mainnet needs >60s for tx settlement)

# SECRETS-CRITICAL
# Create in AWS Secrets Manager:
# - facilitator-evm-private-key
# - facilitator-solana-keypair
```

---

## Files to Create

### Terraform Structure

```
facilitator/terraform/
├── modules/facilitator-service/     # Reusable module
│   ├── main.tf                      # ECS cluster, service, task
│   ├── vpc.tf                       # VPC, NAT, VPC endpoints
│   ├── alb.tf                       # Load balancer (simplified)
│   ├── iam.tf                       # Task execution/task roles
│   ├── security_groups.tf           # ALB + ECS tasks SGs
│   ├── cloudwatch.tf                # Logs, alarms
│   ├── ecr.tf                       # Container registry
│   ├── route53.tf                   # DNS record
│   ├── acm.tf                       # SSL certificate
│   ├── variables.tf                 # Input variables
│   └── outputs.tf                   # Outputs
├── environments/production/
│   ├── main.tf                      # Calls module
│   ├── backend.tf                   # S3 backend config
│   └── terraform.tfvars             # Production values
├── environments/staging/
│   └── ... (same structure)
└── Makefile                         # Deployment commands
```

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| DNS cutover downtime | Medium | High | Use 60s TTL, test staging first |
| Secrets not accessible | Low | Critical | Copy secrets BEFORE deployment |
| Cost overruns | Low | Medium | Always set `use_fargate_spot = true` |
| Terraform state corruption | Low | Critical | S3 versioning + DynamoDB locks |

**Rollback Plan**: Revert DNS to old karmacadabra ALB (60s propagation)

---

## Key Simplifications vs Multi-Agent

**Removed Complexity**:
- ❌ No `for_each = var.agents` loops
- ❌ No `each.key == "facilitator"` conditionals
- ❌ No agent-specific ALB path routing
- ❌ No multi-agent security group rules

**Result**: ~40% less terraform code, easier to maintain

---

## Next Steps

1. **Review cost analysis** - Approve $4-10/month increase
2. **Create S3 backend** for terraform state
3. **Copy & simplify terraform code**
4. **Deploy staging** - Full end-to-end test
5. **Deploy production** - Follow 5-day migration plan
6. **Monitor & optimize** - Right-size tasks after 1 week

---

## Recommendation

✅ **Proceed with extraction**

The facilitator infrastructure is **well-suited for extraction**. The multi-agent architecture is clean, and separation is straightforward. With cost optimizations, the overhead is minimal ($4-10/month).

**Benefits**:
- Operational independence
- Simpler deployment (no multi-agent coordination)
- Clean namespace (no karmacadabra prefix)
- Standalone repository (self-contained)

**Timeline**: 5 days
**Effort**: 20-30 hours
**Risk**: Low-Medium

---

**For detailed analysis, see**: `EXTRACTION_MASTER_PLAN_TERRAFORM_ANALYSIS.md`
