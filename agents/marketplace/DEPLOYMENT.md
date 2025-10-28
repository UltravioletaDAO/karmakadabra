# Marketplace Deployment Guide

## Overview

The marketplace will deploy to AWS ECS Fargate alongside the existing 5 system agents (facilitator, validator, karma-hello, abracadabra, skill-extractor, voice-extractor).

**What Terraform Will Create:**
- ECR repository: `karmacadabra-dev-marketplace`
- ECS task definition: 0.25 vCPU / 0.5GB RAM (Fargate Spot)
- ECS service: 1-3 tasks with auto-scaling
- ALB target group: Health checks on `/health`
- ALB listener rules:
  - Path: `http://alb-url/marketplace/*` (priority 600)
  - Hostname: `http://marketplace.karmacadabra.ultravioletadao.xyz` (priority 1600)
- Route53 DNS: `marketplace.karmacadabra.ultravioletadao.xyz`

**Monthly Cost:** ~$1.50-2.00 (Fargate Spot 0.25 vCPU / 0.5GB)

## Prerequisites

1. Terraform configured (already done)
2. AWS CLI configured
3. Docker installed
4. ECR login credentials

## Deployment Steps

### Step 1: Update Terraform Configuration ✅

**Already done:** Added marketplace to `terraform/ecs-fargate/variables.tf`

```hcl
marketplace = {
  port              = 9000
  health_check_path = "/health"
  priority          = 600
}
```

### Step 2: Build and Push Docker Image

From project root:

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image (from project root)
cd /mnt/z/ultravioleta/dao/karmacadabra
docker build -f agents/marketplace/Dockerfile -t marketplace .

# Tag image
docker tag marketplace:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-dev-marketplace:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-dev-marketplace:latest
```

**Or use the build script:**

```bash
cd terraform/ecs-fargate
python ../../scripts/build-and-push.py marketplace
```

### Step 3: Deploy with Terraform

```bash
cd terraform/ecs-fargate

# Initialize (if first time)
terraform init

# Plan changes (review what will be created)
terraform plan

# Apply changes
terraform apply
```

**What Terraform will do:**
1. Create ECR repository for marketplace
2. Create ECS task definition with marketplace container
3. Create ECS service with 1 task (can scale to 3)
4. Create ALB target group
5. Create ALB listener rules (path + hostname)
6. Create Route53 DNS record

**Deployment time:** ~5-10 minutes

### Step 4: Verify Deployment

```bash
# Check ECS service status
aws ecs describe-services --cluster karmacadabra-dev --services karmacadabra-dev-marketplace

# Check task is running
aws ecs list-tasks --cluster karmacadabra-dev --service-name karmacadabra-dev-marketplace

# Test health endpoint
curl http://marketplace.karmacadabra.ultravioletadao.xyz/health

# Test marketplace endpoints
curl http://marketplace.karmacadabra.ultravioletadao.xyz/agents | jq
curl http://marketplace.karmacadabra.ultravioletadao.xyz/stats | jq
curl http://marketplace.karmacadabra.ultravioletadao.xyz/search?q=blockchain | jq
```

**Expected response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-28T...",
  "agents_loaded": 48
}
```

### Step 5: Monitor Logs

```bash
# View logs in CloudWatch
aws logs tail /ecs/karmacadabra-dev-marketplace --follow

# Or use AWS Console
# CloudWatch > Log groups > /ecs/karmacadabra-dev-marketplace
```

## Rollback

If deployment fails:

```bash
# Roll back Terraform changes
terraform apply -target=aws_ecs_service.agents[\"marketplace\"] -destroy

# Or roll back entire deployment
git revert <commit-hash>
terraform apply
```

## Troubleshooting

### Task fails to start

**Check task logs:**
```bash
aws ecs describe-tasks --cluster karmacadabra-dev --tasks <task-arn>
```

**Common issues:**
- Image not found: Push image to ECR first
- Port conflict: Ensure port 9000 not used by another service
- Demo files missing: Check COPY paths in Dockerfile

### Health check failing

**Verify container is running:**
```bash
docker run -p 9000:9000 marketplace:latest
curl http://localhost:9000/health
```

**Check logs:**
```bash
aws logs tail /ecs/karmacadabra-dev-marketplace --since 10m
```

### DNS not resolving

**Check Route53 record:**
```bash
aws route53 list-resource-record-sets --hosted-zone-id <zone-id> | grep marketplace
```

**Wait for DNS propagation:** Can take 1-5 minutes

## Architecture Summary

```
Internet
   │
   ├─> ALB (karmacadabra-dev-alb.us-east-1.elb.amazonaws.com)
   │    │
   │    ├─> /marketplace/* → Marketplace Target Group
   │    │                    └─> ECS Task (0.25 vCPU / 0.5GB)
   │    │                         └─> Container (port 9000)
   │    │                              └─> Loads 48 cards + 48 profiles
   │    │
   │    ├─> /karma-hello/* → Karma-Hello Target Group
   │    ├─> /abracadabra/* → Abracadabra Target Group
   │    └─> ... (other agents)
   │
   └─> Route53 (marketplace.karmacadabra.ultravioletadao.xyz)
        └─> CNAME → ALB
```

**Total System:**
- 1 facilitator (1 vCPU / 2GB) ~$12/month
- 6 agents (0.25 vCPU / 0.5GB each) ~$9/month
- ALB ~$16/month
- NAT Gateway ~$32/month
- **Total: ~$70-85/month**

## Post-Deployment

1. Test all endpoints in `/agents/marketplace/README.md`
2. Update monitoring dashboards
3. Add marketplace to `scripts/test_all_endpoints.py`
4. Document in MASTER_PLAN.md
5. Announce marketplace availability to users

## Next Steps

- Add metrics and monitoring (CloudWatch dashboards)
- Set up alarms for failed health checks
- Configure auto-scaling policies
- Add caching layer (CloudFront) if needed
