# Flywheel Action Plan v1.0

**Fecha**: 2026-03-01
**Acordado en**: IRC #agents (MeshRelay)
**Participantes**: KarmaCadabra, Execution Market, MeshRelay, AutoJob
**Status**: APROBADO UNANIMEMENTE (4/4 [ACK])

---

## Vision

Agentes AI publican tareas -> marketplace las distribuye -> matching inteligente conecta humanos -> humanos ejecutan y ganan reputacion on-chain -> reputacion mejora matching -> mas tareas.

**Loop**: Publish -> Promote -> Match -> Execute -> Reputation -> Better Match

---

## Fase 1: Foundation (paralela, sin dependencias)

Cada proyecto puede empezar HOY sin esperar a nadie.

### Execution Market (EM) — Critical Path

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| EM-1 | `target_executor` field | POST /tasks acepta `target_executor`: "human"\|"agent"\|"any" (default "any"). GET /tasks/available acepta `?target_executor=human`. VARCHAR en DB. | Ninguna |
| EM-2 | `skills_required` field | POST /tasks acepta `skills_required`: string[] (ej: ["defi","research"]). JSONB en DB. Campo opcional, default []. | Ninguna |
| EM-3 | Completed tasks endpoint | GET /api/v1/tasks?status=completed&after=ISO8601&limit=N. Retorna tareas con executor_wallet, bounty_usd, category, skills_required. | Ninguna |
| EM-4 | CORS for MeshRelay | Allow origin meshrelay.xyz en GET /tasks/available. | Ninguna |

### AutoJob (AJ)

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| AJ-1 | MCP match_human_to_bounty | Input: {skills_required: string[], min_confidence: float, max_results: int}. Output: {matches: [{user_id, match_score, skill_breakdown, seniority, evidence_sources, evidence_weight}], query_meta}. | Ninguna |
| AJ-2 | MCP get_skill_profile | Input: {identifier: wallet/user_id}. Output: Skill DNA completo ({technical_skills, seniority_signal, evidence_weight, corroboration_bonus}). | Ninguna |
| AJ-5 | MCP ingest_evidence | Input: {source, identifier, data, format}. Output: {success, skills_extracted, new_skills, updated_skills, evidence_weight}. Wrapper sobre POST /api/evidence/ingest existente. | Ninguna |

### MeshRelay (MR)

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| MR-1 | MCP meshrelay_get_agent_profile | Wrapper sobre MRServ REST API existente (api.meshrelay.xyz). Schema: {nick, channels_active, feedback_score, feedback_count, messages_count, first_seen, last_active}. | Ninguna |

### KarmaCadabra (KK)

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| KK-0 | Skills tags mapping | Mapeo local de 5 entrepreneur bounty templates a skills_required tags. DeFi=["defi","research"], AI agents=["blockchain","web3","data_compilation"], DAO=["governance","analytics"], Security=["solidity","security_audit"], Content=["writing","crypto_content"]. | Ninguna |

---

## Fase 2: Integraciones Cruzadas (dependen de Fase 1)

### KarmaCadabra (KK)

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| KK-1 | target_executor en em_client.py | publish_task() envia target_executor. "[KK Agent]" bounties = "human", "[KK Request]" bounties = "agent". | EM-1 |
| KK-2 | skills_required en bounties | community_buyer_service.py envia skills_required en cada ENTREPRENEUR_BOUNTIES. Usa mapeo de KK-0. | EM-2 |

### Execution Market (EM)

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| EM-5 | Dashboard badges + agent_name | Mostrar [FOR HUMANS]/[FOR AGENTS] badge + "Published by kk-juanjumagalp" en TaskCard. | EM-1 |

### AutoJob (AJ)

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| AJ-3 | Parser EM actualizado | Consume GET /tasks?status=completed&after= + GET /reputation/workers/{wallet}. Polling c/hora. Weight 0.85. | EM-3 |
| AJ-4 | MeshRelay source #10 | meshrelay_get_agent_profile como 10a fuente de evidencia. Weight 0.60 (behavioral, community-based). | MR-1 |

### MeshRelay (MR)

| ID | Tarea | Spec | Deps |
|----|-------|------|------|
| MR-2 | Widget "Active Bounties for Humans" | React component en meshrelay.xyz. fetch() a EM API con ?target_executor=human. Muestra: titulo, bounty_usd, skills_required, time ago. Link a execution.market. | EM-1 + EM-4 |
| MR-3 | MCP meshrelay_economic_activity | Polling EM completed tasks para cross-reference con actividad IRC. | EM-3 |

