# KarmaCadabra - Estado del Proyecto
## Reporte Completo: 23 de Febrero de 2026

> **Generado por**: Claude Code (Opus 4.6) + equipo de 4 agentes exploradores
> **Propósito**: Documentar el estado actual de v1, inventariar v2, y planificar la migración

---

## 1. Resumen Ejecutivo

KarmaCadabra ha evolucionado significativamente desde su versión original (v1) creada en Octubre 2025. El proyecto pasó de ser un marketplace demo con 5 agentes de sistema + 48 perfiles estáticos en Avalanche Fuji testnet, a un **swarm autónomo de 24 agentes** con wallets fondeadas en **8 chains mainnet**, identidades ERC-8004 on-chain, integración con Execution Market, y comunicación IRC vía MeshRelay.

### Comparación v1 vs v2

| Aspecto | v1 (Actual en repo) | v2 (En Execution Market) |
|---------|---------------------|--------------------------|
| **Agentes** | 5 sistema + 48 perfiles estáticos | 6 sistema + 18 comunidad (24 total) |
| **Blockchain** | Avalanche Fuji (testnet) | 8 chains mainnet (Base, ETH, Polygon, Arbitrum, Avalanche, Optimism, Celo, Monad) |
| **Token** | GLUE Token custom (ERC-20 + EIP-3009) | USDC + 4 stablecoins más (EURC, AUSD, PYUSD, USDT) |
| **Identidad** | ERC-8004 en Fuji testnet | ERC-8004 en Base mainnet (CREATE2, misma address todas las chains) |
| **Facilitador** | x402-rs v0.x (testnet) | x402-rs v1.33.18 (producción, multi-chain, ERC-8004, escrow) |
| **Comunicación** | A2A protocol (agent cards) | IRC vía MeshRelay + OpenClaw framework |
| **Marketplace** | Central Marketplace API estático | Execution Market (REST API + MCP + Supabase) |
| **Fondos totales** | GLUE testnet tokens (sin valor) | $190.93 USD reales ($148.12 en agentes + $42.81 master wallet) |
| **Infraestructura** | Terraform ECS Fargate (us-east-1) | Terraform ECS Fargate (nueva config swarm) |
| **Modelo de operación** | Servidor siempre activo | Heartbeat cada 15 min (wake, execute, sleep) |
| **Wallets** | 5 wallets individuales | 24 wallets HD (BIP-44 desde mnemonic) |

---

## 2. Estado Actual del Repo v1

### 2.1 Estructura de Directorios

```
karmacadabra/                          # Root del proyecto
├── CLAUDE.md                          # Instrucciones para Claude (~1200 líneas)
├── MASTER_PLAN.md                     # Plan maestro v1 (v1.6.2, Oct 28 2025)
├── README.md / README.es.md           # Documentación bilingüe
├── docker-compose.yml                 # Stack completo (6 servicios)
├── docker-compose.dev.yml             # Variante desarrollo
├── docker-compose.irc.yml             # Config IRC
│
├── agents/                            # 6 agentes Python
│   ├── karma-hello/main.py            # Vendedor de chat logs (MongoDB)
│   ├── abracadabra/main.py            # Vendedor de transcripciones (SQLite+Cognee)
│   ├── skill-extractor/main.py        # Extractor de perfiles de habilidades
│   ├── voice-extractor/main.py        # Extractor de perfiles de personalidad
│   ├── validator/main.py              # Validador de calidad (CrewAI)
│   └── marketplace/main.py            # API central de marketplace
│
├── shared/                            # Librerías compartidas (16 archivos)
│   ├── base_agent.py                  # ERC8004BaseAgent base class
│   ├── agent_config.py                # Configuración + AWS Secrets Manager
│   ├── x402_client.py                 # Cliente x402 para pagos
│   ├── payment_signer.py              # Firmador EIP-3009
│   ├── a2a_protocol.py                # Agent-to-Agent discovery
│   ├── contracts_config.py            # Direcciones de contratos
│   ├── transaction_logger.py          # Logger de transacciones
│   ├── validation_crew.py             # CrewAI validation
│   ├── secrets_manager.py             # AWS Secrets Manager client
│   ├── irc_protocol.py                # Protocolo IRC
│   ├── irc_control.py                 # Control plane IRC
│   └── irc_commander.py               # Comandos IRC
│
├── terraform/ecs-fargate/             # Infraestructura AWS (11 archivos .tf)
│   ├── main.tf                        # ECS cluster, capacity providers, task defs
│   ├── variables.tf                   # Variables de configuración
│   ├── vpc.tf                         # VPC 10.0.0.0/16, subnets, NAT
│   ├── alb.tf                         # Application Load Balancer
│   ├── acm.tf                         # Certificados SSL
│   ├── route53.tf                     # DNS records
│   ├── security_groups.tf             # Security groups
│   ├── ecr.tf                         # Container registries
│   ├── iam.tf                         # Roles y policies
│   ├── cloudwatch.tf                  # Logging y monitoring
│   └── outputs.tf                     # Outputs
│
├── erc-20/                            # GLUE Token (Foundry)
│   └── contracts/src/UVD_V2.sol       # ERC-20 + EIP-3009 en Avalanche Fuji
│
├── erc-8004/                          # Registros ERC-8004 (Foundry)
│   └── contracts/src/                 # Identity, Reputation, Validation registries
│
├── client-agents/                     # 48 user agents (estáticos)
│   └── {username}/                    # ~310 líneas cada uno
│
├── scripts/                           # ~65 scripts Python (deploy, test, setup)
├── tests/                             # Test suite
├── docs/                              # Documentación organizada
├── contribution/                      # Material del curso
├── build-context/                     # Build context para Docker
└── .unused/                           # Archivos deprecados
```

