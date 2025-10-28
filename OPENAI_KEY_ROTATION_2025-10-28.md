# OpenAI API Key Rotation - October 28, 2025

## Summary

Successfully rotated all 6 OpenAI API keys and redeployed ECS Fargate services.

## What Was Done

### 1. Keys Rotated ✅
Updated OpenAI API keys for all 6 agents in AWS Secrets Manager:
- ✅ karma-hello-agent
- ✅ abracadabra-agent
- ✅ validator-agent
- ✅ voice-extractor-agent
- ✅ skill-extractor-agent
- ✅ client-agent

### 2. AWS Secrets Manager Updated ✅
```bash
python3 scripts/rotate_openai_keys.py
```
Script successfully read keys from `.unused/keys.txt` and updated the `karmacadabra` secret in AWS Secrets Manager (us-east-1).

### 3. ECS Services Redeployed ✅
Force-deployed all 6 services to pick up new secrets:
```bash
aws ecs update-service --cluster karmacadabra-prod --force-new-deployment
```

**Services updated:**
- karmacadabra-prod-facilitator (1/1 running)
- karmacadabra-prod-validator (1/1 running)
- karmacadabra-prod-abracadabra (1/1 running)
- karmacadabra-prod-voice-extractor (1/1 running)
- karmacadabra-prod-skill-extractor (1/1 running)
- karmacadabra-prod-karma-hello (1/1 running)

All services are now running with the new OpenAI API keys.

## Next Steps

### ⚠️ CRITICAL - Revoke Old Keys
Go to https://platform.openai.com/api-keys and revoke the 6 old keys that were exposed:
1. karma-hello-agent (sk-proj-Uwi...)
2. abracadabra-agent (sk-proj-KD3...)
3. validator-agent (sk-proj-qk_...)
4. voice-extractor-agent (sk-proj-8x7...)
5. skill-extractor-agent (sk-proj-E_h...)
6. client-agent (sk-proj-Skk...)

### Verification
Monitor the services to ensure they're functioning correctly with the new keys:
```bash
# Check service health
aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-validator --region us-east-1

# Check logs for errors
aws logs tail /ecs/karmacadabra-prod-validator --since 10m --region us-east-1
```

### Test Agent Endpoints
```bash
curl https://validator.karmacadabra.ultravioletadao.xyz/health
curl https://karma-hello.karmacadabra.ultravioletadao.xyz/health
curl https://abracadabra.karmacadabra.ultravioletadao.xyz/health
```

## Files Modified

### New Files
- `scripts/rotate_openai_keys.py` - Rotation script for future key rotations

### Read-Only Files
- `.unused/keys.txt` - Source of new keys (NOT committed to git)

## Security Notes

- ✅ New keys stored in AWS Secrets Manager (encrypted at rest)
- ✅ Old keys will be revoked on OpenAI platform
- ✅ Keys file in `.unused/` directory (gitignored)
- ✅ No keys committed to git repository
- ✅ All services restarted to pick up new keys

## Rotation Time
- **Started:** 2025-10-28 17:18 UTC
- **AWS Updated:** 2025-10-28 17:19 UTC
- **Deployments Completed:** 2025-10-28 17:23 UTC
- **Total Duration:** ~5 minutes

## Future Rotations

To rotate keys again in the future:
1. Generate new keys on OpenAI platform
2. Save to `.unused/keys.txt` in the same format
3. Run: `python3 scripts/rotate_openai_keys.py`
4. Force redeploy: `aws ecs update-service --cluster karmacadabra-prod --force-new-deployment`
5. Revoke old keys on OpenAI platform
