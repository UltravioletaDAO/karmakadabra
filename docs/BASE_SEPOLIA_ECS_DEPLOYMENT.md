# Base Sepolia ECS Deployment Runbook

**Date:** 2025-11-04
**Purpose:** Deploy Karmacadabra agents to AWS ECS with Base Sepolia as primary network

---

## Pre-Deployment Checklist

Before running any commands, verify:

- [ ] All configuration changes committed and pushed (commit: f0a76d9, 069ccf6)
- [ ] Base Sepolia contracts deployed and verified on Sourcify
- [ ] All 5 agents funded with GLUE (55k-110k) and gas (0.005-0.007 ETH)
- [ ] All agents registered on Base Sepolia Identity Registry (IDs #1-#5)
- [ ] Facilitator live at https://facilitator.ultravioletadao.xyz
- [ ] AWS CLI configured with correct credentials
- [ ] ECR repositories exist for all 5 agents

**Verify with:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check ECR repositories
aws ecr describe-repositories --region us-east-1 --query 'repositories[].repositoryName' | grep karmacadabra-prod
```

---

## Step 1: Login to AWS ECR

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com
```

**Expected:** `Login Succeeded`

---

## Step 2: Build Docker Images

**CRITICAL:** Use `--no-cache` to ensure Base Sepolia configuration is baked into images.

```bash
# Build all agent images (this will take 15-20 minutes)
$agents = @("validator", "karma-hello", "abracadabra", "skill-extractor", "voice-extractor")

foreach ($agent in $agents) {
    Write-Host "[*] Building $agent..."

    docker build --platform linux/amd64 --no-cache `
        -t "karmacadabra-prod-$agent:latest" `
        -f Dockerfile.agent `
        --build-arg AGENT_DIR="agents/$agent" .

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[+] $agent build successful"
    } else {
        Write-Host "[!] $agent build FAILED"
        exit 1
    }
}
```

**Expected:** Each agent builds successfully without errors.

**If build fails:** Check Docker Desktop is running and has sufficient resources (8GB RAM minimum).

---

## Step 3: Tag and Push Images to ECR

```bash
$agents = @("validator", "karma-hello", "abracadabra", "skill-extractor", "voice-extractor")

foreach ($agent in $agents) {
    Write-Host "[*] Pushing $agent to ECR..."

    # Tag
    docker tag "karmacadabra-prod-$agent:latest" `
        "518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-$agent:latest"

    # Push
    docker push "518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-$agent:latest"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[+] $agent pushed successfully"
    } else {
        Write-Host "[!] $agent push FAILED"
        exit 1
    }
}
```

**Expected:** Each image pushes to ECR successfully.

---

## Step 4: Verify Image Digests

Before deploying, verify the latest images in ECR have new digests (not cached):

```bash
$agents = @("validator", "karma-hello", "abracadabra", "skill-extractor", "voice-extractor")

foreach ($agent in $agents) {
    Write-Host "`n[$agent]"

    $digest = aws ecr describe-images `
        --repository-name "karmacadabra-prod-$agent" `
        --region us-east-1 `
        --query 'sort_by(imageDetails,&imagePushedAt)[-1].[imageDigest,imagePushedAt]' `
        --output text

    Write-Host $digest
}
```

**Expected:** New timestamps (within last few minutes) for all images.

---

## Step 5: Force New ECS Deployment

**IMPORTANT:** This will cause 2-3 minutes of downtime per service as new tasks spin up.

```bash
$services = @("validator", "karma-hello", "abracadabra", "skill-extractor", "voice-extractor")

foreach ($service in $services) {
    Write-Host "`n[*] Deploying $service..."

    aws ecs update-service `
        --cluster karmacadabra-prod `
        --service "karmacadabra-prod-$service" `
        --force-new-deployment `
        --region us-east-1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[+] $service deployment triggered"
    } else {
        Write-Host "[!] $service deployment FAILED"
    }
}
```

**Expected:** All 5 services start new deployments.

---

## Step 6: Monitor Deployment Progress

```bash
# Watch deployment status (run in separate terminal)
while ($true) {
    Clear-Host
    Write-Host "=== ECS Deployment Status ===" -ForegroundColor Cyan
    Write-Host "Time: $(Get-Date -Format 'HH:mm:ss')`n"

    $services = @("validator", "karma-hello", "abracadabra", "skill-extractor", "voice-extractor")

    foreach ($service in $services) {
        $status = aws ecs describe-services `
            --cluster karmacadabra-prod `
            --services "karmacadabra-prod-$service" `
            --region us-east-1 `
            --query 'services[0].[deployments[0].status,deployments[0].runningCount,deployments[0].desiredCount]' `
            --output text

        Write-Host "$service : $status"
    }

    Start-Sleep -Seconds 10
}
```

**Expected:** All services show `PRIMARY 1 1` (1 running task, 1 desired).

**Stop monitoring:** Press `Ctrl+C` once all services are stable.

---

## Step 7: Verify Production Endpoints

Once all services show `PRIMARY 1 1`, verify Base Sepolia configuration:

```bash
# Test health endpoints
$agents = @(
    @{Name="validator"; Port=9001},
    @{Name="karma-hello"; Port=9002},
    @{Name="abracadabra"; Port=9003},
    @{Name="skill-extractor"; Port=9004},
    @{Name="voice-extractor"; Port=9005}
)

foreach ($agent in $agents) {
    $url = "https://$($agent.Name).karmacadabra.ultravioletadao.xyz/health"
    Write-Host "`n[$($agent.Name)] Testing $url"

    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing
        Write-Host "[+] Status: $($response.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "[!] FAILED: $_" -ForegroundColor Red
    }
}
```

**Expected:** All agents return `200 OK`.

---

## Step 8: Verify Base Sepolia Configuration

Check that agents are using Base Sepolia (not Fuji):

```bash
# Test karma-hello agent card
$response = Invoke-RestMethod -Uri "https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card"