### 2.2 Contratos Desplegados (v1 - Avalanche Fuji Testnet)

| Contrato | Address | Chain |
|----------|---------|-------|
| GLUE Token (EIP-3009) | `0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743` | Avalanche Fuji (43113) |
| Identity Registry | `0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618` | Avalanche Fuji |
| Reputation Registry | `0x932d32194C7A47c0fe246C1d61caF244A4804C6a` | Avalanche Fuji |
| Validation Registry | `0x9aF4590035C109859B4163fd8f2224b820d11bc2` | Avalanche Fuji |
| Transaction Logger | `0x85ea82dDc0d3dDC4473AAAcc7E7514f4807fF654` | Avalanche Fuji |

### 2.3 Infraestructura Terraform (v1)

**Cluster**: `karmacadabra-prod` en `us-east-1`

**Servicios ECS definidos**:
- facilitator (1 vCPU / 2GB RAM)
- validator (0.25 vCPU / 0.5GB RAM)
- karma-hello (0.25 vCPU / 0.5GB RAM)
- abracadabra (0.25 vCPU / 0.5GB RAM)
- skill-extractor (0.25 vCPU / 0.5GB RAM)
- voice-extractor (0.25 vCPU / 0.5GB RAM)

**Recursos AWS**:
- VPC con public/private subnets (2 AZs)
- ALB con SSL (ACM certificates)
- Route53 DNS (*.karmacadabra.ultravioletadao.xyz)
- ECR repos por agente
- CloudWatch logs (7 días retención)
- Fargate Spot (70% ahorro)
- S3 backend para Terraform state
- DynamoDB para Terraform locks
- Secrets Manager para API keys

**Costo estimado**: ~$75-92/mes

### 2.4 Estado Git

- **Branch**: master
- **Último commit**: `4a88c1e` - "Add IRC Control Plane for agent fleet orchestration"
- **Commits recientes**: Migración a Base Sepolia, IRC control plane, deployment runbooks
- **Archivos sin commit**: Varios scripts de task definitions, test scripts, agent profile docs

### 2.5 Qué Funciona en v1

- Terraform infrastructure (VPC, ECS, ALB, Route53, etc.)
- Docker Compose local development stack
- Shared libraries (base_agent, x402_client, payment_signer, etc.)
- Agent implementations (5 system agents + marketplace)
- ERC-8004 contract ABIs y deployment scripts
- GLUE token contract
- Scripts de deployment, testing, y management
- AWS Secrets Manager integration
- IRC control plane (nuevo)

### 2.6 Qué Está Desactualizado en v1

- Contratos en Avalanche Fuji testnet (v2 usa Base mainnet)
- GLUE Token custom (v2 usa USDC estándar)
- ERC-8004 addresses de testnet (v2 usa CREATE2 mainnet)
- Facilitador referenciado como testnet (v2 es producción multi-chain)
- 48 user agents estáticos (v2 tiene 18 community agents autónomos)
- A2A protocol para discovery (v2 usa MeshRelay IRC + OpenClaw)
- Docker compose con facilitador local (v2 usa facilitador externo en producción)

---

## 3. Inventario v2 (Desde Execution Market)

### 3.1 Código KK v2 en `execution-market/scripts/kk/`

#### Services (12 archivos)

| Archivo | Propósito |
|---------|-----------|
| `coordinator_service.py` | 6-factor task matching, health monitoring |
| `karma_hello_service.py` | IRC log collection, data publishing |
| `karma_hello_seller.py` | Data product catalog (4 productos) |
| `karma_hello_scheduler.py` | Background job scheduling |
| `abracadabra_service.py` | 4-phase content intelligence |
| `abracadabra_skills.py` | 5-skill registry |
| `skill_extractor_service.py` | Skill profile extraction |
| `voice_extractor_service.py` | Personality profile extraction |
| `soul_extractor_service.py` | Skills + voice fusion (SOUL.md) |
| `standup_service.py` | Daily standup report generator |
| `relationship_tracker.py` | Agent-to-agent trust scoring |
| `irc_service.py` | IRC integration service |
| `em_client.py` | HTTP client para Execution Market API |
| `swarm_dashboard.py` | Dashboard para monitoreo del swarm |
| `swarm_orchestrator.py` | Orquestador del swarm |

#### Libraries (15 archivos)

| Archivo | Propósito |
|---------|-----------|
| `irc_client.py` | Raw socket IRC client (TLS, threading) |
| `eip8128_signer.py` | EIP-8128 request signing |
| `swarm_state.py` | Supabase client para estado del swarm |
| `working_state.py` | WORKING.md parser/writer |
| `memory.py` | MEMORY.md + daily notes management |
| `soul_fusion.py` | Merge skills + voice + stats |
| `performance_tracker.py` | Agent performance metrics |
| `observability.py` | Logging y observability |
| `turnstile_client.py` | Turnstile bot payment client (MeshRelay) |
| `acontext_client.py` | AContext integration |
| `memory_bridge.py` | Memory bridge utility |
| `agent_lifecycle.py` | Agent lifecycle management |
| `reputation_bridge.py` | Reputation bridge (ERC-8004) |

#### TypeScript Scripts (25 archivos)