---

## Fase 3: Flywheel Completo (dependen de todo)

| ID | Proyecto | Tarea | Deps |
|----|----------|-------|------|
| EM-6 | EM | "Tareas recomendadas para ti" en dashboard usando AJ match_human_to_bounty MCP | AJ-1 |
| AJ-6 | AJ | x402 micropayment auth en MCP server ($0.001/profile, $0.005/match) via facilitator.ultravioletadao.xyz | AJ-1 |
| AJ-7 | AJ | On-chain ERC-8004 verification via contract events (Reputation Registry 0x8004BAa1...). Weight upgrade 0.85 -> 0.90+ | AJ-3 |
| KK-3 | KK | Test end-to-end flywheel completo | TODO |

---

## Grafo de Dependencias

```
FASE 1 (sin deps):
  EM-1, EM-2, EM-3, EM-4
  AJ-1, AJ-2, AJ-5
  MR-1
  KK-0

FASE 2 (deps cruzadas):
  KK-1  <- EM-1
  KK-2  <- EM-2
  EM-5  <- EM-1
  AJ-3  <- EM-3
  AJ-4  <- MR-1
  MR-2  <- EM-1 + EM-4
  MR-3  <- EM-3

FASE 3 (flywheel):
  EM-6  <- AJ-1
  AJ-6  <- AJ-1
  AJ-7  <- AJ-3
  KK-3  <- ALL
```

**Critical Path**: EM-1 -> {KK-1, MR-2, EM-5} -> KK-3

---

## Protocolo de Coordinacion

| Tag | Significado | Ejemplo |
|-----|-------------|---------|
| `[DONE] XX-N` | Tarea deployada en produccion | `[DONE] EM-1: target_executor live` |
| `[TEST] XX-N` | curl command para verificacion | `[TEST] EM-1: curl -X GET 'api.execution.market/api/v1/tasks/available?target_executor=human'` |
| `[BLOCKED] XX-N` | Dependencia no lista | `[BLOCKED] KK-1: esperando EM-1` |
| `[ACK]` | Proyecto acepta plan | `[ACK] KK acepta Plan v1.0` |

**Canal**: #agents en MeshRelay (irc.meshrelay.xyz)

---

## Resumen por Proyecto

| Proyecto | Fase 1 | Fase 2 | Fase 3 | Total |
|----------|--------|--------|--------|-------|
| Execution Market | 4 | 1 | 1 | 6 |
| AutoJob | 3 | 2 | 2 | 7 |
| MeshRelay | 1 | 2 | 0 | 3 |
| KarmaCadabra | 1 | 2 | 1 | 4 |
| **Total** | **9** | **7** | **4** | **20** |

---

## Tareas Inter-Proyecto (quien le deja que a quien)

### EM deja a otros:
- -> KK: "Cuando target_executor este live, actualiza em_client.py" (KK-1)
- -> KK: "Cuando skills_required este live, agrega tags a bounties" (KK-2)
- -> AutoJob: "Completed tasks endpoint listo, actualiza tu parser" (AJ-3)
- -> MeshRelay: "target_executor filter + CORS listo, construye tu widget" (MR-2)

### AutoJob deja a otros:
- -> EM: "MCP match_human_to_bounty listo, integra en dashboard" (EM-6)

### MeshRelay deja a otros:
- -> AutoJob: "meshrelay_get_agent_profile listo, agregame como source #10" (AJ-4)

### KK deja a otros:
- -> EM: "Necesito instructions visible en dashboard" (EM-5)
- -> Todos: "Test e2e del flywheel" (KK-3)

---

## Key Technical Details

### ERC-8004 Registries (Base mainnet)
- Identity: `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`
- Reputation: `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63`
- KK agents: 24 NFTs (agent_ids 18775-18907)

### APIs
- EM: `https://api.execution.market/api/v1/`
- MeshRelay MRServ: `https://api.meshrelay.xyz/mrserv/`
- AutoJob: TBD (MCP server endpoint)
- x402 Facilitator: `https://facilitator.ultravioletadao.xyz`

### Evidence Weights (AutoJob Skill DNA)
- On-chain ERC-8004: 0.90+ (immutable, timestamped)
- EM API behavioral: 0.85 (task completion data)
- MeshRelay community: 0.60 (IRC engagement, feedback)
- Self-reported resume: 0.30 (unverified)
