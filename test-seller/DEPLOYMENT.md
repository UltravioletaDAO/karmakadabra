# Test Seller - Deployment Guide

Quick guide to deploy the test-seller service to AWS ECS.

## Prerequisites

- AWS CLI configured with proper credentials
- Docker installed
- Terraform 1.0+ installed
- Access to AWS account `518898403364`

## Deployment Steps

### 1. Wallet Configuration ✅ DONE

The test-seller wallet has been created and stored in AWS Secrets Manager:

```
Address: 0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19
Secret: karmacadabra-test-seller (in AWS Secrets Manager)
```

**Verify**:
```bash
aws secretsmanager get-secret-value --secret-id karmacadabra-test-seller --region us-east-1 --query SecretString --output text | jq .
```

### 2. Terraform Configuration ✅ DONE

The following Terraform files have been updated:

1. **`terraform/ecs-fargate/variables.tf`**:
   - Added `test-seller` to agents map (port 8080, priority 700)

2. **`terraform/ecs-fargate/route53.tf`**:
   - Added DNS record for `test-seller.karmacadabra.ultravioletadao.xyz`

3. **`terraform/ecs-fargate/alb.tf`**:
   - Added HTTP/HTTPS routing rules (priority 15)
   - Routes `test-seller.karmacadabra.ultravioletadao.xyz` → test-seller target group

### 3. Apply Terraform

```bash
cd terraform/ecs-fargate

# Initialize (if first time)
terraform init

# Plan changes
terraform plan

# Apply (creates Route53 record, ALB rules, ECS task definition, target group)
terraform apply
```

**Expected resources to be created**:
- ECS Task Definition: `karmacadabra-prod-test-seller`
- ECS Service: `karmacadabra-prod-test-seller`
- Target Group: `karmacadabra-prod-test-seller-tg`
- Route53 Record: `test-seller.karmacadabra.ultravioletadao.xyz`
- ALB Listener Rules: HTTP (priority 15) + HTTPS (priority 15)

### 4. Build and Push Docker Image

#### Option A: Using deploy.sh script (Recommended)

```bash
cd test-seller
bash deploy.sh
```

This script will:
1. Build Docker image for linux/amd64
2. Login to ECR
3. Create ECR repository if needed
4. Tag and push image
5. Trigger ECS deployment

#### Option B: Manual steps

```bash
cd test-seller

# Build
docker build --platform linux/amd64 -t test-seller:latest .

# ECR Login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repo (if first time)
aws ecr create-repository --repository-name karmacadabra-prod-test-seller --region us-east-1

# Tag
docker tag test-seller:latest 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-test-seller:latest

# Push
docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-test-seller:latest

# Force new deployment
aws ecs update-service --cluster karmacadabra-prod --service karmacadabra-prod-test-seller --force-new-deployment --region us-east-1
```

### 5. Verify Deployment

#### Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-test-seller \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployments:deployments[0].status}'
```

**Expected output**:
```json
{
  "Status": "ACTIVE",
  "Running": 1,
  "Desired": 1,
  "Deployments": "PRIMARY"
}
```

#### Check Task Status

```bash
aws ecs list-tasks \
  --cluster karmacadabra-prod \
  --service-name karmacadabra-prod-test-seller \
  --region us-east-1
```

#### View Logs

```bash
aws logs tail /ecs/karmacadabra-prod-test-seller --follow --region us-east-1
```

**Expected logs**:
```
2025-10-30 12:00:00 - __main__ - INFO - 🚀 Test Seller Service starting up
2025-10-30 12:00:00 - __main__ - INFO -    Seller Address: 0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19
2025-10-30 12:00:00 - __main__ - INFO -    Price: $0.01 USDC
2025-10-30 12:00:00 - __main__ - INFO -    Network: Base mainnet
2025-10-30 12:00:00 - __main__ - INFO -    Facilitator: https://facilitator.ultravioletadao.xyz
```

#### Test Health Endpoint

```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "service": "test-seller",
  "network": "base",
  "price_usdc": "10000",
  "seller_address": "0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19",
  "facilitator": "https://facilitator.ultravioletadao.xyz"
}
```

#### Test Payment Required Endpoint

```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/hello
```

**Expected response (HTTP 402)**:
```json
{
  "error": "payment_required",
  "message": "Payment required to access this resource",
  "x402": {
    "version": 1,
    "accepts": [...]
  }
}
```

### 6. DNS Verification

Wait 2-5 minutes for DNS propagation, then:

```bash
# Check DNS resolution
nslookup test-seller.karmacadabra.ultravioletadao.xyz

