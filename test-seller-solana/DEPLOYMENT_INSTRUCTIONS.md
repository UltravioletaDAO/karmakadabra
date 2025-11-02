# Test Seller Solana - Deployment Instructions

## ✅ Status: Ready to Deploy

All code and configurations have been created. **DO NOT deploy yet** - wait until buyer wallets are funded.

---

## 📦 What's Been Created

### 1. Test Seller Solana (FastAPI Server)
- **Location**: `test-seller-solana/`
- **Endpoint**: Will be `https://test-seller-solana.karmacadabra.ultravioletadao.xyz`
- **Network**: Solana mainnet
- **Asset**: USDC (`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`)
- **Price**: 0.01 USDC per message
- **Facilitator**: `https://facilitator.ultravioletadao.xyz` ✓ (NO .prod, NO .dev)

### 2. Load Test Script
- **Location**: `test-seller-solana/load_test_solana.py`
- **Creates**: Solana VersionedTransaction with SPL Token transfer
- **Features**: Sequential testing, detailed logging, transaction links

### 3. Keypairs Generated

**Seller Keypair:**
```
Public Key: Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB
File: test-seller-solana/seller_keypair.json
```

**Buyer Keypair:** Not generated yet - do this tomorrow

### 4. Docker Image
- **Pushed to ECR**: ✓
- **Repository**: `518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/test-seller-solana`
- **Digest**: `sha256:fc974079a839bbe19097bc00b95021cec60a5ca676562163979e123c210c2e02`

### 5. AWS Infrastructure
- **CloudWatch Log Group**: `/ecs/karmacadabra-prod-test-seller-solana` ✓
- **ECS Task Definition**: `karmacadabra-prod-test-seller-solana` (registered)
- **ECS Service**: NOT created yet (needs to be created manually)

---

## 🔧 BOTH Sellers Updated

**✓ test-seller (EVM)**: Updated to use `facilitator.ultravioletadao.xyz`
**✓ test-seller-solana**: Updated to use `facilitator.ultravioletadao.xyz`

---

## 📝 Tomorrow's Steps

### Step 1: Generate Buyer Keypair

```bash
cd test-seller-solana
pip install -r requirements_loadtest.txt
python generate_keypair.py

# This creates: buyer_keypair.json
# Save the public key that's printed!
```

### Step 2: Fund Wallets

**Seller (Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB):**
- Does NOT need SOL (facilitator pays fees)
- Just needs to exist to receive USDC

**Buyer (your generated pubkey):**
- **SOL**: ~0.001 SOL for transaction fees (~$0.10)
- **USDC**: Amount for testing (1 USDC = 100 requests)

Transfer from your main Solana wallet or buy from exchange.

### Step 3: Create ECS Service

The Docker image is already in ECR, but the service doesn't exist yet. Run this:

```bash
# Get network config from existing service
NETWORK_CONFIG=$(aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1 \
  --query 'services[0].networkConfiguration.awsvpcConfiguration' \
  --output json)

# Extract subnets and security groups
SUBNETS=$(echo $NETWORK_CONFIG | jq -r '.subnets | join(",")')
SECURITY_GROUPS=$(echo $NETWORK_CONFIG | jq -r '.securityGroups | join(",")')

# Create service
aws ecs create-service \
  --cluster karmacadabra-prod \
  --service-name karmacadabra-prod-test-seller-solana \
  --task-definition karmacadabra-prod-test-seller-solana \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUPS],assignPublicIp=ENABLED}" \
  --region us-east-1
```

### Step 4: Configure ALB + Route53 (If Needed)

**Check if ALB target group exists:**
```bash
aws elbv2 describe-target-groups \
  --region us-east-1 \
  --query 'TargetGroups[?TargetGroupName==`test-seller-solana-tg`]'
```

**If doesn't exist, create target group:**
```bash
# Get VPC ID from facilitator service
VPC_ID=$(aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --region us-east-1 \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets[0]' \
  --output text | xargs aws ec2 describe-subnets --subnet-ids --region us-east-1 --query 'Subnets[0].VpcId' --output text)

# Create target group
aws elbv2 create-target-group \
  --name test-seller-solana-tg \
  --protocol HTTP \
  --port 8080 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --region us-east-1

# Get ALB ARN
ALB_ARN=$(aws elbv2 describe-load-balancers \
  --region us-east-1 \
  --query 'LoadBalancers[?contains(LoadBalancerName, `karmacadabra`)].LoadBalancerArn' \
  --output text)

# Get HTTPS listener ARN
LISTENER_ARN=$(aws elbv2 describe-listeners \
  --load-balancer-arn $ALB_ARN \
  --region us-east-1 \
  --query 'Listeners[?Protocol==`HTTPS`].ListenerArn' \
  --output text)

# Add listener rule for test-seller-solana.karmacadabra.ultravioletadao.xyz
aws elbv2 create-rule \
  --listener-arn $LISTENER_ARN \
  --priority 15 \
  --conditions Field=host-header,Values=test-seller-solana.karmacadabra.ultravioletadao.xyz \
  --actions Type=forward,TargetGroupArn=$(aws elbv2 describe-target-groups --names test-seller-solana-tg --region us-east-1 --query 'TargetGroups[0].TargetGroupArn' --output text) \
  --region us-east-1
```

