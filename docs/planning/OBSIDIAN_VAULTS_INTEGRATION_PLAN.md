# Mega Plan: Obsidian Vaults Integration

> Fecha: 2026-03-01
> Estado: IN PROGRESS (Phase 1-3 COMPLETE, Phase 4+ pending)
> Objetivo: Integrar Obsidian Vaults como capa de estado compartido entre todos los agentes KK, interconectando KarmaCadabra, AbraCadabra, KarmaGelou, y Execution Market.

---

## Arquitectura Decidida

**Git-Synced Shared Vault + Direct Filesystem Access**

Los agentes en EC2 NO necesitan Obsidian corriendo. Un vault es simplemente una carpeta de archivos `.md` con frontmatter YAML. Los agentes leen/escriben directamente al filesystem, syncan via git, y los humanos abren el mismo repo como vault en Obsidian Desktop para dashboards y visualizacion.

```
                    +---------------------+
                    |   GitHub Private     |
                    |   kk-shared-vault    |
                    +----------+----------+
                               |
          +--------------------+--------------------+
          |                    |                    |
  +-------v--------+  +-------v--------+  +-------v--------+
  | EC2: karma-hello|  | EC2: validator |  | EC2: coordinator|
  | /vault/         |  | /vault/        |  | /vault/         |
  |  agents/        |  |  agents/       |  |  agents/        |
  |   karma-hello/  |  |   validator/   |  |   coordinator/  |
  +----------------+  +----------------+  +-----------------+
          |                    |                    |
          +--------------------+--------------------+
                  cron: git sync cada 60s
```

### Stack Tecnico

| Capa | Herramienta | Proposito |
|------|-------------|-----------|
| Storage | Git repo + markdown files | Vault = carpeta de .md |
| Read/Write | `python-frontmatter` | Leer/escribir notas con YAML metadata |
| Analysis | `obsidiantools` | Grafo de links, stats del vault |
| Sync | Git CLI via cron | Push/pull entre EC2 y repo central |
| Conflicts | File ownership por agente | Cada agente escribe solo en `agents/<name>/` |
| Human View | Obsidian Desktop | Abrir repo como vault, Dataview dashboards |
| Queries | Dataview plugin (Obsidian) | Tablas de estado de agentes |
| Cross-links | Wikilinks `[[note]]` | Links entre notas del vault |

---

## Estructura del Vault

```
kk-shared-vault/
+-- .obsidian/                          # Config de Obsidian (para humans)
+-- .gitattributes                      # merge=union para logs
+-- agents/                             # Estado por agente (ownership exclusivo)
|   +-- kk-coordinator/
|   |   +-- state.md                    # Status, current task, heartbeat
|   |   +-- memory.md                   # Long-term learnings
|   |   +-- log-YYYY-MM-DD.md          # Activity log diario
|   +-- kk-karma-hello/
|   |   +-- state.md
|   |   +-- memory.md
|   |   +-- log-YYYY-MM-DD.md
|   |   +-- offerings.md               # Productos publicados en EM
|   +-- kk-skill-extractor/
|   +-- kk-voice-extractor/
|   +-- kk-soul-extractor/
|   +-- kk-validator/
|   +-- kk-juanjumagalp/
|   +-- kk-elboorja/                   # Community agents (17)
|   +-- kk-stovedove/
|   +-- ... (17 community agents)
+-- shared/                             # Archivos de coordinacion
|   +-- tasks.md                        # Task board compartido
|   +-- ledger.md                       # Registro de transacciones
|   +-- config.md                       # Config compartida
|   +-- announcements.md               # Broadcast messages
|   +-- supply-chain.md                # Estado de la cadena de suministro
+-- knowledge/                          # Knowledge base compartida
|   +-- contracts/
|   |   +-- erc8004-registry.md
|   |   +-- usdc-base.md
|   +-- apis/
|   |   +-- execution-market.md
|   |   +-- meshrelay-irc.md
|   +-- protocols/
|   |   +-- x402-payment.md
|   |   +-- eip3009-gasless.md
|   +-- lessons-learned.md
+-- dashboards/                         # Dataview dashboards (human use)
|   +-- agent-status.md                 # TABLE de todos los agentes
|   +-- supply-chain-flow.md            # Flujo de la cadena
|   +-- transactions.md                 # Historial de transacciones
|   +-- irc-activity.md                 # Resumen de actividad IRC
+-- projects/                           # Cross-project linking
    +-- karmacadabra.md                 # Link hub a KK repo
    +-- abracadabra.md                  # Link hub a AbraCadabra
    +-- karmagelou.md                   # Link hub a KarmaGelou
    +-- execution-market.md             # Link hub a EM
```

### Formato de State File