| Script | Propósito |
|--------|-----------|
| `check-full-inventory.ts` | Inventario completo multi-chain |
| `generate-allocation.ts` | Generador de allocation por agente |
| `bridge-from-source.ts` | Bridge USDC entre chains (deBridge/Squid) |
| `bridge-gas.ts` | Bridge para gas nativo |
| `distribute-funds.ts` | Fan-out tokens a 24 agentes |
| `sweep-funds.ts` | Sweep back a master wallet |
| `check-balances.ts` | Check balances por chain |
| `check-all-balances.ts` | Check all balances |
| `generate-wallets.ts` | Generar wallets HD |
| `fund-agents.ts` | Fondear agentes |
| `register-agents-erc8004.ts` | Registrar en ERC-8004 |
| + 14 más (eth-status, native, nonce, etc.) |

#### TypeScript Libraries (4 archivos en `lib/`)

| Archivo | Propósito |
|---------|-----------|
| `chains.ts` | 8-chain config, token addresses, RPCs |
| `bridge-router.ts` | Smart bridge selection (deBridge vs Squid) |
| `debridge-client.ts` | deBridge DLN REST API client |
| `squid-client.ts` | Squid Router API client |

#### IRC Module (4 archivos)

| Archivo | Propósito |
|---------|-----------|
| `agent_irc_client.py` | Agent-specific IRC client |
| `abracadabra_irc.py` | Abracadabra IRC integration |
| `log_listener.py` | IRC log listener |
| `em_bridge_bot.py` | EM bridge bot para IRC |
| `trading_signal_bot.py` | Trading signal bot |

#### Tests (25 archivos)

Test suite completa: unit tests, integration tests, chaos tests, E2E tests.

#### Cron/Monitoring

- `daily_routine.py`, `heartbeat.py`, `shutdown_handler.py`
- `balance_monitor.py`, `health_check.py`

#### Skills (OpenClaw)

7 skills para Execution Market: em-apply-task, em-approve-work, em-browse-tasks, em-check-status, em-publish-task, em-register-identity, irc-agent.

#### Config

- `identities.json` - Roster de 24 agentes con wallets y ERC-8004 IDs
- `funding-config.json` - Amounts por chain/token

#### Terraform Swarm (`terraform/swarm/`)

Setup completo de ECS Fargate para el swarm con:
- VPC, ECS Cluster, ECR repo compartido
- Fargate + Fargate Spot
- S3 para agent state
- CloudWatch logging
- Secrets Manager
- Cost alerts

---

## 4. Facilitador x402-rs (Estado Actual)

### 4.1 Versión y Arquitectura

- **Versión**: 1.33.18 (vs ~0.x en v1)
- **Repo local**: `Z:\ultravioleta\dao\x402-rs`
- **Producción**: `https://facilitator.ultravioletadao.xyz`
- **Logs**: AWS CloudWatch `/ecs/facilitator-production` (us-east-2)

### 4.2 Capacidades Nuevas vs v1

El facilitador ha evolucionado enormemente:

| Capacidad | v1 (lo que teníamos) | Actual |
|-----------|---------------------|--------|
| Networks | Avalanche Fuji, Base Sepolia | 17+ mainnets y testnets |
| Token types | GLUE custom | USDC + múltiples stablecoins |
| Auth | EIP-3009 básico | EIP-3009 + ERC-8004 + Payment Operator |
| Escrow | No | AuthCaptureEscrow en 8 chains |
| Discovery | No | Agent discovery + aggregator + crawler |
| Non-EVM | No | Solana, Algorand, Near, Stellar, Sui |
| ERC-8004 | No | Integración nativa (abi.rs, types.rs) |
| OpenAPI | No | Swagger/OpenAPI spec |
| Telemetry | Básico | Avanzado (telemetry.rs) |
| FHE | No | FHE proxy (fhe_proxy.rs) |
| Nonce store | No | Persistent nonce tracking |
| Blocklist | No | Address blocklist |

### 4.3 Módulos del Facilitador

```
src/
├── main.rs                  # Entry point
├── lib.rs                   # Library exports
├── handlers.rs              # HTTP handlers (include_str! for landing page)
├── network.rs               # 17+ networks configuradas
├── facilitator.rs           # Core settlement logic
├── facilitator_local.rs     # Local facilitator variant
├── types.rs / types_v2.rs   # Payment types
├── escrow.rs                # AuthCaptureEscrow
├── from_env.rs              # Environment config
├── openapi.rs               # OpenAPI spec
├── telemetry.rs             # Observability
├── blocklist.rs             # Address blocklist
├── nonce_store.rs           # Nonce tracking
├── provider_cache.rs        # RPC provider cache
├── discovery.rs             # Agent discovery
├── discovery_aggregator.rs  # Discovery aggregation
├── discovery_crawler.rs     # Discovery crawler
├── discovery_store.rs       # Discovery persistence
├── caip2.rs                 # CAIP-2 chain identifiers
├── fhe_proxy.rs             # FHE proxy
├── sig_down.rs              # Graceful shutdown
├── debug_utils.rs           # Debug utilities
├── timestamp.rs             # Timestamp handling
├── erc8004/                 # ERC-8004 integration
│   ├── mod.rs
│   ├── abi.rs               # Contract ABI
│   └── types.rs             # ERC-8004 types
├── payment_operator/        # Payment operator
│   ├── mod.rs
│   ├── abi.rs               # PaymentOperator ABI
│   ├── addresses.rs         # Deployed addresses
│   ├── errors.rs            # Error types
│   ├── operator.rs          # Core operator logic
│   └── types.rs             # Operator types
└── chain/                   # Multi-chain support
    ├── mod.rs
    ├── evm.rs               # EVM chains
    ├── solana.rs
    ├── algorand.rs
    ├── near.rs
    ├── stellar.rs
    └── sui.rs
```

### 4.4 SDKs Disponibles

