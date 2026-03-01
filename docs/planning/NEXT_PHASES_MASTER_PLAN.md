# Master Plan: Fases Pendientes (4, 5, 7 + Golden Flow)

> Fecha: 2026-03-01
> Estado: READY TO EXECUTE
> Contexto: Phases 1-3 y 6 del Obsidian Vault plan COMPLETAS. Golden Flow parcialmente implementado.
> Objetivo: Completar la economia autonoma de 24 agentes.

---

## Estado Actual — Que Funciona Hoy

### Infraestructura (7 agentes en EC2)
- [x] 7 EC2 t3.small corriendo (coordinator, karma-hello, skill/voice/soul-extractor, validator, juanjumagalp)
- [x] Docker image con heartbeat, IRC, vault sync, EM client
- [x] ECR repo + deploy scripts (`restart_all_agents.sh`)
- [x] S3 bucket con 328 archivos de logs
- [x] SSH key `kk-openclaw.pem`

### Obsidian Vault (Phases 1-3, 6 completas)
- [x] `vault/` con 24 carpetas de agentes + shared/ + knowledge/ + dashboards/
- [x] `lib/vault_sync.py` funcional (read/write state, commit+push)
- [x] Heartbeat actualiza vault state en cada ciclo
- [x] Coordinator lee estados de peers via vault
- [x] Dashboards Dataview para humanos
- [x] IRC messages incluyen info del vault

### Golden Flow (parcial)
- [x] Heartbeat cada 5 min, IRC cooldown 30 min
- [x] karma-hello publica tasks en EM
- [x] Community buyer (juanjumagalp) state machine funcional
- [x] Escrow flow buyer->seller con reputacion bidireccional
- [x] Data retrieval wired en 4 buyers
- [ ] Extractors no procesan datos reales (asumen archivos locales)
- [ ] Data delivery via S3 presigned URLs no verificado end-to-end
- [ ] IRC proactive messages enviados pero sin respuestas inteligentes

---

## Phase 4: Cross-Agent Awareness (Vault-Powered Decisions)

**Prerequisito**: Phases 1-3 completas (check)
**Estimado**: 45 min

### 4.2 — Buyers leen offerings del vault

**Que**: Los buyers (extractors + juanjumagalp) leen `vault/agents/kk-karma-hello/offerings.md` antes de buscar en EM. Si el vault dice que karma-hello tiene datos frescos, priorizan comprar.

**Donde**: `services/community_buyer_service.py`, `cron/heartbeat.py`

**Tarea**:
- [ ] 4.2.1 karma-hello escribe `offerings.md` al vault despues de publicar tasks
  - Archivo: `services/karma_hello_service.py` → `seller_flow()`
  - Despues de publish: `vault.write_offerings(published_tasks)`
  - Formato: frontmatter con lista de tasks activos, precios, fechas
- [ ] 4.2.2 Buyers leen offerings antes de `browse_tasks()`
  - Archivo: `cron/heartbeat.py` → cada buyer block
  - `offerings = vault.read_peer_state("kk-karma-hello", "offerings.md")`
  - Si offerings contiene task_ids → aplicar directamente (skip browse)
- [ ] 4.2.3 Agregar `write_offerings()` y `read_offerings()` a `lib/vault_sync.py`

### 4.3 — Extractors leen supply chain del vault

**Que**: Extractors leen `vault/shared/supply-chain.md` para saber en que paso esta la cadena. Si soul-extractor ve que skill-extractor ya publico profiles, sabe que puede comprar.

**Donde**: `services/skill_extractor_service.py`, `services/voice_extractor_service.py`, `services/soul_extractor_service.py`

**Tarea**:
- [ ] 4.3.1 Coordinator actualiza `shared/supply-chain.md` en cada heartbeat
  - Lee estados de los 7 agentes
  - Escribe resumen: "karma-hello: publishing (5 tasks), skill-extractor: processing, ..."
- [ ] 4.3.2 Extractors leen supply-chain.md al inicio de su heartbeat
  - Si upstream tiene datos nuevos → priorizan comprar
  - Si upstream esta idle → skip buying, focus en procesar lo que tienen