```yaml
---
agent_id: kk-karma-hello
status: active
role: seller
last_heartbeat: 2026-03-01T12:34:56Z
current_task: "Publishing chat log bundles"
task_id: "uuid-here"
wallet: "0xa3279F744438F83Bc75ce9f8A8282c448F97cc8A"
executor_id: "001f9c30-6ec4-4bff-8e0b-853e20cb8349"
erc8004_id: 18776
chain: base
daily_revenue_usdc: 0.05
daily_spent_usdc: 0.00
tasks_completed: 12
errors_last_24h: 0
irc_messages_sent: 3
tags:
  - agent
  - seller
  - system
  - karma-hello
aliases:
  - "karma-hello"
  - "KK Data Producer"
---

## Current Activity
Publishing 5 chat log bundles on Execution Market at $0.01 each.

## Recent Actions
- 12:30 - Published raw_logs bundle #5 on EM
- 12:15 - Fulfilled purchase for kk-skill-extractor (task abc123)
- 11:45 - IRC: Announced HAVE: 469K messages, 834 users in #Execution-Market

## Links
- Sells to: [[kk-skill-extractor]], [[kk-voice-extractor]], [[kk-juanjumagalp]]
- Published on: [[execution-market]]
- IRC channels: #karmakadabra, #Execution-Market
```

---

## Fases de Ejecucion

### Phase 1: Vault Bootstrap (Repo + Estructura)

**Objetivo**: Crear el repo Git, estructura de carpetas, y archivos iniciales.

- [x] 1.1 Crear directorio `vault/` en el repo KK (o repo separado `kk-shared-vault`)
- [x] 1.2 Crear estructura de carpetas: `agents/`, `shared/`, `knowledge/`, `dashboards/`, `projects/`
- [x] 1.3 Generar `state.md` inicial para los 7 agentes activos con frontmatter correcto
- [x] 1.4 Generar `state.md` placeholder para los 17 community agents
- [x] 1.5 Crear `.gitattributes` con merge=union para log files
- [x] 1.6 Crear `shared/config.md` con parametros globales
- [x] 1.7 Crear `shared/supply-chain.md` con el estado de la cadena
- [x] 1.8 Crear archivos de `knowledge/` con info de contratos, APIs, protocolos
- [x] 1.9 Crear `dashboards/` con Dataview queries
- [x] 1.10 Crear `projects/` con links a los otros repos

**Archivos**: ~60 archivos markdown nuevos
**Dependencias**: Ninguna

### Phase 2: Python Vault Library (lib/vault_sync.py)

**Objetivo**: Modulo Python reutilizable para que los agentes lean/escriban al vault.

- [x] 2.1 Crear `lib/vault_sync.py` con clase `VaultSync`:
  - `pull()` — git pull --rebase --autostash
  - `write_state(metadata, body)` — actualiza state.md del agente
  - `read_state()` — lee state.md propio
  - `read_peer_state(agent_name)` — lee state.md de otro agente
  - `append_log(message)` — agrega linea al log diario
  - `read_shared(filename)` — lee archivo de shared/
  - `write_shared(filename, metadata, body)` — escribe a shared/ (solo coordinator)
  - `commit_and_push(message)` — commit + push atomico
- [x] 2.2 Agregar `python-frontmatter` a requirements
- [x] 2.3 Tests unitarios para vault_sync
- [x] 2.4 Integrar en `Dockerfile.openclaw` (clonar vault repo en /vault/)

**Archivos**: `lib/vault_sync.py`, `requirements.txt`, `tests/test_vault_sync.py`
**Dependencias**: Phase 1

### Phase 3: Heartbeat Integration

**Objetivo**: Cada heartbeat actualiza el state.md del agente en el vault.

- [x] 3.1 Modificar `cron/heartbeat.py`:
  - Al inicio: `vault.pull()`
  - Despues de cada accion: `vault.write_state({status, current_task, ...})`
  - Al final: `vault.append_log(summary)` + `vault.commit_and_push()`
- [x] 3.2 Agregar vault sync al entrypoint.sh:
  - Clonar vault repo al inicio del container
  - Configurar git identity (agent name como author)
  - Cron job: sync cada 60 segundos
- [x] 3.3 Crear `scripts/kk/vault_sync_cron.sh` — script de sync para cron
- [x] 3.4 Actualizar `terraform/openclaw/user_data.sh.tpl` con vault repo clone

**Archivos**: `cron/heartbeat.py`, `openclaw/entrypoint.sh`, `scripts/kk/vault_sync_cron.sh`
**Dependencias**: Phase 2

### Phase 4: Cross-Agent Awareness

**Objetivo**: Agentes leen el estado de otros agentes del vault para tomar decisiones.

- [ ] 4.1 Coordinator: Lee `agents/*/state.md` para detectar agentes stale
- [ ] 4.2 Buyers: Leen `agents/kk-karma-hello/offerings.md` para saber que hay disponible
- [ ] 4.3 Extractors: Leen `shared/supply-chain.md` para saber en que paso esta la cadena
- [ ] 4.4 IRC integration: Incluir info del vault en mensajes proactivos
  - "HAVE: [offerings from vault] | $price on EM"
  - "STATUS: [from peer state.md] kk-karma-hello last active 2 min ago"
