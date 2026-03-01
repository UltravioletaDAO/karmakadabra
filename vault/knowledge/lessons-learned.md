---
title: Lessons Learned
tags:
  - knowledge
  - lessons
---

## Deployment
- Docker volume mount `-v /data/$NAME:/app/data` HIDES built-in `/app/data/*` -- put config at `/app/config/`
- AWS Secrets Manager stores JSON -- must extract raw key from JSON wrapper
- SSH nested quoting corrupts private keys -- use SCP + local script execution
- Entrypoint uses `KK_AGENT_NAME` not `AGENT_NAME`
- AL2023 AMI requires EBS >= 30GB
- Windows CRLF in entrypoint.sh needs `sed -i 's/\r$//'` in Dockerfile

## EM API
- `evidence_required` is MANDATORY (was missing, caused 422)
- Minimum bounty: $0.01
- 409 Conflict: agent already applied -- skip and try next
- 429 Too Many Requests: throttle with asyncio.sleep(0.5-1.0)
- Evidence format: dict keyed by type, NOT `{type: "json_response"}`

## Escrow Flow
- BUYER publishes task, SELLER applies (not the other way around)
- `[KK Request]` prefix for buyer bounty tasks
- Escrow: 87% seller / 13% fee
