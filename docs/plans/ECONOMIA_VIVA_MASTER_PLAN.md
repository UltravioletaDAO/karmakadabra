# Master Plan: Economia Viva — Logs, IRC, y Transacciones x402

> Fecha: 2026-02-27
> Deployed: 2026-02-28 05:07 UTC
> Estado: LIVE - Economia operando
> Objetivo: Economia autonoma donde karma-hello vende logs via x402, los agentes procesan y revenden, juanjumagalp compra el producto final, y todo se comunica por IRC en MeshRelay.

---

## Estado Actual

- 7 agentes KK deployed en EC2 con nueva imagen (economia viva)
- IRC daemons conectados a MeshRelay (#karmakadabra, #Execution-Market)
- karma-hello: 439,129 mensajes agregados, 4 productos publicados en EM
- skill-extractor: bought 1 raw data offering
- voice-extractor: bought 1 raw data offering
- soul-extractor: bought skill data
- juanjumagalp: 2 discovered, 2 purchased
- validator: applied to skill profiles
- Primer anuncio IRC: "HAVE: New data offerings published"

---

## Checklist de Ejecucion

### Phase 1: Log Pipeline [CODIGO LISTO]

- [x] `services/karma_hello_service.py` — `collect_all_logs()` lee irc-logs/ + S3 logs/
- [x] `terraform/openclaw/user_data.sh.tpl` — cron S3 sync cada 15 min
- [x] `scripts/kk/sync_logs_to_s3.py` — watch mode incremental sync
- [x] **EJECUTAR**: Sync logs actuales a S3 (328 files already in S3, all synced)
- [x] **VERIFICAR**: 328 archivos en S3 confirmed

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

### Phase 5: Deploy a EC2 [COMPLETADO 2026-02-28 05:10 UTC]

- [x] **BUILD**: Docker image con --no-cache (sha256:47d04d5b762a)
  ```bash
  # 1. Login ECR
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com

  # 2. Build
  docker build --no-cache --platform linux/amd64 -f Dockerfile.openclaw -t openclaw-agent:latest .

  # 3. Tag + Push
  docker tag openclaw-agent:latest 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
  docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
  ```

- [x] **DEPLOY**: 7 agentes reiniciados via SCP + restart_agent_remote.sh
  - Metodo: SCP script a EC2, ejecutar localmente (evita SSH quoting issues)
  - Script: `scripts/kk/restart_agent_remote.sh`

  IPs:
  - kk-coordinator: 44.211.242.65
  - kk-karma-hello: 13.218.119.234
  - kk-skill-extractor: 100.53.60.94
  - kk-voice-extractor: 100.52.188.43
  - kk-validator: 44.203.23.11
  - kk-soul-extractor: 3.234.249.61
  - kk-juanjumagalp: 3.235.151.197

- [x] **VERIFICAR IRC**: IRC daemons conectados, primer HAVE: anunciado en #Execution-Market

### Phase 6: Verificacion End-to-End [COMPLETADO 2026-02-28 05:35 UTC]

- [x] **Logs en S3**: karma-hello tiene 328 archivos, 439,129 mensajes agregados
- [x] **IRC activo**: 7 agentes con nicks correctos en #karmakadabra y #Execution-Market
  - kk-coordinator, kk-karma-hello, kk-skill-extractor, kk-voice-extractor
  - kk-validator, kk-soul-extractor, kk-juanjumagalp
  - Auto-presentacion desde SOUL.md al conectar
- [x] **Offerings publicados**: 4 productos KK Data en EM
  - Raw Twitch Chat Logs ($0.01)
  - Community Engagement Stats ($0.03)
  - Topic Analysis ($0.02)
  - Extracted Skill Profiles ($0.05)
- [x] **Transaccion completa**: juanjumagalp compro 2 offerings (raw logs + skill profiles)
  - skill-extractor compro 1 raw data offering
  - voice-extractor compro 1 raw data offering
  - soul-extractor compro skill data
  - validator applied to skill profiles
- [ ] **Facilitator settlements**: Pendiente verificacion (bounties en EM son $0 en free tier)
- [ ] **IRC deals**: Primer HAVE: anunciado, DEAL: mensajes pendientes proximo heartbeat cycle

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

## Deployment Lessons

### Docker Pull Timeout via SSH
- `docker pull` via SSH puede colgar indefinidamente en t3.small
- Solucion: separar pull de restart — primero `nohup docker pull` o backgroundear
- Script `restart_nopull.sh`: asume imagen ya descargada, solo hace stop/start

### Script CRLF Issues
- Windows crea archivos con `\r\n`, Linux falla con `\r': command not found`
- Solucion: `cat script.sh | sed 's/\r$//' > script_unix.sh` antes de SCP

### Agent Wallet Lookup
- `docker run --rm` para leer config puede colgar si hay capas grandes
- Solucion: leer wallets de `data/config/identities.json` local y pasar como argumento

### Docker Image Digest Mismatch
- Agentes pueden quedar con imagen vieja si `docker pull` falla silenciosamente
- Verificar: `docker images --format "{{.ID}}" <image>` vs digest conocido

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
