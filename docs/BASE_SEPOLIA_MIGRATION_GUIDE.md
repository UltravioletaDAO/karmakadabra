# Migration Guide: Avalanche Fuji → Base Sepolia

**Date:** 2025-11-04
**Status:** Configuration Complete - Deployment Pending

---

## Overview

This document guides the migration of all Karmacadabra agents from Avalanche Fuji to Base Sepolia as the primary network.

---

## What Changed

### 1. Default Network ✅ COMPLETE
- `shared/contracts_config.py`: DEFAULT_NETWORK changed to "base-sepolia"
- All agents now use Base Sepolia by default

### 2. Environment Variables ✅ COMPLETE
**Root `.env`:**
```bash
NETWORK=base-sepolia
CHAIN_ID=84532
RPC_URL=https://sepolia.base.org
GLUE_TOKEN_ADDRESS=0xfEe5CC33479E748f40F5F299Ff6494b23F88C425
IDENTITY_REGISTRY=0x8a20f665c02a33562a0462a0908a64716Ed7463d
REPUTATION_REGISTRY=0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F
VALIDATION_REGISTRY=0x3C545DBeD1F587293fA929385442A459c2d316c4
```

**All 5 Agent `.env` files updated:**
- agents/validator/.env
- agents/karma-hello/.env
- agents/abracadabra/.env
- agents/skill-extractor/.env
- agents/voice-extractor/.env

### 3. Docker Compose ✅ COMPLETE
`docker-compose.yml` updated with Base Sepolia as primary network.

---

## Base Sepolia Infrastructure

### Contracts (All Verified on Sourcify)

| Contract | Address |
|----------|---------|
| GLUE Token | 0xfEe5CC33479E748f40F5F299Ff6494b23F88C425 |
| Identity Registry | 0x8a20f665c02a33562a0462a0908a64716Ed7463d |
| Reputation Registry | 0x06767A3ab4680b73eb19CeF2160b7eEaD9e4D04F |
| Validation Registry | 0x3C545DBeD1F587293fA929385442A459c2d316c4 |

### Agent Balances

| Agent | GLUE Balance | Gas Balance | Registry ID |
|-------|--------------|-------------|-------------|
| Validator | 110,000 | 0.005 ETH | #1 |
| Karma-Hello | 55,000 | 0.005 ETH | #2 |
| Abracadabra | 55,000 | 0.005 ETH | #3 |
| Skill-Extractor | 55,000 | 0.005 ETH | #4 |
| Voice-Extractor | 55,000 | 0.007 ETH | #5 |

**All agents funded and ready for operations.**

---

## Deployment Steps

### Option A: Local Testing with Docker Compose

**1. Rebuild containers:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**2. Verify agents started:**
```bash
docker-compose ps
docker-compose logs -f validator
```

**3. Test health endpoints:**
```bash
curl http://localhost:9001/health  # Validator
curl http://localhost:9002/health  # Karma-Hello
curl http://localhost:9003/health  # Abracadabra
curl http://localhost:9004/health  # Skill-Extractor
curl http://localhost:9005/health  # Voice-Extractor
```

**4. Test agent discovery:**
```bash
curl http://localhost:9002/.well-known/agent-card
```

**Expected output:**
```json
{
  "name": "Karma-Hello Agent",
  "description": "Chat logs seller",
  "wallet_address": "0x2C3e071df446B25B821F59425152838ae4931E75",
  "agent_card_url": "http://localhost:9002/.well-known/agent-card",
  "network": "base-sepolia",
  "chain_id": 84532
}
```

---

### Option B: Deploy to AWS ECS Fargate

**Prerequisites:**
- AWS CLI configured
- ECR repositories exist
- ECS cluster `karmacadabra-prod` exists

**1. Update AWS Secrets Manager (if needed):**

Agent private keys are stored in AWS Secrets Manager and don't need updates (same wallets on both networks).

**2. Build and Push Docker Images:**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com

# Build and push each agent
for agent in validator karma-hello abracadabra skill-extractor voice-extractor; do
  echo "[*] Building $agent..."

  # Build
  docker build --platform linux/amd64 \
    -t karmacadabra-prod-$agent:latest \
    -f Dockerfile.agent \
    --build-arg AGENT_DIR=agents/$agent .

  # Tag
  docker tag karmacadabra-prod-$agent:latest \
    518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-$agent:latest

  # Push
  docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra-prod-$agent:latest

  echo "[+] $agent pushed"
done
```

**3. Update ECS Task Definitions:**

For each agent, update the task definition to include Base Sepolia environment variables:

```bash
# Get current task definition
aws ecs describe-task-definition \
  --task-definition karmacadabra-prod-validator \
  --region us-east-1 > task-def-validator.json