| SDK | Repo Local | Propósito |
|-----|-----------|-----------|
| Python | `Z:\ultravioleta\dao\uvd-x402-sdk-python` | Para agentes Python |
| TypeScript | `Z:\ultravioleta\dao\uvd-x402-sdk-typescript` | Para agentes Node.js |

---

## 5. Contratos v2 (Mainnet)

### 5.1 ERC-8004 Identity Registry

| Network | Address | Tipo |
|---------|---------|------|
| **Todos Mainnets** | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` | CREATE2 (mismo en todas) |
| **Todos Testnets** | `0x8004A818BFB912233c491871b3d84c89A494BD9e` | CREATE2 (mismo en todas) |

### 5.2 ERC-8004 Reputation Registry

| Network | Address |
|---------|---------|
| Todos Mainnets | `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63` |

### 5.3 AuthCaptureEscrow (x402r)

| Network | Address |
|---------|---------|
| Base | `0xb9488351E48b23D798f24e8174514F28B741Eb4f` |
| Ethereum | `0x9D4146EF898c8E60B3e865AE254ef438E7cEd2A0` |
| Polygon | `0x32d6AC59BCe8DFB3026F10BcaDB8D00AB218f5b6` |
| Arbitrum, Avalanche, Celo, Monad, Optimism | `0x320a3c35F131E5D2Fb36af56345726B298936037` |

### 5.4 PaymentOperator (EM Trustless Fee Split)

| Network | Address |
|---------|---------|
| Base | `0x271f9fa7f8907aCf178CCFB470076D9129D8F0Eb` |
| Ethereum | `0x69B67962ffb7c5C7078ff348a87DF604dfA8001b` |
| Polygon | `0xB87F1ECC85f074e50df3DD16A1F40e4e1EC4102e` |
| Arbitrum | `0xC2377a9Db1de2520BD6b2756eD012f4E82F7938e` |
| Avalanche | `0xC2377a9Db1de2520BD6b2756eD012f4E82F7938e` |
| Monad | `0x9620Dbe2BB549E1d080Dc8e7982623A9e1Df8cC3` |
| Celo | `0xC2377a9Db1de2520BD6b2756eD012f4E82F7938e` |
| Optimism | `0xC2377a9Db1de2520BD6b2756eD012f4E82F7938e` |

### 5.5 Otras Addresses Importantes

| Entidad | Address | Notas |
|---------|---------|-------|
| StaticFeeCalculator (1300 BPS) | `0xd643DB63028Cd1852AAFe62A0E3d2A5238d7465A` | Base |
| Facilitator EOA | `0x103040545AC5031A11E8C03dd11324C7333a13C7` | Todas las chains |
| EM Platform Wallet / KK Master | `0xD3868E1eD738CED6945A574a7c769433BeD5d474` | Todas las chains |
| Disperse.app | `0xD152f549545093347A162Dce210e7293f1452150` | Base, ETH, Polygon, Arbitrum, Optimism |

---

## 6. MeshRelay (IRC para Agentes)

### 6.1 Infraestructura

| Campo | Valor |
|-------|-------|
| Repo local | `Z:\ultravioleta\dao\meshrelay` |
| Server IRC | `irc.meshrelay.xyz:6697` (TLS) |
| API | `https://api.meshrelay.xyz` |
| MCP | `POST https://api.meshrelay.xyz/mcp` |
| Daemon | InspIRCd 3.x + Anope services |
| Pagos | USDC en Base vía Turnstile bot |
| Primer pago real | 2026-02-22, $0.10 USDC |

### 6.2 APIs Disponibles

| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/irc/stats` | GET | Server statistics |
| `/irc/channels` | GET | List channels |
| `/irc/channels/:ch/messages` | GET | Recent messages |
| `/payments/channels` | GET | Premium channels |
| `/payments/access/:ch` | POST | Pay + access channel (x402) |
| `/payments/sessions/:nick` | GET | Active sessions |
| `/mcp` | POST | MCP endpoint (9 tools) |
| `wss://bridge.meshrelay.xyz/ws` | WebSocket | Real-time chat |

### 6.3 Integración con KK v2

- Cada agente se conecta como `kk-{nombre}` (e.g., `kk-juanjumagalp`)
- NickServ registration para cada agente
- Canales: `#Agents`, `#general`, `#kk-ops` (planned)
- x402 payments para premium channels desde Base USDC
- Heartbeat messages y task announcements vía IRC

---

## 7. Repos Individuales de Agentes

### 7.1 Abracadabra (Standalone)

| Campo | Valor |
|-------|-------|
| Path | `Z:\ultravioleta\ai\cursor\abracadabra` |
| Propósito | Procesamiento de transcripciones, content intelligence |
| Estado | Versión independiente con lógica de transcripción |
| Reutilizable | Lógica de procesamiento de transcripciones, pipelines de contenido |

### 7.2 Karma Hello (Standalone)

| Campo | Valor |
|-------|-------|
| Path | `Z:\ultravioleta\ai\cursor\karma-hello` |
| Propósito | Recopilación de logs de Twitch/chat |
| Estado | Versión independiente con collectors |
| Reutilizable | Lógica de recopilación de logs, parsing de mensajes |

---

## 8. Diccionario de Repositorios

> **Referencia rápida**: Cuándo necesites buscar algo, usa esta tabla.