### 4.5 — Decision engine basado en vault

**Que**: Agentes priorizan acciones basado en el estado global. Si todos tienen datos frescos, focus en procesar. Si hay backlog, focus en vender.

**Donde**: `cron/heartbeat.py`, `lib/vault_sync.py`

**Tarea**:
- [ ] 4.5.1 Crear `lib/vault_decisions.py` con funcion `prioritize_actions(vault, agent_name)`
  - Lee estados de peers → determina si comprar, procesar, o vender
  - Input: vault state + agent role → Output: lista priorizada de acciones
- [ ] 4.5.2 Integrar en heartbeat: cada agente consulta `prioritize_actions()` antes de actuar
- [ ] 4.5.3 Log de decisiones al vault: `vault.append_log("Decision: BUY (upstream has fresh data)")`

**Deploy**: Requiere build + push + restart (usa skill `kk-deploy`)

---

## Phase 5: Community Agents (17 restantes)

**Prerequisito**: Phase 3 completa (check), presupuesto aprobado (~$257/mo)
**Estimado**: 60 min
**Costo**: 17 x t3.small = ~$257/mo adicionales (~$363/mo total con los 7 existentes)

### 5.1 — Actualizar SOUL.md de community agents

**Estado**: Ya existen SOUL.md para los 17 community agents con instrucciones de buyer.
**Que falta**: Agregar seccion de vault operations.

**Tarea**:
- [ ] 5.1.1 Agregar a cada SOUL.md de community agent:
  ```
  ## Vault Operations
  Tu estado se publica automaticamente al vault en cada heartbeat.
  Puedes leer el estado de otros agentes via vault para tomar decisiones.
  No necesitas hacer nada manual — el vault sync corre cada 60 segundos.
  ```
- [ ] 5.1.2 Verificar que `openclaw.json` de cada community agent tiene los campos correctos:
  - `agent_name`, `wallet_address`, `executor_id`, `agent_id`

**Archivos**: 17x `openclaw/agents/kk-*/SOUL.md`

### 5.2 — Crear secrets en AWS

**Que**: Cada community agent necesita su private key en AWS Secrets Manager.

**Tarea**:
- [ ] 5.2.1 Derivar 17 private keys desde el mnemonic en `kk/swarm-seed`
  - Script existente: `scripts/kk/derive_wallet.py`
  - Indices 7-23 (0-6 ya creados para system agents)
- [ ] 5.2.2 Crear 17 secrets en us-east-1:
  - Script existente: `scripts/kk/create_agent_secrets.py`
  - Formato: `kk/<agent-name>` con `{"private_key": "0x..."}`
- [ ] 5.2.3 Verificar que los 17 secrets existen y tienen private keys validas

**SEGURIDAD**: Derivar keys en memoria, nunca escribir a disco. Usar `create_agent_secrets.py` que va directo a Secrets Manager.

### 5.3 — Actualizar Terraform

**Que**: Agregar los 17 community agents al mapa de variables de Terraform.

**Tarea**:
- [ ] 5.3.1 Agregar 17 entries al `agents` map en `terraform/openclaw/variables.tf`
  - Formato: `kk-<name> = { index = N, wallet_address = "0x..." }`
  - Data source: `data/config/wallets.json`
- [ ] 5.3.2 Verificar que `main.tf` usa `for_each` sobre el mapa (ya deberia)
- [ ] 5.3.3 `terraform plan` para preview de los 17 nuevos EC2 instances

### 5.4 — Terraform apply

**Que**: Crear 17 nuevas EC2 t3.small con el mismo setup que las 7 existentes.

**Tarea**:
- [ ] 5.4.1 `terraform apply` — crea 17 EC2 + security groups + EBS volumes
- [ ] 5.4.2 Capturar IPs de las 17 nuevas instancias
- [ ] 5.4.3 Actualizar `kk-deploy` skill con las 24 IPs
- [ ] 5.4.4 Actualizar `kk-swarm-monitor` skill con las 24 IPs
- [ ] 5.4.5 Actualizar `scripts/kk/restart_all_agents.sh` con 24 agentes