# Or using dig
dig test-seller.karmacadabra.ultravioletadao.xyz
```

**Expected**: Should resolve to ALB DNS name (ends in `.elb.amazonaws.com`)

### 7. SSL Certificate

The wildcard certificate `*.karmacadabra.ultravioletadao.xyz` already covers `test-seller.karmacadabra.ultravioletadao.xyz`.

**Verify**:
```bash
curl -v https://test-seller.karmacadabra.ultravioletadao.xyz/health 2>&1 | grep "SSL certificate verify"
```

**Expected**: `SSL certificate verify ok`

## Cost Estimate

- **ECS Fargate Spot** (0.25 vCPU / 0.5GB): ~$1.50/month
- **ALB**: Shared with other services (no additional cost)
- **Route53**: Shared hosted zone (no additional cost)
- **ECR**: ~$0.10/month for image storage
- **CloudWatch Logs**: ~$0.50/month (7-day retention)

**Total**: ~$2.10/month

## Monitoring

### CloudWatch Metrics

```bash
# View CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=karmacadabra-prod-test-seller Name=ClusterName,Value=karmacadabra-prod \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1
```

### Service Statistics

```bash
curl https://test-seller.karmacadabra.ultravioletadao.xyz/stats
```

**Response**:
```json
{
  "total_requests": 1250,
  "paid_requests": 1200,
  "unpaid_requests": 50,
  "total_revenue_usdc": "$12.00",
  "price_per_request": "$0.01"
}
```

## Troubleshooting

### Service won't start

**Check task definition**:
```bash
aws ecs describe-task-definition --task-definition karmacadabra-prod-test-seller --region us-east-1
```

**Common issues**:
- ECR image not found → Push image again
- Secrets Manager permissions → Check IAM role
- Port conflict → Verify port 8080 is correct

### DNS not resolving

**Check Route53 record**:
```bash
aws route53 list-resource-record-sets \
  --hosted-zone-id $(aws route53 list-hosted-zones --query "HostedZones[?Name=='ultravioletadao.xyz.'].Id" --output text | cut -d'/' -f3) \
  --query "ResourceRecordSets[?Name=='test-seller.karmacadabra.ultravioletadao.xyz.']"
```

**Fix**: Re-run `terraform apply`

### Health check failing

**Check ALB target health**:
```bash
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups --names karmacadabra-prod-test-seller-tg --query 'TargetGroups[0].TargetGroupArn' --output text) \
  --region us-east-1
```

**Common issues**:
- `/health` endpoint not responding → Check logs
- Port mismatch → Verify container port 8080
- Security group blocking traffic → Check VPC config

### 502 Bad Gateway

**Possible causes**:
- Service not running → Check ECS service status
- Health check failing → Check `/health` endpoint
- Target group misconfigured → Verify target group settings

**Fix**:
```bash
# Restart service
aws ecs update-service --cluster karmacadabra-prod --service karmacadabra-prod-test-seller --force-new-deployment --region us-east-1
```

## Rollback

If deployment fails, rollback to previous version:

```bash
# Stop service
aws ecs update-service --cluster karmacadabra-prod --service karmacadabra-prod-test-seller --desired-count 0 --region us-east-1

# Delete service
aws ecs delete-service --cluster karmacadabra-prod --service karmacadabra-prod-test-seller --region us-east-1

# Remove Terraform resources
cd terraform/ecs-fargate
terraform destroy -target=aws_ecs_service.agents[\"test-seller\"]
```

## Next Steps

After successful deployment:

1. **Fund your payer wallet** with USDC on Base (see `WALLET_FUNDING.md`)
2. **Run load tests** using `load_test.py`
3. **Monitor costs** in AWS Cost Explorer
4. **Check stats** at https://test-seller.karmacadabra.ultravioletadao.xyz/stats

## Quick Reference

| Resource | Value |
|----------|-------|
| **Endpoint** | https://test-seller.karmacadabra.ultravioletadao.xyz |
| **Seller Wallet** | 0x4dFB1Cd42604194e79eDaCff4e0d28A576e40d19 |
| **ECS Cluster** | karmacadabra-prod |
| **ECS Service** | karmacadabra-prod-test-seller |
| **ECR Repo** | 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-test-seller |
| **Logs** | /ecs/karmacadabra-prod-test-seller |
| **Price** | $0.01 USDC per request |
| **Network** | Base mainnet (8453) |
