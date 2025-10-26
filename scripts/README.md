# Karmacadabra Deployment Scripts

Complete suite of idempotent deployment scripts for Karmacadabra infrastructure.

## Quick Start

```bash
# Full deployment (fund wallets + build images + deploy to Fargate)
python scripts/deploy-all.py

# Partial deployments
python scripts/fund-wallets.py --confirm            # Fund wallets only
python scripts/build-and-push.py                    # Build and push images only
python scripts/deploy-to-fargate.py --force-deploy  # Deploy to Fargate only
```

## Master Deployment Script

### `deploy-all.py`

Orchestrates the complete deployment pipeline in the correct order.

**What it does:**
1. Checks prerequisites (Python, Docker, AWS CLI, Terraform)
2. Funds all agent wallets with AVAX for gas fees
3. Builds Docker images and pushes to ECR
4. Applies Terraform infrastructure changes
5. Forces ECS service redeployments
6. Verifies all services are healthy

**Usage:**
```bash
# Full deployment
python scripts/deploy-all.py

# Skip wallet funding (wallets already funded)
python scripts/deploy-all.py --skip-fund

# Skip Docker build (use existing images)
python scripts/deploy-all.py --skip-build

# Force rebuild Docker images (ignore cache)
python scripts/deploy-all.py --force-rebuild

# Skip health check
python scripts/deploy-all.py --skip-health
```

**Typical workflow:**
```bash
# First time setup - do everything
python scripts/deploy-all.py

# Code changes only - rebuild and redeploy
python scripts/deploy-all.py --skip-fund

# Infrastructure changes only - skip build
python scripts/deploy-all.py --skip-fund --skip-build
```

---

## Individual Scripts

### `fund-wallets.py`

Funds all Karmacadabra wallets with AVAX for gas fees using the ERC-20 deployer wallet.

**Features:**
- Fully idempotent - checks balances first
- Only funds wallets below threshold (0.05 AVAX)
- Fetches addresses from AWS Secrets Manager
- Configurable amounts per wallet

**Wallets funded:**
- `facilitator`: 1.0 AVAX (needs more for settling many transactions)
- `validator-agent`: 0.10 AVAX
- `karma-hello-agent`: 0.10 AVAX
- `abracadabra-agent`: 0.10 AVAX
- `skill-extractor-agent`: 0.10 AVAX
- `voice-extractor-agent`: 0.10 AVAX
- `client-agent`: 0.10 AVAX (if exists)

**Usage:**
```bash
# Dry run (default)
python scripts/fund-wallets.py

# Execute funding
python scripts/fund-wallets.py --confirm
```

**Output:**
```
[OK] facilitator               2.1971 AVAX - Already funded
[FUND] validator-agent         0.0234 AVAX - NEEDS FUNDING (top up to 0.10)
```

---

### `build-and-push.py`

Builds Docker images and pushes them to Amazon ECR.

**Features:**
- Fully idempotent - checks if images exist
- Supports prebuilt images (facilitator uses `ukstv/x402-facilitator:latest`)
- Creates ECR repositories if they don't exist
- Force rebuild option

**Agents:**
- `facilitator` - x402 payment facilitator (Rust)
- `validator` - Data quality validation agent
- `karma-hello` - Chat logs seller/buyer
- `abracadabra` - Transcripts seller/buyer
- `skill-extractor` - Skill profiles seller/buyer
- `voice-extractor` - Personality profiles seller/buyer

**Usage:**
```bash
# Build all agents
python scripts/build-and-push.py

# Build specific agent
python scripts/build-and-push.py facilitator

# Force rebuild (ignore cache)
python scripts/build-and-push.py --force
```

**Example output:**
```
[BUILD] facilitator
  [PREBUILT] Using prebuilt image: ukstv/x402-facilitator:latest
  [OK] Pulled prebuilt image
  [PUSH] Pushing to ECR...
  [OK] Pushed to ECR: 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/facilitator:latest

[BUILD] validator
  [OK] Built image: karmacadabra/validator:latest
  [PUSH] Pushing to ECR...
  [OK] Pushed to ECR: 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/validator:latest
```

---

### `deploy-to-fargate.py`

Deploys infrastructure to AWS Fargate using Terraform and forces ECS service updates.

**Features:**
- Fully idempotent - safe to run multiple times
- Applies Terraform changes automatically
- Forces new ECS deployments with latest images
- Can deploy specific services
- Optional wait for services to stabilize

**Usage:**
```bash
# Terraform apply only
python scripts/deploy-to-fargate.py

# Terraform + force ECS redeployment
python scripts/deploy-to-fargate.py --force-deploy

# Force redeploy specific service
python scripts/deploy-to-fargate.py facilitator

# Skip Terraform (redeploy only)
python scripts/deploy-to-fargate.py --skip-terraform --force-deploy

# Wait for services to stabilize
python scripts/deploy-to-fargate.py --force-deploy --wait
```

**Example output:**
```
[1/4] Initializing Terraform...
  [OK] Terraform initialized

[2/4] Running Terraform plan...
  [OK] Terraform plan completed

[3/4] Applying Terraform changes...
  [OK] Terraform apply completed

[4/4] Forcing ECS service deployments...
  [DEPLOY] Forcing deployment of facilitator...
  [OK] Deployment triggered for facilitator (status: PRIMARY)

DEPLOYMENT STATUS
[OK]   facilitator          1/1 tasks, 1 deployment(s)
[OK]   validator            1/1 tasks, 1 deployment(s)
```

---

## Service Endpoints

After deployment, services are available at:

- **Facilitator**: https://facilitator.ultravioletadao.xyz/health
- **Validator**: https://validator.karmacadabra.ultravioletadao.xyz/health
- **Karma-Hello**: https://karma-hello.karmacadabra.ultravioletadao.xyz/health
- **Abracadabra**: https://abracadabra.karmacadabra.ultravioletadao.xyz/health
- **Skill-Extractor**: https://skill-extractor.karmacadabra.ultravioletadao.xyz/health
- **Voice-Extractor**: https://voice-extractor.karmacadabra.ultravioletadao.xyz/health

## Testing

```bash
# Test facilitator
curl https://facilitator.ultravioletadao.xyz/health
curl https://facilitator.ultravioletadao.xyz/supported

# Test all services
for service in facilitator validator karma-hello abracadabra skill-extractor voice-extractor; do
  echo "Testing $service..."
  curl -s https://$service.karmacadabra.ultravioletadao.xyz/health || \
  curl -s https://$service.ultravioletadao.xyz/health
  echo ""
done
```

## Monitoring

```bash
# View logs
aws logs tail /ecs/karmacadabra-prod/facilitator --follow
aws logs tail /ecs/karmacadabra-prod/validator --follow

# Check service status
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-facilitator \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# List running tasks
aws ecs list-tasks --cluster karmacadabra-prod
```

## Troubleshooting

### Wallet Funding Issues

**Problem**: Deployer wallet has insufficient AVAX
```
[FAIL] Insufficient balance in deployer wallet!
       Need: 1.5000 AVAX
       Have: 0.2000 AVAX
```

**Solution**: Get AVAX from faucet
```bash
# Go to https://faucet.avax.network/
# Send to deployer: 0x34033041a5944B8F10f8E4D8496Bfb84f1A293A8
```

### Docker Build Issues

**Problem**: Rust build fails for facilitator
```
error: let chains are only allowed in Rust 2024 or later
```

**Solution**: Use prebuilt image (already configured)
```python
'facilitator': {
    'use_prebuilt': True,
    'prebuilt_image': 'ukstv/x402-facilitator:latest'
}
```

### ECS Deployment Issues

**Problem**: Service not starting
```
[FAIL] facilitator          0/1 tasks, 1 deployment(s)
```

**Solution**: Check CloudWatch logs
```bash
aws logs tail /ecs/karmacadabra-prod/facilitator --since 30m --follow
```

Common issues:
- Missing environment variables → Check Terraform configuration
- Insufficient memory → Increase task_memory in variables.tf
- Container health check failing → Check /health endpoint implementation

### Terraform Issues

**Problem**: State lock
```
Error: Error acquiring the state lock
```

**Solution**: Clear DynamoDB lock
```bash
# Identify lock ID from error message
aws dynamodb delete-item \
  --table-name karmacadabra-terraform-locks \
  --key '{"LockID":{"S":"ecs-fargate/terraform.tfstate"}}'
```

## Advanced Usage

### Deploy Only Specific Components

```bash
# Update only facilitator
python scripts/build-and-push.py facilitator
python scripts/deploy-to-fargate.py facilitator

# Update Terraform without redeploying services
python scripts/deploy-to-fargate.py
```

### Manual Rollback

```bash
# List task definitions
aws ecs list-task-definitions --family-prefix karmacadabra-prod-facilitator

# Update service to previous task definition
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-facilitator \
  --task-definition karmacadabra-prod-facilitator:1
```

### Force Clean Deployment

```bash
# 1. Stop all services
for service in facilitator validator karma-hello abracadabra skill-extractor voice-extractor; do
  aws ecs update-service \
    --cluster karmacadabra-prod \
    --service karmacadabra-prod-$service \
    --desired-count 0
done

# 2. Wait for tasks to stop (30 seconds)
sleep 30

# 3. Deploy fresh
python scripts/deploy-all.py --force-rebuild

# 4. Restore desired count (Terraform will do this automatically)
```

## Cost Optimization

**Current monthly cost**: ~$79-96/month

**To reduce costs**:
1. Scale down when not in use:
   ```bash
   # Stop all services
   terraform apply -var="desired_count_per_service=0"
   ```

2. Use smaller task sizes:
   ```hcl
   # terraform/ecs-fargate/variables.tf
   task_cpu    = 256  # 0.25 vCPU (smallest)
   task_memory = 512  # 0.5 GB (smallest)
   ```

3. Reduce log retention:
   ```hcl
   # terraform/ecs-fargate/variables.tf
   log_retention_days = 3  # Instead of 7
   ```

## CI/CD Integration

**GitHub Actions example:**
```yaml
name: Deploy to Fargate

on:
  push:
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy
        run: python scripts/deploy-all.py --skip-fund
```

## Maintenance

**Weekly tasks:**
- Check wallet balances: `python scripts/fund-wallets.py`
- Review CloudWatch logs for errors
- Check ECS task health

**Monthly tasks:**
- Rotate secrets: `python scripts/rotate-system.py`
- Review costs in AWS Cost Explorer
- Update Docker images: `python scripts/build-and-push.py --force`

## Support

For issues:
1. Check CloudWatch Logs
2. Review Terraform output
3. Check ECS service events
4. Verify AWS Secrets Manager has all required secrets

**Key files:**
- `terraform/ecs-fargate/main.tf` - Infrastructure definition
- `terraform/ecs-fargate/variables.tf` - Configuration values
- `scripts/fund-wallets.py` - Wallet funding logic
- `scripts/build-and-push.py` - Docker build logic
- `scripts/deploy-to-fargate.py` - Deployment logic