### 5.5 — Build + Deploy a 24 agentes

**Tarea**:
- [ ] 5.5.1 Docker build `--no-cache` con las 17 SOUL.md actualizadas
- [ ] 5.5.2 Push a ECR
- [ ] 5.5.3 Deploy a 24 agentes (adaptar `restart_all_agents.sh` para 24)
- [ ] 5.5.4 Verificar que los 24 containers arrancan

### 5.6 — Verificacion

**Tarea**:
- [ ] 5.6.1 SSH a 3 community agents aleatorios, verificar Docker logs
- [ ] 5.6.2 `python scripts/kk/swarm_ops.py irc-check` — 24 nicks en IRC
- [ ] 5.6.3 Verificar vault: 24 state.md actualizandose cada 5 min
- [ ] 5.6.4 Verificar EM: community agents publican bounties y aplican a tasks

---

## Phase 7: Cross-Project Linking (evaluaciones) — COMPLETA

**Prerequisito**: Phase 1 completa (check)
**Completada**: 2026-03-01

### 7.5 — Evaluar git submodules — DECISION TOMADA

**Que**: Determinar si tiene sentido usar git submodules para compartir vault entre repos (karmacadabra, abracadabra, karmagelou, execution-market).

**Analisis**:

| Opcion | Pros | Contras |
|--------|------|---------|
| Git submodules | Version pinning, dependency tracking | UX horrible: `git submodule update --init --recursive`, nested git ops, merge conflicts in .gitmodules, confunde a contributors nuevos |
| Symlinks | Simple, zero overhead | No funciona en Windows, no portable |
| Repo separado | Limpio, permisos independientes | Requiere segundo clone, sync manual |
| **Mantener en KK repo** | **Zero overhead, ya funciona, un solo `git clone`** | **Solo escala hasta ~100MB** |

- [x] 7.5.1 Documentar pros/cons
- [x] 7.5.2 **DECISION: NO submodules**
- [x] 7.5.3 Documentar decision

**Decision final: Mantener vault dentro del repo KK.**

Razones:
1. Solo 1 repo (KK) escribe al vault activamente — no hay conflictos multi-writer
2. Otros proyectos (EM, facilitator) solo leen via API o `git pull` del vault
3. El vault actual tiene ~50 archivos markdown (<1MB) — muy lejos del limite de 100MB
4. Submodules agregan complejidad operativa sin beneficio real para nuestro caso
5. Windows es entorno principal de desarrollo — symlinks no son opcion

**Criterio para re-evaluar**: Si el vault crece >50MB O si >2 repos necesitan escribir al vault, migrar a repo separado (sin submodules, solo git remote).

### 7.6 — Evaluar obsidian-headless — DECISION TOMADA

**Que**: Determinar si vale la pena usar Obsidian Sync ($8/mo) o obsidian-headless para sync.

**Analisis**:

| Opcion | Costo | Latencia | Pros | Contras |
|--------|-------|----------|------|---------|
| Git sync (actual) | $0/mo | ~60s | Gratis, probado en produccion, funciona en CI | No real-time |
| Obsidian Sync | $8/mo | <1s | Real-time, conflict resolution nativa | Requiere Obsidian account, no funciona headless en EC2 |
| obsidian-headless | $0/mo | <1s | Open source | Experimental, requiere X11/display, no mantenido activamente, no funciona en EC2 AL2023 |

- [x] 7.6.1 Investigar obsidian-headless: Proyecto experimental, ultimo commit hace meses, requiere display virtual (Xvfb), no viable para EC2 headless
- [x] 7.6.2 Comparar con git sync actual
- [x] 7.6.3 **DECISION: Mantener git sync**

**Decision final: Git sync via `vault_sync.py` es la solucion correcta.**

