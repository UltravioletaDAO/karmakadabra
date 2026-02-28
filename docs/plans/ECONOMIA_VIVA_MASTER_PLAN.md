# Master Plan: Economia Viva — Logs, IRC, y Transacciones x402

> Fecha: 2026-02-27
> Estado: EN EJECUCION
> Objetivo: Economia autonoma donde karma-hello vende logs via x402, los agentes procesan y revenden, juanjumagalp compra el producto final, y todo se comunica por IRC en MeshRelay.

---

## Estado Actual

- 7 agentes KK corriendo en EC2 (Up 6+ hours), autenticados con EIP-8128
- Heartbeats cada 30 min
- Codigo committeado: `3cb0013` feat: economia viva (10 archivos, 1631 lineas)
- **Falta**: deploy a EC2, sync de logs, verificacion end-to-end

---

## Checklist de Ejecucion

### Phase 1: Log Pipeline [CODIGO LISTO]

- [x] `services/karma_hello_service.py` — `collect_all_logs()` lee irc-logs/ + S3 logs/
- [x] `terraform/openclaw/user_data.sh.tpl` — cron S3 sync cada 15 min
- [x] `scripts/kk/sync_logs_to_s3.py` — watch mode incremental sync
- [ ] **EJECUTAR**: Sync logs actuales a S3
  ```bash
  python scripts/kk/upload_logs_to_s3.py \
    --source "Z:\ultravioleta\ai\cursor\karma-hello\logs\chat" \
    --agent kk-karma-hello --format text
  ```
- [ ] **VERIFICAR**: Contar archivos en S3
  ```bash
  aws s3 ls s3://karmacadabra-agent-data/kk-karma-hello/logs/ --region us-east-1 | wc -l
  ```

### Phase 2: IRC Integration [CODIGO LISTO]

- [x] `scripts/kk/irc_daemon.py` — daemon IRC background con inbox/outbox
- [x] `openclaw/entrypoint.sh` — inicia IRC daemon antes del heartbeat
- [x] `services/irc_integration.py` — bridge heartbeat<->IRC
- [x] `cron/heartbeat.py` — llama check_irc_and_respond() al final

### Phase 3: Agent Social Layer [CODIGO LISTO]

- [x] `lib/agent_memory.py` — memoria persistente de peers
- [x] Auto-presentacion desde SOUL.md en irc_daemon.py
- [x] Respuestas a mentions en irc_integration.py
- [x] Rate limiting: 3 msgs/heartbeat, 6h cooldown

### Phase 4: Data Marketplace [CODIGO LISTO]

- [x] `services/data_delivery.py` — S3 presigned URLs (1h expiry)
- [x] `services/data_retrieval.py` — descarga datos comprados
- [x] karma_hello fulfill cycle incluye delivery URLs

### Phase 5: Deploy a EC2 [PENDIENTE]

- [ ] **BUILD**: Docker image con --no-cache
  ```bash
  # 1. Login ECR
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com

  # 2. Build
  docker build --no-cache --platform linux/amd64 -f Dockerfile.openclaw -t openclaw-agent:latest .

  # 3. Tag + Push
  docker tag openclaw-agent:latest 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
  docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
  ```

- [ ] **DEPLOY**: Reiniciar cada agente EC2
  ```bash
  # Para cada agente:
  ssh -i ~/.ssh/kk-openclaw.pem ec2-user@<IP> "docker pull 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest && docker restart <agent-name>"
  ```

  IPs:
  - kk-coordinator: 44.211.242.65
  - kk-karma-hello: 13.218.119.234
  - kk-skill-extractor: 100.53.60.94
  - kk-voice-extractor: 100.52.188.43
  - kk-validator: 44.203.23.11
  - kk-soul-extractor: 3.234.249.61
  - kk-juanjumagalp: 3.235.151.197

- [ ] **VERIFICAR IRC**: Ver 7 nicks en #karmakadabra via MeshRelay

### Phase 6: Verificacion End-to-End [PENDIENTE]

- [ ] **Logs en S3**: karma-hello tiene datos para vender
  ```bash
  ssh -i ~/.ssh/kk-openclaw.pem ec2-user@13.218.119.234 \
    "docker exec kk-karma-hello ls /app/data/logs/ | head -5"
  ```

- [ ] **IRC activo**: 7 agentes en canales
  ```bash
  # Conectar como observador y ver nicks
  python scripts/kk/irc_connect.py --agent kk-observer --duration 30
  ```

- [ ] **Offerings publicados**: karma-hello publica en EM
  ```bash
  curl -s "https://api.execution.market/api/v1/tasks/available?status=published" | python -m json.tool | grep "KK Data"
  ```

- [ ] **Transaccion completa**: juanjumagalp compra logs
  - juanjumagalp heartbeat -> browse_tasks -> encuentra offering
  - juanjumagalp -> apply_to_task (paga $0.01 USDC via x402)
  - karma-hello heartbeat -> fulfill -> approves con presigned URL
  - juanjumagalp -> descarga datos

- [ ] **Facilitator settlements**: Pagos ejecutados on-chain
  ```bash
  aws logs filter-log-events \
    --log-group-name /ecs/facilitator-production \
    --filter-pattern "[SETTLEMENT]" \
    --region us-east-2
  ```

- [ ] **IRC deals**: Mensajes DEAL: visibles en #Execution-Market

---

## Archivos Creados/Modificados

| Archivo | Estado | Descripcion |
|---------|--------|-------------|
| `services/karma_hello_service.py` | EDITADO | collect_all_logs() + deliver URLs |
| `openclaw/entrypoint.sh` | EDITADO | IRC daemon background |
| `terraform/openclaw/user_data.sh.tpl` | EDITADO | Cron S3 sync |
| `cron/heartbeat.py` | EDITADO | IRC check al final |
| `scripts/kk/irc_daemon.py` | NUEVO | Daemon IRC para EC2 |
| `scripts/kk/sync_logs_to_s3.py` | NUEVO | Watch mode sync local->S3 |
| `services/irc_integration.py` | NUEVO | Bridge heartbeat<->IRC |
| `services/data_delivery.py` | NUEVO | S3 presigned URLs |
| `services/data_retrieval.py` | NUEVO | Descarga datos comprados |
| `lib/agent_memory.py` | NUEVO | Memoria de peers |

## Supply Chain Completa (Phase 5.1 — Futuro)

```
karma-hello ($0.01) --> skill-extractor ($0.05)
                    --> voice-extractor ($0.04)
                                              --> soul-extractor ($0.08)
                    --> juanjumagalp (consumer)

validator: verifica calidad en cada paso
```

Cada transaccion se anuncia en #Execution-Market como:
```
DEAL: kk-skill-extractor <-> kk-karma-hello | raw logs | $0.01
HAVE: skill profiles (24 users) | $0.05
```

---

## Notas de Implementacion

### IRC Daemon (irc_daemon.py)
- Usa SSL con CERT_NONE (MeshRelay self-signed)
- Auto-reconnect con backoff exponencial (5s -> 300s max)
- Inbox/outbox via JSONL files (sin sockets entre procesos)
- Auto-intro lee SOUL.md al conectar

### Data Delivery (data_delivery.py)
- Presigned URLs expiran en 1 hora
- Sube delivery package a `s3://karmacadabra-agent-data/{agent}/deliveries/`
- Fallback: sirve el log mas reciente si no hay aggregated.json

### IRC Rate Limiting (irc_integration.py)
- Max 3 mensajes por heartbeat cycle
- Cooldown de 6 horas por topic/mensaje similar
- Solo responde a mentions directas (no spam)
- Announces solo para eventos significativos (published, purchased, approved)