| Repo | Path Local | Propósito | Estado |
|------|-----------|-----------|--------|
| **KarmaCadabra (v1)** | `Z:\ultravioleta\dao\karmakadabra` | Monorepo original: agents, terraform, contracts | Activo, base para migración |
| **Execution Market** | `Z:\ultravioleta\dao\execution-market` | Marketplace + código KK v2 en `scripts/kk/` | Activo, fuente de v2 |
| **Facilitador x402-rs** | `Z:\ultravioleta\dao\x402-rs` | Facilitador de pagos Rust (v1.33.18) | Producción en `facilitator.ultravioletadao.xyz` |
| **MeshRelay** | `Z:\ultravioleta\dao\meshrelay` | IRC server para agentes AI | Producción en `meshrelay.xyz` |
| **Abracadabra Standalone** | `Z:\ultravioleta\ai\cursor\abracadabra` | Agente de transcripciones (independiente) | Referencia |
| **Karma Hello Standalone** | `Z:\ultravioleta\ai\cursor\karma-hello` | Agente de logs (independiente) | Referencia |
| **x402 SDK Python** | `Z:\ultravioleta\dao\uvd-x402-sdk-python` | SDK Python para x402 payments | Disponible |
| **x402 SDK TypeScript** | `Z:\ultravioleta\dao\uvd-x402-sdk-typescript` | SDK TypeScript para x402 payments | Disponible |

### Dónde Buscar Qué

| Si necesitas... | Busca en... |
|-----------------|-------------|
| Terraform/ECS config | `karmakadabra/terraform/ecs-fargate/` |
| Shared Python libs (base agent, x402 client) | `karmakadabra/shared/` |
| Docker Compose setup | `karmakadabra/docker-compose.yml` |
| v2 Agent services | `execution-market/scripts/kk/services/` |
| v2 Agent libraries | `execution-market/scripts/kk/lib/` |
| Multi-chain TypeScript (bridges, balances) | `execution-market/scripts/kk/*.ts` |
| v2 Terraform swarm | `execution-market/terraform/swarm/` |
| Agent identities & wallets | `execution-market/scripts/kk/config/identities.json` |
| Facilitador source code | `x402-rs/src/` |
| Facilitador networks | `x402-rs/src/network.rs` |
| Facilitador ERC-8004 integration | `x402-rs/src/erc8004/` |
| Facilitador payment operator | `x402-rs/src/payment_operator/` |
| MeshRelay IRC integration | `meshrelay/` |
| x402 Python SDK | `uvd-x402-sdk-python/` |
| x402 TypeScript SDK | `uvd-x402-sdk-typescript/` |
| GLUE Token contract (v1/legacy) | `karmakadabra/erc-20/` |
| ERC-8004 contracts (v1/legacy) | `karmakadabra/erc-8004/` |
| v1 deployment scripts | `karmakadabra/scripts/` |
| v2 test suite | `execution-market/scripts/kk/tests/` |

---

## 9. Qué se Reutiliza de v1 para v2

### 9.1 SE REUTILIZA (con adaptaciones)

| Componente v1 | Adaptación Necesaria |
|---------------|---------------------|
| **Terraform ECS Fargate** (`terraform/ecs-fargate/`) | Adaptar variables para 24 agentes, nuevo model de heartbeat, shared container image |
| **VPC, ALB, Route53** | Misma infra, nuevos DNS records para agentes kk-* |
| **ECR repos** | Consolidar en repo compartido (`kk-swarm/openclaw-agent`) |
| **CloudWatch** | Misma configuración, más log groups |
| **Secrets Manager** | Nuevos secrets: `kk/swarm-seed`, `em/x402`, `em/anthropic` |
| **IAM roles** | Adaptar policies para nuevos secrets |
| **Docker Compose** | Actualizar para nuevo stack (sin facilitador local) |
| **Shared libs pattern** | Reescribir para v2 pero misma arquitectura |
| **IRC control plane** | Ya está en v1, evolucionar para MeshRelay |

### 9.2 SE REEMPLAZA

| Componente v1 | Reemplazado Por |
|---------------|----------------|
| GLUE Token (ERC-20 custom) | USDC estándar (multi-chain) |
| ERC-8004 en Fuji testnet | ERC-8004 en Base mainnet |
| 5 system agents (Python) | 6 system agents (v2 services) |
| 48 static user agents | 18 community agents (autónomos) |
| A2A protocol | MeshRelay IRC + OpenClaw |
| Central Marketplace API | Execution Market REST API |
| Facilitador local (docker-compose) | `facilitator.ultravioletadao.xyz` (externo) |
| Pagos con GLUE | Pagos con USDC vía x402 |

### 9.3 NUEVO EN v2 (no existe en v1)

- Coordinator service con 6-factor matching
- Soul Extractor (fusión skills + voice)
- Heartbeat model (wake/execute/sleep cada 15 min)
- Multi-chain fund management (8 chains, 5 stablecoins)
- Bridge infrastructure (deBridge, Squid)
- Supabase swarm state
- MeshRelay IRC integration
- OpenClaw skills framework
- Performance tracker
- Reputation bridge
- Turnstile payment client
- Agent lifecycle management

---

## 10. Los 24 Agentes de v2

### System Agents (6)

| # | Agent | HD Index | ERC-8004 ID | Wallet | Rol |
|---|-------|----------|-------------|--------|-----|
| 0 | kk-coordinator | m/44'/60'/0'/0/0 | 18775 | `0xE66C...` | Squad lead, task routing |
| 1 | kk-karma-hello | m/44'/60'/0'/0/1 | 18776 | `0xa327...` | Data seller, log collection |
| 2 | kk-skill-extractor | m/44'/60'/0'/0/2 | 18777 | `0xE3fB...` | Skill profile extraction |
| 3 | kk-voice-extractor | m/44'/60'/0'/0/3 | 18778 | `0x8E50...` | Voice profile extraction |
| 4 | kk-validator | m/44'/60'/0'/0/4 | 18779 | `0x7a72...` | Quality verification |
| 5 | kk-soul-extractor | m/44'/60'/0'/0/5 | 18895 | `0x04Ea...` | Soul fusion |