Razones:
1. 60s de latencia es irrelevante — heartbeats cada 5 min (300s), la info del vault nunca tiene >5 min de edad
2. Zero costo adicional vs $8/mo de Obsidian Sync
3. Ya probado en produccion con 7 agentes, funciona confiablemente
4. Git da history gratis — podemos ver la evolucion del estado de cada agente con `git log`
5. obsidian-headless no es viable para servidores sin display (EC2 AL2023)
6. Si necesitamos real-time en el futuro, un webhook de git push a un endpoint HTTP es mas simple

**Criterio para re-evaluar**: Si necesitamos latencia <5s para coordinacion en tiempo real (unlikely con heartbeats de 5 min).

---

## Orden de Ejecucion

```
Sesion 1 — Phase 4 (Cross-Agent Awareness)          [COMPLETA 2026-03-01]
  4.2  Buyers leen offerings del vault              ✓
  4.3  Extractors leen supply chain                 ✓
  4.5  Decision engine                              ✓
  -> Build + Deploy pendiente

Sesion 2 — Phase 7 (Evaluaciones rapidas)           [COMPLETA 2026-03-01]
  7.5  Decision: NO submodules                      ✓
  7.6  Decision: Mantener git sync                  ✓
  -> Solo documentacion, no requiere deploy

Sesion 3 — Phase 5 (Community Agents)               [PENDIENTE ~60 min]
  5.1  Actualizar SOUL.md (10 min)
  5.2  Crear 17 secrets en AWS (10 min)
  5.3  Actualizar Terraform (10 min)
  5.4  Terraform apply (10 min)
  5.5  Build + Deploy a 24 (10 min)
  5.6  Verificacion (10 min)
```

**Estado**: Phase 4 y 7 completas. Phase 5 es el siguiente paso — requiere presupuesto (~$257/mo adicionales) y tiempo de ejecucion para crear 17 EC2 instances.

---

## Golden Flow — Gaps Restantes

Estos son independientes de las fases de Obsidian Vault:

### GF-1: Extractors procesando datos reales

**Estado**: Los 3 extractors tienen logica de procesamiento pero asumen archivos locales. `check_and_retrieve_all()` ya esta wired pero no verificado.

**Tarea**:
- [ ] GF-1.1 Verificar que `data_retrieval.py` descarga correctamente de S3 presigned URLs
- [ ] GF-1.2 Verificar que `skill_extractor_service.py` lee de `data/purchases/`
- [ ] GF-1.3 Verificar que `voice_extractor_service.py` lee de `data/purchases/`
- [ ] GF-1.4 End-to-end test: karma-hello publica → skill-extractor compra → procesa → publica

### GF-2: Data delivery S3 presigned URLs

**Estado**: `services/data_delivery.py` existe con `prepare_delivery_package()` pero no se ha verificado que los archivos existen en S3.

**Tarea**:
- [ ] GF-2.1 Verificar que `karmacadabra-agent-data` tiene los archivos mapeados en `data_delivery.py`
- [ ] GF-2.2 Test de presigned URL: generar una URL y descargar
- [ ] GF-2.3 Integrar delivery URL en `karma_hello_service.py` → `fulfill_purchases()`

### GF-3: IRC bidireccional

**Estado**: Agentes envian mensajes HAVE/NEED pero no responden a otros agentes.

**Tarea**:
- [ ] GF-3.1 Agentes parsean mensajes IRC de otros agentes
- [ ] GF-3.2 Responden a NEED con ofertas: "I have that! Check EM task_id=..."
- [ ] GF-3.3 Responden a HAVE con interes: "Interested! Applying now."

---

## Verificacion End-to-End (Todas las Fases Completas)

Cuando todo este desplegado:

1. **24 agentes en EC2**: `terraform show | grep "aws_instance"` → 24 instancias
2. **24 state.md activos**: cada state.md con heartbeat < 10 min
3. **IRC poblado**: 24 nicks en #karmakadabra, HAVE/NEED activos
4. **Supply chain activa**: karma-hello → extractors → juanjumagalp + 17 community buyers
5. **Vault sync**: git log muestra commits de 24 agentes cada 60s
6. **Obsidian dashboard**: Abrir vault, ver 24 agentes en tabla Dataview
7. **Revenue**: >$0 USDC movido en escrow por dia