**Add Route53 DNS Record:**
```bash
# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --region us-east-1 \
  --query 'LoadBalancers[?contains(LoadBalancerName, `karmacadabra`)].DNSName' \
  --output text)

# Get ALB Hosted Zone ID
ALB_ZONE=$(aws elbv2 describe-load-balancers \
  --region us-east-1 \
  --query 'LoadBalancers[?contains(LoadBalancerName, `karmacadabra`)].CanonicalHostedZoneId' \
  --output text)

# Get Route53 Hosted Zone ID for ultravioletadao.xyz
ZONE_ID=$(aws route53 list-hosted-zones \
  --query 'HostedZones[?Name==`ultravioletadao.xyz.`].Id' \
  --output text | cut -d'/' -f3)

# Create DNS record
cat > change-batch.json <<EOF
{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "test-seller-solana.karmacadabra.ultravioletadao.xyz",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "$ALB_ZONE",
        "DNSName": "$ALB_DNS",
        "EvaluateTargetHealth": true
      }
    }
  }]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch file://change-batch.json

rm change-batch.json
```

### Step 5: Verify Deployment

```bash
# Wait ~60 seconds for service to start

# Check service status
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-test-seller-solana \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployments:deployments[0].status}'

# Check logs
aws logs tail /ecs/karmacadabra-prod-test-seller-solana --follow --region us-east-1

# Test HTTPS endpoint
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "test-seller-solana",
#   "seller_pubkey": "Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB",
#   "network": "solana"
# }
```

### Step 6: Run Load Test

```bash
cd test-seller-solana

python load_test_solana.py \
  --keypair buyer_keypair.json \
  --seller Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB \
  --num-requests 5 \
  --verbose
```

---

## 🔄 Redeploy Test Seller (EVM) with New Facilitator URL

The EVM test-seller was also updated to use `facilitator.ultravioletadao.xyz`. Redeploy it:

```bash
cd test-seller
./deploy.sh
```

---

## 📊 Expected Results

**Success Rate**: Should be >90% once:
- ✓ Buyer has SOL for fees
- ✓ Buyer has USDC for payments
- ✓ Facilitator is properly funded
- ✓ HTTPS is working

**Transaction Time**: ~400ms (Solana finalization is much faster than EVM)

**Cost per Request**:
- USDC Payment: $0.01
- SOL Fee: ~$0.0005 (paid by facilitator)
- Total: ~$0.0105

---

## 🚨 Important Notes

1. **Seller keypair is generated** - saved in `seller_keypair.json`
2. **Buyer keypair NOT generated yet** - do this tomorrow
3. **ECS service NOT created yet** - do this after funding wallets
4. **Both sellers now use `facilitator.ultravioletadao.xyz`** (no .prod, no .dev)
5. **Docker image is already in ECR** - no need to rebuild unless you change code

---

## 📞 Quick Commands Reference

```bash
# Generate buyer keypair
python generate_keypair.py

# Check service status
aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-test-seller-solana --region us-east-1

# View logs
aws logs tail /ecs/karmacadabra-prod-test-seller-solana --follow --region us-east-1

# Test endpoint
curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health

# Run load test
python load_test_solana.py --keypair buyer_keypair.json --seller Ez4frLQzDbV1AT9BNJkQFEjyTFRTsEwJ5YFaSGG8nRGB --num-requests 5 --verbose
```

---

## ✅ Checklist Before Deployment

- [ ] Generated buyer keypair (`python generate_keypair.py`)
- [ ] Funded buyer with SOL (~0.001 SOL)
- [ ] Funded buyer with USDC (for testing)
- [ ] Created ECS service
- [ ] Configured ALB target group (if needed)
- [ ] Added Route53 DNS record (if needed)
- [ ] Verified HTTPS endpoint works (`curl https://test-seller-solana.karmacadabra.ultravioletadao.xyz/health`)
- [ ] Ran load test successfully