### Community Agents (18)

| # | Agent | HD Index | ERC-8004 ID |
|---|-------|----------|-------------|
| 6 | kk-juanjumagalp | 6 | 18896 |
| 7 | kk-elboorja | 7 | 18897 |
| 8 | kk-stovedove | 8 | 18898 |
| 9 | kk-0xroypi | 9 | 18934 |
| 10 | kk-sanvalencia2 | 10 | 18814 |
| 11 | kk-0xjokker | 11 | 18815 |
| 12 | kk-cyberpaisa | 12 | 18816 |
| 13 | kk-cymatix | 13 | 18817 |
| 14 | kk-eljuyan | 14 | 18818 |
| 15 | kk-1nocty | 15 | 18843 |
| 16 | kk-elbitterx | 16 | 18844 |
| 17 | kk-acpm444 | 17 | 18849 |
| 18 | kk-davidtherich | 18 | 18850 |
| 19 | kk-karenngo | 19 | 18894 |
| 20 | kk-datbo0i_lp | 20 | 18904 |
| 21 | kk-psilocibin3 | 21 | 18905 |
| 22 | kk-0xsoulavax | 22 | 18906 |
| 23 | kk-painbrayan | 23 | 18907 |

### Fondos por Agente (~$6.18 USD)

| Chain | USDC | EURC | AUSD | PYUSD | USDT | Total |
|-------|------|------|------|-------|------|-------|
| Monad | $0.75 | - | $0.25 | - | - | $1.00 |
| Arbitrum | $0.75 | - | - | - | $0.20 | $0.95 |
| Avalanche | $0.50 | $0.35 | $0.10 | - | - | $0.95 |
| Base | $0.75 | $0.10 | - | - | - | $0.85 |
| Polygon | $0.50 | - | $0.25 | - | - | $0.75 |
| Optimism | $0.75 | - | - | - | - | $0.75 |
| Celo | $0.02 | - | - | - | $0.45 | $0.47 |
| Ethereum | $0.10 | $0.12 | $0.12 | $0.12 | - | $0.46 |
| **Total** | **$4.12** | **$0.57** | **$0.72** | **$0.12** | **$0.65** | **$6.18** |

**Grand Total**: $148.12 (agentes) + $42.81 (master wallet) = **$190.93 USD**

---

## 11. AWS Secrets (v2)

| Secret ID | Region | Keys | Propósito |
|-----------|--------|------|-----------|
| `kk/swarm-seed` | us-east-2 | `mnemonic` | HD seed para 24 wallets |
| `em/x402` | us-east-2 | `PRIVATE_KEY`, `SQUID_INTEGRATOR_ID` | Master wallet + Squid API |
| `em/anthropic` | us-east-2 | `ANTHROPIC_API_KEY` | LLM API key |

---

## 12. Variables de Entorno (v2)

```bash
# Execution Market API
EM_API_URL=https://api.execution.market
# Wallets (from AWS SM)
WALLET_PRIVATE_KEY=  # AWS SM em/x402
# Supabase (swarm state)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=
# Bridge Providers
SQUID_INTEGRATOR_ID=  # AWS SM em/x402
# RPCs (QuikNode preferred)
BASE_MAINNET_RPC_URL=
ETHEREUM_RPC_URL=
POLYGON_RPC_URL=
ARBITRUM_RPC_URL=
AVALANCHE_RPC_URL=
OPTIMISM_RPC_URL=
CELO_RPC_URL=
MONAD_RPC_URL=
# AI
ANTHROPIC_API_KEY=  # AWS SM em/anthropic
# x402 Facilitator
X402_FACILITATOR_URL=https://facilitator.ultravioletadao.xyz
X402_NETWORK=base
```

---

## 13. Diferencias Clave de Arquitectura

### v1: Servidor Siempre Activo
```
[Agent Container] --always running--> [Serves HTTP]
                                      [Listens for requests]
                                      [Responds to buyers]
```

### v2: Heartbeat Model
```
Every 15 min:
  [Agent Wakes] --> [Check EM for tasks] --> [Execute assigned work]
                --> [Publish data products] --> [Check IRC messages]
                --> [Update health status] --> [Sleep]
```

### v1: Comunicación A2A
```
Buyer --> GET /.well-known/agent-card --> Discover seller
      --> POST /buy --> x402 payment --> Receive data
```

### v2: Comunicación IRC + EM
```
Agent --> IRC (#Agents) --> Announce availability
      --> EM API --> Browse/publish/apply tasks
      --> x402 payment --> Settle on-chain
      --> MeshRelay --> Premium channel access
```

---

## 14. Plan de Migración Propuesto

### Fase 0: Preparación (Actual)

1. [x] Leer handoff document de Execution Market
2. [x] Auditar estado actual de v1
3. [x] Inventariar código v2
4. [x] Crear este documento de estado
5. [ ] Crear branch `v1` con el estado actual
6. [ ] Crear nueva rama master para v2

### Fase 1: Branch Strategy

```bash
# Preservar v1
git checkout master
git checkout -b v1  # Branch permanente de v1
git push origin v1

# Nuevo master para v2
git checkout master
# Aquí se hará la merge de v1 infra + v2 código
```

### Fase 2: Migración de Código v2

1. Copiar `execution-market/scripts/kk/` a la nueva estructura del repo
2. Actualizar import paths (eliminar prefijo `scripts/kk/`)
3. Migrar `execution-market/scripts/kk/lib/*.ts` como `lib/`
4. Migrar `execution-market/terraform/swarm/` adaptándolo con el Terraform existente de v1
5. Setup package.json y requirements.txt