# Edit task-def-validator.json to add/update environment variables:
# - NETWORK=base-sepolia
# - CHAIN_ID=84532
# - RPC_URL=https://sepolia.base.org
# - GLUE_TOKEN_ADDRESS=0xfEe5CC33479E748f40F5F299Ff6494b23F88C425
# - IDENTITY_REGISTRY=0x8a20f665c02a33562a0462a0908a64716Ed7463d
# etc.

# Register new task definition revision
aws ecs register-task-definition \
  --cli-input-json file://task-def-validator.json \
  --region us-east-1
```

**4. Force New Deployment:**

```bash
# Update each service with new task definition
for service in validator karma-hello abracadabra skill-extractor voice-extractor; do
  echo "[*] Deploying $service..."

  aws ecs update-service \
    --cluster karmacadabra-prod \
    --service karmacadabra-prod-$service \
    --force-new-deployment \
    --region us-east-1

  echo "[+] $service deployment triggered"
done
```

**5. Monitor Deployment:**

```bash
# Check service status
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services karmacadabra-prod-validator \
  --region us-east-1 \
  --query 'services[0].deployments'

# Check task logs
aws logs tail /ecs/karmacadabra-prod-validator --follow --region us-east-1
```

**6. Verify Production Endpoints:**

```bash
curl https://validator.karmacadabra.ultravioletadao.xyz/health
curl https://karma-hello.karmacadabra.ultravioletadao.xyz/health
curl https://abracadabra.karmacadabra.ultravioletadao.xyz/health
curl https://skill-extractor.karmacadabra.ultravioletadao.xyz/health
curl https://voice-extractor.karmacadabra.ultravioletadao.xyz/health
```

---

## Rollback Procedure

If Base Sepolia deployment fails, you can quickly revert to Fuji:

**1. Update Environment Variables:**
```bash
# In each agent's .env file:
NETWORK=fuji
CHAIN_ID=43113
RPC_URL=https://avalanche-fuji-c-chain-rpc.publicnode.com
GLUE_TOKEN_ADDRESS=0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
IDENTITY_REGISTRY=0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
```

**2. Rebuild and Redeploy:**
```bash
docker-compose down
docker-compose up --build -d
```

**Or for ECS:**
```bash
# Revert task definitions to previous revision
aws ecs update-service \
  --cluster karmacadabra-prod \
  --service karmacadabra-prod-validator \
  --task-definition karmacadabra-prod-validator:PREVIOUS_REVISION \
  --force-new-deployment \
  --region us-east-1
```

---

## Testing Checklist

After deployment, verify:

- [ ] All agents respond to `/health`
- [ ] Agent cards accessible at `/.well-known/agent-card`
- [ ] Network shows as "base-sepolia" in agent cards
- [ ] Chain ID is 84532
- [ ] GLUE balances are correct (55k or 110k)
- [ ] Agent registry IDs match (1-5)
- [ ] Purchase flow works (buyer → seller)
- [ ] Facilitator settles transactions on Base Sepolia
- [ ] Block explorer shows transactions

---

## Post-Migration Tasks

1. **Update Documentation:**
   - ✅ README.md (mark Base Sepolia as primary)
   - ✅ MASTER_PLAN.md (update network status)
   - [ ] API documentation (if any)

2. **Monitor Production:**
   - Check CloudWatch logs for errors
   - Monitor GLUE balances
   - Track transaction success rate

3. **Notify Community:**
   - Update Discord/Telegram announcements
   - Update website (if applicable)

---

## Why Base Sepolia?

**Benefits over Avalanche Fuji:**
- ✅ Ethereum L2 ecosystem (more developer tooling)
- ✅ Lower gas costs (optimistic rollup)
- ✅ Better RPC reliability
- ✅ Closer to Base Mainnet migration path

**Trade-offs:**
- ⚠️ Slightly slower block times (2s vs 2s - same)
- ⚠️ Less mature testnet infrastructure
- ⚠️ Requires new faucet (https://www.alchemy.com/faucets/base-sepolia)

---

## Support

**Block Explorer:** https://sepolia.basescan.org
**RPC Endpoint:** https://sepolia.base.org
**Chain ID:** 84532
**Native Token:** ETH (testnet)
**Faucet:** https://www.alchemy.com/faucets/base-sepolia

**Karmacadabra Contracts:**
- See `docs/BASE_SEPOLIA_INTEGRATION_COMPLETE.md` for full details
- See `karmacadabra-base-sepolia/BASE_SEPOLIA_DEPLOYMENT_ADDRESSES.md` for deployment history

---

**Migration Status:** Configuration ✅ Complete | Deployment ⏳ Pending
