# Karmacadabra ECS Fargate Deployment Guide

Complete guide for deploying and managing Karmacadabra agents on AWS ECS Fargate.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Step-by-Step Deployment](#step-by-step-deployment)
4. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
5. [Cost Management](#cost-management)

---

## Prerequisites

### Required Tools

- **AWS CLI** configured with credentials (account ID: 518898403364)
- **Docker Desktop** installed and running
- **Terraform** (already used to deploy infrastructure)

### Verify Prerequisites

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check Docker
docker --version
docker info

# Check Terraform state
cd terraform/ecs-fargate
terraform output
```

---

## Quick Start

### Complete Deployment (One Command)

```powershell
# Windows PowerShell
cd Z:\ultravioleta\dao\karmacadabra

# 1. Build and push images (10-30 minutes)
.\terraform\ecs-fargate\build-and-push.ps1

# 2. Deploy and monitor (5-10 minutes)
.\terraform\ecs-fargate\deploy-and-monitor.ps1
```

```bash
# Linux/Mac/WSL
cd /path/to/karmacadabra

# 1. Build and push images
bash terraform/ecs-fargate/build-and-push.sh

# 2. Deploy and monitor
bash terraform/ecs-fargate/deploy-and-monitor.sh
```

---

## Step-by-Step Deployment

### Step 1: Build and Push Docker Images

**What it does:**
- Builds Docker images for all 5 agents
- Tags images with ECR repository URLs
- Pushes to AWS Elastic Container Registry

**Duration:** 10-30 minutes (depends on internet speed and Docker cache)

**Commands:**

```powershell
# Windows
cd Z:\ultravioleta\dao\karmacadabra
.\terraform\ecs-fargate\build-and-push.ps1
```

```bash
# Linux/Mac/WSL
cd /path/to/karmacadabra
bash terraform/ecs-fargate/build-and-push.sh
```

**Expected output:**
```
=========================================
Karmacadabra ECR Build and Push
=========================================

[1/3] Logging in to ECR...
✓ Successfully logged in to ECR

[2/3] Building Docker images...
Building validator...
✓ Built validator successfully

Building karma-hello...
✓ Built karma-hello successfully

[3/3] Tagging and pushing images to ECR...
Pushing validator...
✓ Pushed validator to ECR successfully
```

**Troubleshooting:**
- **Docker not running**: Start Docker Desktop and wait for it to fully initialize
- **ECR login fails**: Check AWS credentials with `aws sts get-caller-identity`
- **Build fails**: Check Dockerfile.agent exists in project root

---

### Step 2: Deploy to ECS

**What it does:**
- Forces new deployment for all 5 ECS services
- Monitors deployment progress
- Tests health endpoints
- Shows recent logs

**Duration:** 5-10 minutes

**Commands:**

```powershell
# Windows
cd Z:\ultravioleta\dao\karmacadabra
.\terraform\ecs-fargate\deploy-and-monitor.ps1
```

```bash
# Linux/Mac/WSL
cd /path/to/karmacadabra
bash terraform/ecs-fargate/deploy-and-monitor.sh
```

**Expected output:**
```
=========================================
Karmacadabra ECS Deployment & Monitor
=========================================

[STEP 1/5] Forcing new deployment for all services...
✓ validator deployment initiated
✓ karma-hello deployment initiated
✓ abracadabra deployment initiated
✓ skill-extractor deployment initiated
✓ voice-extractor deployment initiated

[STEP 2/5] Monitoring deployment status...
Checking status (0s elapsed)...
  ⟳ validator: 0/1 running (IN_PROGRESS)
  ⟳ karma-hello: 0/1 running (IN_PROGRESS)
  ...

Checking status (60s elapsed)...
  ✓ validator: 1/1 running (COMPLETED)
  ✓ karma-hello: 1/1 running (COMPLETED)
  ...

All deployments completed!

[STEP 3/5] Testing health endpoints...
Testing via ALB (path-based routing)...
  validator: ✓ OK (HTTP 200)
  karma-hello: ✓ OK (HTTP 200)
  ...

Testing via custom domains...
  validator: ✓ OK (HTTP 200)
  karma-hello: ⚠ DNS not propagated yet
  ...

[STEP 4/5] Showing recent logs...

[STEP 5/5] Deployment Summary
```

---

## Monitoring and Troubleshooting

### Check Service Status

```bash
# All services at once
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-validator karmacadabra-prod-karma-hello \
  --query 'services[*].[serviceName,desiredCount,runningCount,deployments[0].rolloutState]' \
  --output table
```

### View Logs

```bash
# Stream logs live
aws logs tail /ecs/karmacadabra-prod/validator --follow

# View last 1 hour
aws logs tail /ecs/karmacadabra-prod/validator --since 1h

# View last 100 lines
aws logs tail /ecs/karmacadabra-prod/validator | tail -100
```

### Test Health Endpoints

```bash
# Custom domains (once DNS propagates)
curl http://validator.karmacadabra.ultravioletadao.xyz/health
curl http://karma-hello.karmacadabra.ultravioletadao.xyz/health
curl http://abracadabra.karmacadabra.ultravioletadao.xyz/health
curl http://skill-extractor.karmacadabra.ultravioletadao.xyz/health
curl http://voice-extractor.karmacadabra.ultravioletadao.xyz/health

# ALB direct (works immediately)
ALB_DNS="karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com"
curl http://$ALB_DNS/validator/health
curl http://$ALB_DNS/karma-hello/health
```

### Common Issues

#### 1. Tasks Keep Restarting

**Symptoms:** Tasks start then immediately stop

**Diagnosis:**
```bash
# List stopped tasks
aws ecs list-tasks --cluster karmacadabra-prod --desired-status STOPPED

# Get task details
aws ecs describe-tasks --cluster karmacadabra-prod --tasks <task-arn>
```

**Common causes:**
- Missing secrets in AWS Secrets Manager
- Application crashes on startup
- Insufficient memory (increase in variables.tf)
- Health check failures

#### 2. Health Checks Failing

**Symptoms:** Tasks marked unhealthy, constantly replaced

**Diagnosis:**
```bash
# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>
```

**Solutions:**
- Check application logs for startup errors
- Verify health endpoint returns 200 OK
- Increase health check grace period in main.tf

#### 3. Container Crashes

**Symptoms:** Container exits with non-zero exit code

**Diagnosis:**
```bash
# Get stopped task reason
aws ecs describe-tasks --cluster karmacadabra-prod --tasks <task-id> \
  --query 'tasks[0].stoppedReason'

# Check container logs
aws logs tail /ecs/karmacadabra-prod/validator --since 1h
```

**Common causes:**
- Missing environment variables
- Invalid AWS credentials
- Python/dependency errors

#### 4. DNS Not Resolving

**Symptoms:** Custom domains return connection refused

**Diagnosis:**
```bash
# Check DNS records
nslookup validator.karmacadabra.ultravioletadao.xyz

# Should return ALB DNS:
# karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com
```

**Solutions:**
- Wait 5-30 minutes for DNS propagation
- Verify Route53 records exist
- Use ALB DNS directly in the meantime

### SSH into Running Container

```bash
# Get task ID
TASK_ID=$(aws ecs list-tasks \
  --cluster karmacadabra-prod \
  --service-name karmacadabra-prod-validator \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text | cut -d'/' -f3)

# Execute shell
aws ecs execute-command \
  --cluster karmacadabra-prod \
  --task $TASK_ID \
  --container validator \
  --interactive \
  --command '/bin/bash'
```

---

## Cost Management

### Current Configuration

**Estimated Monthly Cost: $79-96**

Breakdown:
- Fargate Tasks (Spot): $25-40 (5 agents, 24/7)
- Application Load Balancer: $16-18
- NAT Gateway: $32
- CloudWatch (logs + metrics): $5-8
- ECR (image storage): $1-2

### Cost Optimization Strategies

#### 1. Scale Down When Not in Use

```bash
# Scale to 0 (stop all tasks)
for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
  aws ecs update-service \
    --cluster karmacadabra-prod \
    --service karmacadabra-prod-$agent \
    --desired-count 0
done

# Scale back up
for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
  aws ecs update-service \
    --cluster karmacadabra-prod \
    --service karmacadabra-prod-$agent \
    --desired-count 1
done
```

**Savings:** ~$25-40/month when scaled to 0

#### 2. Reduce Task Sizes

Edit `terraform/ecs-fargate/variables.tf`:

```hcl
variable "task_cpu" {
  default = 256  # 0.25 vCPU (smallest)
}

variable "task_memory" {
  default = 512  # 0.5 GB (smallest for 256 CPU)
}
```

**Savings:** Already using smallest sizes

#### 3. Reduce Log Retention

Edit `terraform/ecs-fargate/variables.tf`:

```hcl
variable "log_retention_days" {
  default = 3  # Instead of 7
}
```

**Savings:** ~$2-3/month

#### 4. Disable Container Insights

Edit `terraform/ecs-fargate/variables.tf`:

```hcl
variable "enable_container_insights" {
  default = false
}
```

**Savings:** ~$3-5/month

**Warning:** Loses detailed metrics

---

## Deployment Checklist

### Before Deployment

- [ ] AWS credentials configured
- [ ] Docker Desktop running
- [ ] Terraform infrastructure deployed
- [ ] AWS Secrets Manager has agent credentials
- [ ] Dockerfile.agent exists in project root

### During Deployment

- [ ] Images built successfully
- [ ] Images pushed to ECR
- [ ] All 5 services deployed
- [ ] Tasks started (running count = desired count)
- [ ] Health checks passing

### After Deployment

- [ ] Test path-based URLs (via ALB)
- [ ] Test custom domain URLs (may take time for DNS)
- [ ] Check CloudWatch logs for errors
- [ ] Monitor auto-scaling behavior
- [ ] Set up CloudWatch alarms notifications (optional)

---

## Quick Reference

### Agent Endpoints

**Custom Domains:**
- http://validator.karmacadabra.ultravioletadao.xyz/health
- http://karma-hello.karmacadabra.ultravioletadao.xyz/health
- http://abracadabra.karmacadabra.ultravioletadao.xyz/health
- http://skill-extractor.karmacadabra.ultravioletadao.xyz/health
- http://voice-extractor.karmacadabra.ultravioletadao.xyz/health

**ALB Direct:**
- http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/validator/health
- http://karmacadabra-prod-alb-1072717858.us-east-1.elb.amazonaws.com/karma-hello/health
- ...

### Useful Commands

```bash
# View all running tasks
aws ecs list-tasks --cluster karmacadabra-prod --desired-status RUNNING

# Force redeploy single service
aws ecs update-service --cluster karmacadabra-prod --service karmacadabra-prod-validator --force-new-deployment

# Stop all services (scale to 0)
aws ecs update-service --cluster karmacadabra-prod --service karmacadabra-prod-validator --desired-count 0

# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=karmacadabra-prod-validator Name=ClusterName,Value=karmacadabra-prod \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-01T01:00:00Z \
  --period 300 \
  --statistics Average
```

---

## Next Steps

After successful deployment:

1. **Monitor logs** for any application errors
2. **Test agent functionality** (not just health endpoints)
3. **Set up monitoring alerts** (CloudWatch → SNS → Email)
4. **Configure CI/CD** for automated deployments
5. **Implement blue-green deployments** for zero-downtime updates
6. **Add HTTPS** with ACM certificate
7. **Configure WAF** for security (optional)

For infrastructure changes, see `terraform/ecs-fargate/README.md`