- [ ] 4.5 Decision engine: Agentes priorizan acciones basado en estado global del vault

**Archivos**: `services/irc_integration.py`, `cron/heartbeat.py`, servicios de cada agente
**Dependencias**: Phase 3

### Phase 5: Community Agents (17 restantes)

**Objetivo**: Preparar y desplegar los 17 community agents con vault integration.

- [ ] 5.1 Actualizar SOUL.md de los 17 community agents con instrucciones de vault
- [ ] 5.2 Crear secrets en AWS (private keys para los 17)
- [ ] 5.3 Actualizar Terraform variables.tf con los 17 agentes
- [ ] 5.4 Terraform apply para crear 17 EC2 nuevas
- [ ] 5.5 Build + deploy imagen con vault integration
- [ ] 5.6 Verificar que los 24 agentes syncan al vault

**Archivos**: `openclaw/agents/kk-*/SOUL.md`, `terraform/openclaw/variables.tf`
**Dependencias**: Phase 3
**Costo estimado**: 17 x t3.small = ~$257/mo adicionales

### Phase 6: Dashboards + Human View

**Objetivo**: Dataview dashboards funcionales para monitoreo humano.

- [ ] 6.1 `dashboards/agent-status.md` — TABLE de todos los agentes con status, revenue, heartbeat
- [ ] 6.2 `dashboards/supply-chain-flow.md` — Flujo visual de la cadena de suministro
- [ ] 6.3 `dashboards/transactions.md` — Historial de compras/ventas
- [ ] 6.4 `dashboards/irc-activity.md` — Resumen de actividad por canal
- [ ] 6.5 Documentar como abrir el vault en Obsidian Desktop
- [ ] 6.6 Crear `.obsidian/` config con Dataview y plugins recomendados

**Archivos**: `dashboards/*.md`, `.obsidian/`
**Dependencias**: Phase 3

### Phase 7: Cross-Project Linking

**Objetivo**: Conectar vaults de KarmaCadabra, AbraCadabra, KarmaGelou, y Execution Market.

- [ ] 7.1 Crear `projects/karmacadabra.md` con MOC (Map of Content) del proyecto
- [ ] 7.2 Crear `projects/abracadabra.md` con links a transcripciones
- [ ] 7.3 Crear `projects/karmagelou.md` con links a metricas on-chain
- [ ] 7.4 Crear `projects/execution-market.md` con links a API/tasks
- [ ] 7.5 Evaluar: git submodules para vaults compartidos entre proyectos
- [ ] 7.6 Evaluar: `obsidian-headless` para sync con Obsidian Sync (si se paga)

**Archivos**: `projects/*.md`
**Dependencias**: Phase 1

---

## Cronograma

```
Phase 1 (Bootstrap):          30 min — crear repo y estructura
Phase 2 (Python lib):         45 min — vault_sync.py + tests
Phase 3 (Heartbeat):          30 min — integrar en heartbeat + entrypoint
Phase 4 (Cross-Agent):        45 min — awareness entre agentes
Phase 5 (Community):          60 min — 17 agents + terraform + deploy
Phase 6 (Dashboards):         30 min — Dataview queries
Phase 7 (Cross-Project):      20 min — links entre proyectos
```

**Total**: ~4 horas de desarrollo + deploy

---

## Decision: Vault Inside Repo vs Repo Separado

**Opcion A: Subdirectorio `vault/` dentro de karmacadabra** (ELEGIDA)
- Pro: Todo en un solo repo, deployment simple (ya esta en Docker)
- Pro: No necesita otro git clone en los containers
- Con: Vault crece con el tiempo, puede ser pesado
- Con: `.obsidian/` config mezclada con codigo

**Opcion B: Repo separado `kk-shared-vault`**
- Pro: Vault limpio, optimizado para Obsidian
- Pro: Humans pueden clonar solo el vault
- Con: Requiere segundo git clone en cada container
- Con: Mas complejidad de sync

**Decision**: Opcion A (subdirectorio) para Phase 1-4. Migrar a repo separado si el vault crece >100MB.

---

## Dependencias Python

```
python-frontmatter>=1.0.0
obsidiantools>=0.11.0  # optional, for analysis
```

Agregar a `requirements.txt` existente.

---

## Verificacion End-to-End

1. **Vault existe**: `ls vault/agents/` muestra 24 carpetas de agentes
2. **State files**: Cada `state.md` tiene frontmatter valido con status, heartbeat, wallet
3. **Git sync**: Commits aparecen en el repo cada 60 segundos desde cada agente
4. **Cross-agent read**: kk-skill-extractor puede leer state de kk-karma-hello
5. **IRC enrichment**: Mensajes IRC incluyen datos del vault
6. **Dataview**: Abrir vault en Obsidian muestra tabla de agentes activos
7. **No conflicts**: 24 agentes pusheando sin merge conflicts
