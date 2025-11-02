# Terraform Extraction - Visual Architecture

## Current State: Multi-Agent Shared Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AWS Account (karmacadabra)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ VPC (10.0.0.0/16)                                                  │ │
│  │                                                                    │ │
│  │  ┌──────────────┐  ┌──────────────┐                              │ │
│  │  │Public Subnet │  │Public Subnet │                              │ │
│  │  │  us-east-1a  │  │  us-east-1b  │                              │ │
│  │  │              │  │              │                              │ │
│  │  │  ┌────────┐  │  │              │                              │ │
│  │  │  │  NAT   │  │  │              │                              │ │
│  │  │  │Gateway │  │  │              │                              │ │
│  │  │  └────┬───┘  │  │              │                              │ │
│  │  └───────┼──────┘  └──────────────┘                              │ │
│  │          │                                                        │ │
│  │  ┌───────▼──────┐  ┌──────────────┐                              │ │
│  │  │Private Subnet│  │Private Subnet│                              │ │
│  │  │  us-east-1a  │  │  us-east-1b  │                              │ │
│  │  │              │  │              │                              │ │
│  │  │  ┌────────┐  │  │  ┌────────┐  │                              │ │
│  │  │  │Facilitr│  │  │  │Validator  │                              │ │
│  │  │  │Task    │  │  │  │Task    │  │                              │ │
│  │  │  │2vCPU   │  │  │  │0.25vCPU│  │                              │ │
│  │  │  └────────┘  │  │  └────────┘  │                              │ │
│  │  │              │  │              │                              │ │
│  │  │  ┌────────┐  │  │  ┌────────┐  │                              │ │
│  │  │  │Karma   │  │  │  │Abracad.│  │                              │ │
│  │  │  │Hello   │  │  │  │Task    │  │                              │ │
│  │  │  └────────┘  │  │  └────────┘  │                              │ │
│  │  │              │  │              │                              │ │
│  │  │  ┌────────┐  │  │  ┌────────┐  │                              │ │
│  │  │  │Skill   │  │  │  │Voice   │  │                              │ │
│  │  │  │Extract.│  │  │  │Extract.│  │                              │ │
│  │  │  └────────┘  │  │  └────────┘  │                              │ │
│  │  │              │  │              │                              │ │
│  │  │  ┌────────┐  │  │  ┌────────┐  │                              │ │
│  │  │  │Market  │  │  │  │Test    │  │                              │ │
│  │  │  │place   │  │  │  │Seller  │  │                              │ │
│  │  │  └────────┘  │  │  └────────┘  │                              │ │
│  │  └──────────────┘  └──────────────┘                              │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Application Load Balancer (karmacadabra-prod-alb)                 │ │
│  │                                                                    │ │
│  │  Listener Rules:                                                  │ │
│  │  - /facilitator/*       → facilitator:8080                        │ │
│  │  - /validator/*         → validator:9001                          │ │
│  │  - /karma-hello/*       → karma-hello:9002                        │ │
│  │  - /abracadabra/*       → abracadabra:9003                        │ │
│  │  - /skill-extractor/*   → skill-extractor:9004                    │ │
│  │  - /voice-extractor/*   → voice-extractor:9005                    │ │
│  │  - /marketplace/*       → marketplace:9000                        │ │
│  │  - /test-seller/*       → test-seller:8080                        │ │
│  │                                                                    │ │
│  │  Hostname Rules:                                                  │ │
│  │  - facilitator.karmacadabra.ultravioletadao.xyz                   │ │
│  │  - validator.karmacadabra.ultravioletadao.xyz                     │ │
│  │  - facilitator.ultravioletadao.xyz (root domain)                  │ │
│  │  ... (8 total hostname rules)                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ ECS Cluster (karmacadabra-prod)                                   │ │
│  │                                                                    │ │
│  │  Services: 8 total                                                │ │
│  │  - karmacadabra-prod-facilitator (Fargate On-Demand)             │ │
│  │  - karmacadabra-prod-validator (Fargate Spot)                    │ │
│  │  - karmacadabra-prod-karma-hello (Fargate Spot)                  │ │
│  │  - karmacadabra-prod-abracadabra (Fargate Spot)                  │ │
│  │  - karmacadabra-prod-skill-extractor (Fargate Spot)              │ │
│  │  - karmacadabra-prod-voice-extractor (Fargate Spot)              │ │
│  │  - karmacadabra-prod-marketplace (Fargate Spot)                  │ │
│  │  - karmacadabra-prod-test-seller (Fargate Spot)                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Shared IAM Roles                                                   │ │
│  │  - ecs_task_execution (used by all 8 services)                    │ │
│  │  - ecs_task (used by all 8 services)                              │ │
│  │  - ecs_autoscaling                                                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  Cost: ~$163-180/month (8 services)                                      │
│        - Facilitator share: ~$46-56/month                                │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Target State: Separated Standalone Infrastructure

```
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│    AWS Account (karmacadabra)           │   │    AWS Account (facilitator)            │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  ┌───────────────────────────────────┐ │   │  ┌───────────────────────────────────┐ │
│  │ VPC (10.0.0.0/16)                 │ │   │  │ VPC (10.1.0.0/16)                 │ │
│  │                                   │ │   │  │                                   │ │
│  │  ┌─────────┐  ┌─────────┐        │ │   │  │  ┌─────────┐  ┌─────────┐        │ │
│  │  │Public   │  │Public   │        │ │   │  │  │Public   │  │Public   │        │ │
│  │  │Subnet 1a│  │Subnet 1b│        │ │   │  │  │Subnet 1a│  │Subnet 1b│        │ │
│  │  │         │  │         │        │ │   │  │  │         │  │         │        │ │
│  │  │ ┌─NAT─┐ │  │         │        │ │   │  │  │ ┌─NAT─┐ │  │         │        │ │
│  │  │ │Gate │ │  │         │        │ │   │  │  │ │Gate │ │  │         │        │ │
│  │  │ └──┬──┘ │  │         │        │ │   │  │  │ └──┬──┘ │  │         │        │ │
│  │  └────┼────┘  └─────────┘        │ │   │  │  └────┼────┘  └─────────┘        │ │
│  │       │                           │ │   │  │       │                           │ │
│  │  ┌────▼────┐  ┌─────────┐        │ │   │  │  ┌────▼────┐  ┌─────────┐        │ │
│  │  │Private  │  │Private  │        │ │   │  │  │Private  │  │Private  │        │ │
│  │  │Subnet 1a│  │Subnet 1b│        │ │   │  │  │Subnet 1a│  │Subnet 1b│        │ │
│  │  │         │  │         │        │ │   │  │  │         │  │         │        │ │
│  │  │┌──────┐ │  │┌──────┐ │        │ │   │  │  │┌──────┐ │  │┌──────┐ │        │ │
│  │  ││Valid.│ │  ││Karma │ │        │ │   │  │  ││Facil.│ │  ││Facil.│ │        │ │
│  │  ││Task  │ │  ││Hello │ │        │ │   │  │  ││Task 1│ │  ││Task 2│ │        │ │
│  │  │└──────┘ │  │└──────┘ │        │ │   │  │  ││2vCPU │ │  ││(Scale)│ │        │ │
│  │  │┌──────┐ │  │┌──────┐ │        │ │   │  │  │└──────┘ │  │└──────┘ │        │ │
│  │  ││Abrac.│ │  ││Skill │ │        │ │   │  │  └─────────┘  └─────────┘        │ │
│  │  │└──────┘ │  │└──────┘ │        │ │   │  └───────────────────────────────────┘ │
│  │  │┌──────┐ │  │┌──────┐ │        │ │   │                                         │
│  │  ││Voice │ │  ││Market│ │        │ │   │  ┌───────────────────────────────────┐ │
│  │  │└──────┘ │  │└──────┘ │        │ │   │  │ ALB (facilitator-prod-alb)        │ │
│  │  │┌──────┐ │  │         │        │ │   │  │                                   │ │
│  │  ││Test  │ │  │         │        │ │   │  │ Listener:                         │ │
│  │  ││Seller│ │  │         │        │ │   │  │  - /* → facilitator:8080          │ │
│  │  │└──────┘ │  │         │        │ │   │  │                                   │ │
│  │  └─────────┘  └─────────┘        │ │   │  │ (SIMPLE - no path routing)        │ │
│  │                                   │ │   │  └───────────────────────────────────┘ │
│  └───────────────────────────────────┘ │   │                                         │
│                                         │   │  ┌───────────────────────────────────┐ │
│  ┌───────────────────────────────────┐ │   │  │ ECS Cluster (facilitator-prod)    │ │
│  │ ALB (karmacadabra-prod-alb)       │ │   │  │                                   │ │
│  │                                   │ │   │  │ Service:                          │ │
│  │ Listener Rules:                   │ │   │  │  - facilitator-prod-facilitator   │ │
│  │  - /validator/*                   │ │   │  │    (Fargate On-Demand)            │ │
│  │  - /karma-hello/*                 │ │   │  │    Auto-scaling: 1-3 tasks        │ │
│  │  - /abracadabra/*                 │ │   │  └───────────────────────────────────┘ │
│  │  - /skill-extractor/*             │ │   │                                         │
│  │  - /voice-extractor/*             │ │   │  ┌───────────────────────────────────┐ │
│  │  - /marketplace/*                 │ │   │  │ IAM Roles (facilitator-specific)  │ │
│  │  - /test-seller/*                 │ │   │  │  - facilitator-task-exec          │ │
│  │  (facilitator REMOVED)            │ │   │  │  - facilitator-task               │ │
│  └───────────────────────────────────┘ │   │  └───────────────────────────────────┘ │
│                                         │   │                                         │
│  ┌───────────────────────────────────┐ │   │  ┌───────────────────────────────────┐ │
│  │ ECS Cluster (karmacadabra-prod)   │ │   │  │ ECR Repository                    │ │
│  │                                   │ │   │  │  - facilitator/facilitator        │ │
│  │ Services: 7 total (no facilitator)│ │   │  │    (changed from karmacadabra/)   │ │
│  │  - validator                      │ │   │  └───────────────────────────────────┘ │
│  │  - karma-hello                    │ │   │                                         │
│  │  - abracadabra                    │ │   │  ┌───────────────────────────────────┐ │
│  │  - skill-extractor                │ │   │  │ Secrets Manager                   │ │
│  │  - voice-extractor                │ │   │  │  - facilitator-evm-private-key    │ │
│  │  - marketplace                    │ │   │  │  - facilitator-solana-keypair     │ │
│  │  - test-seller                    │ │   │  │    (renamed from karmacadabra-*)  │ │
│  └───────────────────────────────────┘ │   │  └───────────────────────────────────┘ │
│                                         │   │                                         │
│  Cost: ~$126-138/month (7 services)    │   │  Cost: ~$113-123/month                  │
│                                         │   │        (or $41-51 optimized)            │
│                                         │   │                                         │
└─────────────────────────────────────────┘   └─────────────────────────────────────────┘
                    │                                           │
                    │                                           │
                    ▼                                           ▼
         ┌──────────────────────┐                  ┌──────────────────────┐
         │ Route53 (ultravioleta│                  │ Route53 (ultravioleta│
         │       dao.xyz)       │                  │       dao.xyz)       │
         ├──────────────────────┤                  ├──────────────────────┤
         │ validator.karmacad.. │                  │ facilitator.         │
         │ karma-hello.karmacad │                  │   ultravioletadao.xyz│
         │ abracadabra.karmacad │                  │                      │
         │ skill-extractor...   │                  │ Points to:           │
         │ voice-extractor...   │                  │ facilitator-prod-alb │
         │ marketplace.karmacad │                  │                      │
         │ test-seller.karmacad │                  │ (DNS cutover here)   │
         └──────────────────────┘                  └──────────────────────┘
```

---

## Resource Mapping: Old → New

### Duplicated Resources (New Names)

| Current (karmacadabra) | New (facilitator) | Change |
|------------------------|-------------------|--------|
| VPC: 10.0.0.0/16 | VPC: 10.1.0.0/16 | Different CIDR |
| karmacadabra-prod-alb | facilitator-prod-alb | New ALB |
| karmacadabra-prod (cluster) | facilitator-prod (cluster) | New cluster |
| ecs_task_execution role | facilitator-task-exec role | New role name |
| ecs_task role | facilitator-task role | New role name |
| alb security group | facilitator-alb security group | New SG |
| ecs_tasks security group | facilitator-tasks security group | New SG |

### Renamed Resources (Same Type, New Name)

| Current | New | Notes |
|---------|-----|-------|
| karmacadabra/facilitator (ECR) | facilitator/facilitator (ECR) | Requires new Docker push |
| karmacadabra-prod-facilitator (service) | facilitator-prod-facilitator | New ECS service |
| /ecs/karmacadabra-prod/facilitator (logs) | /ecs/facilitator-prod/facilitator | New log group |
| karmacadabra-facilitator-mainnet (secret) | facilitator-evm-private-key | NEW secret name |
| karmacadabra-solana-keypair (secret) | facilitator-solana-keypair | NEW secret name |

### Removed Resources (No Longer Needed)

| Resource | Reason |
|----------|--------|
| 7 other ALB listener rules | Facilitator gets single default action |
| 7 other agent hostnames | Only facilitator.ultravioletadao.xyz needed |
| facilitator.karmacadabra.ultravioletadao.xyz | Use root domain instead |
| Service Connect namespace | Not needed for single-service deployment |

---

## Cost Breakdown Diagram

### Current (Shared)

```
┌────────────────────────────────────────────────┐
│ Total Karmacadabra Cost: $163-180/month        │
├────────────────────────────────────────────────┤
│                                                │
│  Shared Infrastructure ($76/month):            │
│  ┌──────────────────────────────────────────┐ │
│  │ NAT Gateway:       $32/month             │ │
│  │ ALB:               $16/month             │ │
│  │ VPC Endpoints:     $28/month             │ │
│  └──────────────────────────────────────────┘ │
│  Split 8 ways = $9.50/agent                    │
│                                                │
│  Facilitator-Specific ($37-47/month):          │
│  ┌──────────────────────────────────────────┐ │
│  │ Fargate (2vCPU/4GB): $35-45/month        │ │
│  │ CloudWatch Logs:     $2/month            │ │
│  │ ECR Storage:         $0.50/month         │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  Facilitator Total: $46-56/month               │
│                                                │
└────────────────────────────────────────────────┘
```

### After Extraction (Optimized)

```
┌────────────────────────────────────────────────┐   ┌────────────────────────────────────────────────┐
│ Karmacadabra Cost: $126-138/month (7 agents)   │   │ Facilitator Cost: $41-51/month (optimized)     │
├────────────────────────────────────────────────┤   ├────────────────────────────────────────────────┤
│                                                │   │                                                │
│  Shared Infrastructure ($76/month):            │   │  Infrastructure:                               │
│  ┌──────────────────────────────────────────┐ │   │  ┌──────────────────────────────────────────┐ │
│  │ NAT Gateway:       $32/month             │ │   │  │ NAT Instance (t4g.nano): $8/month        │ │
│  │ ALB:               $16/month             │ │   │  │ ALB:                     $16/month       │ │
│  │ VPC Endpoints:     $28/month             │ │   │  │ VPC Endpoints:           $0 (removed)    │ │
│  └──────────────────────────────────────────┘ │   │  └──────────────────────────────────────────┘ │
│  Split 7 ways = $10.86/agent                   │   │                                                │
│                                                │   │  Compute:                                      │
│  Agents-Specific ($50-62/month):               │   │  ┌──────────────────────────────────────────┐ │
│  ┌──────────────────────────────────────────┐ │   │  │ Fargate (1vCPU/2GB): $17-22/month        │ │
│  │ Fargate (7 agents): $44-56/month         │ │   │  │ CloudWatch Logs:     $2/month            │ │
│  │ CloudWatch Logs:    $6/month             │ │   │  │ ECR Storage:         $0.50/month         │ │
│  └──────────────────────────────────────────┘ │   │  └──────────────────────────────────────────┘ │
│                                                │   │                                                │
│                                                │   │  Total: $41-51/month                           │
│                                                │   │                                                │
└────────────────────────────────────────────────┘   └────────────────────────────────────────────────┘

Combined: $167-189/month                             Net Increase: +$4-9/month from original
```

---

## Migration Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          BEFORE MIGRATION                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Internet                                                                │
│      │                                                                   │
│      ▼                                                                   │
│  facilitator.ultravioletadao.xyz (DNS)                                  │
│      │                                                                   │
│      ▼                                                                   │
│  karmacadabra-prod-alb                                                  │
│      │                                                                   │
│      ├─ facilitator:8080 ────► ECS Task (karmacadabra-prod-facilitator)│
│      ├─ validator:9001 ───────► ECS Task (karmacadabra-prod-validator) │
│      ├─ karma-hello:9002 ─────► ECS Task (karmacadabra-prod-karma-h..) │
│      └─ ... (5 more agents)                                             │
│                                                                          │
│  State: Single terraform stack managing 8 services                      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

                                    │
                                    │ MIGRATION
                                    │
                                    ▼

┌──────────────────────────────────────────────────────────────────────────┐
│                        DURING MIGRATION (Day 4)                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Internet                                                                │
│      │                                                                   │
│      ├─ facilitator.ultravioletadao.xyz (OLD DNS) ─────────┐            │
│      │                                                      │            │
│      └─ facilitator-new-alb-dns.us-east-1.elb.amazonaws... │            │
│                                                             │            │
│      ┌──────────────────────────────────────────────────────┘            │
│      │                                                                   │
│      ▼                                                                   │
│  karmacadabra-prod-alb (OLD)          facilitator-prod-alb (NEW)        │
│      │                                        │                          │
│      ├─ facilitator:8080 (IDLE)               ├─ facilitator:8080 ──┐   │
│      ├─ validator:9001 ──────►                │                      │   │
│      └─ ... (7 agents)                        │                      │   │
│                                                ▼                      │   │
│                                           NEW ECS Task                │   │
│                                           (facilitator-prod)          │   │
│                                                                       │   │
│  DNS Cutover: Update Route53 record ──────────────────────────────────┘   │
│  (60 second TTL, minimal downtime)                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

                                    │
                                    │ CLEANUP (Day 5)
                                    │
                                    ▼

┌──────────────────────────────────────────────────────────────────────────┐
│                          AFTER MIGRATION                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Internet                                                                │
│      │                                                                   │
│      ├─ facilitator.ultravioletadao.xyz ──────────────────┐             │
│      │                                                     │             │
│      └─ validator.karmacadabra.ultravioletadao.xyz ───┐   │             │
│                                                        │   │             │
│      ┌─────────────────────────────────────────────────┘   │             │
│      │                                                     │             │
│      ▼                                                     ▼             │
│  karmacadabra-prod-alb                      facilitator-prod-alb        │
│      │                                           │                       │
│      ├─ validator:9001 ───────►                 └─ facilitator:8080 ──► │
│      ├─ karma-hello:9002 ─────►                                         │
│      └─ ... (6 more agents)                     NEW ECS Task            │
│                                                  (facilitator-prod)      │
│  State:                                                                  │
│  - karmacadabra terraform: 7 services                                   │
│  - facilitator terraform: 1 service                                     │
│  - Clean separation                                                      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Terraform State Separation

```
BEFORE:
┌─────────────────────────────────────────────────────────────┐
│ S3: karmacadabra-terraform-state                            │
│     Key: ecs-fargate/terraform.tfstate                      │
│                                                             │
│  Resources: 150+ total                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ VPC Resources (20)                                     │ │
│  │ ALB Resources (30)                                     │ │
│  │ ECS Cluster (5)                                        │ │
│  │ ECS Services (8) ◄──── Includes facilitator           │ │
│  │ Task Definitions (8) ◄──── Includes facilitator       │ │
│  │ IAM Roles (10)                                         │ │
│  │ CloudWatch (40)                                        │ │
│  │ Route53 (10)                                           │ │
│  │ ECR (8) ◄──── Includes facilitator                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

AFTER:
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│ S3: karmacadabra-terraform-state    │   │ S3: facilitator-terraform-state     │
│     Key: ecs-fargate/terraform.tfst │   │     Key: production/terraform.tfst  │
│                                     │   │                                     │
│  Resources: ~130 total              │   │  Resources: ~60 total               │
│  ┌────────────────────────────────┐ │   │  ┌────────────────────────────────┐ │
│  │ VPC Resources (20)             │ │   │  │ VPC Resources (20)             │ │
│  │ ALB Resources (30)             │ │   │  │ ALB Resources (8) - simplified │ │
│  │ ECS Cluster (5)                │ │   │  │ ECS Cluster (5)                │ │
│  │ ECS Services (7) - no facil.  │ │   │  │ ECS Service (1) - facilitator  │ │
│  │ Task Definitions (7)           │ │   │  │ Task Definition (1)            │ │
│  │ IAM Roles (10) - shared       │ │   │  │ IAM Roles (10) - facil. only   │ │
│  │ CloudWatch (35) - no facil.   │ │   │  │ CloudWatch (7) - facilitator   │ │
│  │ Route53 (8) - agents only     │ │   │  │ Route53 (2) - facilitator      │ │
│  │ ECR (7) - no facilitator      │ │   │  │ ECR (1) - facilitator          │ │
│  └────────────────────────────────┘ │   │  └────────────────────────────────┘ │
└─────────────────────────────────────┘   └─────────────────────────────────────┘
         │                                          │
         │ terraform apply                          │ terraform apply
         │ (manages karmacadabra agents)            │ (manages facilitator)
         ▼                                          ▼
    INDEPENDENT                                 INDEPENDENT
```

---

## Key Takeaways

1. **Clean Separation**: Facilitator infrastructure is cleanly extractable
2. **Duplication Necessary**: VPC, NAT, ALB must be duplicated for independence
3. **Cost Trade-Off**: +$4-10/month for operational independence (acceptable)
4. **Simplified Code**: 40% less terraform code (no multi-agent complexity)
5. **Zero Downtime**: DNS cutover enables migration without service interruption
6. **Independent Lifecycle**: Can destroy/recreate facilitator without affecting agents

---

**For implementation details, see**:
- Full Analysis: `EXTRACTION_MASTER_PLAN_TERRAFORM_ANALYSIS.md`
- Summary: `TERRAFORM_EXTRACTION_SUMMARY.md`