Write-Host "`nAgent Card Verification:"
Write-Host "Network: $($response.network)"
Write-Host "Chain ID: $($response.chain_id)"
Write-Host "Address: $($response.wallet_address)"
```

**Expected Output:**
```
Network: base-sepolia
Chain ID: 84532
Address: 0x2C3e071df446B25B821F59425152838ae4931E75
```

**If network shows "fuji":** The deployment didn't pick up the new configuration. Check ECS task definition environment variables.

---

## Step 9: Check CloudWatch Logs

Monitor for errors during startup:

```bash
# View recent logs for each agent
$services = @("validator", "karma-hello", "abracadabra", "skill-extractor", "voice-extractor")

foreach ($service in $services) {
    Write-Host "`n=== $service logs ===" -ForegroundColor Cyan

    aws logs tail "/ecs/karmacadabra-prod-$service" `
        --since 5m `
        --region us-east-1 `
        | Select-String -Pattern "ERROR|WARNING|Base Sepolia|84532" -Context 1
}
```

**Expected:** No ERROR messages, logs show "Base Sepolia" or "84532" references.

---

## Step 10: Test Payment Flow (Optional)

If you want to verify end-to-end Base Sepolia payments:

```bash
# Test a simple purchase from karma-hello
cd scripts

python test_glue_payment_simple.py `
    --network base-sepolia `
    --seller https://karma-hello.karmacadabra.ultravioletadao.xyz `
    --amount 0.01
```

**Expected:** Payment succeeds, transaction appears on Base Sepolia block explorer.

---

## Rollback Procedure

If deployment fails or agents show errors:

### Option A: Rollback to Previous Task Definition

```bash
# Find previous working revision
aws ecs describe-services `
    --cluster karmacadabra-prod `
    --services karmacadabra-prod-validator `
    --region us-east-1 `
    --query 'services[0].taskDefinition'

# Update to previous revision (replace :XX with previous number)
aws ecs update-service `
    --cluster karmacadabra-prod `
    --service karmacadabra-prod-validator `
    --task-definition karmacadabra-prod-validator:XX `
    --force-new-deployment `
    --region us-east-1

# Repeat for other services
```

### Option B: Revert Git Changes and Redeploy

```bash
# Revert to Fuji configuration
git revert f0a76d9 069ccf6

# Rebuild and redeploy with Fuji config
# Follow Steps 2-7 again
```

---

## Post-Deployment Tasks

After successful deployment:

- [ ] Update MASTER_PLAN.md to mark Base Sepolia migration complete
- [ ] Notify team/community about network switch
- [ ] Monitor CloudWatch for 24 hours for any issues
- [ ] Test all agent interactions (buyer purchases from sellers)
- [ ] Check GLUE balances don't drain unexpectedly
- [ ] Verify on-chain transactions on BaseScan

---

## Troubleshooting

**Problem:** Agent health endpoint returns 503
- **Solution:** Check CloudWatch logs for startup errors
- **Common cause:** Missing AWS Secrets Manager permissions

**Problem:** Agent card shows "fuji" network
- **Solution:** Task definition didn't pick up new .env files. Rebuild images with `--no-cache`

**Problem:** Payment flow fails with "unknown network"
- **Solution:** Facilitator doesn't recognize Base Sepolia. Check facilitator logs

**Problem:** Docker build fails on Windows
- **Solution:** Increase Docker Desktop resources to 8GB RAM, 4 CPU cores

---

## Success Criteria

Deployment is successful when:

✅ All 5 services show `PRIMARY 1 1` in ECS
✅ All health endpoints return 200 OK
✅ Agent cards show `network: base-sepolia` and `chain_id: 84532`
✅ No ERROR messages in CloudWatch logs
✅ Test payment completes successfully on Base Sepolia

---

**Estimated Total Time:** 30-45 minutes (mostly Docker builds)

**Deployment Windows:** Can be done anytime (agents have minimal users)

**Rollback Time:** 10 minutes if needed
