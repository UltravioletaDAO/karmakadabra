# test-seller-solana - Quick Deployment Guide

## Issue Fixed
**Problem**: `https://test-seller-solana.karmacadabra.ultravioletadao.xyz` was returning 403 "Access denied"
**Root Cause**: Service didn't exist - no infrastructure, no code, no DNS
**Solution**: Created complete test-seller-solana service with Terraform configuration

---

## Deployment Checklist

### ✅ COMPLETED (Already Done)
- [x] Created test-seller-solana service code (main.py, Dockerfile, requirements.txt)
- [x] Added to Terraform configuration (variables.tf - priority 750)
- [x] Created deployment script (deploy.sh)
- [x] Created documentation (README.md)
- [x] Committed and pushed to branch `claude/fix-503-seller-solana-011CUjQd9NL5AiiMAiUBjSFR`

### 🔧 TODO (Manual Steps Required)

#### Step 1: Create Solana Wallet (if not exists)

You need a Solana wallet for the service. If you don't have one:

```bash
# Install Solana CLI (if needed)
sh -c "$(curl -sSfL https://release.solana.com/stable/install)"

# Generate new keypair
solana-keygen new --outfile ~/test-seller-solana-keypair.json

# Get the public key
solana-keygen pubkey ~/test-seller-solana-keypair.json
```

Or use an existing Solana wallet from your infrastructure.

#### Step 2: Create AWS Secrets Manager Secret

```bash
# Set your Solana wallet details
SOLANA_ADDRESS="YOUR_SOLANA_PUBLIC_KEY"
SOLANA_PRIVATE_KEY="YOUR_SOLANA_PRIVATE_KEY_OR_SEED"

# Create the secret
aws secretsmanager create-secret \
  --name karmacadabra-test-seller-solana \
  --description "Wallet credentials for test-seller-solana service" \
  --secret-string "{\"address\":\"$SOLANA_ADDRESS\",\"private_key\":\"$SOLANA_PRIVATE_KEY\"}" \
  --region us-east-1

# Verify secret created
aws secretsmanager get-secret-value \
  --secret-id karmacadabra-test-seller-solana \
  --region us-east-1 \
  --query SecretString \
  --output text | jq .
```

**Expected output**:
```json
{
  "address": "YOUR_SOLANA_PUBLIC_KEY",
  "private_key": "YOUR_SOLANA_PRIVATE_KEY"
}
```

#### Step 3: Apply Terraform Configuration

```bash
cd terraform/ecs-fargate

# Initialize (if needed)
terraform init

# Plan to see what will be created
terraform plan

# Apply to create infrastructure
terraform apply
```

**Resources that will be created**:
- ECS Task Definition: `karmacadabra-prod-test-seller-solana`
- ECS Service: `karmacadabra-prod-test-seller-solana`
- Target Group: `karmacadabra-prod-test-seller-solana-tg`
- Route53 DNS Record: `test-seller-solana.karmacadabra.ultravioletadao.xyz`
- ALB Listener Rules:
  - HTTP (priority 750)
  - HTTPS (priority 1750)

Type `yes` when prompted to apply.

**Wait ~2-5 minutes** for DNS propagation.

#### Step 4: Build and Deploy Docker Image

```bash
cd test-seller-solana

# Run deployment script (requires Docker and AWS CLI)
bash deploy.sh
```

This will:
1. Build Docker image for linux/amd64
2. Login to ECR (AWS Container Registry)
3. Create ECR repository `karmacadabra-prod-test-seller-solana`
4. Push Docker image
5. Trigger ECS deployment

**Wait ~3-5 minutes** for ECS to pull image and start task.

#### Step 5: Verify Deployment

```bash
# Check DNS resolution
nslookup test-seller-solana.karmacadabra.ultravioletadao.xyz
# Should resolve to ALB DNS name

# Test health endpoint
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "service": "test-seller-solana",
  "network": "solana-devnet",
  "price_usdc": "10000",
  "seller_address": "YOUR_SOLANA_ADDRESS",
  "facilitator": "https://facilitator.ultravioletadao.xyz"
}
```

✅ **If you see this response, the service is working!**

#### Step 6: Test Payment Flow

```bash
# Test payment required endpoint
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/hello
```

**Expected response** (HTTP 402):
```json
{
  "error": "payment_required",
  "message": "Payment required to access this resource",
  "x402": {
    "version": 1,
    "accepts": [{
      "scheme": "exact",
      "network": "solana",
      "maxAmountRequired": "10000",
      ...
    }]
  }
}
```

---

## Monitoring

### Check ECS Service Status
```bash
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-test-seller-solana \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

**Expected**:
```json
{
  "Status": "ACTIVE",
  "Running": 1,
  "Desired": 1
}
```

### View Logs
```bash
aws logs tail /ecs/karmacadabra-prod-test-seller-solana --follow --region us-east-1
```

**Expected logs**:
```
2025-11-02 12:00:00 - __main__ - INFO - 🚀 Test Seller Service (Solana) starting up
2025-11-02 12:00:00 - __main__ - INFO -    Seller Address: YOUR_SOLANA_ADDRESS
2025-11-02 12:00:00 - __main__ - INFO -    Price: $0.01 USDC
2025-11-02 12:00:00 - __main__ - INFO -    Network: Solana Devnet
2025-11-02 12:00:00 - __main__ - INFO -    Facilitator: https://facilitator.ultravioletadao.xyz
```

### Check Service Statistics
```bash
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/stats
```

---

## Troubleshooting

### Issue: "Secret not found" error in logs

**Solution**: Create the AWS Secrets Manager secret (Step 2 above)

### Issue: DNS not resolving

**Cause**: DNS propagation delay or Route53 record not created

**Solution**:
1. Wait 5 minutes for DNS propagation
2. Check Route53 records:
```bash
aws route53 list-resource-record-sets \
  --hosted-zone-id $(aws route53 list-hosted-zones --query "HostedZones[?Name=='ultravioletadao.xyz.'].Id" --output text | cut -d'/' -f3) \
  --query "ResourceRecordSets[?contains(Name, 'test-seller-solana')]"
```

### Issue: 502 Bad Gateway

**Cause**: ECS task not running or health check failing

**Solution**:
1. Check ECS service status (see Monitoring section)
2. View logs for errors
3. Verify health endpoint responds: `curl http://TASK_IP:8080/health`

### Issue: "No basic auth credentials" in deploy.sh

**Cause**: Not logged into AWS ECR

**Solution**:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com
```

### Issue: Payment verification fails

**Cause**: Facilitator doesn't support Solana yet, or USDC address incorrect

**Solution**:
1. Verify facilitator has Solana support
2. Check USDC address: `4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU` (Devnet)
3. For mainnet, use: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`

---

## Cost Estimate

- **ECS Fargate Spot** (0.25 vCPU / 0.5GB): ~$1.50/month
- **ALB**: Shared (no additional cost)
- **Route53**: Shared hosted zone (no additional cost)
- **ECR**: ~$0.10/month for image storage
- **CloudWatch Logs**: ~$0.50/month (7-day retention)
- **Total**: ~$2.10/month

---

## Summary

**Created**: Complete test-seller-solana service infrastructure
**Status**: Code committed and pushed to branch
**Remaining**: 4 manual steps (wallet, secret, terraform, deploy)
**Time**: ~15-20 minutes for full deployment
**Result**: Working Solana payment test endpoint

For detailed documentation, see `test-seller-solana/README.md`