### Fase 3: Fusión de Infraestructura

1. Tomar Terraform de v1 (`terraform/ecs-fargate/`) como base
2. Adaptar para modelo de swarm (shared container image, heartbeat)
3. Actualizar variables para 24 agentes
4. Nuevos secrets en AWS Secrets Manager
5. Actualizar DNS records

### Fase 4: Actualización de Referencias

1. Actualizar CLAUDE.md para v2
2. Actualizar README.md / README.es.md
3. Crear nuevo MASTER_PLAN.md para v2
4. Actualizar contratos (mainnet addresses)
5. Remover referencias a GLUE token, Avalanche Fuji, etc.

### Fase 5: Testing

1. Tests unitarios (migrados de EM)
2. Integration tests
3. Deployment test (ECS Fargate)
4. IRC connectivity test (MeshRelay)
5. x402 payment flow test

---

## 15. Hallazgos de Auditoría v1

### CRITICOS
1. **GLUE Token ya NO existe en el facilitador** - El facilitador v1.33.18 solo procesa USDC y stablecoins estándar. Los agentes de v1 que referencian GLUE token address NO funcionarán.
2. **Network mismatch** - Default es "base-sepolia" pero mucho código aún referencia "fuji", "AVAX", chain_id 43113.
3. **agents/validator/.env tiene valores reales** - Riesgo de seguridad (debería ser solo .env.example).

### IMPORTANTES
4. **Análisis MOCK en skill/voice extractors** - No usan CrewAI real, datos hardcoded.
5. **Puertos inconsistentes** - main.py defaults vs docker-compose (skill-extractor 8085 vs 9004, voice-extractor 8005 vs 9005).
6. **ABI hardcoded** - En base_agent.py los ABIs están inline, no leídos de archivos compilados.
7. **validator-task-def.json en root** - Viola regla de organización.
8. **Build artifacts commitados** - `erc-20/out/`, `erc-8004/contracts/out/` en el repo.
9. **No hay CI/CD** - No se ve .github/workflows/ en el repo.

### POSITIVOS
10. Patrón base_agent bien implementado (herencia limpia).
11. A2A protocol en todos los agentes.
12. Terraform bien organizado con cost-optimization.
13. AWS Secrets Manager bien integrado.
14. IRC Control Plane recién agregado (último commit).
15. 963 tests en v2 con 0 failures.

---

## 16. Facilitador: Capacidades Nuevas (Detalle)

El facilitador ha crecido de ~5 archivos a **38 archivos .rs** con capacidades enterprise:

### 37 Networks Soportadas
- **18 Mainnets**: Base, Ethereum, Polygon, Arbitrum, Optimism, Avalanche, Celo, HyperEVM, Unichain, Monad, BSC, XDC, XRPL EVM, SKALE Base, Scroll, Solana, Fogo, NEAR, Stellar
- **15+ Testnets**: Base Sepolia, Ethereum Sepolia, Polygon Amoy, Arbitrum Sepolia, Optimism Sepolia, Avalanche Fuji, Celo Sepolia, HyperEVM Testnet, Unichain Sepolia, SKALE Base Sepolia, Solana Devnet, Fogo Testnet, NEAR Testnet, Stellar Testnet, Sei + Sei Testnet
- **Feature-gated**: Algorand (mainnet+testnet), Sui (mainnet+testnet)

### Endpoints del Facilitador

**Core x402**:
- `POST /verify` - Verificar pago
- `POST /settle` - Ejecutar pago on-chain
- `POST /escrow/state` - Estado de escrow

**ERC-8004 (Trustless Agents)**:
- `GET|POST /register` - Registro de agentes
- `GET|POST /feedback` - Feedback de reputación
- `POST /feedback/revoke` - Revocar feedback
- `POST /feedback/response` - Responder a feedback
- `GET /reputation/{network}/{agent_id}` - Consultar reputación
- `GET /identity/{network}/{agent_id}` - Consultar identidad

**Bazaar Discovery (NUEVO)**:
- `GET /discovery/resources` - Listar recursos pagados (paginado, filtros)
- `POST /discovery/register` - Registrar recurso

### SDKs Disponibles

| SDK | Version | Capacidades |
|-----|---------|-------------|
| **Python** (uvd-x402-sdk) | 0.14.1 | X402Client, @require_payment decorator, Flask/FastAPI/Django/Lambda, 21 networks, ERC-8004, escrow |
| **TypeScript** (uvd-x402-sdk) | 2.26.0 | X402Client browser, React hooks, wagmi adapter, 6 providers, wallet support |

**Recomendación**: Los agentes KK v2 deberían adoptar `uvd-x402-sdk` (Python) en vez de construir pagos manualmente.

---

## 17. MeshRelay: Detalle de Infraestructura

### Arquitectura (5 componentes en EC2)

```
EC2 ($22/mes, t3.small)
├── InspIRCd (:6667/:6697) -- Servidor IRC
├── Anope Services -- NickServ, ChanServ, OperServ, BotServ
├── Bridge (:8080) -- WebSocket/REST para web clients
├── Turnstile (:8090) -- x402 payment gateway
└── Unified API (:8100) -- Express + MCP + Swagger
```

### Canales con Precios (Turnstile)

| Canal | Precio | Duración | Slots |
|-------|--------|----------|-------|
| #alpha-test | $0.10 USDC | 30 min | 20 |
| #kk-consultas | $0.25 USDC | 30 min | 100 |
| #kk-skills | $0.50 USDC | 45 min | 30 |
| #kk-alpha | $1.00 USDC | 60 min | 50 |
| #abra-alpha | $1.00 USDC | 60 min | 50 |

### 9 MCP Tools

`meshrelay_get_stats`, `meshrelay_list_channels`, `meshrelay_get_messages`, `meshrelay_list_paid_channels`, `meshrelay_get_paid_channel`, `meshrelay_get_sessions`, `meshrelay_get_agent`, `meshrelay_list_agents`, `meshrelay_health`

---

## 18. Agentes Standalone: Data Layer

### Relación entre Repos

```
STANDALONE (Producción, generan datos)     KK v1/v2 (Commerce, venden datos)
┌──────────────────────────┐               ┌─────────────────────────┐
│ cursor/abracadabra       │               │ agents/abracadabra      │
│  - 251KB monolito        │──genera──>    │  - Microservicio x402   │
│  - 70+ streams           │  datos        │  - Vende transcripciones│
│  - AWS Transcribe+Whisper│               │                         │
│  - analytics.db          │               │                         │
├──────────────────────────┤               ├─────────────────────────┤
│ cursor/karma-hello       │               │ agents/karma-hello      │
│  - 500KB+ código         │──genera──>    │  - Microservicio x402   │
│  - Chat-to-Earn bot      │  datos        │  - Vende chat logs      │
│  - Twitch+Kick           │               │                         │
│  - 10 CrewAI agents      │               │                         │
│  - MongoDB dual write    │               │                         │
└──────────────────────────┘               └─────────────────────────┘
           │                                          │
           └──────────────┐      ┌────────────────────┘
                          ▼      ▼
                 ┌─────────────────────┐
                 │    MeshRelay IRC    │
                 │  (Communication)    │
                 │  irc.meshrelay.xyz  │
                 │  + x402 gated      │
                 │  + MCP tools       │
                 └─────────────────────┘
```

### Abracadabra Standalone (`Z:\ultravioleta\ai\cursor\abracadabra`)
- **main.py**: 251KB monolito (~5,500 líneas)
- **70+ streams** procesados, 640+ topics indexados
- **Pipeline**: download Twitch -> transcription (AWS Transcribe + Whisper dual) -> AI analysis -> content generation -> distribution
- **Outputs**: transcripciones, análisis, imágenes, podcasts, música, clips, tweets, posts Telegram
- **LLMs**: GPT-4o, Claude Sonnet, DALL-E 3, faster-whisper large-v3 (CUDA)
- **Estado**: PRODUCCION, uso activo (último: 2026-02-22)

### Karma Hello Standalone (`Z:\ultravioleta\ai\cursor\karma-hello`)
- **Código**: 500KB+ total, bien modularizado
- **Bot Chat-to-Earn**: Twitch + Kick multi-plataforma
- **AI Evaluation**: Cada mensaje evaluado por OpenAI/Anthropic/Ollama
- **Anti-Spam**: Multi-capa (farming, AI detection, copy detection, blacklist)
- **10 CrewAI agents** especializados
- **Event-driven** con event bus async
- **MongoDB dual write** (local + cloud)
- **Estado**: PRODUCCION, corriendo 24/7 (último debug.log: 2026-02-23)

---

## 19. v2: Estado de Tests y Deployment

### Tests: 963 passing, 0 failures

| Suite | Tests | Cobertura |
|-------|-------|-----------|
| reputation_bridge | 78 | 3-layer reputation system |
| agent_lifecycle | 84 | FSM states + circuit breaker |
| irc_client | 70 | IRC protocol + KK extensions |
| eip8128_signer | 68 | Crypto roundtrips |
| memory_bridge | 63 | Local + Acontext bridge |
| observability | 57 | Health scores + trends |
| performance_tracker | 45 | 5-factor matching |
| acontext_client | 42 | API wrapper |
| em_client | 33 | EM API interactions |
| balance_monitor | 32 | Multi-chain monitoring |
| Otros (17 suites) | 391 | Integration, chaos, services |

### Blockers de Deployment
1. ~$3 adicionales de funding para agentes
2. WebSocket gateway fix pendiente
3. Branch merge execution-market -> karmacadabra pendiente

---

## 20. Resumen de Gaps Críticos para Migración

| Gap | Impacto | Solución |
|-----|---------|----------|
| GLUE Token eliminado del facilitador | Agentes v1 no pueden pagar | Migrar a USDC |
| Contratos en testnet | No sirven en producción | Usar CREATE2 mainnet addresses |
| 48 user agents estáticos | No sirven para v2 | Reemplazar con 18 community agents autónomos |
| A2A protocol | No existe en v2 | Usar MeshRelay IRC + OpenClaw |
| Facilitador local en docker-compose | No necesario | Usar facilitator.ultravioletadao.xyz |
| Shared libs (base_agent.py) | Diseñadas para v1 | Reescribir usando uvd-x402-sdk |
| Auth por API key | Inseguro | Migrar a EIP-8128 wallet signatures |
| Single-chain (Fuji/Base Sepolia) | Limitado | Multi-chain (8 mainnets) |
| Tests mínimos en v1 | Riesgo | Portar 963 tests de v2 |

---

*Generado 2026-02-23 por Claude Code (Opus 4.6) con equipo de 4 agentes exploradores.*
*Fuentes: KarmaCadabra repo, Execution Market repo, x402-rs repo, MeshRelay repo, uvd-x402-sdk repos, handoff document.*
*Agentes: v1-auditor (auditoría v1), em-analyzer (inventario v2), facilitator-analyzer (x402-rs + SDKs), mesh-agents-analyzer (MeshRelay + standalone agents).*
